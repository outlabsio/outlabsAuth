from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RoleCreateSchema(BaseModel):
    """
    Schema for creating a new role.
    The 'id' is a readable string like 'platform_admin'.
    """
    id: str = Field(..., alias="_id", description="Unique string identifier for the role")
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    is_assignable_by_main_client: bool = False

class RoleUpdateSchema(BaseModel):
    """
    Schema for updating a role. All fields are optional.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_assignable_by_main_client: Optional[bool] = None

class RoleResponseSchema(BaseModel):
    """
    Schema for returning role data in API responses.
    """
    id: str = Field(..., alias="_id")
    name: str
    description: Optional[str] = None
    permissions: List[str]
    is_assignable_by_main_client: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True 