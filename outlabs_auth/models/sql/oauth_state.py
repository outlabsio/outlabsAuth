"""
OAuthState Model

Temporary state storage for OAuth flows.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Index, ForeignKey, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel


class OAuthState(BaseModel, table=True):
    """
    Temporary OAuth state for CSRF protection.

    Stores the state parameter during OAuth flow to prevent CSRF attacks.
    These records are short-lived and should be cleaned up after use or expiry.

    Table: oauth_states
    """
    __tablename__ = "oauth_states"
    __table_args__ = (
        Index("ix_oauth_states_state", "state"),
        Index("ix_oauth_states_expires_at", "expires_at"),
        Index("ix_oauth_states_tenant_id", "tenant_id"),
    )

    # === State Parameter ===
    state: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True),
        description="Random state parameter for CSRF protection",
    )

    # === Provider ===
    provider: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="OAuth provider (google, github, etc.)",
    )

    # === Optional User (for account linking) ===
    user_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        description="User ID if linking account to existing user",
    )

    # === Flow Metadata ===
    redirect_uri: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2000), nullable=True),
        description="Where to redirect after OAuth completes",
    )
    code_verifier: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="PKCE code verifier",
    )
    nonce: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="OpenID Connect nonce",
    )

    # === Expiration ===
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="State expires after 10 minutes",
    )

    # === Usage ===
    used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the state was consumed",
    )

    # === Methods ===
    def is_expired(self) -> bool:
        """Check if this state has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def is_used(self) -> bool:
        """Check if this state has already been used."""
        return self.used_at is not None

    def is_valid(self) -> bool:
        """Check if this state is valid (not expired and not used)."""
        return not self.is_expired() and not self.is_used()

    def mark_used(self) -> None:
        """Mark this state as used."""
        self.used_at = datetime.now(timezone.utc)
