# Multi-Source Authentication

**Tags**: #authentication #multi-source #backends #jwt #api-keys #service-tokens

Configure multiple authentication methods that work together seamlessly.

---

## Overview

Multi-Source Authentication allows your API to accept **multiple authentication methods simultaneously** - JWT tokens, API keys, and service tokens can all be used on the same endpoints. This provides maximum flexibility for different types of clients.

**Prerequisites**: [[22-JWT-Tokens|JWT Tokens]], [[23-API-Keys|API Keys]], [[24-Service-Tokens|Service Tokens]]

**Key Benefits**:
- 🔄 **Fallback authentication** (try JWT → API Key → Service Token)
- 🎯 **Different clients, same endpoint** (web app uses JWT, API clients use keys)
- ⚡ **Zero code changes** to add new auth methods
- 📊 **Perfect Swagger UI** (all methods appear in OpenAPI docs)
- 🔒 **Source-specific endpoints** (restrict certain endpoints to specific auth types)

---

## Quick Start

### Basic Multi-Source Setup

```python
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.authentication import (
    AuthBackend,
    BearerTransport,
    ApiKeyTransport,
    JWTStrategy,
    ApiKeyStrategy
)

app = FastAPI()
auth = SimpleRBAC(database=db)

# Configure authentication backends
jwt_backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret=auth.config.secret_key)
)

api_key_backend = AuthBackend(
    name="api_key",
    transport=ApiKeyTransport(),
    strategy=ApiKeyStrategy()
)

# Create unified dependencies
deps = AuthDeps(
    backends=[jwt_backend, api_key_backend],
    user_service=auth.user_service,
    api_key_service=auth.api_key_service
)

# Single endpoint accepts BOTH JWT and API keys!
@app.get("/protected")
async def protected_route(
    auth_result = Depends(deps.require_auth())
):
    """Works with JWT OR API key!"""
    return {
        "authenticated": True,
        "source": auth_result["source"],  # "jwt" or "api_key"
        "user": auth_result["user"].email
    }
```

Now your endpoint accepts:
- ✅ `Authorization: Bearer eyJhbGciOiJIUzI1NiIs...` (JWT)
- ✅ `X-API-Key: ola_abc123xyz789_...` (API Key)

---

## How It Works

### Transport + Strategy Pattern

Each authentication method is composed of:

1. **Transport**: HOW credentials are sent
   - `BearerTransport` - Authorization: Bearer {token}
   - `ApiKeyTransport` - X-API-Key: {key}
   - Custom header, query param, cookie, etc.

2. **Strategy**: HOW credentials are validated
   - `JWTStrategy` - Decode JWT, verify signature, fetch user
   - `ApiKeyStrategy` - Hash key, lookup in DB, check permissions
   - `ServiceTokenStrategy` - Validate service JWT

3. **Backend**: Combines Transport + Strategy
   ```python
   backend = AuthBackend(
       name="jwt",
       transport=BearerTransport(),  # HOW
       strategy=JWTStrategy(secret)  # WHAT
   )
   ```

### Fallback Chain

When you configure multiple backends, OutlabsAuth tries each one **in order** until one succeeds:

```
Request comes in
  ↓
Try JWT Backend
  ├─ Success → Return user
  └─ Fail → Continue
       ↓
Try API Key Backend
  ├─ Success → Return user
  └─ Fail → Continue
       ↓
Try Service Token Backend
  ├─ Success → Return user
  └─ Fail → 401 Unauthorized
```

---

## Configuring Multiple Sources

### Three-Source Setup (Complete Example)

