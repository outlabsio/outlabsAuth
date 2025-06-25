from typing import List, Optional
from pydantic import Field
from beanie import BackLink, Link
from pymongo import IndexModel

from .base_model import BaseDocument
from .scopes import GroupScope

# Forward reference - PermissionModel will be imported by Beanie

class GroupModel(BaseDocument):
    """
    Beanie Document for the 'groups' collection in MongoDB.
    Groups are organizational teams with direct permissions at all scope levels.
    """
    name: str = Field(..., description="Group name (e.g., 'Sales Team', 'Customer Support')")
    display_name: str = Field(..., description="Human-readable group name")
    description: Optional[str] = Field(None, description="Group purpose and responsibilities")
    
    # Direct permissions (removed roles field)
    permissions: List[Link["PermissionModel"]] = Field(default_factory=list, description="List of permission Links")
    
    # Scoping (all three levels)
    scope: GroupScope = Field(..., description="Group scope: system, platform, or client")
    scope_id: Optional[str] = Field(None, description="Foreign key to scope owner (platform_id or client_account_id)")
    
    # Active status
    is_active: bool = Field(True, description="Whether the group is active")
    
    # Metadata
    created_by_user_id: Optional[str] = Field(None, description="User who created this group")
    created_by_client_id: Optional[str] = Field(None, description="Client account that created this group")
    
    # BackLink to get all users in this group
    members: Optional[BackLink["UserModel"]] = Field(original_field="groups", default=[])
    
    class Settings:
        name = "groups"
        indexes = [
            # Scope-based queries
            IndexModel([("scope", 1), ("scope_id", 1)], name="scope_index"),
            # Name uniqueness within scope
            IndexModel([("name", 1), ("scope", 1), ("scope_id", 1)], unique=True, name="name_scope_unique"),
            # Creator tracking
            IndexModel([("created_by_client_id", 1)], name="created_by_client_index"),
            # Active groups
            IndexModel([("is_active", 1)], name="active_groups_index")
        ] 