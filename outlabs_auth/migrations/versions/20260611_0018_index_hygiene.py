"""Index hygiene: drop duplicate btrees, add missing token/tag-link indexes.

Revision ID: 20260611_0018
Revises: 20260425_0017
Create Date: 2026-06-11 12:00:00.000000+00:00

2026-06 performance audit (Phase 4). Verified against the rendered DDL:

Dropped (write amplification — each is an identical or prefix-redundant btree
maintained on every INSERT/UPDATE of hot-write tables):
  - api_keys: the column-level UNIQUE(prefix) and ix_api_keys_prefix — three
    identical btrees existed alongside uq_api_keys_prefix
  - refresh_tokens: the column-level UNIQUE(token_hash) duplicate of
    uq_refresh_tokens_hash (maintained on every login)
  - permissions.ix_permissions_name / permission_tags.ix_permission_tags_name
    (duplicates of their unique constraints)
  - entity_closure.ix_closure_ancestor_id / ix_closure_descendant_id (leading
    prefixes of the composite (id, depth) indexes; closure inserts are
    O(depth x subtree) rows per entity create/move)
  - entity_memberships.ix_em_user_id / user_role_memberships.ix_urm_user_id
    (leading prefixes of uq_*(user_id, ...) and ix_*_user_status)

Added:
  - partial indexes on users.password_reset_token / users.invite_token —
    reset-password and accept-invite are unauthenticated, attacker-reachable
    endpoints that previously sequentially scanned the users table per attempt
  - permission_tag_links.tag_id — the composite PK leads with permission_id,
    leaving tag-driven joins uncovered
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260611_0018"
down_revision: Union[str, None] = "20260425_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_schema() -> str | None:
    return context.get_context().version_table_schema


def _index_exists(schema: str | None, table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name, schema=schema)}


def _drop_index_if_exists(schema: str | None, table_name: str, index_name: str) -> None:
    if _index_exists(schema, table_name, index_name):
        op.drop_index(index_name, table_name=table_name, schema=schema)


def _duplicate_unique_constraints(
    schema: str | None,
    table_name: str,
    columns: list[str],
    keep_name: str,
) -> list[str]:
    """Names of unique constraints on exactly ``columns`` other than ``keep_name``.

    The duplicates came from column-level ``unique=True`` next to an explicit
    named ``UniqueConstraint``; Postgres auto-named them (e.g.
    ``api_keys_prefix_key``), so they are located by column set rather than by
    a hardcoded name.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return [
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name, schema=schema)
        if constraint.get("column_names") == columns and constraint.get("name") and constraint["name"] != keep_name
    ]


def upgrade() -> None:
    schema = _current_schema()

    # --- duplicate unique constraints (column-level unique=True leftovers) ---
    for name in _duplicate_unique_constraints(schema, "api_keys", ["prefix"], "uq_api_keys_prefix"):
        op.drop_constraint(name, "api_keys", type_="unique", schema=schema)
    for name in _duplicate_unique_constraints(schema, "refresh_tokens", ["token_hash"], "uq_refresh_tokens_hash"):
        op.drop_constraint(name, "refresh_tokens", type_="unique", schema=schema)

    # --- redundant plain indexes ---
    _drop_index_if_exists(schema, "api_keys", "ix_api_keys_prefix")
    _drop_index_if_exists(schema, "permissions", "ix_permissions_name")
    _drop_index_if_exists(schema, "permission_tags", "ix_permission_tags_name")
    _drop_index_if_exists(schema, "entity_closure", "ix_closure_ancestor_id")
    _drop_index_if_exists(schema, "entity_closure", "ix_closure_descendant_id")
    _drop_index_if_exists(schema, "entity_memberships", "ix_em_user_id")
    _drop_index_if_exists(schema, "user_role_memberships", "ix_urm_user_id")

    # --- missing indexes ---
    if not _index_exists(schema, "users", "ix_users_password_reset_token"):
        op.create_index(
            "ix_users_password_reset_token",
            "users",
            ["password_reset_token"],
            unique=False,
            schema=schema,
            postgresql_where=sa.text("password_reset_token IS NOT NULL"),
        )
    if not _index_exists(schema, "users", "ix_users_invite_token"):
        op.create_index(
            "ix_users_invite_token",
            "users",
            ["invite_token"],
            unique=False,
            schema=schema,
            postgresql_where=sa.text("invite_token IS NOT NULL"),
        )
    if not _index_exists(schema, "permission_tag_links", "ix_permission_tag_links_tag_id"):
        op.create_index(
            "ix_permission_tag_links_tag_id",
            "permission_tag_links",
            ["tag_id"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    schema = _current_schema()

    _drop_index_if_exists(schema, "permission_tag_links", "ix_permission_tag_links_tag_id")
    _drop_index_if_exists(schema, "users", "ix_users_invite_token")
    _drop_index_if_exists(schema, "users", "ix_users_password_reset_token")

    if not _index_exists(schema, "user_role_memberships", "ix_urm_user_id"):
        op.create_index("ix_urm_user_id", "user_role_memberships", ["user_id"], unique=False, schema=schema)
    if not _index_exists(schema, "entity_memberships", "ix_em_user_id"):
        op.create_index("ix_em_user_id", "entity_memberships", ["user_id"], unique=False, schema=schema)
    if not _index_exists(schema, "entity_closure", "ix_closure_descendant_id"):
        op.create_index("ix_closure_descendant_id", "entity_closure", ["descendant_id"], unique=False, schema=schema)
    if not _index_exists(schema, "entity_closure", "ix_closure_ancestor_id"):
        op.create_index("ix_closure_ancestor_id", "entity_closure", ["ancestor_id"], unique=False, schema=schema)
    if not _index_exists(schema, "permission_tags", "ix_permission_tags_name"):
        op.create_index("ix_permission_tags_name", "permission_tags", ["name"], unique=False, schema=schema)
    if not _index_exists(schema, "permissions", "ix_permissions_name"):
        op.create_index("ix_permissions_name", "permissions", ["name"], unique=False, schema=schema)
    if not _index_exists(schema, "api_keys", "ix_api_keys_prefix"):
        op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"], unique=False, schema=schema)

    # The duplicate column-level unique constraints are intentionally NOT
    # recreated on downgrade: they were redundant with the named constraints
    # and carried no semantics of their own.
