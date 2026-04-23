from __future__ import annotations

import asyncio
import warnings
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from outlabs_auth.core.auth import OutlabsAuth
from outlabs_auth.core.exceptions import ConfigurationError
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.cache import CacheService


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


class _SessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _snapshot_api_key_model(
    key_id,
    *,
    prefix: str = "sk_live_cached_1",
    entity_id=None,
    inherit_from_tree: bool = False,
):
    return SimpleNamespace(
        id=key_id,
        prefix=prefix,
        status=APIKeyStatus.ACTIVE,
        key_kind=APIKeyKind.PERSONAL,
        owner_type="user",
        resolved_owner_id=None,
        expires_at=None,
        entity_id=entity_id,
        inherit_from_tree=inherit_from_tree,
        rate_limit_per_minute=None,
        rate_limit_per_hour=None,
        rate_limit_per_day=None,
    )


class _FakeApp:
    def __init__(self, fail_middleware: bool = False) -> None:
        self.fail_middleware = fail_middleware
        self.middleware_calls: list[tuple[type, dict]] = []
        self.routers: list[object] = []

    def add_middleware(self, middleware_class: type, **kwargs: object) -> None:
        if self.fail_middleware:
            raise RuntimeError("Cannot add middleware after an application has started")
        self.middleware_calls.append((middleware_class, kwargs))

    def include_router(self, router: object) -> None:
        self.routers.append(router)


class _SnapshotRedis:
    def __init__(self) -> None:
        self.is_available = True
        self.values: dict[str, object] = {}
        self.counters: dict[str, int] = {}
        self.deleted: list[str] = []

    def make_key(self, *parts: str) -> str:
        return ":".join(str(part) for part in parts)

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value, ttl=None):
        self.values[key] = value
        return True

    async def delete(self, key: str):
        self.deleted.append(key)
        self.values.pop(key, None)
        self.counters.pop(key, None)
        return True

    async def get_counter(self, key: str):
        return self.counters.get(key, 0)

    async def increment(self, key: str, amount: int = 1):
        self.counters[key] = self.counters.get(key, 0) + amount
        return self.counters[key]

    async def increment_with_ttl(self, key: str, amount: int = 1, ttl: int | None = None):
        self.counters[key] = self.counters.get(key, 0) + amount
        return self.counters[key]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "Either database_url or engine must be provided"),
        (
            {"database_url": "postgresql+asyncpg://example:example@localhost:5432/test", "secret_key": ""},
            "secret_key is required",
        ),
        (
            {
                "database_url": "postgresql+asyncpg://example:example@localhost:5432/test",
                "secret_key": "test-secret",
                "enable_context_aware_roles": True,
            },
            "enable_context_aware_roles requires enable_entity_hierarchy=True",
        ),
        (
            {
                "database_url": "postgresql+asyncpg://example:example@localhost:5432/test",
                "secret_key": "test-secret",
                "enable_caching": True,
            },
            "enable_caching=True requires Redis",
        ),
    ],
)
def test_outlabs_auth_configuration_validation(kwargs: dict, message: str):
    with pytest.raises(ConfigurationError, match=message):
        OutlabsAuth(**kwargs)


@pytest.mark.unit
def test_outlabs_auth_sets_redis_enabled_and_reports_features():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        redis_url="redis://localhost:6379/0",
        enable_entity_hierarchy=True,
        enable_abac=True,
        enable_audit_log=True,
    )

    assert auth.config.redis_enabled is True
    assert auth.config.enable_caching is True
    assert auth.is_enterprise is True
    assert auth.features["entity_hierarchy"] is True
    assert auth.features["abac"] is True
    assert auth.features["caching"] is True
    assert auth.features["audit_log"] is True
    assert "EnterpriseRBAC" in repr(auth)
    assert "abac" in repr(auth)


@pytest.mark.unit
def test_outlabs_auth_allows_explicit_cache_opt_out_with_redis_url():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        redis_url="redis://localhost:6379/0",
        enable_caching=False,
    )

    assert auth.config.redis_enabled is True
    assert auth.config.enable_caching is False
    assert auth.features["caching"] is False


