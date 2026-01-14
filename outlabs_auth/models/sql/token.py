"""
RefreshToken Model

JWT refresh token storage with device tracking and revocation support.
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, Index, UniqueConstraint, ForeignKey, String, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel

if TYPE_CHECKING:
    from .user import User


class RefreshToken(BaseModel, table=True):
    """
    Refresh token model for JWT token rotation.

    Stores hashed refresh tokens with device fingerprinting
    for session management and security auditing.

    Table: refresh_tokens
    """
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
        Index("ix_refresh_tokens_is_revoked", "is_revoked"),
        Index("ix_refresh_tokens_device", "device_fingerprint"),
    )

    # === Foreign Key ===
    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="User who owns this refresh token",
    )

    # === Token ===
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True),
        description="SHA-256 hash of the refresh token (never store plain token)",
    )

    # === Expiration ===
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Token expiration timestamp",
    )

    # === Revocation ===
    is_revoked: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    revoked_reason: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Reason for revocation (logout, security, password_change)",
    )

    # === Device/Session Info ===
    device_name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
        description="User-friendly device name (e.g., 'iPhone 14 Pro')",
    )
    device_fingerprint: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Hashed device identifier for session binding",
    )
    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(String(45), nullable=True),  # IPv6 max length
        description="IP address at token creation",
    )
    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
        description="Browser/client user agent string",
    )

    # === Usage Tracking ===
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last time this token was used for refresh",
    )
    usage_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Number of times token has been used",
    )

    # === Relationship ===
    user: "User" = Relationship(back_populates="refresh_tokens")

    # === Methods ===
    def is_valid(self) -> bool:
        """Check if token is valid (not revoked and not expired)."""
        if self.is_revoked:
            return False
        return datetime.now(timezone.utc) <= self.expires_at

    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def revoke(self, reason: str = "manual") -> None:
        """Mark token as revoked."""
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_reason = reason

    def record_usage(self) -> None:
        """Record token usage."""
        self.last_used_at = datetime.now(timezone.utc)
        self.usage_count += 1
