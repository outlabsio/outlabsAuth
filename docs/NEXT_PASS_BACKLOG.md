# Next Pass Backlog

**Updated**: 2026-04-22
**Purpose**: Lightweight maintainer backlog for known follow-up work that is too current or too small to keep re-threading through the larger roadmap.

This document is intentionally short. It is not a full project plan and it does not replace [IMPLEMENTATION_ROADMAP.md](/Users/macbookm3/Documents/projects/outlabsAuth/docs/IMPLEMENTATION_ROADMAP.md). It is a working list of already-known follow-ups that came out of real integration, deployment, and performance work.

## Release-Ready Auth Perf Slice

This slice is now implemented locally and verified against the full repo test suite on 2026-04-12 (`712 passed`).

- Reduce `/v1/users/me` from 2 queries to 1 by eager-loading `root_entity` during JWT-authenticated user resolution.
- Reduce `/v1/roles/entity/{entity_id}` round trips by resolving entity type and ancestor chain in one query.
- Add a lean permission-resolution path for the common non-ABAC, non-context-aware-role case:
  - `check_permission(...)`: 14 queries down to 8
  - `get_user_permissions(...)`: 13 queries down to 7
- Remove two obvious route-level N+1s:
  - `/v1/users/{id}/permissions` now batches role permission loading
  - `/v1/entities/{id}/members` now uses `get_entity_members_with_users(...)`
- Add an API-key permission projection and batched response-shaping path for the
  common non-ABAC case:
  - personal `authorize_api_key(...)`: about 22 queries unanchored, 27 queries
    for anchored tree checks
  - self-service `/v1/api-keys/`: about 22 queries for 2 keys
  - self-service `/v1/api-keys/grantable-scopes`: about 8 queries unanchored,
    11 queries anchored
  - admin inventory routes: about 12, 13, and 7 queries for the current seeded
    single-item surfaces
- Make access-scope member projection lazy for packaged role visibility checks:
  - `resolve_for_auth_result(..., include_member_user_ids=False)` now skips the
    extra member-user lookup when callers only need entity/root scope
  - descendant expansion is reused instead of being re-expanded during member
    projection
  - checked-in route budgets now include a non-superuser `/v1/roles/` scope path
- Keep checked-in regression/query-budget coverage for:
  - `/v1/users/me`
  - `/v1/roles/entity/{entity_id}`
  - enterprise permission hot paths
  - `/v1/users/{id}/permissions`
  - `/v1/entities/{id}/members`
  - non-superuser `/v1/roles/`
  - personal API key authorization and self-service routes
  - system integration API key authorization and admin inventory routes
- Package this as the next auth library release instead of leaving it as repo-local optimization work.

## Bootstrap And Operator Tooling

Current packaged commands (`migrate`, `seed-system`, `bootstrap-admin`, `tables`, `current`) are usable, but the operator experience is still too manual for first-boot production deployments.

Known next-pass work:

- Add `outlabs-auth bootstrap`
  - verify DB connectivity
  - verify schema target
  - detect empty vs healthy schema
  - run safe bootstrap/migration steps in the correct order
- Add `outlabs-auth doctor`
  - detect empty schema
  - detect partially bootstrapped schema
  - detect schema/search-path misconfiguration
  - produce explicit repair guidance
- Move first-boot operational ownership toward the library CLI instead of host-app runtime glue.
- Keep multi-worker apps on the recommended pattern:
  - CLI/bootstrap in prestart or release step
  - application workers start only after that succeeds

## Runtime Performance Follow-Ups

First data-plane auth slices implemented on 2026-04-20:

- `AuthDeps.require_permission(...)` now checks a Redis-backed API-key auth
  snapshot before running the DB-backed strategy path when ABAC is off.
- `auth.authorize_api_key(..., required_scope=...)` now uses the same snapshot
  for non-ABAC calls that do not pass a request entity context.
- The snapshot is intentionally limited to non-entity authorization surfaces for
  these slices, matching SimpleRBAC worker routes and avoiding closure-table
  correctness risk until entity/tree projections are compiled too.
- Warm SimpleRBAC dependency-path smoke result:
  `simple_user_api_key_dependency_global` dropped to 0.00 SQL queries/request in
  Redis cache mode after one warmup request.
