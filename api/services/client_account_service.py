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
    """

    async def create_client_account(self, account_data: ClientAccountCreateSchema) -> ClientAccountModel:
        """
        Creates a new client account using Beanie ODM.
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
        
        account = ClientAccountModel(**account_dict)
        try:
            await account.insert()
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

    async def get_client_accounts(self, skip: int = 0, limit: int = 100) -> List[ClientAccountModel]:
        """
        Retrieves a list of client accounts with pagination using Beanie ODM.
        """
        return await ClientAccountModel.find().skip(skip).limit(limit).to_list()

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
        (Note: In a real-world scenario, this would likely deactivate the account
        and trigger a cleanup process for associated users, rather than a hard delete.)
        """
        account = await self.get_client_account_by_id(account_id)
        if account:
            await account.delete()
            return True
        return False

client_account_service = ClientAccountService() 