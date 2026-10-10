# Tenant identities and delegated administration: independent review packet

**Status:** Review instructions for a proposed design; no design acceptance or
implementation approval is recorded by this packet.
**Revision:** 0.1, 2026-10-10.
**Proposal:** [Tenant identities, customer hierarchy and delegated administration](./TENANT_IDENTITIES_AND_ADMINISTRATIVE_GRANTS.md).
**Decision record:** Proposed DD-062. The main proposal's decision register owns
the disposition of each unresolved choice.

This packet gives independent agents and human reviewers a common method for
challenging the proposal. It does not ask reviewers to implement the design,
publish a release, change a customer topology, provision users or apply a data
migration. Repository examples and review reports must remain synthetic and
consumer agnostic. Private deployment evidence stays with its owner.

## 1. What is being reviewed

The proposal introduces stable identity namespaces, independent customer roots,
ordinary membership within a customer and explicit administrative grants across
customers. Internal operators can have different actions at different targets:
one practice, one corporate subtree or an approved group of customer roots.
Customer-wide credential administration and platform administration remain
separate from ordinary roster or practice administration.

The proposal's R01–R26 invariants and U01–U48 use cases are the shared reference
IDs for review. Cite them in findings. The proposed names, table representation,
configuration symbols, policy choices and work packages remain reviewable. Do not
infer that a named object already exists in the released library.

Use these evidence categories consistently:

| Category | Meaning | What it does not establish |
| --- | --- | --- |
| Verified baseline | Behavior of the cited released source and existing tests | The correctness of a future design or a deployed consumer |
| Prototype | Existing side-effect-free administrative evaluator and its focused tests | Persistence, route enforcement, SQL filtering, operational safety or full tenant identity support |
| Proposed contract | A recommendation in the main document | Reviewer acceptance, implementation or migration authorization |
| Accepted decision | Explicit maintainer/human disposition with date, owner and rationale | That implementation, release or consumer migration gates have passed |
| Implementation evidence | Exact source revision and meaningful executable checks of implemented behavior | Production acceptance or approval of another revision |
| Consumer acceptance | A host's own validated policy, mapping, artifact and rehearsal evidence | General proof for every other host |

The prototype's passing tests are useful narrow evidence. They must not be used
to close gaps in tables, transactions, management paths, authentication flows or
hosts that the prototype does not implement. A proposed invariant can be sound
while the current prototype is incomplete. Conversely, a passing prototype can
implement a policy that reviewers reject.

## 2. Reviewer entry instructions

Read the main proposal's outcome, terminology, baseline, invariant table and
use-case table before reviewing a specialist section. Then inspect the relevant
source and prior design decisions. Do not rely solely on summaries of another
reviewer or on variable names that sound like a tenant boundary.

For an agent review, use the following task boundary:

> Review the tenant identity and delegated administration proposal in this
> repository. Keep the work read-only. Challenge the stated contracts against the
> actual source, invariants and synthetic adversarial cases. Distinguish baseline,
> prototype and proposed behavior. Return actionable findings with evidence and
> requirements/use cases; do not implement changes, assume approval, invent
> production topology or include private consumer data.

Before beginning, record the proposal revision, Git revision, relevant working
tree changes, review lane and any unavailable evidence. A review of an earlier
draft must not be presented as review of a later completed document. If a section
is still incomplete, report it explicitly and withhold its verdict.

Prefer independent first-pass reviews. Reviewers should generate their own
threats, alternatives and acceptance cases before reading each other's findings.
Afterward, cross-review unresolved disagreements; agreement between agents is
not a substitute for evidence or a maintainer decision.

Recommended review lanes:

| Lane | Primary sections in main proposal | Required cross-lane consultation |
| --- | --- | --- |
| Identity and privacy | 2, 3, 7, 8, 13, 15, 17 | Authorization for account operations; client review for context selection |
| Authorization and delegation | 4–7, 9–13, 17 | Schema/cache/recovery and host resource mapping |
| Schema, replay and recovery | 7, 12–15, 18–20 | Identity reservation and authorization expansion |
| Client and operational behavior | 5, 8, 11, 16, 18–21 | Identity privacy and current permission/query behavior |
| Human/product owner | 1, 2, 5, 6, 16, 21 | Security consequences, unresolved policy decisions and rollout boundaries |

One reviewer may cover several lanes, but the final review must identify which
lanes were actually examined. Silence on a lane is not acceptance.

