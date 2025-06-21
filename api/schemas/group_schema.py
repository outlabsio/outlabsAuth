from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class GroupCreateSchema(BaseModel):
    """
    Schema for creating a new group.
    """
    name: str
    description: Optional[str] = None
    client_account_id: str  # String ID for client account
    roles: Optional[List[str]] = []

class GroupUpdateSchema(BaseModel):
    """
    Schema for updating a group. All fields are optional.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None

class GroupResponseSchema(BaseModel):
    """
    Schema for returning group data in API responses.
    """
    _id: str  # MongoDB native _id field
    name: str
    description: Optional[str] = None
    client_account_id: Optional[str] = None
    roles: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class GroupMembershipSchema(BaseModel):
    """
    Schema for managing group memberships.
    """
    user_ids: List[str]  # List of user IDs to add/remove

class GroupMembersResponseSchema(BaseModel):
    """
    Schema for returning group members.
    """
    group_id: str
    group_name: str
    members: List[dict]  # Will contain user details

class UserGroupsResponseSchema(BaseModel):
    """
    Schema for returning a user's group memberships.
    """
    user_id: str
    groups: List[GroupResponseSchema]
    effective_roles: List[str]  # All roles from groups + direct roles
    effective_permissions: List[str]  # All permissions from effective roles 