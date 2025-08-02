"""
User routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.models import UserModel
from api.models.user_model import UserStatus
from api.schemas.user_schema import (
    UserProfileUpdate,
    UserResponse,
    UserListResponse,
    UserSearchParams,
    UserStatusUpdate,
    UserInviteRequest,
    UserInviteResponse,
    UserPasswordResetRequest,
    UserPasswordResetResponse,
    UserMembershipListResponse,
    UserStatsResponse,
    UserBulkActionRequest,
    UserBulkActionResponse,
    UserCreateRequest,
    UserUpdateRequest,
    UserEntityAssignment
)
from api.services.user_service import UserService
from api.dependencies import (
    require_user_read,
    require_permission,
    require_self_or_permission,
    get_current_user
)

router = APIRouter()


async def _user_to_response(user: UserModel) -> UserResponse:
    """Convert user model to response with entities"""
    user_data = await UserService.enrich_user_with_entities(user)
    return UserResponse(**user_data)


@router.get("/", response_model=UserListResponse, dependencies=[Depends(require_user_read)])
async def search_users(
    query: Optional[str] = Query(None, description="Search in email, name"),
    entity_id: Optional[str] = Query(None, description="Filter by entity membership"),
    status: Optional[UserStatus] = Query(None, description="Filter by user status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Search users with filtering and pagination
    
    Requires: user:read permission
    """
    users, total = await UserService.search_users(
        query=query,
        entity_id=entity_id,
        status=status,
        page=page,
        page_size=page_size,
        current_user=current_user
    )
    
    # Convert to response models
    items = []
    for user in users:
        user_response = await _user_to_response(user)
        items.append(user_response)
    
    total_pages = (total + page_size - 1) // page_size
    
    return UserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post("/", response_model=UserResponse, dependencies=[Depends(require_permission("user:create"))])
