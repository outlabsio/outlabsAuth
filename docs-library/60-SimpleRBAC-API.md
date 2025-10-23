# SimpleRBAC API Reference

**Complete API reference for the SimpleRBAC preset**

---

## Table of Contents

- [Overview](#overview)
- [Initialization](#initialization)
- [Configuration Options](#configuration-options)
- [Available Services](#available-services)
- [Core Methods](#core-methods)
- [Complete API Example](#complete-api-example)
- [Differences from EnterpriseRBAC](#differences-from-enterpriserbac)
- [Migration to EnterpriseRBAC](#migration-to-enterpriserbac)
- [See Also](#see-also)

---

## Overview

**SimpleRBAC** is a thin wrapper around `OutlabsAuth` that provides a flat role-based access control system without entity hierarchies.

### When to Use

Use SimpleRBAC for:
- ✅ Small to medium applications
- ✅ Flat organizational structure (no departments/teams)
- ✅ Global role assignments (user → role)
- ✅ Simple permission model
- ✅ SaaS tools, blogs, APIs, personal projects

**Don't use if you need:**
- ❌ Departments, teams, or organizational hierarchy
- ❌ Entity-scoped permissions
- ❌ Tree permissions (hierarchical inheritance)
- ❌ Users with different roles in different entities

### What's Disabled

SimpleRBAC **forces** these features off:
- Entity hierarchy (`enable_entity_hierarchy=False`)
- Context-aware roles (`enable_context_aware_roles=False`)
- ABAC conditions (`enable_abac=False`)

---

## Initialization

### Basic Initialization

```python
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC

# Initialize FastAPI
app = FastAPI()

# Initialize MongoDB
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["my_database"]

# Initialize SimpleRBAC
auth = SimpleRBAC(
    database=db,
    secret_key="your-secret-key-change-in-production"
)

# Initialize database collections and indexes
@app.on_event("startup")
async def startup():
    await auth.initialize()
    print("✓ Auth system initialized")

@app.on_event("shutdown")
async def shutdown():
    mongo_client.close()
```

### With All Options

```python
auth = SimpleRBAC(
    # Required
    database=db,
    secret_key="your-secret-key-here",

    # JWT configuration
    algorithm="HS256",
    access_token_expire_minutes=15,
    refresh_token_expire_days=30,

    # Password requirements
    password_min_length=8,
    require_special_char=True,
    require_uppercase=True,
    require_digit=True,

    # Security
    max_login_attempts=5,
    lockout_duration_minutes=30,

    # API Keys
    api_key_prefix_length=12,
    api_key_rate_limit_per_minute=60,
    api_key_temporary_lock_minutes=30,

    # Optional features
    enable_caching=True,  # Redis caching
    redis_url="redis://localhost:6379",
    cache_ttl_seconds=300,
    enable_notifications=True,
    notification_service=notification_service,

    # Multi-tenant (optional)
    multi_tenant=False,

    # Model customization (advanced)
    user_model=CustomUserModel,  # Optional
    role_model=CustomRoleModel,  # Optional
)
```

---

## Configuration Options

### Required Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `database` | `AsyncIOMotorDatabase` | **Required** | MongoDB database instance |
| `secret_key` | `str` | **Required** | JWT signing key (keep secure!) |

### JWT Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algorithm` | `str` | `"HS256"` | JWT signing algorithm |
| `access_token_expire_minutes` | `int` | `15` | Access token lifetime (minutes) |
| `refresh_token_expire_days` | `int` | `30` | Refresh token lifetime (days) |

### Password Requirements

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `password_min_length` | `int` | `8` | Minimum password length |
| `require_special_char` | `bool` | `True` | Require special character |
| `require_uppercase` | `bool` | `True` | Require uppercase letter |
| `require_digit` | `bool` | `True` | Require digit |

### Security Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_login_attempts` | `int` | `5` | Max failed login attempts before lockout |
| `lockout_duration_minutes` | `int` | `30` | Account lockout duration |

### API Key Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key_prefix_length` | `int` | `12` | API key prefix length |
| `api_key_rate_limit_per_minute` | `int` | `60` | Rate limit per minute |
| `api_key_temporary_lock_minutes` | `int` | `30` | Lock duration after failures |

### Optional Features

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_caching` | `bool` | `False` | Enable Redis caching |
| `redis_url` | `str` | `None` | Redis connection URL (required if caching enabled) |
| `cache_ttl_seconds` | `int` | `300` | Cache TTL (5 minutes) |
| `enable_notifications` | `bool` | `False` | Enable notification system |
| `notification_service` | `NotificationService` | `None` | Notification service instance |
| `multi_tenant` | `bool` | `False` | Multi-tenant isolation |

### Model Customization (Advanced)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_model` | `Type[UserModel]` | `UserModel` | Custom user model class |
| `role_model` | `Type[RoleModel]` | `RoleModel` | Custom role model class |
| `permission_model` | `Type[PermissionModel]` | `PermissionModel` | Custom permission model class |

---

## Available Services

SimpleRBAC provides access to these services:

### 1. AuthService

**Authentication operations** (login, logout, token refresh).

```python
# Access
auth.auth_service

# Methods
await auth.auth_service.login(email, password)
await auth.auth_service.logout(refresh_token)
await auth.auth_service.refresh_access_token(refresh_token)
await auth.auth_service.get_current_user(access_token)
await auth.auth_service.revoke_all_user_tokens(user_id)
```

**See:** [74-Auth-Service.md](74-Auth-Service.md)

### 2. UserService

**User management** with lifecycle hooks.

```python
# Access
auth.user_service

# Methods
await auth.user_service.create_user(email, password, **kwargs)
await auth.user_service.get_user(user_id)
await auth.user_service.update_user(user_id, update_dict)
await auth.user_service.delete_user(user_id)

# Lifecycle hooks (override in custom service)
await auth.user_service.on_after_register(user, request)
await auth.user_service.on_after_login(user, request, response)
await auth.user_service.on_before_delete(user, request)
```

**See:** [70-User-Service.md](70-User-Service.md), [131-User-Hooks.md](131-User-Hooks.md)

### 3. RoleService

**Role management**.

```python
# Access
auth.role_service

# Methods
await auth.role_service.create_role(name, display_name, permissions)
await auth.role_service.get_role(role_id)
await auth.role_service.update_role(role_id, **updates)
await auth.role_service.delete_role(role_id)
await auth.role_service.assign_role(user_id, role_id)
await auth.role_service.remove_role(user_id, role_id)
await auth.role_service.get_user_roles(user_id)
```

**See:** [71-Role-Service.md](71-Role-Service.md)

### 4. PermissionService (BasicPermissionService)

**Permission checking** (flat structure).

```python
# Access
auth.permission_service

# Methods
await auth.permission_service.check_permission(user_id, permission)
await auth.permission_service.get_user_permissions(user_id)
await auth.permission_service.require_permission(user_id, permission)
await auth.permission_service.require_any_permission(user_id, permissions)
await auth.permission_service.require_all_permissions(user_id, permissions)

# Permission CRUD
await auth.permission_service.create_permission(name, display_name, description)
await auth.permission_service.get_permission_by_name(name)
await auth.permission_service.list_permissions(page, limit, resource)
await auth.permission_service.delete_permission(permission_id)
```

**See:** [72-Permission-Service.md](72-Permission-Service.md)

### 5. ApiKeyService

**API key management**.

```python
# Access
auth.api_key_service

# Methods
await auth.api_key_service.create_api_key(user_id, name, scopes)
await auth.api_key_service.verify_api_key(api_key_string)
await auth.api_key_service.list_user_api_keys(user_id)
await auth.api_key_service.revoke_api_key(key_id)
```

**See:** [73-API-Key-Service.md](73-API-Key-Service.md), [23-API-Keys.md](23-API-Keys.md)

### 6. ServiceTokenService

**JWT service tokens** for service-to-service auth (v1.4).

```python
# Access
auth.service_token_service

# Methods
token = auth.service_token_service.create_service_token(service_id, service_name)
service_info = auth.service_token_service.verify_service_token(token)
```

**See:** [24-Service-Tokens.md](24-Service-Tokens.md)

### 7. NotificationService (Optional)

**Notification coordinator** (if enabled).

```python
# Access
auth.notification_service  # None if not enabled

# Methods
await auth.notification_service.emit(event_type, data, metadata)
```

**See:** [140-Notification-System.md](140-Notification-System.md)

### Services NOT Available in SimpleRBAC

These services are **only available in EnterpriseRBAC**:
- ❌ `entity_service` (no entity hierarchy)
- ❌ `membership_service` (no entity memberships)
- ❌ `EnterprisePermissionService` (uses BasicPermissionService instead)

---

## Core Methods

### initialize()

Initialize database collections and indexes.

```python
async def initialize() -> None
```

**Usage:**
```python
@app.on_event("startup")
async def startup():
    await auth.initialize()
```

**What it does:**
- Initializes Beanie ODM
- Creates database indexes
- Sets up collections

**Must be called** before using any auth operations.

---

### get_current_user()

Get user from JWT access token.

```python
async def get_current_user(access_token: str) -> UserModel
```

**Parameters:**
- `access_token` (str): JWT access token

**Returns:**
- `UserModel`: Authenticated user

**Raises:**
- `TokenExpiredError`: Token expired
- `TokenInvalidError`: Invalid token
- `UserNotFoundError`: User doesn't exist

**Usage:**
```python
# Manual usage
user = await auth.get_current_user(access_token)

# In FastAPI route (recommended)
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

@app.get("/me")
async def get_me(user = Depends(deps.authenticated())):
    return user
```

---

### verify_password()

Verify plain password against hashed password.

```python
def verify_password(plain_password: str, hashed_password: str) -> bool
```

**Parameters:**
- `plain_password` (str): Plain text password
- `hashed_password` (str): Hashed password from database

**Returns:**
- `bool`: True if password matches

**Usage:**
```python
if auth.verify_password("MyPassword123!", user.hashed_password):
    print("Password correct")
```

---

### hash_password()

Hash a plain password.

```python
def hash_password(password: str) -> str
```

**Parameters:**
- `password` (str): Plain text password

**Returns:**
- `str`: Hashed password (argon2id)

**Usage:**
```python
hashed = auth.hash_password("SecurePassword123!")
```

---

## Complete API Example

### Full Application

```python
from fastapi import FastAPI, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.schemas.auth import LoginRequest, RegisterRequest

# ============================================================================
# 1. Initialize FastAPI
# ============================================================================

app = FastAPI(title="My API with SimpleRBAC")

# ============================================================================
# 2. Initialize MongoDB
# ============================================================================

mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["my_app_db"]

# ============================================================================
# 3. Initialize SimpleRBAC
# ============================================================================

auth = SimpleRBAC(
    database=db,
    secret_key="your-secret-key-here",
    access_token_expire_minutes=15,
    refresh_token_expire_days=30,
    password_min_length=8,
    max_login_attempts=5,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# ============================================================================
# 4. Startup/Shutdown
# ============================================================================

@app.on_event("startup")
async def startup():
    await auth.initialize()
    print("✓ Auth initialized")

@app.on_event("shutdown")
async def shutdown():
    mongo_client.close()

# ============================================================================
# 5. Create Dependencies
# ============================================================================

deps = AuthDeps(auth)

# ============================================================================
# 6. Authentication Routes
# ============================================================================

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest):
    """Register new user."""
    user = await auth.user_service.create_user(
        email=data.email,
        password=data.password,
        first_name=data.first_name,
        last_name=data.last_name
    )
    return {"message": "User created", "user_id": str(user.id)}

@app.post("/auth/login")
async def login(data: LoginRequest):
    """Login and get JWT tokens."""
    user, tokens = await auth.auth_service.login(
        email=data.email,
        password=data.password
    )
    return tokens.to_dict()

@app.post("/auth/refresh")
async def refresh(refresh_token: str):
    """Refresh access token."""
    tokens = await auth.auth_service.refresh_access_token(refresh_token)
    return tokens.to_dict()

@app.post("/auth/logout")
async def logout(user = Depends(deps.authenticated())):
    """Logout (invalidate all sessions)."""
    await auth.auth_service.revoke_all_user_tokens(str(user.id))
    return {"message": "Logged out"}

# ============================================================================
# 7. Protected Routes
# ============================================================================

@app.get("/me")
async def get_me(user = Depends(deps.authenticated())):
    """Get current user profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "profile": user.profile.model_dump()
    }

@app.get("/admin/users")
async def list_users(user = Depends(deps.requires("user:read"))):
    """List all users (requires user:read permission)."""
    # Only users with "user:read" permission can access
    users = await auth.user_service.list_users()
    return {"users": users}

@app.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    user = Depends(deps.requires("user:delete"))
):
    """Delete user (requires user:delete permission)."""
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}

# ============================================================================
# 8. Role Management (Admin Only)
# ============================================================================

@app.post("/admin/roles")
async def create_role(
    name: str,
    display_name: str,
    permissions: list[str],
    user = Depends(deps.requires("role:create"))
):
    """Create role."""
    role = await auth.role_service.create_role(
        name=name,
        display_name=display_name,
        permissions=permissions
    )
    return {"role_id": str(role.id)}

@app.post("/admin/users/{user_id}/roles/{role_id}")
async def assign_role(
    user_id: str,
    role_id: str,
    user = Depends(deps.requires("role:assign"))
):
    """Assign role to user."""
    await auth.role_service.assign_role(user_id, role_id)
    return {"message": "Role assigned"}

# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Differences from EnterpriseRBAC

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|------------|----------------|
| **Structure** | Flat (users → roles → permissions) | Hierarchical (entities → memberships → roles) |
| **Entity System** | ❌ Not available | ✅ Available |
| **Entity Memberships** | ❌ Not available | ✅ Available |
| **Permission Scopes** | Global only | Global, entity-scoped, tree, platform-wide |
| **Tree Permissions** | ❌ Not available | ✅ Available (`_tree` suffix) |
| **Context-Aware Roles** | ❌ Disabled | ✅ Optional |
| **ABAC Conditions** | ❌ Disabled | ✅ Optional |
| **Services** | 7 services | 9 services (includes EntityService, MembershipService) |
| **Permission Service** | `BasicPermissionService` | `EnterprisePermissionService` |
| **Role Assignment** | Global (user → role) | Per-entity (user → entity → role) |
| **Complexity** | Low | Medium-High |
| **Use Case** | Simple apps, SaaS tools | Enterprise apps, multi-department orgs |

---

## Migration to EnterpriseRBAC

**Zero code changes** - just change the class:

```python
# Before: SimpleRBAC
from outlabs_auth import SimpleRBAC
auth = SimpleRBAC(database=db)

# After: EnterpriseRBAC (backward compatible)
from outlabs_auth import EnterpriseRBAC
auth = EnterpriseRBAC(database=db)

# All existing code continues to work!
# Gradually add entity features when needed
```

**See:** [42-Entity-Hierarchy.md](42-Entity-Hierarchy.md) for entity setup guide.

---

## See Also

- **[61-EnterpriseRBAC-API.md](61-EnterpriseRBAC-API.md)** - EnterpriseRBAC API reference
- **[41-RBAC-Patterns.md](41-RBAC-Patterns.md)** - RBAC patterns and examples
- **[14-FastAPI-Integration.md](14-FastAPI-Integration.md)** - FastAPI integration guide
- **[70-User-Service.md](70-User-Service.md)** - UserService API
- **[71-Role-Service.md](71-Role-Service.md)** - RoleService API
- **[72-Permission-Service.md](72-Permission-Service.md)** - PermissionService API

---

**Last Updated:** 2025-01-23
**Applies To:** OutlabsAuth v1.0+
**Class:** `outlabs_auth.presets.SimpleRBAC`
