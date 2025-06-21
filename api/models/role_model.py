from typing import List, Optional
from pydantic import Field
from .base_model import BaseDBModelWithStringID

class RoleModel(BaseDBModelWithStringID):
    """
    Pydantic model for the 'roles' collection in MongoDB.
    Uses a string ID (e.g., "platform_admin").
    """
    name: str = Field(...)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list) # List of permission IDs
    is_assignable_by_main_client: bool = Field(False)

    # Collection metadata - handled by services layer 