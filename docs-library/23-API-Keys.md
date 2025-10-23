# API Keys

**Tags**: #authentication #api-keys #programmatic-access

Complete guide to API key authentication in OutlabsAuth.

---

## What are API Keys?

**API Keys** are long-lived credentials for programmatic access to your API.

**Format**: `ola_abc123xyz789_full_key_here`

**Use Cases**:
- Server-to-server communication
- CLI tools
- External integrations
- Webhooks
- CI/CD pipelines

**Not for**:
- User authentication (use JWT)
- Browser applications (security risk)
- Mobile apps (can be extracted)

---

## Quick Start

### Step 1: Add API Key Router

```python
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_api_keys_router, get_auth_router

app = FastAPI()
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["myapp"]

auth = SimpleRBAC(database=db)

@app.on_event("startup")
async def startup():
    await auth.initialize()

# Add auth routes
app.include_router(get_auth_router(auth), prefix="/auth", tags=["auth"])

# Add API key routes
app.include_router(
    get_api_keys_router(auth),
    prefix="/api-keys",
    tags=["api-keys"]
)
```

### Step 2: Create API Key (as authenticated user)

```bash
# Login first
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Get access token from response, then create API key
curl -X POST "http://localhost:8000/api-keys" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production API Key"}'
```

Response:
```json
{
  "id": "key_abc123",
  "key": "ola_abc123xyz789_1234567890abcdef1234567890abcdef",
  "name": "Production API Key",
  "created_at": "2025-01-23T10:00:00Z",
  "last_used_at": null,
  "usage_count": 0
}
```

**⚠️ IMPORTANT**: Save the full key! It's only shown once.

### Step 3: Use API Key

```bash
curl -X GET "http://localhost:8000/protected" \
  -H "X-API-Key: ola_abc123xyz789_1234567890abcdef1234567890abcdef"
```

---

## API Key Format

### Structure

```
ola_abc123xyz789_1234567890abcdef1234567890abcdef
│   │            │
│   │            └─ Secret portion (hashed in database)
│   └─ 12-character public ID
└─ Prefix (scannable, identifiable)
```

**Components**:
1. **Prefix** (`ola_`): Identifiable prefix for scanning
2. **Public ID** (12 chars): Lookup key in database
3. **Secret** (remaining): Hashed with argon2id

### Why This Format? (DD-029)

#### 1. Scannable Prefix

**Purpose**: GitHub and other platforms can scan for leaked keys

```bash
# GitHub secret scanning looks for patterns like:
ola_[a-zA-Z0-9]{12}_[a-zA-Z0-9]{32}
```

**Benefits**:
- ✅ Automated leak detection
- ✅ Developers recognize keys in logs
- ✅ Easier rotation

#### 2. Public ID

**Purpose**: Fast database lookup without hashing

```python
# Extract public ID
prefix, public_id, secret = key.split("_", 2)

# Fast lookup (indexed)
api_key = await db.api_keys.find_one({"public_id": public_id})

# Then verify hash
if argon2.verify(key, api_key.hashed_key):
    # Valid!
```

**Performance**: O(1) lookup vs O(n) hash comparison

#### 3. argon2id Hashing (DD-028)

**Why argon2id** (not bcrypt):
- ✅ Memory-hard (GPU-resistant)
- ✅ Side-channel resistant
- ✅ OWASP recommended
- ✅ Better for API keys than bcrypt

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Hash API key
hashed = pwd_context.hash(full_key)

# Verify API key
is_valid = pwd_context.verify(full_key, hashed)
```

---

## API Key Management

### Create API Key

```bash
POST /api-keys
Authorization: Bearer {user_access_token}
Content-Type: application/json

