"""User request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    """
    User response schema (safe to expose).

    Only includes authentication and basic identity fields.
    """

    id: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: str  # UserStatus enum value
    email_verified: bool = False
    is_superuser: bool = False
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    root_entity_id: Optional[str] = Field(
        None,
        description="Root entity (organization) this user belongs to.",
    )
    root_entity_name: Optional[str] = Field(
        None,
        description="Display name of the root entity (for convenience).",
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    suspended_until: Optional[datetime] = None
    locked_until: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


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
    root_entity_id: Optional[str] = Field(
        None,
        description="Root entity (organization) to assign user to. Must be a root entity.",
    )


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class AdminResetPasswordRequest(BaseModel):
    """Admin password reset request schema (no current password required)."""

    new_password: str = Field(..., min_length=8)


class UserStatusUpdateRequest(BaseModel):
    """
    User status update request schema.

    Used by admins to change user account status (activate, suspend, ban).

    For suspensions, optionally provide suspended_until for auto-expiry.
    """

    status: str = Field(
        ...,
        description="New user status: active, suspended, or banned",
        pattern="^(active|suspended|banned)$",
    )
    suspended_until: Optional[str] = Field(
        None,
        description="ISO 8601 datetime for suspension auto-expiry (only for 'suspended' status)",
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for status change (stored in audit log)",
    )


class UserSuperuserUpdateRequest(BaseModel):
    """Update a user's platform superuser flag."""

    is_superuser: bool = Field(
        ...,
        description="Whether the user should have platform-wide superuser privileges.",
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for the audit log.",
    )
