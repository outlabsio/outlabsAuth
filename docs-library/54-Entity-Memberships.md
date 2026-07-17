# Entity Memberships

> **Handbook** · EnterpriseRBAC membership lifecycle.  
> Part of the [OutlabsAuth Handbook](./README.md). Related:
> [Entities](./51-Entities.md) ·
> [Core Authorization Concepts](./13-Core-Authorization-Concepts.md) ·
> [Roles & Permissions](./25-Roles-and-Permissions.md).

A membership connects **one user**, **one entity**, and **zero or more roles**.
That is the primary way EnterpriseRBAC grants entity-scoped access. Users can
belong to many entities; each membership has its own status and validity window.

```python
from outlabs_auth.routers import get_memberships_router

app.include_router(get_memberships_router(auth, prefix="/v1/memberships"))
```

SimpleRBAC has no memberships — use direct roles on the users router instead.

---

## Lifecycle

Stored fields include `status`, `valid_from`, `valid_until`, join/revoke
metadata, and `revocation_reason`.

| Status | Grants permissions? |
|--------|---------------------|
| `active` (and inside validity window) | Yes |
| `suspended` / `revoked` | No |
| `expired` / `pending` | Computed: outside window / not yet started — no |
| `rejected` | Reserved for future approval flows |

**`status`** is what you store. **`effective_status`** applies the validity
window at read/check time (e.g. stored `active` + `valid_until` yesterday →
`expired`).

A membership grants permissions only when `status == active` **and** now is
inside the validity window.

**Limitation:** timing is membership-wide — you cannot give different roles on
the same membership different windows.

---

## HTTP API (`/v1/memberships`)

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/me` | Authenticated | Own memberships; `include_inactive` |
| `POST` | `/` | Tree `membership:create` | Add member. Body: `user_id`, `entity_id`, `role_ids`, optional `status` (`active`\|`suspended`), validity, `reason` |
| `GET` | `/entity/{entity_id}` | Tree `membership:read` | Members of one entity (paginated) |
| `GET` | `/entity/{entity_id}/details` | Tree `membership:read` | Same + user/role summaries |
| `GET` | `/user/{user_id}` | Tree / scoped read | User’s memberships (access reviews) |
| `PATCH` | `/{entity_id}/{user_id}` | Tree `membership:update` | Replace roles, suspend/reactivate, set/clear windows (`null` clears) |
| `DELETE` | `/{entity_id}/{user_id}` | Tree `membership:delete` | Soft revoke → `revoked`; reactivate later with `PATCH` `status=active` |

List/detail queries: `page`, `limit`, `include_inactive` (default false).

Roles on create/update are validated against the entity context. Role pickers:
`GET /v1/roles/entity/{entity_id}` — [25](./25-Roles-and-Permissions.md).

Convenience read on the entities router: `GET /v1/entities/{id}/members` —
[51](./51-Entities.md). History/orphans on users router — [23](./23-User-Management-API.md).

---

## Response shape (typical)

```json
{
  "id": "uuid",
  "entity_id": "uuid",
  "user_id": "uuid",
  "role_ids": ["uuid"],
  "status": "active",
  "effective_status": "expired",
  "joined_at": "2026-03-16T09:00:00Z",
  "valid_from": "2026-03-16T09:00:00Z",
  "valid_until": "2026-03-23T09:00:00Z",
  "is_currently_valid": false,
  "can_grant_permissions": false
}
```

---

## Related

- [Entities](./51-Entities.md)
- [Roles & Permissions](./25-Roles-and-Permissions.md)
- [User Management API](./23-User-Management-API.md)
- [Choosing a Preset](./07-Choosing-a-Preset.md)
- Mount catalog: [Routers & Prefixes](./02-Routers-and-Prefixes.md)
