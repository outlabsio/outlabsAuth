# Independent tenant isolation and identity lifecycle review

Reviewed commit: `58230e25ceb373302dc48e167f1dbbe60197d393`.
Reviewed proposal: `docs/TENANT_IDENTITIES_AND_ADMINISTRATIVE_GRANTS.md`, revision 0.1, 2026-10-10, complete 1,937-line committed document.
Review method: `docs/TENANT_AUTH_REVIEW_PACKET.md`, revision 0.1, complete 606-line document.
Lane: credential namespaces, customer ownership, identity resolution, authentication and identity lifecycle, legacy conversion, and separation of account administration from practice authority.
Review date: 2026-10-10.

**Verdict: Revise before implementation for the lifecycle contract and baseline claims identified below.** The namespace and ownership direction survives this review's adversarial scenarios; I found no need to replace it with either a global person identity or a namespace derived from mutable hierarchy. The proposal needs a precise disposition of privileged restoration, pending credential enrollment after security changes, and deleted-identifier edits. Its existing G0 decisions also remain open. The findings do not authorize implementation, release, migration, or deployment, and are not evidence about any deployed consumer.

The four findings are newly established counterexamples in the existing baseline, with implications for the proposed contract. They are **not** claims that unimplemented namespace functionality is already broken. Some corrections already follow from the proposal's general requirements; those are implementation acceptance obligations, not new architecture defects. The baseline statement that restore does not restore access is materially inaccurate.

## Evidence and boundaries

I read the repository `AGENTS.md`, the complete proposal and review packet, pertinent prior design decisions, and current source for User, SocialAccount, OAuthState, AuthChallenge, RefreshToken, UserService, AuthService, password/OTP/magic-link/invitation paths, OAuth login and association, OAuth state consumption, JWT encoders and authentication strategy, membership/root scope, permission bypasses, protected-user mutation guards, and the administrative evaluator. Relevant existing unit and retained-deletion integration tests were inspected.

The reviewed baseline is the cited a36 source, `7ec9acf77f37ead0d7eb50347334224cc9d72e87`. The runtime diff from a36 through the reviewed commit adds the side-effect-free administrative evaluator; the examined identity runtime is otherwise unchanged. The evaluator is unwired, as expressly stated at proposal lines 186–198. Its tests cannot establish namespace resolution, durable grants, service guards, lifecycle transactions, or deployed isolation.

The checkout was clean when the review began. During final citation verification the working proposal changed independently. I excluded those uncommitted edits and verified proposal citations against `git show` of the requested commit. All proposal line references below identify revision 0.1 at the reviewed commit, not a subsequent working copy. No other review report or agent findings were read before completing this review. No repository or vault file was edited, no git state was changed, and no infrastructure or external communication was initiated.

## Newly discovered counterexamples

### TI-01 — High: identity-only restore reactivates retained superuser authority

**Evidence:** Proposal `docs/TENANT_IDENTITIES_AND_ADMINISTRATIVE_GRANTS.md:173` calls the baseline restore non-access-restoring; lines 737–740 require identity-only restore and no resurrection of staff administration. `outlabs_auth/services/user.py:1171` sets deletion status without clearing `is_superuser`; `outlabs_auth/services/user.py:1001` restores ACTIVE without clearing that flag. `outlabs_auth/services/permission.py:502` grants all permissions to a superuser and `outlabs_auth/services/permission.py:1212` returns `*:*`. `outlabs_auth/services/user.py:1058` actually refuses to change superuser privileges while the user is DELETED, so an operator cannot separately clear the flag on the retained row through that method before restore.

**References:** R13, R25; U05, U34, U44; T30; D07/D25/D26; A05/A07/A11.

