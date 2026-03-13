"""
OutlabsAuth CLI.

Database-touching commands always target an explicit DB/schema and use a
caller-owned connection when invoking Alembic.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID

import click
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from outlabs_auth._version import __version__
from outlabs_auth.bootstrap import (
    bootstrap_superuser,
    build_bootstrap_config,
    seed_system_records,
)

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALEMBIC_VERSION_TABLE = "outlabs_auth_alembic_version"
LEGACY_SCHEMA_ADOPTION_TABLES = frozenset(
    {
        "users",
        "roles",
        "permissions",
        "entities",
        "entity_memberships",
        "system_config",
    }
)


def normalize_database_url(url: str) -> str:
    """Normalize postgres URLs to asyncpg SQLAlchemy format."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _resolve_alembic_ini(*, require_local: bool = False) -> Path:
    """
    Resolve alembic.ini for either installed-package usage or local maintenance.

    Installed consumers should use the bundled package config. Repository
    maintainers can require a local config when creating revisions.
    """
    package_dir = Path(__file__).resolve().parent
    package_root = package_dir.parent
    bundled_alembic = package_dir / "alembic.ini"
    repo_alembic = package_root / "alembic.ini"
    cwd_alembic = Path.cwd() / "alembic.ini"

    if require_local:
        if repo_alembic.exists():
            return repo_alembic
        if cwd_alembic.exists():
            return cwd_alembic
        raise FileNotFoundError(
            "Local alembic.ini not found. Expected in repository root or current working directory."
        )

    if bundled_alembic.exists():
        return bundled_alembic
    if repo_alembic.exists():
        return repo_alembic
    if cwd_alembic.exists():
        return cwd_alembic

    raise FileNotFoundError(
        "alembic.ini not found. Expected in package, repository root, or current working directory."
    )


def _validate_schema_name(schema: Optional[str]) -> Optional[str]:
    """Validate schema identifier before using it in SQL or runtime context."""
    if schema is None:
        return None
    normalized = schema.strip()
    if not normalized:
        return None
    if not _SCHEMA_RE.fullmatch(normalized):
        raise ValueError("Schema name must match [A-Za-z_][A-Za-z0-9_]*")
    return normalized


def _resolve_script_location(alembic_ini: Path) -> Optional[str]:
    """
    Resolve absolute Alembic script_location for OutlabsAuth migrations.

    When called from another project, relative script_location values can break.
    """
    package_root = Path(__file__).resolve().parents[1]
    package_scripts = package_root / "outlabs_auth" / "migrations"
    if package_scripts.exists():
        return str(package_scripts)

    fallback_scripts = alembic_ini.parent / "outlabs_auth" / "migrations"
    if fallback_scripts.exists():
        return str(fallback_scripts)

    return None


def _load_alembic_config(*, require_local: bool = False) -> "Config":
    """Load Alembic config and normalize script location for any install mode."""
    alembic_ini = _resolve_alembic_ini(require_local=require_local)
    alembic_cfg = Config(str(alembic_ini))
    script_location = _resolve_script_location(alembic_ini)
    if script_location:
        alembic_cfg.set_main_option("script_location", script_location)
    return alembic_cfg


def _build_connect_args(schema: Optional[str]) -> dict[str, object]:
    target_schema = _validate_schema_name(schema)
    if not target_schema:
        return {}
    return {"server_settings": {"search_path": f"{target_schema},public"}}


def _build_engine(database_url: str, schema: Optional[str]) -> AsyncEngine:
    return create_async_engine(
        normalize_database_url(database_url),
        echo=False,
        connect_args=_build_connect_args(schema),
    )


