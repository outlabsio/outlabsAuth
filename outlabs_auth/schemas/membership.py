"""Membership request/response schemas."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class MembershipResponse(BaseModel):

    id: str
    entity_id: str
    user_id: str
    role_ids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MembershipCreateRequest(BaseModel):
    """Add user to entity with roles."""

    user_id: str
    entity_id: str
    role_ids: List[str] = Field(default_factory=list)


class MembershipUpdateRequest(BaseModel):
    """Update user's roles in an entity."""

    """Update user's roles in an entity."""
    role_ids: List[str]
