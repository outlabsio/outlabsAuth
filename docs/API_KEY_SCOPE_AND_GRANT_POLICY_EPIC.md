# API Key Scope and Grant Policy Epic

**Status**: In Progress
**Updated**: 2026-03-26
**Audience**: OutlabsAuth maintainers and host-application integrators

## Purpose

Define the next major enhancement for API key management in EnterpriseRBAC:

- entity-anchored API keys for human users
- root-entity integration keys for admin-managed org-wide automation
- grant-time policy so users cannot mint keys beyond what they are allowed to grant
- runtime policy so keys immediately lose access when the owner's effective access changes
- proactive revocation on lifecycle changes that should invalidate keys entirely

This started as a design and planning document. It now also records the
implemented backend surface, the remaining pre-UI gaps, and the future work
that still sits beyond the current `personal`-key rollout.

## Why This Epic Exists

OutlabsAuth already has a strong API key primitive layer, but it does not yet provide the full policy model needed by admin products such as Diverse internal admin.

The missing piece is not "how to store or verify an API key." The missing piece is "what is this key allowed to represent, who is allowed to create it, and how does it stay safe when user, role, membership, or entity state changes over time?"

## What Already Exists

The library is closer to the desired model than it may first appear.

### Existing API Key Primitive Support

OutlabsAuth already supports:

- user-owned API keys
- one-time secret reveal on creation
- SHA-256 hashed secret storage
- per-key scopes
- per-key IP allowlists
- rate limits
- revocation
- rotation
- entity anchoring via `entity_id`
- descendant expansion via `inherit_from_tree`

Relevant code:

- `outlabs_auth/models/sql/api_key.py`
- `outlabs_auth/services/api_key.py`
- `outlabs_auth/schemas/api_key.py`

### Existing Runtime Scope Enforcement

For mounted OutlabsAuth routes, API key requests already use a dynamic permission intersection model:

- check the owner's current permission in the requested entity context
- check the API key's stored scopes
- check the API key's entity or descendant access

This logic already exists in:

- `outlabs_auth/dependencies/__init__.py`
- `outlabs_auth/services/permission.py`
- `outlabs_auth/services/access_scope.py`

This means the library already has the core ingredients for live permission reduction when a user's effective permissions shrink.

### Existing Cache Invalidation Hooks

OutlabsAuth already invalidates cached user permissions when role and membership state changes.

Relevant code:

- `outlabs_auth/services/role.py`
- `outlabs_auth/services/membership.py`

This makes a dynamic permission model much more realistic than if every request had to recompute everything from cold state with no invalidation strategy.

### Existing User Lifecycle Revocation

OutlabsAuth already revokes user-owned API keys when a user is deleted.

Relevant code:

- `outlabs_auth/services/user.py`

## Original Gaps This Epic Was Addressing

The sections below describe the original gaps that motivated this epic. Some of
them are now partially or largely addressed in the backend implementation. See
the implementation reality check for current state.

### Gap 1: The Stock Router Is Owner-Centric

The packaged API key router is self-service oriented:

- list my keys
- create my key
- update my key
- revoke my key

It does not provide an admin-facing entity-scoped grant model.

Relevant code:

- `outlabs_auth/routers/api_keys.py`

### Gap 2: There Is No Grant Policy Layer

Today the service layer can create a key with arbitrary scopes as long as the owner exists.

What is missing is a policy layer that answers:

- can this actor grant these scopes?
- can this owner hold these scopes in this entity?
- is this key kind allowed to request these scopes at all?

### Gap 3: Human-Owned Keys Need Better Lifecycle Rules

For human-owned keys, the intended product rule is:

- if the user is deleted, suspended, banned, or removed from the anchor entity, the key must stop working
- if the user's entity-scoped permissions are reduced, the key must immediately lose those capabilities even before any background reconciliation runs

Deletion is already handled well. Suspension, membership loss, and role-change handling need to be enhanced.

### Gap 4: Host Routes Need Consistent Policy

Mounted OutlabsAuth routes already use a strong dynamic intersection model.

Host applications may still have custom authorization code paths. Those paths must either:

- reuse the same API key policy checks
- or accept that mounted and host-authored routes can diverge

