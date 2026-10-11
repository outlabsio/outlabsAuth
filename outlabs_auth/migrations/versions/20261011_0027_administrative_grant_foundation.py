"""Separate, retained administrative policy storage (unreleased S2 foundation).

Revision ID: 20261011_0027
Revises: 20261011_0026
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.sql.schema import SchemaItem

from alembic import context, op

revision = "20261011_0027"
down_revision = "20261011_0026"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    prefix = f"{schema}." if schema else ""
    existing = set(sa.inspect(op.get_bind()).get_table_names(schema=schema))

    def create(name: str, *columns: SchemaItem) -> None:
        # The packaged squashed baseline creates registered current models on
        # an empty install; genuine populated a37 upgrades need these tables.
        if name not in existing:
            op.create_table(name, *_base(), *columns, schema=schema)

    create(
        "auth_administrative_template_revisions",
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("policy", pg.JSONB(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("template_key", "revision", name="uq_auth_admin_template_revision"),
        sa.CheckConstraint("revision > 0", name="ck_auth_admin_template_revision"),
    )
    create(
        "auth_administrative_groups",
        sa.Column("group_key", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("group_key", name="uq_auth_admin_group_key"),
    )
    create(
        "auth_administrative_admissions",
        sa.Column(
            "group_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(prefix + "auth_administrative_groups.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_root_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(prefix + "entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    create(
        "auth_administrative_grants",
        sa.Column(
            "user_id", pg.UUID(as_uuid=True), sa.ForeignKey(prefix + "users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "template_revision_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(prefix + "auth_administrative_template_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("selector_kind", sa.String(20), nullable=False),
        sa.Column(
            "entity_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(prefix + "entities.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "group_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(prefix + "auth_administrative_groups.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("admission_ids", pg.JSONB(), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("grantor_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("holder_security_epoch", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("request_key", name="uq_auth_admin_grant_request"),
        sa.CheckConstraint("selector_kind IN ('entity', 'subtree', 'group')", name="ck_auth_admin_selector_kind"),
        sa.CheckConstraint(
            "(selector_kind = 'group' AND group_id IS NOT NULL AND entity_id IS NULL) OR (selector_kind IN ('entity', 'subtree') AND entity_id IS NOT NULL AND group_id IS NULL)",
            name="ck_auth_admin_selector_exclusive",
        ),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_from < valid_until", name="ck_auth_admin_window"
        ),
        sa.CheckConstraint("holder_security_epoch >= 0", name="ck_auth_admin_holder_epoch"),
    )
    create(
        "auth_administrative_audit",
        sa.Column("actor_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("evidence", pg.JSONB(), nullable=False),
    )
    indexes = [
        ("auth_administrative_admissions", "ix_auth_admin_admission_group_root", ["group_id", "customer_root_id"], {}),
        (
            "auth_administrative_admissions",
            "uq_auth_admin_open_admission",
            ["group_id", "customer_root_id"],
            {"unique": True, "postgresql_where": sa.text("closed_at IS NULL")},
        ),
        (
            "auth_administrative_grants",
            "ix_auth_admin_grant_actor_window",
            ["user_id", "holder_security_epoch", "revoked_at", "valid_until"],
            {},
        ),
        ("auth_administrative_audit", "ix_auth_admin_audit_subject", ["subject_id", "created_at"], {}),
    ]
    for table, name, columns, options in indexes:
        found = {row["name"] for row in sa.inspect(op.get_bind()).get_indexes(table, schema=schema)}
        if name not in found:
            op.create_index(name, table, columns, schema=schema, **options)
        else:
            valid = (
                op.get_bind()
                .execute(
                    sa.text(
                        "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND c.relname=:name"
                    ),
                    {"schema": schema or "public", "name": name},
                )
                .scalar_one()
            )
            if not valid:
                raise RuntimeError(f"Administrative index {name} is invalid; reviewed recovery is required")

    # Published policy revisions, selector lineage, admission identity and audit
    # cannot be silently rewritten through a future service or ordinary SQL.
    quoted = op.get_bind().dialect.identifier_preparer.quote(schema or "public")
    op.execute(f"""CREATE OR REPLACE FUNCTION {quoted}.auth_admin_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Administrative lineage is retained'; END IF;
        IF (to_jsonb(OLD) - TG_ARGV[0] - 'updated_at') IS DISTINCT FROM
           (to_jsonb(NEW) - TG_ARGV[0] - 'updated_at') THEN
            RAISE EXCEPTION 'Administrative authority revision is immutable';
        END IF;
        RETURN NEW;
    END $$""")
    for table, mutable in [
        ("auth_administrative_template_revisions", "active"),
        ("auth_administrative_admissions", "closed_at"),
        ("auth_administrative_grants", "revoked_at"),
        ("auth_administrative_audit", ""),
    ]:
        op.execute(f'DROP TRIGGER IF EXISTS auth_admin_immutable ON {quoted}."{table}"')
        op.execute(
            f"CREATE TRIGGER auth_admin_immutable BEFORE UPDATE OR DELETE ON {quoted}.\"{table}\" FOR EACH ROW EXECUTE FUNCTION {quoted}.auth_admin_immutable('{mutable}')"
        )
    # Terminal withdrawals are monotonic, independent of idempotent service
    # retries. Re-admission/re-grant needs a new row and new audit identity.
    op.execute(f"""CREATE OR REPLACE FUNCTION {quoted}.auth_admin_terminal() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF (to_jsonb(OLD)->TG_ARGV[0]) <> 'null'::jsonb AND
           (to_jsonb(OLD)->TG_ARGV[0]) IS DISTINCT FROM (to_jsonb(NEW)->TG_ARGV[0]) THEN
            RAISE EXCEPTION 'Administrative withdrawal cannot be reversed';
        END IF;
        RETURN NEW;
    END $$""")
    for table, column in [
        ("auth_administrative_admissions", "closed_at"),
        ("auth_administrative_grants", "revoked_at"),
    ]:
        op.execute(f'DROP TRIGGER IF EXISTS auth_admin_terminal ON {quoted}."{table}"')
        op.execute(
            f"CREATE TRIGGER auth_admin_terminal BEFORE UPDATE ON {quoted}.\"{table}\" FOR EACH ROW EXECUTE FUNCTION {quoted}.auth_admin_terminal('{column}')"
        )


def downgrade() -> None:
    raise RuntimeError("Administrative authority lineage requires coordinated recovery, not a routine drop")
