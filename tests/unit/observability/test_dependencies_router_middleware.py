from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Counter
from starlette.requests import Request
from starlette.responses import Response

from outlabs_auth.observability.config import ObservabilityConfig
from outlabs_auth.observability.dependencies import (
    ObservabilityContext,
    ObservabilityDeps,
    current_request_var,
    get_observability_dependency,
    get_observability_with_auth,
)
from outlabs_auth.observability.middleware import CorrelationIDMiddleware
from outlabs_auth.observability.router import create_metrics_router
from outlabs_auth.observability.service import ObservabilityService


def _make_request(
    method: str = "GET",
    path: str = "/users",
    *,
    headers: dict[str, str] | None = None,
) -> Request:
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in (headers or {}).items()
        ],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


def test_observability_context_forwards_logs_and_events():
    logger = SimpleNamespace(info=MagicMock())
    observability = SimpleNamespace(
        get_correlation_id=MagicMock(return_value="corr-123"),
        log_500_error=MagicMock(),
        log_router_error=MagicMock(),
        log_error=MagicMock(),
        log_exception=MagicMock(),
        logger=logger,
    )
    request = _make_request("POST", "/users")

    context = ObservabilityContext(
        request=request,
        observability=observability,
        user_id="user-123",
    )

    assert current_request_var.get() is request

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        context.log_500_error(exc, include_stack_trace=False, tenant="acme")
        context.log_router_error("users", "create_user", exc, tenant="acme")
        context.log_exception(exc, "lookup_failed", tenant="acme")

    context.log_error("user.sync_failed", "not good", tenant="acme")
    context.log_event("custom_event", tenant="acme")
    context.log_event("custom_event_override", user_id="override", tenant="acme")

    observability.log_500_error.assert_called_once_with(
        endpoint="/users",
        error_class="RuntimeError",
        error_message="boom",
        method="POST",
        user_id="user-123",
        request_id="corr-123",
        stack_trace=None,
        tenant="acme",
    )
    observability.log_router_error.assert_called_once()
    assert observability.log_router_error.call_args.kwargs["router"] == "users"
    assert observability.log_router_error.call_args.kwargs["operation"] == "create_user"
    assert observability.log_router_error.call_args.kwargs["endpoint"] == "/users"
    assert observability.log_router_error.call_args.kwargs["user_id"] == "user-123"
    assert "RuntimeError" in observability.log_router_error.call_args.kwargs["stack_trace"]

    observability.log_error.assert_called_once_with(
        event="user.sync_failed",
        error_type="CustomError",
        error_message="not good",
        location="/users",
        endpoint="/users",
        user_id="user-123",
        tenant="acme",
    )
    observability.log_exception.assert_called_once_with(
        exception=observability.log_exception.call_args.kwargs["exception"],
        context="/users.lookup_failed",
        user_id="user-123",
        endpoint="/users",
        method="POST",
        tenant="acme",
    )
    assert str(observability.log_exception.call_args.kwargs["exception"]) == "boom"

    assert logger.info.call_args_list[0].args == ("custom_event",)
    assert logger.info.call_args_list[0].kwargs == {
        "endpoint": "/users",
        "method": "POST",
        "request_id": "corr-123",
        "user_id": "user-123",
        "tenant": "acme",
    }
    assert logger.info.call_args_list[1].args == ("custom_event_override",)
    assert logger.info.call_args_list[1].kwargs == {
        "endpoint": "/users",
        "method": "POST",
        "request_id": "corr-123",
        "user_id": "override",
        "tenant": "acme",
    }


def test_observability_context_noops_without_service_or_logger():
    request = _make_request()
    context = ObservabilityContext(request=request, observability=None)

    context.log_500_error(RuntimeError("boom"))
    context.log_router_error("users", "list_users", RuntimeError("boom"))
    context.log_error("custom", "boom")
    context.log_exception(RuntimeError("boom"), "during_lookup")
    context.log_event("custom_event")

    context_with_disabled_logger = ObservabilityContext(
        request=request,
        observability=SimpleNamespace(get_correlation_id=lambda: "corr-123", logger=None),
    )
    context_with_disabled_logger.log_event("custom_event")


@pytest.mark.asyncio
async def test_observability_dependencies_extract_user_context_and_validate_auth_deps():
    observability = SimpleNamespace(get_correlation_id=MagicMock(return_value="corr-123"))
    request = _make_request("GET", "/audit")
    request.state.user_id = "state-user"

    dependency = get_observability_dependency(observability)
    context = await dependency(request)

    assert context.user_id == "state-user"
    assert context.correlation_id == "corr-123"

    auth_wrapped = get_observability_with_auth(observability, auth_dependency=object())
    auth_context = await auth_wrapped(request, auth_result={"user_id": "auth-user"})
    assert auth_context.user_id == "auth-user"

    no_auth_context = await auth_wrapped(request, auth_result="unexpected")
    assert no_auth_context.user_id is None

    auth_deps = SimpleNamespace(
        require_auth=MagicMock(return_value=object()),
        require_permission=MagicMock(return_value=object()),
    )
    factory = ObservabilityDeps(observability, auth_deps)

    context_dependency = factory.get_context()
    context_from_factory = await context_dependency(request)
    assert context_from_factory.user_id == "state-user"

    with_auth_dependency = factory.with_auth(optional=True)
    auth_deps.require_auth.assert_called_once_with(optional=True)
    with_auth_context = await with_auth_dependency(request, auth_result={"user_id": "factory-user"})
    assert with_auth_context.user_id == "factory-user"

    with_permission_dependency = factory.with_permission("user:read")
    auth_deps.require_permission.assert_called_once_with("user:read")
    with_permission_context = await with_permission_dependency(
        request,
        auth_result={"user_id": "permission-user"},
    )
    assert with_permission_context.user_id == "permission-user"

    with pytest.raises(ValueError, match="auth_deps is required"):
        ObservabilityDeps(observability).with_auth()

    with pytest.raises(ValueError, match="auth_deps is required"):
        ObservabilityDeps(observability).with_permission("user:read")