## 3. Identity, authentication and privacy prompts

### 3.1 Namespace and account ownership

- Can a namespace remain stable when display names, slugs, parentage, memberships
  or root lifecycle change? Trace the foreign keys and proposed service rules,
  including deletion and legacy first-membership adoption. R06, R18; U18–U21,
  U39–U40.
- Does the design distinguish a credential namespace from the owning customer
  root and business account owner? Can a visible member accidentally become an
  owner, or can a root assignment move credentials? R01, R02, R09; U01–U05.
- Is the legacy namespace explicit and non-null? Can nullable data, unassigned
  users or an entity `SET NULL` path become a new global bucket? R06, R23; U39.
- Are identifiers reserved through retained deletion? Explain email or phone
  reuse, restore collisions, tombstones and hard purge rather than assuming a
  partial unique index on active accounts is sufficient. R06, R15; U22–U26, U34.
- Are all declared namespace/root consistency rules enforceable under concurrent
  create, invite, update and reconciliation? Which rules require schema checks,
  composite foreign keys or a locked transaction rather than a preflight query?
- Is a full identifier ledger materially safer than the proposed smaller email
  plus phone-auth reservation model? State migration, support and consistency
  costs for both alternatives; do not accept extra machinery without purpose.

### 3.2 Resolution and discovery

- For each unauthenticated flow, show where canonical namespace is resolved
  before email or phone. Missing context must not become a global scan or
  password trial against multiple accounts. R07, R26; U03, U23–U25, U33.
- Which request fields are hints, and which server configuration or credential
  record supplies authority? Test conflicting body/path/header/hostname context
  and untrusted forwarded headers. R14, R26.
- Does a fixed legacy adapter always select the same default namespace even
  after a duplicate account appears elsewhere? R07, R23.
- What account/customer information can a stranger learn through login, recovery,
  invitation, OTP, registration errors, timing, rate-limit responses and tenant
  discovery? Do responses reveal another customer's matching email or status?
- Are private customer keys or labels required to be public? Is a deployment
  trying to provide account discovery accidentally exposing customer membership?
- Can the same email cause coupled lockout or notification flooding across
  namespaces? Can an attacker rotate invented tenant keys to evade aggregate
  limits? Identify the per-identity and deployment-wide controls.

### 3.3 Lifecycle and credentials

- Enumerate password login, register, forgot/reset password, magic-link request
  and verify, email/phone OTP, phone verification, invite/resend/accept, OAuth
  login/register/associate/unlink, token refresh and service-supported auto-login.
  What exact user, namespace, purpose and destination state does each path bind?
  R08, R15; U22–U33.
- Can an old-email magic link mark a new email verified? Can an old phone code
  verify a replacement phone? Can a prior invitation reset an established user's
  password when only a new membership was intended? R15; U26, U32.
- Which events invalidate which challenge types and credential epochs? Include
  password changes, account deletion, namespace suspension, identifier changes,
  user relocation, recovery and operator compromise response. Avoid a vague
  statement that all tokens are invalidated without an enforceable mechanism.
- Are identity status and membership status separate? An account may be active
  while one membership is suspended or removed. A practice operation must not
  suspend the corporate identity merely because it can manage that membership.
  R09; U12, U36, U45–U46.
- Does restore intentionally leave prior memberships, roles, administrative
  grants, sessions and keys revoked? What additional verification is required
  before restored credentials are usable? R06, R13; U34.
- What happens to OAuth-only identities during password recovery or when their
  last provider is unlinked? Is adding a password explicit policy or an accidental
  recovery side effect? Do not promise a recoverable account without a method.

### 3.4 OAuth, token and session boundaries

- Is provider identity keyed by namespace, stable provider registration/security
  context, verified issuer where applicable and stable subject? Can two providers
  with the same display name collide? R01, R08; U27–U29.
- Does signed OAuth state agree with persisted namespace, provider, flow, app,
  initiating user, PKCE/nonce and browser binding? Which values may change at
  callback, and which mismatches must be rejected before account lookup?
- Can the same upstream provider account safely link to A and C while remaining
  exclusive to one local identity within A? What are the consequences of upstream
  SSO, upstream token revocation and stored provider tokens shared by a grant?
- Is provider email association explicitly approved within a namespace? Does
  provider-email change cause relinking, account substitution or verification
  inheritance? R07–R08; U28–U29.
