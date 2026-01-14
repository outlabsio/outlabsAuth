# Real-World Testing (OutlabsAuth)

This repo currently has:
- Unit tests for core services + schema integrity (`tests/unit`)
- Postgres-backed integration tests for key EnterpriseRBAC endpoints (`tests/integration`)

To validate “enterprise ready” behavior, use **layered testing**:

## 1) Run integration tests (fastest confidence)

Requires a running Postgres DB matching `TEST_DATABASE_URL` from `tests/conftest.py`.

```bash
uv run pytest -q
```

These tests hit real FastAPI endpoints via ASGI transport and validate:
- Tree permission enforcement on create/read/list flows
- Closure table correctness after entity move/re-parent

## 2) Run the example app + hit real endpoints (smoke/regression)

Start the EnterpriseRBAC example and seed it:

```bash
cd examples/enterprise_rbac
uv run python reset_test_env.py
uv run uvicorn main:app --reload --port 8004
```

In another terminal, run the smoke script (hits `/v1/*` endpoints):

```bash
uv run python scripts/smoke_enterprise_api.py
```

Config:
- `BASE_URL` (default `http://localhost:8004/v1`)
- `EMAIL` / `PASSWORD` (default seeded admin `admin@acme.com` / `Test123!!`)

## 3) Add coverage for remaining “enterprise” paths

Recommended next endpoint-level tests:
- Users: CRUD + status transitions + password reset flows
- Roles/permissions: CRUD + assignment edge cases
- API keys: create/revoke + rate-limit/lock behaviors
- Negative cases: invalid UUIDs, forbidden access, pagination bounds, race conditions

## 4) Performance tests (when schema/behavior is stable)

Add a dedicated perf harness (k6/locust) and measure:
- Closure-table descendant queries at depth N (and after move operations)
- Permission checks under high concurrency
- Worst-case list endpoints with pagination + indexes

