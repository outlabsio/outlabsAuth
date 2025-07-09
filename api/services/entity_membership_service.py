"""
Entity Membership Service
Handles user memberships in entities with role assignments
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from beanie import PydanticObjectId
from beanie.operators import And, Or
from fastapi import HTTPException, status

from api.models import EntityModel, EntityMembershipModel, UserModel, RoleModel
from api.schemas.entity_schema import (
    EntityMemberAdd,
    EntityMemberUpdate
)


class EntityMembershipService:
    """Service for entity membership operations"""
    
    @staticmethod
    async def add_member(
        entity_id: str,
        member_data: EntityMemberAdd,
        added_by: UserModel
    ) -> EntityMembershipModel:
        """
        Add a user as a member of an entity with a specific role
        
        Args:
            entity_id: Entity ID
            member_data: Member addition data
            added_by: User adding the member
        
        Returns:
            Created membership
        
        Raises:
            HTTPException: If validation fails
        """
        # Validate entity
        entity = await EntityModel.get(entity_id)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity not found"
            )
        
        # Validate user
        user = await UserModel.get(member_data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Validate role
        role = await RoleModel.get(member_data.role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        # Validate role assignment rules
        await EntityMembershipService._validate_role_assignment(entity, role)
        
        # Check for existing active membership
        existing = await EntityMembershipModel.find_one(
            EntityMembershipModel.entity.id == entity.id,
            EntityMembershipModel.user.id == user.id,
            EntityMembershipModel.status == "active"
        )
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this entity"
            )
        
        # Check entity member limit if configured
        if entity.max_members:
            current_count = await EntityMembershipModel.find(
                EntityMembershipModel.entity.id == entity.id,
                EntityMembershipModel.status == "active"
            ).count()
            
            if current_count >= entity.max_members:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Entity has reached maximum member limit ({entity.max_members})"
                )
        
        # Create membership
        membership = EntityMembershipModel(
            user=user,
            entity=entity,
            role=role,
            status="active",
            valid_from=member_data.valid_from,
            valid_until=member_data.valid_until
        )
        
        await membership.save()
        return membership
    
    @staticmethod
    async def update_member(
        entity_id: str,
        user_id: str,
        update_data: EntityMemberUpdate,
        updated_by: UserModel
    ) -> EntityMembershipModel:
        """
        Update a member's role or status in an entity
        
        Args:
            entity_id: Entity ID
            user_id: User ID
            update_data: Update data
            updated_by: User performing the update
        
        Returns:
            Updated membership
        
        Raises:
            HTTPException: If membership not found or validation fails
        """
        # Find membership
        membership = await EntityMembershipModel.find_one(
            EntityMembershipModel.entity.id == PydanticObjectId(entity_id),
            EntityMembershipModel.user.id == PydanticObjectId(user_id),
            EntityMembershipModel.status != "revoked"
        )
        
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership not found"
            )
        
        # Update role if provided
        if update_data.role_id:
            role = await RoleModel.get(update_data.role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            
            # Validate role assignment
            entity = await membership.entity.fetch()
            await EntityMembershipService._validate_role_assignment(entity, role)
            
            membership.role = role
        
        # Update other fields
        update_dict = update_data.model_dump(exclude_unset=True, exclude={"role_id"})
        for field, value in update_dict.items():
            setattr(membership, field, value)
        
        membership.updated_at = datetime.now(timezone.utc)
        await membership.save()
        
        return membership
    
    @staticmethod
    async def remove_member(
        entity_id: str,
        user_id: str,
        removed_by: UserModel,
        hard_delete: bool = False
    ) -> bool:
        """
        Remove a member from an entity
        
        Args:
            entity_id: Entity ID
            user_id: User ID
            removed_by: User removing the member
            hard_delete: Whether to hard delete or soft delete
        
        Returns:
            Success status
        
        Raises:
            HTTPException: If membership not found
        """
        membership = await EntityMembershipModel.find_one(
            EntityMembershipModel.entity.id == PydanticObjectId(entity_id),
            EntityMembershipModel.user.id == PydanticObjectId(user_id),
            EntityMembershipModel.status == "active"
        )
        
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active membership not found"
            )
        
        # Check if removing last admin (prevent lockout)
        if await EntityMembershipService._is_last_admin(entity_id, membership):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last admin from the entity"
            )
        
        if hard_delete:
            await membership.delete()
        else:
            membership.status = "revoked"
            membership.updated_at = datetime.now(timezone.utc)
            await membership.save()
        
        return True
    
    @staticmethod
    async def list_entity_members(
        entity_id: str,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List all members of an entity with their roles
        
        Args:
            entity_id: Entity ID
            include_inactive: Whether to include inactive members
            page: Page number
            page_size: Items per page
        
        Returns:
            Tuple of (member_list, total_count)
        """
        # Build query
        query_conditions = [
            EntityMembershipModel.entity.id == PydanticObjectId(entity_id)
        ]
        
        if not include_inactive:
            query_conditions.append(EntityMembershipModel.status == "active")
        
        query = EntityMembershipModel.find(And(*query_conditions))
        
        # Get total count
        total = await query.count()
        
        # Apply pagination
        skip = (page - 1) * page_size
        memberships = await query.skip(skip).limit(page_size).to_list()
        
        # Enrich with user and role data
        enriched_members = []
        for membership in memberships:
            user = await membership.user.fetch()
            role = await membership.role.fetch()
            entity = await membership.entity.fetch()
            
            if user and role:
                enriched_members.append({
                    "id": str(membership.id),
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "user_name": f"{user.profile.first_name} {user.profile.last_name}" if user.profile else user.email,
                    "entity_id": str(entity.id),
                    "entity_name": entity.display_name,
                    "role_id": str(role.id),
                    "role_name": role.display_name,
                    "permissions": role.permissions,
                    "status": membership.status,
                    "valid_from": membership.valid_from,
                    "valid_until": membership.valid_until,
                    "created_at": membership.created_at,
                    "updated_at": membership.updated_at
                })
        
        return enriched_members, total
    
    @staticmethod
    async def list_user_memberships(
        user_id: str,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List all entity memberships for a user
        
        Args:
            user_id: User ID
            include_inactive: Whether to include inactive memberships
            page: Page number
            page_size: Items per page
        
        Returns:
            Tuple of (membership_list, total_count)
        """
        # Build query
        query_conditions = [
            EntityMembershipModel.user.id == PydanticObjectId(user_id)
        ]
        
        if not include_inactive:
            query_conditions.append(EntityMembershipModel.status == "active")
        
        query = EntityMembershipModel.find(And(*query_conditions))
        
        # Get total count
        total = await query.count()
        
        # Apply pagination
        skip = (page - 1) * page_size
        memberships = await query.skip(skip).limit(page_size).to_list()
        
        # Enrich with entity and role data
        enriched_memberships = []
        for membership in memberships:
            entity = await membership.entity.fetch()
            role = await membership.role.fetch()
            
            if entity and role:
                # Get entity path for context
                path = []
                current = entity
                while current:
                    path.insert(0, {
                        "id": str(current.id),
                        "name": current.display_name,
                        "type": current.entity_type
                    })
                    if current.parent_entity:
                        current = await current.parent_entity.fetch()
                    else:
                        break
                
                enriched_memberships.append({
                    "id": str(membership.id),
                    "entity_id": str(entity.id),
                    "entity_name": entity.display_name,
                    "entity_type": entity.entity_type,
                    "entity_class": entity.entity_class,
                    "entity_path": path,
                    "role_id": str(role.id),
                    "role_name": role.display_name,
                    "permissions": role.permissions,
                    "status": membership.status,
                    "valid_from": membership.valid_from,
                    "valid_until": membership.valid_until,
                    "created_at": membership.created_at
                })
        
        return enriched_memberships, total
    
    @staticmethod
    async def check_membership_validity(
        membership_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a membership is currently valid
        
        Args:
            membership_id: Membership ID
        
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        membership = await EntityMembershipModel.get(membership_id)
        if not membership:
            return False, "Membership not found"
        
        # Check status
        if membership.status != "active":
            return False, f"Membership is {membership.status}"
        
        # Check time validity
        now = datetime.now(timezone.utc)
        
        if membership.valid_from and now < membership.valid_from:
            return False, "Membership not yet valid"
        
        if membership.valid_until and now > membership.valid_until:
            return False, "Membership has expired"
        
        # Check if user is active
        user = await membership.user.fetch()
        if not user or not user.is_active:
            return False, "User is not active"
        
        # Check if entity is active
        entity = await membership.entity.fetch()
        if not entity or entity.status != "active":
            return False, "Entity is not active"
        
        return True, None
    
    @staticmethod
    async def _validate_role_assignment(
        entity: EntityModel,
        role: RoleModel
    ) -> None:
        """
        Validate that a role can be assigned in an entity
        
        Args:
            entity: Entity where role will be assigned
            role: Role to assign
        
        Raises:
            HTTPException: If role cannot be assigned
        """
        # Check if role belongs to the same entity or a parent
        if role.entity:
            role_entity = await role.entity.fetch()
            if role_entity:
                # Get entity path
                entity_path = await EntityMembershipService._get_entity_ancestors(entity)
                entity_ids = [e.id for e in entity_path]
                
                if role_entity.id not in entity_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Role does not belong to this entity or its ancestors"
                    )
        
        # Check assignable_at_types
        if role.assignable_at_types:
            if entity.entity_type not in role.assignable_at_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role cannot be assigned at {entity.entity_type} level"
                )
    
    @staticmethod
    async def _is_last_admin(
        entity_id: str,
        membership: EntityMembershipModel
    ) -> bool:
        """
        Check if this membership is the last admin in the entity
        
        Args:
            entity_id: Entity ID
            membership: Membership to check
        
        Returns:
            True if this is the last admin
        """
        # Get role
        role = await membership.role.fetch()
        if not role:
            return False
        
        # Check if role has admin permissions
        admin_permissions = [
            "entity:manage",
            "entity:manage_all",
            "user:manage",
            "user:manage_all"
        ]
        
        is_admin = any(perm in role.permissions for perm in admin_permissions)
        if not is_admin:
            return False
        
        # Count other admins
        other_admins = await EntityMembershipModel.find(
            EntityMembershipModel.entity.id == PydanticObjectId(entity_id),
            EntityMembershipModel.status == "active",
            EntityMembershipModel.id != membership.id
        ).to_list()
        
        for other in other_admins:
            other_role = await other.role.fetch()
            if other_role and any(perm in other_role.permissions for perm in admin_permissions):
                return False
        
        return True
    
    @staticmethod
    async def _get_entity_ancestors(entity: EntityModel) -> List[EntityModel]:
        """
        Get all ancestor entities including self
        
        Args:
            entity: Entity to get ancestors for
        
        Returns:
            List of entities from root to current
        """
        ancestors = [entity]
        current = entity
        
        while current.parent_entity:
            parent = await current.parent_entity.fetch()
            if parent:
                ancestors.insert(0, parent)
                current = parent
            else:
                break
        
        return ancestors