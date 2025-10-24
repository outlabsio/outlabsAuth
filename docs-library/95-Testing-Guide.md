# DD-095: Testing Guide

**Status**: Complete
**Created**: 2025-01-24
**Related**: DD-048 (User Status), DD-049 (Activity Tracking)

## Overview

OutlabsAuth has a comprehensive test suite covering authentication, authorization, token management, and user status workflows. Tests are organized by feature and include both unit and integration tests.

---

## Test Structure

```
tests/
├── integration/
│   └── login_logout/
│       ├── conftest.py                    # Shared fixtures
│       ├── test_user_status.py            # User status system (28 tests)
│       ├── test_logout_standard.py        # Standard logout (11 tests)
│       ├── test_logout_stateless.py       # Stateless mode (10 tests)
│       ├── test_token_cleanup.py          # Token cleanup worker (23 tests)
│       └── test_immediate_logout.py       # Redis blacklisting (15 tests)
└── unit/
    └── services/
        └── ...                            # Unit tests for services
```

**Total: 87+ tests** covering login/logout functionality

---

## Running Tests

### All Tests
```bash
# Run entire test suite
pytest

# Run with coverage
pytest --cov=outlabs_auth --cov-report=html
```

### Specific Test Files
```bash
# User status tests
pytest tests/integration/login_logout/test_user_status.py -v

# Token cleanup tests
pytest tests/integration/login_logout/test_token_cleanup.py -v

# Immediate logout (requires Redis)
pytest tests/integration/login_logout/test_immediate_logout.py -v
```

### By Feature
```bash
# All login/logout tests
pytest tests/integration/login_logout/ -v

# All unit tests
pytest tests/unit/ -v
```

---

## Test Coverage

### 1. User Status System (28 tests)

**File**: `test_user_status.py`

Tests all user status workflows and authentication blocking:

#### ACTIVE Status (4 tests)
- Can authenticate normally
- Receives access + refresh tokens
- Both tokens work correctly
- Can refresh access token

#### SUSPENDED Status (6 tests)
- Cannot authenticate (blocked)
- Error message shows status
- Optional expiry date (suspended_until)
- Auto-unsuspend after expiry passes
- Error includes suspension details

#### BANNED Status (4 tests)
- Cannot authenticate (permanently blocked)
- Clear error message
- No auto-expiry (manual intervention required)

#### DELETED Status (4 tests)
- Cannot authenticate (soft delete)
- Preserves data for recovery
- Error shows deleted status
- Includes deleted_at timestamp

#### LOCKED Status (5 tests)
- Account locked after max failed login attempts
- Temporary lockout (30 minutes default)
- Auto-unlock after lockout period
- ACTIVE status but temporarily blocked
- Error message shows unlock time

#### Multiple Users (5 tests)
- Different users, different statuses work independently
- Status transitions don't affect other users
- Concurrent authentication checks

**Key Features Tested**:
- ✅ All 4 status types (ACTIVE, SUSPENDED, BANNED, DELETED)
- ✅ Account lockout (failed login attempts)
- ✅ Status-specific error messages
- ✅ Suspended_until auto-expiry
- ✅ Deleted_at soft delete tracking

---

### 2. Standard Logout (11 tests)

**File**: `test_logout_standard.py`

**Mode**: MongoDB token storage (default)
**Security Window**: 15 minutes (access token lifetime)

#### Token Revocation (5 tests)
- Login returns access + refresh tokens
- Logout revokes refresh token in MongoDB
- Access token still works (15-min window)
- Refresh token fails after logout
- Already-revoked token handling

#### Multi-Device Support (3 tests)
- Multiple sessions per user
- Each session has unique tokens
- Logout revokes one session only
- Other sessions remain active

#### Error Scenarios (3 tests)
- Invalid refresh token
- Token not found
- Already revoked token

**Key Features Tested**:
- ✅ Refresh token revocation in MongoDB
- ✅ 15-minute access token window
- ✅ Multi-device session management
- ✅ Graceful error handling

---

### 3. Stateless Logout (10 tests)

**File**: `test_logout_stateless.py`

**Mode**: No token storage (stateless JWT)
**Tradeoff**: Cannot revoke tokens until expiry

