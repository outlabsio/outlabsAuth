# HTTP key usage and host metrics acceptance — 12 October 2026

Unreleased a38 runtime `99460ab` follows `8e2af1e`; Auth schema stays
`20261012_0031`. Public consumers remain pinned to a37. No release/tag/push occurs.

## Reproduction and change

Diverse's isolated mounted customer IAM router authenticates one key through
multiple dependencies. Real Redis showed the third HTTP request reaching a
three-request window as counter four. This was duplicate accounting, not an
additional request. The host native SQL unit also deliberately defers nested
commits, so calling the usage synchronizer there could clear Redis processing
keys before its SQL receipt committed.

The library shares only the Redis counter operation inside an explicit
`RequestCacheMiddleware` lifetime. Both cold verification and warm snapshots
use the same operation key, bound to the credential's usage key and Redis
namespace. Concurrent dependencies share a task; each still performs its current
permission, entity, scope, deadline and policy checks. Repeated 429 checks reuse
the same counts. The next HTTP request, another key/namespace and direct SDK or
maintenance calls count separately. An inherited child task sees the scope
closed once the response ends. No credential secret is stored in the memo key.

The host, not the SDK, owns the deferred-commit adapter. Its separately enrolled
metrics session holds current read admission and an identity lock, writes only
usage fields/receipts, actually commits, then lets the SDK acknowledge Redis.
A lost Redis ACK retries against the receipt without duplicating SQL usage.
Counters create no native authorization recovery image. Automatic jobs remain
disabled; this is an explicit worker invocation, not a new scheduler.

## Exact local evidence

- Full source suite: **1,655 pass**, no failures/errors/skips, real PostgreSQL and
  required Redis, with the genuine public-a37 interpreter supplied.
- Independent real-Redis selection: **60 pass**. Focused request-lifetime/quota
  selection: 12 pass, including concurrent counting and escaped child lifetime.
- Fresh noneditable wheel/sdist outside source: **115 each**, no failures/skips,
  plus both constructor acceptance checks. All **243 package files** match each
  artifact and the Diverse candidate installation.
- Full Ruff, five changed-file Black checks and three service/module types pass.
  The 132 unrelated inherited Black files remain unchanged.
- Handbook `f40749c`: lint/typecheck/static build pass for the two corresponding
  guides ported after canonical library edits.

Runtime artifacts built from clean `99460ab` before later documentation edits:

| Artifact | SHA256 |
|---|---|
| wheel | `1a300dc151ee4c0c86f3e85a225dbf9697d266fb8a8c7cbbcfefe0fc321afdfd` |
| sdist | `20cd202260c2211365596ba373c144de6ef70ca12629376320f376019b37a719` |

Diverse API frozen runtime `9ea75eea` / host `e94ca923a801` qualifies **187** local
candidate cases, including actual named staff-key SQL writer ceilings, empty/
expanded-scope refusal, cold/warm customer/staff key lifecycle, quota once, usage
ACK retry, unsafe commit settings and owner storage. Public full verify remains
984 pass, with eight existing optional plus 187 separately qualified candidate
skips. 10k people/member/role rows retain 15.1 MB plain / 1.03 MB encrypted,
stage/commit/ACK 0.9033s; all 32 mixed native HTTP requests return 200 in 3.2531s.

## Remaining release boundary

This is local qualification. Exact independent a38 review/publication/adoption
remains open. Diverse still needs broader positive native writer/mixed setup and
population profiles, actual inventory/history/churn/write rate and production
storage/key custody/failure-domain/RPO-RTO evidence. A 1,000-native-write/day
scenario at the 10k capsule size adds 247.76 GB of retained capsule JSON over
180 days before WAL/replicas/backups or larger images; no GC/retention policy is
qualified. These host obligations are not implied by SDK tests or fsync settings.

Host technical truth:
`~/Documents/projects/DiverseAPI-postgres-worktrees/authorization-20261010/docs/parity/native-keys-storage-2026-10-12.md`.
No additional SendGrid send or production operation is performed.
