from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional

from ..models.permission_model import PermissionModel
from ..schemas.permission_schema import PermissionCreateSchema

class PermissionService:
    """
    Service class for permission-related business logic.
    """

    async def create_permission(self, db: AsyncIOMotorDatabase, permission_data: PermissionCreateSchema) -> PermissionModel:
        """
        Creates a new permission in the database.
        """
        permission = PermissionModel(**permission_data.model_dump(by_alias=True))
        await db.permissions.insert_one(permission.model_dump(by_alias=True))
        created_permission = await self.get_permission_by_id(db, permission.id)
        return created_permission

    async def get_permission_by_id(self, db: AsyncIOMotorDatabase, permission_id: str) -> Optional[PermissionModel]:
        """
        Retrieves a single permission by its ID.
        """
        permission_data = await db.permissions.find_one({"_id": permission_id})
        if permission_data:
            return PermissionModel(**permission_data)
        return None

    async def get_permissions(self, db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100) -> List[PermissionModel]:
        """
        Retrieves a list of permissions with pagination.
        """
        permissions_cursor = db.permissions.find().skip(skip).limit(limit)
        permissions = await permissions_cursor.to_list(length=limit)
        return [PermissionModel(**permission) for permission in permissions]

permission_service = PermissionService() 