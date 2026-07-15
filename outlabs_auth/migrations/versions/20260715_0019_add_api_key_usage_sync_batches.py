"""Add durable API-key usage synchronization receipts.

Revision ID: 20260715_0019
Revises: 20260611_0018
Create Date: 2026-07-15 12:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "20260715_0019"
down_revision: Union[str, None] = "20260611_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _table_exists(schema: str | None, table_name: str) -> bool:
    return table_name in set(sa.inspect(op.get_bind()).get_table_names(schema=schema))


def upgrade() -> None:
    schema = _current_schema()
    if _table_exists(schema, "api_key_usage_sync_batches"):
        return

    op.create_table(
        "api_key_usage_sync_batches",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("key_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )
    op.create_index(
        "ix_api_key_usage_sync_batches_applied_at",
        "api_key_usage_sync_batches",
        ["applied_at"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _current_schema()
    if _table_exists(schema, "api_key_usage_sync_batches"):
        op.drop_table("api_key_usage_sync_batches", schema=schema)
