"""
User model for authentication and profile management
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from beanie import Indexed
from pydantic import EmailStr, Field, BaseModel

from outlabs_auth.models.base import BaseDocument


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"
    TERMINATED = "terminated"


class UserProfile(BaseModel):
    """User profile information"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Get user's full name"""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or "Unknown"


class UserModel(BaseDocument):
    """
    User account model for authentication and authorization.

    Supports:
    - Email/password authentication
    - JWT token authentication
    - API key authentication
    - Account status management
    - Security features (lockout, failed attempts)
    """

    # Authentication
    email: EmailStr = Indexed(unique=True)
    hashed_password: str

    # Profile
    profile: UserProfile = Field(default_factory=UserProfile)

    # Status
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    is_system_user: bool = Field(default=False)
    is_superuser: bool = Field(default=False)  # For admin override
    email_verified: bool = Field(default=False)

    # Security
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_locked(self) -> bool:
        """Check if account is locked due to failed login attempts"""
        if self.locked_until:
            # Ensure locked_until is timezone-aware
            locked_until = self.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < locked_until
        return False

    def can_authenticate(self) -> bool:
        """
        Check if user can authenticate.

        Returns True if:
        - Status is ACTIVE or SUSPENDED (suspended may have time restrictions)
        - Account is not locked
        """
        return (
            self.status in [UserStatus.ACTIVE, UserStatus.SUSPENDED]
            and not self.is_locked
        )

    class Settings:
        name = "users"
        indexes = [
            [("email", 1)],
            [("status", 1)],
            [("tenant_id", 1)],  # For multi-tenant filtering
        ]
