# S2 opt-in customer account and membership mount

12 October 2026. Unreleased a38 runtime `180a191`; schema remains
`20261012_0031`. [Earlier facade/key/list qualification](S2_MOUNTED_IAM_PERFORMANCE_2026-10-11.md)
remains historical. Ordinary IAM routes and existing consumers are unchanged.

The explicit staff router adds customer account detail, root-qualified SQL page,
first/last-name editing, active/suspended lifecycle, retained delete and restore.
Whole-account actions need one qualifying action/selector covering the actual
customer root, including a personal key's root envelope. Root transfer, email,
password and privilege inputs are forbidden. SQL count/page excludes Internal,
superusers, retained platform classification and any direct/entity-assigned
system-wide role or retained administrative grant before returning a total.

Membership detail/create/native role replacement/remove/explicit reactivation
locks the actual subject, assigned/requested definitions and target ancestry
before final qualifying-grant approval. Ownership comes from the stored customer
root. Assignment is restricted to active customer-owned roles; the membership
service enforces entity availability/types. Creation and update have separate
actions. Native assignment of a sourced role remains an independent intention;
source withdrawal preserves it. Native account restore retains the security
boundary and does not revive revoked memberships or privileges.

Local proof for `180a191`:

- **14** new actual HTTP cases: commit-visible account/member effects, protected
  target and sibling refusal, forbidden security fields, root/leaf distinction,
  bounded SQL count excluding protected users, personal-key restrictions,
  ordinary-route isolation and native/source overlap.
- All **1,647** collected source cases pass across disjoint owned PostgreSQL/
  required-Redis shards. Initial parallel qualification had one in-process
  Alembic timeout in the concurrent-runner test under fixture load; all fifteen
  migration cases passed independently, then the full affected **235-case shard**
  passed on a fresh DB with unchanged bounds/assertions. Final receipts use that
  whole-shard run; the failed attempt remains preserved.
- Independent required real Redis contract: **102/102**, zero skips.
- Fresh noneditable wheel/source package: **81/81 each**, constructor/frozen
  history/genuine a37 migration acceptance, and **243** package-file byte matches.
- Full Ruff, changed-file Black and two changed modules in MyPy pass. Broad
  inherited formatting drift remains. An accidental broad format operation was
  fully reverted on unrelated files before the qualified commit.
- Canonical handbook port `2658b2d` passes lint/typecheck/build/rendered text.

Wheel SHA-256: `83e1643c25804ffff4b002683578e2ca73d84ea5a069cf75b16db59fd936d43a`.
Source-package SHA-256: `83c263578c076297f486d096cbb1e981a03b3afccc46630b6ced49d6fca7e536`.
Private scratch receipts: `~/Documents/tmp/iam-delivery-20261012/`.

This is bounded human account/member admission, not a grant-management, generic
credential reset, entity/role-definition administration or namespace release.
Broader group/worst-case capacity, restricted runtime DML, multi-host recovery
admission, review/release and exact consumer adoption remain separate exits.
The host owns source normalization, delivery-provider semantics and reconstruction
of later native revocations. No new public version, tag, push or deployment.
