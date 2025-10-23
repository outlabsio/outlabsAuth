# JWT Service Tokens

**Tags**: #authentication #service-tokens #microservices #jwt #performance

Long-lived JWT tokens for service-to-service authentication with embedded permissions.

---

## Overview

JWT Service Tokens provide **ultra-fast authentication** (~0.5ms) for service-to-service communication with **zero database hits**. Unlike user JWT tokens, service tokens embed permissions directly in the token payload for instant validation.

**Prerequisites**: [[22-JWT-Tokens|JWT Tokens]]

**Key Features**:
- ⚡ **~0.5ms validation** (vs ~50ms for API keys with DB lookup)
- 🚀 **Zero database hits** (permissions embedded in token)
- 🔒 **Long-lived** (365 days by default)
- 🎯 **Permission-based** (embed exactly what each service needs)
- 🔧 **Service metadata** (environment, version, etc.)

---

## When to Use Service Tokens

### ✅ Use Service Tokens For:

1. **Microservice Communication**
   ```
   API Gateway → Auth Service
   Backend Service → Queue Service
   Worker → Database API
   ```

2. **Internal APIs**
   - Admin dashboards calling internal APIs
   - Background jobs accessing protected endpoints
   - Scheduled tasks making authenticated requests

3. **High-Volume Traffic**
   - Services making 1000s of requests/second
   - Real-time systems needing <1ms auth
   - Event-driven architectures

4. **Trusted Environments**
   - Internal network services
   - Docker containers in same cluster
   - Kubernetes pods in same namespace

### ❌ Don't Use Service Tokens For:

1. **User Authentication** - Use [[22-JWT-Tokens|JWT access tokens]] instead
2. **Third-Party Integrations** - Use [[23-API-Keys|API keys]] instead
3. **Public APIs** - Use API keys with per-user quotas
4. **Frequent Permission Changes** - Permissions are embedded (can't revoke without new token)

---

## Quick Start

### Create a Service Token

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db)

# Create service token
token = auth.service_token_service.create_service_token(
    service_id="analytics-api",
    service_name="Analytics API",
    permissions=["analytics:read", "data:export", "report:generate"],
    expires_days=365,  # 1 year
    metadata={
        "environment": "production",
        "version": "2.0"
    }
)

print(f"Service Token: {token}")
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Use Service Token

```python
from fastapi import FastAPI, Depends, Header
from outlabs_auth import SimpleRBAC

app = FastAPI()
auth = SimpleRBAC(database=db)

@app.get("/internal/analytics")
async def analytics(
    x_service_token: str = Header(...)
):
    """Endpoint protected by service token"""

    # Validate token (~0.5ms, zero DB hits!)
    payload = auth.service_token_service.validate_service_token(x_service_token)

    # Check permission
    if not auth.service_token_service.check_service_permission(
        payload,
        "analytics:read"
    ):
        raise HTTPException(403, "Permission denied")

    # Service authenticated and authorized!
    return {
        "service": payload["service_name"],
        "data": generate_analytics_data()
    }
```

---

## Creating Service Tokens

### Basic Service Token

```python
# Create token with basic info
token = auth.service_token_service.create_service_token(
    service_id="reporting-service",
    service_name="Reporting Service",
    permissions=["report:generate", "data:read"]
)
```

**Token Payload**:
```json
{
  "sub": "reporting-service",
  "type": "service",
  "service_name": "Reporting Service",
  "permissions": ["report:generate", "data:read"],
  "iat": 1642596000,
  "exp": 1674132000
}
```

### Custom Expiration

```python
# Short-lived service token (30 days)
token = auth.service_token_service.create_service_token(
    service_id="temp-worker",
    service_name="Temporary Worker",
    permissions=["job:process"],
    expires_days=30  # 30 days instead of 365
)

# Very long-lived (5 years)
token = auth.service_token_service.create_service_token(
    service_id="core-service",
    service_name="Core Service",
    permissions=["*:*"],  # All permissions
    expires_days=1825  # 5 years
)
```

### With Metadata

```python
# Add custom metadata
token = auth.service_token_service.create_service_token(
    service_id="notification-worker",
    service_name="Notification Worker",
    permissions=["notification:send", "user:read"],
    metadata={
        "environment": "production",
        "version": "3.2.1",
        "region": "us-west-2",
        "deployed_at": "2025-01-23T10:00:00Z",
        "contact": "ops@company.com"
    }
)
```

