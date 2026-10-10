# Tenant Auth baseline security patch

**Date:** 2026-10-10
**Status:** S1 guards and transactional cache fences, local and unreleased.
**Branch/base:** `codex/auth-security-20261010`, from merged `main baba18c`.
**Package baseline:** `0.1.0a36`; no version, tag, schema or consumer pin change.

The [tenant and administrative-grant plan](./TENANT_IDENTITIES_AND_ADMINISTRATIVE_GRANTS.md)
requires eight baseline corrections before later stages use the existing identity
and permission machinery. This receipt records four corrections, their regression
evidence and the remaining work. A passing current suite does not close defects
that have not yet been implemented. The administrative evaluator prototype stays
unwired.

## Implemented in this slice

### F-admin-01: conditioned decisions evaluate current server time

`PermissionService.check_permission` no longer reads or writes the final decision
cache when ABAC is enabled and stored conditions exist. The policy engine creates
the current time after the old cache key was computed; hashing caller-supplied
attributes could not bind that generated time or the next condition transition.
Both cached allows and cached denials were wrong after the clock crossed a boundary.

This conservative guard applies to all decisions on that conditioned path. It
does not yet distinguish a particular unconditioned role inside an installation
that has other conditions. Policy-loading and request-local caches remain, and
ordinary RBAC retains its decision cache, including ABAC configurations with no
stored conditions. Condition-capable cold-path cost still needs the S1 budget
qualification. Do not market this as transition-aware decision caching.

The effective-permission projection delegates conditioned checks to the same
guard. Regression cases cover individual checks and permission-list projection,
two targets/resources with opposite time conditions, both clock directions and
constant permission epochs, against memory caching and real Redis.

### TI-04: retained-deleted identifiers stay reserved

`UserService.update_user_fields` rejects a changed normalized email on a DELETED
account before uniqueness lookup or profile mutation. The service boundary also
protects the mounted profile HTTP route. The row and its global uniqueness
reservation remain; creating a new account with that email is refused.

A same-normalized-email update and ordinary retained profile maintenance still
work. This patch does not add a purge/reuse or privileged-recovery operation.

### B1: shared authority becomes fresh after the owning commit

Authority mutations now register on the actual SQLAlchemy transaction. The
ordinary `AsyncSession` commit event awaits cache I/O through SQLAlchemy's async
greenlet bridge; this covers host-owned sessions, explicit commits and transaction
context managers without an unawaited background task or custom session subclass.
Membership, role/permission definitions and conditions, direct roles, entity moves,
user/principal state and concrete API-key mutations use this boundary. Holder
fan-out is resolved inside the transaction; only publication waits for commit.

A released savepoint transfers its actions and dirty marker to the parent. A
rolled-back or failed savepoint discards only its actions. Root rollback, failed
flush/commit and close discard pending publication. Request memos reset immediately
and at commit/rollback/close, including when no shared cache is installed. Dirty
sessions bypass shared permission decisions, aggregates, condition flags, tree
relations and compiled auth snapshots, so they can observe their own SQL changes
without leaking uncommitted grants or revocations.

If an action raises after commit, other queued actions are attempted and the first
exception propagates. The database is already committed; this is not a rollback.
This mechanism adds no durable outbox and does not change the backend's existing
fail-soft behavior. Cache outages/recovery, restore fencing and consumer staging
remain part of complete S1 acceptance.

### B2: snapshots carry pre-authority provenance

API-key verification observes global and credential-hash versions before its first
key lookup, then owner/principal/anchor versions before policy or owner reads. It
preserves the earlier global/credential observations. The strategy and direct
host authorization carry that token with their result, including when dependencies
reuse `_outlabs_effective_permissions` computed earlier. The writer refuses missing,
malformed or incomplete provenance and never fetches later versions to label an
old permission set.

Key update, revoke, rotation and deletion bump a credential-specific counter after
commit before deleting the shared snapshot. A paused old reader can still finish
its already-started request, but its later snapshot write remains bound to the old
counter and misses on the next read. Old snapshots without that counter also miss
and rebuild. Counters contain key hashes, never raw credentials. The new scope
uses the same warm version `MGET`; cold verification observes two batches and adds
no SQL. Disabled caching does not add these observation reads.

Entity-tree fallback similarly binds its SQL result to the epoch observed before
the query. Uncommitted tree changes bypass shared relations. The existing opt-in
per-process snapshot TTL still permits bounded staleness; default zero remains
the version-checked profile. Memory epochs remain process-local; shared Redis
epochs are required for coherence across workers. These changes do not claim that the opt-in
profile provides immediate cross-process revocation.

## Regression and local qualification

- Before the fixes, the initial regression set had **6 failures and 2 passes**:
  all four conditioned-cache crossings and both deleted-identifier guard cases
  failed. The unchanged ordinary-RBAC cases passed.
- With the original a36 decision-cache guard temporarily restored, **all eight
  detail/list clock-crossing cases fail** (both backends and both directions).
  The fixed guard was restored before final qualification.
