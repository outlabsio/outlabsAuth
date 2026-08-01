"""
Permission definition history model.

Append-only history for permission definition changes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from outlabs_auth.database.base import BaseModel
from outlabs_auth.models.sql.enums import DefinitionStatus


class PermissionDefinitionHistory(BaseModel, table=True):
    """Append-only permission definition history row."""

    __tablename__ = "permission_definition_history"
    __table_args__ = (
        Index("ix_pdh_permission_occurred_at", "permission_id", "occurred_at"),
        Index("ix_pdh_actor_occurred_at", "actor_user_id", "occurred_at"),
        Index("ix_pdh_event_type", "event_type"),
    )

    permission_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), nullable=False),
    )
    actor_user_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    event_type: str = Field(
        sa_column=Column(String(60), nullable=False),
    )
    event_source: str = Field(
        default="permission_history_service",
        sa_column=Column(
            String(100),
            nullable=False,
            default="permission_history_service",
        ),
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    permission_name_snapshot: str = Field(
        sa_column=Column(String(100), nullable=False),
    )
    permission_display_name_snapshot: str = Field(
        sa_column=Column(String(200), nullable=False),
    )
    permission_description_snapshot: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
    )
    resource_snapshot: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
    )
    action_snapshot: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
    )
    scope_snapshot: Optional[str] = Field(
        default=None,
        sa_column=Column(String(20), nullable=True),
    )
    is_system_snapshot: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    status_snapshot: DefinitionStatus = Field(
        default=DefinitionStatus.ACTIVE,
        sa_column=Column(String(20), nullable=False, default=DefinitionStatus.ACTIVE.value),
    )
    is_active_snapshot: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True),
    )
    tag_names_snapshot: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String(50)), nullable=False),
    )

    before: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    after: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    event_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column("metadata", JSONB, nullable=True),
    )
