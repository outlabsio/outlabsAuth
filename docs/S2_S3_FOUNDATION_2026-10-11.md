# S2 persistent policy and S3 lifecycle observation: local foundation

Date: 2026-10-11. Candidate **0.1.0a38.dev0**, unreleased. Public a37 and its
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
- Final complete PostgreSQL/required-Redis rerun is in progress. The first run
  found enum-only status formatting against legacy string-valued rows; that
  implementation was corrected rather than weakening tenant regression tests.
  Final results are recorded below only after completion.

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
   system-wide accounts, not merely map a practice to its root.
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
