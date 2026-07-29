# TaskQ Authenticated-Context Authorization Plan

**Status:** Implementation candidate; joint TaskQ audit and release pending  
**Created:** 2026-07-28  
**Implemented locally:** 2026-07-29  
**Consumer:** `outlabs-taskq` optional Outlabs adapter  
**Paired plan:** `../../outlabs-taskq/docs/Task Queue Outlabs Auth Composition Remediation Specification.md`

## Problem

Outlabs Auth already memoized default authentication on `request.state`, but
`require_permission(...)` tried the API-key auth-snapshot path before consulting
that memoized result. The snapshot path calls
`record_api_key_auth_snapshot_usage(...)`.

That ordering is efficient when `require_permission(...)` is the only dependency
on a route: a warm snapshot can authorize without PostgreSQL. It was incorrect
for a two-phase consumer that had already called `require_auth()` and then
authorized several resources in the same request. The first authentication
recorded one API-key use, and each warm snapshot permission check recorded
another.

TaskQ worker presence, workflows and cross-queue follow-ups intentionally check
several canonical queues. One HTTP request could therefore consume approximately
`1 + N` API-key usage and fixed-window rate-limit units. Sustained 429 responses
could deny queue heartbeat or settlement, so this was a host-availability and
lease-safety issue rather than cosmetic telemetry drift.

## Delivered contract candidate

`AuthDeps.authorize_authenticated(...)` authorizes an **already-authenticated
result** without authenticating or recording API-key usage again.

The operation:

1. accepts the authenticated result produced by Outlabs Auth, permission
   candidates, `require_all`, and supported entity/resource context;
2. preserves service-token embedded permissions, user permissions and
   superuser behavior, API-key and integration-principal scope narrowing,
   entity/tree access, ABAC conditions, and typed 401/403 behavior;
3. performs no credential backend loop and no
   `record_api_key_auth_snapshot_usage(...)` call;
4. rejects a supplied result that differs from the auth result already bound to
   the request;
5. accepts a session only when the selected policy path needs one.

`AuthDeps.authenticated_authorization_requires_session(...)` is the supported,
auth-owned decision for consumers that acquire sessions lazily. Consumers must
not inspect source metadata or raw scopes to reproduce that decision.

## Compatibility rule for `require_permission(...)`

Ordinary FastAPI routes that use only `Depends(require_permission(...))` retain
the warm API-key snapshot fast path and exactly one usage/rate-limit event for
the request.

When the default authentication result is already present on `request.state`,
`require_permission(...)` now calls `authorize_authenticated(...)` before any
snapshot lookup. The permission-only snapshot path remains unchanged when no
earlier authentication occurred.

The implementation does not depend on TaskQ permission names.

## Non-goals

- Do not move queue permission parsing into Outlabs Auth.
- Do not expose internal SQLAlchemy models as a new host contract.
- Do not weaken Redis fail-closed API-key quota enforcement.
- Do not treat raw key scopes as sufficient authority.
- Do not remove snapshot version checks or broaden cache staleness.
- Do not change service-token format, API-key format, grant policy, or database
  schema for this fix.

## Acceptance evidence

The checked-in regression matrix proves:

- cold and warm system-integration keys authenticate once across five
  authorizations;
- permission-only warm snapshot routes still record exactly one usage event;
- user-owned keys retain owner permission plus key-scope narrowing;
- integration-principal keys retain key-scope and principal-envelope
  narrowing;
- service-token and non-ABAC integration-principal authorization needs no
  database session;
- entity and ABAC behavior continues through the shared authorization core;
- a context from a different request is rejected with 401.

Full package result on Python 3.12:

```text
1050 passed, 16 skipped
```

The skips are the repository's existing optional Redis/performance lanes. No
schema migration is introduced.

## Remaining release gate

The auth package is not published by this slice. Before release:

1. TaskQ must adopt this exact supported operation without raw-scope
   interpretation.
2. The installed Auth wheel and TaskQ `[outlabs]` wheel must pass the joint
   cold/warm/five-queue/workflow denial matrix.
3. Exact package versions and artifact hashes must be recorded in both plans.
4. Publication requires separate owner authorization.
