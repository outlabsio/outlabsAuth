# 80-Auth-Dependencies.md - AuthDeps API Reference

Complete API reference for **AuthDeps** - FastAPI dependency injection for authentication and authorization.

---

## Table of Contents

1. [Overview](#overview)
2. [Setup](#setup)
3. [Dependencies](#dependencies)
4. [Complete Examples](#complete-examples)

---

## Overview

**AuthDeps** provides easy-to-use FastAPI dependency helpers for protecting routes.

### Features

- ✅ `authenticated()` - Require authenticated user
- ✅ `requires(permission)` - Require specific permission(s)
- ✅ `requires_any(permissions)` - Require any of the permissions
- ✅ `optional_auth()` - Optional authentication
- ✅ `superuser()` - Require superuser access

---

## Setup

```python
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")
deps = AuthDeps(auth)
```

---

## Dependencies

### authenticated()

Require authenticated user.

```python
@app.get("/protected")
async def protected_route(user = Depends(deps.authenticated())):
    return {"user_id": str(user.id), "email": user.email}
```

**Returns:** `UserModel`
**Raises:** `HTTPException(401)` if not authenticated

---

### requires(*permissions)

Require specific permission(s) - user must have **ALL**.

```python
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user = Depends(deps.requires("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}

# Multiple permissions (AND logic)
@app.post("/users/{user_id}/assign-role")
async def assign_role(
    user_id: str,
    role_id: str,
    admin = Depends(deps.requires("user:update", "role:assign"))
):
    # User must have BOTH permissions
    return {"message": "Role assigned"}
```

**Returns:** `UserModel`
**Raises:** `HTTPException(403)` if permission denied

---

### requires_any(*permissions)

Require **any** of the permissions - user needs **at least one**.

```python
@app.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user = Depends(deps.requires_any("user:update", "admin:all"))
):
    # User needs EITHER "user:update" OR "admin:all"
    return {"message": "User updated"}
```

**Returns:** `UserModel`
**Raises:** `HTTPException(403)` if no permissions match

---

### optional_auth()

Optional authentication - returns `None` if no token provided.

```python
@app.get("/public-or-private")
async def flexible_route(user = Depends(deps.optional_auth())):
    if user:
        return {"message": f"Hello {user.email}"}
    return {"message": "Hello guest"}
```

**Returns:** `Optional[UserModel]` - User or `None`

---

### superuser()

Require superuser access.

```python
@app.post("/admin/reset-database")
async def reset_db(admin = Depends(deps.superuser())):
    # Only superusers can access
    return {"message": "Database reset"}
```

**Returns:** `UserModel`
**Raises:** `HTTPException(403)` if not superuser

---

### user (property)

Shortcut for `authenticated()`.

```python
@app.get("/me")
async def get_me(user = Depends(deps.user)):
    return user
```

---

## Complete Examples

### Basic Authentication

```python
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")
deps = AuthDeps(auth)

@app.get("/users/me")
async def get_current_user(user = Depends(deps.authenticated())):
    """Get current user (requires authentication)."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.profile.full_name
    }
```

### Permission-Based Routes

```python
# Create user (requires "user:create" permission)
@app.post("/users")
async def create_user(
    email: str,
    password: str,
    admin = Depends(deps.requires("user:create"))
):
    user = await auth.user_service.create_user(email, password)
    return {"id": str(user.id), "email": user.email}

# Delete user (requires "user:delete" permission)
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin = Depends(deps.requires("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}

# Update user (requires EITHER permission)
@app.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user = Depends(deps.requires_any("user:update", "admin:all"))
):
    # User needs "user:update" OR "admin:all"
    return {"message": "User updated"}
```

### Optional Authentication

```python
@app.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    user = Depends(deps.optional_auth())
):
    """Get post (shows extra details if authenticated)."""
    post = await get_post_from_db(post_id)

    if user:
        # Authenticated - show full details
        return {
            "id": post_id,
            "title": post.title,
            "content": post.content,
            "author": post.author,
            "views": post.views
        }
    else:
        # Guest - show limited details
        return {
            "id": post_id,
            "title": post.title,
            "content": post.content[:100] + "..."
        }
```

### Admin Routes

```python
@app.post("/admin/maintenance")
async def start_maintenance(admin = Depends(deps.superuser())):
    """Start maintenance mode (superuser only)."""
    await enable_maintenance_mode()
    return {"message": "Maintenance mode enabled"}

@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    admin = Depends(deps.superuser())
):
    """Force delete user (superuser only)."""
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted by admin"}
```

### Combined Requirements

```python
@app.post("/projects/{project_id}/invite")
async def invite_to_project(
    project_id: str,
    invitee_email: str,
    user = Depends(deps.requires("project:manage", "user:invite"))
):
    """
    Invite user to project.
    Requires BOTH "project:manage" AND "user:invite" permissions.
    """
    # Check project ownership
    project = await get_project(project_id)
    if str(project.owner_id) != str(user.id):
        raise HTTPException(403, "Not project owner")

    # Send invitation
    await send_project_invitation(project_id, invitee_email)
    return {"message": "Invitation sent"}
```

---

## Summary

**AuthDeps** provides FastAPI dependency injection for:

✅ **authenticated()** - Require JWT authentication
✅ **requires(*perms)** - Require all permissions (AND)
✅ **requires_any(*perms)** - Require any permission (OR)
✅ **optional_auth()** - Optional authentication
✅ **superuser()** - Require superuser
✅ **user** - Shortcut for authenticated()

---

## Related Documentation

- **14-FastAPI-Integration.md** - FastAPI integration patterns
- **60-SimpleRBAC-API.md** - SimpleRBAC API reference
- **74-Auth-Service.md** - AuthService API reference
- **72-Permission-Service.md** - PermissionService API reference

---

**Last Updated:** 2025-01-14
