from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from outlabs_auth.cli import SQUASHED_BASELINE_REVISION, run_migrations


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_migrations_reuses_single_engine_and_skips_upgrade_at_head(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_engine = SimpleNamespace(dispose=AsyncMock())
    build_calls: list[tuple[str, str | None, str | None]] = []
    normalized_url = "postgresql+asyncpg://user:pass@db/app"

    def fake_build_engine(
        database_url: str,
        schema: str | None,
        *,
        statement_timeout: str | None = None,
    ):
        build_calls.append((database_url, schema, statement_timeout))
        return fake_engine

    adopt_existing_schema = AsyncMock(return_value=False)
    revision_matches_head = AsyncMock(return_value=True)
    run_alembic_command = AsyncMock()

    monkeypatch.setattr("outlabs_auth.cli._build_engine", fake_build_engine)
    monkeypatch.setattr("outlabs_auth.cli.adopt_existing_schema", adopt_existing_schema)
    monkeypatch.setattr("outlabs_auth.cli._database_revision_matches_head", revision_matches_head)
    monkeypatch.setattr("outlabs_auth.cli._run_alembic_command", run_alembic_command)

    await run_migrations(
        "postgresql://user:pass@db/app",
        schema="auth_schema",
        statement_timeout="15s",
    )

    assert build_calls == [(normalized_url, "auth_schema", "15s")]
    adopt_existing_schema.assert_awaited_once_with(
        normalized_url,
        schema="auth_schema",
        revision=SQUASHED_BASELINE_REVISION,
        engine=fake_engine,
        statement_timeout="15s",
    )
    revision_matches_head.assert_awaited_once_with(
        normalized_url,
        "auth_schema",
        engine=fake_engine,
    )
    run_alembic_command.assert_not_awaited()
    fake_engine.dispose.assert_awaited_once_with()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_migrations_passes_shared_engine_to_alembic_command(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_engine = SimpleNamespace(dispose=AsyncMock())
    normalized_url = "postgresql+asyncpg://user:pass@db/app"

    monkeypatch.setattr(
        "outlabs_auth.cli._build_engine",
        lambda database_url, schema, *, statement_timeout=None: fake_engine,
    )
    monkeypatch.setattr("outlabs_auth.cli.adopt_existing_schema", AsyncMock(return_value=False))
    monkeypatch.setattr(
        "outlabs_auth.cli._database_revision_matches_head",
        AsyncMock(return_value=False),
    )
    run_alembic_command = AsyncMock()
    monkeypatch.setattr("outlabs_auth.cli._run_alembic_command", run_alembic_command)

    await run_migrations(
        "postgresql://user:pass@db/app",
        schema="auth_schema",
        statement_timeout="15s",
    )

    run_alembic_command.assert_awaited_once()
    args, kwargs = run_alembic_command.await_args
    assert args == (normalized_url,)
    assert kwargs["schema"] == "auth_schema"
    assert kwargs["ensure_schema"] is True
    assert kwargs["engine"] is fake_engine
    assert kwargs["statement_timeout"] == "15s"
    assert kwargs["operation_label"] == "migration upgrade to head"
    fake_engine.dispose.assert_awaited_once_with()
