"""Migration safety against real locks and interrupted concurrent indexes."""

import importlib
import asyncio
import time
import os
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from outlabs_auth import cli
from outlabs_auth.cli import _build_engine, run_migrations, _run_alembic_command
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture
async def prior_head():
    schema = "migration_safety_" + uuid4().hex[:12]
    engine = create_async_engine(TEST_DATABASE_URL)
    await run_migrations(TEST_DATABASE_URL, schema=schema, revision="20260802_0025")
    try:
        async with engine.begin() as connection:
            # Bootstrap/model-created legacy installations may already have these
            # columns. This creates the exact populated pre-security shape.
            await connection.execute(
                text(
                    f'ALTER TABLE "{schema}".users DROP COLUMN IF EXISTS session_security_epoch, '
                    "DROP COLUMN IF EXISTS platform_protected"
                )
            )
        yield schema, engine
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def version_and_columns(engine, schema):
    async with engine.connect() as connection:
        version = (
            await connection.execute(text(f'SELECT version_num FROM "{schema}".outlabs_auth_alembic_version'))
        ).scalar_one()
        columns = (
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema=:schema AND table_name='users'"
                    ),
                    {"schema": schema},
                )
            )
            .scalars()
            .all()
        )
        return version, set(columns)


@pytest.mark.asyncio
async def test_migration_connection_has_bounded_lock_timeout():
    engine = _build_engine(TEST_DATABASE_URL, None)
    try:
        async with engine.connect() as connection:
            assert (await connection.execute(text("SHOW lock_timeout"))).scalar_one() == "5s"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_index_is_never_treated_as_complete(monkeypatch):
    schema = "invalid_index_" + uuid4().hex[:12]
    engine = create_async_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    module = importlib.import_module("outlabs_auth.migrations.versions.20260611_0018_index_hygiene")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'CREATE TABLE "{schema}".users (invite_token text)'))
            await connection.execute(text(f"INSERT INTO \"{schema}\".users VALUES ('duplicate'), ('duplicate')"))
            with pytest.raises(IntegrityError) as duplicate:
                await connection.execute(
                    text(f'CREATE UNIQUE INDEX CONCURRENTLY ix_users_invite_token ON "{schema}".users(invite_token)')
                )
            assert duplicate.value.orig.sqlstate == "23505"
            valid = (
                await connection.execute(
                    text(
                        "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND c.relname=:name"
                    ),
                    {"schema": schema, "name": "ix_users_invite_token"},
                )
            ).scalar_one()
            assert valid is False

            def inspect(sync_connection):
                monkeypatch.setattr(module, "op", SimpleNamespace(get_bind=lambda: sync_connection))
                with pytest.raises(RuntimeError, match="invalid|not valid"):
                    module._index_exists(schema, "users", "ix_users_invite_token")

            await connection.run_sync(inspect)
    finally:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest.mark.asyncio
async def test_contended_security_upgrade_rolls_back_with_bounded_wait(prior_head):
    schema, engine = prior_head
    async with engine.begin() as holder:
        await holder.execute(text(f'LOCK TABLE "{schema}".users IN ACCESS SHARE MODE'))
        started = time.monotonic()
        with pytest.raises(Exception) as raised:
            await run_migrations(TEST_DATABASE_URL, schema=schema, lock_timeout="100ms")
        assert getattr(raised.value.orig, "sqlstate", None) == "55P03"
        assert time.monotonic() - started < 2
        version, columns = await version_and_columns(engine, schema)
        assert version == "20260802_0025"
        assert "session_security_epoch" not in columns and "platform_protected" not in columns
    await run_migrations(TEST_DATABASE_URL, schema=schema, lock_timeout="100ms")
    version, columns = await version_and_columns(engine, schema)
    assert version == "20261011_0028"
    assert {"session_security_epoch", "platform_protected"} <= columns


