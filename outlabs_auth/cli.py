"""
OutlabsAuth CLI.

Database-touching commands always target an explicit DB/schema and use a
caller-owned connection when invoking Alembic.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import sys
import time
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
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
from outlabs_auth.cli_support import (
    AgentFriendlyGroup,
    CliError,
    CliRuntime,
    emit_progress,
    emit_result,
    effective_output,
    get_runtime,
    require_confirmation,
)
from outlabs_auth.cli_support.remote_commands import register_remote_commands
from outlabs_auth.cli_support.runtime import EXIT_USAGE
from outlabs_auth.maintenance import MaintenanceReport

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALEMBIC_VERSION_TABLE = "outlabs_auth_alembic_version"
SQUASHED_BASELINE_REVISION = "20260316_0001"
DEFAULT_MIGRATION_STATEMENT_TIMEOUT = "60s"
logger = logging.getLogger("outlabs_auth")
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
        if cwd_alembic.exists():
            return cwd_alembic
        if repo_alembic.exists():
            return repo_alembic
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


def _build_connect_args(
    schema: Optional[str],
    *,
    statement_timeout: Optional[str] = DEFAULT_MIGRATION_STATEMENT_TIMEOUT,
) -> dict[str, object]:
    server_settings: dict[str, str] = {}
    if statement_timeout:
        server_settings["statement_timeout"] = statement_timeout

    target_schema = _validate_schema_name(schema)
    if target_schema:
        server_settings["search_path"] = f"{target_schema},public"

    return {"server_settings": server_settings} if server_settings else {}


def _build_engine(
    database_url: str,
    schema: Optional[str],
    *,
    statement_timeout: Optional[str] = None,
) -> AsyncEngine:
    return create_async_engine(
        normalize_database_url(database_url),
        echo=False,
        connect_args=_build_connect_args(schema, statement_timeout=statement_timeout),
    )


async def _dispose_engine_with_logging(engine: AsyncEngine, label: str = "migration engine") -> None:
    logger.info("[outlabs_auth] disposing %s...", label)
    started_at = time.perf_counter()
    await engine.dispose()
    logger.info("[outlabs_auth] %s disposed in %.2f s", label, time.perf_counter() - started_at)


async def _ensure_schema_exists(
    database_url: str,
    schema: Optional[str],
    *,
    engine: Optional[AsyncEngine] = None,
    statement_timeout: Optional[str] = DEFAULT_MIGRATION_STATEMENT_TIMEOUT,
) -> None:
    target_schema = _validate_schema_name(schema)
    if not target_schema:
        return

    owned_engine = engine is None
    if engine is None:
        engine = _build_engine(
            normalize_database_url(database_url),
            None,
            statement_timeout=statement_timeout,
        )
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{target_schema}"'))
    finally:
        if owned_engine:
            await _dispose_engine_with_logging(engine)


async def _list_schema_tables(
    database_url: str,
    schema: Optional[str],
    *,
    engine: Optional[AsyncEngine] = None,
    statement_timeout: Optional[str] = None,
) -> set[str]:
    schema_name = _validate_schema_name(schema) or "public"
    owned_engine = engine is None
    if engine is None:
        engine = _build_engine(
            normalize_database_url(database_url),
            None,
            statement_timeout=statement_timeout,
        )
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                    """),
                {"schema_name": schema_name},
            )
            return {str(row[0]) for row in result}
    finally:
        if owned_engine:
            await engine.dispose()


async def _get_database_revision(
    database_url: str,
    schema: Optional[str],
    *,
    engine: Optional[AsyncEngine] = None,
    statement_timeout: Optional[str] = None,
) -> Optional[str]:
    target = _validate_schema_name(schema) or "public"
    owned_engine = engine is None
    if engine is None:
        engine = _build_engine(
            normalize_database_url(database_url),
            None,
            statement_timeout=statement_timeout,
        )
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT version_num FROM "{target}"."{ALEMBIC_VERSION_TABLE}"'))
            row = result.first()
            return str(row[0]) if row else None
    finally:
        if owned_engine:
            await engine.dispose()


def _get_code_head_revision() -> Optional[str]:
    from alembic.script import ScriptDirectory

    alembic_cfg = _load_alembic_config()
    script = ScriptDirectory.from_config(alembic_cfg)
    return script.get_current_head()


async def _database_revision_matches_head(
    database_url: str,
    schema: Optional[str],
    *,
    engine: AsyncEngine,
) -> bool:
    tables = await _list_schema_tables(database_url, schema, engine=engine)
    if ALEMBIC_VERSION_TABLE not in tables:
        return False
    return await _get_database_revision(database_url, schema, engine=engine) == _get_code_head_revision()


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
    engine: Optional[AsyncEngine] = None,
    statement_timeout: Optional[str] = DEFAULT_MIGRATION_STATEMENT_TIMEOUT,
    operation_label: str = "alembic command",
) -> None:
    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)
    if ensure_schema:
        await _ensure_schema_exists(
            normalized_url,
            target_schema,
            engine=engine,
            statement_timeout=statement_timeout,
        )

    owned_engine = engine is None
    if engine is None:
        engine = _build_engine(
            normalized_url,
            target_schema,
            statement_timeout=statement_timeout,
        )
    try:
        logger.info("[outlabs_auth] %s: starting", operation_label)
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
        logger.info("[outlabs_auth] %s: completed", operation_label)
    finally:
        if owned_engine:
            await _dispose_engine_with_logging(engine)


async def run_migrations(
    database_url: str,
    revision: str = "head",
    schema: Optional[str] = None,
    statement_timeout: Optional[str] = DEFAULT_MIGRATION_STATEMENT_TIMEOUT,
) -> None:
    """Run Alembic migrations asynchronously against the target DB/schema."""
    from alembic import command

    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)
    engine = _build_engine(
        normalized_url,
        target_schema,
        statement_timeout=statement_timeout,
    )
    try:
        if revision == "head":
            await adopt_existing_schema(
                normalized_url,
                schema=target_schema,
                revision=SQUASHED_BASELINE_REVISION,
                engine=engine,
                statement_timeout=statement_timeout,
            )
            if await _database_revision_matches_head(
                normalized_url,
                target_schema,
                engine=engine,
            ):
                logger.info("[outlabs_auth] migration upgrade: at head, no work to do")
                return

        await _run_alembic_command(
            normalized_url,
            schema=target_schema,
            ensure_schema=True,
            engine=engine,
            statement_timeout=statement_timeout,
            operation_label=f"migration upgrade to {revision}",
            runner=lambda alembic_cfg: command.upgrade(alembic_cfg, revision),
        )
    finally:
        await _dispose_engine_with_logging(engine)


