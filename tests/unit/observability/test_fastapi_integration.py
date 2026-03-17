from fastapi import FastAPI, HTTPException

from outlabs_auth import SimpleRBAC
from outlabs_auth.core.exceptions import OutlabsAuthException
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.middleware import ResourceContextMiddleware
from outlabs_auth.observability import CorrelationIDMiddleware, ObservabilityConfig


def _build_auth(*, metrics_path: str = "/internal/auth/metrics") -> SimpleRBAC:
    return SimpleRBAC(
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        secret_key="test-secret-key",
        observability_config=ObservabilityConfig(
            enable_metrics=True,
            metrics_path=metrics_path,
            async_logging=False,
        ),
    )


def test_register_exception_handlers_auth_only_mode_is_scoped():
    app = FastAPI()

    register_exception_handlers(app, mode="auth_only")

    assert OutlabsAuthException in app.exception_handlers
    assert HTTPException not in app.exception_handlers
    assert Exception not in app.exception_handlers


def test_instrument_fastapi_safe_defaults_do_not_override_host_surfaces():
    app = FastAPI()
    auth = _build_auth()

    auth.instrument_fastapi(app)

    route_paths = {route.path for route in app.routes}
    middleware_classes = {middleware.cls for middleware in app.user_middleware}

    assert OutlabsAuthException in app.exception_handlers
    assert Exception not in app.exception_handlers
    assert "/internal/auth/metrics" not in route_paths
    assert CorrelationIDMiddleware not in middleware_classes
    assert ResourceContextMiddleware not in middleware_classes


def test_instrument_fastapi_standalone_mode_adds_explicit_integrations():
    app = FastAPI()
    auth = _build_auth(metrics_path="/standalone/auth/metrics")

    auth.instrument_fastapi(
        app,
        exception_handler_mode="global",
        include_metrics=True,
        include_correlation_id=True,
        include_resource_context=True,
    )

    route_paths = {route.path for route in app.routes}
    middleware_classes = {middleware.cls for middleware in app.user_middleware}

    assert Exception in app.exception_handlers
    assert "/standalone/auth/metrics" in route_paths
    assert CorrelationIDMiddleware in middleware_classes
    assert ResourceContextMiddleware in middleware_classes
