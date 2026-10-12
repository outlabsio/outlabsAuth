# Native and source membership ownership: local qualification

This is the earlier ownership checkpoint. Reviewed invited identity creation
and source-only return continue in
[S3 population and return](S3_POPULATION_SOURCE_RETURN_2026-10-12.md).

12 October 2026. Unreleased a38 runtime `70d15c9`; Auth head `20261011_0030`.
Public a37 remains the released version. This follows
[mounted staff credentials and performance](S2_MOUNTED_IAM_PERFORMANCE_2026-10-11.md).
It adds a trusted SDK primitive; no source reconciler or new HTTP admission is
enabled in existing consumers.

## Ownership contract

Existing memberships and membership-role rows backfill `native_owned=true`.
Unknown legacy provenance is never relabelled as source ownership. Opaque stable
UUIDs in `membership_source_claims` own one attachment; `membership_source_roles`
owns the exact role subset for that relationship. A host owns stable mappings,
review, source completeness, cutover and recovery admission.

`MembershipService.set_source_membership(session, source_id=..., entity_id=...,
user_id=..., role_ids=(...))` replaces that source's intention. `role_ids=None`
withdraws only that source. It does not initialize, transfer, delete or edit the
account; change credentials or preferences; issue invitations; or send messages.
It rejects protected subjects, root contradictions, inactive/global/wrong-scope
roles, duplicate/oversized role sets and native lifecycle/validity overrides.

Effective roles are the union of native intentions and all source intentions.
Native `add_member`/role replacement records native ownership even when a source
already grants the same role. Replacing native roles retains independently
owned source roles. Auto-assignment also records a native intention when the
effective role already exists. Native full membership suspension/revocation
still blocks access; source replay cannot reactivate it.

Last-source withdrawal revokes a source-only membership and records lifecycle
history, while preserving the account. A native attachment or another source
keeps the membership. Memberships left revoked require an explicit native
reactivation before a later source return; no inferred automatic restoration is
implemented. Source claims restrict hard deletion of claimed memberships/roles;
withdraw ownership explicitly before destructive cleanup. Account initialization,
same-email qualification and invitation/recovery delivery remain separate.

## Compatible writer fences

Source and native SDK membership writers lock the user before reading ownership.
Migration 0030 makes membership, effective-role and source-child DML lock the
owning user, including inserts into an empty collection. Administrative-grant
insertion also locks its holder. Role permission/condition/entity-type/group
children lock their role; permission-owned groups lock their permission;
closure children lock the descendant entity. Source claim IDs cannot transfer
to another membership. Fresh snapshots after locks are required.

These are row-scoped database fences. Hosts must lock and freshly validate the
selected accounts, real ancestry, role definitions and permission definitions
before applying a review. Lock timeout/deadlock is a rejected unit requiring
rollback, never an allow fallback. This does not certify arbitrary privileged
DML, trigger disabling, TRUNCATE, schema/owner access, mixed old membership
writers or a production recovery/lease service. Restricted runtime grants and
full consumer acceptance still precede activation.

## Local proof

- Full source suite: **1,620 passed, zero skips/failures/errors**, on four isolated
  PostgreSQL databases with required Redis and genuine installed public-a37
  upgrade. Runtime/source `70d15c9b935f9d085d40a9ae162491253c003e7b`.
- Twelve new real migrated PostgreSQL cases prove native same-role intention,
  native replacement/source union, overlapping sources, last-source withdrawal,
  credential/native-suspension preservation, scope/transfer denial, rollback,
  raw child/empty-collection parent locks and competing native assignment.
- Genuine a37 populated membership/role upgrade preserves the rows as native,
  leaves source claims empty, preserves account credentials and reaches 0030.
- Ruff, touched-file Black, affected membership/model MyPy and release metadata
  pass. Dedicated installed-artifact and independent Redis gates also pass below.

Broader mounted account/member staff admission, group/worst-case performance,
restricted runtime DML and review/release/consumer activation remain open.
Source reconciliation, frozen absence episodes and recovery/provider outboxes
are host-owned contracts and require separate acceptance.

## Installed artifacts and independent Redis

- Independent required real-Redis run: **102 passed, 1,518 deselected, zero skips**.
- Fresh noneditable wheel and source package: **54 focused cases each, zero
  failures/errors/skips**, including managed-key HTTP, target/list/lock gates,
  real a37 upgrade, 10,000-root query budgets and all twelve new ownership cases.
- Each installed package matches all **242 package files** against the wheel.
  Both configured-constructor smokes prove shared observer dispatch, caught
  observer failure refusing commit and original names surviving hard deletion.
- Wheel SHA-256: `37e35e45b2568ff3045f98e4d3d1b6e227f7cb381f469cb3eb390b6b2043618e`.
- Source package SHA-256: `4f66430530308112e6de0ef5e54516b26dd3ad0a2657d039b724448eec3cbc4c`.

The first installed-test attempt omitted async fixture mode when tests were
copied outside the repository. Its 53 fixture failures are discarded. Final
runs explicitly use `--asyncio-mode=auto`; no product assertion was weakened.
Disposable receipts remain outside Git/vault in the operator's scratch folder.
No push, publication, consumer pin change or deployment occurred.
