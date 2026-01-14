"""
OAuth/Social login Pydantic schemas (v1.2).

Request/response schemas for OAuth authentication endpoints.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OAuthAuthorizeResponse(BaseModel):
    """
    Response from GET /auth/{provider}/authorize endpoint.

    Contains the authorization URL where the user should be redirected
    to complete the OAuth flow with the provider (Google, Facebook, etc.).

    Example:
        ```python
        {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=..."
        }
        ```
    """

    authorization_url: str = Field(
        description="OAuth provider authorization URL (redirect user here)"
    )


class OAuthCallbackError(BaseModel):
    """
    Error response for OAuth callback failures.

    Used when OAuth flow fails (invalid state, user inactive, etc.).
    """

    detail: str = Field(description="Error message")
    error_code: Optional[str] = Field(
        default=None, description="Machine-readable error code"
    )


class SocialAccountResponse(BaseModel):
    """
    Response schema for social account information.

    Returns basic info about a linked OAuth account (without sensitive tokens).
    """

    provider: str = Field(description="OAuth provider name (google, facebook, etc.)")
    provider_user_id: str = Field(description="User ID from the OAuth provider")
    email: str = Field(description="Email address from provider")
    email_verified: bool = Field(description="Whether the provider verified this email")
    display_name: Optional[str] = Field(
        default=None, description="Display name from provider"
    )
    avatar_url: Optional[str] = Field(
        default=None, description="Profile picture URL from provider"
    )
    linked_at: str = Field(description="When this account was linked (ISO 8601)")
    last_used_at: Optional[str] = Field(
        default=None, description="Last time this account was used for login (ISO 8601)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "google",
                "provider_user_id": "1234567890",
                "email": "user@example.com",
                "email_verified": True,
                "display_name": "John Doe",
                "avatar_url": "https://lh3.googleusercontent.com/...",
                "linked_at": "2025-01-15T10:30:00Z",
                "last_used_at": "2025-01-20T14:22:00Z",
            }
        }
    )