@pytest.mark.unit
def test_outlabs_auth_allows_explicit_redis_opt_out_with_redis_url():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        redis_url="redis://localhost:6379/0",
        redis_enabled=False,
    )

    assert auth.config.redis_enabled is False
    assert auth.config.enable_caching is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_initialize_builds_engine_runs_migrations_and_starts_services(
    monkeypatch: pytest.MonkeyPatch,
):
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        database_schema="auth_schema",
        auto_migrate=True,
    )
    fake_engine = SimpleNamespace()
    fake_session_factory = _FakeSessionFactory()
    fake_redis = SimpleNamespace(connect=AsyncMock())
    fake_cache = SimpleNamespace(start=AsyncMock())
    fake_observability = SimpleNamespace(
        initialize=AsyncMock(),
        instrument_sqlalchemy=MagicMock(),
    )
    engine_calls: list[object] = []

    def fake_create_engine(db_config):
        engine_calls.append(db_config)
        return fake_engine

    monkeypatch.setattr("outlabs_auth.core.auth.create_engine", fake_create_engine)
    monkeypatch.setattr(
        "outlabs_auth.core.auth.create_session_factory",
        lambda engine: fake_session_factory,
    )

    async def fake_init_services() -> None:
        auth.redis_client = fake_redis
        auth.cache_service = fake_cache
        auth.activity_tracker = object()

    auth._run_migrations = AsyncMock()
    auth._init_services = AsyncMock(side_effect=fake_init_services)
    auth._init_backends = MagicMock()
    auth._init_deps = MagicMock()
    auth._start_token_cleanup_scheduler = MagicMock()
    auth._start_activity_sync_scheduler = MagicMock()
    auth.observability_config = object()
    auth.observability = fake_observability
    auth.config.enable_token_cleanup = True
    auth.config.store_refresh_tokens = True
    auth.config.enable_activity_tracking = True

    await auth.initialize()
    await auth.initialize()

    assert auth._initialized is True
    assert len(engine_calls) == 1
    assert engine_calls[0].connect_args == {"server_settings": {"search_path": "auth_schema,public"}}
    auth._run_migrations.assert_awaited_once_with()
    fake_observability.initialize.assert_awaited_once_with()
    fake_observability.instrument_sqlalchemy.assert_called_once_with(fake_engine)
    auth._init_services.assert_awaited_once_with()
    fake_redis.connect.assert_awaited_once_with()
    fake_cache.start.assert_awaited_once_with()
    auth._init_backends.assert_called_once_with()
    auth._init_deps.assert_called_once_with()
    auth._start_token_cleanup_scheduler.assert_called_once_with()
    auth._start_activity_sync_scheduler.assert_called_once_with()


