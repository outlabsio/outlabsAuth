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

### Lifecycle and replay barriers (a37)

Deleting or restoring an account retires its pending login/recovery challenges
and advances its durable session generation. Restore returns an identity without
restoring its former privilege; pre-boundary access/refresh proofs remain refused.

Reusing a rotated refresh token aborts the caller transaction, then commits session
revocation and the generation barrier in an independent transaction before refusing
the request. Unrelated pending caller writes roll back. A containment failure
propagates rather than reporting successful revocation. Qualified hosts use ordinary
configured-engine sessions and enough pool capacity for the independent checkout.
Externally held connections, connection-local schema/search-path overrides and
single-connection pools require separate host qualification. See
[Auth recovery](../docs/AUTH_RECOVERY.md) before admission, restore or rollback.

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

## Unreleased transactional lifecycle observer

The local `0.1.0a38` candidate adds optional `lifecycle_observers` to the
Auth constructor. Public a37 does not provide this option. Do not enable it in
a deployed consumer before the library/host artifact and writer coverage gates
in `docs/S2_S3_FOUNDATION_2026-10-11.md` qualify.

An observer is an async callable `(session, event)`. `event` is a frozen scalar
`LifecycleEvent` with a unique event UUID, aware UTC occurrence time, kind,
applicable user/entity/root/membership/actor UUIDs, frozen names, lifecycle
statuses and source. It carries no passwords, email addresses or tokens.

Write host-owned evidence through that exact AsyncSession. The caller owns the
transaction; the observer must not commit, roll back, open another transaction,
change IAM authority or perform mail/network side effects. Observer failure
poisons the active transaction, so a caught error cannot be committed until
rollback. A failed savepoint can be discarded by rolling back that savepoint;
rolling back a later savepoint cannot clear a failure in its outer transaction.

Membership changes/removals, user suspension/retained deletion/hard deletion and
archive cascades invoke the observer before destructive cleanup. Evidence must
use independent host storage without cascading IAM foreign keys to survive
hard deletion. Repeated revocation emits no duplicate removal. Generic
structural hard deletion is refused; use the archive workflow and retain its
evidence. Direct database edits are outside the supported service lifecycle.

No configured observers means no observer queries or events. The callback is
not an external delivery guarantee: write an outbox with the evidence, commit,
then deliver separately. Without verified provider idempotency, record UNKNOWN
outcomes and the possibility of duplicate physical delivery. Crosswalks,
source-owned contributions, recovery fencing and cohort completeness remain
host responsibilities.
