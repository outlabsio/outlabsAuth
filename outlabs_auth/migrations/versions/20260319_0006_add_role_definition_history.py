"""Add role definition history table.

Revision ID: 20260319_0006
Revises: 20260319_0005
Create Date: 2026-03-19 00:06:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260319_0006"
down_revision: Union[str, None] = "20260319_0005"
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
    if _table_exists(schema, "role_definition_history"):
        return

    op.create_table(
        "role_definition_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "root_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "scope_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column(
            "event_source",
            sa.String(length=100),
            server_default=sa.text("'role_history_service'"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("role_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("role_display_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("role_description_snapshot", sa.String(length=1000), nullable=True),
        sa.Column("root_entity_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("scope_entity_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("is_system_role_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_global_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("scope_snapshot", sa.String(length=20), nullable=False),
        sa.Column("is_auto_assigned_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "assignable_at_types_snapshot",
            postgresql.ARRAY(sa.String(length=50)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "permission_ids_snapshot",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column(
            "permission_names_snapshot",
            postgresql.ARRAY(sa.String(length=255)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "entity_type_permissions_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )

    op.create_index(
        "ix_rdh_role_occurred_at",
        "role_definition_history",
        ["role_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_rdh_actor_occurred_at",
        "role_definition_history",
        ["actor_user_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_rdh_root_occurred_at",
        "role_definition_history",
        ["root_entity_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_rdh_scope_occurred_at",
        "role_definition_history",
        ["scope_entity_id", "occurred_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_rdh_event_type",
        "role_definition_history",
        ["event_type"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _current_schema()
    if not _table_exists(schema, "role_definition_history"):
        return

    op.drop_index("ix_rdh_event_type", table_name="role_definition_history", schema=schema)
    op.drop_index("ix_rdh_scope_occurred_at", table_name="role_definition_history", schema=schema)
    op.drop_index("ix_rdh_root_occurred_at", table_name="role_definition_history", schema=schema)
    op.drop_index("ix_rdh_actor_occurred_at", table_name="role_definition_history", schema=schema)
    op.drop_index("ix_rdh_role_occurred_at", table_name="role_definition_history", schema=schema)
    op.drop_table("role_definition_history", schema=schema)
