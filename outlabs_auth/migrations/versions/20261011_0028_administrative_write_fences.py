"""Serialize administrative security withdrawal and child policy writes.

Revision ID: 20261011_0028
Revises: 20261011_0027

No runtime admission is enabled. A protected staff write shares its qualifying
grant/definition/key rows; these triggers make supported child mutations and
account security changes take conflicting row locks, including raw DML.
"""

from alembic import context, op

revision = "20261011_0028"
down_revision = "20261011_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    quoted = op.get_bind().dialect.identifier_preparer.quote_schema(schema)
    op.execute(f"""
      CREATE OR REPLACE FUNCTION {quoted}.auth_admin_withdraw_on_security_change()
      RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.session_security_epoch IS DISTINCT FROM OLD.session_security_epoch
          OR NEW.status IS DISTINCT FROM OLD.status
          OR NEW.root_entity_id IS DISTINCT FROM OLD.root_entity_id THEN
          WITH held AS (
            SELECT id FROM {quoted}.auth_administrative_grants
            WHERE user_id = NEW.id AND revoked_at IS NULL ORDER BY id FOR UPDATE
          )
          UPDATE {quoted}.auth_administrative_grants g
          SET revoked_at = clock_timestamp(), updated_at = clock_timestamp()
          FROM held WHERE g.id = held.id;
        END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(f"DROP TRIGGER IF EXISTS auth_admin_security_withdrawal ON {quoted}.users")
    op.execute(f"""CREATE TRIGGER auth_admin_security_withdrawal AFTER UPDATE ON {quoted}.users
      FOR EACH ROW EXECUTE FUNCTION {quoted}.auth_admin_withdraw_on_security_change()""")
    # Parent-row locks also cover insertion into an empty child collection;
    # locking only existing scope/condition rows would leave that race open.
    for child, parent, foreign_key in [
        ("api_key_scopes", "api_keys", "api_key_id"),
        ("permission_conditions", "permissions", "permission_id"),
        ("user_role_memberships", "users", "user_id"),
    ]:
        function = f"auth_admin_fence_{child}"
        op.execute(f"""
          CREATE OR REPLACE FUNCTION {quoted}.{function}()
          RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN
            PERFORM id FROM {quoted}.{parent}
              WHERE id = ANY(ARRAY[OLD.{foreign_key}, NEW.{foreign_key}])
              ORDER BY id FOR UPDATE;
            IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
          END $$
        """)
        op.execute(f"DROP TRIGGER IF EXISTS {function} ON {quoted}.{child}")
        op.execute(f"""CREATE TRIGGER {function} BEFORE INSERT OR UPDATE OR DELETE ON {quoted}.{child}
          FOR EACH ROW EXECUTE FUNCTION {quoted}.{function}()""")


def downgrade() -> None:
    raise RuntimeError("Administrative security fences require an explicit forward recovery plan")
