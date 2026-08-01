"""Drop redundant single-column indexes on uniquely-constrained columns.

Revision ID: 20260422_0016
Revises: 20260422_0015
Create Date: 2026-04-22 12:30:00.000000+00:00

``UniqueConstraint`` in Postgres already materializes a btree index, so the
additional ``ix_users_email`` and ``ix_entities_slug`` indexes are pure
overhead: extra writes on every INSERT / UPDATE and extra pages on disk for
no planner benefit. Drop them.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260422_0016"
down_revision: Union[str, None] = "20260422_0015"
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

    if _index_exists(schema, "users", "ix_users_email"):
        op.drop_index("ix_users_email", table_name="users", schema=schema)

    if _index_exists(schema, "entities", "ix_entities_slug"):
        op.drop_index("ix_entities_slug", table_name="entities", schema=schema)


def downgrade() -> None:
    schema = _current_schema()

    if not _index_exists(schema, "users", "ix_users_email"):
        op.create_index(
            "ix_users_email",
            "users",
            ["email"],
            unique=False,
            schema=schema,
        )

    if not _index_exists(schema, "entities", "ix_entities_slug"):
        op.create_index(
            "ix_entities_slug",
            "entities",
            ["slug"],
            unique=False,
            schema=schema,
        )