#### Stateless Behavior (4 tests)
- No tokens stored in MongoDB
- Logout returns False (can't revoke)
- Access token works after logout
- Refresh token works after logout

#### Security Tradeoffs (3 tests)
- Documents 30-day security window
- Both tokens valid until expiry
- Clear error messages about tradeoffs

#### Multiple Sessions (3 tests)
- All sessions independent
- No database writes for tokens
- Performance benefits of stateless mode

**Key Features Tested**:
- ✅ Stateless JWT mode (no storage)
- ✅ Cannot revoke tokens (documented tradeoff)
- ✅ Performance characteristics
- ✅ Security considerations

---

### 4. Token Cleanup (23 tests)

**File**: `test_token_cleanup.py`

**Purpose**: Background worker to clean up expired/old tokens

#### Expired Token Cleanup (4 tests)
- Deletes tokens past expires_at
- Keeps valid tokens
- Handles multiple expired tokens
- Edge case: just expired (1 second ago)

#### Revoked Token Cleanup (4 tests)
- Deletes old revoked tokens (>7 days)
- Keeps recent revoked tokens (<7 days)
- Custom retention periods (2, 5, 7 days)
- Exact cutoff boundary handling

#### Mixed Scenarios (3 tests)
- Deletes both expired AND old revoked
- Correctly filters (delete some, keep others)
- Accurate statistics reporting

#### OAuth State Cleanup (3 tests)
- Deletes expired OAuth states (>1 hour)
- Keeps recent OAuth states
- Graceful handling if OAuth not installed

#### Performance Tests (3 tests)
- Large batch (500 tokens in <5 seconds)
- Idempotent (safe to run multiple times)
- Preserves user data (only deletes tokens)

#### Edge Cases (6 tests)
- Empty database returns zeros
- Only valid tokens returns zero deleted
- Timezone-naive datetime handling
- Statistics accuracy
- cleanup_all() runs all tasks

**Key Features Tested**:
- ✅ Expired token cleanup
- ✅ Old revoked token cleanup (7-day retention)
- ✅ OAuth state cleanup
- ✅ Custom retention periods
- ✅ Performance with large datasets
- ✅ Accurate statistics reporting

---

### 5. Immediate Logout (15 tests)

**File**: `test_immediate_logout.py`

**Mode**: High security (MongoDB + Redis blacklist)
**Security**: Immediate access token revocation

#### Immediate Revocation (4 tests)
- Access token blacklisted in Redis
- Access token rejected immediately
- Refresh token also revoked
- TTL matches access token lifetime

#### Multi-Device (2 tests)
- Each session blacklisted independently
- Other sessions unaffected by logout

#### Stateless + Redis Mode (2 tests)
- No token storage but blacklisting works
- Access token revoked, refresh still works (tradeoff)

#### Edge Cases (4 tests)
- Logout without JTI doesn't blacklist
- Graceful degradation if Redis unavailable
- Already-blacklisted tokens rejected
- Different users independent

#### Performance Tests (2 tests)
- Blacklist 10 tokens in <1 second
- Auth check with blacklist <50ms

#### Advanced (1 test)
- TTL auto-expiry after token lifetime

**Key Features Tested**:
- ✅ Redis JTI blacklisting
- ✅ Immediate access token revocation
- ✅ TTL management (auto-expire)
- ✅ Multi-device independence
- ✅ Stateless + Redis hybrid mode
- ✅ Graceful degradation without Redis
- ✅ Performance benchmarks

**Note**: 13 tests require Redis and skip if unavailable

---

## Test Fixtures

### Database Fixtures

**`mongo_db`** (function-scoped)
- Fresh MongoDB database per test
- Auto-cleanup after test completes
- Isolation between tests

### Auth Instance Fixtures

**`auth_standard`**
- Mode: Standard (MongoDB token storage)
- store_refresh_tokens=True
- enable_token_blacklist=False
- Result: 15-min security window

**`auth_high_security`**
- Mode: High security (MongoDB + Redis)
- store_refresh_tokens=True
- enable_token_blacklist=True
- Result: Immediate revocation
- Skips if Redis unavailable

**`auth_stateless`**
- Mode: Stateless JWT (no storage)
- store_refresh_tokens=False
- enable_token_blacklist=False
- Result: Cannot revoke tokens

**`auth_redis_only`**
- Mode: Redis-only (stateless + blacklist)
- store_refresh_tokens=False
- enable_token_blacklist=True
- Result: Stateless + access token blacklisting
- Skips if Redis unavailable

**`auth_with_cleanup`**
- Mode: Standard with token cleanup enabled
- enable_token_cleanup=True
- token_cleanup_interval_hours=1

### User Fixtures

**`active_user`** - ACTIVE status, can authenticate
**`suspended_user`** - SUSPENDED status, blocked
**`suspended_user_with_expiry`** - SUSPENDED with auto-expiry
**`banned_user`** - BANNED status, permanently blocked
**`deleted_user`** - DELETED status (soft delete)
**`locked_user`** - ACTIVE but temporarily locked (failed attempts)

### Token Fixtures

**`user_with_tokens`** - Active user with valid access + refresh tokens
**`expired_refresh_token`** - Token expired 1 day ago
**`old_revoked_token`** - Revoked 8 days ago (should be cleaned up)
**`recent_revoked_token`** - Revoked 2 days ago (should be kept)

---

## Test Requirements

### Required
- **MongoDB**: Running on `localhost:27017`
- **Python 3.12+**
- **pytest**, **pytest-asyncio**

### Optional (for full test coverage)
- **Redis**: Running on `localhost:6379` (for blacklist tests)
  - Without Redis: 13 tests in `test_immediate_logout.py` are skipped
  - All other tests pass without Redis

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
      mongodb:
        image: mongo:7
        ports:
          - 27017:27017

      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests with coverage
        run: |
          pytest --cov=outlabs_auth --cov-report=xml --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v3
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
async def test_logout_revokes_refresh_token_in_mongodb()

# ❌ BAD: Vague names
async def test_login()
async def test_user()
async def test_token()
```

### Test Structure

```python
@pytest.mark.asyncio
async def test_feature_name(fixture1, fixture2):
    """
    Brief description of what this test verifies.

    Include mode/configuration if relevant.
    """
    # 1. Setup - create test data
    user, tokens = await auth.auth_service.login(...)

    # 2. Action - perform the operation being tested
    result = await auth.auth_service.logout(tokens.refresh_token)

    # 3. Assert - verify expected behavior
    assert result is True

    # 4. Additional verifications
    token_model = await RefreshTokenModel.find_one(...)
    assert token_model.is_revoked is True
```

### Using Fixtures

```python
@pytest.mark.asyncio
async def test_example(auth_standard, active_user, password):
    """Example using common fixtures."""
    # auth_standard: OutlabsAuth instance (standard mode)
    # active_user: UserModel with ACTIVE status
    # password: "Password123!" (standard test password)

    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    assert tokens.access_token is not None
```

---

## Test Coverage Goals

### Current Coverage
- **User Status System**: 100% (all 4 statuses + locked)
- **Standard Logout**: 100% (MongoDB revocation)
- **Stateless Logout**: 100% (cannot revoke)
- **Token Cleanup**: 100% (expired + revoked + OAuth)
- **Immediate Logout**: 100% (Redis blacklisting)

### Target Coverage
- **Overall**: 90%+ code coverage
- **Critical paths**: 100% (authentication, authorization)
- **Error handling**: 100% (all exception paths)
- **Edge cases**: 100% (boundary conditions, race conditions)

---

## Common Issues

### MongoDB Connection Errors

```bash
# Error: ConnectionError: localhost:27017
# Solution: Start MongoDB
docker run -d -p 27017:27017 mongo:7
```

### Redis Tests Skipped

```bash
# Skipped: Redis not available for high security testing
# Solution: Start Redis (optional, most tests work without it)
docker run -d -p 6379:6379 redis:7
```

### Timezone Issues

```python
# ✅ ALWAYS use timezone-aware datetimes
from datetime import datetime, timezone
now = datetime.now(timezone.utc)

# ❌ NEVER use naive datetimes
now = datetime.now()  # BAD
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
- Use mocks for external services
- Parallel test execution where possible

### Test Data Cleanup

Tests automatically clean up:
- MongoDB databases (function-scoped)
- Redis keys (via fixtures)
- Temporary files

No manual cleanup required.

---

## Related Documentation

- **DD-048**: User Status System design
- **DD-049**: Activity Tracking design (tests pending)
- **74-Auth-Service.md**: AuthService API reference
- **22-JWT-Tokens.md**: JWT token architecture

---

## Summary

✅ **87+ comprehensive tests** covering:
- User status workflows (ACTIVE, SUSPENDED, BANNED, DELETED)
- Standard logout (MongoDB revocation)
- Stateless mode (cannot revoke)
- Token cleanup worker (expired + old revoked)
- Immediate logout (Redis blacklisting)

✅ **Multiple test configurations**:
- Standard mode (MongoDB storage)
- High security mode (MongoDB + Redis)
- Stateless mode (no storage)
- Redis-only mode (stateless + blacklist)

✅ **Comprehensive coverage**:
- Happy paths (normal flows)
- Error scenarios (edge cases)
- Performance tests (large datasets)
- Security tests (blacklisting, revocation)

**Next**: Activity Tracking tests (DD-049 implementation)
