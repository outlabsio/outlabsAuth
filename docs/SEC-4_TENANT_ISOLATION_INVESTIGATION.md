# SEC-4 — Cross-Tree User Access: Design Investigation (NOT a patch)

**Status:** Open design question — deliberately **deferred** from the 2026-06 security hardening.
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
