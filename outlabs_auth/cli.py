"""
OutlabsAuth CLI

Command-line interface for database management and migrations.

Usage:
    outlabs-auth migrate          Run migrations to head
    outlabs-auth init-db          Create all tables (dev only)
    outlabs-auth drop-db          Drop all tables (dev only)
    outlabs-auth current          Show current migration revision
    outlabs-auth history          Show migration history
    outlabs-auth revision         Create a new migration
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Optional

import click
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_database_url(url: str) -> str:
    """Normalize postgres URLs to asyncpg SQLAlchemy format."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _resolve_alembic_ini() -> Path:
    """
    Resolve alembic.ini from package repository root first, then cwd.

    Library consumers may call run_migrations() from another project that also has
    an alembic.ini; we must prefer OutlabsAuth's migration config.
    """
    package_root = Path(__file__).resolve().parents[1]
    bundled_alembic = package_root / "alembic.ini"
    if bundled_alembic.exists():
        return bundled_alembic

    cwd_alembic = Path.cwd() / "alembic.ini"
    if cwd_alembic.exists():
        return cwd_alembic

    raise FileNotFoundError("alembic.ini not found. Expected in current working directory or package root.")


def _validate_schema_name(schema: Optional[str]) -> Optional[str]:
    """Validate schema identifier before using it in SQL or env context."""
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


async def run_migrations(
    database_url: str,
    revision: str = "head",
    schema: Optional[str] = None,
) -> None:
    """
    Run Alembic migrations asynchronously.

    This helper is safe to call from running event loops because Alembic runs
    in a background thread.
    """
    from alembic.config import Config

    from alembic import command

    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)

    if target_schema:
        engine = create_async_engine(normalized_url, echo=False)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{target_schema}"'))
        finally:
            await engine.dispose()

    def _upgrade() -> None:
        alembic_ini = _resolve_alembic_ini()
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", normalized_url)
        script_location = _resolve_script_location(alembic_ini)
        if script_location:
            alembic_cfg.set_main_option("script_location", script_location)

        previous_database_url = os.environ.get("DATABASE_URL")
        previous_schema = os.environ.get("OUTLABS_AUTH_SCHEMA")
        try:
            os.environ["DATABASE_URL"] = normalized_url
            if target_schema:
                os.environ["OUTLABS_AUTH_SCHEMA"] = target_schema
            else:
                os.environ.pop("OUTLABS_AUTH_SCHEMA", None)
            command.upgrade(alembic_cfg, revision)
        finally:
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url

            if previous_schema is None:
                os.environ.pop("OUTLABS_AUTH_SCHEMA", None)
            else:
                os.environ["OUTLABS_AUTH_SCHEMA"] = previous_schema

    await asyncio.to_thread(_upgrade)


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        click.echo("Error: DATABASE_URL environment variable not set", err=True)
        click.echo("Example: postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth", err=True)
        sys.exit(1)

    return normalize_database_url(url)


@click.group()
@click.version_option(version="2.0.0", prog_name="outlabs-auth")
def main():
    """OutlabsAuth CLI - Database management and migrations."""
    pass


@main.command()
@click.option("--revision", default="head", help="Target revision (default: head)")
def migrate(revision: str):
    """Run database migrations to specified revision."""
    from alembic.config import Config

    from alembic import command

    # Find alembic.ini
    alembic_ini = Path("alembic.ini")
    if not alembic_ini.exists():
        click.echo("Error: alembic.ini not found. Copy from alembic.ini.template", err=True)
        sys.exit(1)

    alembic_cfg = Config(str(alembic_ini))

    click.echo(f"Running migrations to {revision}...")
    command.upgrade(alembic_cfg, revision)
    click.echo("Done!")


