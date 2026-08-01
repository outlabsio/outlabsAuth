# Observability & Monitoring

> **Handbook** · Metrics and logs without taking over your FastAPI app.  
> Part of the [OutlabsAuth Handbook](./README.md). Catalogs:
> [Metrics](./98-Metrics-Reference.md), [Log events](./99-Log-Events-Reference.md).

OutlabsAuth emits **auth-domain** logs and Prometheus metrics. Your host usually
owns process logging, `/metrics`, and tracing.

| Mode | When | What the library adds by default |
|------|------|----------------------------------|
| **Embedded** (recommended) | Real host APIs | Auth exception handler + UnitOfWork / request-cache middleware |
| **Standalone** | Demos / auth-first apps | Opt in to metrics route, correlation ID, resource context, broader exception handlers |

---

## Embedded (default)

Rules of thumb:

- Keep the host logger, Prometheus registry, `/metrics`, and generic exception handlers
- Pass the host registry into OutlabsAuth so auth metrics share one scrape
- Let auth emit only auth-domain signals

```python
import logging
from prometheus_client import REGISTRY
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.observability import ObservabilityConfig

auth = EnterpriseRBAC(
    database_url=...,
    secret_key=...,
    observability_config=ObservabilityConfig(enable_metrics=True),
    observability_logger=logging.getLogger("host_api.auth"),
    observability_metrics_registry=REGISTRY,
)
auth.instrument_fastapi(app)  # auth_only exceptions + UoW + request cache
```

`instrument_fastapi(app)` **always** installs:

- `OutlabsAuthException` handler (`exception_handler_mode="auth_only"`)
- `UnitOfWorkMiddleware` (commit before response — read-your-writes)
- `RequestCacheMiddleware` (request-scoped permission memos)

It does **not** (unless you opt in): mount `/metrics`, correlation-ID middleware,
resource-context middleware, or global HTTP/validation/Exception handlers.

```python
auth.instrument_fastapi(
    app,
    exception_handler_mode="auth_only",
    include_metrics=False,
    include_correlation_id=False,
    include_resource_context=False,
)
```

Shared SQLAlchemy engine: auth will not instrument that engine for DB metrics
unless `observability_instrument_external_engine=True`.

---

## Standalone / demos

```python
auth = SimpleRBAC(
    database_url=...,
    secret_key=...,
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

Use `exception_handler_mode="global"` only when auth should own the full
exception surface for that app.

---

## Logging

Auth does **not** reconfigure global logging.

- Pass `observability_logger=...` to emit through your logger, or
- Fall back to `ObservabilityConfig.logger_name` (namespaced)

Presets: `ObservabilityPresets.development()` / `.staging()` / `.production()` /
`.disabled()`.

Event catalog: [99 — Log Events](./99-Log-Events-Reference.md).

---

## Metrics

With `enable_metrics=True`, auth registers namespaced series such as
`outlabs_auth_login_attempts_total`, `outlabs_auth_permission_checks_total`,
entity ops, and DB query duration histograms.

Inject `observability_metrics_registry=REGISTRY` in embedded hosts so one
`/metrics` scrape includes host + auth. Full list:
[98 — Metrics](./98-Metrics-Reference.md).

Portable Grafana/Prometheus stack: [`observability/`](../observability/).

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No auth metrics on host `/metrics` | `enable_metrics=True`; same registry for scrape and `observability_metrics_registry` |
| Middleware missing | Call `instrument_fastapi` at import time (before the app starts serving) |
| Host handlers overwritten | Stay on `exception_handler_mode="auth_only"` or `register_outlabs_exception_handler(app)` |

---

## Related

- [Metrics Reference](./98-Metrics-Reference.md)
- [Log Events Reference](./99-Log-Events-Reference.md)
- [Configuration](./03-Configuration.md)
- [ABAC](./26-ABAC.md) — `include_resource_context` when using request-state merge
- [`observability/`](../observability/)
