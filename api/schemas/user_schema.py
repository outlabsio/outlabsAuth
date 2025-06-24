from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

from ..models.user_model import UserStatus

class UserCreateSchema(BaseModel):
    """
    Schema for creating a new user, used for registration.
    """
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    client_account_id: Optional[str] = None  # String ID for client account
    roles: Optional[List[str]] = []
    groups: Optional[List[str]] = []  # List of group IDs
    is_main_client: Optional[bool] = False
    is_platform_staff: Optional[bool] = False
    platform_scope: Optional[str] = None
    locale: Optional[str] = None

class UserUpdateSchema(BaseModel):
    """
    Schema for updating a user. All fields are optional.
    """
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    roles: Optional[List[str]] = None
    groups: Optional[List[str]] = None  # List of group IDs
    status: Optional[UserStatus] = None
    locale: Optional[str] = None

class UserResponseSchema(BaseModel):
    """
    Schema for returning user data in API responses.
    This schema excludes sensitive information like the password hash.
    """
    id: str = Field(..., alias="_id")
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    client_account_id: Optional[str] = None  # Will be populated from Link
    roles: List[str]
    groups: Optional[List[str]] = []  # List of group IDs
    permissions: Optional[List[str]] = []  # Effective permissions from roles and groups
    is_main_client: bool
    is_platform_staff: Optional[bool] = False
    platform_scope: Optional[str] = None
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    locale: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class FailedUserCreationSchema(BaseModel):
    """
    Schema to report a failure during a bulk user creation process.
    """
    user_data: UserCreateSchema
    error: str

class UserBulkCreateResponseSchema(BaseModel):
    """
    Schema for the response of a bulk user creation request.
    """
    successful_creates: List[UserResponseSchema]
    failed_creates: List[FailedUserCreationSchema] 