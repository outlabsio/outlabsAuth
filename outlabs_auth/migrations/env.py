"""
Alembic environment for OutlabsAuth.

This environment supports two execution modes:
- installed/local CLI flows that bind an explicit caller-provided connection
- repository-maintainer flows that fall back to an Alembic-managed engine
"""

from __future__ import annotations

import asyncio
import os
import re
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from alembic import context

from outlabs_auth.models.sql import ALL_MODELS  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DEFAULT_VERSION_TABLE = "outlabs_auth_alembic_version"


def _validate_schema_name(raw_schema: str | None) -> str | None:
    if raw_schema is None:
        return None
    normalized = raw_schema.strip()
    if not normalized:
        return None
    if not _SCHEMA_RE.fullmatch(normalized):
        raise RuntimeError("OUTLABS_AUTH_SCHEMA must match [A-Za-z_][A-Za-z0-9_]*")
    return normalized


def get_url() -> str:
    configured_url = config.attributes.get("database_url")
    if isinstance(configured_url, str) and configured_url.strip():
        return configured_url

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        if env_url.startswith("postgres://"):
            return env_url.replace("postgres://", "postgresql+asyncpg://", 1)
        if env_url.startswith("postgresql://") and "+asyncpg" not in env_url:
            return env_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return env_url

    return config.get_main_option("sqlalchemy.url")


def get_target_schema() -> str | None:
    configured_schema = config.attributes.get("target_schema")
    if isinstance(configured_schema, str) or configured_schema is None:
        validated = _validate_schema_name(configured_schema)
        if validated is not None:
            return validated

    return _validate_schema_name(os.environ.get("OUTLABS_AUTH_SCHEMA"))


def get_version_table_name() -> str:
    configured_name = config.attributes.get("version_table")
    if isinstance(configured_name, str) and configured_name.strip():
        return configured_name.strip()
    return _DEFAULT_VERSION_TABLE


def _configure_context(*, connection: Connection | None = None, url: str | None = None) -> None:
    schema = get_target_schema()
    configure_kwargs = dict(
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        version_table=get_version_table_name(),
    )

    if connection is not None:
        configure_kwargs["connection"] = connection
    elif url is not None:
        configure_kwargs["url"] = url
        configure_kwargs["literal_binds"] = True
        configure_kwargs["dialect_opts"] = {"paramstyle": "named"}

    if schema:
        configure_kwargs["include_schemas"] = True
        configure_kwargs["version_table_schema"] = schema

    context.configure(**configure_kwargs)


def run_migrations_offline() -> None:
    _configure_context(url=get_url())
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    schema = get_target_schema()
    if schema:
        connection.execute(text(f'SET search_path TO "{schema}", public'))

    _configure_context(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    caller_connection = config.attributes.get("connection")
    if caller_connection is not None:
        do_run_migrations(caller_connection)
        return

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
