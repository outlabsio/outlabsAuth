# Explicit customer role catalog policy — 14 October 2026

The previous a38 candidate rejected all `role:*` staff templates. Internal
customer-role administration therefore requires a deliberate library contract
extension. A host alias for those permissions would obscure that boundary.

`AdministrativeGrantService.create_template(..., customer_catalog=True)` now
allows exact `role:create`, `role:read`, `role:update` and `role:delete` and seals
`customer_catalog: bounded-customer-role-v1` into the immutable policy hash.
Default template creation still rejects role actions. Wildcards, other role
actions and the remaining control-plane resources remain refused.

The evaluator and credential facade require their own explicit
`customer_catalog=True` argument for a role decision. Unmarked policies and
ordinary callsites deny. Existing JWT epoch, active holder, exact target/action,
grant window/template/permission validity, key boundary, target path and
qualifying-grant protected-write fences remain mandatory. This introduces no
schema or ordinary IAM-router change, shared identity or global principal.

This is a host capability boundary, not a generic roles router. A qualified host
must derive resource ownership from stored rows, reject global/system/automatic
and advanced-policy roles, check each delegated permission at the same target,
prove containment of the role's effective entity/descendant reach (or permit only entity-local, entity-only writes; unscoped root roles still inherit),
use the canonical role service, preserve attribution/history and fence the
actual SQL credential. The qualified host candidate uses a distinct catalog engine and
explicit staff surface with owner-enrolled customer roots, permission definitions
and Internal actor IDs. Customer and Internal roots remain separate.

Eight new library cases cover default/template/callsite admission, sibling and
Internal refusal, forbidden control-plane/wildcard actions, a correctly hashed
legacy-shaped unmarked policy and protected-write revocation. Host mounted,
cached, SQL containment and recovery evidence lives with that consumer; it is
not a generic library deployment claim. Final source/artifact and complete local suite results are appended below;
consumer-specific deployment evidence belongs in the owning application.

a38 remains unpublished. Public consumers remain pinned to a37. No change here
authorizes enabling catalog scope by default, updating existing templates in
place, changing ordinary customer IAM visibility or shipping catalog-key
issuance/rotation without its own exact lifecycle acceptance. Independent
source/artifact review remains required before release/adoption.


## Local library evidence

Runtime source `61f8b6b984657713702854a73b8e93b3adda5290` passes the full
1,663-case collection in three disjoint local shards: 1,662 pass and the genuine
public-a37 migration case skips without its separate interpreter. That same
case then passes from the installed candidate wheel with a genuine public a37
interpreter, covering all 1,663 distinct cases. The eight new policy cases also
pass from the installed wheel outside the source checkout, with zero skips.
All source Redis-dependent fixtures were required, backed by real local Redis.

Wheel SHA256:
`bad724fdfb2f85b23df0337009721ec07f86b1b183df1103d62bc60eb995467b`.
All 243 package files match installed wheel and source byte for byte. Existing
source schema/migration heads remain unchanged. Full Ruff and the two changed
service files' MyPy pass; changed Python files pass Black. Whole-repository
Black still reports 131 unchanged files, with no overlap with this change; that
pre-existing formatting baseline was not relabeled green. An initial interrupted
single-process trial and repaired test-fixture trials are not acceptance proof.

No new sdist qualification is claimed for this wheel. This artifact changes the
previous local a38 wheel and needs new independent exact source/artifact and
consumer review, sdist/packaging qualification and release/adoption acceptance.
The source/version label a38 alone cannot substitute for its exact bytes.
