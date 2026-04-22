from __future__ import annotations

import inspect
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from outlabs_auth.authentication.backend import AuthBackend
from outlabs_auth.authentication.transport import HeaderTransport
from outlabs_auth.dependencies import AuthDeps


class _StaticAuthResultStrategy:
    def __init__(self, auth_result):
        self.auth_result = auth_result

    async def authenticate(self, credentials: str, **kwargs):
        return self.auth_result


class _SequenceStrategy:
    def __init__(self, *results):
        self.results = list(results)

    async def authenticate(self, credentials: str, **kwargs):
        return self.results.pop(0)


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
                "user_id": user_id,
                "permission": permission,
                "entity_id": entity_id,
                "resource_context": resource_context,
                "env_context": env_context,
            }
        )
        if callable(self.result):
            return self.result(permission)
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
async def test_auth_deps_require_auth_filters_inactive_and_unverified_users():
    user_id = uuid4()
    inactive_user = SimpleNamespace(id=user_id, email_verified=True)
    inactive_user.can_authenticate = lambda: False
    unverified_user = SimpleNamespace(id=user_id, email_verified=False)
    unverified_user.can_authenticate = lambda: True
    verified_user = SimpleNamespace(id=user_id, email_verified=True)
    verified_user.can_authenticate = lambda: True

    inactive_backend = AuthBackend(
        name="inactive",
        transport=HeaderTransport(header_name="X-Inactive"),
        strategy=_StaticAuthResultStrategy(
            {"user": inactive_user, "user_id": str(user_id), "source": "inactive"}
        ),
    )
    unverified_backend = AuthBackend(
        name="unverified",
        transport=HeaderTransport(header_name="X-Unverified"),
        strategy=_StaticAuthResultStrategy(
            {"user": unverified_user, "user_id": str(user_id), "source": "unverified"}
        ),
    )
    verified_backend = AuthBackend(
        name="verified",
        transport=HeaderTransport(header_name="X-Verified"),
        strategy=_StaticAuthResultStrategy(
            {"user": verified_user, "user_id": str(user_id), "source": "verified"}
        ),
    )

    deps = AuthDeps(
        backends=[inactive_backend, unverified_backend, verified_backend],
        get_session=lambda: None,
    )
    dep = deps.require_auth(verified=True)
    request = _make_request(
        "GET",
        "/me",
        headers={
            "X-Inactive": "one",
            "X-Unverified": "two",
            "X-Verified": "three",
        },
    )

    auth_result = await dep(request=request, session=object())

    assert auth_result["source"] == "verified"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_deps_require_auth_optional_and_activity_tracking(monkeypatch: pytest.MonkeyPatch):
    user_id = uuid4()
    backend = AuthBackend(
        name="test",
        transport=HeaderTransport(header_name="X-Test-User"),
        strategy=_StaticAuthResultStrategy(None),
    )
    deps = AuthDeps(backends=[backend], get_session=lambda: None)

    optional_dep = deps.require_auth(optional=True)
    request = _make_request("GET", "/me", headers={"X-Test-User": str(user_id)})
    assert await optional_dep(request=request, session=object()) is None

    tracked_user = SimpleNamespace(id=user_id, email_verified=True)
    tracked_user.can_authenticate = lambda: True
    tracking_backend = AuthBackend(
        name="tracking",
        transport=HeaderTransport(header_name="X-Tracking-User"),
        strategy=_StaticAuthResultStrategy(
            {"user": tracked_user, "user_id": str(user_id), "source": "tracking"}
        ),
    )
    tracked: list[str] = []

    def fake_track_activity_detached(tracked_user_id: str) -> None:
        tracked.append(tracked_user_id)

    activity_tracker = SimpleNamespace(
        track_activity_detached=fake_track_activity_detached,
    )
    deps = AuthDeps(
        backends=[tracking_backend],
        activity_tracker=activity_tracker,
        get_session=lambda: None,
    )

    dep = deps.require_auth()
    request = _make_request(
        "GET",
        "/me",
        headers={"X-Tracking-User": str(user_id)},
    )

    auth_result = await dep(request=request, session=object())

    assert auth_result["source"] == "tracking"
    assert tracked == [str(user_id)]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_deps_permission_helpers_handle_missing_ids_and_service_tokens():
    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(backends=[], permission_service=permission_service)

    with pytest.raises(HTTPException) as missing_exc:
        await deps._auth_result_has_permission(
            auth_result={"source": "jwt"},
            session=object(),
            permission="user:read",
            entity_id=None,
            resource_context=None,
            env_context=None,
        )
    assert missing_exc.value.status_code == 401
    assert missing_exc.value.detail == "User ID not found in auth result"

    with pytest.raises(HTTPException) as invalid_exc:
        await deps._auth_result_has_permission(
            auth_result={"source": "jwt", "user_id": "not-a-uuid"},
            session=object(),
            permission="user:read",
            entity_id=None,
            resource_context=None,
            env_context=None,
        )
    assert invalid_exc.value.status_code == 401
    assert invalid_exc.value.detail == "Invalid user ID in auth result"

    allowed = await deps._auth_result_has_permission(
        auth_result={
            "source": "service_token",
            "metadata": {"permissions": ["*"]},
        },
        session=object(),
        permission="report:generate",
        entity_id=None,
        resource_context=None,
        env_context=None,
    )
    assert allowed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_deps_require_permission_merges_abac_context_and_require_all():
    user_id = uuid4()
    backend = AuthBackend(
        name="test",
        transport=HeaderTransport(header_name="X-Test-User"),
        strategy=_StaticAuthResultStrategy(
            {"user": None, "user_id": str(user_id), "source": "jwt"}
        ),
    )
    permission_service = _PermissionServiceStub(
        result=lambda permission: permission != "entity:delete",
        enable_abac=True,
    )
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        get_session=lambda: None,
    )

    async def resource_context_provider(request, session, auth_result):
        assert auth_result["user_id"] == str(user_id)
        return {"owner_id": "abc123"}

    dep = deps.require_permission(
        "entity:update",
        "entity:delete",
        require_all=True,
        allow_entity_context_header=True,
        resource_context_provider=resource_context_provider,
    )
    request = _make_request(
        "PATCH",
        "/entities",
        headers={
            "X-Test-User": str(user_id),
            "X-Entity-Context": str(uuid4()),
            "User-Agent": "pytest",
        },
    )
    request.state.resource_context = {"entity_type": "team"}

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=request, session=object())

    assert exc_info.value.status_code == 403
    assert len(permission_service.calls) == 2
    assert permission_service.calls[0]["resource_context"] == {
        "entity_type": "team",
        "owner_id": "abc123",
    }
    assert permission_service.calls[0]["env_context"]["method"] == "PATCH"
    assert permission_service.calls[0]["env_context"]["user_agent"] == "pytest"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_deps_require_permission_validates_services_and_session():
    user_id = uuid4()
    backend = AuthBackend(
        name="test",
        transport=HeaderTransport(header_name="X-Test-User"),
        strategy=_StaticAuthResultStrategy(
            {"user": None, "user_id": str(user_id), "source": "jwt"}
        ),
    )
    request = _make_request("GET", "/users", headers={"X-Test-User": str(user_id)})

    deps = AuthDeps(backends=[backend], get_session=lambda: None)
    with pytest.raises(HTTPException) as permission_exc:
        await deps.require_permission("user:read")(request=request, session=object())
    assert permission_exc.value.status_code == 500
    assert permission_exc.value.detail == "Permission service not configured"

    deps = AuthDeps(
        backends=[backend],
        permission_service=_PermissionServiceStub(result=True),
        get_session=lambda: None,
    )
    with pytest.raises(HTTPException) as session_exc:
        await deps.require_permission("user:read")(request=request, session=None)
    assert session_exc.value.status_code == 500
    assert session_exc.value.detail == "Database session not configured for auth dependencies"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_deps_require_entity_permission_require_source_and_superuser():
    user_id = uuid4()
    entity_id = uuid4()
    backend = AuthBackend(
        name="test",
        transport=HeaderTransport(header_name="X-Test-User"),
        strategy=_StaticAuthResultStrategy(
            {"user": None, "user_id": str(user_id), "source": "jwt"}
        ),
    )
    permission_service = _PermissionServiceStub(result=True)
    deps = AuthDeps(
        backends=[backend],
        permission_service=permission_service,
        get_session=lambda: None,
    )

    request = _make_request("GET", "/entities", headers={"X-Test-User": str(user_id)})
    with pytest.raises(HTTPException) as missing_entity_exc:
        await deps.require_entity_permission("entity:read")(request=request, session=object())
    assert missing_entity_exc.value.status_code == 400
    assert missing_entity_exc.value.detail == "Entity ID is required"

    header_request = _make_request(
        "GET",
        "/entities",
        headers={
            "X-Test-User": str(user_id),
            "X-Entity-Context": str(entity_id),
        },
    )
    resolved = await deps.require_entity_permission("entity:read")(
        request=header_request,
        session=object(),
    )
    assert resolved["source"] == "jwt"
    assert permission_service.calls[-1]["entity_id"] == UUID(str(entity_id))

    with pytest.raises(HTTPException) as source_exc:
        await deps.require_source("api_key")(request=header_request, session=object())
    assert source_exc.value.status_code == 401
    assert source_exc.value.detail == "Authentication via api_key required"

    with pytest.raises(HTTPException) as superuser_exc:
        await deps.require_superuser()(request=header_request, session=object())
    assert superuser_exc.value.status_code == 403
    assert superuser_exc.value.detail == "Superuser privileges required"


@pytest.mark.unit
def test_auth_deps_tree_permission_validation_and_dynamic_signature():
    backend = AuthBackend(
        name="test",
        transport=HeaderTransport(header_name="X-Test-User"),
        strategy=_StaticAuthResultStrategy(None),
    )
    deps = AuthDeps(backends=[backend], get_session=lambda: None)

    with pytest.raises(ValueError, match="source must be one of: path, query, header, body"):
        deps.require_tree_permission("entity:create", "entity_id", source="cookie")

    signature = deps._get_dependency_signature()
    assert list(signature.parameters) == ["request", "session", "test_credentials"]
    assert signature.parameters["session"].default.dependency == deps.get_session

    dep = deps.require_source("jwt")
    assert list(inspect.signature(dep).parameters) == [
        "request",
        "session",
        "test_credentials",
    ]
