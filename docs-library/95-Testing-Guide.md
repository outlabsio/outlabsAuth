# Testing Guide

> **Handbook · Reference** — run and extend tests for the library and host apps.  
> Part of the [OutlabsAuth Handbook](./README.md). Deeper fixture/CI notes:
> [`tests/README.md`](../tests/README.md).

---

## Quick start

```bash
# Full suite (Postgres required; Redis-backed tests skip if unreachable)
uv run pytest

# With Redis so cache / budget / activity tests actually run
TEST_REDIS_URL=redis://localhost:56379/15 uv run pytest

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

“Unit” here means **narrow**, not necessarily mock-everything. Redis-dependent
fixtures skip cleanly when `TEST_REDIS_URL` is down.

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

Examples of focused suites: OAuth callbacks, session inventory, API key
lifecycle, query-count budgets under `tests/integration/`.

---

## Common issues

| Symptom | Likely fix |
|---------|------------|
| Connection errors to Postgres | Start local Postgres; check `DATABASE_URL` / test defaults in `conftest` |
| Cache / rate-limit tests skipped | Set `TEST_REDIS_URL` to a reachable Redis |
| Flaky timing around activity sync | Prefer unit tests that mock Redis for ActivityTracker |

---

## Related

- [`tests/README.md`](../tests/README.md)
- [Configuration](./03-Configuration.md)
- [Observability](./97-Observability.md)
- Maintainer testing strategy: [`docs/TESTING_GUIDE.md`](../docs/TESTING_GUIDE.md)
