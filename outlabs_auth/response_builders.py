"""Helpers for building API responses from SQL models."""

from collections.abc import Mapping
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.enums import RoleScope
from outlabs_auth.schemas.permission import PermissionResponse
from outlabs_auth.schemas.role import RoleResponse, RoleScopeEnum
from outlabs_auth.schemas.user import UserResponse


def serialize_status(status_val: Any) -> str:
    """Return enum-like status values as plain strings."""
    return status_val.value if hasattr(status_val, "value") else str(status_val)


def build_user_response(user: Any, root_entity_name: Optional[str] = None) -> UserResponse:
    """Build a consistent user response from a SQL model."""
    derived_root_entity_name = root_entity_name
    if derived_root_entity_name is None:
        root_entity = getattr(user, "__dict__", {}).get("root_entity")
        derived_root_entity_name = getattr(root_entity, "display_name", None)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=serialize_status(user.status),
        email_verified=user.email_verified,
        is_superuser=user.is_superuser,
        avatar_url=getattr(user, "avatar_url", None),
        phone=getattr(user, "phone", None),
        locale=getattr(user, "locale", None),
        timezone=getattr(user, "timezone", None),
        root_entity_id=str(user.root_entity_id) if getattr(user, "root_entity_id", None) else None,
        root_entity_name=derived_root_entity_name,
        created_at=getattr(user, "created_at", None),
        updated_at=getattr(user, "updated_at", None),
        last_login=getattr(user, "last_login", None),
        last_activity=getattr(user, "last_activity", None),
        last_password_change=getattr(user, "last_password_change", None),
        suspended_until=getattr(user, "suspended_until", None),
        locked_until=getattr(user, "locked_until", None),
        deleted_at=getattr(user, "deleted_at", None),
    )


async def build_user_responses(
    session: AsyncSession,
    users: list[Any],
) -> list[UserResponse]:
    """Build user responses and hydrate root entity names when only IDs are loaded."""
    from outlabs_auth.models.sql.entity import Entity

    missing_root_entity_ids = {
        user.root_entity_id
        for user in users
        if getattr(user, "root_entity_id", None)
        and getattr(getattr(user, "__dict__", {}).get("root_entity"), "display_name", None) is None
    }

    root_entity_names: dict[Any, str] = {}
    if missing_root_entity_ids:
        result = await session.execute(
            select(Entity.id, Entity.display_name).where(Entity.id.in_(missing_root_entity_ids))
        )
        root_entity_names = {
            entity_id: display_name
            for entity_id, display_name in result.all()
        }

    return [
        build_user_response(
            user,
            root_entity_name=(
                getattr(getattr(user, "__dict__", {}).get("root_entity"), "display_name", None)
                or root_entity_names.get(getattr(user, "root_entity_id", None))
            ),
        )
        for user in users
    ]


async def build_user_response_async(
    session: AsyncSession,
    user: Any,
) -> UserResponse:
    """Build a single user response with a resolved root entity name."""
    return (await build_user_responses(session, [user]))[0]


async def build_role_responses(
    session: AsyncSession,
    roles: list[Any],
    permission_names_by_role_id: Optional[Mapping[Any, list[str]]] = None,
) -> list[RoleResponse]:
    """Build role responses while resolving related entity names in bulk."""
    from outlabs_auth.models.sql.entity import Entity

    missing_entity_ids = {
        entity_id
        for role in roles
        for entity_id, relationship_name in (
            (getattr(role, "root_entity_id", None), "root_entity"),
            (getattr(role, "scope_entity_id", None), "scope_entity"),
        )
        if entity_id
        and getattr(getattr(role, "__dict__", {}).get(relationship_name), "display_name", None) is None
    }

    entity_names: dict[Any, str] = {}
    if missing_entity_ids:
        result = await session.execute(
            select(Entity.id, Entity.display_name).where(Entity.id.in_(missing_entity_ids))
        )
        entity_names = {entity_id: display_name for entity_id, display_name in result.all()}

    responses: list[RoleResponse] = []
    for role in roles:
        root_entity_name = (
            getattr(getattr(role, "__dict__", {}).get("root_entity"), "display_name", None)
            or entity_names.get(getattr(role, "root_entity_id", None))
        )
        scope_entity_name = (
            getattr(getattr(role, "__dict__", {}).get("scope_entity"), "display_name", None)
            or entity_names.get(getattr(role, "scope_entity_id", None))
        )
        resolved_permissions = (
            permission_names_by_role_id.get(getattr(role, "id"))
            if permission_names_by_role_id is not None
            else [
                permission.name
                for permission in (getattr(role, "permissions", []) or [])
                if getattr(getattr(permission, "status", None), "value", getattr(permission, "status", None))
                != "archived"
                and getattr(permission, "name", None)
            ]
        )

        scope_value = RoleScopeEnum.HIERARCHY
        if getattr(role, "scope", None) == RoleScope.ENTITY_ONLY:
            scope_value = RoleScopeEnum.ENTITY_ONLY

        responses.append(
            RoleResponse(
                id=str(role.id),
                name=role.name,
                display_name=role.display_name,
                description=role.description,
                permissions=resolved_permissions or [],
                is_system_role=role.is_system_role,
                is_global=role.is_global,
                status=serialize_status(getattr(role, "status", None)),
                root_entity_id=str(role.root_entity_id) if role.root_entity_id else None,
                root_entity_name=root_entity_name,
                assignable_at_types=list(getattr(role, "assignable_at_types", []) or []),
                scope_entity_id=str(role.scope_entity_id) if role.scope_entity_id else None,
                scope_entity_name=scope_entity_name,
                scope=scope_value,
                is_auto_assigned=role.is_auto_assigned,
            )
        )

    return responses


async def build_role_response(
    session: AsyncSession,
    role: Any,
    permission_names: Optional[list[str]] = None,
) -> RoleResponse:
    """Build a consistent role response from a SQL model."""
    responses = await build_role_responses(
        session,
        [role],
        permission_names_by_role_id=(
            {getattr(role, "id"): permission_names} if permission_names is not None else None
        ),
    )
    return responses[0]


def build_permission_response(permission: Any) -> PermissionResponse:
    """Build a consistent permission response from a SQL model."""
    return PermissionResponse(
        id=str(permission.id),
        name=permission.name,
        display_name=permission.display_name,
        description=permission.description,
        resource=permission.resource,
        action=permission.action,
        scope=permission.scope,
        is_system=permission.is_system,
        status=serialize_status(getattr(permission, "status", None)),
        is_active=bool(getattr(permission, "is_active", False)),
        tags=[tag.name for tag in permission.tags] if getattr(permission, "tags", None) else [],
        metadata={},
    )
