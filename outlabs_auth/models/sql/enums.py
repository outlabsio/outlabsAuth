"""
Enum Definitions for OutlabsAuth Models

All enums used across the authentication and authorization system.
"""

from enum import Enum


class UserStatus(str, Enum):
    """User account status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"  # Temporary suspension (can be auto-lifted)
    BANNED = "banned"  # Permanent ban (manual lift required)
    DELETED = "deleted"  # Soft-deleted (for GDPR compliance)


class MembershipStatus(str, Enum):
    """
    Status of a user's membership (role assignment or entity membership).

    Only ACTIVE grants permissions. All other states block permissions
    while preserving audit trail.
    """

    ACTIVE = "active"  # Currently active, grants permissions
    SUSPENDED = "suspended"  # Paused (e.g., on leave), no permissions
    REVOKED = "revoked"  # Manually removed, no permissions
    EXPIRED = "expired"  # Auto-expired via valid_until
    PENDING = "pending"  # Awaiting approval (future use)
    REJECTED = "rejected"  # Approval denied (future use)

    def can_grant_permissions(self) -> bool:
        """Check if this status allows granting permissions."""
        return self == MembershipStatus.ACTIVE

    def is_inactive(self) -> bool:
        """Check if this status is inactive."""
        return not self.can_grant_permissions()

    @classmethod
    def active_states(cls) -> list["MembershipStatus"]:
        """Get list of states that grant permissions."""
        return [cls.ACTIVE]

    @classmethod
    def inactive_states(cls) -> list["MembershipStatus"]:
        """Get list of states that don't grant permissions."""
        return [cls.SUSPENDED, cls.REVOKED, cls.EXPIRED, cls.PENDING, cls.REJECTED]


class EntityClass(str, Enum):
    """
    Classification of entities in the hierarchy.

    - STRUCTURAL: Organizational units (company, department, team)
    - ACCESS_GROUP: Permission groupings (project, resource pool)
    """

    STRUCTURAL = "structural"
    ACCESS_GROUP = "access_group"


class APIKeyStatus(str, Enum):
    """API key lifecycle status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"  # Temporarily disabled
    REVOKED = "revoked"  # Permanently disabled
    EXPIRED = "expired"  # Past expiration date


class RoleScope(str, Enum):
    """
    Scope of an entity-local role.

    Controls BOTH where the role's permissions apply AND where auto-assignment happens.

    - ENTITY_ONLY: Role permissions and auto-assignment apply only at the scope_entity
    - HIERARCHY: Role permissions and auto-assignment apply at scope_entity AND all descendants
    """

    ENTITY_ONLY = "entity_only"  # Valid only at the defining entity
    HIERARCHY = "hierarchy"  # Valid at defining entity + all descendants


class ConditionOperator(str, Enum):
    """
    Operators for ABAC condition evaluation.

    Used in Condition objects stored as JSONB in roles/permissions.
    """

    # Equality
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"

    # Comparison (numeric/date)
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"

    # Collection
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"

    # String
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # Regex

    # Existence
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"

    # Boolean
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"

    # Time-based
    BEFORE = "before"
    AFTER = "after"
