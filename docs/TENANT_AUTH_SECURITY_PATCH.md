# Tenant Auth baseline security patch

**Date:** 2026-10-11
**Status:** All eight baseline corrections and local migration/recovery/budget/artifact qualification pass; the complete S1 release and consumer adoption remain open.
**Branch/base:** `codex/auth-security-20261010`, from merged `main baba18c`.
**Package baseline:** `0.1.0a36`; two additive nullable columns and migration `20261011_0026` are in the candidate. No version, tag or consumer pin change.

The [tenant and administrative-grant plan](./TENANT_IDENTITIES_AND_ADMINISTRATIVE_GRANTS.md)
requires eight baseline corrections before later stages use the existing identity
and permission machinery. This receipt records eight local corrections, their regression
evidence and the remaining release qualification. Local implementation does not
close the operational release gates. The administrative evaluator prototype stays
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
stored conditions. The [numeric qualification](S1_PERFORMANCE_QUALIFICATION.md)
records its conditioned-path cost. Do not market this as transition-aware decision caching.

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
fail-soft behavior. The recovery continuation below fences reconnects; external
restore admission and consumer staging remain operational acceptance obligations.

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

### B3: mutation versions and time validity are independent

Permission decisions, aggregate permission sets and compiled API-key snapshots
carry a server-owned next-transition deadline, checked even when mutation versions
stay unchanged. Cold permission loads retain ACTIVE scheduled bindings, and observe
both their future start and their end before evaluating current authority. Expired
rows remain SQL-filtered on the memoized paths. Direct role grants, direct entity
memberships and inherited memberships participate; no additional SQL is added.
Scheduled bindings add graph rows to the cold load: the numeric qualification now
measures 250 future roles; arbitrary graph cardinality is not a latency guarantee.

Cache hits propagate their deadline to later derived entries, so an aggregate hit
cannot give a snapshot or decision a new unrestricted lease. Writes round Redis TTLs
down and refuse a subsecond or elapsed lease; jitter cannot extend a deadline.
Readers also check the deadline explicitly, including the optional per-process
snapshot cache. Key expiry and the policy-checked anchor entity's validity bound
snapshots too. A paused writer keeps its observed deadline. Old payloads without a
time proof miss; legacy custom decision/aggregate backends without the explicit
`supports_authority_deadlines` contract are bypassed. Conditioned final decisions
still use the conservative F-admin-01 bypass.

### TI-01: identity-only restore and historical platform protection

`platform_protected` is a sticky, nullable historical classification, never an
allow/bypass. Creation or explicit grant of superuser privilege records it; revoking
that privilege retains it. Enterprise direct system-wide role assignment records
it too. Delete and restore capture retained system-wide grants, irrespective of
membership status/window or definition status, before clearing effective privilege
and withdrawing artifacts. Ordinary SimpleRBAC roles keep their prior classification.

Deletion clears `is_superuser`. Restore never re-grants it and retires leftover
roles, memberships, refresh rows and owned keys, including retained rows from old
or incomplete service wiring. A generic status edit cannot bypass the deletion
workflow. Limited administrators cannot edit a former operator, including when
user-scope enforcement is disabled; enforced tenant visibility still returns 404
before protected-target 403. Self-profile behavior and existing global administration
stay within their previous boundaries. Delete/restore audit records include the
privilege, classification and proof-generation transition.

### TI-02: monotonic security epochs and precise issuance

`session_security_epoch` is a nullable BIGINT on the already-loaded user row. NULL
means the unrevoked legacy generation zero. An atomic database increment advances
it on account-wide session revocation, password security changes and non-active
lifecycle transitions, including retained deletion and restoration. Rollback leaves
the durable generation unchanged; concurrent increments cannot lose a revocation.
New access and refresh pairs carry `security_epoch`; both bearer paths and refresh
rotation require exact, non-negative integer equality. Old claims are accepted only
at generation zero. Restore never lowers the generation, so even a same-clock-tick
delete/restore cannot revive old JWTs. Revocation works with refresh storage disabled.

Refresh and security writers acquire the user row before refresh-token rows, avoiding
a reversed lock order. Newly issued JWTs also carry exact integer `iat_us`; existing
`iat_ms`/`iat` forms remain readable. This prevents a fresh proof being rejected merely
because password-change microseconds were truncated in its millisecond claim.
Account-wide logout now cancels all access proofs; a specific refresh-token logout
keeps its existing per-session/optional blacklist behavior. `exclude_family_id`
retains the current family and does not advance the account-wide generation;
per-family access-proof cancellation is outside this account-wide fix.

### TI-03: enrollment rechecks the initiating proof at commit

Association initiation requires a verified JWT user session and binds its epoch
and issuance precision inside signed state. API keys do not enroll login methods.
After provider exchange and state consumption, the callback loads the current user
with `FOR UPDATE`, rechecks authentication eligibility, the exact initiating epoch
and password-security time, and retains the lock through link persistence, host hook
and commit. A completed reset, revoke-all, suspension/reactivation or delete/restore
cancels a pending flow; enrollment and security revocation serialize at that row.
The accepted state remains burned if the later eligibility check fails.

