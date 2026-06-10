"""Shared authorization helpers for router-layer delegation checks.

Implements *delegation containment* ("you can't grant what you don't hold"): a
user may only attach permissions to a role — or assign a role whose permissions
— that they themselves already possess. Superusers bypass naturally because
``PermissionService.get_user_permissions`` returns ``["*:*"]`` for them.

This closes the privilege-escalation chain documented in
``docs/SECURITY_AUDIT_2026-06-10.md`` (SEC-2/SEC-3): without it, any holder of
``role:create`` / ``role:update`` / ``user:update`` could mint or assign a role
carrying ``*:*`` and escalate to superuser-equivalent access.
"""
from __future__ import annotations

from typing import Iterable, List, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import PermissionDeniedError
from outlabs_auth.services.permission import PermissionService


def grantor_missing_permissions(required: Iterable[str], granted: Set[str]) -> List[str]:
    """Return the sorted permission names in ``required`` that ``granted`` does not cover.

    Wildcard (``*:*``, ``resource:*``) and ``_tree`` / ``_all`` scope semantics are
    delegated to :meth:`PermissionService._permission_set_allows`, so a grantor
    holding ``post:*`` may grant ``post:read`` and a grantor holding ``*:*`` may
    grant anything.
    """
    return sorted(
        {p for p in required if not PermissionService._permission_set_allows(p, granted)}
    )


async def require_can_delegate_permissions(
    session: AsyncSession,
    *,
    auth,
    actor_user_id: UUID,
    permission_names: Iterable[str],
) -> None:
    """Raise :class:`PermissionDeniedError` if the actor would grant a permission they lack.

    Args:
        session: Active DB session.
        auth: The ``OutlabsAuth`` instance (provides ``permission_service``).
        actor_user_id: The acting (granting) user's id.
        permission_names: Permission names about to be attached to a role or
            assigned via a role.
    """
    names = [p for p in permission_names if p]
    if not names:
        return
    granted: Set[str] = set(
        await auth.permission_service.get_user_permissions(session, actor_user_id)
    )
    missing = grantor_missing_permissions(names, granted)
    if missing:
        raise PermissionDeniedError(
            message="You cannot grant permissions you do not hold",
            details={"missing_permissions": missing},
        )
