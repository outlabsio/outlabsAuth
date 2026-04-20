from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from outlabs_auth.authentication.backend import AuthBackend
from outlabs_auth.authentication.strategy import ServiceTokenStrategy
from outlabs_auth.authentication.transport import ApiKeyTransport, BearerTransport
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.service_token import ServiceTokenService


class _StaticAuthResultStrategy:
    def __init__(self, auth_result: dict) -> None:
        self.auth_result = auth_result

    async def authenticate(self, credentials: str, **kwargs):
        return self.auth_result


class _PermissionServiceStub:
    def __init__(
        self,
        result: bool,
        *,
        abac_enabled: bool = False,
        condition_result: bool = False,
        user_permissions: list[str] | None = None,
    ) -> None:
        self.result = result
        self.condition_result = condition_result
        self.user_permissions = user_permissions or []
        self.calls: list[dict] = []
        self.get_user_permissions_calls: list[dict] = []
        self.config = SimpleNamespace(enable_abac=abac_enabled)

    async def check_permission(
        self,
        session,
        *,
        user_id,
        permission,
        entity_id=None,
        resource_context=None,
        env_context=None,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "permission": permission,
                "entity_id": entity_id,
            }
        )
        return self.result

    async def permission_has_conditions(self, session, permission_name):
        return self.condition_result

    async def get_user_permissions(self, session, *, user_id, include_entity_local=True):
        self.get_user_permissions_calls.append(
            {
                "user_id": user_id,
                "include_entity_local": include_entity_local,
            }
        )
        return list(self.user_permissions)


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


