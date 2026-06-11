# Performance Audit — 2026-06

> **Status (2026-06-11)**: Phase 1 ✅ (commit `9fdcf5e`) and Phase 2 ✅ implemented on
> `production-hardening`, with warm-path budget tests
> (`tests/integration/test_cached_hotpath_budgets.py`) and round-trip benchmarks
> (`benchmarks/redis_roundtrips_bench.py`). Phases 3–4 pending. See CHANGELOG `[Unreleased]`.

**Scope**: `outlabs_auth/` package (library code only).
**Method**: Five independent audit passes (DB/ORM, auth hot path, caching/Redis, permission resolution, async/observability), every finding verified against current source with file:line evidence. Index claims verified against rendered PostgreSQL DDL. Branch: `production-hardening`.

---

## Executive summary

The library's architecture is sound and most of the *right* optimizations have already been built — Redis permission cache, API-key auth snapshots with versioned invalidation, a one-round-trip usage pipeline, request-scoped memoization, batched fetch helpers, closure table with O(1) ancestor queries, thread-offloaded Argon2. **The core problem is that the hottest paths don't use them.**

The single most expensive pattern: a standard authenticated JWT request with one `require_permission(...)` check costs **4 SQL queries (SimpleRBAC) / 7 SQL queries (EnterpriseRBAC) + 1 guaranteed-miss Redis round trip, on every request, with zero cross-request caching** — even with `enable_caching=True`. The Redis permission cache is only reachable on entity-context/ABAC paths, not the common case.

Secondary themes:

1. **Sequential Redis round trips** where one pipeline would do (snapshot validation 4–5 RTTs, activity tracking 7 RTTs, `verify_api_key` up to 8 RTTs — the pipeline helper exists and is used in exactly one place).
2. **Backwards or unwired cache infrastructure**: `get_descendants` cache *hits* are N+1 and slower than misses; the DD-033 usage sync worker is never started, so DB `usage_count`/`last_used_at` go permanently stale and Redis counter keys grow without bound; invalidation SCANs the whole keyspace once per app instance.
3. **No Redis failure handling**: down at startup → caching disabled for process lifetime; down at runtime → every wrapped call eats up to a 2s socket timeout, multiplied by 3–8 calls per request.
4. **Event-loop blockers**: Twilio (SMS/WhatsApp) and SendGrid notification channels make synchronous HTTPS calls inside `async def`, stalling all in-flight requests for 100ms–1s+ per send.
5. **Write-path amplification**: bulk membership archival ≈ 9 queries per membership; one admin role edit ≈ 27 queries; duplicate/triplicate indexes on hot-write tables.

Estimated effect of the Phase 1 fixes alone (wiring existing machinery): typical authenticated request drops from 4–7 SQL + 1 Redis RTT to **~1 SQL + 1–2 Redis RTTs** with warm caches; API-key snapshot hits drop from 5–6 Redis RTTs to ~2.

---

## Traced cost of a typical request (today)

JWT request through `Depends(require_permission("post:read"))`, SimpleRBAC, Redis on, default config:

| Step | Cost |
|---|---|
| 3× `transport.get_credentials` via DI (results discarded, re-extracted later) | CPU (µs) |
| `jwt.decode` HS256 | CPU (~20–50µs) |
| JWT blacklist `EXISTS` — **feature disabled by default, guaranteed miss** | **Redis ×1** |
| `get_user_by_id` (SELECT users LEFT JOIN entities) + pool pre-ping | **SQL ×1** (+1 ping RTT) |
| Fast path `get_user_permissions`: memberships SELECT | **SQL ×2** |
| selectinload roles | **SQL ×3** |
| selectinload role→permissions | **SQL ×4** |
| (EnterpriseRBAC: + entity_memberships + roles + permissions selectinloads) | (**SQL ×5–7**) |
| Activity tracking (detached task) | Redis ×7 |
| uow teardown rollback | DB ×1 RTT |

EnterpriseRBAC entity-context check (`check_permission` with `entity_id`, cold): **13 queries** (9 with context-aware roles off). Each *additional* permission checked on an entity route re-pays ~10 of them — there is no request-level memo for the entity-context path.

API-key request: snapshot hit = 0 SQL but 4–5 sequential Redis RTTs; snapshot miss or `require_auth()`-only route = ~4–8 SQL + up to 8 sequential Redis RTTs.

---

## Findings

