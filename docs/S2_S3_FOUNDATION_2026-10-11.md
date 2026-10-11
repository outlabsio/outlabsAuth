# S2 persistent policy and S3 lifecycle observation: local foundation

Date: 2026-10-11. Candidate **0.1.0a38**, unreleased. Public a37 and its
accepted security proof remain in [S1_RELEASE_A37.md](S1_RELEASE_A37.md).
The [tenant/admin plan](TENANT_IDENTITIES_AND_ADMINISTRATIVE_GRANTS.md) is the
design authority. This foundation does not accept all DD-062 decisions, activate
runtime staff authority, implement namespaces or close the S2/S3 stage exits.

## Persistent administrative policy

The additive `20261011_0027` migration follows public a37 head
`20261011_0026`. It creates separate template revisions, groups, customer
admissions, grants and security audit. Registered models also support a fresh
current-model baseline; a genuine populated public-a37 upgrade is tested with
an independently installed a37 interpreter, preserving existing user UUID,
password hash, profile and platform classification.

Template contents, grant selector/admission lineage and audit are immutable at
the database boundary. Admission closure and grant revocation are monotonic;
re-admission/re-grant requires new identities. Foreign keys use RESTRICT rather
than cascading away policy. Required indexes are checked for validity. Routine
downgrade refuses to destroy retained administrative authority/evidence.

`AdministrativeGrantService` requires one configured independent Internal root
UUID, an active platform management actor and a caller-owned transaction. It
refreshes locked management rows, so another transaction's platform demotion
cannot be ignored through an older ORM instance. Management writes and security
audit use the same transaction. Request keys bind immutable request content;
retrying a revoked grant does not reactivate it.

Grant selectors are an exact entity, an entity subtree or a group containing
independent customer roots. Group grants pin admission UUIDs. A removed/re-added
customer, or a newly admitted customer, is outside the old grant. The Internal
control root cannot be selected as a customer. Bounded parent traversal and
exact closure agreement validate active structural ancestry and validity.
Administrative groups are not new structural parents or identity namespaces.

Policy supports explicit unconditional permission IDs/names and optional entity
types. Wildcards, conditioned permissions and control-plane actions are
refused. Current permission retirement, holder suspension, template/group kill
switches and expired windows deny. One complete grant must match both the exact
action and target; permission read-at-A and update-at-B cannot be stitched.
Account operations may request the customer root rather than a practice target.
Supplied personal-key action/entity ceilings are intersected with the result.
A grant pins the holder's monotonic session security epoch. Retained delete/
restore, suspension/reactivation and password security changes cannot revive
an earlier grant; a fresh platform-approved request is required at the new
security boundary. Epoch matching is in the indexed actor query and immutable
lineage/audit, not another legacy runtime query. This conservative initial rule
applies only to administrative grants, not ordinary memberships/roles.

This is a fresh-DB evaluator **without a runtime admission caller**. It does
not authenticate the supplied UUID or ceiling sets. Do not call it from a route
using request-body identities or unverified ceiling values. No ordinary Role
or existing permission result receives administrative authority from these rows.

## Same-transaction lifecycle observation

The candidate constructor accepts `lifecycle_observers`, an optional list of
async `(AsyncSession, LifecycleEvent) -> None` callbacks. One dispatcher is
shared by the configured user, membership and entity services. An empty list
does no observer queries/events and leaves existing mounted authorization
unchanged. The callback receives frozen scalar IDs, names, status, source and
aware event time, with no credential, email or token material.

Supported observation sites in this foundation:

| Service path | Evidence before cleanup |
| --- | --- |
| Membership history create/update/status/role operations | `membership.<event_type>` with current/previous snapshot |
| `remove_member` | Locked row, one revoked event; repeated revoke is a no-op |
| User suspension/status transition | `user.status_changed` with enum/string normalization |
| Retained user delete and bulk membership cleanup | `user.deleted`, per-membership revoked evidence |
| SDK user hard delete | User and per-membership hard-delete evidence before cascade |
| Entity archive and bulk membership cleanup | Entity snapshot and per-membership archive evidence |
| SDK membership hard delete | Frozen subject/parent before history cascade |

The observer writes host-owned evidence with the exact caller session. It must
not commit/roll back, create an independent transaction, mutate IAM authority or
send mail/network effects. A commit attempt during observation refuses. A
raised exception or cancellation poisons the current transaction even when the
caller catches it. Root rollback clears its failures; savepoint rollback clears
only failures owned by that discarded savepoint. A later savepoint rollback
cannot clear an outer failure. Successful callbacks may not be interpreted as
committed evidence until the outer transaction commits.

Host evidence must not cascade from mutable IAM rows. Tests retain the original
removed person's names after profile changes and user hard deletion. A removal
event identifies a relationship; it does not infer that a shared user should be
globally disabled. Native identities and source identities are not joined by
names/emails or by this library.

Generic structural SDK hard deletion is fenced in favor of `delete_entity`
archive. This deliberate safety restriction applies even without observers;
the fresh default is not blanket compatibility for that raw purge API. Raw SQL,
generic status changes outside approved service workflows, recovery scripts and
structural purge need an explicit supported-writer disposition before S3 exits.
Callbacks are trusted host code, not a sandbox for arbitrary code; a callback
that violates transaction ownership requires discarding the affected unit/session.

No automatic delivery is provided. A host can write an outbox alongside frozen
evidence, then send after commit. Provider idempotency needs independent proof;
otherwise physical delivery is at-least-once and uncertain acceptance/receipt
must retain an UNKNOWN outcome. Credentials must not rotate on retries.