**Use Case**: Track service version, environment, deployment info for debugging.

---

## Convenience Methods

### API Service Token

```python
# Convenience method for API services
token = auth.service_token_service.create_api_service_token(
    api_name="analytics-api",
    permissions=["analytics:read", "data:export"]
)

# Equivalent to:
# service_id="api-analytics-api"
# service_name="Analytics-Api API"
# metadata={"service_type": "api"}
```

### Worker Service Token

```python
# Convenience method for background workers
token = auth.service_token_service.create_worker_service_token(
    worker_name="email-sender",
    permissions=["email:send", "user:read"]
)

# Equivalent to:
# service_id="worker-email-sender"
# service_name="Email-Sender Worker"
# metadata={"service_type": "worker"}
```

---

## Validating Service Tokens

### Basic Validation

```python
try:
    # Validate token (~0.5ms, zero DB hits!)
    payload = auth.service_token_service.validate_service_token(token)

    print(f"Service ID: {payload['sub']}")
    print(f"Service Name: {payload['service_name']}")
    print(f"Permissions: {payload['permissions']}")
    print(f"Expires: {payload['exp']}")

except TokenInvalidError as e:
    print(f"Invalid token: {e.message}")
```

### Check Specific Permission

```python
# Validate token
payload = auth.service_token_service.validate_service_token(token)

# Check if service has permission
has_permission = auth.service_token_service.check_service_permission(
    payload,
    "report:generate"
)

if has_permission:
    # Service can generate reports
    pass
```

### Get All Permissions

```python
payload = auth.service_token_service.validate_service_token(token)

# Get all permissions
permissions = auth.service_token_service.get_service_permissions(payload)
print(permissions)
# ['analytics:read', 'data:export', 'report:generate']
```

### Get Service Info

```python
payload = auth.service_token_service.validate_service_token(token)

# Get complete service info
info = auth.service_token_service.get_service_info(payload)
print(info)
# {
#   "service_id": "analytics-api",
#   "service_name": "Analytics API",
#   "token_type": "service",
#   "issued_at": 1642596000,
#   "expires_at": 1674132000,
#   "permissions": ["analytics:read", "data:export"],
#   "metadata": {"environment": "production"}
# }
```

### Get Service Metadata

```python
payload = auth.service_token_service.validate_service_token(token)

# Get service metadata
metadata = auth.service_token_service.get_service_metadata(payload)
environment = metadata.get("environment")
version = metadata.get("version")
```

---

## Permission Checking

### Exact Permission Match

```python
payload = auth.service_token_service.validate_service_token(token)

# Check exact permission
if auth.service_token_service.check_service_permission(payload, "report:generate"):
    # Service has report:generate permission
    pass
```

### Wildcard Permissions

```python
# Create token with wildcard permissions
token = auth.service_token_service.create_service_token(
    service_id="admin-service",
    service_name="Admin Service",
    permissions=["report:*", "data:read"]  # All report actions
)

payload = auth.service_token_service.validate_service_token(token)

# These all return True:
auth.service_token_service.check_service_permission(payload, "report:generate")
auth.service_token_service.check_service_permission(payload, "report:export")
auth.service_token_service.check_service_permission(payload, "report:delete")

# This returns True:
auth.service_token_service.check_service_permission(payload, "data:read")

# This returns False:
auth.service_token_service.check_service_permission(payload, "data:write")
```

### Full Wildcard

```python
# Create super-admin service token
token = auth.service_token_service.create_service_token(
    service_id="super-service",
    service_name="Super Admin Service",
    permissions=["*:*"]  # All permissions!
)

payload = auth.service_token_service.validate_service_token(token)

# Any permission check returns True:
auth.service_token_service.check_service_permission(payload, "anything:anywhere")
```

---

## FastAPI Integration

### Using Service Tokens in Routes

