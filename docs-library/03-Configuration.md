# 03. Configuration

Constructor and environment knobs you need when embedding OutlabsAuth. Full field
list: `outlabs_auth/core/config.py` (`AuthConfig`).

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
)
```

| Setting | Guidance |
|---------|----------|
| `database_schema` | Keep auth tables in a dedicated schema (e.g. `outlabs_auth`) |
| `auto_migrate` | `False` in multi-worker runtime; migrate via CLI in prestart |
| `redis_url` | Enables counters, rate limits, and permission caching |
| Mount prefix | App-owned, e.g. `/iam` or `/v1` — keep consistent with OutlabsAuth UI `authApiPrefix` |

Prefer a **direct** Postgres URL over provider transaction-pooler (`-pooler`)
endpoints for auth-heavy traffic. Details: root README + [`docs/DEPLOYMENT_GUIDE.md`](../docs/DEPLOYMENT_GUIDE.md).

## Preset feature flags

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
| `enable_audit_log` | `False` | Audit logging |
| `enable_caching` | follows Redis | Permission cache (requires Redis) |
| `store_refresh_tokens` | `True` | DB-backed refresh revocation |
| `enable_token_blacklist` | `False` | Immediate access-token blacklist (Redis) |

Passwordless and messaging: [`docs/AUTH_EXTENSIONS.md`](../docs/AUTH_EXTENSIONS.md).

## CLI environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres URL for `outlabs-auth` CLI |
| `OUTLABS_AUTH_SCHEMA` | Schema for migrate / seed / doctor / bootstrap |
| `OUTLABS_AUTH_BOOTSTRAP_*` | Optional admin email/password for `outlabs-auth bootstrap` |

## Operator commands

```bash
outlabs-auth migrate          # apply packaged Alembic revisions
outlabs-auth seed-system      # system permissions / seed data
outlabs-auth bootstrap-admin  # create an initial admin
outlabs-auth doctor           # read-only preflight (safe on prod)
outlabs-auth bootstrap        # migrate → seed → optional admin (aborts on drift)
outlabs-auth tables           # list auth tables
outlabs-auth current          # current Alembic revision
```

`doctor` and `bootstrap` support `--format text|json`. Exit codes: `0` healthy,
`1` check/plan failure, `2` missing `DATABASE_URL`.

## Redis

Providing `redis_url` typically enables Redis features and caching unless you
explicitly set `redis_enabled=False` or `enable_caching=False`.

Without Redis, the library still runs; permission checks hit Postgres every time.
Use Redis in production when you care about API-key counters and hot-path authz
latency.

## Observability

Pass `observability_config=` (see `ObservabilityConfig` / presets) and call
`auth.instrument_fastapi(app)`. Guides: [97-Observability.md](./97-Observability.md).

## Related

- [01-Getting-Started.md](./01-Getting-Started.md)
- [02-Routers-and-Prefixes.md](./02-Routers-and-Prefixes.md)
- [`docs/AUTH_UI.md`](../docs/AUTH_UI.md)
