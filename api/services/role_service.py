from typing import List, Optional
from fastapi import HTTPException, status

from ..models.role_model import RoleModel
from ..schemas.role_schema import RoleCreateSchema, RoleUpdateSchema
from .permission_service import permission_service

class RoleService:
    """
    Service class for role-related business logic using Beanie ODM.
    """

    async def create_role(self, role_data: RoleCreateSchema) -> RoleModel:
        """
        Creates a new role in the database using Beanie ODM.
        """
        # Validate that all permissions exist
        for permission_id in role_data.permissions:
            permission = await permission_service.get_permission_by_id(permission_id)
            if not permission:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Permission '{permission_id}' does not exist."
                )

        role = RoleModel(**role_data.model_dump())
        await role.insert()
        return role

    async def get_role_by_id(self, role_id: str) -> Optional[RoleModel]:
        """
        Retrieves a single role by its ID using Beanie ODM.
        """
        return await RoleModel.get(role_id)

    async def get_roles(self, skip: int = 0, limit: int = 100) -> List[RoleModel]:
        """
        Retrieves a list of roles with pagination using Beanie ODM.
        """
        return await RoleModel.find().skip(skip).limit(limit).to_list()

    async def update_role(self, role_id: str, role_data: RoleUpdateSchema) -> Optional[RoleModel]:
        """
        Updates a role's information using Beanie ODM.
        """
        role = await self.get_role_by_id(role_id)
        if not role:
            return None
            
        update_data = role_data.model_dump(exclude_unset=True)

        # Validate that all permissions exist if they are being updated
        if "permissions" in update_data:
            for permission_id in update_data["permissions"]:
                permission = await permission_service.get_permission_by_id(permission_id)
                if not permission:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Permission '{permission_id}' does not exist."
                    )
        
        if not update_data:
            return role
            
        # Update role fields
        for field, value in update_data.items():
            setattr(role, field, value)
            
        await role.save()
        return role

    async def delete_role(self, role_id: str) -> bool:
        """
        Deletes a role from the database using Beanie ODM.
        Returns True if deleted, False if role not found.
        """
        # TODO: Add logic to check if role is assigned to any users before deletion
        role = await self.get_role_by_id(role_id)
        if role:
            await role.delete()
            return True
        return False

role_service = RoleService() 