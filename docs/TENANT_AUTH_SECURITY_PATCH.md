# Tenant Auth baseline security patch

**Date:** 2026-10-10
**Status:** First S1 implementation slice, local and unreleased.
**Branch/base:** `codex/auth-security-20261010`, from merged `main baba18c`.
**Package baseline:** `0.1.0a36`; no version, tag, schema or consumer pin change.

The [tenant and administrative-grant plan](./TENANT_IDENTITIES_AND_ADMINISTRATIVE_GRANTS.md)
requires eight baseline corrections before later stages use the existing identity
and permission machinery. This receipt records two corrections, their regression
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

Tests use disposable loopback databases/cache and synthetic accounts. They do not
qualify deployed consumers, production data or the complete administrative model.

## S1 remaining work and release boundary

| Finding | Next correction / required proof |
| --- | --- |
| B1 | Move version increments/publications after the owning transaction commits; reset local memos immediately. Qualify concurrent readers, rollback and failed commit, including supported standalone service callers. |
| B2 | Observe snapshot versions before any reused/computed authority, carry that token through the compiled context, and never relabel stale authority with a later version. Deterministically pause the reader between observation and write. |
| B3 | Bound decision, aggregate and API-key snapshot validity by relevant membership/role deadlines; cover expiry and scheduled activation with no version change. |
| TI-01 | Withdraw effective privilege on deletion/restore while retaining historical protection from limited administrators. Include dormant/scheduled privileged roles in that classification. |
| TI-02 | Add a monotonic account session-security epoch, advance it on lifecycle/security revocation, compare it on both bearer paths, and preserve it on restore. Qualify token precision and delete/restore races. |
| TI-03 | At OAuth association commit, recheck current eligibility and initiating proof against the security epoch. Qualify reset, revoke-all, suspend and delete/restore during a pending association. |
| Migration safety | Bounded runner `lock_timeout`, validity-checked index helpers, online nullable session-epoch migration and installed-artifact checks. |
| Performance / release | Record numeric budgets; preserve warm query contracts; measure conditioned paths. Build and test immutable artifacts, then follow the separate release and consumer staging contracts. |

The eventual S1 security patch remains a single release containing the complete
accepted baseline correction. These two local fixes are not a partially published
security release. S2 persistent administrative grants, S3 lifecycle observation
and S4/S5 identity namespaces are still separate stages. No grant activation,
release, deployment or consumer upgrade follows from this receipt.

## Implementation notes for the next pass

- B1 affects the unit-of-work contract as well as the membership helper. The
  current library session factory returns ordinary `AsyncSession` instances,
  consumers also call services with their own sessions, and OAuth callbacks
  commit explicitly. An after-commit design must cover supported commit paths,
  rollback/savepoints and response timing. An unawaited task scheduled after
  commit is not proof that freshness is established before the response.
- B2 includes the dependency's `_outlabs_effective_permissions` reuse: reading
  versions inside the snapshot writer, after that set was computed, preserves
  the original race. Carry observation provenance with reused sets rather than
  fixing only a fresh computation in the writer.
- TI-01 cannot close by clearing `is_superuser` alone. `routers/users.py`
  currently protects that flag and, via `user_is_global_account`, direct
  system-wide role holders across active/scheduled/suspended/expired/revoked
  states. A former superuser without a direct role also needs durable historical
  protection. Resolve D35's storage/compatibility contract before claiming the
  one-column S1 migration promise covers both that protection and session epochs.
