"""
UserRoleMembership Model (SimpleRBAC)

Junction table for user-to-role assignments in flat RBAC structure.
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, Index, UniqueConstraint, ForeignKey, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel
from .enums import MembershipStatus

if TYPE_CHECKING:
    from .user import User
    from .role import Role


class UserRoleMembership(BaseModel, table=True):
    """
    User-to-role membership for SimpleRBAC.

    Represents a user's assignment to a role with:
    - Time-based validity (valid_from, valid_until)
    - Status management (active, suspended, revoked, etc.)
    - Audit trail (assigned_by, revoked_by)

    Table: user_role_memberships
    """
    __tablename__ = "user_role_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role_membership"),
        Index("ix_urm_user_id", "user_id"),
        Index("ix_urm_role_id", "role_id"),
        Index("ix_urm_user_status", "user_id", "status"),
        Index("ix_urm_status", "status"),
        Index("ix_urm_valid_until", "valid_until"),
    )

    # === Foreign Keys ===
    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    role_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # === Assignment Audit ===
    assigned_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    assigned_by_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # === Time-Based Validity ===
    valid_from: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Start of validity period (null = immediately)",
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="End of validity period (null = indefinite)",
    )

    # === Status ===
    status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE,
        sa_column=Column(String(20), nullable=False, default="active"),
    )

    # === Revocation Audit ===
    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    revoked_by_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    revocation_reason: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )

    # === Relationships ===
    user: "User" = Relationship(
        back_populates="role_memberships",
        sa_relationship_kwargs={"foreign_keys": "[UserRoleMembership.user_id]"},
    )
    role: "Role" = Relationship(back_populates="user_memberships")

    # === Methods ===
    def is_currently_valid(self) -> bool:
        """Check if membership is within its validity period."""
        now = datetime.now(timezone.utc)
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    def can_grant_permissions(self) -> bool:
        """Check if this membership should grant permissions."""
        if self.status != MembershipStatus.ACTIVE:
            return False
        return self.is_currently_valid()

    def revoke(self, revoked_by_id: Optional[UUID] = None, reason: Optional[str] = None) -> None:
        """Revoke this membership."""
        self.status = MembershipStatus.REVOKED
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_by_id = revoked_by_id
        self.revocation_reason = reason

    def suspend(self) -> None:
        """Suspend this membership."""
        self.status = MembershipStatus.SUSPENDED

    def reactivate(self) -> None:
        """Reactivate a suspended membership."""
        self.status = MembershipStatus.ACTIVE
        self.revoked_at = None
        self.revoked_by_id = None
        self.revocation_reason = None
