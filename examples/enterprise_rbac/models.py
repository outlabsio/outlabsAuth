"""
Domain Models for Real Estate Leads Platform

Contains the Lead model and related domain objects.
"""
from datetime import datetime
from typing import Optional, List, Literal
from beanie import Document, Indexed
from pydantic import Field


class Lead(Document):
    """
    A potential buyer or seller in the real estate pipeline.

    Leads are owned by ACCESS_GROUP entities (teams, agent workspaces).
    Tree permissions allow managers/brokers to see descendant leads.
    """

    # Ownership & Assignment
    entity_id: str = Indexed()        # Which entity (team/workspace) owns this lead
    assigned_to: Optional[str] = None  # Agent user_id (optional)

    # Lead Classification
    lead_type: Literal["buyer", "seller", "both"] = Indexed()

    # Contact Information
    first_name: str
    last_name: str
    email: str
    phone: str

    # Lead Status Pipeline
    status: Literal["new", "contacted", "qualified", "showing", "offer", "closed", "dead"] = Indexed()

    # Lead Source & Details
    source: str = Indexed()           # Website, referral, Zillow, realtor.com, etc.
    budget: Optional[int] = None       # Budget range (for buyers)
    location: Optional[str] = None     # Desired location/area
    property_type: Optional[str] = None  # House, condo, townhouse, land, etc.
    bedrooms: Optional[int] = None     # Desired bedrooms (for buyers)
    bathrooms: Optional[float] = None  # Desired bathrooms (for buyers)
    timeline: Optional[str] = None     # immediate, 1-3 months, 3-6 months, 6-12 months

    # Seller-specific fields (if lead_type is "seller")
    property_address: Optional[str] = None
    asking_price: Optional[int] = None
    property_condition: Optional[str] = None  # excellent, good, needs_work

    # Interaction History
    notes: List[str] = Field(default_factory=list)
    last_contact: Optional[datetime] = None
    next_followup: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str               # User ID who created (agent or internal support)

    class Settings:
        name = "leads"
        indexes = [
            "entity_id",              # Fast lookups by entity
            "assigned_to",            # Agent's leads
            "status",                 # Filter by status
            "lead_type",              # Filter by type
            "source",                 # Filter by source
            [("entity_id", 1), ("status", 1)],  # Compound index
            [("assigned_to", 1), ("status", 1)],  # Agent's active leads
            "created_at",             # Time-based queries
            "next_followup"           # Upcoming followups
        ]

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
        timestamp = datetime.utcnow().isoformat()
        self.notes.append(f"[{timestamp}] (by {author_id}): {note}")
        self.updated_at = datetime.utcnow()


class LeadNote(Document):
    """
    Separate collection for lead notes (alternative to embedded notes).

    This allows for better querying and filtering of notes.
    Currently using embedded notes in Lead, but this is here as an option.
    """
    lead_id: str = Indexed()
    author_id: str = Indexed()
    author_name: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    note_type: Literal["general", "call", "email", "showing", "offer"] = "general"

    class Settings:
        name = "lead_notes"
        indexes = [
            "lead_id",
            "author_id",
            [("lead_id", 1), ("created_at", -1)]  # Lead's notes chronologically
        ]
