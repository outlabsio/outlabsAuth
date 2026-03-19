from __future__ import annotations

from sqlalchemy import Index
from sqlalchemy.schema import ForeignKeyConstraint, UniqueConstraint


def _get_table(name: str):
    # Import loads SQLModel metadata via model modules.
    from sqlmodel import SQLModel

    import outlabs_auth.models.sql  # noqa: F401

    return SQLModel.metadata.tables[name]


def _fk_ondelete(table, column: str) -> str | None:
    for fk in table.foreign_keys:
        if fk.parent.name == column:
            return fk.ondelete
    return None


def _has_unique(table, *columns: str) -> bool:
    want = tuple(columns)
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            got = tuple(col.name for col in constraint.columns)
            if got == want:
                return True
    return False


def _has_index(table, name: str, *columns: str) -> bool:
    want = tuple(columns)
    for idx in table.indexes:
        if isinstance(idx, Index) and idx.name == name:
            got = tuple(col.name for col in idx.columns)
            return got == want
    return False


def _has_column(table, column: str) -> bool:
    return column in table.c


def test_entity_closure_has_fks_unique_and_indexes():
    table = _get_table("entity_closure")

    assert _has_unique(table, "ancestor_id", "descendant_id")
    assert _fk_ondelete(table, "ancestor_id") == "CASCADE"
    assert _fk_ondelete(table, "descendant_id") == "CASCADE"

    assert _has_index(table, "ix_closure_ancestor_id", "ancestor_id")
    assert _has_index(table, "ix_closure_descendant_id", "descendant_id")
    assert _has_index(table, "ix_closure_ancestor_depth", "ancestor_id", "depth")
    assert _has_index(table, "ix_closure_descendant_depth", "descendant_id", "depth")
    assert not _has_column(table, "tenant_id")


def test_entities_parent_fk_is_set_null():
    table = _get_table("entities")
    assert _fk_ondelete(table, "parent_id") == "SET NULL"
    assert _has_unique(table, "slug")
    assert not _has_column(table, "tenant_id")
    assert not _has_column(table, "direct_permissions")
    assert not _has_column(table, "metadata")


def test_entity_membership_constraints_and_join_table_cascades():
    memberships = _get_table("entity_memberships")
    assert _has_unique(memberships, "user_id", "entity_id")
    assert _fk_ondelete(memberships, "user_id") == "CASCADE"
    assert _fk_ondelete(memberships, "entity_id") == "CASCADE"

    join = _get_table("entity_membership_roles")
    assert _fk_ondelete(join, "membership_id") == "CASCADE"
    assert _fk_ondelete(join, "role_id") == "CASCADE"


def test_user_role_membership_constraints():
    urm = _get_table("user_role_memberships")
    assert _has_unique(urm, "user_id", "role_id")
    assert _fk_ondelete(urm, "user_id") == "CASCADE"
    assert _fk_ondelete(urm, "role_id") == "CASCADE"


def test_user_audit_event_constraints_and_indexes():
    table = _get_table("user_audit_events")

    assert _fk_ondelete(table, "actor_user_id") == "SET NULL"
    assert _fk_ondelete(table, "subject_user_id") == "SET NULL"
    assert _fk_ondelete(table, "root_entity_id") == "SET NULL"
    assert _fk_ondelete(table, "entity_id") == "SET NULL"
    assert _fk_ondelete(table, "role_id") == "SET NULL"

    assert _has_index(table, "ix_uae_subject_occurred_at", "subject_user_id", "occurred_at")
    assert _has_index(table, "ix_uae_root_occurred_at", "root_entity_id", "occurred_at")
    assert _has_index(table, "ix_uae_entity_occurred_at", "entity_id", "occurred_at")
    assert _has_index(table, "ix_uae_role_occurred_at", "role_id", "occurred_at")
    assert _has_index(table, "ix_uae_event_category", "event_category")
    assert _has_index(table, "ix_uae_event_type", "event_type")
    assert not _has_column(table, "tenant_id")


def test_role_definition_history_constraints_and_indexes():
    table = _get_table("role_definition_history")

    assert _fk_ondelete(table, "role_id") is None
    assert _fk_ondelete(table, "actor_user_id") == "SET NULL"
    assert _fk_ondelete(table, "root_entity_id") == "SET NULL"
    assert _fk_ondelete(table, "scope_entity_id") == "SET NULL"

    assert _has_index(table, "ix_rdh_role_occurred_at", "role_id", "occurred_at")
    assert _has_index(table, "ix_rdh_actor_occurred_at", "actor_user_id", "occurred_at")
    assert _has_index(table, "ix_rdh_root_occurred_at", "root_entity_id", "occurred_at")
    assert _has_index(table, "ix_rdh_scope_occurred_at", "scope_entity_id", "occurred_at")
    assert _has_index(table, "ix_rdh_event_type", "event_type")
    assert _has_column(table, "status_snapshot")
    assert not _has_column(table, "tenant_id")


def test_permission_definition_history_constraints_and_indexes():
    table = _get_table("permission_definition_history")

    assert _fk_ondelete(table, "permission_id") is None
    assert _fk_ondelete(table, "actor_user_id") == "SET NULL"

    assert _has_index(table, "ix_pdh_permission_occurred_at", "permission_id", "occurred_at")
    assert _has_index(table, "ix_pdh_actor_occurred_at", "actor_user_id", "occurred_at")
    assert _has_index(table, "ix_pdh_event_type", "event_type")
    assert _has_column(table, "status_snapshot")
    assert not _has_column(table, "tenant_id")


def test_role_permissions_join_table_cascades():
    rp = _get_table("role_permissions")
    assert _fk_ondelete(rp, "role_id") == "CASCADE"
    assert _fk_ondelete(rp, "permission_id") == "CASCADE"


def test_roles_table_includes_assignable_entity_type_restrictions():
    roles = _get_table("roles")

    assert _has_column(roles, "assignable_at_types")
    assert _has_column(roles, "status")
    assert _has_index(roles, "ix_roles_status", "status")
    assert not _has_column(roles, "tenant_id")


def test_permission_tags_join_table_cascades():
    links = _get_table("permission_tag_links")
    assert _fk_ondelete(links, "permission_id") == "CASCADE"
    assert _fk_ondelete(links, "tag_id") == "CASCADE"


def test_user_and_permission_tables_are_global_and_tenantless():
    users = _get_table("users")
    permissions = _get_table("permissions")
    tags = _get_table("permission_tags")
    metrics = _get_table("activity_metrics")

    assert _has_unique(users, "email")
    assert _has_unique(permissions, "name")
    assert _has_column(permissions, "status")
    assert _has_index(permissions, "ix_permissions_status", "status")
    assert _has_unique(tags, "name")
    assert _has_unique(metrics, "metric_date", "metric_type")

    assert not _has_column(users, "tenant_id")
    assert not _has_column(permissions, "tenant_id")
    assert not _has_column(tags, "tenant_id")
    assert not _has_column(metrics, "tenant_id")
