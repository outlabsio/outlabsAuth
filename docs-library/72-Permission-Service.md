# 72-Permission-Service.md - PermissionService API Reference

Complete API reference for the **PermissionService** - permission checking and management.

---

## Table of Contents

1. [Overview](#overview)
2. [Accessing PermissionService](#accessing-permissionservice)
3. [Permission Checking Methods](#permission-checking-methods)
4. [Enterprise Permission Checking](#enterprise-permission-checking-enterpriserbac)
5. [Tree Permissions](#tree-permissions-enterpriserbac)
6. [Permission CRUD](#permission-crud)
7. [Wildcard Permissions](#wildcard-permissions)
8. [Permission Resolution Flow](#permission-resolution-flow)
9. [Error Handling](#error-handling)
10. [Complete Examples](#complete-examples)

---

## Overview

**PermissionService** handles all permission-related operations including:

- ✅ Permission checking (user has permission?)
- ✅ Entity-scoped permissions (EnterpriseRBAC)
- ✅ Tree permissions with closure table (EnterpriseRBAC)
- ✅ Wildcard permissions (`user:*`, `*:*`)
- ✅ Platform-wide permissions (`_all` suffix)
- ✅ Permission management (CRUD)
- ✅ Redis caching (optional)
- ✅ ABAC policy evaluation (optional)

### Two Implementations

| Service | Preset | Features |
|---------|--------|----------|
| **BasicPermissionService** | SimpleRBAC | Flat permission checking, wildcards |
| **EnterprisePermissionService** | EnterpriseRBAC | + Entity scope, tree permissions, closure table |

### Permission Naming Convention

```python
# Standard format: resource:action
"user:create"       # Create users
"user:read"         # Read user data
"user:update"       # Update users
"user:delete"       # Delete users

# Wildcard formats
"user:*"            # All user actions
"*:*"               # All permissions (superuser)

# Tree permissions (EnterpriseRBAC only)
"project:approve_tree"  # Approve in this entity + all descendants

# Platform-wide (EnterpriseRBAC only)
"analytics:view_all"    # View analytics in ALL entities
```

---

## Accessing PermissionService

### SimpleRBAC (BasicPermissionService)

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db, secret_key="...")
await auth.initialize()

# Access BasicPermissionService
perm_service = auth.permission_service
```

### EnterpriseRBAC (EnterprisePermissionService)

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(database=db, secret_key="...")
await auth.initialize()

# Access EnterprisePermissionService
perm_service = auth.permission_service
```

---

## Permission Checking Methods

### check_permission() - SimpleRBAC

Check if user has a specific permission (flat, no entity context).

```python
has_perm = await auth.permission_service.check_permission(
    user_id="507f1f77bcf86cd799439011",
    permission="user:create"
)
```

**Parameters:**
- `user_id` (str): User ID
- `permission` (str): Permission name (e.g., "user:create")

**Returns:** `bool` - `True` if user has permission

**Raises:**
- `UserNotFoundError` - User doesn't exist

**Example:**

```python
# Check single permission
has_perm = await auth.permission_service.check_permission(
    user_id=str(user.id),
    permission="user:delete"
)

if has_perm:
    await auth.user_service.delete_user(target_user_id)
else:
    raise PermissionError("You don't have permission to delete users")
```

**Wildcard Support:**

```python
# User has "user:*" permission
has_create = await auth.permission_service.check_permission(
    user_id, "user:create"
)  # True (matches user:*)

# User has "*:*" permission (superuser)
has_any = await auth.permission_service.check_permission(
    user_id, "invoice:approve"
)  # True (matches *:*)
```

### get_user_permissions() - SimpleRBAC

Get all permissions for a user.

```python
permissions = await auth.permission_service.get_user_permissions(
    user_id="507f1f77bcf86cd799439011"
)
print(permissions)
# ['user:create', 'user:read', 'user:update', 'role:read']
```

**Parameters:**
- `user_id` (str): User ID

**Returns:** `list[str]` - List of permission names

**Raises:**
- `UserNotFoundError` - User doesn't exist

**Example:**

```python
user = await auth.user_service.get_user_by_email("admin@example.com")
permissions = await auth.permission_service.get_user_permissions(str(user.id))

print(f"Admin permissions ({len(permissions)}):")
for perm in permissions:
    print(f"  - {perm}")
```

### require_permission()

Require user to have permission (raises exception if not).

```python
await auth.permission_service.require_permission(
    user_id="507f1f77bcf86cd799439011",
    permission="user:delete"
)
# Raises PermissionDeniedError if user lacks permission
```

**Parameters:**
- `user_id` (str): User ID
- `permission` (str): Required permission

**Returns:** `None`

**Raises:**
- `UserNotFoundError` - User doesn't exist
- `PermissionDeniedError` - User lacks permission

**Example:**

```python
from outlabs_auth.core.exceptions import PermissionDeniedError

try:
    # Require permission before action
    await auth.permission_service.require_permission(
        user_id=str(current_user.id),
        permission="invoice:approve"
    )

    # Permission granted - proceed with action
    await approve_invoice(invoice_id)

except PermissionDeniedError as e:
    print(f"Access denied: {e.message}")
```

### require_any_permission()

Require user to have **at least one** of the permissions.

```python
await auth.permission_service.require_any_permission(
    user_id="507f...",
    permissions=["user:update", "user:delete"]
)
```

**Parameters:**
- `user_id` (str): User ID
- `permissions` (list[str]): List of permission names (OR logic)

**Returns:** `None`

**Raises:**
- `UserNotFoundError` - User doesn't exist
- `PermissionDeniedError` - User lacks all permissions

**Example:**

```python
# User needs either "user:update" OR "user:delete"
await auth.permission_service.require_any_permission(
    user_id=str(current_user.id),
    permissions=["user:update", "user:delete"]
)

# If user has at least one, proceed
await modify_user(target_user_id)
```

### require_all_permissions()

Require user to have **all** of the permissions.

```python
await auth.permission_service.require_all_permissions(
    user_id="507f...",
    permissions=["user:create", "role:assign"]
)
```

**Parameters:**
- `user_id` (str): User ID
- `permissions` (list[str]): List of permission names (AND logic)

**Returns:** `None`

**Raises:**
- `UserNotFoundError` - User doesn't exist
- `PermissionDeniedError` - User lacks any permission

**Example:**

```python
# User needs BOTH "user:create" AND "role:assign"
await auth.permission_service.require_all_permissions(
    user_id=str(current_user.id),
    permissions=["user:create", "role:assign"]
)

# If user has all permissions, proceed
await create_user_with_role(email, password, role_id)
```

---

## Enterprise Permission Checking (EnterpriseRBAC)

### check_permission() - EnterpriseRBAC

Check if user has permission **with entity context**.

```python
has_perm, source = await auth.permission_service.check_permission(
    user_id="507f1f77bcf86cd799439011",
    permission="project:approve",
    entity_id="60c72b2f9b1d8b3a4c8e4f1a"  # Optional
)
```

**Parameters:**
- `user_id` (str): User ID
- `permission` (str): Permission name
- `entity_id` (str, optional): Entity ID for scoped check

**Returns:** `tuple[bool, str]` - (has_permission, source)

**Permission Sources:**
- `"direct"` - User is a member of the target entity
- `"tree"` - Permission inherited from ancestor entity via tree permission
- `"all"` - Platform-wide permission (`_all` suffix)
- `"superuser"` - User is a superuser
- `"none"` - No permission found

**Raises:**
- `UserNotFoundError` - User doesn't exist

**Example:**

```python
# Check permission in specific entity
has_perm, source = await auth.permission_service.check_permission(
    user_id=str(user.id),
    permission="project:approve",
    entity_id=str(backend_team.id)
)

if has_perm:
    print(f"Permission granted via: {source}")
    if source == "tree":
        print("User has tree permission from ancestor entity")
    elif source == "direct":
        print("User is direct member of this entity")
    elif source == "all":
        print("User has platform-wide permission")
```

### Permission Resolution Algorithm

EnterpriseRBAC uses a sophisticated resolution algorithm:

```
1. Check Redis cache (if enabled)
2. Check if user is superuser → Grant all permissions
3. Check direct permission in target entity
   - User is a member of the entity
   - Role has the permission
4. Check tree permission in ancestor entities
   - Get all ancestors via closure table (O(1))
   - Check if user has tree permission (_tree suffix) in any ancestor
5. Check platform-wide permission (_all suffix)
   - Permission granted in ANY entity the user belongs to
6. Cache result in Redis (if enabled)
```

### has_permission()

Convenience method that only returns boolean (hides source).

```python
has_perm = await auth.permission_service.has_permission(
    user_id=str(user.id),
    permission="project:approve",
    entity_id=str(entity.id)
)
```

**Parameters:**
- `user_id` (str): User ID
- `permission` (str): Permission name
- `entity_id` (str, optional): Entity ID

**Returns:** `bool` - `True` if user has permission

**Example:**

```python
# Simple boolean check (ignore source)
if await auth.permission_service.has_permission(user_id, "budget:approve", entity_id):
    await approve_budget(entity_id, amount)
```

### get_user_permissions_in_entity()

Get all permissions user has in specific entity.

```python
permissions = await auth.permission_service.get_user_permissions_in_entity(
    user_id="507f...",
    entity_id="60c72b2f9b1d8b3a4c8e4f1a"
)
```

**Parameters:**
- `user_id` (str): User ID
- `entity_id` (str): Entity ID

**Returns:** `list[str]` - Permission names

**Raises:**
- `UserNotFoundError` - User doesn't exist

**Example:**

```python
# Get all permissions in Engineering department
permissions = await auth.permission_service.get_user_permissions_in_entity(
    user_id=str(user.id),
    entity_id=str(engineering_dept.id)
)

print(f"Permissions in Engineering ({len(permissions)}):")
for perm in permissions:
    print(f"  - {perm}")
```

---

## Tree Permissions (EnterpriseRBAC)

Tree permissions allow **hierarchical permission inheritance** via closure table.

### Permission Naming

```python
# Tree permission format: resource:action_tree
"project:approve_tree"     # Approve projects in entity + descendants
"budget:view_tree"         # View budgets in entity + descendants
"team:manage_tree"         # Manage teams in entity + descendants
```

### check_tree_permission()

Check if user has tree permission for target entity.

```python
can_update_tree = await auth.permission_service.check_tree_permission(
    user_id=str(user.id),
    permission="entity:update_tree",
    target_entity_id=str(target_entity.id)
)
```

**Parameters:**
- `user_id` (str): User ID
- `permission` (str): Tree permission name (with `_tree` suffix)
- `target_entity_id` (str): Target entity ID

**Returns:** `bool` - `True` if user has tree permission

**Example:**

```python
# User has "project:approve_tree" in Engineering department
# Check if they can approve in Backend team (descendant of Engineering)
can_approve = await auth.permission_service.check_tree_permission(
    user_id=str(manager.id),
    permission="project:approve_tree",
    target_entity_id=str(backend_team.id)
)  # True - inherited from Engineering
```

### Tree Permission Flow

```python
# Setup hierarchy
org = await auth.entity_service.create_entity(
    name="acme_corp",
    display_name="ACME Corporation",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="organization"
)

engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(org.id)
)

backend_team = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(engineering.id)
)

# Create role with tree permission
manager_role = await auth.role_service.create_role(
    name="manager",
    permissions=["project:approve_tree"]  # Tree permission
)

# Assign manager to Engineering
await auth.membership_service.add_member(
    entity_id=str(engineering.id),
    user_id=str(manager.id),
    role_ids=[str(manager_role.id)],
    granted_by=str(admin.id)
)

# Check permission in Backend team (descendant of Engineering)
has_perm, source = await auth.permission_service.check_permission(
    user_id=str(manager.id),
    permission="project:approve",
    entity_id=str(backend_team.id)
)
# has_perm = True
# source = "tree" (inherited from Engineering)
```

**See Also:** **43-Tree-Permissions.md** for complete tree permission guide.

---

## Permission CRUD

### create_permission()

Create a new permission definition.

```python
permission = await auth.permission_service.create_permission(
    name="invoice:approve",
    display_name="Approve Invoices",
    description="Can approve invoices up to $10,000",
    is_system=False
)
```

**Parameters:**
- `name` (str): Permission name (e.g., "invoice:approve")
- `display_name` (str): Human-readable name
- `description` (str): Permission description
- `is_system` (bool): System permission (cannot be deleted)

**Returns:** `PermissionModel`

**Example:**

```python
# Create custom permission
approval_perm = await auth.permission_service.create_permission(
    name="invoice:approve",
    display_name="Approve Invoices",
    description="Approve invoices up to $10,000"
)

# Add to role
await auth.role_service.add_permissions(
    role_id=str(accountant_role.id),
    permissions=["invoice:approve"]
)
```

### get_permission_by_name()

Get permission definition by name.

```python
permission = await auth.permission_service.get_permission_by_name("invoice:approve")
if permission:
    print(permission.display_name)
```

**Parameters:**
- `name` (str): Permission name

**Returns:** `Optional[PermissionModel]` - Permission or `None`

**Example:**

```python
perm = await auth.permission_service.get_permission_by_name("user:delete")
if perm:
    print(f"Permission: {perm.display_name}")
    print(f"Description: {perm.description}")
```

### list_permissions()

List all permissions with pagination.

```python
permissions, total = await auth.permission_service.list_permissions(
    page=1,
    limit=50,
    resource="user"  # Optional filter
)
```

**Parameters:**
- `page` (int): Page number (1-indexed)
- `limit` (int): Results per page (default: 50)
- `resource` (str, optional): Filter by resource (e.g., "user")

**Returns:** `tuple[list[PermissionModel], int]` - (permissions, total_count)

**Example:**

```python
# List all user permissions
user_perms, total = await auth.permission_service.list_permissions(
    page=1,
    limit=100,
    resource="user"
)

print(f"User permissions ({total}):")
for perm in user_perms:
    print(f"  - {perm.name}: {perm.display_name}")
```

### delete_permission()

Delete permission definition.

```python
deleted = await auth.permission_service.delete_permission("507f...")
```

**Parameters:**
- `permission_id` (str): Permission ID

**Returns:** `bool` - `True` if deleted

**Raises:**
- `InvalidInputError` - Cannot delete system permission

**Example:**

```python
perm = await auth.permission_service.get_permission_by_name("temp:test")
if perm and not perm.is_system:
    await auth.permission_service.delete_permission(str(perm.id))
```

---

## Wildcard Permissions

### Wildcard Patterns

```python
# Resource wildcard - all actions on resource
"user:*"         # Matches: user:create, user:read, user:update, user:delete

# Full wildcard - all permissions (superuser)
"*:*"            # Matches: ANY permission

# Tree wildcard (EnterpriseRBAC)
"user:*_tree"    # Matches: user:create, user:read, etc. in entity + descendants

# Platform-wide wildcard (EnterpriseRBAC)
"analytics:*_all"  # Matches: analytics:view, analytics:export in ALL entities
```

### Example

```python
# Create admin role with wildcard
admin_role = await auth.role_service.create_role(
    name="admin",
    display_name="Administrator",
    permissions=["*:*"]  # All permissions
)

# Check any permission
has_perm = await auth.permission_service.check_permission(
    user_id=str(admin.id),
    permission="any:action"
)  # True (matches *:*)

# Create department admin with resource wildcard
dept_admin_role = await auth.role_service.create_role(
    name="department_admin",
    permissions=["user:*", "team:*"]  # All user and team actions
)

has_create = await auth.permission_service.check_permission(
    user_id=str(dept_admin.id),
    permission="user:create"
)  # True (matches user:*)
```

---

## Permission Resolution Flow

### SimpleRBAC Resolution

```
1. Check if user is superuser → Grant all permissions
2. Get all user roles
3. Aggregate permissions from all roles
4. Check exact match
5. Check wildcard match (resource:*, *:*)
```

### EnterpriseRBAC Resolution

```
1. Check Redis cache (if enabled)
2. Check if user is superuser → Grant all permissions
3. Parse permission (resource:action)
4. Get user's entity memberships
5. Check DIRECT permission:
   - User is member of target entity
   - Role has permission (context-aware)
6. Check TREE permission:
   - Get ancestors via closure table (O(1))
   - Check if user has tree permission (_tree) in any ancestor
   - Use context-aware permissions for ancestor entity type
7. Check PLATFORM-WIDE permission:
   - User has permission with _all suffix
   - Can be from ANY entity membership
8. Cache result in Redis (if enabled)
```

### Performance

| Operation | SimpleRBAC | EnterpriseRBAC |
|-----------|------------|----------------|
| Permission check | O(R) roles | O(M + A) memberships + ancestors |
| With Redis cache | O(1) | O(1) |
| Ancestor lookup | N/A | O(1) via closure table |

---

## Error Handling

### Exception Types

```python
from outlabs_auth.core.exceptions import (
    UserNotFoundError,
    PermissionDeniedError,
    InvalidInputError,
)
```

### Error Handling Pattern

```python
from fastapi import HTTPException

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user = Depends(deps.authenticated())
):
    try:
        # Check permission
        await auth.permission_service.require_permission(
            user_id=str(current_user.id),
            permission="user:delete"
        )

        # Permission granted - delete user
        await auth.user_service.delete_user(user_id)
        return {"message": "User deleted"}

    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
```

---

## Complete Examples

### SimpleRBAC Permission Checking

```python
from fastapi import FastAPI, Depends, HTTPException
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.core.exceptions import PermissionDeniedError

app = FastAPI()
auth = SimpleRBAC(database=db, secret_key="...")
deps = AuthDeps(auth)

# ============================================
# Manual Permission Checks
# ============================================

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user = Depends(deps.authenticated())
):
    """Delete user with manual permission check."""
    try:
        # Check permission
        await auth.permission_service.require_permission(
            user_id=str(current_user.id),
            permission="user:delete"
        )

        # Delete user
        deleted = await auth.user_service.delete_user(user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")

        return {"message": "User deleted"}

    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

# ============================================
# Using AuthDeps (Recommended)
# ============================================

@app.delete("/users/{user_id}/v2")
async def delete_user_v2(
    user_id: str,
    current_user = Depends(deps.requires("user:delete"))
):
    """Delete user with AuthDeps dependency."""
    # Permission already checked by dependency
    deleted = await auth.user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}

# ============================================
# Multiple Permission Checks
# ============================================

@app.post("/users/{user_id}/promote")
async def promote_user(
    user_id: str,
    role_id: str,
    current_user = Depends(deps.authenticated())
):
    """Promote user (requires multiple permissions)."""
    try:
        # Require ALL permissions
        await auth.permission_service.require_all_permissions(
            user_id=str(current_user.id),
            permissions=["user:update", "role:assign"]
        )

        # Assign role
        # (Implementation depends on your role assignment method)
        return {"message": "User promoted"}

    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

# ============================================
# Get User Permissions
# ============================================

@app.get("/users/me/permissions")
async def get_my_permissions(
    current_user = Depends(deps.authenticated())
):
    """Get current user's permissions."""
    permissions = await auth.permission_service.get_user_permissions(
        str(current_user.id)
    )
    return {
        "user_id": str(current_user.id),
        "permissions": permissions,
        "count": len(permissions)
    }
```

### EnterpriseRBAC Permission Checking

```python
from fastapi import FastAPI, Depends, HTTPException
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
auth = EnterpriseRBAC(database=db, secret_key="...")
deps = AuthDeps(auth)

# ============================================
# Entity-Scoped Permission Checks
# ============================================

@app.get("/entities/{entity_id}/budget")
async def get_budget(
    entity_id: str,
    current_user = Depends(deps.authenticated())
):
    """Get budget for entity (entity-scoped permission)."""
    # Check permission in entity context
    has_perm, source = await auth.permission_service.check_permission(
        user_id=str(current_user.id),
        permission="budget:view",
        entity_id=entity_id
    )

    if not has_perm:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Get budget
    entity = await auth.entity_service.get_entity(entity_id)
    return {
        "entity_id": entity_id,
        "entity_name": entity.display_name,
        "budget": 50000,
        "access_type": source  # "direct", "tree", "all", or "superuser"
    }

@app.put("/entities/{entity_id}/budget")
async def update_budget(
    entity_id: str,
    amount: float,
    current_user = Depends(deps.authenticated())
):
    """Update budget (requires approval permission)."""
    has_perm, source = await auth.permission_service.check_permission(
        user_id=str(current_user.id),
        permission="budget:approve",
        entity_id=entity_id
    )

    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to approve budgets in this entity"
        )

    # Update budget
    return {
        "entity_id": entity_id,
        "budget": amount,
        "approved_by": current_user.email,
        "access_via": source
    }

# ============================================
# Tree Permission Checks
# ============================================

@app.get("/entities/{entity_id}/tree")
async def get_entity_tree(
    entity_id: str,
    current_user = Depends(deps.authenticated())
):
    """Get entity and all descendants (requires tree permission)."""
    # Check tree permission
    can_manage_tree = await auth.permission_service.check_tree_permission(
        user_id=str(current_user.id),
        permission="org:manage_tree",
        target_entity_id=entity_id
    )

    if not can_manage_tree:
        raise HTTPException(
            status_code=403,
            detail="You don't have tree permission for this entity"
        )

    # Get entity and descendants
    entity = await auth.entity_service.get_entity(entity_id)
    descendants = await auth.entity_service.get_descendants(entity_id)

    return {
        "entity": entity,
        "descendants": descendants,
        "total_descendants": len(descendants)
    }

# ============================================
# Get Permissions in Entity
# ============================================

@app.get("/entities/{entity_id}/my-permissions")
async def get_my_permissions_in_entity(
    entity_id: str,
    current_user = Depends(deps.authenticated())
):
    """Get current user's permissions in specific entity."""
    permissions = await auth.permission_service.get_user_permissions_in_entity(
        user_id=str(current_user.id),
        entity_id=entity_id
    )

    return {
        "entity_id": entity_id,
        "permissions": permissions,
        "count": len(permissions)
    }

# ============================================
# Platform-Wide Permission Check
# ============================================

@app.get("/analytics/global")
async def get_global_analytics(
    current_user = Depends(deps.authenticated())
):
    """Get global analytics (requires platform-wide permission)."""
    # This checks for "analytics:view_all" in ANY entity membership
    has_perm, source = await auth.permission_service.check_permission(
        user_id=str(current_user.id),
        permission="analytics:view"
        # No entity_id - checks for _all suffix in any membership
    )

    if not has_perm or source != "all":
        raise HTTPException(
            status_code=403,
            detail="You don't have platform-wide analytics access"
        )

    return {
        "message": "Global analytics data",
        "access_via": source
    }
```

---

## Summary

**PermissionService** provides complete permission management:

✅ **Permission Checking** - `check_permission()`, `has_permission()`
✅ **Permission Requirements** - `require_permission()`, `require_any_permission()`, `require_all_permissions()`
✅ **User Permissions** - `get_user_permissions()`, `get_user_permissions_in_entity()`
✅ **Tree Permissions** - `check_tree_permission()` with closure table (EnterpriseRBAC)
✅ **Entity Scope** - Permission checking with entity context (EnterpriseRBAC)
✅ **Wildcard Support** - `user:*`, `*:*`, `*_tree`, `*_all`
✅ **Permission CRUD** - `create_permission()`, `list_permissions()`, `delete_permission()`
✅ **Redis Caching** - O(1) permission lookups (optional)
✅ **ABAC Support** - Attribute-based conditions (optional)

**Permission Sources (EnterpriseRBAC):**
- `"direct"` - Direct membership in target entity
- `"tree"` - Inherited from ancestor via tree permission
- `"all"` - Platform-wide permission (`_all` suffix)
- `"superuser"` - User is superuser

---

## Related Documentation

- **40-Authorization-Overview.md** - Authorization system overview
- **41-RBAC-Patterns.md** - RBAC design patterns
- **43-Tree-Permissions.md** - Complete tree permission guide
- **46-ABAC-Policies.md** - Attribute-based access control
- **60-SimpleRBAC-API.md** - SimpleRBAC API reference
- **61-EnterpriseRBAC-API.md** - EnterpriseRBAC API reference
- **71-Role-Service.md** - RoleService API reference

---

**Last Updated:** 2025-01-14
