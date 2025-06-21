from datetime import datetime
from typing import Optional, Any, Dict
from beanie import Document
from pydantic import Field, BaseModel

class BaseDocument(Document):
    """
    Base Beanie Document for MongoDB collections.
    Handles ObjectId serialization, timestamps, and common configurations automatically.
    """
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        # Beanie handles ObjectId serialization automatically
        use_state_management = True
        
    def update_timestamp(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.utcnow()

# For backwards compatibility during migration
BaseDBModel = BaseDocument 