Severity reflects frequency × cost: **HIGH** = every-request or scales with data size; **MEDIUM** = noticeable under load or per-login/admin-action; **LOW** = minor or rare path.

### Theme 1 — The hot path bypasses caching that already exists

#### 1.1 `require_permission` JWT fast path never touches the Redis permission cache — HIGH
`outlabs_auth/dependencies/__init__.py:299-344`, `outlabs_auth/services/permission.py:945-1060`

The fast path (JWT user, non-ABAC, no entity context — the most common request shape) calls `get_user_permissions` directly: 3 SELECTs (SimpleRBAC) / 6 (EnterpriseRBAC) per request. The memo (`cached_permissions`) lives only inside one dependency call's closure. `get_user_permissions` has no Redis or request-scoped caching; the Redis boolean cache (`enable_caching`, 15-min TTL, pub/sub invalidated) is only reachable via `check_permission`, which the fast path deliberately skips. Net: entity-context checks are cached, the common global check is not.

**Fix**: Cache the aggregated permission-name set per `(user_id, include_entity_local)` in Redis. The invalidation machinery already exists (`CacheService.publish_user_permissions_invalidation` bumps per-user versions). Single biggest win in the audit.

#### 1.2 JWT blacklist Redis `EXISTS` on every request even when the feature is disabled — HIGH
`outlabs_auth/authentication/strategy.py:110-117`, wired at `outlabs_auth/core/auth.py:633-638`; write-side gating at `outlabs_auth/services/auth.py:464,496`

`JWTStrategy` receives `redis_client` unconditionally; `config.enable_token_blacklist` (default **False**) is consulted only when *writing* blacklist entries on logout. With Redis on and blacklist off, every JWT request pays one guaranteed-miss Redis round trip.

**Fix** (one line): pass `redis_client` to the strategy only when `enable_token_blacklist=True`, or pass the flag and skip the `exists()`.

#### 1.3 `require_auth()`-only API-key routes bypass the snapshot cache entirely — MEDIUM
`outlabs_auth/dependencies/__init__.py:595-611` (no snapshot attempt; snapshot only in `require_permission`/`require_entity_permission`/`require_tree_permission`)

Routes guarded only by `require_auth()` go straight to `ApiKeyStrategy.authenticate` → `verify_api_key`: ~4 SQL queries + non-pipelined Redis ops per request, even when a fresh snapshot exists. The scopes are also fetched twice within one request (strategy `_check_scope` + `verify_api_key`).

**Fix**: attempt the snapshot in `_authenticate_request` when `X-API-Key` is present; at minimum request-cache the scopes/owner lookups.

#### 1.4 A single permission check materializes the user's entire permission universe — HIGH
`outlabs_auth/services/permission.py:441-447, 455-460, 885-924, 989-1060`

To answer one boolean, every check fetches ALL memberships × ALL roles × ALL permissions as fully-hydrated ORM rows (O(M×R×P)) across 3–5 sequential selectinload round trips per membership type. The wildcard grammar (`name`, `*:*`, `resource:*`, tree variants) is statically enumerable, so the check is expressible as one indexed SQL `EXISTS ... WHERE p.name IN (:variants) LIMIT 1`.

**Fix**: add a targeted single-query path for boolean checks (one JOIN + `IN` over the ≤5 name variants, second branch for `role_entity_type_permissions` when context-aware roles are on). 13 queries → 2–3 per cold Enterprise check. Keep the aggregate path for listing endpoints.

#### 1.5 No request-level memo for entity-context / ABAC multi-permission checks — HIGH
`outlabs_auth/services/permission.py:1449-1451, 1476-1479`; `outlabs_auth/routers/permissions.py:207-212`; fast-path exclusions at `dependencies/__init__.py:299-303`

`require_permission("a","b","c")` on an entity route = 3 × ~10 queries. `POST /permissions/check` with 10 names = 10 × (4–13) queries — it bypasses the deps-layer memo entirely. `request_cache` memoizes user/entity/ancestor rows but never membership/role/permission sets.

**Fix**: memoize granted-name sets per request under `("urm_perms", user_id, entity_type)` / `("em_perms", user_id, entity_id, entity_type)` via the existing `request_cache.get_or_load`; route `POST /permissions/check` through `get_effective_permission_names` (one graph load + in-memory `PermissionMatcher`).

### Theme 2 — Sequential Redis round trips that should be pipelined

#### 2.1 API-key snapshot validation: 4–5 sequential RTTs per request — MEDIUM
`outlabs_auth/services/cache.py:61-83`, `outlabs_auth/services/api_key.py:816-871, 893-929`

