"""
Entity Model - Core of hierarchical RBAC system

Represents organizational entities (departments, teams) and access groups
with full support for tree permissions and closure table optimization.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from beanie import Link, Indexed
from pydantic import Field

from outlabs_auth.models.base import BaseDocument


class EntityClass(str, Enum):
    """
    Classification of entities.

    - STRUCTURAL: Organizational hierarchy (departments, divisions, teams)
    - ACCESS_GROUP: Cross-cutting permission groups (not part of org chart)
    """
    STRUCTURAL = "structural"
    ACCESS_GROUP = "access_group"


class EntityModel(BaseDocument):
    """
    Unified Entity Model - represents both structural entities and access groups.

    Structural entities form organizational hierarchies (org → dept → team).
    Access groups provide cross-cutting permissions (admin_group, viewer_group).

    Example hierarchy:
        Platform (structural)
        └── Organization (structural)
            ├── Engineering Dept (structural)
            │   └── Backend Team (structural)
            └── Admin Group (access_group)
    """

    # Identity
    name: str = Indexed()  # System name (lowercase, underscores)
    display_name: str  # User-friendly name
    slug: str = Indexed(unique=True)  # URL-friendly identifier
    description: Optional[str] = None

    # Classification
    entity_class: EntityClass  # STRUCTURAL or ACCESS_GROUP
    entity_type: str  # Flexible: "organization", "department", "team", etc.

    # Hierarchy
    parent_entity: Optional[Link["EntityModel"]] = None

    # Lifecycle
    status: str = Field(default="active")  # active, inactive, archived
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Permissions (optional direct permissions on entity)
    direct_permissions: List[str] = Field(default_factory=list)

    # Flexible metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Configuration
    allowed_child_classes: List[EntityClass] = Field(default_factory=list)
    allowed_child_types: List[str] = Field(default_factory=list)
    max_members: Optional[int] = None

    # Helper properties
    @property
    def is_structural(self) -> bool:
        """Check if entity is a structural (organizational) entity"""
        return self.entity_class == EntityClass.STRUCTURAL

    @property
    def is_access_group(self) -> bool:
        """Check if entity is an access group"""
        return self.entity_class == EntityClass.ACCESS_GROUP

    def is_active(self) -> bool:
        """
        Check if entity is currently active.

        Returns False if:
        - Status is not "active"
        - Current time is before valid_from
        - Current time is after valid_until
        """
        if self.status != "active":
            return False

        now = datetime.now(timezone.utc)

        if self.valid_from and now < self.valid_from:
            return False

        if self.valid_until and now > self.valid_until:
            return False

        return True

    async def is_ancestor_of(self, entity: "EntityModel") -> bool:
        """
        Check if this entity is an ancestor of another entity.

        Note: For O(1) performance, use EntityClosureModel instead.
        This method walks the tree and is O(depth).

        Args:
            entity: Entity to check

        Returns:
            bool: True if this entity is an ancestor
        """
        current = entity
        while current.parent_entity:
            parent = await current.parent_entity.fetch()
            if parent.id == self.id:
                return True
            current = parent
        return False

    def __repr__(self) -> str:
        return f"<EntityModel(name={self.name}, class={self.entity_class}, type={self.entity_type})>"

    class Settings:
        name = "entities"
        indexes = [
            "name",
            "slug",
            [("entity_class", 1), ("entity_type", 1)],
            "parent_entity",
            [("tenant_id", 1)],  # For multi-tenant filtering
            "status",
        ]


# Rebuild RoleModel now that EntityModel is fully defined
# This resolves the forward reference in RoleModel.entity
from outlabs_auth.models.role import RoleModel

RoleModel.model_rebuild()
