from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from beanie import PydanticObjectId

from ..dependencies import has_permission, get_current_user
from ..schemas.group_schema import (
    GroupCreateSchema, GroupUpdateSchema, GroupResponseSchema,
    AvailableGroupsResponseSchema, GroupMembershipSchema, 
    GroupMembersResponseSchema, UserGroupsResponseSchema
)
from ..schemas.user_schema import UserResponseSchema
from ..services.group_service import group_service
from ..models.user_model import UserModel
from ..models.scopes import GroupScope

router = APIRouter(
    prefix="/v1/groups",
    tags=["Group Management"],
    dependencies=[Depends(has_permission("group:read"))]
)

@router.post("/", response_model=GroupResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreateSchema,
    current_user: UserModel = Depends(get_current_user),
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
    return GroupResponseSchema.model_validate(new_group)

@router.get("/", response_model=List[GroupResponseSchema])
async def get_groups(
    skip: int = Query(0, ge=0, description="Number of groups to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of groups to return"),
    scope: Optional[GroupScope] = Query(None, description="Filter by group scope"),
    scope_id: Optional[str] = Query(None, description="Filter by specific scope ID"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Retrieve groups with optional filtering by scope.
    """
    groups = await group_service.get_groups(
        skip=skip, 
        limit=limit,
        scope=scope,
        scope_id=scope_id
    )
    return [GroupResponseSchema.model_validate(group) for group in groups]

@router.get("/available", response_model=AvailableGroupsResponseSchema)
async def get_available_groups(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get groups that the current user can assign to others, grouped by scope.
    """
    current_client_id = str(current_user.client_account.id) if current_user.client_account else None
    current_platform_id = current_user.platform_scope  # From user model
    
    # Determine user permissions (simplified - in real implementation, check roles)
    is_super_admin = "super_admin" in [role for role in current_user.roles]
    is_platform_admin = current_user.is_platform_staff
    
    return await group_service.get_available_groups_for_user(
        current_user_client_id=current_client_id,
        current_user_platform_id=current_platform_id,
        is_super_admin=is_super_admin,
        is_platform_admin=is_platform_admin
    )

@router.get("/{group_id}", response_model=GroupResponseSchema)
async def get_group_by_id(
    group_id: str,
    current_user: UserModel = Depends(get_current_user)
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
    
    return GroupResponseSchema.model_validate(group)

@router.put("/{group_id}", response_model=GroupResponseSchema)
async def update_group(
    group_id: str,
    group_data: GroupUpdateSchema,
    current_user: UserModel = Depends(get_current_user)
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
    
    return GroupResponseSchema.model_validate(updated_group)

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    current_user: UserModel = Depends(get_current_user)
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
    current_user: UserModel = Depends(get_current_user)
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
    current_user: UserModel = Depends(get_current_user)
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
    current_user: UserModel = Depends(get_current_user)
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
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get all groups that a user belongs to, along with their effective permissions.
    """
    try:
        user_groups = await group_service.get_user_groups(PydanticObjectId(user_id))
        effective_permissions = await group_service.get_user_effective_permissions(PydanticObjectId(user_id))
        
        groups_response = [GroupResponseSchema.model_validate(group) for group in user_groups]
        
        return UserGroupsResponseSchema(
            user_id=user_id,
            groups=groups_response,
            effective_permissions=list(effective_permissions)
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format") 