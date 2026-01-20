## Enterprise Readiness Validation Plan (Postgres)

> **Status: Updated 2025-01-20** - Many items from the original plan are now complete. See section 0 for current state.

This repo makes "enterprise" claims (hierarchical entities, tree permissions, closure-table performance, caching/observability). This plan is how we validate those claims against the **actual SQL schema**, **actual query plans**, and **real client behavior** (admin UI).

### Goals
- Prove the SQL migration matches the design intent: tables, foreign keys, cascade semantics, and indexes.
- Prove correctness of hierarchical behaviors at scale: closure table, tree permissions, membership scoping, revocations.
- Prove performance in realistic and worst-case scenarios with repeatable benchmarks and clear acceptance criteria.
- Prove real integration with the admin UI + any consumer app via running FastAPI instances.

### Non-goals (for now)
- Perfect backwards compatibility (explicitly not required; no production users).
- Multi-tenant isolation hard guarantees (can be added after core enterprise correctness/perf is green).

---

## 0) Current State / Known Gaps

**Updated 2025-01-20**: Most gaps have been addressed.

| Item | Status | Notes |
|------|--------|-------|
| Enterprise permission evaluation | ✅ Complete | `PermissionService` supports entity context, uses closure table, `_tree` semantics |
| Closure-table maintenance (create/delete/move) | ✅ Complete | `EntityService.move_entity()` rebuilds closure correctly |
| Example seeding docs | ✅ Fixed | `reset_test_env.py` is canonical, MongoDB refs removed |
| Schema validation | ✅ Automated | `tests/unit/test_schema_integrity.py` - 104 tests passing |
| Observability instrumentation | ✅ Complete | All services instrumented with metrics and logging |

### Remaining Work

- **Performance benchmarks**: k6/locust harness not yet created
- **Browser automation**: Playwright/Cypress tests for admin UI not yet created
- **Contract tests**: API contract test suite not yet created

---

## 1) Schema Conformance (DB-Level)

### 1.1 Generate schema from migrations (or metadata if migrations aren't ready)
**Status**: ✅ Working - `SQLModel.metadata.create_all` for dev, Alembic planned for production.

### 1.2 Verify constraints and cascade semantics in Postgres
**Status**: ✅ Automated in `tests/unit/test_schema_integrity.py`

**Must-haves** (all verified):
- Closure table unique constraint: `(ancestor_id, descendant_id)`
- Closure FKs cascade on entity delete (`ON DELETE CASCADE`)
- Entity `parent_id` is `ON DELETE SET NULL`
- Membership join-table FKs cascade
- Indexes exist for descendant/ancestor lookups and membership lookups

---

## 2) Correctness Conformance (Behavior)

### 2.1 Closure table correctness invariants
**Status**: ✅ Tested

Tests in `tests/unit/services/test_entity_service_move.py` verify:
- Self row exists: `(E,E,depth=0)`
- Ancestor relationships maintained correctly
- Delete cascades closure rows
- Move/re-parent rebuilds closure correctly

### 2.2 Tree permissions semantics
**Status**: ✅ Implemented and tested

Implementation in `outlabs_auth/services/permission.py`:
- `permission` without `_tree` grants access only within the target entity
- `permission` with `_tree` grants access to descendants via closure table
- Global roles from `UserRoleMembership` apply regardless of entity context

Tests in `tests/unit/services/test_permission_service_enterprise.py` verify tree permission behavior.

### 2.3 Re-parenting / moving entities
**Status**: ✅ Implemented

`EntityService.move_entity()` in `outlabs_auth/services/entity.py`:
- Updates `parent_id`
- Rebuilds closure rows for moved subtree
- Handles cache invalidation

---

## 3) Performance Conformance (Extreme Cases)

### 3.1 Scale targets
Suggested targets (not yet benchmarked):
- Max depth: 10 (in config defaults)
- Entities per tenant: 10k / 50k / 100k tiers
- Memberships per user: 1 / 10 / 100
- Roles per membership: 1–5

**Latency targets (P95)**
- `check_permission` (uncached): < 20ms for 10k entities, depth<=10
- `check_permission` (cached): < 5ms
- "get descendants" for an org: < 50ms for 10k entities

### 3.2 Bench harness
**Status**: ⏳ Not yet created

Need to add `benchmarks/` folder with:
- Dataset generator
- Benchmark runner (k6/locust/pytest-benchmark)
- EXPLAIN (ANALYZE, BUFFERS) snapshot capture

### 3.3 Query plan verification
**Status**: ⏳ Manual verification done, automated capture not yet

Critical queries use closure table indexes correctly (manual verification).

---

## 4) Example Seeding + Validation

### 4.1 SimpleRBAC example
**Status**: ✅ Working

```bash
cd examples/simple_rbac
python reset_test_env.py
uv run uvicorn main:app --port 8000 --reload
```

### 4.2 EnterpriseRBAC example
**Status**: ✅ Working

```bash
cd examples/enterprise_rbac
python reset_test_env.py
uv run uvicorn main:app --port 8000 --reload
```

---

## 5) Frontend (Admin UI) Integration

### 5.1 Contract tests
**Status**: ⏳ Not yet created

Need automated test suite hitting:
- `/v1/auth/config` (preset detection)
- Auth flows: login/refresh/logout
- CRUD: users, roles, permissions, api keys
- Enterprise: entities, memberships

### 5.2 Browser automation
**Status**: ⏳ Not yet created

Need Playwright/Cypress tests for:
- SimpleRBAC example instance
- EnterpriseRBAC example instance
- Entity switching (enterprise)
- Config detection

---

## 6) Deliverables Checklist

### Phase A (Schema + Correctness) ✅ COMPLETE
- [x] DB-level schema conformance
- [x] Postgres-backed integration tests for closure correctness
- [x] Example seed scripts unified

### Phase B (Core Enterprise Correctness) ✅ COMPLETE
- [x] Enterprise permission service using closure + entity memberships
- [x] Re-parent/move entity support with closure rebuild
- [x] Integration tests for tree semantics

### Phase C (Enterprise Performance) ⏳ PENDING
- [ ] Deterministic dataset generator
- [ ] Bench runner (k6/locust)
- [ ] Query plan snapshots

### Phase D (Frontend) ⏳ PENDING
- [ ] Contract tests
- [ ] Browser automation suite
