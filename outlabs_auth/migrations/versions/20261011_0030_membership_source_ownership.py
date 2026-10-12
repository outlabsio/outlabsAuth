"""Conservative native ownership and compatible IAM child writer fences.

Revision ID: 20261011_0030
Revises: 20261011_0029
"""

from alembic import context, op

revision = "20261011_0030"
down_revision = "20261011_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    q = op.get_bind().dialect.identifier_preparer.quote_schema(schema)
    for table in ("entity_memberships", "entity_membership_roles"):
        op.execute(f"ALTER TABLE {q}.{table} ADD COLUMN IF NOT EXISTS native_owned boolean NOT NULL DEFAULT true")
    op.execute(f"""CREATE TABLE IF NOT EXISTS {q}.membership_source_claims (
        source_id uuid PRIMARY KEY, membership_id uuid NOT NULL
          REFERENCES {q}.entity_memberships(id) ON DELETE RESTRICT)""")
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_membership_source_claims_membership_id ON {q}.membership_source_claims(membership_id)"
    )
    op.execute(f"""CREATE TABLE IF NOT EXISTS {q}.membership_source_roles (
        source_id uuid NOT NULL REFERENCES {q}.membership_source_claims(source_id) ON DELETE CASCADE,
        role_id uuid NOT NULL REFERENCES {q}.roles(id) ON DELETE RESTRICT,
        PRIMARY KEY(source_id,role_id))""")
    # Lock the account even when its child collection is empty. Native SDK,
    # mounted routes and ordinary raw DML therefore conflict with replay.
    specs = [
        ("auth_administrative_grants", "SELECT OLD.user_id AS id UNION SELECT NEW.user_id", "users"),
        (
            "entity_memberships",
            "SELECT user_id AS id FROM (SELECT OLD.user_id AS user_id UNION SELECT NEW.user_id) x",
            "users",
        ),
        (
            "entity_membership_roles",
            f"SELECT user_id AS id FROM {q}.entity_memberships WHERE id=ANY(ARRAY[OLD.membership_id,NEW.membership_id])",
            "users",
        ),
        (
            "membership_source_claims",
            f"SELECT user_id AS id FROM {q}.entity_memberships WHERE id=ANY(ARRAY[OLD.membership_id,NEW.membership_id])",
            "users",
        ),
        (
            "membership_source_roles",
            f"SELECT m.user_id AS id FROM {q}.entity_memberships m JOIN {q}.membership_source_claims c ON c.membership_id=m.id WHERE c.source_id=ANY(ARRAY[OLD.source_id,NEW.source_id])",
            "users",
        ),
        ("role_permissions", "SELECT OLD.role_id AS id UNION SELECT NEW.role_id", "roles"),
        ("role_conditions", "SELECT OLD.role_id AS id UNION SELECT NEW.role_id", "roles"),
        ("role_entity_type_permissions", "SELECT OLD.role_id AS id UNION SELECT NEW.role_id", "roles"),
        ("condition_groups", "SELECT OLD.role_id AS id UNION SELECT NEW.role_id", "roles"),
        ("entity_closure", "SELECT OLD.descendant_id AS id UNION SELECT NEW.descendant_id", "entities"),
    ]
    for child, ids, parent in specs:
        name = "auth_member_fence_" + child
        op.execute(f"""CREATE OR REPLACE FUNCTION {q}.{name}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          PERFORM id FROM {q}.{parent} WHERE id IN ({ids}) ORDER BY id FOR UPDATE;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $$""")
        op.execute(f"DROP TRIGGER IF EXISTS {name} ON {q}.{child}")
        op.execute(
            f"CREATE TRIGGER {name} BEFORE INSERT OR UPDATE OR DELETE ON {q}.{child} FOR EACH ROW EXECUTE FUNCTION {q}.{name}()"
        )
    op.execute(
        f"""CREATE OR REPLACE FUNCTION {q}.auth_member_group_permission_fence() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM id FROM {q}.permissions WHERE id=ANY(ARRAY[OLD.permission_id,NEW.permission_id]) ORDER BY id FOR UPDATE;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$"""
    )
    op.execute(f"DROP TRIGGER IF EXISTS auth_member_group_permission_fence ON {q}.condition_groups")
    op.execute(
        f"CREATE TRIGGER auth_member_group_permission_fence BEFORE INSERT OR UPDATE OR DELETE ON {q}.condition_groups FOR EACH ROW EXECUTE FUNCTION {q}.auth_member_group_permission_fence()"
    )
    op.execute(f"""CREATE OR REPLACE FUNCTION {q}.auth_source_claim_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.source_id,NEW.membership_id) IS DISTINCT FROM (OLD.source_id,OLD.membership_id) THEN
        RAISE EXCEPTION 'Source membership identity cannot transfer';
      END IF; RETURN NEW;
    END $$""")
    op.execute(f"DROP TRIGGER IF EXISTS auth_source_claim_identity ON {q}.membership_source_claims")
    op.execute(
        f"CREATE TRIGGER auth_source_claim_identity BEFORE UPDATE ON {q}.membership_source_claims FOR EACH ROW EXECUTE FUNCTION {q}.auth_source_claim_identity()"
    )


def downgrade() -> None:
    raise RuntimeError("Source ownership and IAM fences require reviewed forward recovery")
