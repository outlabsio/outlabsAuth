# Staff personal-key lifecycle and remaining credential acceptance

Continued by [mounted credential and performance qualification](S2_MOUNTED_IAM_PERFORMANCE_2026-10-11.md).
The counts below remain the historical runtime `4c4aebf` receipt.

Date: 2026-10-11. Runtime `4c4aebf66f6204f036c27a6b99552a86ec03982e`,
unreleased a38 / schema `20261011_0028`.
This continues [credential/target/list/concurrency qualification](S2_CREDENTIAL_TARGET_CONCURRENCY_2026-10-11.md).
Public a37 remains the consumer release; existing mounted IAM admission is not activated.

## Qualified SDK behavior

The explicit, application-lifetime staff facade now supports current-JWT
self-service for narrowing, rotation, revocation and own-key metadata inventory.
Ownership is resolved from a fresh personal-key row held `FOR UPDATE`; contexts
cannot cross transactions, sessions or installations. Integration keys, another
owner's credentials and personal-key-authenticated management are refused.

Narrowing requires a nonempty subset of the stored exact actions, bounded to 64,
and current target-bound grants for those actions. Owner, anchor, inheritance,
status and expiry extension are not accepted update fields. Rotation requires a
live anchored expiring original and fresh grants, retains all restrictions and
the **exact** expiry, and revokes the original in the same caller transaction.
The SDK's ceiling-day creation adapter does not extend the replacement deadline.
Actor/JWT and key expiry are rechecked after authority waits. An aborted rotation
leaves the original active and no replacement. Self-revocation remains possible
after grant withdrawal; it does not revive, mint or broaden authority.

`personal_key_page` counts and keyset-pages only the authenticated owner's
personal credentials in one filtered SQL statement after actor validation. The
projection includes UUID, name, status, anchor and expiry; it includes no raw
secret, hash or prefix. Retained revoked credentials remain visible to their
owner. This is not customer-wide credential inventory.

Private transaction-bound approvals are accepted only by explicitly opted-in
SDK calls. Ordinary create/update/rotation calls retain their existing policy
and audit dispatch. The ordinary mounted handlers are not rerouted or widened.

## Credential operation inventory

| Operation | Current qualified administrative boundary | Remaining activation work |
| --- | --- | --- |
| Staff own-key create | JWT + exact live actions/anchor + bounded expiry | Consumer route pairing/installed host acceptance |
| Staff own-key narrow / rotate / revoke | Fresh locked owner key, exact ceilings and rollback above | Consumer route pairing; broader writer/race inventory |
| Staff own-key list | Owner-only SQL count/keyset metadata | Workload query/latency benchmark |
| Mounted self-service `api_keys` list/detail/create/update/delete/rotate | Existing ordinary owner/policy semantics | Explicit staff workflow selection; prevent alternative mounted update/reactivation/expiry paths from escaping new staff policy |
| Entity-first `api_key_admin` list/detail/delete | Existing ordinary tree permission + entity scope guard | Target-bound administrative adoption, exact SQL projection and key/owner protection |
| Integration-principal key creation/update/rotation and service tokens | Existing ordinary machine-principal policy; not human staff grants | Separate machine scope; first staff release must not borrow these credentials |
| Customer account/session/password/OAuth credential changes | Only explicit root-target account admission foundation | Full mounted operation inventory, protected subjects, effects and writer/concurrency tests |
| Hard deletion/bulk native SDK and direct DB maintenance | Trusted existing service/maintenance paths | Restricted runtime privileges and qualified supported writer/cascade inventory |

No consumer should expose staff keys while alternate mounted routes can bypass
the intended lifecycle policy. Administrative integration must cover those
routes or deny that workflow explicitly. Passing this isolated SDK receipt does
not close that activation gate.

## Local evidence

- All **1,596 collected source cases pass**, zero failures/errors/skips, at the
  runtime revision above. Complete collection is partitioned into three isolated
  PostgreSQL integration shards (218/218/217) and 943 unit cases, with required
  Redis and the genuine public-a37 interpreter supplied. This supersedes the
  intermediate 04b80e7/1236b70 runs; the last runtime change preserves ordinary
  key-update policy/audit dispatch.
- The independent required Redis suite passes **102 cases** at the final runtime
  revision (`pytest -m redis`, `TEST_REDIS_REQUIRED=1`); the complete suite also
  runs with required Redis.
- **29 credential/target/list/concurrency facade cases** cover the previous target
  boundaries plus own-key narrowing/rotation/revocation/inventory, expansion and
  expiry denial, live-grant withdrawal, rotation rollback, lock-timeout rollback
  and a key deadline crossed after authority admission.
- Ruff, Black on all 22 changed Python files, MyPy across five affected facade/
  credential modules, and the release metadata helper pass. Existing warm/cold
  query budgets remain part of the complete suite; no new workload SLA is claimed.
- Noneditable wheel and sdist installations each pass **56 focused cases**, zero
  skips, including the genuine a37 migration rehearsal. Each also passes the
  configured-constructor observer failure/commit-refusal/frozen-history smoke.
  All **239 installed package files** match wheel bytes in both environments.
- Exact local artifacts built from runtime `4c4aebf`:
  wheel SHA-256 `bed6096a8bec457f7b0b2e3ee1c0c72ed5da736166ac7704fa257d40ecc40b49`;
  sdist SHA-256 `ac0fa0c017eaa7c28bc5060a8f2744f767860d36d76802a5951850abcc101869`.
  These replace earlier local builds; a38 remains unpublished.
- Handbook port `7b22070` passes lint, type checks, static build and inspection
  of rendered lifecycle methods and the public-a37 boundary.

Disposable collection/shard/JUnit/artifact receipts are outside Git and the vault
under `~/Documents/tmp/staff-lifecycle-ledger-20261011/`. The initial installed
run omitted `S2_A37_PYTHON` and skipped the preceding-release rehearsal; it is
superseded by the zero-skip 56-case reruns, not counted as release evidence.

## Remaining exits

Full IAM target/detail/account/list/credential routing and supported mutation
inventory; deterministic multi-effect ordering and deadlock handling; restricted
runtime DML acceptance; numeric list/detail/concurrency/degraded-cache budgets;
maintainer review and separately authorized release/consumer adoption.

The functional recursive entity list remains outside the plan's indexed
customer-root scale design; no 50k scale or production latency claim is made.
The 64-grant/100-item bounds are admission limits, not a throughput benchmark.
The host-owned Mongo review ledger is separate and does not apply IAM changes,
accept source watermark advancement or establish external recovery admission.
Owned loopback PostgreSQL/Redis containers and the local API listener are removed.
No push, publication, deployment, live Mongo write or consumer pin change occurred.
