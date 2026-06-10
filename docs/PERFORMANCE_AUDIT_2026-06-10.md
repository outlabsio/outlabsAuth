# OutlabsAuth — Performance / Latency Audit

**Date:** 2026-06-10
**Trigger:** Auth adds significant latency under high traffic "even with Redis." External workers authenticate with **API keys** at **30–40 req/s per worker** and the system slows down.
**Scope:** The per-request hot paths — API-key authentication (the worker case), permission checking on every authenticated request, the Redis caching strategy, DB connection pooling, middleware, and logging/observability overhead.
**Method:** Source trace of the request path through `dependencies/`, `services/api_key.py`, `services/permission.py`, `services/cache.py`, `services/redis_client.py`, `database/engine.py`, `core/auth.py`, and `core/config.py`. Round-trip counts are derived from the code (query/`await` structure), not from a profiler — absolute milliseconds depend on whether Postgres/Redis are localhost vs. networked/managed.

---

## Implementation status (updated 2026-06-10)

Tier-1 hot-path work **landed and tested** (854 tests green; 7 new perf regression tests in `tests/unit/services/test_api_key_perf.py`):

- **#2 — Redis pipelining (DONE).** The per-request usage `INCR` + `last_used` `SET` + per-window rate-limit writes are now a **single** non-transactional pipeline (`RedisClient.record_api_key_usage_pipeline`), replacing 3–4 sequential round trips. Fixed-window semantics preserved via `SET key 0 NX EX ttl` + `INCR` (TTL set once per window, no read-back).
- **#1 — In-process snapshot cache (DONE, opt-in).** When `AuthConfig.api_key_local_snapshot_cache_ttl > 0`, each process serves hot keys from a short-TTL in-memory cache, skipping the Redis snapshot GET + 2 version reads. **Default 0 (off)** — it also skips per-read version revalidation, so set it to 1–5 s for high-throughput workers (bounded per-process staleness).
- **#4 — Pool sizing (DONE).** `db_pool_size` / `db_max_overflow` / `db_pool_timeout` / `db_pool_pre_ping` are now configurable on `AuthConfig` (defaults preserve prior behavior; raise to ~20/40 for high throughput).
- **#5 — Skip EntityMembership under SimpleRBAC (DONE, earlier batch).** `get_user_permissions` no longer issues the always-empty entity query when entity hierarchy is disabled.
- **#3 — Lazy DB session: NOT NEEDED (correction).** The diagnosis below assumed the warm path eagerly checks out + pre-pings a Postgres connection. Verified empirically that **SQLAlchemy 2.0 async sessions acquire a pool connection lazily** (only on the first query); the warm snapshot path runs no query and checks out **0** connections. No change warranted — a lazy-session wrapper would add risk for zero gain.

- **#8 — Fine-grained cache invalidation (DONE).** Role-definition edits (add/remove/set permissions, update) now invalidate **only the users who hold that role** (`RoleService._invalidate_role_permissions_cache`, both SimpleRBAC and EnterpriseRBAC grant paths) instead of flushing the whole permission cache + bumping the **global** API-key snapshot version (which forced every worker to rebuild at once — the thundering herd). **Fail-safe:** any error, or a fan-out above the cap, falls back to a global invalidation, so it never under-invalidates (no stale/elevated grants).

**Net effect** on a steady worker request with the in-process cache enabled: **~6–7 sequential Redis round trips → ~1** (the single pipelined write), and a role/permission edit no longer stampedes every worker. **#6 (JWT permission-path caching)** remains open — lower priority since the worker fleet is API-key, not JWT.

---

## The diagnosis in one paragraph

The latency is **network round trips, not CPU**. A steady worker request on the warm cache path makes **~6–7 sequential Redis round trips** (snapshot read + 2 version reads + usage `INCR` + `last_used` `SETEX` + rate-limit `INCR`/`EXPIRE`) with **no pipelining**, and it still **checks out and pre-pings a Postgres connection it never uses**. By contrast, a JWT **service token** authenticates in ~0.5 ms because it's a pure in-process `jwt.decode` with permissions embedded — **zero** Redis/DB hits. That gap *is* your problem: API keys pay 6–7 stacked network hops where service tokens pay none. On managed/networked Redis (~0.5–2 ms per hop) those hops dominate the request. Three structural issues make it worse under load: the **DB pool is hardcoded to 15 connections per worker and is not configurable**, the **JWT permission path issues 3–4 SQL queries per request and never uses the Redis cache**, and **any permission/role edit flushes the entire permission cache cluster-wide**, triggering a Postgres thundering herd.

---

## Part 1 — API-key worker hot path (the primary concern)

There are two paths; which one runs depends on config and route type.

