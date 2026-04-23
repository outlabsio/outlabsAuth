from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from outlabs_auth.authentication.backend import AuthBackend
from outlabs_auth.authentication.transport import HeaderTransport
from outlabs_auth.dependencies import AuthDeps, create_auth_deps


class _StaticAuthResultStrategy:
    def __init__(self, auth_result):
        self.auth_result = auth_result

    async def authenticate(self, credentials: str, **kwargs):
        return self.auth_result


class _ExplodingStrategy:
    async def authenticate(self, credentials: str, **kwargs):
        raise RuntimeError("backend exploded")


class _PermissionServiceStub:
    def __init__(self, result=True, *, enable_abac: bool = False):
        self.result = result
        self.calls: list[dict] = []
        self.config = SimpleNamespace(enable_abac=enable_abac)

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
                "session": session,
                "user_id": user_id,
                "permission": permission,
                "entity_id": entity_id,
                "resource_context": resource_context,
                "env_context": env_context,
            }
        )
        return self.result


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
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in (headers or {}).items()
        ],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


@pytest.mark.unit
def test_permission_set_allows_delegates_to_permission_service_helper():
    permission_service = SimpleNamespace(_permission_set_allows=MagicMock(return_value=True))
    deps = AuthDeps(backends=[], permission_service=permission_service)

    allowed = deps._permission_set_allows("user:read", ["*", "", None])

    assert allowed is True
    permission_service._permission_set_allows.assert_called_once_with("user:read", {"*:*"})
    assert isinstance(create_auth_deps([]), AuthDeps)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_result_permission_denies_api_keys_without_runtime_services():
    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(backends=[], permission_service=permission_service)

    allowed = await deps._auth_result_has_permission(
        auth_result={
            "source": "api_key",
            "user_id": str(uuid4()),
            "api_key": SimpleNamespace(id=uuid4()),
            "metadata": {"scopes": ["user:read"]},
        },
        session=object(),
        permission="user:read",
        entity_id=None,
        resource_context=None,
        env_context=None,
    )

    assert allowed is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_auth_continues_past_backend_exceptions():
    user_id = uuid4()
    exploding_backend = AuthBackend(
        name="exploding",
        transport=HeaderTransport(header_name="X-Exploding"),
        strategy=_ExplodingStrategy(),
    )
    working_backend = AuthBackend(
        name="working",
        transport=HeaderTransport(header_name="X-Working"),
        strategy=_StaticAuthResultStrategy(
            {"user_id": str(user_id), "source": "working", "user": None}
        ),
    )
    deps = AuthDeps(backends=[exploding_backend, working_backend], get_session=lambda: None)

    dependency = deps.require_auth()
    request = _make_request(
        "GET",
        "/me",
        headers={"X-Exploding": "bad", "X-Working": str(user_id)},
    )

    auth_result = await dependency(request=request, session=object())

    assert auth_result["source"] == "working"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_handles_empty_auth_and_abac_request_context(
    monkeypatch: pytest.MonkeyPatch,
):
    permission_service = _PermissionServiceStub(result=True, enable_abac=True)
    deps = AuthDeps(backends=[], permission_service=permission_service)

    async def _no_auth(*args, **kwargs):
        return None

    monkeypatch.setattr(deps, "_authenticate_request", _no_auth)

    dependency = deps.require_permission("user:read")
    with pytest.raises(HTTPException) as exc_info:
        await dependency(request=_make_request("GET", "/users"))
    assert exc_info.value.status_code == 401

    user_id = uuid4()
    backend = AuthBackend(
        name="header",
        transport=HeaderTransport(header_name="X-User"),
        strategy=_StaticAuthResultStrategy({"user_id": str(user_id), "source": "jwt"}),
    )
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        get_session=lambda: None,
    )
    dependency = deps.require_permission("user:read", allow_entity_context_header=True)
    request = _make_request(
        "GET",
        "/users",
        headers={"X-User": str(user_id), "X-Entity-Context": str(uuid4()), "User-Agent": "pytest"},
    )
    request.state.resource_context = {"owner_id": "123"}

    auth_result = await dependency(request=request, session=object())

    assert auth_result["user_id"] == str(user_id)
    assert permission_service.calls[-1]["resource_context"] == {"owner_id": "123"}
    assert permission_service.calls[-1]["env_context"] == {
        "method": "GET",
        "path": "/users",
        "client_host": "testclient",
        "user_agent": "pytest",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_permission_ignores_empty_and_rejects_invalid_entity_context_headers():
    user_id = uuid4()
    permission_service = _PermissionServiceStub(result=True)
    backend = AuthBackend(
        name="header",
        transport=HeaderTransport(header_name="X-User"),
        strategy=_StaticAuthResultStrategy({"user_id": str(user_id), "source": "jwt"}),
    )
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        get_session=lambda: None,
    )
    dependency = deps.require_permission("entity:read", allow_entity_context_header=True)

    empty_request = _make_request(
        "GET",
        "/entities",
        headers={"X-User": str(user_id), "X-Entity-Context": ""},
    )
    await dependency(request=empty_request, session=object())
    assert permission_service.calls[-1]["entity_id"] is None

    invalid_request = _make_request(
        "GET",
        "/entities",
        headers={"X-User": str(user_id), "X-Entity-Context": "not-a-uuid"},
    )
    with pytest.raises(HTTPException) as invalid_exc:
        await dependency(request=invalid_request, session=object())
    assert invalid_exc.value.status_code == 400
    assert invalid_exc.value.detail == "Invalid entity context ID"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_entity_permission_handles_missing_auth_service_session_and_abac(
    monkeypatch: pytest.MonkeyPatch,
):
    user_id = uuid4()
    request = _make_request(
        "GET",
        f"/entities/{uuid4()}",
        path_params={"entity_id": str(uuid4())},
    )

    deps = AuthDeps(backends=[], get_session=lambda: None)

    async def _no_auth(*args, **kwargs):
        return None

    monkeypatch.setattr(deps, "_authenticate_request", _no_auth)
    dependency = deps.require_entity_permission("entity:read")
    with pytest.raises(HTTPException) as no_auth_exc:
        await dependency(request=request, session=object())
    assert no_auth_exc.value.status_code == 401

    async def _auth_result(*args, **kwargs):
        return {"user_id": str(user_id), "source": "jwt"}

    monkeypatch.setattr(deps, "_authenticate_request", _auth_result)
    with pytest.raises(HTTPException) as no_service_exc:
        await dependency(request=request, session=object())
    assert no_service_exc.value.status_code == 500
    assert no_service_exc.value.detail == "Permission service not configured"

    permission_service = _PermissionServiceStub(result=True, enable_abac=True)
    deps = AuthDeps(backends=[], permission_service=permission_service, get_session=lambda: None)
    monkeypatch.setattr(deps, "_authenticate_request", _auth_result)
    dependency = deps.require_entity_permission("entity:read")

    with pytest.raises(HTTPException) as no_session_exc:
        await dependency(request=request, session=None)
    assert no_session_exc.value.status_code == 500
    assert no_session_exc.value.detail == "Database session not configured for auth dependencies"

    success_request = _make_request(
        "GET",
        f"/entities/{uuid4()}",
        headers={"User-Agent": "pytest"},
        path_params={"entity_id": str(uuid4())},
    )
    success_request.state.resource_context = {"entity_type": "team"}

    auth_result = await dependency(request=success_request, session=object())

    assert auth_result["user_id"] == str(user_id)
    assert permission_service.calls[-1]["resource_context"] == {"entity_type": "team"}
    assert permission_service.calls[-1]["env_context"] == {
        "method": "GET",
        "path": success_request.url.path,
        "client_host": "testclient",
        "user_agent": "pytest",
    }

    invalid_request = _make_request(
        "GET",
        "/entities/bad",
        path_params={"entity_id": "not-a-uuid"},
    )
    with pytest.raises(HTTPException) as invalid_exc:
        await dependency(request=invalid_request, session=object())
    assert invalid_exc.value.status_code == 400
    assert invalid_exc.value.detail == "Entity ID is required"


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("permission", "source", "value", "expected_permission"),
    [
        ("*:*", "query", "11111111-1111-1111-1111-111111111111", "*:*"),
        ("report", "query", "11111111-1111-1111-1111-111111111111", "report"),
        ("entity:*", "header", "11111111-1111-1111-1111-111111111111", "entity:*"),
        (
            "entity:read_tree",
            "header",
            "11111111-1111-1111-1111-111111111111",
            "entity:read_tree",
        ),
    ],
)
async def test_require_tree_permission_preserves_special_permission_forms(
    permission: str,
    source: str,
    value: str,
    expected_permission: str,
):
    user_id = uuid4()
    backend = AuthBackend(
        name="header",
        transport=HeaderTransport(header_name="X-User"),
        strategy=_StaticAuthResultStrategy({"user_id": str(user_id), "source": "jwt"}),
    )
    permission_service = _PermissionServiceStub(result=True, enable_abac=True)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        get_session=lambda: None,
    )
    dependency = deps.require_tree_permission(permission, "target_id", source=source)

    request_kwargs = {
        "method": "GET",
        "path": "/entities",
        "headers": {"X-User": str(user_id), "User-Agent": "pytest"},
        "query_params": {"target_id": value} if source == "query" else None,
    }
    if source == "header":
        request_kwargs["headers"]["target_id"] = value

    request = _make_request(**request_kwargs)
    request.state.resource_context = {"kind": "child"}

    auth_result = await dependency(request=request, session=object())

    assert auth_result["user_id"] == str(user_id)
    assert permission_service.calls[-1]["permission"] == expected_permission
    assert permission_service.calls[-1]["resource_context"] == {"kind": "child"}
    assert permission_service.calls[-1]["env_context"] == {
        "method": "GET",
        "path": "/entities",
        "client_host": "testclient",
        "user_agent": "pytest",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_tree_permission_validates_inputs_and_permission_service(
    monkeypatch: pytest.MonkeyPatch,
):
    with pytest.raises(ValueError, match="source must be one of"):
        AuthDeps(backends=[]).require_tree_permission("entity:create", "entity_id", source="cookie")

    deps = AuthDeps(backends=[], get_session=lambda: None)
    request = _make_request(
        "GET",
        "/entities",
        query_params={"entity_id": str(uuid4())},
    )

    async def _auth_result(*args, **kwargs):
        return {"user_id": str(uuid4()), "source": "jwt"}

    monkeypatch.setattr(deps, "_authenticate_request", _auth_result)
    dependency = deps.require_tree_permission("entity:create", "entity_id", source="query")

    with pytest.raises(HTTPException) as no_service_exc:
        await dependency(request=request, session=object())
    assert no_service_exc.value.status_code == 500
    assert no_service_exc.value.detail == "Permission service not configured"

    deps = AuthDeps(
        backends=[],
        permission_service=_PermissionServiceStub(result=True),
        get_session=lambda: None,
    )
    monkeypatch.setattr(deps, "_authenticate_request", _auth_result)
    dependency = deps.require_tree_permission("entity:create", "entity_id", source="query")

    with pytest.raises(HTTPException) as no_session_exc:
        await dependency(request=request, session=None)
    assert no_session_exc.value.status_code == 500
    assert no_session_exc.value.detail == "Database session not configured for auth dependencies"

    invalid_request = _make_request(
        "GET",
        "/entities",
        query_params={"entity_id": "bad"},
    )
    with pytest.raises(HTTPException) as invalid_exc:
        await dependency(request=invalid_request, session=object())
    assert invalid_exc.value.status_code == 400
    assert invalid_exc.value.detail == "Invalid entity_id"

    denied_service = _PermissionServiceStub(result=False)
    deps = AuthDeps(
        backends=[],
        permission_service=denied_service,
        get_session=lambda: None,
    )
    monkeypatch.setattr(deps, "_authenticate_request", _auth_result)
    denied_dependency = deps.require_tree_permission("entity:create", "entity_id", source="query")

    with pytest.raises(HTTPException) as denied_exc:
        await denied_dependency(request=request, session=object())
    assert denied_exc.value.status_code == 403
    assert denied_exc.value.detail == "Insufficient permissions"

    async def _no_auth(*args, **kwargs):
        return None

    monkeypatch.setattr(deps, "_authenticate_request", _no_auth)
    no_auth_dependency = deps.require_tree_permission("entity:create", "entity_id", source="path")
    no_auth_request = _make_request(
        "GET",
        f"/entities/{uuid4()}",
        path_params={"entity_id": str(uuid4())},
    )
    with pytest.raises(HTTPException) as no_auth_exc:
        await no_auth_dependency(request=no_auth_request, session=object())
    assert no_auth_exc.value.status_code == 401

    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(
        backends=[],
        permission_service=permission_service,
        get_session=lambda: None,
    )
    monkeypatch.setattr(deps, "_authenticate_request", _auth_result)
    path_dependency = deps.require_tree_permission("entity:create", "entity_id", source="path")
    path_request = _make_request(
        "GET",
        f"/entities/{uuid4()}",
        path_params={"entity_id": "11111111-1111-1111-1111-111111111111"},
    )

    await path_dependency(request=path_request, session=object())
    assert permission_service.calls[-1]["permission"] == "entity:create_tree"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_snapshot_preflight_preserves_auth_first_failures(
    monkeypatch: pytest.MonkeyPatch,
):
    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(
        backends=[],
        permission_service=permission_service,
        get_session=lambda: None,
    )

    async def _no_auth(*args, **kwargs):
        return None

    monkeypatch.setattr(deps, "_authenticate_request", _no_auth)

    entity_dependency = deps.require_entity_permission("entity:read")
    invalid_entity_request = _make_request(
        "GET",
        "/entities/not-a-uuid",
        path_params={"entity_id": "not-a-uuid"},
    )
    with pytest.raises(HTTPException) as entity_exc:
        await entity_dependency(request=invalid_entity_request, session=object())
    assert entity_exc.value.status_code == 401

    tree_dependency = deps.require_tree_permission("entity:create", "entity_id", source="query")
    invalid_tree_request = _make_request(
        "GET",
        "/entities",
        query_params={"entity_id": "not-a-uuid"},
    )
    with pytest.raises(HTTPException) as tree_exc:
        await tree_dependency(request=invalid_tree_request, session=object())
    assert tree_exc.value.status_code == 401
    assert permission_service.calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_require_source_and_superuser_cover_success_and_no_auth(
    monkeypatch: pytest.MonkeyPatch,
):
    user_id = uuid4()
    superuser = SimpleNamespace(is_superuser=True)
    superuser.can_authenticate = lambda: True
    backend = AuthBackend(
        name="header",
        transport=HeaderTransport(header_name="X-User"),
        strategy=_StaticAuthResultStrategy(
            {"user_id": str(user_id), "source": "jwt", "user": superuser}
        ),
    )
    deps = AuthDeps(backends=[backend], get_session=lambda: None)
    request = _make_request("GET", "/admin", headers={"X-User": str(user_id)})

    source_dependency = deps.require_source("jwt")
    superuser_dependency = deps.require_superuser()

    assert (await source_dependency(request=request, session=object()))["source"] == "jwt"
    assert (await superuser_dependency(request=request, session=object()))["user"] is superuser

    async def _no_auth(*args, **kwargs):
        return None

    monkeypatch.setattr(deps, "_authenticate_request", _no_auth)
    with pytest.raises(HTTPException) as exc_info:
        await deps.require_superuser()(request=request, session=object())
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"
