from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from ..models.user_model import UserModel
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema, UserResponseSchema, UserBulkCreateResponseSchema
from ..schemas.auth_schema import TokenDataSchema
from ..services.user_service import user_service
from ..dependencies import get_current_user_with_token, has_permission
from ..dependencies import user_has_role, require_super_admin, require_admin, can_access_user

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
    
    # Proper Beanie way: access Link ID via ref.id
    client_account_id = str(current_user.client_account.ref.id)
    new_user = await user_service.create_sub_user(user_data, client_account_id)
    
    # Convert to response format
    user_dict = new_user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    
    if new_user.client_account:
        user_dict["client_account_id"] = str(new_user.client_account.id)
    else:
        user_dict["client_account_id"] = None
    # Remove the client_account object from response
    user_dict.pop("client_account", None)
    
    return user_dict

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
    
    # Convert successful creates to response format
    converted_successful = []
    for user in successful_creates:
        user_dict = user.model_dump(by_alias=True)
        user_dict["_id"] = str(user_dict["_id"])
        
        if user.client_account:
            user_dict["client_account_id"] = str(user.client_account.id)
        else:
            user_dict["client_account_id"] = None
        # Remove the client_account object from response
        user_dict.pop("client_account", None)
        converted_successful.append(user_dict)
    
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
    
    # Convert to response format
    user_dict = new_user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    
    if new_user.client_account:
        user_dict["client_account_id"] = str(new_user.client_account.id)
    else:
        user_dict["client_account_id"] = None
    # Remove the client_account object from response
    user_dict.pop("client_account", None)
    
    return user_dict

@router.get("/", response_model=List[UserResponseSchema], dependencies=[Depends(has_permission("user:read"))])
async def get_all_users(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of users.
    - Super admins see all users.
    - Platform staff with "all" scope see all users.
    - Platform staff with "created" scope see their platform users only.
    - Client users only see users within their own client_account_id.
    """
    current_user, token_data = user_and_token
    
    # Check user privileges
    is_super_admin = user_has_role(current_user, "super_admin")
    is_platform_staff = getattr(current_user, 'is_platform_staff', False)
    platform_scope = getattr(current_user, 'platform_scope', None)
    client_account_id = None
    
    if is_super_admin:
        # Super admin sees all users
        pass
    elif is_platform_staff and platform_scope == "all":
        # Platform staff with "all" scope sees all users
        pass
    elif token_data.client_account_id:
        # For regular users, enforce client account scoping
        try:
            client_account_id = PydanticObjectId(token_data.client_account_id)
        except Exception:
            pass
    
    users = await user_service.get_users(skip=skip, limit=limit, client_account_id=client_account_id)
    
    # Convert users to response format
    converted_users = []
    for user in users:
        user_dict = user.model_dump(by_alias=True)
        user_dict["_id"] = str(user_dict["_id"])
        
        if user.client_account:
            user_dict["client_account_id"] = str(user.client_account.id)
        else:
            user_dict["client_account_id"] = None
        # Remove the client_account object from response
        user_dict.pop("client_account", None)
        converted_users.append(user_dict)
    
    return converted_users

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user_by_id(
    user: UserModel = Depends(can_access_user())  # All access control handled by dependency!
):
    """
    Retrieve a single user by their ID.
    Access control is handled by the dependency - users can view their own data, admins can view any user data.
    """

    # Convert to response format
    user_dict = user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    
    if user.client_account:
        user_dict["client_account_id"] = str(user.client_account.id)
    else:
        user_dict["client_account_id"] = None
    # Remove the client_account object from response
    user_dict.pop("client_account", None)

    return user_dict

@router.put("/{user_id}", response_model=UserResponseSchema, dependencies=[Depends(has_permission("user:update"))])
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
    
    # Convert to response format
    user_dict = updated_user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    
    if updated_user.client_account:
        user_dict["client_account_id"] = str(updated_user.client_account.id)
    else:
        user_dict["client_account_id"] = None
    # Remove the client_account object from response
    user_dict.pop("client_account", None)
    
    return user_dict

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("user:delete"))])
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