```python
from outlabs_auth.authentication import (
    AuthBackend,
    BearerTransport,
    ApiKeyTransport,
    JWTStrategy,
    ApiKeyStrategy,
    ServiceTokenStrategy
)
from outlabs_auth.dependencies import AuthDeps

# 1. JWT Authentication (user tokens)
jwt_backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(
        secret=auth.config.secret_key,
        algorithm="HS256"
    )
)

# 2. API Key Authentication (third-party integrations)
api_key_backend = AuthBackend(
    name="api_key",
    transport=ApiKeyTransport(header_name="X-API-Key"),
    strategy=ApiKeyStrategy()
)

# 3. Service Token Authentication (microservices)
service_backend = AuthBackend(
    name="service",
    transport=BearerTransport(token_header="X-Service-Token"),
    strategy=ServiceTokenStrategy(secret=auth.config.secret_key)
)

# Create dependencies with all three backends
deps = AuthDeps(
    backends=[jwt_backend, api_key_backend, service_backend],
    user_service=auth.user_service,
    api_key_service=auth.api_key_service
)

# Use in routes
@app.get("/data")
async def get_data(
    auth_result = Depends(deps.require_auth())
):
    """Accepts JWT, API Key, OR Service Token!"""
    return {
        "source": auth_result["source"],
        "data": "..."
    }
```

Now your endpoint accepts:
- ✅ `Authorization: Bearer <jwt>` (users)
- ✅ `X-API-Key: ola_...` (API clients)
- ✅ `X-Service-Token: <service_jwt>` (internal services)

---

## Using Multi-Source Dependencies

### Basic Authentication

```python
@app.get("/users/me")
async def get_current_user(
    auth_result = Depends(deps.require_auth())
):
    """Any valid auth method works"""
    return {
        "email": auth_result["user"].email,
        "source": auth_result["source"],
        "metadata": auth_result["metadata"]
    }
```

**Request Examples**:
```bash
# With JWT
curl -H "Authorization: Bearer eyJhbGci..." http://localhost:8000/users/me

# With API Key
curl -H "X-API-Key: ola_abc123_..." http://localhost:8000/users/me

# With Service Token
curl -H "X-Service-Token: eyJhbGci..." http://localhost:8000/users/me
```

### Optional Authentication

```python
@app.get("/public-with-bonus")
async def public_endpoint(
    auth_result = Depends(deps.require_auth(optional=True))
):
    """Public endpoint with optional authentication"""
    if auth_result:
        # Authenticated - provide extra data
        return {
            "data": "public data",
            "premium_data": "bonus data for authenticated users",
            "user": auth_result["user"].email
        }
    else:
        # Anonymous - basic data only
        return {
            "data": "public data"
        }
```

### Require Active Users

```python
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    auth_result = Depends(deps.require_auth(active=True))
):
    """Only active users allowed"""
    # auth_result["user"].is_active == True
    await auth.user_service.delete_user(user_id)
    return {"deleted": True}
```

### Require Verified Users

```python
@app.post("/posts")
async def create_post(
    post_data: dict,
    auth_result = Depends(deps.require_auth(verified=True))
):
    """Only verified users can post"""
    # auth_result["user"].is_verified == True
    post = await create_post_in_db(post_data, auth_result["user"].id)
    return post
```

---

## Checking Authentication Source

### Inspect Which Method Was Used

```python
@app.get("/data")
async def get_data(
    auth_result = Depends(deps.require_auth())
):
    """Handle different auth sources"""

    source = auth_result["source"]

    if source == "jwt":
        # User authenticated with JWT
        user = auth_result["user"]
        return {"message": f"Hello {user.email}!", "data": get_user_data(user)}

    elif source == "api_key":
        # Third-party authenticated with API key
        key_prefix = auth_result["metadata"]["key_prefix"]
        return {"message": f"API Key: {key_prefix}", "data": get_api_data()}

    elif source == "service":
        # Internal service authenticated
        service_name = auth_result["metadata"]["service_name"]
        return {"message": f"Service: {service_name}", "data": get_all_data()}
```

### Restrict to Specific Source

```python
@app.post("/internal/sync")
async def internal_sync(
    auth_result = Depends(deps.require_source("service"))
):
    """ONLY service tokens allowed"""
    return {
        "service": auth_result["metadata"]["service_name"],
        "synced": True
    }

@app.get("/api-only")
async def api_only_endpoint(
    auth_result = Depends(deps.require_source("api_key"))
):
    """ONLY API keys allowed"""
    return {
        "key_prefix": auth_result["metadata"]["key_prefix"],
        "data": "..."
    }
```

---

## Authentication Result Structure

### Result Dictionary

Every successful authentication returns a consistent dictionary:

```python
{
    "user": UserModel,           # User object (if applicable)
    "source": str,               # "jwt", "api_key", "service", etc.
    "metadata": dict,            # Source-specific metadata
    "user_id": str               # User ID (optional)
}
```

### Source-Specific Metadata

**JWT Authentication**:
```python
{
    "user": <UserModel>,
    "source": "jwt",
    "user_id": "64a1b2c3...",
    "metadata": {
        "sub": "64a1b2c3...",
        "exp": 1674132000,
        "iat": 1642596000,
        "type": "access"
    }
}
```

**API Key Authentication**:
```python
{
    "user": <UserModel>,
    "source": "api_key",
    "user_id": "64a1b2c3...",
    "metadata": {
        "key_id": "64a1b2c3...",
        "key_prefix": "ola_abc123",
        "permissions": ["data:read", "data:write"],
        "name": "Production API Key"
    }
}
```

**Service Token Authentication**:
```python
{
    "user": None,  # No user for services
    "source": "service",
    "metadata": {
        "sub": "analytics-api",
        "service_name": "Analytics API",
        "permissions": ["analytics:read", "data:export"],
        "environment": "production"
    }
}
```

---

## Permission Checking

### Require Specific Permissions

```python
@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    auth_result = Depends(deps.require_permission("post:delete"))
):
    """Requires post:delete permission from ANY auth source"""
    await delete_post_from_db(post_id)
    return {"deleted": True}
```

**Works with**:
- JWT user with "post:delete" role permission
- API key with "post:delete" in key permissions
- Service token with "post:delete" embedded

### Require Multiple Permissions (ANY)

```python
@app.post("/admin/action")
async def admin_action(
    auth_result = Depends(deps.require_permission("admin:all", "superuser:access"))
):
    """User needs admin:all OR superuser:access"""
    return {"success": True}
```

### Require Multiple Permissions (ALL)

```python
@app.post("/critical")
async def critical_action(
    auth_result = Depends(deps.require_permission(
        "admin:all",
        "system:critical",
        require_all=True  # Must have BOTH
    ))
):
    """User needs admin:all AND system:critical"""
    return {"success": True}
```

---

## Custom Transports

### Custom Header Transport

```python
from outlabs_auth.authentication import Transport
from fastapi import Request
from typing import Optional

class CustomHeaderTransport(Transport):
    """Custom header for authentication"""

    def __init__(self, header_name: str = "X-Custom-Auth"):
        self.header_name = header_name

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract credentials from custom header"""
        return request.headers.get(self.header_name)

    def get_openapi_schema(self) -> dict:
        """Define how this appears in Swagger UI"""
        return {
            "type": "apiKey",
            "in": "header",
            "name": self.header_name
        }

# Use custom transport
custom_backend = AuthBackend(
    name="custom",
    transport=CustomHeaderTransport(header_name="X-My-Auth"),
    strategy=JWTStrategy(secret=SECRET)
)

deps = AuthDeps(
    backends=[jwt_backend, custom_backend],
    user_service=auth.user_service
)
```

### Query Parameter Transport

```python
class QueryParamTransport(Transport):
    """Token in query parameter (for webhooks, not recommended for production)"""

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract token from ?token=... query param"""
        return request.query_params.get("token")

    def get_openapi_schema(self) -> dict:
        return {
            "type": "apiKey",
            "in": "query",
            "name": "token"
        }

# Use for webhooks
webhook_backend = AuthBackend(
    name="webhook",
    transport=QueryParamTransport(),
    strategy=JWTStrategy(secret=WEBHOOK_SECRET)
)
```

### Cookie Transport

```python
class CookieTransport(Transport):
    """Token in HTTP cookie"""

    def __init__(self, cookie_name: str = "auth_token"):
        self.cookie_name = cookie_name

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract token from cookie"""
        return request.cookies.get(self.cookie_name)

    def get_openapi_schema(self) -> dict:
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": self.cookie_name
        }

# Use for browser-based apps
cookie_backend = AuthBackend(
    name="cookie",
    transport=CookieTransport(),
    strategy=JWTStrategy(secret=SECRET)
)
```

