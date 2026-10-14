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
