# SimpleRBAC - Simple Role-Based Access Control

**Tags**: #authorization #simple-rbac #flat-structure #getting-started

Complete guide to using SimpleRBAC for flat role-based access control.

---

## What is SimpleRBAC?

SimpleRBAC is a **flat role-based access control** system for applications that don't need hierarchical organization structures.

**Use When**:
- ✅ Flat organizational structure (no departments/teams)
- ✅ Simple role-based permissions (admin, user, moderator)
- ✅ No hierarchical access control needed
- ✅ Want fastest setup and simplest API

**Don't Use When**:
- ❌ Need organizational hierarchy (company → departments → teams)
- ❌ Need tree permissions (access to entire subtrees)
- ❌ Need context-aware roles (different permissions per entity type)
- ❌ Multi-tenant SaaS with complex permissions

**For those cases**, use [[42-EnterpriseRBAC|EnterpriseRBAC]] instead.

---

## Architecture

```
┌─────────────────────────────────────────┐
│              Users                       │
│  • user_123 (admin)                     │
│  • user_456 (editor)                    │
│  • user_789 (viewer)                    │
└─────────────────────────────────────────┘
                  │
                  │ has role
                  ▼
┌─────────────────────────────────────────┐
│              Roles                       │
│  • admin    → [user:*, content:*]       │
│  • editor   → [content:create, ...]     │
│  • viewer   → [content:read]            │
└─────────────────────────────────────────┘
                  │
                  │ has permissions
                  ▼
┌─────────────────────────────────────────┐
│           Permissions                    │
│  • user:read                            │
│  • user:create                          │
│  • user:update                          │
│  • user:delete                          │
│  • content:read                         │
│  • content:create                       │
│  • content:update                       │
│  • content:delete                       │
└─────────────────────────────────────────┘
```

**Flow**: User → Role → Permissions → Check

---

## Quick Start

### Step 1: Install

```bash
pip install outlabs-auth
```

### Step 2: Initialize

```python
from fastapi import FastAPI, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router, get_users_router

# FastAPI app
app = FastAPI(title="Blog with Auth")

# MongoDB connection
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["blog_app"]

# Initialize SimpleRBAC
auth = SimpleRBAC(database=db)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    await auth.initialize()

# Add authentication routes
app.include_router(
    get_auth_router(auth),
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    get_users_router(auth),
    prefix="/users",
    tags=["users"]
)
```

### Step 3: Create Roles

```python
# Create roles (run once during setup)
@app.on_event("startup")
async def create_roles():
    # Admin role - full access
    await auth.role_service.create_role(
        name="admin",
        permissions=[
            "user:read",
            "user:create",
            "user:update",
            "user:delete",
            "content:read",
            "content:create",
            "content:update",
            "content:delete",
        ]
    )

    # Editor role - content management
    await auth.role_service.create_role(
        name="editor",
        permissions=[
            "content:read",
            "content:create",
            "content:update",
            "content:delete",
        ]
    )

    # Viewer role - read-only
    await auth.role_service.create_role(
        name="viewer",
        permissions=[
            "content:read",
        ]
    )
```

### Step 4: Protect Routes

```python
# Require authentication
@app.get("/me")
async def get_me(ctx = Depends(auth.deps.require_auth())):
    user = ctx.metadata.get("user")
    return {"user_id": user.id, "email": user.email}

# Require specific permission
@app.get("/content")
async def list_content(ctx = Depends(auth.deps.require_permission("content:read"))):
    # User has "content:read" permission
    return await get_content_from_db()

@app.post("/content")
async def create_content(
    content: dict,
    ctx = Depends(auth.deps.require_permission("content:create"))
):
    # User has "content:create" permission
    return await save_content_to_db(content)

# Require specific role
@app.get("/admin/dashboard")
async def admin_dashboard(ctx = Depends(auth.deps.require_role("admin"))):
    # User has "admin" role
    return {"message": "Welcome, admin!"}

# Multiple permissions (requires ALL)
@app.delete("/content/{content_id}")
async def delete_content(
    content_id: str,
    ctx = Depends(auth.deps.require_permissions([
        "content:read",
        "content:delete"
    ]))
):
    # User has BOTH permissions
    return await delete_content_from_db(content_id)
```