---

## OpenAPI / Swagger UI

### Automatic Security Schemas

All configured backends automatically appear in Swagger UI:

```python
deps = AuthDeps(backends=[jwt_backend, api_key_backend, service_backend])

@app.get("/protected")
async def protected(auth = Depends(deps.require_auth())):
    return {"success": True}
```

**Swagger UI Shows**:
- 🔐 Bearer Authentication (JWT)
- 🔐 API Key (X-API-Key header)
- 🔐 Service Token (X-Service-Token header)

Users can **select which auth method to use** directly in Swagger!

### Custom Security Scheme Names

```python
jwt_backend = AuthBackend(
    name="jwt",  # Appears as "jwt" in Swagger
    transport=BearerTransport(),
    strategy=JWTStrategy(secret=SECRET)
)

api_key_backend = AuthBackend(
    name="api_key",  # Appears as "api_key" in Swagger
    transport=ApiKeyTransport(),
    strategy=ApiKeyStrategy()
)
```

---

## Use Cases & Examples

### Use Case 1: SaaS Application

```python
# Users authenticate with JWT (web app)
# Third-party integrations use API keys
# Internal services use service tokens

deps = AuthDeps(
    backends=[
        AuthBackend("jwt", BearerTransport(), JWTStrategy(SECRET)),
        AuthBackend("api_key", ApiKeyTransport(), ApiKeyStrategy()),
        AuthBackend("service", BearerTransport("X-Service-Token"), ServiceTokenStrategy(SECRET))
    ],
    user_service=auth.user_service,
    api_key_service=auth.api_key_service
)

# Public endpoint - works for everyone
@app.get("/api/data")
async def get_data(auth = Depends(deps.require_auth())):
    """All clients can access"""
    if auth["source"] == "jwt":
        return get_user_specific_data(auth["user"])
    elif auth["source"] == "api_key":
        return get_api_data()
    else:
        return get_internal_data()

# Internal endpoint - services only
@app.post("/internal/process")
async def process(auth = Depends(deps.require_source("service"))):
    """Only internal services"""
    return {"processed": True}
```

### Use Case 2: Public API with Premium Features

```python
@app.get("/api/basic")
async def basic_data(auth = Depends(deps.require_auth(optional=True))):
    """Public endpoint with optional authentication"""
    data = {"basic": "data"}

    if auth:
        # Authenticated users get more
        data["premium"] = "extra data"
        data["user"] = auth["user"].email

    return data

@app.get("/api/premium")
async def premium_data(auth = Depends(deps.require_auth())):
    """Premium endpoint - authentication required"""
    return {
        "premium": "data",
        "user": auth["user"].email
    }
```

### Use Case 3: Microservices Architecture

```python
# API Gateway accepts user JWT
# Internal services use service tokens
# Admin tools use special admin API keys

deps = AuthDeps(backends=[
    AuthBackend("jwt", BearerTransport(), JWTStrategy(USER_SECRET)),
    AuthBackend("service", BearerTransport("X-Service-Token"), ServiceTokenStrategy(SERVICE_SECRET)),
    AuthBackend("admin", ApiKeyTransport("X-Admin-Key"), ApiKeyStrategy())
])

@app.get("/api/users")
async def list_users(auth = Depends(deps.require_auth())):
    """Users and admins can access"""
    if auth["source"] == "admin":
        # Admin sees all users
        return get_all_users()
    else:
        # Regular users see limited info
        return get_public_users()

@app.post("/internal/sync")
async def sync(auth = Depends(deps.require_source("service"))):
    """Only microservices"""
    return {"synced": True}
```

---

## Best Practices

### 1. Order Backends by Frequency

```python
# Put most common auth method first
deps = AuthDeps(backends=[
    jwt_backend,        # Most common (web app users)
    api_key_backend,    # Less common (API clients)
    service_backend     # Least common (internal services)
])

# Faster authentication (fewer fallback attempts)
```

### 2. Use Source-Specific Endpoints