Snapshot GET, then global/user/integration-principal/entity version GETs, each individually awaited. Entity-scoped checks re-fetch the global version again in `_entity_relation_cache_version`.

**Fix**: one `MGET`/pipeline for all version keys; memoize the global version in the request cache.

#### 2.2 `verify_api_key` issues up to ~8 sequential Redis ops; the pipeline helper exists but is unused here — MEDIUM
`outlabs_auth/services/api_key.py:490-512, 574-650`; helper `record_api_key_usage_pipeline` at `outlabs_auth/services/redis_client.py:454-508` (used only by the snapshot path)

INCR + SET + up to 3× `increment_with_ttl` (INCR+EXPIRE each), all sequential, on every snapshot-miss / caching-off / `require_auth` key request.

**Fix**: call `record_api_key_usage_pipeline` here too and enforce limits from the returned counts (mirroring `_enforce_snapshot_rate_limits`).

#### 2.3 Activity tracker: 7 sequential Redis RTTs + a detached task per authenticated request — MEDIUM
`outlabs_auth/services/activity_tracker.py:111-132`; invoked at `dependencies/__init__.py:566-569`, `services/auth.py:283-284`

3×SADD + 3×EXPIRE + 1×SET per request. SADDs are idempotent — a busy user generates thousands of redundant ops; EXPIREs re-issued every time.

**Fix**: one `pipeline(transaction=False)`; EXPIRE only when SADD returns 1; optional tiny in-process `(user_id, date)` LRU to skip repeats entirely.

#### 2.4 Role-edit invalidation fan-out: up to 400 sequential Redis RTTs inside the write request — MEDIUM
`outlabs_auth/services/role.py:2431-2447`; `outlabs_auth/services/cache.py:224-226`

Up to 200 users × (INCR + PUBLISH) awaited one-by-one, each publish then triggering a keyspace SCAN per instance (see 3.3).

**Fix**: pipeline the INCRs, publish one batched message.

### Theme 3 — Cache infrastructure that is broken, backwards, or unwired

#### 3.1 `get_descendants` cache *hit* is N+1 — strictly slower than the miss path — HIGH
`outlabs_auth/services/entity.py:675-685` (same shape in `get_ancestors` at `1276-1281`)

The cache stores only IDs; a hit issues one `session.get` SELECT per descendant (500-node subtree = 500 queries) while the miss path is exactly 2 queries. Exposed via `GET /entities/{id}/descendants` and `invalidate_entity_tree_cache` (runs on every move/delete). Found independently by four audit passes.

