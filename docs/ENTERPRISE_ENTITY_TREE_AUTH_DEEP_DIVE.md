# Enterprise Entity/Tree Auth Deep Dive

**Date:** 2026-04-20

This note captures the EnterpriseRBAC API-key entity/tree hot path after the
Redis-backed API-key auth snapshot and entity-relation cache slices.

## Current State

Warm Redis snapshots now make these paths zero-SQL:

- SimpleRBAC direct `auth.authorize_api_key(..., required_scope=...)`
- SimpleRBAC `auth.deps.require_permission(...)`
- Enterprise unanchored personal API keys
- Enterprise platform-global system integration API keys
- Enterprise anchored personal API keys after the `(key, target entity,
  permission)` path is warm
- Enterprise entity-scoped system integration API keys after the
  `(anchor entity, target entity)` relation path is warm

ABAC-conditioned authorization remains intentionally on the relational path.

## Current Code Path

Direct host authorization:

```text
auth.authorize_api_key(..., required_scope=..., entity_id=target)
  -> _try_authorize_api_key_snapshot(...)
       load API-key snapshot from Redis
       validate scope and owner permission from Redis permission-check cache
       validate anchor-to-target relation from Redis entity-relation cache
       record usage/rate limits in Redis
       return host-safe snapshot auth result
  -> APIKeyService.verify_api_key(...)
       used only on cache miss/cold path
       load API key by prefix/hash
       validate_runtime_use(...)
         load owner/principal
         load anchor entity when key is entity-scoped
       validate_runtime_permission(...)
         user key: PermissionService.check_permission(owner, scope, target)
         principal key: resolve principal effective scopes
       load API key scopes
       check_entity_access_with_tree(...)
         direct anchor match or closure-table descendant check
       record usage in Redis or DB fallback
  -> resolve owner again for host-safe auth result
  -> load API key scopes again for response metadata
  -> cache API-key auth snapshot
```

FastAPI dependencies:

- `require_permission(...)`, `require_entity_permission(...)`, and
  `require_tree_permission(...)` now attempt the API-key snapshot path before
  invoking DB-backed API-key authentication when ABAC is off.
- The slow path still populates the API-key snapshot, permission-check cache,
  and entity-relation cache after a successful authorization.

## Measured Query Shape

Fresh local benchmark, concurrency 10, 25 iterations:

| scenario | Redis off q/req | Redis cache q/req | Redis off p95 ms | Redis cache p95 ms |
|---|---:|---:|---:|---:|
| `enterprise_personal_api_key_anchored_tree` | 19 | 0 | 91.45 | 7.34 |
| `enterprise_system_api_key_entity_tree` | 11 | 0 | 49.40 | 6.67 |

Single-request trace for cold personal anchored-tree authorization:

| group | queries |
|---|---:|
| API-key row lookup | 1 |
| owner and anchor runtime-use checks | 2 |
| owner permission graph at target entity | 7 |
| API-key scope check | 1 |
| API-key anchor-to-target closure check | 1 |
| DB usage write when Redis is off | 1 |
| owner/scopes reload for auth result | 2 |

With Redis cache warm, the owner permission graph is hidden by the existing
permission-check cache and the anchor-to-target closure check is hidden by the
entity-relation cache. The API-key auth snapshot now avoids the repeated
API-key/owner/scope/entity metadata loads.

## What The Snapshot Is Missing

The current API-key snapshot already stores:

- key id/prefix/status/expiration/kind
- owner id/type
- user id or integration-principal id
- API-key scopes
- integration principal allowed scopes
- API-key anchor entity id
- `inherit_from_tree`
- IP whitelist
- rate limits
- Redis invalidation versions

It still intentionally does not provide Redis-only answers for:

- ABAC-conditioned permissions
- cached negative entity/permission checks as hard denials
- cold first-target requests that have not populated the relation and
  permission caches yet

## Implemented Slice

The implementation uses Redis-backed projections instead of serializing the
whole Enterprise tree into each API-key snapshot.

