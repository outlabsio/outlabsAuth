"""Add integration principals and dual-owner API keys.

Revision ID: 20260406_0013
Revises: 20260326_0012
Create Date: 2026-04-06 11:15:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260406_0013"
down_revision: Union[str, None] = "20260326_0012"
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


def _index_exists(schema: str | None, table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {
        index["name"] for index in inspector.get_indexes(table_name, schema=schema)
    }


def _check_constraint_exists(schema: str | None, table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_check_constraints(table_name, schema=schema)
    }


def _qualified_table(schema: str | None, table_name: str) -> str:
    if schema:
        return f'"{schema}"."{table_name}"'
    return f'"{table_name}"'


def upgrade() -> None:
    schema = _current_schema()

    if not _table_exists(schema, "integration_principals"):
        op.create_table(
            "integration_principals",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.String(length=1000), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("scope_kind", sa.String(length=40), nullable=False),
            sa.Column("anchor_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("inherit_from_tree", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "allowed_scopes",
                postgresql.ARRAY(sa.String(length=100)),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.ForeignKeyConstraint(["anchor_entity_id"], ["entities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )

    if not _index_exists(schema, "integration_principals", "ix_integration_principals_name"):
        op.create_index(
            "ix_integration_principals_name",
            "integration_principals",
            ["name"],
            unique=False,
            schema=schema,
        )
    if not _index_exists(schema, "integration_principals", "ix_integration_principals_status"):
        op.create_index(
            "ix_integration_principals_status",
            "integration_principals",
            ["status"],
            unique=False,
            schema=schema,
        )
    if not _index_exists(schema, "integration_principals", "ix_integration_principals_scope_kind"):
        op.create_index(
            "ix_integration_principals_scope_kind",
            "integration_principals",
            ["scope_kind"],
            unique=False,
            schema=schema,
        )
    if not _index_exists(schema, "integration_principals", "ix_integration_principals_anchor_entity_id"):
        op.create_index(
            "ix_integration_principals_anchor_entity_id",
            "integration_principals",
            ["anchor_entity_id"],
            unique=False,
            schema=schema,
        )

    if not _table_exists(schema, "api_keys"):
        return

    if not _column_exists(schema, "api_keys", "integration_principal_id"):
        op.add_column(
            "api_keys",
            sa.Column("integration_principal_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
        op.create_foreign_key(
            "fk_api_keys_integration_principal_id_integration_principals",
            "api_keys",
            "integration_principals",
            ["integration_principal_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
            ondelete="CASCADE",
        )

    if _column_exists(schema, "api_keys", "owner_id"):
        op.alter_column(
            "api_keys",
            "owner_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=True,
            schema=schema,
        )

    if not _index_exists(schema, "api_keys", "ix_api_keys_integration_principal_id"):
        op.create_index(
            "ix_api_keys_integration_principal_id",
            "api_keys",
            ["integration_principal_id"],
            unique=False,
            schema=schema,
        )

    if not _check_constraint_exists(schema, "api_keys", "ck_api_keys_exactly_one_owner"):
        op.create_check_constraint(
            "ck_api_keys_exactly_one_owner",
            "api_keys",
            "(owner_id IS NOT NULL AND integration_principal_id IS NULL) OR "
            "(owner_id IS NULL AND integration_principal_id IS NOT NULL)",
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()

    if _table_exists(schema, "api_keys"):
        if _check_constraint_exists(schema, "api_keys", "ck_api_keys_exactly_one_owner"):
            op.drop_constraint("ck_api_keys_exactly_one_owner", "api_keys", type_="check", schema=schema)

        if _column_exists(schema, "api_keys", "integration_principal_id"):
            qualified_api_keys = _qualified_table(schema, "api_keys")
            op.execute(sa.text(f"DELETE FROM {qualified_api_keys} WHERE owner_id IS NULL"))

        if _index_exists(schema, "api_keys", "ix_api_keys_integration_principal_id"):
            op.drop_index("ix_api_keys_integration_principal_id", table_name="api_keys", schema=schema)

        if _column_exists(schema, "api_keys", "integration_principal_id"):
            op.drop_constraint(
                "fk_api_keys_integration_principal_id_integration_principals",
                "api_keys",
                type_="foreignkey",
                schema=schema,
            )
            op.drop_column("api_keys", "integration_principal_id", schema=schema)

        if _column_exists(schema, "api_keys", "owner_id"):
            op.alter_column(
                "api_keys",
                "owner_id",
                existing_type=postgresql.UUID(as_uuid=True),
                nullable=False,
                schema=schema,
            )

    if _table_exists(schema, "integration_principals"):
        if _index_exists(schema, "integration_principals", "ix_integration_principals_anchor_entity_id"):
            op.drop_index(
                "ix_integration_principals_anchor_entity_id",
                table_name="integration_principals",
                schema=schema,
            )
        if _index_exists(schema, "integration_principals", "ix_integration_principals_scope_kind"):
            op.drop_index(
                "ix_integration_principals_scope_kind",
                table_name="integration_principals",
                schema=schema,
            )
        if _index_exists(schema, "integration_principals", "ix_integration_principals_status"):
            op.drop_index(
                "ix_integration_principals_status",
                table_name="integration_principals",
                schema=schema,
            )
        if _index_exists(schema, "integration_principals", "ix_integration_principals_name"):
            op.drop_index(
                "ix_integration_principals_name",
                table_name="integration_principals",
                schema=schema,
            )
        op.drop_table("integration_principals", schema=schema)
