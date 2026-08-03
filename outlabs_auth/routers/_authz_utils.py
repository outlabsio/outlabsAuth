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
