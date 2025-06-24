from typing import List, Optional, Set
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status

from ..models.group_model import GroupModel
from ..models.scopes import GroupScope
from ..models.client_account_model import ClientAccountModel
from ..models.user_model import UserModel
from ..schemas.group_schema import (
    GroupCreateSchema, 
    GroupUpdateSchema,
    GroupResponseSchema,
    AvailableGroupsResponseSchema
)
from .role_service import role_service
from .permission_service import permission_service

class GroupService:
    """
    Service class for group-related business logic with scoped groups.
    """

    async def create_group(
        self, 
        group_data: GroupCreateSchema,
        current_user_id: str,
        current_client_id: Optional[str] = None,
        scope_id: Optional[str] = None
    ) -> GroupModel:
        """
        Create a new scoped group with direct permissions.
        
        Args:
            group_data: Group creation data
            current_user_id: ID of user creating the group
            current_client_id: Client ID of current user
            scope_id: Explicit scope ID (platform_id or client_account_id)
        """
        # Determine scope_id based on group scope
        if group_data.scope == GroupScope.SYSTEM:
            final_scope_id = None
        elif group_data.scope == GroupScope.CLIENT:
            final_scope_id = scope_id or current_client_id
            if not final_scope_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client ID required for client-scoped groups"
                )
        elif group_data.scope == GroupScope.PLATFORM:
            if not scope_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Platform ID required for platform-scoped groups"
                )
            final_scope_id = scope_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scope: {group_data.scope}"
            )

        # Check if group name already exists in this scope
        existing_group = await GroupModel.find_one(
            GroupModel.name == group_data.name,
            GroupModel.scope == group_data.scope,
            GroupModel.scope_id == final_scope_id
        )
        
        if existing_group:
            scope_desc = f"{group_data.scope} scope"
            if final_scope_id:
                scope_desc += f" ({final_scope_id})"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Group '{group_data.name}' already exists in {scope_desc}"
            )

        # Convert permission names to ObjectIds and validate they exist
        permission_ids = []
        if group_data.permissions:
            for permission_name in group_data.permissions:
                # Check if it's already an ObjectId (for backward compatibility)
                try:
                    from beanie import PydanticObjectId
                    # If it's already an ObjectId, validate it exists
                    permission_id = PydanticObjectId(permission_name)
                    permission = await permission_service.get_permission_by_id(str(permission_id))
                    if not permission:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Permission with ID '{permission_name}' not found"
                        )
                    permission_ids.append(str(permission_id))
                except Exception:
                    # It's a permission name, find the ObjectId
                    from ..models.permission_model import PermissionModel
                    permission = await PermissionModel.find_one(PermissionModel.name == permission_name)
                    if not permission:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Permission '{permission_name}' not found"
                        )
                    permission_ids.append(str(permission.id))

        # Create group
        group = GroupModel(
            name=group_data.name,
            display_name=group_data.display_name,
            description=group_data.description,
            permissions=permission_ids,
            scope=group_data.scope,
            scope_id=final_scope_id,
            created_by_user_id=current_user_id,
            created_by_client_id=current_client_id
        )
        
        try:
            await group.insert()
        except DuplicateKeyError as e:
            # Handle duplicate key errors gracefully
            if "name" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A group with this name already exists in this scope."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A group with these details already exists."
                )
        
        return group

    async def get_group_by_id(self, group_id: PydanticObjectId) -> Optional[GroupModel]:
        """Get a group by its MongoDB ObjectId."""
        return await GroupModel.get(group_id, fetch_links=True)

    async def get_groups_by_scope(
        self, 
        scope: GroupScope, 
        scope_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[GroupModel]:
        """Get all groups for a specific scope."""
        if scope == GroupScope.SYSTEM:
            # For system groups, just query by scope since scope_id should be None
            groups = await GroupModel.find(
                GroupModel.scope == scope
            ).skip(skip).limit(limit).to_list()
        else:
            # For platform/client groups, filter by scope_id if provided
            if scope_id is not None:
                groups = await GroupModel.find(
                    GroupModel.scope == scope,
                    GroupModel.scope_id == scope_id
                ).skip(skip).limit(limit).to_list()
            else:
                groups = await GroupModel.find(
                    GroupModel.scope == scope
                ).skip(skip).limit(limit).to_list()
            
        return groups

    async def get_available_groups_for_user(
        self,
        current_user_client_id: Optional[str] = None,
        current_user_platform_id: Optional[str] = None,
        is_super_admin: bool = False,
        is_platform_admin: bool = False
    ) -> AvailableGroupsResponseSchema:
        """
        Get groups that a user can assign to others, grouped by scope.
        """
        available_groups = AvailableGroupsResponseSchema()

        # System groups (only super admins can assign these)
        if is_super_admin:
            system_groups = await self.get_groups_by_scope(GroupScope.SYSTEM)
            available_groups.system_groups = [
                GroupResponseSchema.model_validate(group) for group in system_groups
            ]

        # Platform groups (platform admins can assign within their platform)
        if is_super_admin or (is_platform_admin and current_user_platform_id):
            platform_groups = await self.get_groups_by_scope(
                GroupScope.PLATFORM, 
                current_user_platform_id
            )
            available_groups.platform_groups = [
                GroupResponseSchema.model_validate(group) for group in platform_groups
            ]

        # Client groups (client admins can assign within their client)
        if current_user_client_id:
            client_groups = await self.get_groups_by_scope(
                GroupScope.CLIENT,
                current_user_client_id
            )
            available_groups.client_groups = [
                GroupResponseSchema.model_validate(group) for group in client_groups
            ]

        return available_groups

    async def update_group(
        self,
        group_id: PydanticObjectId, 
        group_data: GroupUpdateSchema
    ) -> Optional[GroupModel]:
        """Update a group by ID."""
        group = await self.get_group_by_id(group_id)
        if not group:
            return None
            
        update_data = group_data.model_dump(exclude_unset=True)
        
        # Convert permission names to ObjectIds and validate if being updated
        if "permissions" in update_data:
            permission_ids = []
            for permission_name in update_data["permissions"]:
                # Check if it's already an ObjectId (for backward compatibility)
                try:
                    from beanie import PydanticObjectId
                    # If it's already an ObjectId, validate it exists
                    permission_id = PydanticObjectId(permission_name)
                    permission = await permission_service.get_permission_by_id(str(permission_id))
                    if not permission:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Permission with ID '{permission_name}' not found"
                        )
                    permission_ids.append(str(permission_id))
                except Exception:
                    # It's a permission name, find the ObjectId
                    from ..models.permission_model import PermissionModel
                    permission = await PermissionModel.find_one(PermissionModel.name == permission_name)
                    if not permission:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Permission '{permission_name}' not found"
                        )
                    permission_ids.append(str(permission.id))
            update_data["permissions"] = permission_ids

        if not update_data:
            return group
            
        # Update group fields
        for field, value in update_data.items():
            setattr(group, field, value)
            
        group.update_timestamp()
        await group.save()
        
        return group

    async def delete_group(self, group_id: PydanticObjectId) -> bool:
        """
        Delete a group by ID.
        First removes all users from the group.
        """
        group = await self.get_group_by_id(group_id)
        if not group:
            return False
            
        # Remove all users from this group
        await self.remove_all_users_from_group(group_id)
        
        # Delete the group
        await group.delete()
        return True

    async def add_users_to_group(self, group_id: PydanticObjectId, user_ids: List[str]) -> bool:
        """Add multiple users to a group."""
        group = await self.get_group_by_id(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        # Convert user IDs and validate they exist
        valid_users = []
        for user_id_str in user_ids:
            try:
                user_id = PydanticObjectId(user_id_str)
                user = await UserModel.get(user_id)
                if user:
                    valid_users.append(user)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User {user_id_str} not found"
                    )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid user ID: {user_id_str}"
                )
        
        # Add group to each user's groups list
        for user in valid_users:
            if group not in user.groups:
                user.groups.append(group)
                user.update_timestamp()
                await user.save()
        
        return True

    async def remove_users_from_group(self, group_id: PydanticObjectId, user_ids: List[str]) -> bool:
        """Remove multiple users from a group."""
        group = await self.get_group_by_id(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        # Convert user IDs and validate they exist
        valid_users = []
        for user_id_str in user_ids:
            try:
                user_id = PydanticObjectId(user_id_str)
                user = await UserModel.get(user_id, fetch_links=True)
                if user:
                    valid_users.append(user)
            except Exception:
                continue  # Skip invalid user IDs
        
        # Remove group from each user's groups list
        for user in valid_users:
            user.groups = [g for g in user.groups if str(g.id) != str(group_id)]
            user.update_timestamp()
            await user.save()
        
        return True

    async def remove_all_users_from_group(self, group_id: PydanticObjectId) -> bool:
        """Remove all users from a group."""
        # Find all users that belong to this group
        users_in_group = await UserModel.find(
            UserModel.groups.id == group_id, 
            fetch_links=True
        ).to_list()
        
        # Remove the group from each user
        for user in users_in_group:
            user.groups = [g for g in user.groups if str(g.id) != str(group_id)]
            user.update_timestamp()
            await user.save()
        
        return True

    async def get_group_members(self, group_id: PydanticObjectId) -> List[UserModel]:
        """Get all users that belong to a specific group."""
        return await UserModel.find(
            UserModel.groups.id == group_id,
            fetch_links=True
        ).to_list()

    async def get_user_groups(self, user_id: PydanticObjectId) -> List[GroupModel]:
        """Get all groups that a user belongs to."""
        user = await UserModel.get(user_id, fetch_links=True)
        return user.groups if user and user.groups else []

    async def get_user_effective_permissions(self, user_id: PydanticObjectId) -> Set[str]:
        """
        Get all effective permissions for a user from:
        1. Direct role assignments
        2. Group memberships
        
        Returns clean permission names (not ObjectIds).
        """
        from ..models.permission_model import PermissionModel
        
        user = await UserModel.get(user_id, fetch_links=True)
        if not user:
            return set()
        
        permission_ids = set()
        
        # Get permission IDs from direct roles
        # (This will be handled by user_service, but included for completeness)
        for role_id in user.roles:
            try:
                role = await role_service.get_role_by_id(PydanticObjectId(role_id))
                if role:
                    permission_ids.update(role.permissions)
            except Exception:
                continue  # Skip invalid role IDs
        
        # Get permission IDs from groups
        user_groups = await self.get_user_groups(user.id)
        for group in user_groups:
            if hasattr(group, 'permissions'):
                permission_ids.update(group.permissions)
        
        # Resolve permission IDs to clean permission names
        permission_names = set()
        for permission_id in permission_ids:
            try:
                permission = await PermissionModel.get(PydanticObjectId(permission_id))
                if permission:
                    permission_names.add(permission.name)
            except Exception:
                continue  # Skip invalid permission IDs
                
        return permission_names

    async def get_groups(
        self, 
        skip: int = 0, 
        limit: int = 100,
        scope: Optional[GroupScope] = None,
        scope_id: Optional[str] = None
    ) -> List[GroupModel]:
        """
        Get groups with optional filtering by scope.
        """
        if scope:
            return await self.get_groups_by_scope(scope, scope_id, skip, limit)
        else:
            return await GroupModel.find().skip(skip).limit(limit).to_list()

    async def resolve_permission_names(self, permission_ids: List[str]) -> List[str]:
        """
        Convert permission ObjectIds to clean permission names.
        """
        from ..models.permission_model import PermissionModel
        from beanie import PydanticObjectId
        
        permission_names = []
        for permission_id in permission_ids:
            try:
                permission = await PermissionModel.get(PydanticObjectId(permission_id))
                if permission:
                    permission_names.append(permission.name)
            except Exception:
                continue  # Skip invalid permission IDs
        
        return permission_names

    async def group_to_response_dict(self, group: GroupModel) -> dict:
        """
        Convert a GroupModel to a dictionary with resolved permission names.
        """
        group_dict = group.model_dump(by_alias=True)
        
        # Resolve permission ObjectIds to clean names
        if group.permissions:
            group_dict["permissions"] = await self.resolve_permission_names(group.permissions)
        else:
            group_dict["permissions"] = []
            
        return group_dict

# Instantiate the service for use in other parts of the application
group_service = GroupService() 