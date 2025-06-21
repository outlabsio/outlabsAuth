from typing import List, Optional
from pydantic import Field
from beanie import Link, BackLink
from pymongo import IndexModel

from .base_model import BaseDocument

class GroupModel(BaseDocument):
    """
    Beanie Document for the 'groups' collection in MongoDB.
    Groups are collections of users with shared roles within a client account.
    """
    name: str
    description: Optional[str] = None
    client_account: Link["ClientAccountModel"]
    roles: List[str] = Field(default_factory=list)  # List of role IDs assigned to this group
    is_active: bool = True
    
    # BackLink to get all users in this group (optional, for convenience)
    members: Optional[BackLink["UserModel"]] = Field(original_field="groups", default=[])
    
    class Settings:
        name = "groups"  # MongoDB collection name
        indexes = [
            IndexModel([("name", 1), ("client_account", 1)], unique=True, name="name_client_unique"),  # Unique name per client
            IndexModel([("client_account", 1)], name="client_account_idx"),  # Index for client queries
        ] 