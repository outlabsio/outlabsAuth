# Login/Logout Test Suite

Comprehensive test coverage for the OutlabsAuth login/logout system.

## ✅ Completed

### 1. User Status Tests (`test_user_status.py`) - **COMPLETE**

**30+ tests covering**:
- ✅ ACTIVE user login, refresh, get_current_user
- ✅ SUSPENDED user (cannot login, specific error messages)
- ✅ SUSPENDED with expiry date (shows suspension end time)
- ✅ BANNED user (cannot login, permanent block)
- ✅ DELETED user (cannot login, soft delete)
- ✅ Locked user (too many failed attempts)
- ✅ Failed attempt counter increments
- ✅ Successful login resets counter
- ✅ Max attempts locks account
- ✅ can_authenticate() method for all statuses
- ✅ Status transitions (reactivation, recovery)
- ✅ Status checked before password (security)
- ✅ Status change invalidates tokens
- ✅ Multiple users with different statuses

**Run tests**:
```bash
pytest tests/integration/login_logout/test_user_status.py -v
```

---

## 📝 Remaining Tests (To Be Written)

### 2. Standard Logout Tests (`test_logout_standard.py`) - **TODO**

**Configuration**: `store_refresh_tokens=True`, `enable_token_blacklist=False`

**Tests needed**:
- Login → tokens returned
- Logout → refresh token revoked in MongoDB
- Use access token after logout → works for 15 min (security window)
- Use refresh token after logout → fails immediately
- Logout all devices → all refresh tokens revoked
- Multiple sessions → logout one device, others still work

---

### 3. High Security Logout Tests (`test_logout_high_security.py`) - **TODO**

**Configuration**: `store_refresh_tokens=True`, `enable_token_blacklist=True`, Redis required

**Tests needed**:
- Login → tokens returned
- Logout with `immediate=true` → access token blacklisted in Redis
- Use access token after immediate logout → fails immediately
- Use refresh token after logout → fails immediately
- JTI included in JWT payload
- Logout without Redis → graceful degradation to standard mode

---

### 4. Stateless Logout Tests (`test_logout_stateless.py`) - **TODO**

**Configuration**: `store_refresh_tokens=False`, `enable_token_blacklist=False`

**Tests needed**:
- Login → tokens returned
- Logout → returns success but cannot revoke
- Refresh tokens NOT stored in MongoDB
- Access token works until expiration (cannot revoke)
- Refresh token works until expiration (cannot revoke)

---

### 5. Redis-Only Logout Tests (`test_logout_redis_only.py`) - **TODO**

**Configuration**: `store_refresh_tokens=False`, `enable_token_blacklist=True`, Redis required

**Tests needed**:
- Login → tokens returned
- Logout with `immediate=true` → access token blacklisted
- Refresh tokens NOT stored in MongoDB
- Access token revocation works (via Redis)
- Refresh token cannot be revoked (stateless)

---

### 6. Token Cleanup Tests (`test_token_cleanup.py`) - **TODO**

**Tests needed**:
- Create expired tokens → run cleanup → verify deleted
- Create old revoked tokens (>7 days) → run cleanup → verify deleted
- Create recent revoked tokens (<7 days) → run cleanup → verify kept
- Scheduler starts when `enable_token_cleanup=True`
- Scheduler doesn't start when `enable_token_cleanup=False`
- Scheduler task cancelled on `auth.shutdown()`
- Cleanup interval configurable via `token_cleanup_interval_hours`
- Manual cleanup via `cleanup_expired_refresh_tokens()`

---

### 7. Redis Degradation Tests (`test_redis_degradation.py`) - **TODO**

**Tests needed**:
- Config with `enable_token_blacklist=True` but Redis down → graceful fallback
- JWTStrategy with Redis down → skips blacklist check
- Logout with Redis down → still revokes refresh token (MongoDB)
- Redis reconnection after failure

---

### 8. Immediate Logout Tests (`test_immediate_logout.py`) - **TODO**

**Tests needed**:
- Logout with `immediate=false` (default) → 15-min window
- Logout with `immediate=true` + Redis → blacklisted immediately
- Logout with `immediate=true` without Redis → graceful degradation
- JTI claim included in access tokens
- Blacklist TTL matches token expiration
- Blacklist key format: `blacklist:jwt:{jti}`

---

## 🏃 Running Tests

### Run all login/logout tests:
```bash
pytest tests/integration/login_logout/ -v
```

### Run specific test file:
```bash
pytest tests/integration/login_logout/test_user_status.py -v
```

### Run with coverage:
```bash
pytest tests/integration/login_logout/ --cov=outlabs_auth.services.auth --cov=outlabs_auth.models.user --cov-report=html
```

### Run tests requiring Redis (skip if Redis unavailable):
```bash
pytest tests/integration/login_logout/ -v -m "not redis"  # Skip Redis tests
pytest tests/integration/login_logout/test_logout_high_security.py -v  # Run only Redis tests
```

---

## 📊 Test Coverage Goals

| Component | Current | Target |
|-----------|---------|--------|
| `auth_service.py` (login/logout) | TBD | 90%+ |
| `user.py` (UserModel, statuses) | ~80% | 95%+ |
| `strategy.py` (JWTStrategy) | TBD | 85%+ |
| `token.py` (RefreshTokenModel) | TBD | 90%+ |
| `token_cleanup.py` | 0% | 90%+ |

---

## 🔧 Prerequisites

### MongoDB
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### Redis (optional, for high security/Redis-only tests)
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

Tests will automatically skip Redis-dependent tests if Redis is unavailable.

---

## 📝 Test Fixtures

See `conftest.py` for available fixtures:

**Auth Instances**:
- `auth_standard` - Standard config (MongoDB only)
- `auth_high_security` - High security (MongoDB + Redis blacklist)
- `auth_stateless` - Stateless JWT (no storage)
- `auth_redis_only` - Redis blacklist only (no MongoDB tokens)
- `auth_with_cleanup` - With token cleanup scheduler enabled

**Users**:
- `active_user` - ACTIVE status
- `suspended_user` - SUSPENDED status
- `suspended_user_with_expiry` - SUSPENDED with auto-expiry
- `banned_user` - BANNED status
- `deleted_user` - DELETED status (soft delete)
- `locked_user` - ACTIVE but locked (failed attempts)

**Tokens**:
- `user_with_tokens` - User + access/refresh tokens
- `expired_refresh_token` - Expired token for cleanup tests
- `old_revoked_token` - Revoked >7 days ago
- `recent_revoked_token` - Revoked <7 days ago

---

## 🎯 Next Steps

1. **Write remaining test files** (7 files, ~150 tests total)
2. **Run full test suite** with coverage report
3. **Update documentation** to reference new user status system
4. **Commit changes** with organized commit messages

---

**Status**: User status tests complete (30+ tests), remaining tests TODO
**Last Updated**: 2025-01-24
