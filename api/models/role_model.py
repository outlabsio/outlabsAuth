from typing import List, Optional
from pydantic import Field
from pymongo import IndexModel
from beanie import PydanticObjectId

from .base_model import BaseDocument
from .scopes import RoleScope

class RoleModel(BaseDocument):
    """
    Beanie Document for the 'roles' collection in MongoDB.
    Uses standard MongoDB ObjectIds with scope fields for tenant isolation.
    """
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")
    name: str = Field(..., description="Role name (e.g., 'admin', 'manager')")
    display_name: str = Field(..., description="Human-readable role name")
    description: Optional[str] = Field(None, description="Role purpose and capabilities")
    permissions: List[str] = Field(default_factory=list, description="List of permission IDs")
    
    # Scope/Ownership
    scope: RoleScope = Field(..., description="Role scope: system, platform, or client")
    scope_id: Optional[str] = Field(None, description="Foreign key to scope owner (platform_id or client_account_id)")
    
    # Assignment control
    is_assignable_by_main_client: bool = Field(False, description="Can client admins assign this role?")
    
    # Metadata
    created_by_user_id: Optional[str] = Field(None, description="User who created this role")
    created_by_client_id: Optional[str] = Field(None, description="Client account that created this role")
    
    class Settings:
        name = "roles"
        indexes = [
            # Scope-based queries
            IndexModel([("scope", 1), ("scope_id", 1)], name="scope_index"),
            # Name uniqueness within scope
            IndexModel([("name", 1), ("scope", 1), ("scope_id", 1)], unique=True, name="name_scope_unique"),
            # Creator tracking
            IndexModel([("created_by_client_id", 1)], name="created_by_client_index"),
            # Common queries
            IndexModel([("scope", 1), ("is_assignable_by_main_client", 1)], name="assignable_roles_index")
        ]
        
    class Config:
        populate_by_name = True 