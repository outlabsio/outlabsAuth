"""Add allowed_child_types and allowed_child_classes columns to entities

This migration adds columns for configuring which child entity types
are allowed under a root entity.

Changes:
1. Add allowed_child_types (ARRAY of String) to entities table
2. Add allowed_child_classes (ARRAY of String) to entities table

Revision ID: add_entity_child_type_config
Revises: add_system_config_table
Create Date: 2026-01-22 00:03:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_entity_child_type_config"
down_revision: Union[str, None] = "add_system_config_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add allowed_child_types column
    op.add_column(
        "entities",
        sa.Column(
            "allowed_child_types",
            ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
    )

    # Add allowed_child_classes column
    op.add_column(
        "entities",
        sa.Column(
            "allowed_child_classes",
            ARRAY(sa.String(20)),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("entities", "allowed_child_classes")
    op.drop_column("entities", "allowed_child_types")
