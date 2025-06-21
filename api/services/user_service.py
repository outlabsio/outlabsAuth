from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from bson import ObjectId

from ..models.user_model import UserModel
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema
from .security_service import security_service

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
        created_user = await self.get_user_by_id(db, result.inserted_id)
        
        return created_user

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

    async def get_users(self, db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100) -> List[UserModel]:
        """
        Retrieves a list of users with pagination.
        """
        users_cursor = db.users.find().skip(skip).limit(limit)
        users = await users_cursor.to_list(length=limit)
        return [UserModel(**user) for user in users]

    async def update_user(self, db: AsyncIOMotorDatabase, user_id: ObjectId, user_data: UserUpdateSchema) -> Optional[UserModel]:
        """
        Updates a user's information.
        """
        update_data = user_data.model_dump(exclude_unset=True)
        
        if not update_data:
            return await self.get_user_by_id(db, user_id)
            
        await db.users.update_one({"_id": user_id}, {"$set": update_data})
        
        updated_user = await self.get_user_by_id(db, user_id)
        return updated_user

    async def delete_user(self, db: AsyncIOMotorDatabase, user_id: ObjectId) -> int:
        """
        Deletes a user from the database.
        Returns the number of users deleted.
        """
        result = await db.users.delete_one({"_id": user_id})
        return result.deleted_count

# Instantiate the service for use in other parts of the application
user_service = UserService() 