async def adopt_existing_schema(
    database_url: str,
    *,
    schema: Optional[str] = None,
    revision: str = "head",
    engine: Optional[AsyncEngine] = None,
    statement_timeout: Optional[str] = DEFAULT_MIGRATION_STATEMENT_TIMEOUT,
) -> bool:
    """
    Stamp a legacy auth schema that was created outside Alembic.

    This is intended for older installs that used model bootstrap/create_all and
    therefore have a complete auth schema but no Alembic version table yet.
    """

    from alembic import command

    normalized_url = normalize_database_url(database_url)
    target_schema = _validate_schema_name(schema)
    owned_engine = engine is None
    if engine is None:
        engine = _build_engine(
            normalized_url,
            target_schema,
            statement_timeout=statement_timeout,
        )

    try:
        tables = await _list_schema_tables(normalized_url, target_schema, engine=engine)

        if ALEMBIC_VERSION_TABLE in tables:
            logger.info("[outlabs_auth] adopt_existing_schema: schema already versioned, skipping stamp")
            return False
        if not tables:
            logger.info("[outlabs_auth] adopt_existing_schema: target schema is empty, skipping stamp")
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
            engine=engine,
            statement_timeout=statement_timeout,
            operation_label=f"adopt_existing_schema stamp to {revision}",
            runner=lambda alembic_cfg: command.stamp(alembic_cfg, revision),
        )
        logger.info("[outlabs_auth] adopt_existing_schema: stamped schema at %s", revision)
        return True
    finally:
        if owned_engine:
            await _dispose_engine_with_logging(engine)


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
        raise CliError(
            code="DATABASE_URL_MISSING",
            message="DATABASE_URL environment variable not set.",
            exit_code=EXIT_USAGE,
            hint=(
                "Export a postgresql+asyncpg:// URL for the target database. "
                "Database URLs are intentionally not accepted as command-line flags because they may contain secrets."
            ),
        )

    return normalize_database_url(url)


def get_target_schema_from_env() -> Optional[str]:
    """Get optional auth schema from environment."""
    runtime = get_runtime()
    value = runtime.schema if runtime.schema is not None else os.environ.get("OUTLABS_AUTH_SCHEMA")
    try:
        return _validate_schema_name(value)
    except ValueError as exc:
        raise CliError(
            code="INVALID_SCHEMA",
            message=str(exc),
            exit_code=EXIT_USAGE,
            details={"schema": value},
        ) from exc


# ============================================================================
# Doctor — read-only diagnostics
# ============================================================================


class DoctorStatus:
    OK = "ok"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str
    remediation: Optional[str] = None


DOCTOR_CHECK_NAMES = (
    "Database connectivity",
    "Target schema",
    "Alembic version table",
    "Revision matches code",
    "Core auth tables",
)


def _redact_database_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return "<unparseable URL>"
    redacted_netloc = parsed.netloc
    if parsed.password:
        redacted_netloc = redacted_netloc.replace(f":{parsed.password}@", ":****@", 1)

    sensitive_query_names = {
        "access_token",
        "api_key",
        "credential",
        "key",
        "pass",
        "password",
        "secret",
        "token",
    }
    query = parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = urlencode(
        [(name, "****" if name.lower() in sensitive_query_names else value) for name, value in query]
    )
    return urlunparse(parsed._replace(netloc=redacted_netloc, query=redacted_query))


