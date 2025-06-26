from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from beanie import PydanticObjectId

from ..dependencies import get_current_user, has_permission
from ..models.user_model import UserModel
from ..models.scopes import GroupScope
from ..schemas.group_schema import (
    GroupCreateSchema, GroupUpdateSchema, GroupResponseSchema,
    AvailableGroupsResponseSchema, GroupMembershipSchema, 
    GroupMembersResponseSchema, UserGroupsResponseSchema
)
from ..services.group_service import group_service
from ..dependencies import (
    user_has_role, require_super_admin, require_admin,
    require_group_manage_access, require_group_read_access
)

router = APIRouter(
    prefix="/v1/groups",
    tags=["Group Management"]
)

@router.post("/", response_model=GroupResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreateSchema,
    current_user: UserModel = Depends(require_group_manage_access),
    scope_id: Optional[str] = Query(None, description="Platform ID or Client ID for scoped groups")
):
    """
    Create a new scoped group with direct permissions.
    
    Scope ID requirements:
    - System groups: scope_id not needed (ignored)
    - Platform groups: scope_id must be platform_id
    - Client groups: scope_id must be client_account_id (or auto-determined from user)
    
    Examples:
    - System: {"name": "customer_support", "scope": "system", "permissions": ["platform:support:all_clients"]}
    - Platform: {"name": "marketing_team", "scope": "platform", "permissions": ["platform:marketing:manage"]} + scope_id=platform_id
    - Client: {"name": "sales_team", "scope": "client", "permissions": ["client:listing:create"]} + scope_id=client_id
    """
    current_client_id = str(current_user.client_account.id) if current_user.client_account else None
    
    new_group = await group_service.create_group(
        group_data=group_data,
        current_user_id=str(current_user.id),
        current_client_id=current_client_id,
        scope_id=scope_id
    )
    return await group_service.group_to_response_schema(new_group)

@router.get("/", response_model=List[GroupResponseSchema])
async def get_groups(
    skip: int = Query(0, ge=0, description="Number of groups to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of groups to return"),
    scope: Optional[GroupScope] = Query(None, description="Filter by group scope"),
    scope_id: Optional[str] = Query(None, description="Filter by specific scope ID"),
    current_user: UserModel = Depends(require_group_read_access)  # Access control only
):
    """
    Retrieve groups with optional filtering by scope.
    """
    # Apply client account scoping for non-super admins and non-platform admins
    is_super_admin = user_has_role(current_user, "super_admin")
    is_platform_admin = any(role.scope.value == "platform" for role in current_user.roles if hasattr(role, 'scope'))
    
    if not is_super_admin and not is_platform_admin and current_user.client_account and not scope_id:
        # For client admins (not platform admins), filter to their client account if no specific scope_id is provided
        scope = GroupScope.CLIENT
        scope_id = str(current_user.client_account.id)
    
    groups = await group_service.get_groups(
        skip=skip, 
        limit=limit,
        scope=scope,
        scope_id=scope_id
    )
    
    # Apply additional client account filtering on the results for non-super admins and non-platform admins
    if not is_super_admin and not is_platform_admin and current_user.client_account:
        filtered_groups = []
        user_client_id = str(current_user.client_account.id)
        for group in groups:
            # Allow system/platform groups + client groups from their account
            if (group.scope.value != "client" or 
                not group.scope_id or 
                group.scope_id == user_client_id):
                filtered_groups.append(group)
        groups = filtered_groups
    
    # Convert groups to response format with resolved permission details
    group_responses = []
    for group in groups:
        group_response = await group_service.group_to_response_schema(group)
        group_responses.append(group_response)
    return group_responses

