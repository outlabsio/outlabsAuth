"""Add auth challenges for magic-link authentication.

Revision ID: 20260425_0017
Revises: 20260422_0016
Create Date: 2026-04-25 12:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260425_0017"
down_revision: Union[str, None] = "20260422_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _table_exists(schema: str | None, table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names(schema=schema))


def upgrade() -> None:
    schema = _current_schema()

    if _table_exists(schema, "auth_challenges"):
        return

    op.create_table(
        "auth_challenges",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("challenge_type", sa.String(length=50), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redirect_url", sa.String(length=2048), nullable=True),
        sa.Column("requested_ip_address", sa.String(length=45), nullable=True),
        sa.Column("requested_user_agent", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_challenges_token_hash"),
        schema=schema,
    )
    op.create_index("ix_auth_challenges_user_id", "auth_challenges", ["user_id"], schema=schema)
    op.create_index(
        "ix_auth_challenges_type_expires_at",
        "auth_challenges",
        ["challenge_type", "expires_at"],
        schema=schema,
    )
    op.create_index("ix_auth_challenges_used_at", "auth_challenges", ["used_at"], schema=schema)


def downgrade() -> None:
    schema = _current_schema()

    if _table_exists(schema, "auth_challenges"):
        op.drop_table("auth_challenges", schema=schema)