## Qualification status

- Persistent-policy cases include same-grant action/target matching, subtree and
  account-root checks, personal ceilings, pinned admission withdrawal/re-addition,
  platform-only management including concurrent demotion, target/actor windows,
  suspension/kill switches, request conflicts and same-transaction audit rollback.
- Real public-a37 upgrade and immutable database policy checks pass. The earlier
  direct S1 migration fixtures remain pinned to `20261011_0026`; current-head
  upgrade/rehearsal assertions advance to `20261011_0027`.
- Lifecycle cases exercise frozen names after hard deletion, repeated revoke,
  suspension/retained deletion/archive, observer failure caught by a caller,
  premature observer commit refusal and nested transaction failure ownership.
- Final runtime source `df0c29526e967ae4853b1bd1a3a7c447e22becb3` passes
  **all 1,567 collected tests**, with no failures, errors or skips. The complete
  suite ran in four local shards: three integration shards of 208 cases and
  one unit shard of 943, each with a separate disposable PostgreSQL database
  and Redis index. Exact collected node IDs were partitioned once, without
  overlap; JUnit totals and successful exits matched every selected node.
  Optional mocked channel SDKs were installed. Independent required-Redis
  acceptance also passes **102 tests / 1,465 deselected**.
- Earlier runs caught enum-only status formatting against string-valued rows
  and unsupported `.dev0` packaging metadata. Both were corrected; behavioral
  dev0 artifacts are superseded by this unreleased a38 candidate. Reproduced
  delete/restore and suspension/reactivation grant revival is corrected by
  epoch pinning; password-change withdrawal and an explicit fresh grant also
  pass. No release metadata guard was weakened.
- A wheel and an sdist built from that clean committed runtime source each
  pass **27 installed cases** (17 policy, one genuine populated-a37 upgrade,
  nine lifecycle), outside the source checkout with noneditable imports.
  Each separately passes the actual configured Enterprise constructor smoke:
  shared dispatcher, caught observer failure refusing commit, and original
  names surviving hard deletion. All **237 installed package files** match
  the exact wheel bytes. These are local candidate artifacts, not published
  or accepted for consumer runtime admission.
- Whole-repository Ruff, Black on all 16 changed Python files, targeted MyPy
  on the three foundation modules and supported a38 release metadata pass.
  The isolated canonical handbook port passes site lint, types and static
  generation; the rendered lifecycle page preserves the unreleased/public-a37
  boundary. No site deployment is included.

| Local candidate artifact | SHA-256 |
| --- | --- |
| `outlabs_auth-0.1.0a38-py3-none-any.whl` | `8c08a1aae04e77816a5aee7b4edece5ca7feb0242ffeea68f5773eda661262ea` |
| `outlabs_auth-0.1.0a38.tar.gz` | `6e45d42920f6eab0ecdddac3fc0cf4dc19d6296e3fe1f4f315bd6c3de5130920` |

Receipt-only commits after `df0c295` do not change these qualified runtime
bytes. Complete S2/S3 stage acceptance remains subject to the gates below.

Run from a Python 3.12 development/test environment with disposable local
Postgres and real Redis:

```bash
TEST_REDIS_REQUIRED=1 uv run pytest
TEST_REDIS_REQUIRED=1 uv run pytest -m redis
```

The genuine upgrade test additionally requires `S2_A37_PYTHON` pointing to an
independently installed **public a37** interpreter. It refuses an arbitrary
current-model stand-in. Without that input the focused genuine upgrade is
explicitly unqualified, not equivalent to a migration-pass claim.

## Gates before runtime adoption or release

1. A verified authenticated-context/credential facade. Bind personal-key ceilings
   from real validation; preserve machine-principal separation. Do not expose
   the UUID-based foundation as a public authorization facade.
2. An exhaustive IAM/detail/account/host operation inventory and action-bound SQL
   list predicates, including empty scope. Existing tenant rules remain intact.
   Account-root checks must protect platform, historical-platform and dormant
   system-wide accounts, not merely map a practice to its root. Holder security
   epoch pinning closes reproduced administrative grant revival after identity
   restore; end-to-end credential and account operations still require acceptance.
3. Withdrawal, admission, definition and topology changes serialized against
   sensitive writes/multi-target effects, with failure injection. Current fresh
   checks alone do not promise that a concurrently revoked grant cannot race a
   later write. No administrative decision cache is activated.
4. Measured numeric query/latency/memory ceilings for actor grants, admissions,
   detail/list paths and degraded cache operation, plus immutable conditions or
   an explicit restrictive first-release policy disposition. Current per-actor
   scans and permission reads are not scale/performance exit evidence.
5. Full supported lifecycle writer/cascade inventory, configured-constructor and
   installed wheel/sdist/host compatibility, no-observer query evidence and
   observer failure/cancellation/transaction-ownership acceptance. Qualification
   must distinguish the structural purge restriction from compatible routes.
6. Host-owned source-cut/cohort/episode/crosswalk/contribution policy and target
   fingerprints, conditional writes, runner/recovery fencing, outbox receipts
   and replay acceptance. The library observer is not a Mongo sync engine.
7. Maintainer/reviewer disposition of remaining S0 decisions, immutable release
   artifacts, publication and consumer-specific package/schema/staging gates.

Qualified namespaces, delegated grant management, machine grants and structural
super-parent topology remain separate stages. Public a37 consumers retain their
exact pin until a later release independently qualifies.
