# ObservabilityContext Migration Guide

## Overview

This guide documents the migration of OutlabsAuth routers to use the new **ObservabilityContext** dependency injection pattern for automatic error logging and metrics tracking.

## What Changed

### Before (Old Pattern)
```python
@router.post("/users/")
async def create_user(
    data: UserCreateRequest,
    auth_result = Depends(auth.deps.require_permission("user:create")),
):
    try:
        user = await auth.user_service.create_user(...)
        return user
    except Exception as e:
        # Manual error logging or no logging at all
        raise HTTPException(status_code=400, detail=str(e))
```

### After (New Pattern)
```python
@router.post("/users/")
async def create_user(
    data: UserCreateRequest,
    obs: ObservabilityContext = Depends(
        get_observability_with_auth(
            auth.observability,
            auth.deps.require_permission("user:create"),
        )
    ),
):
    try:
        user = await auth.user_service.create_user(...)
        obs.log_event("user_created", user_id=str(user.id))
        return user
    except HTTPException:
        raise
    except Exception as e:
        obs.log_500_error(e, email=data.email)  # Automatic context capture
        raise HTTPException(
            status_code=500,
            detail="Failed to create user",
        )
```

## Benefits

1. **Automatic Context Capture**: `obs` automatically captures:
   - `endpoint` (e.g., `/v1/users/`)
   - `method` (e.g., `POST`)
   - `user_id` (from auth)
   - `correlation_id` (for request tracing)

2. **Cleaner Code**: No manual context passing or verbose error logging

3. **Consistent Logging**: All errors logged with same structure

4. **Metrics Integration**: Automatic Prometheus metric increments

5. **Stack Traces**: Full stack traces included in error logs

## Migration Status

### ✅ Completed Routers

1. **users.py** - All 8 endpoints migrated
   - `POST /` - Create user
   - `GET /` - List users  
   - `GET /me` - Get current user
   - `PATCH /me` - Update current user
   - `POST /me/change-password` - Change password
   - `GET /{user_id}` - Get user by ID
   - `PATCH /{user_id}` - Update user by ID
   - `DELETE /{user_id}` - Delete user

2. **auth.py** - 4 endpoints migrated
   - `POST /register` - User registration
   - `POST /login` - User login
   - `POST /refresh` - Refresh token
   - `POST /reset-password` - Password reset
   - **Note**: `POST /logout` and `POST /forgot-password` don't need observability (no errors to track)

3. **roles.py** - 1 endpoint migrated (partial)
   - `GET /` - List roles

### 🔄 Pending Routers

- **roles.py** - 6 more endpoints
- **permissions.py** - All endpoints
- **apikeys.py** - All endpoints

## How to Migrate a Router

### Step 1: Add Imports

```python
from outlabs_auth.observability import (
    ObservabilityContext,
    get_observability_with_auth,  # For authenticated endpoints
    get_observability_dependency,  # For public endpoints
)
```

### Step 2: Create Observability Dependency

**For authenticated endpoints:**
```python
# In router factory function, after creating the router
obs: ObservabilityContext = Depends(
    get_observability_with_auth(
        auth.observability,
        auth.deps.require_permission("user:read"),  # Or require_auth()
    )
)
```

**For public endpoints (no auth):**
```python
# Create once at router level
get_obs = get_observability_dependency(auth.observability)

# Then use in endpoint
obs: ObservabilityContext = Depends(get_obs)
```

### Step 3: Update Endpoint Signature

**Before:**
```python
async def create_role(
    data: RoleCreateRequest,
    auth_result = Depends(auth.deps.require_permission("role:create")),
):
```

**After:**
```python
async def create_role(
    data: RoleCreateRequest,
    obs: ObservabilityContext = Depends(
        get_observability_with_auth(
            auth.observability,
            auth.deps.require_permission("role:create"),
        )
    ),
):
```

### Step 4: Update Error Handling

**Before:**
```python
try:
    role = await auth.role_service.create_role(...)
    return role
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

**After:**
```python
try:
    role = await auth.role_service.create_role(...)
    obs.log_event("role_created", role_id=str(role.id))  # Optional success logging
    return role
