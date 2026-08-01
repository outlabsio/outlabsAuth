"""Add integration principal role assignments.

Revision ID: 20260415_0014
Revises: 20260406_0013
Create Date: 2026-04-15 17:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260415_0014"
down_revision: Union[str, None] = "20260406_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _table_exists(schema: str | None, table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names(schema=schema))


def _index_exists(schema: str | None, table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {
        index["name"] for index in inspector.get_indexes(table_name, schema=schema)
    }


def upgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "integration_principal_roles"):
        op.create_table(
            "integration_principal_roles",
            sa.Column("integration_principal_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["integration_principal_id"],
                ["integration_principals.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["role_id"],
                ["roles.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("integration_principal_id", "role_id"),
            schema=schema,
        )

    if not _index_exists(schema, "integration_principal_roles", "ix_integration_principal_roles_principal_id"):
        op.create_index(
            "ix_integration_principal_roles_principal_id",
            "integration_principal_roles",
            ["integration_principal_id"],
            unique=False,
            schema=schema,
        )

    if not _index_exists(schema, "integration_principal_roles", "ix_integration_principal_roles_role_id"):
        op.create_index(
            "ix_integration_principal_roles_role_id",
            "integration_principal_roles",
            ["role_id"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()

    if _table_exists(schema, "integration_principal_roles"):
        if _index_exists(schema, "integration_principal_roles", "ix_integration_principal_roles_role_id"):
            op.drop_index(
                "ix_integration_principal_roles_role_id",
                table_name="integration_principal_roles",
                schema=schema,
            )

        if _index_exists(schema, "integration_principal_roles", "ix_integration_principal_roles_principal_id"):
            op.drop_index(
                "ix_integration_principal_roles_principal_id",
                table_name="integration_principal_roles",
                schema=schema,
            )

        op.drop_table("integration_principal_roles", schema=schema)
