"""Social account model for OAuth/social login integration."""

from datetime import datetime
from typing import Optional, Dict, Any
from beanie import Document
from pydantic import Field, ConfigDict
from bson import ObjectId


class SocialAccount(Document):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    """
    Links a user to an OAuth provider account.
    
    Used for social login (Google, Facebook, Apple, etc.) and allows users
    to have multiple authentication methods linked to their account.
    """
    
    # Relationships
    user_id: ObjectId = Field(description="Reference to UserModel")
    
    # Provider information
    provider: str = Field(
        description="OAuth provider name (google, facebook, apple, github, etc.)"
    )
    provider_user_id: str = Field(
        description="User ID from the OAuth provider"
    )
    
    # User data from provider (cached for convenience)
    email: str = Field(description="Email address from provider")
    email_verified: bool = Field(
        default=False,
        description="Whether the provider verified this email"
    )
    display_name: Optional[str] = Field(
        default=None,
        description="Display name from provider"
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="Profile picture URL from provider"
    )
    
    # OAuth tokens (encrypted at rest - encryption handled by application layer)
    access_token: Optional[str] = Field(
        default=None,
        description="OAuth access token (encrypted)"
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description="OAuth refresh token (encrypted)"
    )
    token_expires_at: Optional[datetime] = Field(
        default=None,
        description="When the access token expires"
    )
    
    # Provider-specific data (full profile from provider)
    provider_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional data from provider (profile, permissions, etc.)"
    )
    
    # Metadata
    linked_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this account was linked"
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        description="Last time this social account was used for login"
    )
    
    class Settings:
        name = "social_accounts"
        indexes = [
            "user_id",  # Find all accounts for a user
            [("provider", 1), ("provider_user_id", 1)],  # Unique per provider
            [("provider", 1), ("email", 1)],  # Find by provider + email
        ]
    
    def __repr__(self) -> str:
        return (
            f"SocialAccount(provider={self.provider}, "
            f"email={self.email}, user_id={self.user_id})"
        )
