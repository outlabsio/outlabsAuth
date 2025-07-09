"""
Base model for all documents
"""
from datetime import datetime, timezone
from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class BaseDocument(Document):
    """Base document with common fields"""
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    
    def __eq__(self, other):
        if isinstance(other, BaseDocument):
            return self.id == other.id
        return False
    
    def __hash__(self):
        return hash(self.id)
    
    class Settings:
        use_state_management = True
        validate_on_save = True
        
    async def save(self, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = datetime.now(timezone.utc)
        return await super().save(**kwargs)