async def _check_connectivity(database_url: str) -> DoctorCheck:
    engine = create_async_engine(normalize_database_url(database_url), echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return DoctorCheck(
            name="Database connectivity",
            status=DoctorStatus.OK,
            detail="Connected successfully",
        )
    except Exception as exc:
        return DoctorCheck(
            name="Database connectivity",
            status=DoctorStatus.FAIL,
            detail=f"Cannot reach database: {type(exc).__name__}",
            remediation="Verify DATABASE_URL and that Postgres is reachable from this host.",
        )
    finally:
        await engine.dispose()


async def _check_target_schema(database_url: str, schema: Optional[str]) -> DoctorCheck:
    if not schema:
        return DoctorCheck(
            name="Target schema",
            status=DoctorStatus.OK,
            detail="OUTLABS_AUTH_SCHEMA is unset; using 'public'",
        )
    engine = create_async_engine(normalize_database_url(database_url), echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :name"),
                {"name": schema},
            )
            exists = result.first() is not None
    finally:
        await engine.dispose()

    if exists:
        return DoctorCheck(
            name="Target schema",
            status=DoctorStatus.OK,
            detail=f"Schema '{schema}' exists",
        )
    return DoctorCheck(
        name="Target schema",
        status=DoctorStatus.FAIL,
        detail=f"Schema '{schema}' does not exist",
        remediation="Run: outlabs-auth migrate",
    )


async def _check_alembic_version_table(database_url: str, schema: Optional[str]) -> DoctorCheck:
    tables = await _list_schema_tables(database_url, schema)
    if ALEMBIC_VERSION_TABLE in tables:
        return DoctorCheck(
            name="Alembic version table",
            status=DoctorStatus.OK,
            detail=f"{ALEMBIC_VERSION_TABLE} present",
        )
    if not tables:
        return DoctorCheck(
            name="Alembic version table",
            status=DoctorStatus.FAIL,
            detail="Schema is empty",
            remediation="Run: outlabs-auth migrate",
        )
    if LEGACY_SCHEMA_ADOPTION_TABLES.issubset(tables):
        return DoctorCheck(
            name="Alembic version table",
            status=DoctorStatus.FAIL,
            detail="Pre-Alembic auth schema detected",
            remediation="Run: outlabs-auth adopt-existing-schema",
        )
    return DoctorCheck(
        name="Alembic version table",
        status=DoctorStatus.FAIL,
        detail=f"Tables exist but {ALEMBIC_VERSION_TABLE} is missing",
        remediation="Run: outlabs-auth migrate",
    )


async def _check_revision(database_url: str, schema: Optional[str]) -> DoctorCheck:
    from alembic.script import ScriptDirectory

    target = _validate_schema_name(schema) or "public"
    engine = create_async_engine(normalize_database_url(database_url), echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT version_num FROM "{target}"."{ALEMBIC_VERSION_TABLE}"'))
            row = result.first()
            db_revision = str(row[0]) if row else None
    finally:
        await engine.dispose()

    alembic_cfg = _load_alembic_config()
    script = ScriptDirectory.from_config(alembic_cfg)
    code_head = script.get_current_head()

    if db_revision is None:
        return DoctorCheck(
            name="Revision matches code",
            status=DoctorStatus.FAIL,
            detail="Alembic version table exists but is empty",
            remediation="Run: outlabs-auth migrate",
        )
    if db_revision == code_head:
        return DoctorCheck(
            name="Revision matches code",
            status=DoctorStatus.OK,
            detail=f"At head ({code_head})",
        )
    try:
        script.get_revision(db_revision)
        known = True
    except Exception:
        known = False
    if not known:
        return DoctorCheck(
            name="Revision matches code",
            status=DoctorStatus.FAIL,
            detail=f"DB is at unknown revision '{db_revision}'; code head is '{code_head}'",
            remediation="Investigate schema drift; confirm the installed library version matches this database.",
        )
    return DoctorCheck(
        name="Revision matches code",
        status=DoctorStatus.FAIL,
        detail=f"DB is at '{db_revision}', code head is '{code_head}'",
        remediation="Run: outlabs-auth migrate",
    )


async def _check_core_tables(database_url: str, schema: Optional[str]) -> DoctorCheck:
    tables = await _list_schema_tables(database_url, schema)
    missing = sorted(LEGACY_SCHEMA_ADOPTION_TABLES - tables)
    if not missing:
        return DoctorCheck(
            name="Core auth tables",
            status=DoctorStatus.OK,
            detail=f"All {len(LEGACY_SCHEMA_ADOPTION_TABLES)} core tables present",
        )
    return DoctorCheck(
        name="Core auth tables",
        status=DoctorStatus.FAIL,
        detail=f"Missing: {', '.join(missing)}",
        remediation="Run: outlabs-auth migrate",
    )


def _skip(name: str, reason: str) -> DoctorCheck:
    return DoctorCheck(name=name, status=DoctorStatus.SKIP, detail=f"Skipped — {reason}")


async def run_doctor(database_url: str, schema: Optional[str]) -> list[DoctorCheck]:
    """Run all doctor checks sequentially, short-circuiting on prerequisite failures.

    Read-only: never mutates schema, tables, or rows.
    """
    checks: list[DoctorCheck] = []

    connectivity = await _check_connectivity(database_url)
    checks.append(connectivity)
    if connectivity.status != DoctorStatus.OK:
        for name in DOCTOR_CHECK_NAMES[1:]:
            checks.append(_skip(name, "database unreachable"))
        return checks

    schema_check = await _check_target_schema(database_url, schema)
    checks.append(schema_check)
    if schema_check.status != DoctorStatus.OK:
        for name in DOCTOR_CHECK_NAMES[2:]:
            checks.append(_skip(name, "target schema missing"))
        return checks

    alembic_check = await _check_alembic_version_table(database_url, schema)
    checks.append(alembic_check)
    if alembic_check.status != DoctorStatus.OK:
        checks.append(_skip("Revision matches code", "Alembic version table missing"))
        checks.append(await _check_core_tables(database_url, schema))
        return checks

    checks.append(await _check_revision(database_url, schema))
    checks.append(await _check_core_tables(database_url, schema))
    return checks


def _format_doctor_text(
    checks: list[DoctorCheck],
    database_url: str,
    schema: Optional[str],
) -> str:
    symbols = {
        DoctorStatus.OK: "[OK]",
        DoctorStatus.FAIL: "[FAIL]",
        DoctorStatus.SKIP: "[--]",
    }
    name_width = max((len(c.name) for c in checks), default=0)

    lines = [
        "OutlabsAuth Doctor",
        f"  Database: {_redact_database_url(database_url)}",
        f"  Schema:   {schema or '(public)'}",
        "",
    ]
    for check in checks:
        symbol = symbols.get(check.status, "[?]")
        lines.append(f"  {symbol:<6} {check.name:<{name_width}}  {check.detail}")
        if check.status == DoctorStatus.FAIL and check.remediation:
            lines.append(f"         -> {check.remediation}")

    failed = sum(1 for c in checks if c.status == DoctorStatus.FAIL)
    lines.append("")
    if failed:
        plural = "s" if failed != 1 else ""
        lines.append(f"{failed} check{plural} failed. See remediation above.")
    else:
        lines.append("All checks passed.")
    return "\n".join(lines)


def _format_doctor_json(
    checks: list[DoctorCheck],
    database_url: str,
    schema: Optional[str],
) -> str:
    healthy = all(c.status == DoctorStatus.OK for c in checks)
    payload = {
        "database_url": _redact_database_url(database_url),
        "schema": schema,
        "healthy": healthy,
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "detail": c.detail,
                **({"remediation": c.remediation} if c.remediation else {}),
            }
            for c in checks
        ],
    }
    return json.dumps(payload, indent=2)


# ============================================================================
# Bootstrap — safe idempotent first-boot orchestration
# ============================================================================


class SchemaState:
    """Target-schema classification used to plan bootstrap actions."""

    NO_CONNECTION = "no_connection"
    SCHEMA_MISSING = "schema_missing"
    EMPTY = "empty"
    LEGACY = "legacy"
    PARTIAL_NON_AUTH = "partial_non_auth"
    ALEMBIC_EMPTY = "alembic_empty"
    DRIFTED = "drifted"
    HEALTHY_BEHIND = "healthy_behind"
    HEALTHY_CURRENT = "healthy_current"


class BootstrapAction:
    MIGRATE = "migrate"
    SKIP_MIGRATE = "skip_migrate"
    SEED = "seed"
    CREATE_ADMIN = "create_admin"
    SKIP_ADMIN = "skip_admin"


@dataclass(frozen=True)
class BootstrapStep:
    action: str
    detail: str


@dataclass(frozen=True)
class BootstrapStepResult:
    action: str
    status: str
    detail: str


@dataclass(frozen=True)
class BootstrapPlan:
    state: str
    state_detail: str
    can_proceed: bool
    steps: tuple[BootstrapStep, ...]
    abort_reason: Optional[str] = None


@dataclass(frozen=True)
class BootstrapResult:
    plan: BootstrapPlan
    dry_run: bool
    success: bool
    executed: tuple[BootstrapStepResult, ...]
    final_checks: tuple[DoctorCheck, ...]
    error: Optional[str]