- Warm SimpleRBAC direct-helper smoke result:
  `simple_user_api_key_global` now also drops to 0.00 SQL queries/request in
  Redis cache mode after one warmup request.
- Snapshot correctness is no longer only TTL-bounded. Cached API-key auth
  snapshots now include Redis epoch versions for global RBAC state, user state,
  integration-principal state, and entity state. Role/permission/membership
  changes bump the relevant existing cache invalidation epochs, while user
  status, integration-principal, and API-key lifecycle changes invalidate their
  dependent snapshots directly.
- The cached direct-helper result is intentionally host-safe: it preserves the
  authorization result shape, but does not rehydrate live SQLAlchemy user,
  principal, or API-key models from Redis.

Current local benchmark snapshot after the snapshot slices:

```bash
uv run python scripts/benchmark_auth_paths.py \
  --presets simple,enterprise \
  --redis-modes off,cache \
  --redis-url redis://:guest@localhost:6379/0 \
  --iterations 25 \
  --warmup 3 \
  --concurrency 10 \
  --commit-usage \
  --no-service-tokens
```

| scenario | off q/req | cache q/req | off p95 ms | cache p95 ms |
|---|---:|---:|---:|---:|
| `simple_user_api_key_global` | 12 | 0 | 80.92 | 8.53 |
| `simple_user_api_key_dependency_global` | 17 | 0 | 106.78 | 4.49 |
| `enterprise_personal_api_key_unanchored` | 14 | 0 | 89.03 | 14.40 |
| `enterprise_personal_api_key_dependency_unanchored` | 21 | 0 | 144.10 | 5.00 |
| `enterprise_personal_api_key_anchored_tree` | 19 | 0 | 91.45 | 7.34 |
| `enterprise_system_api_key_global` | 9 | 0 | 42.38 | 4.86 |
| `enterprise_system_api_key_entity_tree` | 11 | 0 | 49.40 | 6.67 |

Known hot-path areas worth another pass after the next release:

- Tighten entity-relation invalidation beyond the current versioned relation-key
  strategy once production mutation patterns are clearer.
- Add explicit fast-deny semantics for cached negative entity/permission checks
  if denied hot paths show up in production traces.
- Keep tightening invalidation granularity where global role/permission changes
  can eventually be narrowed to affected principals/users instead of bumping the
  global RBAC epoch.
- Audit remaining enterprise admin routes that still perform multiple auth/member/entity round trips:
  - `/v1/memberships/me`
  - `/v1/entities/{id}`
  - `/v1/entities/{id}/path`
  - `/v1/entities/{id}/descendants`
- Keep query-budget tests aligned with the real optimized route behavior.
- Add one small, explicit maintainer benchmark note for “expected query counts on hot admin routes” so regressions are easier to spot before downstream apps feel them.
- If that shape is kept reusable, add a small benchmark/query-budget note for
  scope resolution with and without member-user expansion so host integrations
  can reason about the tradeoff before rebuilding local workarounds.

### Benchmarking And Permission-Resolution Audit

- Keep building toward a checked-in benchmark suite for EnterpriseRBAC hot paths
  using seeded enterprise data and real API requests, not only direct service
  calls.
- Cover at least:
  - direct RBAC permission checks
  - entity-local permission checks
  - ancestor `_tree` permission checks
  - `get_user_permissions`
  - access-scope resolution
  - representative admin/API routes for regular RBAC users and superusers
  - API key authorization flows
- Record both SQL query counts and request/service latency for each scenario so
  the next release has a concrete baseline before optimization work starts.
- Current checked-in coverage after this slice:
  - `tests/integration/test_enterprise_permission_query_counts.py`
  - `tests/integration/test_enterprise_route_query_counts.py`
  - `tests/integration/test_enterprise_api_key_query_counts.py`
  - `tests/integration/test_enterprise_api_key_admin_query_counts.py`
- Keep non-superuser query-budget coverage explicit. Current route-budget tests
  can look artificially cheap when authenticated as a superuser because the
  normal permission-resolution path is bypassed.
- Validate the closure-table path explicitly before planning broader changes.
  Current findings suggest the closure table is doing the hierarchy part it was
  meant to do; the larger cost is the fixed ORM graph-loading around permission
  resolution, not ancestor lookup itself.
