"""
Domain Models for Real Estate Leads Platform - EnterpriseRBAC Example

Uses SQLModel for PostgreSQL integration.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Index, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID, TIMESTAMP
from sqlmodel import Field, SQLModel


class Lead(SQLModel, table=True):
    """
    A potential buyer or seller in the real estate pipeline.

    Leads are owned by ACCESS_GROUP entities (teams, agent workspaces).
    Tree permissions allow managers/brokers to see descendant leads.
    """

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_entity_id", "entity_id"),
        Index("ix_leads_assigned_to", "assigned_to"),
        Index("ix_leads_status", "status"),
        Index("ix_leads_lead_type", "lead_type"),
        Index("ix_leads_source", "source"),
        Index("ix_leads_entity_status", "entity_id", "status"),
        Index("ix_leads_assigned_status", "assigned_to", "status"),
        Index("ix_leads_created_at", "created_at"),
        Index("ix_leads_next_followup", "next_followup"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_type=PG_UUID(as_uuid=True),
        primary_key=True,
    )

    # Ownership & Assignment
    entity_id: UUID = Field(
        sa_type=PG_UUID(as_uuid=True),
        description="Which entity (team/workspace) owns this lead",
    )
    assigned_to: Optional[UUID] = Field(
        default=None,
        sa_type=PG_UUID(as_uuid=True),
        description="Agent user_id (optional)",
    )

    # Lead Classification
    lead_type: str = Field(
        max_length=20,
        description="buyer, seller, or both",
    )

    # Contact Information
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: str = Field(max_length=255)
    phone: str = Field(max_length=50)

    # Lead Status Pipeline
    status: str = Field(
        default="new",
        max_length=20,
        description="new, contacted, qualified, showing, offer, closed, dead",
    )

    # Lead Source & Details
    source: str = Field(
        max_length=100,
        description="Website, referral, Zillow, realtor.com, etc.",
    )
    budget: Optional[int] = Field(default=None, description="Budget range (for buyers)")
    location: Optional[str] = Field(default=None, max_length=255, description="Desired location/area")
    property_type: Optional[str] = Field(
        default=None, max_length=50, description="House, condo, townhouse, land, etc."
    )
    bedrooms: Optional[int] = Field(default=None, description="Desired bedrooms (for buyers)")
    bathrooms: Optional[float] = Field(default=None, description="Desired bathrooms (for buyers)")
    timeline: Optional[str] = Field(
        default=None,
        max_length=50,
        description="immediate, 1-3 months, 3-6 months, 6-12 months",
    )

    # Seller-specific fields (if lead_type is "seller")
    property_address: Optional[str] = Field(default=None, max_length=500)
    asking_price: Optional[int] = Field(default=None)
    property_condition: Optional[str] = Field(
        default=None, max_length=50, description="excellent, good, needs_work"
    )

    # Interaction History
    notes: List[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text)))
    last_contact: Optional[datetime] = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
    )
    next_followup: Optional[datetime] = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    created_by: UUID = Field(
        sa_type=PG_UUID(as_uuid=True),
        description="User ID who created (agent or internal support)",
    )

    def __repr__(self) -> str:
        return f"<Lead({self.first_name} {self.last_name} - {self.lead_type} - {self.status})>"

    def full_name(self) -> str:
        """Get lead's full name"""
        return f"{self.first_name} {self.last_name}"

    def is_buyer(self) -> bool:
        """Check if lead is a buyer"""
        return self.lead_type in ["buyer", "both"]

    def is_seller(self) -> bool:
        """Check if lead is a seller"""
        return self.lead_type in ["seller", "both"]

    def is_active(self) -> bool:
        """Check if lead is still active (not closed or dead)"""
        return self.status not in ["closed", "dead"]

    def add_note(self, note: str, author_id: str) -> None:
        """Add a note to the lead"""
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.notes is None:
            self.notes = []
        self.notes.append(f"[{timestamp}] (by {author_id}): {note}")
        self.updated_at = datetime.now(timezone.utc)


class LeadNote(SQLModel, table=True):
    """
    Separate table for lead notes (alternative to embedded notes).

    This allows for better querying and filtering of notes.
    """

    __tablename__ = "lead_notes"
    __table_args__ = (
        Index("ix_lead_notes_lead_id", "lead_id"),
        Index("ix_lead_notes_author_id", "author_id"),
        Index("ix_lead_notes_lead_created", "lead_id", "created_at"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_type=PG_UUID(as_uuid=True),
        primary_key=True,
    )
    lead_id: UUID = Field(sa_type=PG_UUID(as_uuid=True))
    author_id: UUID = Field(sa_type=PG_UUID(as_uuid=True))
    author_name: str = Field(max_length=200)
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    note_type: str = Field(
        default="general",
        max_length=20,
        description="general, call, email, showing, offer",
    )
