# Configuration

Knobs you set when embedding OutlabsAuth: database, secrets, Redis, cache, and
feature flags. The full field list lives in `outlabs_auth/core/config.py`
(`AuthConfig`).

New install? Start with [Getting Started](./01-Getting-Started.md), then come
back here for production defaults.

---

## Required

| Setting | How | Notes |
|---------|-----|-------|
| Database URL | `database_url=` or `DATABASE_URL` for CLI | Must be `postgresql+asyncpg://...` |
| JWT secret | `secret_key=` or `SECRET_KEY` | ≥ 32 characters for HS256 |

## Recommended production baseline

```python
from outlabs_auth import EnterpriseRBAC  # or SimpleRBAC

auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://user:password@db-host/app?ssl=require",
    database_schema="outlabs_auth",
    secret_key="...",  # long random secret
    auto_migrate=False,
    redis_url="redis://cache-host:6379/0",
    background_job_mode="disabled",
)
```

| Setting | Guidance |
|---------|----------|
| `database_schema` | Keep auth tables in a dedicated schema (e.g. `outlabs_auth`) |
| `auto_migrate` | `False` in multi-worker runtime; migrate via CLI in prestart |
| `redis_url` | Enables counters, rate limits, and shared permission caching |
| `cache_backend` | `redis` (multi-instance), `memory` (single-process, no Redis), or `none` |
| `background_job_mode` | `disabled` in production APIs; one external worker runs maintenance |
| Mount prefix | App-owned, e.g. `/iam` or `/v1` — keep consistent with OutlabsAuth UI `authApiPrefix` |

### Permission cache backends

| Backend | When to use | Invalidation |
|---------|-------------|--------------|
| `redis` | Multi-instance / multi-worker production | Instant via Redis pub/sub version bumps |
| `memory` | Single-process hosts that want cache without Redis | Instant in-process; TTL-bounded across processes |
| `none` | No cross-request permission cache | N/A |

```python
# Single-instance, no Redis
auth = SimpleRBAC(
    database_url=...,
    secret_key=...,
    cache_backend="memory",
)

# Multi-instance (default when redis_url is set)
auth = EnterpriseRBAC(
    database_url=...,
    secret_key=...,
    redis_url="redis://cache-host:6379/0",
    redis_key_prefix="outlabs-auth:prod:myapp",
)
```

Do **not** use `memory` when multiple workers or instances must see each other's
permission invalidations immediately — use `redis` instead.

Prefer a **direct** Postgres URL over provider transaction-pooler (`-pooler`)
endpoints for auth-heavy traffic. Details: root README +
[`docs/DEPLOYMENT_GUIDE.md`](../docs/DEPLOYMENT_GUIDE.md).

## Feature flags

Set on the preset constructor (or underlying `AuthConfig`):

| Flag | SimpleRBAC | EnterpriseRBAC |
|------|------------|----------------|
| `enable_entity_hierarchy` | forced off | forced on |
| `enable_context_aware_roles` | forced off | optional (default off) |
| `enable_abac` | forced off | optional (default off) |

Other common toggles:

| Flag | Default | Purpose |
|------|---------|---------|
| `enable_invitations` | `True` | Invite-by-email flow |
| `enable_magic_links` | `False` | Passwordless magic links |
| `enable_access_codes` | `False` | Passwordless access codes |
| `enable_audit_log` | `False` | Legacy audit feature-status flag (does **not** gate session/audit HTTP routes) |
| `enable_caching` | follows Redis | Permission cache |
| `store_refresh_tokens` | `True` | DB-backed refresh revocation (powers session inventory) |
| `refresh_token_absolute_lifetime_days` | `90` | Maximum age of one refresh-token family |
| `enable_token_blacklist` | `False` | Immediate access-token blacklist (Redis) |
| `login_ip_rate_limit_max` | `20` | Password-login attempts per client IP/window |
| `login_ip_rate_limit_window_seconds` | `300` | Password-login IP window in seconds |
| `login_ip_rate_limit_failure_mode` | `fail_closed` | Redis outage behavior (`local_fallback` is opt-in) |

`background_job_mode` accepts `"disabled"` (default) or `"embedded"`.
Embedded mode is only a single-process development convenience. TaskQ, Celery,
Cron, and host timers are integrations that invoke
`auth.run_maintenance_once()` while the library stays disabled. See
[Background Maintenance](./09-Background-Maintenance.md).

Passwordless and messaging walkthrough:
[Passwordless & Messaging](./06-Passwordless-and-Messaging.md).  
ABAC: [26 — ABAC](./26-ABAC.md).  
Deep maintainer notes: [`docs/AUTH_EXTENSIONS.md`](../docs/AUTH_EXTENSIONS.md).

