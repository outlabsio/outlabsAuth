from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from beanie import PydanticObjectId

from ..models.user_model import UserModel
from ..models.role_model import RoleScope
from ..schemas.role_schema import (
    RoleCreateSchema, 
    RoleUpdateSchema, 
    RoleResponseSchema,
    AvailableRolesResponseSchema
)
from ..services.role_service import role_service
from ..dependencies import (
    user_has_role, require_admin,
    can_read_roles, can_manage_roles
)


router = APIRouter(prefix="/v1/roles", tags=["roles"])

@router.post("/", response_model=RoleResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreateSchema,
    current_user: UserModel = Depends(can_manage_roles)
):
    """
    Create a new role in the specified scope.
    
    - **Client admins** create client-scoped roles within their organization
    - **Platform admins** create platform-scoped roles within their platform
    - **Super admins** can create roles in any scope
    """
    # Validate user can create roles in requested scope
    scope_id = None
    
    # User roles are now Beanie Links, so we can access them directly
    user_roles = current_user.roles if current_user.roles else []

    is_super_admin = any(role.name == "super_admin" and role.scope == RoleScope.SYSTEM for role in user_roles)

    if role_data.scope == RoleScope.SYSTEM:
        if not is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can create system roles"
            )
    elif role_data.scope == RoleScope.PLATFORM:
        # Check if user is platform admin and extract platform ID
        platform_admin_roles = [
            role for role in user_roles 
            if (role.name == "admin" and role.scope == RoleScope.PLATFORM)
        ]
        if not platform_admin_roles and not is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform admins can create platform roles"
            )
        if platform_admin_roles:
            scope_id = platform_admin_roles[0].scope_id
    elif role_data.scope == RoleScope.CLIENT:
        if not current_user.client_account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client account ID required for client roles"
            )
        scope_id = str(current_user.client_account.id)
        
        # Check if user is client admin
        client_admin_roles = [
            role for role in user_roles 
            if (role.name == "admin" and 
                role.scope == RoleScope.CLIENT and 
                role.scope_id == str(current_user.client_account.id))
        ]
        if not client_admin_roles and not is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only client admins can create client roles"
            )

    # Create the role
    role = await role_service.create_role(
        role_data=role_data,
        current_user_id=str(current_user.id),
        current_client_id=str(current_user.client_account.id) if current_user.client_account else None,
        scope_id=scope_id
    )
    
    return await role_service.role_to_response_schema(role)

