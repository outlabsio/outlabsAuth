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
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import (
    EntityMembership,
    EntityMembershipRole,
)
from outlabs_auth.models.sql.enums import MembershipStatus, RoleScope
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
            if not await self._is_role_available_for_entity(session, role, entity_id, root_entity_id):
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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
            options=[selectinload(EntityMembership.roles)],
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
            stmt = sql_delete(EntityMembershipRole).where(EntityMembershipRole.membership_id == existing.id)
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
            EntityMembership.user_id == user_id,
            EntityMembership.entity_id == entity_id,
            options=[selectinload(EntityMembership.roles)],
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": str(entity_id), "user_id": str(user_id)},
            )

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

            root_entity_id = await self._get_root_entity_id(session, entity_id)
            for role in roles:
                if not await self._is_role_available_for_entity(session, role, entity_id, root_entity_id):
                    raise InvalidInputError(
                        message=f"Role '{role.name}' is not available for this entity",
                        details={
                            "role_id": str(role.id),
                            "role_name": role.name,
                            "entity_id": str(entity_id),
                            "role_root_entity_id": str(role.root_entity_id) if role.root_entity_id else None,
                        },
                    )

            stmt = sql_delete(EntityMembershipRole).where(EntityMembershipRole.membership_id == membership.id)
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
        filters = [EntityMembership.entity_id == entity_id]
        if active_only:
            filters.append(EntityMembership.status == MembershipStatus.ACTIVE)

        # Get total count
        count_stmt = select(func.count()).select_from(EntityMembership).where(*filters)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # Get paginated results with user AND roles eager loaded
        skip = (page - 1) * limit
        stmt = (
            select(EntityMembership)
            .where(*filters)
            .options(
                selectinload(EntityMembership.roles),
                selectinload(EntityMembership.user),
            )
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
            count_stmt = select(func.count()).select_from(EntityMembership).where(*filters)
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

        stmt = select(EntityMembership).where(*filters).options(selectinload(EntityMembership.roles))
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
            select(EntityClosure.ancestor_id)
            .where(EntityClosure.descendant_id == entity_id)
            .order_by(EntityClosure.depth.desc())
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
                ancestors_stmt = select(EntityClosure.ancestor_id).where(EntityClosure.descendant_id == entity_id)
                ancestors_result = await session.execute(ancestors_stmt)
                ancestor_ids = {row[0] for row in ancestors_result.all()}
                return role.scope_entity_id in ancestor_ids
            else:
                # Entity-only scope: available only at the exact scope entity
                return role.scope_entity_id == entity_id

        # Role with no root_entity_id and is_global=False is orphaned/unusable
        return False

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
        # Get all ancestors (including self)
        ancestors_stmt = select(EntityClosure.ancestor_id).where(EntityClosure.descendant_id == entity_id)
        ancestors_result = await session.execute(ancestors_stmt)
        ancestor_ids = [row[0] for row in ancestors_result.all()]

        if not ancestor_ids:
            return []

        # Find auto-assigned roles:
        # 1. Entity-only roles defined at THIS entity
        # 2. Hierarchy roles defined at any ancestor (including self)
        from sqlalchemy import and_, or_

        role_filter = and_(
            Role.is_auto_assigned == True,
            or_(
                # Entity-only auto-assigned for this specific entity
                and_(
                    Role.scope_entity_id == entity_id,
                    Role.scope == RoleScope.ENTITY_ONLY,
                ),
                # Hierarchy auto-assigned from any ancestor
                and_(
                    Role.scope_entity_id.in_(ancestor_ids),
                    Role.scope == RoleScope.HIERARCHY,
                ),
            ),
        )

        stmt = select(Role).where(role_filter).order_by(Role.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

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
            descendants_stmt = select(EntityClosure.descendant_id).where(
                EntityClosure.ancestor_id == role.scope_entity_id
            )
            descendants_result = await session.execute(descendants_stmt)
            target_entity_ids = [row[0] for row in descendants_result.all()]

        if not target_entity_ids:
            return 0

        # Get all active memberships in target entities
        memberships_stmt = (
            select(EntityMembership)
            .options(selectinload(EntityMembership.roles))
            .where(
                EntityMembership.entity_id.in_(target_entity_ids),
                EntityMembership.status == MembershipStatus.ACTIVE,
            )
        )
        memberships_result = await session.execute(memberships_stmt)
        memberships = list(memberships_result.scalars().all())

        # Add role to memberships that don't already have it
        updated_count = 0
        for membership in memberships:
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
