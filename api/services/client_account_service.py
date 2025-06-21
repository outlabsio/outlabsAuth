from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from bson import ObjectId

from ..models.client_account_model import ClientAccountModel
from ..schemas.client_account_schema import ClientAccountCreateSchema, ClientAccountUpdateSchema

class ClientAccountService:
    """
    Service class for client account-related business logic.
    """

    async def create_client_account(self, db: AsyncIOMotorDatabase, account_data: ClientAccountCreateSchema) -> ClientAccountModel:
        """
        Creates a new client account.
        """
        account = ClientAccountModel(**account_data.model_dump())
        await db.client_accounts.insert_one(account.model_dump(by_alias=True))
        created_account = await self.get_client_account_by_id(db, account.id)
        return created_account

    async def get_client_account_by_id(self, db: AsyncIOMotorDatabase, account_id: ObjectId) -> Optional[ClientAccountModel]:
        """
        Retrieves a single client account by its ID.
        """
        account_data = await db.client_accounts.find_one({"_id": account_id})
        if account_data:
            return ClientAccountModel(**account_data)
        return None

    async def get_client_accounts(self, db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100) -> List[ClientAccountModel]:
        """
        Retrieves a list of client accounts with pagination.
        """
        accounts_cursor = db.client_accounts.find().skip(skip).limit(limit)
        accounts = await accounts_cursor.to_list(length=limit)
        return [ClientAccountModel(**account) for account in accounts]

    async def update_client_account(self, db: AsyncIOMotorDatabase, account_id: ObjectId, account_data: ClientAccountUpdateSchema) -> Optional[ClientAccountModel]:
        """
        Updates a client account's information.
        """
        update_data = account_data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_client_account_by_id(db, account_id)
            
        await db.client_accounts.update_one({"_id": account_id}, {"$set": update_data})
        return await self.get_client_account_by_id(db, account_id)

    async def delete_client_account(self, db: AsyncIOMotorDatabase, account_id: ObjectId) -> int:
        """
        Deletes a client account.
        (Note: In a real-world scenario, this would likely deactivate the account
        and trigger a cleanup process for associated users, rather than a hard delete.)
        """
        result = await db.client_accounts.delete_one({"_id": account_id})
        return result.deleted_count

client_account_service = ClientAccountService() 