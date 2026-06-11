# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is in alpha (pre-1.0); breaking changes are allowed between alpha releases.

## [Unreleased]

### Security (breaking)

- **Tenant isolation on user-management routes (DD-056, closes SEC-4).** All `/users` endpoints now
  enforce entity-scope isolation: a non-global actor can only read or mutate users whose
  `root_entity_id` or active entity membership falls inside the actor's (closure-expanded) accessible
  entities. Out-of-scope targets return **404** (anti-enumeration); `GET /users/` and
  `GET /users/orphaned` are silently filtered to the actor's trees (the `root_entity_id` param narrows
  within scope, never widens). Non-global actors can no longer mutate superuser accounts (403), even
  in-tree. Superusers, unscoped API keys, and SimpleRBAC deployments are unaffected.
- **System-wide roles now grant global scope.** A currently-valid assignment of a system-wide role
  (`is_global=True`, no `root_entity_id`/`scope_entity_id`) resolves to global access scope — the
  explicit, auditable replacement for the previous implicit cross-tree access. **Migration:** if a
  deployment relied on a non-superuser admin managing users across trees (e.g. an "administration"
  entity), have a superuser assign that admin a system-wide role. Transitional escape hatch:
  `OutlabsAuth(enforce_user_scope=False)` restores the legacy behavior and will be removed in a future
  alpha.
