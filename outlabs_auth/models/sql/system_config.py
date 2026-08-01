"""
System Configuration Model

Key-value storage for system-level settings that can be managed via UI.
Used for things like:
- Allowed root entity types
- Default child entity types
- System-wide feature flags
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class SystemConfig(SQLModel, table=True):
    """
    System configuration key-value store.

    Values are stored as JSON-encoded strings for flexibility.
    Only superusers can modify these settings.

    Table: system_config
    """

    __tablename__ = "system_config"
    __table_args__ = (Index("ix_system_config_key", "key", unique=True),)

    # === Primary Key ===
    key: str = Field(
        sa_column=Column(String(100), primary_key=True),
        description="Configuration key (e.g., 'entity_types', 'feature_flags')",
    )

    # === Value ===
    value: str = Field(
        sa_column=Column(Text, nullable=False),
        description="JSON-encoded value",
    )

    # === Metadata ===
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
        description="Human-readable description of this setting",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        ),
    )

    updated_by_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="User who last updated this setting",
    )


# === Configuration Keys (Constants) ===
class ConfigKeys:
    """Well-known configuration keys."""

    # Entity type configuration
    ENTITY_TYPES = "entity_types"

    # Feature flags (for future use)
    FEATURE_FLAGS = "feature_flags"


# === Default Values ===
DEFAULT_STRUCTURAL_ROOT_TYPES = ["organization"]
DEFAULT_ACCESS_GROUP_ROOT_TYPES = [
    "permission_group",
    "admin_group",
    "team",
    "department",
    "project",
    "agent_workspace",
]

DEFAULT_ENTITY_TYPE_CONFIG = {
    "allowed_root_types": {
        "structural": list(DEFAULT_STRUCTURAL_ROOT_TYPES),
        "access_group": list(DEFAULT_ACCESS_GROUP_ROOT_TYPES),
    },
    "default_child_types": {
        "structural": ["department", "team", "branch"],
        "access_group": ["permission_group", "admin_group"],
    },
}