_ABORT_STATES = frozenset(
    {
        SchemaState.NO_CONNECTION,
        SchemaState.SCHEMA_MISSING,
        SchemaState.PARTIAL_NON_AUTH,
        SchemaState.DRIFTED,
    }
)


async def _classify_schema_state(database_url: str, schema: Optional[str]) -> tuple[str, str]:
    """Classify the target schema for bootstrap planning (read-only).

    Returns a ``(state, detail)`` tuple where ``state`` is one of the
    ``SchemaState`` constants and ``detail`` is a human-readable explanation.
    """
    normalized_url = normalize_database_url(database_url)

    engine = create_async_engine(normalized_url, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        return SchemaState.NO_CONNECTION, f"Cannot reach database: {type(exc).__name__}"
    else:
        await engine.dispose()

    if schema:
        exists_engine = create_async_engine(normalized_url, echo=False)
        try:
            async with exists_engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :name"),
                    {"name": schema},
                )
                if result.first() is None:
                    return (
                        SchemaState.SCHEMA_MISSING,
                        f"Schema '{schema}' does not exist",
                    )
        finally:
            await exists_engine.dispose()

    tables = await _list_schema_tables(normalized_url, schema)
    if not tables:
        return SchemaState.EMPTY, "Target schema is empty"

    if ALEMBIC_VERSION_TABLE not in tables:
        if LEGACY_SCHEMA_ADOPTION_TABLES.issubset(tables):
            return (
                SchemaState.LEGACY,
                "Pre-Alembic auth schema detected; adoption is safe",
            )
        return (
            SchemaState.PARTIAL_NON_AUTH,
            "Schema contains tables that are neither the legacy auth set nor " "the Alembic version table",
        )

    from alembic.script import ScriptDirectory

    target = _validate_schema_name(schema) or "public"
    rev_engine = create_async_engine(normalized_url, echo=False)
    try:
        async with rev_engine.connect() as conn:
            result = await conn.execute(text(f'SELECT version_num FROM "{target}"."{ALEMBIC_VERSION_TABLE}"'))
            row = result.first()
            db_revision = str(row[0]) if row else None
    finally:
        await rev_engine.dispose()

    if db_revision is None:
        return (
            SchemaState.ALEMBIC_EMPTY,
            "Alembic version table exists but is empty",
        )

    alembic_cfg = _load_alembic_config()
    script = ScriptDirectory.from_config(alembic_cfg)
    code_head = script.get_current_head()

    if db_revision == code_head:
        return SchemaState.HEALTHY_CURRENT, f"At head ({code_head})"

    try:
        script.get_revision(db_revision)
    except Exception:
        return (
            SchemaState.DRIFTED,
            f"DB is at unknown revision '{db_revision}'; code head is '{code_head}'",
        )

    return (
        SchemaState.HEALTHY_BEHIND,
        f"DB is at '{db_revision}', code head is '{code_head}'",
    )


def _build_bootstrap_plan(
    state: str,
    state_detail: str,
    *,
    skip_seed: bool,
    admin_email: Optional[str],
) -> BootstrapPlan:
    """Translate a classified state into an ordered, executable plan."""
    if state in _ABORT_STATES:
        abort_messages = {
            SchemaState.NO_CONNECTION: state_detail,
            SchemaState.SCHEMA_MISSING: (
                f"{state_detail}. Create the schema explicitly (CREATE SCHEMA or "
                "outlabs-auth init-db) before re-running bootstrap."
            ),
            SchemaState.PARTIAL_NON_AUTH: (
                f"{state_detail}. Refusing to co-tenant into an unclaimed schema; " "inspect contents manually."
            ),
            SchemaState.DRIFTED: (
                f"{state_detail}. Run 'outlabs-auth doctor' for details and confirm the "
                "installed library version matches this database before migrating."
            ),
        }
        return BootstrapPlan(
            state=state,
            state_detail=state_detail,
            can_proceed=False,
            steps=(),
            abort_reason=abort_messages[state],
        )

    steps: list[BootstrapStep] = []
    if state == SchemaState.EMPTY:
        steps.append(BootstrapStep(BootstrapAction.MIGRATE, "Run all migrations to head"))
    elif state == SchemaState.LEGACY:
        steps.append(
            BootstrapStep(
                BootstrapAction.MIGRATE,
                "Stamp pre-Alembic auth schema, then upgrade to head",
            )
        )
    elif state == SchemaState.ALEMBIC_EMPTY:
        steps.append(BootstrapStep(BootstrapAction.MIGRATE, "Run all migrations to head"))
    elif state == SchemaState.HEALTHY_BEHIND:
        steps.append(BootstrapStep(BootstrapAction.MIGRATE, "Upgrade to head"))
    elif state == SchemaState.HEALTHY_CURRENT:
        steps.append(BootstrapStep(BootstrapAction.SKIP_MIGRATE, "Schema already at head"))

    if not skip_seed:
        steps.append(BootstrapStep(BootstrapAction.SEED, "Seed permissions and config"))

    if admin_email:
        steps.append(
            BootstrapStep(
                BootstrapAction.CREATE_ADMIN,
                f"Ensure admin user exists: {admin_email}",
            )
        )
    else:
        steps.append(
            BootstrapStep(
                BootstrapAction.SKIP_ADMIN,
                "No --admin-email provided; skipping admin creation",
            )
        )

    return BootstrapPlan(
        state=state,
        state_detail=state_detail,
        can_proceed=True,
        steps=tuple(steps),
    )


