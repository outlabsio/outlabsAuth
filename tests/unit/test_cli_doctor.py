from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from click.testing import CliRunner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

import outlabs_auth.cli as cli_module
from outlabs_auth.cli import (
    ALEMBIC_VERSION_TABLE,
    DOCTOR_CHECK_NAMES,
    DoctorCheck,
    DoctorStatus,
    _build_connect_args,
    _format_doctor_json,
    _format_doctor_text,
    _redact_database_url,
    main as cli_main,
    run_doctor,
    run_migrations,
)
from outlabs_auth.maintenance import MaintenanceReport
from tests.conftest import TEST_DATABASE_URL

# ----------------------------------------------------------------------------
# Pure-function unit tests
# ----------------------------------------------------------------------------


def test_redact_database_url_redacts_password():
    url = "postgresql+asyncpg://postgres:superSecret@localhost:5432/mydb"
    redacted = _redact_database_url(url)
    assert "superSecret" not in redacted
    assert ":****@" in redacted
    assert "postgres" in redacted
    assert "localhost:5432/mydb" in redacted


def test_run_maintenance_requires_explicit_runtime_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(cli_main, ["run-maintenance"])

    assert result.exit_code == 2
    assert "DATABASE_URL environment variable not set" in result.output


def test_run_maintenance_emits_typed_success_report(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://runtime@example.test/auth")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-production-1234567890")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("OUTLABS_AUTH_REDIS_KEY_PREFIX", raising=False)
    run_once = AsyncMock(
        return_value=MaintenanceReport.from_results(
            {"token_cleanup": {"refresh_tokens": {"total": 1}}},
            expected_steps=("token_cleanup",),
        )
    )
    monkeypatch.setattr(cli_module, "_run_maintenance_once", run_once)

    result = CliRunner().invoke(cli_main, ["run-maintenance"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["completed_steps"] == ["token_cleanup"]
    assert payload["reported_errors"] == 0


def test_run_maintenance_exits_nonzero_for_partial_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://runtime@example.test/auth")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-production-1234567890")
    monkeypatch.setenv("REDIS_URL", "redis://cache.example.test/0")
    monkeypatch.setenv("OUTLABS_AUTH_REDIS_KEY_PREFIX", "test:maintenance")
    run_once = AsyncMock(
        return_value=MaintenanceReport.from_results(
            {"token_cleanup": {"refresh_tokens": {"total": 0}}},
            expected_steps=("token_cleanup", "api_key_usage_sync"),
        )
    )
    monkeypatch.setattr(cli_module, "_run_maintenance_once", run_once)

    result = CliRunner().invoke(cli_main, ["run-maintenance"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["missing_steps"] == ["api_key_usage_sync"]


def test_run_maintenance_json_failure_uses_agent_error_contract(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://runtime@example.test/auth")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-production-1234567890")
    monkeypatch.setenv("REDIS_URL", "redis://cache.example.test/0")
    monkeypatch.setenv("OUTLABS_AUTH_REDIS_KEY_PREFIX", "test:maintenance")
    run_once = AsyncMock(
        return_value=MaintenanceReport.from_results(
            {"token_cleanup": {"refresh_tokens": {"total": 0}}},
            expected_steps=("token_cleanup", "api_key_usage_sync"),
        )
    )
    monkeypatch.setattr(cli_module, "_run_maintenance_once", run_once)

    result = CliRunner().invoke(cli_main, ["--output", "json", "run-maintenance"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "MAINTENANCE_INCOMPLETE"
    assert payload["error"]["details"]["missing_steps"] == ["api_key_usage_sync"]
    assert payload["error"]["retryable"] is False


def test_redact_database_url_preserves_url_without_password():
    url = "postgresql+asyncpg://reader@localhost:5432/mydb"
    assert _redact_database_url(url) == url


def test_redact_database_url_passthrough_on_garbage_input():
    # urlparse is permissive, so this returns unchanged rather than raising.
    assert _redact_database_url("not a url") == "not a url"


def test_build_connect_args_applies_migration_statement_timeout_and_schema():
    assert _build_connect_args("auth_schema") == {
        "server_settings": {
            "statement_timeout": "60s",
            "search_path": "auth_schema,public",
        }
    }


def test_build_connect_args_allows_disabling_statement_timeout():
    assert _build_connect_args("auth_schema", statement_timeout=None) == {
        "server_settings": {"search_path": "auth_schema,public"}
    }


def test_format_doctor_text_success_case_shows_all_passed():
    checks = [DoctorCheck(name=name, status=DoctorStatus.OK, detail="ok") for name in DOCTOR_CHECK_NAMES]
    output = _format_doctor_text(checks, "postgresql://u@h/d", "myschema")
    assert "All checks passed." in output
    assert "myschema" in output
    assert "FAIL" not in output


def test_format_doctor_text_fail_case_includes_remediation_arrow():
    checks = [
        DoctorCheck(name="Database connectivity", status=DoctorStatus.OK, detail="ok"),
        DoctorCheck(
            name="Target schema",
            status=DoctorStatus.FAIL,
            detail="Schema 'x' does not exist",
            remediation="Run: outlabs-auth migrate",
        ),
    ]
    output = _format_doctor_text(checks, "postgresql://u@h/d", None)
    assert "[FAIL]" in output
    assert "-> Run: outlabs-auth migrate" in output
    assert "1 check failed" in output
    assert "(public)" in output


def test_format_doctor_text_redacts_password():
    checks = [DoctorCheck(name="Database connectivity", status=DoctorStatus.OK, detail="ok")]
    url = "postgresql+asyncpg://postgres:topsecret@localhost:5432/db"
    output = _format_doctor_text(checks, url, None)
    assert "topsecret" not in output
    assert ":****@" in output


def test_format_doctor_json_shape_for_healthy_case():
    checks = [DoctorCheck(name=name, status=DoctorStatus.OK, detail="ok") for name in DOCTOR_CHECK_NAMES]
    payload = json.loads(_format_doctor_json(checks, "postgresql://u@h/d", "myschema"))
    assert payload["healthy"] is True
    assert payload["schema"] == "myschema"
    assert len(payload["checks"]) == len(DOCTOR_CHECK_NAMES)
    # Remediation field is omitted on success entries.
    assert all("remediation" not in c for c in payload["checks"])


def test_format_doctor_json_includes_remediation_on_failure():
    checks = [
        DoctorCheck(
            name="Target schema",
            status=DoctorStatus.FAIL,
            detail="missing",
            remediation="Run: outlabs-auth migrate",
        ),
    ]
    payload = json.loads(_format_doctor_json(checks, "postgresql://u@h/d", "x"))
    assert payload["healthy"] is False
    assert payload["checks"][0]["remediation"] == "Run: outlabs-auth migrate"


def test_format_doctor_json_redacts_password():
    checks = [DoctorCheck(name="Database connectivity", status=DoctorStatus.OK, detail="ok")]
    url = "postgresql+asyncpg://postgres:topsecret@localhost:5432/db"
    payload = json.loads(_format_doctor_json(checks, url, None))
    assert "topsecret" not in payload["database_url"]
    assert ":****@" in payload["database_url"]


# ----------------------------------------------------------------------------
# Orchestrator tests against a real Postgres
# ----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def empty_schema():
    """Create a fresh empty schema and drop it after the test."""
    schema = f"doctor_{uuid4().hex[:10]}"
    admin = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        yield schema
    finally:
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


@pytest_asyncio.fixture
async def legacy_schema():
    """Create a schema with core auth tables via SQLModel.metadata.create_all — no alembic version table."""
    schema = f"doctor_legacy_{uuid4().hex[:10]}"
    admin = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        tabled = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            connect_args={"server_settings": {"search_path": schema}},
        )
        try:
            async with tabled.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
        finally:
            await tabled.dispose()
        yield schema
    finally:
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


@pytest_asyncio.fixture
async def migrated_schema():
    """Create a schema and run the packaged migrations — fully healthy state."""
    schema = f"doctor_healthy_{uuid4().hex[:10]}"
    admin = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        await run_migrations(TEST_DATABASE_URL, schema=schema)
        yield schema
    finally:
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


@pytest.mark.asyncio
async def test_run_doctor_short_circuits_on_bad_connectivity():
    bad_url = "postgresql+asyncpg://postgres:postgres@127.0.0.1:1/doesnotexist"
    checks = await run_doctor(bad_url, schema=None)
    assert len(checks) == len(DOCTOR_CHECK_NAMES)
    assert checks[0].status == DoctorStatus.FAIL
    assert checks[0].name == "Database connectivity"
    assert all(c.status == DoctorStatus.SKIP for c in checks[1:])


@pytest.mark.asyncio
async def test_run_doctor_reports_missing_schema():
    nonexistent = f"doctor_nope_{uuid4().hex[:10]}"
    checks = await run_doctor(TEST_DATABASE_URL, schema=nonexistent)
    by_name = {c.name: c for c in checks}
    assert by_name["Database connectivity"].status == DoctorStatus.OK
    assert by_name["Target schema"].status == DoctorStatus.FAIL
    assert nonexistent in by_name["Target schema"].detail
    assert by_name["Alembic version table"].status == DoctorStatus.SKIP
    assert by_name["Revision matches code"].status == DoctorStatus.SKIP
    assert by_name["Core auth tables"].status == DoctorStatus.SKIP


@pytest.mark.asyncio
async def test_run_doctor_reports_empty_schema(empty_schema):
    checks = await run_doctor(TEST_DATABASE_URL, schema=empty_schema)
    by_name = {c.name: c for c in checks}
    assert by_name["Target schema"].status == DoctorStatus.OK
    assert by_name["Alembic version table"].status == DoctorStatus.FAIL
    assert "empty" in by_name["Alembic version table"].detail.lower()
    assert by_name["Alembic version table"].remediation == "Run: outlabs-auth migrate"
    assert by_name["Revision matches code"].status == DoctorStatus.SKIP
    # Core-tables check still runs (operator wants the full picture for an empty schema).
    assert by_name["Core auth tables"].status == DoctorStatus.FAIL


@pytest.mark.asyncio
async def test_run_doctor_detects_legacy_schema_without_alembic(legacy_schema):
    checks = await run_doctor(TEST_DATABASE_URL, schema=legacy_schema)
    by_name = {c.name: c for c in checks}
    assert by_name["Target schema"].status == DoctorStatus.OK
    alembic = by_name["Alembic version table"]
    assert alembic.status == DoctorStatus.FAIL
    assert "Pre-Alembic" in alembic.detail
    assert alembic.remediation == "Run: outlabs-auth adopt-existing-schema"


@pytest.mark.asyncio
async def test_run_doctor_reports_healthy_after_migrate(migrated_schema):
    checks = await run_doctor(TEST_DATABASE_URL, schema=migrated_schema)
    statuses = {c.name: c.status for c in checks}
    assert all(status == DoctorStatus.OK for status in statuses.values()), statuses


@pytest.mark.asyncio
async def test_run_doctor_flags_revision_drift(migrated_schema):
    # Forge a drifted revision in the alembic version table.
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(f'UPDATE "{migrated_schema}"."{ALEMBIC_VERSION_TABLE}" ' "SET version_num = :v"),
                {"v": "not_a_real_revision"},
            )
    finally:
        await engine.dispose()

    checks = await run_doctor(TEST_DATABASE_URL, schema=migrated_schema)
    revision = next(c for c in checks if c.name == "Revision matches code")
    assert revision.status == DoctorStatus.FAIL
    assert "not_a_real_revision" in revision.detail


# ----------------------------------------------------------------------------
# CLI invocation tests
# ----------------------------------------------------------------------------


def test_doctor_cli_exits_two_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["doctor"])
    assert result.exit_code == 2
    assert "DATABASE_URL" in result.output


def test_doctor_cli_exits_one_on_failure(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("OUTLABS_AUTH_SCHEMA", f"doctor_missing_{uuid4().hex[:10]}")
    runner = CliRunner()
    result = runner.invoke(cli_main, ["doctor"])
    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "does not exist" in result.output


def test_doctor_cli_json_output_is_valid(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("OUTLABS_AUTH_SCHEMA", f"doctor_missing_{uuid4().hex[:10]}")
    runner = CliRunner()
    result = runner.invoke(cli_main, ["doctor", "--format", "json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["healthy"] is False
    assert any(c["status"] == "fail" for c in payload["checks"])