@pytest.mark.unit
def test_outlabs_auth_init_backends_and_deps_and_wrappers():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
    )
    auth.api_key_service = object()
    auth.service_token_service = object()
    auth.permission_service = object()
    auth.access_scope_service = object()
    auth.role_service = object()
    auth.entity_service = object()
    auth.membership_service = object()

    auth._init_backends()
    auth._init_deps()

    assert [backend.name for backend in auth.backends] == [
        "jwt",
        "api_key",
        "service_token",
    ]
    assert auth.deps.get_session == auth.uow

    auth._deps = SimpleNamespace(
        require_permission=MagicMock(return_value="perm"),
        require_entity_permission=MagicMock(return_value="entity"),
        require_tree_permission=MagicMock(return_value="tree"),
    )
    assert auth.require_permission("user:read", require_all=True) == "perm"
    assert auth.require_entity_permission("entity:read") == "entity"
    assert auth.require_tree_permission("entity:create", "parent_id", source="body") == "tree"
    auth._deps.require_permission.assert_called_once_with("user:read", require_all=True)
    auth._deps.require_entity_permission.assert_called_once_with(
        "entity:read",
        entity_id_param="entity_id",
    )
    auth._deps.require_tree_permission.assert_called_once_with(
        "entity:create",
        "parent_id",
        source="body",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_session_uow_and_property_guards():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )

    with pytest.raises(ConfigurationError, match="Database not initialized"):
        auth.get_session()
    with pytest.raises(ConfigurationError, match="Database not initialized"):
        await auth.session().__anext__()
    with pytest.raises(ConfigurationError, match="Database not initialized"):
        await auth.uow(SimpleNamespace(method="GET")).__anext__()
    with pytest.raises(ConfigurationError, match="OutlabsAuth not initialized"):
        await auth.get_current_user(object(), "token")
    with pytest.raises(ConfigurationError, match="Database not initialized"):
        _ = auth.engine
    with pytest.raises(ConfigurationError, match="Database not initialized"):
        _ = auth.session_factory
    with pytest.raises(ConfigurationError, match="Backends not initialized"):
        _ = auth.backends
    with pytest.raises(ConfigurationError, match="Dependencies not initialized"):
        _ = auth.deps

    fake_session_factory = _FakeSessionFactory()
    auth._session_factory = fake_session_factory
    auth._engine = SimpleNamespace()
    auth._backends = ["backend"]
    auth._deps = "deps"
    auth._initialized = True
    auth.auth_service = SimpleNamespace(get_current_user=AsyncMock(return_value="user"))

    managed = auth.get_session()
    assert isinstance(managed, _FakeSession)

    session_dep = auth.session()
    yielded_session = await session_dep.__anext__()
    assert yielded_session is fake_session_factory.sessions[1]
    with pytest.raises(RuntimeError, match="boom"):
        await session_dep.athrow(RuntimeError("boom"))
    fake_session_factory.sessions[1].rollback.assert_awaited_once_with()

    post_uow = auth.uow(SimpleNamespace(method="POST"))
    post_session = await post_uow.__anext__()
    assert post_session is fake_session_factory.sessions[2]
    with pytest.raises(StopAsyncIteration):
        await post_uow.__anext__()
    post_session.commit.assert_awaited_once_with()
    post_session.rollback.assert_not_awaited()

    get_uow = auth.uow(SimpleNamespace(method="GET"))
    get_session = await get_uow.__anext__()
    assert get_session is fake_session_factory.sessions[3]
    with pytest.raises(StopAsyncIteration):
        await get_uow.__anext__()
    get_session.rollback.assert_awaited_once_with()
    get_session.commit.assert_not_awaited()

    error_uow = auth.uow(SimpleNamespace(method="DELETE"))
    error_session = await error_uow.__anext__()
    assert error_session is fake_session_factory.sessions[4]
    with pytest.raises(RuntimeError, match="write failed"):
        await error_uow.athrow(RuntimeError("write failed"))
    error_session.rollback.assert_awaited_once_with()

    assert await auth.get_current_user("db-session", "jwt-token") == "user"
    auth.auth_service.get_current_user.assert_awaited_once_with("db-session", "jwt-token")
    assert auth.engine is auth._engine
    assert auth.session_factory is fake_session_factory
    assert auth.backends == ["backend"]
    assert auth.deps == "deps"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_authorize_api_key_returns_host_safe_auth_result():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    owner_id = uuid4()
    entity_id = uuid4()
    api_key = SimpleNamespace(
        id=uuid4(),
        prefix="sk_live_12345678",
        owner_id=owner_id,
        key_kind=APIKeyKind.PERSONAL,
        entity_id=entity_id,
    )
    user = SimpleNamespace(id=owner_id, can_authenticate=lambda: True)
    auth._initialized = True
    auth.api_key_service = SimpleNamespace(
        verify_api_key=AsyncMock(return_value=(api_key, 7)),
        get_api_key_scopes=AsyncMock(return_value=["contacts:read"]),
    )
    auth.user_service = SimpleNamespace(get_user_by_id=AsyncMock(return_value=user))
    auth.api_key_policy_service = SimpleNamespace(
        evaluate_effectiveness=AsyncMock(
            return_value=SimpleNamespace(
                is_currently_effective=True,
                ineffective_reasons=[],
            )
        )
    )

    result = await auth.authorize_api_key(
        "db-session",
        "sk_live_secret",
        required_scope="contacts:read",
        entity_id=entity_id,
        ip_address="127.0.0.1",
    )

    assert result is not None
    assert result["user"] is user
    assert result["user_id"] == str(owner_id)
    assert result["source"] == "api_key"
    assert result["api_key"] is api_key
    assert result["metadata"] == {
        "key_id": str(api_key.id),
        "key_prefix": "sk_live_12345678",
        "key_kind": "personal",
        "scopes": ["contacts:read"],
        "usage_count": 7,
        "entity_id": str(entity_id),
        "is_currently_effective": True,
        "ineffective_reasons": [],
    }
    auth.api_key_service.verify_api_key.assert_awaited_once_with(
        "db-session",
        "sk_live_secret",
        required_scope="contacts:read",
        entity_id=entity_id,
        ip_address="127.0.0.1",
    )
    auth.api_key_service.get_api_key_scopes.assert_awaited_once_with("db-session", api_key.id)
    auth.user_service.get_user_by_id.assert_awaited_once_with("db-session", owner_id)
    auth.api_key_policy_service.evaluate_effectiveness.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_authorize_api_key_uses_cached_snapshot_without_db_auth():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    api_key_string = "sk_live_direct_cached_key_123456"
    key_id = uuid4()
    user_id = uuid4()
    redis = _SnapshotRedis()
    snapshot_config = auth.config.model_copy(update={"redis_enabled": True, "enable_caching": True})
    cache_service = CacheService(redis, snapshot_config)
    api_key_service = APIKeyService(snapshot_config, redis_client=redis)
    api_key_service.cache_service = cache_service
    await api_key_service.set_api_key_auth_snapshot(
        api_key_string,
        auth_result={
            "user": None,
            "user_id": str(user_id),
            "source": "api_key",
            "api_key": _snapshot_api_key_model(key_id),
            "metadata": {
                "scopes": ["contacts:read"],
                "owner_type": "user",
                "owner_id": str(user_id),
            },
        },
        effective_permissions=["contacts:read"],
        ip_whitelist=["127.0.0.1"],
    )
    api_key_service.verify_api_key = AsyncMock(side_effect=AssertionError("slow path should not run"))

    auth._initialized = True
    auth.api_key_service = api_key_service
    auth.user_service = SimpleNamespace()
    auth.permission_service = SimpleNamespace(config=SimpleNamespace(enable_abac=False))

    result = await auth.authorize_api_key(
        "db-session",
        api_key_string,
        required_scope="contacts:read",
        ip_address="127.0.0.1",
    )

    assert result is not None
    assert result["source"] == "api_key"
    assert result["user_id"] == str(user_id)
    assert result["user"] is None
    assert result["api_key"] is None
    assert result["metadata"]["auth_snapshot"] is True
    assert result["metadata"]["is_currently_effective"] is True
    assert result["metadata"]["ineffective_reasons"] == []
    assert redis.counters[f"apikey:{key_id}:usage"] == 1
    api_key_service.verify_api_key.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_authorize_api_key_uses_entity_snapshot_without_db_auth():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    api_key_string = "sk_live_entity_cached_key_123456"
    key_id = uuid4()
    user_id = uuid4()
    anchor_id = uuid4()
    target_id = uuid4()
    redis = _SnapshotRedis()
    snapshot_config = auth.config.model_copy(update={"redis_enabled": True, "enable_caching": True})
    cache_service = CacheService(redis, snapshot_config)
    api_key_service = APIKeyService(snapshot_config, redis_client=redis)
    api_key_service.cache_service = cache_service
    await api_key_service.set_api_key_auth_snapshot(
        api_key_string,
        auth_result={
            "user": None,
            "user_id": str(user_id),
            "source": "api_key",
            "api_key": _snapshot_api_key_model(
                key_id,
                entity_id=anchor_id,
                inherit_from_tree=True,
            ),
            "metadata": {
                "scopes": ["pipeline:read_tree"],
                "owner_type": "user",
                "owner_id": str(user_id),
            },
        },
        effective_permissions=[],
        ip_whitelist=[],
    )
    await cache_service.set_permission_check(
        str(user_id),
        "pipeline:read_tree",
        True,
        str(target_id),
    )
    await cache_service.set_entity_relation(
        str(anchor_id),
        str(target_id),
        True,
        version=0,
    )
    api_key_service.verify_api_key = AsyncMock(side_effect=AssertionError("slow path should not run"))

    auth._initialized = True
    auth.api_key_service = api_key_service
    auth.user_service = SimpleNamespace()
    auth.permission_service = SimpleNamespace(config=SimpleNamespace(enable_abac=False))

    result = await auth.authorize_api_key(
        "db-session",
        api_key_string,
        required_scope="pipeline:read_tree",
        entity_id=target_id,
    )

    assert result is not None
    assert result["source"] == "api_key"
    assert result["user_id"] == str(user_id)
    assert result["metadata"]["auth_snapshot"] is True
    assert redis.counters[f"apikey:{key_id}:usage"] == 1
    api_key_service.verify_api_key.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_authorize_api_key_populates_direct_snapshot_after_slow_success():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    api_key_string = "sk_live_direct_cache_fill_key_123456"
    key_id = uuid4()
    user_id = uuid4()
    redis = _SnapshotRedis()
    snapshot_config = auth.config.model_copy(update={"redis_enabled": True, "enable_caching": True})
    cache_service = CacheService(redis, snapshot_config)
    api_key_service = APIKeyService(snapshot_config, redis_client=redis)
    api_key_service.cache_service = cache_service
    api_key = _snapshot_api_key_model(key_id)
    user = SimpleNamespace(id=user_id, can_authenticate=lambda: True)
    api_key_service.verify_api_key = AsyncMock(return_value=(api_key, 3))
    api_key_service.resolve_api_key_owner = AsyncMock(
        return_value=SimpleNamespace(
            user=user,
            integration_principal=None,
            owner_id=user_id,
        )
    )
    api_key_service.get_api_key_scopes = AsyncMock(return_value=["contacts:read"])
    api_key_service.get_api_key_ip_whitelist = AsyncMock(return_value=[])
    permission_service = SimpleNamespace(
        config=SimpleNamespace(enable_abac=False),
        get_user_permissions=AsyncMock(return_value=["contacts:read"]),
    )

    auth._initialized = True
    auth.api_key_service = api_key_service
    auth.user_service = SimpleNamespace()
    auth.permission_service = permission_service

    result = await auth.authorize_api_key(
        "db-session",
        api_key_string,
        required_scope="contacts:read",
    )

    snapshot_key = api_key_service._make_auth_snapshot_key(APIKey.hash_key(api_key_string))
    assert result is not None
    assert result["api_key"] is api_key
    assert redis.values[snapshot_key]["effective_permissions"] == ["contacts:read"]
    assert redis.values[snapshot_key]["scopes"] == ["contacts:read"]
    assert redis.values[snapshot_key]["versions"] == {
        "global": 0,
        f"user:{user_id}": 0,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_shutdown_cleans_up_background_resources():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    auth._cleanup_task = asyncio.create_task(asyncio.sleep(3600))
    auth._activity_sync_task = asyncio.create_task(asyncio.sleep(3600))
    auth.cache_service = SimpleNamespace(shutdown=AsyncMock())
    auth.redis_client = SimpleNamespace(disconnect=AsyncMock())
    auth.observability = SimpleNamespace(shutdown=AsyncMock())
    auth._engine = SimpleNamespace(dispose=AsyncMock())

    await auth.shutdown()

    auth.cache_service.shutdown.assert_awaited_once_with()
    auth.redis_client.disconnect.assert_awaited_once_with()
    auth.observability.shutdown.assert_awaited_once_with()
    auth._engine.dispose.assert_awaited_once_with()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_run_migrations_forwards_database_url_and_schema(monkeypatch: pytest.MonkeyPatch):
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        database_schema="auth_schema",
    )
    run_migrations = AsyncMock()

    monkeypatch.setattr("outlabs_auth.cli.run_migrations", run_migrations)

    await auth._run_migrations()

    run_migrations.assert_awaited_once_with(
        "postgresql+asyncpg://example:example@localhost:5432/test",
        schema="auth_schema",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_init_services_wires_redis_cache_enterprise_and_activity_tracking():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
        redis_url="redis://localhost:6379/0",
        enable_activity_tracking=True,
        store_oauth_provider_tokens=True,
        oauth_token_encryption_key=Fernet.generate_key().decode(),
    )
    auth.observability = object()

    await auth._init_services()

    assert auth.redis_client is not None
    assert auth.cache_service is not None
    assert auth.cache is auth.cache_service
    assert auth.oauth_token_cipher is not None
    assert auth.entity_service is not None
    assert auth.membership_service is not None
    assert auth.entity_service.membership_service is auth.membership_service
    assert auth.entity_service.role_service is auth.role_service
    assert auth.entity_service.api_key_service is auth.api_key_service
    assert auth.user_service.membership_service is auth.membership_service
    assert auth.user_service.role_service is auth.role_service
    assert auth.api_key_policy_service is not None
    assert auth.api_key_service.policy_service is auth.api_key_policy_service
    assert auth.user_service.api_key_service is auth.api_key_service
    assert auth.user_service.cache_service is auth.cache_service
    assert auth.role_service.cache_service is auth.cache_service
    assert auth.permission_service.cache_service is auth.cache_service
    assert auth.entity_service.cache_service is auth.cache_service
    assert auth.membership_service.cache_service is auth.cache_service
    assert auth.integration_principal_service.cache_service is auth.cache_service
    assert auth.api_key_service.cache_service is auth.cache_service
    assert auth.activity_tracker is not None
    assert auth.auth_service.activity_tracker is auth.activity_tracker
    assert auth.api_key_policy_service.observability is auth.observability
    assert auth.api_key_service.observability is auth.observability


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_init_services_can_use_redis_without_permission_cache():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        redis_url="redis://localhost:6379/0",
        enable_caching=False,
    )

    await auth._init_services()

    assert auth.redis_client is not None
    assert auth.cache_service is None
    assert auth.cache is None
    assert auth.api_key_service.redis_client is auth.redis_client
    assert auth.user_service.cache_service is None
    assert auth.role_service.cache_service is None
    assert auth.permission_service.cache_service is None
    assert auth.integration_principal_service.cache_service is None
    assert auth.api_key_service.cache_service is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_init_services_rejects_activity_tracking_without_redis():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_activity_tracking=True,
    )

    with pytest.raises(ConfigurationError, match="Activity tracking requires Redis"):
        await auth._init_services()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_token_cleanup_scheduler_runs_success_and_error_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    captured: dict[str, object] = {}
    sleep_calls = 0
    fake_session = _FakeSession()
    cleanup = AsyncMock(side_effect=[None, RuntimeError("cleanup failed")])
    printed: list[str] = []

    def fake_create_task(coro):
        captured["coro"] = coro
        return SimpleNamespace(cancel=lambda: None)

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls < 3:
            return None
        raise asyncio.CancelledError

    monkeypatch.setattr("outlabs_auth.core.auth.asyncio.create_task", fake_create_task)
    monkeypatch.setattr("outlabs_auth.core.auth.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("outlabs_auth.workers.token_cleanup.cleanup_expired_refresh_tokens", cleanup)
    monkeypatch.setattr("builtins.print", lambda message: printed.append(message))
    auth.get_session = lambda: _SessionContext(fake_session)  # type: ignore[method-assign]
    auth.config.token_cleanup_interval_hours = 1

    auth._start_token_cleanup_scheduler()

    with pytest.raises(asyncio.CancelledError):
        await captured["coro"]  # type: ignore[misc]

    assert auth._cleanup_task is not None
    cleanup.assert_any_await(fake_session)
    assert cleanup.await_count == 2
    fake_session.commit.assert_awaited_once_with()
    assert printed == ["[TokenCleanup] Error: cleanup failed"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlabs_auth_activity_sync_scheduler_runs_success_and_error_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    captured: dict[str, object] = {}
    sleep_calls = 0
    fake_session = _FakeSession()
    printed: list[str] = []
    auth.activity_tracker = SimpleNamespace(
        sync_to_database=AsyncMock(side_effect=[{"daily": 1, "monthly": 0}, RuntimeError("sync failed")])
    )

    def fake_create_task(coro):
        captured["coro"] = coro
        return SimpleNamespace(cancel=lambda: None)

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls < 3:
            return None
        raise asyncio.CancelledError

    monkeypatch.setattr("outlabs_auth.core.auth.asyncio.create_task", fake_create_task)
    monkeypatch.setattr("outlabs_auth.core.auth.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("builtins.print", lambda message: printed.append(message))
    auth.get_session = lambda: _SessionContext(fake_session)  # type: ignore[method-assign]
    auth.config.activity_sync_interval = 10

    auth._start_activity_sync_scheduler()

    with pytest.raises(asyncio.CancelledError):
        await captured["coro"]  # type: ignore[misc]

    assert auth._activity_sync_task is not None
    auth.activity_tracker.sync_to_database.assert_any_await(fake_session)
    assert auth.activity_tracker.sync_to_database.await_count == 2
    fake_session.commit.assert_awaited_once_with()
    assert printed == [
        "[ActivitySync] Synced metrics - DAU: 1, MAU: 0",
        "[ActivitySync] Error: sync failed",
    ]


@pytest.mark.unit
def test_outlabs_auth_instrument_fastapi_registers_integrations_and_warns(
    monkeypatch: pytest.MonkeyPatch,
):
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        trust_resource_context_header=True,
    )
    auth.observability = SimpleNamespace(config=SimpleNamespace(metrics_path="/metrics"))

    register_calls: list[dict] = []
    monkeypatch.setattr(
        "outlabs_auth.fastapi.register_exception_handlers",
        lambda app, **kwargs: register_calls.append(kwargs),
    )

    correlation_middleware = type("CorrelationIDMiddleware", (), {})
    resource_context_middleware = type("ResourceContextMiddleware", (), {})
    request_cache_middleware = type("RequestCacheMiddleware", (), {})
    monkeypatch.setattr(
        "outlabs_auth.observability.CorrelationIDMiddleware",
        correlation_middleware,
    )
    monkeypatch.setattr(
        "outlabs_auth.observability.create_metrics_router",
        lambda observability, path: {"observability": observability, "path": path},
    )
    monkeypatch.setattr(
        "outlabs_auth.middleware.ResourceContextMiddleware",
        resource_context_middleware,
    )
    monkeypatch.setattr(
        "outlabs_auth.middleware.RequestCacheMiddleware",
        request_cache_middleware,
    )

    app = _FakeApp(fail_middleware=False)
    auth.instrument_fastapi(
        app,
        debug=True,
        exception_handler_mode="global",
        include_metrics=True,
        include_correlation_id=True,
        include_resource_context=True,
    )

    assert register_calls == [
        {
            "debug": True,
            "observability": auth.observability,
            "mode": "global",
        }
    ]
    assert app.middleware_calls == [
        (request_cache_middleware, {}),
        (correlation_middleware, {"obs_service": auth.observability}),
        (resource_context_middleware, {"trust_client_header": True}),
    ]
    assert app.routers == [{"observability": auth.observability, "path": "/metrics"}]

    warning_app = _FakeApp(fail_middleware=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        auth.instrument_fastapi(
            warning_app,
            include_correlation_id=True,
            include_resource_context=True,
        )

    assert len(caught) == 1
    assert "middleware was skipped" in str(caught[0].message)


@pytest.mark.unit
def test_outlabs_auth_instrument_fastapi_re_raises_unexpected_middleware_runtime_error():
    auth = OutlabsAuth(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
    )
    auth.observability = SimpleNamespace(config=SimpleNamespace(metrics_path="/metrics"))

    class _ExplodingApp:
        def exception_handler(self, _exc_type):
            def _decorator(func):
                return func

            return _decorator

        def add_middleware(self, middleware_class: type, **kwargs: object) -> None:
            raise RuntimeError("middleware exploded")

        def include_router(self, router: object) -> None:
            raise AssertionError("include_router should not be reached")

    with pytest.raises(RuntimeError, match="middleware exploded"):
        auth.instrument_fastapi(
            _ExplodingApp(),
            include_correlation_id=True,
        )
