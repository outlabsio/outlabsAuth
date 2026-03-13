from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from outlabs_auth.bootstrap import get_system_permission_catalog
from tests.conftest import TEST_DATABASE_URL


ROOT = Path(__file__).resolve().parents[2]


def _python_bin(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _install_packaged_repo(tmp_path: Path) -> Path:
    venv_dir = tmp_path / ".venv"
    install_env = os.environ.copy()
    install_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    subprocess.run(
        ["uv", "venv", str(venv_dir)],
        cwd=tmp_path,
        check=True,
        env=install_env,
    )
    python_bin = _python_bin(venv_dir)

    subprocess.run(
        ["uv", "pip", "install", "--python", str(python_bin), str(ROOT)],
        cwd=ROOT,
        check=True,
        env=install_env,
    )
    return python_bin


async def _drop_schema(schema: str) -> None:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await engine.dispose()


async def _table_count(schema: str, table_name: str) -> int:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                      AND table_name = :table_name
                    """
                ),
                {"schema_name": schema, "table_name": table_name},
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


async def _count_rows(schema: str, table_name: str) -> int:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table_name}"'))
            return int(result.scalar_one())
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_packaged_cli_migrate_seed_and_bootstrap(tmp_path):
    schema = f"release_{uuid4().hex[:10]}"
    python_bin = _install_packaged_repo(tmp_path)
    cmd_env = os.environ.copy()
    cmd_env["DATABASE_URL"] = TEST_DATABASE_URL
    cmd_env["OUTLABS_AUTH_SCHEMA"] = schema

    try:
        asyncio.run(_drop_schema(schema))

        subprocess.run(
            [str(python_bin), "-m", "outlabs_auth.cli", "migrate"],
            cwd=tmp_path,
            check=True,
            env=cmd_env,
        )
        subprocess.run(
            [str(python_bin), "-m", "outlabs_auth.cli", "seed-system"],
            cwd=tmp_path,
            check=True,
            env=cmd_env,
        )
        subprocess.run(
            [
                str(python_bin),
                "-m",
                "outlabs_auth.cli",
                "bootstrap-admin",
                "--email",
                "admin@example.com",
                "--password",
                "BootstrapPass123!",
            ],
            cwd=tmp_path,
            check=True,
            env=cmd_env,
        )
        subprocess.run(
            [
                str(python_bin),
                "-m",
                "outlabs_auth.cli",
                "bootstrap-admin",
                "--email",
                "admin@example.com",
                "--password",
                "BootstrapPass123!",
            ],
            cwd=tmp_path,
            check=True,
            env=cmd_env,
        )

        assert asyncio.run(_table_count(schema, "users")) == 1
        assert asyncio.run(_table_count(schema, "permissions")) == 1
        assert asyncio.run(_table_count(schema, "system_config")) == 1
        assert asyncio.run(_table_count(schema, "outlabs_auth_alembic_version")) == 1
        assert asyncio.run(_count_rows(schema, "users")) == 1
        assert asyncio.run(_count_rows(schema, "permissions")) == len(
            get_system_permission_catalog()
        )
        assert asyncio.run(_count_rows(schema, "system_config")) == 1
    finally:
        asyncio.run(_drop_schema(schema))


@pytest.mark.integration
def test_packaged_cli_migrate_adopts_legacy_bootstrap_schema(tmp_path):
    schema = f"legacy_{uuid4().hex[:10]}"
    python_bin = _install_packaged_repo(tmp_path)
    cmd_env = os.environ.copy()
    cmd_env["DATABASE_URL"] = TEST_DATABASE_URL
    cmd_env["OUTLABS_AUTH_SCHEMA"] = schema

    try:
        asyncio.run(_drop_schema(schema))

        subprocess.run(
            [str(python_bin), "-m", "outlabs_auth.cli", "init-db", "--force"],
            cwd=tmp_path,
            check=True,
            env=cmd_env,
        )

        assert asyncio.run(_table_count(schema, "users")) == 1
        assert asyncio.run(_table_count(schema, "outlabs_auth_alembic_version")) == 0

        subprocess.run(
            [str(python_bin), "-m", "outlabs_auth.cli", "migrate"],
            cwd=tmp_path,
            check=True,
            env=cmd_env,
        )

        assert asyncio.run(_table_count(schema, "outlabs_auth_alembic_version")) == 1

        subprocess.run(
            [str(python_bin), "-m", "outlabs_auth.cli", "seed-system"],
            cwd=tmp_path,
            check=True,
            env=cmd_env,
        )

        assert asyncio.run(_count_rows(schema, "permissions")) == len(
            get_system_permission_catalog()
        )
    finally:
        asyncio.run(_drop_schema(schema))
