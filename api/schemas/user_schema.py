from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from bson import ObjectId

from ..models.user_model import UserStatus
from ..models.base_model import PyObjectId

class UserCreateSchema(BaseModel):
    """
    Schema for creating a new user, used for registration.
    """
    email: EmailStr
    password: str = Field(min_length=8, description="User's password")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    client_account_id: Optional[PyObjectId] = None
    roles: Optional[List[str]] = Field(default_factory=list)
    is_main_client: Optional[bool] = False

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class UserUpdateSchema(BaseModel):
    """
    Schema for updating a user. All fields are optional.
    """
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    roles: Optional[List[str]] = None
    status: Optional[UserStatus] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class UserResponseSchema(BaseModel):
    """
    Schema for returning user data in API responses.
    This schema excludes sensitive information like the password hash.
    """
    id: PyObjectId = Field(alias="_id")
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    client_account_id: Optional[PyObjectId] = None
    roles: List[str]
    is_main_client: bool
    status: UserStatus

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str} 