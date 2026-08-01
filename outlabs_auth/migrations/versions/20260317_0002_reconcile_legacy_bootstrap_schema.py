"""Reconcile legacy bootstrap schemas with the squashed baseline.

Revision ID: 20260317_0002
Revises: 20260316_0001
Create Date: 2026-03-17 00:02:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260317_0002"
down_revision: Union[str, None] = "20260316_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANTLESS_TABLES = (
    "users",
    "roles",
    "permissions",
    "permission_tags",
    "permission_conditions",
    "auth_challenges",
    "refresh_tokens",
    "api_keys",
    "social_accounts",
    "oauth_states",
    "activity_metrics",
    "user_activities",
    "login_history",
    "entities",
    "entity_closure",
    "entity_memberships",
    "user_role_memberships",
    "role_conditions",
    "role_entity_type_permissions",
    "condition_groups",
)


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _has_column(
    inspector: sa.Inspector,
    table_name: str,
    column_name: str,
    schema: str | None,
) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name, schema=schema))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    schema = _current_schema()
    table_names = set(inspector.get_table_names(schema=schema))

    for table_name in TENANTLESS_TABLES:
        if table_name not in table_names:
            continue
        if _has_column(inspector, table_name, "tenant_id", schema):
            op.drop_column(table_name, "tenant_id", schema=schema)

    if "social_accounts" not in table_names:
        return

    if not _has_column(inspector, "social_accounts", "provider_email_verified", schema):
        op.add_column(
            "social_accounts",
            sa.Column("provider_email_verified", sa.Boolean(), nullable=True),
            schema=schema,
        )
        qualified_table = f'"{schema}"."social_accounts"' if schema else "social_accounts"
        op.execute(
            sa.text(
                f"UPDATE {qualified_table} SET provider_email_verified = FALSE WHERE provider_email_verified IS NULL"
            )
        )
        op.alter_column(
            "social_accounts",
            "provider_email_verified",
            existing_type=sa.Boolean(),
            nullable=False,
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    schema = _current_schema()
    table_names = set(inspector.get_table_names(schema=schema))

    if "social_accounts" in table_names and _has_column(
        inspector,
        "social_accounts",
        "provider_email_verified",
        schema,
    ):
        op.drop_column("social_accounts", "provider_email_verified", schema=schema)

    for table_name in TENANTLESS_TABLES:
        if table_name not in table_names:
            continue
        if not _has_column(inspector, table_name, "tenant_id", schema):
            op.add_column(
                table_name,
                sa.Column("tenant_id", sa.String(length=36), nullable=True),
                schema=schema,
            )
