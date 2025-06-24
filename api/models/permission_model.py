from typing import Optional
from pydantic import Field
from beanie import Document
from pymongo import IndexModel

from .scopes import PermissionScope

class PermissionModel(Document):
    """
    Beanie Document for the 'permissions' collection in MongoDB.
    Supports three-tier scoped permissions following the role architecture.
    """
    # MongoDB ObjectId (auto-generated)
    name: str = Field(..., description="Permission name without scope prefix")
    display_name: str = Field(..., description="Human-readable permission name")
    description: Optional[str] = Field(None, description="What this permission allows")
    
    # Scoping (same pattern as roles)
    scope: PermissionScope = Field(..., description="Permission scope: system, platform, or client")
    scope_id: Optional[str] = Field(None, description="Foreign key to scope owner (platform_id or client_account_id)")
    
    # Metadata
    created_by_user_id: Optional[str] = Field(None, description="User who created this permission")
    created_by_client_id: Optional[str] = Field(None, description="Client account that created this permission")
    
    class Settings:
        name = "permissions"
        indexes = [
            # Scope-based queries
            IndexModel([("scope", 1), ("scope_id", 1)], name="scope_index"),
            # Name uniqueness within scope
            IndexModel([("name", 1), ("scope", 1), ("scope_id", 1)], unique=True, name="name_scope_unique"),
            # Creator tracking
            IndexModel([("created_by_client_id", 1)], name="created_by_client_index"),
            # Common queries
            IndexModel([("scope", 1)], name="scope_lookup_index")
        ]
        
    class Config:
        populate_by_name = True 