except HTTPException:
    raise  # Re-raise HTTP exceptions (4xx errors)
except Exception as e:
    obs.log_500_error(e, **extra_context)  # Log 500 errors
    raise HTTPException(
        status_code=500,
        detail="Failed to create role",
    )
```

### Step 5: Add Success Event Logging (Optional)

For important operations, log success events:

```python
obs.log_event("user_created", user_id=str(user.id), email=user.email)
obs.log_event("user_deleted", target_user_id=user_id, deleted_by=obs.user_id)
obs.log_event("password_changed", user_id=obs.user_id)
```

## ObservabilityContext API Reference

### Properties
- `obs.endpoint` - Current endpoint path
- `obs.method` - HTTP method (GET, POST, etc.)
- `obs.user_id` - Authenticated user ID (if available)
- `obs.correlation_id` - Request correlation ID
- `obs.request` - FastAPI Request object
- `obs.observability` - ObservabilityService instance

### Methods

#### `obs.log_500_error(exception, **extra)`
Log a 500 Internal Server Error with full context.

```python
obs.log_500_error(e)
obs.log_500_error(e, email=data.email, role_id=role_id)
```

**Automatically logs:**
- `endpoint`, `method`, `user_id`, `correlation_id`
- `error_class` (exception type)
- `error_message` (exception message)
- `stack_trace` (full traceback)
- Any `**extra` fields you provide

**Increments metric:** `outlabs_auth_500_errors_total{endpoint, error_class}`

#### `obs.log_event(event_name, **fields)`
Log a custom success event.

```python
obs.log_event("user_created", user_id=str(user.id))
obs.log_event("password_changed", user_id=obs.user_id)
```

#### `obs.log_router_error(router, operation, exception, **extra)`
Log a router-level error (for non-500 errors that you still want to track).

```python
obs.log_router_error("users", "create_user", e, email=data.email)
```

#### `obs.log_exception(exception, context, **extra)`
Log any exception with custom context.

```python
obs.log_exception(e, "database query failed", table="users")
```

## Error Handling Best Practices

### 1. Always Re-raise HTTPException

```python
try:
    ...
except HTTPException:
    raise  # Don't log 4xx errors as 500s
except Exception as e:
    obs.log_500_error(e)
    raise HTTPException(500, detail="...")
```

### 2. Provide Contextual Data

```python
# Good - provides debugging context
obs.log_500_error(e, user_id=user_id, role_id=role_id, operation="assign_role")

# Less useful - no extra context
obs.log_500_error(e)
```

### 3. Use Specific Error Messages

```python
# Good - specific error message
raise HTTPException(500, detail="Failed to create user")

# Bad - exposes internal details
raise HTTPException(500, detail=str(e))
```

### 4. Log Success Events for Important Operations

```python
# After successful user creation
obs.log_event("user_created", user_id=str(user.id), created_by=obs.user_id)

# After successful deletion
obs.log_event("user_deleted", target_user_id=user_id, deleted_by=obs.user_id)
```

## Testing the Pattern

### 1. Verify Error Logging

Trigger an error and check logs:

```bash
# View logs in terminal
tail -f /tmp/outlabs-auth.log | grep error

# Should see structured JSON logs with full context
```

### 2. Verify Metrics

Check Prometheus metrics:

```bash
curl http://localhost:8003/metrics | grep 500_errors_total

# Should see:
# outlabs_auth_500_errors_total{endpoint="/v1/users/",error_class="UserAlreadyExistsError"} 1.0
```

### 3. View in Grafana

1. Open http://localhost:3011
2. Go to **Dashboards → OutlabsAuth Overview**
3. Check error panels for data

## Common Patterns

### Pattern 1: Simple CRUD Endpoint

```python
@router.post("/", response_model=RoleResponse)
async def create_role(
    data: RoleCreateRequest,
    obs: ObservabilityContext = Depends(
        get_observability_with_auth(
            auth.observability,
            auth.deps.require_permission("role:create"),
        )
    ),
):
    try:
        role = await auth.role_service.create_role(data)
        obs.log_event("role_created", role_id=str(role.id))
        return role
    except HTTPException:
        raise
    except Exception as e:
        obs.log_500_error(e, role_name=data.name)
        raise HTTPException(500, detail="Failed to create role")
