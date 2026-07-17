# Entities

> **Handbook** · Enterprise entity hierarchy HTTP API.  
> Part of the [OutlabsAuth Handbook](./README.md). Related:
> [Choosing a Preset](./07-Choosing-a-Preset.md) ·
> [Core Authorization Concepts](./13-Core-Authorization-Concepts.md) ·
> [Entity Memberships](./54-Entity-Memberships.md).

How to mount and call the entity tree when `enable_entity_hierarchy` is on
(**EnterpriseRBAC**).

---

## When this API exists

| Preset | Mount `get_entities_router`? |
|--------|------------------------------|
| **SimpleRBAC** | No — hierarchy is forced off |
| **EnterpriseRBAC** | Yes — typical prefix `/v1/entities` |

```python
from outlabs_auth.routers import get_entities_router, get_config_router

app.include_router(get_entities_router(auth, prefix="/v1/entities"))
app.include_router(get_config_router(auth, prefix="/v1/config"))  # root type vocabulary
```

Runnable: [`examples/enterprise_rbac`](../examples/enterprise_rbac/).  
Catalog: [Routers & Prefixes](./02-Routers-and-Prefixes.md).

---

## Concepts you need

An **entity** is a node in an org tree:

- `structural` — org chart (company → office → team, …)
- `access_group` — cross-cutting workspace / group

`entity_type` is a free-form string (`organization`, `office`, `team`, …).
Parent/child rules live on the parent (`allowed_child_classes` /
`allowed_child_types`). Root types come from system config (below).

**Closure table (one idea):** OutlabsAuth stores every ancestor→descendant pair
(with depth) so “is this under that org?” and “list the whole subtree” stay
cheap. Prefer `/children`, `/descendants`, `/path`, and `*_tree` permissions
over querying closure yourself. Deeper write-up:
[Core Authorization Concepts](./13-Core-Authorization-Concepts.md).

Users get access via **memberships on entities**, not by appearing on the
entity row alone — [Entity Memberships](./54-Entity-Memberships.md).

---

## Permissions (short)

| Style | When |
|-------|------|
| `require_permission("entity:…")` | Global check (no entity context) |
| Tree check (`entity:create_tree`, …) | Target entity present — subtree auth |
| Entity-scoped check | Permission in a specific entity context |

Create under a parent uses tree create on that parent; root create falls back
to a global create check.

---

## HTTP API

Paths relative to `/v1/entities`.

### List / CRUD

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/` | `entity:read` | Paginated active entities. Query: `search`, `entity_class`, `entity_type`, `parent_id`, `root_only`, `page`, `limit` |
| `POST` | `/` | Tree `entity:create` on `parent_entity_id` (or global if root) | `EntityCreateRequest` → `EntityResponse` (201) |
| `GET` | `/{entity_id}` | `entity:read` | `EntityResponse` |
| `PATCH` | `/{entity_id}` | `entity:update` | Partial `EntityUpdateRequest` (identity / parent not renamed here) |
| `DELETE` | `/{entity_id}` | `entity:delete` | Query `cascade` (default false) → 204 |

### Tree navigation

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/{entity_id}/children` | `entity:read` | Direct active children |
| `GET` | `/{entity_id}/descendants` | Tree `entity:read` | Subtree; optional `entity_type` filter |
| `GET` | `/{entity_id}/path` | `entity:read` | Breadcrumb root → entity |
| `POST` | `/{entity_id}/move` | Entity `entity:update`; tree create on new parent if set | `EntityMoveRequest` (`new_parent_id` optional → promote to root). Rewrites closure |

### Create UX helper

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/type-suggestions` | Tree `entity:create` on `parent_id` | Sibling-based `entity_type` autocomplete. Query: `parent_id`, `entity_class` |

### Members bridge (read-only)

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| `GET` | `/{entity_id}/members` | Tree `membership:read` | Paginated convenience list. Full lifecycle: `/v1/memberships` → [54](./54-Entity-Memberships.md) |

---

## Entity-type config API

Mounted separately under `/v1/config` (`get_config_router`):

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/v1/config/entity-types` | Public | Allowed root types + child-type hints |
| `PUT` | `/v1/config/entity-types` | Superuser | Update vocabulary |

Empty `allowed_root_types` for a class rejects root creates of that class.
Per-parent child rules still use the entity’s `allowed_child_*` fields.

---

## Response cheatsheet

**`EntityResponse`:** `id`, `name`, `display_name`, `slug`, `description`,
`entity_class`, `entity_type`, `parent_entity_id`, `status`, validity window,
`allowed_child_classes` / `allowed_child_types`, optional naming governance.

**`MemberResponse`:** `user_id`, email/names, `role_ids`, `role_names`.

---

## Typical host flow

1. Choose Enterprise — [07](./07-Choosing-a-Preset.md)
2. Mount entities + config routers — [02](./02-Routers-and-Prefixes.md)
3. Set root types via `PUT /v1/config/entity-types` (or accept defaults)
4. Create roots → children; use `/type-suggestions` in admin UI
5. Attach users with memberships — [54](./54-Entity-Memberships.md)
6. Protect host routes with entity / tree permission deps — [13](./13-Core-Authorization-Concepts.md)

## Related

- [Choosing a Preset](./07-Choosing-a-Preset.md)
- [Core Authorization Concepts](./13-Core-Authorization-Concepts.md)
- [Entity Memberships](./54-Entity-Memberships.md)
- [Data Models](./12-Data-Models.md)