- **WARM** (snapshot cache hit): `require_permission` → `AuthDeps._try_api_key_auth_snapshot` (`dependencies/__init__.py:160`, invoked at `:656` *before* DB auth). Taken when `enable_abac=False` **and** `enable_caching=True` **and** a prior request populated the snapshot. **Zero Postgres queries.** A 30–40 TPS worker on one key mostly lives here.
- **COLD** (snapshot miss / ABAC on / first request / route not using `require_permission`): falls to `ApiKeyStrategy.authenticate` → `APIKeyService.verify_api_key` (`api_key.py:316`). **Multiple Postgres round trips.**

### Warm-path per-request cost (what a busy worker actually pays)

| # | Operation | Location | Cost |
|---|---|---|---|
| 1 | `GET auth:api-key-snapshot:{hash}` (+`json.loads`) | `api_key.py:831` | 1 Redis RTT |
| 2 | Version validation: `GET global-version` + `GET user:{id}-version` | `cache.py:61-83` | **2 Redis RTT (sequential)** |
| 3 | Permission check (no-entity user) | `api_key.py:1130-1150` | CPU only, 0 RTT ✅ |
| 4 | `INCR usage` + `SETEX last_used` + rate-limit `INCR`(+`EXPIRE`) | `api_key.py:940-951` | **3–4 Redis RTT (sequential)** |
| 5 | DB connection checkout + `SELECT 1` pre-ping | `dependencies/__init__.py:1097`, `engine.py:51` | 1 pool checkout + 1 RTT — **wasted; warm path never queries PG** |

→ **~6–7 sequential Redis round trips + a needless DB checkout per warm request, none pipelined.** At ~0.2–0.5 ms each on localhost (and several ms on networked Redis) this is the bulk of the added latency.

### Cold-path per-request cost (first request per key, ABAC on, or non-`require_permission` routes)

- **Postgres (~4–5 RTT):** pre-ping `SELECT 1` · key lookup by `prefix`+`key_hash` (indexed ✅) · policy `validate_runtime_use` → `session.get(User)` · eager scope load `get_api_key_scopes` (**runs even when `required_scope is None`**) · `resolve_api_key_owner` → a **second** `session.get(User)` for the same owner.
- **Redis (~3–5 RTT):** usage `INCR` · `last_used` `SETEX` · rate-limit `INCR`(+`EXPIRE`).
- **CPU:** one SHA-256 over the key (cheap ✅ — confirmed *not* argon2/bcrypt) + ORM hydration.
- **First request per key is heaviest:** it also reads the IP whitelist (`api_key_ip_whitelist` SELECT) and writes the snapshot (which itself does up to 2 more Redis GETs for versions).

### Confirmed working (don't "fix" these)
- **DD-033 deferred writes work:** with Redis up there is **no per-request DB write** for `usage_count`/`last_used_at` — both go to Redis and the `APIKeyUsageSyncWorker` flushes every 300 s (`workers/api_key_sync.py`). The only synchronous DB write is the Redis-down fallback.
- **Services are singletons** built at `initialize()` (not per request); the dependency signature is built once and cached.

### Notes / things to verify
- **Index mismatch:** `ix_api_keys_status_expires_at` (migration `20260422_0015`) is **not used** by the hot-path query, which filters on `prefix`+`key_hash` and evaluates status/expiry in Python (`api_key.py:356,368`). Not harmful, but it doesn't accelerate auth — confirm with `EXPLAIN`.
- **Snapshot TTL is only 60 s** (`config.py:174`); version checks already guard staleness, so this can safely be longer.

---

## Part 2 — Permission-check hot path (every authenticated request)

### SimpleRBAC, JWT user, no entity (the dominant case)
`require_permission` → `_build_permission_check_cache` fast path (`dependencies/__init__.py:296-341`) → `get_user_permissions` once:
1. `UserRoleMembership` + `selectinload(role).selectinload(permissions)` → **2 SQL RTT**.
2. **`EntityMembership` aggregation runs unconditionally** (`permission.py:1028-1056`) → **2 more SQL RTT** — *even in SimpleRBAC, where it always returns empty*. Pure waste.

→ **~3–4 SQL round trips per request, and the Redis permission-result cache is never used on the JWT path** (the fast path calls `get_user_permissions` directly, bypassing `check_permission` where the cache lives). So "even with Redis," JWT requests hit Postgres every time.

### EnterpriseRBAC / entity context (`_check_permission_in_entity`, `permission.py:599`)
~4–7 SQL RTT depending on context-aware roles. Closure-depth and entity-type lookups **are** already memoized per request via `request_cache` (good, recent work).

