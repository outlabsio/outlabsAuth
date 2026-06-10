# SEC-4 — Cross-Tree User Access: Design Investigation (RESOLVED)

**Status:** **Resolved** (2026-06-10). The maintainer accepted the recommendation (candidate 1) and
the open decision points: **404** for out-of-scope targets, **default-on** enforcement with a
transitional `enforce_user_scope` flag, and reads + writes scoped **together**. The decision is
recorded as **DD-056** in `docs/DESIGN_DECISIONS.md` and is implemented with tests
(`tests/integration/test_users_scope_and_isolation.py`). This document is retained as the
investigation record behind DD-056.
**Why this is separate:** Unlike the other SEC findings, this is not clearly a bug. It depends on
intended multi-tenant semantics that must be decided with full product context before any code changes.
Changing it would alter the authorization model and break an existing test that asserts the current
behavior. **Do not implement until this is resolved.**

---

## The observation (from the audit)

User-management endpoints (`/users/{id}` read/update/delete, `/users/{id}/status`, `/users/{id}/roles`,
password reset, restore) enforce **no entity/tenant scoping**. Authorization is a flat
`require_permission("user:read" | "user:update" | ...)` with no check that the *target* user is within
the *actor's* accessible entity scope. So a non-superuser admin in one top-level tree can read/modify
users belonging to a different top-level tree.

- SimpleRBAC and superusers are unaffected (scope is always `is_global=True`).
- `AccessScopeService.resolve_for_auth_result(...)` already computes the actor's `entity_ids`,
  `root_entity_ids`, and `member_user_ids` — the machinery to enforce scoping exists; it's simply not
  applied on the user routes (it *is* applied on the roles routes via `_require_role_visibility`).
- An existing test (`tests/integration/test_users_router_callback_paths.py::
  test_users_router_callback_identity_and_cross_root_access_paths`) explicitly asserts a non-superuser
  actor in `root_a` can read a user in `root_b`. (Note: that test bypasses the `require_permission`
  dependency and exercises the endpoint body, so it documents body behavior, not an authz decision.)

## The actual design question (from the maintainer)

There are **no "organizations"** as a first-class concept — only **top-level entities** and their
**child entities** (trees). The intuition:

- A **top-level entity admin should NOT** be able to reach down into *other* top-level entities' trees.
  → argues SEC-4 **is** a real isolation gap that should be closed.
- **But**: a legitimate use case is an **"administration" top-level entity** whose admins are meant to
  manage **all** other top-level entities. → if isolation is enforced naively, how does that actor
  operate? This may need a dedicated **system-level role** (or a "global scope" grant) rather than
  implicit cross-tree access.

So the behavior might be **partly by design** today (cross-tree access = the only way an admin-entity
can manage everything), and the right fix might be *introducing an explicit elevated role* rather than
*adding a blanket scope check*.

## Candidate designs to evaluate (not decided)

1. **Enforce tree isolation + explicit elevated scope.** Scope user mutations (and possibly reads) to
   the actor's `member_user_ids` / accessible `entity_ids`; introduce a `system:admin`-style role (or a
   `is_global` grant on a membership) that an administration entity holds to legitimately span all
   trees. Most secure; needs a new role/grant concept and migration of any existing admin-entity setups.
2. **Writes-scoped, reads-global.** Keep reads cross-tree (directory-style) but scope the dangerous
   mutations. Smaller change; leaves a read-side information-disclosure surface.
3. **Status quo is intended.** Cross-tree access is the deliberate model; document it as a design
   decision (a new DD-xxx) and add tests asserting it, so it's an explicit choice rather than an
   accidental gap. Lowest effort; accepts the current exposure.

## Open questions for the investigation

- Is there (or should there be) a first-class notion of a **system/administration entity** or
  **system-level role**? How is "this actor may span all top-level trees" represented today, if at all?
- Do the **roles** routes' scoping semantics (`_role_is_visible_in_scope`, `is_global`) already imply an
  intended user-scoping model that the user routes simply failed to mirror?