**Reproduction:** Create synthetic Internal operator `operator@example.com` with `is_superuser=True`. Delete it using the ordinary retained-deletion service. Its memberships, direct roles, refresh tokens, and keys can all be revoked correctly while the flag stays true. Restore the retained identity without a separate platform privilege grant. The account is ACTIVE and still a superuser. Calling the actual permission aggregation service returns `['*:*']`. The synthetic check reproduced this with the actual delete/restore and permission methods and mocked persistence.

**Consequence:** A workflow described as restoring only an identity silently restores platform authority. Retained deletion becomes a temporary status gate for this authority rather than revocation. This is particularly dangerous during incident recovery or source reconciliation. It does not show that a practice manager can restore an arbitrary protected operator: the existing protected-target guards still restrict those actors, and the counterexample assumes an authorized restorer.

**Correction:** Decide explicitly how deletion revokes the effective superuser/platform authorization while retaining the historical privileged classification used to protect the account from limited administrators. Do not simply clear the only privilege marker and thereby make a former operator look like an ordinary manageable account. Restore must require a separate explicit platform regrant, or privileged identities must be excluded from ordinary restore and handled by a dedicated audited recovery operation. Correct the baseline table and ensure the migration contract preserves historical protection without preserving active bypass authority.

**Gate:** This is a specification clarification before WP00/G0 acceptance of the restoration contract and a functional blocker for WP02/G1 and WP04/G2 when those operations are implemented. Add a privileged target to retained-deletion tests; assert restore alone cannot produce a permission bypass. It is not merely a deployment checklist item. The proposed requirement already rejects privilege resurrection; the new issue is the baseline contradiction and the unchosen treatment of a retained privilege flag.

### TI-02 — High for protected accounts, Medium otherwise: deleted access JWTs become valid again after restore

**Evidence:** Proposal lines 701–707 require current retained user/namespace/session checks, and lines 737–740 require deletion to revoke sessions. `outlabs_auth/services/auth.py:852` revokes refresh rows only; `outlabs_auth/services/auth.py:814`–848 accepts a signed access token based on its subject, current status, and password-change timestamp. `outlabs_auth/authentication/strategy.py:154`–157 similarly checks only password staleness and current authentication eligibility after any per-JTI blacklist check. Neither `outlabs_auth/services/user.py:1171`–1175 nor `outlabs_auth/services/user.py:1001`–1004 advances a durable session revocation epoch. The token's persisted refresh family is not consulted by those access paths.

**References:** R08, R13; U26/U34; T15/T30; D09/D10; A05/A10/A13.

**Reproduction:** Mint an unexpired access JWT for an ACTIVE synthetic account, then delete the account. Both AuthService and JWTStrategy reject the JWT while the account is DELETED. Restore before that JWT expires, without a password change. The exact same JWT authenticates again through both methods, even though the associated refresh row remains revoked. This was reproduced using real JWT signing/verification and actual delete/restore/AuthService/JWTStrategy code with mocked database results. No token text was recorded.

**Consequence:** Restoring an identity also restores possession-based access from a session supposedly revoked by deletion. A stolen pre-deletion access token can recover account self-service or any authority granted after restore; combined with TI-01 it recovers platform authority. Ordinary revoked memberships and keys need not themselves revive for this to be a real session revocation failure. The window is the access token's remaining lifetime, rather than an unlimited refresh window.

**Correction:** Retained deletion must durably invalidate every old session independently of current account status, for example by advancing a monotonically increasing account/session security epoch checked by both bearer verification paths, or by a consistently enforced persisted-family invalidation contract. Restore must not lower or reset that marker. Refresh-only revocation and temporary status checks are insufficient. Apply the same rule when D25 conversion invalidates old sessions, and define how legacy tokens lacking the marker are rejected or bounded.

**Gate:** The intended behavior is already in the specification; this is a new baseline counterexample and missing negative test, not a new topology decision. Correct line 173's baseline claim before specification acceptance, then block WP02/G1 session qualification until both service and request authentication paths prove deletion → restore does not revive old JWTs. Include protected and ordinary accounts, cache conditions, legacy-token policy, and a delete/restore race in A05/A10. No new G0 architecture veto is necessary if the current-state session contract is made enforceable.

