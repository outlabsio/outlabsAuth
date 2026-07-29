"""Add azp (authorized-party frontend profile) to refresh tokens (DD-059 slice 4).

Revision ID: 20260729_0023
Revises: 20260729_0022
Create Date: 2026-07-29 18:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260729_0023"
down_revision: Union[str, None] = "20260729_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _column_exists(schema: str | None, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name, schema=schema)}


def upgrade() -> None:
    schema = _current_schema()
    if not _column_exists(schema, "refresh_tokens", "azp"):
        op.add_column(
            "refresh_tokens",
            sa.Column("azp", sa.String(64), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()
    if _column_exists(schema, "refresh_tokens", "azp"):
        op.drop_column("refresh_tokens", "azp", schema=schema)