- Which endpoints are sensitive enough to scope: **mutations only**, or **reads too**?
- What existing deployments/admin-entity arrangements would a scoping change break? Migration path?
- Should `member_user_ids` be the basis, or `root_entity_id` membership, or both? (Edge case:
  users with a `root_entity_id` but no `EntityMembership` row.)

## Recommendation

Treat as a **dedicated design investigation** producing a Design Decision (DD-xxx) record, *then*
implement. Until then, the current behavior is **unchanged**. The other SEC findings are being fixed
independently and do not depend on this.

---

# Investigation findings (2026-06-10)

Code references are to branch `production-hardening` (post-fa2af29, i.e. with the SEC-1/2/3 fixes in).

## Q1 — How is "this actor spans all top-level trees" represented today? Is there a system/administration concept?

There are exactly **three** global-actor representations, and **none of them is grantable through a role**:

1. **`User.is_superuser`** — short-circuits everything: `PermissionService.check_permission` returns
   `True` immediately (`services/permission.py:407`), `get_user_permissions` returns `["*:*"]`
   (`permission.py:986`), and `AccessScopeService` returns `is_global=True` (`services/access_scope.py:103-111`).
2. **Unscoped API keys** — `APIKey.entity_id IS NULL` → `is_global=True` (`access_scope.py:216-225`).
3. **SimpleRBAC mode** — `enable_entity_hierarchy=False` forces `scope["is_global"] = True` at the
   router layer (`routers/roles.py:90-91`). SimpleRBAC is therefore structurally unaffected by any
   scoping change.

**The key structural fact: scope resolution is role-blind.** `resolve_for_auth_result` computes scope
purely from `User.root_entity_id` + active `EntityMembership` rows (+ closure-table descendants).
Holding *any* role — including a system-wide one — never widens an actor's scope. So if user routes
naively enforced scope today, the only surviving cross-tree actors would be superusers and unscoped
API keys. **The "administration top-level entity" pattern works today only because user routes check
no scope at all.** Neither the code, docs, nor `examples/enterprise_rbac` contain an
"administration entity" concept — the enterprise example grants global admin via the superuser flag,
not via an entity (`examples/enterprise_rbac/reset_test_env.py`).

However, a natural carrier for an explicit global grant **already exists in the model**:
**system-wide roles** — `is_global=True AND root_entity_id IS NULL AND scope_entity_id IS NULL`
(`routers/roles.py:75-76`). The roles router already treats them as privileged objects: invisible to
non-global actors ("Only superusers can access system-wide roles", `roles.py:140-141`), creatable
only by global-scope actors (`_require_role_create_scope`, `roles.py:157-161`), and — since the SEC-2
fix — assignable only by actors who already hold every permission the role carries
(`require_can_delegate_permissions`, `routers/users.py:1125-1133`). What's missing is one link:
**holding an active system-wide role does not currently influence `AccessScopeService`.** Adding that
link (system-wide role ⇒ `is_global=True` scope) gives the administration-entity use case an explicit,
auditable grant with zero schema change. This is precisely the "dedicated system-level role" the
maintainer hypothesized — it exists; it just doesn't affect scope yet.

## Q2 — Do the roles routes already imply the intended user-scoping model?

**Yes.** `_role_is_visible_in_scope` (`roles.py:112-128`) is a complete decision procedure:

| Object | Visible iff |
|---|---|
| anything, when `scope.is_global` | always |
| system-wide role | never (global scope only) |
| entity-local (`scope_entity_id` set) | `scope_entity_id ∈ actor.entity_ids` |
| root-scoped (`root_entity_id` set) | `root_entity_id ∈ actor.root_entity_ids` |

It is applied to **reads as well as writes** (get/update/delete/permission-edit/ABAC endpoints all call
`_require_role_visibility`; `GET /roles/` filters at query level, `roles.py:205-228`), resolved cheaply
with `include_member_user_ids=False` (`roles.py:87`), and tested
(`tests/integration/test_roles_scope_and_contract.py::test_scoped_admin_role_management_is_limited_to_access_scope`).
The user-route mirror is direct: a target **user** is in scope iff the actor's scope is global, or the
target's root/membership entities intersect the actor's `entity_ids` (predicate in Q5). The asymmetry
today — roles scoped, users not — is itself a trap: a scoped admin who cannot *see* a root_b role can
still *deactivate every root_b user*.

