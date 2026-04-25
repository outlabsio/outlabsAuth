"""Temporary authentication challenge storage."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship

from outlabs_auth.database.base import BaseModel

from .enums import AuthChallengeType

if TYPE_CHECKING:
    from .user import User


class AuthChallenge(BaseModel, table=True):
    """
    Single-use temporary auth challenge.

    The plain token is only returned to the host integration. The database keeps
    a SHA-256 hash so a leaked database snapshot cannot be used as a login link.
    """

    __tablename__ = "auth_challenges"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_challenges_token_hash"),
        Index("ix_auth_challenges_user_id", "user_id"),
        Index("ix_auth_challenges_type_expires_at", "challenge_type", "expires_at"),
        Index("ix_auth_challenges_used_at", "used_at"),
    )

    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="User this challenge authenticates.",
    )
    challenge_type: AuthChallengeType = Field(
        default=AuthChallengeType.MAGIC_LINK,
        sa_column=Column(String(50), nullable=False),
        description="Challenge kind, e.g. magic_link.",
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False),
        description="SHA-256 hash of the one-time challenge token.",
    )
    recipient: str = Field(
        sa_column=Column(String(255), nullable=False),
        description="Email or destination the challenge was requested for.",
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When this challenge expires.",
    )
    used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When this challenge was consumed.",
    )
    redirect_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2048), nullable=True),
        description="Optional host-owned post-login redirect hint.",
    )
    requested_ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(String(45), nullable=True),
    )
    requested_user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )

    user: "User" = Relationship()
