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
import sys
from pathlib import Path

import click
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        click.echo("Error: DATABASE_URL environment variable not set", err=True)
        click.echo("Example: postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth", err=True)
        sys.exit(1)

    # Normalize URL for asyncpg
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url


@click.group()
@click.version_option(version="2.0.0", prog_name="outlabs-auth")
def main():
    """OutlabsAuth CLI - Database management and migrations."""
    pass


@main.command()
@click.option("--revision", default="head", help="Target revision (default: head)")
def migrate(revision: str):
    """Run database migrations to specified revision."""
    from alembic import command
    from alembic.config import Config

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
    from alembic import command
    from alembic.config import Config

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
    from alembic import command
    from alembic.config import Config

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
    from alembic import command
    from alembic.config import Config

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
    from alembic import command
    from alembic.config import Config

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
    from alembic import command
    from alembic.config import Config

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
                text("""
                    SELECT table_name,
                           (SELECT COUNT(*) FROM information_schema.columns
                            WHERE table_name = t.table_name AND table_schema = 'public') as column_count
                    FROM information_schema.tables t
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
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
