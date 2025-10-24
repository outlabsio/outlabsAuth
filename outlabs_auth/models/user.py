"""
User model for authentication and profile management
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
from beanie import Indexed
from pydantic import EmailStr, Field, BaseModel

from outlabs_auth.models.base import BaseDocument


class UserStatus(str, Enum):
    """
    User account status controlling authentication access.

    - ACTIVE: Normal user, can authenticate
    - SUSPENDED: Temporarily blocked, cannot authenticate
    - BANNED: Permanently blocked, cannot authenticate
    - DELETED: Soft-deleted account, cannot authenticate

    See docs-library/48-User-Status-System.md for detailed semantics.
    """
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DELETED = "deleted"


class UserModel(BaseDocument):
    """
    User account model for authentication and authorization.

    Supports:
    - Email/password authentication
    - OAuth/social login (Google, Facebook, Apple, etc.)
    - JWT token authentication
    - API key authentication
    - Account status management
    - Security features (lockout, failed attempts)
    """

    # Authentication
    email: EmailStr = Indexed(unique=True)
    hashed_password: Optional[str] = None  # Optional for OAuth-only users
    auth_methods: List[str] = Field(
        default_factory=lambda: ["PASSWORD"],
        description="Authentication methods available (PASSWORD, GOOGLE, FACEBOOK, etc.)"
    )

    # Basic Identity (optional - use Beanie Links for extended profiles)
    first_name: Optional[str] = Field(
        default=None,
        description="User's first name (optional, commonly used for display)"
    )
    last_name: Optional[str] = Field(
        default=None,
        description="User's last name (optional, commonly used for display)"
    )

    # Status
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    is_superuser: bool = Field(default=False)  # For admin override
    email_verified: bool = Field(default=False)

    # Status-related timestamps
    suspended_until: Optional[datetime] = Field(
        default=None,
        description="Optional auto-expiry for SUSPENDED status"
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        description="Soft delete timestamp for DELETED status"
    )

    # Security & Activity Tracking
    last_login: Optional[datetime] = Field(
        default=None,
        description="Last successful login timestamp (only on email/password or OAuth login)"
    )
    last_activity: Optional[datetime] = Field(
        default=None,
        description="Last authenticated action timestamp (any authenticated request, updated via background sync)"
    )
    last_password_change: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """
        Get user's full name.

        Returns first_name + last_name if available, otherwise email username.
        """
        if self.first_name or self.last_name:
            parts = [p for p in [self.first_name, self.last_name] if p]
            return " ".join(parts)
        # Fallback to email username
        return self.email.split("@")[0]

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

        Returns True only if:
        - Status is ACTIVE (not suspended/banned/deleted)
        - Account is not locked (from failed login attempts)

        Note: Email verification is checked separately if required by application.

        See docs-library/48-User-Status-System.md for status semantics.
        """
        return (
            self.status == UserStatus.ACTIVE
            and not self.is_locked
        )

    class Settings:
        name = "users"
        indexes = [
            [("email", 1)],
            [("status", 1)],
            [("tenant_id", 1)],  # For multi-tenant filtering
        ]
