"""
Membership Status Enum

Defines the status of role/entity memberships for both SimpleRBAC and EnterpriseRBAC.
"""
from enum import Enum


class MembershipStatus(str, Enum):
    """
    Status of a role or entity membership assignment.

    Used by both UserRoleMembership (SimpleRBAC) and EntityMembershipModel (EnterpriseRBAC)
    to track the lifecycle of membership assignments with detailed audit trail.

    **States**:

    - **ACTIVE**: Membership is currently active and grants permissions.
      This is the normal operating state.

    - **SUSPENDED**: Membership is temporarily paused and does NOT grant permissions.
      Use cases:
      - User on leave/vacation
      - Pending investigation
      - Temporary access removal

    - **REVOKED**: Membership was manually removed by an admin and does NOT grant permissions.
      The membership record is preserved for audit trail.
      Use cases:
      - Admin removes role from user
      - User leaves team/organization
      - Security incident response

    - **EXPIRED**: Membership automatically expired based on valid_until timestamp.
      Does NOT grant permissions.
      Use cases:
      - Contractor role expires after 90 days
      - Temporary elevated permissions expire
      - Time-limited project access

    - **PENDING**: Membership is awaiting approval and does NOT grant permissions.
      (Future feature for approval workflows)
      Use cases:
      - User requests role, needs manager approval
      - Self-service role requests
      - Compliance approval workflows

    - **REJECTED**: Membership request was denied and does NOT grant permissions.
      (Future feature for approval workflows)
      Use cases:
      - Manager rejected role request
      - Failed compliance check
      - Insufficient justification

    **Transitions**:

    ```
    PENDING → ACTIVE (approved)
    PENDING → REJECTED (denied)
    ACTIVE → SUSPENDED (temporary pause)
    ACTIVE → REVOKED (manual removal)
    ACTIVE → EXPIRED (auto-expiration)
    SUSPENDED → ACTIVE (resume)
    SUSPENDED → REVOKED (remove while suspended)
    ```

    **Permission Granting**:
    - ACTIVE = ✅ Grants permissions (if time-valid)
    - SUSPENDED = ❌ Does not grant permissions
    - REVOKED = ❌ Does not grant permissions
    - EXPIRED = ❌ Does not grant permissions
    - PENDING = ❌ Does not grant permissions
    - REJECTED = ❌ Does not grant permissions

    See docs/DESIGN_DECISIONS.md (DD-047) for rationale.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"
    REJECTED = "rejected"

    def can_grant_permissions(self) -> bool:
        """
        Check if this status allows granting permissions.

        Returns:
            bool: True only if status is ACTIVE
        """
        return self == MembershipStatus.ACTIVE

    def is_inactive(self) -> bool:
        """
        Check if this status is inactive (does not grant permissions).

        Returns:
            bool: True if status is not ACTIVE
        """
        return not self.can_grant_permissions()

    @classmethod
    def active_states(cls) -> list['MembershipStatus']:
        """
        Get list of statuses that can grant permissions.

        Currently only ACTIVE, but could expand in future
        (e.g., if we add ACTIVE_PENDING_REVIEW or similar).

        Returns:
            list[MembershipStatus]: List of permission-granting statuses
        """
        return [cls.ACTIVE]

    @classmethod
    def inactive_states(cls) -> list['MembershipStatus']:
        """
        Get list of statuses that cannot grant permissions.

        Returns:
            list[MembershipStatus]: List of non-permission-granting statuses
        """
        return [cls.SUSPENDED, cls.REVOKED, cls.EXPIRED, cls.PENDING, cls.REJECTED]
