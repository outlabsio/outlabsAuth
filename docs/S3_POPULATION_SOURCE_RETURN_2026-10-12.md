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
reactivation, cleanup and rollback. Full source/Redis/installed artifact receipts
will be recorded after qualification of this commit.