@router.get("/available", response_model=AvailableGroupsResponseSchema)
async def get_available_groups(
    current_user: UserModel = Depends(require_admin)
):
    """
    Get groups that the current user can assign to others, grouped by scope.
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
    
    return await group_service.get_available_groups_for_user(
        current_user_client_id=current_client_id,
        current_user_platform_id=current_user_platform_id,
        is_super_admin=is_super_admin,
        is_platform_admin=is_platform_admin
    )

@router.get("/{group_id}", response_model=GroupResponseSchema)
async def get_group_by_id(
    group_id: str,
    current_user: UserModel = Depends(require_group_read_access)  # Access control only
):
    """
    Get a single group by ID.
    """
    try:
        group = await group_service.get_group_by_id(PydanticObjectId(group_id))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group ID format")
    
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    # Apply client account scoping - client admins can only access groups in their client account
    is_super_admin = user_has_role(current_user, "super_admin")
    if not is_super_admin and current_user.client_account:
        # Client admin should only access client-scoped groups from their client account
        # System and platform groups are accessible to all client admins
        if (group.scope.value == "client" and 
            group.scope_id and 
            group.scope_id != str(current_user.client_account.id)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    return await group_service.group_to_response_schema(group)

@router.put("/{group_id}", response_model=GroupResponseSchema)
async def update_group(
    group_id: str,
    group_data: GroupUpdateSchema,
    _: UserModel = Depends(require_group_manage_access)  # Access control only
):
    """
    Update a group's information.
    """
    try:
        updated_group = await group_service.update_group(PydanticObjectId(group_id), group_data)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group ID format")
    
    if not updated_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    return await group_service.group_to_response_schema(updated_group)

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    _: UserModel = Depends(require_group_manage_access)  # Access control only
):
    """
    Delete a group. This will remove all users from the group first.
    """
    try:
        success = await group_service.delete_group(PydanticObjectId(group_id))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group ID format")
    
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

# Group membership management endpoints

@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_users_to_group(
    group_id: str,
    membership_data: GroupMembershipSchema,
    _: UserModel = Depends(require_group_manage_access)  # Access control only
):
    """
    Add users to a group.
    """
    try:
        success = await group_service.add_users_to_group(PydanticObjectId(group_id), membership_data.user_ids)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        return {"message": f"Successfully added {len(membership_data.user_ids)} users to group"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group ID format")

@router.delete("/{group_id}/members", status_code=status.HTTP_200_OK)
async def remove_users_from_group(
    group_id: str,
    membership_data: GroupMembershipSchema,
    _: UserModel = Depends(require_group_manage_access)  # Access control only
):
    """
    Remove users from a group.
    """
    try:
        success = await group_service.remove_users_from_group(PydanticObjectId(group_id), membership_data.user_ids)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        return {"message": f"Successfully removed {len(membership_data.user_ids)} users from group"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group ID format")

@router.get("/{group_id}/members", response_model=GroupMembersResponseSchema)
async def get_group_members(
    group_id: str,
    _: UserModel = Depends(require_group_read_access)  # Access control only
):
    """
    Get all members of a group.
    """
    try:
        group = await group_service.get_group_by_id(PydanticObjectId(group_id))
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        
        members = await group_service.get_group_members(PydanticObjectId(group_id))
        
        # Convert members to dict format
        member_dicts = []
        for member in members:
            member_dict = {
                "id": str(member.id),
                "email": member.email,
                "first_name": member.first_name,
                "last_name": member.last_name,
                "status": member.status
            }
            member_dicts.append(member_dict)
        
        return GroupMembersResponseSchema(
            group_id=group_id,
            group_name=group.name,
            group_scope=group.scope,
            members=member_dicts
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group ID format")

@router.get("/users/{user_id}/groups", response_model=UserGroupsResponseSchema)
async def get_user_groups(
    user_id: str,
    _: UserModel = Depends(require_group_read_access)  # Access control only
):
    """
    Get all groups that a user belongs to, along with their effective permissions.
    """
    try:
        from ..services.user_service import user_service
        
        user_groups = await group_service.get_user_groups(PydanticObjectId(user_id))
        effective_permission_details = await user_service.get_user_effective_permission_details(PydanticObjectId(user_id))
        
        # Convert groups to response schema with permission details
        groups_response = []
        for group in user_groups:
            group_response = await group_service.group_to_response_schema(group)
            groups_response.append(group_response)
        
        return UserGroupsResponseSchema(
            user_id=user_id,
            groups=groups_response,
            effective_permissions=effective_permission_details
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format") 