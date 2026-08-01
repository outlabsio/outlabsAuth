"""Add user audit events table.

Revision ID: 20260319_0005
Revises: 20260318_0004
Create Date: 2026-03-19 00:05:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260319_0005"
down_revision: Union[str, None] = "20260318_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _table_exists(schema: str | None, table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names(schema=schema))


def upgrade() -> None:
    schema = _current_schema()
    if _table_exists(schema, "user_audit_events"):
        return

    op.create_table(
        "user_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("event_category", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "event_source",
            sa.String(length=100),
            server_default=sa.text("'user_audit_service'"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("subject_email_snapshot", sa.String(length=255), nullable=False),
        sa.Column(
            "root_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )

    op.create_index(
        "ix_uae_subject_occurred_at",
        "user_audit_events",
        ["subject_user_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_uae_root_occurred_at",
        "user_audit_events",
        ["root_entity_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_uae_entity_occurred_at",
        "user_audit_events",
        ["entity_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_uae_role_occurred_at",
        "user_audit_events",
        ["role_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_uae_event_category",
        "user_audit_events",
        ["event_category"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_uae_event_type",
        "user_audit_events",
        ["event_type"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _current_schema()
    if not _table_exists(schema, "user_audit_events"):
        return

    op.drop_index("ix_uae_event_type", table_name="user_audit_events", schema=schema)
    op.drop_index("ix_uae_event_category", table_name="user_audit_events", schema=schema)
    op.drop_index("ix_uae_role_occurred_at", table_name="user_audit_events", schema=schema)
    op.drop_index("ix_uae_entity_occurred_at", table_name="user_audit_events", schema=schema)
    op.drop_index("ix_uae_root_occurred_at", table_name="user_audit_events", schema=schema)
    op.drop_index("ix_uae_subject_occurred_at", table_name="user_audit_events", schema=schema)
    op.drop_table("user_audit_events", schema=schema)