@main.command("init-db")
@click.option("--force", is_flag=True, help="Drop existing tables first")
def init_db(force: bool):
    """Create all database tables (development only)."""
    # Import models to register them
    from outlabs_auth.models.sql import ALL_MODELS  # noqa: F401

    url = get_database_url()

    async def create_tables():
        engine = create_async_engine(url, echo=False)

        async with engine.begin() as conn:
            if force:
                click.echo("Dropping existing tables...")
                await conn.execute(text("DROP SCHEMA public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
                await conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
                await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

            click.echo("Creating tables...")
            await conn.run_sync(SQLModel.metadata.create_all)

        # Count tables created
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            )
            count = result.scalar()

        await engine.dispose()
        return count

    count = asyncio.run(create_tables())
    click.echo(f"Created {count} tables.")


@main.command("drop-db")
@click.confirmation_option(prompt="Are you sure you want to drop all tables?")
def drop_db():
    """Drop all database tables (development only)."""
    url = get_database_url()

    async def drop_tables():
        engine = create_async_engine(url, echo=False)

        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

        await engine.dispose()

    click.echo("Dropping all tables...")
    asyncio.run(drop_tables())
    click.echo("Done!")


@main.command()
def current():
    """Show current migration revision."""
    from alembic.config import Config

    from alembic import command

    alembic_ini = Path("alembic.ini")
    if not alembic_ini.exists():
        click.echo("Error: alembic.ini not found", err=True)
        sys.exit(1)

    alembic_cfg = Config(str(alembic_ini))
    command.current(alembic_cfg)


@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed history")
def history(verbose: bool):
    """Show migration history."""
    from alembic.config import Config

    from alembic import command

    alembic_ini = Path("alembic.ini")
    if not alembic_ini.exists():
        click.echo("Error: alembic.ini not found", err=True)
        sys.exit(1)

    alembic_cfg = Config(str(alembic_ini))
    command.history(alembic_cfg, verbose=verbose)


@main.command()
@click.option("--message", "-m", required=True, help="Migration message")
@click.option("--autogenerate", is_flag=True, help="Auto-generate from model changes")
def revision(message: str, autogenerate: bool):
    """Create a new migration revision."""
    from alembic.config import Config

    from alembic import command

    alembic_ini = Path("alembic.ini")
    if not alembic_ini.exists():
        click.echo("Error: alembic.ini not found", err=True)
        sys.exit(1)

    alembic_cfg = Config(str(alembic_ini))

    click.echo(f"Creating migration: {message}")
    command.revision(alembic_cfg, message=message, autogenerate=autogenerate)
    click.echo("Done!")


@main.command()
def heads():
    """Show current available heads."""
    from alembic.config import Config

    from alembic import command

    alembic_ini = Path("alembic.ini")
    if not alembic_ini.exists():
        click.echo("Error: alembic.ini not found", err=True)
        sys.exit(1)

    alembic_cfg = Config(str(alembic_ini))
    command.heads(alembic_cfg)


@main.command()
@click.option("--revision", "-r", default="-1", help="Revision to downgrade to")
def downgrade(revision: str):
    """Downgrade to a previous revision."""
    from alembic.config import Config

    from alembic import command

    alembic_ini = Path("alembic.ini")
    if not alembic_ini.exists():
        click.echo("Error: alembic.ini not found", err=True)
        sys.exit(1)

    alembic_cfg = Config(str(alembic_ini))

    click.echo(f"Downgrading to {revision}...")
    command.downgrade(alembic_cfg, revision)
    click.echo("Done!")


@main.command()
def tables():
    """List all database tables."""
    url = get_database_url()

    async def list_tables():
        engine = create_async_engine(url, echo=False)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT table_name,
                           (SELECT COUNT(*) FROM information_schema.columns
                            WHERE table_name = t.table_name AND table_schema = 'public') as column_count
                    FROM information_schema.tables t
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """
                )
            )
            tables = [(row[0], row[1]) for row in result]

        await engine.dispose()
        return tables

    tables_list = asyncio.run(list_tables())

    if not tables_list:
        click.echo("No tables found.")
        return

    click.echo(f"\nDatabase tables ({len(tables_list)} total):\n")
    for table, columns in tables_list:
        click.echo(f"  {table} ({columns} columns)")


if __name__ == "__main__":
    main()