async def _ensure_schema_exists(database_url: str, schema: Optional[str]) -> None:
    target_schema = _validate_schema_name(schema)
    if not target_schema:
        return

    engine = create_async_engine(normalize_database_url(database_url), echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{target_schema}"'))
    finally:
        await engine.dispose()


async def _list_schema_tables(database_url: str, schema: Optional[str]) -> set[str]:
    schema_name = _validate_schema_name(schema) or "public"
    engine = create_async_engine(normalize_database_url(database_url), echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                    """
                ),
                {"schema_name": schema_name},
            )
            return {str(row[0]) for row in result}
    finally:
        await engine.dispose()


def _invoke_alembic_command(
    sync_connection,
    *,
    database_url: str,
    schema: Optional[str],
    runner: Callable[["Config"], None],
) -> None:
    alembic_cfg = _load_alembic_config()
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.attributes["connection"] = sync_connection
    alembic_cfg.attributes["database_url"] = database_url
    alembic_cfg.attributes["target_schema"] = _validate_schema_name(schema)
    alembic_cfg.attributes["version_table"] = ALEMBIC_VERSION_TABLE
    runner(alembic_cfg)


async def _run_alembic_command(
    database_url: str,
    *,
    schema: Optional[str],
    runner: Callable[["Config"], None],
    ensure_schema: bool = False,
) -> None:
    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)
    if ensure_schema:
        await _ensure_schema_exists(normalized_url, target_schema)

    engine = _build_engine(normalized_url, target_schema)
    try:
        # Alembic expects the caller-owned connection to commit DDL changes.
        # Using a plain connect() here can leave the migration transaction open
        # and rolled back on exit even though upgrade logs look successful.
        async with engine.begin() as conn:
            await conn.run_sync(
                _invoke_alembic_command,
                database_url=normalized_url,
                schema=target_schema,
                runner=runner,
            )
    finally:
        await engine.dispose()


async def run_migrations(
    database_url: str,
    revision: str = "head",
    schema: Optional[str] = None,
) -> None:
    """Run Alembic migrations asynchronously against the target DB/schema."""
    from alembic import command

    if revision == "head":
        adopted = await adopt_existing_schema(database_url, schema=schema, revision=revision)
        if adopted:
            return

    await _run_alembic_command(
        database_url,
        schema=schema,
        ensure_schema=True,
        runner=lambda alembic_cfg: command.upgrade(alembic_cfg, revision),
    )


async def adopt_existing_schema(
    database_url: str,
    *,
    schema: Optional[str] = None,
    revision: str = "head",
) -> bool:
    """
    Stamp a legacy auth schema that was created outside Alembic.

    This is intended for older installs that used model bootstrap/create_all and
    therefore have a complete auth schema but no Alembic version table yet.
    """

    from alembic import command

    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)
    tables = await _list_schema_tables(normalized_url, target_schema)

    if ALEMBIC_VERSION_TABLE in tables:
        return False
    if not tables:
        return False

    if not LEGACY_SCHEMA_ADOPTION_TABLES.issubset(tables):
        missing_tables = sorted(LEGACY_SCHEMA_ADOPTION_TABLES - tables)
        schema_name = target_schema or "public"
        raise RuntimeError(
            "Target schema contains tables but is not versioned by Alembic. "
            f'Automatic adoption only supports fully bootstrapped auth schemas in "{schema_name}". '
            f"Missing required tables: {', '.join(missing_tables)}"
        )

    await _run_alembic_command(
        normalized_url,
        schema=target_schema,
        ensure_schema=True,
        runner=lambda alembic_cfg: command.stamp(alembic_cfg, revision),
    )
    return True


async def downgrade_migrations(
    database_url: str,
    revision: str = "-1",
    schema: Optional[str] = None,
) -> None:
    """Run Alembic downgrade asynchronously against the target DB/schema."""
    from alembic import command

    await _run_alembic_command(
        database_url,
        schema=schema,
        runner=lambda alembic_cfg: command.downgrade(alembic_cfg, revision),
    )


async def show_current_revision(
    database_url: str,
    schema: Optional[str] = None,
) -> None:
    """Print the active Alembic revision for the target DB/schema."""
    from alembic import command

    await _run_alembic_command(
        database_url,
        schema=schema,
        runner=lambda alembic_cfg: command.current(alembic_cfg),
    )


async def seed_system_state(
    database_url: str,
    *,
    schema: Optional[str] = None,
    include_permissions: bool = True,
    include_config: bool = True,
) -> tuple[int, int, bool]:
    """Seed library-owned permissions and config defaults."""

    from outlabs_auth.services.config import ConfigService
    from outlabs_auth.services.permission import PermissionService

    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)
    engine = _build_engine(normalized_url, target_schema)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    config = build_bootstrap_config(
        database_url=normalized_url,
        database_schema=target_schema,
    )
    permission_service = PermissionService(config)
    config_service = ConfigService()

    try:
        async with session_factory() as session:
            result = await seed_system_records(
                session,
                permission_service=permission_service,
                config_service=config_service,
                include_permissions=include_permissions,
                include_config=include_config,
            )
            await session.commit()
            return (
                result.permissions_created,
                result.permissions_existing,
                result.config_seeded,
            )
    finally:
        await engine.dispose()


async def bootstrap_admin_user(
    database_url: str,
    *,
    email: str,
    password: str,
    schema: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    root_entity_id: Optional[str] = None,
) -> tuple[str, str, str]:
    """Create the initial superuser in the target DB/schema."""

    from outlabs_auth.services.user import UserService

    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)
    engine = _build_engine(normalized_url, target_schema)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    config = build_bootstrap_config(
        database_url=normalized_url,
        database_schema=target_schema,
    )
    user_service = UserService(config)
    root_entity_uuid = UUID(root_entity_id) if root_entity_id else None

    try:
        async with session_factory() as session:
            result = await bootstrap_superuser(
                session,
                user_service=user_service,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                root_entity_id=root_entity_uuid,
            )
            await session.commit()
            return (result.status, result.user_id, result.email)
    finally:
        await engine.dispose()


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        click.echo("Error: DATABASE_URL environment variable not set", err=True)
        click.echo(
            "Example: postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth",
            err=True,
        )
        sys.exit(1)

    return normalize_database_url(url)


def get_target_schema_from_env() -> Optional[str]:
    """Get optional auth schema from environment."""
    return _validate_schema_name(os.environ.get("OUTLABS_AUTH_SCHEMA"))


@click.group()
@click.version_option(version=__version__, prog_name="outlabs-auth")
def main():
    """OutlabsAuth CLI - migrations, bootstrap, and inspection."""


@main.command()
@click.option("--revision", default="head", help="Target revision (default: head)")
def migrate(revision: str):
    """Run database migrations to specified revision."""
    click.echo(f"Running migrations to {revision}...")
    asyncio.run(
        run_migrations(
            get_database_url(),
            revision=revision,
            schema=get_target_schema_from_env(),
        )
    )
    click.echo("Done!")


@main.command("adopt-existing-schema")
@click.option("--revision", default="head", show_default=True, help="Alembic revision to stamp")
def adopt_existing_schema_command(revision: str):
    """Stamp a fully bootstrapped legacy auth schema into Alembic history."""
    click.echo(f"Checking for legacy auth schema adoption at revision {revision}...")
    adopted = asyncio.run(
        adopt_existing_schema(
            get_database_url(),
            schema=get_target_schema_from_env(),
            revision=revision,
        )
    )
    if adopted:
        click.echo("Stamped existing auth schema into Alembic history.")
    else:
        click.echo("No legacy auth schema adoption was needed.")


@main.command("seed-system")
@click.option(
    "--permissions/--no-permissions",
    default=True,
    show_default=True,
    help="Seed the library-owned permission catalog.",
)
@click.option(
    "--config/--no-config",
    "seed_config",
    default=True,
    show_default=True,
    help="Seed library-owned default config values.",
)
def seed_system(permissions: bool, seed_config: bool):
    """Seed library-owned permissions and default config into the target DB/schema."""
    click.echo("Seeding OutlabsAuth system records...")
    created, existing, config_seeded = asyncio.run(
        seed_system_state(
            get_database_url(),
            schema=get_target_schema_from_env(),
            include_permissions=permissions,
            include_config=seed_config,
        )
    )
    click.echo(
        "Permissions created: "
        f"{created} | existing: {existing} | config seeded: {'yes' if config_seeded else 'no'}"
    )


@main.command("bootstrap-admin")
@click.option("--email", envvar="OUTLABS_AUTH_BOOTSTRAP_EMAIL", required=True, help="Admin email address.")
@click.option(
    "--password",
    envvar="OUTLABS_AUTH_BOOTSTRAP_PASSWORD",
    required=True,
    help="Admin password.",
)
@click.option(
    "--first-name",
    envvar="OUTLABS_AUTH_BOOTSTRAP_FIRST_NAME",
    default="",
    show_default=False,
    help="Optional first name.",
)
@click.option(
    "--last-name",
    envvar="OUTLABS_AUTH_BOOTSTRAP_LAST_NAME",
    default="",
    show_default=False,
    help="Optional last name.",
)
@click.option(
    "--root-entity-id",
    default=None,
    help="Optional root entity ID for the admin user.",
)
def bootstrap_admin(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    root_entity_id: Optional[str],
):
    """Create the initial superuser if the auth system has no users yet."""
    click.echo("Bootstrapping OutlabsAuth admin user...")
    status_value, user_id, normalized_email = asyncio.run(
        bootstrap_admin_user(
            get_database_url(),
            schema=get_target_schema_from_env(),
            email=email,
            password=password,
            first_name=first_name or None,
            last_name=last_name or None,
            root_entity_id=root_entity_id,
        )
    )
    if status_value == "created":
        click.echo(f"Created bootstrap admin {normalized_email} ({user_id})")
    else:
        click.echo(f"Bootstrap admin already exists: {normalized_email} ({user_id})")


@main.command("init-db")
@click.option("--force", is_flag=True, help="Drop existing target schema/tables first")
def init_db(force: bool):
    """Create all database tables directly from models (development only)."""
    from outlabs_auth.models.sql import ALL_MODELS  # noqa: F401

    url = get_database_url()
    schema = get_target_schema_from_env()
    schema_name = schema or "public"

    async def create_tables():
        target_schema = _validate_schema_name(schema)
        if target_schema:
            await _ensure_schema_exists(url, target_schema)

        engine = _build_engine(url, target_schema)
        try:
            async with engine.begin() as conn:
                if force:
                    if target_schema:
                        click.echo(f'Dropping schema "{target_schema}"...')
                        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{target_schema}" CASCADE'))
                        await conn.execute(text(f'CREATE SCHEMA "{target_schema}"'))
                    else:
                        click.echo("Dropping existing public schema...")
                        await conn.execute(text("DROP SCHEMA public CASCADE"))
                        await conn.execute(text("CREATE SCHEMA public"))
                        await conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
                        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :schema_name"
                    ),
                    {"schema_name": schema_name},
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    count = asyncio.run(create_tables())
    click.echo(f"Created {count} tables in schema {schema_name}.")


@main.command("drop-db")
@click.confirmation_option(prompt="Are you sure you want to drop the target schema/tables?")
def drop_db():
    """Drop all database tables in the target schema (development only)."""
    url = get_database_url()
    schema = get_target_schema_from_env()

    async def drop_tables():
        engine = create_async_engine(normalize_database_url(url), echo=False)
        try:
            async with engine.begin() as conn:
                if schema:
                    await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                    await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                else:
                    await conn.execute(text("DROP SCHEMA public CASCADE"))
                    await conn.execute(text("CREATE SCHEMA public"))
                    await conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
                    await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        finally:
            await engine.dispose()

    click.echo("Dropping target schema/tables...")
    asyncio.run(drop_tables())
    click.echo("Done!")


@main.command()
def current():
    """Show current migration revision for the target DB/schema."""
    asyncio.run(
        show_current_revision(
            get_database_url(),
            schema=get_target_schema_from_env(),
        )
    )


@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed history")
def history(verbose: bool):
    """Show migration history from the packaged migration script."""
    from alembic import command

    alembic_cfg = _load_alembic_config()
    command.history(alembic_cfg, verbose=verbose)


@main.command()
@click.option("--message", "-m", required=True, help="Migration message")
@click.option("--autogenerate", is_flag=True, help="Auto-generate from model changes")
def revision(message: str, autogenerate: bool):
    """Create a new migration revision."""
    from alembic import command

    alembic_cfg = _load_alembic_config(require_local=True)

    click.echo(f"Creating migration: {message}")
    command.revision(alembic_cfg, message=message, autogenerate=autogenerate)
    click.echo("Done!")


@main.command()
def heads():
    """Show current available heads."""
    from alembic import command

    alembic_cfg = _load_alembic_config()
    command.heads(alembic_cfg)


@main.command()
@click.option("--revision", "-r", default="-1", help="Revision to downgrade to")
def downgrade(revision: str):
    """Downgrade to a previous revision."""
    click.echo(f"Downgrading to {revision}...")
    asyncio.run(
        downgrade_migrations(
            get_database_url(),
            revision=revision,
            schema=get_target_schema_from_env(),
        )
    )
    click.echo("Done!")


@main.command()
def tables():
    """List tables in the target schema."""
    url = get_database_url()
    schema = get_target_schema_from_env() or "public"

    async def list_tables():
        engine = create_async_engine(normalize_database_url(url), echo=False)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT table_name,
                               (SELECT COUNT(*) FROM information_schema.columns
                                WHERE table_name = t.table_name AND table_schema = :schema_name) AS column_count
                        FROM information_schema.tables t
                        WHERE table_schema = :schema_name
                        ORDER BY table_name
                        """
                    ),
                    {"schema_name": schema},
                )
                return [(row[0], row[1]) for row in result]
        finally:
            await engine.dispose()

    tables_list = asyncio.run(list_tables())
    if not tables_list:
        click.echo(f"No tables found in schema {schema}.")
        return

    click.echo(f"\nDatabase tables in schema {schema} ({len(tables_list)} total):\n")
    for table, columns in tables_list:
        click.echo(f"  {table} ({columns} columns)")


if __name__ == "__main__":
    main()
