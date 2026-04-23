# OutlabsAuth Performance Optimization Review

**Date**: 2026-04-22
**Scope**: End-to-end deep dive across the authenticated-request hot path — orchestration, database, permission resolution, caching, FastAPI dependency injection, and cryptography.
**Method**: Six parallel investigations (request lifecycle, DB/ORM, permission algorithms, caching, DI/middleware, crypto) with full-codebase evidence.
**Constraint**: Every recommendation must preserve current security semantics. Nothing in this document weakens authentication, authorization, or cryptographic guarantees.

---

## Executive Summary

### Anatomy of a typical authenticated request (current state)

| Phase | Cost | Dominant work |
|---|---|---|
| Middleware (correlation ID + resource context) | 0.1–0.4 ms | `BaseHTTPMiddleware` async wrapping |
| FastAPI routing + param parsing | 0.5–1.0 ms | — |
| Session checkout from pool | 1–5 ms | — |
| JWT decode + user lookup (or API-key verify) | 5–15 ms | 1 DB query (user) |
| Permission check (DB or Redis cached) | 1–20 ms | DB role/permission join OR Redis GET |
| Snapshot cache write (API-key path) | 2–5 ms | Redis SET + extra DB query for permissions |
| **Total happy-path** | **~8–43 ms** | |

**The two biggest levers**: (1) eliminate redundant work *within* a request, and (2) make the permission-cache hit the default — not an opt-in.

### Top 10 prioritized optimizations

| # | Optimization | Effort | Impact | Risk | Area |
|---|---|---|---|---|---|
| 1 | **Per-request memoization** for user, roles, permissions, entity ancestors (ContextVar-based) | L | **H** | L | Caching / Lifecycle |
| 2 | **Reuse the already-fetched `User` in `PermissionService.check_permission()`** | L | M | None | Lifecycle / DB |
| 3 | **Enable permission caching by default** (currently opt-in via `enable_caching=True`) | L | **H** | L | Permissions / Caching |
| 4 | **Fix N+1 in `MembershipService.add_member()`** (role fetch + closure-table repeat) | M | **H** | L | DB |
| 5 | **Avoid double authentication in `require_permission()`** (JWT decoded twice on the fallback path) | M | M | L | Lifecycle |
| 6 | **Batch permission checks** (`require_any_permission` / `require_all_permissions` loop 1 DB call per perm) | M | **H** | L | Permissions |
| 7 | **In-process user-role snapshot cache** (pub/sub invalidated) | L | M | L | Caching |
| 8 | **Evaluate migration from `python-jose` → `pyjwt`** (5–10× faster JWT verify) | M | M | L | Crypto |
| 9 | **Anonymous / null-user short-circuit** before any DB work | L | M | None | Permissions |
| 10 | **Missing compound index `api_keys (status, expires_at)`** | L | M | L | DB |

Plus **one security fix** not strictly in scope but found during review: **`superuser_token` comparison uses `==`, not `secrets.compare_digest`** — timing-attack vector. Fix immediately (see §8).

### Implementation status

**Phase 1 (landed)** — low-risk, test-covered:

- ✅ #2 Reuse already-fetched `User` in `check_permission()` (enterprise `global_no_entity` budget 8 → 7)
- ✅ #3 Permission caching auto-enables with Redis — verified existing validator at [config.py:203](../outlabs_auth/core/config.py) matches intent
- ✅ #9 Anonymous / null-user short-circuit
- ✅ #10 Compound index `api_keys (status, expires_at)` (migration `20260422_0015`)
- ✅ Superuser-token timing-safe compare (see §8)
- ✅ Drop redundant `ix_users_email` / `ix_entities_slug` (migration `20260422_0016`)
- ✅ Cache `AuthDeps` signatures per instance (avoids rebuild on every router factory call)
- ✅ Pool-recycle tuning: default `3600 → 1800`, production preset `1800 → 750` (under Neon's 900 s idle-kill — §2.4)

**Phase 2 (landed)** — medium-risk, covered by existing query-budget and enforcement suites:

- ✅ #5 Avoid double authentication in `require_permission()` — memoize default-params `auth_result` on `request.state`
- ✅ #4 N+1 fix in `MembershipService.add_member()` — batch `Role` IN-query + single closure lookup per call
- ✅ #6 Batch permission checks for `require_any` / `require_all` — fast path folds user-auth/no-entity/non-ABAC into one `get_user_permissions` per loop
- ✅ #3 (§1.3) Reuse effective permissions from `check_permission` to `_cache_api_key_auth_snapshot` via optional `capture` dict

**Phase 3 (landed)** — per-request cache + ABAC caching + JWT library:

- ✅ #1 Per-request ContextVar memoization — `outlabs_auth/services/request_cache.py` + `RequestCacheMiddleware`; caches User, Entity, and closure-ancestor lookups; both `PermissionService` and `MembershipService` share the same keys
- ✅ ABAC cache-keying fix (§3.1 inline) — `PermissionService._permission_cache_context_hash()` folds `{resource, env, time}` into a stable SHA-256 prefix appended to the cache key; `_can_use_permission_cache()` no longer bails when ABAC is enabled, so ABAC callers hit Redis with the full context as part of the key
- ✅ #8 `python-jose` → `pyjwt` migration (§6.1) — benchmark on this machine (HS256, 20k samples): encode 10.14 → 6.60 µs (1.54×), decode 19.07 → 9.00 µs (2.12×). `utils/jwt.py`, `authentication/strategy.py`, and `services/service_token.py` migrated; `python-jose` dropped from `pyproject.toml`

**Phase 4 (landed)** — middleware + dependency fast-paths:

- ✅ 4.1 Auth and resource-context middleware rewritten as pure-ASGI — no `BaseHTTPMiddleware` wrap-per-request
- ✅ 4.2 `AuthDeps` short-circuits the backend loop when a request carries no credentials for any configured transport
- ✅ 4.3 ABAC `env_context` deferred via a lazy, memoized supplier — dict is materialized only when a check actually reads it
- ✅ 4.4 `APIKey.hash_key_bytes` helper for byte-identity internal hot paths (hex form still used for persistence and Redis keys)
- ✅ 4.5 `PermissionMatcher` precomputed frozenset index — replaces per-candidate string-splitting in `get_user_permission_names` fan-out

**Phase 5 (landed)** — ABAC condition lazy-loading (§3.5):

- ✅ `_abac_allows_role_and_permission` narrows permissions by name match first, then batch-loads ABAC conditions for just those candidates; outer queries no longer eager-load conditions. Also lazy-loads `role.conditions` as a side-effect correctness fix (previously silently treated unloaded collections as empty).

**Phase 6 (landed)** — invalidation scope (§4.4):

- ✅ `EntityService._invalidate_permission_cache` defaults to per-entity only; `scope_global=True` is passed explicitly by `move_entity` / `delete_entity` because they reshape the closure table. Create/update no longer nuke every cached permission check deployment-wide.

**Phase 7 (landed)** — entity fetch dedup (§1.4):

- ✅ `_resolve_context_entity_type` — shared helper that goes through `request_cache.get_or_load`, so `check_permission` and `get_user_permissions` share a single fetch per request per entity.

**Phase 8 (landed)** — closure-ancestor fetch dedup (scope of §4.3):

- ✅ `_load_ancestor_depths` — closure lookup shared across `_check_permission_in_entity` and `_get_entity_context_membership_permission_names` via the request cache. Full app-scoped warm-start deliberately skipped; queries are indexed and the cross-request win doesn't justify the invalidation-tracking complexity.

**Not landed — deliberately deferred:**

- ⏳ #7 In-process user-role snapshot cache (§4.2) — review notes "defer until Redis round-trips measurably bottleneck"; no measurement motivates it yet, and it adds a new cache layer (TTL, size-cap, pub/sub-driven eviction) whose staleness would be security-relevant.
- ⏳ Full closure-table warm start (§4.3) — superseded by the request-cache dedup in Phase 8. Can revisit if across-request closure lookups show up as a measured hotspot.

Test harness additions: Redis fixture with graceful skip, `LatencyStats` p50/p95/p99 instrumentation, SimpleRBAC query-budget suite.

---

## 1. Redundant work on the request hot path

These are operations done more than once per request. Each is a straight "save a DB round-trip" win.

### 1.1 User fetched twice per authenticated permission check  [**HIGH CONFIDENCE, 2 agents**]

- `JWTStrategy.authenticate()` at [outlabs_auth/authentication/strategy.py:118-124](outlabs_auth/authentication/strategy.py) fetches the user with `load_root_entity=True`.
- `PermissionService.check_permission()` at [outlabs_auth/services/permission.py:225-227](outlabs_auth/services/permission.py) does `session.get(User, user_id)` again, because the caller does not pass the already-resolved user.

**Fix**: plumb `user=auth_result["user"]` into `check_permission()`. Its signature already accepts a user; the call sites at [outlabs_auth/dependencies/__init__.py:512-526](outlabs_auth/dependencies/__init__.py) just don't supply it.

**Effort** L · **Impact** M · **Risk** None (user already validated by auth layer).

### 1.2 Double authentication in `require_permission()`

- `require_permission()` [outlabs_auth/dependencies/__init__.py:469-475](outlabs_auth/dependencies/__init__.py) calls `require_auth()` internally, which re-runs the backend loop — a second JWT decode + user fetch.
- Only bypassed when an API-key snapshot is hit [outlabs_auth/dependencies/__init__.py:459-467](outlabs_auth/dependencies/__init__.py).
- **For JWT users this runs on every request.**

**Fix**: share the `auth_result` from the first pass. Either (a) cache on `request.state`, or (b) refactor `require_permission` to compose with the upstream auth result instead of re-invoking it.

**Effort** M · **Impact** M · **Risk** Low.

### 1.3 Permissions re-queried after a successful check (API-key snapshot write)

- `_cache_api_key_auth_snapshot()` [outlabs_auth/dependencies/__init__.py:547-553](outlabs_auth/dependencies/__init__.py) calls `get_user_permissions()` again to build the snapshot — even though `check_permission()` just computed the same permission set.

**Fix**: `check_permission()` returns a tuple `(allowed: bool, effective_perms: Set[str] | None)` so the snapshot writer can reuse.

**Effort** M · **Impact** M · **Risk** None.

### 1.4 Entity fetched twice for context-aware roles

- [outlabs_auth/services/permission.py:237-239](outlabs_auth/services/permission.py) fetches `Entity` directly when `enable_context_aware_roles=True`.
- [outlabs_auth/services/permission.py:861-872](outlabs_auth/services/permission.py) eager-loads the same entity via role-membership join.

**Fix**: single fetch, passed through context. **Effort** M · **Impact** L.

### 1.5 Permission string parsing per check

`_permission_set_allows()` does wildcard string matching (`user:*` matches `user:create`) on every call — string splits, not a precomputed index.

**Fix (conservative)**: precompute a `{resource: {actions, wildcards}}` index when the permission set is loaded; matching becomes O(1) dict lookups. (Bitfield is a more invasive option, H effort, deferred.)

**Effort** M · **Impact** L–M · **Risk** L.

---

## 2. Database and ORM

Overall: the schema is well-indexed and the pool/session setup is sensible. The biggest wins are specific N+1 fixes.

### 2.1 N+1: `MembershipService.add_member()`  [**HIGH IMPACT**]

[outlabs_auth/services/membership.py:168-220](outlabs_auth/services/membership.py) has **two stacked N+1s**:

1. Line 168 loops `await session.get(Role, role_id)` — one query per role.
2. Line 204 calls `_is_role_available_for_entity()` per role, which [line 1586-1591](outlabs_auth/services/membership.py) re-issues the same `SELECT ancestor_id FROM entity_closure WHERE descendant_id = ?` for every role.

Adding 5 roles → **10 DB round-trips** when 2 would suffice.

**Fix**:
- Batch role fetch: `select(Role).where(Role.id.in_(role_ids))`.
- Fetch ancestor set once; pass to the availability check as a parameter.

**Effort** M · **Impact** H · **Risk** L.

### 2.2 Missing compound index `api_keys (status, expires_at)`

API-key verification filters by active + not expired on every API-key request, but there is no compound index — only separate ones.

**Fix**: add `Index("ix_api_keys_status_expires", "status", "expires_at")` in [outlabs_auth/models/sql/api_key.py](outlabs_auth/models/sql/api_key.py).

**Effort** L · **Impact** M · **Risk** L (index-only, reversible).

### 2.3 Redundant single-column indexes where a unique constraint already covers

- `users.email` and `entities.slug` each have both a unique constraint and an explicit regular index. The unique constraint already provides an index — the second is dead weight (write overhead + storage, no read benefit).

**Effort** L · **Impact** L · **Risk** L.

### 2.4 Pool recycle timing

`engine.py` uses `pool_recycle=3600` in dev, `1800` in prod. If running against Neon/RDS with a 900 s idle timeout this risks handing out a dead connection.

**Fix**: reduce to 600–750 s for managed-Postgres providers with known idle-kill windows; leave `pool_pre_ping=True` as a safety net.

**Effort** L · **Impact** M (stability, not throughput) · **Risk** L.

### 2.5 Already efficient (don't touch)

- Closure-table design: ancestor/descendant queries are true O(1) via index.
- `selectinload` on role/permission fan-out avoids N+1 within a single resolution.
- `expire_on_commit=False` + `autoflush=False` on sessions.
- Session-per-request via FastAPI dep, shared across all deps in the same request.

---

## 3. Permission resolution

### 3.1 Permission cache is **off by default**  [**HIGHEST LEVERAGE**]

[outlabs_auth/services/permission.py:1167](outlabs_auth/services/permission.py) (`_can_use_permission_cache`) returns `False` unless `enable_caching=True`. Most callers never flip it. Invalidation is already wired (pub/sub at [outlabs_auth/services/cache.py](outlabs_auth/services/cache.py)) — the infra is ready, the default is wrong.

**Fix**: make `enable_caching=True` the default. Document how to disable for low-latency single-node deployments that don't want Redis. Also: currently any ABAC check bypasses the cache entirely — fix by caching the (user, permission, context-hash) tuple and keying on a deterministic hash of the ABAC env.

**Effort** L (flip default) + M (ABAC-safe caching) · **Impact** **H** · **Risk** L.

### 3.2 No bulk permission checks

`require_any_permission` / `require_all_permissions` loop [outlabs_auth/services/permission.py:1249,1276](outlabs_auth/services/permission.py), calling `check_permission` once per permission. Each call does its own role resolution.

**Fix**: `check_permissions_bulk(user_id, permissions: list[str])` → resolve the user's effective permission set once, test each in-process. Collapses N round-trips to 1.

**Effort** M · **Impact** H (10× for multi-perm guards) · **Risk** L.

### 3.3 No short-circuit for anonymous / null user

[outlabs_auth/services/permission.py:225](outlabs_auth/services/permission.py) still queries when `user_id is None`. Anonymous can never have a permission.

**Fix**: `if user_id is None: return False` as the first line. Small but free.

**Effort** L · **Impact** M on public-facing routes · **Risk** None.

### 3.4 Global checks load entity memberships unnecessarily

For a `check_permission(user, "user:read", entity_id=None)` call, `get_user_permissions()` [outlabs_auth/services/permission.py:857-890](outlabs_auth/services/permission.py) still loads `EntityMembership` rows — wasteful when the caller doesn't supply an entity.

**Fix**: split the path; for `entity_id is None` skip the entity-membership query entirely.

**Effort** L · **Impact** M · **Risk** L.

### 3.5 ABAC conditions eagerly loaded even when not needed

Conditions are `selectinload`-ed for every role on every check [outlabs_auth/services/permission.py:143](outlabs_auth/services/permission.py), regardless of whether the target permission has any conditions attached.

**Fix**: load conditions lazily, only when a candidate permission has `has_conditions=True`. Combine with the cache key fix in §3.1.

**Effort** M · **Impact** M (non-ABAC installs), H (ABAC-light installs) · **Risk** M (test ABAC semantics thoroughly).

### 3.6 Already efficient

- Superuser early return before any DB work.
- Membership validity (`is_currently_valid`) computed in memory.
- Closure table for ancestors — single SQL, no recursive CTE.
- Pub/sub invalidation is correct and granular (user-scoped, entity-scoped, global).

---

## 4. Caching strategy

### 4.1 No per-request memoization  [**TOP SINGLE WIN**]

Three independent agents flagged this — it's the highest-leverage miss. Within one HTTP request, the same `User`, the same role set, and the same ancestor set can be fetched 3–5 times as different dependencies run.

**Proposal** — `ContextVar`-backed request-scoped cache:

```python
# outlabs_auth/services/request_cache.py
from contextvars import ContextVar
_request_cache: ContextVar[dict | None] = ContextVar("request_cache", default=None)

def get() -> dict:
    cache = _request_cache.get()
    if cache is None:
        cache = {}
        _request_cache.set(cache)
    return cache

def clear() -> None:
    _request_cache.set(None)
```

Wire with a thin middleware that calls `clear()` on response, and have `PermissionService.check_permission` / `get_user_permissions` / ancestor lookups check this first. Key format: `("user", user_id)`, `("roles", user_id)`, `("ancestors", entity_id)`.

**Effort** L (~150 LOC) · **Impact** H (70–90% DB query reduction on multi-dep routes) · **Risk** L (cleared per request — no cross-user bleed).

### 4.2 In-process user-role snapshot cache

`UserRoleMembership` + eager-loaded permissions are fetched on every check but rarely change. The pub/sub channel `permissions:user:{uid}` already exists.

**Proposal**: a small app-scoped dict on `PermissionService`: `{user_id: (snapshot, expires_at)}`, 5-minute TTL, invalidated on pub/sub message. No serialization cost, no Redis round-trip.

**Effort** L · **Impact** M · **Risk** L (invalidation is already the hard part, and it's solved).

### 4.3 Entity-hierarchy warm start

Entity closure changes rarely. Load the whole closure table once at app init into a `set[(ancestor, descendant)]` — ancestor checks become in-memory. Invalidate on hierarchy mutations via an existing version counter.

**Effort** L · **Impact** L (closure queries are already cheap) · **Risk** L.

### 4.4 Coarse invalidation blast radius

`publish_all_permissions_invalidation` nukes every cached permission check. Fine for rare global events; watch for call sites that trigger it for per-user events.

**Fix**: audit the triggers. Prefer user- or entity-scoped channels where possible.

**Effort** L · **Impact** L · **Risk** L.

### 4.5 Already efficient

- Redis API-key counters (DD-033): 99 %+ write reduction. Keep.
- Regex LRU cache in ABAC evaluator (1024 entries).
- Pub/sub-based cache invalidation with version counters.
- Activity tracking is detached — non-blocking.

---

## 5. FastAPI dependency injection and middleware

### 5.1 `BaseHTTPMiddleware` wrapping overhead

Both `CorrelationIDMiddleware` and `ResourceContextMiddleware` subclass `BaseHTTPMiddleware`, which wraps each request in an extra async-generator context. Per the Starlette maintainers this adds ~0.1–0.2 ms each.

**Fix**: rewrite as pure ASGI middleware. Cheap overall (~0.4 ms saved), but shows up on high-RPS services.

**Effort** M · **Impact** M (proportional to RPS) · **Risk** L — standard pattern, well documented.

### 5.2 `makefun` signature reconstruction per `require_*` call

[outlabs_auth/dependencies/__init__.py:912-939](outlabs_auth/dependencies/__init__.py) rebuilds a `Signature` object on every call to `require_auth` / `require_permission` / `require_entity_permission` / `require_tree_permission`. This is a route-definition-time cost, not per-request, but it bloats startup for large apps and creates churn when tests instantiate these in loops.

**Fix**: cache the signature on the `AuthDeps` instance the first time it's built.

**Effort** L · **Impact** L (startup only) · **Risk** None.

### 5.3 Backend loop on every failed auth attempt

[outlabs_auth/dependencies/__init__.py:367-394](outlabs_auth/dependencies/__init__.py) iterates all backends until one succeeds. On an anonymous request it pays credential-extraction for every backend even though it will return 401. Marginal.

**Fix**: short-circuit on "no credentials supplied at all" before entering the backend loop. **Effort** L · **Impact** L.

### 5.4 ABAC env context built even when unused

`env_context` is assembled in `require_permission` whenever `abac_enabled`, including for the common case where the specific permission has no ABAC conditions.

**Fix**: defer construction until the permission is known to require evaluation. **Effort** L · **Impact** L.

### 5.5 Already efficient

- Single `AsyncSession` per request via `Depends(auth.uow)` — no redundant session creation.
- Activity tracking is fire-and-forget (detached).
- Parallel snapshot permission checks use `asyncio.gather` [outlabs_auth/dependencies/__init__.py:155-176](outlabs_auth/dependencies/__init__.py).
- Correlation ID via `ContextVar` — <0.1 ms.
- Middleware chain is short and has no synchronous I/O.

---

## 6. Cryptography and tokens

### 6.1 Potential `python-jose` → `pyjwt` migration

`python-jose` is used for all user + service tokens; `pyjwt` is only used by the Apple OAuth client. In HS256 benchmarks, `pyjwt` is typically 5–10× faster for verify — and the JWT verify runs on every authenticated request.

**Action**: benchmark locally first (micro + macro). If confirmed, migrate `outlabs_auth/utils/jwt.py`, `authentication/strategy.py`, and `services/service_token.py`. APIs are similar; exception names differ (`ExpiredSignatureError` is in both libs but from different modules).

**Effort** M · **Impact** M (5–10 % of per-request auth latency) · **Risk** L with good test coverage.

### 6.2 Redundant JWT library in core dependencies

If the migration above goes through, keep `pyjwt` only in the optional OAuth deps group (for Apple). Shrinks the core install and drops one attack surface.

**Effort** L · **Impact** L · **Risk** L.

### 6.3 API-key hash hex round-trip

`sha256(...).hexdigest()` is stored and compared as hex. Internally, comparing as bytes saves the hex encode/decode on every API-key verification.

**Effort** L · **Impact** L · **Risk** L (internal only — wire format unchanged).

### 6.4 Already efficient

- Password hashing is Argon2id, async-offloaded — never on the hot path.
- Refresh-token storage hash is SHA-256 (correct — the token is already high-entropy).
- API-key verification uses prefix + SHA-256 lookup, no full-table scan.
- HS256 is the correct choice for a single-issuer deployment.
- OAuth PKCE/state/nonce comparisons use `secrets.compare_digest`.
- Service tokens do zero DB hits — pure JWT decode, ~0.5 ms as claimed.

---

## 7. Cross-cutting patterns observed

- **No `request.state` used as a shared scratchpad.** Fixing this unlocks §1.2, §1.3, §4.1, §5.4 simultaneously. Probably the single largest refactor payoff.
- **Opt-in caches that should be default-on.** Permission cache (§3.1) and Redis snapshot writes are gated by config flags that nearly every deployment will want.
- **"Defense in depth" fetches.** Several services re-fetch data the caller already has as a safety habit. Trust the caller — the validation happened at the auth boundary.

---

## 8. Security fix (found during review, fix immediately)

**`SuperuserStrategy.authenticate()` at [outlabs_auth/authentication/strategy.py:447](outlabs_auth/authentication/strategy.py) compares credentials with `==`, not `secrets.compare_digest`.** This is a timing-attack vector against a static secret. Trivial fix, must ship regardless of this performance work.

```python
import secrets
if not secrets.compare_digest(credentials, self.superuser_token):
    return None
```

---

## 9. Recommended implementation order

Group by landing blast radius and risk, not just priority score.

### Phase 1 — near-zero-risk wins (days, not weeks)

1. Security fix §8 (timing-safe superuser compare).
2. Anonymous short-circuit §3.3.
3. Reuse user in `check_permission` §1.1.
4. Missing compound index on `api_keys` §2.2.
5. Drop redundant unique+index pairs §2.3.
6. Enable permission cache by default §3.1 (the flag flip, not the ABAC-safe extension).
7. Cache `AuthDeps` signatures §5.2.
8. Pool recycle tuning §2.4 if on managed Postgres.

**Expected gain**: 15–30 % per-request latency reduction on the happy path; one vuln closed.

### Phase 2 — structural (1–2 weeks)

9. **Per-request memoization** §4.1 — biggest single unlock, wires into everything below.
10. Avoid double auth in `require_permission` §1.2 (builds on §4.1).
11. Return effective permissions from `check_permission` §1.3.
12. Fix N+1 in `add_member` §2.1.
13. Bulk permission checks §3.2.
14. In-process user-role snapshot cache §4.2.
15. Skip entity-membership load on global checks §3.4.

**Expected gain**: 50–70 % fewer DB queries per request on multi-dep routes.

### Phase 3 — larger refactors (2–4 weeks)

16. `python-jose` → `pyjwt` migration §6.1 after benchmarks confirm.
17. ABAC-safe permission caching + lazy condition loading §3.1 / §3.5.
18. Pure-ASGI middleware rewrites §5.1.
19. Precomputed permission-matching index §1.5.

**Expected gain**: another 10–15 %, plus a more scalable baseline for high-RPS deployments.

---

## 10. Measurement plan

Before and after each phase, capture:

- p50 / p95 / p99 latency on:
  - a JWT-authenticated `GET` that requires one permission,
  - a JWT-authenticated `GET` that requires three permissions (checks §3.2 + §4.1),
  - an API-key call with snapshot hit and miss (checks §1.3, §1.4).
- Queries per request via SQLAlchemy event hooks or `pg_stat_statements`.
- Redis ops per request.
- `Prometheus` counters already exposed by the observability module — use `auth_permission_checks_total{result="cache_hit|miss"}` to validate §3.1.

Do not ship a phase without a pre/post measurement — "optimizations" that don't move the needle are noise.

---

## Appendix A — Findings we chose NOT to recommend

- **Bitfield permissions**: 10–20 % gain on permission matching, but the refactor touches every permission-literate service, migration, and external client. Defer until the other wins are exhausted.
- **RS256 / EdDSA switch**: only relevant in multi-verifier topologies; currently single-verifier, so HS256 is correct.
- **Lowering Argon2id cost factors**: absolutely not — password hashing is already off the hot path.
- **Dropping `pool_pre_ping`**: saves a tiny round-trip but trades reliability; not worth it.

---

## Appendix B — Scope statement

This review is about the **shared hot path** — what every authenticated API call does. It does not cover:

- Login / token-issuance flow (runs only on login).
- Admin / CLI code paths.
- Background workers and notification delivery.
- Database migrations.

Those are next on the list if this first round lands the expected gains.
