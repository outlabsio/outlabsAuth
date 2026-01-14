"""
Permission Model and Related Tables

Permission definitions for RBAC/ABAC authorization - properly normalized.
"""

from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, Index, UniqueConstraint, ForeignKey, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel
from .enums import ConditionOperator

if TYPE_CHECKING:
    from .role import Role, RolePermission


# === Permission Tags (Many-to-Many) ===
class PermissionTag(BaseModel, table=True):
    """
    Tags for categorizing permissions.

    Table: permission_tags
    """
    __tablename__ = "permission_tags"
    __table_args__ = (
        UniqueConstraint("name", "tenant_id", name="uq_permission_tags_name_tenant"),
        Index("ix_permission_tags_name", "name"),
    )

    name: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="Tag name (e.g., 'admin', 'finance', 'hr')",
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )


# === Junction Table: Permission ↔ Tag ===
class PermissionTagLink(SQLModel, table=True):
    """
    Junction table linking permissions to tags.

    Table: permission_tag_links
    """
    __tablename__ = "permission_tag_links"

    permission_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    tag_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("permission_tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


# === ABAC Condition for Permissions ===
class PermissionCondition(BaseModel, table=True):
    """
    ABAC condition attached to a permission.

    These conditions must be satisfied for the permission to be granted,
    regardless of which role provides it.

    Table: permission_conditions
    """
    __tablename__ = "permission_conditions"
    __table_args__ = (
        Index("ix_permission_conditions_permission_id", "permission_id"),
        Index("ix_permission_conditions_group_id", "condition_group_id"),
    )

    permission_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Condition group for AND/OR logic
    condition_group_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("condition_groups.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Condition definition
    attribute: str = Field(
        sa_column=Column(String(200), nullable=False),
    )
    operator: ConditionOperator = Field(
        sa_column=Column(String(30), nullable=False),
    )
    value: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    value_type: str = Field(
        default="string",
        sa_column=Column(String(20), nullable=False, default="string"),
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )

    # Relationship
    permission: "Permission" = Relationship(back_populates="conditions")


# === Main Permission Model ===
class Permission(BaseModel, table=True):
    """
    Permission model defining granular access rights.

    Permissions follow the pattern: resource:action
    Examples: user:create, post:read, document:delete_tree

    Table: permissions
    """
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("name", "tenant_id", name="uq_permissions_name_tenant"),
        Index("ix_permissions_name", "name"),
        Index("ix_permissions_resource", "resource"),
        Index("ix_permissions_is_system", "is_system"),
        Index("ix_permissions_is_active", "is_active"),
    )

    # === Identity ===
    name: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="Permission identifier (e.g., 'user:create')",
    )
    display_name: str = Field(
        sa_column=Column(String(200), nullable=False),
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
    )

    # === Derived Fields (parsed from name) ===
    resource: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
        description="Resource part (e.g., 'user')",
    )
    action: Optional[str] = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
        description="Action part (e.g., 'create')",
    )
    scope: Optional[str] = Field(
        default=None,
        sa_column=Column(String(20), nullable=True),
        description="Scope modifier (e.g., 'tree', 'own')",
    )

    # === Status ===
    is_system: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True),
    )

    # === Relationships ===
    # Note: Role relationship defined via RolePermission junction table
    # Use Role.permissions to query permissions for a role
    tags: List["PermissionTag"] = Relationship(
        link_model=PermissionTagLink,
    )
    conditions: List["PermissionCondition"] = Relationship(
        back_populates="permission",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    def __init__(self, **data):
        """Auto-populate resource, action, scope from name."""
        super().__init__(**data)
        self._parse_name()

    def _parse_name(self) -> None:
        """Parse name into components."""
        if not self.name:
            return

        if ":" not in self.name:
            self.resource = self.name
            return

        parts = self.name.split(":", 1)
        self.resource = parts[0]

        if len(parts) > 1:
            action_part = parts[1]
            if "_" in action_part:
                action_parts = action_part.rsplit("_", 1)
                if action_parts[-1] in ("tree", "all", "own"):
                    self.action = action_parts[0]
                    self.scope = action_parts[-1]
                else:
                    self.action = action_part
            else:
                self.action = action_part

    def is_tree_permission(self) -> bool:
        """Check if this is a tree (hierarchical) permission."""
        return self.scope == "tree"

    def is_wildcard(self) -> bool:
        """Check if this is a wildcard permission."""
        return self.name in ("*:*", "*") or self.action == "*"

    def matches(self, required: str) -> bool:
        """Check if this permission matches a required permission."""
        if self.name == "*:*":
            return True
        if self.name == required:
            return True
        if ":" in required:
            req_resource, _ = required.split(":", 1)
            if self.resource == req_resource and self.action == "*":
                return True
        return False
