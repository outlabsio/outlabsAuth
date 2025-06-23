from typing import List, Optional
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status

from ..models.client_account_model import ClientAccountModel
from ..models.user_model import UserModel
from ..schemas.client_account_schema import ClientAccountCreateSchema, ClientAccountUpdateSchema

class ClientAccountService:
    """
    Service class for client account-related business logic using Beanie ODM.
    Enhanced for Hierarchical Multi-Platform Tenancy.
    """

    async def create_client_account(self, account_data: ClientAccountCreateSchema, created_by_client_id: Optional[str] = None) -> ClientAccountModel:
        """
        Creates a new client account using Beanie ODM.
        Enhanced for hierarchical multi-platform tenancy.
        """
        account_dict = account_data.model_dump()
        
        # Handle main_contact_user Link
        if account_data.main_contact_user_id:
            try:
                user = await UserModel.get(PydanticObjectId(account_data.main_contact_user_id))
                if user:
                    account_dict["main_contact_user"] = user
                    del account_dict["main_contact_user_id"]  # Remove the string ID
            except Exception:
                # If user not found, set to None
                account_dict["main_contact_user"] = None
                del account_dict["main_contact_user_id"]
        else:
            account_dict["main_contact_user"] = None
            if "main_contact_user_id" in account_dict:
                del account_dict["main_contact_user_id"]
        
        # Set hierarchical relationship if created by another client
        if created_by_client_id:
            account_dict["created_by_client_id"] = created_by_client_id
            
            # Get parent client to inherit platform_id
            parent_client = await self.get_client_account_by_id(PydanticObjectId(created_by_client_id))
            if parent_client:
                account_dict["platform_id"] = parent_client.platform_id
        
        account = ClientAccountModel(**account_dict)
        try:
            await account.insert()
            
            # Update parent's child_clients list if this is a sub-client
            if created_by_client_id:
                parent_client = await self.get_client_account_by_id(PydanticObjectId(created_by_client_id))
                if parent_client:
                    parent_client.child_clients.append(str(account.id))
                    await parent_client.save()
                    
        except DuplicateKeyError as e:
            # Handle duplicate key errors gracefully
            if "name" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A client account with this name already exists."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A client account with these details already exists."
                )
        
        return account

    async def get_client_account_by_id(self, account_id: PydanticObjectId) -> Optional[ClientAccountModel]:
        """
        Retrieves a single client account by its ID using Beanie ODM.
        """
        return await ClientAccountModel.get(account_id)

    async def get_client_accounts(self, skip: int = 0, limit: int = 100, 
                                platform_id: Optional[str] = None,
                                created_by_client_id: Optional[str] = None) -> List[ClientAccountModel]:
        """
        Retrieves a list of client accounts with pagination using Beanie ODM.
        Enhanced for platform-scoped and hierarchical filtering.
        """
        query = {}
        
        # Filter by platform if specified
        if platform_id:
            query["platform_id"] = platform_id
            
        # Filter by creator if specified (for platform admins)
        if created_by_client_id:
            query["created_by_client_id"] = created_by_client_id
        
        if query:
            return await ClientAccountModel.find(query).skip(skip).limit(limit).to_list()
        else:
            return await ClientAccountModel.find().skip(skip).limit(limit).to_list()

    async def get_client_accounts_by_platform(self, platform_id: str, skip: int = 0, limit: int = 100) -> List[ClientAccountModel]:
        """
        Retrieves all client accounts within a specific platform.
        For platform admins to see all clients in their platform.
        """
        return await ClientAccountModel.find(
            ClientAccountModel.platform_id == platform_id
        ).skip(skip).limit(limit).to_list()

    async def get_client_accounts_created_by(self, created_by_client_id: str, skip: int = 0, limit: int = 100) -> List[ClientAccountModel]:
        """
        Retrieves all client accounts created by a specific client.
        For platform admins to see only their created sub-clients.
        """
        return await ClientAccountModel.find(
            ClientAccountModel.created_by_client_id == created_by_client_id
        ).skip(skip).limit(limit).to_list()

    async def get_sub_clients(self, parent_client_id: str) -> List[ClientAccountModel]:
        """
        Gets all direct sub-clients of a parent client account.
        """
        return await ClientAccountModel.find(
            ClientAccountModel.created_by_client_id == parent_client_id
        ).to_list()

    async def can_user_access_client_account(self, user_client_id: str, target_client_id: str, 
                                           user_permissions: List[str], is_super_admin: bool = False) -> bool:
        """
        Determines if a user can access a specific client account based on hierarchical rules.
        
        Args:
            user_client_id: The user's client account ID
            target_client_id: The client account they're trying to access
            user_permissions: List of user's permissions
            is_super_admin: Whether user has super admin permissions
        
        Returns:
            bool: Whether access is allowed
        """
        if is_super_admin:
            return True
            
        # Get user's client account
        user_client = await self.get_client_account_by_id(PydanticObjectId(user_client_id))
        target_client = await self.get_client_account_by_id(PydanticObjectId(target_client_id))
        
        if not user_client or not target_client:
            return False
            
        # Same client account - always allowed
        if user_client_id == target_client_id:
            return True
            
        # Platform admin permissions
        if "client_account:read_platform" in user_permissions:
            # Can access all clients in same platform
            return user_client.platform_id == target_client.platform_id
            
        if "client_account:read_created" in user_permissions:
            # Can access clients they created
            return target_client.created_by_client_id == user_client_id
            
        return False

    async def update_client_account(self, account_id: PydanticObjectId, account_data: ClientAccountUpdateSchema) -> Optional[ClientAccountModel]:
        """
        Updates a client account's information using Beanie ODM.
        """
        account = await self.get_client_account_by_id(account_id)
        if not account:
            return None
            
        update_data = account_data.model_dump(exclude_unset=True)
        if not update_data:
            return account
        
        # Handle main_contact_user Link update
        if "main_contact_user_id" in update_data:
            user_id = update_data.pop("main_contact_user_id")
            if user_id:
                try:
                    user = await UserModel.get(PydanticObjectId(user_id))
                    account.main_contact_user = user
                except Exception:
                    account.main_contact_user = None
            else:
                account.main_contact_user = None
        
        # Update other fields
        for field, value in update_data.items():
            setattr(account, field, value)
        
        try:
            account.update_timestamp()
            await account.save()
        except DuplicateKeyError as e:
            # Handle duplicate key errors gracefully
            if "name" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A client account with this name already exists."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A client account with these details already exists."
                )
                
        return account

    async def delete_client_account(self, account_id: PydanticObjectId) -> bool:
        """
        Deletes a client account using Beanie ODM.
        Enhanced to handle hierarchical relationships.
        """
        account = await self.get_client_account_by_id(account_id)
        if not account:
            return False
            
        # Remove from parent's child_clients list if this is a sub-client
        if account.created_by_client_id:
            parent_client = await self.get_client_account_by_id(PydanticObjectId(account.created_by_client_id))
            if parent_client and str(account.id) in parent_client.child_clients:
                parent_client.child_clients.remove(str(account.id))
                await parent_client.save()
        
        # Note: In a real implementation, you'd also need to handle cascading
        # deletion of sub-clients or prevent deletion if sub-clients exist
        
        await account.delete()
        return True

client_account_service = ClientAccountService() 