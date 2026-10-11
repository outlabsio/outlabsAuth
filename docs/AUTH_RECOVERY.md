# Auth migration and recovery fencing

**Status:** S1 local recovery contract, 2026-10-11. No deployment authorization,
production RPO/RTO, lifecycle outbox or source-replay runner is implied.

## Ordinary upgrade

Qualify the exact wheel and sdist SHA-256 with a new release version, an inventory
of validators/writers and a tested recovery image before admitting a consumer.
Run migration once as a controlled startup/release step; application instances may
also converge safely, but each one needlessly running DDL is not a release strategy.

`outlabs-auth migrate --lock-timeout 5s` and `migration_lock_timeout="5s"` use a
separate bounded PostgreSQL lock budget, irrespective of `statement_timeout`.
Positive values from 1ms through 30s are accepted. The CLI rolls a failed attempt
back and retries only SQLSTATE `55P03`, at most three attempts with 100/200ms
backoff. This bounds each lock wait, not the total duration of multiple DDL statements
or a large migration; keep the separate statement timeout enabled. Same-process
commands serialize Alembic's global proxy, and independent processes serialize on
a transaction-scoped advisory lock for the target schema. Caller connection settings
are transaction-local. Ordinary authentication does not acquire that mutex.

Security revision `20261011_0026` adds nullable columns with no defaults, indexes or
backfill. Contended DDL must roll back with both the version and schema unchanged;
retry after inspecting/removing the actual blocker. Do not lengthen lock budgets
blindly. A version at head is not sufficient: the runner checks all Auth-owned
table indexes for `indisvalid`, `indisready` and `indislive`. An interrupted concurrent
index must be diagnosed and explicitly repaired under a reviewed SQL procedure,
including duplicate-data inspection for unique indexes. The library never drops it
automatically or treats its name as proof of completion. This patch does not change
historical revisions into concurrent-index jobs. Offline SQL exports still require
operator lock-budget/transaction controls; they are not the qualified online runner.

## Redis loss and reconnect

While Redis is unavailable, authority reads use the database and shared publication
may be missed after commit. Before initial connection or a reconnect enables cache
reads, RedisClient atomically advances the existing global authority version. A
failed fence keeps the cache unavailable and the reconnect probe retries. Shared
decisions, aggregates, condition flags, tree relations and key snapshots carry this
version; the recovering worker also drops its optional local key snapshots. Rate
limits, usage counters and unrelated cached data are preserved.

The default local snapshot TTL is zero: every shared hit checks versions. Opt-in
nonzero TTL still permits bounded staleness on another worker that remained connected.
This fix is not a durable outbox. A partitioned writer can miss publication while
another reader remains connected; detecting that event and fencing the affected
consumer/workers is an operational obligation until durable delivery is available.
For recovery, close admission, stop all affected workers and resume them under a
fresh `redis_key_prefix` selected outside the restored failure domain. A successful
PING, counter increment, or an unchanged prefix alone does not qualify a Redis backup
restore: rewound counters can collide with saved entries. Never reset rate-limit
state as a side effect of clearing authority.

## Database restore or code rollback

The security epoch is monotonic within the current database, not across backup
restore. A backup can restore a revoked key, refresh row, user epoch or removed grant.
Retaining the two columns does not make an older binary safe: a pre-epoch validator
can ignore them. Routine downgrade refuses to remove this barrier. Use a qualified
forward repair/security-aware recovery image; reverting to old validators requires
the coordinated credential reset and external admission fence below.

The owning application/release platform, outside the Auth database and restored
Redis, must retain and enforce the admission record. S1 does not implement that
external gate or infer that it exists in a consumer. Its operator receipt must bind:

1. A fresh recovery generation and owner approval; exact consumer/runtime inventory,
   source commit, immutable package/image hashes and migration head.
2. Traffic, authentication, writes, background replay and pending-delivery admission
   closed; all old workers and saved runner leases stopped. Restored database flags
   cannot reopen this fence.
3. Verified backup identity/time, participating Auth/host schemas and a coordinated
   reference/history checkpoint; measured restoration and accepted lost-write window.
4. Fresh signing material held outside the backup domain. Rotate user access/refresh
   JWT secrets, service-token secrets where used, OAuth signed-state secrets, and
   challenge/enrollment proofs as appropriate. Deny old signatures; do not retain an
   old-key verification overlap. Invalidate retained OAuth states and reset/invite
   proofs so an old pending enrollment cannot complete. Existing provider credentials
   are a separate inventory, not automatically revoked by JWT rotation.
5. A fresh authority-cache namespace and restarted workers. Reconstruct later key,
   role/membership and platform-grant revocations from evidence outside the restored
   database before allowing their authentication. JWT rotation alone does not revoke
   restored API keys or an external identity provider's login session.
6. For hosts with source sync/delivery: reconstruct source-owner mappings, high-water
   marks, cutover acceptance, removal episodes and pending-delivery outcomes. Missing
   evidence keeps the affected admission closed. Never blindly replay a saved plan,
   reactivate source authority after accepted cutover, merge conflicting identities,
   or replace removed limited grants with global privileges.
7. Negative checks against the installed recovery artifact: old access and refresh
   tokens, revoked keys, stale cache, pending OAuth enrollment and any old runner/plan
   refuse; fresh authorized credentials work; target isolation remains. Then record
   exactly which admissions are reopened and the responsible approver.

Public library evidence is synthetic and consumer-neutral. Each adopting host must
add its own external admission test and restore rehearsal. S3 outbox/checkpoint and
later namespace recovery acceptance remain separate gates; this runbook does not
claim their implementation or declare F-MR-01 fully closed.

## Local proof

`test_migration_safety.py` exercises real lock contention, full rollback, retry,
same/separate-process runners and failed concurrent-index catalog state.
`test_cache_recovery_fencing.py` reproduces a real offline committed revocation and
tests shared/local snapshots plus a second worker. `test_restore_recovery_fencing.py`
rewinds the relevant user epoch to a backup value, demonstrates old proof revival
under the old secret, and proves both bearer paths and refresh refuse it after
external signing-key rotation. This is a security-state rewind rehearsal, not a
timed full-database backup/restore or a production recovery SLA.

See [S1 qualification](TENANT_AUTH_SECURITY_PATCH.md) for the exact local receipt.
