"""Shared tenant-scope helpers for router factories (DD-056, DD-061).

DD-056 introduced tenant isolation on the user-management routes. The same
predicate now also protects every other route that reads or writes another
user's identity graph (memberships, effective permissions) and the entity
routes. Keeping the predicate in one module guarantees a single contract:

* ``is_global`` actors (superusers, holders of an active system-wide role,
  platform-global integration principals, service tokens) span every tree;
* everyone else sees only the entities in their resolved access scope and the
  users rooted in, or holding an active membership in, those entities;
* out-of-scope targets answer **404**, indistinguishable from nonexistent ones.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import PermissionDeniedError
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.models.sql.role import Role


def _global_scope(source: str) -> dict[str, Any]:
    return {
        "source": source,
        "is_global": True,
        "entity_ids": [],
        "root_entity_ids": [],
        "direct_entity_ids": [],
    }


def _empty_scope(source: str) -> dict[str, Any]:
    return {
        "source": source,
        "is_global": False,
        "entity_ids": [],
        "root_entity_ids": [],
        "direct_entity_ids": [],
    }


def scope_enforced(auth: Any) -> bool:
    """Tenant scoping applies to EnterpriseRBAC hosts with ``enforce_user_scope`` on."""
    return bool(auth.config.enable_entity_hierarchy and auth.config.enforce_user_scope)


async def resolve_user_scope(auth: Any, session: AsyncSession, user: Any) -> dict[str, Any]:
    """Resolve the tenant scope of a human user exactly as DD-056 does for user routes."""
    if not auth.config.enable_entity_hierarchy:
        return _global_scope("jwt")
    scope = cast(
        dict[str, Any],
        await auth.access_scope_service.resolve_for_auth_result(
            session,
            {"source": "jwt", "user_id": str(user.id), "user": user},
            include_member_user_ids=False,
        ),
    )
    return scope


async def resolve_principal_scope(
    auth: Any,
    session: AsyncSession,
    auth_result: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve the tenant scope of any authenticated principal.

    * a human (JWT or personal API key) resolves to the user's DD-056 scope;
    * an integration principal resolves to its key anchor (no anchor = global);
    * a host-minted service token is a platform credential with no tenant
      anchor and is treated as global;
    * anything else resolves to an empty, non-global scope (deny).
    """
    if not auth.config.enable_entity_hierarchy:
        return _global_scope("simple")
    if not auth_result:
        return _empty_scope("anonymous")

    source = str(auth_result.get("source") or "unknown")
    user = auth_result.get("user")
    if user is None and auth_result.get("user_id"):
        try:
            user = await auth.user_service.get_user_by_id(session, UUID(str(auth_result["user_id"])))
        except (TypeError, ValueError):
            user = None
    if user is not None:
        return await resolve_user_scope(auth, session, user)

    if source == "service_token":
        return _global_scope(source)

    if source == "api_key":
        api_key = auth_result.get("api_key")
        if api_key is None:
            raw_key_id = (auth_result.get("metadata") or {}).get("key_id")
            if raw_key_id and getattr(auth, "api_key_service", None) is not None:
                try:
                    api_key = await auth.api_key_service.get_api_key(session, UUID(str(raw_key_id)))
                except (TypeError, ValueError):
                    api_key = None
        if api_key is None:
            return _empty_scope(source)
        resolved = await auth.access_scope_service.resolve_for_api_key(
            session,
            api_key=api_key,
            include_member_user_ids=False,
        )
        return cast(dict[str, Any], resolved.to_dict())

    return _empty_scope(source)


def scope_entity_ids(scope: dict[str, Any]) -> set[str]:
    return {str(entity_id) for entity_id in (scope.get("entity_ids") or [])}


def entity_in_scope(scope: dict[str, Any], entity_id: Any) -> bool:
    if scope.get("is_global"):
        return True
    if entity_id is None:
        return False
    return str(entity_id) in scope_entity_ids(scope)


async def target_user_in_scope(
    session: AsyncSession,
    target_user: Any,
    scope: dict[str, Any],
) -> bool:
    """DD-056 predicate, evaluated from the target side (O(target's memberships))."""
    if scope.get("is_global"):
        return True
    entity_ids = scope_entity_ids(scope)
    if not entity_ids:
        return False

    target_root_entity_id = getattr(target_user, "root_entity_id", None)
    if target_root_entity_id is not None and str(target_root_entity_id) in entity_ids:
        return True

    now = datetime.now(timezone.utc)
    stmt = select(cast(Any, EntityMembership.entity_id)).where(
        cast(Any, EntityMembership.user_id) == target_user.id,
        cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE,
        or_(
            cast(Any, EntityMembership.valid_from).is_(None),
            cast(Any, EntityMembership.valid_from) <= now,
        ),
        or_(
            cast(Any, EntityMembership.valid_until).is_(None),
            cast(Any, EntityMembership.valid_until) >= now,
        ),
    )
    result = await session.execute(stmt)
    target_entity_ids = {str(entity_id) for (entity_id,) in result.all() if entity_id is not None}
    return bool(target_entity_ids & entity_ids)


