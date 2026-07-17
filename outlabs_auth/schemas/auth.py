"""Authentication request/response schemas."""

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

_E164_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def _normalize_optional_phone(phone: Optional[str]) -> Optional[str]:
    if phone is None:
        return None
    normalized = phone.strip().replace(" ", "")
    return normalized or None


def _require_exactly_one_email_or_phone(
    *,
    email: Optional[EmailStr],
    phone: Optional[str],
) -> Optional[str]:
    normalized_phone = _normalize_optional_phone(phone)
    has_email = email is not None
    has_phone = normalized_phone is not None
    if has_email == has_phone:
        raise ValueError("Provide exactly one of email or phone")
    if normalized_phone is not None and not _E164_PHONE_RE.match(normalized_phone):
        raise ValueError("Phone must be E.164 format (e.g. +15551234567)")
    return normalized_phone


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginResponse(BaseModel):
    """Login response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RegisterRequest(BaseModel):
    """User registration request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
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
    new_password: str = Field(..., min_length=8, max_length=128)


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
    """Request a short-lived access code by email or verified phone (WhatsApp/SMS)."""

    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="E.164 phone for WhatsApp/SMS login when the number is verified on the account.",
    )
    channel: Optional[str] = Field(
        default=None,
        description=(
            "Delivery channel. Required semantics: email when email is set; "
            "whatsapp (default) or sms when phone is set."
        ),
    )
    redirect_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional host-owned redirect URL to include in the access-code email.",
    )

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "AccessCodeRequest":
        self.phone = _require_exactly_one_email_or_phone(email=self.email, phone=self.phone)
        channel = (self.channel or "").strip().lower() or None
        if self.email is not None:
            if channel is not None and channel != "email":
                raise ValueError("Email access codes must use channel=email or omit channel")
            self.channel = "email"
        else:
            if channel is None:
                self.channel = "whatsapp"
            elif channel not in {"whatsapp", "sms"}:
                raise ValueError("Phone access codes must use channel=whatsapp or channel=sms")
            else:
                self.channel = channel
        return self


class AccessCodeVerifyRequest(BaseModel):
    """Verify an access code (email or verified phone) and exchange it for JWT tokens."""

    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="E.164 phone used when the access code was requested by WhatsApp or SMS.",
    )
    channel: Optional[str] = Field(
        default=None,
        description="Delivery channel used when the code was requested (email|whatsapp|sms).",
    )
    code: str = Field(..., min_length=1, max_length=32)

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "AccessCodeVerifyRequest":
        self.phone = _require_exactly_one_email_or_phone(email=self.email, phone=self.phone)
        channel = (self.channel or "").strip().lower() or None
        if self.email is not None:
            if channel is not None and channel != "email":
                raise ValueError("Email access codes must use channel=email or omit channel")
            self.channel = "email"
        else:
            if channel is None:
                self.channel = "whatsapp"
            elif channel not in {"whatsapp", "sms"}:
                raise ValueError("Phone access codes must use channel=whatsapp or channel=sms")
            else:
                self.channel = channel
        return self


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
    new_password: str = Field(..., min_length=8, max_length=128)


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
