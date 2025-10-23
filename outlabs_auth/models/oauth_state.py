"""OAuth state model for CSRF protection and PKCE flow."""

from datetime import datetime, timedelta
from typing import Optional
from beanie import Document
from pydantic import Field, ConfigDict
from bson import ObjectId


class OAuthState(Document):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    """
    Temporary state for OAuth flow validation.
    
    Stores state parameter (CSRF protection), PKCE verifier, and nonce for
    OpenID Connect flows. Expires after 10 minutes.
    """
    
    # CSRF protection
    state: str = Field(
        description="Random state parameter for CSRF protection"
    )
    provider: str = Field(
        description="OAuth provider name (google, facebook, etc.)"
    )
    
    # PKCE (Proof Key for Code Exchange)
    code_verifier: Optional[str] = Field(
        default=None,
        description="PKCE code verifier (kept secret)"
    )
    code_challenge: Optional[str] = Field(
        default=None,
        description="PKCE code challenge (sent to provider)"
    )
    code_challenge_method: str = Field(
        default="S256",
        description="PKCE challenge method (S256 or plain)"
    )
    
    # OpenID Connect
    nonce: Optional[str] = Field(
        default=None,
        description="Nonce for OpenID Connect ID token validation"
    )
    
    # Context
    redirect_uri: str = Field(
        description="Where to redirect after OAuth callback"
    )
    original_url: Optional[str] = Field(
        default=None,
        description="Original URL before OAuth flow (for deep linking)"
    )
    user_id: Optional[ObjectId] = Field(
        default=None,
        description="User ID if linking to existing user (not new registration)"
    )
    
    # Expiration
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(minutes=10),
        description="State expires after 10 minutes"
    )
    
    # Metadata (for security auditing)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this state was created"
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="IP address that initiated OAuth flow"
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="User agent that initiated OAuth flow"
    )
    
    class Settings:
        name = "oauth_states"
        indexes = [
            "state",  # Lookup by state parameter
            "expires_at",  # Cleanup expired states
            [("provider", 1), ("user_id", 1)],  # Find pending flows for user
        ]
    
    def is_expired(self) -> bool:
        """Check if this state has expired."""
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self) -> str:
        return (
            f"OAuthState(provider={self.provider}, "
            f"state={self.state[:10]}..., "
            f"expires_at={self.expires_at})"
        )
