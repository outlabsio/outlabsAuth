# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is in alpha (pre-1.0); breaking changes are allowed between alpha releases.

## [0.1.0a24] - 2026-07-15

### Security and robustness

- **OAuth authorization responses are now browser-bound and single-use.** Signed state claims are
  backed by a short-lived server-side record and a binding cookie; callbacks reject replayed,
  expired, or cross-browser state. OAuth account association applies the same check.
- **Refresh-token rotation now detects reuse.** Tokens are tracked as a family, each refresh token
  may be used once, and reuse revokes the affected user's active token families.
- **Service tokens are isolated from human JWTs.** They use a separate derived signing key and now
  require issuer, audience, token ID, and a bounded lifetime (30 days maximum).
- **API-key protection fails closed when configured Redis rate limiting is unavailable.** Requests
  receive a retryable 503 rather than silently bypassing the configured rate limit. Redis key,
  scan-pattern, and pub/sub channel names are also consistently namespaced.
- **Background maintenance is explicit by default.** Embedded schedulers are disabled unless opted
  in; operators can instead run one deterministic cycle with `outlabs-auth run-maintenance`.

### Performance and correctness

- **API-key usage sync is durable across worker failures.** Counter batches are staged in Redis,
  recorded with an idempotency receipt in PostgreSQL, and acknowledged only after a successful
  commit, preventing usage loss or double-counting on retry.
- **Current production dependency minimums and lockfile are refreshed.** Release CI now performs a
  production-only dependency vulnerability audit.

### Database migrations

- **`20260715_0019_add_api_key_usage_sync_batches`** adds idempotency receipts for durable API-key
  usage synchronization.
- **`20260715_0020_add_refresh_token_families`** adds refresh-token family and replacement fields
  required for single-use rotation and reuse detection.
- Apply with `auto_migrate=True`, `outlabs-auth bootstrap`, or `outlabs-auth migrate` before
  deploying code that enables the new behavior. Rehearse both migrations against a populated
  staging copy before production rollout.

### Fixed

- **Write commits now complete before the response reaches the client (read-your-writes).**
  `OutlabsAuth.uow` committed in dependency teardown, which FastAPI (>=0.106) runs only after the
  response has been sent — so a client could receive its 201 and race the commit with an immediate
  dependent request (observed in CI as a 404 for a role created by the preceding request, Release
  Readiness run 27383495356). A new pure-ASGI `UnitOfWorkMiddleware` — installed unconditionally by
  `instrument_fastapi()` — now finalizes the unit of work just before `http.response.start` is
  forwarded: commit for write methods, rollback for reads, exactly once per request (teardown only
  finalizes as a fallback when the middleware is not installed, preserving the legacy
  response-then-commit behavior for un-instrumented apps). Service-level cache-version bumps still
  happen during the handler, so the bump-before-commit invalidation ordering from the 2026-06
  performance audit is unchanged. Two deliberate side effects: a commit failure now aborts the
  response (the client gets a 500 instead of a success status for data that was never persisted),
  and Starlette background tasks now run after the commit instead of before it. The read-after-create
  polling barriers (`confirm_visible`) carried by `scripts/smoke_enterprise_api.py` and
  `examples/enterprise_rbac/api_integration_check.py` as a workaround are removed — the release gate
  asserts immediate visibility again, and a regression test drives the ASGI app by hand to assert the
  created row is visible from a second DB connection at the moment the client has the response
  (`tests/integration/test_uow_commit_before_response.py`).
- **The SimpleRBAC example now actually installs the library middleware.**
  `examples/simple_rbac/main.py` called `instrument_fastapi()` inside lifespan — after the app had
  started — so Starlette rejected every middleware add and the example booted with a UserWarning and
  the legacy response-then-commit ordering. The example now constructs `SimpleRBAC` and calls
  `instrument_fastapi()` at module level (mirroring the EnterpriseRBAC example), so
  `UnitOfWorkMiddleware`, `RequestCacheMiddleware`, and `ResourceContextMiddleware` install cleanly.
  Its blog routes also now enforce the permissions their docstrings always claimed
  (`post:create/update/update_own/delete`, `comment:create/delete/delete_own`): `author_id` comes
  from the authenticated principal instead of an all-zeros placeholder, and the `_own` variants are
  gated by ownership checks. Its `reset_test_env.py` was also unblocked: the hardcoded
  password-hashing secret was shorter than the 32-character HS256 minimum introduced in 0.1.0a23 and
  crashed the script on startup.

## [0.1.0a23] - 2026-06-11

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

Phase 3 (permission-resolution algorithmics + event-loop hygiene):

