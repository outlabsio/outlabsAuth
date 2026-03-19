"""Schemas for entity membership history and orphaned-user discovery."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from outlabs_auth.schemas.user import UserResponse


class MembershipHistoryEventResponse(BaseModel):
    """Membership lifecycle history event."""

    id: str
    membership_id: str
    user_id: str
    entity_id: str
    root_entity_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    event_type: str
    event_source: str
    event_at: datetime
    reason: Optional[str] = None
    status: str
    previous_status: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    previous_valid_from: Optional[datetime] = None
    previous_valid_until: Optional[datetime] = None
    role_ids: List[str] = Field(default_factory=list)
    previous_role_ids: List[str] = Field(default_factory=list)
    role_names: List[str] = Field(default_factory=list)
    previous_role_names: List[str] = Field(default_factory=list)
    entity_display_name: Optional[str] = None
    entity_path: List[str] = Field(default_factory=list)
    root_entity_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrphanedUserResponse(BaseModel):
    """User with no active entity memberships and historical assignment context."""

    user: UserResponse
    active_membership_count: int
    total_membership_count: int
    last_membership_event_type: Optional[str] = None
    last_membership_event_at: Optional[datetime] = None
    last_entity_id: Optional[str] = None
    last_entity_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