This epic assumes the library should become the canonical source of API key policy rather than leaving host apps to reinvent it.

## Implementation Reality Check (2026-03-26)

This section records what the current code actually does today so the document
describes the shipped backend surface rather than only the target design.

### Implemented Backend Surface

- `APIKey` now carries `key_kind`, and the current implemented v1 kind is
  `personal`
- EnterpriseRBAC `personal` keys now use grant-time policy:
  - explicit scopes required
  - entity anchor required on the admin-managed path
  - requested scopes must fit the current `personal` rules
- the packaged self-service router still exists, and EnterpriseRBAC now also
  has a separate entity-first admin router
- the admin API now exposes:
  - `grantable-scopes`
  - paginated and filterable entity key listing
  - create, read, update, revoke, and rotate flows
- API key responses now expose derived runtime state:
  - `is_currently_effective`
  - `ineffective_reasons`
- runtime API key authorization is now available through an auth-owned host
  helper:
  - `auth.authorize_api_key(...)`
- runtime API key checks now deny inactive owners and inactive or missing anchor
  entities
- archived anchor entities now revoke anchored API keys
- auth-owned observability now emits bounded metrics/logging for validation,
  policy denials, lifecycle operations, and rate-limit hits

### Remaining Gaps Against The Full Epic

- only `personal` keys are implemented today; `system_integration` remains
  future work
- service-account ownership is still future work
- stored-but-ineffective keys are exposed through derived runtime state rather
  than a dedicated persisted status
- there is still no full reconciliation worker for role, membership, or
  permission-definition churn
- the backend host/admin surface is implemented, but UI adoption in
  `../OutlabsAuthUI` has not started yet
- migration remains intentionally out of scope for the current rollout because
  the system is still pre-production and there are no existing API keys

### Current Backend Test Position

The backend implementation now has direct Python coverage across:

- `tests/integration/test_api_key_admin_endpoints.py`
- `tests/integration/test_api_key_lifecycle.py`
- `tests/integration/test_api_keys_router_callback_paths.py`
- `tests/integration/test_enterprise_api_key_policy_matrix.py`
- `tests/unit/services/test_api_key_service.py`
- `tests/unit/test_auth_core_lifecycle.py`
- `tests/unit/observability/test_observability_integration.py`

This is enough backend confidence to proceed to host/UI adoption, but the
remaining backend test work is still worth tracking:

- exhaustive denial-branch coverage through the actual admin HTTP surface
- route-flow observability assertions on the new admin/runtime API key paths
- more edge-case coverage for pagination, search, and filter combinations
- more edge-case coverage for admin-created key IP-whitelist and rate-limit
  behavior

## Audit and Observability Planning

Audit trail design should be part of this planning work, even if the full
implementation lands in a follow-up phase.

This should not be treated as a bolt-on after the policy model is already
shipping, because the grant/update/reconcile flows define the event vocabulary.

### Planning Direction

- reuse the library's existing audit and observability primitives rather than inventing a parallel subsystem
- specify the event shapes during design so router, service, and UI work can target stable contracts
- keep durable audit history focused on high-signal state changes
- keep high-volume runtime policy denials primarily in structured logs and metrics unless a stricter compliance need emerges

### Recommended Durable Audit Coverage

The planned audit trail should capture at least:

- key created
- key updated
- key rotated
- key revoked
- key automatically disabled or reconciled due to policy/lifecycle change

Each durable event should aim to capture:

- actor user ID
- owner user ID
- key ID
- key kind
- anchor entity ID
- inherit-from-tree setting
- requested scopes
- resulting stored scopes
- reason or policy basis for the change

### Recommended Observability Coverage

The follow-up observability slice should add visibility for:

- grant-policy denials
- runtime policy denials
- reconciliation runs and outcomes
- API key counts by kind and status

The intent is:

- audit history for durable, queryable change tracking
- logs and metrics for operational monitoring and debugging

## Product Model

### Key Principle

Every admin-created API key should be anchored to an entity.

There should be no normal admin flow for creating a platform-global user-owned API key.

If truly platform-global automation is needed, that should be handled by a separate system-level mechanism such as service tokens or a future system-integrations layer, not by reusing normal admin-created user-owned keys.