### TI-03 — High: pending OAuth association survives password security reset and inactive-account transitions

**Evidence:** Proposal lines 453–457 call for flow-specific OAuth epochs; lines 656–658 require security changes to invalidate outstanding state according to type. The explicit OAuth state list at lines 671–676 binds account/namespace/profile/browser/PKCE/nonce, but does not define how revocation of the initiating credential proof cancels method enrollment. `outlabs_auth/routers/oauth_associate.py:177`–200 issues state from an authenticated account without a credential/session epoch. `outlabs_auth/routers/oauth_state_store.py:125`–132 verifies expiration, one-use state, browser binding, exact user and profile, but not current account eligibility or the initiating proof's continued validity. In the association callback, `outlabs_auth/routers/oauth_associate.py:375`–380 checks only that the retained user exists; lines 448–468 add the provider identity, append the auth method, and commit. `outlabs_auth/models/sql/oauth_state.py:107` defines validity as unexpired and unused. A password reset changes `last_password_change` at `outlabs_auth/services/auth.py:1379` and revokes refresh tokens at line 1389, without cancelling these OAuth states.

**References:** R08/R13; U29/U34; D08/D10/D24; A04/A05/A10; credential enrollment is also a root-account operation under proposal line 867.

**Reproduction:** A temporary holder of the victim's local session starts an association with an attacker-controlled provider account. The owner performs a password security reset and revokes local sessions. Within the association state's ten-minute validity window, the attacker completes the same otherwise-valid browser/PKCE/provider flow. The callback can still attach the provider subject. Later OAuth login uses that new method and bypasses the changed local password. A second counterexample starts a valid flow, suspends or retained-deletes the local account, and completes it: the callback still inserts and commits the link. It does not mint an ACTIVE session while the account is suspended/deleted, but the credential enrollment survives that lifecycle transition.

The synthetic callback check deliberately mocked already-valid state consumption and provider responses. It tested the subsequent account-mutation admission, using the actual callback code. ACTIVE with a later password timestamp, SUSPENDED, and DELETED all inserted and committed a SocialAccount. This does not claim to bypass OAuth cryptography or the browser binding.

**Consequence:** Exact UUID/namespace and one-use state prevent account substitution, but do not establish that the authority which permitted enrollment still exists. A recovery action can remove the compromised local credential and nevertheless allow that earlier compromise to establish a fresh login method. A later restored account can carry a method added during deletion.

**Correction:** State the cancellation matrix explicitly: method enrollment must bind a durable credential/security epoch and an initiating authentication proof/session where applicable, and must check current account and namespace eligibility at the enrollment commit. Password security reset, terminal deletion, and incident revocation must permanently cancel earlier enrollment proofs; decide ordinary logout and routine password-change semantics separately. Serialize the enrollment commit against those security mutations under D10's shared transaction protocol. A current-state check at token minting alone cannot repair an already-committed unauthorized provider link. If this contract is deferred, disable association in the qualified capability instead of inheriting the baseline callback.

**Gate:** D08 and D10 are expressly open, so this is a concrete input to their disposition rather than a newly invented open decision. Clarify the enrollment cancellation rule before WP02's flow contract is accepted; block WP02/G1 association qualification and the sensitive mutation portion of G2 until A04/A05/A10 prove reset, revoke-all, suspension, delete → restore, namespace suspension, and commit-order races. Namespace-bound state alone is insufficient closure evidence.

### TI-04 — Medium: editing a deleted user releases its supposedly retained email reservation

