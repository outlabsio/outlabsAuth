from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from outlabs_auth.database.engine import (
    DatabaseConfig,
    DatabasePresets,
    create_engine,
    create_session_factory,
    get_session,
)


class _FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[_FakeSession] = []

    def __call__(self) -> _FakeSession:
        session = _FakeSession()
        self.sessions.append(session)
        return session


@pytest.mark.unit
def test_database_config_normalizes_postgres_urls_and_rejects_invalid_scheme():
    normalized = DatabaseConfig("postgresql://user:pass@localhost:5432/app")

    assert normalized.database_url == "postgresql+asyncpg://user:pass@localhost:5432/app"
    assert normalized.connect_args == {}

    explicit = DatabaseConfig(
        "postgresql+asyncpg://user:pass@localhost:5432/app",
        connect_args={"server_settings": {"search_path": "auth,public"}},
    )
    assert explicit.connect_args == {"server_settings": {"search_path": "auth,public"}}

    with pytest.raises(ValueError, match="database_url must be a PostgreSQL URL"):
        DatabaseConfig("sqlite:///tmp/test.db")


@pytest.mark.unit
def test_database_presets_apply_expected_pool_defaults():
    development = DatabasePresets.development("postgresql://dev")
    production = DatabasePresets.production("postgresql://prod")
    serverless = DatabasePresets.serverless("postgresql://srv")
    testing = DatabasePresets.testing("postgresql://test")

    assert development.echo is True
    assert development.pool_size == 2
    assert development.max_overflow == 3
    assert development.pool_recycle == 300

    assert production.echo is False
    assert production.pool_size == 10
    assert production.max_overflow == 20
    assert production.pool_timeout == 30
    assert production.pool_recycle == 1800

    assert serverless.pool_size == 0
    assert serverless.max_overflow == 0
    assert serverless.pool_pre_ping is False

    assert testing.echo is False
    assert testing.pool_size == 1
    assert testing.max_overflow == 2
    assert testing.pool_recycle == 60


@pytest.mark.unit
def test_create_engine_uses_expected_pool_class_and_kwargs(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []

    def fake_create_async_engine(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return SimpleNamespace(url=url, kwargs=kwargs)

    monkeypatch.setattr("outlabs_auth.database.engine.create_async_engine", fake_create_async_engine)

    pooled_config = DatabaseConfig(
        "postgresql+asyncpg://user:pass@localhost:5432/app",
        echo=True,
        pool_size=7,
        max_overflow=11,
        pool_timeout=22,
        pool_recycle=333,
        pool_pre_ping=False,
        connect_args={"timeout": 5},
    )
    serverless_config = DatabasePresets.serverless("postgresql://serverless")

    pooled_engine = create_engine(pooled_config)
    serverless_engine = create_engine(serverless_config)

    assert pooled_engine.url == pooled_config.database_url
    assert calls[0]["echo"] is True
    assert calls[0]["poolclass"].__name__ == "AsyncAdaptedQueuePool"
    assert calls[0]["pool_size"] == 7
    assert calls[0]["max_overflow"] == 11
    assert calls[0]["pool_timeout"] == 22
    assert calls[0]["pool_recycle"] == 333
    assert calls[0]["pool_pre_ping"] is False
    assert calls[0]["connect_args"] == {"timeout": 5}

    assert serverless_engine.url == serverless_config.database_url
    assert calls[1]["poolclass"].__name__ == "NullPool"
    assert "pool_size" not in calls[1]
    assert calls[1]["connect_args"] == {}


@pytest.mark.unit
def test_create_session_factory_binds_async_session_defaults(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []

    def fake_async_sessionmaker(engine, **kwargs):
        calls.append({"engine": engine, **kwargs})
        return SimpleNamespace(engine=engine, kwargs=kwargs)

    monkeypatch.setattr("outlabs_auth.database.engine.async_sessionmaker", fake_async_sessionmaker)

    engine = SimpleNamespace(name="engine")
    factory = create_session_factory(engine)

    assert factory.engine is engine
    assert calls == [
        {
            "engine": engine,
            "class_": calls[0]["class_"],
            "expire_on_commit": False,
            "autocommit": False,
            "autoflush": False,
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_session_commits_on_success_and_rolls_back_on_error():
    session_factory = _FakeSessionFactory()

    session_gen = get_session(session_factory)
    yielded = await session_gen.__anext__()
    assert yielded is session_factory.sessions[0]
    with pytest.raises(StopAsyncIteration):
        await session_gen.__anext__()
    session_factory.sessions[0].commit.assert_awaited_once_with()
    session_factory.sessions[0].rollback.assert_not_awaited()

    error_gen = get_session(session_factory)
    errored = await error_gen.__anext__()
    assert errored is session_factory.sessions[1]
    with pytest.raises(RuntimeError, match="boom"):
        await error_gen.athrow(RuntimeError("boom"))
    session_factory.sessions[1].rollback.assert_awaited_once_with()
    session_factory.sessions[1].commit.assert_not_awaited()
