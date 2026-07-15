"""Add refresh-token rotation families and replacement links.

Revision ID: 20260715_0020
Revises: 20260715_0019
Create Date: 2026-07-15 12:05:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "20260715_0020"
down_revision: Union[str, None] = "20260715_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _column_exists(schema: str | None, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name, schema=schema)}


def _index_exists(schema: str | None, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name, schema=schema)}


def _foreign_key_exists(schema: str | None, table_name: str, name: str) -> bool:
    return name in {fk.get("name") for fk in sa.inspect(op.get_bind()).get_foreign_keys(table_name, schema=schema)}


def upgrade() -> None:
    schema = _current_schema()
    if not _column_exists(schema, "refresh_tokens", "family_id"):
        op.add_column("refresh_tokens", sa.Column("family_id", PG_UUID(as_uuid=True), nullable=True), schema=schema)
        qualified = f'"{schema}"."refresh_tokens"' if schema else "refresh_tokens"
        op.execute(sa.text(f"UPDATE {qualified} SET family_id = id WHERE family_id IS NULL"))
        op.alter_column("refresh_tokens", "family_id", nullable=False, schema=schema)
    if not _column_exists(schema, "refresh_tokens", "replaced_by_token_id"):
        op.add_column(
            "refresh_tokens",
            sa.Column("replaced_by_token_id", PG_UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
    if not _foreign_key_exists(schema, "refresh_tokens", "fk_refresh_tokens_replaced_by"):
        op.create_foreign_key(
            "fk_refresh_tokens_replaced_by",
            "refresh_tokens",
            "refresh_tokens",
            ["replaced_by_token_id"],
            ["id"],
            ondelete="SET NULL",
            source_schema=schema,
            referent_schema=schema,
        )
    if not _index_exists(schema, "refresh_tokens", "ix_refresh_tokens_family_id"):
        op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], schema=schema)


def downgrade() -> None:
    schema = _current_schema()
    if _index_exists(schema, "refresh_tokens", "ix_refresh_tokens_family_id"):
        op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens", schema=schema)
    if _foreign_key_exists(schema, "refresh_tokens", "fk_refresh_tokens_replaced_by"):
        op.drop_constraint("fk_refresh_tokens_replaced_by", "refresh_tokens", type_="foreignkey", schema=schema)
    if _column_exists(schema, "refresh_tokens", "replaced_by_token_id"):
        op.drop_column("refresh_tokens", "replaced_by_token_id", schema=schema)
    if _column_exists(schema, "refresh_tokens", "family_id"):
        op.drop_column("refresh_tokens", "family_id", schema=schema)