{
  "name": "Production API Key",
  "expires_at": "2025-12-31T23:59:59Z",  # Optional
  "rate_limit": 1000  # Optional: requests per minute
}
```

Response:
```json
{
  "id": "key_abc123",
  "key": "ola_abc123xyz789_full_key_here",  # ⚠️ Only shown once!
  "name": "Production API Key",
  "prefix": "ola_abc123xyz789",
  "created_at": "2025-01-23T10:00:00Z",
  "expires_at": "2025-12-31T23:59:59Z",
  "last_used_at": null,
  "usage_count": 0,
  "rate_limit": 1000
}
```

### List API Keys

```bash
GET /api-keys
Authorization: Bearer {user_access_token}
```

Response:
```json
{
  "keys": [
    {
      "id": "key_abc123",
      "name": "Production API Key",
      "prefix": "ola_abc123xyz789",  # Only prefix shown
      "created_at": "2025-01-23T10:00:00Z",
      "last_used_at": "2025-01-23T12:30:00Z",
      "usage_count": 1547,
      "is_active": true
    },
    {
      "id": "key_xyz789",
      "name": "Development API Key",
      "prefix": "ola_xyz789abc123",
      "created_at": "2025-01-20T09:00:00Z",
      "last_used_at": "2025-01-23T11:00:00Z",
      "usage_count": 342,
      "is_active": true
    }
  ]
}
```

### Revoke API Key

```bash
DELETE /api-keys/{key_id}
Authorization: Bearer {user_access_token}
```

Response:
```json
{
  "message": "API key revoked successfully"
}
```

### Rotate API Key

```bash
POST /api-keys/{key_id}/rotate
Authorization: Bearer {user_access_token}
```

Response:
```json
{
  "id": "key_abc123",
  "key": "ola_new123key789_new_secret_here",  # New key!
  "name": "Production API Key",
  "created_at": "2025-01-23T10:00:00Z",
  "rotated_at": "2025-01-23T15:00:00Z"
}
```

**Note**: Old key is immediately revoked.

---

## Using API Keys

### In Requests

```python
import httpx

async def call_api(api_key: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.example.com/protected",
            headers={"X-API-Key": api_key}
        )
        return response.json()
```

```bash
# cURL
curl -H "X-API-Key: ola_abc123..." https://api.example.com/protected
```

### Custom Header Name

```python
from outlabs_auth.transports import ApiKeyTransport

# Custom header name
custom_transport = ApiKeyTransport(header_name="X-Custom-API-Key")

backend = AuthBackend(
    name="api_key",
    transport=custom_transport,
    strategy=ApiKeyStrategy()
)
```

### Multiple API Keys per User

Users can create multiple API keys for different purposes:

```python
# Production key
prod_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Production",
    rate_limit=10000
)

# Development key
dev_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Development",
    rate_limit=100
)

# CI/CD key
ci_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="CI/CD Pipeline",
    rate_limit=1000
)
```

---

## Security Features

### 1. argon2id Hashing

**Storage**: Never store plaintext keys!

```python
# Generate key
full_key = secrets.token_urlsafe(32)

# Hash with argon2id
hashed = pwd_context.hash(full_key)

# Store in database
await db.api_keys.insert_one({
    "user_id": user.id,
    "prefix": prefix,
    "public_id": public_id,
    "hashed_key": hashed,  # Only hash stored
    "created_at": datetime.utcnow()
})
```

**Verification** (~50ms):
```python
# Fast lookup by public_id (indexed)
api_key = await db.api_keys.find_one({"public_id": public_id})

# Verify hash (slow but secure)
if pwd_context.verify(full_key, api_key["hashed_key"]):
    return api_key  # Valid!
else:
    raise InvalidAPIKey()
```

### 2. Rate Limiting

**Per-key rate limits** prevent abuse:

```python
from outlabs_auth.services import ApiKeyService

class MyApiKeyService(ApiKeyService):
    async def check_rate_limit(self, api_key_id: str) -> bool:
        """Check if API key is within rate limit"""
        # Get key
        key = await self.get_api_key(api_key_id)

        # Check usage in last minute
        recent_usage = await self.get_usage_last_minute(api_key_id)

        if recent_usage >= key.rate_limit:
            return False  # Rate limit exceeded

        return True  # Within limit

# In route
@app.get("/protected")
async def protected(ctx = Depends(auth.deps.require_auth())):
    api_key_id = ctx.get("api_key_id")

    if api_key_id:
        # API key authentication
        within_limit = await auth.api_key_service.check_rate_limit(api_key_id)

        if not within_limit:
            raise HTTPException(429, "Rate limit exceeded")

    return {"data": "..."}
```

### 3. Temporary Locks

**Lock after failed attempts** (prevent brute force):

```python
from outlabs_auth.services import ApiKeyService

class MyApiKeyService(ApiKeyService):
    async def record_failed_attempt(self, public_id: str):
        """Record failed API key attempt"""
        api_key = await self.get_by_public_id(public_id)

        # Increment failed attempts
        api_key.failed_attempts += 1

        # Lock after 5 failed attempts
        if api_key.failed_attempts >= 5:
            # Lock for 15 minutes
            api_key.locked_until = datetime.utcnow() + timedelta(minutes=15)

            # Notify user
            user = await self.user_service.get_user(api_key.user_id)
            await email_service.send_security_alert(
                user.email,
                f"API key '{api_key.name}' locked due to failed attempts"
            )

        await api_key.save()

    async def check_lock(self, api_key) -> bool:
        """Check if API key is locked"""
        if api_key.locked_until:
            if datetime.utcnow() < api_key.locked_until:
                return True  # Still locked
            else:
                # Lock expired, clear it
                api_key.locked_until = None
                api_key.failed_attempts = 0
                await api_key.save()

        return False  # Not locked