## Q3 — Scope mutations only, or reads too?

**Reads too.** The read surface is the larger practical leak:

- `GET /users/` returns **all users across all trees by default** — `root_entity_id` is an optional
  filter, never forced (`routers/users.py:239-318`; `services/user.py:978-1077`). Same for
  `GET /users/orphaned`.
- Per-user reads expose PII plus `roles`, `role-memberships`, `permissions`, `membership-history`, and
  `audit-events` (`users.py` — all gated by flat `user:read`). That is cross-tenant disclosure of the
  *authorization model itself*, ideal recon for the SEC-2/3-style escalation chain.
- The roles precedent already scopes reads; mirroring it keeps one mental model.

Error semantics: the roles router returns **403** for out-of-scope objects (`roles.py:139-146`).
For *user* targets, **404** is the better default (don't confirm existence of users in other tenants —
the audit classified this as IDOR); list endpoints silently filter. This diverges from the roles
router's 403 — flagged as a decision point in DD-056.

## Q4 — What breaks, and what's the migration?

- **The known test** — `tests/integration/test_users_router_callback_paths.py::
  test_users_router_callback_identity_and_cross_root_access_paths` asserts a root_a actor can read a
  root_b user (lines 240-245). It bypasses the `require_permission` dependency and calls the endpoint
  body directly, so enforcement placed in the endpoint body (the recommended placement, in/alongside
  `_get_target_user_or_404`) breaks it as intended. Update it to assert 404 cross-root + add a
  system-wide-role/global-path test. No other test asserts cross-tree user access (the only other
  cross-root tests cover membership role validation and roles-router scoping).
- **Deployments using an "administration entity"** whose admins manage all trees via the gap: after
  enforcement their cross-tree access stops. Migration = assign those admins the system-wide role (a
  superuser one-time action). Needs a release-note recipe; the library is pre-1.0 (0.1.0a22), so a
  breaking security default is acceptable — an opt-out config flag can ease transition (decision point).
- **Orphaned users** (no `root_entity_id`, no memberships — `GET /users/orphaned` exists for these)
  match no non-global scope, so they become visible/fixable **only by global actors**. That is arguably
  the correct semantics for orphan repair, but it must be documented.
- **Scoped API keys** (`entity_id` set) currently act on any user; after enforcement their existing
  entity scope applies via the same resolver. Unscoped keys are `is_global` — unaffected.
- **Performance**: `resolve_for_auth_result` is uncached and runs a CTE + closure expansion per call.
  The roles router already pays this per-request. Use `include_member_user_ids=False` (the expensive
  member enumeration is not needed — see Q5); a short-TTL per-user cache invalidated via the existing
  Redis pub/sub (DD-037) is an available optimization, not a blocker.

## Q5 — Enforcement basis: `member_user_ids`, `root_entity_id`, or both?

**`member_user_ids` alone is the wrong basis**, on two grounds:

1. **Correctness**: it is built solely from active `EntityMembership` rows
   (`access_scope.py:401-414`). A user with `root_entity_id` set but **no membership rows** — the edge
   case this doc raised — appears in *nobody's* `member_user_ids` and would be invisible to their own
   tree's admins.
