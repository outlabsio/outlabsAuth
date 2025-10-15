"""
Role Model - Context-aware roles
"""
from typing import List, Optional, Dict
from datetime import datetime
from beanie import Link, Indexed
from pydantic import Field
from api.models.base_model import BaseDocument
from api.models.entity_model import EntityModel
from api.models.user_model import UserModel


class RoleModel(BaseDocument):
    """
    Role definition with context-aware scoping
    """
    # Identity
    name: str = Indexed()
    display_name: str
    description: Optional[str] = None
    
    # Permissions this role grants (default permissions when no entity type match)
    permissions: List[str] = Field(default_factory=list)
    
    # Context-aware permissions: Different permissions based on entity type
    # Example: {"region": ["entity:manage_tree", "user:manage_tree"], 
    #          "office": ["entity:read", "user:read"]}
    entity_type_permissions: Optional[Dict[str, List[str]]] = Field(
        default_factory=dict,
        description="Permissions that apply when role is assigned at specific entity types"
    )
    
    # Scoping - which entity owns this role
    entity: Link[EntityModel]
    
    # Where this role can be assigned (flexible entity type strings)
    assignable_at_types: List[str] = Field(default_factory=list)
    
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