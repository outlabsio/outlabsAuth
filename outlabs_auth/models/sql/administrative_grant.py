"""Separate administrative policy storage; ordinary roles cannot assign it.

Rows retain authority lineage. The initial service supports platform-managed
human grants, exact actions and pinned group admissions only. No runtime route
uses these rows until the remaining S2 admission gates are qualified.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from outlabs_auth.database.base import BaseModel


class AdministrativeTemplateRevision(BaseModel, table=True):
    __tablename__ = "auth_administrative_template_revisions"
    __table_args__ = (
        UniqueConstraint("template_key", "revision", name="uq_auth_admin_template_revision"),
        CheckConstraint("revision > 0", name="ck_auth_admin_template_revision"),
    )
    template_key: str = Field(sa_column=Column(String(100), nullable=False))
    revision: int = Field(sa_column=Column(Integer, nullable=False))
    policy: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    policy_hash: str = Field(sa_column=Column(String(64), nullable=False))
    active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))


class AdministrativeGroup(BaseModel, table=True):
    __tablename__ = "auth_administrative_groups"
    __table_args__ = (UniqueConstraint("group_key", name="uq_auth_admin_group_key"),)
    group_key: str = Field(sa_column=Column(String(100), nullable=False))
    active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))


class AdministrativeAdmission(BaseModel, table=True):
    __tablename__ = "auth_administrative_admissions"
    __table_args__ = (
        Index("ix_auth_admin_admission_group_root", "group_id", "customer_root_id"),
        Index(
            "uq_auth_admin_open_admission",
            "group_id",
            "customer_root_id",
            unique=True,
            postgresql_where=Column("closed_at", DateTime(timezone=True)).is_(None),
        ),
    )
    group_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("auth_administrative_groups.id", ondelete="RESTRICT"), nullable=False
        )
    )
    customer_root_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    )
    closed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class AdministrativeGrantRecord(BaseModel, table=True):
    __tablename__ = "auth_administrative_grants"
    __table_args__ = (
        UniqueConstraint("request_key", name="uq_auth_admin_grant_request"),
        CheckConstraint("selector_kind IN ('entity', 'subtree', 'group')", name="ck_auth_admin_selector_kind"),
        CheckConstraint(
            "(selector_kind = 'group' AND group_id IS NOT NULL AND entity_id IS NULL) OR "
            "(selector_kind IN ('entity', 'subtree') AND entity_id IS NOT NULL AND group_id IS NULL)",
            name="ck_auth_admin_selector_exclusive",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_from < valid_until", name="ck_auth_admin_window"
        ),
        Index("ix_auth_admin_grant_actor_window", "user_id", "revoked_at", "valid_until"),
    )
    user_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    )
    template_revision_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("auth_administrative_template_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    selector_kind: str = Field(sa_column=Column(String(20), nullable=False))
    entity_id: UUID | None = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("entities.id", ondelete="RESTRICT"), nullable=True),
    )
    group_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("auth_administrative_groups.id", ondelete="RESTRICT"), nullable=True
        ),
    )
    admission_ids: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    request_key: str = Field(sa_column=Column(String(100), nullable=False))
    request_hash: str = Field(sa_column=Column(String(64), nullable=False))
    reason: str = Field(sa_column=Column(String(500), nullable=False))
    grantor_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False))
    valid_from: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    valid_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class AdministrativeAudit(BaseModel, table=True):
    """Security lineage snapshots without cascading identity foreign keys."""

    __tablename__ = "auth_administrative_audit"
    __table_args__ = (Index("ix_auth_admin_audit_subject", "subject_id", "created_at"),)
    actor_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False))
    subject_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False))
    event_type: str = Field(sa_column=Column(String(100), nullable=False))
    evidence: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