async def run_bootstrap(
    database_url: str,
    schema: Optional[str],
    *,
    skip_seed: bool = False,
    admin_email: Optional[str] = None,
    admin_password: Optional[str] = None,
    admin_first_name: Optional[str] = None,
    admin_last_name: Optional[str] = None,
    dry_run: bool = False,
) -> BootstrapResult:
    """Classify schema state, build a plan, and execute (unless dry-run).

    On successful execution, runs a final doctor pass to confirm the healthy
    end state. Idempotent: re-running against an already-bootstrapped schema
    is a safe no-op on migrate/admin steps.
    """
    state, state_detail = await _classify_schema_state(database_url, schema)
    plan = _build_bootstrap_plan(state, state_detail, skip_seed=skip_seed, admin_email=admin_email)

    if not plan.can_proceed:
        return BootstrapResult(
            plan=plan,
            dry_run=dry_run,
            success=False,
            executed=(),
            final_checks=(),
            error=plan.abort_reason,
        )

    if dry_run:
        return BootstrapResult(
            plan=plan,
            dry_run=True,
            success=True,
            executed=(),
            final_checks=(),
            error=None,
        )

    executed: list[BootstrapStepResult] = []
    try:
        for step in plan.steps:
            if step.action == BootstrapAction.MIGRATE:
                await run_migrations(database_url, schema=schema)
                executed.append(
                    BootstrapStepResult(
                        action=step.action,
                        status=DoctorStatus.OK,
                        detail="Migrated to head",
                    )
                )
            elif step.action == BootstrapAction.SKIP_MIGRATE:
                executed.append(
                    BootstrapStepResult(
                        action=step.action,
                        status=DoctorStatus.SKIP,
                        detail="Already at head",
                    )
                )
            elif step.action == BootstrapAction.SEED:
                created, existing, config_seeded = await seed_system_state(database_url, schema=schema)
                executed.append(
                    BootstrapStepResult(
                        action=step.action,
                        status=DoctorStatus.OK,
                        detail=(
                            f"Permissions: {created} created, {existing} existing; "
                            f"config: {'seeded' if config_seeded else 'already present'}"
                        ),
                    )
                )
            elif step.action == BootstrapAction.CREATE_ADMIN:
                if not admin_password:
                    raise RuntimeError(
                        "--admin-password (or OUTLABS_AUTH_BOOTSTRAP_PASSWORD) is required " "when --admin-email is set"
                    )
                status_str, user_id, email = await bootstrap_admin_user(
                    database_url,
                    schema=schema,
                    email=admin_email or "",
                    password=admin_password,
                    first_name=admin_first_name,
                    last_name=admin_last_name,
                )
                executed.append(
                    BootstrapStepResult(
                        action=step.action,
                        status=DoctorStatus.OK,
                        detail=f"Admin {status_str}: {email} ({user_id})",
                    )
                )
            elif step.action == BootstrapAction.SKIP_ADMIN:
                executed.append(
                    BootstrapStepResult(
                        action=step.action,
                        status=DoctorStatus.SKIP,
                        detail="No admin email provided",
                    )
                )
    except Exception as exc:
        return BootstrapResult(
            plan=plan,
            dry_run=False,
            success=False,
            executed=tuple(executed),
            final_checks=(),
            error=f"{type(exc).__name__}: {exc}",
        )

    final_checks = await run_doctor(database_url, schema)
    success = all(c.status == DoctorStatus.OK for c in final_checks)
    return BootstrapResult(
        plan=plan,
        dry_run=False,
        success=success,
        executed=tuple(executed),
        final_checks=tuple(final_checks),
        error=None if success else "Final doctor check reported failures",
    )


def _format_bootstrap_text(
    result: BootstrapResult,
    database_url: str,
    schema: Optional[str],
) -> str:
    symbols = {
        DoctorStatus.OK: "[OK]",
        DoctorStatus.FAIL: "[FAIL]",
        DoctorStatus.SKIP: "[--]",
    }
    lines = [
        "OutlabsAuth Bootstrap",
        f"  Database: {_redact_database_url(database_url)}",
        f"  Schema:   {schema or '(public)'}",
        f"  State:    {result.plan.state} - {result.plan.state_detail}",
        "",
    ]

    if not result.plan.can_proceed:
        lines.append("Refusing to bootstrap:")
        lines.append(f"  {result.plan.abort_reason}")
        return "\n".join(lines)

    if result.dry_run:
        lines.append("Plan (dry-run - no changes applied):")
        for idx, step in enumerate(result.plan.steps, 1):
            lines.append(f"  {idx}. [{step.action}] {step.detail}")
        lines.append("")
        lines.append("Re-run without --dry-run to execute.")
        return "\n".join(lines)

    lines.append("Executed:")
    for step_result in result.executed:
        symbol = symbols.get(step_result.status, "[?]")
        lines.append(f"  {symbol:<6} [{step_result.action}] {step_result.detail}")

    if result.final_checks:
        lines.append("")
        lines.append("Final health check:")
        for check in result.final_checks:
            symbol = symbols.get(check.status, "[?]")
            lines.append(f"  {symbol:<6} {check.name} - {check.detail}")
            if check.status == DoctorStatus.FAIL and check.remediation:
                lines.append(f"         -> {check.remediation}")

    lines.append("")
    if result.success:
        lines.append("Bootstrap complete.")
    else:
        lines.append(f"Bootstrap did not complete cleanly: {result.error}")
    return "\n".join(lines)


def _format_bootstrap_json(
    result: BootstrapResult,
    database_url: str,
    schema: Optional[str],
) -> str:
    payload: dict[str, object] = {
        "database_url": _redact_database_url(database_url),
        "schema": schema,
        "state": result.plan.state,
        "state_detail": result.plan.state_detail,
        "can_proceed": result.plan.can_proceed,
        "dry_run": result.dry_run,
        "success": result.success,
        "plan": [{"action": s.action, "detail": s.detail} for s in result.plan.steps],
        "executed": [{"action": e.action, "status": e.status, "detail": e.detail} for e in result.executed],
        "final_checks": [
            {
                "name": c.name,
                "status": c.status,
                "detail": c.detail,
                **({"remediation": c.remediation} if c.remediation else {}),
            }
            for c in result.final_checks
        ],
        "error": result.error,
    }
    if not result.plan.can_proceed:
        payload["abort_reason"] = result.plan.abort_reason
    return json.dumps(payload, indent=2)