- **Request-scoped memoization of the membership graph.** Multi-permission dependencies
  (`require_permission("a", "b", ...)`, stacked checks, `POST /permissions/check`) re-enter the
  permission service once per name; the UserRoleMembership / EntityMembership eager-loads (and
  per-role context name sets, ABAC role conditions, condition-group operators) are now memoized for
  the request — every check after the first is SQL-free (previously ~10 queries per additional name
  on an entity route). Memos are keyed by the request's session (ORM rows never outlive it) and are
  dropped by every permission-affecting mutation, so a mutation observes its own change within the
  same request. Pinned by `tests/integration/test_request_memo_query_counts.py`.
- **`POST /permissions/check` is one graph load.** The endpoint now delegates to
  `get_effective_permission_names` (in-memory matching over the aggregated set) instead of a full
  `check_permission` round per requested name.
- **Condition-less ABAC deployments take the fast path.** With `enable_abac=True` but zero authored
  conditions (a common rollout state), evaluation is vacuously RBAC-only — checks now fall through to
  the non-ABAC path and its caches instead of paying the per-role condition-loading tax. The "any
  conditions exist?" flag is request-memoized and Redis-cached against the global version counter,
  which every condition mutation bumps. `get_effective_permission_names` applies the same gate, so
  its ABAC fan-out (one full check per candidate name) only runs when conditions actually exist.
- **Membership validity windows filter in SQL.** `valid_from`/`valid_until` predicates (matching
  `is_currently_valid()`, which still runs) keep expired memberships from triggering the full
  role+permission eager-load only to be discarded in Python.
- **ABAC evaluation cost trims**: the stateless `PolicyEvaluationEngine` is a module singleton
  (was constructed per check), and AND/OR condition groups short-circuit at the first
  decisive result (previously every condition in a group was evaluated and materialized).
- **Notification channels no longer block the event loop.** The synchronous Twilio (SMS/WhatsApp)
  and SendGrid SDK calls — blocking HTTPS that stalled *every* in-flight request for 100ms-1s+ per
  send — now run via `asyncio.to_thread`. The webhook channel and the SendGrid/Mailgun/webhook
  transactional-mail providers reuse a pooled `httpx.AsyncClient` (was a fresh client + TCP/TLS
  handshake per message; closed via the new `aclose()` seam in `OutlabsAuth.shutdown()`), and the
  RabbitMQ channel resolves its exchange once instead of per publish. Pinned by
  `tests/unit/services/test_channels_async.py`.

Phase 4 (write paths, schema, observability):

- **Index hygiene (migration `20260611_0018`).** Verified against the rendered DDL: `api_keys.prefix`
  carried **three** identical btrees and `refresh_tokens.token_hash` two (every login maintained
  both); `permissions.name`/`permission_tags.name` duplicated their unique constraints; the closure
  table and both membership tables carried single-column indexes fully covered by composite
  prefixes. All dropped — pure write amplification removed from the hottest-write tables. Added:
  partial indexes on `users.password_reset_token` / `users.invite_token` (reset/invite are
  unauthenticated, attacker-reachable lookups that previously **sequentially scanned the users
  table** per attempt) and `permission_tag_links.tag_id`.
- **Bulk membership archival batched.** Archiving an entity's memberships cost ~9 queries per
  membership (two ~4-query history snapshots, a user SELECT, and a flush per row — ~9,000 statements
  in one transaction for 1,000 members). The batch now shares one closure-context query and one user
  `IN` fetch, passes precomputed snapshots into the history writer, and flushes inserts together:
  measured 14 memberships in 33 queries vs ~126 before
  (`tests/integration/test_bulk_write_query_counts.py`). Same treatment for user-deletion membership
  revocation.
- **Background syncs batched.** API-key usage sync consumes counters with pipelined atomic `GETDEL`
  (the old GET→DELETE silently dropped increments landing in between), MGETs `last_used` timestamps,
  and applies one executemany UPDATE — was a SELECT + single-row flush + 2 Redis ops per key.
  Activity sync MGETs each SCAN page and bulk-updates `users.last_activity` — was one GET + one
  SELECT + one UPDATE per active user (≈30k round trips per cycle at 10k DAU).
- **Role/permission definition edits stop rebuilding snapshots a third time.** History events reuse
  the caller-computed post-mutation snapshot (a role edit previously ran the ~7-query snapshot
  build three times, ~27 queries per admin edit).