### Key Kinds

### 1. `personal`

Characteristics:

- user-owned
- entity-anchored
- intended for human-operated integrations, personal automation, and assistant/CRM use cases
- may optionally inherit to descendants if policy allows

Safety model:

- requested scopes must be a subset of the owner's current effective permissions in the anchor entity
- requested scopes must also be a subset of what the creator is allowed to grant in that entity
- requested scopes must also be a subset of the product allowlist for `personal` keys

### 2. `system_integration`

Characteristics:

- still entity-anchored
- intended for durable org-scoped automation
- most likely anchored at a root entity
- broader allowed scope set than `personal`

Current direction:

- authorized admin users at a root entity may create these for their own root
- they are still not platform-global
- a `Diverse Internal` root key should not automatically access other roots such as brokerages or agent-practice trees

Long-term direction:

- these should eventually be owned by service accounts rather than normal human users

### Recommended Effective Access Model

For a request using an API key, effective access should be:

`effective permissions = stored_key_scopes`
`  ∩ owner_current_effective_permissions_in_anchor_context`
`  ∩ key_kind_allowlist`
`  ∩ key_entity_scope`

Where:

- `stored_key_scopes` are the scopes requested and accepted at creation time
- `owner_current_effective_permissions_in_anchor_context` are dynamically derived from current role and membership state
- `key_kind_allowlist` is the product policy for `personal` vs `system_integration`
- `key_entity_scope` is the anchor entity plus optional descendants

This is a hybrid model:

- the key never gains permissions beyond what was explicitly granted at creation time
- the key can lose permissions automatically when the owner's current access shrinks

This is the recommended model for v1 of the enhancement.

### Why Hybrid Is Preferred

### Snapshot-Only Model

`effective permissions = stored_key_scopes`

Pros:

- simplest runtime path
- predictable integrations

Cons:

- stale privilege risk
- requires aggressive background revocation to avoid unsafe drift

### Fully Dynamic Model

`effective permissions = owner_current_permissions_in_entity`

Pros:

- minimal drift

Cons:

- key can unexpectedly gain new powers when the owner gains new privileges
- poor fit for explicit API-key provisioning UX

### Hybrid Model

`effective permissions = stored_key_scopes ∩ owner_current_permissions_in_entity`

Pros:

- no privilege gain after creation
- automatic privilege reduction when owner access shrinks
- maps well to explicit admin UI

Cons:

- slightly more runtime complexity

Recommendation: use the hybrid model.

### Grant-Time Policy

Creation, update, and rotation should all pass through the same grant policy rules.

#### Required Inputs

- actor user ID
- owner user ID
- key kind
- anchor entity ID
- inherit-from-tree flag
- requested scopes

#### Required Checks

### 1. Ownership Validity

- owner must exist
- owner must be active
- owner must be a member of or otherwise validly anchored to the selected entity

### 2. Actor Grant Authority

The actor creating or updating the key must:

- have key-management authority in the selected entity
- only be allowed to grant scopes they themselves can grant in that entity

This is stricter than "the actor has some admin role somewhere."

### 3. Owner Capability Ceiling

The requested scopes must be a subset of the owner's current effective permissions in the selected entity context.

### 4. Key-Kind Allowlist

The requested scopes must be a subset of the allowed scope catalog for that key kind.

Example product policy:

- `personal` keys may allow read/update integration scopes only
- `system_integration` keys may allow broader CRUD and automation scopes

The exact allowlist remains an open product decision.

### 5. Entity Policy

- `personal` keys require an anchor entity
- `system_integration` keys also require an anchor entity
- root anchors are allowed to cover the root subtree
- root anchors do not cross into other roots

### Runtime Policy

Even if proactive revocation misses an event, a key should still stop working immediately when it should no longer be valid.

At runtime, the library should check:

- key exists and is active
- key owner still exists
- key owner can still authenticate
- owner still has valid access to the anchor entity context
- requested permission is included in the key's stored scopes
- requested permission is still currently allowed by the owner's effective permissions in that context
- requested entity lies within the key's allowed entity scope

If any of these checks fail, deny the request.

### Proactive Revocation and Reconciliation

