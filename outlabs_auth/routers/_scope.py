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
from typing import Any, Callable, Iterable, Optional, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
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


async def _load_auth_result_api_key(
    auth: Any,
    session: AsyncSession,
    auth_result: dict[str, Any],
) -> Optional[Any]:
    api_key = auth_result.get("api_key")
    if api_key is not None:
        return api_key
    raw_key_id = (auth_result.get("metadata") or {}).get("key_id")
    if not raw_key_id or getattr(auth, "api_key_service", None) is None:
        return None
    try:
        return await auth.api_key_service.get_api_key(session, UUID(str(raw_key_id)))
    except (TypeError, ValueError):
        return None


def _intersect_user_and_key_scope(user_scope: dict[str, Any], key_scope: dict[str, Any]) -> dict[str, Any]:
    """A personal key anchored at an entity never reaches past its owner or its anchor."""
    if user_scope.get("is_global"):
        # A global owner's anchored key keeps the key's own anchor scope.
        return key_scope
    key_entity_ids = scope_entity_ids(key_scope)
    entity_ids = sorted(entity_id for entity_id in scope_entity_ids(user_scope) if entity_id in key_entity_ids)
    allowed = set(entity_ids)
    return {
        **user_scope,
        "is_global": False,
        "api_key_id": key_scope.get("api_key_id"),
        "api_key_entity_id": key_scope.get("api_key_entity_id"),
        "entity_ids": entity_ids,
        "root_entity_ids": [str(e) for e in (user_scope.get("root_entity_ids") or []) if str(e) in allowed],
        "direct_entity_ids": [str(e) for e in (user_scope.get("direct_entity_ids") or []) if str(e) in allowed],
    }


async def resolve_principal_scope(
    auth: Any,
    session: AsyncSession,
    auth_result: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve the tenant scope of any authenticated principal.

    * a human (JWT) resolves to the user's DD-056 scope;
    * a personal API key resolves to its owner's DD-056 scope — never to
      global scope just because the key has no entity anchor — and, when the
      key is anchored at an entity, to the part of that scope the anchor
      covers (a superuser owner stays global);
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
        user_scope = await resolve_user_scope(auth, session, user)
        if source != "api_key" or bool(getattr(user, "is_superuser", False)):
            return user_scope
        raw_key = auth_result.get("api_key")
        if raw_key is not None:
            anchored = getattr(raw_key, "entity_id", None) is not None
        else:
            anchored = bool((auth_result.get("metadata") or {}).get("entity_id"))
        if not anchored:
            return user_scope
        api_key = await _load_auth_result_api_key(auth, session, auth_result)
        if api_key is None:
            # Anchored key we cannot load: fail closed rather than widen.
            return _empty_scope(source)
        key_scope = await auth.access_scope_service.resolve_for_api_key(
            session,
            api_key=api_key,
            include_member_user_ids=False,
        )
        return _intersect_user_and_key_scope(user_scope, cast(dict[str, Any], key_scope.to_dict()))

    if source == "service_token":
        return _global_scope(source)

    if source == "api_key":
        api_key = await _load_auth_result_api_key(auth, session, auth_result)
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


async def entity_visible_in_scope(
    session: AsyncSession,
    scope: dict[str, Any],
    entity_id: Any,
    *,
    max_depth: int = 64,
) -> bool:
    """Whether an entity is inside the scope, including archived entities.

    Scope entity sets come from the closure table, and archiving an entity
    removes its closure rows. An archived entity therefore stays visible when
    its nearest still-linked ancestor is in scope (its tenant can still open
    it, e.g. from history), while archived roots remain global-only.
    """
    if entity_in_scope(scope, entity_id):
        return True
    if not scope_entity_ids(scope):
        return False
    from outlabs_auth.models.sql.entity import Entity

    current = await session.get(Entity, entity_id)
    for _ in range(max_depth):
        if current is None or getattr(current, "status", "active") == "active":
            return False
        parent_id = getattr(current, "parent_id", None)
        if parent_id is None:
            return False
        if entity_in_scope(scope, parent_id):
            return True
        current = await session.get(Entity, parent_id)
    return False


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
    *,
    scope: Optional[dict[str, Any]] = None,
) -> Any:
    """Load a target user and apply the DD-056 read predicate for any principal.

    Self-requests always pass. Out-of-scope users answer 404 exactly like
    nonexistent ones. ``scope`` reuses an already-resolved principal scope.
    """
    target_user = await auth.user_service.get_user_by_id(session, target_user_id)
    if not target_user:
        raise user_not_found()
    if not scope_enforced(auth):
        return target_user

    actor_user_id = (auth_result or {}).get("user_id")
    if actor_user_id is not None and str(actor_user_id) == str(target_user.id):
        return target_user

    if scope is None:
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


