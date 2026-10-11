# Mounted staff credential and target performance qualification

Date: 2026-10-11. Runtime `fda9394` (unreleased a38), schema `20261011_0029`.
This continues [owned-key acceptance](S2_KEY_LIFECYCLE_ACCEPTANCE_2026-10-11.md).
The public consumer release remains a37. Full qualification is in progress;
the final local counts and artifact hashes will be recorded before closeout.

## Explicit mount and credential escape-path closure

`outlabs_auth.routers.get_staff_router(facade)` uses one application-lifetime
staff facade and the configured Auth unit of work. It advertises the `staff`
capability only when actually mounted. The bounded surface exposes:

| Route | Admission and effect |
| --- | --- |
| GET `/staff/entities` | Human JWT/personal key; server-fixed `entity:read`; action/target SQL count and keyset page |
| GET `/staff/keys` | Current owner JWT; own metadata only, no secret/hash/prefix |
| POST `/staff/keys` | Current owner JWT; exact currently held actions, anchor and 1–30-day expiry |
| PATCH `/staff/keys/{id}` | Current owner JWT; narrow exact actions or shorten expiry only |
| POST `/staff/keys/{id}/rotate` | Current owner JWT; fresh authority, exact retained deadline/restrictions, atomic old-key revocation |
| DELETE `/staff/keys/{id}` | Current owner JWT; self-revocation remains possible after grants end |

Install `auth.instrument_fastapi(app)` before startup. Actual HTTP qualification
proves that issuance is committed and visible to a second session before the
response returns, and rollback/denial leaves authority unchanged. The mount is
opt-in and absent from existing consumer startup and ordinary permission union.

Staff issuance persists `APIKey.staff_managed`. Ordinary SDK and self-service
HTTP update/rotation refuse those credentials, including metadata-only updates,
status reactivation and expiry extension. Ordinary mounted self-revocation of a
managed key also requires JWT. Trusted native lifecycle cleanup may still revoke
keys through the SDK; revocation reduces authority and does not issue a secret.
The opaque update/rotation approval binds the exact old key ID as well as its
issuer, session, transaction, owner/security epoch, anchor, scopes and inheritance.

Migration 0029 retains provenance and prevents its removal, owner/kind/anchor/
inheritance or existing secret changes, expiry expansion and reactivation.
Existing keys backfill to ordinary `false`; the real preceding-release upgrade
and concurrent/contended migration tests target the new head. This is not a
claim that arbitrary direct SQL scope writes are a supported staff workflow.
Restricted runtime DML and the complete native-writer inventory remain exits.

## Measured SQL budgets and local latency

Target ancestry is now a bounded recursive SQL walk followed by closure
agreement, rather than a sequential parent query at every level. Sensitive
admission locks base entity rows in UUID order and reconstructs current parent
links; an intervening move cannot preserve a stale discovered path.

Entity lists restrict root seeds using the grant's entity/subtree selectors or
pinned group admissions before walking the selected forest. The first scale
run exposed an unnecessary whole-forest walk for one exact entity; the revised
query is measured below. Final predicates still recheck the live action/grant/
template/permission/group, active ancestry, closure, actor and key ceilings.

Focused serial loopback PostgreSQL 16 baseline, 20 samples per case:

| Fixture | SQL ceiling | Measured p50 / p95 |
| --- | --- | --- |
| One-grant target, depth 1 | 10 read / 29 protected admission | 4.94 / 6.71 ms read |
| One-grant target, depth 8 | 10 / 29 | 4.51 / 5.36 ms read |
| One-grant target, depth 32 | 10 / 29 | 4.99 / 5.54 ms read |
| Exact-selector entity list, 10,000 extra customer roots, one visible item | 5 | 15.68 / 20.16 ms |

The statement ceilings are checked-in regression gates. These latencies are
recorded local measurements, not deployment SLAs. They do not qualify 64-grant
worst cases, all-customer groups, 100,000 memberships, customer credential lists,
degraded cache, mass revocation, contention or multi-effect ordering. C5's stored
indexed root projection and C8's revision-watermark group storage remain open;
the current selector optimization does not claim to implement those designs.

## Coverage and remaining exits

The 12 new mounted/performance cases and 29 preceding facade cases pass the
focused real-PostgreSQL run. They cover customer/machine/ambiguous credentials,
strict request fields, actual commit-before-response, ordinary-route/SDK escape
denial, raw lifecycle expansion refusal, SQL filtering and depth budgets.

Customer account/session/password/OAuth operations, user/member lists and
membership/role mutations are not exposed by this first staff mount. They keep
ordinary IAM admission and require separately paired target/protected-subject
guards, SQL projections, supported writer/cleanup inventory and concurrency
qualification. No grants are injected into stock IAM dependencies. Complete S2
activation and S3 ownership/history/recovery/outbox remain open before review,
release and exact consumer artifact/schema/staging acceptance.

Disposable local receipts live outside Git/vault under
`~/Documents/tmp/staff-mounted-sync-20261011/`. No public release, consumer pin
change, deployment or production write is authorized by this receipt.

## Installed-artifact qualification

Fresh noneditable wheel and sdist installations each pass 68 focused cases,
zero skips, including actual preceding-release migration and mounted HTTP/
performance behavior. Each also passes configured-constructor observation,
frozen removal names and failure/commit-refusal acceptance; all 241 installed
package files match wheel bytes. Exact runtime-fda9394 local artifacts:

- Wheel SHA-256 `f4d0780ab0e5b650d1a3d63081013ba124fd461334d4154e75217356f992b855`.
- Sdist SHA-256 `b6f10f2be6126c4639f26a7455a3226356d4927ebbb4455b78fbee5021ec655d`.

Handbook port `491b4f8` passes lint, types, static build and rendered-content
checks for the explicit mount, managed-key policy and public-a37 boundary.
An intermediate overlapping test batch reused Redis databases and observed
another batch's global-counter change. It is discarded. Final source and
independent Redis qualification use a dedicated Redis server; no assertion is
weakened. Final counts will be appended after that clean run.
