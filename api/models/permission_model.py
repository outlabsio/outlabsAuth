from typing import Optional
from .base_model import BaseDBModelWithStringID

class PermissionModel(BaseDBModelWithStringID):
    """
    Pydantic model for the 'permissions' collection in MongoDB.
    Uses a string ID (e.g., "user:create").
    """
    description: Optional[str] = None 