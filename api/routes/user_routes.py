from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from ..models.user_model import UserModel
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema, UserResponseSchema, UserBulkCreateResponseSchema
from ..schemas.auth_schema import TokenDataSchema
from ..services.user_service import user_service
from ..dependencies import get_current_user_with_token, has_permission, convert_user_to_response
from ..dependencies import user_has_role, require_super_admin, require_admin, can_access_user, require_user_read_access

router = APIRouter(
    prefix="/v1/users",
    tags=["User Management"],
    # Temporarily removing router-level dependency to debug 307 redirects
    # dependencies=[Depends(has_permission("user:read"))]
)

@router.post("/create_sub_user", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("user:create_sub"))])
async def create_sub_user(
    user_data: UserCreateSchema,
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
):
    """
    Allows a 'main_client' user to create a new user within their own client account.
    """
    current_user, _ = user_and_token
    
    # Check if the current user is a main client and has a client account
    if not current_user.is_main_client or not current_user.client_account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create sub-users."
        )
    
    # Get client account ID directly
    client_account_id = str(current_user.client_account.id)
    new_user = await user_service.create_sub_user(user_data, client_account_id)
    
    # Convert to response format using utility
    return convert_user_to_response(new_user)

@router.post("/bulk-create", response_model=UserBulkCreateResponseSchema, status_code=status.HTTP_201_CREATED)
async def bulk_create_users(
    users_data: List[UserCreateSchema],
    current_user: UserModel = Depends(require_admin)  # Using dependency for admin-only access
):
    """
    Creates multiple users in a single request.
    This is an admin-only endpoint that processes users one by one and reports
    on successes and failures.
    """
    successful_creates, failed_creates = await user_service.bulk_create_users(users_data)
    
    # Convert successful creates to response format using utility
    converted_successful = [convert_user_to_response(user) for user in successful_creates]
    
    return UserBulkCreateResponseSchema(
        successful_creates=converted_successful,
        failed_creates=failed_creates
    )

@router.post("/", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateSchema,
    current_user: UserModel = Depends(require_admin)  # Using dependency for admin-only access
):
    """
    Create a new user.
    This endpoint is intended for admin use.
    """
    # Check if user with this email already exists
    existing_user = await user_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists."
        )
    
    new_user = await user_service.create_user(user_data)
    
    # Convert to response format using utility
    return convert_user_to_response(new_user)

@router.get("/", response_model=List[UserResponseSchema])
async def get_all_users(
    current_user: UserModel = Depends(require_user_read_access),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of users.
    Only accessible by admin users (super_admin, admin, client_admin roles).
    - Super admins and platform admins see all users.
    - Client admins see users scoped to their domain.
    """
    # Check user privileges for data scoping
    user_permissions = await user_service.get_user_effective_permissions(current_user.id)
    is_super_admin = user_has_role(current_user, "super_admin")
    has_manage_all = "user:manage_all" in user_permissions
    has_read_all = "user:read_all" in user_permissions
    client_account_id = None
    
    if is_super_admin or has_manage_all or has_read_all:
        # Super admin or platform admin with system-wide access sees all users
        pass
    elif current_user.client_account:
        # Check if user is from a platform root account
        user_client = current_user.client_account
        if user_client.is_platform_root and ("user:read_client" in user_permissions or "support:cross_client" in user_permissions):
            # Platform staff with cross-client permissions see all users
            pass
        else:
            # Regular client admins see only users within their client account
            client_account_id = current_user.client_account.id
    
    users = await user_service.get_users(skip=skip, limit=limit, client_account_id=client_account_id)
    
    # Convert users to response format using utility
    return [convert_user_to_response(user) for user in users]

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user_by_id(
    user: UserModel = Depends(can_access_user())  # All access control handled by dependency!
):
    """
    Retrieve a single user by their ID.
    Access control is handled by the dependency - users can view their own data, admins can view any user data.
    """

    # Convert to response format using utility
    return convert_user_to_response(user)

@router.put("/{user_id}", response_model=UserResponseSchema, dependencies=[Depends(has_permission("user:manage_client"))])
async def update_user(
    user_id: str,
    user_data: UserUpdateSchema,
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
):
    """
    Update a user's details.
    """
    # Validate ObjectId format
    try:
        user_object_id = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid ObjectId: {user_id}")
    
    current_user, token_data = user_and_token
    
    # First, verify the user to be updated exists
    user_to_update = await user_service.get_user_by_id(user_object_id)
    if user_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
    
    # Enforce data scoping - but allow super admins to access all users
    is_super_admin = user_has_role(current_user, "super_admin")
    if not is_super_admin and token_data.client_account_id:
        # For non-platform admins, enforce client account scoping
        if user_to_update.client_account:
            if str(user_to_update.client_account.id) != token_data.client_account_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
        else:
            # User has no client account but admin does - not allowed to access
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")

    updated_user = await user_service.update_user(user_object_id, user_data, current_user)
    
    # Convert to response format using utility
    return convert_user_to_response(updated_user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("user:manage_client"))])
async def delete_user(
    user_id: str,
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
):
    """
    Delete a user.
    """
    # Validate ObjectId format
    try:
        user_object_id = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid ObjectId: {user_id}")
    
    current_user, token_data = user_and_token
    
    # First, verify the user to be deleted exists
    user_to_delete = await user_service.get_user_by_id(user_object_id)
    if user_to_delete is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
    
    # Enforce data scoping - but allow super admins to access all users
    is_super_admin = user_has_role(current_user, "super_admin")
    if not is_super_admin and token_data.client_account_id:
        # For non-platform admins, enforce client account scoping
        if user_to_delete.client_account:
            if str(user_to_delete.client_account.id) != token_data.client_account_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
        else:
            # User has no client account but admin does - not allowed to access
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")

    success = await user_service.delete_user(user_object_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")