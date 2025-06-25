from typing import List, Optional
from fastapi import HTTPException, status

from ..models.permission_model import PermissionModel
from ..models.scopes import PermissionScope
from ..schemas.permission_schema import (
    PermissionCreateSchema,
    PermissionUpdateSchema,
    PermissionResponseSchema,
    AvailablePermissionsResponseSchema,
    PermissionDetailSchema
)

class PermissionService:
    """
    Service class for permission-related business logic with scoped permissions.
    """

    async def create_permission(
        self, 
        permission_data: PermissionCreateSchema,
        current_user_id: str,
        current_client_id: Optional[str] = None,
        scope_id: Optional[str] = None
    ) -> PermissionModel:
        """
        Create a new scoped permission.
        
        Args:
            permission_data: Permission creation data
            current_user_id: ID of user creating the permission
            current_client_id: Client ID of current user
            scope_id: Explicit scope ID (platform_id or client_account_id)
        """
        # Determine scope_id based on permission scope
        if permission_data.scope == PermissionScope.SYSTEM:
            final_scope_id = None
        elif permission_data.scope == PermissionScope.CLIENT:
            final_scope_id = scope_id or current_client_id
            if not final_scope_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client ID required for client-scoped permissions"
                )
        elif permission_data.scope == PermissionScope.PLATFORM:
            if not scope_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Platform ID required for platform-scoped permissions"
                )
            final_scope_id = scope_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scope: {permission_data.scope}"
            )

        # Check if permission name already exists in this scope
        existing_permission = await PermissionModel.find_one(
            PermissionModel.name == permission_data.name,
            PermissionModel.scope == permission_data.scope,
            PermissionModel.scope_id == final_scope_id
        )
        
        if existing_permission:
            scope_desc = f"{permission_data.scope} scope"
            if final_scope_id:
                scope_desc += f" ({final_scope_id})"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Permission '{permission_data.name}' already exists in {scope_desc}"
            )

        # Create permission (let MongoDB generate ObjectId, no custom ID)
        permission = PermissionModel(
            name=permission_data.name,
            display_name=permission_data.display_name,
            description=permission_data.description,
            scope=permission_data.scope,
            scope_id=final_scope_id,
            created_by_user_id=current_user_id,
            created_by_client_id=current_client_id
        )
        
        await permission.insert()
        return permission

    async def get_permission_by_id(self, permission_id: str) -> Optional[PermissionModel]:
        """Get a permission by its ObjectId."""
        from beanie import PydanticObjectId
        try:
            return await PermissionModel.get(PydanticObjectId(permission_id))
        except Exception:
            return None

    async def get_permission_by_name(self, permission_name: str, scope: Optional[PermissionScope] = None, scope_id: Optional[str] = None) -> Optional[PermissionModel]:
        """Get a permission by its name, optionally filtered by scope."""
        query = {"name": permission_name}
        if scope:
            query["scope"] = scope
            if scope_id is not None:
                query["scope_id"] = scope_id
        
        return await PermissionModel.find_one(query)

    async def convert_permission_names_to_links(self, permission_names: List[str]) -> List[PermissionModel]:
        """
        Convert permission names to PermissionModel Link objects for Beanie relationships.
        
        Args:
            permission_names: List of permission names (e.g., ['user:create', 'listings:manage'])
            
        Returns:
            List of PermissionModel objects (for Beanie Links)
            
        Raises:
            HTTPException: If any permission name is not found
        """
        permission_links = []
        
        for permission_name in permission_names:
            # Check if it's already an ObjectId (for backward compatibility)
            try:
                from beanie import PydanticObjectId
                permission_id = PydanticObjectId(permission_name)
                permission = await self.get_permission_by_id(str(permission_id))
                if not permission:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Permission with ID '{permission_name}' not found"
                    )
                permission_links.append(permission)
            except Exception:
                # It's a permission name, find the permission object
                permission = await self.get_permission_by_name(permission_name)
                if not permission:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Permission '{permission_name}' not found"
                    )
                permission_links.append(permission)
        
        return permission_links

    async def convert_permission_names_to_ids(self, permission_names: List[str]) -> List[str]:
        """
        Convert permission names to ObjectIds for database storage.
        
        Args:
            permission_names: List of permission names (e.g., ['user:create', 'listings:manage'])
            
        Returns:
            List of ObjectId strings
            
        Raises:
            HTTPException: If any permission name is not found
        """
        permission_ids = []
        
        for permission_name in permission_names:
            # Check if it's already an ObjectId (for backward compatibility)
            try:
                from beanie import PydanticObjectId
                permission_id = PydanticObjectId(permission_name)
                permission = await self.get_permission_by_id(str(permission_id))
                if not permission:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Permission with ID '{permission_name}' not found"
                    )
                permission_ids.append(str(permission_id))
            except Exception:
                # It's a permission name, find the ObjectId
                permission = await self.get_permission_by_name(permission_name)
                if not permission:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Permission '{permission_name}' not found"
                    )
                permission_ids.append(str(permission.id))
        
        return permission_ids

    async def resolve_permissions_to_details(self, permission_ids: List[str]) -> List[PermissionDetailSchema]:
        """
        Convert ObjectIds to full permission details for API responses.
        
        Args:
            permission_ids: List of ObjectId strings
            
        Returns:
            List of PermissionDetailSchema objects with id, name, scope, etc.
        """
        permission_details = []
        
        for permission_id in permission_ids:
            permission = await self.get_permission_by_id(permission_id)
            if permission:
                detail = PermissionDetailSchema(
                    id=str(permission.id),
                    name=permission.name,
                    scope=permission.scope,
                    display_name=permission.display_name,
                    description=permission.description
                )
                permission_details.append(detail)
        
        return permission_details

    async def get_permissions_by_scope(
        self, 
        scope: PermissionScope, 
        scope_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PermissionModel]:
        """Get all permissions for a specific scope."""
        if scope == PermissionScope.SYSTEM:
            # For system permissions, just query by scope since scope_id should be None
            permissions = await PermissionModel.find(
                PermissionModel.scope == scope
            ).skip(skip).limit(limit).to_list()
        else:
            # For platform/client permissions, filter by scope_id if provided
            if scope_id is not None:
                permissions = await PermissionModel.find(
                    PermissionModel.scope == scope,
                    PermissionModel.scope_id == scope_id
                ).skip(skip).limit(limit).to_list()
            else:
                permissions = await PermissionModel.find(
                    PermissionModel.scope == scope
                ).skip(skip).limit(limit).to_list()
            
        return permissions

    async def get_available_permissions_for_user(
        self,
        current_user_client_id: Optional[str] = None,
        current_user_platform_id: Optional[str] = None,
        is_super_admin: bool = False,
        is_platform_admin: bool = False
    ) -> AvailablePermissionsResponseSchema:
        """
        Get permissions that a user can assign, grouped by scope.
        """
        available_permissions = AvailablePermissionsResponseSchema()

        # System permissions (only super admins can assign these)
        if is_super_admin:
            system_permissions = await self.get_permissions_by_scope(PermissionScope.SYSTEM)
            available_permissions.system_permissions = [
                PermissionResponseSchema.model_validate(perm) for perm in system_permissions
            ]

        # Platform permissions (platform admins can assign within their platform)
        if is_super_admin or (is_platform_admin and current_user_platform_id):
            platform_permissions = await self.get_permissions_by_scope(
                PermissionScope.PLATFORM, 
                current_user_platform_id
            )
            available_permissions.platform_permissions = [
                PermissionResponseSchema.model_validate(perm) for perm in platform_permissions
            ]

        # Client permissions (client admins can assign within their client)
        if current_user_client_id:
            client_permissions = await self.get_permissions_by_scope(
                PermissionScope.CLIENT,
                current_user_client_id
            )
            available_permissions.client_permissions = [
                PermissionResponseSchema.model_validate(perm) for perm in client_permissions
            ]

        return available_permissions

    async def update_permission(
        self, 
        permission_id: str, 
        permission_data: PermissionUpdateSchema
    ) -> Optional[PermissionModel]:
        """Update a permission by ID."""
        permission = await self.get_permission_by_id(permission_id)
        if not permission:
            return None

        update_data = permission_data.model_dump(exclude_unset=True)
        
        if update_data:
            for field, value in update_data.items():
                setattr(permission, field, value)
            await permission.save()
            
        return permission

    async def delete_permission(self, permission_id: str) -> bool:
        """Delete a permission by ObjectId."""
        permission = await self.get_permission_by_id(permission_id)
        if not permission:
            return False

        await permission.delete()
        return True

    async def get_permissions(
        self, 
        skip: int = 0, 
        limit: int = 100,
        scope: Optional[PermissionScope] = None,
        scope_id: Optional[str] = None
    ) -> List[PermissionModel]:
        """
        Get permissions with optional filtering by scope.
        """
        if scope:
            return await self.get_permissions_by_scope(scope, scope_id, skip, limit)
        else:
            return await PermissionModel.find().skip(skip).limit(limit).to_list()

permission_service = PermissionService() 