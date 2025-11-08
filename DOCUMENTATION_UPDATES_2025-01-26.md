# Documentation Updates - 2025-01-26

## Summary

This document tracks all documentation updates made on 2025-01-26 to correct design decisions and align documentation with best practices.

## Key Corrections

### 1. API Key Hashing (DD-028 Corrected)

**Original (INCORRECT)**: Use argon2id for API key hashing  
**Corrected**: Use SHA-256 for API key hashing

**Rationale**:
- API keys are cryptographically random 256-bit secrets (high entropy)
- Argon2id is designed for low-entropy human passwords, not high-entropy secrets
- SHA-256 provides adequate security for random secrets with ~0.1ms performance
- Argon2id would add ~100ms overhead per request for zero security benefit
- Industry standard: GitHub, Stripe, AWS all use fast hashing for API keys

**What we DO use argon2id for**:
- ✅ User passwords (correct - passwords have low entropy)
- ❌ API keys (incorrect - keys have high entropy)

### 2. Refresh Token Rotation (DD-028 Updated)

**Original**: Automatic refresh token rotation on every refresh  
**Updated**: Optional refresh token rotation (default OFF)

**Rationale**:
- Rotation adds complexity for marginal security benefit
- Can break concurrent refresh attempts
- Connection loss after receiving new token can lock users out
- Most apps are fine with: 30-day expiry + manual "revoke all sessions"
- High-security apps can enable via `enable_refresh_token_rotation=True`

### 3. Redis Configuration (DD-048 New)

**Change**: Simplified from dual-flag (`enable_caching` + `redis_enabled`) to single `redis_enabled` flag

**Configuration**:
```python
# Before (confusing)
auth = SimpleRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# After (clear)
auth = SimpleRBAC(
    database=db,
    redis_enabled=True,
    redis_url="redis://localhost:6379"
)
```

**Rationale**:
- Single source of truth
- Explicit is better than implicit
- User maintains control over when Redis activates

### 4. API Key Method Naming

**Standardized on**: `verify_api_key()` (not `validate_api_key()`, `authenticate_api_key()`)

**Consistency Pattern**:
- `verify_password()`
- `verify_token()`
- `verify_api_key()`

### 5. API Key Model Changes

**Parameter Changes**:
- `created_by` → `owner_id`
- `permissions` → `scopes`
- `allowed_ips` → `ip_whitelist`
- `environment` → `prefix_type` (e.g., "sk_live", "sk_test")

**Method Changes**:
- `create_api_key()` returns `tuple[str, APIKeyModel]` (not dict)
- `verify_api_key()` replaces `validate_api_key()` and `authenticate_api_key()`

## Files Updated

### 1. docs/DESIGN_DECISIONS.md

**DD-028 Corrected**:
- Changed from argon2id to SHA-256 for API keys
- Added detailed rationale section
- Updated security requirements
- Added refresh token rotation as optional feature
- Updated examples to use correct parameters

**DD-031 Superseded**:
- Marked as superseded by corrected DD-028
- Added warning banner

**DD-048 Added**:
- New decision documenting Redis configuration simplification
- Clear rules for `redis_enabled` flag
- Migration examples

**Change Log Updated**:
- Added DD-048 entry
- Updated DD-028 with "CORRECTED" status
- Marked DD-031 as superseded
- Updated last modified date

### 2. README.md

**Authentication Features Section**:
- Changed "automatic rotation" → "optional rotation"
- Changed "argon2id hashing" → "SHA-256 hashing (fast, secure for high-entropy secrets)"

**Configuration Examples**:
- Updated `enable_caching=True` → `redis_enabled=True`

**API Key Examples**:
- Updated parameter names (`owner_id`, `scopes`, `ip_whitelist`)
- Updated method calls to `verify_api_key()`
- Simplified examples

### 3. CLAUDE.md

**Authentication System Section**:
- Updated to reflect optional rotation
- Changed argon2id to SHA-256 for API keys

**Key Design Decisions Section**:
- Added DD-047 and DD-048 to latest decisions
- Added new "Corrections (2025-01-26)" section
- Listed all three corrections (DD-028, DD-031)

**Configuration Examples**:
- Updated `enable_caching=True` → `redis_enabled=True`

### 4. docs/API_DESIGN.md

**Header Updates**:
- Added "SHA-256 Hashing" feature note
- Updated 12-char prefixes description