### 1. Cache entity relationship checks

Added a small Redis relation cache:

```text
auth:entity-relation:{global_epoch}:{anchor_id}:{target_id} -> true/false
```

Rules:

- global/unanchored key: allow any target
- exact anchor match: allow without Redis
- `inherit_from_tree=False`: deny descendants
- `inherit_from_tree=True`: use the relation cache for descendant access
- relation cache miss: fall back to the existing DB closure-table path, then
  populate the relation cache

This avoids storing every descendant in the API-key snapshot and works for both
small and large trees. Relation keys include the global auth snapshot epoch, so
global RBAC/entity invalidations move new requests onto fresh relation keys
without requiring a wide Redis key delete.

### 2. Reuse the existing permission-check cache for user owners

The slice does not compile every entity-local permission into the API-key snapshot. The
existing permission cache already stores:

```text
auth:permission-check:{user_id}:{entity_id}:{permission} -> bool
```

Entity snapshot fast path uses it like this:

- if key is user-backed and target entity is present, require a cached
  permission result for `(user_id, target_entity_id, required_scope)`
- if cached `True`, continue with scope/entity checks from Redis
- if cache miss, fall back to the existing DB path; `PermissionService` will
  populate the cache
- if cached `False`, fall back to the DB-backed path for now; explicit fast-deny
  semantics are a separate follow-up

This keeps entity-local roles, ancestor `_tree` permissions, role scope rules,
and ABAC exclusion semantics centralized in `PermissionService`.

### 3. Extend snapshot use to entity dependencies

Added entity-aware snapshot attempts before DB-backed API-key auth in:

- direct `auth.authorize_api_key(..., entity_id=...)`
- `AuthDeps.require_permission(...)` with entity context
- `AuthDeps.require_entity_permission(...)`
- `AuthDeps.require_tree_permission(...)`

For ABAC-enabled configs, keep the existing DB path.

### 4. Kept cold-path cleanup separate

There is duplicate work in the slow path:

- owner/principal is loaded for runtime-use checks and again for the auth result
- API-key scopes are loaded for validation and again for metadata
- principal effective scopes can be resolved twice

This can be cleaned up with a richer internal verification result, but it is a
separate refactor from the Redis entity/tree projection. The projection gives
the bigger production win because worker traffic is dominated by repeated warm
requests.

## Observed Result

After the entity relation projection and permission-cache reuse:

- Enterprise anchored personal keys move from `19` SQL queries/request with
  Redis off to `0` for repeated `(key, target_entity, permission)` checks in
  Redis cache mode
- Enterprise entity-scoped system keys move from `11` SQL queries/request with
  Redis off to `0` after the relation cache is populated
- cold or first-target requests still pay the existing DB path once, then warm
  subsequent requests

## Main Correctness Risks

- Entity moves and archive/delete operations must keep bumping the global auth
  snapshot epoch so new requests avoid stale relation-cache keys.
- Role, permission, and membership mutations must keep invalidating
  `auth:permission-check:*` entries and API-key snapshot versions.
- Denial caching should be explicit. Returning `None` from the current snapshot
  helper means "fallback" today, not "hard deny"; fast-deny behavior needs a
  small return-shape change to avoid accidental DB fallback on known denials.
- ABAC-conditioned permissions must remain excluded from snapshot authorization.

## Suggested Test Targets

- Direct `authorize_api_key(..., entity_id=descendant)` uses snapshot +
  relation cache + permission-check cache without calling `verify_api_key`.
- `require_tree_permission(...)` can authorize a warm API key without invoking
  the DB-backed API-key strategy.
- Relation cache miss falls back to the existing closure-table path and
  populates the relation cache.
- Entity move/archive bumps the global auth snapshot epoch so stale relation
  answers are bypassed.
- User membership/role/permission mutation invalidates cached permission checks
  and API-key snapshot versions.
- ABAC-enabled auth ignores entity/tree snapshot fast paths.
