# Next Pass Backlog

**Updated**: 2026-04-12
**Purpose**: Lightweight maintainer backlog for known follow-up work that is too current or too small to keep re-threading through the larger roadmap.

This document is intentionally short. It is not a full project plan and it does not replace [IMPLEMENTATION_ROADMAP.md](/Users/macbookm3/Documents/projects/outlabsAuth/docs/IMPLEMENTATION_ROADMAP.md). It is a working list of already-known follow-ups that came out of real integration, deployment, and performance work.

## Release-Ready Auth Perf Slice

This slice is now implemented locally and verified against the full repo test suite on 2026-04-12 (`703 passed`).

- Reduce `/v1/users/me` from 2 queries to 1 by eager-loading `root_entity` during JWT-authenticated user resolution.
- Reduce `/v1/roles/entity/{entity_id}` round trips by resolving entity type and ancestor chain in one query.
- Add a lean permission-resolution path for the common non-ABAC, non-context-aware-role case:
  - `check_permission(...)`: 14 queries down to 8
  - `get_user_permissions(...)`: 13 queries down to 7
- Remove two obvious route-level N+1s:
  - `/v1/users/{id}/permissions` now batches role permission loading
  - `/v1/entities/{id}/members` now uses `get_entity_members_with_users(...)`
- Keep checked-in regression/query-budget coverage for:
  - `/v1/users/me`
  - `/v1/roles/entity/{entity_id}`
  - enterprise permission hot paths
  - `/v1/users/{id}/permissions`
  - `/v1/entities/{id}/members`
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

Known hot-path areas worth another pass after the next release:

- Audit remaining enterprise admin routes that still perform multiple auth/member/entity round trips:
  - `/v1/memberships/me`
  - `/v1/entities/{id}`
  - `/v1/entities/{id}/path`
  - `/v1/entities/{id}/descendants`
- Keep query-budget tests aligned with the real optimized route behavior.
- Add one small, explicit maintainer benchmark note for “expected query counts on hot admin routes” so regressions are easier to spot before downstream apps feel them.
- Add a shared cheap permission-name resolution path for embedded hosts so
  downstream apps do not need repo-local SQL projections just to avoid the
  heavier full permission graph-loading path on hot requests.
- Revisit whether generic descendant scope resolution should always broaden to
  full `member_user_ids`, or whether member-user projection should become
  opt-in/lazy for hosts that only need entity scope first.
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
  - `resolve_for_user(...)`: 5 queries, about 3-4 ms
  - `GET /v1/entities/{id}`: 1 query as superuser vs 7 queries as regular RBAC user
- Prioritize investigation of the current fixed query tax in permission
  resolution:
  - eager loading of role permissions, role conditions, permission conditions,
    and entity-type overrides even when ABAC/context-aware-role features are
    off
  - separate loading of direct user-role grants and entity-membership grants
  - repeated descendant expansion during access-scope resolution
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

## Intentional Deferrals

These are known and accepted for now:

- No first-class `bootstrap` / `doctor` CLI yet.
- No broader admin-route perf benchmark suite beyond the current query-budget tests.
- No guarantee yet that every downstream host app is using the optimized production defaults unless they follow the current docs.