@click.group(cls=AgentFriendlyGroup)
@click.version_option(version=__version__, prog_name="outlabs-auth")
@click.option(
    "--output",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    envvar="OUTLABS_AUTH_OUTPUT",
    help="Global output contract. JSON uses the versioned CLI envelope.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    envvar="OUTLABS_AUTH_NON_INTERACTIVE",
    help="Never prompt; fail with a structured interaction-required error.",
)
@click.option("--profile", envvar="OUTLABS_AUTH_PROFILE", help="Remote context profile to use.")
@click.option("--base-url", envvar="OUTLABS_AUTH_BASE_URL", help="One-off remote API base URL.")
@click.option("--api-prefix", envvar="OUTLABS_AUTH_API_PREFIX", help="Override the remote API prefix.")
@click.option(
    "--credential-type",
    type=click.Choice(["bearer", "api-key"]),
    default=None,
    envvar="OUTLABS_AUTH_CREDENTIAL_TYPE",
    help="Override the remote credential transport.",
)
@click.option(
    "--credential-env",
    default=None,
    envvar="OUTLABS_AUTH_CREDENTIAL_ENV",
    help="Override the environment variable containing the remote credential.",
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.1, max=300.0),
    default=10.0,
    show_default=True,
    envvar="OUTLABS_AUTH_TIMEOUT",
    help="Remote request timeout in seconds.",
)
@click.option("--schema", envvar="OUTLABS_AUTH_SCHEMA", help="Target schema for local database commands.")
@click.option("--debug", is_flag=True, envvar="OUTLABS_AUTH_DEBUG", help="Show tracebacks for unexpected failures.")
@click.pass_context
def main(
    ctx: click.Context,
    output: str,
    non_interactive: bool,
    profile: Optional[str],
    base_url: Optional[str],
    api_prefix: Optional[str],
    credential_type: Optional[str],
    credential_env: Optional[str],
    timeout: float,
    schema: Optional[str],
    debug: bool,
):
    """Operate OutlabsAuth locally or administer a mounted remote API."""

    ctx.obj = CliRuntime(
        output=output,
        non_interactive=non_interactive,
        debug=debug,
        profile=profile,
        base_url=base_url,
        api_prefix=api_prefix,
        credential_type=credential_type.replace("-", "_") if credential_type else None,
        credential_env=credential_env,
        timeout=timeout,
        schema=schema,
    )


register_remote_commands(main)


@main.command()
@click.option("--revision", default="head", help="Target revision (default: head)")
def migrate(revision: str):
    """Run database migrations to specified revision."""
    url = get_database_url()
    schema = get_target_schema_from_env()
    emit_progress(f"Running migrations to {revision}...")
    asyncio.run(
        run_migrations(
            url,
            revision=revision,
            schema=schema,
        )
    )
    emit_result(
        "db.migrate",
        {"revision": revision, "schema": schema or "public"},
        changed=True,
        text="Done!",
    )


async def _run_maintenance_once(
    *,
    database_url: str,
    secret_key: str,
    redis_url: str | None,
    redis_key_prefix: str | None,
) -> MaintenanceReport:
    from outlabs_auth.presets.simple import SimpleRBAC

    auth = SimpleRBAC(
        database_url=normalize_database_url(database_url),
        database_schema=get_target_schema_from_env(),
        secret_key=secret_key,
        redis_enabled=bool(redis_url),
        redis_url=redis_url,
        redis_key_prefix=redis_key_prefix,
        background_job_mode="disabled",
    )
    try:
        await auth.initialize()
        return await auth.run_maintenance_once()
    finally:
        await auth.shutdown()


@main.command("run-maintenance")
def run_maintenance_command():
    """Run one deterministic auth-maintenance cycle for an external scheduler.

    Invoke this from exactly one CronJob, worker deployment, or host scheduler.
    It deliberately does not start an in-web-process loop.
    """
    database_url = os.environ.get("DATABASE_URL")
    secret_key = os.environ.get("SECRET_KEY")
    redis_url = os.environ.get("REDIS_URL")
    redis_key_prefix = os.environ.get("OUTLABS_AUTH_REDIS_KEY_PREFIX")
    if not database_url:
        raise CliError(
            code="DATABASE_URL_MISSING",
            message="DATABASE_URL environment variable not set.",
            exit_code=EXIT_USAGE,
        )
    if not secret_key:
        raise CliError(
            code="SECRET_KEY_MISSING",
            message="SECRET_KEY environment variable is not set.",
            exit_code=EXIT_USAGE,
        )
    if redis_url and not redis_key_prefix:
        raise CliError(
            code="REDIS_KEY_PREFIX_MISSING",
            message="OUTLABS_AUTH_REDIS_KEY_PREFIX is required when REDIS_URL is configured.",
            exit_code=EXIT_USAGE,
        )

    report = asyncio.run(
        _run_maintenance_once(
            database_url=database_url,
            secret_key=secret_key,
            redis_url=redis_url,
            redis_key_prefix=redis_key_prefix,
        )
    )
    result = report.model_dump(mode="json")
    emit_result(
        "ops.run-maintenance",
        result,
        text=json.dumps(result, default=str, sort_keys=True),
    )
    if not report.ok:
        raise click.exceptions.Exit(1)


@main.command("adopt-existing-schema")
@click.option("--revision", default="head", show_default=True, help="Alembic revision to stamp")
def adopt_existing_schema_command(revision: str):
    """Stamp a fully bootstrapped legacy auth schema into Alembic history."""
    url = get_database_url()
    schema = get_target_schema_from_env()
    emit_progress(f"Checking for legacy auth schema adoption at revision {revision}...")
    adopted = asyncio.run(
        adopt_existing_schema(
            url,
            schema=schema,
            revision=revision,
        )
    )
    text_output = (
        "Stamped existing auth schema into Alembic history."
        if adopted
        else "No legacy auth schema adoption was needed."
    )
    emit_result(
        "db.adopt-existing-schema",
        {"adopted": adopted, "revision": revision, "schema": schema or "public"},
        changed=adopted,
        text=text_output,
    )


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
    url = get_database_url()
    schema = get_target_schema_from_env()
    emit_progress("Seeding OutlabsAuth system records...")
    created, existing, config_seeded = asyncio.run(
        seed_system_state(
            url,
            schema=schema,
            include_permissions=permissions,
            include_config=seed_config,
        )
    )
    emit_result(
        "db.seed-system",
        {
            "permissions_created": created,
            "permissions_existing": existing,
            "config_seeded": config_seeded,
            "schema": schema or "public",
        },
        changed=created > 0 or config_seeded,
        text=(
            "Permissions created: "
            f"{created} | existing: {existing} | config seeded: {'yes' if config_seeded else 'no'}"
        ),
    )


