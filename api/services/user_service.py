from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from ..models.user_model import UserModel
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema
from .security_service import security_service
from .role_service import role_service

class UserService:
    """
    Service class for user-related business logic.
    """

    async def create_user(self, db: AsyncIOMotorDatabase, user_data: UserCreateSchema) -> UserModel:
        """
        Creates a new user in the database.
        """
        # Hash the password before storing
        hashed_password = security_service.get_password_hash(user_data.password)
        
        # Create a user model instance, excluding the plain password
        user_dict = user_data.model_dump(exclude={"password"})
        user_dict["password_hash"] = hashed_password
        
        new_user = UserModel(**user_dict)
        
        # Insert the new user into the database
        result = await db.users.insert_one(new_user.model_dump(by_alias=True))
        new_user.id = result.inserted_id
        
        return new_user

    async def create_sub_user(self, db: AsyncIOMotorDatabase, user_data: UserCreateSchema, client_account_id: ObjectId) -> UserModel:
        """
        Creates a new sub-user for a specific client account.
        Validates that assigned roles are assignable by client admins.
        """
        # Ensure all assigned roles are valid and assignable
        if user_data.roles:
            for role_id in user_data.roles:
                role = await role_service.get_role_by_id(db, role_id)
                if not role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role '{role_id}' not found.")
                if not role.is_assignable_by_main_client:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role_id}' cannot be assigned by a client administrator.")
        
        # Force the client account ID and set is_main_client to False
        user_data.client_account_id = client_account_id
        user_data.is_main_client = False

        # Use the existing create_user method to handle the rest
        return await self.create_user(db, user_data)

    async def get_user_by_id(self, db: AsyncIOMotorDatabase, user_id: ObjectId) -> Optional[UserModel]:
        """
        Retrieves a single user by their ID.
        """
        user_data = await db.users.find_one({"_id": user_id})
        if user_data:
            return UserModel(**user_data)
        return None

    async def get_user_by_email(self, db: AsyncIOMotorDatabase, email: str) -> Optional[UserModel]:
        """
        Retrieves a single user by their email address.
        """
        user_data = await db.users.find_one({"email": email})
        if user_data:
            return UserModel(**user_data)
        return None

    async def get_users(
        self, 
        db: AsyncIOMotorDatabase, 
        skip: int = 0, 
        limit: int = 100, 
        client_account_id: Optional[ObjectId] = None
    ) -> List[UserModel]:
        """
        Retrieves a list of users with pagination.
        If client_account_id is provided, filters users by that account.
        """
        query = {}
        if client_account_id:
            query["client_account_id"] = client_account_id
            
        users_cursor = db.users.find(query).skip(skip).limit(limit)
        users = await users_cursor.to_list(length=limit)
        return [UserModel(**user) for user in users]

    async def update_user(
        self,
        db: AsyncIOMotorDatabase, 
        user_id: ObjectId, 
        user_data: UserUpdateSchema,
        current_user: UserModel
    ) -> Optional[UserModel]:
        """
        Updates a user's information.
        If the updater is a main_client, validates that assigned roles are assignable.
        """
        update_data = user_data.model_dump(exclude_unset=True)
        
        # If roles are being updated by a main_client, validate them
        if "roles" in update_data and current_user.is_main_client:
            for role_id in update_data["roles"]:
                role = await role_service.get_role_by_id(db, role_id)
                if not role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role '{role_id}' not found.")
                if not role.is_assignable_by_main_client:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role_id}' cannot be assigned by a client administrator.")

        if not update_data:
            return await self.get_user_by_id(db, user_id)
            
        await db.users.update_one({"_id": user_id}, {"$set": update_data})
        
        updated_user = await self.get_user_by_id(db, user_id)
        return updated_user

    async def update_password(self, db: AsyncIOMotorDatabase, *, user_id: ObjectId, new_password: str):
        """
        Updates a user's password.
        """
        new_password_hash = security_service.get_password_hash(new_password)
        await db.users.update_one(
            {"_id": user_id},
            {"$set": {"password_hash": new_password_hash}}
        )

    async def delete_user(self, db: AsyncIOMotorDatabase, user_id: ObjectId) -> int:
        """
        Deletes a user from the database.
        Returns the number of users deleted.
        """
        result = await db.users.delete_one({"_id": user_id})
        return result.deleted_count

# Instantiate the service for use in other parts of the application
user_service = UserService() 