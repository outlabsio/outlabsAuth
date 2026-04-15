"""
Integration principal model.

Non-human durable owners for admin-managed system integration API keys.
"""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship, SQLModel

from outlabs_auth.database.base import BaseModel

from .enums import IntegrationPrincipalScopeKind, IntegrationPrincipalStatus

if TYPE_CHECKING:
    from .api_key import APIKey
    from .entity import Entity
    from .role import Role
    from .user import User


class IntegrationPrincipalRole(SQLModel, table=True):
    """Junction table linking integration principals to roles."""

    __tablename__ = "integration_principal_roles"
    __table_args__ = (
        Index("ix_integration_principal_roles_principal_id", "integration_principal_id"),
        Index("ix_integration_principal_roles_role_id", "role_id"),
    )

    integration_principal_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("integration_principals.id", ondelete="CASCADE"),
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


class IntegrationPrincipal(BaseModel, table=True):
    """
    Non-human durable identity used to own system integration API keys.

    Table: integration_principals
    """

    __tablename__ = "integration_principals"
    __table_args__ = (
        Index("ix_integration_principals_name", "name"),
        Index("ix_integration_principals_status", "status"),
        Index("ix_integration_principals_scope_kind", "scope_kind"),
        Index("ix_integration_principals_anchor_entity_id", "anchor_entity_id"),
    )

    name: str = Field(
        sa_column=Column(String(200), nullable=False),
        description="Human-readable integration principal name",
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(1000), nullable=True),
    )
    status: IntegrationPrincipalStatus = Field(
        default=IntegrationPrincipalStatus.ACTIVE,
        sa_column=Column(String(20), nullable=False, default=IntegrationPrincipalStatus.ACTIVE.value),
    )
    scope_kind: IntegrationPrincipalScopeKind = Field(
        sa_column=Column(String(40), nullable=False),
        description="Entity-scoped or platform-global principal",
    )
    anchor_entity_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="Anchor entity for entity-scoped principals",
    )
    inherit_from_tree: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False),
        description="Whether entity-scoped principals may access descendant entities",
    )
    allowed_scopes: List[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(String(100)),
            nullable=False,
            server_default="{}",
        ),
        description="Upper bound of scopes any key owned by this principal may hold",
    )
    created_by_user_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="Human actor who created this principal",
    )

    api_keys: List["APIKey"] = Relationship(
        back_populates="integration_principal",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    anchor_entity: Optional["Entity"] = Relationship(
        back_populates="integration_principals",
        sa_relationship_kwargs={"foreign_keys": "[IntegrationPrincipal.anchor_entity_id]"},
    )
    created_by_user: Optional["User"] = Relationship(
        back_populates="created_integration_principals",
        sa_relationship_kwargs={"foreign_keys": "[IntegrationPrincipal.created_by_user_id]"},
    )
    roles: List["Role"] = Relationship(
        back_populates="integration_principals",
        link_model=IntegrationPrincipalRole,
    )

    @property
    def status_enum(self) -> IntegrationPrincipalStatus:
        """Return status as an enum even when the ORM loads raw strings."""
        if isinstance(self.status, IntegrationPrincipalStatus):
            return self.status
        return IntegrationPrincipalStatus(str(self.status))

    @property
    def scope_kind_enum(self) -> IntegrationPrincipalScopeKind:
        """Return scope_kind as an enum even when the ORM loads raw strings."""
        if isinstance(self.scope_kind, IntegrationPrincipalScopeKind):
            return self.scope_kind
        return IntegrationPrincipalScopeKind(str(self.scope_kind))

    def is_active(self) -> bool:
        """Only active principals can authenticate via owned API keys."""
        return self.status_enum == IntegrationPrincipalStatus.ACTIVE
