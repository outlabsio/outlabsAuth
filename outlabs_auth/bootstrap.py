"""Explicit bootstrap helpers for OutlabsAuth-owned system data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.config import ConfigService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.user import UserService


@dataclass(frozen=True)
class PermissionSeed:
    """Canonical permission definition owned by the auth library."""

    name: str
    display_name: str
    description: str


@dataclass(frozen=True)
class SeedSystemResult:
    """Result summary for system seeding."""

    permissions_created: int = 0
    permissions_existing: int = 0
    config_seeded: bool = False


@dataclass(frozen=True)
class BootstrapAdminResult:
    """Result summary for first-admin bootstrap."""

    status: Literal["created", "existing"]
    user_id: str
    email: str


SYSTEM_PERMISSION_CATALOG: tuple[PermissionSeed, ...] = (
    PermissionSeed("user:read", "User Read", "View users."),
    PermissionSeed("user:create", "User Create", "Create users."),
    PermissionSeed("user:update", "User Update", "Update users."),
    PermissionSeed("user:delete", "User Delete", "Delete users."),
    PermissionSeed("user:create_superuser", "User Create Superuser", "Create superusers."),
    PermissionSeed("role:read", "Role Read", "View roles."),
    PermissionSeed("role:read_tree", "Role Read Tree", "View roles across descendant entities."),
    PermissionSeed("role:create", "Role Create", "Create roles."),
    PermissionSeed("role:update", "Role Update", "Update roles."),
    PermissionSeed("role:delete", "Role Delete", "Delete roles."),
    PermissionSeed("permission:read", "Permission Read", "View permissions."),
    PermissionSeed("permission:create", "Permission Create", "Create permissions."),
    PermissionSeed("permission:update", "Permission Update", "Update permissions."),
    PermissionSeed("permission:delete", "Permission Delete", "Delete permissions."),
    PermissionSeed("permission:check", "Permission Check", "Check permission access."),
    PermissionSeed("entity:read", "Entity Read", "View entities."),
    PermissionSeed("entity:read_tree", "Entity Read Tree", "View descendant entities."),
    PermissionSeed("entity:create", "Entity Create", "Create root entities."),
    PermissionSeed("entity:create_tree", "Entity Create Tree", "Create descendant entities."),
    PermissionSeed("entity:update", "Entity Update", "Update entities."),
    PermissionSeed("entity:delete", "Entity Delete", "Delete entities."),
    PermissionSeed("membership:create", "Membership Create", "Create entity memberships."),
    PermissionSeed("membership:read", "Membership Read", "View memberships."),
    PermissionSeed("membership:read_tree", "Membership Read Tree", "View memberships across descendant entities."),
    PermissionSeed("membership:update", "Membership Update", "Update memberships."),
    PermissionSeed("membership:update_tree", "Membership Update Tree", "Update memberships across descendant entities."),
    PermissionSeed("membership:delete", "Membership Delete", "Delete memberships."),
    PermissionSeed("membership:delete_tree", "Membership Delete Tree", "Delete memberships across descendant entities."),
)


def get_system_permission_catalog() -> tuple[PermissionSeed, ...]:
    """Return the canonical library-owned permission catalog."""

    return SYSTEM_PERMISSION_CATALOG


async def seed_system_records(
    session: AsyncSession,
    *,
    permission_service: PermissionService | None = None,
    config_service: ConfigService | None = None,
    include_permissions: bool = True,
    include_config: bool = True,
    permission_catalog: Sequence[PermissionSeed] | None = None,
) -> SeedSystemResult:
    """Seed the library-owned permission catalog and config defaults."""

    permissions_created = 0
    permissions_existing = 0
    config_seeded = False

    if include_permissions:
        if permission_service is None:
            raise ValueError("permission_service is required when include_permissions=True")
        for permission in permission_catalog or SYSTEM_PERMISSION_CATALOG:
            existing = await permission_service.get_permission_by_name(session, permission.name)
            if existing is not None:
                permissions_existing += 1
                continue
            await permission_service.create_permission(
                session,
                name=permission.name,
                display_name=permission.display_name,
                description=permission.description,
                is_system=True,
                is_active=True,
            )
            permissions_created += 1

    if include_config:
        if config_service is None:
            raise ValueError("config_service is required when include_config=True")
        existing_config = await config_service.get_config(session, "entity_types")
        await config_service.seed_defaults(session)
        config_seeded = existing_config is None

    return SeedSystemResult(
        permissions_created=permissions_created,
        permissions_existing=permissions_existing,
        config_seeded=config_seeded,
    )


async def bootstrap_superuser(
    session: AsyncSession,
    *,
    user_service: UserService,
    email: str,
    password: str,
    first_name: str | None = None,
    last_name: str | None = None,
    root_entity_id: UUID | None = None,
) -> BootstrapAdminResult:
    """
    Create the initial superuser if and only if the auth system has no users.

    Existing matching email is treated as success for idempotent automation.
    """

    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("email is required")
    if not password:
        raise ValueError("password is required")

    existing = await user_service.get_user_by_email(session, normalized_email)
    if existing is not None:
        return BootstrapAdminResult(
            status="existing",
            user_id=str(existing.id),
            email=normalized_email,
        )

    any_user_result = await session.execute(select(cast(Any, User.id)).limit(1))
    if any_user_result.scalar_one_or_none() is not None:
        raise RuntimeError(
            "bootstrap-admin refused because users already exist and the requested email is not present"
        )

    user = await user_service.create_user(
        session,
        email=normalized_email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_superuser=True,
        root_entity_id=root_entity_id,
    )
    return BootstrapAdminResult(
        status="created",
        user_id=str(user.id),
        email=normalized_email,
    )


def build_bootstrap_config(
    *,
    secret_key: str = "outlabs-auth-bootstrap",
    database_url: str | None = None,
    database_schema: str | None = None,
) -> AuthConfig:
    """Construct a minimal config for CLI bootstrap flows."""

    return AuthConfig(
        secret_key=secret_key,
        database_url=database_url,
        database_schema=database_schema,
        enable_token_cleanup=False,
        enable_activity_tracking=False,
    )
