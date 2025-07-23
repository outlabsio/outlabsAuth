"""
User Model
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from beanie import Indexed
from pydantic import EmailStr, Field
from api.models.base_model import BaseDocument


class UserProfile(BaseDocument):
    """User profile information"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or "Unknown"


class UserModel(BaseDocument):
    """
    User account model
    """
    # Authentication
    email: EmailStr = Indexed(unique=True)
    hashed_password: str
    
    # Profile
    profile: UserProfile = Field(default_factory=UserProfile)
    
    # Status
    is_active: bool = Field(default=True)
    is_system_user: bool = Field(default=False)
    email_verified: bool = Field(default=False)
    
    # Security
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def is_locked(self) -> bool:
        """Check if account is locked"""
        if self.locked_until:
            # Ensure locked_until is timezone-aware
            locked_until = self.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < locked_until
        return False
    
    def can_authenticate(self) -> bool:
        """Check if user can authenticate"""
        return self.is_active and not self.is_locked()
    
    class Settings:
        name = "users"
        indexes = [
            [("email", 1)],
            [("is_active", 1)],
        ]