New state records store a fixed-size SHA-256 lookup key, avoiding the existing
255-character SQL limit as signed proof claims grow. Consumption reads both hashed
and legacy raw state keys. Browser binding, profile, one-time use and PKCE/nonce
checks remain. Old epoch-less state is usable only on a still-unrevoked generation
zero account; new-generation accounts refuse it. Namespace-specific cancellation
and the full qualified-mode matrix still belong to S5.

### Storage contract correction (D35)

The earlier S1 estimate of one nullable column covered session revocation but could
not retain a flag-only former operator's protected classification. The candidate uses
two nullable columns: BIGINT epoch and BOOLEAN historical protection. Neither has a
server default, backfill or index, so adding them does not rewrite a populated user
table. The existing installation is interpreted lazily: effective superuser/current
Enterprise system-role checks still work, and qualifying operations capture durable
history. This cannot reconstruct history already erased before the patch.

Migration `20261011_0026` preserves existing rows and is idempotent. Routine downgrade
refuses to remove the credential barrier. Retaining columns alone does not make old
code safe: a code rollback to validators that ignore the epoch requires the separate
credential/reset or traffic-fencing recovery procedure. Local runner, installed
artifact and recovery evidence is below; consumer rollout acceptance remains open.

### Migration safety and recovered authority (2026-10-11)

`eaa5ff3` adds a separate default **5s lock_timeout**, validated within 1ms–30s,
and at most three retries of rolled-back PostgreSQL lock timeout `55P03`. Same-process
commands serialize Alembic's global proxy; independent processes hold a target-schema
transaction advisory mutex before migration setup. Locks/settings are transaction-local
on caller connections. Historical index helpers require valid/ready/live catalog state;
the at-head shortcut audits Auth-owned indexes too. No auto-drop or concurrent-index
conversion is inferred. [Migration/recovery contract](AUTH_RECOVERY.md).

Redis startup/recovery advances the shared global authority version before advertising
availability and clears the recovering worker's optional local key snapshots. Failure
keeps caching unavailable. This prevents a missed offline invalidation from reviving an
old shared allow on reconnect, while preserving counters. It does not provide durable
publication during a partial partition or immediate coherence for another worker's
opt-in local TTL. Database backup restore still requires externally held signing/cache
generations and reconstructed later revocations; the local security-state rewind test
proves signing-key fencing, not a full production restore or S3 runner/outbox acceptance.

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

### Expiry and identity/security continuation (2026-10-11)

- B3 commit `14bba85` adds **32** memory/required-Redis cases for scheduled activation
  and expiry of direct roles, direct/ancestor memberships, aggregate/decision leases,
  compiled snapshots with local TTL zero/120, key/anchor expiry, subsecond lease
  refusal and legacy payload rejection. **All 12** corrected window cases fail on
  the preceding `0d08a68` source. Focused cache/transaction/warm-budget qualification:
  **133 passed**. Fixture setup failures were corrected before the baseline result.
- The lifecycle baseline run on archived pre-patch source reproduces **10 failures
  and 1 passing control**. Current coverage has **24** cases: both bearer paths,
  all retained direct-role membership states, exact epoch claims, stateless refresh,
  rollback/concurrent increments, same-clock issuance, a real HTTP limited-admin
  guard and incomplete legacy artifact cleanup on restore.
- Pending association on archived source reproduces **5 failures and 1 passing
  control** after reset, revoke-all, password change, suspension/reactivation and
  delete/restore. All **7** current cases pass, including a real PostgreSQL lock
  race: enrollment holds the user lock through the host hook and link commit;
  the revocation writer is observed waiting on that lock before it advances the
  epoch. This establishes transaction ordering, not cancellation of a link that
  committed before a later revocation.
- Populated-user migration and tenant-scope acceptance pass **52** cases. The
  migration is applied twice, preserves rows, leaves both columns nullable without
  defaults and preserves `pg_relation_filenode` (no table rewrite). The downgrade
  test refuses removal of the proof barrier. Runner lock/recovery acceptance is
  still separate.
- Initial expanded full qualification: **1485 passed, 278 fixture/library warnings,
  433.23 seconds**, with real PostgreSQL and required Redis; no failures or skips.
  Final review strengthened the retained-role test to require the original removal
  timestamp/reason. It reproduced one failure in the new standalone delete fallback;
  removing its duplicate bulk update preserves that history. The final focused
  lifecycle/retained-delete/OAuth run passes **34** cases. Fresh full qualification
  after that correction and final formatting: **1485 passed, 278 fixture/library
  warnings, 440.38 seconds**, with real PostgreSQL and `TEST_REDIS_REQUIRED=1`;
  no failures or skips. Warning categories remain the existing deprecated Redis
  fixture close, model/library deprecations and synthetic short signing-key cases.
