"""
Membership Service

Manages entity memberships for EnterpriseRBAC.
Handles user-entity-role relationships with multiple roles per membership.
"""
from typing import List, Optional
from datetime import datetime, timezone

from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.entity import EntityModel
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    UserNotFoundError,
    RoleNotFoundError,
    InvalidInputError,
    MembershipNotFoundError,
)


class MembershipService:
    """
    Service for entity membership management.

    Features:
    - Add/remove members from entities
    - Assign multiple roles per membership
    - Time-based validity management
    - Member listing and filtering
    """

    def __init__(self, config: AuthConfig):
        """
        Initialize MembershipService.

        Args:
            config: Authentication configuration
        """
        self.config = config

    async def add_member(
        self,
        entity_id: str,
        user_id: str,
        role_ids: List[str],
        joined_by: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
    ) -> EntityMembershipModel:
        """
        Add user to entity with role(s).

        Creates new membership or updates existing one.

        Args:
            entity_id: Entity ID
            user_id: User ID
            role_ids: List of role IDs to assign
            joined_by: Optional user ID who added the member
            valid_from: Optional start date for membership
            valid_until: Optional end date for membership

        Returns:
            EntityMembershipModel: Created or updated membership

        Raises:
            EntityNotFoundError: If entity not found
            UserNotFoundError: If user not found
            RoleNotFoundError: If role not found
            InvalidInputError: If max_members limit exceeded

        Example:
            >>> membership = await membership_service.add_member(
            ...     entity_id=dept_id,
            ...     user_id=user_id,
            ...     role_ids=[developer_role_id, team_lead_role_id]
            ... )
        """
        # Validate entity exists
        entity = await EntityModel.get(entity_id)
        if not entity:
            raise EntityNotFoundError(
                message="Entity not found",
                details={"entity_id": entity_id}
            )

        # Validate user exists
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Validate roles exist
        roles = []
        for role_id in role_ids:
            role = await RoleModel.get(role_id)
            if not role:
                raise RoleNotFoundError(
                    message=f"Role not found",
                    details={"role_id": role_id}
                )
            roles.append(role)

        # Check if membership already exists
        existing = await EntityMembershipModel.find_one(
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.entity.id == entity.id
        )

        # Check max_members limit only for NEW memberships
        if not existing and entity.max_members:
            current_members = await self.get_entity_members_count(
                entity_id,
                active_only=True
            )
            if current_members >= entity.max_members:
                raise InvalidInputError(
                    message=f"Entity has reached maximum members limit ({entity.max_members})",
                    details={
                        "entity_id": entity_id,
                        "max_members": entity.max_members,
                        "current_members": current_members
                    }
                )

        if existing:
            # Update existing membership
            existing.roles = roles
            existing.is_active = True
            existing.valid_from = valid_from
            existing.valid_until = valid_until
            existing.updated_at = datetime.now(timezone.utc)
            await existing.save()
            return existing

        # Create new membership
        joined_by_user = None
        if joined_by:
            joined_by_user = await UserModel.get(joined_by)

        membership = EntityMembershipModel(
            user=user,
            entity=entity,
            roles=roles,
            joined_by=joined_by_user,
            valid_from=valid_from,
            valid_until=valid_until,
            tenant_id=entity.tenant_id
        )

        await membership.save()
        return membership

    async def remove_member(
        self,
        entity_id: str,
        user_id: str
    ) -> bool:
        """
        Remove user from entity (soft delete by setting is_active=False).

        Args:
            entity_id: Entity ID
            user_id: User ID

        Returns:
            bool: True if membership removed

        Raises:
            MembershipNotFoundError: If membership not found

        Example:
            >>> await membership_service.remove_member(entity_id, user_id)
        """
        # Fetch user and entity to get ObjectIds for query
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        entity = await EntityModel.get(entity_id)
        if not entity:
            raise EntityNotFoundError(
                message="Entity not found",
                details={"entity_id": entity_id}
            )

        # Find membership
        membership = await EntityMembershipModel.find_one(
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.entity.id == entity.id
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": entity_id, "user_id": user_id}
            )

        # Soft delete
        membership.is_active = False
        membership.updated_at = datetime.now(timezone.utc)
        await membership.save()

        return True

    async def update_member_roles(
        self,
        entity_id: str,
        user_id: str,
        role_ids: List[str]
    ) -> EntityMembershipModel:
        """
        Update user's roles in entity.

        Args:
            entity_id: Entity ID
            user_id: User ID
            role_ids: New list of role IDs

        Returns:
            EntityMembershipModel: Updated membership

        Raises:
            MembershipNotFoundError: If membership not found
            RoleNotFoundError: If role not found

        Example:
            >>> membership = await membership_service.update_member_roles(
            ...     entity_id,
            ...     user_id,
            ...     [new_role_id1, new_role_id2]
            ... )
        """
        # Fetch user and entity to get ObjectIds for query
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        entity = await EntityModel.get(entity_id)
        if not entity:
            raise EntityNotFoundError(
                message="Entity not found",
                details={"entity_id": entity_id}
            )

        # Find membership using ObjectIds
        membership = await EntityMembershipModel.find_one(
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.entity.id == entity.id
        )

        if not membership:
            raise MembershipNotFoundError(
                message="Membership not found",
                details={"entity_id": entity_id, "user_id": user_id}
            )

        # Validate and fetch roles
        roles = []
        for role_id in role_ids:
            role = await RoleModel.get(role_id)
            if not role:
                raise RoleNotFoundError(
                    message=f"Role not found",
                    details={"role_id": role_id}
                )
            roles.append(role)

        # Update roles
        membership.roles = roles
        membership.updated_at = datetime.now(timezone.utc)
        await membership.save()

        return membership

    async def get_entity_members(
        self,
        entity_id: str,
        page: int = 1,
        limit: int = 50,
        active_only: bool = True
    ) -> tuple[List[EntityMembershipModel], int]:
        """
        Get members of entity with pagination.

        Args:
            entity_id: Entity ID
            page: Page number (1-indexed)
            limit: Results per page
            active_only: Only return active memberships

        Returns:
            tuple[List[EntityMembershipModel], int]: (memberships, total_count)

        Example:
            >>> members, total = await membership_service.get_entity_members(
            ...     entity_id,
            ...     page=1,
            ...     limit=20
            ... )
        """
        # Fetch entity to get ObjectId
        entity = await EntityModel.get(entity_id)
        if not entity:
            return [], 0  # Entity not found, so no members

        # Build query
        query_conditions = [EntityMembershipModel.entity.id == entity.id]
        if active_only:
            query_conditions.append(EntityMembershipModel.is_active == True)

        # Get total count
        total_count = await EntityMembershipModel.find(*query_conditions).count()

        # Get paginated results
        skip = (page - 1) * limit
        memberships = await EntityMembershipModel.find(
            *query_conditions
        ).skip(skip).limit(limit).to_list()

        return memberships, total_count

    async def get_entity_members_count(
        self,
        entity_id: str,
        active_only: bool = True
    ) -> int:
        """
        Get count of entity members.

        Args:
            entity_id: Entity ID
            active_only: Only count active memberships

        Returns:
            int: Member count

        Example:
            >>> count = await membership_service.get_entity_members_count(entity_id)
        """
        # Fetch entity to get ObjectId
        entity = await EntityModel.get(entity_id)
        if not entity:
            return 0  # Entity not found, so no members

        query_conditions = [EntityMembershipModel.entity.id == entity.id]
        if active_only:
            query_conditions.append(EntityMembershipModel.is_active == True)

        return await EntityMembershipModel.find(*query_conditions).count()

    async def get_user_entities(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 50,
        entity_type: Optional[str] = None,
        active_only: bool = True
    ) -> tuple[List[EntityMembershipModel], int]:
        """
        Get entities user belongs to with pagination.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            limit: Results per page
            entity_type: Optional filter by entity type
            active_only: Only return active memberships

        Returns:
            tuple[List[EntityMembershipModel], int]: (memberships, total_count)

        Example:
            >>> memberships, total = await membership_service.get_user_entities(
            ...     user_id,
            ...     entity_type="department"
            ... )
        """
        # Fetch user to get ObjectId
        user = await UserModel.get(user_id)
        if not user:
            return [], 0  # User not found, so no entities

        # Build query
        query_conditions = [EntityMembershipModel.user.id == user.id]
        if active_only:
            query_conditions.append(EntityMembershipModel.is_active == True)

        # Note: entity_type filtering requires fetching entities
        # For performance, we'll filter after query if needed

        # Get total count
        all_memberships = await EntityMembershipModel.find(*query_conditions).to_list()

        # Filter by entity_type if provided
        if entity_type:
            filtered_memberships = []
            for membership in all_memberships:
                entity = await membership.entity.fetch() if hasattr(membership.entity, 'fetch') else membership.entity
                if entity and entity.entity_type == entity_type.lower():
                    filtered_memberships.append(membership)
            all_memberships = filtered_memberships

        total_count = len(all_memberships)

        # Apply pagination
        skip = (page - 1) * limit
        memberships = all_memberships[skip:skip + limit]

        return memberships, total_count

    async def get_member(
        self,
        entity_id: str,
        user_id: str
    ) -> Optional[EntityMembershipModel]:
        """
        Get specific membership.

        Args:
            entity_id: Entity ID
            user_id: User ID

        Returns:
            EntityMembershipModel or None: Membership if found

        Example:
            >>> membership = await membership_service.get_member(entity_id, user_id)
        """
        # Fetch user and entity to get ObjectIds for query
        user = await UserModel.get(user_id)
        if not user:
            return None

        entity = await EntityModel.get(entity_id)
        if not entity:
            return None

        return await EntityMembershipModel.find_one(
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.entity.id == entity.id
        )

    async def is_member(
        self,
        entity_id: str,
        user_id: str,
        active_only: bool = True
    ) -> bool:
        """
        Check if user is member of entity.

        Args:
            entity_id: Entity ID
            user_id: User ID
            active_only: Only check active memberships

        Returns:
            bool: True if user is member

        Example:
            >>> is_member = await membership_service.is_member(entity_id, user_id)
        """
        # Fetch user and entity to get ObjectIds for query
        user = await UserModel.get(user_id)
        if not user:
            return False

        entity = await EntityModel.get(entity_id)
        if not entity:
            return False

        query_conditions = [
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.entity.id == entity.id
        ]

        if active_only:
            query_conditions.append(EntityMembershipModel.is_active == True)

        membership = await EntityMembershipModel.find_one(*query_conditions)
        return membership is not None
