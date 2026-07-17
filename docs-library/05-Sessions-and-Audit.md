# 05. Sessions and Audit

How hosts expose **active login sessions** (refresh tokens) and **user audit
events**. Requires `get_users_router` (sessions + per-user audit) and optionally
`get_audit_router` (cross-user search).

## Sessions = refresh tokens

When `store_refresh_tokens=True` (default), each successful login creates a
refresh-token row. The users router surfaces those as “sessions” **without**
returning secrets.

Mount users (examples use `/v1/users`):

```python
from outlabs_auth.routers import get_users_router

app.include_router(get_users_router(auth, prefix="/v1/users"))
```

### Self-service

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/users/me/sessions` | Authenticated |
| `DELETE` | `/v1/users/me/sessions/{session_id}` | Authenticated (own session) |
| `DELETE` | `/v1/users/me/sessions` | Authenticated — revoke all |

Response fields (see `UserSessionResponse`): `id`, `device_name`, `ip_address`,
`user_agent`, `created_at`, `last_used_at`, `expires_at`, `usage_count`.

### Admin

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/users/{user_id}/sessions` | `user:read` |
| `DELETE` | `/v1/users/{user_id}/sessions/{session_id}` | `user:update` |
| `DELETE` | `/v1/users/{user_id}/sessions` | `user:update` (all for that user) |

Scoped actors (Enterprise + `enforce_user_scope`) only see targets in their
access scope. Admin revokes emit audit events when audit is wired.

### Do not confuse with `get_session_router`

`get_session_router` is a **minimal login/refresh/logout** surface for embedded
hosts — not the session *inventory* API. Prefer `get_auth_router` for full auth
plus `get_users_router` for session list/revoke.

## Audit events

User-centric audit is driven by `user_audit_service` when present on the auth
instance. Enable audit logging via config when your deployment expects it
(`enable_audit_log` and related wiring — see `AuthConfig` / status docs).

### Per-user history

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/users/{user_id}/audit-events` | `user:read` |

Supports filters such as `category`, `event_type`, pagination.

### Cross-user search

```python
from outlabs_auth.routers import get_audit_router

app.include_router(get_audit_router(auth, prefix="/v1/audit-events"))
```

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/audit-events` | `user:read` |

Query params include `category`, `event_type`, `subject_user_id`,
`actor_user_id`, `entity_id`, `occurred_from`, `occurred_to`, plus pagination.

Scoped Enterprise actors only receive events whose `root_entity_id` is in their
access scope. Global/superuser actors see the wider set according to scope
resolution.

If `user_audit_service` is not available, search returns an empty page rather
than failing hard.

## OutlabsAuth UI

With users (+ audit) routers mounted under the same `authApiPrefix`, the sister
admin console can show session and audit surfaces that the backend advertises.
Point the UI as described in [`docs/AUTH_UI.md`](../docs/AUTH_UI.md).

## Related

- [02-Routers-and-Prefixes.md](./02-Routers-and-Prefixes.md)
- [03-Configuration.md](./03-Configuration.md)
- [22-JWT-Tokens.md](./22-JWT-Tokens.md)
- Live OpenAPI on a running example (`/docs`)
