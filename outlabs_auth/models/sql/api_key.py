"""
APIKey Model

API key authentication with scoping and rate limiting.
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel
from .enums import APIKeyKind, APIKeyStatus

if TYPE_CHECKING:
    from .integration_principal import IntegrationPrincipal
    from .user import User


# === API Key Scopes (Junction Table) ===
class APIKeyScope(SQLModel, table=True):
    """
    Scopes (permissions) assigned to an API key.

    Table: api_key_scopes
    """

    __tablename__ = "api_key_scopes"
    __table_args__ = (Index("ix_api_key_scopes_key_id", "api_key_id"),)

    api_key_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("api_keys.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    scope: str = Field(
        sa_column=Column(String(100), primary_key=True),
        description="Permission scope (e.g., 'user:read', 'data:*')",
    )


# === API Key IP Whitelist ===
class APIKeyIPWhitelist(SQLModel, table=True):
    """
    IP addresses allowed to use an API key.

    Table: api_key_ip_whitelist
    """

    __tablename__ = "api_key_ip_whitelist"
    __table_args__ = (Index("ix_api_key_ip_key_id", "api_key_id"),)

    api_key_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("api_keys.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    ip_address: str = Field(
        sa_column=Column(String(45), primary_key=True),  # IPv6 max length
        description="Allowed IP address or CIDR range",
    )


class APIKey(BaseModel, table=True):
    """
    API key model for programmatic access.

    Features:
    - SHA-256 hashed key storage (prefix visible for identification)
    - Scope-based permissions
    - Rate limiting
    - IP whitelisting
    - Usage tracking

    Table: api_keys
    """

    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("prefix", name="uq_api_keys_prefix"),
        Index("ix_api_keys_prefix", "prefix"),
        Index("ix_api_keys_owner_id", "owner_id"),
        Index("ix_api_keys_integration_principal_id", "integration_principal_id"),
        Index("ix_api_keys_key_kind", "key_kind"),
        # Compound index covers the hot-path authentication filter
        # (status = 'active' AND (expires_at IS NULL OR expires_at > now())).
        # Supersedes the separate single-column indexes on status and expires_at.
        Index("ix_api_keys_status_expires_at", "status", "expires_at"),
        CheckConstraint(
            "(owner_id IS NOT NULL AND integration_principal_id IS NULL) OR "
            "(owner_id IS NULL AND integration_principal_id IS NOT NULL)",
            name="ck_api_keys_exactly_one_owner",
        ),
    )

    # === Key Information ===
    name: str = Field(
        sa_column=Column(String(200), nullable=False),
        description="Human-readable name for this key",
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
    )
    prefix: str = Field(
        sa_column=Column(String(20), nullable=False, unique=True),
        description="Key prefix for identification (e.g., 'sk_live_abc123')",
    )
    key_hash: str = Field(
        sa_column=Column(String(255), nullable=False),
        description="SHA-256 hash of the full key",
    )

    # === Owner ===
    owner_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    integration_principal_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("integration_principals.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    key_kind: APIKeyKind = Field(
        default=APIKeyKind.PERSONAL,
        sa_column=Column(String(40), nullable=False, default=APIKeyKind.PERSONAL.value),
        description="Intent classification for this key",
    )

    # === Status & Lifecycle ===
    status: APIKeyStatus = Field(
        default=APIKeyStatus.ACTIVE,
        sa_column=Column(String(20), nullable=False, default="active"),
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Expiration time (null = never expires)",
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # === Usage Tracking ===
    usage_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Total number of times this key has been used",
    )

    # === Rate Limiting ===
    rate_limit_per_minute: int = Field(
        default=60,
        sa_column=Column(Integer, nullable=False, default=60),
    )
    rate_limit_per_hour: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )
    rate_limit_per_day: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )

    # === Entity Scoping (EnterpriseRBAC) ===
    entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="Scope key to specific entity",
    )
    inherit_from_tree: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="Allow access to entity descendants",
    )

    # === Relationships ===
    owner: Optional["User"] = Relationship(back_populates="api_keys")
    integration_principal: Optional["IntegrationPrincipal"] = Relationship(back_populates="api_keys")

    # === Static Methods ===
    @staticmethod
    def generate_key(prefix_type: str = "sk_live") -> tuple[str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, prefix) - store prefix, hash the full key
        """
        key_material = secrets.token_hex(32)
        full_key = f"{prefix_type}_{key_material}"
        prefix = full_key[:16]  # First 16 chars as prefix
        return full_key, prefix

    @staticmethod
    def hash_key(full_key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(full_key.encode()).hexdigest()

    # === Instance Methods ===
    def is_active(self) -> bool:
        """Check if key is active and not expired."""
        if self.status != APIKeyStatus.ACTIVE:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def verify_hash(self, full_key: str) -> bool:
        """Verify a key matches this API key's hash."""
        return self.key_hash == self.hash_key(full_key)

    def record_usage(self) -> None:
        """Record key usage."""
        self.last_used_at = datetime.now(timezone.utc)
        self.usage_count += 1

    def revoke(self) -> None:
        """Revoke this API key."""
        self.status = APIKeyStatus.REVOKED

    def suspend(self) -> None:
        """Suspend this API key."""
        self.status = APIKeyStatus.SUSPENDED

    def reactivate(self) -> None:
        """Reactivate this API key."""
        self.status = APIKeyStatus.ACTIVE

    @property
    def owner_type(self) -> str:
        """Return the concrete owner type for this key."""
        return "integration_principal" if self.integration_principal_id is not None else "user"

    @property
    def resolved_owner_id(self) -> Optional[UUID]:
        """Return the concrete owner UUID regardless of owner type."""
        return self.integration_principal_id or self.owner_id