- Focused final regression set: **14 passed**. Ten conditioned/cache-retention
  cases use the real permission service, policy engine and cache backend; their
  authority/condition loaders are synthetic suppliers. Three deleted-identifier
  service cases include real PostgreSQL deletion/reservation and allowed profile
  maintenance. One real HTTP case confirms `422 INVALID_INPUT` and unchanged
  persisted email/profile.
- Full local suite on the source fixes before the four added list cases:
  **1370 passed, 155 existing warnings, 476.75 seconds** with real PostgreSQL and
  `TEST_REDIS_REQUIRED=1`. Final expanded full suite: **1374 passed, 157
  fixture/library warnings, 466.58 seconds**, with real PostgreSQL and required
  Redis. No skips or failures. The extra warning instances come from the added
  Redis fixture cases; they are the existing deprecated `close()` warning.
- Ruff over the repository and Black over the two touched service files and
  three regression files pass. No hosted CI is used as acceptance.

### Transaction/cache continuation

- The original B1/B2 regression set fails **all 14 cases** on the preceding
  local candidate (which contained only F-admin-01/TI-04). The failures reproduce
  pre-commit membership publication, stale user/credential authority relabeling,
  and acceptance of snapshots without provenance. Initial fixture setup mistakes
  were corrected before this baseline result; dependency/setup failures are not
  counted as reproductions.
- Expanded coverage adds real grant/revoke with separate reader/writer sessions,
  commit and rollback on memory/Redis; key update/revoke/delete publication;
  a key revoked during actual strategy authentication; stale tree-query publication
  and a writer's private tree changes. Strategy cases use real Redis for usage
  accounting with either memory or Redis permission epochs.
- Transaction cases cover outer commit, released/rolled-back/failed savepoints,
  failed root commit, close, async context commit, awaited visibility on another
  connection, post-commit publication exceptions and memo reset without a backend.
  The ASGI response-order regression observes publication before the response body;
  its uninstrumented control still detects late teardown publication.
- Existing warm aggregate/decision reads retain **zero SQL**. An intermediate full
  run exposed admin principal inventory at **15 queries against its 14-query cap**
  after stale setup memos were cleared. Loading principals and their current anchor
  in one outer join restores the existing cap, with separate/missing key anchors
  still loaded and checked. All **7** related enterprise key/query-policy cases
  and the additional real-DB anchor-fallback case pass; budgets are not raised.
- Expanded final focused qualification: **77 passed**, with real PostgreSQL
  and required Redis, including dependency guards and all new cache/transaction
  cases. Ruff over the repository, Black over touched files and targeted MyPy
  on the new transaction module pass. Final full local suite: **1420 passed,
  207 fixture/library warnings, 514.64 seconds**, with real PostgreSQL and
  `TEST_REDIS_REQUIRED=1`; no failures or skips. Additional warnings are instances
  of the existing fixture/library categories, not new runtime coroutine warnings.
- Legacy invalidation assertions now await the owning commit; explicit purges
  without a transaction remain immediate. Synthetic permission sessions declare
  an empty `info` dictionary. Custom authentication results without observation
  support keep their previous shape and are not compiled into shared snapshots.

Tests use disposable loopback databases/cache and synthetic accounts. They do not
qualify deployed consumers, production data or the complete administrative model.

## S1 remaining work and release boundary

| Finding | Next correction / required proof |
| --- | --- |
| B3 | Bound decision, aggregate and API-key snapshot validity by relevant membership/role deadlines; cover expiry and scheduled activation with no version change. |
| TI-01 | Withdraw effective privilege on deletion/restore while retaining historical protection from limited administrators. Include dormant/scheduled privileged roles in that classification. |
| TI-02 | Add a monotonic account session-security epoch, advance it on lifecycle/security revocation, compare it on both bearer paths, and preserve it on restore. Qualify token precision and delete/restore races. |
| TI-03 | At OAuth association commit, recheck current eligibility and initiating proof against the security epoch. Qualify reset, revoke-all, suspend and delete/restore during a pending association. |
| Migration safety | Bounded runner `lock_timeout`, validity-checked index helpers, online nullable session-epoch migration and installed-artifact checks. |
| Performance / release | Record numeric budgets; preserve warm query contracts; measure conditioned paths. Build and test immutable artifacts, then follow the separate release and consumer staging contracts. |

The eventual S1 security patch remains a single release containing the complete
accepted baseline correction. These four local corrections are not a partially published
security release. S2 persistent administrative grants, S3 lifecycle observation
and S4/S5 identity namespaces are still separate stages. No grant activation,
release, deployment or consumer upgrade follows from this receipt.

## Implementation notes for the next pass

- B1/B2 have local transactional/cache implementations; the four remaining
  baseline defects are B3 and TI-01/TI-02/TI-03. Complete runner, outage/recovery,
  artifact and performance gates still apply before any S1 release.
- TI-01 cannot close by clearing `is_superuser` alone. `routers/users.py`
  currently protects that flag and, via `user_is_global_account`, direct
  system-wide role holders across active/scheduled/suspended/expired/revoked
  states. A former superuser without a direct role also needs durable historical
  protection. Resolve D35's storage/compatibility contract before claiming the
  one-column S1 migration promise covers both that protection and session epochs.