**Fix**: use the existing batched `_get_entities_by_ids` (as `get_entity_path`'s hit path already does), or drop this cache — it only saves a cheap indexed closure query.

#### 3.2 DD-033 half-wired: the API-key usage sync worker is never started — HIGH
`outlabs_auth/workers/api_key_sync.py` (worker exists, exported); `outlabs_auth/core/auth.py:444-462` (`_initialize` starts only token-cleanup + activity sync); `redis_client.increment` sets no TTL

`verify_api_key` INCRs `apikey:{id}:usage` (no TTL) and writes `last_used` to Redis, relying on a periodic sync to flush to Postgres — but nothing in `core/`, `presets/`, or `bootstrap.py` ever starts `APIKeyUsageSyncWorker`. Unless the host wires it manually: DB `usage_count`/`last_used_at` stay stale forever, and counter keys for deleted/rotated keys accumulate in Redis indefinitely.

**Fix**: start the worker in `OutlabsAuth._initialize()` when Redis is enabled (same pattern as the activity scheduler); add a long self-refreshing TTL to counter keys as a safety net.

#### 3.3 Invalidation = SCAN the whole keyspace, duplicated once per app instance — HIGH
`outlabs_auth/services/cache.py:200-222, 298-316`; `outlabs_auth/services/redis_client.py:255-278`

Pattern invalidation `scan_iter`s the entire Redis DB (default COUNT≈10 → thousands of RTTs at scale), then one giant multi-key DEL. Because deletion happens in the pub/sub *subscriber*, every instance re-runs the same SCAN+DEL against the same shared keys: N instances = N duplicate full scans per invalidation event.

**Fix**: adopt the versioned-key pattern already used for API-key snapshots (include a per-user/global version in the cache key; invalidation = one INCR; stale keys age out by TTL). If SCAN stays: delete once in the publisher, larger COUNT, `UNLINK` in batches.

#### 3.4 Coarse global invalidation: any permission CRUD wipes everything — HIGH
`outlabs_auth/services/permission.py:1552, 1718, 1781, 1820, 1912, 2549-2555`; `outlabs_auth/services/cache.py:232-237`; also `entity.py:497, 609` (`scope_global=True` on move/delete)

`create_permission` (a permission no role references yet), tag edits, and description updates all bump the **global** snapshot version — instantly invalidating every API-key snapshot cluster-wide — and trigger a full `auth:permission-check:*` wipe on every instance. `role.py:2386-2393` documents this exact thundering-herd risk and implements targeted per-user fan-out for role edits; permission.py and entity.py never adopted it. Entity tree invalidation publishes a hierarchy message per node, and each message maps to `invalidate_all_permissions()` on every instance — a subtree move wipes the permission cache N times. No TTL jitter anywhere to spread rebuilds.

**Fix**: skip invalidation on create; resolve affected roles → users for updates/deletes and reuse the role.py fan-out; collapse tree invalidation to one publish; add TTL jitter.

#### 3.5 Pub/sub listener dies permanently on the first Redis error; publishers never delete — MEDIUM
`outlabs_auth/services/cache.py:224-247 (publish), 278-296 (_listen)`

`_listen` has no try/except — one `ConnectionError` kills the task silently (no done-callback, no restart), permanently halting all SCAN-based invalidation while stale grant/deny booleans live up to 900s. Publishers rely entirely on the message round-trip; Redis pub/sub is fire-and-forget, so a dropped message = stale authorization results.

**Fix**: delete matching keys synchronously in `publish_*` (shared Redis — one delete suffices), keep pub/sub for future local caches; wrap `_listen` in try/except with reconnect/backoff and a logging done-callback that restarts it.

#### 3.6 No Redis reconnect or fail-fast: outages multiply request latency; down-at-startup disables caching forever — HIGH
`outlabs_auth/services/redis_client.py:56-115`

`connect()` runs once at init: Redis down at startup → `_available=False` for the process lifetime (never recovers). Redis dies later → `_available` stays True and every wrapped call (3–8 per request) eats up to a 2s socket timeout before its exception is swallowed — a Redis outage becomes multi-second request latency. No circuit breaker, no in-process fallback.

**Fix**: cheap circuit breaker — on RedisError set `_available=False` + monotonic retry-after, background ping to re-enable. One mechanism fixes both directions.

#### 3.7 `increment_with_ttl` is non-atomic INCR-then-EXPIRE → immortal rate-limit counters — MEDIUM
`outlabs_auth/services/redis_client.py:438-452`; used by API-key rate limits and all of `utils/rate_limit.py`

If EXPIRE never lands (crash/timeout after INCR), the window key never expires — that key/email is rate-limited forever. The robust one-RTT pattern (`SET NX EX` + INCR pipeline) already exists in `record_api_key_usage_pipeline`.

**Fix**: reimplement as a 2-command pipeline (`SET key 0 NX EX ttl`, `INCRBY`).

#### 3.8 ABAC cache keys hash request path + client IP + user agent → near-zero hit rate — MEDIUM (HIGH for ABAC deployments)
`outlabs_auth/services/permission.py:1336-1360`; `outlabs_auth/dependencies/__init__.py:44-53`

Every cached entry is keyed per (user, permission, entity, method+path+IP+UA hash): different endpoints/clients never share entries, so the cache rarely hits while writing a 900s-TTL key per unique combination — keyspace bloat with no benefit. Related asymmetry: ABAC *global grants* are never cached at all (`permission.py:472-483` returns without `_cache_permission_result`, while denies and entity grants are cached).

**Fix**: include only env attributes the deployment's conditions actually reference (drop path/UA from the default hash); add the missing cache write on the global-grant branch.

#### 3.9 Smaller cache issues — LOW
- Entity path/descendants caches gate on `redis_client.is_available` only, ignoring `enable_caching` (`entity.py:627, 652-653, 675, 708-709`).
- Dead Redis helpers with no callers: `reset_counter`, `get_and_reset_counter` (its "Use GETDEL" comment is also unimplemented — it's GET-then-DELETE, lossy), `make_permission_key` (`redis_client.py:341-351, 381-410, 568-581`).
- Opt-in local snapshot cache evicts via `dict.clear()` at 50k entries → periodic miss-storm (`api_key.py:125-127`); use an LRU.
- Wasted invalidations on create: `create_entity` publishes entity-scope invalidation for an entity that can't have cached checks (`entity.py:231`).
- In-memory rate-limiter fallback grows unbounded; `cleanup_rate_limiter` never called (`utils/rate_limit.py:61-78, 206-208`).
- `RedisClient.set` treats `ttl=0` as "no expiry" (`redis_client.py:226-229`) — footgun.
- `_cleanup_old_metrics` hardcodes 90 days, ignoring `config.activity_ttl_days` (`activity_tracker.py:456-458`).

### Theme 4 — Event-loop blocking and outbound I/O

#### 4.1 Twilio SMS/WhatsApp channels make synchronous HTTPS calls inside `async def` — HIGH
`outlabs_auth/services/channels/twilio.py:108, 138`; `outlabs_auth/services/channels/whatsapp.py:134, 180-185`

`twilio.rest.Client.messages.create` is a blocking HTTPS request (100ms–1s+) executed directly on the event loop — every in-flight request in the process stalls for the duration. The twilio.py docstring claims it "runs in the default executor"; it does not.

**Fix**: `await asyncio.to_thread(self.client.messages.create, ...)` — same pattern already used in `utils/password.py`.

#### 4.2 SendGrid notification channel is synchronous on the loop — HIGH
`outlabs_auth/services/channels/sendgrid.py:108, 168`

The official `sendgrid` SDK is sync (urllib3); each send blocks the loop for a full TLS+HTTP round trip.

**Fix**: `asyncio.to_thread`, or switch the channel to the already-async `mail/providers.py:SendGridMailProvider` (httpx.AsyncClient).

#### 4.3 Transactional auth mail awaited inline while the uow transaction is held — MEDIUM (HIGH under load)
`outlabs_auth/routers/auth.py:361` (forgot_password), `outlabs_auth/services/user.py:113-122, 180-242`, invite/resend paths; mail timeout = 10s

The HTTP response and the open DB session/transaction wait on an outbound SMTP/HTTPS call with a 10s timeout. A burst exhausts the connection pool. Side effect: response-time difference also leaks account existence (the no-user branch returns immediately).

**Fix**: dispatch mail post-commit via a bounded background task (the fire-and-forget shape `NotificationService.emit` already uses).

#### 4.4 New `httpx.AsyncClient` per email send — no connection reuse — MEDIUM
`outlabs_auth/mail/providers.py:154, 223, 273`; `outlabs_auth/services/channels/webhook.py:160`

Every send pays TCP+TLS handshake (~100–300ms). The OAuth side already caches its client (`oauth/provider.py:78-83`).

**Fix**: one lazily-created client per provider instance, closed on shutdown. Also: RabbitMQ channel re-fetches the exchange per publish (`channels/rabbitmq.py:152-153`) — cache it after `connect()`.

#### 4.5 Unbounded fire-and-forget notification tasks — MEDIUM-LOW
`outlabs_auth/services/notification.py:157-159`

Task hygiene is good (strong refs + done callbacks) but there's no concurrency bound — a login storm with slow channels accumulates tasks/memory without backpressure.

**Fix**: `asyncio.Semaphore` or fixed-size queue + worker.

### Theme 5 — Write-path amplification

#### 5.1 Membership history snapshots rebuilt 2–3× per mutation; bulk revoke/archive ≈ 9 queries per membership — HIGH
`outlabs_auth/services/membership.py:244, 275, 1040-1145, 1318, 1378, 1405-1440`

Each snapshot ≈ 4 queries (entity get, path query, root query, root get). Bulk loops build per-membership "previous" snapshots, then `_record_membership_history` rebuilds each *again*, plus a per-membership `session.get(User)`. Archiving an entity with 1,000 members ≈ **9,000 queries in one transaction**; `delete_entity(cascade=True)` multiplies this per descendant.

**Fix**: accept a pre-built snapshot parameter in `_record_membership_history`; in bulk paths compute entity/path/root once per distinct entity and batch-fetch users with one `IN`.

#### 5.2 `delete_entity(cascade=True)` recurses the full delete workflow per descendant — MEDIUM
`outlabs_auth/services/entity.py:528-554, 562-596`

S-entity subtree → S × (children query + membership archival N+1 + role revocation + key revocation + closure delete + cache publishes), when the closure table yields the whole descendant set in one query.

**Fix**: resolve descendants once via `EntityClosure`, bulk-archive with `id IN (...)`, call the (batched) membership/role/key archival once with the full list.

#### 5.3 Role/permission definition edits rebuild full snapshots 3× (~17–27 queries per admin edit) — MEDIUM
`outlabs_auth/services/role.py:511, 582, 2244, 2258-2340`; `outlabs_auth/services/permission.py:1679, 1720, 2573, 2587-2630`

`update_role` ≈ 27 queries: initial load + before-snapshot (7q) + reload + after-snapshot (7q) + a third identical snapshot inside `_record_role_definition_history_event`.

**Fix**: pass the already-computed snapshot into `_record_*_history_event`; reuse loaded ORM objects in `_build_*_snapshot`.

#### 5.4 Duplicate/triplicate indexes on hot-write tables (verified in rendered DDL) — MEDIUM
`models/sql/api_key.py:98-107, 124-127`; `token.py:31-37, 50-52`; `permission.py:29-32, 138-144`; `closure.py:41-47`; `entity_membership.py:65-72`; `user_role_membership.py:34-42`

`api_keys.prefix` has **3 identical btrees**; `refresh_tokens.token_hash` has 2 unique indexes (every login maintains both); closure carries prefix-redundant indexes (entity create/move inserts O(depth×subtree) rows into each). Cause: `unique=True` + `UniqueConstraint` + `Index` all declared, and the baseline migration materializes models verbatim.

**Fix**: one migration dropping `ix_api_keys_prefix`, the duplicate unique on `refresh_tokens.token_hash`, `ix_permissions_name`, `ix_closure_ancestor_id`, `ix_closure_descendant_id`, `ix_em_user_id`, `ix_urm_user_id`; remove the redundant model declarations.

#### 5.5 ABAC `get_effective_permission_names` = one full `check_permission` per candidate (all active permissions) — HIGH when ABAC is on
`outlabs_auth/services/permission.py:1094-1105`; duplicated at `api_key_policy.py:760, 799, 808-818, 1264`

Candidates default to every active permission; each uncached check is 3–8 queries. P=100 → **300–800+ queries** per API-key grantable-scope calculation. The non-ABAC branch already solves this (one graph load + `PermissionMatcher`).

**Fix**: load the membership→role→permission graph once with conditions eager-loaded, evaluate candidates in memory.

#### 5.6 ABAC per-check query tax and re-parsing — HIGH for ABAC deployments
`outlabs_auth/services/permission.py:803-879`; `policy_engine.py:394-459, 114-124`

Up to 3 queries per candidate role per check just to learn "no conditions → allow"; conditions re-queried per membership occurrence (no per-role memo); every evaluation rebuilds a validated Pydantic `Condition` and `json.loads`es stored values; group evaluation doesn't short-circuit. `PolicyEvaluationEngine()` instantiated per check (`permission.py:411`).

**Fix**: per-check/request "any conditions at all?" pre-check falling through to the set-match path; memoize `(role_id → conditions)` in the request cache; evaluate raw rows with cached parsed values; generator-based `all()`/`any()`; module-level engine singleton.

#### 5.7 `apply_auto_assigned_role` loads every active membership in the target subtree — MEDIUM
`outlabs_auth/services/membership.py:1792-1824` (triggered synchronously from `POST/PATCH /roles`)

**Fix**: set-based `INSERT ... SELECT ... WHERE NOT EXISTS`.

#### 5.8 Membership time-window validity filtered in Python after full eager-load — MEDIUM-LOW
`outlabs_auth/services/permission.py:905-915, 999-1010, 638-644`

Expired-window memberships still pay the full 3–5-query selectinload chain, then get discarded. The correct SQL predicate already exists in `access_scope.py:290-297`; `ix_*_valid_until` indexes already exist.

**Fix**: add the `valid_from`/`valid_until` predicates to the WHERE clauses.

### Theme 6 — Missing indexes and query shape

#### 6.1 `users.password_reset_token` / `users.invite_token` unindexed → full table scan on unauthenticated endpoints — MEDIUM (security-adjacent)
`outlabs_auth/services/auth.py:998, 1458`; `models/sql/user.py:52-58, 170-194`

Every reset-password / accept-invite attempt sequentially scans `users`. Internet-facing and attacker-triggerable.

**Fix**: partial indexes (`WHERE ... IS NOT NULL`) + migration. Also add `ix_permission_tag_links_tag_id` (`models/sql/permission.py:45-66`).

#### 6.2 `list_users` search loads 1,000 rows and paginates/counts in Python — MEDIUM
`outlabs_auth/routers/users.py:370-386`

50× over-fetch per page-of-20 request; wrong `total` beyond 1,000 matches.

**Fix**: add `skip` + `COUNT(*)` to `search_users` (same shape as the non-search path).

#### 6.3 `get_roles_for_entity` unbounded + Python filtering/pagination — MEDIUM
`outlabs_auth/services/role.py:1143-1162`

No SQL LIMIT; eager-loads permissions for every matching role then slices.

**Fix**: push the `assignable_at_types` check into SQL (ARRAY ops) + `COUNT`/`OFFSET`/`LIMIT`.

#### 6.4 Background syncs are N+1 against both Redis and Postgres — MEDIUM
`outlabs_auth/services/activity_tracker.py:384-447`; `outlabs_auth/services/api_key.py:674-716`; `redis_client.py:353-379`

Activity sync: per-key GET inside SCAN + per-user SELECT-then-UPDATE (10k DAU ≈ 20k DB + 10k Redis round trips per cycle). API-key sync: per-key SELECT + per-key flush + per-key GET/DELETE, and the non-atomic GET→…→DELETE silently drops increments that land in between.

**Fix**: MGET per SCAN page; bulk `UPDATE ... FROM (VALUES ...)` (no SELECTs); `GETDEL` per counter; single flush.

#### 6.5 Assorted N+1s and small wastes — LOW
- `GET /roles/{id}` + create/update re-fetch role+permissions already in hand (`routers/roles.py:326-328, 342-345, 399-401`).
- `RoleService.get_user_permission_names` re-selects each role's permissions despite eager loading (`role.py:2160-2183`).
- Per-role `build_role_response` in loops — bulk `build_role_responses` exists (`routers/users.py:1122, 1164-1182`).
- Bulk role-revocation paths: per-row `session.get(Role)`/`get(User)` (`role.py:1984-1995, 2052-2084`).
- API-key bulk revocation: ~5 queries per key; batched scope/whitelist helpers exist but unused there (`api_key.py:1542-1549, 1922-1973`).
- `BaseService.exists()` uses `COUNT(*)` instead of `EXISTS ... LIMIT 1` (`base.py:208-225`).
- `BaseService.create()/update()` always `flush()+refresh()` — one extra SELECT per write; PKs/timestamps are client-generated (`base.py:149-187`).
- `bulk_create_permissions`: per-item existence check + per-item refresh (`permission.py:2524-2547`).
- `list_orphaned_users` loads all history rows to keep latest-per-user — use `DISTINCT ON` (`membership.py:1254-1267`).
- `_validate_hierarchy` fetches the whole ancestor path when `parent.depth` answers it (`entity.py:1010-1016`).
- `refresh_access_token`: two SELECTs that could join, an extra flush, and a minted-then-discarded refresh JWT (`auth.py:575-641`).
- Context-aware role overrides fetched unfiltered (composite index `ix_retp_role_entity_type` unused) and re-lowercased per role per check; dead code at `permission.py:1312-1313`.
- Transport credentials extracted twice per backend per request; DI-injected values discarded (`dependencies/__init__.py:1119-1127`, `authentication/backend.py:84`).
- TypeError-string-matching capability probes per check — detect kwargs once at init via `inspect.signature` (`dependencies/__init__.py:334-341, 452-487`).
- AccessScope: member-user projection fetched by default; UUIDs sorted with `key=str` 4× per scope (`access_scope.py:39-40, 90`).
- `pool_pre_ping=True` default: +1 RTT per connection checkout, every DB-touching request (`core/config.py:50-53`) — documented/configurable; consider production guidance.
- Service tokens pay a wasted JWT signature verification first (backend order; `core/auth.py:630-672`).

### Theme 7 — Observability overhead

#### 7.1 Raw URL paths as Prometheus labels → unbounded cardinality — MEDIUM
`outlabs_auth/observability/dependencies.py:61`; `observability/service.py:415-426, 1220, 1268-1269`

`/v1/users/{uuid}/roles`-style concrete paths create a new label series per distinct ID that ever errors; a scanner grows registry memory and scrape size without bound.

**Fix**: label with the route template (`request.scope["route"].path_format`); keep the concrete path in logs only.

#### 7.2 Log payloads built and JSON-serialized before any level check — MEDIUM
`outlabs_auth/observability/service.py:53-101, 551-581`

No `isEnabledFor` gate: every debug-level emit (e.g. 3× per authenticated request from activity tracking) pays timestamp formatting + full `json.dumps`, then gets dropped at INFO. The async log worker also executes the blocking `stream.write/flush` on the event loop — the queue defers but doesn't offload I/O.

**Fix**: gate on level before building; use `QueueHandler`+`QueueListener` (real thread) for the writer.

---

## Verified non-issues (already good — don't re-fix)

- **Password hashing**: Argon2id at OWASP params, fully thread-offloaded (`asyncio.to_thread`) at every call site, including the timing-equalizing dummy verify.
- **No sync HTTP/`time.sleep`/sync-Redis anywhere else**; OAuth uses a cached `httpx.AsyncClient`; SMTP via `aiosmtplib`; RabbitMQ via `aio_pika`.
- **makefun/signature construction is startup-only**; dependencies built once per router.
- **Auth memoized per request** (`request.state._outlabs_auth_result`); anonymous requests short-circuit before backend work.
- **Closure table is real and O(1) in query count** — one indexed query for the full ancestor map, request-cached; no per-level walking; `move_entity` maintains closure set-based.
- **Request-scoped ContextVar cache** dedupes user/entity/ancestor fetches; middleware is pure ASGI (no body reads, no BaseHTTPMiddleware).
- **DD-033 Redis counters are the hot path when Redis is up** (the gap is the unstarted sync worker); **DD-037 pub/sub is wired and subscribed** (the gaps are robustness and SCAN fan-out).
- **Snapshot usage recording is pipelined (1 RTT)**; snapshot invalidation uses versioned keys (the pattern the permission cache should adopt); role-edit fan-out is capped with a fail-safe.
- **Engine/pool config**: pre-ping + recycle + configurable pool sizing; `expire_on_commit=False`, `autoflush=False`; uow commits only on writes.
- **Login path**: single indexed SELECT, commit-batched writes, no intermediate flushes.
- **List endpoints** (non-search): proper `COUNT(*)` + `OFFSET/LIMIT` with capped page sizes.
- **Negative permission results are cached**; ABAC conditions lazily loaded and batched per name-matching permission; regex `MATCHES` is `lru_cache`d.
- **Wildcard matching is set-based** (no regex, ≤2 splits of the required name); `PermissionMatcher` precomputes an O(1) index for fan-out paths.

---

## Recommended remediation order

**Phase 1 — wire existing machinery into the hot path** (days, low risk, biggest win)
1. Skip blacklist check when `enable_token_blacklist=False` (1.2 — one line).
2. Redis-cache the user permission set on the fast path, invalidated by the existing per-user version keys (1.1).
3. Pipeline snapshot version GETs into one MGET (2.1); use `record_api_key_usage_pipeline` in `verify_api_key` (2.2); pipeline activity tracking (2.3).
4. Start `APIKeyUsageSyncWorker` in `_initialize()` (3.2).
5. Fix `get_descendants`/`get_ancestors` cache-hit N+1 via `_get_entities_by_ids` (3.1).

**Phase 2 — Redis resilience & invalidation correctness**
6. Circuit breaker + reconnect (3.6).
7. Versioned-key invalidation replacing SCAN; targeted invalidation for permission CRUD; single publish per tree change; TTL jitter (3.3, 3.4).
8. Harden `_listen` (restart on error); publishers delete synchronously (3.5).
9. Atomic `increment_with_ttl` (3.7).

**Phase 3 — algorithmic fixes in permission resolution**
10. Targeted SQL `EXISTS` for single-permission boolean checks (1.4).
11. Request-level memo of granted-name sets for entity-context/multi-permission paths; route `POST /permissions/check` through the batched matcher (1.5).
12. ABAC: conditions pre-check, per-role memo, batched effective-names, engine singleton, short-circuit groups (5.5, 5.6).
13. Thread-offload Twilio/SendGrid channels; post-commit mail; shared httpx clients (4.1–4.4).

**Phase 4 — write paths, schema, and polish**
14. Index migration: drop duplicates, add reset/invite-token partial indexes (5.4, 6.1).
15. Batch membership history/bulk archival; set-based `delete_entity` cascade; snapshot reuse in history events (5.1–5.3).
16. SQL-side search pagination and role listing (6.2, 6.3); batch background syncs with GETDEL/bulk UPDATE (6.4).
17. Route-template metric labels; level-gate log serialization (7.1, 7.2); LOW-severity cleanups as touched.