- Do both access and refresh encoders carry required namespace provenance? Trace
  actual helpers rather than assuming generic `additional_claims` reaches both.
  Do stored token owner, family, namespace and signed claims agree?
- Can refresh switch tenant or frontend? What happens to legacy tokens without
  new claims? Is their default-namespace compatibility bounded and predictable?
- Does stateless operation satisfy lifecycle/revocation guarantees? If not, is it
  rejected for the new mode or subject to an explicit reviewed security window?
- Does switching practices preserve identity while switching unrelated customers
  requires independently authenticated local sessions? R01–R02, R08; U04, U30–U31.

## 4. Authorization, delegated administration and host prompts

### 4.1 Action and target remain joined

- Evaluate a staff user who can read B and update A. Can any flat permission union
  plus broad visibility grant update at B? Each allow must join action and target
  within a qualifying live authority source. R10; U09–U10.
- Does every target selector mean something exact: one entity, a bounded subtree,
  or an approved customer-root group? Test ancestors, siblings, customer root
  operations, archived nodes, missing closure rows and unrelated roots. R04, R14.
- Do account-wide changes use the account's owning customer root, while local
  membership changes use the relationship entity? Can a West-only manager reset
  a user who also belongs to East or revoke all of that user's sessions? R09;
  U08, U11–U12, U46.
- Does roster visibility expose all host profiles or other memberships linked to
  a visible user? List/export APIs must constrain each resource to its own
  authoritative entity, not to the global set of profiles belonging to the user.
  R17, R26; U41, U48.
- Is platform authority separate from all-customer reach even with wildcards?
  Which permission catalog entries are inherently protected? R12, R25; U06, U44.

### 4.2 Principal admission and role representation

- What proves an actor belongs to a trusted Internal namespace? Email domain,
  entity type/name, a client flag and matching person data must be insufficient.
  Can an external same-email account become an operator? R05; U05.
- Does a role/template require live permissions and applicable conditions before
  widening query scope? Can an empty, deleted or inactive template reveal data?
  R13–R14.
- If existing `Role` storage is reused, inspect every direct assignment,
  membership, auto-assignment, integration, seed, CLI, HTTP and restore path.
  Could an administrative template become a direct system-global role? R25.
- Are ordinary memberships restricted to the owning customer even for staff?
  Administrative reach must not bypass that invariant. R11.
- Are dormant, invited, scheduled, suspended and retained privileged identities
  protected from a customer grant that could later reactivate them?
- Does a personal API key remain the intersection of credential restrictions,
  owner's current authority and concrete target? Does an unanchored key have
  explicitly documented semantics rather than accidental global reach? R16; U37.
- If machine administration is deferred, can current integration principals or
  service tokens bypass the new guards? Inventory this boundary rather than
  claiming that a human-only first phase covers every principal. U38.

### 4.3 Delegation and indirect privilege expansion

- Can an operator grant an action or target it does not itself control? Does
  granting require explicit delegation authority in addition to use authority?
- Are role/template edit, permission edit, group membership edit, ancestor move,
  condition edit, trusted-root designation and grant validity extension treated
  as authority expansion? A grant row need not change for its power to grow.
  R19; U15, U18.
- If groups can be dynamic, who approves new customers joining every holder's
  reach? If grants are pinned, how do retirement/removal still immediately reduce
  eligibility without reactivating an old snapshot? U15–U17.
- Are nested groups, transitive delegation and condition containment intentionally
  deferred or given a decidable policy? Do not assume arbitrary ABAC predicates
  can be proven to be subsets of another operator's authority.
- What happens to a delegated child grant when the parent expires, is revoked,
  changes template or loses a target? Is the result race-safe and auditable?
- Can a staff operator authorize its own expansion or alter the trusted-root
  policy indirectly through entity/config/CLI operations? R05, R12, R19, R25.

### 4.4 Route and query enforcement

- Produce a route-family coverage map: list/detail, create/update/delete,
  memberships, roles/permissions, account status, credential reset, sessions,
  personal keys, invitations, audit, orphan search, entity movement and exports.
  Where is the invariant enforced for both HTTP and direct service consumers?
- Does the host's supported API return action-specific scope/predicate information
  rather than an unrestricted flag or flat union? Is resource ownership mapping
  verified server-side on detail reads and writes as well as lists? R17, R26.
- Are SQL authorization filters applied before limit, pagination, total counts,
  distinct, aggregation and export? Can post-filtering produce missing authorized
  results or leak unauthorized totals? R17; U48.