@router.get("/", response_model=List[RoleResponseSchema])
async def get_roles(
    scope: Optional[RoleScope] = Query(None, description="Filter by scope"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserModel = Depends(can_read_roles)
):
    """
    Get roles visible to the current user.
    
    - **Super admins** see all roles
    - **Platform admins** see system + their platform roles
    - **Client admins** see system + their client roles
    """
    # User roles are now Beanie Links, so we can access them directly
    user_roles = current_user.roles if current_user.roles else []

    is_super_admin = any(role.name == "super_admin" and role.scope == RoleScope.SYSTEM for role in user_roles)
    
    roles = []
    
    if scope:
        # Filter by specific scope
        if scope == RoleScope.SYSTEM:
            roles = await role_service.get_roles_by_scope(scope, skip=skip, limit=limit)
        elif scope == RoleScope.PLATFORM:
            # Get platform ID from user's roles
            platform_admin_roles = [
                role for role in user_roles 
                if (role.name == "admin" and role.scope == RoleScope.PLATFORM)
            ]
            if platform_admin_roles or is_super_admin:
                platform_id = platform_admin_roles[0].scope_id if platform_admin_roles else None
                roles = await role_service.get_roles_by_scope(scope, platform_id, skip, limit)
        elif scope == RoleScope.CLIENT:
            if current_user.client_account:
                roles = await role_service.get_roles_by_scope(scope, str(current_user.client_account.id), skip, limit)
    else:
        # Get all visible roles
        if is_super_admin:
            # Super admin sees everything - get from all scopes
            system_roles = await role_service.get_roles_by_scope(RoleScope.SYSTEM, skip=skip, limit=limit//3)
            platform_roles = await role_service.get_roles_by_scope(RoleScope.PLATFORM, skip=skip, limit=limit//3) 
            client_roles = await role_service.get_roles_by_scope(RoleScope.CLIENT, skip=skip, limit=limit//3)
            roles = system_roles + platform_roles + client_roles
        else:
            # Regular users see system + their scope
            system_roles = await role_service.get_roles_by_scope(RoleScope.SYSTEM, skip=skip, limit=limit//3)
            roles.extend(system_roles)
            
            # Add platform roles if user is platform admin
            platform_admin_roles = [
                role for role in user_roles 
                if (role.name == "admin" and role.scope == RoleScope.PLATFORM)
            ]
            if platform_admin_roles:
                platform_id = platform_admin_roles[0].scope_id
                platform_roles = await role_service.get_roles_by_scope(RoleScope.PLATFORM, platform_id, skip=skip, limit=limit//3)
                roles.extend(platform_roles)
            
            # Add client roles if user has client account
            if current_user.client_account:
                client_roles = await role_service.get_roles_by_scope(RoleScope.CLIENT, str(current_user.client_account.id), skip=skip, limit=limit//3)
                roles.extend(client_roles)

    # Filter roles user can actually view
    visible_roles = []
    for role in roles:
        client_account_id = str(current_user.client_account.id) if current_user.client_account else None
        if await role_service.user_can_view_role(user_roles, client_account_id, role):
            visible_roles.append(role)

    # Convert roles to response schema with permission details
    response_roles = []
    for role in visible_roles:
        response_role = await role_service.role_to_response_schema(role)
        response_roles.append(response_role)
    
    return response_roles

@router.get("/available", response_model=AvailableRolesResponseSchema)
async def get_available_roles(
    current_user: UserModel = Depends(require_admin)
):
    """
    Get roles that the current user can assign to others, grouped by scope.
    Only admins can assign roles to users.
    """
    # User roles are now Beanie Links, so we can access them directly
    user_roles = current_user.roles if current_user.roles else []

    # Determine user permissions
    is_super_admin = any(role.name == "super_admin" and role.scope == RoleScope.SYSTEM for role in user_roles)
    platform_admin_roles = [
        role for role in user_roles 
        if (role.name == "admin" and role.scope == RoleScope.PLATFORM)
    ]
    is_platform_admin = len(platform_admin_roles) > 0
    
    # Extract platform ID if platform admin
    current_user_platform_id = None
    if is_platform_admin:
        current_user_platform_id = platform_admin_roles[0].scope_id
    
    return await role_service.get_available_roles_for_user(
        current_user_client_id=str(current_user.client_account.id) if current_user.client_account else None,
        current_user_platform_id=current_user_platform_id,
        is_super_admin=is_super_admin,
        is_platform_admin=is_platform_admin
    )

@router.get("/{role_id}", response_model=RoleResponseSchema)
async def get_role(
    role_id: PydanticObjectId,
    current_user: UserModel = Depends(can_read_roles)
):
    """Get a specific role by ID."""
    role = await role_service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Check if user can view this role
    user_roles = current_user.roles if current_user.roles else []
    client_account_id = str(current_user.client_account.id) if current_user.client_account else None
    if not await role_service.user_can_view_role(user_roles, client_account_id, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this role"
        )
    
    return await role_service.role_to_response_schema(role)

@router.put("/{role_id}", response_model=RoleResponseSchema)
async def update_role(
    role_id: PydanticObjectId,
    role_data: RoleUpdateSchema,
    current_user: UserModel = Depends(can_manage_roles)
):
    """Update a role."""
    # Check if role exists
    existing_role = await role_service.get_role_by_id(role_id)
    if not existing_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Check permissions
    user_roles = current_user.roles if current_user.roles else []
    client_account_id = str(current_user.client_account.id) if current_user.client_account else None
    can_manage = await role_service.user_can_manage_role(
        user_roles=user_roles,
        user_client_id=client_account_id,
        target_role=existing_role
    )
    
    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this role"
        )
    
    updated_role = await role_service.update_role(role_id, role_data)
    return await role_service.role_to_response_schema(updated_role)

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: PydanticObjectId,
    current_user: UserModel = Depends(can_manage_roles)
):
    """Delete a role."""
    # Check if role exists
    existing_role = await role_service.get_role_by_id(role_id)
    if not existing_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Check permissions
    user_roles = current_user.roles if current_user.roles else []
    client_account_id = str(current_user.client_account.id) if current_user.client_account else None
    can_manage = await role_service.user_can_manage_role(
        user_roles=user_roles,
        user_client_id=client_account_id,
        target_role=existing_role
    )
    
    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this role"
        )
    
    deleted = await role_service.delete_role(role_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        ) 