**That's it!** You now have a fully functional authentication and authorization system.

---

## Complete Example: Blog API

Here's a complete blog API with SimpleRBAC:

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router, get_users_router
from pydantic import BaseModel
from typing import List
from datetime import datetime

app = FastAPI(title="Blog API")

# MongoDB
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["blog"]

# Auth
auth = SimpleRBAC(database=db)

# Blog post schema
class BlogPost(BaseModel):
    title: str
    content: str
    author_id: str
    created_at: datetime
    updated_at: datetime

# Initialize
@app.on_event("startup")
async def startup():
    await auth.initialize()

    # Create roles (idempotent - won't create duplicates)
    try:
        await auth.role_service.create_role(
            name="admin",
            permissions=["user:*", "post:*"]  # Wildcard: all permissions
        )
    except Exception:
        pass  # Role already exists

    try:
        await auth.role_service.create_role(
            name="writer",
            permissions=["post:read", "post:create", "post:update"]
        )
    except Exception:
        pass

    try:
        await auth.role_service.create_role(
            name="reader",
            permissions=["post:read"]
        )
    except Exception:
        pass

# Add auth routes
app.include_router(get_auth_router(auth), prefix="/auth", tags=["auth"])
app.include_router(get_users_router(auth), prefix="/users", tags=["users"])

# Blog routes
@app.get("/posts", response_model=List[BlogPost])
async def list_posts(ctx = Depends(auth.deps.require_permission("post:read"))):
    """List all blog posts (requires post:read)"""
    posts_collection = db["posts"]
    posts = await posts_collection.find().to_list(100)
    return posts

@app.get("/posts/{post_id}", response_model=BlogPost)
async def get_post(
    post_id: str,
    ctx = Depends(auth.deps.require_permission("post:read"))
):
    """Get single blog post (requires post:read)"""
    posts_collection = db["posts"]
    post = await posts_collection.find_one({"_id": post_id})
    if not post:
        raise HTTPException(404, "Post not found")
    return post