```python
from fastapi import FastAPI, Depends, Header, HTTPException
from outlabs_auth import SimpleRBAC
from outlabs_auth.core.exceptions import TokenInvalidError

app = FastAPI()
auth = SimpleRBAC(database=db)

async def validate_service_token(
    x_service_token: str = Header(..., description="Service JWT token")
) -> dict:
    """Dependency to validate service token"""
    try:
        payload = auth.service_token_service.validate_service_token(x_service_token)
        return payload
    except TokenInvalidError:
        raise HTTPException(401, "Invalid service token")

async def require_service_permission(permission: str):
    """Dependency to check service permission"""
    async def dependency(
        service = Depends(validate_service_token)
    ):
        if not auth.service_token_service.check_service_permission(service, permission):
            raise HTTPException(403, f"Service lacks permission: {permission}")
        return service
    return dependency

# Use in routes
@app.get("/internal/analytics")
async def analytics(
    service = Depends(require_service_permission("analytics:read"))
):
    """Only services with analytics:read permission"""
    return {
        "service": service["service_name"],
        "data": generate_analytics_data()
    }

@app.post("/internal/reports")
async def generate_report(
    service = Depends(require_service_permission("report:generate"))
):
    """Only services with report:generate permission"""
    return {
        "service": service["service_name"],
        "report": create_report()
    }
```

### Multi-Auth Endpoints

```python
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.authentication import (
    AuthBackend,
    BearerTransport,
    JWTStrategy,
    ServiceTokenStrategy
)

# Configure backends
jwt_backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret=SECRET_KEY)
)

service_backend = AuthBackend(
    name="service",
    transport=BearerTransport(token_header="X-Service-Token"),
    strategy=ServiceTokenStrategy(secret=SECRET_KEY)
)

# Create deps with both backends
deps = AuthDeps(backends=[jwt_backend, service_backend])

# Route accepts both user JWT and service tokens!
@app.get("/api/data")
async def get_data(
    auth = Depends(deps.require_auth())
):
    """Works with user JWT OR service token"""
    if auth["source"] == "jwt":
        # User authentication
        user = auth["user"]
        return {"user": user.email, "data": get_user_data(user)}
    elif auth["source"] == "service":
        # Service authentication
        service_name = auth["metadata"]["service_name"]
        return {"service": service_name, "data": get_all_data()}
```

---

## Use Cases & Examples

### Use Case 1: Microservice Communication

```python
# Service A (API Gateway) calling Service B (Auth Service)

# In Service A:
import httpx

# Use service token for authentication
SERVICE_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

async def call_auth_service():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://auth-service:8000/internal/validate",
            headers={"X-Service-Token": SERVICE_TOKEN}
        )
        return response.json()

# In Service B (Auth Service):
@app.get("/internal/validate")
async def validate(
    service = Depends(validate_service_token)
):
    return {"valid": True, "service": service["service_name"]}
```

### Use Case 2: Background Workers

```python
# Create worker token
worker_token = auth.service_token_service.create_worker_service_token(
    worker_name="notification-sender",
    permissions=["notification:send", "user:read", "email:send"],
    expires_days=180  # 6 months
)

# Store in worker environment
# WORKER_SERVICE_TOKEN=eyJhbGci...

# In worker code:
import os
import httpx

SERVICE_TOKEN = os.getenv("WORKER_SERVICE_TOKEN")

async def send_notification(user_id: str, message: str):
    """Worker sends notification via API"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://api:8000/notifications/send",
            headers={"X-Service-Token": SERVICE_TOKEN},
            json={"user_id": user_id, "message": message}
        )
        return response.json()
```

### Use Case 3: Admin Dashboard (Internal)

```python
# Create admin dashboard service token
admin_token = auth.service_token_service.create_service_token(
    service_id="admin-dashboard",
    service_name="Admin Dashboard",
    permissions=["user:*", "role:*", "report:*", "analytics:*"],
    expires_days=90,  # Rotate every 3 months
    metadata={
        "environment": "production",
        "contact": "admin@company.com"
    }
)

# Admin dashboard uses this token for all API calls
# No user authentication needed for internal admin tools
```

### Use Case 4: Scheduled Jobs

```python
# Create token for scheduled job
job_token = auth.service_token_service.create_service_token(
    service_id="daily-report-job",
    service_name="Daily Report Generator",
    permissions=["report:generate", "data:read", "email:send"],
    expires_days=365
)

# In scheduled job (cron):
import httpx

async def generate_daily_report():
    """Runs daily at 9am"""
    async with httpx.AsyncClient() as client:
        # Authenticate with service token
        response = await client.post(
            "http://api:8000/reports/daily",
            headers={"X-Service-Token": job_token}
        )
        return response.json()
```

