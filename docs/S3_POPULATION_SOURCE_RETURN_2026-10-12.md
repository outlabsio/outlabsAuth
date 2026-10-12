# S3 reviewed identity population and source-only return

12 October 2026. Unreleased a38; Auth schema `20261012_0031`. This adds to
[S3 ownership](S3_MEMBERSHIP_OWNERSHIP_2026-10-12.md). Public a37 and other
consumer manifests remain unchanged.

The trusted `create_source_user` primitive admits a pre-reviewed UUID/email/root
as invited with no password, email verification, session, challenge or mail.
Collisions refuse instead of adopting or merging accounts. Existing customer
entities and explicit identity aliases are host prerequisites. `create_role`
accepts an optional reviewed UUID for host-owned customer-root catalog creation;
public HTTP inputs and ordinary role creation remain unchanged.

Source-only return needs durable proof written after the last source withdrawal
and effective role projection. Its membership ID, DB write revision and account
security epoch must still match. Native role writes, membership DML including
same-value updates, repeated SDK removal/lifecycle intent and account security
boundaries invalidate it. A retained proof survives hard deletion and denies
recreating a natively deleted attachment. Native reactivation records a native
attachment; future source absence preserves it. Native revocation still permits
source cleanup but cannot manufacture return proof. Historical revoked rows
without proof require native acknowledgement. Same-value native intent from
older SDKs that emit no DML remains outside this compatible-writer qualification.

0031 is forward-only, supports metadata-created test schemas and adds revision
and withdrawal fences after 0030. Restricted runtime DML and consistent deployed
SDK/schema versions remain activation gates. DB-owner tampering is not a supported
runtime path. The host must bind a complete immutable cut, exact live target,
code and recovery admission, and own the encompassing transaction; the SDK alone
is not a replay scheduler or account delivery protocol.

Local focused acceptance: 13 actual migrated PostgreSQL cases pass, including
no credentials/challenges, both collision types, same-membership source return,
native same-value SDK/DML, role DML, security epoch, hard deletion, native
reactivation, cleanup and rollback. Full qualification for runtime `439c661cf34ecb6acdc1697c1773a7b3b9b63d95`:

- All **1,633** collected source cases pass across four disjoint local shards
  with real owned PostgreSQL and required Redis, **zero skips/failures/errors**.
- Independent required Redis selection: **119/119**, including expiry,
  transactional freshness, recovery and cached numeric budget regressions.
- Fresh noneditable wheel and source-package installs: **67/67 each**, plus
  constructor/shared observer wiring, poisoned-commit refusal and original frozen
  names after hard deletion. Both installs match all **243** wheel package files.
  The installed migration case includes genuine a37 population/backfill; new
  return/new-account tests run against actual migrations, not metadata-only proof.
- Full Ruff and targeted services MyPy pass. All changed Python files pass Black.
  Broad Black reveals inherited unrelated formatting drift (114 files before the
  changed migration was formatted); it is not qualified or silently reformatted.

The source collection manifest, JUnit counts and owned service identities are
retained outside the vault under `~/Documents/tmp/member-population-20261012`.
Wheel SHA-256: `6e685e9a3b9ca5208cb4d24b314457099b2983fc33b4610715602b264b9b8570`.
Source-package SHA-256: `557e344e3b2c2e1b550ac2e11d27fda677e9f8d9262d6195a2ca98b960431121`.
These artifacts are built from the runtime commit; this qualification receipt
and subsequent documentation edits do not change package code. Release remains
unapproved/unpublished and requires its own exact final-source/artifact review.

The first owned-run failures found the earlier revoked-status guard; it was fixed,
then all thirteen source-only-return assertions passed. Empty-array/canonical
catalog/test-message corrections belong to the separately qualified host adapter.
An initial artifact dependency attempt included the editable source; it was
refused, corrected before installation, and only fresh noneditable/byte-verified
runs above count as artifact evidence.