**Evidence:** Proposal lines 421–424 require deleted accounts to keep their identifier reservation, lines 428–429 permit email to remain on User, lines 737–740 preserve reservation through deletion, and D18 at line 1813 defers explicit reuse/purge. `outlabs_auth/models/sql/user.py:53` makes the current email column unique. `outlabs_auth/services/user.py:654` fetches the row for profile editing and lines 671–684 replace its email without rejecting DELETED status. The ordinary administrative profile route at `outlabs_auth/routers/users.py:1135`–1174 calls this service after target authorization. In contrast, the status method expressly rejects deleted users at `outlabs_auth/services/user.py:911`.

**References:** R06/R15; U22/U34; D04/D18/D19; T14/T30/T34; A01/A03/A11.

**Reproduction:** Retained-delete `reserved@example.com`. An authorized account-profile editor calls the existing update service with `replacement@example.com`. The actual method keeps the row DELETED but changes its email column. With only uniqueness on the current column, `reserved@example.com` is no longer reserved by that row and can be assigned to another UUID. The synthetic service check reproduced the deleted-row edit. The resulting release of the unique key follows from the schema; an actual database insertion was not run.

**Consequence:** Ordinary profile maintenance can perform the identifier-reuse operation that D18 proposes to defer to a reviewed purge/reuse workflow. Restore returns the original UUID under a different address, and prior source/identifier history no longer identifies an exclusive retained reservation. This is not evidence that properly epoch-bound old challenges would authenticate the replacement UUID; that stronger consequence was not assumed.

**Correction:** Specify whether authentication identifiers on tombstones are immutable until privileged purge/reuse. Enforce that invariant in supported service and writer paths, or store the retained deletion reservation independently from the editable contact/profile field. The smaller User-email model remains viable with an explicit lifecycle guard; a full history ledger is not automatically necessary. Do not confuse this with active-account email changes: the plan may deliberately free an old active address after invalidation under D19.

**Gate:** Clarify this edge of D04/D18 before G0 schema/lifecycle acceptance, and require WP01/WP02/G1 checks for direct services and HTTP profile writes. A01 must prove a deleted-identifier edit cannot bypass the reservation, and A11 must prove an explicit reuse operation has the required evidence. This is a specific bypass of the proposed default, not an argument that the already-open choice of identifier storage is itself a defect.

## Existing open decisions and acceptable proposed defaults

The following are already visible gates, not additional novel findings:

| Existing choice | Lane assessment and necessary disposition |
| --- | --- |
| D01/D02: stable namespace, independent customer roots | A reasonable default. Immutable non-null namespace plus restricted owner-root mapping prevents root deletion or regrouping from changing credential ownership. Ordinary same-customer memberships and cross-customer staff grants remain different relationships. |
| D04/D18/D19: email canonicalization, phone-auth reservations, retention and edits | Existing normalization without provider-specific stripping is a defensible first release. Separate authoritative phone-login reservations avoid turning shared contact metadata into authentication ambiguity. The smaller model is acceptable if TI-04's lifecycle invariant is explicit; active identifier reuse and verification policy still require a recorded choice. |
| D05/D09/D16/D17: legacy/Simple mode, old credentials, explicit context and writer fences | A fixed legacy namespace and initial Enterprise-only qualified mode are reasonable exclusions. A token/challenge adapter must not infer namespace from current root or email. Invalidating unverifiable old credentials is safer than an ambiguous bridge. The operational fence against unchanged old binaries is already acknowledged, not a newly discovered issue. |
| D07/D08/D10: granular actions, explicit provider association, current revocation | Human staff grants with no delegation and explicit same-account association are useful bounded defaults. Account credential operations must use owning-root authority; practice roster authority must not invoke them. The exact sensitive-operation and cancellation rules must include TI-01–TI-03. |
| D11/D21/D24/D25: transfers, shared provider subjects, OAuth-only recovery, legacy conversion | Prefer new identities for unrelated ownership changes, allow qualified local provider links without implying independent upstream passwords, and avoid implicit PASSWORD enrollment during OAuth-only recovery. Preserve a legacy UUID only after verified single ownership and complete reference accounting. These are acceptable proposed defaults with their stated costs; a reviewer cannot record their acceptance for the owner. |

