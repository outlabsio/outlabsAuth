from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from fastapi import HTTPException, status

from ..models.role_model import RoleModel
from ..schemas.role_schema import RoleCreateSchema, RoleUpdateSchema
from .permission_service import permission_service

class RoleService:
    """
    Service class for role-related business logic.
    """

    async def create_role(self, db: AsyncIOMotorDatabase, role_data: RoleCreateSchema) -> RoleModel:
        """
        Creates a new role in the database.
        """
        # Validate that all permissions exist
        for permission_id in role_data.permissions:
            permission = await permission_service.get_permission_by_id(db, permission_id)
            if not permission:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Permission '{permission_id}' does not exist."
                )

        role = RoleModel(**role_data.model_dump(by_alias=True))
        await db.roles.insert_one(role.model_dump(by_alias=True))
        created_role = await self.get_role_by_id(db, role.id)
        return created_role

    async def get_role_by_id(self, db: AsyncIOMotorDatabase, role_id: str) -> Optional[RoleModel]:
        """
        Retrieves a single role by its ID.
        """
        role_data = await db.roles.find_one({"_id": role_id})
        if role_data:
            return RoleModel(**role_data)
        return None

    async def get_roles(self, db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100) -> List[RoleModel]:
        """
        Retrieves a list of roles with pagination.
        """
        roles_cursor = db.roles.find().skip(skip).limit(limit)
        roles = await roles_cursor.to_list(length=limit)
        return [RoleModel(**role) for role in roles]

    async def update_role(self, db: AsyncIOMotorDatabase, role_id: str, role_data: RoleUpdateSchema) -> Optional[RoleModel]:
        """
        Updates a role's information.
        """
        update_data = role_data.model_dump(exclude_unset=True)

        # Validate that all permissions exist if they are being updated
        if "permissions" in update_data:
            for permission_id in update_data["permissions"]:
                permission = await permission_service.get_permission_by_id(db, permission_id)
                if not permission:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Permission '{permission_id}' does not exist."
                    )
        
        if not update_data:
            return await self.get_role_by_id(db, role_id)
            
        await db.roles.update_one({"_id": role_id}, {"$set": update_data})
        
        updated_role = await self.get_role_by_id(db, role_id)
        return updated_role

    async def delete_role(self, db: AsyncIOMotorDatabase, role_id: str) -> int:
        """
        Deletes a role from the database.
        Returns the number of roles deleted.
        """
        # TODO: Add logic to check if role is assigned to any users before deletion
        result = await db.roles.delete_one({"_id": role_id})
        return result.deleted_count

role_service = RoleService() 