async def user_holds_global_scope(auth: Any, session: AsyncSession, user: Any) -> bool:
    """Whether a user spans every tree: superuser or active direct system-wide role (DD-056)."""
    if bool(getattr(user, "is_superuser", False)):
        return True
    if not auth.config.enable_entity_hierarchy:
        return False
    scope = await resolve_user_scope(auth, session, user)
    return bool(scope.get("is_global"))


async def require_entity_visible_or_404(
    auth: Any,
    session: AsyncSession,
    auth_result: Optional[dict[str, Any]],
    entity_id: Any,
    *,
    scope: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """404 unless the entity is inside the principal's scope (DD-061).

    Returns the resolved scope so callers can reuse it.
    """
    if scope is None:
        if not scope_enforced(auth):
            return _global_scope("unscoped")
        scope = await resolve_principal_scope(auth, session, auth_result)
    if scope.get("is_global"):
        return scope
    if not await entity_visible_in_scope(session, scope, entity_id):
        raise entity_not_found()
    return scope


def entity_scope_guard(auth: Any, entity_id_field: str, *, source: str = "path") -> Callable[..., Any]:
    """FastAPI dependency: answer 404 for an entity outside the caller's scope.

    Declare it *before* an entity-context permission dependency
    (``require_tree_permission`` / ``require_entity_permission``) so a
    tenant-scoped caller learns nothing about another tenant's entities: out
    of scope and nonexistent IDs both answer 404 (DD-061), while an in-scope
    entity still gets the permission check's 403 when the caller lacks the
    permission. ``source`` is ``path``, ``query`` or ``body``; a missing or
    malformed value is left to the permission dependency.
    """
    if source not in ("path", "query", "body"):
        raise ValueError("source must be one of: path, query, body")

    async def dependency(
        request: Request,
        session: AsyncSession = Depends(auth.uow),
        auth_result: Any = Depends(auth.deps.require_auth()),
    ) -> None:
        if not scope_enforced(auth):
            return None
        if source == "path":
            raw = request.path_params.get(entity_id_field)
        elif source == "query":
            raw = request.query_params.get(entity_id_field)
        else:
            try:
                body = await request.json()
            except Exception:
                return None
            raw = body.get(entity_id_field) if isinstance(body, dict) else None
        if raw in (None, ""):
            return None
        try:
            entity_id = raw if isinstance(raw, UUID) else UUID(str(raw))
        except (TypeError, ValueError):
            return None
        await require_entity_visible_or_404(auth, session, auth_result, entity_id)
        return None

    return dependency


async def require_global_actor_for_system_wide_roles(
    auth: Any,
    session: AsyncSession,
    *,
    actor_user: Optional[Any],
    role_ids: Iterable[UUID],
    auth_result: Optional[dict[str, Any]] = None,
) -> None:
    """Directly granting a system-wide role grants global scope (DD-056).

    Only an actor who already spans every tree may make that grant: a
    superuser, a system-wide role holder, or — for host automation with no
    user record — a global principal (service token, unanchored integration
    principal) identified by ``auth_result``. Entity-membership role grants
    are not affected: membership roles never widen scope.
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
    elif auth_result:
        scope = await resolve_principal_scope(auth, session, auth_result)
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