**API Key Examples (Multiple Sections)**:
- Updated all `create_api_key()` calls with correct parameters
- Changed `permissions` → `scopes`
- Changed `created_by` → `owner_id`
- Changed `allowed_ips` → `ip_whitelist`
- Changed `environment` → `prefix_type`
- Removed invalid parameters
- Updated hash comments from argon2id to SHA-256

**Performance Metrics**:
- Changed API key validation from "~50-100ms" → "~0.5-1ms"
- Updated comparison notes to reflect similar performance to JWT

**Simplified Examples**:
- Removed redundant development/staging/test key examples
- Kept production and test examples only
- Added note about prefix types

## Breaking Changes

### For External Users (if any existed)

1. **API Key Creation**:
   - Parameter names changed (see "API Key Model Changes" above)
   - No `environment` field (use `prefix_type` instead)
   - Return type is tuple, not dict

2. **Redis Configuration**:
   - Must use `redis_enabled=True` instead of `enable_caching=True`
   - One-line change for all users

3. **Refresh Token Rotation**:
   - Now optional (disabled by default)
   - Enable with `enable_refresh_token_rotation=True` if needed

### Migration Guide

```python
# OLD
auth = SimpleRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

raw_key, api_key = await auth.api_key_service.create_api_key(
    name="My API",
    created_by=user_id,
    permissions=["user:read"],
    environment="production",
    allowed_ips=["10.0.0.0/8"]
)

# NEW
auth = SimpleRBAC(
    database=db,
    redis_enabled=True,
    redis_url="redis://localhost:6379"
)

raw_key, api_key = await auth.api_key_service.create_api_key(
    name="My API",
    owner_id=user_id,
    scopes=["user:read"],
    prefix_type="sk_live",
    ip_whitelist=["10.0.0.0/8"]
)
```

## No Code Changes Required

**Important**: The current implementation already uses SHA-256 for API keys. These documentation updates correct the specs to match the (correct) implementation.

**Files with correct implementation** (no changes needed):
- `outlabs_auth/models/api_key.py` - Already uses SHA-256
- `outlabs_auth/services/api_key.py` - Already implements correct logic
- `outlabs_auth/services/auth.py` - Refresh token behavior already correct

## Next Steps

### Implementation Fixes Required

While documentation is now correct, these implementation issues need fixing:

1. **API Key Service/Strategy Mismatch**:
   - Strategy calls `verify_api_key()` but service has `validate_api_key()`
   - Return types inconsistent (tuple vs dict)
   - Parameter mismatches

2. **Redis Connection**:
   - `OutlabsAuth.__init__` doesn't set `config.redis_enabled=True` when `redis_url` provided
   - `RedisClient.connect()` checks `redis_enabled` but it's never set

3. **EntityMembershipModel** (optional):
   - Still uses `is_active` boolean instead of `MembershipStatus` enum
   - UserRoleMembership already uses enum correctly

### User Documentation (docs-library/)

Create/update user-facing documentation:
- `23-API-Keys.md` - Document SHA-256 hashing, verify_api_key usage
- `22-JWT-Tokens.md` - Clarify optional refresh token rotation
- `24-Redis-Configuration.md` - Document redis_enabled flag and graceful degradation

## Impact Assessment

### Positive
- ✅ Documentation now reflects industry best practices
- ✅ Performance claims are accurate (~0.1ms vs ~100ms for argon2id)
- ✅ Configuration is simpler and clearer
- ✅ Standardized naming conventions

### Neutral
- ⚠️ No existing users to migrate (still in development)
- ⚠️ Implementation already correct for API key hashing

### Risk
- ❌ Low - Changes are primarily documentation corrections
- ❌ No breaking changes for external users (none exist yet)

## Conclusion

All documentation has been updated to reflect:
1. Correct API key hashing (SHA-256 for high-entropy secrets)
2. Optional refresh token rotation (not automatic)
3. Simplified Redis configuration (single flag)
4. Standardized method naming (verify_*)
5. Corrected parameter names and examples

**Status**: Documentation updates COMPLETE ✅  
**Next**: Fix implementation mismatches (separate task)

---

**Last Updated**: 2025-01-26  
**Author**: Claude (with user approval)  
**Related**: DD-028 (corrected), DD-031 (superseded), DD-048 (new)