### The cross-dependency / multi-permission N+1
Memoization lives only *within one* `_check` closure. A route with `require_all=["a:x","b:y","c:z"]` in entity/ABAC context re-runs the full membership+closure query set **per permission** (3× here). ABAC adds up to 3 lazy condition SELECTs per matching role.

---

## Part 3 — Cross-cutting overhead

- **DB pool is mis-sized AND unconfigurable (highest-impact infra finding).** The core builds `DatabaseConfig` at `core/auth.py:355-359` & `:413-417` passing only `database_url`/`echo`/`connect_args`, so it always falls to defaults `pool_size=5, max_overflow=10` → **15 connections max per worker**. There is **no `AuthConfig` field** to override it, and `DatabasePresets.production()` (10/20) is **dead code** from the core's perspective. At 30–40 req/s × 3–4 sequential queries each, 15 connections queue under burst; `pool_timeout=30` means requests block up to 30 s rather than failing fast.
- **`pool_pre_ping=True`** (`engine.py:51`) adds a `SELECT 1` per checkout. Safe, but a measurable per-request tax given `pool_recycle` already guards staleness.
- **Coarse cache invalidation = thundering herd.** Every permission/role create/update/delete calls `_invalidate_all_permissions_cache` → publishes `permissions:all` (`permission.py:2547-2553`, `role.py:2383`); every instance then runs `delete_pattern("auth:permission-check:*")` via `scan_iter` (`redis_client.py:270-274`). A *single* role edit flushes the whole permission cache cluster-wide, after which every request misses → synchronized cold-cache stampede against the under-sized pool. **Fine-grained invalidation exists** (`publish_user_permissions_invalidation` / `publish_entity_permissions_invalidation`) **but is unused** for permission/role edits. No TTL jitter or single-flight.
- **Middleware is lean** — 3 pure-ASGI middlewares (no `BaseHTTPMiddleware` wrapping); correlation-ID is one `uuid4` + ContextVar. Not a concern.
- **Per-check logging:** `check_permission` calls `datetime.now(tz)` **twice per check** to compute `duration_ms` even when the log is suppressed (`permission.py:354,936`), and always emits the `permission_checks` metric. The granted log line itself is gated (`FAILURES_ONLY` default ✅). The JWT fast path skips this entirely.
- **`staging()` preset ships `log_db_queries=True`** (`config.py:209`) — per-query `perf_counter` + histogram on every query if staging config reaches prod.
- **asyncpg + PgBouncer caveat:** no escape hatch to set `statement_cache_size=0`; prepared statements break under PgBouncer transaction-pooling. Deployment caveat, not a default bug.

---

## Ranked optimizations