- Can a missing or failed scope resolver produce `None` meaning unrestricted?
  Is an empty authorized set distinguished from global authority? R14.
- For a batch containing unauthorized items, does atomic refusal remain the
  default? If partial mode exists, are per-item authorization and failures
  explicit without leaking additional records? U47.

## 5. Schema, replay, concurrency and recovery prompts

### 5.1 Schema and compatibility

- Can additive migration preserve existing user UUIDs, credentials, verification,
  lifecycle, roots and memberships? What evidence proves the default namespace
  does not accidentally classify a legacy account as Internal? R05, R23; U39.
- How are duplicate/case/normalization anomalies and verified-phone collisions
  discovered before enforcing new constraints? Do reports expose conflicts
  instead of inventing owners, aliases or silently merging records? R03.
- Who owns Auth migrations when embedded in a host? Host migrations must not
  compete with Auth's Alembic ownership or partially create its new tables.
- Is new schema safe for an old binary before duplicate identities are enabled?
  Exactly which data/policy transition prevents binary or database downgrade?
  A runtime feature toggle is not evidence of reversibility after duplicates.
- Can mixed workers, CLI versions, caches or background jobs use incompatible
  identifier semantics in one schema? How is incompatible startup fenced?
- Is SimpleRBAC explicitly supported or clearly rejected for scoped mode without
  silently activating hierarchy? R23; decision D05.
- Are indexes and constraints designed for actual queries and concurrency, not
  merely added by convention? Require query-plan evidence with realistic volume
  before implementation acceptance; do not invent performance proof in review.

### 5.2 Repeatable external-source reconciliation

- Does a complete immutable source snapshot define its cohort, watermarks,
  identifiers, counts and hash? Can partial, limited, errored or stale scans ever
  infer absence? R20–R21; U42.
- Are customer, practice, source-person, relationship and source-event crosswalks
  stable and qualified by their real ownership? Does email remain a candidate
  for review rather than the sole reconciliation key? R01–R03; U03–U04.
- Are source-owned contributions separate from target-native credentials,
  verification, grants and preferences? How do changed last-applied fingerprints
  become conflicts rather than unconditional overwrite? R20; U43.
- Can removing one source contribution revoke a role/member that another source
  or a local operator still owns? Can practice absence suspend the corporate
  identity or unrelated practice memberships? R09, R20–R21; U12, U42–U43.
- Are reviewed plan hash, source snapshot, policy/topology version, schema heads,
  code revision and target fingerprints checked again at apply? Is a new plan
  required when those inputs change?
- Is the transaction unit defined and resumable? Inject failure after identity
  creation, member creation, grant removal, history capture and checkpoint. What
  rolls back, and which unit is safe to retry? R22.
- Do replays avoid mail, invitations, password overwrite, OAuth-token copying,
  verification changes and session churn unless explicitly authorized as a
  separate operation? U32–U36, U43.
- Do source events have deterministic keys and payload hashes? Does duplicate
  key/same payload mean no-op while changed payload becomes a conflict? Is an
  observed disappearance distinct from a known historical deletion event? R21.
- Can final ownership/watermark switch reject later stale source writes? Is a
  rollback after partial cutover operationally possible without losing target
  changes? R20–R24.

### 5.3 Atomicity, revocation and caches

- What is the linearization point for an authorized mutation racing grant
  revocation, role edit, namespace suspension or subtree move? A read already
  completed cannot be retroactively revoked; describe guarantees precisely.
- Are applicable policy and target versions locked or rechecked through commit?
  Is authorization checked inside the same transaction as the protected change?
- Can cache keys confuse namespace, actor, permission, selector, API-key anchor,
  condition context or policy/topology epoch? What invalidates each dependency?
- What happens when Redis or invalidation delivery fails? Does a stale positive
  cache keep authorizing a revoked grant? R13–R14; U13–U14.
- Are required audit/history/provenance writes transactional? If an audit
  constraint or callback fails, can a destructive action commit anyway? R22.
- Is external notification delivery separated by an outbox or equivalent retry
  contract? An email provider outage must not undo committed policy or produce
  repeated invitations on replay.

### 5.4 Delete, restore and exceptional recovery

- Does immutable historical evidence survive user, membership, entity and grant
  lifecycle changes? What is intentionally retained versus purged? Can nullable
  live references coexist with immutable identity/target snapshots?
