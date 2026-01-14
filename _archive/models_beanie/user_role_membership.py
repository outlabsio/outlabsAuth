"""
User Role Membership Model

Represents user role assignments in SimpleRBAC (flat structure, no entity context).
Provides audit trail and consistency with EnterpriseRBAC's EntityMembership pattern.
"""
from typing import Optional
from datetime import datetime, timezone
from beanie import Link
from pydantic import Field

from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.membership_status import MembershipStatus


class UserRoleMembership(BaseDocument):
    """
    User's role assignment in SimpleRBAC (flat structure).

    This provides the same membership pattern as EnterpriseRBAC's EntityMembership,
    but without entity context. This ensures:
    - Architectural consistency between SimpleRBAC and EnterpriseRBAC
    - Full audit trail (who assigned, when assigned)
    - Time-based role assignments (temporary access)
    - Seamless migration path from SimpleRBAC → EnterpriseRBAC

    Example:
        User "alice@example.com" is assigned role "admin" by "bob@example.com"
        on 2025-01-14 at 10:00 UTC, valid for 90 days.

    See DD-047 in docs/DESIGN_DECISIONS.md for rationale.
    """

    # Relationships
    user: Link[UserModel] = Field(description="User who is assigned the role")
    role: Link[RoleModel] = Field(description="Role being assigned to the user")

    # Assignment metadata (audit trail)
    assigned_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the role was assigned"
    )
    assigned_by: Optional[Link[UserModel]] = Field(
        default=None,
        description="User who assigned this role (for audit trail)"
    )

    # Time-based validity (optional)
    valid_from: Optional[datetime] = Field(
        default=None,
        description="Optional start date for role validity"
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        description="Optional end date for role validity (e.g., 90-day contractor access)"
    )

    # Status
    status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE,
        description="Current status of the role assignment"
    )

    # Revocation metadata (when status=REVOKED)
    revoked_at: Optional[datetime] = Field(
        default=None,
        description="When the role was revoked (if status=REVOKED)"
    )
    revoked_by: Optional[Link[UserModel]] = Field(
        default=None,
        description="User who revoked this role (if status=REVOKED)"
    )

    def is_currently_valid(self) -> bool:
        """
        Check if role assignment is currently valid based on time windows.

        This checks time-based validity (valid_from/valid_until) but does NOT
        check status. Use can_grant_permissions() to check both status and validity.

        Returns False if:
        - Current time is before valid_from
        - Current time is after valid_until

        Returns:
            bool: True if role assignment is within its valid time window
        """
        now = datetime.now(timezone.utc)

        if self.valid_from and now < self.valid_from:
            return False

        if self.valid_until and now > self.valid_until:
            return False

        return True

    def can_grant_permissions(self) -> bool:
        """
        Check if membership can currently grant permissions.

        Returns True only if:
        - Status is ACTIVE
        - Time-based validity check passes (if applicable)

        This is the method to use when checking if a user should get
        permissions from this role membership.

        Returns:
            bool: True if membership can grant permissions right now
        """
        if self.status != MembershipStatus.ACTIVE:
            return False

        return self.is_currently_valid()

    def __repr__(self) -> str:
        return f"<UserRoleMembership(user={self.user}, role={self.role}, status={self.status.value})>"

    class Settings:
        name = "user_role_memberships"
        indexes = [
            [("user", 1), ("role", 1)],  # Unique constraint: user can only have role assigned once
            [("user", 1), ("status", 1)],  # Fast lookup of roles by status for user
            "role",  # Fast lookup of users with a specific role
            "status",  # Fast filtering by membership status
            "valid_until",  # For cleanup jobs to expire old assignments
            [("tenant_id", 1)],  # For multi-tenant filtering (optional)
        ]