- Ruff over the repository, Black over all **26** touched Python files and targeted
  MyPy on session-security and cache-validity modules pass. Existing warm query
  contracts are unchanged. High-cardinality scheduled/conditioned cold-path latency,
  outage recovery and installed artifacts still need their own acceptance evidence.

Tests use disposable loopback databases/cache and synthetic accounts. They do not
qualify deployed consumers, production data or the complete administrative model.

### Migration, recovery, performance and artifacts (2026-10-11)

- Archived `a6305fe` reproduces two real migration failures: default lock timeout
  is unbounded (`0`) and a failed concurrent unique index is incorrectly treated
  as complete. It also reproduces a committed offline permission revocation
  becoming an ALLOW after Redis reconnect. These are assertion failures with
  working real fixtures, not unavailable dependencies.
- Expanded migration qualification exposed Alembic's process-global proxy race;
  bounded process serialization fixes it. Real PostgreSQL cases now cover lock
  exhaustion/rollback, release-and-retry, separate-process advisory locking,
  unchanged caller settings and at-head refusal of an invalid index. The final
  migration/security-state set passes **16**; recovery/Redis primitives pass **14**.
- The first complete run is **1509 passed / 1 failed**: an old forwarding mock
  did not expect the new lock-timeout argument. Its regression now tests both
  5s and 100ms forwarding; **42** focused core/migration checks pass. The fresh
  complete run is **1511 passed, 485 existing fixture/library warnings, 490.49s**,
  real PostgreSQL and required Redis, **no failures or skips**. A final isolated
  separate-process observer also filters its own database, avoiding cross-fixture
  activity being mistaken for its lock proof.
- **55 installed wheel cases + 55 installed sdist cases + 94 earlier installed
  wheel cache/identifier regressions pass**, with immutable hashes and imports
  outside the checkout. All **233 packaged library files** match qualified source
  bytes. [Installed artifact receipt](S1_ARTIFACT_QUALIFICATION.md).
- Cold/warm numeric SQL and local p95 ceilings pass with zero or **250 scheduled
  roles**. All **10 warm key/token scenarios**, each 100 samples, also pass with
  **zero SQL and zero failures** at both serial and ten-operation concurrency.
  [Measured budgets and their limits](S1_PERFORMANCE_QUALIFICATION.md).
- The owned Enterprise HTTP example passes **62/62** checks plus its smoke flow.
  Ruff over the repository, Black over all **25** changed Python files, targeted
  MyPy on CLI/migration safety, release metadata and **12** release-document/package
  checks pass. No hosted CI was used as a gate; no workflow was enabled or changed.

These results qualify the local candidate. No version/tag, published artifact,
consumer pin, deployment or live migration is implied. The historical a36 package
identifier must change and the resulting exact release artifacts must be qualified
before publication/adoption. Restore admission remains an external host obligation;
full production restore, accepted RPO/RTO and later S3 replay/outbox fences are not
claimed by the security-state rewind test.

## S1 remaining work and release boundary

| Finding | Next correction / required proof |
| --- | --- |
| Migration safety | Locally implemented/tested bounded runner, lock-only retries, concurrent runners, rollback and index-validity checks. Review exact release artifacts; invalid indexes require explicit repair. |
| Outage / recovery | Reconnect/local snapshot fencing and backup-epoch signing-key refusal pass locally. Adopting hosts must enforce the external admission fence and reconstruct later revocations; full restore/RPO/RTO and S3 runner/outbox proof are not claimed. |
| Performance | Numeric SQL caps and local p95 ceilings pass; [measurement receipt](S1_PERFORMANCE_QUALIFICATION.md). Production hardware/latency budgets and S2 staff-grant budgets still need owner disposition. |
| Installed artifacts | Hashed wheel/sdist pass outside-checkout installation and security/migration acceptance; [artifact receipt](S1_ARTIFACT_QUALIFICATION.md). They remain unreleased candidates with the historical a36 version identifier. |
| Release and consumers | Review the complete S1 candidate and D35/recovery contract; select a new version, rebuild/qualify its exact artifacts, verify the Auth/TaskQ release train and private consumer inventory, then follow separately authorized publication, consumer staging and promotion. |

The eventual S1 security patch remains a single release containing the complete
accepted baseline correction. These eight local corrections are not a partially published
security release. S2 persistent administrative grants, S3 lifecycle observation
and S4/S5 identity namespaces are still separate stages. No grant activation,
release, deployment or consumer upgrade follows from this receipt.

## Implementation notes for the next pass

All eight baseline findings and the local runner/recovery/budget/artifact work now
have implementations and acceptance evidence. Review the operational boundaries
and prepare one complete S1 release under the
separate release contract. No consumer adoption, persistent staff grants or replay/history
acceptance follows from local qualification. The pure S2 evaluator remains unwired.