Runtime denial is mandatory. Proactive revocation is still desirable for clarity, auditability, and operational hygiene.

#### Revoke Immediately When

- owner is deleted
- owner is suspended or banned
- owner loses access to the key anchor entity entirely
- anchor entity is archived

#### Reconcile When

- role assignments change
- entity membership role mix changes
- role definitions change
- membership status changes

In these cases, a key may:

- remain valid with reduced live capabilities
- or be revoked if it now has no effective scopes at all

#### Recommended Rule

Do not automatically revoke a key on every permission reduction.

Instead:

- let runtime intersection reduce capabilities immediately
- revoke only when the owner loses anchor access entirely, becomes non-authenticatable, or the key collapses to zero effective scopes

This preserves key continuity while still staying safe.

### Root-Level Behavior

#### Root Entity Keys

A root-level key should mean:

- access to that root entity
- and optionally all descendants in that root tree

It should not mean:

- access to all roots in the system
- access to unrelated organizations

Example:

- a key anchored to `Diverse Internal` may reach departments below `Diverse Internal`
- it should not automatically reach brokerage or agent-practice trees that are rooted elsewhere

#### Platform-Wide or Worker-Level Automation

True system-wide automation should not reuse normal admin-created user-owned keys.

That should be handled separately, likely through:

- service tokens
- or a dedicated future system-integrations layer

This epic intentionally excludes platform-global user-owned keys.

### Recommended Service Design Changes

#### New Policy Service

Add a dedicated policy service, for example:

- `ApiKeyPolicyService`

Potential responsibilities:

- `validate_key_grant(...)`
- `calculate_owner_grantable_scopes(...)`
- `calculate_actor_grantable_scopes(...)`
- `is_key_still_valid(...)`
- `reconcile_user_keys(user_id)`
- `reconcile_entity_keys(entity_id)`

This service should centralize policy so the router, service layer, and host apps do not each invent their own version.

#### Router Strategy

Keep the current packaged router for owner-self-service if needed, but add a clearer admin-oriented path for EnterpriseRBAC integrations.

The admin flow should be entity-first rather than owner-first.

Desired admin flow:

- choose anchor entity
- choose key kind
- choose inherit-from-tree
- choose owner
- show only grantable scopes
- create key

### UI Implications for Host Apps

The admin UI should not try to invent policy in the browser.

The UI should:

- ask the backend what key kinds are allowed here
- ask the backend what scopes are grantable for this actor, owner, key kind, and entity
- present only those scopes
- still expect backend validation to be authoritative

The API key UI that exists in current host apps is not yet aligned with this model and should be treated as pre-epic scaffolding rather than final design.

### Implementation Phases

#### Phase 1: Library Policy Foundation

- add key kinds
- add policy service
- add grant-time validation
- add runtime owner-state and anchor-state validation helpers
- define revocation triggers and reconciliation utilities

#### Phase 2: Enterprise Admin Management Surface

- add admin-oriented API endpoints
- expose grantable scopes and key-kind policy to host apps
- expose root-entity integration-key behavior clearly

#### Phase 3: Host-App Adoption

- migrate admin UI to entity-first key management
- stop relying on legacy API-key UI contracts
- align host-route policy with mounted-route policy

#### Phase 4: Audit and Observability Hardening

- wire API key grant/update/revoke/reconcile events into existing audit/history surfaces
- add metrics and structured logs for policy denials and reconciliation outcomes
- make the new policy layer operationally visible before broader rollout

#### Phase 5: Service Account Follow-Up

- add non-human principals for durable integration ownership
- migrate `system_integration` keys away from normal human ownership where appropriate

### Phase Status Checkpoint

- Phase 1 is largely complete for the current `personal`-key backend slice
- Phase 2 is largely complete on the backend through the entity-first admin API
- Phase 3 is partially complete:
  - the backend host contract now exists through mounted routers and
    `auth.authorize_api_key(...)`
  - the UI adoption step in `../OutlabsAuthUI` is still pending
- Phase 4 is partially complete:
  - observability hooks are in place
  - audit/reconciliation hardening can still expand later
- Phase 5 has not started

### Validation Strategy

This epic should be validated in two distinct testing phases rather than
treating backend and frontend verification as one blended test harness.

