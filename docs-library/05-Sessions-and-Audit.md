# Sessions and Audit

Let users (and admins) see **active devices / logins** and search **audit
events**. Mount `get_users_router` for sessions and per-user history; mount
`get_audit_router` when you need cross-user search.

## Sessions (active logins)

Under the hood, a “session” is a stored refresh-token row
(`store_refresh_tokens=True`, the default). The users router lists those rows as
sessions **without** returning secrets.

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
| `DELETE` | `/v1/users/me/sessions` | Authenticated — revoke all (`?keep_current=true` keeps the calling session) |

Response fields (see `UserSessionResponse`): `id`, `device_name`, `ip_address`,
`user_agent`, `created_at`, `last_used_at`, `expires_at`, `usage_count`,
`is_current`.

Access tokens carry a `sid` claim naming their session family, so the list can
mark `is_current: true` on the caller's own session and
`DELETE /v1/users/me/sessions?keep_current=true` can implement "sign out other
devices". Tokens minted before 0.1.0a35 carry no `sid`: they match no row, and
`keep_current=true` answers 400 until the user signs in again.

With frontend profiles configured (`0.1.0a25+`), sessions also record which
frontend minted them as an `azp` claim — preserved and re-validated at refresh
rotation. See [Multi-Frontend Support](../docs/MULTI_FRONTEND_SUPPORT.md).

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

User-centric audit is driven by `user_audit_service`, which is created during
`auth.initialize()` (always available after init). Mount the routers below to
expose it over HTTP.

`enable_audit_log` on `AuthConfig` is a separate/legacy feature-status flag — it
does **not** gate these routes.

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

Besides user lifecycle events the log carries structural changes:
`category=entity` (`entity.created`, `entity.updated` with a field-level diff,
`entity.moved`, `entity.archived`, rooted at the entity's tenant) and
`category=config` (`config.entity_types_updated`, platform-wide, visible to
global actors only). These events have no subject user.

### Definition history

Role and permission definitions keep an append-only history (who changed what,
with before/after snapshots):

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/v1/roles/{role_id}/history` | `role:read` + role visibility |
| `GET` | `/v1/permissions/{permission_id}/history` | `permission:read` |

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