@pytest.mark.asyncio
async def test_lock_retry_succeeds_after_holder_releases(prior_head, monkeypatch):
    schema, engine = prior_head
    attempts = []
    release = asyncio.Event()
    held = asyncio.Event()
    invoke = cli._invoke_alembic_command

    def observed(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 2:
            release.set()
        return invoke(*args, **kwargs)

    monkeypatch.setattr(cli, "_invoke_alembic_command", observed)

    async def hold():
        async with engine.begin() as connection:
            await connection.execute(text(f'LOCK TABLE "{schema}".users IN ACCESS SHARE MODE'))
            held.set()
            await release.wait()

    holder = asyncio.create_task(hold())
    await held.wait()
    try:
        await asyncio.wait_for(run_migrations(TEST_DATABASE_URL, schema=schema, lock_timeout="100ms"), 5)
        assert len(attempts) == 2
        assert (await version_and_columns(engine, schema))[0] == "20261011_0028"
    finally:
        release.set()
        await holder


@pytest.mark.asyncio
async def test_concurrent_runners_converge_without_duplicate_ddl(prior_head):
    schema, engine = prior_head
    await asyncio.gather(*(run_migrations(TEST_DATABASE_URL, schema=schema, lock_timeout="500ms") for _ in range(2)))
    assert (await version_and_columns(engine, schema))[0] == "20261011_0028"


@pytest.mark.asyncio
async def test_separate_process_runners_converge(prior_head):
    schema, engine = prior_head
    # Separate interpreters cannot share the Alembic proxy lock. Retain the
    # database migration mutex after DDL until the second runner is waiting.
    barrier = uuid4().int % (2**63)
    code = """
import asyncio, os
from alembic import command
from sqlalchemy import text
from outlabs_auth.cli import _run_alembic_command
def runner(config):
    command.upgrade(config, 'head')
    print('DDL_READY', flush=True)
    config.attributes['connection'].execute(text('SELECT pg_advisory_xact_lock(:barrier)'), {'barrier': int(os.environ['TEST_BARRIER'])})
asyncio.run(_run_alembic_command(os.environ['TEST_DATABASE_URL'], schema=os.environ['TEST_SCHEMA'], runner=runner, lock_timeout='5s'))
"""
    env = dict(os.environ, TEST_DATABASE_URL=TEST_DATABASE_URL, TEST_SCHEMA=schema, TEST_BARRIER=str(barrier))
    processes = []
    try:
        async with engine.begin() as holder:
            await holder.execute(text("SELECT pg_advisory_xact_lock(:barrier)"), {"barrier": barrier})
            first = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            processes.append(first)
            assert await asyncio.wait_for(first.stdout.readline(), 10) == b"DDL_READY\n"
            second = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import asyncio,os; from outlabs_auth.cli import run_migrations; asyncio.run(run_migrations(os.environ['TEST_DATABASE_URL'],schema=os.environ['TEST_SCHEMA']))",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            processes.append(second)

            async def wait_for_mutex():
                while True:
                    async with engine.connect() as observer:
                        waiting = (
                            await observer.execute(
                                text(
                                    "SELECT count(*) FROM pg_stat_activity WHERE wait_event='advisory' "
                                    "AND datname=current_database() "
                                    "AND query LIKE '%outlabs_auth:migrate:%' AND pid<>pg_backend_pid()"
                                )
                            )
                        ).scalar_one()
                    if waiting:
                        return
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(wait_for_mutex(), 5)
        for process in processes:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 10)
            assert process.returncode == 0, (stdout, stderr)
        assert (await version_and_columns(engine, schema))[0] == "20261011_0028"
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
                await process.wait()


@pytest.mark.asyncio
async def test_head_shortcut_refuses_invalid_auth_index(prior_head):
    schema, _ = prior_head
    await run_migrations(TEST_DATABASE_URL, schema=schema)
    engine = create_async_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            # An expression producing the same key for two version-independent
            # user rows leaves a real invalid index on an Auth-owned table.
            from outlabs_auth.models.sql.user import User

            await connection.execute(text(f'SET search_path TO "{schema}"'))
            await connection.execute(
                User.__table__.insert(),
                [{"id": uuid4(), "email": "a@example.test"}, {"id": uuid4(), "email": "b@example.test"}],
            )
            with pytest.raises(IntegrityError) as duplicate:
                await connection.execute(
                    text(f'CREATE UNIQUE INDEX CONCURRENTLY bad_auth_recovery_index ON "{schema}".users ((1))')
                )
            assert duplicate.value.orig.sqlstate == "23505"
        with pytest.raises(RuntimeError, match="bad_auth_recovery_index"):
            await run_migrations(TEST_DATABASE_URL, schema=schema)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_non_lock_errors_are_not_retried(prior_head):
    schema, _ = prior_head
    attempts = []

    def broken(config):
        attempts.append(1)
        raise RuntimeError("Synthetic non-lock failure")

    with pytest.raises(RuntimeError, match="non-lock"):
        await _run_alembic_command(TEST_DATABASE_URL, schema=schema, runner=broken, lock_timeout="100ms")
    assert len(attempts) == 1


@pytest.mark.asyncio
async def test_caller_connection_settings_are_restored(prior_head):
    schema, _ = prior_head
    engine = create_async_engine(
        TEST_DATABASE_URL, connect_args={"server_settings": {"lock_timeout": "10s", "search_path": "public"}}
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                cli._invoke_alembic_command,
                database_url=TEST_DATABASE_URL,
                schema=schema,
                runner=lambda config: command.upgrade(config, "head"),
                lock_timeout="100ms",
            )
        async with engine.connect() as connection:
            assert (await connection.execute(text("SHOW lock_timeout"))).scalar_one() == "10s"
            assert (await connection.execute(text("SHOW search_path"))).scalar_one() == "public"
    finally:
        await engine.dispose()


@pytest.mark.parametrize("value", ["0", "0ms", "-1s", "31s", "1h", None])
def test_unbounded_or_invalid_lock_budget_is_rejected(value):
    with pytest.raises(ValueError):
        _build_engine(TEST_DATABASE_URL, None, lock_timeout=value)