- **SQL-side pagination.** User search pushes `OFFSET/LIMIT` + `COUNT(*)` into SQL (previously
  fetched up to 1,000 full rows to slice a page of 20, with a wrong total beyond the cap);
  `get_roles_for_entity` filters `assignable_at_types` in SQL (`unnest` + `lower()` parity with the
  Python matcher) and paginates with `COUNT`/`OFFSET`/`LIMIT` instead of eagerly loading every
  matching role.
- **Observability**: HTTP error metrics label by route template (`/users/{user_id}`) instead of the
  concrete path — concrete IDs minted a new Prometheus series per distinct value that ever errored
  (unbounded registry growth under scanners); structured log emits below the configured level now
  skip payload construction and JSON serialization entirely.

### Fixed

- **`POST /permissions/check` now honors `entity_id`.** The schema has always advertised an optional
  entity context, but the endpoint silently ignored it and answered from the user's global aggregate.
  With `entity_id` set, checks are now evaluated within that entity (direct membership grants plus
  tree permissions inherited from ancestors), matching `check_permission` semantics; malformed ids
  return 400. **Behavior change** for clients that were already sending the field — they previously
  received global-scope answers.
- **Cache-invalidation listener no longer dies permanently on the first Redis error.** The DD-037
  pub/sub listener had no error handling: one `ConnectionError` killed the task silently and the
  instance stopped reacting to invalidation messages for its lifetime. It now resubscribes with
  capped backoff, and unexpected task death is logged.
- **Rate-limit window counters are atomic.** `increment_with_ttl` was INCR-then-EXPIRE; if the EXPIRE
  never landed (crash/timeout between the two), the window key never expired and that API key or
  email stayed rate-limited forever. The window is now established atomically (`SET NX EX` + `INCRBY`
  in one pipeline), and legacy TTL-less counters are healed on their next increment.
- **ABAC condition and condition-group CRUD now invalidate the permission cache.** All six
  permission-side condition/group mutation methods previously performed no invalidation, leaving
  stale ABAC verdicts cached for up to the 15-minute TTL after a condition change. Phase 3 closed
  the same gap in the six **role-side** condition/group CRUD methods (`RoleService.create/update/
  delete_role_condition[_group]`), whose global bump also keeps the new "conditions exist" flag
  honest.

### Compatibility notes (hosts integrating below the router layer)

- **REST API: no contract changes.** Request/response shapes are unchanged across all routers
  (user-search totals are now *correct* beyond 1,000 matches, which is a fix, not a break).
- **BREAKING for direct `CacheService` callers:** `get_permission_check` now returns
  `(result, versions)` instead of a bare bool, and `set_permission_check` requires a `versions`
  token (writes without one are refused). `PermissionService` shims host-*supplied* cache services
  with the legacy contract, but host code *calling* `CacheService` directly must update.
- **Redis floor: 6.2.** The API-key counter sync uses `GETDEL`; on older servers the sync logs a
  failure and counters are not consumed. The opt-in helpers added this cycle (MGET validation,
  pipelines) work on any modern Redis.
- **Library versions older than this release cannot run migrations against a database already at
  `20260611_0018`** (standard Alembic: unknown revision). Roll out the library before or together
  with the migration, and don't leave old instances running `auto_migrate=True`. Old code merely
  *running* against the migrated schema is fine — the migration is index-only.
- **Monitoring-visible:** HTTP error metrics now label `endpoint` with the route template
  (`/users/{user_id}`); dashboards filtering on concrete paths need their queries updated.
- The pub/sub invalidation channel is still published, but subscribed instances no longer
  SCAN-delete on messages (shared entries are version-validated). The DD-033 usage sync worker now
  starts automatically; a host that also starts one manually just runs a redundant (safe) second
  worker.
- Permission caching assumes mutations flow through the library's services. Rows mutated via raw
  SQL won't invalidate cached permission sets until the TTL (15 min default) expires.

### Database migrations

- **New Alembic revision `20260611_0018_index_hygiene`** (index-only — no table or column changes,
  no data migration). Drops the duplicate/prefix-redundant indexes listed under Performance Phase 4
  and creates `ix_users_password_reset_token` (partial), `ix_users_invite_token` (partial), and
  `ix_permission_tag_links_tag_id`. Applied automatically with `auto_migrate=True`, or run
  `outlabs-auth bootstrap` / the packaged Alembic migrations before upgrading app instances. The
  migration is idempotent (existence-checked) and safe to run online; index creation is
  non-concurrent, so on very large `users` tables expect a brief write lock while the two partial
  indexes build. Downgrade restores the dropped indexes (except the redundant column-level unique
  constraints, which carried no semantics).
- DD-056 itself uses existing tables; `enforce_user_scope` and `api_key_usage_sync_interval` are
  config flags only.

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
