from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from bson import ObjectId

from ..database import get_database
from ..services.user_service import user_service
from ..schemas.user_schema import UserCreateSchema, UserUpdateSchema, UserResponseSchema
from ..dependencies import valid_object_id

router = APIRouter(
    prefix="/v1/users",
    tags=["User Management"]
)

@router.post("/", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
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
    db: AsyncIOMotorDatabase = Depends(get_database),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of all users with pagination.
    """
    users = await user_service.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user_by_id(
    user_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieve a single user by their ID.
    """
    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    return user

@router.put("/{user_id}", response_model=UserResponseSchema)
async def update_user(
    user_data: UserUpdateSchema,
    user_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update a user's details.
    """
    updated_user = await user_service.update_user(db, user_id, user_data)
    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    return updated_user 