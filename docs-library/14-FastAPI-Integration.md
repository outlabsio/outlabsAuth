# FastAPI Integration

**Complete guide to integrating OutlabsAuth with FastAPI applications**

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Authentication Dependencies](#authentication-dependencies)
  - [AuthDeps Class](#authdeps-class)
  - [require_auth()](#require_auth)
  - [require_permission()](#require_permission)
  - [require_any_permission()](#require_any_permission)
  - [optional_auth()](#optional_auth)
  - [superuser()](#superuser)
- [Router Factories](#router-factories)
  - [get_auth_router()](#get_auth_router)
  - [get_users_router()](#get_users_router)
  - [get_api_keys_router()](#get_api_keys_router)
  - [get_oauth_router()](#get_oauth_router)
- [Complete Integration Example](#complete-integration-example)
- [Custom Route Protection](#custom-route-protection)
- [Error Handling](#error-handling)
- [OpenAPI Documentation](#openapi-documentation)
- [Best Practices](#best-practices)
- [See Also](#see-also)

---

## Overview

OutlabsAuth provides **native FastAPI integration** with:

✓ **Dependency injection** for route protection
✓ **Pre-built routers** for common auth flows
✓ **Automatic OpenAPI documentation**
✓ **Type-safe request/response models**
✓ **Lifecycle hook integration**

### Integration Philosophy

```
┌──────────────────────────────────────────────────────┐
│  FastAPI Application                                  │
├──────────────────────────────────────────────────────┤
│  1. Initialize OutlabsAuth instance                   │
│  2. Create AuthDeps for dependency injection          │
│  3. Include pre-built routers (optional)              │
│  4. Protect custom routes with dependencies           │
└──────────────────────────────────────────────────────┘
```

---

## Quick Start

### Minimal Setup (SimpleRBAC)

```python
from fastapi import FastAPI, Depends
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.routers import get_auth_router, get_users_router

# Initialize FastAPI
app = FastAPI(title="My API")

# Initialize MongoDB
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["my_database"]

# Initialize auth
auth = SimpleRBAC(
    database=db,
    secret_key="your-secret-key-here",
)

# Initialize database collections
@app.on_event("startup")
async def startup():
    await auth.initialize()

# Create dependency factory
deps = AuthDeps(auth)

# Include pre-built routers
app.include_router(get_auth_router(auth))      # POST /auth/login, /auth/register, etc.
app.include_router(get_users_router(auth))     # GET /users/me, PATCH /users/me, etc.

# Protected custom route
@app.get("/protected")
async def protected_route(user = Depends(deps.authenticated())):
    return {"message": f"Hello {user.email}"}

# Permission-protected route
@app.delete("/admin/reset")
async def admin_route(user = Depends(deps.requires("admin:reset"))):
    return {"message": "Database reset"}
```

### EnterpriseRBAC Setup

```python
from outlabs_auth import EnterpriseRBAC

# Initialize with entity hierarchy enabled
auth = EnterpriseRBAC(
    database=db,
    secret_key="your-secret-key-here",
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Same integration as SimpleRBAC
deps = AuthDeps(auth)
app.include_router(get_auth_router(auth))
app.include_router(get_users_router(auth))

# Entity-scoped permission check
@app.put("/entities/{entity_id}/projects")
async def create_project(
    entity_id: str,
    user = Depends(deps.requires("project:create"))
):
    # Check permission in specific entity context
    has_perm, source = await auth.permission_service.check_permission(
        str(user.id),
        "project:create",
        entity_id
    )

    if not has_perm:
        raise HTTPException(403, "Permission denied in this entity")

    return {"message": f"Project created (permission via {source})"}
```

---

## Authentication Dependencies

### AuthDeps Class

**Location:** `outlabs_auth/dependencies/auth.py`

Factory for creating FastAPI dependencies.

#### Initialization

```python
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)  # Pass your OutlabsAuth instance
```

---

### require_auth()

**Require authenticated user.**

```python
deps.authenticated()  # Returns Depends(...)
```

**Returns:** `UserModel`
**Raises:** `HTTPException(401)` if not authenticated

#### Example

```python
from fastapi import Depends, FastAPI
from outlabs_auth.models.user import UserModel

app = FastAPI()

@app.get("/profile")
async def get_profile(user: UserModel = Depends(deps.authenticated())):
    """Get user profile (authentication required)."""
    return {
        "user_id": str(user.id),
        "email": user.email,
        "profile": user.profile.model_dump()
    }
```

#### Token Extraction

Expects `Authorization` header:
```
Authorization: Bearer <jwt-token>
```

**cURL Example:**
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     http://localhost:8000/profile
```

**Error Responses:**
```json
// Missing token
{
  "detail": "Not authenticated"
}

// Invalid token
{
  "detail": "Invalid token: ..."
}

// Expired token
{
  "detail": "Token has expired"
}

// User not found
{
  "detail": "User not found"
}
```

---

### require_permission()

**Require specific permission(s).**

```python
deps.requires(*permissions)  # User must have ALL permissions
```

**Returns:** `UserModel`
**Raises:** `HTTPException(403)` if permission denied

#### Example: Single Permission

```python
@app.post("/users")
async def create_user(
    data: UserCreate,
    user: UserModel = Depends(deps.requires("user:create"))
):
    """Create user (requires user:create permission)."""
    return await auth.user_service.create_user(**data.dict())
```

#### Example: Multiple Permissions

```python
@app.post("/admin/roles")
async def create_role(
    data: RoleCreate,
    user: UserModel = Depends(deps.requires("role:create", "permission:grant"))
):
    """
    Create role (requires BOTH permissions).

    User must have:
    - role:create
    - permission:grant
    """
    return await auth.role_service.create_role(**data.dict())
```

#### Superuser Bypass

Superusers automatically pass all permission checks:

```python
# If user.is_superuser == True, they can access this route
# regardless of their actual permissions
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user: UserModel = Depends(deps.requires("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}
```

---

### require_any_permission()

**Require AT LEAST ONE of the permissions.**

```python
deps.requires_any(*permissions)  # User needs ANY permission
```

**Returns:** `UserModel`
**Raises:** `HTTPException(403)` if user has NONE of the permissions

#### Example

```python
@app.put("/posts/{post_id}")
async def update_post(
    post_id: str,
    data: PostUpdate,
    user: UserModel = Depends(
        deps.requires_any("post:update", "post:update_own", "admin:all")
    )
):
    """
    Update post.

    User needs ONE of:
    - post:update (can update any post)
    - post:update_own (can update own posts)
    - admin:all (admin with all permissions)
    """
    # Additional business logic to check ownership if using post:update_own
    if "post:update" not in user_permissions and "admin:all" not in user_permissions:
        # User only has post:update_own, verify ownership
        post = await get_post(post_id)
        if post.author_id != user.id:
            raise HTTPException(403, "Can only update own posts")

    return await update_post_logic(post_id, data)
```

---

### optional_auth()

**Optional authentication (doesn't raise if not authenticated).**

```python
deps.optional_auth()  # Returns Optional[UserModel]
```

**Returns:** `Optional[UserModel]` - `UserModel` if authenticated, `None` otherwise
**Raises:** Never raises exceptions

#### Example: Public Content with Personalization

```python
from typing import Optional

@app.get("/feed")
async def get_feed(user: Optional[UserModel] = Depends(deps.optional_auth())):
    """
    Get content feed.

    - Authenticated users get personalized feed
    - Anonymous users get public feed
    """
    if user:
        # Personalized feed for logged-in users
        return {
            "feed": await get_personalized_feed(user.id),
            "user": user.email
        }
    else:
        # Public feed for anonymous users
        return {
            "feed": await get_public_feed(),
            "user": None
        }
```

#### Example: Like Count with User State

```python
@app.get("/posts/{post_id}/likes")
async def get_likes(
    post_id: str,
    user: Optional[UserModel] = Depends(deps.optional_auth())
):
    """
    Get likes for post.

    If authenticated, includes whether current user has liked.
    """
    likes = await get_post_likes(post_id)

    response = {
        "count": len(likes),
        "users": [l.user_id for l in likes]
    }

    if user:
        # Add user-specific state
        response["liked_by_me"] = user.id in response["users"]

    return response
```

---

### superuser()

**Require superuser access.**

```python
deps.superuser()  # User must have is_superuser=True
```

**Returns:** `UserModel`
**Raises:** `HTTPException(403)` if not superuser

#### Example

```python
@app.post("/admin/database/reset")
async def reset_database(user: UserModel = Depends(deps.superuser())):
    """
    Reset database (superuser only).

    DANGER: Only superusers can access this route.
    """
    await database_reset_logic()
    return {"message": "Database reset complete"}

@app.post("/admin/users/{user_id}/promote")
async def promote_to_admin(
    user_id: str,
    user: UserModel = Depends(deps.superuser())
):
    """Grant admin role to user (superuser only)."""
    await grant_admin_role(user_id)
    return {"message": f"User {user_id} promoted to admin"}
```

---

### Shortcut: `.user`

Alias for `authenticated()`:

```python
# These are equivalent:
user = Depends(deps.authenticated())
user = Depends(deps.user)
```

**Example:**
```python
@app.get("/me")
async def get_me(user = Depends(deps.user)):
    return user
```

---

## Router Factories

**Pre-built routers for common auth flows** (DD-041).

### get_auth_router()

**Authentication routes (login, register, password reset).**

**Location:** `outlabs_auth/routers/auth.py`

#### Signature

```python
def get_auth_router(
    auth: OutlabsAuth,
    prefix: str = "/auth",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False
) -> APIRouter
```

#### Routes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | User registration |
| `POST` | `/auth/login` | User login (JWT tokens) |
| `POST` | `/auth/refresh` | Refresh access token |
| `POST` | `/auth/logout` | Logout (invalidate tokens) |
| `POST` | `/auth/forgot-password` | Request password reset |
| `POST` | `/auth/reset-password` | Reset password with token |

#### Usage

```python
from outlabs_auth.routers import get_auth_router

# Include with default settings
app.include_router(get_auth_router(auth))

# Customize prefix and tags
app.include_router(
    get_auth_router(
        auth,
        prefix="/api/auth",
        tags=["Authentication"],
        requires_verification=True  # Require email verification for login
    )
)
```

#### Request/Response Examples

**Register:**
```bash
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe"
}

# Response (201 Created):
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "profile": {
    "first_name": "John",
    "last_name": "Doe"
  },
  "status": "active",
  "created_at": "2025-01-23T10:00:00Z"
}
```

**Login:**
```bash
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}

# Response (200 OK):
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Refresh:**
```bash
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

# Response (200 OK):
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  # New
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  # Same
  "token_type": "bearer"
}
```

---

### get_users_router()

**User management routes.**

**Location:** `outlabs_auth/routers/users.py`

#### Signature

```python
def get_users_router(
    auth: OutlabsAuth,
    prefix: str = "/users",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False
) -> APIRouter
```

#### Routes

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/users/me` | Authenticated | Get current user profile |
| `PATCH` | `/users/me` | Authenticated | Update current user profile |
| `POST` | `/users/me/change-password` | Authenticated | Change password |
| `GET` | `/users/{user_id}` | `user:read` | Get user by ID (admin) |
| `PATCH` | `/users/{user_id}` | `user:update` | Update user by ID (admin) |
| `DELETE` | `/users/{user_id}` | `user:delete` | Delete user by ID (admin) |

#### Usage

```python
from outlabs_auth.routers import get_users_router

# Include with default settings
app.include_router(get_users_router(auth))

# Customize
app.include_router(
    get_users_router(
        auth,
        prefix="/api/users",
        tags=["User Management"],
        requires_verification=True
    )
)
```

#### Request/Response Examples

**Get Current User:**
```bash
GET /users/me
Authorization: Bearer <token>

# Response (200 OK):
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "profile": {
    "first_name": "John",
    "last_name": "Doe",
    "avatar_url": null
  },
  "status": "active"
}
```

**Update Profile:**
```bash
PATCH /users/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "profile": {
    "first_name": "Jane",
    "avatar_url": "https://example.com/avatar.jpg"
  }
}

# Response (200 OK):
{
  "id": "507f1f77bcf86cd799439011",
  "email": "user@example.com",
  "profile": {
    "first_name": "Jane",  # Updated
    "last_name": "Doe",
    "avatar_url": "https://example.com/avatar.jpg"  # Updated
  }
}
```

**Change Password:**
```bash
POST /users/me/change-password
Authorization: Bearer <token>
Content-Type: application/json

{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!"
}

# Response (204 No Content)
```

---

### get_api_keys_router()

**API key management routes.**

**Location:** `outlabs_auth/routers/api_keys.py`

#### Routes

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `POST` | `/api-keys` | Authenticated | Create API key |
| `GET` | `/api-keys` | Authenticated | List user's API keys |
| `DELETE` | `/api-keys/{key_id}` | Authenticated | Revoke API key |

#### Usage

```python
from outlabs_auth.routers import get_api_keys_router

app.include_router(get_api_keys_router(auth))
```

---

### get_oauth_router()

**OAuth social login routes** (v1.2).

**Location:** `outlabs_auth/routers/oauth.py`

#### Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/oauth/{provider}/authorize` | Start OAuth flow |
| `GET` | `/oauth/{provider}/callback` | Handle OAuth callback |
| `POST` | `/oauth/{provider}/associate` | Link account (authenticated) |
| `DELETE` | `/oauth/{provider}/unlink` | Unlink account (authenticated) |

#### Usage

```python
from outlabs_auth.routers import get_oauth_router
from outlabs_auth.oauth.providers import GoogleProvider

# Configure OAuth providers
google_provider = GoogleProvider(
    client_id="your-client-id",
    client_secret="your-client-secret"
)

auth.configure_oauth(providers={"google": google_provider})

# Include router
app.include_router(get_oauth_router(auth))
```

---

## Complete Integration Example

### Full Application with All Features

```python
from fastapi import FastAPI, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.routers import (
    get_auth_router,
    get_users_router,
    get_api_keys_router,
    get_oauth_router
)
from outlabs_auth.models.user import UserModel

# ============================================================================
# 1. Initialize FastAPI
# ============================================================================

app = FastAPI(
    title="My Enterprise API",
    description="API with OutlabsAuth integration",
    version="1.0.0"
)

# ============================================================================
# 2. Initialize MongoDB
# ============================================================================

mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["my_database"]

# ============================================================================
# 3. Initialize OutlabsAuth
# ============================================================================

auth = EnterpriseRBAC(
    database=db,
    secret_key="your-secret-key-change-in-production",
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# ============================================================================
# 4. Database Initialization
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize database collections and indexes."""
    await auth.initialize()
    print("✓ Database initialized")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    mongo_client.close()
    print("✓ Database connection closed")

# ============================================================================
# 5. Create Dependency Factory
# ============================================================================

deps = AuthDeps(auth)

# ============================================================================
# 6. Include Pre-Built Routers
# ============================================================================

# Authentication routes
app.include_router(
    get_auth_router(auth, prefix="/api/auth", tags=["Authentication"])
)

# User management routes
app.include_router(
    get_users_router(auth, prefix="/api/users", tags=["Users"])
)

# API key management routes
app.include_router(
    get_api_keys_router(auth, prefix="/api/api-keys", tags=["API Keys"])
)

# OAuth routes (if configured)
app.include_router(
    get_oauth_router(auth, prefix="/api/oauth", tags=["OAuth"])
)

# ============================================================================
# 7. Custom Protected Routes
# ============================================================================

@app.get("/")
async def root():
    """Public root endpoint."""
    return {
        "message": "Welcome to My Enterprise API",
        "docs": "/docs",
        "auth": "/api/auth/login"
    }

@app.get("/api/protected")
async def protected_route(user: UserModel = Depends(deps.authenticated())):
    """Example: Authentication required."""
    return {
        "message": f"Hello {user.email}",
        "user_id": str(user.id)
    }

@app.get("/api/optional")
async def optional_route(user: Optional[UserModel] = Depends(deps.optional_auth())):
    """Example: Optional authentication."""
    if user:
        return {"message": f"Hello {user.email}", "authenticated": True}
    return {"message": "Hello guest", "authenticated": False}

# ============================================================================
# 8. Permission-Protected Routes
# ============================================================================

@app.get("/api/admin/users")
async def list_users(user: UserModel = Depends(deps.requires("user:read"))):
    """List all users (requires user:read permission)."""
    users = await auth.user_service.list_users()
    return {"users": users, "count": len(users)}

@app.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    user: UserModel = Depends(deps.requires("user:delete"))
):
    """Delete user (requires user:delete permission)."""
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}

@app.post("/api/admin/database/backup")
async def backup_database(user: UserModel = Depends(deps.superuser())):
    """Backup database (superuser only)."""
    # Only superusers can access
    await backup_logic()
    return {"message": "Backup created"}

# ============================================================================
# 9. Entity-Scoped Routes (EnterpriseRBAC)
# ============================================================================

@app.post("/api/entities/{entity_id}/projects")
async def create_project(
    entity_id: str,
    project_data: dict,
    user: UserModel = Depends(deps.authenticated())
):
    """Create project in entity (entity-scoped permission check)."""
    # Check permission in specific entity context
    has_perm, source = await auth.permission_service.check_permission(
        str(user.id),
        "project:create",
        entity_id
    )

    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: project:create in entity {entity_id}"
        )

    # Permission granted - create project
    project = await create_project_logic(entity_id, project_data)

    return {
        "project": project,
        "permission_source": source  # "direct", "tree", "all", or "superuser"
    }

# ============================================================================
# 10. Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom error response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "path": str(request.url),
            "method": request.method
        }
    )

# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Custom Route Protection

### Complex Permission Logic

```python
@app.put("/posts/{post_id}")
async def update_post(
    post_id: str,
    data: PostUpdate,
    user: UserModel = Depends(deps.authenticated())
):
    """
    Update post with custom permission logic.

    Rules:
    - Admin can update any post (post:update)
    - Author can update own post (post:update_own)
    - Others denied
    """
    # Check admin permission first
    has_admin_perm = await auth.permission_service.check_permission(
        str(user.id),
        "post:update"
    )

    if has_admin_perm:
        # Admin can update any post
        return await update_post_logic(post_id, data)

    # Check ownership for post:update_own
    has_own_perm = await auth.permission_service.check_permission(
        str(user.id),
        "post:update_own"
    )

    if has_own_perm:
        # Verify user is the author
        post = await get_post(post_id)
        if post.author_id != user.id:
            raise HTTPException(403, "Can only update own posts")

        return await update_post_logic(post_id, data)

    # No permission
    raise HTTPException(403, "Permission denied: post:update")
```

### ABAC with Context

```python
@app.post("/entities/{entity_id}/approve-budget")
async def approve_budget(
    entity_id: str,
    amount: float,
    user: UserModel = Depends(deps.authenticated())
):
    """
    Approve budget with ABAC conditions.

    Rules (defined in role conditions):
    - resource.department == user.department
    - resource.budget <= user.approval_limit
    """
    # Build ABAC context
    entity = await auth.entity_service.get_entity(entity_id)

    context = {
        "user": {
            "id": str(user.id),
            "department": user.profile.preferences.get("department"),
            "approval_limit": user.profile.preferences.get("approval_limit", 0)
        },
        "resource": {
            "id": entity_id,
            "department": entity.metadata.get("department"),
            "budget": amount
        }
    }

    # Check permission with ABAC context
    has_perm, source = await auth.permission_service.check_permission_with_context(
        str(user.id),
        "budget:approve",
        entity_id,
        context
    )

    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail="ABAC conditions not met for budget approval"
        )

    # Conditions passed - approve budget
    return await approve_budget_logic(entity_id, amount)
```

---

## Error Handling

### Standard HTTP Exceptions

OutlabsAuth dependencies raise standard FastAPI `HTTPException`:

| Error | Status Code | Description |
|-------|-------------|-------------|
| Not authenticated | 401 | Missing or invalid token |
| Token expired | 401 | JWT token expired |
| Permission denied | 403 | User lacks required permission |
| User not found | 401 | User ID in token doesn't exist |

### Custom Error Handler

```python
from fastapi.responses import JSONResponse
from fastapi import Request, HTTPException

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Custom error response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "path": str(request.url),
                "method": request.method
            }
        },
        headers=exc.headers
    )
```

**Response:**
```json
{
  "error": {
    "code": 401,
    "message": "Token has expired",
    "path": "http://localhost:8000/api/protected",
    "method": "GET"
  }
}
```

---

## OpenAPI Documentation

### Automatic Documentation

OutlabsAuth dependencies automatically add OpenAPI security schemes:

```python
app = FastAPI(
    title="My API",
    description="API with JWT authentication",
    version="1.0.0"
)

# Dependencies automatically add security to OpenAPI schema
@app.get("/protected")
async def protected(user = Depends(deps.authenticated())):
    return {"message": "Protected"}
```

**Generated OpenAPI:**
```yaml
paths:
  /protected:
    get:
      summary: Protected
      security:
        - HTTPBearer: []
      responses:
        '200':
          description: Successful Response
        '401':
          description: Unauthorized
```

### Custom Security Scheme

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.get("/custom")
async def custom_route(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user: UserModel = Depends(deps.authenticated())
):
    """Custom security scheme in OpenAPI."""
    return {"token": credentials.credentials[:10] + "..."}
```

### Response Models

Use Pydantic response models for type-safe OpenAPI docs:

```python
from outlabs_auth.schemas.user import UserResponse

@app.get("/users/me", response_model=UserResponse)
async def get_me(user = Depends(deps.user)):
    """Get current user (typed response)."""
    return user
```

---

## Best Practices

### 1. Use Environment Variables for Secrets

```python
import os
from dotenv import load_dotenv

load_dotenv()

auth = SimpleRBAC(
    database=db,
    secret_key=os.getenv("SECRET_KEY"),  # From .env
    redis_url=os.getenv("REDIS_URL")
)
```

### 2. Initialize Database on Startup

```python
@app.on_event("startup")
async def startup():
    await auth.initialize()  # Create indexes
```

### 3. Use Type Hints

```python
from outlabs_auth.models.user import UserModel

@app.get("/me")
async def get_me(user: UserModel = Depends(deps.user)) -> dict:
    """Type hints improve IDE support and OpenAPI docs."""
    return {"email": user.email}
```

### 4. Centralize Permission Checks

```python
# utils/permissions.py
async def require_entity_permission(
    user_id: str,
    entity_id: str,
    permission: str,
    auth: OutlabsAuth
):
    """Centralized entity permission check."""
    has_perm, source = await auth.permission_service.check_permission(
        user_id, permission, entity_id
    )
    if not has_perm:
        raise HTTPException(403, f"Permission denied: {permission}")
    return source

# In route:
@app.post("/entities/{entity_id}/projects")
async def create_project(
    entity_id: str,
    user = Depends(deps.user)
):
    source = await require_entity_permission(
        str(user.id), entity_id, "project:create", auth
    )
    # ... create project
```

### 5. Use Router Tags for Organization

```python
# Group related routes with tags
app.include_router(
    get_auth_router(auth, tags=["🔐 Authentication"])
)
app.include_router(
    get_users_router(auth, tags=["👤 User Management"])
)

# Custom routers
entities_router = APIRouter(prefix="/entities", tags=["🏢 Entities"])

@entities_router.get("/")
async def list_entities(user = Depends(deps.user)):
    ...

app.include_router(entities_router)
```

### 6. Document Permissions in Route Docstrings

```python
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user = Depends(deps.requires("user:delete"))
):
    """
    Delete user account.

    **Required Permission:** `user:delete`

    **Superuser:** Bypass permission check
    """
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}
```

### 7. Handle Background Tasks

```python
from fastapi import BackgroundTasks

@app.post("/users")
async def create_user(
    data: UserCreate,
    background_tasks: BackgroundTasks,
    user = Depends(deps.requires("user:create"))
):
    """Create user with background email send."""
    new_user = await auth.user_service.create_user(**data.dict())

    # Send welcome email in background
    background_tasks.add_task(send_welcome_email, new_user.email)

    return new_user
```

---

## See Also

- **[11. Core Components](11-Core-Components.md)** - OutlabsAuth unified class
- **[13. Service Layer](13-Service-Layer.md)** - Business logic services
- **[40. Authorization Overview](40-Authorization-Overview.md)** - Permission checking patterns
- **[41. RBAC Patterns](41-RBAC-Patterns.md)** - Role-based access control
- **[42. Entity Hierarchy](42-Entity-Hierarchy.md)** - Organizational structure
- **[43. Tree Permissions](43-Tree-Permissions.md)** - Hierarchical permissions

---

**Last Updated:** 2025-01-23
**Applies To:** OutlabsAuth v1.0+
**Related Design Decisions:** DD-041 (Router Factories), DD-035 (Unified AuthDeps)
