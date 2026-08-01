"""User Role Membership request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.schemas.role import RoleResponse


class UserRoleMembershipResponse(BaseModel):
    """User role membership response schema (safe to expose)."""

    id: str
    user_id: str
    role_id: str
    assigned_at: datetime
    assigned_by_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    status: MembershipStatus
    revoked_at: Optional[datetime] = None
    revoked_by_id: Optional[str] = None
    revocation_reason: Optional[str] = None
    is_currently_valid: bool
    can_grant_permissions: bool

    model_config = ConfigDict(from_attributes=True)


class UserRoleMembershipDetailResponse(UserRoleMembershipResponse):
    """User role membership response with embedded role details."""

    role: RoleResponse


class UserRoleMembershipCreate(BaseModel):
    """User role membership creation request schema."""

    user_id: str = Field(..., description="User ID to assign role to")
    role_id: str = Field(..., description="Role ID to assign")
    assigned_by_id: Optional[str] = Field(
        None, description="User ID who assigned this role (for audit)"
    )
    valid_from: Optional[datetime] = Field(
        None, description="Optional start date for role validity"
    )
    valid_until: Optional[datetime] = Field(
        None, description="Optional end date for role validity"
    )


class UserRoleMembershipUpdate(BaseModel):
    """User role membership update request schema."""

    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    status: Optional[MembershipStatus] = None


class AssignRoleRequest(BaseModel):
    """Simplified request for assigning a role to a user."""

    role_id: str = Field(..., description="Role ID to assign")
    valid_from: Optional[datetime] = Field(
        None, description="Optional start date for role validity"
    )
    valid_until: Optional[datetime] = Field(
        None,
        description="Optional end date for role validity (e.g., 90-day contractor)",
    )


class RevokeRoleRequest(BaseModel):
    """Request for revoking a role from a user."""

    role_id: str = Field(..., description="Role ID to revoke")
