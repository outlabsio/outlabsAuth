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
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.service_token import ServiceTokenService


class _StaticAuthResultStrategy:
    def __init__(self, auth_result: dict) -> None:
        self.auth_result = auth_result

    async def authenticate(self, credentials: str, **kwargs):
        return self.auth_result


class _PermissionServiceStub:
    def __init__(self, result: bool, *, abac_enabled: bool = False, condition_result: bool = False) -> None:
        self.result = result
        self.condition_result = condition_result
        self.calls: list[dict] = []
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