@main.command("bootstrap-admin")
@click.option("--email", envvar="OUTLABS_AUTH_BOOTSTRAP_EMAIL", required=True, help="Admin email address.")
@click.option(
    "--password",
    envvar="OUTLABS_AUTH_BOOTSTRAP_PASSWORD",
    default=None,
    help="Admin password. Prefer the environment or --password-stdin to avoid process-list exposure.",
)
@click.option("--password-stdin", is_flag=True, help="Read the admin password from one line on stdin.")
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
    password: Optional[str],
    password_stdin: bool,
    first_name: str,
    last_name: str,
    root_entity_id: Optional[str],
):
    """Create the initial superuser if the auth system has no users yet."""
    if password_stdin and password:
        raise CliError(
            code="CONFLICTING_SECRET_INPUT",
            message="Use either --password-stdin or the password environment/option, not both.",
            exit_code=EXIT_USAGE,
        )
    if password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        runtime = get_runtime()
        if runtime.non_interactive or not sys.stdin.isatty():
            raise CliError(
                code="ADMIN_PASSWORD_MISSING",
                message="An admin password is required.",
                exit_code=EXIT_USAGE,
                hint="Set OUTLABS_AUTH_BOOTSTRAP_PASSWORD or pass --password-stdin.",
            )
        password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)

    url = get_database_url()
    schema = get_target_schema_from_env()
    emit_progress("Bootstrapping OutlabsAuth admin user...")
    status_value, user_id, normalized_email = asyncio.run(
        bootstrap_admin_user(
            url,
            schema=schema,
            email=email,
            password=password,
            first_name=first_name or None,
            last_name=last_name or None,
            root_entity_id=root_entity_id,
        )
    )
    text_output = (
        f"Created bootstrap admin {normalized_email} ({user_id})"
        if status_value == "created"
        else f"Bootstrap admin already exists: {normalized_email} ({user_id})"
    )
    emit_result(
        "db.bootstrap-admin",
        {"status": status_value, "user_id": user_id, "email": normalized_email},
        changed=status_value == "created",
        text=text_output,
    )


@main.command("init-db")
@click.option("--force", is_flag=True, help="Drop existing target schema/tables first")
@click.option("--yes", is_flag=True, help="Confirm destructive --force behavior without prompting.")
def init_db(force: bool, yes: bool):
    """Create all database tables directly from models (development only)."""
    from outlabs_auth.models.sql import ALL_MODELS  # noqa: F401

    url = get_database_url()
    schema = get_target_schema_from_env()
    schema_name = schema or "public"
    if force:
        require_confirmation(
            prompt=f"Drop and recreate schema '{schema_name}' before initializing?",
            yes=yes,
        )

    async def create_tables():
        target_schema = _validate_schema_name(schema)
        if target_schema:
            await _ensure_schema_exists(url, target_schema)

        engine = _build_engine(url, target_schema)
        try:
            async with engine.begin() as conn:
                if force:
                    if target_schema:
                        emit_progress(f'Dropping schema "{target_schema}"...')
                        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{target_schema}" CASCADE'))
                        await conn.execute(text(f'CREATE SCHEMA "{target_schema}"'))
                    else:
                        emit_progress("Dropping existing public schema...")
                        await conn.execute(text("DROP SCHEMA public CASCADE"))
                        await conn.execute(text("CREATE SCHEMA public"))
                        await conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
                        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :schema_name"),
                    {"schema_name": schema_name},
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    count = asyncio.run(create_tables())
    emit_result(
        "db.init",
        {"schema": schema_name, "table_count": count, "recreated": force},
        changed=True,
        text=f"Created {count} tables in schema {schema_name}.",
    )


@main.command("drop-db")
@click.option("--yes", is_flag=True, help="Confirm the destructive operation without prompting.")
def drop_db(yes: bool):
    """Drop all database tables in the target schema (development only)."""
    url = get_database_url()
    schema = get_target_schema_from_env()
    schema_name = schema or "public"
    require_confirmation(
        prompt=f"Drop and recreate schema '{schema_name}'?",
        yes=yes,
    )

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

    emit_progress("Dropping target schema/tables...")
    asyncio.run(drop_tables())
    emit_result(
        "db.drop",
        {"schema": schema_name, "recreated_empty": True},
        changed=True,
        text="Done!",
    )


@main.command()
def current():
    """Show current migration revision for the target DB/schema."""
    url = get_database_url()
    schema = get_target_schema_from_env()
    captured = io.StringIO()
    with redirect_stdout(captured):
        asyncio.run(
            show_current_revision(
                url,
                schema=schema,
            )
        )
    output = captured.getvalue().strip()
    emit_result(
        "db.current",
        {"schema": schema or "public", "alembic_output": output},
        text=output or "No current revision reported.",
    )


@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed history")
def history(verbose: bool):
    """Show migration history from the packaged migration script."""
    from alembic import command

    alembic_cfg = _load_alembic_config()
    captured = io.StringIO()
    with redirect_stdout(captured):
        command.history(alembic_cfg, verbose=verbose)
    output = captured.getvalue().strip()
    emit_result(
        "db.history",
        {"verbose": verbose, "alembic_output": output},
        text=output or "No migration history reported.",
    )


@main.command()
@click.option("--message", "-m", required=True, help="Migration message")
@click.option("--autogenerate", is_flag=True, help="Auto-generate from model changes")
def revision(message: str, autogenerate: bool):
    """Create a new migration revision."""
    from alembic import command

    alembic_cfg = _load_alembic_config(require_local=True)

    emit_progress(f"Creating migration: {message}")
    captured = io.StringIO()
    with redirect_stdout(captured):
        created = command.revision(alembic_cfg, message=message, autogenerate=autogenerate)
    output = captured.getvalue().strip()
    revision_ids: list[str] = []
    for item in created if isinstance(created, list) else [created]:
        revision_id = getattr(item, "revision", None)
        if revision_id:
            revision_ids.append(str(revision_id))
    emit_result(
        "db.revision",
        {"message": message, "autogenerate": autogenerate, "revisions": revision_ids, "output": output},
        changed=True,
        text=f"{output}\nDone!" if output else "Done!",
    )


@main.command()
def heads():
    """Show current available heads."""
    from alembic import command

    alembic_cfg = _load_alembic_config()
    captured = io.StringIO()
    with redirect_stdout(captured):
        command.heads(alembic_cfg)
    output = captured.getvalue().strip()
    emit_result(
        "db.heads",
        {"alembic_output": output},
        text=output or "No migration heads reported.",
    )