The complete decision register is expressly proposed at lines 1790–1821. Resolving these gates is still required even if all four counterexamples are fixed. None of the baseline focused tests supplies those decisions.

One projection question belongs within the already-open D07/D14 contract. Proposal lines 593–599 permit a same-namespace invitation to return an exact identity result or conflict, while U11 limits a practice-only manager's account visibility. In Customer B, a West-only manager can invite a known email that currently belongs only to East. Define whether existence, UUID, lifecycle status, and profile fields may be revealed at this step. Minimal relationship-oriented responses or a separate customer-directory permission are defensible choices; returning a full User response by reuse is not justified merely by same-customer eligibility. This is a **Question**, not a proven cross-customer leak. Close it in WP04/WP05, A02/A06/A09, before enabling that invitation API. An explicitly accepted minimal directory consequence may be acceptable.

## Flow coverage and adversarial conclusions

| Flow or boundary | Evidence and conclusion |
| --- | --- |
| Same-email identities and customer selection | Proposal lines 398–426 require stable namespaces, one canonical scoped namespace per root, a fully accounted legacy conversion, and no membership-driven namespace move. Lines 561–599 resolve trusted context before identifier and reject conflicting context. With those conditions, an A login or recovery cannot fall back to C or Internal. Client-selected IDs remain inputs to server validation. No contrary proposed lookup rule was found. |
| Registration, invitation, resend and existing-user reuse | Baseline create/invite still use global email (`services/user.py:477`, `:1477`). Future qualification is explicit at lines 593–599 and 624–654: exact account and target, same-namespace reuse, issuing authority rechecked, no credential reset for a practice invite, one-use/idempotency policy and no silent restore. Test concurrent create/invite collisions and revoked grantor activation under A01/A02/A10. Missing future fields are not new design findings. |
| Password login and account eligibility | Baseline uses global email at `services/auth.py:159`; the proposed resolver, dummy work, per-account lockout and aggregate anti-abuse rules at lines 609–620 are adequate requirements. Account authentication without business memberships is a stated bounded self-service choice, not proof of business authority. |
| Reset, magic link, email/phone verification and access codes | Baseline magic-link redemption marks current email verified without a recipient check (`services/auth.py:1779`); OTP paths resolve email/phone before finding the challenge (`:1470`, `:1486`). These are already expressly covered by R15, U26 and lines 647–667. Required A03 checks must exercise stale destination, exact UUID/namespace/profile, authoritative phone reservation, attempts and atomic one-use redemption. I did not count this known future work as a new design defect. |
| OAuth login, provider subject and association | The namespace-qualified registration/issuer/subject key and ban on cross-namespace provider-email linking are sound boundaries. The baseline global-email link at `routers/oauth.py:554` is explicitly superseded by D08. Changed/absent provider email must keep the stable local link, and the same upstream account in two customers does not imply independent upstream SSO security. TI-03 adds the method-enrollment lifecycle case. |
| Access/refresh/session provenance | `utils/jwt.py:336`–350 deliberately does not copy arbitrary additional claims into refresh payloads; `tests/unit/test_jwt_utils.py:125` tests that behavior. Proposal lines 453–457 already warn about this exact encoder distinction, and A05 requires every issuance path. This is a documented implementation trap, not a new finding. Rotation must preserve qualified account/namespace/profile and never derive a new identity. TI-02 adds restoration revocation. |
| Identifier edits, retained deletion and restore | Epoch-bound destination checks close the proposed old-email/new-email substitution. Retention is not equivalent to an account status toggle: privilege flags, access sessions and identifiers need separate enduring rules. TI-01–TI-04 provide concrete counterexamples and negative cases. |
| Legacy conversion and ownership transfer | Lines 1418–1449 require verified single ownership, every reference reconciled, rekeyed social/identifier rows, epoch increments and session/challenge invalidation. Ambiguous/shared accounts require a reviewed split; credentials/MFA/provider copying is an explicit decision and sessions/recovery state cannot be blindly copied. This addresses the obvious UUID-retention hazard. No synthetic real-DDL or host-reference conversion was executed, so its feasibility remains unproven. |
| Internal and platform separation | Same-email identity equality is never operator authority. Trusted Internal designation, protected control-domain objects, explicit account-root operations, and preserved dormant privileged-account protection are substantial strengths. TI-01 concerns restoration of an already privileged exact account, not a claim that a matching customer email becomes Internal. |
| Direct services, CLI and host boundaries | The proposal expressly inventories supported writers and requires authoritative host ownership/action scopes rather than opaque-ID visibility. These are unimplemented gates. The synthetic profile and association checks show why a route-only review would miss service-level lifecycle transitions. This lane did not fully audit every host, machine credential, SQL query, or policy mutation route. |