### Use Case 5: Event-Driven Architecture

```python
# Event publisher service
publisher_token = auth.service_token_service.create_service_token(
    service_id="event-publisher",
    service_name="Event Publisher",
    permissions=["event:publish"],
    expires_days=365
)

# Event consumer service
consumer_token = auth.service_token_service.create_service_token(
    service_id="event-consumer",
    service_name="Event Consumer",
    permissions=["event:consume", "data:write"],
    expires_days=365
)

# Each service authenticates with its own token
# Fast validation, no shared database lookups
```

---

## Performance Comparison

### Service Tokens vs API Keys

| Metric | Service Tokens | API Keys |
|--------|----------------|----------|
| **Validation Time** | ~0.5ms | ~50ms |
| **Database Hits** | 0 | 2-3 |
| **Permission Check** | Embedded (instant) | DB lookup |
| **Suitable For** | High-volume internal | Third-party external |
| **Revocation** | Recreate token | Update DB |
| **Rate Limiting** | Application-level | Built-in |

**Benchmark** (1000 validations):
```python
# Service Tokens: ~500ms total (0.5ms each)
# API Keys: ~50,000ms total (50ms each)
# Service tokens are 100x faster!
```

### Why So Fast?

1. **No Database Lookups**
   - Permissions embedded in token
   - No user fetch required
   - No API key hash comparison

2. **Pure JWT Validation**
   - Verify signature
   - Check expiration
   - Read payload
   - Done!

3. **In-Memory Operation**
   - No network calls
   - No database queries
   - CPU-only validation

---

## Security Considerations

### Storage

**✅ Secure Storage**:
```python
# Environment variables (Docker, Kubernetes)
SERVICE_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Kubernetes secrets
kubectl create secret generic service-token --from-literal=token=eyJhbGci...

# Docker secrets
docker secret create service_token token.txt
```

**❌ Insecure Storage**:
```python
# Never hardcode in source code!
SERVICE_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # ❌

# Never commit to git!
# Never log token values!
```

### Rotation

```python
# Rotate service tokens periodically
OLD_TOKEN = os.getenv("SERVICE_TOKEN")
NEW_TOKEN = auth.service_token_service.create_service_token(
    service_id="analytics-api",
    service_name="Analytics API",
    permissions=["analytics:read", "data:export"],
    expires_days=365
)

# Deploy new token to all services
# Remove old token from environment
```

**Best Practices**:
- Rotate every 90-180 days for production
- Rotate immediately if compromised
- Use different tokens per service
- Track token metadata (version, deployment date)

### Least Privilege

```python
# Good: Minimal permissions
worker_token = auth.service_token_service.create_service_token(
    service_id="email-worker",
    service_name="Email Worker",
    permissions=["email:send", "user:read"]  # Only what's needed
)

# Bad: Excessive permissions
admin_token = auth.service_token_service.create_service_token(
    service_id="email-worker",
    service_name="Email Worker",
    permissions=["*:*"]  # ❌ Too much!
)
```

### Network Isolation

**Best Practice**: Use service tokens only in trusted environments:
- Internal Docker networks
- Kubernetes cluster networking
- VPC private subnets
- Behind API gateway

**Don't Use** service tokens for:
- Public APIs
- Third-party integrations
- Customer-facing services
- Untrusted networks

---

## Limitations

### 1. Cannot Revoke Individual Tokens

**Issue**: Service tokens are stateless (no DB). Once issued, valid until expiration.

**Solution**:
```python
# Option 1: Short expiration
token = auth.service_token_service.create_service_token(
    service_id="temp-service",
    permissions=["data:read"],
    expires_days=7  # Expires in 1 week
)

# Option 2: Rotate secret key (revokes ALL tokens)
# Update SECRET_KEY in config
# Reissue all service tokens

# Option 3: Use API keys instead (can revoke individually)
```

### 2. Permissions Can't Change Without New Token

**Issue**: Permissions embedded in token. Can't update without reissuing.

**Solution**:
```python
# Create new token with updated permissions
new_token = auth.service_token_service.create_service_token(
    service_id="analytics-api",
    service_name="Analytics API",
    permissions=["analytics:read", "analytics:write", "data:export"],  # Added write
    expires_days=365
)

# Deploy new token to service
# Old token still valid until expiration
```

