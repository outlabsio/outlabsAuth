"""
EntityClosure Model (EnterpriseRBAC)

Closure table for O(1) ancestor/descendant queries in entity hierarchy.
"""

from uuid import UUID

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Index, UniqueConstraint, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel


class EntityClosure(BaseModel, table=True):
    """
    Closure table for efficient hierarchical queries.

    Stores all ancestor-descendant relationships with depth.
    Enables O(1) queries for:
    - Get all ancestors of an entity
    - Get all descendants of an entity
    - Check if A is ancestor of B
    - Get entities at specific depth

    For hierarchy: Platform → Org → Dept → Team
    Records stored:
      (Platform, Platform, 0)  # self-reference
      (Platform, Org, 1)       # direct child
      (Platform, Dept, 2)      # grandchild
      (Platform, Team, 3)      # great-grandchild
      (Org, Org, 0)            # self-reference
      (Org, Dept, 1)           # direct child
      (Org, Team, 2)           # grandchild
      ... etc

    Table: entity_closure
    """
    __tablename__ = "entity_closure"
    __table_args__ = (
        UniqueConstraint("ancestor_id", "descendant_id", name="uq_entity_closure"),
        Index("ix_closure_ancestor_id", "ancestor_id"),
        Index("ix_closure_descendant_id", "descendant_id"),
        Index("ix_closure_ancestor_depth", "ancestor_id", "depth"),
        Index("ix_closure_descendant_depth", "descendant_id", "depth"),
        Index("ix_closure_tenant_id", "tenant_id"),
    )

    # === Foreign Keys to Entity ===
    ancestor_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="Ancestor entity in the relationship",
    )
    descendant_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="Descendant entity in the relationship",
    )

    # === Depth ===
    depth: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="Distance between ancestor and descendant (0 = self)",
    )

    @property
    def is_self_reference(self) -> bool:
        """Check if this is a self-reference (depth=0)."""
        return self.depth == 0

    @property
    def is_direct_relationship(self) -> bool:
        """Check if this is a direct parent-child relationship."""
        return self.depth == 1
