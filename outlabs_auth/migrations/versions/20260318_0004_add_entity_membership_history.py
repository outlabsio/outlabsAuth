"""Add entity membership history table.

Revision ID: 20260318_0004
Revises: 20260317_0003
Create Date: 2026-03-18 00:04:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260318_0004"
down_revision: Union[str, None] = "20260317_0003"
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
    if _table_exists(schema, "entity_membership_history"):
        return

    op.create_table(
        "entity_membership_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entity_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "root_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column(
            "event_source",
            sa.String(length=100),
            server_default=sa.text("'membership_service'"),
            nullable=False,
        ),
        sa.Column(
            "event_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("valid_from", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("previous_valid_from", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("previous_valid_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "role_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column(
            "previous_role_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column(
            "role_names",
            postgresql.ARRAY(sa.String(length=255)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "previous_role_names",
            postgresql.ARRAY(sa.String(length=255)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("entity_display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "entity_path",
            postgresql.ARRAY(sa.String(length=255)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("root_entity_name", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )

    op.create_index(
        "ix_emh_membership_event_at",
        "entity_membership_history",
        ["membership_id", "event_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_emh_user_event_at",
        "entity_membership_history",
        ["user_id", "event_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_emh_entity_event_at",
        "entity_membership_history",
        ["entity_id", "event_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_emh_root_entity_event_at",
        "entity_membership_history",
        ["root_entity_id", "event_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_emh_event_type",
        "entity_membership_history",
        ["event_type"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _current_schema()
    if not _table_exists(schema, "entity_membership_history"):
        return

    op.drop_index("ix_emh_event_type", table_name="entity_membership_history", schema=schema)
    op.drop_index("ix_emh_root_entity_event_at", table_name="entity_membership_history", schema=schema)
    op.drop_index("ix_emh_entity_event_at", table_name="entity_membership_history", schema=schema)
    op.drop_index("ix_emh_user_event_at", table_name="entity_membership_history", schema=schema)
    op.drop_index("ix_emh_membership_event_at", table_name="entity_membership_history", schema=schema)
    op.drop_table("entity_membership_history", schema=schema)
