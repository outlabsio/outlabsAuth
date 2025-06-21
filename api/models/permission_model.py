from typing import Optional
from pydantic import Field
from beanie import Document

class PermissionModel(Document):
    """
    Beanie Document for the 'permissions' collection in MongoDB.
    Uses a string ID (e.g., "user:create").
    """
    id: str = Field(alias="_id")  # String ID instead of ObjectId
    description: Optional[str] = None
    
    class Settings:
        name = "permissions"  # MongoDB collection name
        
    class Config:
        populate_by_name = True 