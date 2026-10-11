"""Qualify the additive migration against a populated retained user table."""

import importlib
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from outlabs_auth.models.sql.user import User


@pytest.mark.asyncio
async def test_security_columns_are_nullable_idempotent_and_do_not_rewrite_users(
    test_engine,
    test_session,
    monkeypatch,
):
    user = User(email=f"legacy-{uuid4().hex}@example.test", is_superuser=True)
    test_session.add(user)
    await test_session.commit()
    user_id = user.id
    module = importlib.import_module("outlabs_auth.migrations.versions.20261011_0026_add_user_security_state")
    async with test_engine.begin() as connection:
        schema = (await connection.execute(text("SELECT current_schema()"))).scalar_one()
        await connection.execute(
            text("ALTER TABLE users DROP COLUMN session_security_epoch, DROP COLUMN platform_protected")
        )
        before = (await connection.execute(text("SELECT pg_relation_filenode('users'::regclass)"))).scalar_one()

        def upgrade(sync_connection):
            context = MigrationContext.configure(sync_connection, opts={"version_table_schema": schema})
            monkeypatch.setattr(module.context, "get_context", lambda: context)
            monkeypatch.setattr(module, "op", Operations(context))
            module.upgrade()
            module.upgrade()

        await connection.run_sync(upgrade)
        after = (await connection.execute(text("SELECT pg_relation_filenode('users'::regclass)"))).scalar_one()
        assert after == before
        row = (
            await connection.execute(
                text("SELECT is_superuser, session_security_epoch, platform_protected FROM users WHERE id=:id"),
                {"id": user_id},
            )
        ).one()
        assert tuple(row) == (True, None, None)
        columns = (
            await connection.execute(
                text(
                    "SELECT is_nullable, column_default FROM information_schema.columns WHERE table_schema=:schema AND table_name='users' AND column_name IN ('session_security_epoch','platform_protected')"
                ),
                {"schema": schema},
            )
        ).all()
        assert [tuple(row) for row in columns] == [("YES", None), ("YES", None)]


def test_migration_refuses_credential_barrier_removal():
    module = importlib.import_module("outlabs_auth.migrations.versions.20261011_0026_add_user_security_state")
    with pytest.raises(RuntimeError, match="coordinated credential reset"):
        module.downgrade()
