# 71-Role-Service.md - RoleService API Reference

Complete API reference for the **RoleService** - role management and permission assignment.

---

## Table of Contents

1. [Overview](#overview)
2. [Accessing RoleService](#accessing-roleservice)
3. [Role Management Methods](#role-management-methods)
4. [Permission Management](#permission-management)
5. [Role Lookup](#role-lookup)
6. [Role Listing](#role-listing)
7. [Context-Aware Roles](#context-aware-roles-enterpriserbac)
8. [System Roles](#system-roles)
9. [Error Handling](#error-handling)
10. [Complete Examples](#complete-examples)

---

## Overview

**RoleService** handles all role-related operations including:

- ✅ Role creation and management
- ✅ Permission assignment to roles
- ✅ Role listing and search
- ✅ System role protection
- ✅ Context-aware roles (EnterpriseRBAC)
- ✅ Entity-scoped roles (EnterpriseRBAC)
- ✅ Global roles (SimpleRBAC + EnterpriseRBAC)

### Role Model Fields

```python
class RoleModel:
    # Identity
    name: str                # Unique role name (slug)
    display_name: str        # Human-readable name
    description: str         # Optional description

    # Permissions
    permissions: list[str]   # Default permissions (all contexts)

    # Context-aware (EnterpriseRBAC only)
    entity_type_permissions: dict[str, list[str]]  # Type-specific permissions

    # Entity scope (EnterpriseRBAC)
    entity: EntityModel      # Optional entity scope

    # Configuration
    is_system_role: bool     # Cannot be modified
    is_global: bool          # Can be assigned anywhere

    # Type restrictions (EnterpriseRBAC)
    assignable_at_types: list[str]  # Allowed entity types
```

### SimpleRBAC vs EnterpriseRBAC

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|------------|----------------|
| **Global Roles** | ✅ Yes (default) | ✅ Yes (optional) |
| **Default Permissions** | ✅ Yes | ✅ Yes |
| **Context-Aware Permissions** | ❌ No | ✅ Optional |
| **Entity-Scoped Roles** | ❌ No | ✅ Yes |
| **Type Restrictions** | ❌ No | ✅ Yes |

---

## Accessing RoleService

### SimpleRBAC

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db, secret_key="...")
await auth.initialize()

# Access RoleService
role_service = auth.role_service
```

### EnterpriseRBAC

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(database=db, secret_key="...")
await auth.initialize()

# Access RoleService
role_service = auth.role_service
```

---

## Role Management Methods

### create_role()

Create a new role.

```python
role = await auth.role_service.create_role(
    name="developer",
    display_name="Developer",
    description="Software developer role",
    permissions=["code:read", "code:write", "repo:push"],
    is_global=True,              # Optional (default: True)
    is_system_role=False,        # Optional (default: False)
    entity_id=None               # Optional (EnterpriseRBAC only)
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | ✅ Yes | Role name (slug, normalized to lowercase) |
| `display_name` | `str` | ✅ Yes | Human-readable name |
| `description` | `str` | ❌ No | Role description |
| `permissions` | `list[str]` | ❌ No | Permission names (default: []) |
| `is_global` | `bool` | ❌ No | Can be assigned anywhere (default: True) |
| `is_system_role` | `bool` | ❌ No | System role protection (default: False) |
| `entity_id` | `str` | ❌ No | Entity scope (EnterpriseRBAC only) |

**Returns:** `RoleModel`

**Raises:**
- `InvalidInputError` - Role name already exists or is invalid
- `EntityNotFoundError` - Entity ID not found (EnterpriseRBAC)

**Example:**

```python
# Create basic role
developer_role = await auth.role_service.create_role(
    name="developer",
    display_name="Developer",
    permissions=["code:read", "code:write"]
)

# Create admin role
admin_role = await auth.role_service.create_role(
    name="admin",
    display_name="Administrator",
    description="Full system access",
    permissions=[
        "user:create", "user:read", "user:update", "user:delete",
        "role:create", "role:read", "role:update", "role:delete"
    ]
)

# Create system role (protected)
superadmin_role = await auth.role_service.create_role(
    name="superadmin",
    display_name="Super Administrator",
    permissions=["*:*"],  # All permissions
    is_system_role=True   # Cannot be modified or deleted
)
```

**Entity-Scoped Role (EnterpriseRBAC):**

```python
# Create role scoped to specific entity
engineering_manager = await auth.role_service.create_role(
    name="engineering_manager",
    display_name="Engineering Manager",
    permissions=["project:manage_tree", "budget:approve_tree"],
    is_global=False,
    entity_id=str(engineering_dept.id)  # Can only be assigned in Engineering
)
```

### get_role_by_id()

Get role by ID.

```python
role = await auth.role_service.get_role_by_id("507f1f77bcf86cd799439011")
if role:
    print(role.display_name)
```

**Parameters:**
- `role_id` (str): Role ID

**Returns:** `Optional[RoleModel]` - Role or `None` if not found

**Example:**

```python
role = await auth.role_service.get_role_by_id(str(role.id))
if role:
    print(f"Role: {role.display_name}")
    print(f"Permissions: {', '.join(role.permissions)}")
```

### get_role_by_name()

Get role by name.

```python
role = await auth.role_service.get_role_by_name("developer")
if role:
    print(f"Role ID: {str(role.id)}")
```

**Parameters:**
- `name` (str): Role name (case-insensitive)

**Returns:** `Optional[RoleModel]` - Role or `None` if not found

**Example:**

```python
# Check if role exists before creating
existing = await auth.role_service.get_role_by_name("admin")
if existing:
    print("Admin role already exists")
else:
    admin = await auth.role_service.create_role(
        name="admin",
        display_name="Administrator",
        permissions=["*:*"]
    )
```

### update_role()

Update role fields.

```python
role = await auth.role_service.update_role(
    role_id="507f1f77bcf86cd799439011",
    display_name="Senior Developer",     # Optional
    description="Experienced developer", # Optional
    permissions=["code:read", "code:write", "code:review"]  # Optional (replaces)
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `role_id` | `str` | ✅ Yes | Role ID |
| `display_name` | `str` | ❌ No | Updated display name |
| `description` | `str` | ❌ No | Updated description |
| `permissions` | `list[str]` | ❌ No | Updated permissions (replaces existing) |

**Returns:** `RoleModel` - Updated role

**Raises:**
- `RoleNotFoundError` - Role doesn't exist
- `InvalidInputError` - Trying to modify system role

**Note:** Cannot update `name` or `is_system_role` after creation.

**Example:**

```python
# Update display name
role = await auth.role_service.update_role(
    role_id=str(developer_role.id),
    display_name="Senior Developer"
)

# Update permissions (replaces existing)
role = await auth.role_service.update_role(
    role_id=str(developer_role.id),
    permissions=["code:read", "code:write", "code:review", "code:deploy"]
)

# Update multiple fields
role = await auth.role_service.update_role(
    role_id=str(developer_role.id),
    display_name="Lead Developer",
    description="Team lead with code review responsibilities",
    permissions=["code:read", "code:write", "code:review", "team:manage"]
)
```

### delete_role()

Delete a role.

```python
deleted = await auth.role_service.delete_role("507f1f77bcf86cd799439011")
if deleted:
    print("Role deleted")
else:
    print("Role not found")
```

**Parameters:**
- `role_id` (str): Role ID

**Returns:** `bool` - `True` if deleted, `False` if not found

**Raises:**
- `InvalidInputError` - Trying to delete system role

**Warning:** This is a hard delete. Users with this role will lose those permissions.

**Example:**

```python
# Delete role with confirmation
role = await auth.role_service.get_role_by_id(role_id)
if role:
    if role.is_system_role:
        print("Cannot delete system role")
    else:
        # Check for users with this role
        members = await auth.membership_service.get_members_with_role(role_id)
        if members:
            print(f"Warning: {len(members)} users have this role")

        # Delete
        deleted = await auth.role_service.delete_role(role_id)
        if deleted:
            print(f"Deleted role: {role.display_name}")
```

---

## Permission Management

### add_permissions()

Add permissions to role (without removing existing).

```python
role = await auth.role_service.add_permissions(
    role_id="507f1f77bcf86cd799439011",
    permissions=["code:deploy", "user:invite"]
)
```

**Parameters:**
- `role_id` (str): Role ID
- `permissions` (list[str]): Permission names to add

**Returns:** `RoleModel` - Updated role

**Raises:**
- `RoleNotFoundError` - Role doesn't exist
- `InvalidInputError` - Trying to modify system role

**Example:**

```python
# Add single permission
role = await auth.role_service.add_permissions(
    role_id=str(developer_role.id),
    permissions=["code:deploy"]
)

# Add multiple permissions
role = await auth.role_service.add_permissions(
    role_id=str(developer_role.id),
    permissions=["user:invite", "team:view"]
)

# Idempotent - duplicates are ignored
role = await auth.role_service.add_permissions(
    role_id=str(developer_role.id),
    permissions=["code:read"]  # Already exists, no change
)
```

### remove_permissions()

Remove permissions from role.

```python
role = await auth.role_service.remove_permissions(
    role_id="507f1f77bcf86cd799439011",
    permissions=["code:deploy"]
)
```

**Parameters:**
- `role_id` (str): Role ID
- `permissions` (list[str]): Permission names to remove

**Returns:** `RoleModel` - Updated role

**Raises:**
- `RoleNotFoundError` - Role doesn't exist
- `InvalidInputError` - Trying to modify system role

**Example:**

```python
# Remove single permission
role = await auth.role_service.remove_permissions(
    role_id=str(developer_role.id),
    permissions=["code:deploy"]
)

# Remove multiple permissions
role = await auth.role_service.remove_permissions(
    role_id=str(developer_role.id),
    permissions=["user:invite", "team:manage"]
)
```

### get_role_permissions()

Get all permissions for a role.

```python
permissions = await auth.role_service.get_role_permissions("507f...")
print(permissions)
# Output: ['code:read', 'code:write', 'repo:push']
```

**Parameters:**
- `role_id` (str): Role ID

**Returns:** `list[str]` - Permission names

**Raises:**
- `RoleNotFoundError` - Role doesn't exist

**Example:**

```python
role = await auth.role_service.get_role_by_name("admin")
permissions = await auth.role_service.get_role_permissions(str(role.id))

print(f"Admin permissions ({len(permissions)}):")
for perm in permissions:
    print(f"  - {perm}")
```

---

## Role Lookup

### list_roles()

List roles with pagination.

```python
roles, total = await auth.role_service.list_roles(
    page=1,
    limit=20,
    is_global=None  # Optional filter
)
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | `int` | ❌ No | `1` | Page number (1-indexed) |
| `limit` | `int` | ❌ No | `20` | Results per page |
| `is_global` | `bool` | ❌ No | `None` | Filter by global flag |

**Returns:** `tuple[list[RoleModel], int]` - (roles, total_count)

**Example:**

```python
# Get first page
roles, total = await auth.role_service.list_roles(page=1, limit=10)
print(f"Showing {len(roles)} of {total} roles")

for role in roles:
    print(f"- {role.display_name} ({len(role.permissions)} permissions)")

# Pagination
total_pages = (total + limit - 1) // limit
print(f"Total pages: {total_pages}")

# Filter by global
global_roles, global_total = await auth.role_service.list_roles(
    is_global=True
)
print(f"Global roles: {global_total}")
```

**API Route Example:**

```python
from pydantic import BaseModel

class RoleListResponse(BaseModel):
    roles: list[dict]
    total: int
    page: int
    limit: int

@app.get("/admin/roles", response_model=RoleListResponse)
async def list_roles(
    page: int = 1,
    limit: int = 20,
    admin = Depends(deps.requires("role:list"))
):
    roles, total = await auth.role_service.list_roles(
        page=page,
        limit=limit
    )

    return {
        "roles": [
            {
                "id": str(r.id),
                "name": r.name,
                "display_name": r.display_name,
                "description": r.description,
                "permissions": r.permissions,
                "is_global": r.is_global,
                "is_system_role": r.is_system_role,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in roles
        ],
        "total": total,
        "page": page,
        "limit": limit
    }
```

---

## Context-Aware Roles (EnterpriseRBAC)

Context-aware roles have **different permissions based on entity type**.

### Creating Context-Aware Roles

```python
from outlabs_auth import EnterpriseRBAC

# Enable context-aware roles
auth = EnterpriseRBAC(
    database=db,
    secret_key="...",
    enable_context_aware_roles=True
)

# Create context-aware role
manager_role = await auth.role_service.create_role(
    name="manager",
    display_name="Manager",
    permissions=["project:read", "project:write"],  # Default permissions
    entity_type_permissions={
        "department": ["budget:approve", "team:manage_tree"],
        "team": ["task:assign", "member:add"]
    }
)
```

**Behavior:**
- When assigned in **department**: Gets `project:read`, `project:write`, `budget:approve`, `team:manage_tree`
- When assigned in **team**: Gets `project:read`, `project:write`, `task:assign`, `member:add`
- When assigned elsewhere: Gets only default permissions (`project:read`, `project:write`)

### Getting Permissions by Entity Type

```python
role = await auth.role_service.get_role_by_name("manager")

# Get permissions for department
dept_perms = role.get_permissions_for_entity_type("department")
print(dept_perms)
# ['project:read', 'project:write', 'budget:approve', 'team:manage_tree']

# Get permissions for team
team_perms = role.get_permissions_for_entity_type("team")
print(team_perms)
# ['project:read', 'project:write', 'task:assign', 'member:add']

# Get default permissions
default_perms = role.get_permissions_for_entity_type(None)
print(default_perms)
# ['project:read', 'project:write']
```

### Updating Context-Aware Permissions

```python
role = await auth.role_service.get_role_by_name("manager")

# Update entity type permissions
role.entity_type_permissions = {
    "department": [
        "budget:approve",
        "team:manage_tree",
        "user:hire"  # Added
    ],
    "team": [
        "task:assign",
        "member:add",
        "sprint:manage"  # Added
    ],
    "project": [
        "milestone:set",
        "resource:allocate"
    ]
}

await role.save()
```

**See Also:** **41-RBAC-Patterns.md** for complete context-aware role guide.

---

## System Roles

System roles are **protected roles** that cannot be modified or deleted.

### Creating System Roles

```python
# Create system role
superadmin = await auth.role_service.create_role(
    name="superadmin",
    display_name="Super Administrator",
    permissions=["*:*"],
    is_system_role=True  # Protected
)
```

### System Role Protection

```python
# ❌ Cannot update system role
try:
    await auth.role_service.update_role(
        role_id=str(superadmin.id),
        permissions=["user:read"]
    )
except InvalidInputError as e:
    print(e.message)  # "Cannot modify system role"

# ❌ Cannot delete system role
try:
    await auth.role_service.delete_role(str(superadmin.id))
except InvalidInputError as e:
    print(e.message)  # "Cannot delete system role"
```

### Use Cases for System Roles

```python
# Bootstrap admin role (cannot be modified by users)
bootstrap_admin = await auth.role_service.create_role(
    name="bootstrap_admin",
    display_name="Bootstrap Administrator",
    description="Initial admin account for system setup",
    permissions=["*:*"],
    is_system_role=True
)

# Service account role
service_role = await auth.role_service.create_role(
    name="internal_service",
    display_name="Internal Service",
    description="For microservice-to-microservice communication",
    permissions=["api:internal", "data:sync"],
    is_system_role=True
)
```

---

## Error Handling

### Exception Types

```python
from outlabs_auth.core.exceptions import (
    RoleNotFoundError,
    InvalidInputError,
    EntityNotFoundError,
)
```

### Error Handling Pattern

```python
from fastapi import HTTPException

@app.post("/admin/roles")
async def create_role_endpoint(
    name: str,
    display_name: str,
    permissions: list[str],
    admin = Depends(deps.requires("role:create"))
):
    try:
        role = await auth.role_service.create_role(
            name=name,
            display_name=display_name,
            permissions=permissions
        )
        return {
            "id": str(role.id),
            "name": role.name,
            "display_name": role.display_name
        }
    except InvalidInputError as e:
        # Role name already exists
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create role: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/admin/roles/{role_id}")
async def update_role_endpoint(
    role_id: str,
    permissions: list[str],
    admin = Depends(deps.requires("role:update"))
):
    try:
        role = await auth.role_service.update_role(
            role_id=role_id,
            permissions=permissions
        )
        return {"message": "Role updated", "role": role.name}
    except RoleNotFoundError:
        raise HTTPException(status_code=404, detail="Role not found")
    except InvalidInputError as e:
        # Trying to modify system role
        raise HTTPException(status_code=403, detail=str(e))
```

---

## Complete Examples

### Role Management API

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.core.exceptions import RoleNotFoundError, InvalidInputError

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")
deps = AuthDeps(auth)

class CreateRoleRequest(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: list[str] = []

class UpdateRoleRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[list[str]] = None

# ============================================
# Role CRUD
# ============================================

@app.post("/admin/roles")
async def create_role(
    data: CreateRoleRequest,
    admin = Depends(deps.requires("role:create"))
):
    """Create new role."""
    try:
        role = await auth.role_service.create_role(
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            permissions=data.permissions
        )
        return {
            "id": str(role.id),
            "name": role.name,
            "display_name": role.display_name,
            "permissions": role.permissions
        }
    except InvalidInputError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.get("/admin/roles/{role_id}")
async def get_role(
    role_id: str,
    admin = Depends(deps.requires("role:read"))
):
    """Get role by ID."""
    role = await auth.role_service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return {
        "id": str(role.id),
        "name": role.name,
        "display_name": role.display_name,
        "description": role.description,
        "permissions": role.permissions,
        "is_global": role.is_global,
        "is_system_role": role.is_system_role,
        "created_at": role.created_at.isoformat() if role.created_at else None
    }

@app.get("/admin/roles")
async def list_roles(
    page: int = 1,
    limit: int = 20,
    admin = Depends(deps.requires("role:list"))
):
    """List all roles with pagination."""
    roles, total = await auth.role_service.list_roles(page=page, limit=limit)

    return {
        "roles": [
            {
                "id": str(r.id),
                "name": r.name,
                "display_name": r.display_name,
                "permissions_count": len(r.permissions),
                "is_system_role": r.is_system_role
            }
            for r in roles
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@app.put("/admin/roles/{role_id}")
async def update_role(
    role_id: str,
    data: UpdateRoleRequest,
    admin = Depends(deps.requires("role:update"))
):
    """Update role."""
    try:
        role = await auth.role_service.update_role(
            role_id=role_id,
            display_name=data.display_name,
            description=data.description,
            permissions=data.permissions
        )
        return {
            "message": "Role updated",
            "role": {
                "id": str(role.id),
                "name": role.name,
                "display_name": role.display_name
            }
        }
    except RoleNotFoundError:
        raise HTTPException(status_code=404, detail="Role not found")
    except InvalidInputError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.delete("/admin/roles/{role_id}")
async def delete_role(
    role_id: str,
    admin = Depends(deps.requires("role:delete"))
):
    """Delete role."""
    try:
        deleted = await auth.role_service.delete_role(role_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Role not found")
        return {"message": "Role deleted"}
    except InvalidInputError as e:
        # Cannot delete system role
        raise HTTPException(status_code=403, detail=str(e))

# ============================================
# Permission Management
# ============================================

@app.post("/admin/roles/{role_id}/permissions")
async def add_permissions(
    role_id: str,
    permissions: list[str],
    admin = Depends(deps.requires("role:update"))
):
    """Add permissions to role."""
    try:
        role = await auth.role_service.add_permissions(role_id, permissions)
        return {
            "message": f"Added {len(permissions)} permission(s)",
            "permissions": role.permissions
        }
    except RoleNotFoundError:
        raise HTTPException(status_code=404, detail="Role not found")
    except InvalidInputError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.delete("/admin/roles/{role_id}/permissions")
async def remove_permissions(
    role_id: str,
    permissions: list[str],
    admin = Depends(deps.requires("role:update"))
):
    """Remove permissions from role."""
    try:
        role = await auth.role_service.remove_permissions(role_id, permissions)
        return {
            "message": f"Removed {len(permissions)} permission(s)",
            "permissions": role.permissions
        }
    except RoleNotFoundError:
        raise HTTPException(status_code=404, detail="Role not found")
    except InvalidInputError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.get("/admin/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: str,
    admin = Depends(deps.requires("role:read"))
):
    """Get all permissions for role."""
    try:
        permissions = await auth.role_service.get_role_permissions(role_id)
        return {
            "role_id": role_id,
            "permissions": permissions,
            "count": len(permissions)
        }
    except RoleNotFoundError:
        raise HTTPException(status_code=404, detail="Role not found")
```

### Bootstrap Roles on Startup

```python
@app.on_event("startup")
async def startup():
    await auth.initialize()
    await create_default_roles()

async def create_default_roles():
    """Create default roles if they don't exist."""

    # Admin role
    admin = await auth.role_service.get_role_by_name("admin")
    if not admin:
        admin = await auth.role_service.create_role(
            name="admin",
            display_name="Administrator",
            description="Full system access",
            permissions=[
                "user:create", "user:read", "user:update", "user:delete",
                "role:create", "role:read", "role:update", "role:delete",
                "permission:grant", "permission:revoke"
            ],
            is_system_role=True
        )
        print(f"Created admin role: {str(admin.id)}")

    # User role
    user = await auth.role_service.get_role_by_name("user")
    if not user:
        user = await auth.role_service.create_role(
            name="user",
            display_name="User",
            description="Standard user access",
            permissions=[
                "profile:read", "profile:update"
            ]
        )
        print(f"Created user role: {str(user.id)}")

    # Developer role
    developer = await auth.role_service.get_role_by_name("developer")
    if not developer:
        developer = await auth.role_service.create_role(
            name="developer",
            display_name="Developer",
            description="Software developer access",
            permissions=[
                "code:read", "code:write",
                "repo:push", "repo:pull",
                "issue:create", "issue:update"
            ]
        )
        print(f"Created developer role: {str(developer.id)}")
```

---

## Summary

**RoleService** provides complete role management:

✅ **Role Creation** - `create_role()` with validation
✅ **Role Lookup** - `get_role_by_id()`, `get_role_by_name()`
✅ **Role Updates** - `update_role()` for modifications
✅ **Role Deletion** - `delete_role()` with protection
✅ **Permission Management** - `add_permissions()`, `remove_permissions()`
✅ **Permission Lookup** - `get_role_permissions()`
✅ **Role Listing** - `list_roles()` with pagination
✅ **System Roles** - Protected roles that cannot be modified
✅ **Context-Aware** - Different permissions by entity type (EnterpriseRBAC)
✅ **Entity Scoping** - Roles scoped to specific entities (EnterpriseRBAC)

---

## Related Documentation

- **41-RBAC-Patterns.md** - RBAC patterns and best practices
- **60-SimpleRBAC-API.md** - SimpleRBAC API reference
- **61-EnterpriseRBAC-API.md** - EnterpriseRBAC API reference
- **70-User-Service.md** - UserService API reference
- **72-Permission-Service.md** - PermissionService API reference

---

**Last Updated:** 2025-01-14
