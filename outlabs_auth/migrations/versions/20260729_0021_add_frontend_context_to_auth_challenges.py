"""Add frontend profile + canonical next_url to auth challenges (DD-059 slice 2).

Revision ID: 20260729_0021
Revises: 20260715_0020
Create Date: 2026-07-29 12:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260729_0021"
down_revision: Union[str, None] = "20260715_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _column_exists(schema: str | None, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name, schema=schema)}


def upgrade() -> None:
    schema = _current_schema()
    if not _column_exists(schema, "auth_challenges", "profile_id"):
        op.add_column(
            "auth_challenges",
            sa.Column("profile_id", sa.String(64), nullable=True),
            schema=schema,
        )
    if not _column_exists(schema, "auth_challenges", "next_url"):
        op.add_column(
            "auth_challenges",
            sa.Column("next_url", sa.String(2048), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()
    if _column_exists(schema, "auth_challenges", "next_url"):
        op.drop_column("auth_challenges", "next_url", schema=schema)
    if _column_exists(schema, "auth_challenges", "profile_id"):
        op.drop_column("auth_challenges", "profile_id", schema=schema)
