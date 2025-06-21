from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from beanie import PydanticObjectId

from ..dependencies import has_permission, valid_object_id, get_current_user_with_token
from ..schemas.group_schema import (
    GroupCreateSchema, GroupUpdateSchema, GroupResponseSchema,
    GroupMembershipSchema, GroupMembersResponseSchema, UserGroupsResponseSchema
)
from ..schemas.user_schema import UserResponseSchema
from ..services.group_service import group_service
from ..models.user_model import UserModel
from ..schemas.auth_schema import TokenDataSchema

router = APIRouter(
    prefix="/v1/groups",
    tags=["groups"],
    dependencies=[Depends(has_permission("group:read"))]
)

@router.post("/", response_model=GroupResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("group:create"))])
async def create_group(
    group_data: GroupCreateSchema,
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Create a new group.
    """
    current_user, _ = current_user_and_token
    
    # Ensure non-admin users can only create groups in their own client account
    if not current_user.is_main_client:
        if current_user.client_account and str(current_user.client_account.ref.id) != group_data.client_account_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create groups within your own client account"
            )
    
    try:
        new_group = await group_service.create_group(group_data)
        
        # Convert to response format
        response_data = new_group.model_dump()
        response_data["client_account_id"] = str(str(new_group.client_account.id).ref.id) if new_group.client_account else None
        
        return GroupResponseSchema(**response_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/", response_model=List[GroupResponseSchema])
async def list_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    client_account_id: Optional[str] = Query(None, description="Filter groups by client account ID"),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    List all groups with pagination and optional client account filtering.
    """
    current_user, _ = current_user_and_token
    
    # For non-admin users, automatically filter by their client account
    filter_client_id = None
    if client_account_id:
        filter_client_id = PydanticObjectId(client_account_id)
    elif current_user.client_account and not current_user.is_main_client:
        filter_client_id = current_user.client_account.id
    
    groups = await group_service.get_groups(skip=skip, limit=limit, client_account_id=filter_client_id)
    
    # Convert to response format
    response_groups = []
    for group in groups:
        response_data = group.model_dump()
        # Convert PydanticObjectId to string for API response
        response_data["id"] = str(group.id)
        response_data["client_account_id"] = str(str(group.client_account.id).ref.id) if group.client_account else None
        response_groups.append(GroupResponseSchema(**response_data))
    
    return response_groups

@router.get("/{group_id}", response_model=GroupResponseSchema)
async def get_group(
    group_id: PydanticObjectId = Depends(valid_object_id),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Get a single group by ID.
    """
    current_user, _ = current_user_and_token
    
    group = await group_service.get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    # Check if user has access to this group
    if current_user.client_account and not current_user.is_main_client:
        if group.client_account.id != current_user.client_account.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access groups within your own client account"
            )
    
    # Convert to response format
    response_data = group.model_dump()
    response_data["client_account_id"] = str(str(group.client_account.id).ref.id) if group.client_account else None
    
    return GroupResponseSchema(**response_data)

@router.put("/{group_id}", response_model=GroupResponseSchema, dependencies=[Depends(has_permission("group:update"))])
async def update_group(
    group_data: GroupUpdateSchema,
    group_id: PydanticObjectId = Depends(valid_object_id),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Update a group's information.
    """
    current_user, _ = current_user_and_token
    
    # Check if group exists and user has access
    existing_group = await group_service.get_group_by_id(group_id)
    if not existing_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    if current_user.client_account and not current_user.is_main_client:
        if existing_group.client_account.id != current_user.client_account.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update groups within your own client account"
            )
    
    try:
        updated_group = await group_service.update_group(group_id, group_data)
        if not updated_group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        
        # Convert to response format
        response_data = updated_group.model_dump()
        response_data["client_account_id"] = str(str(updated_group.client_account.id).ref.id) if updated_group.client_account else None
        
        return GroupResponseSchema(**response_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("group:delete"))])