- Does restore preserve namespace, check reservations and restore identity only?
  Is a source reappearance ever mistaken for authorization to reactivate access?
  R06, R13, R20; U34.
- Does emergency repair require separate platform authority, reason and audit?
  Does ordinary customer support avoid credential takeover or staff promotion?
  R12, R25; U44.
- Is bootstrap idempotent by exact designated namespace/operator identity rather
  than matching email or whichever user is first? Can it recover safely if the
  matching email belongs to a customer?
- Are rollback recipes honest about duplicate identities, transferred ownership,
  mail already delivered and external provider effects? R18, R24.

## 6. Client, product and operational prompts

- Can users understand whether they are switching practice, customer account or
  frontend? Do labels and account menus show enough context to avoid changing
  the wrong customer without revealing unrelated memberships? U03–U04, U30–U31.
- What do two tabs signed into different customers do? Trace token storage,
  refresh coordination, API requests, background queries and logout. A shared
  local-storage token slot is not sufficient isolation. R08; U30.
- Does client-selected entity context receive server validation on every action?
  Is stale context cleared on revocation or account change rather than merely
  hiding a menu? R26; U13–U14.
- Do account rosters distinguish local membership suspension from customer-wide
  account suspension? Can an operator see why an action is unavailable without
  being shown protected global policy or unrelated memberships? R09; U11–U12,
  U46.
- Do login, invite and recovery messages identify the intended customer and app?
  Can several accounts sharing an inbox choose the correct independent flow?
- Are API capability/version discovery and actionable incompatibility errors
  available to old clients? Will optional fields be discarded by existing client
  normalizers before server behavior is paired?
- Does CLI context separate deployment, namespace and frontend? Do stored sessions
  validate that context before reuse? Administrative email resolution must use an
  exact namespace-qualified endpoint or UUID, not the first search page.
- Does declarative plan/apply include namespace-qualified references, immutable
  IDs, protected object rules and stale-plan rejection? Which HTTP operations are
  atomic, and which explicitly report partial outcomes?
- Do monitoring and audit permit investigation by exact identity, namespace,
  grant, target and policy version without logging passwords, token values,
  secrets or unnecessary email/phone data? Which retention/redaction rules apply?
- Is rollout staged by additive schema, server support, client context, protected
  topology/policy configuration, rehearsed host migration and activation? Which
  step first permits duplicate credentials, and what is its recovery gate?
- Are release checks local and reproducible, with real PostgreSQL and Redis where
  required? A prototype's unit tests or an unrelated hosted check cannot prove
  schema, route, replay or consumer acceptance. R24.
- Is the support burden of separate logins, same-inbox messages, customer merger,
  provider SSO and account recovery understood by humans? A technically coherent
  boundary still needs a workable operator/customer experience.

## 7. Cross-review adversarial scenarios

Use synthetic Customer A, Customer B with West/East practices, Customer C and a
trusted Internal organization. These are review constructions, not production
facts. Specify principal, credential, action, target, policy/version and expected
outcome before examining a proposed code path.