### 3. No Rate Limiting

**Issue**: Service tokens don't have built-in rate limiting like API keys.

**Solution**:
```python
# Implement application-level rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/internal/analytics")
@limiter.limit("100/minute")
async def analytics(
    service = Depends(validate_service_token)
):
    return generate_analytics()
```

---

## Best Practices

### 1. One Token Per Service

```python
# Good: Each service has its own token
analytics_token = auth.service_token_service.create_service_token(
    service_id="analytics-api",
    permissions=["analytics:read", "data:export"]
)

reporting_token = auth.service_token_service.create_service_token(
    service_id="reporting-api",
    permissions=["report:generate"]
)

# Bad: Sharing tokens between services ❌
```

### 2. Include Metadata

```python
# Always include useful metadata
token = auth.service_token_service.create_service_token(
    service_id="worker-email",
    service_name="Email Worker",
    permissions=["email:send"],
    metadata={
        "version": "2.1.0",
        "environment": "production",
        "deployed_at": "2025-01-23",
        "contact": "ops@company.com",
        "region": "us-west-2"
    }
)
```

### 3. Log Service Activity

```python
@app.get("/internal/data")
async def get_data(
    service = Depends(validate_service_token)
):
    # Log service access
    logger.info(
        f"Service access: {service['service_name']} "
        f"(ID: {service['sub']}) "
        f"Environment: {service.get('metadata', {}).get('environment')}"
    )

    return {"data": "..."}
```

### 4. Monitor Token Expiration

```python
# Check expiration before it happens
payload = auth.service_token_service.validate_service_token(token)

expires_at = datetime.fromtimestamp(payload["exp"])
days_until_expiration = (expires_at - datetime.now()).days

if days_until_expiration < 30:
    logger.warning(
        f"Service token expires in {days_until_expiration} days! "
        f"Service: {payload['service_name']}"
    )
```

### 5. Test Service Authentication

```python
import pytest

@pytest.mark.asyncio
async def test_service_token_authentication():
    """Test service token validation"""

    # Create token
    token = auth.service_token_service.create_service_token(
        service_id="test-service",
        service_name="Test Service",
        permissions=["test:read"]
    )

    # Validate token
    payload = auth.service_token_service.validate_service_token(token)

    assert payload["sub"] == "test-service"
    assert payload["service_name"] == "Test Service"
    assert "test:read" in payload["permissions"]

    # Check permission
    assert auth.service_token_service.check_service_permission(
        payload,
        "test:read"
    )
```

---

## Troubleshooting

### Issue 1: Token Invalid

```python
try:
    payload = auth.service_token_service.validate_service_token(token)
except TokenInvalidError as e:
    print(f"Error: {e.message}")
    print(f"Details: {e.details}")
```

**Common Causes**:
- Token expired (check `exp` claim)
- Wrong secret key (service using different config)
- Token corrupted (network transmission issue)
- Not a service token (wrong token type)

### Issue 2: Permission Denied

```python
payload = auth.service_token_service.validate_service_token(token)

if not auth.service_token_service.check_service_permission(payload, "data:write"):
    # Service doesn't have permission
    permissions = auth.service_token_service.get_service_permissions(payload)
    print(f"Service has: {permissions}")
    print(f"Service needs: data:write")
```

**Solution**: Reissue token with correct permissions.

### Issue 3: Token Expired

```python
try:
    payload = auth.service_token_service.validate_service_token(token)
except TokenInvalidError as e:
    if e.details.get("expired"):
        # Token expired - need to reissue
        print("Service token expired. Please reissue.")
```

**Solution**: Create new token and redeploy.

---

## Next Steps

- **[[25-Multi-Source-Auth|Multi-Source Authentication]]** - Combine JWT, API keys, and service tokens
- **[[22-JWT-Tokens|JWT Tokens]]** - User access tokens
- **[[23-API-Keys|API Keys]]** - Third-party authentication
- **[[80-Auth-Dependencies|AuthDeps]]** - FastAPI dependency injection

---

**Previous**: [[23-API-Keys|← API Keys]]
**Next**: [[25-Multi-Source-Auth|Multi-Source Authentication →]]
