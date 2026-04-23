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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship

from outlabs_auth.database.base import BaseModel

from .enums import EntityClass

if TYPE_CHECKING:
    from .entity_membership import EntityMembership
    from .integration_principal import IntegrationPrincipal
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
        # The unique constraint on slug already creates a btree index; the
        # separate ix_entities_slug is redundant and dropped.
        UniqueConstraint("slug", name="uq_entities_slug"),
        Index("ix_entities_name", "name"),
        Index("ix_entities_class_type", "entity_class", "entity_type"),
        Index("ix_entities_parent_id", "parent_id"),
        Index("ix_entities_status", "status"),
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

    # === Child Entity Configuration (for root entities) ===
    allowed_child_types: List[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(String(50)),
            nullable=False,
            server_default="{}",
        ),
        description="Entity types allowed as children (for root entities). Empty = use system defaults.",
    )
    allowed_child_classes: List[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(String(20)),
            nullable=False,
            server_default="{}",
        ),
        description="Entity classes allowed as children (structural, access_group). Empty = all allowed.",
    )
    child_name_pattern: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Optional regex pattern used to validate descendant system names within this root hierarchy.",
    )
    child_display_name_pattern: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Optional regex pattern used to validate descendant display names within this root hierarchy.",
    )
    child_slug_pattern: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Optional regex pattern used to validate descendant slugs within this root hierarchy.",
    )
    child_naming_guidance: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
        description="Optional operator guidance for descendant naming within this root hierarchy.",
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
    scoped_roles: List["Role"] = Relationship(
        back_populates="root_entity",
        sa_relationship_kwargs={"foreign_keys": "Role.root_entity_id"},
    )
    memberships: List["EntityMembership"] = Relationship(
        back_populates="entity",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    users: List["User"] = Relationship(
        back_populates="root_entity",
        sa_relationship_kwargs={"foreign_keys": "[User.root_entity_id]"},
    )
    integration_principals: List["IntegrationPrincipal"] = Relationship(
        back_populates="anchor_entity",
        sa_relationship_kwargs={"foreign_keys": "[IntegrationPrincipal.anchor_entity_id]"},
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
