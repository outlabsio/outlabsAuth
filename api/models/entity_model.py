"""
Entity Model - Core of the Unified Entity Architecture
"""
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from api.models.role_model import RoleModel
from datetime import datetime, timezone
from beanie import Link, Indexed
from pydantic import Field
from api.models.base_model import BaseDocument
from api.models.user_model import UserModel


class EntityClass(str, Enum):
    """Classification of entities"""
    STRUCTURAL = "structural"
    ACCESS_GROUP = "access_group"


class EntityType(str, Enum):
    """Types of entities"""
    # Structural types
    PLATFORM = "platform"
    ORGANIZATION = "organization"
    DIVISION = "division"
    BRANCH = "branch"
    TEAM = "team"
    
    # Access group types
    FUNCTIONAL_GROUP = "functional_group"
    PERMISSION_GROUP = "permission_group"
    PROJECT_GROUP = "project_group"
    ROLE_GROUP = "role_group"
    ACCESS_GROUP = "access_group"


class EntityModel(BaseDocument):
    """
    Unified Entity Model - represents both structural entities and access groups
    """
    # Identity
    name: str = Indexed()
    display_name: str  # User-friendly name
    slug: str = Indexed(unique=True)
    description: Optional[str] = None
    
    # Classification
    entity_class: EntityClass
    entity_type: str  # Flexible entity type
    
    # Hierarchy
    platform_id: str = Indexed()
    parent_entity: Optional[Link["EntityModel"]] = None
    
    # Access control
    status: str = Field(default="active")
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    # Permissions and roles
    direct_permissions: List[str] = Field(default_factory=list)
    
    # Flexible metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Configuration
    allowed_child_classes: List[EntityClass] = Field(default_factory=list)
    allowed_child_types: List[str] = Field(default_factory=list)  # Flexible child types
    max_members: Optional[int] = None
    
    @property
    def is_structural(self) -> bool:
        return self.entity_class == EntityClass.STRUCTURAL
    
    @property
    def is_access_group(self) -> bool:
        return self.entity_class == EntityClass.ACCESS_GROUP
    
    def is_active(self) -> bool:
        """Check if entity is currently active"""
        if self.status != "active":
            return False
        now = datetime.now(timezone.utc)
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    async def is_ancestor_of(self, entity: "EntityModel") -> bool:
        """Check if this entity is an ancestor of another"""
        current = entity
        while current.parent_entity:
            parent = await current.parent_entity.fetch()
            if parent.id == self.id:
                return True
            current = parent
        return False
    
    class Settings:
        name = "entities"
        indexes = [
            [("slug", 1)],
            [("platform_id", 1)],
            [("entity_class", 1), ("entity_type", 1)],
            [("parent_entity", 1)],
        ]


class EntityMembershipModel(BaseDocument):
    """
    Represents a user's membership in an entity with assigned roles
    """
    user: Link[UserModel]
    entity: Link[EntityModel]
    
    # Roles assigned to user in THIS entity context
    roles: List[Link["RoleModel"]] = Field(default_factory=list)
    
    # Membership metadata
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    joined_by: Optional[Link[UserModel]] = None
    
    # Time-based membership
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    # Status
    is_active: bool = Field(default=True)
    
    def is_currently_valid(self) -> bool:
        """Check if membership is currently valid (active and within valid dates)"""
        if not self.is_active:
            return False
        now = datetime.now(timezone.utc)
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    class Settings:
        name = "entity_memberships"
        indexes = [
            [("user", 1), ("entity", 1)],  # Unique constraint
            [("entity", 1)],  # Fast entity member lookup
            [("user", 1)],  # Fast user membership lookup
            [("is_active", 1)],
        ]