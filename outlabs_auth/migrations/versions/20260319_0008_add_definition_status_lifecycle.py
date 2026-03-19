"""Add lifecycle status columns for retained role and permission definitions.

Revision ID: 20260319_0008
Revises: 20260319_0007
Create Date: 2026-03-19 00:08:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260319_0008"
down_revision: Union[str, None] = "20260319_0007"
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


def _index_exists(schema: str | None, table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {
        index["name"] for index in inspector.get_indexes(table_name, schema=schema)
    }


def _qualified_name(schema: str | None, table_name: str) -> str:
    if schema:
        return f'"{schema}"."{table_name}"'
    return f'"{table_name}"'


def upgrade() -> None:
    schema = _current_schema()
    if _table_exists(schema, "roles") and not _column_exists(schema, "roles", "status"):
        op.add_column(
            "roles",
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            schema=schema,
        )

    if _table_exists(schema, "permissions") and not _column_exists(schema, "permissions", "status"):
        op.add_column(
            "permissions",
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            schema=schema,
        )

    if _table_exists(schema, "roles") and _column_exists(schema, "roles", "status"):
        op.execute(
            sa.text(
                f"UPDATE {_qualified_name(schema, 'roles')} "
                "SET status = 'active' WHERE status IS NULL OR status = ''"
            )
        )

    if _table_exists(schema, "permissions") and _column_exists(schema, "permissions", "status"):
        op.execute(
            sa.text(
                f"UPDATE {_qualified_name(schema, 'permissions')} "
                "SET status = CASE WHEN is_active THEN 'active' ELSE 'inactive' END "
                "WHERE status IS NULL OR status = ''"
            )
        )

    if _table_exists(schema, "roles") and not _index_exists(schema, "roles", "ix_roles_status"):
        op.create_index(
            "ix_roles_status",
            "roles",
            ["status"],
            unique=False,
            schema=schema,
        )

    if _table_exists(schema, "permissions") and not _index_exists(
        schema, "permissions", "ix_permissions_status"
    ):
        op.create_index(
            "ix_permissions_status",
            "permissions",
            ["status"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()

    if _table_exists(schema, "permissions") and _index_exists(
        schema, "permissions", "ix_permissions_status"
    ):
        op.drop_index(
            "ix_permissions_status",
            table_name="permissions",
            schema=schema,
        )

    if _table_exists(schema, "roles") and _index_exists(schema, "roles", "ix_roles_status"):
        op.drop_index(
            "ix_roles_status",
            table_name="roles",
            schema=schema,
        )

    if _table_exists(schema, "permissions") and _column_exists(schema, "permissions", "status"):
        op.drop_column("permissions", "status", schema=schema)

    if _table_exists(schema, "roles") and _column_exists(schema, "roles", "status"):
        op.drop_column("roles", "status", schema=schema)
