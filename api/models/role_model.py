"""
Role Model - Context-aware roles
"""
from typing import List, Optional
from datetime import datetime
from beanie import Link, Indexed
from pydantic import Field
from api.models.base_model import BaseDocument
from api.models.entity_model import EntityModel, EntityType
from api.models.user_model import UserModel


class RoleModel(BaseDocument):
    """
    Role definition with context-aware scoping
    """
    # Identity
    name: str = Indexed()
    display_name: str
    description: Optional[str] = None
    
    # Permissions this role grants
    permissions: List[str] = Field(default_factory=list)
    
    # Scoping - which entity owns this role
    entity: Link[EntityModel]
    
    # Where this role can be assigned
    assignable_at_types: List[EntityType] = Field(default_factory=list)
    
    # Configuration
    is_system_role: bool = Field(default=False)
    is_global: bool = Field(default=False)  # Platform-level roles can be global
    
    # Audit
    created_by: Optional[Link[UserModel]] = None
    
    class Settings:
        name = "roles"
        indexes = [
            [("name", 1), ("entity", 1)],  # Unique per entity
            [("entity", 1)],
            [("is_system_role", 1)],
        ]