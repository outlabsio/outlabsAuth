from __future__ import annotations

import json
from uuid import uuid4

import pytest
import pytest_asyncio
from click.testing import CliRunner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from outlabs_auth.cli import (
    ALEMBIC_VERSION_TABLE,
    BootstrapAction,
    BootstrapPlan,
    BootstrapResult,
    BootstrapStep,
    DoctorStatus,
    SchemaState,
    _build_bootstrap_plan,
    _classify_schema_state,
    _format_bootstrap_json,
    _format_bootstrap_text,
    main as cli_main,
    run_bootstrap,
    run_migrations,
)
from tests.conftest import TEST_DATABASE_URL


# ----------------------------------------------------------------------------
# Pure plan-builder tests
# ----------------------------------------------------------------------------


def test_plan_aborts_on_no_connection():
    plan = _build_bootstrap_plan(
        SchemaState.NO_CONNECTION,
        "Cannot reach database: TimeoutError",
        skip_seed=False,
        admin_email=None,
    )
    assert plan.can_proceed is False
    assert plan.steps == ()
    assert "TimeoutError" in plan.abort_reason


def test_plan_aborts_on_missing_schema_with_create_schema_hint():
    plan = _build_bootstrap_plan(
        SchemaState.SCHEMA_MISSING,
        "Schema 'foo' does not exist",
        skip_seed=False,
        admin_email=None,
    )
    assert plan.can_proceed is False
    assert "CREATE SCHEMA" in plan.abort_reason
    assert "init-db" in plan.abort_reason


def test_plan_aborts_on_drift_with_doctor_hint():
    plan = _build_bootstrap_plan(
        SchemaState.DRIFTED,
        "DB is at unknown revision 'xyz'",
        skip_seed=False,
        admin_email=None,
    )
    assert plan.can_proceed is False
    assert "doctor" in plan.abort_reason


def test_plan_aborts_on_partial_non_auth_schema():
    plan = _build_bootstrap_plan(
        SchemaState.PARTIAL_NON_AUTH,
        "Schema has unrelated tables",
        skip_seed=False,
        admin_email=None,
    )
    assert plan.can_proceed is False
    assert "co-tenant" in plan.abort_reason.lower()


def test_plan_for_empty_schema_migrates_seeds_skips_admin():
    plan = _build_bootstrap_plan(
        SchemaState.EMPTY,
        "Empty",
        skip_seed=False,
        admin_email=None,
    )
    actions = [s.action for s in plan.steps]
    assert plan.can_proceed
    assert actions == [
        BootstrapAction.MIGRATE,
        BootstrapAction.SEED,
        BootstrapAction.SKIP_ADMIN,
    ]


def test_plan_for_healthy_current_issues_skip_migrate():
    plan = _build_bootstrap_plan(
        SchemaState.HEALTHY_CURRENT,
        "At head",
        skip_seed=False,
        admin_email=None,
    )
    actions = [s.action for s in plan.steps]
    assert actions[0] == BootstrapAction.SKIP_MIGRATE
    assert BootstrapAction.SEED in actions


def test_plan_for_legacy_mentions_stamping():
    plan = _build_bootstrap_plan(
        SchemaState.LEGACY,
        "Pre-Alembic",
        skip_seed=False,
        admin_email=None,
    )
    assert plan.steps[0].action == BootstrapAction.MIGRATE
    assert "Stamp" in plan.steps[0].detail


def test_plan_with_admin_email_and_skip_seed():
    plan = _build_bootstrap_plan(
        SchemaState.EMPTY,
        "Empty",
        skip_seed=True,
        admin_email="admin@example.com",
    )
    actions = [s.action for s in plan.steps]
    assert BootstrapAction.SEED not in actions
    assert BootstrapAction.CREATE_ADMIN in actions


# ----------------------------------------------------------------------------
# Fixtures for real-DB tests
# ----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def empty_schema():
    schema = f"bootstrap_{uuid4().hex[:10]}"
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
    schema = f"bootstrap_legacy_{uuid4().hex[:10]}"
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
    schema = f"bootstrap_healthy_{uuid4().hex[:10]}"
    admin = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        await run_migrations(TEST_DATABASE_URL, schema=schema)
        yield schema
    finally:
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


@pytest_asyncio.fixture
async def partial_non_auth_schema():
    schema = f"bootstrap_partial_{uuid4().hex[:10]}"
    admin = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text(f'CREATE TABLE "{schema}".unrelated_thing (id int)'))
        yield schema
    finally:
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


# ----------------------------------------------------------------------------
# Classifier tests against real Postgres
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_reports_empty_schema(empty_schema):
    state, _ = await _classify_schema_state(TEST_DATABASE_URL, empty_schema)
    assert state == SchemaState.EMPTY