async def delete_group(
    group_id: PydanticObjectId = Depends(valid_object_id),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Delete a group. This will remove all users from the group first.
    """
    current_user, _ = current_user_and_token
    
    # Check if group exists and user has access
    existing_group = await group_service.get_group_by_id(group_id)
    if not existing_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    if current_user.client_account and not current_user.is_main_client:
        if existing_group.client_account.id != current_user.client_account.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete groups within your own client account"
            )
    
    success = await group_service.delete_group(group_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

# Group membership management endpoints

@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("group:manage_members"))])
async def add_users_to_group(
    membership_data: GroupMembershipSchema,
    group_id: PydanticObjectId = Depends(valid_object_id),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Add users to a group.
    """
    current_user, _ = current_user_and_token
    
    # Check if group exists and user has access
    existing_group = await group_service.get_group_by_id(group_id)
    if not existing_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    if current_user.client_account and not current_user.is_main_client:
        if existing_group.client_account.id != current_user.client_account.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage members of groups within your own client account"
            )
    
    try:
        await group_service.add_users_to_group(group_id, membership_data.user_ids)
        return {"message": f"Successfully added {len(membership_data.user_ids)} users to group"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{group_id}/members", status_code=status.HTTP_200_OK, dependencies=[Depends(has_permission("group:manage_members"))])
async def remove_users_from_group(
    membership_data: GroupMembershipSchema,
    group_id: PydanticObjectId = Depends(valid_object_id),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Remove users from a group.
    """
    current_user, _ = current_user_and_token
    
    # Check if group exists and user has access
    existing_group = await group_service.get_group_by_id(group_id)
    if not existing_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    if current_user.client_account and not current_user.is_main_client:
        if existing_group.client_account.id != current_user.client_account.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage members of groups within your own client account"
            )
    
    try:
        await group_service.remove_users_from_group(group_id, membership_data.user_ids)
        return {"message": f"Successfully removed {len(membership_data.user_ids)} users from group"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{group_id}/members", response_model=GroupMembersResponseSchema)
async def get_group_members(
    group_id: PydanticObjectId = Depends(valid_object_id),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Get all members of a group.
    """
    current_user, _ = current_user_and_token
    
    # Check if group exists and user has access
    existing_group = await group_service.get_group_by_id(group_id)
    if not existing_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    if current_user.client_account and not current_user.is_main_client:
        if existing_group.client_account.id != current_user.client_account.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view members of groups within your own client account"
            )
    
    members = await group_service.get_group_members(group_id)
    
    # Convert users to basic response format
    member_data = []
    for member in members:
        member_dict = member.model_dump()
        member_dict["client_account_id"] = str(str(member.client_account.id).ref.id) if member.client_account else None
        member_data.append(member_dict)
    
    return GroupMembersResponseSchema(
        group_id=str(group_id),
        group_name=existing_group.name,
        members=member_data
    )

# User-centric group endpoints

@router.get("/users/{user_id}/groups", response_model=UserGroupsResponseSchema)
async def get_user_groups(
    user_id: PydanticObjectId = Depends(valid_object_id),
    current_user_and_token = Depends(get_current_user_with_token)
):
    """
    Get all groups that a user belongs to, along with their effective roles and permissions.
    """
    current_user, _ = current_user_and_token
    
    # Check if user exists and current user has access
    target_user = await UserModel.get(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Users can view their own groups, or admin users can view any user's groups
    if current_user.id != user_id and not current_user.is_main_client:
        if current_user.client_account != target_user.client_account:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view group memberships within your own client account"
            )
    
    # Get user's groups
    user_groups = await group_service.get_user_groups(user_id)
    
    # Get effective roles and permissions
    effective_roles = await group_service.get_user_effective_roles(user_id)
    effective_permissions = await group_service.get_user_effective_permissions(user_id)
    
    # Convert groups to response format
    groups_response = []
    for group in user_groups:
        response_data = group.model_dump()
        response_data["client_account_id"] = str(str(group.client_account.id).ref.id) if group.client_account else None
        groups_response.append(GroupResponseSchema(**response_data))
    
    return UserGroupsResponseSchema(
        user_id=str(user_id),
        groups=groups_response,
        effective_roles=list(effective_roles),
        effective_permissions=list(effective_permissions)
    ) 