## Checks performed and limits

Ran the existing focused pure/mocked tests, with bytecode directed to scratch and pytest's cache provider disabled:

```text
uv run --no-sync pytest -p no:cacheprovider
  tests/unit/services/test_administrative_scope.py
  tests/unit/test_jwt_utils.py
  tests/unit/test_invitation_system.py
  tests/unit/test_phone_verify.py
  tests/unit/test_phone_validation_and_update.py
```

Result: **83 passed, 0 skipped, 7 warnings**; reported test execution 0.27 seconds. Counts: 51 administrative evaluator cases, 4 JWT cases, 20 invitation cases, 4 phone verification cases, and 4 phone validation/update cases. The warnings were test short-HMAC-key warnings; they were not treated as evidence about deployed key configuration.

Ran scratch helper `synthetic_baseline_checks.py` under the existing uv environment. It used public example addresses, synthetic signing material, mocked persistence and provider responses, and no external services. Its final run succeeded and produced these observations:

```text
association: active account, password changed after state -> link inserted and committed
association: suspended account -> link inserted and committed
association: deleted account -> link inserted and committed
profile: deleted account -> current email changed; old unique column reservation removed
restore: superuser retained -> all permissions; revoked refresh stays revoked
access: same JWT accepted before deletion, denied while deleted, accepted after restore
```

These six checks establish local source counterexamples with the stated mock boundaries. They do not establish a complete HTTP attack, OAuth provider policy, a database uniqueness/concurrency result, cache behavior, or customer deployment state. The association check assumes a legitimately issued, still-unexpired state/browser/provider flow and tests what happens after that boundary; it does not defeat its cryptographic checks.

Not run: broad/full regression suite; PostgreSQL or Redis infrastructure; retained-deletion integration tests; real OAuth, mail, SMS or browser flows; migration DDL upgrades; namespace races; cache/revocation races; A01–A15 implementation acceptance suites; staging, load, artifact, rollout or recovery checks. Existing integration tests at `tests/integration/test_user_retained_deletion.py:284`–383 show revoked memberships/direct roles/refresh tokens/API keys and a new login after restore, but do not cover a privileged target or a pre-deletion access JWT after restore. Those inspected tests were not executed.

## Required disposition

Correct the claimed restore baseline, resolve the retained privileged flag and tombstoned identifier policies, and spell out enrollment-proof cancellation. Preserve the proposed immutable namespace, exact-account resolution, explicit legacy bridge, independent same-email identities, and root-account versus practice-relationship separation. Add the concrete transition cases above to the executable requirement/use-case ledger when WP02/WP04 begins.

With those dispositions and the existing G0 choices recorded by their authorized owners, bounded implementation behind disabled capabilities is reasonable. This review provides no approval for namespace duplicate admission, persistent staff grants, legacy conversion, publication, host cutover, or production deployment. Their existing G1–G5 evidence requirements remain applicable.