| Case | Construction and expected boundary | Reference IDs | Required joint review |
| --- | --- | --- | --- |
| X01 | Same email/password in A and C; A is suspended. Login/recovery in A cannot use C even if C is the only active match. | R01, R07–R08; U03, U25 | Identity + privacy |
| X02 | External account has the same email as an Internal operator and a customer-supplied Internal-looking type/name. It gains no staff authority. | R05, R12; U05 | Identity + authorization |
| X03 | Actor can read B and update A. Request updates B-West. Deny; no permission/scope stitching. | R10; U09 | Authorization + host |
| X04 | West-only manager sees a user also in East. It may perform an allowed West membership action, but cannot reset customer-wide password, revoke all sessions or expose East resources. | R09, R17, R26; U08, U11–U12, U41, U46 | Authorization + identity + client |
| X05 | All-customers grant receives a group containing Internal. Reject configuration and runtime access; wildcard actions do not make platform authority. | R12, R19, R25; U15–U16 | Authorization + schema |
| X06 | Harmless template is edited to add a powerful permission while a dynamic group adds C. Both are authority expansions even though no grant row changes. | R13, R19; U15 | Authorization + operations |
| X07 | Grant revocation commits between an authorization read and target update. Describe the admitted-operation boundary and enforce it transactionally. | R13–R14, R22; U13–U14 | Authorization + concurrency |
| X08 | Permission cache is warm; Redis fails during revocation. No stale cached allow can grant an operation beyond the approved failure policy. | R13–R14; U14 | Authorization + operations |
| X09 | An old-email magic link/reset arrives after email change. It cannot verify the new email or recover another same-email identity. | R07–R08, R15; U22, U26 | Identity + schema |
| X10 | A phone is contact metadata for several people in B and a login identifier in A/C. Ambiguous B phone login is unavailable; A code cannot log into C. | R07–R08; U23–U24 | Identity + migration |
| X11 | OAuth starts for A, callback adds C context and provider returns an email already registered in C. Reject changed context and never globally associate. | R07–R08; U27–U29 | Identity + client |
| X12 | Two same-provider/app OAuth flows start in separate customer tabs. Neither tab overwrites the other's browser binding or stores the wrong account token. | R08; U30–U31 | Identity + client |
| X13 | SQL query has authorized rows after the first page of unauthorized rows. Filter before pagination/counts; return complete permitted page without unauthorized totals. | R17; U48 | Authorization + performance |
| X14 | Staff owner has broad grants but a key is anchored at B-West. Key cannot access East, A or B-wide credentials. | R16; U37 | Authorization + identity |
| X15 | Administrative template is accidentally assigned through a legacy direct-role or auto-role path. It cannot activate system-global scope. | R25 | Authorization + schema + CLI |
| X16 | Source replay is limited and omits C; another source/local operator also grants one B role. No absence-based C removal or B grant loss. | R20–R21; U42–U43 | Replay + authorization |
| X17 | Source event key repeats with a changed payload. Surface a conflict; do not overwrite frozen history or create a new event to hide the collision. | R20–R22; U34 | Replay + audit |
| X18 | Crash occurs after user creation and before membership/history/checkpoint. Roll back the declared unit or resume through a documented idempotent checkpoint. | R22 | Replay + transactions |
| X19 | Account is retained-deleted, source reappears and a later invite uses the same email. Reservation/restore policy prevents silent reactivation and duplicate ownership. | R06, R13, R20; U34 | Identity + replay |
| X20 | B-West subtree moves under B-East; both sides have different grants. Review authority expansion, destination/source authorization and cache/topology epoch. | R18–R19; U18 | Authorization + topology |
| X21 | A practice moves from B to C. Parent edit must not transfer credentials, namespace or local/global policy; use dedicated migration. | R06, R18; U19–U21 | Identity + migration |
| X22 | Old binary starts after scoped duplicate emails are enabled. It must be fenced before ambiguous/global lookups or incompatible writes. | R07, R23–R24 | Schema + recovery |
| X23 | CLI email search yields one matching user on its first page and another later. Sensitive command must demand exact UUID/namespace resolution. | R07, R17, R26; U48 | CLI + authorization |
| X24 | Required audit/history write fails while membership/account deletion proceeds. No successful security mutation may lose its mandatory evidence. | R22 | Audit + transactions |
| X25 | Bulk payload includes one authorized practice and one foreign practice. Atomic refusal is default; partial mode must be explicit and report per-item decisions. | R10, R14, R26; U47 | Authorization + client |

For each case, try the happy path, missing data, invalid input, stale versions,
concurrent operations and retry after a partial failure. Reviewers should also
add cases the table misses. A list of test names is not execution evidence; record
when a case is still a proposed acceptance requirement.

## 8. Finding severity and response format

Severity identifies the consequence if the gap is implemented or shipped. It
does not automatically assign a runtime exploit to a documentation-only proposal.
State whether the finding concerns released baseline, prototype, proposed design
or a missing acceptance requirement.

| Severity | Definition | Typical disposition |
| --- | --- | --- |
| Critical | Credible cross-customer credential substitution, platform takeover, systematic unauthorized access or irreversible destructive transfer | Blocks affected design acceptance and implementation gate until resolved |
| High | Privilege escalation, meaningful isolation failure, unrecoverable migration/lifecycle ambiguity or required evidence loss | Blocks the affected work package/release unless replaced by a safe explicit scope boundary |
| Medium | Incomplete contract, important compatibility/operational gap, or behavior whose risk is bounded but material | Resolve before the dependent implementation/acceptance gate or explicitly defer the capability |
| Low | Clarity, maintainability or usability issue without an immediate invariant violation | Track with exact improvement and owner |
| Question | A product/policy choice without enough evidence to select an alternative | Add to decision register; identify which work cannot proceed before the answer |

