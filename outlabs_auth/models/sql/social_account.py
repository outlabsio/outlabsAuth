"""
SocialAccount Model

OAuth/social login provider connections for users.
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Boolean, Column, Index, UniqueConstraint, ForeignKey, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel

if TYPE_CHECKING:
    from .user import User


class SocialAccount(BaseModel, table=True):
    """
    OAuth/social login account linked to a user.

    Stores the connection between a user and their social provider account.
    Each user can have multiple social accounts from different providers.

    Table: social_accounts
    """

    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_social_provider_user"),
        Index("ix_social_accounts_user_id", "user_id"),
        Index("ix_social_accounts_provider", "provider"),
    )

    # === User Link ===
    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # === Provider Information ===
    provider: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="OAuth provider name (google, github, microsoft, etc.)",
    )
    provider_user_id: str = Field(
        sa_column=Column(String(255), nullable=False),
        description="User ID from the provider",
    )
    provider_email: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Email from the provider (may differ from user's primary email)",
    )
    provider_email_verified: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="Whether the provider verified this email address",
    )
    provider_username: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Username from the provider",
    )

    # === Tokens ===
    access_token: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="OAuth access token (encrypted)",
    )
    refresh_token: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="OAuth refresh token (encrypted)",
    )
    token_expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the access token expires",
    )

    # === Profile Data (Normalized) ===
    display_name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    avatar_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2000), nullable=True),
    )
    profile_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2000), nullable=True),
    )

    # === Timestamps ===
    last_login_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    token_refreshed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # === Relationships ===
    user: "User" = Relationship(back_populates="social_accounts")

    # === Methods ===
    def is_token_expired(self) -> bool:
        """Check if the access token is expired."""
        if not self.token_expires_at:
            return False
        return datetime.now(timezone.utc) > self.token_expires_at

    def update_tokens(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> None:
        """Update OAuth tokens."""
        if access_token is not None:
            self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token
        if expires_at is not None:
            self.token_expires_at = expires_at
        self.token_refreshed_at = datetime.now(timezone.utc)

    def record_login(self) -> None:
        """Record a login via this social account."""
        self.last_login_at = datetime.now(timezone.utc)
