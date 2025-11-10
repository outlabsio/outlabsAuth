"""User request/response schemas."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    """
    User response schema (safe to expose).

    Only includes authentication and basic identity fields.
    For extended profile data, use Beanie Links to your own profile models.
    """

    id: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: str  # UserStatus enum value
    email_verified: bool = False
    is_superuser: bool = False

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """User profile update request schema."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserCreateRequest(BaseModel):
    """
    Admin user creation request schema.

    Allows admins to create users with specific settings.
    Different from RegisterRequest which is for self-registration.
    """

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_superuser: bool = Field(default=False)


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class AdminResetPasswordRequest(BaseModel):
    """Admin password reset request schema (no current password required)."""

    new_password: str = Field(..., min_length=8)
