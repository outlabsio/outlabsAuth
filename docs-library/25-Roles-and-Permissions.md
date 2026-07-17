# Roles and Permissions

> **Handbook** · Catalog and role *definitions* (not who has them).  
> Part of the [OutlabsAuth Handbook](./README.md). Related:
> [User Management API](./23-User-Management-API.md) ·
> [Entity Memberships](./54-Entity-Memberships.md) ·
> [Core Authorization Concepts](./13-Core-Authorization-Concepts.md).

---

## Mental model

| Layer | What it is | Where |
|-------|------------|--------|
| **Catalog** | Permission names (`resource:action`) | `/v1/permissions` |
| **Definitions** | Roles + which permissions they carry | `/v1/roles` |
| **Direct assign** | User ↔ role | `/v1/users/{id}/roles` → [23](./23-User-Management-API.md) |
| **Entity assign** | User ↔ entity + roles | `/v1/memberships` → [54](./54-Entity-Memberships.md) |

This page is catalog + definitions only.

```python
from outlabs_auth.routers import get_roles_router, get_permissions_router

app.include_router(get_roles_router(auth, prefix="/v1/roles"))
app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
```

---

## Permissions catalog (`/v1/permissions`)

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/` | `permission:read` | Paginated. Query: `page`, `limit`, `resource` |
| `POST` | `/` | `permission:create` | `PermissionCreateRequest` — `name` must be `resource:action` (409 on duplicate) |
| `GET` | `/{permission_id}` | `permission:read` | One permission |
| `PATCH` | `/{permission_id}` | `permission:update` | Display/status/tags — **not** rename |
| `DELETE` | `/{permission_id}` | `permission:delete` | System permissions blocked in service |
| `GET` | `/me` | Authenticated | Current user’s permission **names** (`list[str]`) |
| `GET` | `/user/{user_id}` | `permission:read` | Another user’s permission names |
| `POST` | `/check` | `permission:check` | Batch check; optional `entity_id` for entity/tree context |

**Schemas:** `PermissionResponse`, `PermissionCreateRequest`,
`PermissionUpdateRequest`, `PermissionCheckRequest` /
`PermissionCheckResponse` (`has_all_permissions`, `results` map).

> `/me` and `/user/{id}` accept `entity_id` in query today but the service path
> may not apply it. For “can they do X **here**?”, prefer
> `POST /check` with `entity_id`.

For effective permissions **with sources** (role vs membership), use
`GET /v1/users/{id}/permissions` on the users router.

ABAC condition groups/conditions also hang off `/{permission_id}/…` when you
use ABAC — same pattern as roles below.

---

## Roles (`/v1/roles`)

### CRUD and permission sets

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/` | `role:read` | Paginated. Query: `page`, `limit`, `search`, `is_global`, `root_entity_id` |
| `POST` | `/` | `role:create` | `RoleCreateRequest`. Actor must already hold every permission they attach |
| `GET` | `/{role_id}` | `role:read` | One role |
| `PATCH` | `/{role_id}` | `role:update` | `RoleUpdateRequest`; `permissions` replaces the set when sent |
| `DELETE` | `/{role_id}` | `role:delete` | 204 |
| `POST` | `/{role_id}/permissions` | `role:update` | Body: `list[str]` permission names to add |
| `DELETE` | `/{role_id}/permissions` | `role:update` | Body: `list[str]` to remove |

### Enterprise helper

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/entity/{entity_id}` | Tree `role:read` | Roles available for that entity (pickers / memberships UI) |

### Role response fields worth knowing

`RoleResponse` includes: `name`, `display_name`, `permissions[]`,
`is_system_role`, `is_global`, `status`, optional `root_entity_id` /
`scope_entity_id`, `scope` (`entity_only` | `hierarchy`),
`assignable_at_types[]`, `is_auto_assigned`.

Enterprise tips:

- Non-global actors only manage roles in their trees; system-wide roles they
  cannot touch → **403**; out-of-tree → **404**
- SimpleRBAC treats list/create visibility as effectively global
- `assignable_at_types` limits which entity types may receive the role
- `is_auto_assigned` can auto-apply on membership create/update

### ABAC on roles (when enabled)

Under `/{role_id}/condition-groups` and `/{role_id}/conditions` — CRUD with
`role:read` / `role:update`. Walkthrough: [ABAC](./26-ABAC.md).

---

## Simple vs Enterprise

| Concern | SimpleRBAC | EnterpriseRBAC |
|---------|------------|----------------|
| Role visibility | System-wide | Scoped to actor’s entity access |
| `GET /roles/entity/{id}` | Rarely useful | Primary picker for memberships |
| Tree permissions | Unused | `resource:action_tree` + `/permissions/check?entity_id=` |
| Assign path | Users router direct roles | Prefer memberships; direct assign for org-wide roles |

---

## Suggested host flow

1. Seed or create permissions (`resource:action`).
2. Create roles and attach permission lists (delegation check applies).
3. **Simple:** `POST /v1/users/{id}/roles`.  
   **Enterprise:** `POST /v1/memberships/` with `role_ids`; use
   `GET /v1/roles/entity/{entity_id}` in the UI.
4. Gate product UI with `POST /v1/permissions/check` (and `entity_id` when needed).
5. Optional attribute conditions: [ABAC](./26-ABAC.md).

## Related

- [Routers & Prefixes](./02-Routers-and-Prefixes.md)
- [User Management API](./23-User-Management-API.md)
- [ABAC](./26-ABAC.md)
- [Entities](./51-Entities.md)
- [Entity Memberships](./54-Entity-Memberships.md)
- [Core Authorization Concepts](./13-Core-Authorization-Concepts.md)
