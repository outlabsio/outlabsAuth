from pydantic import BaseModel, Field
from typing import Optional, List
from beanie import PydanticObjectId
from ..models.scopes import PermissionScope

class PermissionDetailSchema(BaseModel):
    """
    Schema for permission details in API responses.
    Includes both ObjectId and human-readable information.
    """
    id: str = Field(..., description="Permission ObjectId")
    name: str = Field(..., description="Permission name (e.g., 'user:create')")
    scope: PermissionScope = Field(..., description="Permission scope")
    display_name: str = Field(..., description="Human-readable permission name")
    description: Optional[str] = Field(None, description="What this permission allows")

class PermissionCreateSchema(BaseModel):
    """
    Schema for creating a new scoped permission.
    """
    name: str = Field(..., description="Permission name without scope prefix (e.g., 'analytics:view')")
    display_name: str = Field(..., description="Human-readable permission name")
    description: Optional[str] = Field(None, description="What this permission allows")
    scope: PermissionScope = Field(..., description="Permission scope: system, platform, or client")

class PermissionUpdateSchema(BaseModel):
    """
    Schema for updating a permission.
    """
    name: Optional[str] = Field(None, description="Permission name without scope prefix")
    display_name: Optional[str] = Field(None, description="Human-readable permission name")
    description: Optional[str] = Field(None, description="What this permission allows")

class PermissionResponseSchema(BaseModel):
    """
    Schema for returning permission data in API responses.
    """
    id: PydanticObjectId = Field(alias="_id")
    name: str
    display_name: str
    description: Optional[str] = None
    scope: PermissionScope
    scope_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_by_client_id: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True

class AvailablePermissionsResponseSchema(BaseModel):
    """
    Schema for returning permissions available to a user, grouped by scope.
    """
    system_permissions: List[PermissionResponseSchema] = Field(default_factory=list)
    platform_permissions: List[PermissionResponseSchema] = Field(default_factory=list)
    client_permissions: List[PermissionResponseSchema] = Field(default_factory=list) 