from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
from beanie import PydanticObjectId
from .permission_schema import PermissionDetailSchema

class RoleScope(str, Enum):
    """Role scope enumeration"""
    SYSTEM = "system"
    PLATFORM = "platform" 
    CLIENT = "client"

class RoleCreateSchema(BaseModel):
    """
    Schema for creating a new role.
    Frontend provides permission names, backend converts to ObjectIds.
    """
    name: str = Field(..., description="Role name (e.g., 'admin', 'manager')")
    display_name: str = Field(..., description="Human-readable role name")
    description: Optional[str] = Field(None, description="Role purpose and capabilities")
    permissions: List[str] = Field(default_factory=list, description="List of permission names")
    scope: RoleScope = Field(..., description="Role scope: system, platform, or client")
    is_assignable_by_main_client: bool = Field(False, description="Can client admins assign this role?")

class RoleUpdateSchema(BaseModel):
    """
    Schema for updating a role. All fields are optional.
    Note: scope and scope_id cannot be changed after creation.
    """
    name: Optional[str] = Field(None, description="Role name")
    display_name: Optional[str] = Field(None, description="Human-readable role name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: Optional[List[str]] = Field(None, description="List of permission names")
    is_assignable_by_main_client: Optional[bool] = Field(None, description="Can client admins assign this role?")

class RoleResponseSchema(BaseModel):
    """
    Schema for returning role data in API responses.
    Returns full permission details with both ID and name.
    """
    id: PydanticObjectId = Field(..., alias="_id", description="Role ID")
    name: str = Field(..., description="Role name")
    display_name: str = Field(..., description="Human-readable role name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: List[PermissionDetailSchema] = Field(..., description="Permission details with ID and name")
    scope: RoleScope = Field(..., description="Role scope")
    scope_id: Optional[str] = Field(None, description="Scope owner ID")
    is_assignable_by_main_client: bool = Field(..., description="Can client admins assign this role?")
    created_by_user_id: Optional[str] = Field(None, description="User who created this role")
    created_by_client_id: Optional[str] = Field(None, description="Client that created this role")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True
        populate_by_name = True

class AvailableRolesResponseSchema(BaseModel):
    """
    Schema for returning roles available to assign, grouped by scope.
    """
    system_roles: List[RoleResponseSchema] = Field(default_factory=list)
    platform_roles: List[RoleResponseSchema] = Field(default_factory=list) 
    client_roles: List[RoleResponseSchema] = Field(default_factory=list) 