# Observability Dependency Injection Pattern

## Overview

We've implemented a FastAPI dependency injection pattern for observability that automatically captures request context and provides clean error logging utilities.

## New Components

### 1. ObservabilityContext
A context object with request information and logging helpers, automatically injected into routes.

### 2. ObservabilityDeps
Dependency factory similar to `AuthDeps`, provides clean API for creating observability dependencies.

### 3. Error Logging Methods
- `log_500_error()` - Log 500 errors with full context
- `log_router_error()` - Log router-level errors
- `log_error()` - Log custom errors
- `log_exception()` - Log any exception with stack trace

## New Metrics

- `outlabs_auth_errors_total{error_type, location}` - Total errors by type
- `outlabs_auth_500_errors_total{endpoint, error_class}` - HTTP 500 errors
- `outlabs_auth_router_errors_total{router, endpoint}` - Router errors
- `outlabs_auth_service_errors_total{service, operation}` - Service errors

## Usage Patterns

### Pattern 1: Simple Error Logging (No Auth Required)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from outlabs_auth.observability import ObservabilityContext, get_observability_dependency

def create_public_router(auth):
    router = APIRouter()
    
    # Create the dependency
    get_obs = get_observability_dependency(auth.observability)
    
    @router.get("/health")
    async def health_check(obs: ObservabilityContext = Depends(get_obs)):
        try:
            # Your logic here
            db_status = await check_database()
            return {"status": "healthy"}
        except Exception as e:
            # Automatic logging with endpoint, method, correlation_id
            obs.log_500_error(e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    return router
```

**What you get automatically:**
- ✅ Endpoint path (`/health`)
- ✅ HTTP method (`GET`)
- ✅ Correlation ID (from middleware)
- ✅ Stack trace (configurable)
- ✅ Prometheus metric incremented (`outlabs_auth_500_errors_total`)

### Pattern 2: With Authentication (User Context)

```python
from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth

def get_users_router(auth):
    router = APIRouter()
    
    # Combine auth + observability
    get_obs_with_auth = get_observability_with_auth(
        auth.observability,
        auth.deps.require_auth()
    )
    
    @router.get("/me")
    async def get_me(obs: ObservabilityContext = Depends(get_obs_with_auth)):
        try:
            # obs.user_id is automatically populated from auth!
            user = await get_user(obs.user_id)
            return user
        except Exception as e:
            obs.log_500_error(e)  # Includes user_id automatically
            raise HTTPException(500, detail=str(e))
    
    return router
```

**What you get automatically:**
- ✅ Everything from Pattern 1
- ✅ User ID (from auth result)
- ✅ User context in logs

### Pattern 3: With Permission Check

```python
from outlabs_auth.observability import ObservabilityDeps

def get_users_router(auth):
    router = APIRouter()
    
    # Use ObservabilityDeps for cleaner API
    obs_deps = ObservabilityDeps(auth.observability, auth.deps)
    
    @router.get("/")
    async def list_users(
        page: int = Query(1, ge=1),
        obs: ObservabilityContext = Depends(obs_deps.with_permission("user:read"))
    ):
        try:
            users = await auth.user_service.list_users(page=page, limit=20)
            return users
        except Exception as e:
            # Log with full context
            obs.log_router_error(
                router="users",
                operation="list_users",
                exception=e
            )
            raise HTTPException(500, detail=str(e))
    
    return router
```

**What you get automatically:**
- ✅ Everything from Pattern 2
- ✅ Permission enforcement (`user:read`)
- ✅ Router-specific error tracking

### Pattern 4: Granular Error Logging

```python
@router.post("/")
async def create_user(
    data: UserCreateRequest,
    obs: ObservabilityContext = Depends(obs_deps.with_permission("user:create"))
):
    try:
        # Validate input
        if not data.email:
            obs.log_error("validation_error", "Email is required")
            raise HTTPException(400, detail="Email is required")
        
        # Create user
        user = await auth.user_service.create_user(**data.dict())
        
        return user
        
    except ValueError as e:
        # Log specific error type
        obs.log_router_error("users", "create_user", e, error_category="validation")
        raise HTTPException(400, detail=str(e))
        
    except Exception as e:
        # Log unexpected errors
        obs.log_500_error(e, custom_field="extra_context")
        raise HTTPException(500, detail=str(e))
```

## Old Pattern (Manual Logging)

### ❌ Before: Verbose and Error-Prone

```python
@router.get("/users")
async def list_users(
    auth_result = Depends(auth.deps.require_permission("user:read"))
):
    try:
        users = await get_users()
        return users
    except Exception as e:
        # Manually build context
        import traceback
        if auth.observability:
            auth.observability.logger.error(
                "list_users_error",
                endpoint="/v1/users",  # Hard-coded!
                method="GET",  # Hard-coded!
                user_id=auth_result.get("user_id"),
                error_type=type(e).__name__,
                error_message=str(e),
                traceback=traceback.format_exc()
            )
        raise HTTPException(500, detail=str(e))
```

**Problems:**
- ❌ Endpoint path hard-coded
- ❌ HTTP method hard-coded
- ❌ No correlation ID
- ❌ Verbose and repetitive
- ❌ Easy to forget fields
- ❌ No automatic metrics

## New Pattern (Dependency Injection)

### ✅ After: Clean and Automatic

```python
@router.get("/users")
async def list_users(
    obs: ObservabilityContext = Depends(obs_deps.with_permission("user:read"))
):
    try:
        users = await get_users()
        return users
    except Exception as e:
        obs.log_500_error(e)  # One line!
        raise HTTPException(500, detail=str(e))
```

**Benefits:**
- ✅ Endpoint path automatic (from request)
- ✅ HTTP method automatic (from request)
- ✅ Correlation ID automatic (from middleware)
- ✅ User ID automatic (from auth)
- ✅ Clean and concise
- ✅ Type-safe with IDE autocomplete
- ✅ Automatic Prometheus metrics

## Log Output Example

### Development (Text Format)

```
2025-01-26 10:15:23 [ERROR] http_500_internal_server_error
  endpoint: /v1/users
  error_class: DatabaseConnectionError
  error_message: Unable to connect to MongoDB
  method: GET
  user_id: 507f1f77bcf86cd799439011
  request_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  stack_trace: Traceback (most recent call last):
    File "/app/routers/users.py", line 45, in list_users
      users = await get_users()
    ...
```

### Production (JSON Format)

```json
{
  "timestamp": "2025-01-26T10:15:23.456Z",
  "level": "error",
  "event": "http_500_internal_server_error",
  "endpoint": "/v1/users",
  "error_class": "DatabaseConnectionError",
  "error_message": "Unable to connect to MongoDB",
  "method": "GET",
  "user_id": "507f1f77bcf86cd799439011",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "hostname": "api-server-1"
}
```

## Prometheus Metrics

### Error Rate by Endpoint

```promql
# 500 errors per second by endpoint
rate(outlabs_auth_500_errors_total[5m])

# Top endpoints with errors
topk(5, sum by (endpoint) (rate(outlabs_auth_500_errors_total[1h])))
```

### Error Rate by Type

```promql
# Errors by exception class
sum by (error_type) (rate(outlabs_auth_errors_total[5m]))

# Database errors specifically
rate(outlabs_auth_errors_total{error_type=~".*Database.*"}[5m])
```

### Router Health

```promql
# Error rate per router
sum by (router) (rate(outlabs_auth_router_errors_total[5m]))

# Endpoints with highest error rates
topk(10, rate(outlabs_auth_router_errors_total[5m]))
```

## Grafana Dashboard Queries

### Panel 1: 500 Error Rate

```promql
sum(rate(outlabs_auth_500_errors_total[5m])) * 60
```

### Panel 2: Top Error Types

```promql
topk(10, sum by (error_type) (increase(outlabs_auth_errors_total[1h])))
```

### Panel 3: Errors by Endpoint (Heatmap)

```promql
sum by (endpoint) (increase(outlabs_auth_500_errors_total[5m]))
```

## Migration Guide

### Step 1: Add Dependency to Router

```python
from outlabs_auth.observability import ObservabilityDeps

def get_my_router(auth):
    router = APIRouter()
    obs_deps = ObservabilityDeps(auth.observability, auth.deps)
    
    # ... routes below
```

### Step 2: Update Route Signatures

**Before:**
```python
@router.get("/")
async def list_items(auth_result = Depends(auth.deps.require_auth())):
```

**After:**
```python
@router.get("/")
async def list_items(obs = Depends(obs_deps.with_auth())):
```

### Step 3: Replace Manual Error Logging

**Before:**
```python
except Exception as e:
    if auth.observability:
        auth.observability.logger.error(...)
    raise HTTPException(500, detail=str(e))
```

**After:**
```python
except Exception as e:
    obs.log_500_error(e)
    raise HTTPException(500, detail=str(e))
```

## Configuration

### Enable Stack Traces (Development)

```python
ObservabilityConfig(
    logs_format="text",
    logs_level="DEBUG",
    log_stack_traces=True,  # Full traces in dev
)
```

### Disable Stack Traces (Production)

```python
ObservabilityConfig(
    logs_format="json",
    logs_level="INFO",
    log_stack_traces=False,  # Cleaner logs in prod
)
```

## Best Practices

### 1. Use the Right Dependency

- Public endpoints → `obs_deps.get_context()`
- Authenticated → `obs_deps.with_auth()`
- Permission-based → `obs_deps.with_permission("resource:action")`

### 2. Log at the Right Level

- `obs.log_500_error()` → Unexpected server errors
- `obs.log_router_error()` → Router-specific errors
- `obs.log_error()` → Custom application errors
- `obs.log_exception()` → Generic exception logging

### 3. Add Context Where Useful

```python
obs.log_500_error(
    e,
    resource_id=resource_id,
    operation="create",
    additional_context="value"
)
```

### 4. Don't Log Expected Errors as 500s

```python
# ❌ Bad - validation errors aren't 500s
except ValueError as e:
    obs.log_500_error(e)
    raise HTTPException(400, detail=str(e))

# ✅ Good - use appropriate log level
except ValueError as e:
    obs.log_error("validation_error", str(e))
    raise HTTPException(400, detail=str(e))
```

## Next Steps

1. ✅ ObservabilityService has error logging methods
2. ✅ ObservabilityDeps pattern implemented
3. ✅ ObservabilityContext provides clean API
4. ⏳ Update routers to use new pattern
5. ⏳ Update documentation
6. ⏳ Add Grafana dashboard panels

## Testing

```python
from outlabs_auth.observability import ObservabilityContext

async def test_error_logging(test_client, observability_service):
    # ObservabilityContext is easily mockable
    mock_obs = Mock(spec=ObservabilityContext)
    
    # Test your route
    response = await test_client.get("/users")
    
    # Verify error was logged
    mock_obs.log_500_error.assert_called_once()
```

---

**Summary:** The new dependency injection pattern makes error logging automatic, consistent, and type-safe while reducing boilerplate by ~80%.
