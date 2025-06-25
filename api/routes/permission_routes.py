from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from ..services.permission_service import permission_service
from ..schemas.permission_schema import (
    PermissionCreateSchema, 
    PermissionUpdateSchema,
    PermissionResponseSchema,
    AvailablePermissionsResponseSchema
)
from ..models.scopes import PermissionScope
from ..dependencies import has_permission, get_current_user
from ..models.user_model import UserModel
from ..dependencies import (
    user_has_role, require_super_admin, require_admin,
    require_permission_manage_access, require_user_read_access
)


router = APIRouter(
    prefix="/v1/permissions",
    tags=["Permission Management"]
)

@router.post("/", response_model=PermissionResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_permission(
    permission_data: PermissionCreateSchema,
    current_user: UserModel = Depends(require_permission_manage_access),
    scope_id: Optional[str] = Query(None, description="Platform ID or Client ID for scoped permissions")
):
    """
    Create a new scoped permission.
    
    Scope ID requirements:
    - System permissions: scope_id not needed (ignored)
    - Platform permissions: scope_id must be platform_id
    - Client permissions: scope_id must be client_account_id (or auto-determined from user)
    
    Examples:
    - System: {"name": "user:create", "scope": "system"}
    - Platform: {"name": "analytics:view", "scope": "platform"} + scope_id=platform_id
    - Client: {"name": "listing:create", "scope": "client"} + scope_id=client_id
    """
    current_client_id = str(current_user.client_account.id) if current_user.client_account else None
    
    new_permission = await permission_service.create_permission(
        permission_data=permission_data,
        current_user_id=str(current_user.id),
        current_client_id=current_client_id,
        scope_id=scope_id
    )
    return PermissionResponseSchema.model_validate(new_permission)

@router.get("/", response_model=List[PermissionResponseSchema])
async def get_permissions(
    skip: int = Query(0, ge=0, description="Number of permissions to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of permissions to return"),
    scope: Optional[PermissionScope] = Query(None, description="Filter by permission scope"),
    scope_id: Optional[str] = Query(None, description="Filter by specific scope ID"),
    current_user: UserModel = Depends(require_user_read_access)
):
    """
    Retrieve permissions with optional filtering by scope.
    """
    permissions = await permission_service.get_permissions(
        skip=skip, 
        limit=limit,
        scope=scope,
        scope_id=scope_id
    )
    return [PermissionResponseSchema.model_validate(perm) for perm in permissions]

@router.get("/available", response_model=AvailablePermissionsResponseSchema)
async def get_available_permissions(
    current_user: UserModel = Depends(require_admin)
):
    """
    Get permissions that the current user can assign to others, grouped by scope.
    """
    current_client_id = str(current_user.client_account.id) if current_user.client_account else None
    
    # Determine user permissions and platform ID from roles
    is_super_admin = user_has_role(current_user, "super_admin")
    
    # Extract platform ID from platform admin roles
    current_user_platform_id = None
    is_platform_admin = False
    
    if current_user.roles:
        for role in current_user.roles:
            if (role.name == "admin" and 
                hasattr(role, 'scope') and 
                role.scope.value == "platform"):  # Check if it's a platform-scoped admin role
                is_platform_admin = True
                current_user_platform_id = role.scope_id
                break
    
    return await permission_service.get_available_permissions_for_user(
        current_user_client_id=current_client_id,
        current_user_platform_id=current_user_platform_id,
        is_super_admin=is_super_admin,
        is_platform_admin=is_platform_admin
    )

@router.get("/{permission_id}", response_model=PermissionResponseSchema)
async def get_permission_by_id(
    permission_id: str,
    current_user: UserModel = Depends(require_user_read_access)
):
    """
    Retrieve a single permission by its ID.
    """
    permission = await permission_service.get_permission_by_id(permission_id)
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found."
        )
    return PermissionResponseSchema.model_validate(permission)

@router.put("/{permission_id}", response_model=PermissionResponseSchema)
async def update_permission(
    permission_id: str,
    permission_data: PermissionUpdateSchema,
    current_user: UserModel = Depends(require_permission_manage_access)
):
    """
    Update a permission by ID.
    """
    updated_permission = await permission_service.update_permission(
        permission_id=permission_id,
        permission_data=permission_data
    )
    if updated_permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found."
        )
    return PermissionResponseSchema.model_validate(updated_permission)

@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: str,
    current_user: UserModel = Depends(require_permission_manage_access)
):
    """
    Delete a permission by ID.
    """
    deleted = await permission_service.delete_permission(permission_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found."
        ) 