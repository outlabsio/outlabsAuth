## Enterprise Readiness Validation Plan (Postgres)

This repo makes “enterprise” claims (hierarchical entities, tree permissions, closure-table performance, caching/observability). This plan is how we validate those claims against the **actual SQL schema**, **actual query plans**, and **real client behavior** (admin UI).

### Goals
- Prove the SQL migration matches the design intent: tables, foreign keys, cascade semantics, and indexes.
- Prove correctness of hierarchical behaviors at scale: closure table, tree permissions, membership scoping, revocations.
- Prove performance in realistic and worst-case scenarios with repeatable benchmarks and clear acceptance criteria.
- Prove real integration with the admin UI + any consumer app via running FastAPI instances.

### Non-goals (for now)
- Perfect backwards compatibility (explicitly not required; no production users).
- Multi-tenant isolation hard guarantees (can be added after core enterprise correctness/perf is green).

---

## 0) Current State / Known Gaps To Address

These are important because they determine what we can validate today vs what we must implement first.

1) **Enterprise permission evaluation is not implemented**
- `outlabs_auth/dependencies/__init__.py` calls `permission_service.check_permission(session, user_id, permission)` with no entity context.
- `outlabs_auth/services/permission.py` currently aggregates permissions from `UserRoleMembership` (global/flat RBAC). It does not use:
  - `EntityMembership`
  - `EntityMembershipRole`
  - `EntityClosure`
  - permission “_tree” semantics in an entity context

2) **Closure-table maintenance exists for create/delete, but not re-parent/move**
- `outlabs_auth/services/entity.py` maintains closure on create/delete.
- Re-parenting an entity (change `parent_id`) requires closure + path rebuild and should be implemented explicitly.

3) **Example seeding/testing docs are inconsistent**
- `examples/*/reset_test_env.py` is the real Postgres seeding path today.
- Some example docs mention `seed_data.py` which isn’t present.
- `tests/README.md` and parts of `docs/TESTING_GUIDE.md` still contain Mongo-era instructions.

4) **Schema validation is partially automated**
- We added metadata-level schema integrity tests (constraints/indexes) in `tests/unit/test_schema_integrity.py`.
- Still need DB-level verification via migrations + `psql` introspection (because metadata != actual deployed schema if migrations drift).

---

## 1) Schema Conformance (DB-Level)

### 1.1 Generate schema from migrations (or metadata if migrations aren’t ready)
**Expected deliverable:** A reproducible “create schema” path.

- If Alembic is the source of truth:
  - Apply migrations in a clean DB and treat that as authoritative.
- If SQLModel metadata is the source of truth:
  - Use `SQLModel.metadata.create_all` only for dev/testing, and migrate to Alembic ASAP for production readiness.

### 1.2 Verify constraints and cascade semantics in Postgres (not just in code)
**Commands (examples):**
- `\\d+ entities`
- `\\d+ entity_closure`
- `\\d+ entity_memberships`
- `\\d+ entity_membership_roles`
- `\\d+ role_permissions`

**Must-haves:**
- Closure table unique constraint: `(ancestor_id, descendant_id)`
- Closure FKs cascade on entity delete (`ON DELETE CASCADE`)
- Entity `parent_id` is `ON DELETE SET NULL`
- Membership join-table FKs cascade (`entity_membership_roles.membership_id` etc.)
- Indexes exist for descendant/ancestor lookups (closure) and membership lookups (`user_id`, `entity_id`, `(user_id,status)`).

---

## 2) Correctness Conformance (Behavior)

### 2.1 Closure table correctness invariants
**Must-haves for any entity `E`:**
- Self row exists: `(E,E,depth=0)`
- For any ancestor `A` of `E`, closure includes `(A,E,depth>=1)`
- No duplicates (enforced by unique constraint)

**Test plan:**
- Seed a hierarchy using `examples/enterprise_rbac/reset_test_env.py`.
- Add integration tests that:
  - Assert counts for known small trees.
  - Validate ancestor/descendant sets match expected nodes.
  - Validate deletes cascade closure rows.

### 2.2 Tree permissions semantics (enterprise claims)
**Expected deliverable:** An “EnterprisePermissionService” (or equivalent) that checks permissions in an entity context and uses the closure table.

**Proposed semantics to implement (explicit, testable):**
- `permission` without `_tree` (e.g. `lead:read`) grants access only within the target entity.
- `permission` with `_tree` (e.g. `lead:read_tree`) grants access to the target entity AND its descendants.
- Global roles from `UserRoleMembership` optionally apply regardless of entity context (decision needed; document it and test it).

