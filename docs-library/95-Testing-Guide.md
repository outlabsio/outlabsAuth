# Testing Guide

> **Handbook · Reference** — how to run and extend tests for hosts and the library.  
> Part of the [OutlabsAuth Handbook](./README.md).

## Overview

OutlabsAuth has a comprehensive test suite covering authentication, authorization, token management, RBAC, entities, API keys, and observability. Tests are organized into unit and integration suites and run against **PostgreSQL**, with Redis-dependent tests skipping automatically when Redis is unreachable.

**Scale**: 80 unit test files + 56 integration test files.

---

## Test Structure

```
tests/
├── README.md
├── conftest.py            # Shared fixtures (engine, session, auth instances, test data)
├── fixtures/
│
├── unit/                  # Isolated component testing
│   ├── authentication/    # backend, strategy, transport
│   ├── database/          # engine, registry
│   ├── integrations/      # host query service
│   ├── oauth/             # provider flows, state tokens, security
│   ├── observability/     # metrics, logging, FastAPI integration
│   ├── services/          # activity_tracker, api_key, auth lifecycle, access scope, ...
│   └── test_*.py          # jwt utils, password, presets, schema integrity, CLI, ...
│
└── integration/           # End-to-end workflows against a real database
    └── test_*.py          # auth/user/role/permission routers, entity hierarchy,
                           # API key lifecycle, session lifecycle, query budgets, ...
```

Both suites talk to a real PostgreSQL instance; "unit" here means narrow in scope, not necessarily database-free. Tests that mock their dependencies entirely (for example `tests/unit/services/test_activity_tracker.py`, which mocks Redis) need no services at all.

---

## Running Tests

### All Tests
```bash
# Run entire test suite
uv run pytest

# Run with coverage
uv run pytest --cov=outlabs_auth --cov-report=html
```

### By Suite
```bash
# All unit tests
uv run pytest tests/unit/ -v

# All integration tests
uv run pytest tests/integration/ -v

# A subdirectory
uv run pytest tests/unit/oauth/ -v
```

### Specific Test Files
```bash
uv run pytest tests/unit/services/test_activity_tracker.py -v
uv run pytest tests/integration/test_session_lifecycle.py -v

# A single test function
uv run pytest tests/unit/test_password.py::test_name
```

### By Marker

`conftest.py` registers three markers:

```bash
uv run pytest -m unit           # marked unit tests
uv run pytest -m integration    # marked integration tests
uv run pytest -m "not slow"     # skip slow tests
```

### By Pattern
```bash
uv run pytest -k "user"
uv run pytest -k "login"
uv run pytest -k "not slow"
```

---

## Test Fixtures

All shared fixtures live in `tests/conftest.py`.

### Database Fixtures

**`test_engine`** (function-scoped)
- Creates an async engine against `TEST_DATABASE_URL`
- Creates an **isolated PostgreSQL schema per test** (`test_<uuid>`), sets `search_path` to it, and runs `SQLModel.metadata.create_all`
- Drops the schema (CASCADE) after the test

**`test_session`** (function-scoped)
- An `AsyncSession` bound to `test_engine`, with `expire_on_commit=False`

Schema-per-test is what provides isolation - tests do not share tables and can run without cross-contamination.

### Configuration Fixtures

**`test_secret_key`** - a fixed test JWT secret

**`auth_config`** - an `AuthConfig` with the standard test policy: HS256, 15-min access tokens, 30-day refresh tokens, `max_login_attempts=5`, `lockout_duration_minutes=30`

### Auth Instance Fixtures

**`auth`**
- An initialized `SimpleRBAC` against `TEST_DATABASE_URL`
- `enable_token_cleanup=False`, observability disabled
- Creates tables on entry, drops them and calls `shutdown()` on exit

**`auth_with_cache`**
- `SimpleRBAC` wired with **real Redis** and permission caching enabled
- Exercises the cache service, pub/sub invalidation, and API-key counters
- **Skips** if Redis is unreachable

### Redis Fixtures

**`redis_client`**
- A connected `RedisClient` pointing at `TEST_REDIS_URL` (DB 15 by default)
- Flushes the test DB before and after each test
- **Skips** if the `redis` package is missing or the server is unreachable

**Important**: `redis_client` and `auth_with_cache` call `FLUSHDB`. Never point `TEST_REDIS_URL` at a shared or production Redis database.

### User & Data Fixtures

**`test_password`** - `"TestPass123!"` (meets all policy requirements)
**`test_user`** - ACTIVE, non-superuser, `test@example.com`
**`test_admin`** - admin user
**`test_role`** - a `test_role` / "Test Role" with `is_system_role=False`
**`test_permissions`** - pre-created permissions
**`sample_user_data`** / **`invalid_user_data`** - request payloads for validation tests

### Token Fixtures

**`test_access_token`** - a valid 15-minute access token for `test_user`
**`test_expired_token`** - an already-expired access token

