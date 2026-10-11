"""Upgrade a genuine installed public a37 schema, never a stamped new model."""

import os
import subprocess
import textwrap
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from outlabs_auth.cli import run_migrations


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_a37_upgrade_and_database_immutability():
    previous_python = os.getenv("S2_A37_PYTHON")
    if not previous_python:
        pytest.skip("Genuine public a37 interpreter is required for S2 release qualification")
    assert Path(previous_python).is_absolute() and Path(previous_python).is_file()
    url = os.environ["TEST_DATABASE_URL"]
    parsed = urlparse(url)
    assert parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.path.endswith("_test")
    schema = f"upgrade_s2_{uuid4().hex}"
    child_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "DATABASE_URL": url,
        "OUTLABS_AUTH_SCHEMA": schema,
    }
    script = textwrap.dedent("""
        import asyncio, importlib.metadata, os
        from outlabs_auth import EnterpriseRBAC
        from outlabs_auth.cli import run_migrations
        assert importlib.metadata.version("outlabs-auth") == "0.1.0a37"
        async def main():
            await run_migrations(os.environ["DATABASE_URL"], schema=os.environ["OUTLABS_AUTH_SCHEMA"])
            auth=EnterpriseRBAC(database_url=os.environ["DATABASE_URL"], database_schema=os.environ["OUTLABS_AUTH_SCHEMA"], secret_key="synthetic-genuine-public-a37-upgrade-fixture", enable_caching=False)
            await auth.initialize()
            async with auth.get_session() as session:
                await auth.user_service.create_user(session, email="retained@example.com", password="SyntheticUpgrade123!", first_name="Retained", is_superuser=True)
                await session.commit()
            await auth.shutdown()
        asyncio.run(main())
    """)
    result = subprocess.run(
        [previous_python, "-c", script], env=child_env, cwd="/tmp", capture_output=True, text=True, timeout=180
    )
    assert result.returncode == 0, result.stderr[-1500:]
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            before = (
                await connection.execute(
                    text(f'SELECT id, email, hashed_password, first_name, is_superuser FROM "{schema}".users')
                )
            ).one()
            assert (
                await connection.execute(text(f'SELECT version_num FROM "{schema}".outlabs_auth_alembic_version'))
            ).scalar_one() == "20261011_0026"
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema=:schema AND table_name LIKE 'auth_administrative_%'"
                    ),
                    {"schema": schema},
                )
            ).scalar_one() == 0
        await run_migrations(url, schema=schema, lock_timeout="5s")
        async with engine.begin() as connection:
            after = (
                await connection.execute(
                    text(f'SELECT id, email, hashed_password, first_name, is_superuser FROM "{schema}".users')
                )
            ).one()
            assert before == after
            assert (
                await connection.execute(text(f'SELECT version_num FROM "{schema}".outlabs_auth_alembic_version'))
            ).scalar_one() == "20261011_0028"
            identity = uuid4()
            await connection.execute(
                text(
                    f"""INSERT INTO "{schema}".auth_administrative_template_revisions
                (id,template_key,revision,policy,policy_hash,active) VALUES (:id,'policy',1,'{{}}'::jsonb,:hash,true)"""
                ),
                {"id": identity, "hash": "a" * 64},
            )
            for change in ['UPDATE {table} SET policy=\'{{"permissions":["*:*"]}}\'::jsonb', "DELETE FROM {table}"]:
                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError, match="Administrative"):
                    await connection.execute(
                        text(change.format(table=f'"{schema}".auth_administrative_template_revisions'))
                    )
                await savepoint.rollback()
            await connection.execute(
                text(f'UPDATE "{schema}".auth_administrative_template_revisions SET active=false WHERE id=:id'),
                {"id": identity},
            )
            # All declared indexes are valid, not just present by name.
            assert (
                (
                    await connection.execute(
                        text("""SELECT bool_and(i.indisvalid) FROM pg_index i
                JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
                WHERE n.nspname=:schema AND t.relname LIKE 'auth_administrative_%' """),
                        {"schema": schema},
                    )
                ).scalar_one()
                is True
            )
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()