Do not reduce severity merely because the code is currently unwired. Identify the
stage at which the gap becomes dangerous. Do not inflate an incomplete proposed
path into a claim of a deployed exploit. Separate likelihood, impact, affected
capability and evidence confidence.

Use this template for each finding:

```markdown
### F-<reviewer>-<number>: <concrete issue>

- Severity: Critical | High | Medium | Low | Question
- Evidence category: baseline | prototype | proposal | acceptance gap
- Proposal revision / source revision:
- Review lane:
- Requirement / use case: Rxx; Uxx; optional Xxx
- Decision dependency: Dxx, if already registered; otherwise proposed new decision
- Claim:
- Evidence: exact document section, source symbol/path, test or reproducible case
- Counterexample: actor/namespace/credential/action/target/state and expected result
- Consequence: what a user/operator/attacker can do or lose
- Confidence and assumptions:
- Recommendation: smallest complete correction, plus viable alternatives
- Required proof: meaningful positive/negative/concurrency/migration checks
- Gate affected: design | implementation | migration | release | host activation
- Suggested disposition: accept fix | revise | defer capability | reject alternative
```

Evidence can be a reasoned counterexample when code is not implemented. Mark it
as design reasoning. Never describe a fabricated test execution as evidence.
Include enough detail that another reviewer can independently reproduce the
logical failure or inspect the exact contract.

Maintainer response template:

```markdown
### Response to F-<reviewer>-<number>

- Disposition: accepted | partly accepted | rejected | needs evidence | deferred
- Rationale:
- Decision owner and date:
- Changed contract or intentionally excluded capability:
- Main proposal / decision-register references:
- Implementation task or later gate, if applicable:
- Proof required to close the finding:
- Residual risk and operational consequence:
- Independent recheck: reviewer, revision and result; pending if not yet performed
```

Rejecting a finding requires a concrete explanation and supporting contract or
evidence. Deferring it requires disabling/excluding the dependent capability,
identifying an owner and naming the gate that prevents accidental shipment. A
backlog entry alone does not make an enabled security gap acceptable.

## 9. Decisions, disagreement and acceptance process

1. Freeze the reviewable revision and enumerate missing sections. Distribute the
   proposal and this packet, with the same source revision, to independent
   reviewers. No implementation edits are part of this first design review.
2. Collect lane coverage, assumptions, finding IDs and proposed alternatives.
   Do not collapse distinct requirements into one generic approval statement.
3. Deduplicate findings by their counterexample/outcome, preserving independent
   reasoning and dissent. A shared title does not prove they are the same issue.
4. Resolve the main proposal's decision register explicitly. D01–D06 already
   appear in model/configuration/group discussions; use their canonical meanings
   and map new questions into the completed register rather than inventing
   conflicting IDs in review reports.
5. Require a named human/maintainer owner for product policy and architectural
   choices. Agent consensus provides review evidence, not authority to accept
   independent-customer lifecycle or operational risk on the owner's behalf.
6. Rewrite the proposal around accepted decisions while retaining rationale,
   superseded alternatives and open matters. Increment the revision and record
   which findings the revision addresses.
7. Re-review changed and dependent sections. A change to namespace/root binding,
   role storage or dynamic-group semantics may invalidate several earlier lane
   verdicts; do not claim review of untouched wording as review of new behavior.
8. Only after design acceptance, create implementation-sized work with proof
   obligations. Schema, service, route, host, client and migration gates remain
   separate. Existing prototype code may be replaced rather than grandfathered.
9. Review implementation and consumer rehearsal evidence independently against
   the accepted version. Publication and operational activation require their
   own explicit release/owner gates. R24 remains applicable throughout.

Useful final review verdicts are:

- **Revise before implementation:** unresolved blockers or architectural/policy
  decisions prevent a complete enforceable contract.
- **Design accepted for bounded implementation:** the identified contract/version
  is accepted, with explicit excluded capabilities and outstanding later gates.
- **Additional evidence required:** a decision cannot be made from the current
  source, threat analysis or operational constraints.

These are review recommendations until the authorized maintainer/human records a
decision. Do not use “approved,” “secure,” “production ready” or “migration ready”
without specifying who accepted what revision, for which scope, on what evidence.

## 10. Blocker checklist and closure evidence

The following are not claims that every item is a current defect. They are the
minimum questions whose unresolved answers block the corresponding capability.

