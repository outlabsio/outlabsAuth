"""Membership request/response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.schemas.role import RoleSummary


class MembershipResponse(BaseModel):
    """Membership response with lifecycle metadata."""

    id: str
    entity_id: str
    user_id: str
    role_ids: List[str] = Field(default_factory=list)
    status: str
    effective_status: str
    joined_at: datetime
    joined_by_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by_id: Optional[str] = None
    revocation_reason: Optional[str] = None
    is_currently_valid: bool
    can_grant_permissions: bool

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
    effective_status: str
    joined_at: datetime
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MembershipCreateRequest(BaseModel):
    """Add user to entity with roles and optional lifecycle settings."""

    user_id: str
    entity_id: str
    role_ids: List[str] = Field(default_factory=list)
    status: MembershipStatus = MembershipStatus.ACTIVE
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: MembershipStatus) -> MembershipStatus:
        """Only active and suspended memberships are created directly."""
        if value not in {MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED}:
            raise ValueError("Membership status must be 'active' or 'suspended' when creating a membership")
        return value

    @field_validator("valid_until")
    @classmethod
    def validate_valid_until(cls, value: Optional[datetime], info) -> Optional[datetime]:
        """Ensure validity windows are ordered."""
        valid_from = info.data.get("valid_from")
        if value and valid_from and value < valid_from:
            raise ValueError("valid_until must be after valid_from")
        return value


class MembershipUpdateRequest(BaseModel):
    """Update user's membership lifecycle and/or role set in an entity."""

    role_ids: Optional[List[str]] = None
    status: Optional[MembershipStatus] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[MembershipStatus]) -> Optional[MembershipStatus]:
        """Only active and suspended are updated via PATCH; DELETE handles revocation."""
        if value is None:
            return value
        if value not in {MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED}:
            raise ValueError("Membership status must be 'active' or 'suspended'; use DELETE to revoke a membership")
        return value

    @field_validator("valid_until")
    @classmethod
    def validate_valid_until(cls, value: Optional[datetime], info) -> Optional[datetime]:
        """Ensure validity windows are ordered when both are provided."""
        valid_from = info.data.get("valid_from")
        if value and valid_from and value < valid_from:
            raise ValueError("valid_until must be after valid_from")
        return value
