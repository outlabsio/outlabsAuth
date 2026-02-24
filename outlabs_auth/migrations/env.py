"""
Alembic Environment Configuration

Async-aware migration environment for PostgreSQL with SQLModel.
"""

import asyncio
import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

# Import all models to register them with SQLModel.metadata
from outlabs_auth.models.sql import ALL_MODELS  # noqa: F401

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel metadata for autogenerate support
target_metadata = SQLModel.metadata
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_url() -> str:
    """Get database URL from environment or config."""
    # Priority: environment variable > alembic.ini
    url = os.environ.get("DATABASE_URL")
    if url:
        # Convert postgres:// to postgresql+asyncpg://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url
    return config.get_main_option("sqlalchemy.url")


def get_target_schema() -> str | None:
    """Get optional schema target for running migrations."""
    raw_schema = os.environ.get("OUTLABS_AUTH_SCHEMA", "").strip()
    if not raw_schema:
        return None
    if not _SCHEMA_RE.fullmatch(raw_schema):
        raise RuntimeError(
            "OUTLABS_AUTH_SCHEMA must match [A-Za-z_][A-Za-z0-9_]*"
        )
    return raw_schema


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_url()
    schema = get_target_schema()
    configure_kwargs = dict(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    if schema:
        configure_kwargs["include_schemas"] = True
        configure_kwargs["version_table_schema"] = schema

    context.configure(**configure_kwargs)

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    schema = get_target_schema()
    if schema:
        connection.execute(text(f'SET search_path TO "{schema}", public'))

    configure_kwargs = dict(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    if schema:
        configure_kwargs["include_schemas"] = True
        configure_kwargs["version_table_schema"] = schema

    context.configure(**configure_kwargs)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an async Engine and associates a connection with the context.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
