"""
Entity membership history model.

Append-only audit events for entity membership lifecycle changes.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from outlabs_auth.database.base import BaseModel


class EntityMembershipHistory(BaseModel, table=True):
    """
    Append-only history for entity membership lifecycle events.

    Each row captures the post-change membership snapshot plus immediate
    pre-change comparison fields where relevant.
    """

    __tablename__ = "entity_membership_history"
    __table_args__ = (
        Index("ix_emh_membership_event_at", "membership_id", "event_at"),
        Index("ix_emh_user_event_at", "user_id", "event_at"),
        Index("ix_emh_entity_event_at", "entity_id", "event_at"),
        Index("ix_emh_root_entity_event_at", "root_entity_id", "event_at"),
        Index("ix_emh_event_type", "event_type"),
    )

    membership_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entity_memberships.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    entity_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    root_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa_column=Column(String(50), nullable=False),
    )
    event_source: str = Field(
        default="membership_service",
        sa_column=Column(String(100), nullable=False, default="membership_service"),
    )
    event_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    reason: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )

    status: str = Field(
        sa_column=Column(String(20), nullable=False),
    )
    previous_status: Optional[str] = Field(
        default=None,
        sa_column=Column(String(20), nullable=True),
    )

    valid_from: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    previous_valid_from: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    previous_valid_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    role_ids: List[UUID] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(PG_UUID(as_uuid=True)), nullable=False),
    )
    previous_role_ids: List[UUID] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(PG_UUID(as_uuid=True)), nullable=False),
    )
    role_names: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String(255)), nullable=False),
    )
    previous_role_names: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String(255)), nullable=False),
    )

    entity_display_name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    entity_path: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String(255)), nullable=False),
    )
    root_entity_name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
