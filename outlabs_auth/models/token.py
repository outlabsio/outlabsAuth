"""
Token models for authentication
"""
from typing import Optional
from datetime import datetime
from beanie import Link, Indexed
from pydantic import Field

from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.user import UserModel


class RefreshTokenModel(BaseDocument):
    """
    Refresh token model for JWT authentication.

    Features:
    - Multi-device support (one refresh token per device/session)
    - Revocation support
    - Usage tracking
    - Device fingerprinting
    """

    # Associated user
    user: Link[UserModel]

    # Token value (hashed for security)
    token_hash: str = Indexed(unique=True)

    # Expiration
    expires_at: datetime

    # Revocation
    is_revoked: bool = Field(default=False)
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None

    # Device/Session information
    device_name: Optional[str] = None  # e.g., "iPhone 12", "Chrome on MacOS"
    device_fingerprint: Optional[str] = None  # Hashed device identifier
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Usage tracking
    last_used_at: Optional[datetime] = None
    usage_count: int = Field(default=0)

    def is_valid(self) -> bool:
        """Check if refresh token is valid (not expired and not revoked)"""
        if self.is_revoked:
            return False

        if datetime.utcnow() > self.expires_at:
            return False

        return True

    class Settings:
        name = "refresh_tokens"
        indexes = [
            [("token_hash", 1)],
            [("user", 1)],
            [("expires_at", 1)],
            [("is_revoked", 1)],
            [("tenant_id", 1)],  # For multi-tenant filtering
        ]
