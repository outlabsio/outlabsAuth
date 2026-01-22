"""Add system_config table for platform settings

This migration creates the system_config table for storing
key-value configuration that can be managed via UI.

Changes:
1. Create system_config table with key, value, description, updated_at, updated_by_id

Revision ID: add_system_config_table
Revises: add_root_entity_scoping
Create Date: 2026-01-22 00:02:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_system_config_table"
down_revision: Union[str, None] = "add_root_entity_scoping"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create system_config table
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_by_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Create unique index on key
    op.create_index("ix_system_config_key", "system_config", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_system_config_key", table_name="system_config")
    op.drop_table("system_config")
