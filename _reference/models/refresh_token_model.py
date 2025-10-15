"""
Refresh Token Model
"""
from datetime import datetime, timezone
from typing import Optional
from beanie import Link, Indexed
from pydantic import Field
from api.models.base_model import BaseDocument
from api.models.user_model import UserModel


class RefreshTokenModel(BaseDocument):
    """
    Refresh token for token rotation
    """
    token: str = Indexed(unique=True)
    user: Link[UserModel]
    
    # Token family for rotation tracking
    family_id: str = Indexed()
    
    # Device/session info
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    
    # Validity
    expires_at: datetime
    used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    
    # Security
    is_active: bool = Field(default=True)
    
    def is_valid(self) -> bool:
        """Check if token is valid"""
        now = datetime.now(timezone.utc)
        
        # Ensure expires_at is timezone-aware for comparison
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        return (
            self.is_active and
            not self.used_at and
            not self.revoked_at and
            now < expires_at
        )
    
    class Settings:
        name = "refresh_tokens"
        indexes = [
            [("token", 1)],
            [("user", 1)],
            [("family_id", 1)],
            [("expires_at", 1)],
        ]