```

### 4. Expiration

**Set expiration dates** for temporary keys:

```python
# Create key with expiration
api_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Temporary Key",
    expires_at=datetime.utcnow() + timedelta(days=30)
)

# Check expiration on use
if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
    raise HTTPException(401, "API key expired")
```

---

## Usage Tracking

### Redis Counters (DD-033)

**Problem**: Tracking usage in MongoDB generates massive writes.

**Solution**: Use Redis counters, flush periodically to MongoDB.

**Performance**: 99%+ reduction in database writes!

```python
import redis.asyncio as redis

class ApiKeyService:
    def __init__(self, database, redis_url: str = None):
        self.database = database
        self.redis = redis.from_url(redis_url) if redis_url else None

    async def track_usage(self, api_key_id: str):
        """Track API key usage"""
        if self.redis:
            # Increment Redis counter (fast!)
            await self.redis.incr(f"api_key_usage:{api_key_id}")

            # Update last used timestamp in Redis
            await self.redis.set(
                f"api_key_last_used:{api_key_id}",
                datetime.utcnow().isoformat()
            )
        else:
            # Fallback to MongoDB (slower)
            await self.database.api_keys.update_one(
                {"_id": api_key_id},
                {
                    "$inc": {"usage_count": 1},
                    "$set": {"last_used_at": datetime.utcnow()}
                }
            )

    async def flush_usage_to_database(self):
        """Flush Redis counters to MongoDB (run periodically)"""
        if not self.redis:
            return

        # Get all usage keys
        keys = await self.redis.keys("api_key_usage:*")

        for key in keys:
            api_key_id = key.decode().replace("api_key_usage:", "")

            # Get count from Redis
            count = await self.redis.get(key)
            if count:
                count = int(count)

                # Update MongoDB
                await self.database.api_keys.update_one(
                    {"_id": api_key_id},
                    {"$inc": {"usage_count": count}}
                )

                # Delete Redis key
                await self.redis.delete(key)

        # Flush last_used timestamps
        last_used_keys = await self.redis.keys("api_key_last_used:*")

        for key in last_used_keys:
            api_key_id = key.decode().replace("api_key_last_used:", "")

            # Get timestamp
            timestamp = await self.redis.get(key)
            if timestamp:
                # Update MongoDB
                await self.database.api_keys.update_one(
                    {"_id": api_key_id},
                    {"$set": {"last_used_at": datetime.fromisoformat(timestamp.decode())}}
                )

                # Delete Redis key
                await self.redis.delete(key)

# Run flush periodically (every 5 minutes)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=5)
async def flush_api_key_usage():
    await auth.api_key_service.flush_usage_to_database()

scheduler.start()
```

**Performance Comparison**:

| Requests/sec | MongoDB writes/sec | Redis writes/sec | MongoDB writes/sec (with flush) |
|--------------|-------------------|------------------|--------------------------------|
| 1000 | 1000 | 1000 | 0.2 (every 5 min) |
| 10000 | 10000 | 10000 | 2 (every 5 min) |

**Result**: 99.9%+ reduction in MongoDB writes!

---

## Programmatic Management

### Create API Key

```python
api_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Production API Key",
    expires_at=datetime.utcnow() + timedelta(days=365),
    rate_limit=10000,
    metadata={"environment": "production"}
)

print(f"Save this key: {api_key.full_key}")
# ⚠️ full_key only available at creation!
```

### Get API Key

```python
# By ID
api_key = await auth.api_key_service.get_api_key(key_id)

# By public ID
api_key = await auth.api_key_service.get_by_public_id(public_id)

# List user's keys
keys = await auth.api_key_service.list_user_keys(user_id)
```

### Validate API Key

```python
# From request header
async def get_current_user_from_api_key(
    x_api_key: str = Header(None)
):
    if not x_api_key:
        raise HTTPException(401, "API key required")

    # Validate
    try:
        api_key, user = await auth.api_key_service.validate_api_key(x_api_key)

        # Track usage
        await auth.api_key_service.track_usage(api_key.id)

        return user

    except Exception as e:
        raise HTTPException(401, f"Invalid API key: {e}")
```

### Revoke API Key

```python
await auth.api_key_service.revoke_api_key(key_id)
```

### Rotate API Key

```python
new_key = await auth.api_key_service.rotate_api_key(key_id)
print(f"New key: {new_key.full_key}")
```

---

## Lifecycle Hooks

### Available Hooks

```python
from outlabs_auth.services import ApiKeyService