async def create_user(
    user_data: UserCreateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Create a new user with entity assignments
    
    Requires: user:create permission
    """
    profile_data = {
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "phone": user_data.phone
    }
    
    entity_assignments = [
        {
            "entity_id": assignment.entity_id,
            "role_ids": assignment.role_ids,
            "status": assignment.status,
            "valid_from": assignment.valid_from,
            "valid_until": assignment.valid_until
        }
        for assignment in user_data.entity_assignments
    ]
    
    user, temp_password = await UserService.create_user_with_entities(
        email=user_data.email,
        password=user_data.password,
        profile_data=profile_data,
        entity_assignments=entity_assignments,
        status=user_data.status,
        send_welcome_email=user_data.send_welcome_email,
        current_user=current_user
    )
    
    return await _user_to_response(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: UserModel = Depends(require_self_or_permission("user:read"))
):
    """
    Get user profile by ID
    
    Requires: user:read permission or self
    """
    user = await UserService.get_user(user_id)
    return await _user_to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    current_user: UserModel = Depends(require_self_or_permission("user:update"))
):
    """
    Update user profile and entity assignments
    
    Requires: user:update permission or self
    """
    # Update profile if provided
    if any([user_data.email, user_data.first_name, user_data.last_name, user_data.phone, user_data.status is not None]):
        profile_dict = {}
        if user_data.first_name is not None:
            profile_dict["first_name"] = user_data.first_name
        if user_data.last_name is not None:
            profile_dict["last_name"] = user_data.last_name
        if user_data.phone is not None:
            profile_dict["phone"] = user_data.phone
            
        user = await UserService.update_user_profile(
            user_id=user_id,
            profile_data=profile_dict,
            current_user=current_user
        )
        
        # Update email if provided
        if user_data.email:
            user.email = user_data.email
            await user.save()
            
        # Update status if provided
        if user_data.status is not None:
            user.status = user_data.status
            await user.save()
    else:
        user = await UserService.get_user(user_id)
    
    # Update entity assignments if provided
    if user_data.entity_assignments is not None:
        entity_assignments = [
            {
                "entity_id": assignment.entity_id,
                "role_ids": assignment.role_ids,
                "status": assignment.status,
                "valid_from": assignment.valid_from,
                "valid_until": assignment.valid_until
            }
            for assignment in user_data.entity_assignments
        ]
        
        user = await UserService.update_user_entities(
            user_id=user_id,
            entity_assignments=entity_assignments,
            current_user=current_user
        )
    
    return await _user_to_response(user)


@router.delete("/{user_id}", dependencies=[Depends(require_permission("user:delete"))])
async def delete_user(
    user_id: str,
    hard_delete: bool = Query(False, description="Permanently delete user"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Delete or deactivate user
    
    Requires: user:delete permission
    """
    await UserService.delete_user(
        user_id=user_id,
        current_user=current_user,
        hard_delete=hard_delete
    )
    
    action = "permanently deleted" if hard_delete else "deactivated"
    return {"message": f"User {action} successfully"}


@router.post("/{user_id}/status", response_model=UserResponse, dependencies=[Depends(require_permission("user:update"))])
async def update_user_status(
    user_id: str,
    status_update: UserStatusUpdate,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Update user account status
    
    Requires: user:update permission
    """
    user = await UserService.update_user_status(
        user_id=user_id,
        status=status_update.status,
        current_user=current_user
    )
    
    return await _user_to_response(user)


@router.post("/invite", response_model=UserInviteResponse, dependencies=[Depends(require_permission("user:invite"))])
async def invite_user(
    invite_request: UserInviteRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Invite a user to an entity
    
    Requires: user:invite permission
    """
    user = await UserService.invite_user(
        email=invite_request.email,
        entity_id=invite_request.entity_id,
        role_id=invite_request.role_id,
        invited_by=current_user,
        first_name=invite_request.first_name,
        last_name=invite_request.last_name,
        send_email=invite_request.send_email
    )
    
    user_response = await _user_to_response(user)
    
    # Return temporary password if user was created
    temp_password = None
    if user.metadata and user.metadata.get("temp_password"):
        temp_password = "Check email for temporary password"
    
    return UserInviteResponse(
        user=user_response,
        temporary_password=temp_password,
        invitation_sent=invite_request.send_email,
        message="User invited successfully"
    )


@router.post("/{user_id}/reset-password", response_model=UserPasswordResetResponse, dependencies=[Depends(require_permission("user:update"))])
async def reset_user_password(
    user_id: str,
    reset_request: UserPasswordResetRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Reset user password (admin function)
    
    Requires: user:update permission
    """
    temp_password = await UserService.reset_user_password(
        user_id=user_id,
        current_user=current_user,
        send_email=reset_request.send_email
    )
    
    return UserPasswordResetResponse(
        message="Password reset successfully",
        temporary_password=temp_password if not reset_request.send_email else None,
        email_sent=reset_request.send_email
    )


@router.get("/{user_id}/memberships", response_model=UserMembershipListResponse)
async def get_user_memberships(
    user_id: str,
    include_inactive: bool = Query(False, description="Include inactive memberships"),
    current_user: UserModel = Depends(require_self_or_permission("user:read"))
):
    """
    Get user's entity memberships
    
    Requires: user:read permission or self
    """
    memberships = await UserService.get_user_memberships(
        user_id=user_id,
        current_user=current_user,
        include_inactive=include_inactive
    )
    
    return UserMembershipListResponse(
        user_id=user_id,
        memberships=memberships,
        total=len(memberships)
    )


@router.get("/stats/overview", response_model=UserStatsResponse, dependencies=[Depends(require_user_read)])
async def get_user_stats():
    """
    Get user statistics overview
    
    Requires: user:read permission
    """
    from datetime import datetime, timezone, timedelta
    
    # Get current time
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    
    # Count users by status
    total_users = await UserModel.count()
    active_users = await UserModel.find(UserModel.status == UserStatus.ACTIVE).count()
    inactive_users = await UserModel.find(UserModel.status == UserStatus.INACTIVE).count()
    suspended_users = await UserModel.find(UserModel.status == UserStatus.SUSPENDED).count()
    banned_users = await UserModel.find(UserModel.status == UserStatus.BANNED).count()
    terminated_users = await UserModel.find(UserModel.status == UserStatus.TERMINATED).count()
    
    # Recent signups (last 30 days)
    recent_signups = await UserModel.find(
        UserModel.created_at >= thirty_days_ago
    ).count()
    
    # Recent logins (last 30 days)
    recent_logins = await UserModel.find(
        UserModel.last_login >= thirty_days_ago
    ).count()
    
    return UserStatsResponse(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        suspended_users=suspended_users,
        banned_users=banned_users,
        terminated_users=terminated_users,
        recent_signups=recent_signups,
        recent_logins=recent_logins
    )


@router.post("/bulk-action", response_model=UserBulkActionResponse)
async def bulk_user_action(
    bulk_request: UserBulkActionRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Perform bulk action on multiple users
    
    Requires: user:update permission for status changes
    """
    # Check permission first
    from api.dependencies import PermissionChecker
    await PermissionChecker.require_user_permission(current_user, "user:update")
    
    successful = []
    failed = []
    
    for user_id in bulk_request.user_ids:
        try:
            # Prevent self-action if not activation
            if user_id == str(current_user.id) and bulk_request.status != UserStatus.ACTIVE:
                failed.append({
                    "user_id": user_id,
                    "error": "Cannot perform this action on your own account"
                })
                continue
            
            await UserService.update_user_status(
                user_id=user_id,
                status=bulk_request.status,
                current_user=current_user
            )
            successful.append(user_id)
            
        except Exception as e:
            failed.append({
                "user_id": user_id,
                "error": str(e)
            })
    
    return UserBulkActionResponse(
        successful=successful,
        failed=failed,
        total_processed=len(bulk_request.user_ids),
        total_successful=len(successful),
        total_failed=len(failed)
    )