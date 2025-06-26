from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from ..models.user_model import UserModel
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema, UserResponseSchema, UserBulkCreateResponseSchema
from ..schemas.auth_schema import TokenDataSchema
from ..services.user_service import user_service
from ..dependencies import get_current_user_with_token, has_permission, convert_user_to_response
from ..dependencies import require_admin, can_access_user
from ..dependencies import can_read_users, can_manage_users

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
    current_user: UserModel = Depends(can_manage_users)
):
    """
    Create a new user.
    Access control is handled by the dependency which ensures the user has appropriate permissions.
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
    current_user: UserModel = Depends(can_read_users),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of users, automatically scoped by the user's permissions.
    The dependency ensures the user has appropriate read permissions,
    and the service layer handles data scoping based on user context.
    """
    # The user_service now handles all the scoping logic internally
    users = await user_service.get_users(
        current_user=current_user,
        skip=skip,
        limit=limit
    )
    
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

@router.put("/{user_id}", response_model=UserResponseSchema)
async def update_user(
    user_id: str,
    user_data: UserUpdateSchema,
    current_user: UserModel = Depends(can_manage_users)
):
    """
    Update a user's details.
    Access control and data scoping are handled by the dependency and service layer.
    """
    # Validate ObjectId format
    try:
        user_object_id = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid ObjectId: {user_id}")
    
    # The service layer now handles all access control and scoping
    updated_user = await user_service.update_user(user_object_id, user_data, current_user)
    
    if not updated_user:
        # Service layer returned None because of a scope violation or user not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or access denied.")
    
    # Convert to response format using utility
    return convert_user_to_response(updated_user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: UserModel = Depends(can_manage_users)
):
    """
    Delete a user.
    Access control and data scoping are handled by the dependency and service layer.
    """
    # Validate ObjectId format
    try:
        user_object_id = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid ObjectId: {user_id}")
    
    # The service layer now handles all access control and scoping
    success = await user_service.delete_user(user_object_id, current_user)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or access denied.")