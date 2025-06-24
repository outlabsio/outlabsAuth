from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from beanie import PydanticObjectId
from ..models.scopes import GroupScope

class GroupCreateSchema(BaseModel):
    """
    Schema for creating a new scoped group with direct permissions.
    """
    name: str = Field(..., description="Group name (e.g., 'Sales Team', 'Customer Support')")
    display_name: str = Field(..., description="Human-readable group name")
    description: Optional[str] = Field(None, description="Group purpose and responsibilities")
    permissions: List[str] = Field(default_factory=list, description="List of permission IDs")
    scope: GroupScope = Field(..., description="Group scope: system, platform, or client")
    # scope_id determined by service based on user context

class GroupUpdateSchema(BaseModel):
    """
    Schema for updating a group. All fields are optional.
    """
    name: Optional[str] = Field(None, description="Group name")
    display_name: Optional[str] = Field(None, description="Human-readable group name")
    description: Optional[str] = Field(None, description="Group purpose and responsibilities")
    permissions: Optional[List[str]] = Field(None, description="List of permission IDs")
    is_active: Optional[bool] = Field(None, description="Whether the group is active")

class GroupResponseSchema(BaseModel):
    """
    Schema for returning group data in API responses.
    """
    id: PydanticObjectId = Field(..., alias="_id")
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[str]
    scope: GroupScope
    scope_id: Optional[str] = None
    is_active: bool
    created_by_user_id: Optional[str] = None
    created_by_client_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class AvailableGroupsResponseSchema(BaseModel):
    """
    Schema for returning groups available to a user, grouped by scope.
    """
    system_groups: List[GroupResponseSchema] = Field(default_factory=list)
    platform_groups: List[GroupResponseSchema] = Field(default_factory=list)
    client_groups: List[GroupResponseSchema] = Field(default_factory=list)

class GroupMembershipSchema(BaseModel):
    """
    Schema for managing group memberships.
    """
    user_ids: List[str] = Field(..., description="List of user IDs to add/remove")

class GroupMembersResponseSchema(BaseModel):
    """
    Schema for returning group members.
    """
    group_id: str
    group_name: str
    group_scope: GroupScope
    members: List[dict]  # Will contain user details

class UserGroupsResponseSchema(BaseModel):
    """
    Schema for returning a user's group memberships.
    """
    user_id: str
    groups: List[GroupResponseSchema]
    effective_permissions: List[str]  # All permissions from groups + direct roles 