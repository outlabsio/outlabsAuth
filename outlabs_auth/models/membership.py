"""
Entity Membership Model

Represents user memberships in entities with role assignments.
Supports multiple roles per membership and time-based validity.
"""
from typing import Optional, List
from datetime import datetime, timezone
from beanie import Link
from pydantic import Field

from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.entity import EntityModel
from outlabs_auth.models.role import RoleModel


class EntityMembershipModel(BaseDocument):
    """
    User's membership in an entity with assigned roles.

    A user can be a member of multiple entities, and can have
    multiple roles within each entity.

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

    # Membership metadata
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    joined_by: Optional[Link[UserModel]] = None

    # Time-based membership (optional)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status
    is_active: bool = Field(default=True)

    def is_currently_valid(self) -> bool:
        """
        Check if membership is currently valid.

        Returns False if:
        - is_active is False
        - Current time is before valid_from
        - Current time is after valid_until

        Returns:
            bool: True if membership is valid now
        """
        if not self.is_active:
            return False

        now = datetime.now(timezone.utc)

        if self.valid_from and now < self.valid_from:
            return False

        if self.valid_until and now > self.valid_until:
            return False

        return True

    def __repr__(self) -> str:
        return f"<EntityMembershipModel(user={self.user}, entity={self.entity}, roles={len(self.roles)})>"

    class Settings:
        name = "entity_memberships"
        indexes = [
            [("user", 1), ("entity", 1)],  # Unique constraint
            "entity",  # Fast entity member lookup
            "user",  # Fast user membership lookup
            "is_active",
            [("tenant_id", 1)],  # For multi-tenant filtering
        ]
