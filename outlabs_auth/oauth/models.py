"""Data models for OAuth provider responses."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class OAuthTokenResponse(BaseModel):
    """
    OAuth token response from provider.
    
    Standard OAuth 2.0 token response with optional OpenID Connect id_token.
    """
    
    access_token: str = Field(description="OAuth access token")
    token_type: str = Field(
        default="Bearer",
        description="Token type (usually 'Bearer')"
    )
    expires_in: Optional[int] = Field(
        default=None,
        description="Token lifetime in seconds"
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description="OAuth refresh token (if available)"
    )
    scope: Optional[str] = Field(
        default=None,
        description="Granted scopes (space-separated)"
    )
    
    # OpenID Connect
    id_token: Optional[str] = Field(
        default=None,
        description="OpenID Connect ID token (JWT)"
    )
    
    # Provider-specific extras
    extras: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific additional fields"
    )


class OAuthUserInfo(BaseModel):
    """
    Standardized user info from OAuth provider.
    
    Maps provider-specific user info to a common format.
    """
    
    # Required fields
    provider_user_id: str = Field(
        description="Unique user ID from provider"
    )
    email: str = Field(
        description="User's email address"
    )
    email_verified: bool = Field(
        default=False,
        description="Whether provider verified this email"
    )
    
    # Optional profile fields
    name: Optional[str] = Field(
        default=None,
        description="User's full name"
    )
    given_name: Optional[str] = Field(
        default=None,
        description="User's first/given name"
    )
    family_name: Optional[str] = Field(
        default=None,
        description="User's last/family name"
    )
    picture: Optional[str] = Field(
        default=None,
        description="URL to user's profile picture"
    )
    locale: Optional[str] = Field(
        default=None,
        description="User's locale/language preference"
    )
    
    # Provider-specific data
    provider_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Original provider response for reference"
    )


class OAuthAuthorizationURL(BaseModel):
    """
    OAuth authorization URL with state.
    
    Returned when initiating OAuth flow.
    """
    
    url: str = Field(
        description="Full authorization URL to redirect user to"
    )
    state: str = Field(
        description="State parameter for CSRF protection"
    )
    code_verifier: Optional[str] = Field(
        default=None,
        description="PKCE code verifier (keep secret)"
    )
    code_challenge: Optional[str] = Field(
        default=None,
        description="PKCE code challenge (sent to provider)"
    )
    nonce: Optional[str] = Field(
        default=None,
        description="Nonce for OpenID Connect (keep secret)"
    )


class OAuthCallbackResult(BaseModel):
    """
    Result of handling OAuth callback.
    
    Contains user, tokens, and whether account was created or linked.
    """
    
    user_id: str = Field(
        description="User ID (new or existing)"
    )
    is_new_user: bool = Field(
        description="Whether a new user was created"
    )
    social_account_id: str = Field(
        description="ID of the SocialAccount record"
    )
    access_token: str = Field(
        description="JWT access token for our system"
    )
    refresh_token: str = Field(
        description="JWT refresh token for our system"
    )
    linked_account: bool = Field(
        default=False,
        description="Whether account was linked to existing user"
    )