def _asgi_http_scope(headers: dict[str, str] | None = None) -> dict:
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/users",
        "raw_path": b"/users",
        "query_string": b"",
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in (headers or {}).items()
        ],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }


async def _noop_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def _response_header(messages: list[dict], name: str) -> str | None:
    start = next((m for m in messages if m["type"] == "http.response.start"), None)
    if start is None:
        return None
    wanted = name.lower().encode("utf-8")
    for key, value in start["headers"]:
        if key.lower() == wanted:
            return value.decode("utf-8")
    return None


@pytest.mark.asyncio
async def test_correlation_id_middleware_propagates_and_generates_ids(monkeypatch: pytest.MonkeyPatch):
    obs_service = SimpleNamespace(config=ObservabilityConfig(async_logging=False))
    header_name = obs_service.config.correlation_id_header

    observed_cids: list[str | None] = []

    async def inner_app(scope, receive, send):
        observed_cids.append(ObservabilityService.get_correlation_id())
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    middleware = CorrelationIDMiddleware(app=inner_app, obs_service=obs_service)

    messages: list[dict] = []

    async def send(message):
        messages.append(message)

    await middleware(_asgi_http_scope({header_name: "cid-existing"}), _noop_receive, send)
    assert observed_cids[-1] == "cid-existing"
    assert _response_header(messages, header_name) == "cid-existing"
    assert ObservabilityService.get_correlation_id() is None

    monkeypatch.setattr(
        "outlabs_auth.observability.middleware.uuid.uuid4",
        lambda: UUID("11111111-1111-1111-1111-111111111111"),
    )

    messages2: list[dict] = []

    async def send2(message):
        messages2.append(message)

    await middleware(_asgi_http_scope(), _noop_receive, send2)
    assert observed_cids[-1] == "11111111-1111-1111-1111-111111111111"
    assert (
        _response_header(messages2, header_name)
        == "11111111-1111-1111-1111-111111111111"
    )
    assert ObservabilityService.get_correlation_id() is None


@pytest.mark.asyncio
async def test_correlation_id_middleware_skips_generation_and_clears_on_errors():
    obs_service = SimpleNamespace(
        config=ObservabilityConfig(async_logging=False, generate_correlation_id=False)
    )

    async def failing_app(scope, receive, send):
        raise RuntimeError("boom")

    middleware = CorrelationIDMiddleware(app=failing_app, obs_service=obs_service)

    ObservabilityService.set_correlation_id("stale-value")

    async def send(message):
        pass

    with pytest.raises(RuntimeError, match="boom"):
        await middleware(_asgi_http_scope(), _noop_receive, send)

    assert ObservabilityService.get_correlation_id() is None


@pytest.mark.asyncio
async def test_correlation_id_middleware_passes_through_non_http_scope():
    obs_service = SimpleNamespace(config=ObservabilityConfig(async_logging=False))
    calls: list[tuple] = []

    async def inner_app(scope, receive, send):
        calls.append((scope, receive, send))

    middleware = CorrelationIDMiddleware(app=inner_app, obs_service=obs_service)

    lifespan_scope = {"type": "lifespan"}
    await middleware(lifespan_scope, _noop_receive, lambda _m: None)

    assert calls and calls[0][0] is lifespan_scope


def test_create_metrics_router_respects_enablement_and_serves_metrics():
    disabled_service = SimpleNamespace(
        config=ObservabilityConfig(enable_metrics=False, async_logging=False),
        metrics_registry=CollectorRegistry(),
    )
    disabled_router = create_metrics_router(disabled_service)
    assert disabled_router.routes == []

    registry = CollectorRegistry()
    Counter("outlabs_auth_test_metric", "test metric", registry=registry).inc()
    enabled_service = SimpleNamespace(
        config=ObservabilityConfig(
            enable_metrics=True,
            metrics_path="/internal/metrics",
            async_logging=False,
        ),
        metrics_registry=registry,
    )

    app = FastAPI()
    app.include_router(create_metrics_router(enabled_service, tags=["Ops"]))

    with TestClient(app) as client:
        response = client.get("/internal/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "outlabs_auth_test_metric_total" in response.text
    assert any(route.path == "/internal/metrics" for route in app.routes)
