from typing import List, Optional

from ..models.permission_model import PermissionModel
from ..schemas.permission_schema import PermissionCreateSchema

class PermissionService:
    """
    Service class for permission-related business logic using Beanie ODM.
    """

    async def create_permission(self, permission_data: PermissionCreateSchema) -> PermissionModel:
        """
        Creates a new permission in the database using Beanie ODM.
        """
        permission = PermissionModel(**permission_data.model_dump())
        await permission.insert()
        return permission

    async def get_permission_by_id(self, permission_id: str) -> Optional[PermissionModel]:
        """
        Retrieves a single permission by its ID using Beanie ODM.
        """
        return await PermissionModel.get(permission_id)

    async def get_permissions(self, skip: int = 0, limit: int = 100) -> List[PermissionModel]:
        """
        Retrieves a list of permissions with pagination using Beanie ODM.
        """
        return await PermissionModel.find().skip(skip).limit(limit).to_list()

permission_service = PermissionService() 