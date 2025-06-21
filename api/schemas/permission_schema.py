from pydantic import BaseModel, Field
from typing import Optional

class PermissionCreateSchema(BaseModel):
    """
    Schema for creating a new permission.
    The 'id' is a readable string like 'user:create'.
    """
    id: str = Field(..., alias="_id", description="Unique string identifier for the permission")
    description: Optional[str] = None

class PermissionResponseSchema(BaseModel):
    """
    Schema for returning permission data in API responses.
    """
    id: str = Field(alias="_id")
    description: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True 