- Add a small maintainer note with current observed baselines from ad hoc local
  measurements so future work starts from real numbers:
  - `check_permission(...)` global/no-entity: 8 queries after the lean loader path
  - `check_permission(...)` entity-direct: 8 queries after the lean loader path
  - `check_permission(...)` ancestor-tree grant: 8 queries after the lean loader path
  - `get_user_permissions(...)`: 7 queries after the lean loader path
  - warm cached personal `authorize_api_key(...)` unanchored grant: 0 queries
  - warm cached personal `authorize_api_key(...)` anchored tree grant: 0 queries
  - `GET /v1/api-keys/`: about 22 queries for 2 keys
  - `GET /v1/api-keys/grantable-scopes`: about 8 queries unanchored, 11 anchored
  - `GET /v1/admin/entities/{id}/api-keys`: about 12 queries
  - `resolve_for_user(...)`: 2 queries after the CTE collapse (1 scope + 1 member projection); was ~5 before
  - non-superuser `GET /v1/roles/`: about 14 queries on the current seeded path
  - `GET /v1/entities/{id}`: 1 query as superuser vs 7 queries as regular RBAC user
- Prioritize investigation of the current fixed query tax in permission
  resolution:
  - eager loading of role permissions, role conditions, permission conditions,
    and entity-type overrides even when ABAC/context-aware-role features are
    off
- API-key policy no longer needs a separate repo-local permission projection
  workaround in the common non-ABAC case; remaining API-key perf follow-ups
  should focus on:
  - mutation/invalidation cost after role and membership churn
  - anchored-key denied-entity and deep-tree scaling behavior
  - ABAC-enabled API-key grant/runtime budgets, which still intentionally fall
    back to the slower conditioned permission path
- Access-scope member projection is now opt-in on the packaged path, so the
  next access-scope follow-up should be broader host-facing adoption:
  - audit whether other consumers actually need `member_user_ids`
  - extend the lazy/explicit pattern to host-facing integrations before adding
    more route-local workarounds
- Remaining route-level follow-ups should be evaluated from fresh query-budget
  output rather than the now-fixed `users/{id}/permissions` and
  `entities/{id}/members` hotspots.
- Reconcile roadmap/docs claims about existing benchmark coverage with what is
  actually checked into the repo so release planning is based on the current
  test surface, not stale documentation.

## Production Docs And Runbooks

The README now has the correct production defaults, but some operator guidance still deserves a tighter pass:

- Keep documenting the recommended runtime baseline:
  - direct `postgresql+asyncpg://...` URL
  - explicit auth schema such as `outlabs_auth`
  - `auto_migrate=False` during normal runtime
  - Redis enabled for enterprise/admin-heavy apps
- Add a short first-boot/cutover example that shows:
  - CLI migration
  - system seeding
  - optional bootstrap admin
  - app startup after bootstrap
- Document common failure modes more explicitly:
  - transaction-pooler latency
  - missing schema search path
  - empty auth schema on first deploy
  - multi-worker startup migration races

## UI / Consumer Adoption Gaps

These are known ecosystem follow-ups, not core auth-library blockers:

- External admin UI should adopt the newer enterprise API key and integration-principal surfaces.
- Add Playwright coverage in the UI repo when those newer surfaces are actually in use.
- Keep consumer examples validating the packaged wheel path, not repo-local editable assumptions.

## Sync-In-Async Audit Follow-Ups (2026-04-22)

**Context**: Login was taking 2–3 seconds under production concurrency. Root cause
was Argon2id hashing (~20ms per verify) running synchronously on the event loop.
Commit `ece5095` fixed login by offloading Argon2 to `asyncio.to_thread(...)`,
retuning Argon2 to OWASP 2023 minimums, and batching flushes into the commit.
Login p95 under concurrency dropped roughly 40x on the local baseline.

The items below came out of sweeping the rest of the auth data plane for
similar patterns (sync CPU, sync crypto, sequential independent awaits, chatty
flushes). The key lesson from this pass — written up front because it changed
several of the findings — is the measurement rule below.

### Measurement rule: when does thread offload actually win?

`asyncio.to_thread(...)` has ~35μs of scheduling overhead (loop hop, executor
submit, future resolution). Offloading a sync op to a thread is only a win when
the sync op cost is >> that overhead. Concretely:

| Operation | Sync cost | to_thread cost | Verdict |
|---|---:|---:|---|
| Argon2id verify | ~20 ms | ~35 μs | ✅ Offload wins ~600x |
| Fernet encrypt | 11.5 μs | ~35 μs | ❌ Offload LOSES 3x |
| Fernet decrypt | 8.4 μs | ~35 μs | ❌ Offload LOSES 4x |
| SHA-256 (API key) | 0.4 μs | ~35 μs | ❌ Offload LOSES 90x |
| JWT HS256 encode | ~13 μs | ~35 μs | ❌ Offload LOSES 2.7x |
| JWT HS256 decode | ~19 μs | ~35 μs | ❌ Offload LOSES 1.8x |

**Rule of thumb: only offload sync CPU when the op costs >> 100 μs.** On this
codebase, Argon2 is the only thing that qualifies. Everything else is better
left sync — the offload costs more than it saves and it also burns worker
threads that other code paths (DB driver, actual Argon2 work) may need.

This rule is what made us revert the original P1.1 and P1.2 offloads below
after measuring them. Treat it as a default when evaluating any future
"unblock the event loop" task in this codebase.

### P1 — what actually landed after measurement

**Status (2026-04-22)**: P1 pass re-evaluated. Full suite (745 collected) green.

- **Fernet offload for OAuth token encryption** — ❌ REVERTED
  - Was originally implemented as `encrypt_async` / `decrypt_async` on
    `FernetCipher` + an async `encrypt_provider_token` helper. Subsequent
    measurement showed Fernet encrypt/decrypt at ~8–12 μs, well below the
    ~35 μs to_thread overhead. Net loss per call.
  - Reverted across
    [utils/crypto.py](outlabs_auth/utils/crypto.py),
    [routers/oauth_utils.py](outlabs_auth/routers/oauth_utils.py),
    [routers/oauth.py](outlabs_auth/routers/oauth.py),
    [routers/oauth_associate.py](outlabs_auth/routers/oauth_associate.py),
    [tests/unit/test_oauth_utils.py](tests/unit/test_oauth_utils.py).

- **API-key SHA-256 offload on the verify path** — ❌ REVERTED
  - `APIKey.hash_key_async` was removed after measurement showed SHA-256
    over a short API key at ~0.4 μs — the offload made the verify path ~90x
    slower. Reverted across
    [models/sql/api_key.py](outlabs_auth/models/sql/api_key.py) and
    [services/api_key.py](outlabs_auth/services/api_key.py).

- **`_check_ip` query collapse** — ✅ KEPT (real DB win, unrelated to offload)
  - [services/api_key.py](outlabs_auth/services/api_key.py) `_check_ip`
    collapsed from two queries (COUNT, then SELECT-for-row) to a single
    `SELECT ip_address` that returns all whitelist entries; empty list →
    allow-all, otherwise in-memory membership check. Saves one real DB
    round trip per IP-whitelisted key authentication.

- **`AccessScopeService.resolve_for_user` CTE collapse** — ✅ DONE
  - [services/access_scope.py](outlabs_auth/services/access_scope.py)
    `resolve_for_user` was 3 sequential queries (root → direct → closure).
    Replaced with a single `_resolve_user_scope_inputs` method that unions
    the root seed (hydrated literal when possible, else a `User` lookup)
    with direct memberships as a CTE, LEFT JOINed against `entity_closure`
    when hierarchy is enabled. Saves 1 round trip on the hydrated-user
    path and 2 round trips when `user=None`. The two helpers
    `_resolve_root_entity_ids` / `_resolve_direct_entity_ids` were
    deleted; [tests/unit/services/test_access_scope.py](tests/unit/services/test_access_scope.py)
    updated to monkeypatch the new combined method.

- **`verify_api_key` broader short-circuit flatten** — ⚠️ STILL DEFERRED
  - Same `AsyncSession` constraint blocks naive `gather` across the status /
    expiry / IP / rate-limit / owner / entity checks. Preserving per-reason
    `_log_api_key_validation` labels and "first failing reason wins" semantics
    rules out run-all-then-pick. A real win would mean combining more of these
    into a single SQL round trip (status + owner + entity via a JOIN) — that
    is an architectural refactor, not a drop-in gather.
  - `validate_runtime_use` in
    [services/api_key_policy.py](outlabs_auth/services/api_key_policy.py)
    has up to three sequential `session.get(...)` calls
    (principal/owner → entity). They are conditionally dependent (entity
    only checked after owner passes), so combining them means loading
    eagerly even when owner is rejected, or restructuring the policy
    method entirely. Defer until traces show it.

