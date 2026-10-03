"""Shared authorization helpers for router-layer delegation checks.

Implements *delegation containment* ("you can't grant what you don't hold"): a
user may only attach permissions to a role — or assign a role whose permissions
— that they themselves already possess. Superusers bypass naturally because
``PermissionService.get_user_permissions`` returns ``["*:*"]`` for them.

This closes the privilege-escalation chain re-verified in
``docs/SECURITY_AUDIT_2026-08-02.md``: without it, any holder of
``role:create`` / ``role:update`` / ``user:update`` could mint or assign a role
carrying ``*:*`` and escalate to superuser-equivalent access.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import PermissionDeniedError
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.utils.lifecycle import lifecycle_update_grants_access

__all__ = [
    "grantor_missing_permissions",
    "lifecycle_update_grants_access",
    "require_can_delegate_direct_roles",
    "require_can_delegate_permissions",
    "require_can_delegate_roles",
]


def grantor_missing_permissions(required: Iterable[str], granted: Set[str]) -> List[str]:
    """Return the sorted permission names in ``required`` that ``granted`` does not cover.

    Wildcard (``*:*``, ``resource:*``) and ``_tree`` / ``_all`` scope semantics are
    delegated to :meth:`PermissionService._permission_set_allows`, so a grantor
    holding ``post:*`` may grant ``post:read`` and a grantor holding ``*:*`` may
    grant anything.
    """
    return sorted({p for p in required if not PermissionService._permission_set_allows(p, granted)})


async def require_can_delegate_permissions(
    session: AsyncSession,
    *,
    auth,
    actor_user_id: UUID,
    permission_names: Iterable[str],
    entity_id: Optional[UUID] = None,
) -> None:
    """Raise :class:`PermissionDeniedError` if the actor would grant a permission they lack.

    Args:
        session: Active DB session.
        auth: The ``OutlabsAuth`` instance (provides ``permission_service``).
        actor_user_id: The acting (granting) user's id.
        permission_names: Permission names about to be attached to a role or
            assigned via a role.
        entity_id: Entity where the grant will take effect. ``None`` means
            system-wide/direct RBAC and excludes entity-local grants.
    """
    names = [p for p in permission_names if p]
    if not names:
        return
    granted: Set[str] = set(
        await auth.permission_service.get_effective_permission_names(
            session,
            actor_user_id,
            entity_id=entity_id,
            candidate_permission_names=names,
        )
    )
    missing = sorted(set(names) - granted)
    if missing:
        raise PermissionDeniedError(
            message="You cannot grant permissions you do not hold",
            details={"missing_permissions": missing},
        )


async def require_can_delegate_roles(
    session: AsyncSession,
    *,
    auth: Any,
    actor_user_id: UUID,
    role_ids: Iterable[UUID],
    entity_id: Optional[UUID] = None,
) -> None:
    """Require containment for every permission carried by ``role_ids``."""
    permission_names: Set[str] = set()
    target_entity_type: Optional[str] = None
    if entity_id is not None:
        target_entity = await session.get(Entity, entity_id)
        target_entity_type = (
            target_entity.entity_type.lower() if target_entity is not None and target_entity.entity_type else None
        )

    for role_id in set(role_ids):
        permission_names.update(await auth.role_service.get_role_permission_names(session, role_id))
        entity_type_permissions = await auth.role_service.get_role_entity_type_permission_names(session, role_id)
        if target_entity_type is None:
            for contextual_names in entity_type_permissions.values():
                permission_names.update(contextual_names)
        else:
            permission_names.update(entity_type_permissions.get(target_entity_type, []))
    await require_can_delegate_permissions(
        session,
        auth=auth,
        actor_user_id=actor_user_id,
        permission_names=permission_names,
        entity_id=entity_id,
    )


def _direct_role_grant_context(auth: Any, role: Any) -> Optional[UUID]:
    """Entity where a *direct* role's grants take effect for SEC-2 containment.

    With tenant scope enforced (EnterpriseRBAC, ``enforce_user_scope``), a
    direct org-scoped role grants inside its root's tree and an entity-local
    one inside its scope entity (DD-054 / DD-061 decision 10), so the grantor
    must hold the permissions *there*. A system-wide role, SimpleRBAC and the
    ``enforce_user_scope=False`` escape hatch keep the flat (no entity) check.
    """
    config = getattr(auth, "config", None)
    if not (getattr(config, "enable_entity_hierarchy", False) and getattr(config, "enforce_user_scope", True)):
        return None
    return getattr(role, "scope_entity_id", None) or getattr(role, "root_entity_id", None)


async def require_can_delegate_direct_roles(
    session: AsyncSession,
    *,
    auth: Any,
    actor_user_id: UUID,
    roles: Iterable[Any],
) -> None:
    """SEC-2 containment for direct (``UserRoleMembership``) role grants.

    Every permission a role can carry — its base permissions and its
    entity-type-contextual ones, since a direct role reaches entities of every
    type in its tree — must be held by the grantor at the role's own entity
    context (see :func:`_direct_role_grant_context`).
    """
    for role in roles:
        permission_names: Set[str] = set(await auth.role_service.get_role_permission_names(session, role.id))
        contextual = await auth.role_service.get_role_entity_type_permission_names(session, role.id)
        for names in contextual.values():
            permission_names.update(names)
        await require_can_delegate_permissions(
            session,
            auth=auth,
            actor_user_id=actor_user_id,
            permission_names=permission_names,
            entity_id=_direct_role_grant_context(auth, role),
        )