def user_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


def entity_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")


async def get_visible_user_or_404(
    auth: Any,
    session: AsyncSession,
    auth_result: Optional[dict[str, Any]],
    target_user_id: UUID,
) -> Any:
    """Load a target user and apply the DD-056 read predicate for any principal.

    Self-requests always pass. Out-of-scope users answer 404 exactly like
    nonexistent ones.
    """
    target_user = await auth.user_service.get_user_by_id(session, target_user_id)
    if not target_user:
        raise user_not_found()
    if not scope_enforced(auth):
        return target_user

    actor_user_id = (auth_result or {}).get("user_id")
    if actor_user_id is not None and str(actor_user_id) == str(target_user.id):
        return target_user

    scope = await resolve_principal_scope(auth, session, auth_result)
    if scope.get("is_global"):
        return target_user
    if not await target_user_in_scope(session, target_user, scope):
        raise user_not_found()
    return target_user


def role_is_system_wide(role: Any) -> bool:
    """A system-wide role (DD-056) is the explicit global-scope grant."""
    return bool(
        getattr(role, "is_global", False)
        and getattr(role, "root_entity_id", None) is None
        and getattr(role, "scope_entity_id", None) is None
    )


async def require_global_actor_for_system_wide_roles(
    auth: Any,
    session: AsyncSession,
    *,
    actor_user: Optional[Any],
    role_ids: Iterable[UUID],
) -> None:
    """Directly granting a system-wide role grants global scope (DD-056).

    Only an actor who already spans every tree (superuser or system-wide role
    holder) may make that grant. Entity-membership role grants are not
    affected: membership roles never widen scope.
    """
    if not scope_enforced(auth):
        return
    unique_role_ids = {UUID(str(role_id)) for role_id in role_ids}
    if not unique_role_ids:
        return
    result = await session.execute(select(Role).where(cast(Any, Role.id).in_(sorted(unique_role_ids, key=str))))
    system_wide_ids = sorted(str(role.id) for role in result.scalars().all() if role_is_system_wide(role))
    if not system_wide_ids:
        return
    if actor_user is not None:
        if bool(getattr(actor_user, "is_superuser", False)):
            return
        scope = await resolve_user_scope(auth, session, actor_user)
        if scope.get("is_global"):
            return
    raise PermissionDeniedError(
        message="Only global administrators can grant system-wide roles directly",
        details={"system_wide_role_ids": system_wide_ids},
    )


async def actor_is_global(auth: Any, session: AsyncSession, auth_result: Optional[dict[str, Any]]) -> bool:
    if not auth.config.enable_entity_hierarchy:
        return True
    scope = await resolve_principal_scope(auth, session, auth_result)
    return bool(scope.get("is_global"))


async def resolve_root_for_scoped_create(
    auth: Any,
    session: AsyncSession,
    *,
    actor_user: Optional[Any],
    auth_result: Optional[dict[str, Any]] = None,
    requested_root_entity_id: Optional[UUID],
) -> Optional[UUID]:
    """Apply the DD-056 creation rule to a new account's root entity.

    Global actors keep full control (any root, or none). A tenant-scoped actor
    may only root a new account at an entity inside its own scope; when it
    names no root the account inherits the actor's own root so the new user
    stays visible to (and manageable by) the tenant that created it. An actor
    with no root of its own must name an in-scope root explicitly.
    """
    if not scope_enforced(auth):
        return requested_root_entity_id
    if actor_user is not None:
        if bool(getattr(actor_user, "is_superuser", False)):
            return requested_root_entity_id
        scope = await resolve_user_scope(auth, session, actor_user)
    else:
        scope = await resolve_principal_scope(auth, session, auth_result)
    if scope.get("is_global"):
        return requested_root_entity_id

    if requested_root_entity_id is None:
        actor_root_entity_id = getattr(actor_user, "root_entity_id", None) if actor_user is not None else None
        if actor_root_entity_id is not None and entity_in_scope(scope, actor_root_entity_id):
            return cast(UUID, actor_root_entity_id)
        raise PermissionDeniedError(
            message=(
                "Tenant-scoped administrators must place new accounts inside their own scope: "
                "provide a root entity (or an entity membership) within your accessible scope"
            ),
            details={"reason": "root_entity_required"},
        )

    if not entity_in_scope(scope, requested_root_entity_id):
        raise PermissionDeniedError(
            message="Root entity is outside your accessible entity scope",
            details={"root_entity_id": str(requested_root_entity_id)},
        )
    return requested_root_entity_id