@main.command()
@click.option("--revision", "-r", default="-1", help="Revision to downgrade to")
@click.option("--yes", is_flag=True, help="Confirm the destructive migration without prompting.")
@click.option("--dry-run", is_flag=True, help="Show the requested downgrade without applying it.")
def downgrade(revision: str, yes: bool, dry_run: bool):
    """Downgrade to a previous revision."""
    schema = get_target_schema_from_env()
    if dry_run:
        emit_result(
            "db.downgrade",
            {"revision": revision, "schema": schema or "public", "dry_run": True},
            changed=False,
            text=f"Dry run: would downgrade schema {schema or 'public'} to {revision}.",
        )
        return
    require_confirmation(
        prompt=f"Downgrade schema '{schema or 'public'}' to revision '{revision}'?",
        yes=yes,
    )
    url = get_database_url()
    emit_progress(f"Downgrading to {revision}...")
    asyncio.run(
        downgrade_migrations(
            url,
            revision=revision,
            schema=schema,
        )
    )
    emit_result(
        "db.downgrade",
        {"revision": revision, "schema": schema or "public", "dry_run": False},
        changed=True,
        text="Done!",
    )


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
                    text("""
                        SELECT table_name,
                               (SELECT COUNT(*) FROM information_schema.columns
                                WHERE table_name = t.table_name AND table_schema = :schema_name) AS column_count
                        FROM information_schema.tables t
                        WHERE table_schema = :schema_name
                        ORDER BY table_name
                        """),
                    {"schema_name": schema},
                )
                return [(row[0], row[1]) for row in result]
        finally:
            await engine.dispose()

    tables_list = asyncio.run(list_tables())
    if not tables_list:
        emit_result(
            "db.tables",
            {"schema": schema, "tables": []},
            text=f"No tables found in schema {schema}.",
        )
        return

    lines = [f"Database tables in schema {schema} ({len(tables_list)} total):", ""]
    lines.extend(f"  {table} ({columns} columns)" for table, columns in tables_list)
    emit_result(
        "db.tables",
        {
            "schema": schema,
            "tables": [{"name": table, "column_count": columns} for table, columns in tables_list],
        },
        text="\n".join(lines),
    )


@main.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def doctor(output_format: str):
    """Diagnose the target DB/schema for bootstrap and migration issues (read-only)."""
    normalized = get_database_url()
    schema = get_target_schema_from_env()
    checks = asyncio.run(run_doctor(normalized, schema))

    if output_format == "json":
        click.echo(_format_doctor_json(checks, normalized, schema))
    elif effective_output() == "json":
        emit_result(
            "ops.doctor",
            json.loads(_format_doctor_json(checks, normalized, schema)),
        )
    else:
        click.echo(_format_doctor_text(checks, normalized, schema))

    has_failure = any(c.status == DoctorStatus.FAIL for c in checks)
    sys.exit(1 if has_failure else 0)


@main.command()
@click.option(
    "--admin-email",
    envvar="OUTLABS_AUTH_BOOTSTRAP_EMAIL",
    default=None,
    help="Admin email. If set, bootstrap creates or re-uses the admin user.",
)
@click.option(
    "--admin-password",
    envvar="OUTLABS_AUTH_BOOTSTRAP_PASSWORD",
    default=None,
    help="Admin password. Prefer the environment or --admin-password-stdin.",
)
@click.option("--admin-password-stdin", is_flag=True, help="Read the admin password from one line on stdin.")
@click.option(
    "--admin-first-name",
    envvar="OUTLABS_AUTH_BOOTSTRAP_FIRST_NAME",
    default=None,
    help="Optional admin first name.",
)
@click.option(
    "--admin-last-name",
    envvar="OUTLABS_AUTH_BOOTSTRAP_LAST_NAME",
    default=None,
    help="Optional admin last name.",
)
@click.option(
    "--skip-seed",
    is_flag=True,
    default=False,
    help="Skip seeding system permissions and config.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the plan without making any changes.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def bootstrap(
    admin_email: Optional[str],
    admin_password: Optional[str],
    admin_password_stdin: bool,
    admin_first_name: Optional[str],
    admin_last_name: Optional[str],
    skip_seed: bool,
    dry_run: bool,
    output_format: str,
):
    """First-boot orchestrator: classify, migrate, seed, and optionally create admin (idempotent)."""
    if admin_password_stdin and admin_password:
        raise CliError(
            code="CONFLICTING_SECRET_INPUT",
            message="Use either --admin-password-stdin or the password environment/option, not both.",
            exit_code=EXIT_USAGE,
        )
    if admin_password_stdin:
        admin_password = sys.stdin.readline().rstrip("\r\n")
    if admin_email and not admin_password:
        runtime = get_runtime()
        if runtime.non_interactive or not sys.stdin.isatty():
            raise CliError(
                code="ADMIN_PASSWORD_MISSING",
                message="An admin password is required whenever an admin email is set.",
                exit_code=EXIT_USAGE,
                hint="Set OUTLABS_AUTH_BOOTSTRAP_PASSWORD or pass --admin-password-stdin.",
            )
        admin_password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)

    normalized = get_database_url()
    schema = get_target_schema_from_env()
    result = asyncio.run(
        run_bootstrap(
            normalized,
            schema,
            skip_seed=skip_seed,
            admin_email=admin_email,
            admin_password=admin_password,
            admin_first_name=admin_first_name,
            admin_last_name=admin_last_name,
            dry_run=dry_run,
        )
    )

    if output_format == "json":
        click.echo(_format_bootstrap_json(result, normalized, schema))
    elif effective_output() == "json":
        emit_result(
            "ops.bootstrap",
            json.loads(_format_bootstrap_json(result, normalized, schema)),
            changed=bool(result.executed) and result.success,
        )
    else:
        click.echo(_format_bootstrap_text(result, normalized, schema))

    sys.exit(0 if result.success else 1)


@main.group("db")
def db_group():
    """Run local schema lifecycle and inspection commands."""


db_group.add_command(migrate)
db_group.add_command(adopt_existing_schema_command, "adopt-existing-schema")
db_group.add_command(seed_system, "seed-system")
db_group.add_command(bootstrap_admin, "bootstrap-admin")
db_group.add_command(init_db, "init")
db_group.add_command(drop_db, "drop")
db_group.add_command(current)
db_group.add_command(history)
db_group.add_command(revision)
db_group.add_command(heads)
db_group.add_command(downgrade)
db_group.add_command(tables)
db_group.add_command(bootstrap)


@main.group("ops")
def ops_group():
    """Run diagnostics and deterministic maintenance operations."""


ops_group.add_command(doctor)
ops_group.add_command(run_maintenance_command, "maintenance")


if __name__ == "__main__":
    main()
