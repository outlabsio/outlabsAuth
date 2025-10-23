# 73-API-Key-Service.md - ApiKeyService API Reference

Complete API reference for the **ApiKeyService** - API key management with Redis counter pattern.

---

## Table of Contents

1. [Overview](#overview)
2. [Accessing ApiKeyService](#accessing-apikeyservice)
3. [API Key Creation](#api-key-creation)
4. [API Key Validation](#api-key-validation)
5. [API Key Management](#api-key-management)
6. [Rate Limiting](#rate-limiting)
7. [Redis Counter Pattern](#redis-counter-pattern)
8. [Security Features](#security-features)
9. [Error Handling](#error-handling)
10. [Complete Examples](#complete-examples)

---

## Overview

**ApiKeyService** handles API key authentication with high-performance Redis counter pattern for usage tracking.

### Features

- ✅ Secure API key generation with prefixes
- ✅ argon2id-equivalent SHA256 key hashing
- ✅ **Redis counter pattern** (99% fewer DB writes)
- ✅ Rate limiting (per minute/hour/day)
- ✅ Scoped permissions
- ✅ IP whitelisting
- ✅ Entity-scoped access (EnterpriseRBAC)
- ✅ Expiration support
- ✅ Background sync to MongoDB

### Key Components

```python
class APIKeyModel:
    # Key Information
    name: str              # Human-readable name
    prefix: str            # First 12 chars (e.g., "sk_live_abc1")
    key_hash: str          # SHA256 hash (never store plain key)

    # Ownership
    owner: UserModel       # Key owner

    # Status
    status: APIKeyStatus   # ACTIVE, SUSPENDED, REVOKED, EXPIRED
    expires_at: datetime   # Expiration date (None = never)
    last_used_at: datetime # Last usage timestamp

    # Usage Tracking
    usage_count: int       # Total uses (synced from Redis)

    # Rate Limiting
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    rate_limit_per_day: int

    # Permissions
    scopes: list[str]      # Allowed permissions
    entity_ids: list[str]  # Restrict to entities

    # Security
    ip_whitelist: list[str]  # Allowed IPs
```

### API Key Format

```
sk_live_abc123def456ghi789jkl012mno345pqr678
│      │
│      └─ Random 64-char hex string (32 bytes)
└──────── Prefix type (sk_live, sk_test)

Prefix (first 12 chars): sk_live_abc1  ← Used for identification
Full key: sk_live_abc123def456...      ← Only shown once at creation
Hash: SHA256(full_key)                 ← Stored in database
```

---

## Accessing ApiKeyService

### Enable API Keys

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database=db,
    secret_key="...",
    enable_api_keys=True,              # Enable API keys
    api_key_default_expiry_days=90,    # Default expiration
)
await auth.initialize()

# Access ApiKeyService
api_key_service = auth.api_key_service
```

### With Redis (Recommended)

```python
auth = SimpleRBAC(
    database=db,
    secret_key="...",
    enable_api_keys=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"  # Redis for counter pattern
)
```

---

## API Key Creation

### create_api_key()

Create a new API key.

```python
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Production API Key",
    scopes=["user:read", "entity:read"],
    rate_limit_per_minute=60,
    expires_in_days=90
)

print(f"API Key: {key}")  # ONLY TIME THIS IS SHOWN!
print(f"Prefix: {model.prefix}")
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `owner_id` | `str` | ✅ Yes | - | User ID who owns the key |
| `name` | `str` | ✅ Yes | - | Human-readable key name |
| `scopes` | `list[str]` | ❌ No | `[]` | Allowed permissions (empty = all) |
| `rate_limit_per_minute` | `int` | ❌ No | `60` | Max requests per minute |
| `rate_limit_per_hour` | `int` | ❌ No | `None` | Max requests per hour |
| `rate_limit_per_day` | `int` | ❌ No | `None` | Max requests per day |
| `entity_ids` | `list[str]` | ❌ No | `None` | Restrict to entities (None = all) |
| `ip_whitelist` | `list[str]` | ❌ No | `None` | Allowed IPs (None = all) |
| `expires_in_days` | `int` | ❌ No | `None` | Days until expiration (None = never) |
| `description` | `str` | ❌ No | `None` | Key description |
| `metadata` | `dict` | ❌ No | `{}` | Additional metadata |
| `prefix_type` | `str` | ❌ No | `"sk_live"` | Key prefix (sk_live, sk_test) |

**Returns:** `tuple[str, APIKeyModel]` - (full_api_key, api_key_model)

**⚠️ WARNING:** The full API key is **only returned once**. Store it securely!

**Raises:**
- `UserNotFoundError` - Owner doesn't exist

**Example:**

```python
# Create basic API key
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Production Key"
)

# Store the key securely (e.g., return to user)
return {
    "api_key": key,  # Only shown once!
    "prefix": model.prefix,
    "created_at": model.created_at.isoformat()
}

# Create scoped API key
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Read-Only Key",
    scopes=["user:read", "entity:read"],
    description="Read-only access for analytics"
)

# Create rate-limited key
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Rate Limited Key",
    rate_limit_per_minute=100,
    rate_limit_per_hour=5000,
    rate_limit_per_day=50000
)

# Create entity-scoped key (EnterpriseRBAC)
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Engineering Department Key",
    entity_ids=[str(engineering_dept.id)],
    scopes=["project:read", "task:update"]
)

# Create IP-whitelisted key
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Office IP Key",
    ip_whitelist=["192.168.1.100", "192.168.1.101"]
)

# Create test key
test_key, test_model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Test Environment Key",
    prefix_type="sk_test"
)
```

---

## API Key Validation

### validate_api_key()

Validate API key and track usage (**core authentication method**).

```python
api_key, usage = await auth.api_key_service.validate_api_key(
    api_key_string="sk_live_abc123...",
    required_scope="user:read",      # Optional
    entity_id=str(entity.id),        # Optional (EnterpriseRBAC)
    ip_address=request.client.host   # Optional
)

if not api_key:
    raise HTTPException(status_code=401, detail="Invalid API key")
```

**Parameters:**
- `api_key_string` (str): Full API key string
- `required_scope` (str, optional): Required permission
- `entity_id` (str, optional): Entity ID for access check
- `ip_address` (str, optional): Client IP for whitelist check

**Returns:** `tuple[Optional[APIKeyModel], int]` - (api_key, current_usage)
- `api_key`: Valid API key model or `None` if invalid
- `usage`: Current usage count from Redis counter

**Validation Steps:**
1. Verify key hash matches (SHA256)
2. Check if key is active (status + expiration)
3. Check required scope (if provided)
4. Check entity access (if provided)
5. Check IP whitelist (if provided)
6. Increment usage counter in Redis (~0.1ms)
7. Check rate limits (Redis counters with TTL)

**Example:**

```python
from fastapi import Request, HTTPException

@app.get("/api/users")
async def list_users(request: Request):
    # Get API key from header
    api_key_str = request.headers.get("X-API-Key")
    if not api_key_str:
        raise HTTPException(status_code=401, detail="API key required")

    # Validate API key
    api_key, usage = await auth.api_key_service.validate_api_key(
        api_key_string=api_key_str,
        required_scope="user:read",
        ip_address=request.client.host
    )

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # API key is valid - fetch owner
    owner = await api_key.owner.fetch()

    # Use API key (usage already incremented)
    users = await auth.user_service.list_users()
    return {
        "users": users,
        "api_key_usage": usage
    }
```

### Performance

| Method | Without Redis | With Redis |
|--------|---------------|------------|
| Validate + track usage | ~15ms (MongoDB write) | ~0.1ms (Redis INCR) |
| Rate limit check | N/A | ~0.1ms (Redis TTL counter) |
| **Improvement** | - | **~150x faster** |

---

## API Key Management

### get_api_key()

Get API key by ID.

```python
api_key = await auth.api_key_service.get_api_key("507f1f77bcf86cd799439011")
if api_key:
    print(f"Key: {api_key.name} ({api_key.prefix})")
```

**Parameters:**
- `key_id` (str): API key ID

**Returns:** `Optional[APIKeyModel]`

### list_user_api_keys()

List all API keys for a user.

```python
keys = await auth.api_key_service.list_user_api_keys(
    user_id=str(user.id),
    status=APIKeyStatus.ACTIVE  # Optional filter
)

for key in keys:
    print(f"- {key.name} ({key.prefix}): {key.usage_count} uses")
```

**Parameters:**
- `user_id` (str): User ID
- `status` (APIKeyStatus, optional): Filter by status

**Returns:** `list[APIKeyModel]`

**Example:**

```python
from outlabs_auth.models.api_key import APIKeyStatus

# Get all active keys
active_keys = await auth.api_key_service.list_user_api_keys(
    user_id=str(user.id),
    status=APIKeyStatus.ACTIVE
)

# Get all keys (any status)
all_keys = await auth.api_key_service.list_user_api_keys(
    user_id=str(user.id)
)

print(f"User has {len(active_keys)} active keys out of {len(all_keys)} total")
```

### update_api_key()

Update API key fields.

```python
updated = await auth.api_key_service.update_api_key(
    key_id=str(api_key.id),
    name="Updated Name",
    rate_limit_per_minute=120,
    scopes=["user:read", "user:write"]
)
```

**Parameters:**
- `key_id` (str): API key ID
- `**updates`: Fields to update

**Allowed Fields:**
- `name`, `description`, `metadata`
- `scopes`, `entity_ids`, `ip_whitelist`
- `rate_limit_per_minute`, `rate_limit_per_hour`, `rate_limit_per_day`
- `status`, `expires_at`

**Returns:** `Optional[APIKeyModel]`

**Example:**

```python
# Update rate limits
await auth.api_key_service.update_api_key(
    key_id=str(api_key.id),
    rate_limit_per_minute=200,
    rate_limit_per_hour=10000
)

# Update scopes
await auth.api_key_service.update_api_key(
    key_id=str(api_key.id),
    scopes=["user:read", "entity:read", "project:read"]
)

# Update IP whitelist
await auth.api_key_service.update_api_key(
    key_id=str(api_key.id),
    ip_whitelist=["192.168.1.100", "192.168.1.200"]
)
```

### revoke_api_key()

Revoke an API key (sets status to REVOKED).

```python
revoked = await auth.api_key_service.revoke_api_key(str(api_key.id))
if revoked:
    print("API key revoked")
```

**Parameters:**
- `key_id` (str): API key ID

**Returns:** `bool` - `True` if revoked

**Example:**

```python
# Revoke compromised key
await auth.api_key_service.revoke_api_key(str(api_key.id))

# Key can no longer be used
api_key_check, _ = await auth.api_key_service.validate_api_key(compromised_key)
# api_key_check = None (revoked keys fail validation)
```

---

## Rate Limiting

### Rate Limit Configuration

```python
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Rate Limited Key",
    rate_limit_per_minute=60,    # 60 requests per minute
    rate_limit_per_hour=3000,    # 3000 requests per hour
    rate_limit_per_day=50000     # 50,000 requests per day
)
```

### How Rate Limiting Works

Rate limits use **Redis counters with TTL**:

```python
# Per-minute limit
redis_key = f"apikey:{key_id}:ratelimit:minute"
count = INCR redis_key  # Atomic increment
EXPIRE redis_key 60     # Auto-delete after 60 seconds

if count > rate_limit_per_minute:
    raise RateLimitExceeded()
```

### Rate Limit Response

When rate limit is exceeded, `validate_api_key()` raises:

```python
InvalidInputError(
    message="Rate limit exceeded: 60 requests per minute",
    details={
        "limit": 60,
        "current": 61,
        "window": "minute"
    }
)
```

### Example API Response

```python
from outlabs_auth.core.exceptions import InvalidInputError

@app.get("/api/data")
async def get_data(request: Request):
    api_key_str = request.headers.get("X-API-Key")

    try:
        api_key, usage = await auth.api_key_service.validate_api_key(
            api_key_string=api_key_str
        )
    except InvalidInputError as e:
        # Rate limit exceeded
        raise HTTPException(
            status_code=429,
            detail=e.message,
            headers={
                "X-RateLimit-Limit": str(e.details.get("limit")),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "60"  # seconds
            }
        )

    return {"data": "..."}
```

---

## Redis Counter Pattern

The Redis counter pattern provides **99% reduction in database writes** for API key usage tracking.

### How It Works

**Without Redis (Direct MongoDB):**
```python
# Every API call = MongoDB write (~15ms)
api_key.usage_count += 1
await api_key.save()  # Expensive!
```

**With Redis Counter Pattern:**
```python
# Every API call = Redis INCR (~0.1ms)
count = await redis.incr(f"apikey:{key_id}:usage")

# Background sync every 5 minutes
# Batch update MongoDB with accumulated count
```

### Implementation

**1. Fast Increment (Every Request)**
```python
# In validate_api_key()
counter_key = f"apikey:{key_id}:usage"
usage_count = await redis_client.increment(counter_key, amount=1)
# ~0.1ms - atomic, fast, no DB write
```

**2. Background Sync (Every 5 Minutes)**
```python
# Background worker
await api_key_service.sync_usage_counters_to_db()
```

### sync_usage_counters_to_db()

Sync Redis counters to MongoDB (called by background worker).

```python
stats = await auth.api_key_service.sync_usage_counters_to_db()
print(f"Synced {stats['synced_keys']} keys, {stats['total_usage']} uses")
```

**Returns:** `dict` with sync statistics:
- `synced_keys`: Number of keys synced
- `total_usage`: Total usage count synced
- `errors`: Number of errors

**Example Background Worker:**

```python
import asyncio

async def background_sync_worker():
    """Background worker to sync API key usage counters."""
    while True:
        try:
            # Sync every 5 minutes
            await asyncio.sleep(300)

            stats = await auth.api_key_service.sync_usage_counters_to_db()
            logger.info(
                f"Synced {stats['synced_keys']} API keys, "
                f"{stats['total_usage']} total uses"
            )

        except Exception as e:
            logger.error(f"Error in sync worker: {e}")

# Start worker on app startup
@app.on_event("startup")
async def startup():
    await auth.initialize()
    asyncio.create_task(background_sync_worker())
```

### Performance Impact

| Metric | Without Redis | With Redis Pattern |
|--------|---------------|-------------------|
| **DB Writes per Request** | 1 | 0 |
| **DB Writes per Hour** | 60,000 (at 1000 req/min) | 12 (sync every 5 min) |
| **Write Reduction** | - | **99.98%** |
| **Latency per Request** | ~15ms | ~0.1ms |
| **Speedup** | - | **~150x faster** |

---

## Security Features

### 1. Secure Key Generation

```python
# Generate cryptographically secure API key
full_key, prefix = APIKeyModel.generate_key("sk_live")
# Uses secrets.token_hex(32) - 32 bytes of randomness

# Key format: sk_live_<64 hex chars>
# Example: sk_live_abc123def456...
```

### 2. Key Hashing

```python
# Hash key before storage (SHA256)
key_hash = APIKeyModel.hash_key(full_key)
# Never store plain key in database!
```

### 3. Scoped Permissions

```python
# Restrict key to specific permissions
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Read-Only Key",
    scopes=["user:read", "entity:read"]
)

# Validation checks scope
api_key, _ = await auth.api_key_service.validate_api_key(
    api_key_string=key,
    required_scope="user:delete"  # ❌ Fails - not in scopes
)
```

### 4. IP Whitelisting

```python
# Restrict key to specific IPs
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Office Key",
    ip_whitelist=["192.168.1.100", "203.0.113.5"]
)

# Validation checks IP
api_key, _ = await auth.api_key_service.validate_api_key(
    api_key_string=key,
    ip_address="203.0.113.99"  # ❌ Fails - not in whitelist
)
```

### 5. Entity Scoping (EnterpriseRBAC)

```python
# Restrict key to specific entities
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Engineering Key",
    entity_ids=[str(engineering_dept.id)]
)

# Validation checks entity access
api_key, _ = await auth.api_key_service.validate_api_key(
    api_key_string=key,
    entity_id=str(sales_dept.id)  # ❌ Fails - not in entity_ids
)
```

### 6. Expiration

```python
# Create key with expiration
key, model = await auth.api_key_service.create_api_key(
    owner_id=str(user.id),
    name="Temporary Key",
    expires_in_days=30
)

# After 30 days, key automatically becomes invalid
# is_active() returns False for expired keys
```

---

## Error Handling

### Exception Types

```python
from outlabs_auth.core.exceptions import (
    UserNotFoundError,
    InvalidInputError,  # Rate limit exceeded
)
```

### Error Handling Pattern

```python
from fastapi import Request, HTTPException
from outlabs_auth.core.exceptions import InvalidInputError

@app.get("/api/resource")
async def get_resource(request: Request):
    # Get API key from header
    api_key_str = request.headers.get("X-API-Key")
    if not api_key_str:
        raise HTTPException(status_code=401, detail="API key required")

    try:
        # Validate API key
        api_key, usage = await auth.api_key_service.validate_api_key(
            api_key_string=api_key_str,
            required_scope="resource:read",
            ip_address=request.client.host
        )

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid, inactive, or expired API key"
            )

        # Process request
        return {"data": "..."}

    except InvalidInputError as e:
        # Rate limit exceeded
        raise HTTPException(
            status_code=429,
            detail=e.message,
            headers={"Retry-After": "60"}
        )
```

---

## Complete Examples

### API Key Management API

```python
from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.models.api_key import APIKeyStatus

app = FastAPI()
auth = SimpleRBAC(
    database=db,
    secret_key="...",
    enable_api_keys=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)
deps = AuthDeps(auth)

class CreateAPIKeyRequest(BaseModel):
    name: str
    scopes: list[str] = []
    rate_limit_per_minute: int = 60
    expires_in_days: Optional[int] = 90
    description: Optional[str] = None

# ============================================
# Create API Key
# ============================================

@app.post("/api-keys")
async def create_api_key(
    data: CreateAPIKeyRequest,
    user = Depends(deps.authenticated())
):
    """Create new API key."""
    key, model = await auth.api_key_service.create_api_key(
        owner_id=str(user.id),
        name=data.name,
        scopes=data.scopes,
        rate_limit_per_minute=data.rate_limit_per_minute,
        expires_in_days=data.expires_in_days,
        description=data.description
    )

    return {
        "api_key": key,  # ⚠️ Only shown once!
        "prefix": model.prefix,
        "name": model.name,
        "scopes": model.scopes,
        "rate_limit_per_minute": model.rate_limit_per_minute,
        "expires_at": model.expires_at.isoformat() if model.expires_at else None,
        "created_at": model.created_at.isoformat()
    }

# ============================================
# List User's API Keys
# ============================================

@app.get("/api-keys")
async def list_my_api_keys(
    user = Depends(deps.authenticated())
):
    """List all API keys for current user."""
    keys = await auth.api_key_service.list_user_api_keys(
        user_id=str(user.id)
    )

    return {
        "api_keys": [
            {
                "id": str(k.id),
                "name": k.name,
                "prefix": k.prefix,
                "status": k.status.value,
                "usage_count": k.usage_count,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat()
            }
            for k in keys
        ],
        "count": len(keys)
    }

# ============================================
# Revoke API Key
# ============================================

@app.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    user = Depends(deps.authenticated())
):
    """Revoke API key."""
    # Get key
    api_key = await auth.api_key_service.get_api_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Check ownership
    owner = await api_key.owner.fetch()
    if str(owner.id) != str(user.id):
        raise HTTPException(status_code=403, detail="Not your API key")

    # Revoke
    revoked = await auth.api_key_service.revoke_api_key(key_id)
    return {"message": "API key revoked", "revoked": revoked}

# ============================================
# Protected Route with API Key Auth
# ============================================

async def get_current_user_from_api_key(request: Request):
    """Dependency to authenticate via API key."""
    api_key_str = request.headers.get("X-API-Key")
    if not api_key_str:
        raise HTTPException(status_code=401, detail="API key required")

    api_key, usage = await auth.api_key_service.validate_api_key(
        api_key_string=api_key_str,
        ip_address=request.client.host
    )

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Fetch owner
    owner = await api_key.owner.fetch()
    return owner

@app.get("/api/users")
async def list_users_api(
    request: Request,
    user = Depends(get_current_user_from_api_key)
):
    """List users (API key authentication)."""
    # Validate scope
    api_key_str = request.headers.get("X-API-Key")
    api_key, _ = await auth.api_key_service.validate_api_key(
        api_key_string=api_key_str,
        required_scope="user:read"
    )

    if not api_key:
        raise HTTPException(status_code=403, detail="API key lacks user:read scope")

    users, total = await auth.user_service.list_users()
    return {"users": users, "total": total}
```

### Background Sync Worker

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

async def api_key_sync_worker():
    """Background worker to sync API key usage counters from Redis to MongoDB."""
    while True:
        try:
            # Sync every 5 minutes
            await asyncio.sleep(300)

            logger.info("Starting API key usage counter sync...")
            stats = await auth.api_key_service.sync_usage_counters_to_db()

            logger.info(
                f"API key sync complete: "
                f"{stats['synced_keys']} keys, "
                f"{stats['total_usage']} total uses, "
                f"{stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Error in API key sync worker: {e}", exc_info=True)
            # Continue running even if sync fails
            await asyncio.sleep(60)  # Wait 1 minute before retry

@app.on_event("startup")
async def startup():
    await auth.initialize()

    # Start background worker
    asyncio.create_task(api_key_sync_worker())
    logger.info("Started API key sync background worker")

@app.on_event("shutdown")
async def shutdown():
    # Final sync on shutdown
    logger.info("Performing final API key usage counter sync...")
    stats = await auth.api_key_service.sync_usage_counters_to_db()
    logger.info(f"Final sync: {stats['synced_keys']} keys synced")
```

---

## Summary

**ApiKeyService** provides high-performance API key authentication:

✅ **Secure Generation** - Cryptographically secure keys with SHA256 hashing
✅ **Redis Counter Pattern** - 99% reduction in DB writes (~150x faster)
✅ **Rate Limiting** - Per-minute/hour/day limits with Redis TTL counters
✅ **Scoped Permissions** - Restrict keys to specific permissions
✅ **Entity Scoping** - Restrict keys to entities (EnterpriseRBAC)
✅ **IP Whitelisting** - Restrict keys to specific IPs
✅ **Expiration Support** - Automatic key expiration
✅ **Background Sync** - Batch sync to MongoDB every 5 minutes
✅ **Usage Tracking** - Real-time usage counts via Redis

**Performance:**
- **Without Redis**: ~15ms per request (MongoDB write)
- **With Redis**: ~0.1ms per request (Redis INCR)
- **Improvement**: ~150x faster

---

## Related Documentation

- **23-API-Keys.md** - API key authentication overview
- **60-SimpleRBAC-API.md** - SimpleRBAC API reference
- **61-EnterpriseRBAC-API.md** - EnterpriseRBAC API reference
- **70-User-Service.md** - UserService API reference
- **74-Auth-Service.md** - AuthService API reference

---

**Last Updated:** 2025-01-14
