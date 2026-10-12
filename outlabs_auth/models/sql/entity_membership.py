"""
EntityMembership Model (EnterpriseRBAC)

User membership in entities with role assignments.
"""

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, Index, UniqueConstraint, ForeignKey, String, DateTime, Boolean, BigInteger, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel
from .enums import MembershipStatus

if TYPE_CHECKING:
    from .user import User
    from .entity import Entity
    from .role import Role


# === Junction Table: EntityMembership ↔ Role ===
class EntityMembershipRole(SQLModel, table=True):
    """
    Junction table for entity membership roles.

    A user's membership in an entity can have multiple roles.

    Table: entity_membership_roles
    """

    __tablename__ = "entity_membership_roles"
    __table_args__ = (
        Index("ix_emr_membership_id", "membership_id"),
        Index("ix_emr_role_id", "role_id"),
    )

    membership_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entity_memberships.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    role_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    native_owned: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))


class MembershipSourceClaim(SQLModel, table=True):
    """One opaque, stable source relationship owns an attachment and role subset.

    Host crosswalks resolve source IDs; these claims never own account state.
    """

    __tablename__ = "membership_source_claims"
    source_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    membership_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("entity_memberships.id", ondelete="RESTRICT"), nullable=False, index=True
        )
    )


class MembershipSourceRole(SQLModel, table=True):
    __tablename__ = "membership_source_roles"
    source_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("membership_source_claims.source_id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    role_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)
    )


class MembershipSourceWithdrawal(SQLModel, table=True):
    """Standing source-only withdrawal proof; survives a native hard deletion."""

    __tablename__ = "membership_source_withdrawals"
    user_id: UUID = Field(primary_key=True)
    entity_id: UUID = Field(primary_key=True)
    membership_id: UUID
    revision: int = Field(sa_column=Column(BigInteger, nullable=False))
    user_epoch: int = Field(sa_column=Column(BigInteger, nullable=False))


class EntityMembership(BaseModel, table=True):
    """
    User membership in an entity (EnterpriseRBAC).

    Represents a user's membership in an organizational entity,
    along with the roles they have within that entity.

    Table: entity_memberships
    """

    __tablename__ = "entity_memberships"
    __table_args__ = (
        # uq(user_id, entity_id) and ix_em_user_status both cover user_id via
        # their leading prefix; the single-column index was redundant.
        UniqueConstraint("user_id", "entity_id", name="uq_entity_membership"),
        Index("ix_em_entity_id", "entity_id"),
        Index("ix_em_user_status", "user_id", "status"),
        Index("ix_em_status", "status"),
        Index("ix_em_valid_until", "valid_until"),
    )
    native_owned: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))
    write_revision: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default=text("0")))

    # === Foreign Keys ===
    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    entity_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # === Membership Audit ===
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    joined_by_id: Optional[UUID] = Field(
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
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
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
        sa_relationship_kwargs={"foreign_keys": "[EntityMembership.user_id]"},
    )
    entity: "Entity" = Relationship(back_populates="memberships")
    roles: List["Role"] = Relationship(
        link_model=EntityMembershipRole,
    )

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

    def get_role_names(self) -> List[str]:
        """Get names of all roles in this membership."""
        return [role.name for role in self.roles]
