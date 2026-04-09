"""
Membership Service

Manages entity memberships for EnterpriseRBAC.
Handles user-entity-role relationships with multiple roles per membership.
Uses SQLAlchemy for PostgreSQL backend.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast
from uuid import UUID

if TYPE_CHECKING:
    from outlabs_auth.observability import ObservabilityService

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidInputError,
    MembershipNotFoundError,
    RoleNotFoundError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import (
    EntityMembership,
    EntityMembershipRole,
)
from outlabs_auth.models.sql.entity_membership_history import EntityMembershipHistory
from outlabs_auth.models.sql.enums import DefinitionStatus, MembershipStatus, RoleScope
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.base import BaseService


@dataclass
class OrphanedUserRecord:
    """Projected orphaned-user discovery row."""

    user: User
    active_membership_count: int
    total_membership_count: int
    last_event_type: Optional[str]
    last_event_at: Optional[datetime]
    last_entity_id: Optional[UUID]
    last_entity_name: Optional[str]


class MembershipService(BaseService[EntityMembership]):
    """
    Service for entity membership management.

    Features:
    - Add/remove members from entities
    - Assign multiple roles per membership
    - Time-based validity management
    - Member listing and filtering
    """

    def __init__(
        self,
        config: AuthConfig,
        observability: Optional["ObservabilityService"] = None,
        user_audit_service: Optional[Any] = None,
    ):
        """
        Initialize MembershipService.

        Args:
            config: Authentication configuration
            observability: Optional observability service for metrics/logging
        """
        super().__init__(EntityMembership)
        self.config = config
        self.observability = observability
        self.user_audit_service = user_audit_service

    @staticmethod
    def _membership_roles_option() -> Any:
        return selectinload(cast(Any, EntityMembership.roles))

    @classmethod
    def _membership_roles_user_options(cls) -> list[Any]:
        return [
            cls._membership_roles_option(),
            selectinload(cast(Any, EntityMembership.user)),
        ]

    @classmethod
    def _membership_roles_entity_options(cls) -> list[Any]:
        return [
            cls._membership_roles_option(),
            selectinload(cast(Any, EntityMembership.entity)),
        ]

    async def add_member(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
        role_ids: Optional[List[UUID]] = None,
        joined_by_id: Optional[UUID] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        status: MembershipStatus = MembershipStatus.ACTIVE,
        reason: Optional[str] = None,
        skip_auto_assign: bool = False,
    ) -> EntityMembership:
        """
        Add user to entity with role(s).

        Creates new membership or updates existing one.
        Automatically includes auto-assigned roles for the entity.

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID
            role_ids: List of role IDs to assign (optional, auto-assigned roles always included)
            joined_by_id: Optional user ID who added the member
            valid_from: Optional start date for membership
            valid_until: Optional end date for membership
            status: Initial membership status (active or suspended)
            reason: Optional status reason (used for suspended memberships)
            skip_auto_assign: If True, don't auto-assign roles (used for retroactive assignment)

        Returns:
            EntityMembership: Created or updated membership

        Raises:
            EntityNotFoundError: If entity not found
            UserNotFoundError: If user not found
            RoleNotFoundError: If role not found
            InvalidInputError: If max_members limit exceeded
        """
        start_time = time.perf_counter()
        role_ids = role_ids or []

        if valid_from and valid_until and valid_until < valid_from:
            raise InvalidInputError(
                message="valid_until must be after valid_from",
                details={
                    "entity_id": str(entity_id),
                    "user_id": str(user_id),
                },
            )

        # Validate entity exists
        entity = await session.get(Entity, entity_id)
        if not entity:
            raise EntityNotFoundError(message="Entity not found", details={"entity_id": str(entity_id)})

        # Validate user exists
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFoundError(message="User not found", details={"user_id": str(user_id)})

        # Validate explicitly requested roles exist
        roles = []
        for role_id in role_ids:
            role = await session.get(Role, role_id)
            if not role:
                raise RoleNotFoundError(message="Role not found", details={"role_id": str(role_id)})
            roles.append(role)

        # Get the root entity for this entity using closure table
        root_entity_id = await self._get_root_entity_id(session, entity_id)

        # Validate/set user's root_entity_id
        if user.root_entity_id is None:
            # First membership - set user's root entity
            user.root_entity_id = root_entity_id
            await session.flush()
        elif user.root_entity_id != root_entity_id:
            # User already belongs to a different organization
            raise InvalidInputError(
                message="User belongs to a different organization",
                details={
                    "user_id": str(user_id),
                    "user_root_entity_id": str(user.root_entity_id),
                    "entity_root_entity_id": str(root_entity_id),
                },
            )

        # Get auto-assigned roles for this entity (unless skipped)
        if not skip_auto_assign:
            auto_roles = await self._get_auto_assigned_roles_for_entity(session, entity_id)
            # Merge auto-assigned roles with explicitly requested roles (avoiding duplicates)
            auto_role_ids = {r.id for r in auto_roles}
            explicit_role_ids = {r.id for r in roles}
            for auto_role in auto_roles:
                if auto_role.id not in explicit_role_ids:
                    roles.append(auto_role)

        # Validate each role is available for this entity
        for role in roles:
            if not await self._is_role_available_for_entity(
                session,
                role,
                entity_id,
                root_entity_id,
                entity_type=entity.entity_type,
            ):
                raise InvalidInputError(
                    message=f"Role '{role.name}' is not available for this entity",
                    details={
                        "role_id": str(role.id),
                        "role_name": role.name,
                        "entity_id": str(entity_id),
                        "role_root_entity_id": str(role.root_entity_id) if role.root_entity_id else None,
                    },
                )

        # Check if membership already exists
        existing = await self.get_one(
            session,
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id) == entity_id,
            options=[self._membership_roles_option()],
        )

        # Check max_members limit only for NEW memberships
        if not existing and entity.max_members:
            current_members = await self.get_entity_members_count(session, entity_id, active_only=True)
            if current_members >= entity.max_members:
                raise InvalidInputError(
                    message=f"Entity has reached maximum members limit ({entity.max_members})",
                    details={
                        "entity_id": str(entity_id),
                        "max_members": entity.max_members,
                        "current_members": current_members,
                    },
                )

        if existing:
            previous_snapshot = await self._build_membership_history_snapshot(session, existing)
            previous_reason = existing.revocation_reason

            # Update existing membership
            existing.status = status
            existing.valid_from = valid_from
            existing.valid_until = valid_until
            if status == MembershipStatus.ACTIVE:
                existing.revoked_at = None
                existing.revoked_by_id = None
                existing.revocation_reason = None
            else:
                existing.revocation_reason = reason

            # Update roles via junction table
            # First, clear existing roles
            stmt = sql_delete(EntityMembershipRole).where(
                cast(Any, EntityMembershipRole.membership_id) == existing.id
            )
            await session.execute(stmt)

            # Add new roles
            for role in roles:
                role_link = EntityMembershipRole(
                    membership_id=existing.id,
                    role_id=role.id,
                )
                session.add(role_link)

            await session.flush()
            await session.refresh(existing, ["roles"])
            current_snapshot = await self._build_membership_history_snapshot(session, existing)
            event_type = self._determine_membership_event_type(
                previous_snapshot,
                current_snapshot,
                reason_changed=previous_reason != existing.revocation_reason,
            )
            if event_type is not None:
                await self._record_membership_history(
                    session,
                    membership=existing,
                    event_type=event_type,
                    previous_snapshot=previous_snapshot,
                    actor_user_id=joined_by_id,
                    reason=existing.revocation_reason,
                    event_source="membership_service.add_member",
                )

            # Log observability for update
            if self.observability:
                duration_ms = (time.perf_counter() - start_time) * 1000
                self.observability.log_membership_operation(
                    operation="update",
                    user_id=str(user_id),
                    entity_id=str(entity_id),
                    duration_ms=duration_ms,
                    roles=[str(r) for r in role_ids],
                    performed_by=str(joined_by_id) if joined_by_id else None,
                )

            await self._invalidate_membership_permissions_cache(user_id)
            return existing

        # Create new membership
        membership = EntityMembership(
            user_id=user_id,
            entity_id=entity_id,
            joined_by_id=joined_by_id,
            valid_from=valid_from,
            valid_until=valid_until,
            status=status,
            revocation_reason=reason,
        )

        session.add(membership)
        await session.flush()

        # Add roles via junction table
        for role in roles:
            role_link = EntityMembershipRole(
                membership_id=membership.id,
                role_id=role.id,
            )
            session.add(role_link)

        await session.flush()
        await session.refresh(membership, ["roles"])
        await self._record_membership_history(
            session,
            membership=membership,
            event_type="created",
            actor_user_id=joined_by_id,
            reason=membership.revocation_reason,
            event_source="membership_service.add_member",
        )

        # Log observability for add
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_membership_operation(
                operation="add",
                user_id=str(user_id),
                entity_id=str(entity_id),
                duration_ms=duration_ms,
                roles=[str(r) for r in role_ids],
                performed_by=str(joined_by_id) if joined_by_id else None,
            )

        await self._invalidate_membership_permissions_cache(user_id)
        return membership

    async def remove_member(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Remove user from entity (soft delete by setting status=REVOKED).

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID
            revoked_by_id: Optional user ID who is revoking the membership
            reason: Optional revocation reason

        Returns:
            bool: True if membership removed

        Raises:
            MembershipNotFoundError: If membership not found
        """
        start_time = time.perf_counter()

        # Find membership
        membership = await self.get_one(
            session,
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id) == entity_id,
            options=[self._membership_roles_option()],
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        previous_snapshot = await self._build_membership_history_snapshot(session, membership)
        membership.status = MembershipStatus.REVOKED
        membership.revoked_at = datetime.now(timezone.utc)
        membership.revoked_by_id = revoked_by_id
        membership.revocation_reason = reason

        await session.flush()
        await self._record_membership_history(
            session,
            membership=membership,
            event_type="revoked",
            previous_snapshot=previous_snapshot,
            actor_user_id=revoked_by_id,
            reason=reason,
            event_source="membership_service.remove_member",
        )

        # Log observability
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_membership_operation(
                operation="remove",
                user_id=str(user_id),
                entity_id=str(entity_id),
                duration_ms=duration_ms,
                performed_by=str(revoked_by_id) if revoked_by_id else None,
            )

        await self._invalidate_membership_permissions_cache(user_id)
        return True

    async def update_membership(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
        *,
        role_ids: Optional[List[UUID]] = None,
        update_roles: bool = False,
        status: Optional[MembershipStatus] = None,
        update_status: bool = False,
        valid_from: Optional[datetime] = None,
        update_valid_from: bool = False,
        valid_until: Optional[datetime] = None,
        update_valid_until: bool = False,
        reason: Optional[str] = None,
        update_reason: bool = False,
        changed_by_id: Optional[UUID] = None,
    ) -> EntityMembership:
        """
        Update a membership's roles and/or lifecycle settings.

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID
            role_ids: Updated role IDs when update_roles=True
            update_roles: Whether to replace the membership role set
            status: Updated membership status when update_status=True
            update_status: Whether to update the membership status
            valid_from: Updated validity start when update_valid_from=True
            update_valid_from: Whether to update valid_from
            valid_until: Updated validity end when update_valid_until=True
            update_valid_until: Whether to update valid_until
            reason: Updated lifecycle reason when update_reason=True
            update_reason: Whether to update the reason field
            changed_by_id: Optional actor performing the update

        Returns:
            EntityMembership: Updated membership with roles loaded
        """
        membership = await self.get_one(
            session,
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id) == entity_id,
            options=[self._membership_roles_option()],
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        previous_snapshot = await self._build_membership_history_snapshot(session, membership)
        previous_reason = membership.revocation_reason
        next_valid_from = valid_from if update_valid_from else membership.valid_from
        next_valid_until = valid_until if update_valid_until else membership.valid_until
        if next_valid_from and next_valid_until and next_valid_until < next_valid_from:
            raise InvalidInputError(
                message="valid_until must be after valid_from",
                details={
                    "entity_id": str(entity_id),
                    "user_id": str(user_id),
                },
            )

        if update_roles:
            roles = []
            for role_id in role_ids or []:
                role = await session.get(Role, role_id)
                if not role:
                    raise RoleNotFoundError(message="Role not found", details={"role_id": str(role_id)})
                roles.append(role)

            entity = await session.get(Entity, entity_id)
            if not entity:
                raise EntityNotFoundError(
                    message="Entity not found",
                    details={"entity_id": str(entity_id)},
                )

            root_entity_id = await self._get_root_entity_id(session, entity_id)
            for role in roles:
                if not await self._is_role_available_for_entity(
                    session,
                    role,
                    entity_id,
                    root_entity_id,
                    entity_type=entity.entity_type,
                ):
                    raise InvalidInputError(
                        message=f"Role '{role.name}' is not available for this entity",
                        details={
                            "role_id": str(role.id),
                            "role_name": role.name,
                            "entity_id": str(entity_id),
                            "role_root_entity_id": str(role.root_entity_id) if role.root_entity_id else None,
                        },
                    )

            stmt = sql_delete(EntityMembershipRole).where(
                cast(Any, EntityMembershipRole.membership_id) == membership.id
            )
            await session.execute(stmt)

            for role in roles:
                role_link = EntityMembershipRole(
                    membership_id=membership.id,
                    role_id=role.id,
                )
                session.add(role_link)

        if update_valid_from:
            membership.valid_from = valid_from
        if update_valid_until:
            membership.valid_until = valid_until
        if update_reason:
            membership.revocation_reason = reason

        if update_status and status is not None:
            membership.status = status
            if status == MembershipStatus.ACTIVE:
                membership.revoked_at = None
                membership.revoked_by_id = None
                if not update_reason:
                    membership.revocation_reason = None
            elif status == MembershipStatus.SUSPENDED:
                membership.revoked_by_id = changed_by_id

        await session.flush()
        await session.refresh(membership, ["roles"])
        current_snapshot = await self._build_membership_history_snapshot(session, membership)
        event_type = self._determine_membership_event_type(
            previous_snapshot,
            current_snapshot,
            reason_changed=previous_reason != membership.revocation_reason,
        )
        if event_type is not None:
            await self._record_membership_history(
                session,
                membership=membership,
                event_type=event_type,
                previous_snapshot=previous_snapshot,
                actor_user_id=changed_by_id,
                reason=membership.revocation_reason,
                event_source="membership_service.update_membership",
            )
        await self._invalidate_membership_permissions_cache(user_id)

        return membership

    async def update_member_roles(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
        role_ids: List[UUID],
    ) -> EntityMembership:
        """
        Update user's roles in entity.

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID
            role_ids: New list of role IDs

        Returns:
            EntityMembership: Updated membership

        Raises:
            MembershipNotFoundError: If membership not found
            RoleNotFoundError: If role not found
        """
        return await self.update_membership(
            session=session,
            entity_id=entity_id,
            user_id=user_id,
            role_ids=role_ids,
            update_roles=True,
        )

    async def get_entity_members(
        self,
        session: AsyncSession,
        entity_id: UUID,
        page: int = 1,
        limit: int = 50,
        active_only: bool = True,
    ) -> Tuple[List[EntityMembership], int]:
        """
        Get members of entity with pagination.

        Args:
            session: Database session
            entity_id: Entity ID
            page: Page number (1-indexed)
            limit: Results per page
            active_only: Only return active memberships

        Returns:
            Tuple[List[EntityMembership], int]: (memberships, total_count)
        """
        # Build filters
        filters: list[Any] = [cast(Any, EntityMembership.entity_id) == entity_id]
        if active_only:
            filters.append(cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE)

        # Get total count
        count_stmt = select(func.count()).select_from(EntityMembership).where(*filters)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # Get paginated results with roles eager loaded
        skip = (page - 1) * limit
        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(self._membership_roles_option())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        memberships = list(result.scalars().all())

        return memberships, total_count

    async def get_entity_members_with_users(
        self,
        session: AsyncSession,
        entity_id: UUID,
        page: int = 1,
        limit: int = 50,
        active_only: bool = True,
    ) -> Tuple[List[EntityMembership], int]:
        """
        Get members of entity with user details and roles eager loaded.

        Args:
            session: Database session
            entity_id: Entity ID
            page: Page number (1-indexed)
            limit: Results per page
            active_only: Only return active memberships

        Returns:
            Tuple[List[EntityMembership], int]: (memberships with user+roles, total_count)
        """
        # Build filters
        filters: list[Any] = [cast(Any, EntityMembership.entity_id) == entity_id]
        if active_only:
            filters.append(cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE)

        # Get total count
        count_stmt = select(func.count()).select_from(EntityMembership).where(*filters)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # Get paginated results with user AND roles eager loaded
        skip = (page - 1) * limit
        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(*self._membership_roles_user_options())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        memberships = list(result.scalars().all())

        return memberships, total_count

    async def get_entity_members_count(
        self,
        session: AsyncSession,
        entity_id: UUID,
        active_only: bool = True,
    ) -> int:
        """
        Get count of entity members.

        Args:
            session: Database session
            entity_id: Entity ID
            active_only: Only count active memberships

        Returns:
            int: Member count
        """
        filters: list[Any] = [cast(Any, EntityMembership.entity_id) == entity_id]
        if active_only:
            filters.append(cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE)

        return await self.count(session, *filters)

    async def get_user_entities(
        self,
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        limit: int = 50,
        entity_type: Optional[str] = None,
        active_only: bool = True,
    ) -> Tuple[List[EntityMembership], int]:
        """
        Get entities user belongs to with pagination.

        Args:
            session: Database session
            user_id: User ID
            page: Page number (1-indexed)
            limit: Results per page
            entity_type: Optional filter by entity type
            active_only: Only return active memberships

        Returns:
            Tuple[List[EntityMembership], int]: (memberships, total_count)
        """
        # Build base query with join to Entity for filtering
        filters: list[Any] = [cast(Any, EntityMembership.user_id) == user_id]
        if active_only:
            filters.append(cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE)

        # If filtering by entity_type, join with Entity table
        if entity_type:
            # Get count with join
            count_stmt = (
                select(func.count())
                .select_from(EntityMembership)
                .join(Entity, cast(Any, EntityMembership.entity_id) == Entity.id)
                .where(*filters, cast(Any, Entity.entity_type) == entity_type.lower())
            )
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Get paginated results
            skip = (page - 1) * limit
            stmt = (
                select(EntityMembership)
                .join(Entity, cast(Any, EntityMembership.entity_id) == Entity.id)
                .where(*filters, cast(Any, Entity.entity_type) == entity_type.lower())
                .options(*self._membership_roles_entity_options())
                .offset(skip)
                .limit(limit)
            )
        else:
            # Get count without entity_type filter
            count_stmt = select(func.count()).select_from(EntityMembership).where(*filters)
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Get paginated results
            skip = (page - 1) * limit
            stmt = (
                select(EntityMembership)
                .where(*filters)
                .options(*self._membership_roles_entity_options())
                .offset(skip)
                .limit(limit)
            )

        result = await session.execute(stmt)
        memberships = list(result.scalars().all())

        return memberships, total_count

    async def get_user_memberships_with_entities(
        self,
        session: AsyncSession,
        user_id: UUID,
        active_only: bool = True,
    ) -> List[EntityMembership]:
        """
        Get all memberships for a user with entity and roles loaded.

        Args:
            session: Database session
            user_id: User ID
            active_only: Only return active memberships

        Returns:
            List[EntityMembership]: User's memberships with entities loaded
        """
        filters: list[Any] = [cast(Any, EntityMembership.user_id) == user_id]
        if active_only:
            filters.append(cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE)

        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(*self._membership_roles_entity_options())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_member(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
    ) -> Optional[EntityMembership]:
        """
        Get specific membership.

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID

        Returns:
            EntityMembership or None: Membership if found
        """
        return await self.get_one(
            session,
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id) == entity_id,
            options=[self._membership_roles_option()],
        )

    async def is_member(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
        active_only: bool = True,
    ) -> bool:
        """
        Check if user is member of entity.

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID
            active_only: Only check active memberships

        Returns:
            bool: True if user is member
        """
        filters = [
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id) == entity_id,
        ]

        if active_only:
            filters.append(cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE)

        return await self.exists(session, *filters)

    async def get_memberships_for_entities(
        self,
        session: AsyncSession,
        user_id: UUID,
        entity_ids: List[UUID],
        active_only: bool = True,
    ) -> List[EntityMembership]:
        """
        Get memberships for a user in multiple entities.

        Useful for permission checking across entity hierarchy.

        Args:
            session: Database session
            user_id: User ID
            entity_ids: List of entity IDs to check
            active_only: Only return active memberships

        Returns:
            List[EntityMembership]: Memberships with roles loaded
        """
        if not entity_ids:
            return []

        filters = [
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id).in_(entity_ids),
        ]

        if active_only:
            filters.append(cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE)

        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(self._membership_roles_option())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def suspend_membership(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> EntityMembership:
        """
        Suspend a membership (can be reactivated later).

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID
            reason: Optional suspension reason

        Returns:
            EntityMembership: Suspended membership

        Raises:
            MembershipNotFoundError: If membership not found
        """
        start_time = time.perf_counter()

        membership = await self.get_one(
            session,
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id) == entity_id,
            options=[self._membership_roles_option()],
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        previous_snapshot = await self._build_membership_history_snapshot(session, membership)
        membership.status = MembershipStatus.SUSPENDED
        membership.revocation_reason = reason

        await session.flush()
        await self._record_membership_history(
            session,
            membership=membership,
            event_type="suspended",
            previous_snapshot=previous_snapshot,
            reason=reason,
            event_source="membership_service.suspend_membership",
        )

        # Log observability
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_membership_operation(
                operation="suspend",
                user_id=str(user_id),
                entity_id=str(entity_id),
                duration_ms=duration_ms,
                status="suspended",
            )

        await self._invalidate_membership_permissions_cache(user_id)
        return membership

    async def reactivate_membership(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
    ) -> EntityMembership:
        """
        Reactivate a suspended membership.

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID

        Returns:
            EntityMembership: Reactivated membership

        Raises:
            MembershipNotFoundError: If membership not found
        """
        start_time = time.perf_counter()

        membership = await self.get_one(
            session,
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.entity_id) == entity_id,
            options=[self._membership_roles_option()],
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        previous_snapshot = await self._build_membership_history_snapshot(session, membership)
        membership.status = MembershipStatus.ACTIVE
        membership.revocation_reason = None
        membership.revoked_at = None
        membership.revoked_by_id = None

        await session.flush()
        await self._record_membership_history(
            session,
            membership=membership,
            event_type="reactivated",
            previous_snapshot=previous_snapshot,
            event_source="membership_service.reactivate_membership",
        )

        # Log observability
        if self.observability:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.observability.log_membership_operation(
                operation="reactivate",
                user_id=str(user_id),
                entity_id=str(entity_id),
                duration_ms=duration_ms,
                status="active",
            )

        await self._invalidate_membership_permissions_cache(user_id)
        return membership

    async def revoke_memberships_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        event_source: str = "user_service.delete_user",
    ) -> List[EntityMembership]:
        """Revoke all non-revoked memberships for a user and record history."""
        stmt = (
            select(EntityMembership)
            .where(
                cast(Any, EntityMembership.user_id) == user_id,
                cast(Any, EntityMembership.status) != MembershipStatus.REVOKED,
            )
            .options(self._membership_roles_option())
        )
        result = await session.execute(stmt)
        memberships = list(result.scalars().all())
        if not memberships:
            return []

        event_at = datetime.now(timezone.utc)
        previous_snapshots: Dict[UUID, Dict[str, Any]] = {}

        for membership in memberships:
            previous_snapshots[membership.id] = await self._build_membership_history_snapshot(
                session,
                membership,
            )
            membership.status = MembershipStatus.REVOKED
            membership.revoked_at = event_at
            membership.revoked_by_id = revoked_by_id
            membership.revocation_reason = reason

        await session.flush()

        for membership in memberships:
            await self._record_membership_history(
                session,
                membership=membership,
                event_type="revoked",
                previous_snapshot=previous_snapshots[membership.id],
                actor_user_id=revoked_by_id,
                reason=reason,
                event_source=event_source,
                event_at=event_at,
            )

        await self._invalidate_membership_permissions_cache(user_id)
        return memberships

    async def archive_memberships_for_entity(
        self,
        session: AsyncSession,
        entity_id: UUID,
        *,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        event_source: str = "entity_service.delete_entity",
    ) -> List[EntityMembership]:
        """Revoke non-revoked memberships on an archived entity and record history."""
        stmt = (
            select(EntityMembership)
            .where(
                cast(Any, EntityMembership.entity_id) == entity_id,
                cast(Any, EntityMembership.status) != MembershipStatus.REVOKED,
            )
            .options(self._membership_roles_option())
        )
        result = await session.execute(stmt)
        memberships = list(result.scalars().all())
        if not memberships:
            return []

        event_at = datetime.now(timezone.utc)
        previous_snapshots: Dict[UUID, Dict[str, Any]] = {}
        affected_user_ids: set[UUID] = set()

        for membership in memberships:
            previous_snapshots[membership.id] = await self._build_membership_history_snapshot(session, membership)
            membership.status = MembershipStatus.REVOKED
            membership.revoked_at = event_at
            membership.revoked_by_id = revoked_by_id
            membership.revocation_reason = reason
            affected_user_ids.add(membership.user_id)

        await session.flush()

        for membership in memberships:
            await self._record_membership_history(
                session,
                membership=membership,
                event_type="entity_archived",
                previous_snapshot=previous_snapshots[membership.id],
                actor_user_id=revoked_by_id,
                reason=reason,
                event_source=event_source,
                event_at=event_at,
            )

        for user_id in affected_user_ids:
            await self._invalidate_membership_permissions_cache(user_id)

        return memberships

    async def get_user_membership_history(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        page: int = 1,
        limit: int = 50,
        entity_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
    ) -> Tuple[List[EntityMembershipHistory], int]:
        """Return paginated membership lifecycle history for a user."""
        filters: list[Any] = [cast(Any, EntityMembershipHistory.user_id) == user_id]
        if entity_id is not None:
            filters.append(cast(Any, EntityMembershipHistory.entity_id) == entity_id)
        if event_type:
            filters.append(cast(Any, EntityMembershipHistory.event_type) == event_type)

        count_stmt = select(func.count()).select_from(EntityMembershipHistory).where(*filters)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        skip = (page - 1) * limit
        stmt = (
            select(EntityMembershipHistory)
            .where(*filters)
            .order_by(
                cast(Any, EntityMembershipHistory.event_at).desc(),
                cast(Any, EntityMembershipHistory.created_at).desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def list_orphaned_users(
        self,
        session: AsyncSession,
        *,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        root_entity_id: Optional[UUID] = None,
    ) -> Tuple[List[OrphanedUserRecord], int]:
        """List users with no active memberships but historical assignment rows."""
        active_memberships = (
            select(func.count(cast(Any, EntityMembership.id)))
            .where(
                cast(Any, EntityMembership.user_id) == User.id,
                cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE,
            )
            .correlate(User)
            .scalar_subquery()
        )
        any_memberships = (
            select(func.count(cast(Any, EntityMembership.id)))
            .where(cast(Any, EntityMembership.user_id) == User.id)
            .correlate(User)
            .scalar_subquery()
        )

        filters: list[Any] = [active_memberships == 0, any_memberships > 0]
        if root_entity_id is not None:
            filters.append(cast(Any, User.root_entity_id) == root_entity_id)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    cast(Any, User.email).ilike(pattern),
                    cast(Any, User.first_name).ilike(pattern),
                    cast(Any, User.last_name).ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(User).where(*filters)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        skip = (page - 1) * limit
        users_stmt = (
            select(User)
            .where(*filters)
            .order_by(
                cast(Any, User.updated_at).desc(),
                cast(Any, User.created_at).desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        users_result = await session.execute(users_stmt)
        users = list(users_result.scalars().all())
        if not users:
            return [], total_count

        user_ids = [user.id for user in users]

        membership_count_stmt = (
            select(
                cast(Any, EntityMembership.user_id),
                func.count(cast(Any, EntityMembership.id)),
            )
            .where(cast(Any, EntityMembership.user_id).in_(user_ids))
            .group_by(cast(Any, EntityMembership.user_id))
        )
        membership_count_result = await session.execute(membership_count_stmt)
        membership_counts = {user_id: count for user_id, count in membership_count_result.all()}

        history_stmt = (
            select(EntityMembershipHistory)
            .where(cast(Any, EntityMembershipHistory.user_id).in_(user_ids))
            .order_by(
                cast(Any, EntityMembershipHistory.user_id),
                cast(Any, EntityMembershipHistory.event_at).desc(),
                cast(Any, EntityMembershipHistory.created_at).desc(),
            )
        )
        history_result = await session.execute(history_stmt)
        history_rows = list(history_result.scalars().all())
        latest_history_by_user: Dict[UUID, EntityMembershipHistory] = {}
        for row in history_rows:
            latest_history_by_user.setdefault(row.user_id, row)

        records = [
            OrphanedUserRecord(
                user=user,
                active_membership_count=0,
                total_membership_count=int(membership_counts.get(user.id, 0) or 0),
                last_event_type=(
                    latest_history_by_user[user.id].event_type
                    if user.id in latest_history_by_user
                    else None
                ),
                last_event_at=(
                    latest_history_by_user[user.id].event_at
                    if user.id in latest_history_by_user
                    else None
                ),
                last_entity_id=(
                    latest_history_by_user[user.id].entity_id
                    if user.id in latest_history_by_user
                    else None
                ),
                last_entity_name=(
                    latest_history_by_user[user.id].entity_display_name
                    if user.id in latest_history_by_user
                    else None
                ),
            )
            for user in users
        ]
        return records, total_count

    async def _invalidate_membership_permissions_cache(self, user_id: UUID) -> None:
        cache_service = getattr(self, "cache_service", None)
        if cache_service is None:
            return
        await cache_service.publish_user_permissions_invalidation(str(user_id))

    async def _record_membership_history(
        self,
        session: AsyncSession,
        *,
        membership: EntityMembership,
        event_type: str,
        previous_snapshot: Optional[Dict[str, Any]] = None,
        actor_user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        event_source: str = "membership_service",
        event_at: Optional[datetime] = None,
    ) -> EntityMembershipHistory:
        """Append one membership lifecycle history event."""
        current_snapshot = await self._build_membership_history_snapshot(session, membership)
        history = EntityMembershipHistory(
            membership_id=membership.id,
            user_id=membership.user_id,
            entity_id=membership.entity_id,
            root_entity_id=current_snapshot["root_entity_id"],
            actor_user_id=actor_user_id,
            event_type=event_type,
            event_source=event_source,
            event_at=event_at or datetime.now(timezone.utc),
            reason=reason,
            status=current_snapshot["status"],
            previous_status=previous_snapshot["status"] if previous_snapshot else None,
            valid_from=current_snapshot["valid_from"],
            valid_until=current_snapshot["valid_until"],
            previous_valid_from=previous_snapshot["valid_from"] if previous_snapshot else None,
            previous_valid_until=previous_snapshot["valid_until"] if previous_snapshot else None,
            role_ids=current_snapshot["role_ids"],
            previous_role_ids=previous_snapshot["role_ids"] if previous_snapshot else [],
            role_names=current_snapshot["role_names"],
            previous_role_names=previous_snapshot["role_names"] if previous_snapshot else [],
            entity_display_name=current_snapshot["entity_display_name"],
            entity_path=current_snapshot["entity_path"],
            root_entity_name=current_snapshot["root_entity_name"],
        )
        session.add(history)
        await session.flush()
        await self._record_user_membership_audit_event(
            session,
            membership=membership,
            history_event_type=event_type,
            event_source=event_source,
            actor_user_id=actor_user_id,
            reason=reason,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            occurred_at=history.event_at,
        )
        return history

    async def _record_user_membership_audit_event(
        self,
        session: AsyncSession,
        *,
        membership: EntityMembership,
        history_event_type: str,
        event_source: str,
        actor_user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        previous_snapshot: Optional[Dict[str, Any]] = None,
        current_snapshot: Dict[str, Any],
        occurred_at: Optional[datetime] = None,
    ) -> None:
        if self.user_audit_service is None:
            return

        audit_event_type = self._map_membership_event_type_to_user_audit_type(history_event_type)
        if audit_event_type is None:
            return

        user = await session.get(User, membership.user_id)
        if user is None:
            return

        await self.user_audit_service.record_event(
            session,
            event_category="membership",
            event_type=audit_event_type,
            event_source=event_source,
            actor_user_id=actor_user_id,
            subject_user_id=user.id,
            subject_email_snapshot=user.email,
            root_entity_id=current_snapshot["root_entity_id"] or user.root_entity_id,
            entity_id=membership.entity_id,
            reason=reason,
            before=previous_snapshot,
            after=current_snapshot,
            metadata={
                "membership_id": membership.id,
                "history_event_type": history_event_type,
                "entity_display_name": current_snapshot["entity_display_name"],
                "entity_path": current_snapshot["entity_path"],
                "root_entity_name": current_snapshot["root_entity_name"],
            },
            occurred_at=occurred_at,
        )

    async def _build_membership_history_snapshot(
        self,
        session: AsyncSession,
        membership: EntityMembership,
    ) -> Dict[str, Any]:
        """Build a serializable snapshot of the current membership state."""
        roles = list(getattr(membership, "roles", []) or [])
        if not roles:
            await session.refresh(membership, ["roles"])
            roles = list(getattr(membership, "roles", []) or [])

        roles = sorted(roles, key=lambda role: str(role.id))
        entity = await session.get(Entity, membership.entity_id)
        entity_path = await self._get_entity_path_display_names(session, membership.entity_id)
        root_entity_id = await self._get_root_entity_id(session, membership.entity_id)
        root_entity = await session.get(Entity, root_entity_id) if root_entity_id else None

        return {
            "status": self._membership_status_value(membership.status),
            "valid_from": membership.valid_from,
            "valid_until": membership.valid_until,
            "role_ids": [role.id for role in roles],
            "role_names": [
                (getattr(role, "display_name", None) or role.name)
                for role in roles
                if getattr(role, "name", None)
            ],
            "entity_display_name": entity.display_name if entity else None,
            "entity_path": entity_path,
            "root_entity_id": root_entity_id,
            "root_entity_name": (
                root_entity.display_name
                if root_entity is not None
                else (entity_path[0] if entity_path else None)
            ),
        }

    async def _get_entity_path_display_names(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> List[str]:
        """Resolve the display path from root to entity."""
        stmt = (
            select(cast(Any, Entity.display_name))
            .join(EntityClosure, cast(Any, EntityClosure.ancestor_id) == Entity.id)
            .where(cast(Any, EntityClosure.descendant_id) == entity_id)
            .order_by(cast(Any, EntityClosure.depth).desc())
        )
        result = await session.execute(stmt)
        return [display_name for (display_name,) in result.all() if display_name]

    def _determine_membership_event_type(
        self,
        previous_snapshot: Dict[str, Any],
        current_snapshot: Dict[str, Any],
        *,
        reason_changed: bool = False,
    ) -> Optional[str]:
        """Classify the lifecycle event from before/after snapshots."""
        previous_status = previous_snapshot["status"]
        current_status = current_snapshot["status"]

        if previous_status != current_status:
            if current_status == MembershipStatus.REVOKED.value:
                return "revoked"
            if current_status == MembershipStatus.SUSPENDED.value:
                return "suspended"
            if current_status == MembershipStatus.ACTIVE.value:
                return "reactivated"
            return "updated"

        if previous_snapshot["role_ids"] != current_snapshot["role_ids"]:
            return "updated"
        if previous_snapshot["valid_from"] != current_snapshot["valid_from"]:
            return "updated"
        if previous_snapshot["valid_until"] != current_snapshot["valid_until"]:
            return "updated"
        if reason_changed:
            return "updated"

        return None

    def _map_membership_event_type_to_user_audit_type(self, history_event_type: str) -> Optional[str]:
        return {
            "created": "user.membership_created",
            "updated": "user.membership_updated",
            "suspended": "user.membership_suspended",
            "reactivated": "user.membership_reactivated",
            "revoked": "user.membership_revoked",
            "entity_archived": "user.membership_entity_archived",
        }.get(history_event_type)

    def _membership_status_value(self, value: Any) -> str:
        """Normalize enum-or-string membership values into API-safe strings."""
        return str(getattr(value, "value", value))

    # =========================================================================
    # Helper Methods for Root Entity Validation
    # =========================================================================

    async def _get_root_entity_id(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> UUID:
        """
        Get the root entity ID for a given entity.

        Uses the closure table to find the root ancestor (highest depth).

        Args:
            session: Database session
            entity_id: Entity ID

        Returns:
            UUID: Root entity ID
        """
        # The root has the highest depth value in the closure table for this descendant
        stmt = (
            select(cast(Any, EntityClosure.ancestor_id))
            .where(cast(Any, EntityClosure.descendant_id) == entity_id)
            .order_by(cast(Any, EntityClosure.depth).desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else entity_id

    async def _is_role_available_for_entity(
        self,
        session: AsyncSession,
        role: Role,
        entity_id: UUID,
        root_entity_id: UUID,
        entity_type: Optional[str] = None,
    ) -> bool:
        """
        Check if a role can be assigned within an entity's context.

        A role is available at entity X if:
        1. System-wide global: is_global=True AND root_entity_id=NULL AND scope_entity_id=NULL
        2. Org-scoped: root_entity_id matches X's root AND scope_entity_id=NULL
        3. Entity-local (hierarchy): scope_entity_id is X or an ancestor AND scope=hierarchy
        4. Entity-local (entity_only): scope_entity_id = X AND scope=entity_only

        Args:
            session: Database session
            role: Role to check
            entity_id: Entity where role would be assigned
            root_entity_id: Pre-computed root entity ID for the entity

        Returns:
            bool: True if role can be used in this entity's context
        """
        if getattr(role, "status", DefinitionStatus.ACTIVE) != DefinitionStatus.ACTIVE:
            return False

        if not self._allows_entity_type(role, entity_type):
            return False

        # 1. Global system-wide roles are available everywhere
        if role.is_global and role.root_entity_id is None and role.scope_entity_id is None:
            return True

        # 2. Org-scoped roles (not entity-local)
        if role.root_entity_id and role.scope_entity_id is None:
            return role.root_entity_id == root_entity_id

        # 3 & 4. Entity-local roles
        if role.scope_entity_id:
            # First check org scope
            if role.root_entity_id and role.root_entity_id != root_entity_id:
                return False

            if role.scope == RoleScope.HIERARCHY:
                # Hierarchy scope: available if scope_entity is this entity or an ancestor
                # Get ancestors of entity_id
                ancestors_stmt = select(cast(Any, EntityClosure.ancestor_id)).where(
                    cast(Any, EntityClosure.descendant_id) == entity_id
                )
                ancestors_result = await session.execute(ancestors_stmt)
                ancestor_ids = {row[0] for row in ancestors_result.all()}
                return role.scope_entity_id in ancestor_ids
            else:
                # Entity-only scope: available only at the exact scope entity
                return role.scope_entity_id == entity_id

        # Role with no root_entity_id and is_global=False is orphaned/unusable
        return False

    @staticmethod
    def _allows_entity_type(role: Role, entity_type: Optional[str]) -> bool:
        if not role.assignable_at_types:
            return True

        if not entity_type:
            return False

        return entity_type.lower() in {
            role_entity_type.lower() for role_entity_type in role.assignable_at_types
        }

    async def _get_auto_assigned_roles_for_entity(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> List[Role]:
        """
        Get roles that should be auto-assigned to members of an entity.

        Returns auto-assigned roles where:
        - scope_entity_id matches entity_id AND scope=entity_only
        - OR scope_entity_id is an ancestor AND scope=hierarchy

        Args:
            session: Database session
            entity_id: Entity to get auto-assigned roles for

        Returns:
            List of Role objects that should be auto-assigned
        """
        entity = await session.get(Entity, entity_id)
        if not entity:
            return []

        # Get all ancestors (including self)
        ancestors_stmt = select(cast(Any, EntityClosure.ancestor_id)).where(
            cast(Any, EntityClosure.descendant_id) == entity_id
        )
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_ids = [row[0] for row in ancestors_result.all()]

        if not ancestor_ids:
            return []

        # Find auto-assigned roles:
        # 1. Entity-only roles defined at THIS entity
        # 2. Hierarchy roles defined at any ancestor (including self)
        from sqlalchemy import and_, or_

        role_filter = and_(
            cast(Any, Role.status) == DefinitionStatus.ACTIVE,
            cast(Any, Role.is_auto_assigned) == True,
            or_(
                # Entity-only auto-assigned for this specific entity
                and_(
                    cast(Any, Role.scope_entity_id) == entity_id,
                    cast(Any, Role.scope) == RoleScope.ENTITY_ONLY,
                ),
                # Hierarchy auto-assigned from any ancestor
                and_(
                    cast(Any, Role.scope_entity_id).in_(ancestor_ids),
                    cast(Any, Role.scope) == RoleScope.HIERARCHY,
                ),
            ),
        )

        stmt = select(Role).where(role_filter).order_by(cast(Any, Role.name))
        result = await session.execute(stmt)
        return [
            role
            for role in result.scalars().all()
            if self._allows_entity_type(role, entity.entity_type)
        ]

    async def apply_auto_assigned_role(
        self,
        session: AsyncSession,
        role_id: UUID,
    ) -> int:
        """
        Retroactively apply an auto-assigned role to all existing members within scope.

        Called when a role's is_auto_assigned is set to True.

        Args:
            session: Database session
            role_id: Role ID to apply

        Returns:
            int: Number of memberships updated

        Raises:
            RoleNotFoundError: If role not found
            InvalidInputError: If role is not auto-assigned or has no scope_entity_id
        """
        # Get the role
        role = await session.get(Role, role_id)
        if not role:
            raise RoleNotFoundError(
                message="Role not found",
                details={"role_id": str(role_id)},
            )

        if getattr(role, "status", DefinitionStatus.ACTIVE) != DefinitionStatus.ACTIVE:
            raise InvalidInputError(
                message="Only active roles can be auto-assigned",
                details={
                    "role_id": str(role_id),
                    "status": getattr(role.status, "value", role.status),
                },
            )

        if not role.is_auto_assigned:
            raise InvalidInputError(
                message="Role is not marked as auto-assigned",
                details={"role_id": str(role_id), "is_auto_assigned": False},
            )

        if not role.scope_entity_id:
            raise InvalidInputError(
                message="Auto-assigned roles must have a scope_entity_id",
                details={"role_id": str(role_id)},
            )

        # Determine which entities' members should get this role
        if role.scope == RoleScope.ENTITY_ONLY:
            # Only members of the scope entity itself
            target_entity_ids = [role.scope_entity_id]
        else:
            # Members of scope entity AND all descendants
            descendants_stmt = select(cast(Any, EntityClosure.descendant_id)).where(
                cast(Any, EntityClosure.ancestor_id) == role.scope_entity_id
            )
            descendants_result = await session.execute(descendants_stmt)
            target_entity_ids = [row[0] for row in descendants_result.all()]

        if not target_entity_ids:
            return 0

        # Get all active memberships in target entities
        memberships_stmt = (
            select(EntityMembership)
            .options(*self._membership_roles_entity_options())
            .where(
                cast(Any, EntityMembership.entity_id).in_(target_entity_ids),
                cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE,
            )
        )
        memberships_result = await session.execute(memberships_stmt)
        memberships = list(memberships_result.scalars().all())

        # Add role to memberships that don't already have it
        updated_count = 0
        for membership in memberships:
            entity_type = (
                membership.entity.entity_type
                if getattr(membership, "entity", None) is not None
                else None
            )
            if not self._allows_entity_type(role, entity_type):
                continue

            existing_role_ids = {r.id for r in membership.roles}
            if role_id not in existing_role_ids:
                role_link = EntityMembershipRole(
                    membership_id=membership.id,
                    role_id=role_id,
                )
                session.add(role_link)
                updated_count += 1

        await session.flush()
        return updated_count