### Tier 1 — biggest wins for the 30–40 TPS worker case (do these first)
| # | Change | Location | Impact | Effort | Tradeoff |
|---|---|---|---|---|---|
| **1** | **In-process LRU cache (short TTL ~1–5 s) for the auth snapshot**, keyed by `hash_key`, in front of `get_api_key_auth_snapshot` / `_try_api_key_auth_snapshot`. Hot keys serve auth+perms from process memory, skipping Redis. | `api_key.py:831`, `dependencies/__init__.py:160` | **Largest win** — removes ~3 of ~6 warm Redis RTT (snapshot + 2 version GETs) on hot keys; ~halves warm latency. | Med | Staleness bounded by local TTL (≤ few seconds — far tighter than today's 60 s snapshot TTL); per-process. |
| **2** | **Pipeline the per-request Redis ops** — combine usage `INCR` + `last_used` `SETEX` + rate-limit `INCR`/`EXPIRE` into one `pipeline()`; `MGET` the 2 version GETs. Apply to warm and cold paths. | `api_key.py:940-951` & `:451-473`, `cache.py:71-83`, `redis_client.py` | Collapses 3–4 write RTT → 1 and 2 version GETs → 1. With #1, ~50–70% fewer hops. | Med | Add a pipeline/MGET helper to `RedisClient`; rate-limit semantics unchanged. Low risk. |
| **3** | **Don't hold a DB connection on the warm path.** `Depends(auth.session)` is injected unconditionally, so every request checks out + pre-pings a connection even when the snapshot path returns without touching PG. Make the session lazy (factory / request-scoped lazy open). | `dependencies/__init__.py:1097`, `core/auth.py` (`auth.session`) | Removes a pool checkout + `SELECT 1` per warm request and **frees pool capacity** so high TPS stops queueing on connections. | Med–High | Changes the dependency contract; ensure the cold path still gets a session. Biggest structural throughput win. |
| **4** | **Right-size & expose the DB pool.** Add `pool_size`/`max_overflow`/`pool_timeout` to `AuthConfig`; pass them through at both `DatabaseConfig` construction sites. Default ~20/40; lower `pool_timeout` to ~5–10 s to fail fast. | `core/auth.py:355-359` & `:413-417`, `core/config.py`, `engine.py:43` | **High** — removes the 15-connection ceiling that serializes bursts. | Low | None (pure capacity). Document the asyncpg + PgBouncer caveat. |

> **If you do nothing else:** #1 + #2 + #3 together take the steady worker request from ~6–7 sequential Redis RTT + 1 DB checkout down to **~1 Redis RTT and 0 DB work** — within striking distance of the ~0.5 ms service-token path. #4 protects the cold path and everything else under burst.

### Tier 2 — general per-request wins (apply to all authenticated traffic)
| # | Change | Location | Impact | Effort | Tradeoff |
|---|---|---|---|---|---|
| **5** | **Skip `EntityMembership` aggregation when entity hierarchy is disabled** (`if self.config.enable_entity_hierarchy:`). | `permission.py:1028-1056` | **High for SimpleRBAC** — removes 2 of ~4 SQL RTT on the JWT hot path. | Low | None when hierarchy is off (no entity memberships exist). |
| **6** | **Memoize `get_user_permissions` per-request across dependencies** — stash the aggregated set in `request_cache` keyed by `(user_id, include_entity_local, entity_type)`. | `dependencies/__init__.py:314-341`, `permission.py:885-945` | Med–High on routes with multiple permission deps / `require_all`/`require_any` — collapses N aggregations to 1. | Low–Med | Request-scoped; same isolation as existing `request_cache`. |
| **7** | **Cache the JWT permission path** — Redis snapshot keyed by `(user_id, snapshot_version)`, mirroring the API-key snapshot, so JWT requests stop doing 3–4 SQL every time. | `dependencies/__init__.py:316-341`, `cache.py` | **High if JWT traffic dominates** — per-request 3–4 SQL → one Redis read. | Med–High | Must invalidate on role/membership change — **reuse the existing version-bump** (`bump_user_api_key_auth_snapshot_version`); keep TTL low. |
| **8** | **Fine-grained cache invalidation instead of flush-all** — publish `permissions:user:*`/`permissions:entity:*` (role→affected-users fan-out) instead of `permissions:all`. Interim: keep flush-all but add **single-flight + TTL jitter** to cap the herd. | `permission.py:2547-2553`, `cache.py:236-301`, `redis_client.py:255-278` | **High under write load** — eliminates cluster-wide flush + Postgres stampede on every permission/role edit. | Med | **Security-sensitive:** a revoked grant must stop working within the TTL window — enumerate affected keys carefully; reuse the version-bump mechanism rather than inventing new invalidation. |

### Tier 3 — cleanups (low effort, modest each)
| # | Change | Location | Impact |
|---|---|---|---|
| 9 | Skip eager scope load when `required_scope is None` | `strategy.py:276` | −1 SQL RTT cold path |
| 10 | De-dupe the owner fetch (`validate_runtime_use` + `resolve_api_key_owner` both `session.get(User)`) | `api_key_policy.py:225`, `api_key.py:107` | −1 redundant lookup cold path |
| 11 | Make `pool_pre_ping` opt-out for stable networks | `engine.py:51` (+ `AuthConfig`) | −1 RTT per checkout (keep ON for serverless/flaky PG) |
| 12 | Stop double-timestamping on suppressed permission logs; gate/document the `permission` metric label | `permission.py:354,936`, `service.py:756-774` | −2 `datetime.now()` per check |
| 13 | Set `staging()` preset `log_db_queries=False` | `config.py:209` | removes per-query timing when staging config runs in prod |
| 14 | Raise / auto-extend `api_key_auth_snapshot_ttl` from 60 s (versions already guard staleness) | `config.py:174` | fewer heavy cold rebuilds |

---

## Strategic option worth considering

For **trusted high-throughput workers** that can tolerate revocation latency (the 30–40 TPS case), the fundamentally fastest path is the one that already hits ~0.5 ms: **JWT service tokens with permissions embedded** (stateless, zero round trips). Tier-1 optimizations make API keys *approach* that by caching in-process; but if a class of workers doesn't need per-request revocation or fine-grained DB-backed scopes, issuing them short-lived service tokens (refreshed every N minutes) sidesteps the Redis/DB round trips entirely. Use API keys where instant revocation and per-key rate limiting matter; use service tokens where raw throughput matters.

---

## Caveats
- Round-trip counts are derived from reading query/`await` structure, not a profiler or load test. Absolute latency scales with Redis/Postgres network distance — the **sequential-await pattern hurts most on managed/networked backends**, which matches the reported symptom.
- SQLAlchemy compiled-statement cache hit rates under the pervasive `cast(Any, ...)` wrapping weren't empirically verified.
- If any host injects its own pre-built engine, the pool finding (Tier-1 #4) may not apply to them.
