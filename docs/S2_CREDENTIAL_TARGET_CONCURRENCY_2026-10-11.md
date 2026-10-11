# Staff credentials, targets, lists and concurrent withdrawal

Latest continuation: [owned-key lifecycle and operation inventory](S2_KEY_LIFECYCLE_ACCEPTANCE_2026-10-11.md). The evidence below retains its original revision.

Date: 2026-10-11. Runtime source `501bf269a7534cd3ecdee559981db7d095467a28`.
Candidate `0.1.0a38`, unreleased; public a37 consumers keep their pins.
This follows [the retained-policy/observer foundation](S2_S3_FOUNDATION_2026-10-11.md)
and qualifies the explicit SDK facade below. It does not close the complete
S2/S3 release or consumer IAM adoption gates.

## Verified host boundary

`auth.host_query_service.staff_administration(auth,
trusted_internal_root_id=<reviewed server UUID>)` creates an opt-in
`AdministrativeAuthorization`. `authenticate(session, request)` uses the real
configured AuthDeps backend, accepting current human JWT or personal API key
only. Simultaneous key/bearer headers, integration credentials, service tokens,
forged actor dictionaries, another Auth installation/session and a context
carried across transaction completion are refused. A context is private-sealed
and bound to the exact caller transaction. User/root/status/security epoch and
key state/expiry are read afresh. A context cannot outlive the verified JWT
expiration even while its host transaction remains open.

`authorize(action, entity_id)` binds one action and target to the same grant.
A personal key's actual persisted scopes and anchor/inheritance intersect that
grant; unrestricted legacy keys require explicit host configuration. Usage is
accounted once by real authentication, not once per subsequent decision.
`authorize_account(action, user_id)` resolves the durable customer root and
refuses Internal, platform-protected, retained administrative subjects and
accounts assigned system-wide roles, including future or suspended definitions.
A practice grant/key cannot authorize the customer's root credential operation.

`create_personal_key` is a separate opt-in JWT-authenticated self-service path.
It takes exact nonempty bounded actions and a durable anchor, derives its owner
from verified context, holds all qualifying grants and issues an opaque approval
bound to policy instance, transaction, owner, epoch, anchor and scopes. Native
SDK and mounted creation paths retain their tenant-root policy. A supplied
boolean/dictionary, extra scope, wildcard or unrelated anchor cannot mint a key.
Update/rotation and the full credential operation inventory remain release gates.

## SQL projection and transaction discipline

`entity_page(action, limit, cursor, customer_root_id)` filters action, target,
current grants, pinned group admissions, key ceilings and valid active topology
in SQL before count, sorting and pagination. Count/page share one statement.
It returns a small entity projection, not arbitrary IAM rows. The recursive
parent selector checks exact closure agreement; corrupt paths exclude rows.
Pagination uses a bounded UUID keyset and expiring signed cursor bound to actor,
credential, action, filter and current policy/key fingerprint. Current group
admissions are re-evaluated on every page. List admission does not establish
write authority or copy grants into ordinary user permissions.

For sensitive writes, call `authorize(..., protected_write=True)` in the same
transaction as the effect, check `allowed`, then commit through the host unit of
work. The facade holds only the selected grant and its permission/template,
applicable admission/group and target ancestry, plus a personal key parent when
used. It rechecks the same qualifying grant after any lock wait. It does not
silently select another grant. Account operations also hold the target user and
assigned role definitions to serialize new assignments and classification.

Migration `20261011_0028` follows `0027`. It closes a holder's retained grants
when account security epoch, root or status changes. Parent-row trigger fences
cover API-key scope, permission-condition and user-role membership INSERT,
UPDATE and DELETE, including insertion into an empty collection. These invoker
triggers apply to raw DML too; restricted consumer DML privileges must still be
qualified. Source sync must never write these administrative grant tables.

No decision cache, global mutex or SERIALIZABLE isolation is introduced. Hosts
must set appropriate lock/statement budgets and handle rollback on database
failure. Deterministic multi-target ordering, timeout/deadlock failure injection,
and all consumer supported writers are not accepted by these focused cases.
Time expiry is rechecked before returning a protected decision; the host must
apply its effect immediately in the same bounded transaction.

## Local qualification

- All **1,585 collected tests pass**, zero failures/errors/skips, PostgreSQL 16
  and required Redis 7. Four disjoint file shards cover exact collected nodes:
  214, 214, 214 integration cases and 943 unit cases. JUnit totals/exit codes
  match the collection manifest.
- **18 new integration cases**, including actual HTTP host routes and verified
  credentials, SQL action/count/keyset/group/closure behavior, personal-key
  issuance/proof, account-root and dormant platform protection, and eight real
  competing-transaction cases. Database lock observation proves a sensitive
  effect commits before grant/template/admission/security/key-scope/condition/
  entity withdrawal or future role classification proceeds; later access denies.
- Genuine populated installed a37 upgrade reaches `0028`, retaining existing
  UUIDs, credentials and platform classification. Frozen lifecycle rollback,
  savepoint/cancellation and retained evidence cases remain green.
- Fresh noneditable wheel and sdist each pass **45 focused cases**, plus actual
  configured-constructor failure/commit and original-name retention smoke.
  All **239 packaged files** match the wheel in both installed environments.
- Ruff, changed Python Black, MyPy across the five touched service/facade modules,
  and release metadata checks pass. Public a37, primary checkouts and unrelated
  documentation work are preserved. No publication, push or deployment.

| Artifact from the runtime commit | SHA-256 |
| --- | --- |
| `outlabs_auth-0.1.0a38-py3-none-any.whl` | `5202a3baeabbe1d5d2fb89fc4b4337dc36c7b3369769bb12f6ca740e3ba29245` |
| `outlabs_auth-0.1.0a38.tar.gz` | `91f419c59b3dd6f9dd0a91707f5a1aa20d6417b05ab4fe69376d5299ad2dfc6b` |

Local artifacts/logs are disposable evidence under
`~/Documents/tmp/business-api-a38-context-sync-20261011/`. These artifacts
supersede the earlier local foundation and `2e9097c` builds; no a38 release exists.

## Remaining exits

The functional recursive list query is not the plan's 50k-customer performance
acceptance or indexed stored-root architecture. Actor grants are bounded to 64,
pages to 100; numeric query/latency/memory and degraded-cache budgets remain open.
Existing mounted IAM lists/detail/account controllers are not automatically
rewritten by the facade. Broader credential and supported writer inventory,
restricted-runtime migration/DML privileges, multieffect failure fencing,
maintainer review and artifact publication precede consumer adoption.

The business API remains on a37. Its recurring Mongo contribution planner is
host-owned, preview-only; durable crosswalk/episode/contribution ledgers,
conditional apply, recovery fencing, outbox/UNKNOWN outcomes and consistent
capture acceptance must qualify before automatic recurring writes.
