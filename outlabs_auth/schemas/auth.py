"""Authentication request/response schemas."""

from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    """Login response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RegisterRequest(BaseModel):
    """User registration request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class RefreshRequest(BaseModel):
    """Token refresh request schema."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Token refresh response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request schema."""

    token: str
    new_password: str = Field(..., min_length=8)


class LogoutRequest(BaseModel):
    """
    Logout request schema.

    Supports flexible logout patterns:
    - Single device logout (provide refresh_token)
    - All devices logout (omit refresh_token)
    - Immediate access token revocation (set immediate=True, requires Redis)
    """

    refresh_token: Optional[str] = Field(
        default=None,
        description="Specific refresh token to revoke. If omitted, revokes all user sessions.",
    )
    immediate: bool = Field(
        default=False,
        description="If True, blacklist current access token immediately (requires Redis). Default: False (15-min security window)",
    )


class AuthConfigResponse(BaseModel):
    """
    Auth configuration response schema.

    Returns information about the current OutlabsAuth preset and enabled features.
    Used by admin UIs to conditionally show/hide features.
    """

    preset: str = Field(
        ..., description="Preset name: 'SimpleRBAC' or 'EnterpriseRBAC'"
    )
    features: Dict[str, bool] = Field(
        ...,
        description="Enabled features (entity_hierarchy, context_aware_roles, abac, etc.)",
    )
    available_permissions: List[str] = Field(
        ..., description="List of all available permission strings for this preset"
    )
