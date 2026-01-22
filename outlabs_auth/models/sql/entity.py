"""
Entity Model (EnterpriseRBAC)

Organizational hierarchy entities - companies, departments, teams, projects.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship

from outlabs_auth.database.base import BaseModel

from .enums import EntityClass

if TYPE_CHECKING:
    from .entity_membership import EntityMembership
    from .role import Role
    from .user import User


class Entity(BaseModel, table=True):
    """
    Entity model for organizational hierarchy.

    Entities represent organizational units (STRUCTURAL) or access groups
    (ACCESS_GROUP) in a hierarchical structure.

    Table: entities
    """

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("slug", "tenant_id", name="uq_entities_slug_tenant"),
        Index("ix_entities_name", "name"),
        Index("ix_entities_slug", "slug"),
        Index("ix_entities_class_type", "entity_class", "entity_type"),
        Index("ix_entities_parent_id", "parent_id"),
        Index("ix_entities_status", "status"),
        Index("ix_entities_tenant_id", "tenant_id"),
    )

    # === Identity ===
    name: str = Field(
        sa_column=Column(String(200), nullable=False),
        description="Entity name (for display)",
    )
    display_name: str = Field(
        sa_column=Column(String(200), nullable=False),
    )
    slug: str = Field(
        sa_column=Column(String(200), nullable=False),
        description="URL-friendly unique identifier",
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
    )

    # === Classification ===
    entity_class: EntityClass = Field(
        sa_column=Column(String(20), nullable=False),
        description="STRUCTURAL (org units) or ACCESS_GROUP (permission groups)",
    )
    entity_type: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="Specific type: organization, department, team, project, etc.",
    )

    # === Hierarchy (Self-referential) ===
    parent_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="Parent entity in hierarchy",
    )
    depth: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Depth in hierarchy (0 = root)",
    )
    path: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2000), nullable=True),
        description="Materialized path for efficient queries (e.g., '/root/org/dept/')",
    )

    # === Lifecycle ===
    status: str = Field(
        default="active",
        sa_column=Column(String(20), nullable=False, default="active"),
        description="active, inactive, archived",
    )
    valid_from: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # === Configuration ===
    max_members: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="Maximum number of members (null = unlimited)",
    )
    max_depth: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="Maximum child depth allowed (null = unlimited)",
    )

    # === Relationships ===
    parent: Optional["Entity"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "Entity.id",
            "foreign_keys": "[Entity.parent_id]",
        },
    )
    children: List["Entity"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"foreign_keys": "[Entity.parent_id]"},
    )
    scoped_roles: List["Role"] = Relationship(back_populates="root_entity")
    memberships: List["EntityMembership"] = Relationship(
        back_populates="entity",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    users: List["User"] = Relationship(
        back_populates="root_entity",
        sa_relationship_kwargs={"foreign_keys": "[User.root_entity_id]"},
    )

    # === Properties ===
    @property
    def is_structural(self) -> bool:
        return self.entity_class == EntityClass.STRUCTURAL

    @property
    def is_access_group(self) -> bool:
        return self.entity_class == EntityClass.ACCESS_GROUP

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    def is_active(self) -> bool:
        """Check if entity is currently active."""
        if self.status != "active":
            return False
        now = datetime.now(timezone.utc)
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    def update_path(self, parent_path: Optional[str] = None) -> None:
        """Update materialized path based on parent."""
        if parent_path:
            self.path = f"{parent_path}{self.slug}/"
        else:
            self.path = f"/{self.slug}/"
