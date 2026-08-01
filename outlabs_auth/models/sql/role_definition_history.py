"""
Role definition history model.

Append-only history for role definition and permission-set changes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from outlabs_auth.models.sql.enums import DefinitionStatus

from outlabs_auth.database.base import BaseModel


class RoleDefinitionHistory(BaseModel, table=True):
    """Append-only role definition history row."""

    __tablename__ = "role_definition_history"
    __table_args__ = (
        Index("ix_rdh_role_occurred_at", "role_id", "occurred_at"),
        Index("ix_rdh_actor_occurred_at", "actor_user_id", "occurred_at"),
        Index("ix_rdh_root_occurred_at", "root_entity_id", "occurred_at"),
        Index("ix_rdh_scope_occurred_at", "scope_entity_id", "occurred_at"),
        Index("ix_rdh_event_type", "event_type"),
    )

    role_id: UUID = Field(
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
    root_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    scope_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    event_type: str = Field(
        sa_column=Column(String(60), nullable=False),
    )
    event_source: str = Field(
        default="role_history_service",
        sa_column=Column(String(100), nullable=False, default="role_history_service"),
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    role_name_snapshot: str = Field(
        sa_column=Column(String(100), nullable=False),
    )
    role_display_name_snapshot: str = Field(
        sa_column=Column(String(200), nullable=False),
    )
    role_description_snapshot: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
    )
    root_entity_name_snapshot: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    scope_entity_name_snapshot: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    is_system_role_snapshot: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    is_global_snapshot: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    scope_snapshot: str = Field(
        sa_column=Column(String(20), nullable=False),
    )
    status_snapshot: DefinitionStatus = Field(
        default=DefinitionStatus.ACTIVE,
        sa_column=Column(String(20), nullable=False, default=DefinitionStatus.ACTIVE.value),
    )
    is_auto_assigned_snapshot: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )

    assignable_at_types_snapshot: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String(50)), nullable=False),
    )
    permission_ids_snapshot: List[UUID] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(PG_UUID(as_uuid=True)), nullable=False),
    )
    permission_names_snapshot: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String(255)), nullable=False),
    )
    entity_type_permissions_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
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
