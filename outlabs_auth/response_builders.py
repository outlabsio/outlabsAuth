"""Helpers for building API responses from SQL models."""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.enums import RoleScope
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


async def build_role_response(
    session: AsyncSession,
    role: Any,
    permission_names: Optional[list[str]] = None,
) -> RoleResponse:
    """Build a consistent role response from a SQL model."""
    from outlabs_auth.models.sql.entity import Entity

    root_entity_name = None
    if getattr(role, "root_entity_id", None):
        root_entity = await session.get(Entity, role.root_entity_id)
        if root_entity:
            root_entity_name = root_entity.display_name

    scope_entity_name = None
    if getattr(role, "scope_entity_id", None):
        scope_entity = await session.get(Entity, role.scope_entity_id)
        if scope_entity:
            scope_entity_name = scope_entity.display_name

    resolved_permissions = permission_names
    if resolved_permissions is None:
        resolved_permissions = (
            role.get_permission_names()
            if hasattr(role, "get_permission_names")
            else []
        )

    scope_value = RoleScopeEnum.HIERARCHY
    if getattr(role, "scope", None) == RoleScope.ENTITY_ONLY:
        scope_value = RoleScopeEnum.ENTITY_ONLY

    return RoleResponse(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        permissions=resolved_permissions,
        is_system_role=role.is_system_role,
        is_global=role.is_global,
        root_entity_id=str(role.root_entity_id) if role.root_entity_id else None,
        root_entity_name=root_entity_name,
        assignable_at_types=list(getattr(role, "assignable_at_types", []) or []),
        scope_entity_id=str(role.scope_entity_id) if role.scope_entity_id else None,
        scope_entity_name=scope_entity_name,
        scope=scope_value,
        is_auto_assigned=role.is_auto_assigned,
    )