@app.post("/posts", response_model=BlogPost)
async def create_post(
    title: str,
    content: str,
    ctx = Depends(auth.deps.require_permission("post:create"))
):
    """Create blog post (requires post:create)"""
    user = ctx.metadata.get("user")
    posts_collection = db["posts"]

    post = {
        "title": title,
        "content": content,
        "author_id": user.id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = await posts_collection.insert_one(post)
    post["_id"] = str(result.inserted_id)
    return post

@app.patch("/posts/{post_id}", response_model=BlogPost)
async def update_post(
    post_id: str,
    title: str = None,
    content: str = None,
    ctx = Depends(auth.deps.require_permission("post:update"))
):
    """Update blog post (requires post:update)"""
    user = ctx.metadata.get("user")
    posts_collection = db["posts"]

    # Get existing post
    post = await posts_collection.find_one({"_id": post_id})
    if not post:
        raise HTTPException(404, "Post not found")

    # Only author or admin can update
    if post["author_id"] != user.id and "admin" not in user.roles:
        raise HTTPException(403, "Can only update your own posts")

    # Update
    update_data = {"updated_at": datetime.utcnow()}
    if title:
        update_data["title"] = title
    if content:
        update_data["content"] = content

    await posts_collection.update_one(
        {"_id": post_id},
        {"$set": update_data}
    )

    updated_post = await posts_collection.find_one({"_id": post_id})
    return updated_post

@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    ctx = Depends(auth.deps.require_permission("post:delete"))
):
    """Delete blog post (requires post:delete - admin only)"""
    posts_collection = db["posts"]

    result = await posts_collection.delete_one({"_id": post_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Post not found")

    return {"status": "deleted"}

# Admin-only routes
@app.get("/admin/users")
async def list_users(ctx = Depends(auth.deps.require_role("admin"))):
    """List all users (admin only)"""
    users = await auth.user_service.list_users()
    return users

@app.post("/admin/users/{user_id}/roles/{role_name}")
async def assign_role(
    user_id: str,
    role_name: str,
    ctx = Depends(auth.deps.require_role("admin"))
):
    """Assign role to user (admin only)"""
    await auth.role_service.assign_role_to_user(user_id, role_name)
    return {"status": "role assigned"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## User Workflow

### 1. Register User

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePassword123!"
  }'
```

Response:
```json
{
  "id": "user_123",
  "email": "john@example.com",
  "is_active": true,
  "is_verified": false
}
```

### 2. Assign Role (Admin)

```bash
curl -X POST "http://localhost:8000/admin/users/user_123/roles/writer" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### 3. Login

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePassword123!"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### 4. Create Blog Post

```bash
curl -X POST "http://localhost:8000/posts" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "Hello, world!"
  }'
```

---

## Role Management

### Create Role

```python
await auth.role_service.create_role(
    name="moderator",
    permissions=[
        "post:read",
        "post:update",  # Can edit any post
        "comment:delete",  # Can delete comments
    ]
)
```

### Get Role

```python
role = await auth.role_service.get_role("moderator")
print(role.name)  # "moderator"
print(role.permissions)  # ["post:read", "post:update", ...]
```

### Update Role

```python
await auth.role_service.update_role(
    role_name="moderator",
    permissions=[
        "post:read",
        "post:update",
        "comment:read",
        "comment:update",
        "comment:delete",
    ]
)
```

### Delete Role

```python
await auth.role_service.delete_role("moderator")
```

### List All Roles

```python
roles = await auth.role_service.list_roles()
for role in roles:
    print(f"{role.name}: {role.permissions}")
```

---

## User Role Assignment

### Assign Role to User

```python
await auth.role_service.assign_role_to_user(
    user_id="user_123",
    role_name="editor"
)
```

### Assign Multiple Roles

```python
await auth.role_service.assign_role_to_user("user_123", "editor")
await auth.role_service.assign_role_to_user("user_123", "moderator")
# User now has both roles and all their permissions
```

### Remove Role from User

```python
await auth.role_service.remove_role_from_user(
    user_id="user_123",
    role_name="editor"
)
```

### Get User's Roles

```python
user = await auth.user_service.get_user("user_123")
print(user.roles)  # ["editor", "moderator"]
```

### Check if User Has Role

```python
user = await auth.user_service.get_user("user_123")
has_admin = "admin" in user.roles  # True or False
```

---

## Permission Checking

### In Route Dependencies (Recommended)

```python
# Single permission
@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    ctx = Depends(auth.deps.require_permission("post:delete"))
):
    # User has "post:delete" permission
    pass

# Multiple permissions (requires ALL)
@app.post("/admin/backup")
async def create_backup(
    ctx = Depends(auth.deps.require_permissions([
        "admin:backup",
        "system:write"
    ]))
):
    # User has BOTH permissions
    pass

# Role-based (instead of permission)
@app.get("/admin/dashboard")
async def admin_dashboard(ctx = Depends(auth.deps.require_role("admin"))):
    # User has "admin" role
    pass
```

### Programmatic Checking

```python
# Check if user has permission
has_permission = await auth.permission_service.check_permission(
    user_id="user_123",
    permission="post:delete"
)

if has_permission:
    # Allow action
    pass
else:
    raise HTTPException(403, "Permission denied")
```

### Check Multiple Permissions

```python
# Requires ALL permissions
has_all = await auth.permission_service.check_permissions(
    user_id="user_123",
    permissions=["post:read", "post:update"]
)

# Requires ANY permission
has_any = await auth.permission_service.check_any_permission(
    user_id="user_123",
    permissions=["post:update", "post:delete"]
)
```

---

## Permission Naming Conventions

### Format: `resource:action`

**Resources**: What you're protecting
- `user` - User management
- `post` - Blog posts
- `comment` - Comments
- `file` - File uploads
- `admin` - Admin features
- `billing` - Billing/payments

**Actions**: What you can do
- `read` - View/list resources
- `create` - Create new resources
- `update` - Modify existing resources
- `delete` - Delete resources
- `manage` - Full access (create/read/update/delete)

**Examples**:
- `user:read` - Can view users
- `user:create` - Can create users
- `post:update` - Can edit posts
- `comment:delete` - Can delete comments
- `admin:manage` - Full admin access

### Wildcard Permissions

Use `*` for wildcard matching:

```python
# All actions on user resource
"user:*" → ["user:read", "user:create", "user:update", "user:delete"]

# All resources, all actions (superuser)
"*:*" → All permissions

# All resources, read action only
"*:read" → ["user:read", "post:read", "comment:read", ...]
```

**Example**:
```python
await auth.role_service.create_role(
    name="super_admin",
    permissions=["*:*"]  # All permissions
)
```

---

## Advanced Features

### Lifecycle Hooks

Override service methods to add custom logic:

```python
from outlabs_auth.services import UserService

class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        # Send welcome email
        await email_service.send_welcome(user.email)

        # Create default workspace
        await workspace_service.create_default(user.id)

        # Assign default role
        await self.role_service.assign_role_to_user(user.id, "reader")

        # Track analytics
        await analytics.track("user_registered", {
            "user_id": user.id,
            "email": user.email
        })

    async def on_after_login(self, user, request=None):
        # Update last login time
        await self.update_user(user.id, last_login=datetime.utcnow())

        # Track login
        await analytics.track("user_logged_in", {"user_id": user.id})

# Use custom service
auth = SimpleRBAC(
    database=db,
    user_service_class=MyUserService
)
```

**Available Hooks** (13 for UserService):
- `on_after_register`
- `on_after_login`
- `on_after_logout`
- `on_after_update`
- `on_after_delete`
- `on_after_verify`
- `on_after_forgot_password`
- `on_after_reset_password`
- And more...

See [[131-User-Hooks|User Lifecycle Hooks]] for complete list.

### API Key Authentication

Add API keys for programmatic access:

```python
from outlabs_auth.routers import get_api_keys_router

# Add API key routes
app.include_router(
    get_api_keys_router(auth),
    prefix="/api-keys",
    tags=["api-keys"]
)

# Create API key (as authenticated user)
api_key = await auth.api_key_service.create_api_key(
    user_id="user_123",
    name="Production API Key"
)

print(api_key.full_key)  # "ola_1234567890abcdef..."
# ⚠️ Save this! It's only shown once!

# Use API key
curl -H "X-API-Key: ola_1234567890abcdef..." \
  http://localhost:8000/posts
```

See [[23-API-Keys|API Keys Guide]] for details.

### Redis Caching

Enable Redis for 10x-100x performance improvement:

```python
auth = SimpleRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)
```

**Cached Data**:
- Permission checks (95%+ hit rate)
- Role lookups (98%+ hit rate)
- User sessions

**Performance**:
- Without Redis: ~5-10ms per permission check
- With Redis: ~0.5-1ms per permission check (cache hit)

See [[120-Redis-Integration|Redis Integration]] for details.

---

## Common Patterns

### Pattern 1: Default Role on Registration

```python
class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        # Assign "reader" role to all new users
        await self.role_service.assign_role_to_user(user.id, "reader")
```

### Pattern 2: Owner-Only Access

```python
@app.patch("/posts/{post_id}")
async def update_post(
    post_id: str,
    ctx = Depends(auth.deps.require_permission("post:update"))
):
    user = ctx.metadata.get("user")
    post = await get_post(post_id)

    # Only owner or admin can update
    if post.author_id != user.id and "admin" not in user.roles:
        raise HTTPException(403, "Can only update your own posts")

    # Update post...
```

### Pattern 3: Tiered Permissions

```python
# Free tier
await auth.role_service.create_role(
    name="free_user",
    permissions=["post:read", "post:create:5"]  # Create up to 5 posts
)

# Pro tier
await auth.role_service.create_role(
    name="pro_user",
    permissions=["post:read", "post:create:*", "post:analytics"]
)

# Check in route
@app.post("/posts")
async def create_post(ctx = Depends(auth.deps.require_permission("post:create"))):
    user = ctx.metadata.get("user")

    # Check post count for free users
    if "free_user" in user.roles:
        post_count = await count_user_posts(user.id)
        if post_count >= 5:
            raise HTTPException(403, "Upgrade to Pro for unlimited posts")

    # Create post...
```

### Pattern 4: Time-Limited Permissions

```python
from datetime import datetime, timedelta

# Grant temporary permission
await auth.permission_service.grant_temporary_permission(
    user_id="user_123",
    permission="admin:access",
    expires_at=datetime.utcnow() + timedelta(hours=24)
)

# Check will automatically respect expiration
```

---

## Testing

### Unit Tests

```python
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC

@pytest.fixture
async def auth():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_blog"]
    auth = SimpleRBAC(database=db)
    await auth.initialize()

    # Create test role
    await auth.role_service.create_role(
        name="test_role",
        permissions=["post:read", "post:create"]
    )

    yield auth

    # Cleanup
    await client.drop_database("test_blog")

@pytest.mark.asyncio
async def test_role_assignment(auth):
    # Create user
    user = await auth.user_service.create_user(
        email="test@example.com",
        password="password123"
    )

    # Assign role
    await auth.role_service.assign_role_to_user(user.id, "test_role")

    # Verify
    updated_user = await auth.user_service.get_user(user.id)
    assert "test_role" in updated_user.roles

@pytest.mark.asyncio
async def test_permission_check(auth):
    # Create user with role
    user = await auth.user_service.create_user(
        email="test@example.com",
        password="password123"
    )
    await auth.role_service.assign_role_to_user(user.id, "test_role")

    # Check permission
    has_read = await auth.permission_service.check_permission(
        user.id,
        "post:read"
    )
    assert has_read is True

    has_delete = await auth.permission_service.check_permission(
        user.id,
        "post:delete"
    )
    assert has_delete is False
```

### Integration Tests

```python
from fastapi.testclient import TestClient

def test_protected_route(client: TestClient, auth_token: str):
    # Access protected route
    response = client.get(
        "/posts",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200

def test_permission_denied(client: TestClient, user_token: str):
    # Try to access admin route without permission
    response = client.delete(
        "/admin/users/123",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
```

See [[113-Testing-Strategies|Testing Strategies]] for comprehensive guide.

---

## Migrating to EnterpriseRBAC

If you need hierarchical permissions later, upgrading is straightforward:

```python
# Before (SimpleRBAC)
from outlabs_auth import SimpleRBAC
auth = SimpleRBAC(database=db)

# After (EnterpriseRBAC)
from outlabs_auth import EnterpriseRBAC
auth = EnterpriseRBAC(database=db)

# All existing code continues to work!
# Just add entity hierarchy when needed
```

**What changes**:
- ✅ All existing users, roles, permissions stay the same
- ✅ All existing routes continue to work
- ✅ Can now create entity hierarchy
- ✅ Can now use tree permissions

See [[42-EnterpriseRBAC|EnterpriseRBAC Guide]] for details.

---

## API Reference

### SimpleRBAC Class

```python
class SimpleRBAC:
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        jwt_secret: str = None,
        jwt_algorithm: str = "HS256",
        access_token_lifetime: int = 900,  # 15 minutes
        refresh_token_lifetime: int = 2592000,  # 30 days
        enable_caching: bool = False,
        redis_url: str = None,
        user_service_class: Type[UserService] = UserService,
        role_service_class: Type[RoleService] = RoleService,
        auth_service_class: Type[AuthService] = AuthService,
    )
```

### Services

- `auth.user_service` - [[70-User-Service|UserService]]
- `auth.role_service` - [[71-Role-Service|RoleService]]
- `auth.permission_service` - [[72-Permission-Service|PermissionService]]
- `auth.api_key_service` - [[73-API-Key-Service|ApiKeyService]]
- `auth.auth_service` - [[74-Auth-Service|AuthService]]

### Dependencies

- `auth.deps.require_auth()` - [[81-Require-Auth|require_auth()]]
- `auth.deps.require_permission()` - [[82-Require-Permission|require_permission()]]
- `auth.deps.require_role()` - [[83-Require-Role|require_role()]]

---

## Next Steps

- **[[42-EnterpriseRBAC|EnterpriseRBAC]]** - Hierarchical RBAC
- **[[30-OAuth-Overview|OAuth]]** - Add social login
- **[[23-API-Keys|API Keys]]** - Programmatic access
- **[[150-Tutorial-Simple-App|Tutorial]]** - Build complete app

---

**Previous**: [[40-Authorization-Overview|← Authorization Overview]]
**Next**: [[42-EnterpriseRBAC|EnterpriseRBAC →]]
