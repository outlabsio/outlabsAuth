"""
User audit event model.

Append-only audit events for high-signal user lifecycle changes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from outlabs_auth.database.base import BaseModel


class UserAuditEvent(BaseModel, table=True):
    """Append-only user-centric audit timeline event."""

    __tablename__ = "user_audit_events"
    __table_args__ = (
        Index("ix_uae_subject_occurred_at", "subject_user_id", "occurred_at"),
        Index("ix_uae_root_occurred_at", "root_entity_id", "occurred_at"),
        Index("ix_uae_entity_occurred_at", "entity_id", "occurred_at"),
        Index("ix_uae_role_occurred_at", "role_id", "occurred_at"),
        Index("ix_uae_event_category", "event_category"),
        Index("ix_uae_event_type", "event_type"),
    )

    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    event_category: str = Field(
        sa_column=Column(String(50), nullable=False),
    )
    event_type: str = Field(
        sa_column=Column(String(100), nullable=False),
    )
    event_source: str = Field(
        default="user_audit_service",
        sa_column=Column(String(100), nullable=False, default="user_audit_service"),
    )

    actor_user_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    subject_user_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    subject_email_snapshot: str = Field(
        sa_column=Column(String(255), nullable=False),
    )
    root_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    role_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    request_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
    )
    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )
    reason: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
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
