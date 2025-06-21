from typing import List, Optional, Set
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status

from ..models.group_model import GroupModel
from ..models.client_account_model import ClientAccountModel
from ..models.user_model import UserModel
from ..schemas.group_schema import GroupCreateSchema, GroupUpdateSchema
from .role_service import role_service

class GroupService:
    """
    Service class for group-related business logic using Beanie ODM.
    """

    async def create_group(self, group_data: GroupCreateSchema) -> GroupModel:
        """
        Creates a new group in the database using Beanie ODM.
        """
        # Handle client_account Link
        client_account = await ClientAccountModel.get(PydanticObjectId(group_data.client_account_id))
        if not client_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client account {group_data.client_account_id} not found"
            )
        
        # Validate roles exist
        if group_data.roles:
            for role_id in group_data.roles:
                role = await role_service.get_role_by_id(role_id)
                if not role:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Role '{role_id}' not found"
                    )
        
        # Create group model instance
        group_dict = group_data.model_dump(exclude={"client_account_id"})
        group_dict["client_account"] = client_account
        
        new_group = GroupModel(**group_dict)
        
        try:
            await new_group.insert()
        except DuplicateKeyError as e:
            # Handle duplicate key errors gracefully
            if "name" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A group with this name already exists in this client account."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A group with these details already exists."
                )
        
        return new_group

    async def get_group_by_id(self, group_id: PydanticObjectId) -> Optional[GroupModel]:
        """
        Retrieves a single group by its ID using Beanie ODM.
        """
        return await GroupModel.get(group_id, fetch_links=True)

    async def get_groups(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        client_account_id: Optional[PydanticObjectId] = None
    ) -> List[GroupModel]:
        """
        Retrieves a list of groups with pagination using Beanie ODM.
        If client_account_id is provided, filters groups by that account.
        """
        query = GroupModel.find(fetch_links=True)
        
        if client_account_id:
            # Get the client account first
            client_account = await ClientAccountModel.get(client_account_id)
            if client_account:
                query = query.find(GroupModel.client_account.id == client_account_id)
            
        return await query.skip(skip).limit(limit).to_list()

    async def update_group(
        self,
        group_id: PydanticObjectId, 
        group_data: GroupUpdateSchema
    ) -> Optional[GroupModel]:
        """
        Updates a group's information using Beanie ODM.
        """
        group = await self.get_group_by_id(group_id)
        if not group:
            return None
            
        update_data = group_data.model_dump(exclude_unset=True)
        
        # Validate roles if being updated
        if "roles" in update_data:
            for role_id in update_data["roles"]:
                role = await role_service.get_role_by_id(role_id)
                if not role:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Role '{role_id}' not found"
                    )

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
        Deletes a group from the database using Beanie ODM.
        First removes all users from the group.
        Returns True if deleted, False if group not found.
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
        """
        Adds multiple users to a group.
        """
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
        """
        Removes multiple users from a group.
        """
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
            # Find and remove the group Link from user.groups
            # Compare Link IDs properly
            user.groups = [g for g in user.groups if g.ref.id != group_id]
            user.update_timestamp()
            await user.save()
        
        return True

    async def remove_all_users_from_group(self, group_id: PydanticObjectId) -> bool:
        """
        Removes all users from a group (used during group deletion).
        """
        # Find all users who are members of this group
        users = await UserModel.find(UserModel.groups.id == group_id).to_list()
        
        for user in users:
            # Remove the group from user's groups list
            user.groups = [g for g in user.groups if g.id != group_id]
            user.update_timestamp()
            await user.save()
        
        return True

    async def get_group_members(self, group_id: PydanticObjectId) -> List[UserModel]:
        """
        Gets all users who are members of a specific group.
        """
        return await UserModel.find(UserModel.groups.id == group_id).to_list()

    async def get_user_groups(self, user_id: PydanticObjectId) -> List[GroupModel]:
        """
        Gets all groups that a user belongs to.
        """
        user = await UserModel.get(user_id, fetch_links=True)
        if not user:
            return []
        
        return [await group.fetch() for group in user.groups] if user.groups else []

    async def get_user_effective_roles(self, user_id: PydanticObjectId) -> Set[str]:
        """
        Gets all effective roles for a user (direct roles + group roles).
        """
        user = await UserModel.get(user_id, fetch_links=True)
        if not user:
            return set()
        
        effective_roles = set(user.roles or [])  # Direct roles
        
        # Add roles from groups
        if user.groups:
            for group_link in user.groups:
                group = await group_link.fetch()
                if group and group.is_active:
                    effective_roles.update(group.roles or [])
        
        return effective_roles

    async def get_user_effective_permissions(self, user_id: PydanticObjectId) -> Set[str]:
        """
        Gets all effective permissions for a user (from direct roles + group roles).
        """
        effective_roles = await self.get_user_effective_roles(user_id)
        effective_permissions = set()
        
        # Get permissions from all effective roles
        for role_id in effective_roles:
            role = await role_service.get_role_by_id(role_id)
            if role and role.permissions:
                effective_permissions.update(role.permissions)
        
        return effective_permissions

# Instantiate the service for use in other parts of the application
group_service = GroupService() 