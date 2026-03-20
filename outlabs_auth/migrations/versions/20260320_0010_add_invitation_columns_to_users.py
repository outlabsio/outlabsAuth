"""Add invitation columns to users for adopted legacy schemas.

Revision ID: 20260320_0010
Revises: 20260319_0009
Create Date: 2026-03-20 13:40:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260320_0010"
down_revision: Union[str, None] = "20260319_0009"
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


def _fk_exists(schema: str | None, table_name: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return fk_name in {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name, schema=schema)
    }


def upgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "users"):
        return

    if not _column_exists(schema, "users", "invite_token"):
        op.add_column(
            "users",
            sa.Column("invite_token", sa.String(length=255), nullable=True),
            schema=schema,
        )

    if not _column_exists(schema, "users", "invite_token_expires"):
        op.add_column(
            "users",
            sa.Column("invite_token_expires", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )

    if not _column_exists(schema, "users", "invited_by_id"):
        op.add_column(
            "users",
            sa.Column("invited_by_id", PG_UUID(as_uuid=True), nullable=True),
            schema=schema,
        )

    if _column_exists(schema, "users", "invited_by_id") and not _fk_exists(
        schema, "users", "fk_users_invited_by_id_users"
    ):
        op.create_foreign_key(
            "fk_users_invited_by_id_users",
            "users",
            "users",
            ["invited_by_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
            ondelete="SET NULL",
        )


def downgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "users"):
        return

    if _fk_exists(schema, "users", "fk_users_invited_by_id_users"):
        op.drop_constraint(
            "fk_users_invited_by_id_users",
            "users",
            type_="foreignkey",
            schema=schema,
        )

    if _column_exists(schema, "users", "invited_by_id"):
        op.drop_column("users", "invited_by_id", schema=schema)

    if _column_exists(schema, "users", "invite_token_expires"):
        op.drop_column("users", "invite_token_expires", schema=schema)

    if _column_exists(schema, "users", "invite_token"):
        op.drop_column("users", "invite_token", schema=schema)
