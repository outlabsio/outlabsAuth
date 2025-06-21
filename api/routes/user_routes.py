from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Tuple
from bson import ObjectId

from ..database import get_database
from ..services.user_service import user_service
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema, UserResponseSchema, UserBulkCreateResponseSchema
from ..schemas.auth_schema import TokenDataSchema
from ..models.user_model import UserModel
from ..dependencies import valid_object_id, has_permission, get_current_user_with_token

router = APIRouter(
    prefix="/v1/users",
    tags=["User Management"],
    dependencies=[Depends(has_permission("user:read"))]
)

@router.post("/create_sub_user", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("user:create_sub"))])
async def create_sub_user(
    user_data: UserCreateSchema,
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Allows a 'main_client' user to create a new user within their own client account.
    """
    current_user, _ = user_and_token
    
    # Check if the current user is a main client and has a client account
    if not current_user.is_main_client or not current_user.client_account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create sub-users."
        )
    
    new_user = await user_service.create_sub_user(db, user_data, current_user.client_account_id)
    return new_user

@router.post("/bulk-create", response_model=UserBulkCreateResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("user:bulk_create"))])
async def bulk_create_users(
    users_data: List[UserCreateSchema],
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Creates multiple users in a single request.
    This is an admin-only endpoint that processes users one by one and reports
    on successes and failures.
    """
    successful_creates, failed_creates = await user_service.bulk_create_users(db, users_data)
    
    # Manually convert successful UserModel list to UserResponseSchema list if needed
    # For now, let's assume Pydantic handles this conversion based on response_model
    
    return UserBulkCreateResponseSchema(
        successful_creates=successful_creates,
        failed_creates=failed_creates
    )

@router.post("/", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("user:create"))])
async def create_user(
    user_data: UserCreateSchema,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Create a new user.
    This endpoint is intended for admin use.
    """
    # Check if user with this email already exists
    existing_user = await user_service.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists."
        )
    
    new_user = await user_service.create_user(db, user_data)
    return new_user

@router.get("/", response_model=List[UserResponseSchema])
async def get_all_users(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    db: AsyncIOMotorDatabase = Depends(get_database),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of users.
    - Platform admins see all users.
    - Client users only see users within their own client_account_id.
    """
    _, token_data = user_and_token
    users = await user_service.get_users(db, skip=skip, limit=limit, client_account_id=token_data.client_account_id)
    return users

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user_by_id(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    user_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieve a single user by their ID.
    """
    _, token_data = user_and_token
    user = await user_service.get_user_by_id(db, user_id)
    
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found.")
        
    # Enforce data scoping
    if token_data.client_account_id and user.client_account_id != token_data.client_account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found.")

    return user

@router.put("/{user_id}", response_model=UserResponseSchema, dependencies=[Depends(has_permission("user:update"))])
async def update_user(
    user_data: UserUpdateSchema,
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    user_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update a user's details.
    """
    _, token_data = user_and_token
    
    # First, verify the user to be updated exists and belongs to the client account if necessary
    user_to_update = await user_service.get_user_by_id(db, user_id)
    if user_to_update is None or (token_data.client_account_id and user_to_update.client_account_id != token_data.client_account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found.")

    current_user, _ = user_and_token
    updated_user = await user_service.update_user(db, user_id, user_data, current_user)
    return updated_user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("user:delete"))])
async def delete_user(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    user_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Delete a user by their ID.
    """
    _, token_data = user_and_token
    
    # Verify the user to be deleted exists and belongs to the client account if necessary
    user_to_delete = await user_service.get_user_by_id(db, user_id)
    if user_to_delete is None or (token_data.client_account_id and user_to_delete.client_account_id != token_data.client_account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found.")

    await user_service.delete_user(db, user_id)