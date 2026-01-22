"""Add entity-local role fields to roles table (DD-053)

This migration adds support for entity-local roles that can be:
- Defined at any entity level (not just root)
- Scoped to entity-only or hierarchy (descendants)
- Auto-assigned to members within scope

Changes:
1. Add scope_entity_id (UUID FK to entities) - entity that defines the role
2. Add scope (VARCHAR) - 'entity_only' or 'hierarchy'
3. Add is_auto_assigned (BOOLEAN) - auto-assign to members within scope
4. Add indexes for efficient queries

Revision ID: add_entity_local_roles
Revises: add_entity_child_type_config
Create Date: 2026-01-22 00:04:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_entity_local_roles"
down_revision: Union[str, None] = "add_entity_child_type_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scope_entity_id column with FK to entities
    op.add_column(
        "roles",
        sa.Column(
            "scope_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Add scope column with default 'hierarchy' for backward compatibility
    op.add_column(
        "roles",
        sa.Column(
            "scope",
            sa.String(20),
            nullable=False,
            server_default="hierarchy",
        ),
    )

    # Add is_auto_assigned column
    op.add_column(
        "roles",
        sa.Column(
            "is_auto_assigned",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Add indexes for efficient queries
    op.create_index(
        "ix_roles_scope_entity_id",
        "roles",
        ["scope_entity_id"],
    )
    op.create_index(
        "ix_roles_is_auto_assigned",
        "roles",
        ["is_auto_assigned"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_roles_is_auto_assigned", table_name="roles")
    op.drop_index("ix_roles_scope_entity_id", table_name="roles")

    # Drop columns
    op.drop_column("roles", "is_auto_assigned")
    op.drop_column("roles", "scope")
    op.drop_column("roles", "scope_entity_id")
