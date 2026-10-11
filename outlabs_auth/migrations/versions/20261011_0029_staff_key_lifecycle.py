"""Retain staff credential provenance and prevent lifecycle expansion.

Revision ID: 20261011_0029
Revises: 20261011_0028
"""

from alembic import context, op

revision = "20261011_0029"
down_revision = "20261011_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    quoted = op.get_bind().dialect.identifier_preparer.quote_schema(schema)
    # IF NOT EXISTS also supports the library's metadata-created test schemas.
    op.execute(f"ALTER TABLE {quoted}.api_keys ADD COLUMN IF NOT EXISTS staff_managed boolean NOT NULL DEFAULT false")
    op.execute(f"""
      CREATE OR REPLACE FUNCTION {quoted}.auth_staff_key_lifecycle()
      RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF OLD.staff_managed AND (
          NOT NEW.staff_managed OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
          OR NEW.integration_principal_id IS DISTINCT FROM OLD.integration_principal_id
          OR NEW.key_kind IS DISTINCT FROM OLD.key_kind
          OR NEW.key_hash IS DISTINCT FROM OLD.key_hash OR NEW.prefix IS DISTINCT FROM OLD.prefix
          OR NEW.entity_id IS DISTINCT FROM OLD.entity_id
          OR NEW.inherit_from_tree IS DISTINCT FROM OLD.inherit_from_tree
          OR NEW.expires_at IS NULL OR NEW.expires_at > OLD.expires_at
          OR (OLD.status <> 'active' AND NEW.status = 'active')
        ) THEN
          RAISE EXCEPTION 'staff credential lifecycle cannot expand';
        END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(f"DROP TRIGGER IF EXISTS auth_staff_key_lifecycle ON {quoted}.api_keys")
    op.execute(
        f"CREATE TRIGGER auth_staff_key_lifecycle BEFORE UPDATE ON {quoted}.api_keys "
        f"FOR EACH ROW EXECUTE FUNCTION {quoted}.auth_staff_key_lifecycle()"
    )


def downgrade() -> None:
    raise RuntimeError("Staff credential provenance requires forward recovery")
