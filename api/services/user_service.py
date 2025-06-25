from typing import List, Optional, Set
from beanie import PydanticObjectId
from beanie.exceptions import RevisionIdWasChanged
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status

from ..models.user_model import UserModel, UserStatus
from ..models.client_account_model import ClientAccountModel
from ..models.group_model import GroupModel
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema, FailedUserCreationSchema
from .security_service import security_service
from .role_service import role_service

class UserService:
    """
    Service class for user-related business logic using Beanie ODM.
    """

    async def create_user(self, user_data: UserCreateSchema) -> UserModel:
        """
        Creates a new user in the database using Beanie ODM.
        """
        # Hash the password before storing
        hashed_password = security_service.get_password_hash(user_data.password)
        
        # Create a user model instance, excluding the plain password
        user_dict = user_data.model_dump(exclude={"password"})
        user_dict["password_hash"] = hashed_password
        
        # Handle client_account Link
        if user_data.client_account_id:
            try:
                client_account = await ClientAccountModel.get(PydanticObjectId(user_data.client_account_id))
                if client_account:
                    user_dict["client_account"] = client_account
                    del user_dict["client_account_id"]  # Remove the string ID
            except Exception:
                # If client account not found, set to None
                user_dict["client_account"] = None
                del user_dict["client_account_id"]
        else:
            user_dict["client_account"] = None
            if "client_account_id" in user_dict:
                del user_dict["client_account_id"]
        
        # Handle roles Links
        roles_list = []
        if user_data.roles:
            from ..models.role_model import RoleModel
            for role_identifier in user_data.roles:
                try:
                    # Try to treat as ObjectId first
                    role_id = PydanticObjectId(role_identifier)
                    role = await RoleModel.get(role_id)
                    if role:
                        roles_list.append(role)
                except Exception:
                    # If not a valid ObjectId, try to find by name
                    try:
                        role = await RoleModel.find_one(RoleModel.name == role_identifier)
                        if role:
                            roles_list.append(role)
                    except Exception:
                        continue  # Skip invalid role identifiers
        
        user_dict["roles"] = roles_list
        
        # Handle groups Links
        groups_list = []
        if user_data.groups:
            for group_id_str in user_data.groups:
                try:
                    group_id = PydanticObjectId(group_id_str)
                    group = await GroupModel.get(group_id)
                    if group:
                        groups_list.append(group)
                except Exception:
                    continue  # Skip invalid group IDs
        
        user_dict["groups"] = groups_list
        
        try:
            new_user = UserModel(**user_dict)
            await new_user.insert()
            return new_user
        except DuplicateKeyError as e:
            # Handle duplicate email constraint
            if "email" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User with email '{user_data.email}' already exists."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this information already exists."
                )

    async def create_sub_user(self, user_data: UserCreateSchema, client_account_id: str) -> UserModel:
        """
        Creates a new sub-user for a specific client account.
        Validates that assigned roles are assignable by client admins.
        """
        # Ensure all assigned roles are valid and assignable
        if user_data.roles:
            from ..models.role_model import RoleModel
            for role_identifier in user_data.roles:
                try:
                    # Try to get role by ObjectId first
                    role = await RoleModel.get(PydanticObjectId(role_identifier))
                except Exception:
                    # If not a valid ObjectId, try to find by name
                    role = await RoleModel.find_one(RoleModel.name == role_identifier)
                
                if not role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role '{role_identifier}' not found.")
                if not role.is_assignable_by_main_client:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role_identifier}' cannot be assigned by a client administrator.")
        
        # Force the client account ID and set is_main_client to False
        user_data.client_account_id = client_account_id
        user_data.is_main_client = False

        # Use the existing create_user method to handle the rest
        return await self.create_user(user_data)

    async def get_user_by_id(self, user_id: PydanticObjectId) -> Optional[UserModel]:
        """
        Retrieves a single user by their ID using Beanie ODM.
        """
        return await UserModel.get(user_id, fetch_links=True)

    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """
        Retrieves a single user by their email address using Beanie ODM.
        """
        return await UserModel.find_one(UserModel.email == email, fetch_links=True)

    async def get_users(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        client_account_id: Optional[PydanticObjectId] = None
    ) -> List[UserModel]:
        """
        Retrieves a list of users with pagination using Beanie ODM.
        If client_account_id is provided, filters users by that account.
        """
        if client_account_id:
            # Filter by client account
            query = UserModel.find(UserModel.client_account.id == client_account_id, fetch_links=True)
        else:
            query = UserModel.find(fetch_links=True)
            
        return await query.skip(skip).limit(limit).to_list()

    async def update_user(
        self,
        user_id: PydanticObjectId, 
        user_data: UserUpdateSchema,
        current_user: UserModel
    ) -> Optional[UserModel]:
        """
        Updates a user's information using Beanie ODM.
        If the updater is a main_client, validates that assigned roles are assignable.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
            
        update_data = user_data.model_dump(exclude_unset=True)
        
        # If roles are being updated by a main_client, validate them
        if "roles" in update_data and current_user.is_main_client:
            from ..models.role_model import RoleModel
            for role_identifier in update_data["roles"]:
                try:
                    # Try to get role by ObjectId first
                    role = await RoleModel.get(PydanticObjectId(role_identifier))
                except Exception:
                    # If not a valid ObjectId, try to find by name
                    role = await RoleModel.find_one(RoleModel.name == role_identifier)
                
                if not role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role '{role_identifier}' not found.")
                if not role.is_assignable_by_main_client:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role_identifier}' cannot be assigned by a client administrator.")

        # Handle roles updates
        if "roles" in update_data:
            from ..models.role_model import RoleModel
            roles_list = []
            for role_identifier in update_data["roles"]:
                try:
                    # Try to treat as ObjectId first
                    role_id = PydanticObjectId(role_identifier)
                    role = await RoleModel.get(role_id)
                    if role:
                        roles_list.append(role)
                except Exception:
                    # If not a valid ObjectId, try to find by name
                    try:
                        role = await RoleModel.find_one(RoleModel.name == role_identifier)
                        if role:
                            roles_list.append(role)
                    except Exception:
                        continue  # Skip invalid role identifiers
            update_data["roles"] = roles_list

        # Handle groups updates
        if "groups" in update_data:
            groups_list = []
            for group_id_str in update_data["groups"]:
                try:
                    group_id = PydanticObjectId(group_id_str)
                    group = await GroupModel.get(group_id)
                    if group:
                        groups_list.append(group)
                except Exception:
                    continue  # Skip invalid group IDs
            update_data["groups"] = groups_list

        if not update_data:
            return user
            
        # Update user fields
        for field, value in update_data.items():
            setattr(user, field, value)
            
        try:
            user.update_timestamp()
            await user.save()
            return user
        except DuplicateKeyError as e:
            # Handle duplicate email constraint on updates
            if "email" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User with email '{update_data.get('email', 'this email')}' already exists."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Update conflicts with existing user data."
                )
        except RevisionIdWasChanged as e:
            # Beanie may wrap DuplicateKeyError in RevisionIdWasChanged during updates
            # First check if the original error is a duplicate key error
            original_error_str = str(e.__cause__ or e)
            if "duplicate key error" in original_error_str.lower() and "email" in original_error_str:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User with email '{update_data.get('email', 'this email')}' already exists."
                )
            
            # If we're updating email and got RevisionIdWasChanged, it's likely a duplicate key issue
            # even if Beanie didn't preserve the original error properly
            if "email" in update_data:
                # Verify by checking if a user with this email already exists
                existing_user = await self.get_user_by_email(update_data["email"])
                if existing_user and existing_user.id != user.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"User with email '{update_data['email']}' already exists."
                    )
            
            # Re-raise if it's an actual revision conflict or other issue
            raise

    async def update_password(self, user_id: PydanticObjectId, new_password: str):
        """
        Updates a user's password using Beanie ODM.
        """
        user = await self.get_user_by_id(user_id)
        if user:
            user.password_hash = security_service.get_password_hash(new_password)
            user.update_timestamp()
            await user.save()

    async def delete_user(self, user_id: PydanticObjectId) -> bool:
        """
        Deletes a user from the database using Beanie ODM.
        Returns True if deleted, False if user not found.
        """
        user = await self.get_user_by_id(user_id)
        if user:
            await user.delete()
            return True
        return False

    async def bulk_create_users(
        self, 
        users_data: List[UserCreateSchema]
    ) -> tuple[List[UserModel], List[FailedUserCreationSchema]]:
        """
        Creates multiple users in a single operation, handling individual failures.
        """
        successful_creates = []
        failed_creates = []

        for user_data in users_data:
            try:
                # We can reuse the existing create_user method
                new_user = await self.create_user(user_data)
                successful_creates.append(new_user)
            except Exception as e:
                # Capture the user data and the error message for reporting
                failed_creates.append(
                    FailedUserCreationSchema(user_data=user_data, error=str(e))
                )
        
        return successful_creates, failed_creates

    async def get_user_effective_permissions(self, user_id: PydanticObjectId) -> Set[str]:
        """
        Get all effective permissions for a user from:
        1. Direct role assignments
        2. Group memberships
        
        Returns clean permission names (not ObjectIds).
        """
        from ..models.permission_model import PermissionModel
        
        user = await self.get_user_by_id(user_id)
        if not user:
            return set()
        
        permission_ids = set()
        
        # Get permission IDs from direct roles (now Links)
        if user.roles:
            for role in user.roles:
                if hasattr(role, 'permissions') and role.permissions:
                    # Extract ObjectIds from the Link objects
                    for permission_link in role.permissions:
                        if hasattr(permission_link, 'id'):
                            permission_ids.add(permission_link.id)
                        else:
                            # Fallback if it's still an ObjectId
                            permission_ids.add(permission_link)
        
        # Get permission IDs from groups (already Links)
        if user.groups:
            for group in user.groups:
                if hasattr(group, 'permissions') and group.permissions:
                    # Extract ObjectIds from the Link objects
                    for permission_link in group.permissions:
                        if hasattr(permission_link, 'id'):
                            permission_ids.add(permission_link.id)
                        else:
                            # Fallback if it's still an ObjectId
                            permission_ids.add(permission_link)
        
        # Resolve permission IDs to clean permission names
        permission_names = set()
        for permission_id in permission_ids:
            try:
                permission = await PermissionModel.get(permission_id)
                if permission:
                    permission_names.add(permission.name)
            except Exception:
                continue  # Skip invalid permission IDs
                
        return permission_names

    async def get_user_effective_permission_details(self, user_id: PydanticObjectId) -> List:
        """
        Get all effective permissions for a user with full permission details.
        Returns PermissionDetailSchema objects for API responses.
        
        Args:
            user_id: User's ObjectId
            
        Returns:
            List of PermissionDetailSchema objects with id, name, scope, etc.
        """
        from .permission_service import permission_service
        
        user = await self.get_user_by_id(user_id)
        if not user:
            return []
        
        permission_ids = set()
        
        # Get permission IDs from direct roles (now Links)
        if user.roles:
            for role in user.roles:
                if hasattr(role, 'permissions') and role.permissions:
                    # Extract ObjectIds from the Link objects
                    for permission_link in role.permissions:
                        if hasattr(permission_link, 'id'):
                            permission_ids.add(permission_link.id)
                        else:
                            # Fallback if it's still an ObjectId
                            permission_ids.add(permission_link)
        
        # Get permission IDs from groups (already Links)
        if user.groups:
            for group in user.groups:
                if hasattr(group, 'permissions') and group.permissions:
                    # Extract ObjectIds from the Link objects
                    for permission_link in group.permissions:
                        if hasattr(permission_link, 'id'):
                            permission_ids.add(permission_link.id)
                        else:
                            # Fallback if it's still an ObjectId
                            permission_ids.add(permission_link)
        
        # Convert permission IDs to detailed permission information
        permission_details = await permission_service.resolve_permissions_to_details(list(permission_ids))
        
        return permission_details

# Instantiate the service for use in other parts of the application
user_service = UserService() 