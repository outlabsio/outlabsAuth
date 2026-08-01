"""Add API key kind column.

Revision ID: 20260326_0012
Revises: 20260320_0011
Create Date: 2026-03-26 15:10:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260326_0012"
down_revision: Union[str, None] = "20260320_0011"
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


def upgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "api_keys"):
        return

    if not _column_exists(schema, "api_keys", "key_kind"):
        op.add_column(
            "api_keys",
            sa.Column(
                "key_kind",
                sa.String(length=40),
                nullable=False,
                server_default="personal",
            ),
            schema=schema,
        )

    if not _index_exists(schema, "api_keys", "ix_api_keys_key_kind"):
        op.create_index(
            "ix_api_keys_key_kind",
            "api_keys",
            ["key_kind"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "api_keys"):
        return

    if _index_exists(schema, "api_keys", "ix_api_keys_key_kind"):
        op.drop_index("ix_api_keys_key_kind", table_name="api_keys", schema=schema)

    if _column_exists(schema, "api_keys", "key_kind"):
        op.drop_column("api_keys", "key_kind", schema=schema)
