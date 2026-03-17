# 97. Observability & Monitoring

> **Quick Reference**: How to use OutlabsAuth observability without taking over the host FastAPI application's logging, metrics, middleware, or generic exception handling.

## Overview

OutlabsAuth emits auth-domain logs and Prometheus metrics. The library is
designed for two integration modes:

- **Embedded mode**: default for real host APIs. The host app owns logging,
  `/metrics`, tracing, request middleware, and broad exception handling.
- **Standalone mode**: optional for demos and isolated auth-first apps. The
  library can mount a metrics endpoint and add broader middleware/handlers when
  you opt in explicitly.

## Embedded Mode

Use this mode when OutlabsAuth is installed inside an existing API such as
`outlabsAPI` or `DiverseAPI-postgres`.

### Rules

- Keep the host application's logger configuration.
- Keep the host application's Prometheus registry and `/metrics` route.
- Keep the host application's tracing and correlation middleware.
- Keep the host application's generic `HTTPException`, validation, and catch-all
  exception handlers.
- Let OutlabsAuth emit only auth-domain logs, metrics, and auth-specific
  exceptions.

### Host-Owned Metrics Endpoint

If the host app already exposes `/metrics`, keep using it. Pass the host
registry into OutlabsAuth and the auth metrics will appear in the same scrape.

```python
import logging

from fastapi import FastAPI
from prometheus_client import REGISTRY

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_outlabs_exception_handler
from outlabs_auth.observability import ObservabilityConfig

app = FastAPI()
logger = logging.getLogger("host_api.auth")

auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/mydb",
    secret_key="your-secret-key",
    observability_config=ObservabilityConfig(
        enable_metrics=True,
        metrics_path="/internal/auth/metrics",
    ),
    observability_logger=logger,
    observability_metrics_registry=REGISTRY,
)

register_outlabs_exception_handler(app)
```

### FastAPI Helper Defaults

`auth.instrument_fastapi(app)` is safe for embedded apps by default. It only:

- registers the `OutlabsAuthException` handler

It does **not**:

- mount a metrics route
- add correlation-ID middleware
- add resource-context middleware
- register global `HTTPException`, validation, or generic `Exception` handlers

This is equivalent to:

```python
auth.instrument_fastapi(
    app,
    exception_handler_mode="auth_only",
    include_metrics=False,
    include_correlation_id=False,
    include_resource_context=False,
)
```

### Shared vs External SQLAlchemy Engines

If the host passes a shared SQLAlchemy engine into OutlabsAuth, auth will not
instrument that engine for DB-query observability unless you opt in:

```python
auth = EnterpriseRBAC(
    engine=shared_engine,
    secret_key="your-secret-key",
    observability_config=ObservabilityConfig(enable_metrics=True),
    observability_instrument_external_engine=True,
)
```

Leave `observability_instrument_external_engine=False` when the host owns DB
instrumentation for a shared engine.

## Standalone Mode

Use this for isolated demos or library-owned example apps where OutlabsAuth is
expected to provide the main auth observability surfaces itself.

```python
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.observability import ObservabilityConfig

app = FastAPI()

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/mydb",
    secret_key="your-secret-key",
    observability_config=ObservabilityConfig(
        enable_metrics=True,
        metrics_path="/metrics",
    ),
)

auth.instrument_fastapi(
    app,
    exception_handler_mode="global",
    include_metrics=True,
    include_correlation_id=True,
    include_resource_context=True,
)
```

That standalone configuration will:

- add the auth metrics router
- add correlation ID middleware
- add resource context middleware
- install the broader validation, `HTTPException`, and catch-all handlers

## Logging Behavior

OutlabsAuth no longer configures global logging for the whole process.

- If you pass `observability_logger=...`, auth emits through that logger.
- If you do not pass one, auth uses a namespaced fallback logger defined by
  `ObservabilityConfig.logger_name`.
- Injecting a host logger does not reconfigure its handlers or level.

```python
import logging

from outlabs_auth import SimpleRBAC
from outlabs_auth.observability import ObservabilityConfig

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/mydb",
    secret_key="your-secret-key",
    observability_config=ObservabilityConfig(
        enable_metrics=True,
        logger_name="outlabs_auth",
    ),
    observability_logger=logging.getLogger("host_api.auth"),
)
```

## Metrics Behavior

When metrics are enabled, OutlabsAuth records namespaced metrics such as:

- `outlabs_auth_login_attempts_total`
- `outlabs_auth_permission_checks_total`
- `outlabs_auth_entity_operations_total`
- `outlabs_auth_db_query_duration_seconds`

If you inject `observability_metrics_registry`, those metrics are registered in
that collector registry. This is the recommended approach for embedded apps.

If you do not inject a registry, the default Prometheus registry is used.

## Host Integration Example

For a host app that already exposes `/metrics`:

```python
from prometheus_client import REGISTRY

auth = EnterpriseRBAC(
    database_url=settings.AUTH_DATABASE_URL,
    secret_key=settings.AUTH_SECRET_KEY,
    observability_config=ObservabilityConfig(enable_metrics=True),
    observability_metrics_registry=REGISTRY,
)

# Keep the host app's existing /metrics endpoint.
```

Prometheus still scrapes one endpoint, but the response now includes both host
metrics and OutlabsAuth metrics from the same process.

## Troubleshooting

### No auth metrics on the host `/metrics` endpoint

Check:

1. `ObservabilityConfig(enable_metrics=True)` is set.
2. The host app is exposing `generate_latest()` from the same process.
3. If you inject a custom registry, the host `/metrics` route is rendering that
   same registry.

### `instrument_fastapi()` did not add middleware

`instrument_fastapi()` must run before the FastAPI app starts serving. If you
call it after startup, auth warns and skips middleware registration.

### Host exception handlers changed unexpectedly

Use embedded defaults or register only the auth-specific handler:

```python
from outlabs_auth.fastapi import register_outlabs_exception_handler

register_outlabs_exception_handler(app)
```

Avoid `exception_handler_mode="global"` unless the auth library should own the
full exception surface for that app.

## Related Docs

- [README.md](../README.md) - installation and integration overview
- [98-Metrics-Reference.md](98-Metrics-Reference.md) - metrics catalog
- [99-Log-Events-Reference.md](99-Log-Events-Reference.md) - event catalog
- [grafana-dashboards/README.md](../grafana-dashboards/README.md) - Grafana setup
