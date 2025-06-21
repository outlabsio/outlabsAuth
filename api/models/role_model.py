from typing import List, Optional
from pydantic import Field
from pymongo import IndexModel

from .base_model import BaseDocument

class RoleModel(BaseDocument):
    """
    Beanie Document for the 'roles' collection in MongoDB.
    Uses a string ID (e.g., "platform_admin").
    """
    id: str = Field(alias="_id")  # String ID instead of ObjectId
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list) # List of permission IDs
    is_assignable_by_main_client: bool = Field(False)
    
    class Settings:
        name = "roles"  # MongoDB collection name
        indexes = [
            IndexModel([("name", 1)], unique=True, name="name_unique"),  # Unique name index
        ]
        
    class Config:
        populate_by_name = True 