**Query shape (fast path):**
- Find ancestors of target entity via `entity_closure` (`descendant_id = target`, includes self).
- Join memberships for `user_id` on `entity_id IN ancestors`.
- Join membership roles → roles → role_permissions → permissions.
- Check:
  - exact match OR wildcard (`resource:*` OR `*:*`)
  - `_tree` logic: permission should match if membership is on an ancestor and permission ends in `_tree`.

**Acceptance tests:**
- Membership on parent with `lead:read_tree` allows reading leads in child.
- Membership on child with `lead:read_tree` does **not** allow reading leads in parent.
- Revoked/suspended memberships do not grant.
- Validity windows respected.

### 2.3 Re-parenting / moving entities (enterprise requirement)
**Expected deliverable:** A supported, tested operation for changing `parent_id`.

**Required behaviors:**
- Update `depth`/`path` for moved subtree.
- Rebuild closure rows for moved subtree (delete old closure edges + insert new).
- Cache invalidation (if enabled).

---

## 3) Performance Conformance (Extreme Cases)

### 3.1 Define scale targets and acceptance criteria
We need explicit numeric targets. Suggested starting points:
- Max depth: 10 (already in config defaults)
- Entities per tenant: 10k / 50k / 100k tiers
- Memberships per user: 1 / 10 / 100
- Roles per membership: 1–5

**Latency targets (P95)**
- `check_permission` (uncached): < 20ms for 10k entities, depth<=10
- `check_permission` (cached): < 5ms
- “get descendants” for an org: < 50ms for 10k entities

These numbers should be tuned once we have real EXPLAIN results.

### 3.2 Bench harness
**Deliverable:** Add a `benchmarks/` folder with:
- Dataset generator (deterministic seed, parameterized sizes)
- Benchmark runner (k6/locust/pytest-benchmark)
- Optional `EXPLAIN (ANALYZE, BUFFERS)` snapshot capture for critical queries

### 3.3 Query plan verification (the “enterprise proof”)
For each critical query, capture:
- SQL text (or ORM query shape)
- `EXPLAIN (ANALYZE, BUFFERS)`
- Confirmation that the intended indexes are used (no sequential scans on closure/membership joins)

Critical queries:
- `entity_closure` ancestor lookup for a target entity
- permission check join across closure → memberships → roles → permissions

---

## 4) Example Seeding + Example Validation

### 4.1 SimpleRBAC example
Seed/reset:
- `python examples/simple_rbac/reset_test_env.py`

Validation:
- Run `examples/simple_rbac/main.py` and verify core flows:
  - login/register, users/roles/permissions CRUD, API keys
  - metrics at `/metrics` when enabled

### 4.2 EnterpriseRBAC example
Seed/reset:
- `python examples/enterprise_rbac/reset_test_env.py`

Validation:
- Run `examples/enterprise_rbac/main.py` and verify:
  - entity hierarchy endpoints
  - memberships endpoints
  - closure table correctness (basic sanity)
  - (after enterprise permission service is implemented) tree permission behavior in domain routes

**Note:** Some example docs reference `seed_data.py` which isn’t present; either update docs to use `reset_test_env.py` or reintroduce a canonical `seed_data.py`.

---

## 5) Frontend (Admin UI) Integration Validation

**Objective:** Confirm the admin UI can manage both presets against any running FastAPI instance using the plugin.

### 5.1 Contract tests (API surface)
Automate a “contract” suite that hits:
- `/v1/auth/config` (preset detection)
- auth flows: login/refresh/logout
- CRUD: users, roles, permissions, api keys
- enterprise: entities, memberships

### 5.2 Browser automation (Playwright/Cypress)
Run the admin UI against:
- SimpleRBAC example instance
- EnterpriseRBAC example instance

Validate:
- config detection works
- entity switching works (enterprise)
- tree permission UX flows (after backend semantics are complete)

---

## 6) Deliverables Checklist (Proposed)

### Phase A (Now)
- DB-level schema conformance checklist + `psql` verification steps
- Postgres-backed integration tests for closure correctness
- Example seed scripts unified and docs aligned

### Phase B (Core Enterprise Correctness)
- Enterprise permission service using closure + entity memberships
- Re-parent/move entity support with closure rebuild + cache invalidation
- Integration tests for all invariants (revocation/validity, tree semantics)

### Phase C (Enterprise Performance)
- Deterministic dataset generator
- Bench runner (k6/locust) + published P95 results
- Query plan snapshots + index verification

### Phase D (Frontend)
- Contract tests + browser automation suite
