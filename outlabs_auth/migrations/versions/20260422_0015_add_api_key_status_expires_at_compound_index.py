"""Consolidate api_keys status/expires_at indexes into a compound index.

Revision ID: 20260422_0015
Revises: 20260415_0014
Create Date: 2026-04-22 12:00:00.000000+00:00

Motivation: the API-key authentication hot path filters by
``status = 'active' AND (expires_at IS NULL OR expires_at > now())``.
A single compound index on ``(status, expires_at)`` serves both the
status-only lookup (leftmost prefix) and the combined filter, so the
previous pair of single-column indexes is redundant.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260422_0015"
down_revision: Union[str, None] = "20260415_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _index_exists(schema: str | None, table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {
        index["name"] for index in inspector.get_indexes(table_name, schema=schema)
    }


def upgrade() -> None:
    schema = _current_schema()

    if not _index_exists(schema, "api_keys", "ix_api_keys_status_expires_at"):
        op.create_index(
            "ix_api_keys_status_expires_at",
            "api_keys",
            ["status", "expires_at"],
            unique=False,
            schema=schema,
        )

    if _index_exists(schema, "api_keys", "ix_api_keys_status"):
        op.drop_index("ix_api_keys_status", table_name="api_keys", schema=schema)

    if _index_exists(schema, "api_keys", "ix_api_keys_expires_at"):
        op.drop_index("ix_api_keys_expires_at", table_name="api_keys", schema=schema)


def downgrade() -> None:
    schema = _current_schema()

    if not _index_exists(schema, "api_keys", "ix_api_keys_status"):
        op.create_index(
            "ix_api_keys_status",
            "api_keys",
            ["status"],
            unique=False,
            schema=schema,
        )

    if not _index_exists(schema, "api_keys", "ix_api_keys_expires_at"):
        op.create_index(
            "ix_api_keys_expires_at",
            "api_keys",
            ["expires_at"],
            unique=False,
            schema=schema,
        )

    if _index_exists(schema, "api_keys", "ix_api_keys_status_expires_at"):
        op.drop_index(
            "ix_api_keys_status_expires_at",
            table_name="api_keys",
            schema=schema,
        )
