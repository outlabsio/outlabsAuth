# 02. Routers and Prefixes

OutlabsAuth ships **router factories** (`get_*_router`). You choose which ones to
mount and under which URL prefix. Nothing is mounted automatically.

## Convention

Pick a **base prefix** for the auth surface and keep it consistent:

| Context | Common base | Auth login path | UI `authApiPrefix` |
|---------|-------------|-----------------|--------------------|
| Root README quickstart | `/auth` | `/auth/login` | `""` or mount under `/auth` only for auth |
| Examples (`simple_rbac`, `enterprise_rbac`) | `/v1` | `/v1/auth/login` | `/v1` |
| Production (README guidance) | `/iam` | `/iam/auth/login` | `/iam` |

[OutlabsAuth UI](https://github.com/outlabsio/OutlabsAuthUI) joins
`apiBaseUrl` + `authApiPrefix` + resource paths. With `authApiPrefix: "/v1"` it
calls `/v1/auth/config`, `/v1/users`, `/v1/roles`, and so on.

**Rule:** if you mount `get_auth_router(..., prefix="/v1/auth")`, set the UI’s
`authApiPrefix` to `/v1` (the parent of `/auth`), not `/v1/auth`.

## Factory Catalog

Imported from `outlabs_auth.routers` unless noted.

| Factory | Typical prefix | Role |
|---------|----------------|------|
| `get_auth_router` | `/v1/auth` | Login, register, refresh, logout, password reset, invites, magic link / access code (when enabled), **`GET /config`** for admin UIs |
| `get_users_router` | `/v1/users` | Admin user management |
| `get_self_service_users_router` | host-chosen | Authenticated self-service user profile routes |
| `get_session_router` | `/v1/auth` (minimal) | Login / refresh / logout only — **not** session inventory |
| `get_roles_router` | `/v1/roles` | Role CRUD and permission assignment |
| `get_permissions_router` | `/v1/permissions` | Permission catalog |
| `get_api_keys_router` | `/v1/api-keys` | Personal / self-service API keys |
| `get_api_key_admin_router` | `/v1/admin/entities` | Enterprise admin API-key / entity workspace helpers |
| `get_integration_principals_router` | `/v1/admin` | Integration principals for system keys |
| `get_entities_router` | `/v1/entities` | Entity hierarchy (Enterprise) |
| `get_memberships_router` | `/v1/memberships` | User–entity memberships (Enterprise) |
| `get_config_router` | `/v1/config` | Mutable entity-type vocabulary (`/entity-types`) |
| `get_audit_router` | `/v1/audit-events` | Cross-user audit event search |

**Sessions and social accounts** live on `get_users_router` (`/me/sessions`,
`/me/social-accounts`, admin `/{user_id}/sessions`, …) — see
[05-Sessions-and-Audit.md](./05-Sessions-and-Audit.md) and
[04-OAuth-and-Social-Login.md](./04-OAuth-and-Social-Login.md).

OAuth factories live on the oauth modules (not always re-exported from
`outlabs_auth.routers`):

| Factory | Module | Role |
|---------|--------|------|
| `get_oauth_router` | `outlabs_auth.routers.oauth` | Social login callback paths |
| `get_oauth_associate_router` | `outlabs_auth.routers.oauth_associate` | Link provider to existing account |

Host examples may also mount app-owned routers (e.g. team directory) next to these.

## Minimal vs Full Mount Sets

### Minimum (auth only)

Enough for login tokens; not enough for OutlabsAuth UI admin screens:

```python
from outlabs_auth.routers import get_auth_router

app.include_router(get_auth_router(auth, prefix="/v1/auth"))
```

### SimpleRBAC + admin UI–friendly

Matches `examples/simple_rbac` closely:

```python
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_integration_principals_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)

app.include_router(get_auth_router(auth, prefix="/v1/auth"))
app.include_router(get_users_router(auth, prefix="/v1/users"))
app.include_router(get_roles_router(auth, prefix="/v1/roles"))
app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
app.include_router(get_api_keys_router(auth, prefix="/v1/api-keys"))
app.include_router(get_integration_principals_router(auth, prefix="/v1/admin"))
```

### EnterpriseRBAC + admin UI–friendly

Matches `examples/enterprise_rbac` closely:

```python
from outlabs_auth.routers import (
    get_api_key_admin_router,
    get_api_keys_router,
    get_audit_router,
    get_auth_router,
    get_config_router,
    get_entities_router,
    get_integration_principals_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)

app.include_router(get_auth_router(auth, prefix="/v1/auth"))
app.include_router(get_users_router(auth, prefix="/v1/users"))
app.include_router(get_audit_router(auth, prefix="/v1/audit-events"))
app.include_router(get_api_keys_router(auth, prefix="/v1/api-keys"))
app.include_router(get_api_key_admin_router(auth, prefix="/v1/admin/entities"))
app.include_router(get_integration_principals_router(auth, prefix="/v1/admin"))
app.include_router(get_roles_router(auth, prefix="/v1/roles"))
app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
app.include_router(get_entities_router(auth, prefix="/v1/entities"))
app.include_router(get_memberships_router(auth, prefix="/v1/memberships"))
app.include_router(get_config_router(auth, prefix="/v1/config"))
```

## Config Endpoints (Easy to Confuse)

| Endpoint | Router | Purpose |
|----------|--------|---------|
| `GET {base}/auth/config` | `get_auth_router` | Preset, feature flags, auth methods — **required for OutlabsAuth UI** |
| `GET/PUT {base}/config/entity-types` | `get_config_router` | Mutable entity-type vocabulary (Enterprise settings) |

## Mount Timing

Router factories resolve `auth.deps` at call time. Either:

1. Call `auth.prime_fastapi_routing()` before `include_router(...)` at import time, or
2. Mount inside `lifespan` after `await auth.initialize()` (see `examples/simple_rbac/main.py`)

Also call `auth.instrument_fastapi(app)` so UnitOfWork middleware commits correctly.

## Source of Truth

- Factory exports: `outlabs_auth/routers/__init__.py`
- Runnable mounts: `examples/simple_rbac/main.py`, `examples/enterprise_rbac/main.py`
- Live OpenAPI: `{your-api}/docs` after boot