@pytest.mark.asyncio
async def test_classifier_reports_legacy_schema(legacy_schema):
    state, _ = await _classify_schema_state(TEST_DATABASE_URL, legacy_schema)
    assert state == SchemaState.LEGACY


@pytest.mark.asyncio
async def test_classifier_reports_healthy_current(migrated_schema):
    state, _ = await _classify_schema_state(TEST_DATABASE_URL, migrated_schema)
    assert state == SchemaState.HEALTHY_CURRENT


@pytest.mark.asyncio
async def test_classifier_reports_partial_non_auth(partial_non_auth_schema):
    state, _ = await _classify_schema_state(TEST_DATABASE_URL, partial_non_auth_schema)
    assert state == SchemaState.PARTIAL_NON_AUTH


@pytest.mark.asyncio
async def test_classifier_reports_drift(migrated_schema):
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f'UPDATE "{migrated_schema}"."{ALEMBIC_VERSION_TABLE}" '
                    "SET version_num = :v"
                ),
                {"v": "not_a_real_revision"},
            )
    finally:
        await engine.dispose()
    state, detail = await _classify_schema_state(TEST_DATABASE_URL, migrated_schema)
    assert state == SchemaState.DRIFTED
    assert "not_a_real_revision" in detail


@pytest.mark.asyncio
async def test_classifier_reports_missing_schema():
    missing = f"bootstrap_nope_{uuid4().hex[:10]}"
    state, _ = await _classify_schema_state(TEST_DATABASE_URL, missing)
    assert state == SchemaState.SCHEMA_MISSING


# ----------------------------------------------------------------------------
# Orchestrator tests against real Postgres
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_bootstrap_brings_empty_schema_to_healthy(empty_schema):
    result = await run_bootstrap(TEST_DATABASE_URL, empty_schema)
    assert result.success is True
    assert result.plan.state == SchemaState.EMPTY
    actions = [e.action for e in result.executed]
    assert BootstrapAction.MIGRATE in actions
    assert BootstrapAction.SEED in actions
    assert all(c.status == DoctorStatus.OK for c in result.final_checks)


@pytest.mark.asyncio
async def test_run_bootstrap_adopts_legacy_schema(legacy_schema):
    result = await run_bootstrap(TEST_DATABASE_URL, legacy_schema)
    assert result.success is True
    assert result.plan.state == SchemaState.LEGACY
    assert all(c.status == DoctorStatus.OK for c in result.final_checks)


@pytest.mark.asyncio
async def test_run_bootstrap_is_idempotent_on_healthy_schema(migrated_schema):
    result = await run_bootstrap(TEST_DATABASE_URL, migrated_schema)
    assert result.success is True
    assert result.plan.state == SchemaState.HEALTHY_CURRENT
    skip_step = next(
        e for e in result.executed if e.action == BootstrapAction.SKIP_MIGRATE
    )
    assert skip_step.status == DoctorStatus.SKIP


@pytest.mark.asyncio
async def test_run_bootstrap_aborts_on_drift(migrated_schema):
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f'UPDATE "{migrated_schema}"."{ALEMBIC_VERSION_TABLE}" '
                    "SET version_num = :v"
                ),
                {"v": "not_a_real_revision"},
            )
    finally:
        await engine.dispose()
    result = await run_bootstrap(TEST_DATABASE_URL, migrated_schema)
    assert result.success is False
    assert result.plan.can_proceed is False
    assert result.executed == ()
    assert "doctor" in (result.error or "")


@pytest.mark.asyncio
async def test_run_bootstrap_aborts_on_partial_non_auth(partial_non_auth_schema):
    result = await run_bootstrap(TEST_DATABASE_URL, partial_non_auth_schema)
    assert result.success is False
    assert result.plan.state == SchemaState.PARTIAL_NON_AUTH
    assert result.executed == ()


@pytest.mark.asyncio
async def test_run_bootstrap_dry_run_makes_no_changes(empty_schema):
    result = await run_bootstrap(TEST_DATABASE_URL, empty_schema, dry_run=True)
    assert result.success is True
    assert result.dry_run is True
    assert result.executed == ()
    state, _ = await _classify_schema_state(TEST_DATABASE_URL, empty_schema)
    assert state == SchemaState.EMPTY


@pytest.mark.asyncio
async def test_run_bootstrap_creates_admin_user(empty_schema):
    result = await run_bootstrap(
        TEST_DATABASE_URL,
        empty_schema,
        admin_email="admin@bootstrap-test.example",
        admin_password="Testpass1!",
    )
    assert result.success is True
    admin_step = next(
        e for e in result.executed if e.action == BootstrapAction.CREATE_ADMIN
    )
    assert "admin@bootstrap-test.example" in admin_step.detail