#### Phase A: Python / Example-API Validation

The primary backend validation harness for this work should be the
EnterpriseRBAC example API in this repository.

Use this phase to validate:

- grant-time policy behavior
- runtime permission reduction
- lifecycle invalidation and reconciliation behavior
- admin-oriented API contracts
- audit and observability outputs at the backend boundary

Planning direction:

- prefer Python integration and contract tests first
- use the EnterpriseRBAC example app as the host-like environment for testing mounted routers and host-facing policy behavior
- treat this as the backend source of truth before any frontend end-to-end work begins

#### Phase B: Frontend End-to-End Validation

After the backend behavior is stable in the example API, run end-to-end testing
through the external admin UI sidecar in `../OutlabsAuthUI`, pointed at the
EnterpriseRBAC example backend.

Use this phase to validate:

- entity-first key management workflows
- grantable-scope UX and denial handling
- create, update, rotate, and revoke flows
- audit/visibility surfaces exposed to operators
- the real browser behavior of the admin product against the example API

Planning direction:

- use Playwright-based browser coverage in the UI repository
- keep the backend-under-test anchored to the EnterpriseRBAC example API
- treat this as a second validation phase, not as a substitute for Python-based backend testing

## Locked Decisions for Initial Implementation

These decisions are now considered locked for the first implementation slice so
work can begin without reopening the same design questions repeatedly.

### 1. V1 Scope: `personal` First

The initial implementation will ship `personal` keys first.

This means:

- self-owned flow first
- entity anchor required
- explicit scopes required
- optional descendant inheritance if policy allows

`system_integration` remains part of the planned design, but it is not required
for the first implementation slice.

To avoid a later refactor:

- introduce `key_kind` in the model and policy design now
- keep the policy service and admin API shaped so `system_integration` can slot in later
- preserve the documented path for root-anchored integration keys and later service-account ownership

The goal is to defer product surface area, not to defer the extensibility point.

### 2. New Admin-Managed Keys Must Be Anchored and Explicitly Scoped

For the initial implementation:

- new admin-managed keys must have an anchor entity
- new admin-managed keys must have explicit scopes
- the admin flow should not create unanchored keys
- the admin flow should not treat empty scopes as unrestricted access

This intentionally tightens the current permissive defaults because there are no
existing production keys to preserve.

### 3. Zero-Effective-Scope Keys Stay Stored but Become Ineffective

If a key still exists but its effective permissions collapse to zero:

- do not auto-delete it
- do not introduce a new persisted status solely for this in the first cut
- keep it stored but runtime-denied
- expose this clearly through derived state, audit, or operator-facing visibility

This keeps the implementation simpler while preserving a clear path to stronger
reconciliation semantics later if needed.

### 4. Lifecycle Rule: Runtime Denial for Temporary Changes, Revoke for Durable Invalidations

For the first implementation:

- temporary or reversible access changes should rely on runtime denial first
- durable invalidation events should revoke the key

Practical direction:

- suspension or ordinary permission reduction: runtime denial, not immediate revoke
- user deleted or banned: revoke
- owner loses anchor access entirely: revoke
- anchor entity archived: revoke

This preserves safety without making every temporary state change destructive.

### 5. Reconciliation Can Be Asynchronous in V1

Runtime safety remains mandatory and immediate.

Reconciliation exists to improve:

- stored state clarity
- auditability
- operational hygiene

Because runtime intersection already provides the main safety property, the
first implementation does not need synchronous reconciliation on every
membership, role, or permission-definition change.

Planning direction:

- allow asynchronous reconciliation for cleanup and consistency
- reserve synchronous handling for clearly durable invalidation events where the write path already owns the transition

### 6. Audit History for Durable Changes, Logs and Metrics for Denials

For the first implementation:

- durable audit history should cover key state changes and policy-driven lifecycle changes
- structured logs and metrics should cover denials and high-volume runtime outcomes

Durable audit events should include at least:

- create
- update
- rotate
- revoke
- automatically disabled or reconciled due to lifecycle/policy changes

This keeps the durable event stream useful and queryable without turning it
into a noisy runtime telemetry sink.

## Remaining Pre-UI Checklist

