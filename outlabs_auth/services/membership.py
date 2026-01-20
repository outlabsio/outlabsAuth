"""
Membership Service

Manages entity memberships for EnterpriseRBAC.
Handles user-entity-role relationships with multiple roles per membership.
Uses SQLAlchemy for PostgreSQL backend.
"""

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Tuple
from uuid import UUID

if TYPE_CHECKING:
    from outlabs_auth.observability import ObservabilityService

from sqlalchemy import and_, func, select, update
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
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import (
    EntityMembership,
    EntityMembershipRole,
)
from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.base import BaseService


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

    async def add_member(
        self,
        session: AsyncSession,
        entity_id: UUID,
        user_id: UUID,
        role_ids: List[UUID],
        joined_by_id: Optional[UUID] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
    ) -> EntityMembership:
        """
        Add user to entity with role(s).

        Creates new membership or updates existing one.

        Args:
            session: Database session
            entity_id: Entity ID
            user_id: User ID
            role_ids: List of role IDs to assign
            joined_by_id: Optional user ID who added the member
            valid_from: Optional start date for membership
            valid_until: Optional end date for membership

        Returns:
            EntityMembership: Created or updated membership

        Raises:
            EntityNotFoundError: If entity not found
            UserNotFoundError: If user not found
            RoleNotFoundError: If role not found
            InvalidInputError: If max_members limit exceeded
        """
        start_time = time.perf_counter()

        # Validate entity exists
        entity = await session.get(Entity, entity_id)
        if not entity:
            raise EntityNotFoundError(
                message="Entity not found", details={"entity_id": str(entity_id)}
            )

        # Validate user exists
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found", details={"user_id": str(user_id)}
            )

        # Validate roles exist
        roles = []
        for role_id in role_ids:
            role = await session.get(Role, role_id)
            if not role:
                raise RoleNotFoundError(
                    message="Role not found", details={"role_id": str(role_id)}
                )
            roles.append(role)

        # Check if membership already exists
        existing = await self.get_one(
            session,
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
            options=[selectinload(EntityMembership.roles)],
        )

        # Check max_members limit only for NEW memberships
        if not existing and entity.max_members:
            current_members = await self.get_entity_members_count(
                session, entity_id, active_only=True
            )
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
            # Update existing membership
            existing.status = MembershipStatus.ACTIVE
            existing.valid_from = valid_from
            existing.valid_until = valid_until

            # Update roles via junction table
            # First, clear existing roles
            stmt = sql_delete(EntityMembershipRole).where(
                EntityMembershipRole.membership_id == existing.id
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

            return existing

        # Create new membership
        membership = EntityMembership(
            user_id=user_id,
            entity_id=entity_id,
            joined_by_id=joined_by_id,
            valid_from=valid_from,
            valid_until=valid_until,
            tenant_id=entity.tenant_id,
            status=MembershipStatus.ACTIVE,
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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        await session.execute(
            update(EntityMembership)
            .where(EntityMembership.id == membership.id)
            .values(
                status=MembershipStatus.REVOKED,
                revoked_at=func.now(),
                revoked_by_id=revoked_by_id,
                revocation_reason=reason,
                updated_at=func.now(),
            )
        )

        await session.flush()

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

        return True

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
        # Find membership
        membership = await self.get_one(
            session,
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
            options=[selectinload(EntityMembership.roles)],
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        # Validate roles exist
        roles = []
        for role_id in role_ids:
            role = await session.get(Role, role_id)
            if not role:
                raise RoleNotFoundError(
                    message="Role not found", details={"role_id": str(role_id)}
                )
            roles.append(role)

        # Clear existing roles
        stmt = sql_delete(EntityMembershipRole).where(
            EntityMembershipRole.membership_id == membership.id
        )
        await session.execute(stmt)

        # Add new roles
        for role in roles:
            role_link = EntityMembershipRole(
                membership_id=membership.id,
                role_id=role.id,
            )
            session.add(role_link)

        await session.execute(
            update(EntityMembership)
            .where(EntityMembership.id == membership.id)
            .values(updated_at=func.now())
        )
        await session.flush()
        await session.refresh(membership, ["roles"])

        return membership

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
        filters = [EntityMembership.entity_id == entity_id]
        if active_only:
            filters.append(EntityMembership.status == MembershipStatus.ACTIVE)

        # Get total count
        count_stmt = select(func.count()).select_from(EntityMembership).where(*filters)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # Get paginated results with roles eager loaded
        skip = (page - 1) * limit
        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(selectinload(EntityMembership.roles))
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
        filters = [EntityMembership.entity_id == entity_id]
        if active_only:
            filters.append(EntityMembership.status == MembershipStatus.ACTIVE)

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
        filters = [EntityMembership.user_id == user_id]
        if active_only:
            filters.append(EntityMembership.status == MembershipStatus.ACTIVE)

        # If filtering by entity_type, join with Entity table
        if entity_type:
            # Get count with join
            count_stmt = (
                select(func.count())
                .select_from(EntityMembership)
                .join(Entity, EntityMembership.entity_id == Entity.id)
                .where(*filters, Entity.entity_type == entity_type.lower())
            )
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Get paginated results
            skip = (page - 1) * limit
            stmt = (
                select(EntityMembership)
                .join(Entity, EntityMembership.entity_id == Entity.id)
                .where(*filters, Entity.entity_type == entity_type.lower())
                .options(
                    selectinload(EntityMembership.roles),
                    selectinload(EntityMembership.entity),
                )
                .offset(skip)
                .limit(limit)
            )
        else:
            # Get count without entity_type filter
            count_stmt = (
                select(func.count()).select_from(EntityMembership).where(*filters)
            )
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Get paginated results
            skip = (page - 1) * limit
            stmt = (
                select(EntityMembership)
                .where(*filters)
                .options(
                    selectinload(EntityMembership.roles),
                    selectinload(EntityMembership.entity),
                )
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
        filters = [EntityMembership.user_id == user_id]
        if active_only:
            filters.append(EntityMembership.status == MembershipStatus.ACTIVE)

        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(
                selectinload(EntityMembership.entity),
                selectinload(EntityMembership.roles),
            )
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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
            options=[selectinload(EntityMembership.roles)],
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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
        ]

        if active_only:
            filters.append(EntityMembership.status == MembershipStatus.ACTIVE)

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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id.in_(entity_ids),
        ]

        if active_only:
            filters.append(EntityMembership.status == MembershipStatus.ACTIVE)

        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(selectinload(EntityMembership.roles))
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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        membership.status = MembershipStatus.SUSPENDED
        membership.revocation_reason = reason

        await session.flush()

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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

        membership.status = MembershipStatus.ACTIVE
        membership.revocation_reason = None
        membership.revoked_at = None
        membership.revoked_by_id = None

        await session.flush()

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

        return membership