@pytest.mark.asyncio
async def test_run_bootstrap_admin_step_is_idempotent(empty_schema):
    await run_bootstrap(
        TEST_DATABASE_URL,
        empty_schema,
        admin_email="admin@bootstrap-test.example",
        admin_password="Testpass1!",
    )
    result = await run_bootstrap(
        TEST_DATABASE_URL,
        empty_schema,
        admin_email="admin@bootstrap-test.example",
        admin_password="Testpass1!",
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_run_bootstrap_skip_seed_omits_seed_step(empty_schema):
    result = await run_bootstrap(TEST_DATABASE_URL, empty_schema, skip_seed=True)
    assert result.success is True
    actions = [e.action for e in result.executed]
    assert BootstrapAction.SEED not in actions
    assert BootstrapAction.MIGRATE in actions


# ----------------------------------------------------------------------------
# Formatter tests
# ----------------------------------------------------------------------------


def _abort_result(state: str = SchemaState.NO_CONNECTION) -> BootstrapResult:
    plan = BootstrapPlan(
        state=state,
        state_detail="unreachable",
        can_proceed=False,
        steps=(),
        abort_reason="Cannot reach database: TimeoutError",
    )
    return BootstrapResult(
        plan=plan,
        dry_run=False,
        success=False,
        executed=(),
        final_checks=(),
        error="Cannot reach database: TimeoutError",
    )


def test_format_bootstrap_text_redacts_password():
    result = _abort_result()
    url = "postgresql+asyncpg://postgres:topsecret@localhost:5432/db"
    output = _format_bootstrap_text(result, url, None)
    assert "topsecret" not in output
    assert ":****@" in output


def test_format_bootstrap_text_dry_run_lists_plan():
    plan = BootstrapPlan(
        state=SchemaState.EMPTY,
        state_detail="Empty",
        can_proceed=True,
        steps=(
            BootstrapStep(BootstrapAction.MIGRATE, "Run all migrations to head"),
            BootstrapStep(BootstrapAction.SEED, "Seed permissions and config"),
        ),
    )
    result = BootstrapResult(
        plan=plan,
        dry_run=True,
        success=True,
        executed=(),
        final_checks=(),
        error=None,
    )
    output = _format_bootstrap_text(result, "postgresql://u@h/d", None)
    assert "dry-run" in output
    assert "1. [migrate]" in output
    assert "2. [seed]" in output


def test_format_bootstrap_json_shape_and_redaction():
    plan = BootstrapPlan(
        state=SchemaState.EMPTY,
        state_detail="Empty",
        can_proceed=True,
        steps=(BootstrapStep(BootstrapAction.MIGRATE, "Migrate to head"),),
    )
    result = BootstrapResult(
        plan=plan,
        dry_run=True,
        success=True,
        executed=(),
        final_checks=(),
        error=None,
    )
    url = "postgresql+asyncpg://postgres:topsecret@localhost:5432/db"
    payload = json.loads(_format_bootstrap_json(result, url, "myschema"))
    assert payload["state"] == "empty"
    assert payload["dry_run"] is True
    assert payload["can_proceed"] is True
    assert payload["plan"][0]["action"] == "migrate"
    assert payload["schema"] == "myschema"
    assert "topsecret" not in payload["database_url"]
    assert ":****@" in payload["database_url"]


def test_format_bootstrap_json_includes_abort_reason_on_refusal():
    result = _abort_result(SchemaState.DRIFTED)
    payload = json.loads(_format_bootstrap_json(result, "postgresql://u@h/d", None))
    assert payload["can_proceed"] is False
    assert payload["abort_reason"].startswith("Cannot reach database")


# ----------------------------------------------------------------------------
# CLI invocation tests
# ----------------------------------------------------------------------------


def test_bootstrap_cli_exits_two_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["bootstrap"])
    assert result.exit_code == 2
    assert "DATABASE_URL" in result.output


def test_bootstrap_cli_exits_two_when_admin_email_without_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.delenv("OUTLABS_AUTH_BOOTSTRAP_PASSWORD", raising=False)
    runner = CliRunner()
    result = runner.invoke(
        cli_main, ["bootstrap", "--admin-email", "admin@test.com", "--dry-run"]
    )
    assert result.exit_code == 2
    assert "admin-password" in result.output


def test_bootstrap_cli_aborts_with_json_for_missing_schema(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("OUTLABS_AUTH_SCHEMA", f"bootstrap_missing_{uuid4().hex[:10]}")
    runner = CliRunner()
    result = runner.invoke(
        cli_main, ["bootstrap", "--dry-run", "--format", "json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["state"] == "schema_missing"
    assert payload["can_proceed"] is False
