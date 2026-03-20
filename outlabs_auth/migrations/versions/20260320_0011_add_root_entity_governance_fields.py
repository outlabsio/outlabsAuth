"""Add root entity governance columns for naming rules.

Revision ID: 20260320_0011
Revises: 20260320_0010
Create Date: 2026-03-20 16:20:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260320_0011"
down_revision: Union[str, None] = "20260320_0010"
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


def upgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "entities"):
        return

    if not _column_exists(schema, "entities", "child_name_pattern"):
        op.add_column(
            "entities",
            sa.Column("child_name_pattern", sa.String(length=255), nullable=True),
            schema=schema,
        )

    if not _column_exists(schema, "entities", "child_display_name_pattern"):
        op.add_column(
            "entities",
            sa.Column("child_display_name_pattern", sa.String(length=255), nullable=True),
            schema=schema,
        )

    if not _column_exists(schema, "entities", "child_slug_pattern"):
        op.add_column(
            "entities",
            sa.Column("child_slug_pattern", sa.String(length=255), nullable=True),
            schema=schema,
        )

    if not _column_exists(schema, "entities", "child_naming_guidance"):
        op.add_column(
            "entities",
            sa.Column("child_naming_guidance", sa.String(length=1000), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "entities"):
        return

    if _column_exists(schema, "entities", "child_naming_guidance"):
        op.drop_column("entities", "child_naming_guidance", schema=schema)

    if _column_exists(schema, "entities", "child_slug_pattern"):
        op.drop_column("entities", "child_slug_pattern", schema=schema)

    if _column_exists(schema, "entities", "child_display_name_pattern"):
        op.drop_column("entities", "child_display_name_pattern", schema=schema)

    if _column_exists(schema, "entities", "child_name_pattern"):
        op.drop_column("entities", "child_name_pattern", schema=schema)
