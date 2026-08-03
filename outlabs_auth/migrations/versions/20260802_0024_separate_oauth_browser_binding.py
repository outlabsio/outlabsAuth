"""Separate OAuth browser binding from the OIDC nonce.

Revision ID: 20260802_0024
Revises: 20260729_0023
Create Date: 2026-08-02 18:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260802_0024"
down_revision: Union[str, None] = "20260729_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _column_exists(schema: str | None, table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name, schema=schema)
    }


def upgrade() -> None:
    schema = _current_schema()
    if not _column_exists(schema, "oauth_states", "browser_binding"):
        op.add_column(
            "oauth_states",
            sa.Column("browser_binding", sa.String(255), nullable=True),
            schema=schema,
        )
        # Preserve in-flight pre-migration states. They expire after ten minutes,
        # but copying the old overloaded nonce avoids an unnecessary login break.
        table = sa.table(
            "oauth_states",
            sa.column("nonce", sa.String(255)),
            sa.column("browser_binding", sa.String(255)),
            schema=schema,
        )
        op.execute(table.update().values(browser_binding=table.c.nonce))
        op.execute(table.update().values(nonce=None))


def downgrade() -> None:
    schema = _current_schema()
    if _column_exists(schema, "oauth_states", "browser_binding"):
        # Restore the browser binding to the legacy overloaded nonce column.
        table = sa.table(
            "oauth_states",
            sa.column("nonce", sa.String(255)),
            sa.column("browser_binding", sa.String(255)),
            schema=schema,
        )
        op.execute(table.update().values(nonce=table.c.browser_binding))
        op.drop_column("oauth_states", "browser_binding", schema=schema)
