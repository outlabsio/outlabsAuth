"""Add assignable_at_types to roles.

Revision ID: 20260317_0003
Revises: 20260317_0002
Create Date: 2026-03-17 00:03:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260317_0003"
down_revision: Union[str, None] = "20260317_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _has_column(
    inspector: sa.Inspector,
    table_name: str,
    column_name: str,
    schema: str | None,
) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name, schema=schema))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    schema = _current_schema()

    if _has_column(inspector, "roles", "assignable_at_types", schema):
        return

    op.add_column(
        "roles",
        sa.Column(
            "assignable_at_types",
            sa.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        schema=schema,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    schema = _current_schema()

    if _has_column(inspector, "roles", "assignable_at_types", schema):
        op.drop_column("roles", "assignable_at_types", schema=schema)