```

### Pattern 2: Public Endpoint (No Auth)

```python
# At router level
get_obs = get_observability_dependency(auth.observability)

@router.post("/register", response_model=UserResponse)
async def register(
    data: RegisterRequest,
    obs: ObservabilityContext = Depends(get_obs),
):
    try:
        user = await auth.user_service.create_user(data)
        obs.log_event("user_registered", user_id=str(user.id))
        return user
    except HTTPException:
        raise
    except Exception as e:
        obs.log_500_error(e, email=data.email)
        raise HTTPException(500, detail="Registration failed")
```

### Pattern 3: Endpoint with Multiple Error Types

```python
@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    data: UserUpdateRequest,
    obs: ObservabilityContext = Depends(...),
):
    try:
        user = await auth.user_service.update_user(user_id, data)
        obs.log_event("user_updated", target_user_id=user_id)
        return user
    except HTTPException:
        raise  # 404 Not Found, 403 Forbidden, etc.
    except ValidationError as e:
        obs.log_router_error("users", "update_user", e, user_id=user_id)
        raise HTTPException(400, detail="Invalid data")
    except Exception as e:
        obs.log_500_error(e, target_user_id=user_id)
        raise HTTPException(500, detail="Failed to update user")
```

## Metrics Generated

All endpoints using ObservabilityContext automatically generate these metrics:

1. **outlabs_auth_500_errors_total**
   - Labels: `endpoint`, `error_class`
   - Description: Total 500 Internal Server Errors

2. **outlabs_auth_errors_total**
   - Labels: `error_type`, `location`
   - Description: Total errors by type and location

3. **outlabs_auth_router_errors_total**
   - Labels: `router`, `operation`
   - Description: Total router-level errors

## Log Events Generated

All errors are logged with this structure:

```json
{
  "timestamp": "2025-11-09T02:01:54.124913Z",
  "level": "error",
  "event": "http_500_internal_server_error",
  "endpoint": "/v1/users/",
  "method": "POST",
  "error_class": "UserAlreadyExistsError",
  "error_message": "User with email admin@test.com already exists",
  "user_id": "690fe8839fcff497004aa683",
  "request_id": null,
  "hostname": "Andrews-MacBook-Pro.local",
  "stack_trace": "Traceback (most recent call last):\n  File ..."
}
```

## Next Steps

1. **Complete Router Migration**
   - Finish `roles.py` (5 more endpoints)
   - Migrate `permissions.py`
   - Migrate `apikeys.py`

2. **Add Service-Level Logging**
   - Add error logging in service layer (`auth.py`, `user.py`, `role.py`, etc.)
   - Use `observability.log_service_error()` for service-level errors

3. **Set Up Alerts**
   - Create Prometheus alerting rules
   - Alert on high error rates
   - Alert on specific error types

4. **Dashboard Improvements**
   - Add more granular error panels
   - Add error rate trends
   - Add error distribution charts

## Troubleshooting

### Logs not appearing in Grafana/Loki
- **Issue**: Promtail can't access log files outside Docker
- **Solution**: Run server in Docker or use terminal logs (`tail -f /tmp/outlabs-auth.log`)

### Metrics not incrementing
- **Issue**: ObservabilityContext not being used
- **Check**: Verify endpoint has `obs: ObservabilityContext = Depends(...)`

### Stack traces not in logs
- **Issue**: `log_stack_traces` config disabled
- **Solution**: Set `log_stack_traces=True` in ObservabilityConfig

## Resources

- **Observability Stack Documentation**: `OBSERVABILITY_STACK.md`
- **Pattern Examples**: `OBSERVABILITY_PATTERN_EXAMPLE.md`
- **Log Events Reference**: `docs-library/99-Log-Events-Reference.md`
- **Metrics Reference**: `docs-library/98-Metrics-Reference.md`

---

**Last Updated**: 2025-01-09  
**Status**: Active Migration  
**Next Review**: After all routers migrated