---

## Test Requirements

### Required
- **PostgreSQL** - reachable at `TEST_DATABASE_URL`, which defaults to
  `postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test`
- **Python 3.12+**
- **pytest**, **pytest-asyncio**

The test user needs `CREATE SCHEMA` rights - `test_engine` creates and drops a schema per test.

### Optional
- **Redis** - `TEST_REDIS_URL`, defaults to `redis://localhost:6379/15`
  - Without Redis, tests using `redis_client` / `auth_with_cache` **skip**; the rest of the suite runs

### Environment

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test"
export TEST_REDIS_URL="redis://localhost:6379/15"
```

```bash
# Start services locally
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
docker run -d -p 6379:6379 redis:7

# Create the test database
createdb -h localhost -U postgres outlabs_auth_test
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: outlabs_auth_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports:
          - 6379:6379

    env:
      TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test
      TEST_REDIS_URL: redis://localhost:6379/15

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: uv sync --extra test

      - name: Run tests with coverage
        run: uv run pytest --cov=outlabs_auth --cov-report=xml --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

---

## Writing New Tests

### Test Naming Convention

```python
# ✅ GOOD: Clear, descriptive names
async def test_login_with_active_user_returns_tokens()
async def test_suspended_user_cannot_authenticate()
async def test_logout_revokes_refresh_token()

# ❌ BAD: Vague names
async def test_login()
async def test_user()
async def test_token()
```

### Test Structure

```python
@pytest.mark.asyncio
async def test_feature_name(auth, test_user, test_password):
    """
    Brief description of what this test verifies.

    Include mode/configuration if relevant.
    """
    # 1. Arrange
    async with auth.get_session() as session:

        # 2. Act
        user, tokens = await auth.auth_service.login(
            session,
            email=test_user.email,
            password=test_password,
        )

        # 3. Assert
        assert tokens.access_token is not None
```

Note that the services take an `AsyncSession` as their first argument - get one
from `auth.get_session()` or the `test_session` fixture.

### Asserting on Persisted State

```python
from sqlmodel import select

from outlabs_auth.models.sql.token import RefreshToken

result = await session.execute(
    select(RefreshToken).where(RefreshToken.user_id == test_user.id)
)
token_row = result.scalar_one()
assert token_row.is_revoked is True
```

---

## Common Issues

### PostgreSQL Connection Errors

```bash
# Error: connection refused on localhost:5432
# Solution: start PostgreSQL and create the test database
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
createdb -h localhost -U postgres outlabs_auth_test
```

### Permission Denied Creating Schema

`test_engine` creates a schema per test. Grant the test role `CREATE` on the
test database, or use a superuser role locally.

### Redis Tests Skipped

```bash
# Skipped: Redis not reachable
# Solution: start Redis (optional — most tests run without it)
docker run -d -p 6379:6379 redis:7
```

### Timezone Issues

```python
# ✅ ALWAYS use timezone-aware datetimes
from datetime import datetime, timezone
now = datetime.now(timezone.utc)

# ❌ NEVER use naive datetimes
now = datetime.now()     # BAD
now = datetime.utcnow()  # DEPRECATED in Python 3.12
```

### Async Test Issues

```python
# ✅ CORRECT: Use @pytest.mark.asyncio
@pytest.mark.asyncio
async def test_example():
    result = await some_async_function()
    assert result is not None

# ❌ WRONG: Forget @pytest.mark.asyncio
async def test_example():  # Will fail!
    result = await some_async_function()
```

---

## Test Maintenance

### When to Update Tests

1. **After code changes**: Verify tests still pass
2. **After bug fixes**: Add regression tests
3. **After feature additions**: Add tests for new functionality
4. **After refactoring**: Ensure behavior unchanged

### Keeping Tests Fast

- Use function-scoped fixtures (isolation)
- Avoid unnecessary database writes
- Use mocks for external services (see `test_activity_tracker.py` for a mocked-Redis example)
- Prefer asserting on call shape over wall-clock timings — timing assertions are flaky on shared CI

### Test Data Cleanup

Tests clean up automatically:
- The per-test PostgreSQL schema is dropped (CASCADE) by `test_engine`
- The Redis test DB is flushed before and after by `redis_client`

No manual cleanup required.

---

## Related Documentation

- **DD-048**: User Status System design
- **DD-049**: Activity Tracking design
- **12-Data-Models.md**: Model and schema reference
- **22-JWT-Tokens.md**: JWT token architecture

---

## Summary

✅ **80 unit + 56 integration test files** covering authentication, authorization, tokens, RBAC, entities, API keys, OAuth, and observability

✅ **Real-database testing** with per-test schema isolation on PostgreSQL

✅ **Graceful degradation** — Redis-dependent tests skip automatically when Redis is unavailable

✅ **Coverage** of happy paths, error scenarios, query budgets, and security behavior
