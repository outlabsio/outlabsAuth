"""
User Model

Core user authentication and profile model - properly normalized.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship

from outlabs_auth.database.base import BaseModel

from .enums import UserStatus

if TYPE_CHECKING:
    from .api_key import APIKey
    from .entity import Entity
    from .social_account import SocialAccount
    from .token import RefreshToken
    from .user_role_membership import UserRoleMembership


class User(BaseModel, table=True):
    """
    User model for authentication and profile management.

    Supports multiple authentication methods (password, OAuth, API keys)
    and comprehensive security features (lockout, suspension, soft delete).

    Note: For custom application data, extend this model or create a
    separate UserProfile table with a 1:1 relationship.

    Table: users
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "tenant_id", name="uq_users_email_tenant"),
        Index("ix_users_email", "email"),
        Index("ix_users_status", "status"),
        Index("ix_users_tenant_id", "tenant_id"),
        Index("ix_users_root_entity_id", "root_entity_id"),
    )

    # === Organization Binding (EnterpriseRBAC) ===
    root_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="Root entity (organization) this user belongs to. NULL for superusers or unassigned users.",
    )

    # === Authentication ===
    email: str = Field(
        sa_column=Column(String(255), nullable=False),
        description="User email address (unique per tenant)",
    )
    hashed_password: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Password hash (Argon2id preferred; legacy bcrypt supported, null for OAuth-only users)",
    )
    auth_methods: List[str] = Field(
        default=["PASSWORD"],
        sa_column=Column(
            ARRAY(String(50)),
            nullable=False,
            server_default="{PASSWORD}",
        ),
        description="Enabled auth methods: PASSWORD, GOOGLE, FACEBOOK, APPLE, GITHUB",
    )

    # === Profile ===
    first_name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
    )
    last_name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
    )
    avatar_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )
    phone: Optional[str] = Field(
        default=None,
        sa_column=Column(String(20), nullable=True),
    )
    locale: Optional[str] = Field(
        default=None,
        sa_column=Column(String(10), nullable=True),
        description="User's preferred locale (e.g., 'en-US')",
    )
    timezone: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
        description="User's timezone (e.g., 'America/New_York')",
    )

    # === Status ===
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        sa_column=Column(String(20), nullable=False, default="active"),
    )
    is_superuser: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    email_verified: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    phone_verified: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )

    # === Status Timestamps ===
    suspended_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # === Security & Activity ===
    last_login: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_activity: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_password_change: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    failed_login_attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
    )
    locked_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # === Password Reset ===
    password_reset_token: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    password_reset_expires: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # === Email Verification ===
    email_verification_token: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    email_verification_expires: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # === Relationships ===
    refresh_tokens: List["RefreshToken"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    api_keys: List["APIKey"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    role_memberships: List["UserRoleMembership"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[UserRoleMembership.user_id]",
        },
    )
    social_accounts: List["SocialAccount"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    root_entity: Optional["Entity"] = Relationship(
        back_populates="users",
        sa_relationship_kwargs={"foreign_keys": "[User.root_entity_id]"},
    )

    # === Properties ===
    @property
    def full_name(self) -> str:
        """Get user's full name or email prefix."""
        parts = [p for p in [self.first_name, self.last_name] if p]
        if parts:
            return " ".join(parts)
        return self.email.split("@")[0]

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until:
            return datetime.now(timezone.utc) < self.locked_until
        return False

    def can_authenticate(self) -> bool:
        """Check if user can authenticate."""
        if self.status != UserStatus.ACTIVE:
            return False
        return not self.is_locked

    def has_auth_method(self, method: str) -> bool:
        """Check if user has a specific auth method enabled."""
        return method.upper() in [m.upper() for m in self.auth_methods]
