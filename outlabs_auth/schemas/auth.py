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


class MagicLinkRequest(BaseModel):
    """Request a magic-link login email."""

    email: EmailStr
    redirect_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional host-owned redirect URL to include when building the email link.",
    )


class MagicLinkVerifyRequest(BaseModel):
    """Verify a magic-link token and exchange it for JWT tokens."""

    token: str


class AccessCodeRequest(BaseModel):
    """Request a short-lived email access code."""

    email: EmailStr
    redirect_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional host-owned redirect URL to include in the access-code email.",
    )


class AccessCodeVerifyRequest(BaseModel):
    """Verify an email access code and exchange it for JWT tokens."""

    email: EmailStr
    code: str = Field(..., min_length=1, max_length=32)


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


class InviteUserRequest(BaseModel):
    """Invite user request schema."""

    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_superuser: bool = Field(
        default=False,
        description="Invite this user with platform-wide superuser privileges. Only current superusers may set this.",
    )
    role_ids: Optional[List[str]] = Field(default=None, description="Role IDs to assign after invite")
    entity_id: Optional[str] = Field(default=None, description="Entity ID to add membership to")


class AcceptInviteRequest(BaseModel):
    """Accept invite request schema."""

    token: str
    new_password: str = Field(..., min_length=8)


class AuthConfigResponse(BaseModel):
    """
    Auth configuration response schema.

    Returns information about the current OutlabsAuth preset and enabled features.
    Used by admin UIs to conditionally show/hide features.
    """

    preset: str = Field(..., description="Preset name: 'SimpleRBAC' or 'EnterpriseRBAC'")
    features: Dict[str, bool] = Field(
        ...,
        description="Enabled features (entity_hierarchy, context_aware_roles, abac, etc.)",
    )
    auth_methods: Dict[str, bool] = Field(
        default_factory=lambda: {"password": True, "magic_link": False, "access_code": False},
        description="Public human-auth methods currently enabled by this auth router.",
    )
    available_permissions: List[str] = Field(
        ..., description="List of all available permission strings for this preset"
    )