```python
# Don't use multi-source for everything
@app.get("/public")  # No auth
async def public():
    return {"data": "..."}

@app.get("/users/me")  # JWT only
async def get_me(auth = Depends(deps.require_source("jwt"))):
    return auth["user"]

@app.get("/api/data")  # API keys only
async def api_data(auth = Depends(deps.require_source("api_key"))):
    return {"data": "..."}

@app.post("/internal")  # Service tokens only
async def internal(auth = Depends(deps.require_source("service"))):
    return {"success": True}
```

### 3. Log Authentication Sources

```python
import logging

@app.get("/data")
async def get_data(auth = Depends(deps.require_auth())):
    # Log which auth method was used
    logging.info(
        f"Authenticated via {auth['source']} "
        f"- User: {auth.get('user_id', 'service')}"
    )

    return {"data": "..."}
```

### 4. Monitor Source Distribution

```python
from collections import Counter

auth_sources = Counter()

@app.get("/stats")
async def stats(auth = Depends(deps.require_auth())):
    # Track auth source usage
    auth_sources[auth["source"]] += 1

    return {
        "source": auth["source"],
        "stats": dict(auth_sources)
    }

# After 1000 requests:
# {"jwt": 850, "api_key": 130, "service": 20}
```

### 5. Test All Auth Methods

```python
import pytest

@pytest.mark.asyncio
async def test_jwt_authentication(client, jwt_token):
    """Test JWT authentication"""
    response = await client.get(
        "/protected",
        headers={"Authorization": f"Bearer {jwt_token}"}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_api_key_authentication(client, api_key):
    """Test API key authentication"""
    response = await client.get(
        "/protected",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_service_token_authentication(client, service_token):
    """Test service token authentication"""
    response = await client.get(
        "/protected",
        headers={"X-Service-Token": service_token}
    )
    assert response.status_code == 200
```

---

## Troubleshooting

### Issue 1: All Backends Fail

```python
# Check if any backend authenticated
@app.get("/debug")
async def debug(request: Request):
    for backend in deps.backends:
        try:
            result = await backend.authenticate(request, **services)
            if result:
                return {"backend": backend.name, "success": True}
        except Exception as e:
            print(f"{backend.name} failed: {e}")

    return {"error": "All backends failed"}
```

### Issue 2: Wrong Backend Used

```python
# Check backend order and credentials
print("Backend order:", [b.name for b in deps.backends])
print("Request headers:", request.headers)

# Make sure the right credentials are sent
# JWT: Authorization: Bearer <token>
# API Key: X-API-Key: <key>
# Service: X-Service-Token: <token>
```

### Issue 3: OpenAPI Schema Issues

```python
# Ensure each backend has a unique name
deps = AuthDeps(backends=[
    AuthBackend("jwt", ...),      # Unique name
    AuthBackend("api_key", ...),  # Unique name
    AuthBackend("service", ...)   # Unique name
])

# Check OpenAPI schema
from fastapi.openapi.utils import get_openapi

schema = get_openapi(
    title="My API",
    version="1.0.0",
    routes=app.routes
)

print("Security schemes:", schema.get("components", {}).get("securitySchemes"))
```

---

## Performance Considerations

### Fallback Overhead

Each failed authentication attempt adds latency:

```
JWT attempt: ~1ms
API Key attempt: ~50ms (DB lookup)
Service Token attempt: ~0.5ms

Total worst case: ~51.5ms (if first two fail)
```

**Optimization**: Order backends by frequency to minimize fallbacks.

### Caching Strategies

```python
# Enable Redis caching for API key lookups
auth = SimpleRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# API key lookups: 50ms → 1ms (cached)
```

### Concurrent Backend Checks

Current implementation checks backends sequentially. For high-performance needs, consider parallel checks (custom implementation).

---

## Next Steps

- **[[80-Auth-Dependencies|AuthDeps]]** - Complete dependency injection reference
- **[[22-JWT-Tokens|JWT Tokens]]** - User authentication
- **[[23-API-Keys|API Keys]]** - Third-party authentication
- **[[24-Service-Tokens|Service Tokens]]** - Microservice authentication

---

**Previous**: [[24-Service-Tokens|← Service Tokens]]
**Next**: [[30-OAuth-Overview|OAuth Overview →]]
