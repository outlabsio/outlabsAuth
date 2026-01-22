"""
Role Model and Related Tables

Role-based access control with proper normalization.
- RolePermission: Junction table for role → permission assignments
- RoleCondition: ABAC conditions attached to roles
- RoleEntityTypePermission: Context-aware permissions by entity type
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship, SQLModel

from outlabs_auth.database.base import BaseModel

from .enums import ConditionOperator, RoleScope

if TYPE_CHECKING:
    from .entity import Entity
    from .permission import Permission
    from .user_role_membership import UserRoleMembership


# === Junction Table: Role ↔ Permission ===
class RolePermission(SQLModel, table=True):
    """
    Junction table linking roles to permissions.

    Each role can have multiple permissions assigned.
    Uses FK to Permission table for referential integrity.

    Table: role_permissions
    """

    __tablename__ = "role_permissions"
    __table_args__ = (
        Index("ix_role_permissions_role_id", "role_id"),
        Index("ix_role_permissions_permission_id", "permission_id"),
    )

    role_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    permission_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


# === ABAC Condition Table ===
class RoleCondition(BaseModel, table=True):
    """
    ABAC condition attached to a role.

    Conditions are evaluated at runtime to determine if the role's
    permissions apply in the current context.

    Example: role grants "document:edit" only if resource.department == "engineering"

    Table: role_conditions
    """

    __tablename__ = "role_conditions"
    __table_args__ = (
        Index("ix_role_conditions_role_id", "role_id"),
        Index("ix_role_conditions_group_id", "condition_group_id"),
    )

    role_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Condition group for AND/OR logic (null = standalone condition with implicit AND)
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
        description="Dot-notation path (e.g., 'resource.department', 'user.role')",
    )
    operator: ConditionOperator = Field(
        sa_column=Column(String(30), nullable=False),
        description="Comparison operator",
    )
    value: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Value to compare (stored as string, parsed by type)",
    )
    value_type: str = Field(
        default="string",
        sa_column=Column(String(20), nullable=False, default="string"),
        description="Type of value: string, integer, float, boolean, list",
    )

    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )

    # Relationship
    role: "Role" = Relationship(back_populates="conditions")


# === Context-Aware Permissions by Entity Type ===
class RoleEntityTypePermission(BaseModel, table=True):
    """
    Context-aware permission assignment by entity type.

    In EnterpriseRBAC, a role can grant different permissions depending
    on the entity type context. E.g., "Manager" role grants:
    - At organization level: ["budget:approve", "hire:approve"]
    - At team level: ["task:assign", "review:approve"]

    Table: role_entity_type_permissions
    """

    __tablename__ = "role_entity_type_permissions"
    __table_args__ = (
        Index("ix_retp_role_id", "role_id"),
        Index("ix_retp_entity_type", "entity_type"),
        Index("ix_retp_role_entity_type", "role_id", "entity_type"),
    )

    role_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    entity_type: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="Entity type this permission applies to",
    )
    permission_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Relationships
    role: "Role" = Relationship(back_populates="entity_type_permissions")
    permission: "Permission" = Relationship()


# === Condition Group for Complex Logic ===
class ConditionGroup(BaseModel, table=True):
    """
    Groups conditions with AND/OR logic.

    Allows complex permission rules like:
    "(department = engineering AND level >= 3) OR is_admin = true"

    Table: condition_groups
    """

    __tablename__ = "condition_groups"
    __table_args__ = (
        Index("ix_condition_groups_role_id", "role_id"),
        Index("ix_condition_groups_permission_id", "permission_id"),
    )

    # Parent (either role or permission, not both)
    role_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    permission_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Logical operator
    operator: str = Field(
        default="AND",
        sa_column=Column(String(5), nullable=False, default="AND"),
        description="Logical operator: AND or OR",
    )

    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )

    # Nested group support (for complex expressions)
    parent_group_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("condition_groups.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )


# === Main Role Model ===
class Role(BaseModel, table=True):
    """
    Role model for RBAC permission grouping.

    Permissions are assigned via the role_permissions junction table.
    ABAC conditions are stored in role_conditions table.
    Context-aware permissions stored in role_entity_type_permissions.

    Table: roles
    """

    __tablename__ = "roles"
    __table_args__ = (
        Index("ix_roles_name", "name"),
        Index("ix_roles_name_tenant", "name", "tenant_id"),
        Index("ix_roles_is_global", "is_global"),
        Index("ix_roles_root_entity_id", "root_entity_id"),
        Index("ix_roles_scope_entity_id", "scope_entity_id"),
        Index("ix_roles_is_auto_assigned", "is_auto_assigned"),
    )

    # === Identity ===
    name: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="System name (lowercase, e.g., 'admin', 'editor')",
    )
    display_name: str = Field(
        sa_column=Column(String(200), nullable=False),
        description="Human-readable name",
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
    )

    # === Root Entity Scope (EnterpriseRBAC) ===
    root_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="Root entity (organization) that owns this role. NULL = system-wide role available everywhere.",
    )

    # === Configuration ===
    is_system_role: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="System roles cannot be modified/deleted",
    )
    is_global: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="Global roles can be assigned anywhere in hierarchy",
    )

    # === Entity-Local Role Configuration (DD-053) ===
    scope_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=True,
        ),
        description="Entity where this role is defined. NULL = root/system-level role.",
    )
    scope: RoleScope = Field(
        default=RoleScope.HIERARCHY,
        sa_column=Column(String(20), nullable=False, default="hierarchy"),
        description="Controls where permissions apply and auto-assignment scope: entity_only or hierarchy.",
    )
    is_auto_assigned: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="If true, automatically assigned to all members within scope (retroactive).",
    )

    # === Relationships ===
    root_entity: Optional["Entity"] = Relationship(
        back_populates="scoped_roles",
        sa_relationship_kwargs={"foreign_keys": "[Role.root_entity_id]"},
    )
    scope_entity: Optional["Entity"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Role.scope_entity_id]"},
    )
    user_memberships: List["UserRoleMembership"] = Relationship(back_populates="role")

    # Permissions via junction table
    permissions: List["Permission"] = Relationship(
        link_model=RolePermission,
    )

    # ABAC conditions
    conditions: List["RoleCondition"] = Relationship(
        back_populates="role",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # Context-aware permissions
    entity_type_permissions: List["RoleEntityTypePermission"] = Relationship(
        back_populates="role",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # === Methods ===
    def get_permission_names(self) -> List[str]:
        """Get list of permission names assigned to this role."""
        return [p.name for p in self.permissions]

    def has_conditions(self) -> bool:
        """Check if role has ABAC conditions."""
        return len(self.conditions) > 0

    def is_entity_local(self) -> bool:
        """Check if this is an entity-local role (has scope_entity_id)."""
        return self.scope_entity_id is not None

    def is_hierarchy_scoped(self) -> bool:
        """Check if role permissions cascade to descendants."""
        return self.scope == RoleScope.HIERARCHY

    def is_entity_only_scoped(self) -> bool:
        """Check if role permissions are limited to the scope entity only."""
        return self.scope == RoleScope.ENTITY_ONLY
