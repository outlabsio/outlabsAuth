# Independent review of tenant identities and administrative grants

Date: 2026-10-10. Status: review complete; corrections and maintainer/human dispositions pending.

## Verdict and reviewed source

Three independent reviews support the proposed separation of immutable credential namespaces, customer business hierarchy and staff administrative authority. None recommends replacing separate customer identities with a global person identity or deriving login boundaries from a mutable parent tree. The recommended first phase of independent customer roots, administrative grouping and non-delegable human grants remains a reasonable direction.

**Revise the lifecycle, conditioned-cache and recovery/replay contracts before accepting their affected implementation packages.** Five authorization/identity findings have executable baseline reproductions; four replay findings expose missing acceptance or recovery rules. The findings do not establish a deployed consumer exploit, reject the entire architecture, or qualify the unwired evaluator as a persistent authorization system.

The reviewed source is **revision 0.1**, committed as [`58230e25ceb373302dc48e167f1dbbe60197d393`](https://github.com/outlabsio/outlabsAuth/tree/58230e25ceb373302dc48e167f1dbbe60197d393), with the complete 1,937-line proposal and 606-line reviewer packet. Proposal SHA-256: `4b9a271125519008f0c8824621d792e60f232323e8ca123ee40e39f00976f6b5`. The examined identity and permission/cache baseline matches the cited a36 source `7ec9acf77f37ead0d7eb50347334224cc9d72e87`; the new administrative evaluator is explicitly unwired.

A concurrent working-tree edit started **revision 0.2** during review, with HEAD unchanged. Those edits were preserved and excluded. This report is neither a review nor an acceptance of revision 0.2. Reconcile these findings against that draft explicitly; a reordered delivery plan or another cache correction is not, by itself, closure evidence for these cases.

The reviewers received separate fresh contexts, the same frozen proposal and packet, and distinct lanes. They did not read one another's findings before completing their reports. The coordinator subsequently inspected the cited source, reconciled overlapping claims and reran the identity and administrative synthetic checks. Original reports are retained for independent inspection:

- [Tenant isolation and identity lifecycle](reviews/tenant-auth-2026-10-10/tenant-isolation.md).
- [Administrative roles and target-bound grants](reviews/tenant-auth-2026-10-10/admin-roles.md).
- [Migration and replay](reviews/tenant-auth-2026-10-10/migration-replay.md).

## Findings and affected gates

Gate names below refer to revision 0.1. They must be mapped to the new delivery order during revision 0.2 reconciliation. Severity describes the reproduced behavior or proposed-contract risk under each report's stated assumptions, rather than a claim about an installed host.

| ID | Severity | Finding and consequence | Required disposition / blocked acceptance |
| --- | --- | --- | --- |
| TI-01 | High | Ordinary retained deletion leaves `is_superuser` set; identity-only restore makes it effective again. | Define effective privilege revocation separately from historical protected-account classification. Restore must require a separate audited platform regrant or dedicated privileged recovery. Correct the baseline claim before the G0 restoration contract; qualify WP02/G1 and WP04/G2 with a privileged target. |
| TI-02 | High for protected accounts; Medium otherwise | An unexpired pre-deletion access JWT is rejected while deleted, then accepted again after restore. Refresh revocation remains intact. | Make old-session invalidation durable across restore, through an enforced security epoch or equivalent persisted-family contract in both authentication paths. WP02/G1 must prove deletion/restore cannot revive old tokens, including the legacy-token policy. |
| TI-03 | High | A pending OAuth association can commit after password security reset, suspension or deletion. | Bind method enrollment to current security authority and define cancellation/commit serialization. D08/D10 and WP02/G1 association acceptance must cover resets, incident revocation and lifecycle races; sensitive mutation acceptance in G2 also depends on this. |
| TI-04 | Medium | Ordinary profile editing can change a deleted user's email and release the supposedly retained reservation. | Make tombstoned authentication identifiers immutable until explicit reuse, or retain reservation independently from editable contact data. Clarify D04/D18; WP01/WP02/G1 must prove service and route writes cannot bypass it. |
| F-admin-01 | High, for the affected cached ABAC profile | Generated current-time attributes are absent from the cached decision key. A cached allow survives a time condition becoming false. | Resolve and bind the complete trusted condition context before caching, with proven transition deadlines, or evaluate unbindable conditioned paths freshly. Clarify WP04; block affected conditioned authorization at G2 until the negative cases pass. |
| F-MR-01 | High | Restoring the database can also rewind its migration fences, cutover state and revocations. An old plan can match the restored guards. | Define recovery authority outside the rollback boundary, or keep admission closed until accepted reconstruction of security and source/cutover state. WP08/WP09 recovery and G4/G5 acceptance need anti-rewind evidence. |
| F-MR-02 | Medium | A unique outbox row cannot distinguish an accepted external send from a crash before the local receipt. Physical delivery deduplication is not guaranteed. | Require verified provider idempotency or explicitly accept at-least-once delivery with an UNKNOWN outcome and bounded retry/operator rules. WP06/G3 automatic replay delivery must state and test its actual guarantee. |
| F-MR-03 | Medium | A consistent source cut can still contain contradictory current/removed facts for the same relationship episode. | Define host lifecycle precedence/episode evidence and quarantine unresolved contradictions. This blocks affected cohort acceptance at WP06/G3 and WP09/G5, not unrelated additive schema work. |
| F-MR-04 | Medium | A source-owned login-email change can conflict with the promise to preserve native verification and recovery state. | Prefer target-owned login identifiers after provisioning, with separate source contact fields. Any supported login change needs an explicit authorized exception, collision/epoch checks and proof at the new destination. WP06/G3 must resolve this before replay changes identifiers. |

## Why the security findings matter

TI-01 and TI-02 are separate failures. Deletion correctly revokes memberships, direct roles, keys and refresh rows in the inspected code, yet the retained privilege flag and access JWT can independently become effective after restore. Simply clearing the only superuser flag is not a complete correction: limited administrators must still recognize and protect formerly privileged accounts. Current active authority and historical protected classification need distinct rules.

The proposal's baseline table says restore is non-access-restoring. The tenant review establishes a concrete exception, confirmed by the coordinator. The administrative review's favorable assessment of the intended identity-only restoration rule does not override that reproduced exception. Amend the baseline claim and the privileged restoration contract. The ordinary account counterexample has an access-token-lifetime window; it does not establish indefinitely renewed refresh access.

TI-03 assumes legitimately issued, unexpired browser/provider state. Its synthetic check mocks successful state consumption and provider responses, then exercises the actual association callback's account mutation. It does not bypass OAuth cryptography. The defect is accepting enrollment after the initiating security authority changed. Preventing a session from being minted while the account is inactive does not undo an already committed provider link.

F-admin-01 reproduces an actual baseline ordering problem: the cache hashes absent caller `time_attrs` before the policy engine generates the time used for evaluation. With unchanged policy/user/entity epochs, a role allowing an action before noon remains cached as allowed after noon, although a fresh condition denies. Durable mutation epochs and grant-expiry deadlines alone cannot cover all condition transitions. A conservative initial correction can preserve ordinary RBAC and policy-loading caches while bypassing decision caching for conditioned paths whose complete dependencies and deadlines cannot be established.

## Replay and recovery consequences

F-MR-01 is distinct from the plan's already documented stale-runner protection. Restoring all schemas to a consistent backup is necessary but insufficient when the backup includes the very monotonic counters intended to reject an old plan. A newly started runner can also carry that saved plan; process restarts alone do not fix restored authority. The accepted recovery procedure must reconstruct current cutover/security authority or deny authentication, mutation, replay and pending delivery until it can do so. It must not silently reopen source ownership after an accepted cutover.

F-MR-02 distinguishes one logical invitation/outbox operation from one physical provider delivery. A crash after provider acceptance and before receipt persistence leaves an uncertain external outcome. A local uniqueness constraint cannot decide whether retry duplicates or withholding retry loses a delivery. Test the provider's actual idempotency window if relying on it; otherwise specify honest retry and operator semantics without rotating invitation tokens to disguise repeated sends.

F-MR-03 does not classify every removal followed by current membership as a conflict. Ordered re-addition with a new episode can be valid. The gap concerns the same episode containing incompatible observations without authoritative ordering. Preserve the observations, quarantine the relationship and avoid expanding access or inventing history while disposition is pending.

F-MR-04 concerns ownership of each field, rather than whether ordinary business/contact updates are replayable. Verification of one email destination cannot transfer to another simply because both came from the same source person. A host can avoid this initial acceptance dependency by keeping login identifiers target-owned and treating source contact corrections separately.

## Existing gates and sound boundaries

The following remain explicit open decisions or qualification work; they were not counted again as new findings:

- G0 semantic decisions D01–D26, including namespace binding, identifier lifecycle, transaction linearization, legacy bridge and recovery choices. Proposed defaults have not received human/maintainer acceptance.
- Persistent namespace/grant schema, all authentication and enrollment paths, exact action/target operation mapping, protected Internal/platform classification, and action-bound SQL/query projections.
- Actual old-installation DDL, legacy readers and writers, mixed-version fencing, full source/population classification and repeatable host migration acceptance.
- Real PostgreSQL/Redis concurrency, stored-policy HTTP behavior, performance, immutable artifact, staging, host activation and recovery evidence.

The pure evaluator's current acceptance of a second unclassified Internal root, wildcard platform action or supplied condition result is already bounded by missing validated adapter inputs described in the proposal. These are integration obligations, not additional deployed grant vulnerabilities. Do not wire the prototype directly into request admission and treat its 51 tests as system qualification.

The reviews specifically support exact/subtree/group reach without sibling borrowing, action-and-target coupling, pinned admission IDs with new identities on re-addition, immutable policy closure, protected control-domain designation, root-account credential authority, human-first non-delegable grants, and filtering before paging/counting/export. These conclusions assume the documented restrictions are actually enforced and tested.

## Local verification and limits

| Check | Result and boundary |
| --- | --- |
| Tenant review focused tests | 83 passed: 51 evaluator, 4 JWT, 20 invitation, 4 phone verification and 4 phone validation/update cases. Pure/mocked paths; no infrastructure qualification. |
| Administrative review / coordinator | Both verified the 51 evaluator cases. Coordinator also passed the existing cache/context helper case. These overlap the tenant run and are not additional unique suite counts. |
| Tenant synthetic reproducer | Six checks passed; coordinator reran them. Real service/callback/JWT code with mocked persistence and provider boundaries confirmed TI-01–TI-04. No token contents retained. |
| Administrative synthetic reproducer | Reviewer and coordinator confirmed cached allow versus fresh deny at the time transition, plus three explicitly acknowledged prototype integration boundaries. Real memory cache/policy services with deterministic authority suppliers. |
| Migration review | Two mocked CLI migration-runtime tests passed. Four standard-library countermodels passed; these demonstrate logical gaps, not database or provider qualification. |

Retained runnable evidence: [identity lifecycle checks](reviews/tenant-auth-2026-10-10/synthetic_baseline_checks.py) and [administrative cache/boundary checks](reviews/tenant-auth-2026-10-10/admin-synthetic-checks.py). From the repository root, run `uv run --no-sync python` with the respective relative script path. They use synthetic inputs and do not contact production services. See individual reports for exact source citations, assumptions and commands.

No full regression suite, PostgreSQL/Redis infrastructure, real provider/browser flow, populated migration, namespace race, host deployment or recovery rehearsal was run in this review. Prior broader test receipts are not new evidence from this pass. The report and scripts change no library runtime, migration or application configuration.

## Next disposition

1. Reconcile the nine findings with the working revision 0.2 and map each required proof to its revised work package. Record accepted corrections, exclusions or reasoned rejections; do not silently assume closure from a reordered plan.
2. Correct the baseline restore claim and settle the lifecycle, conditioned-cache and recovery guarantees before accepting the affected contracts. Preserve the bounded model and separately disposition the existing semantic decisions.
3. Turn accepted corrections into implementation work with the negative tests described in the lane reports. Qualify baseline fixes, new capabilities and individual host adoption separately.

The requested independent review is complete. Design acceptance, persistent implementation, namespace duplicate admission, package publication and consumer activation remain separate outcomes.
