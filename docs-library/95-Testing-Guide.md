# Testing Guide

> **Handbook · Reference** — run and extend tests for the library and host apps.  
> Part of the [OutlabsAuth Handbook](./README.md). Deeper fixture/CI notes:
> [`tests/README.md`](../tests/README.md).

---

## Quick start

```bash
# Full local suite (Postgres required; Redis is optional in this mode)
uv run pytest

# Mandatory real-Redis contract: counter, quota, cache and invalidation tests
TEST_REDIS_URL=redis://localhost:56379/15 \
TEST_REDIS_REQUIRED=1 \
uv run pytest -m redis

# Focused
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/unit/services/test_permission_scope.py -v
```

Prefer `uv run pytest` so the interpreter matches `pyproject.toml` (Python 3.12+).

---

## Layout

```
tests/
├── README.md          # Detailed fixtures, markers, troubleshooting
├── conftest.py        # Shared engine / session / auth fixtures
├── unit/              # Narrow scope (often still hits Postgres)
└── integration/       # Router + multi-service flows against a real DB
```

“Unit” here means **narrow**, not necessarily mock-everything. Tests using the
real-Redis fixtures are automatically marked `redis`. They may skip in an ordinary
local run, but `TEST_REDIS_REQUIRED=1` converts an unavailable Redis into a failure.
Release CI runs that fail-closed selection independently and again as part of the
complete PostgreSQL + Redis suite.

---

## What hosts should test

When embedding OutlabsAuth, prefer:

1. **Smoke** — migrate/bootstrap, login, one `require_permission` route  
2. **Your mounts** — prefixes and feature flags you actually enable  
3. **Example parity** — run or copy patterns from
   `examples/*/api_integration_check.py` / smoke scripts when relevant  

Do **not** re-test the whole library suite inside every host CI — depend on
published versions and keep host tests on product routes.

Library release gates also run an Enterprise API integration suite; see
[`docs/PRIVATE_RELEASE.md`](../docs/PRIVATE_RELEASE.md).

---

## Writing library tests (contributors)

| Prefer | Avoid |
|--------|--------|
| Existing fixtures in `conftest.py` / `tests/fixtures/` | One-off engines per file |
| Asserting public router/service contracts | Scraping private helpers unless testing that helper |
| Markers (`@pytest.mark.unit`, `.integration`) | Undocumented skips |
| Real Redis for counter expiry, concurrency and recovery | Redis-shaped mocks for server semantics |

Examples of focused suites: OAuth callbacks, session inventory, API key
lifecycle, query-count budgets under `tests/integration/`.

---

## Common issues

| Symptom | Likely fix |
|---------|------------|
| Connection errors to Postgres | Start local Postgres; check `DATABASE_URL` / test defaults in `conftest` |
| Cache / rate-limit tests skipped | Set `TEST_REDIS_URL`, `TEST_REDIS_REQUIRED=1`, then run `pytest -m redis` |
| Flaky timing around activity sync | Prefer unit tests that mock Redis for ActivityTracker |

---

## Related

- [`tests/README.md`](../tests/README.md)
- [Configuration](./03-Configuration.md)
- [Observability](./97-Observability.md)
- Maintainer testing strategy: [`docs/TESTING_GUIDE.md`](../docs/TESTING_GUIDE.md)
