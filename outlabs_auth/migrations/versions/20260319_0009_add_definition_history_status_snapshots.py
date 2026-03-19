"""Add lifecycle status snapshot columns to definition history tables.

Revision ID: 20260319_0009
Revises: 20260319_0008
Create Date: 2026-03-19 00:09:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260319_0009"
down_revision: Union[str, None] = "20260319_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _table_exists(schema: str | None, table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names(schema=schema))


def _column_exists(schema: str | None, table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name, schema=schema)
    }


def _qualified_name(schema: str | None, table_name: str) -> str:
    if schema:
        return f'"{schema}"."{table_name}"'
    return f'"{table_name}"'


def upgrade() -> None:
    schema = _current_schema()

    if _table_exists(schema, "role_definition_history") and not _column_exists(
        schema, "role_definition_history", "status_snapshot"
    ):
        op.add_column(
            "role_definition_history",
            sa.Column(
                "status_snapshot",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            schema=schema,
        )

    if _table_exists(schema, "permission_definition_history") and not _column_exists(
        schema, "permission_definition_history", "status_snapshot"
    ):
        op.add_column(
            "permission_definition_history",
            sa.Column(
                "status_snapshot",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            schema=schema,
        )

    if _table_exists(schema, "role_definition_history") and _column_exists(
        schema, "role_definition_history", "status_snapshot"
    ):
        op.execute(
            sa.text(
                f"UPDATE {_qualified_name(schema, 'role_definition_history')} "
                "SET status_snapshot = COALESCE("
                "NULLIF(\"after\" ->> 'status', ''), "
                "NULLIF(\"before\" ->> 'status', ''), "
                "'active'"
                ")"
            )
        )

    if _table_exists(schema, "permission_definition_history") and _column_exists(
        schema, "permission_definition_history", "status_snapshot"
    ):
        op.execute(
            sa.text(
                f"UPDATE {_qualified_name(schema, 'permission_definition_history')} "
                "SET status_snapshot = COALESCE("
                "NULLIF(\"after\" ->> 'status', ''), "
                "NULLIF(\"before\" ->> 'status', ''), "
                "CASE WHEN is_active_snapshot THEN 'active' ELSE 'inactive' END"
                ")"
            )
        )


def downgrade() -> None:
    schema = _current_schema()

    if _table_exists(schema, "permission_definition_history") and _column_exists(
        schema, "permission_definition_history", "status_snapshot"
    ):
        op.drop_column("permission_definition_history", "status_snapshot", schema=schema)

    if _table_exists(schema, "role_definition_history") and _column_exists(
        schema, "role_definition_history", "status_snapshot"
    ):
        op.drop_column("role_definition_history", "status_snapshot", schema=schema)