- **Roles router aligned to the same anti-enumeration contract (DD-056 follow-up).** Role
  detail/update/delete/permission/ABAC endpoints now return **404** for roles outside the actor's
  accessible scope (previously 403 "Role is outside your accessible scope"), indistinguishable from
  nonexistent roles. System-wide roles still return the explanatory **403** ("Only superusers can
  access system-wide roles"): they are platform objects, not tenant data, and their IDs already
  surface on in-scope users' role lists.

### Performance

Phase 1 of the 2026-06 performance audit (`docs/PERFORMANCE_AUDIT_2026-06.md`): wire the caching and
pipelining machinery that already existed into the hot paths that weren't using it.

- **Aggregated user permission sets are Redis-cached on the hot path.**
  `PermissionService.get_user_permissions` — what every JWT `require_permission` dependency resolves
  through — now serves from a versioned-key Redis entry (`CacheService.get/set_user_permission_names`)
  validated against the same global/user invalidation counters the API-key snapshots use. Every role,
  permission, and membership mutation already bumps those counters, so revocations take effect on the
  next request. Warm authenticated requests drop from 3–6 SQL queries to one Redis MGET.
- **JWT blacklist check gated by `enable_token_blacklist`.** With the flag off (default), every JWT
  request previously paid a guaranteed-miss Redis `EXISTS`; the strategy now only gets the Redis
  client when blacklisting is enabled.
- **API-key snapshot version validation uses one MGET** instead of 2–4 sequential GETs
  (snapshot-validated requests go from 4–5 Redis round trips to 2).
- **`verify_api_key` records usage, `last_used`, and rate-limit windows in one pipelined round trip**
  (was up to 8 sequential Redis ops), enforcing limits from the returned counts — same semantics as
  the snapshot path. The counter-sync job now reads `last_used` in both raw and legacy JSON encodings.
- **DD-033 usage sync worker is actually started.** `OutlabsAuth._initialize()` now launches
  `APIKeyUsageSyncWorker` when Redis is available (new `api_key_usage_sync_interval` config, default
  300s) and stops it on shutdown. Previously the worker existed but was never wired in, so
  `api_keys.usage_count`/`last_used_at` went permanently stale and counter keys accumulated forever.
- **Activity tracking pipelined**: the per-request DAU/MAU/QAU bookkeeping (3×SADD + 3×EXPIRE + SET)
  collapses from 7 sequential Redis round trips to 1.
- **Entity cache hits no longer N+1.** `get_descendants` (cache-hit path) and `get_ancestors`
  batch-fetch entities with one `IN` query via `_get_entities_by_ids`; previously a 500-node subtree
  cache "hit" issued 500 sequential SELECTs — slower than the cache miss.

Phase 2 (Redis resilience + invalidation correctness):

- **Versioned permission-check cache — invalidation without SCAN.** Boolean permission verdicts now
  embed the global/user (+entity) version counters and are validated in the same MGET that reads
  them. Invalidating is the single version INCR the publishers already perform, so the pub/sub
  listener no longer SCAN-deletes — previously **every** app instance SCANned the entire Redis
  keyspace per invalidation event. Pre-upgrade boolean entries read as misses and age out via TTL
  (mixed-version deployments stay safe). Permission TTLs now carry ±10% jitter to avoid rebuild
  stampedes.
- **Targeted invalidation for permission definitions.** Creating a permission (or editing
  display/description/tags) no longer invalidates anything — previously each of these bumped the
  GLOBAL snapshot version, instantly expiring every API-key snapshot cluster-wide. Status changes
  and archival fan out only to users holding a role that references the permission (200-user cap
  with fail-safe global fallback, mirroring the existing role-edit machinery); permissions carrying
  ABAC conditions still invalidate globally because integration principals hold no roles.
- **Redis circuit breaker with background reconnect.** A connection-class failure now flips the
  client unavailable immediately (callers fall back instantly) instead of every wrapped call eating
  up to a 2s socket timeout — previously a Redis outage added multi-second latency to every request,
  and Redis being down **at startup** disabled caching for the process lifetime. A single background
  probe re-pings with capped exponential backoff and restores availability when Redis answers.
- **Invalidation fan-outs are pipelined.** Role/permission edits touching up to 200 users issued 2
  sequential Redis round trips per user inside the admin write request (up to 400 RTTs); they now
  bump all versions and publish all messages in one pipeline (`benchmarks/redis_roundtrips_bench.py`
  measures ~18x on localhost). Entity-tree invalidation similarly batches per-node deletes into one
  UNLINK and publishes a single hierarchy message instead of 3 sequential ops per node.

Verification: `tests/integration/test_cached_hotpath_budgets.py` pins the warm-path budgets against
real Postgres + Redis (warm aggregated reads and boolean checks = **0 SQL**; grants/revocations apply
on the very next read), and `benchmarks/redis_roundtrips_bench.py` re-measures the round-trip wins on
any box.

### Fixed

- **Cache-invalidation listener no longer dies permanently on the first Redis error.** The DD-037
  pub/sub listener had no error handling: one `ConnectionError` killed the task silently and the
  instance stopped reacting to invalidation messages for its lifetime. It now resubscribes with
  capped backoff, and unexpected task death is logged.
- **Rate-limit window counters are atomic.** `increment_with_ttl` was INCR-then-EXPIRE; if the EXPIRE
  never landed (crash/timeout between the two), the window key never expired and that API key or
  email stayed rate-limited forever. The window is now established atomically (`SET NX EX` + `INCRBY`
  in one pipeline), and legacy TTL-less counters are healed on their next increment.
- **ABAC condition and condition-group CRUD now invalidate the permission cache.** All six
  condition/group mutation methods previously performed no invalidation, leaving stale ABAC verdicts
  cached for up to the 15-minute TTL after a condition change.

### Database migrations

- None. DD-056 uses existing tables; `enforce_user_scope` is a config flag. The performance work adds
  only the `api_key_usage_sync_interval` config field — no schema changes. The latest Alembic
  revision remains `20260425_0017`.

## [0.1.0a22] - 2026-04-25

Retroactive entry (covers 0.1.0a21–a22, which shipped without changelog sections).

### Added

- **Magic-link and email access-code authentication** (`enable_magic_links`, `enable_access_codes`)
  with per-recipient rate limiting, challenge expiry, and one-time use. New auth router endpoints and
  schemas; example wiring in `examples/enterprise_rbac`.

### Database migrations

- **New `auth_challenges` table** — Alembic revision `20260425_0017_add_auth_challenges` (plus indexes
  on `user_id` and `used_at`). Applied automatically with `auto_migrate=True`, or run
  `outlabs-auth bootstrap` / the packaged Alembic migrations before upgrading app instances.

## [0.1.0a20] - 2026-04-23

Performance pass covering middleware, dependency wiring, ABAC lazy-loading, permission-cache invalidation scope, and request-scoped dedup of repeat entity and closure-table fetches. Full test suite (815 tests) green.

### Performance

- **Pure-ASGI middleware.** `CorrelationIdMiddleware` and `ResourceContextMiddleware` rewritten as ASGI middleware — no `BaseHTTPMiddleware` wrapper, no `Request` rebuild per request.
- **`AuthDeps` credential short-circuit.** When a request has no credentials for any configured transport, the auth-backend loop exits immediately instead of instantiating each backend only to probe empty headers.
- **Lazy ABAC `env_context`.** `env_context` is now built by a memoized supplier; the dict materializes only when a check actually reads `request.*` or `time.*` attributes.
- **`APIKey.hash_key_bytes` helper.** Returns the raw 32-byte digest for byte-identity internal hot paths; the hex form is still used for persistence and Redis keys. Dropped an unused `verify_hash` path along the way.
- **`PermissionMatcher` precomputed index.** Replaces per-candidate string-splitting in the `get_user_permission_names` fan-out with a single frozenset-backed index covering super-grant, exact, wildcard, `_all`, and `_tree` matches.
- **ABAC condition lazy-load.** `_abac_allows_role_and_permission` now narrows permissions by name match first, then batch-loads ABAC conditions only for the matching candidates. Outer queries no longer eager-load `permission.conditions`. Side-effect correctness fix: `role.conditions` is also lazy-loaded now (previously an unloaded collection was silently treated as empty).
- **Targeted entity cache invalidation.** `EntityService._invalidate_permission_cache` defaults to per-entity and takes an explicit `scope_global=True` from `move_entity` / `delete_entity` (the operations that reshape the closure table). Create and update no longer nuke every cached permission check deployment-wide.
- **Request-scoped entity fetch dedup.** New `_resolve_context_entity_type` helper routes context-aware-role resolution through `request_cache.get_or_load`, so `check_permission` and `get_user_permissions` share a single entity fetch per request per entity.
- **Request-scoped closure-ancestor dedup.** New `_load_ancestor_depths` helper deduplicates closure-table ancestor lookups across `_check_permission_in_entity` and `_get_entity_context_membership_permission_names` via the same request cache.

### Deliberately deferred

- **In-process user-role snapshot cache.** No measurement yet shows Redis round-trips as the bottleneck; a new cache layer with TTL, size-cap, and pub/sub eviction would add security-relevant staleness surface for speculative gain.
- **Full closure-table warm-start.** The request-cache dedup covers the observed repeat-fetch pattern; a cross-request warm-start would also need invalidation tracking and isn't justified without a measured hotspot.

## [0.1.0a19] - 2026-04-22

Operator tooling release: first-class `doctor` and `bootstrap` CLI commands for preflight diagnostics and idempotent first-boot orchestration. Full test suite (793 tests) green.

### Added

- **`outlabs-auth doctor` — read-only preflight diagnostics.** New CLI command that runs five safe, read-only checks against the target database and schema: connectivity, target schema existence, Alembic version table presence, revision matches the packaged head, and core auth tables present. Supports `--format text` (default, with `[OK]` / `[FAIL]` / `[--]` markers and `->` remediation hints) and `--format json` (machine-readable payload with `healthy`, `schema`, and a `checks[]` array). Exit codes: `0` healthy, `1` one or more checks failed, `2` `DATABASE_URL` not set. Short-circuits cleanly on prerequisite failures (skipped checks are reported, not silently dropped) and redacts passwords from any URL printed to stdout or embedded in JSON output. Covered by 18 new tests in `tests/unit/test_cli_doctor.py`, wired into the release-gate workflow.
- **`outlabs-auth bootstrap` — idempotent first-boot orchestrator.** New CLI command that classifies the target schema (`empty`, `legacy`, `healthy_current`, `healthy_behind`, `alembic_empty`, `schema_missing`, `partial_non_auth`, `drifted`, `no_connection`) and builds a deterministic plan to reach a healthy state: migrate → seed → (optionally) create admin. Composes existing `run_migrations` (which already handles legacy adoption), `seed_system_state`, and `bootstrap_admin_user` primitives. Safe by default: aborts with explicit remediation on `drifted`, `partial_non_auth`, `schema_missing`, and `no_connection` states rather than attempting auto-repair. Flags: `--dry-run` (print plan without changes), `--skip-seed`, `--admin-email` / `--admin-password` (also via `OUTLABS_AUTH_BOOTSTRAP_*` env vars), `--format text|json`. Same exit-code semantics as doctor (`0`/`1`/`2`). Runs a final doctor pass on success to confirm the healthy end state. Idempotent: re-running against a healthy schema is a safe no-op. Covered by 30 new tests in `tests/unit/test_cli_bootstrap.py`, wired into the release-gate workflow.

## [0.1.0a18] - 2026-04-22

Async/perf pass across the auth data plane. Full test suite (745 tests) green.

### Performance

- **Login: Argon2id offload + flush batching.** `login` now runs Argon2id verify (~20 ms per call) on `asyncio.to_thread` and batches the last-login flush into the commit. Login p95 under concurrent load dropped roughly 40x on the local baseline. Argon2 parameters retuned to OWASP 2023 minimums.
- **`AccessScopeService.resolve_for_user`: 3 queries → 1.** Root, direct-membership, and closure-table lookups collapsed into a single CTE + LEFT JOIN via `_resolve_user_scope_inputs`. Saves 1 round trip on the hydrated-user path, 2 when `user=None`.
- **API-key `_check_ip`: 2 queries → 1.** `COUNT` + `SELECT` pair replaced with a single `SELECT ip_address`. Empty list → allow-all; otherwise membership is checked in memory.
- **Policy engine `matches` operator: compiled regex cache.** ABAC `matches` conditions now go through `functools.lru_cache(maxsize=1024)` via a module-level `_compile_regex` helper. Invalid patterns still fail closed.
- **Snapshot auth check: `asyncio.gather` for multi-permission routes.** `_try_api_key_auth_snapshot` parallelizes when a route declares multiple required permissions. Safe because the path is pure CPU + Redis — no `AsyncSession` work.

### Fixed

- **Fire-and-forget background tasks now have an error path.** `ActivityTracker.track_activity_detached()` and `NotificationService.emit()` retain their `asyncio.create_task` handles in an instance-level set and attach a `done_callback` that logs exceptions structurally. Callers in `services/auth.py` and `dependencies/__init__.py` use the detached helper so no background task escapes observability.
- Simple example contract: dropped a stale `integration_principals` assertion that fired after the fixture stopped seeding them.

### Intentionally reverted after measurement

Three thread-offload refactors were implemented, measured, and reverted in this pass because `asyncio.to_thread` has ~35 μs of scheduling overhead and the target ops cost well under that threshold:

- Fernet encrypt/decrypt for OAuth token encryption (~8–12 μs sync).
- API-key SHA-256 hash on the verify path (~0.4 μs sync).
- JWT HS256 encode/decode in service tokens and `utils/jwt.py` (~13 μs / ~19 μs sync).

See [docs/NEXT_PASS_BACKLOG.md](docs/NEXT_PASS_BACKLOG.md) → "Measurement rule" for the cost table and the rule of thumb: **only offload sync CPU when the op costs >> 100 μs.**

## [0.1.0a17] - 2026-04-21

Route-level perf slice (2026-04-12 pass). See [docs/NEXT_PASS_BACKLOG.md](docs/NEXT_PASS_BACKLOG.md) → "Release-Ready Auth Perf Slice" for the full list. High-level wins:

- `/v1/users/me`: 2 queries → 1 (`root_entity` eager-loaded on JWT-authenticated user resolution).
- `/v1/roles/entity/{entity_id}`: entity type + ancestor chain resolved in a single query.
- Lean permission-resolution path for the common non-ABAC, non-context-aware-role case: `check_permission(...)` 14 → 8 queries, `get_user_permissions(...)` 13 → 7 queries.
- Removed route-level N+1s on `/v1/users/{id}/permissions` (batched role permission loading) and `/v1/entities/{id}/members` (`get_entity_members_with_users(...)`).
- API-key permission projection + batched response shaping for the non-ABAC case; personal `authorize_api_key(...)` drops from ~22 queries unanchored / ~27 anchored into that faster path, and the self-service and admin inventory routes benefit in turn.
- Lazy access-scope member projection: `resolve_for_auth_result(..., include_member_user_ids=False)` skips the extra member-user lookup when callers only need entity/root scope; descendant expansion is reused rather than re-expanded.
- Checked-in query-budget regression coverage for `/v1/users/me`, `/v1/roles/entity/{entity_id}`, enterprise permission hot paths, `/v1/users/{id}/permissions`, `/v1/entities/{id}/members`, non-superuser `/v1/roles/`, and the personal / system API-key authorization and inventory surfaces.

[0.1.0a18]: https://github.com/outlabsio/outlabsAuth/compare/v0.1.0a17...v0.1.0a18
[0.1.0a17]: https://github.com/outlabsio/outlabsAuth/compare/v0.1.0a16...v0.1.0a17