With the backend `personal`-key slice now in place, the remaining items are no
longer broad architecture questions. They are mostly pre-UI contract and test
follow-ups.

### Product and Policy Checklist

- confirm whether the initial `personal` allowlist needs any expansion for the
  first real admin-product use case
- confirm whether destructive operations stay fully excluded for `personal`
  keys
- confirm whether descendant inheritance is exposed in the first UI workflow or
  kept behind a stricter policy gate

### API and Runtime Contract Checklist

- document the exact host-facing response/denial contract around
  `auth.authorize_api_key(...)` if host products need to render richer runtime
  failure states
- confirm whether `inherit_from_tree` should be exposed in the first admin UI
  workflow or left implicit there
- confirm whether the current derived effectiveness fields are sufficient for
  operators or whether an additional admin diagnostic surface is needed

### Audit and Observability Checklist

- finalize durable audit event names for create, update, rotate, revoke, and reconcile outcomes
- finalize the minimum audit payload for those events
- finalize which policy denials are logs/metrics only versus durable audit history
- finalize the initial metric/log vocabulary for policy denials and reconciliation outcomes

### Validation Checklist

- add the remaining Python edge-case coverage for denial branches,
  observability-through-route-flow, pagination/filter extremes, and
  admin-created key rate-limit/IP-whitelist behavior
- identify the Playwright end-to-end scenarios to add in `../OutlabsAuthUI`
  against the EnterpriseRBAC example backend
- confirm the backend API behavior that must remain stable before the UI phase
  begins

### Explicitly Open Questions

These points are not fully decided yet and should remain open until implementation planning begins.

#### Product and Policy Questions

- Which exact permissions are allowed for `personal` keys? This determines the backend allowlist and what the UI can safely present.
- Which exact permissions are allowed for `system_integration` keys? This determines whether org-scoped automation remains controlled or drifts into quasi-platform access.
- Should `personal` keys ever be allowed to request destructive operations such as delete? This is the main blast-radius decision for human-owned automation.
- Should `system_integration` keys be creatable by any admin at a root entity, or only by a narrower root-admin tier? This defines who can mint durable org-scoped automation credentials.
- Should `inherit_from_tree` become an explicit public API field in the first admin surface, or stay implicit until the entity-first workflow is introduced? This affects API contract stability.

#### Lifecycle Questions

- Should role-definition permission changes trigger immediate key reconciliation synchronously, or should that happen asynchronously through a background workflow? This determines write-path latency and implementation complexity.
- Should host applications be expected to call an auth-owned runtime policy helper rather than using `verify_api_key(...)` directly? Without this, mounted routes and host routes will continue to drift.
- Which API key policy outcomes belong in durable audit history versus structured logs/metrics only? This should be decided before implementation so the event surface stays coherent.

#### Ownership Questions

- Is human ownership acceptable for `system_integration` keys in the near term, or should those wait for service accounts? This determines whether Phase 2 can ship independently of service-account work.

#### Platform-Scope Questions

- Should platform-global automation live entirely in service tokens? This is the cleanest way to avoid normal API keys becoming a second system-wide credential type.
- Or should OutlabsAuth eventually add a separate system-integration primitive that is distinct from normal API keys? This remains open if service tokens prove too narrow for long-lived external integrations.

### Current Recommendation

If implementation started today, the recommended first cut would be:

- `personal` keys
  - self-owned only
  - anchor entity required
  - optional descendant inheritance
  - safe allowlist only
  - live runtime reduction through owner-permission intersection

- `system_integration` keys
  - root-entity anchored
  - broader allowlist
  - allowed for authorized admins within that root entity
  - still not cross-root
  - service-account migration planned later

- true platform-global automation
  - not supported through normal admin-created API keys
  - handled separately through service tokens or a future dedicated layer

### Summary

This is not a greenfield API key system. OutlabsAuth already has the core primitives and part of the runtime enforcement model.

The main work is:

- adding a real grant policy layer
- making entity anchoring and key kinds explicit
- making runtime and lifecycle invalidation rules consistent
- exposing an admin-oriented management surface

The target design should preserve explicit API-key provisioning while ensuring keys never exceed what the owner can currently do inside the intended entity scope.