### P2 — landed in this pass

- **JWT encode/decode offload in service tokens** — ❌ SKIPPED
  - [services/service_token.py:111](outlabs_auth/services/service_token.py),
    line 150. Not implemented. Benchmark showed sync JWT encode at ~13 μs
    and decode at ~19 μs — both under the ~35 μs to_thread overhead. Same
    rule applies for the `utils/jwt.py` access/refresh token helpers. Leave
    all JWT ops sync; revisit only if we move to RS256 / ES256 (asymmetric
    signing is much more expensive and may cross the threshold).

- **Compile-cache regex in policy engine MATCHES operator** — ✅ DONE
  - Added module-level `_compile_regex(pattern)` with
    `functools.lru_cache(maxsize=1024)` in
    [services/policy_engine.py](outlabs_auth/services/policy_engine.py)
    and routed the `ConditionOperator.MATCHES` branch through it. Invalid
    patterns return `None` from the cache and fail the condition closed,
    matching the previous behavior. Bounded cache avoids unbounded growth
    on user-supplied patterns.

- **Snapshot permission check `asyncio.gather`** — ✅ DONE
  - `_try_api_key_auth_snapshot` in
    [dependencies/__init__.py](outlabs_auth/dependencies/__init__.py)
    now uses `asyncio.gather` when multiple permissions are declared on a
    route. Single-permission path stays as a plain await (no gather
    overhead when there's nothing to parallelize). Safe because this path
    is pure CPU + Redis — it does not touch the `AsyncSession`, so the
    constraint that blocks other gather work does not apply.

- **Entity-creation `session.flush()`** — ⚠️ REVIEWED, KEPT AS-IS
  - [services/entity.py:952](outlabs_auth/services/entity.py). The trailing
    flush after closure-table inserts could be removed to batch into the
    commit, but entity creation is an admin operation (not a hot path),
    the savings are ~1 round trip, and the current flush provides early
    constraint-violation detection before the caller continues. Not worth
    the correctness risk on a low-traffic path. Decision documented here
    so the next audit does not re-open it.

### P3 — nice-to-have

- **Fire-and-forget background tasks have no error path** — ✅ DONE (commit `c9bfe16`)
  - `ActivityTracker` now exposes `track_activity_detached()` and
    `NotificationService.emit()` both track their `asyncio.create_task`
    handles in an instance-level set with `task.add_done_callback(...)`
    that logs exceptions structurally. Callers in `services/auth.py` and
    `dependencies/__init__.py` were migrated to the detached helper so no
    fire-and-forget task escapes observability any more.

- **API key auth snapshot dict construction is hot on the serialize path**
  - [services/api_key.py](outlabs_auth/services/api_key.py) lines 910–932.
    Snapshot dict rebuilt from scratch on every miss. Only worth touching
    if cold-start snapshot construction shows up in the benchmark.

- **Regex compile at entity validation**
  - [services/entity.py:869](outlabs_auth/services/entity.py). Lift slug /
    name validation pattern to a module-level `_SLUG_RE`. Same shape as
    the policy engine fix.

### Deferred architectural work (for a future session with fresh context)

The items below did not land in this pass because they are real architectural
refactors, not drop-in async fixes. They are parked here with enough detail
that a later session can pick them up cold.

1. ~~**Combine `AccessScopeService.resolve_for_user` direct + closure into one query.**~~
   - ✅ Landed in this pass. `_resolve_user_scope_inputs` CTE replaces the
     three sequential queries; tests rewritten against the combined shape.
     Integration suite (292 tests, including real-DB roles scope paths)
     passes green.

2. **Flatten the `verify_api_key` short-circuit chain into fewer queries.**
   - File: [services/api_key.py](outlabs_auth/services/api_key.py) around
     `verify_api_key` and `_check_ip`/`_check_status`/`_check_expiry`/...
   - Goal: combine status + owner + entity-scope lookups into a single
     SELECT with JOINs so the verify path makes ~2 round trips instead of
     the current ~5 in the worst case.
   - Blocker: preserving the current per-reason failure labeling in
     `_log_api_key_validation`. Today each check runs independently so the
     first failing reason wins; a single combined query needs a deterministic
     way to pick which reason to emit when multiple fail.
   - **Measurement guard: DO NOT pick this up without trace data.** Warm
     traffic already hits ~0 queries through the Redis snapshot layer, so
     the uncached path is the only possible target. A maintainer picking
     this up cold should first confirm the no-cache verify path actually
     shows up as a hot spot in production traces. If it does not, leave it
     deferred — the refactor cost (redesigning the check chain to preserve
     per-reason labels deterministically) is not justified by intuition.

3. **Restructure `validate_runtime_use` for fewer sequential `session.get(...)` calls.**
   - File: [services/api_key_policy.py:192](outlabs_auth/services/api_key_policy.py)
     (method spans ~90 lines).
   - Shape today: up to 2 sequential `session.get(...)` calls on the happy
     path (principal OR user, then optionally entity when `entity_id` is
     set). The backlog previously said "3" — that was counting the OR as
     two branches rather than two sequential awaits. Happy-path ceiling is
     2 round trips, reject-on-owner short-circuits at 1.
   - Goal: one LEFT JOIN query that pulls `User`/`IntegrationPrincipal`
     alongside the optional `Entity`. Save 1 round trip on the happy path
     when the key is entity-anchored.
   - Blocker: the conditional structure is load-bearing — the owner check
     legitimately gates whether the entity check runs. A combined query
     trades that for slightly more wasted work on the reject path (the
     entity join runs even when owner is rejected).
   - **Measurement guard: DO NOT pick this up without trace data.** The
     uncached API-key verify path is where this sits; warm traffic skips
     it entirely via the snapshot cache. A fresh session picking this up
     should first confirm it shows up in production traces. The code is
     contained (~45 min of work) but the measurement rule above still
     applies — we have already reverted three speculative perf refactors
     (Fernet, SHA-256, JWT offloads) in this pass. Do not add a fourth.

### How to verify changes in this area

- `uv run python benchmarks/bench_login.py` — login smoke on the async flow.
- `uv run python scripts/benchmark_auth_paths.py --presets simple,enterprise
  --redis-modes off,cache --iterations 25 --warmup 3 --concurrency 10
  --commit-usage --no-service-tokens` — per-request query counts and p95 on
  the API-key paths.
- `uv run pytest` — full suite must stay green. When touching session
  concurrency (any new gather involving DB reads), specifically re-run
  `tests/integration/test_enterprise_*` and the query-budget tests; those
  will catch "operation already in progress" races.

### Intentionally NOT on this list

- Argon2 tuning and login flush batching — shipped in `ece5095`.
- Broader snapshot/cache invalidation tightening — tracked under
  "Runtime Performance Follow-Ups" above.
- Re-trying any of the reverted thread offloads (Fernet, SHA-256, JWT)
  without a CPU profile showing a concrete hot spot that crosses the
  ~100 μs offload threshold. The measurement rule above takes precedence
  over intuition.

### Lesson learned from this pass

Two separate lessons:

1. **`asyncio.to_thread` is not free.** It has ~35 μs of scheduling
   overhead. Any offload candidate must be measured, not assumed — on
   this codebase only Argon2 qualified. See the measurement rule above.

2. **Naive `asyncio.gather(session.execute(...), session.execute(...))`
   on the same `AsyncSession` is unsafe.** SQLAlchemy's async session only
   permits one task at a time. Parallelization involving DB reads must
   either (a) combine queries (CTE / UNION / JOIN), (b) use separate
   sessions per parallel task, or (c) only parallelize CPU/Redis work
   that does not touch the session (this is what the snapshot gather
   does).

The real latency wins in this broader pass came from the original login
Argon2 offload + flush batching (in `ece5095`) and the `_check_ip` query
collapse — not from the speculative offloads or parallelizations that the
original P1 scope proposed.

## Intentional Deferrals

These are known and accepted for now:

- No first-class `bootstrap` / `doctor` CLI yet.
- No broader admin-route perf benchmark suite beyond the current query-budget tests.
- No guarantee yet that every downstream host app is using the optimized production defaults unless they follow the current docs.