| Gate | Blocking uncertainty | Evidence needed for closure |
| --- | --- | --- |
| Namespace/schema design | Mutable/null credential boundary, unchosen identifier model or undefined reservation/normalization | Accepted model, schema invariants and upgrade/collision plan |
| Authentication design | Missing namespace path, cross-account fallback or stale-destination challenge acceptance | Flow coverage map and binding/invalidation contract |
| Administrative model | Undefined role storage, Internal trust, action/target evaluation or account-root operation boundary | Accepted representation, protected permission classification and operation matrix |
| Delegation/group expansion | Undefined dynamic/pinned reach, indirect expansion or unverifiable condition containment | Explicit grant/management semantics or capability deferred and disabled |
| Routes/host integration | No action-specific SQL scope or detail/resource mapping enforcement | Route/query/host contract and positive/negative acceptance map |
| Concurrency/cache contract | Undefined revocation linearization, stale positive cache or partial audit commit | Transaction/version/failure policy with concurrent proof obligations |
| Replay acceptance | Missing complete cohort, stable crosswalks, contribution ownership or stale-plan checks | Versioned snapshot/plan/apply/retry/conflict contract |
| Client acceptance | Ambiguous account switching, token storage or CLI references | Client/CLI compatibility, interaction and storage contract |
| Rollout/recovery | Unsafe mixed versions or undefined downgrade after duplicate identities | Version fencing, staged activation and honest recovery runbook |
| Product acceptance | Unchosen lifecycle/privacy/support consequences | Recorded human decisions and intentionally excluded capabilities |

A design finding is closed when the reviewed contract resolves the counterexample
and the owning reviewer or independent rechecker verifies the cited revision.
That closure creates implementation requirements; it does not prove their tests
have run. An implementation finding requires exact executable evidence. A host
migration finding additionally requires the host owner's accepted source and
rehearsal evidence. Keep these finish lines distinct.

## 11. Reviewer handoff summary

Return a self-contained review with:

- The proposal/source revision reviewed, lanes covered and unavailable evidence.
- Overall recommendation and any capability-specific blockers.
- Findings using the required template, ordered by impact.
- Decisions the human/maintainer must make, with alternatives and consequences.
- New or changed adversarial acceptance cases.
- What the baseline/prototype already establishes, without extrapolating it.
- What remains proposed, unimplemented, untested or awaiting owner acceptance.

If a lane finds no actionable issue, name the concrete boundaries examined and
the limits of that conclusion. “No issues found” cannot imply coverage of omitted
sections or production behavior. Keep reviewer artifacts synthetic and free of
credentials, tokens, private account data, host paths and consumer-specific names.

## 12. Additional revision-consistency challenges

These questions capture preparatory source-review corrections incorporated in the
proposal. They do not mark the design accepted.

- Prove a removed/re-added customer uses a new group admission ID. An old pinned
  grant must remain denied; an approved dynamic grant follows its explicit admission
  contract. Distinguish this from namespace suspension/restoration. D06, A07.
- Trace the full immutable policy closure: permission matching, condition content
  and entity-type restrictions must not change an old template revision through a
  live dependency. Denial-only suspension and reviewed semantic promotion differ.
  D03, A07.
- Check administrative-domain consistency for actor trust, templates, groups,
  grants and customer admission, including a foreign-domain reference. D23.
- Attempt concurrent creation of two scoped namespaces for one customer root.
  Verify a unique canonical mapping and unambiguous legacy conversion overlap. D01.
- Walk archived practice/history/restore operations without live closure rows;
  verify retained ancestry/customer evidence and current authority. Retired roots
  and removed group admissions must not regain history through stale selectors. D26.
- Remove every membership with and without a remaining valid direct business role.
  The outcome must reflect independent surviving authority, not a blanket rule.
- Exercise actual old-release user creation and OAuth linking against additive
  schema. Identify defaults/bridges for every required field and fence incompatible
  authentication/read handlers as well as writers before duplicate admission. D17.
- Prove the source cut is logically consistent across collections, and an expired
  migration runner cannot commit after a newer fencing epoch takes ownership.
- Review one-time legacy conversion: preserved UUID versus split/new identity,
  native password/OAuth changes, host owner references, retained history, session/
  challenge invalidation and exact Internal operator mapping. No ambiguous identity
  may be automatically assigned to a customer by email. D25, A13.
- Decide OAuth-only recovery: does resetting implicitly add a password, or is a
  separately authorized enrollment/recovery workflow required? D24.