## CLI environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres URL for `outlabs-auth` CLI |
| `OUTLABS_AUTH_SCHEMA` | Schema for migrate / seed / doctor / bootstrap |
| `OUTLABS_AUTH_BOOTSTRAP_*` | Optional admin email/password for `outlabs-auth bootstrap` |
| `OUTLABS_AUTH_CONFIG` | Optional path to the non-secret remote-context JSON file |
| `OUTLABS_AUTH_CREDENTIALS` | Optional path to the target-bound bearer-session store (mode `0600`) |
| `OUTLABS_AUTH_PROFILE` | Remote context selected for this invocation |
| `OUTLABS_AUTH_BASE_URL` | One-off remote base URL override |
| `OUTLABS_AUTH_API_PREFIX` | One-off remote API-prefix override |
| `OUTLABS_AUTH_CREDENTIAL_TYPE` | One-off remote transport override (`bearer` or `api-key`) |
| `OUTLABS_AUTH_CREDENTIAL_ENV` | One-off name of the environment variable holding the credential |
| `OUTLABS_AUTH_TOKEN` | Default remote bearer credential; never stored in context config |
| `OUTLABS_AUTH_API_KEY` | Default remote `X-API-Key` credential for scoped automation |
| `OUTLABS_AUTH_OUTPUT` | Global output contract (`text` or versioned `json`) |
| `OUTLABS_AUTH_NON_INTERACTIVE` | Disable prompts; confirmation then requires command-specific `--yes` |
| `OUTLABS_AUTH_TIMEOUT` | Remote HTTP timeout in seconds |
| `OUTLABS_AUTH_DEBUG` | Include tracebacks for unexpected CLI failures |

## Operator commands

```bash
outlabs-auth migrate          # apply packaged Alembic revisions
outlabs-auth seed-system      # system permissions / seed data
outlabs-auth bootstrap-admin  # create an initial admin
outlabs-auth doctor           # read-only preflight (safe on prod)
outlabs-auth bootstrap        # migrate → seed → optional admin (aborts on drift)
outlabs-auth run-maintenance  # one typed external maintenance cycle
outlabs-auth tables           # list auth tables
outlabs-auth current          # current Alembic revision
```

`doctor` and `bootstrap` support `--format text|json`. Exit codes: `0` healthy,
`1` check/plan failure, `2` missing `DATABASE_URL`.

The same local commands are grouped under `outlabs-auth db`; diagnostics and
maintenance are grouped under `outlabs-auth ops`. Existing top-level command
names remain supported.

Remote API setup and inspection:

```bash
outlabs-auth context add production --base-url https://api.example.com --api-prefix /iam
outlabs-auth capabilities
outlabs-auth auth login --email admin@example.com
outlabs-auth auth status
outlabs-auth whoami
outlabs-auth users list --all
outlabs-auth permissions explain reports:read --user admin@example.com
```

For scoped agent automation, add the context with `--credential-type api-key`
and provide `OUTLABS_AUTH_API_KEY` instead of a human bearer token.

Use global `--output json --non-interactive` for coding agents and unattended
automation. Unlike legacy command-specific `--format json`, the global form
uses the versioned envelope documented in [`docs/CLI_DESIGN.md`](../docs/CLI_DESIGN.md).
Agents can introspect exact flags and types with
`outlabs-auth --output json commands PATH... --shallow`; new endpoints remain
available through the guarded `api request` escape hatch.
See the [coding-agent operating guide](../docs/CLI_AGENT_GUIDE.md) for
least-privilege integration keys, retry categories, and recovery behavior.

For repeatable resource changes, use the target-bound declarative workflow:

```bash
outlabs-auth --output json plan state.json --out state.plan.json
outlabs-auth --output json --non-interactive apply state.plan.json --yes
```

Manifest shape, ordering, drift behavior, and destructive gates are documented
in [`docs/CLI_MANIFEST.md`](../docs/CLI_MANIFEST.md).

## Redis

Providing `redis_url` typically enables Redis features, `cache_backend='redis'`,
and caching unless you explicitly set `redis_enabled=False` or
`enable_caching=False`.

Without Redis you can still enable permission caching with
`cache_backend='memory'` (single-instance). Otherwise permission checks hit
Postgres every time. Use Redis in production when you need shared API-key
counters and multi-instance cache invalidation.

## Observability

Pass `observability_config=` (see `ObservabilityConfig` / presets) and call
`auth.instrument_fastapi(app)`. Guide: [Observability](./97-Observability.md).

## Related

- [Getting Started](./01-Getting-Started.md)
- [Deployment](./08-Deployment.md)
- [Background Maintenance](./09-Background-Maintenance.md)
- [Routers & Prefixes](./02-Routers-and-Prefixes.md)
- [OutlabsAuth UI](../docs/AUTH_UI.md)
