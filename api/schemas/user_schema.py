from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from beanie import PydanticObjectId
from datetime import datetime
from .permission_schema import PermissionDetailSchema

from ..models.user_model import UserStatus

class UserCreateSchema(BaseModel):
    """
    Schema for user creation via API endpoints.
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password (min 8 characters)")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    status: UserStatus = Field(UserStatus.ACTIVE, description="User account status")
    
    # Optional fields for advanced user creation
    client_account_id: Optional[str] = Field(None, description="Client account ID")
    roles: Optional[List[str]] = Field(default_factory=list, description="List of role IDs")
    groups: Optional[List[str]] = Field(default_factory=list, description="List of group IDs")
    is_main_client: Optional[bool] = Field(False, description="Whether user is main client admin")
    is_platform_staff: Optional[bool] = Field(False, description="Whether user is platform staff")
    platform_scope: Optional[str] = Field(None, description="Platform scope for staff members")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "first_name": "John",
                "last_name": "Doe",
                "status": "active",
                "client_account_id": "optional_client_id",
                "roles": ["role_id_1", "role_id_2"],
                "groups": ["group_id_1"]
            }
        }
    )

class UserUpdateSchema(BaseModel):
    """
    Schema for user updates.
    """
    email: Optional[EmailStr] = Field(None, description="User's email address")
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    status: Optional[UserStatus] = Field(None, description="User account status")
    roles: Optional[List[str]] = Field(None, description="List of role IDs to assign")
    groups: Optional[List[str]] = Field(None, description="List of group IDs to assign")

class UserResponseSchema(BaseModel):
    """
    Schema for user data in API responses.
    Returns full permission details with both ID and name.
    """
    id: PydanticObjectId = Field(alias="_id")
    email: EmailStr
    first_name: str
    last_name: str
    status: UserStatus
    client_account_id: Optional[str] = None
    roles: List[str] = []  # Role ObjectIds for updates
    groups: List[str] = []  # Group ObjectIds for updates
    permissions: Optional[List[PermissionDetailSchema]] = []  # Effective permissions with full details
    is_platform_staff: bool = False
    platform_scope: Optional[str] = None
    created_at: datetime
    updated_at: datetime

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