class MyApiKeyService(ApiKeyService):
    async def on_after_create(self, api_key, request=None):
        """Called after API key created"""
        user = await self.user_service.get_user(api_key.user_id)
        await email_service.send(
            user.email,
            "New API key created",
            f"API key '{api_key.name}' was created"
        )

    async def on_after_use(self, api_key, request=None):
        """Called after API key used"""
        # Track analytics
        await analytics.track("api_key_used", {
            "key_id": api_key.id,
            "user_id": api_key.user_id
        })

    async def on_after_rotate(self, old_key, new_key, request=None):
        """Called after API key rotated"""
        user = await self.user_service.get_user(new_key.user_id)
        await email_service.send(
            user.email,
            "API key rotated",
            f"API key '{new_key.name}' was rotated. Old key is now invalid."
        )

    async def on_after_revoke(self, api_key, request=None):
        """Called after API key revoked"""
        user = await self.user_service.get_user(api_key.user_id)
        await email_service.send(
            user.email,
            "API key revoked",
            f"API key '{api_key.name}' was revoked"
        )

auth = SimpleRBAC(
    database=db,
    api_key_service_class=MyApiKeyService
)
```

See [[133-API-Key-Hooks|API Key Lifecycle Hooks]] for complete reference.

---

## Best Practices

### 1. One Key Per Purpose

```python
# ❌ BAD: Single key for everything
universal_key = "ola_..."

# ✅ GOOD: Separate keys
production_key = "ola_prod..."
development_key = "ola_dev..."
ci_cd_key = "ola_ci..."
```

### 2. Set Expiration

```python
# ❌ BAD: Never expires
api_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Key"
)

# ✅ GOOD: Expires
api_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Key",
    expires_at=datetime.utcnow() + timedelta(days=365)
)
```

### 3. Use Rate Limits

```python
# ✅ Set appropriate rate limits
production_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Production",
    rate_limit=10000  # 10K requests/minute
)

dev_key = await auth.api_key_service.create_api_key(
    user_id=user.id,
    name="Development",
    rate_limit=100  # 100 requests/minute
)
```

### 4. Rotate Regularly

```python
# Rotate production keys every 90 days
async def rotate_old_keys():
    keys = await auth.api_key_service.list_api_keys()

    for key in keys:
        age = datetime.utcnow() - key.created_at

        if age.days >= 90:
            # Rotate key
            new_key = await auth.api_key_service.rotate_api_key(key.id)

            # Notify user
            user = await auth.user_service.get_user(key.user_id)
            await email_service.send(
                user.email,
                "API key rotated",
                f"New key: {new_key.full_key}"
            )
```

### 5. Monitor Usage

```python
# Alert on suspicious usage
async def monitor_api_keys():
    keys = await auth.api_key_service.list_api_keys()

    for key in keys:
        # Get usage in last hour
        recent_usage = await get_usage_last_hour(key.id)

        # Alert if unusual
        if recent_usage > key.rate_limit * 0.9:
            await send_alert(
                f"API key '{key.name}' at 90% rate limit"
            )
```

### 6. Secure Storage

```python
# ❌ BAD: Store in code
API_KEY = "ola_abc123..."

# ✅ GOOD: Store in environment variables
import os
API_KEY = os.getenv("API_KEY")

# ✅ BETTER: Use secrets management
from aws_secretsmanager import get_secret
API_KEY = get_secret("prod/api_key")
```

---

## Testing

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_api_key_creation():
    # Create user and get token
    user = await auth.user_service.create_user(
        email="test@example.com",
        password="password"
    )
    tokens = await auth.auth_service.login("test@example.com", "password")

    # Create API key
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api-keys",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"name": "Test Key"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "key" in data
    assert data["key"].startswith("ola_")

@pytest.mark.asyncio
async def test_api_key_authentication():
    # Create API key
    api_key = await auth.api_key_service.create_api_key(
        user_id=user.id,
        name="Test Key"
    )

    # Use API key
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/protected",
            headers={"X-API-Key": api_key.full_key}
        )

    assert response.status_code == 200

@pytest.mark.asyncio
async def test_invalid_api_key():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/protected",
            headers={"X-API-Key": "invalid_key"}
        )

    assert response.status_code == 401
```

---

## Next Steps

- **[[24-Service-Tokens|Service Tokens]]** - Microservice authentication
- **[[25-Multi-Source-Auth|Multi-Source Auth]]** - Multiple auth methods
- **[[93-API-Keys-Router|API Keys Router]]** - Router reference
- **[[133-API-Key-Hooks|API Key Hooks]]** - Lifecycle hooks reference

---

**Previous**: [[22-JWT-Tokens|← JWT Tokens]]
**Next**: [[24-Service-Tokens|Service Tokens →]]
