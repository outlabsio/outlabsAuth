"""Auth-owned query facade for host applications embedding OutlabsAuth."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import MembershipStatus, UserStatus
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.role import RoleService


@dataclass(frozen=True)
class HostUserProjection:
    """Minimal user shape safe for cross-domain host reads."""

    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    phone: str | None
    status: str


@dataclass(frozen=True)
class HostEntityProjection:
    """Minimal entity shape for host-side orchestration."""

    id: UUID
    name: str
    display_name: str
    slug: str
    entity_type: str
    status: str
    parent_id: UUID | None


@dataclass(frozen=True)
class HostRoleProjection:
    """Stable role projection for host integrations."""

    id: UUID
    name: str
    display_name: str
    description: str | None
    status: str
    is_global: bool
    is_auto_assigned: bool
    root_entity_id: UUID | None
    scope_entity_id: UUID | None
    assignable_at_types: tuple[str, ...]


@dataclass(frozen=True)
class HostEntityMembershipProjection:
    """Entity membership with resolved user/entity/role details."""

    id: UUID
    user_id: UUID
    entity_id: UUID
    status: str
    joined_at: datetime
    valid_from: datetime | None
    valid_until: datetime | None
    user: HostUserProjection
    entity: HostEntityProjection
    roles: tuple[HostRoleProjection, ...]


class HostQueryService:
    """
    Auth-owned read facade for host apps embedding OutlabsAuth in-process.

    Host applications should prefer this service over raw SQL joins into
    auth-owned tables. It provides the stable cross-domain reads that host
    products commonly need while keeping auth schema details inside the library.
    """

    def __init__(
        self,
        *,
        membership_service: MembershipService,
        role_service: RoleService,
    ) -> None:
        self.membership_service = membership_service
        self.role_service = role_service
        self.database_schema = membership_service.config.database_schema

    async def list_entity_members(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        page: int = 1,
        limit: int = 50,
        active_only: bool = True,
    ) -> tuple[list[HostEntityMembershipProjection], int]:
        """
        Return entity memberships with user, entity, and role details.

        When ``active_only`` is true, the result is limited to memberships that
        are currently valid, belong to active users, and sit on active entities.
        """
        async with self._auth_schema_context(session):
            filters = [EntityMembership.entity_id == entity_id]
            if active_only:
                filters.extend(self._active_membership_filters())

            total = await self._count_memberships(session, *filters)
            memberships = await self._load_memberships(
                session,
                filters=filters,
                page=page,
                limit=limit,
            )
            return [self._project_membership(membership) for membership in memberships], total

    async def list_user_entity_memberships(
        self,
        session: AsyncSession,
        *,
        user_ids: Sequence[UUID],
        active_only: bool = True,
        entity_types: Sequence[str] | None = None,
    ) -> list[HostEntityMembershipProjection]:
        """
        Return memberships for one or more users with entity and role context.

        This is intended for host-side cross-domain lookups such as resolving a
        user's current entity scope without exposing auth table joins.
        """
        normalized_user_ids = list(dict.fromkeys(user_ids))
        if not normalized_user_ids:
            return []

        async with self._auth_schema_context(session):
            filters = [EntityMembership.user_id.in_(normalized_user_ids)]
            if entity_types:
                normalized_types = [entity_type.strip().lower() for entity_type in entity_types if entity_type.strip()]
                if normalized_types:
                    filters.append(Entity.entity_type.in_(normalized_types))
            if active_only:
                filters.extend(self._active_membership_filters())

            memberships = await self._load_memberships(
                session,
                filters=filters,
                page=1,
                limit=None,
            )
            return [self._project_membership(membership) for membership in memberships]

    async def list_users_by_ids(
        self,
        session: AsyncSession,
        *,
        user_ids: Sequence[UUID],
        active_only: bool = False,
    ) -> list[HostUserProjection]:
        """
        Return stable user projections for one or more auth users.

        This is intended for host-side reads that need canonical user identity
        details without coupling those reads to membership presence.
        """
        normalized_user_ids = list(dict.fromkeys(user_ids))
        if not normalized_user_ids:
            return []

        async with self._auth_schema_context(session):
            stmt = select(User).where(User.id.in_(normalized_user_ids))
            if active_only:
                stmt = stmt.where(User.status == UserStatus.ACTIVE)
            stmt = stmt.order_by(User.id.asc())
            result = await session.execute(stmt)
            users = list(result.scalars().all())
            return [self._project_user(user) for user in users]

    async def list_roles_for_entity(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        page: int = 1,
        limit: int = 50,
        include_global: bool = True,
        include_auto_assigned_only: bool = False,
    ) -> tuple[list[HostRoleProjection], int]:
        """Return roles that are assignable in one entity context."""
        async with self._auth_schema_context(session):
            roles, total = await self.role_service.get_roles_for_entity(
                session,
                entity_id=entity_id,
                page=page,
                limit=limit,
                include_global=include_global,
                include_auto_assigned_only=include_auto_assigned_only,
            )
            return [self._project_role(role) for role in roles], total

    async def _count_memberships(
        self,
        session: AsyncSession,
        *filters,
    ) -> int:
        membership_ids = (
            select(EntityMembership.id)
            .join(User, EntityMembership.user_id == User.id)
            .join(Entity, EntityMembership.entity_id == Entity.id)
            .where(*filters)
            .subquery()
        )
        stmt = select(func.count()).select_from(membership_ids)
        result = await session.execute(stmt)
        return int(result.scalar() or 0)

    async def _load_memberships(
        self,
        session: AsyncSession,
        *,
        filters: list,
        page: int,
        limit: int | None,
    ) -> list[EntityMembership]:
        stmt = (
            select(EntityMembership)
            .join(User, EntityMembership.user_id == User.id)
            .join(Entity, EntityMembership.entity_id == Entity.id)
            .where(*filters)
            .options(
                selectinload(EntityMembership.user),
                selectinload(EntityMembership.entity),
                selectinload(EntityMembership.roles),
            )
            .order_by(
                EntityMembership.joined_at.desc(),
                EntityMembership.id.asc(),
            )
        )
        if limit is not None:
            skip = max(page - 1, 0) * limit
            stmt = stmt.offset(skip).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().unique().all())

    @staticmethod
    def _active_membership_filters() -> list:
        now = datetime.now(timezone.utc)
        return [
            EntityMembership.status == MembershipStatus.ACTIVE,
            User.status == UserStatus.ACTIVE,
            Entity.status == "active",
            or_(EntityMembership.valid_from.is_(None), EntityMembership.valid_from <= now),
            or_(EntityMembership.valid_until.is_(None), EntityMembership.valid_until >= now),
        ]

    def _project_membership(
        self,
        membership: EntityMembership,
    ) -> HostEntityMembershipProjection:
        if membership.user is None or membership.entity is None:
            raise RuntimeError("Membership projection requires user and entity relationships")
        return HostEntityMembershipProjection(
            id=membership.id,
            user_id=membership.user_id,
            entity_id=membership.entity_id,
            status=self._enum_value(membership.status),
            joined_at=membership.joined_at,
            valid_from=membership.valid_from,
            valid_until=membership.valid_until,
            user=self._project_user(membership.user),
            entity=self._project_entity(membership.entity),
            roles=tuple(self._project_role(role) for role in membership.roles),
        )

    @staticmethod
    def _project_user(user: User) -> HostUserProjection:
        return HostUserProjection(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            status=HostQueryService._enum_value(user.status),
        )

    @asynccontextmanager
    async def _auth_schema_context(self, session: AsyncSession):
        if not self.database_schema:
            yield
            return

        escaped_schema = self.database_schema.replace('"', '""')
        await session.execute(text(f'SET LOCAL search_path TO "{escaped_schema}", public'))
        yield

    @staticmethod
    def _project_entity(entity: Entity) -> HostEntityProjection:
        return HostEntityProjection(
            id=entity.id,
            name=entity.name,
            display_name=entity.display_name,
            slug=entity.slug,
            entity_type=entity.entity_type,
            status=entity.status,
            parent_id=entity.parent_id,
        )

    @staticmethod
    def _project_role(role: Role) -> HostRoleProjection:
        assignable_at_types = tuple(role.assignable_at_types or [])
        return HostRoleProjection(
            id=role.id,
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            status=HostQueryService._enum_value(role.status),
            is_global=role.is_global,
            is_auto_assigned=role.is_auto_assigned,
            root_entity_id=role.root_entity_id,
            scope_entity_id=role.scope_entity_id,
            assignable_at_types=assignable_at_types,
        )

    @staticmethod
    def _enum_value(value: object) -> str:
        return str(getattr(value, "value", value))
