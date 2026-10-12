"""Fence source-only membership return against native edits/security boundaries.

Revision ID: 20261012_0031
Revises: 20261011_0030
"""

from alembic import context, op

revision = "20261012_0031"
down_revision = "20261011_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema or "public"
    q = op.get_bind().dialect.identifier_preparer.quote_schema(schema)
    op.execute(f"ALTER TABLE {q}.entity_memberships ADD COLUMN IF NOT EXISTS write_revision bigint NOT NULL DEFAULT 0")
    op.execute(f"""CREATE TABLE IF NOT EXISTS {q}.membership_source_withdrawals (
      user_id uuid NOT NULL,entity_id uuid NOT NULL,membership_id uuid NOT NULL,
      revision bigint NOT NULL,user_epoch bigint NOT NULL,PRIMARY KEY(user_id,entity_id))""")
    op.execute(f"""CREATE OR REPLACE FUNCTION {q}.auth_member_write_revision() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN NEW.write_revision=OLD.write_revision+1; RETURN NEW; END $$""")
    op.execute(f"DROP TRIGGER IF EXISTS auth_member_write_revision ON {q}.entity_memberships")
    op.execute(
        f"CREATE TRIGGER auth_member_write_revision BEFORE UPDATE ON {q}.entity_memberships FOR EACH ROW EXECUTE FUNCTION {q}.auth_member_write_revision()"
    )
    op.execute(f"""CREATE OR REPLACE FUNCTION {q}.auth_member_role_revision() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      UPDATE {q}.entity_memberships SET write_revision=write_revision
      WHERE id=ANY(ARRAY[OLD.membership_id,NEW.membership_id]);
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$""")
    op.execute(f"DROP TRIGGER IF EXISTS auth_member_role_revision ON {q}.entity_membership_roles")
    op.execute(
        f"CREATE TRIGGER auth_member_role_revision AFTER INSERT OR UPDATE OR DELETE ON {q}.entity_membership_roles FOR EACH ROW EXECUTE FUNCTION {q}.auth_member_role_revision()"
    )
    op.execute(
        f"""CREATE OR REPLACE FUNCTION {q}.auth_source_withdrawal_user_fence() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM id FROM {q}.users WHERE id=ANY(ARRAY[OLD.user_id,NEW.user_id]) ORDER BY id FOR UPDATE;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END $$"""
    )
    op.execute(f"DROP TRIGGER IF EXISTS auth_source_withdrawal_user_fence ON {q}.membership_source_withdrawals")
    op.execute(
        f"CREATE TRIGGER auth_source_withdrawal_user_fence BEFORE INSERT OR UPDATE OR DELETE ON {q}.membership_source_withdrawals FOR EACH ROW EXECUTE FUNCTION {q}.auth_source_withdrawal_user_fence()"
    )


def downgrade() -> None:
    raise RuntimeError("Source return provenance requires reviewed forward recovery")