2. **Cost**: it enumerates every user in scope on every request (unbounded for large tenants), where
   the alternative is O(target's memberships).

**Recommended predicate** — evaluate from the **target side** against the actor's (closure-expanded)
`entity_ids`; target user T is in actor scope iff:

```
scope.is_global
OR T.root_entity_id ∈ actor.entity_ids
OR ∃ active EntityMembership(T, e) with e ∈ actor.entity_ids
```

Using `entity_ids` (not just `root_entity_ids`) for the comparison is the safe superset: it covers
targets whose `root_entity_id` points at a non-top-level entity (the schema doesn't enforce
top-level-ness) and gives tree semantics for actors rooted mid-tree. Multi-root users (memberships
under several top-level roots) are visible to admins of *each* root — consistent with membership
semantics.

## Candidate evaluation

| Candidate | Verdict | Why |
|---|---|---|
| 1. Tree isolation + explicit elevated scope | **Recommended** | All machinery exists (resolver, system-wide roles, SimpleRBAC global-forcing, roles-router precedent + tests). The only new concept is one link: system-wide role ⇒ global scope. Closes both read and write surfaces; restores symmetry with roles routes. |
| 2. Writes-scoped, reads-global | Rejected | Leaves the biggest practical leak open (`GET /users/` enumerates all tenants; per-user permission/audit reads are escalation recon). Two mental models in one API. Roles precedent scopes reads. |
| 3. Status quo as intended | Rejected | Contradicts the maintainer's own isolation intuition, DD-005's "root-entity scoping provides practical isolation boundaries", and the roles-router model. Amplifies any future permission misconfiguration into cross-tenant compromise. |

---

# Proposed DD-056 (draft — ACCEPTED 2026-06-10; the canonical record lives in `docs/DESIGN_DECISIONS.md`)

**Title:** Tenant isolation on user-management routes; system-wide roles grant global scope
**Status:** PROPOSED (2026-06-10)
**Supersedes/extends:** complements DD-050/DD-053/DD-054 (role scoping), DD-005 (entity-based isolation)

## Decision

1. **Scope enforcement on user routes.** Every `/users` endpoint that targets or enumerates users
   resolves the actor's scope via `AccessScopeService.resolve_for_auth_result(...,
   include_member_user_ids=False)` and enforces the Q5 predicate:
   - **Target endpoints** (get/update/delete/status/restore/password/resend-invite/roles
     add-remove/role-memberships/permissions/membership-history/audit-events): out-of-scope target →
     **404** (anti-enumeration; deliberate divergence from the roles router's 403 — see decision
     point 2).
   - **List endpoints** (`GET /users/`, `GET /users/orphaned`): silently filter to actor scope;
     `root_entity_id` param narrows within scope, never widens. Orphaned users match only global scopes.
   - Enforcement lives in the endpoint body via `_get_target_user_or_404` (which already receives the
     unused `actor_user`) — making the existing parameter real, and covering the test's
     direct-call path.
2. **System-wide roles become the explicit global-scope grant.** `AccessScopeService` returns
   `is_global=True` for actors holding an **active** system-wide role (`is_global=True`,
   `root_entity_id IS NULL`, `scope_entity_id IS NULL`) via a currently-valid membership. Granting
   global span is thereby already a controlled operation: system-wide roles are creatable only by
   global actors and assignable only under SEC-2 delegation containment.
3. **Superuser-target guard.** A non-global actor can never mutate a user with `is_superuser=True`,
   even if that user has a membership inside the actor's tree.
4. **SimpleRBAC and unscoped API keys are unaffected** (scope is always global there). Scoped API
   keys are bounded by their existing `entity_id` scope.

## Consequences

- Closes the SEC-4 IDOR (read + write) and the third leg of the SEC-2/3/4 escalation chain.
- The administration-entity use case becomes an explicit, auditable role grant instead of an implicit
  gap; migration is a one-time system-wide-role assignment by a superuser.
- `test_users_router_callback_identity_and_cross_root_access_paths` must be updated to assert the new
  behavior; new tests mirror `test_roles_scope_and_contract.py` for users.
- Per-request scope resolution cost on user routes (same as roles routes today); optimizable with a
  short-TTL cache + DD-037 pub/sub invalidation.

## Decision points — RESOLVED (2026-06-10)

1. **Candidate 1 adopted** (candidates 2/3 rejected per evaluation).
2. **404** for out-of-scope user targets (anti-enumeration; deliberate divergence from the roles
   router's 403 — aligning roles to 404 is a possible follow-up).
3. **Rollout**: default-on, with `enforce_user_scope=False` as a transitional escape hatch for one
   alpha cycle.
4. **Reads and writes scoped together.**

DD-056 is recorded as **Accepted** in `docs/DESIGN_DECISIONS.md` and implemented;
`docs/SECURITY_AUDIT_2026-06-10.md` (SEC-4 row) is updated accordingly.
