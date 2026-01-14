"""
Entity Membership Model

Represents user memberships in entities with role assignments.
Supports multiple roles per membership and time-based validity.
"""

from datetime import datetime, timezone
from typing import List, Optional

from beanie import Link
from pydantic import Field

from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.entity import EntityModel
from outlabs_auth.models.membership_status import MembershipStatus
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.user import UserModel


class EntityMembershipModel(BaseDocument):
    """
    User's membership in an entity with assigned roles.

    A user can be a member of multiple entities, and can have
    multiple roles within each entity.

    Uses MembershipStatus enum for rich lifecycle tracking (DD-047).

    Example:
        User "alice" is a member of "engineering" entity with roles:
        - "developer" (read/write code)
        - "team_lead" (manage team members)
    """

    # Relationships
    user: Link[UserModel]
    entity: Link[EntityModel]

    # Multiple roles per membership (EnterpriseRBAC feature)
    roles: List[Link[RoleModel]] = Field(default_factory=list)

    # Membership metadata (audit trail)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    joined_by: Optional[Link[UserModel]] = None

    # Time-based membership (optional)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status (uses MembershipStatus enum)
    status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE, description="Current status of the membership"
    )

    # Revocation metadata (when status=REVOKED)
    revoked_at: Optional[datetime] = Field(
        default=None, description="When the membership was revoked (if status=REVOKED)"
    )
    revoked_by: Optional[Link[UserModel]] = Field(
        default=None, description="User who revoked this membership (if status=REVOKED)"
    )

    def is_currently_valid(self) -> bool:
        """
        Check if membership is currently valid based on time windows.

        This checks time-based validity (valid_from/valid_until) but does NOT
        check status. Use can_grant_permissions() to check both status and validity.

        Returns False if:
        - Current time is before valid_from
        - Current time is after valid_until

        Returns:
            bool: True if membership is within its valid time window
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
        permissions from this membership.

        Returns:
            bool: True if membership can grant permissions right now
        """
        if self.status != MembershipStatus.ACTIVE:
            return False

        return self.is_currently_valid()

    def __repr__(self) -> str:
        return f"<EntityMembershipModel(user={self.user}, entity={self.entity}, roles={len(self.roles)})>"

    class Settings:
        name = "entity_memberships"
        indexes = [
            [("user", 1), ("entity", 1)],  # Unique constraint
            [
                ("user", 1),
                ("status", 1),
            ],  # Fast lookup of memberships by status for user
            "entity",  # Fast entity member lookup
            "user",  # Fast user membership lookup
            "status",  # Fast filtering by membership status
            "valid_until",  # For cleanup jobs to expire old memberships
            [("tenant_id", 1)],  # For multi-tenant filtering
        ]
