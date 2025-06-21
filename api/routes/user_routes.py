from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Tuple
from beanie import PydanticObjectId

from ..services.user_service import user_service
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema, UserResponseSchema, UserBulkCreateResponseSchema
from ..schemas.auth_schema import TokenDataSchema
from ..models.user_model import UserModel
from ..dependencies import valid_object_id, has_permission, get_current_user_with_token

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
        user_dict["client_account_id"] = str(new_user.client_account.ref.id)
    else:
        user_dict["client_account_id"] = None
    # Remove the client_account object from response
    user_dict.pop("client_account", None)
    
    return user_dict

@router.post("/bulk-create", response_model=UserBulkCreateResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("user:bulk_create"))])
async def bulk_create_users(
    users_data: List[UserCreateSchema]
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
            user_dict["client_account_id"] = str(user.client_account.ref.id)
        else:
            user_dict["client_account_id"] = None
        # Remove the client_account object from response
        user_dict.pop("client_account", None)
        converted_successful.append(user_dict)
    
    return UserBulkCreateResponseSchema(
        successful_creates=converted_successful,
        failed_creates=failed_creates
    )

@router.post("/", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("user:create"))])
async def create_user(
    user_data: UserCreateSchema
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
        user_dict["client_account_id"] = str(new_user.client_account.ref.id)
    else:
        user_dict["client_account_id"] = None
    # Remove the client_account object from response
    user_dict.pop("client_account", None)
    
    return user_dict

@router.get("/", response_model=List[UserResponseSchema])
async def get_all_users(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of users.
    - Platform admins see all users.
    - Client users only see users within their own client_account_id.
    """
    _, token_data = user_and_token
    
    # Convert client_account_id from string to ObjectId if present
    client_account_id = None
    if token_data.client_account_id:
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
            user_dict["client_account_id"] = str(user.client_account.ref.id)
        else:
            user_dict["client_account_id"] = None
        # Remove the client_account object from response
        user_dict.pop("client_account", None)
        converted_users.append(user_dict)
    
    return converted_users

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user_by_id(
    user_id: str,
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
):
    """
    Retrieve a single user by their ID.
    """
    # Validate ObjectId format
    try:
        user_object_id = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid ObjectId: {user_id}")
    
    _, token_data = user_and_token
    user = await user_service.get_user_by_id(user_object_id)
    
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
        
    # Enforce data scoping - compare client account IDs
    if token_data.client_account_id and user.client_account:
        if str(user.client_account.ref.id) != token_data.client_account_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
    elif token_data.client_account_id and not user.client_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")

    # Convert to response format
    user_dict = user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    if user.client_account:
        user_dict["client_account_id"] = str(user.client_account.ref.id)
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
    
    _, token_data = user_and_token
    
    # First, verify the user to be updated exists and belongs to the client account if necessary
    user_to_update = await user_service.get_user_by_id(user_object_id)
    if user_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
    
    # Enforce data scoping
    if token_data.client_account_id and user_to_update.client_account:
        if str(user_to_update.client_account.ref.id) != token_data.client_account_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
    elif token_data.client_account_id and not user_to_update.client_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")

    current_user, _ = user_and_token
    updated_user = await user_service.update_user(user_object_id, user_data, current_user)
    
    # Convert to response format
    user_dict = updated_user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    if updated_user.client_account:
        user_dict["client_account_id"] = str(updated_user.client_account.ref.id)
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
    
    _, token_data = user_and_token
    
    # First, verify the user to be deleted exists and belongs to the client account if necessary
    user_to_delete = await user_service.get_user_by_id(user_object_id)
    if user_to_delete is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
    
    # Enforce data scoping
    if token_data.client_account_id and user_to_delete.client_account:
        if str(user_to_delete.client_account.ref.id) != token_data.client_account_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")
    elif token_data.client_account_id and not user_to_delete.client_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")

    success = await user_service.delete_user(user_object_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_object_id} not found.")