def _make_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    path_params: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
    body: dict | None = None,
) -> Request:
    raw_body = json.dumps(body or {}).encode("utf-8")
    query_string = (
        "&".join(f"{key}={value}" for key, value in (query_params or {}).items()).encode("utf-8")
    )

    async def receive():
        return {"type": "http.request", "body": raw_body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "path_params": path_params or {},
        "query_string": query_string,
        "headers": [
            *[
                (k.lower().encode("utf-8"), v.encode("utf-8"))
                for k, v in (headers or {}).items()
            ]
        ],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


def _api_key_model(
    key_id: UUID,
    *,
    prefix: str = "sk_live_cached_1",
    entity_id: UUID | None = None,
    inherit_from_tree: bool = False,
) -> SimpleNamespace:
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_allows_cached_api_key_snapshot_without_backend_auth(
    test_session,
    auth_config,
):
    api_key_string = "sk_live_cached_permission_key_123456"
    key_id = uuid4()
    user_id = uuid4()
    redis = _SnapshotRedis()
    snapshot_config = auth_config.model_copy(update={"redis_enabled": True, "enable_caching": True})
    api_key_service = APIKeyService(snapshot_config, redis_client=redis)
    await api_key_service.set_api_key_auth_snapshot(
        api_key_string,
        auth_result={
            "user": None,
            "user_id": str(user_id),
            "source": "api_key",
            "api_key": _api_key_model(key_id),
            "metadata": {
                "scopes": ["job:write"],
                "owner_type": "user",
                "owner_id": str(user_id),
            },
        },
        effective_permissions=["job:write"],
        ip_whitelist=[],
    )

    permission_service = _PermissionServiceStub(result=False)
    deps = AuthDeps(
        backends=[],
        permission_service=permission_service,
        api_key_service=api_key_service,
        get_session=lambda: None,
    )

    dep = deps.require_permission("job:write")
    request = _make_request("POST", "/jobs/claim", headers={"X-API-Key": api_key_string})

    resolved = await dep(request=request, session=test_session)

    assert resolved["source"] == "api_key"
    assert resolved["user_id"] == str(user_id)
    assert resolved["metadata"]["auth_snapshot"] is True
    assert permission_service.calls == []
    assert redis.counters[f"apikey:{key_id}:usage"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_tree_permission_allows_cached_entity_snapshot_without_backend_auth(
    test_session,
    auth_config,
):
    api_key_string = "sk_live_cached_tree_key_123456789"
    key_id = uuid4()
    user_id = uuid4()
    anchor_id = uuid4()
    target_id = uuid4()
    redis = _SnapshotRedis()
    snapshot_config = auth_config.model_copy(update={"redis_enabled": True, "enable_caching": True})
    cache_service = CacheService(redis, snapshot_config)
    api_key_service = APIKeyService(snapshot_config, redis_client=redis)
    api_key_service.cache_service = cache_service
    await api_key_service.set_api_key_auth_snapshot(
        api_key_string,
        auth_result={
            "user": None,
            "user_id": str(user_id),
            "source": "api_key",
            "api_key": _api_key_model(
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
    permission_service = _PermissionServiceStub(result=False)
    deps = AuthDeps(
        backends=[],
        permission_service=permission_service,
        api_key_service=api_key_service,
        get_session=lambda: None,
    )

    dep = deps.require_tree_permission("pipeline:read", "entity_id", source="path")
    request = _make_request(
        "GET",
        f"/entities/{target_id}/pipeline",
        headers={"X-API-Key": api_key_string},
        path_params={"entity_id": str(target_id)},
    )

    resolved = await dep(request=request, session=test_session)

    assert resolved["source"] == "api_key"
    assert resolved["user_id"] == str(user_id)
    assert resolved["metadata"]["auth_snapshot"] is True
    assert permission_service.calls == []
    assert redis.counters[f"apikey:{key_id}:usage"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_populates_api_key_snapshot_after_slow_success(
    test_session,
    auth_config,
):
    api_key_string = "sk_live_cache_fill_key_123456789"
    key_id = uuid4()
    user_id = uuid4()
    redis = _SnapshotRedis()
    snapshot_config = auth_config.model_copy(update={"redis_enabled": True, "enable_caching": True})
    api_key_service = APIKeyService(snapshot_config, redis_client=redis)
    auth_result = {
        "user": None,
        "user_id": str(user_id),
        "source": "api_key",
        "api_key": _api_key_model(key_id),
        "metadata": {
            "scopes": ["job:write"],
            "owner_type": "user",
            "owner_id": str(user_id),
        },
    }
    backend = AuthBackend(
        name="api_key",
        transport=ApiKeyTransport(header_name="X-API-Key"),
        strategy=_StaticAuthResultStrategy(auth_result),
    )
    permission_service = _PermissionServiceStub(result=True, user_permissions=["job:write"])
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        api_key_service=api_key_service,
        get_session=lambda: None,
    )

    dep = deps.require_permission("job:write")
    request = _make_request("POST", "/jobs/claim", headers={"X-API-Key": api_key_string})

    resolved = await dep(request=request, session=test_session)

    snapshot_key = api_key_service._make_auth_snapshot_key(APIKey.hash_key(api_key_string))
    assert resolved is auth_result
    assert permission_service.calls
    assert redis.values[snapshot_key]["effective_permissions"] == ["job:write"]
    assert redis.values[snapshot_key]["scopes"] == ["job:write"]
    assert redis.values[snapshot_key]["versions"] == {
        "global": 0,
        f"user:{user_id}": 0,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_rejects_stale_api_key_snapshot(
    test_session,
    auth_config,
):
    api_key_string = "sk_live_stale_permission_key_123456"
    key_id = uuid4()
    user_id = uuid4()
    redis = _SnapshotRedis()
    snapshot_config = auth_config.model_copy(update={"redis_enabled": True, "enable_caching": True})
    cache_service = CacheService(redis, snapshot_config)
    api_key_service = APIKeyService(snapshot_config, redis_client=redis)
    api_key_service.cache_service = cache_service
    await api_key_service.set_api_key_auth_snapshot(
        api_key_string,
        auth_result={
            "user": None,
            "user_id": str(user_id),
            "source": "api_key",
            "api_key": _api_key_model(key_id),
            "metadata": {
                "scopes": ["job:write"],
                "owner_type": "user",
                "owner_id": str(user_id),
            },
        },
        effective_permissions=["job:write"],
        ip_whitelist=[],
    )
    await cache_service.bump_user_api_key_auth_snapshot_version(str(user_id))

    permission_service = _PermissionServiceStub(result=False)
    deps = AuthDeps(
        backends=[],
        permission_service=permission_service,
        api_key_service=api_key_service,
        get_session=lambda: None,
    )

    dep = deps.require_permission("job:write")
    request = _make_request("POST", "/jobs/claim", headers={"X-API-Key": api_key_string})

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=request, session=test_session)

    snapshot_key = api_key_service._make_auth_snapshot_key(APIKey.hash_key(api_key_string))
    assert exc_info.value.status_code == 401
    assert snapshot_key in redis.deleted
    assert snapshot_key not in redis.values


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_denies_api_key_when_scope_is_narrower(
    test_session,
    auth_config,
):
    user_id = uuid4()
    backend = AuthBackend(
        name="api_key",
        transport=ApiKeyTransport(header_name="X-API-Key"),
        strategy=_StaticAuthResultStrategy(
            {
                "user": None,
                "user_id": str(user_id),
                "source": "api_key",
                "api_key": SimpleNamespace(id=uuid4()),
                "metadata": {"scopes": ["user:read"]},
            }
        ),
    )
    permission_service = _PermissionServiceStub(result=True)
    api_key_service = APIKeyService(auth_config)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        api_key_service=api_key_service,
        get_session=lambda: None,
    )

    dep = deps.require_permission("user:delete")
    request = _make_request("GET", "/users", headers={"X-API-Key": "sk_test"})

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=request, session=test_session)

    assert exc_info.value.status_code == 403
    assert permission_service.calls == [
        {
            "user_id": UUID(str(user_id)),
            "permission": "user:delete",
            "entity_id": None,
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_allows_unscoped_api_key_when_owner_has_permission(
    test_session,
    auth_config,
):
    user_id = uuid4()
    auth_result = {
        "user": None,
        "user_id": str(user_id),
        "source": "api_key",
        "api_key": SimpleNamespace(id=uuid4()),
        "metadata": {"scopes": []},
    }
    backend = AuthBackend(
        name="api_key",
        transport=ApiKeyTransport(header_name="X-API-Key"),
        strategy=_StaticAuthResultStrategy(auth_result),
    )
    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        api_key_service=APIKeyService(auth_config),
        get_session=lambda: None,
    )

    dep = deps.require_permission("user:delete")
    request = _make_request("GET", "/users", headers={"X-API-Key": "sk_test"})

    resolved = await dep(request=request, session=test_session)

    assert resolved["source"] == "api_key"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_entity_permission_denies_api_key_outside_entity_scope(
    test_session,
    auth_config,
    monkeypatch,
):
    user_id = uuid4()
    entity_id = uuid4()
    auth_result = {
        "user": None,
        "user_id": str(user_id),
        "source": "api_key",
        "api_key": SimpleNamespace(id=uuid4()),
        "metadata": {"scopes": ["entity:read"]},
    }
    backend = AuthBackend(
        name="api_key",
        transport=ApiKeyTransport(header_name="X-API-Key"),
        strategy=_StaticAuthResultStrategy(auth_result),
    )
    permission_service = _PermissionServiceStub(result=True)
    api_key_service = APIKeyService(auth_config)

    async def _deny_entity_access(session, api_key, requested_entity_id):
        return False

    monkeypatch.setattr(api_key_service, "check_entity_access_with_tree", _deny_entity_access)

    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        api_key_service=api_key_service,
        get_session=lambda: None,
    )

    dep = deps.require_entity_permission("entity:read")
    request = _make_request(
        "GET",
        f"/entities/{entity_id}",
        headers={"X-API-Key": "sk_test"},
        path_params={"entity_id": str(entity_id)},
    )

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=request, session=test_session)

    assert exc_info.value.status_code == 403


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_allows_service_token_with_embedded_permissions(
    test_session,
    auth_config,
):
    service_token_service = ServiceTokenService(auth_config)
    token = service_token_service.create_service_token(
        service_id="reporting-service",
        service_name="Reporting Service",
        permissions=["report:generate"],
    )
    backend = AuthBackend(
        name="service_token",
        transport=BearerTransport(),
        strategy=ServiceTokenStrategy(
            secret=auth_config.secret_key,
            algorithm=auth_config.algorithm,
        ),
    )
    deps = AuthDeps(
        backends=[backend],
        permission_service=_PermissionServiceStub(result=False),
        service_token_service=service_token_service,
        get_session=lambda: None,
    )

    dep = deps.require_permission("report:generate")
    request = _make_request(
        "GET",
        "/reports",
        headers={"Authorization": f"Bearer {token}"},
    )

    auth_result = await dep(request=request, session=test_session)

    assert auth_result["source"] == "service_token"
    assert auth_result["service_id"] == "reporting-service"
    assert auth_result["service_name"] == "Reporting Service"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_allows_principal_backed_api_key_without_user_id(
    test_session,
    auth_config,
):
    entity_id = uuid4()
    auth_result = {
        "user": None,
        "user_id": None,
        "integration_principal_id": str(uuid4()),
        "source": "api_key",
        "api_key": SimpleNamespace(id=uuid4(), entity_id=entity_id, inherit_from_tree=False),
        "metadata": {
            "scopes": ["jobs:run"],
            "principal_allowed_scopes": ["jobs:run"],
        },
    }
    backend = AuthBackend(
        name="api_key",
        transport=ApiKeyTransport(header_name="X-API-Key"),
        strategy=_StaticAuthResultStrategy(auth_result),
    )
    permission_service = _PermissionServiceStub(result=False)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        api_key_service=APIKeyService(auth_config),
        get_session=lambda: None,
    )

    dep = deps.require_permission("jobs:run")
    request = _make_request("GET", "/jobs", headers={"X-API-Key": "sk_test"})

    resolved = await dep(request=request, session=test_session)

    assert resolved["integration_principal_id"] == auth_result["integration_principal_id"]
    assert permission_service.calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_denies_principal_backed_api_key_for_abac_conditioned_permission(
    test_session,
    auth_config,
):
    auth_result = {
        "user": None,
        "user_id": None,
        "integration_principal_id": str(uuid4()),
        "source": "api_key",
        "api_key": SimpleNamespace(id=uuid4(), entity_id=None, inherit_from_tree=False),
        "metadata": {
            "scopes": ["reports:read"],
            "principal_allowed_scopes": ["reports:read"],
        },
    }
    backend = AuthBackend(
        name="api_key",
        transport=ApiKeyTransport(header_name="X-API-Key"),
        strategy=_StaticAuthResultStrategy(auth_result),
    )
    permission_service = _PermissionServiceStub(result=False, abac_enabled=True, condition_result=True)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        api_key_service=APIKeyService(auth_config),
        get_session=lambda: None,
    )

    dep = deps.require_permission("reports:read")
    request = _make_request("GET", "/reports", headers={"X-API-Key": "sk_test"})

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=request, session=test_session)

    assert exc_info.value.status_code == 403


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_denies_service_token_missing_embedded_permission(
    test_session,
    auth_config,
):
    service_token_service = ServiceTokenService(auth_config)
    token = service_token_service.create_service_token(
        service_id="reporting-service",
        service_name="Reporting Service",
        permissions=["report:read"],
    )
    backend = AuthBackend(
        name="service_token",
        transport=BearerTransport(),
        strategy=ServiceTokenStrategy(
            secret=auth_config.secret_key,
            algorithm=auth_config.algorithm,
        ),
    )
    deps = AuthDeps(
        backends=[backend],
        permission_service=_PermissionServiceStub(result=False),
        service_token_service=service_token_service,
        get_session=lambda: None,
    )

    dep = deps.require_permission("report:generate")
    request = _make_request(
        "GET",
        "/reports",
        headers={"Authorization": f"Bearer {token}"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=request, session=test_session)

    assert exc_info.value.status_code == 403
