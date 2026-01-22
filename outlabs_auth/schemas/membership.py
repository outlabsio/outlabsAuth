"""Membership request/response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from outlabs_auth.schemas.role import RoleSummary


class MembershipResponse(BaseModel):
    """Basic membership response (IDs only)."""

    id: str
    entity_id: str
    user_id: str
    role_ids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EntityMemberResponse(BaseModel):
    """
    Rich membership response with user and role details.

    Used when listing members of an entity.
    """

    id: str  # membership ID
    user_id: str
    user_email: str
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_status: str
    roles: List[RoleSummary] = Field(default_factory=list)
    status: str  # membership status (active, suspended, etc.)
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipCreateRequest(BaseModel):
    """Add user to entity with roles."""

    user_id: str
    entity_id: str
    role_ids: List[str] = Field(default_factory=list)


class MembershipUpdateRequest(BaseModel):
    """Update user's roles in an entity."""

    role_ids: List[str]
