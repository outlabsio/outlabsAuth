"""Add root_entity_id to users, rename entity_id to root_entity_id on roles

This migration implements role scoping to root entities (top-level organizations)
so that different organizations have isolated role sets.

Changes:
1. Add root_entity_id to users table - explicit binding of users to their organization
2. Rename entity_id to root_entity_id on roles table - clearer semantics
3. Make existing roles with NULL root_entity_id global

Revision ID: add_root_entity_scoping
Revises: fd27d12e791e
Create Date: 2026-01-22 00:01:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_root_entity_scoping"
down_revision: Union[str, None] = "fd27d12e791e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add root_entity_id to users table
    op.add_column(
        "users", sa.Column("root_entity_id", PG_UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_users_root_entity_id",
        "users",
        "entities",
        ["root_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_root_entity_id", "users", ["root_entity_id"])

    # 2. Rename entity_id to root_entity_id on roles table
    # First, drop the old index
    op.drop_index("ix_roles_entity_id", table_name="roles")

    # Rename the column
    op.alter_column("roles", "entity_id", new_column_name="root_entity_id")

    # Create new index with correct name
    op.create_index("ix_roles_root_entity_id", "roles", ["root_entity_id"])

    # 3. Make existing roles with NULL root_entity_id global
    # This ensures roles without a root entity are available everywhere
    op.execute("""
        UPDATE roles
        SET is_global = TRUE
        WHERE root_entity_id IS NULL AND is_global = FALSE
    """)


def downgrade() -> None:
    # 1. Revert roles table: rename root_entity_id back to entity_id
    op.drop_index("ix_roles_root_entity_id", table_name="roles")
    op.alter_column("roles", "root_entity_id", new_column_name="entity_id")
    op.create_index("ix_roles_entity_id", "roles", ["entity_id"])

    # 2. Remove root_entity_id from users table
    op.drop_index("ix_users_root_entity_id", table_name="users")
    op.drop_constraint("fk_users_root_entity_id", "users", type_="foreignkey")
    op.drop_column("users", "root_entity_id")

    # Note: We don't revert the is_global changes as they're data-specific
    # and the original values are unknown
