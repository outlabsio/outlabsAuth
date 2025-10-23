# Permissions System

**Tags**: #authorization #permissions #access-control

Complete guide to OutlabsAuth's permission system.

---

## Overview

OutlabsAuth uses a flexible permission system that works in both SimpleRBAC and EnterpriseRBAC.

**Permission Format**: `resource:action`

**Examples**:
- `user:read` - Can view users
- `post:create` - Can create posts
- `project:delete` - Can delete projects
- `project:read_tree` - Can view project and all children (EnterpriseRBAC)

---

## Permission Format

### Standard Format

```
resource:action
```

**Resource**: What you're protecting
- `user`, `post`, `comment`, `file`, `project`, `team`

**Action**: What can be done
- `read`, `create`, `update`, `delete`, `manage`

### Examples

```python
# User management
"user:read"      # View users
"user:create"    # Create users
"user:update"    # Update users
"user:delete"    # Delete users
"user:manage"    # All user operations

# Content management
"post:read"      # View posts
"post:create"    # Create posts
"post:update"    # Edit posts
"post:delete"    # Delete posts

# File management
"file:read"      # View files
"file:upload"    # Upload files
"file:download"  # Download files
"file:delete"    # Delete files

# Project management
"project:read"   # View project
"project:update" # Edit project
"project:archive" # Archive project
"project:read_tree"   # View project + children (EnterpriseRBAC)
"project:manage_tree" # Manage project + children (EnterpriseRBAC)
```

---

## SimpleRBAC Permissions

### How It Works

```
User → Roles → Permissions
```

**Flow**:
1. User has one or more roles
2. Each role has a list of permissions
3. User's effective permissions = union of all role permissions

### Example

```python
# Create roles with permissions
await auth.role_service.create_role(
    name="admin",
    permissions=["user:*", "post:*", "comment:*"]  # All permissions
)

await auth.role_service.create_role(
    name="editor",
    permissions=["post:read", "post:create", "post:update", "comment:read"]
)

await auth.role_service.create_role(
    name="viewer",
    permissions=["post:read", "comment:read"]
)

# Assign role to user
await auth.role_service.assign_role_to_user(user.id, "editor")

# User now has: post:read, post:create, post:update, comment:read
```

### Checking Permissions

```python
# In route
@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    ctx = Depends(auth.deps.require_permission("post:delete"))
):
    # User has "post:delete" permission
    await delete_post_from_db(post_id)
    return {"status": "deleted"}

# Programmatically
has_permission = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="post:delete"
)
```

---

## EnterpriseRBAC Permissions

### How It Works

```
Entity Hierarchy
  ↓
Memberships (User → Entity → Role)
  ↓
Permissions (Context-aware + Tree)
```

**Flow**:
1. User is member of entities with roles
2. Each role has permissions (context-aware)
3. Tree permissions grant access to entire subtrees
4. User's effective permissions = union across all memberships + tree permissions

### Example

```python
# Create entity hierarchy
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_type="company",
    is_structural=True
)

engineering = await auth.entity_service.create_entity(
    name="Engineering",
    entity_type="department",
    parent_id=company.id,
    is_structural=True
)

backend_team = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_type="team",
    parent_id=engineering.id,
    is_structural=False
)

# Create context-aware role
await auth.role_service.create_role(
    name="manager",
    permissions=["member:invite"],  # Base permissions
    context_permissions={
        "department": ["report:read_tree", "budget:manage"],
        "team": ["task:assign", "pr:approve"]
    }
)

# Add user to team as manager
await auth.entity_service.add_member(
    entity_id=backend_team.id,
    user_id=user.id,
    role_name="manager"
)

# User has in backend_team context:
# - member:invite (base)
# - task:assign, pr:approve (team context)
```

### Checking Permissions in Entity Context

```python
# Check permission in specific entity
@app.post("/teams/{team_id}/assign-task")
async def assign_task(
    team_id: str,
    task_data: dict,
    ctx = Depends(auth.deps.require_permission(
        "task:assign",
        entity_id_param="team_id"  # Check in this team's context
    ))
):
    # User has "task:assign" in this team
    await assign_task_to_member(team_id, task_data)
    return {"status": "assigned"}

# Programmatically
has_permission = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="task:assign",
    entity_id=team_id  # Entity context
)
```

---

## Wildcard Permissions

Use `*` for wildcard matching.

### Resource Wildcard

```python
# All actions on user resource
"user:*" → ["user:read", "user:create", "user:update", "user:delete"]

# All actions on all resources
"*:*" → All permissions

# All resources, read action only
"*:read" → ["user:read", "post:read", "comment:read", ...]
```

### Examples

```python
# Superuser role
await auth.role_service.create_role(
    name="superuser",
    permissions=["*:*"]  # Everything!
)

# Read-only role
await auth.role_service.create_role(
    name="readonly",
    permissions=["*:read"]  # Read anything, modify nothing
)

# User admin role
await auth.role_service.create_role(
    name="user_admin",
    permissions=["user:*"]  # All user operations
)
```

### Wildcard Matching Logic

```python
def matches_permission(user_permission: str, required_permission: str) -> bool:
    """Check if user_permission matches required_permission"""
    user_resource, user_action = user_permission.split(":")
    req_resource, req_action = required_permission.split(":")

    # Check resource match
    resource_match = (
        user_resource == req_resource or
        user_resource == "*"
    )

    # Check action match
    action_match = (
        user_action == req_action or
        user_action == "*"
    )

    return resource_match and action_match

# Examples
matches_permission("user:*", "user:read")    # True
matches_permission("*:read", "post:read")    # True
matches_permission("*:*", "anything:action") # True
matches_permission("user:read", "post:read") # False
```

---

## Tree Permissions (EnterpriseRBAC)

**Tree permissions** grant access to entire subtrees in entity hierarchy.

### Format

Add `_tree` suffix to action:

```python
"project:read_tree"   # Read project + all descendants
"file:read_tree"      # Read folder + all subfolders
"report:manage_tree"  # Manage report + all sub-reports
```

### Example

```
Company
├── Engineering
│   ├── Backend Team
│   │   └── Project Alpha
│   └── Frontend Team
│       └── Project Beta
```

```python
# Grant tree permission at Engineering level
await auth.permission_service.grant_permission(
    user_id=manager.id,
    entity_id=engineering.id,
    permission="project:read_tree"
)

# Manager can now read:
# - Project Alpha (in Backend Team)
# - Project Beta (in Frontend Team)
# - Any future projects added to Engineering
```

### Checking Tree Permissions

```python
# Check tree permission
has_tree_access = await auth.permission_service.check_tree_permission(
    user_id=manager.id,
    entity_id=project_alpha.id,
    permission="project:read_tree"
)
# Returns True (manager has tree permission at ancestor)
```

**See**: [[44-Tree-Permissions|Tree Permissions Guide]]

---

## Permission Checking Methods

### 1. Route Dependencies (Recommended)

```python
# Single permission
@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    ctx = Depends(auth.deps.require_permission("post:delete"))
):
    pass

# Multiple permissions (requires ALL)
@app.post("/admin/backup")
async def backup(
    ctx = Depends(auth.deps.require_permissions([
        "admin:backup",
        "system:write"
    ]))
):
    pass

# Permission with entity context (EnterpriseRBAC)
@app.patch("/projects/{project_id}")
async def update_project(
    project_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:update",
        entity_id_param="project_id"
    ))
):
    pass
```

### 2. Programmatic Checking

```python
# Check single permission
has_perm = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="post:delete"
)

if not has_perm:
    raise HTTPException(403, "Permission denied")

# Check multiple permissions (requires ALL)
has_all = await auth.permission_service.check_permissions(
    user_id=user.id,
    permissions=["post:read", "post:update"]
)

# Check any permission (requires ANY)
has_any = await auth.permission_service.check_any_permission(
    user_id=user.id,
    permissions=["post:update", "post:delete"]
)

# Check with entity context (EnterpriseRBAC)
has_perm_in_context = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="task:assign",
    entity_id=team_id
)
```

### 3. Superuser Bypass

```python
# Superusers bypass ALL permission checks
user.is_superuser = True
await user.save()

# Now user can do anything, regardless of roles/permissions
```

---

## Permission Resolution

### SimpleRBAC Resolution

```
1. Get user's roles
2. For each role, get permissions
3. Combine all permissions (union)
4. Check if required permission is in the set
5. Check wildcard matches
6. Return True/False
```

**Example**:
```python
# User has roles: ["editor", "moderator"]

# editor role permissions:
["post:read", "post:create", "post:update"]

# moderator role permissions:
["comment:read", "comment:delete", "user:ban"]

# User's effective permissions:
[
    "post:read",
    "post:create",
    "post:update",
    "comment:read",
    "comment:delete",
    "user:ban"
]

# Check: user has "post:delete"?
# → False (not in list)

# Check: user has "comment:delete"?
# → True (in list)
```

### EnterpriseRBAC Resolution

```
1. Get user's entity memberships
2. For each membership:
   a. Get role permissions (base + context-specific)
   b. Check if entity matches target entity
   c. Check tree permissions in ancestor entities
3. Combine all permissions (union)
4. Check if required permission is in the set
5. Check wildcard matches
6. Return True/False
```

**Example**:
```python
# User memberships:
# - Backend Team: "developer" role
# - Project Alpha: "lead" role

# developer role permissions (in team context):
["code:read", "code:write", "pr:create"]

# lead role permissions (in project context):
["project:update", "task:assign", "member:invite"]

# Checking "task:assign" in Project Alpha:
# → True (user is "lead" in Project Alpha)

# Checking "task:assign" in Backend Team:
# → False ("lead" permissions only apply in project context)

# Checking "code:write" in Backend Team:
# → True (user is "developer" in Backend Team)
```

---

## Permission Caching

### Redis Caching

**Enable for 10x-100x performance**:

```python
auth = SimpleRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)
```

**What's Cached**:
- User roles
- Role permissions
- Permission check results
- Entity memberships (EnterpriseRBAC)
- Entity hierarchies (EnterpriseRBAC)

**Cache Keys**:
```python
# SimpleRBAC
f"user_roles:{user_id}"
f"role_permissions:{role_name}"
f"permission_check:{user_id}:{permission}"

# EnterpriseRBAC
f"user_memberships:{user_id}"
f"entity_ancestors:{entity_id}"
f"permission_check:{user_id}:{permission}:{entity_id}"
```

**Cache TTL**:
- User roles: 10 minutes
- Role permissions: 10 minutes
- Permission checks: 5 minutes
- Entity data: 15 minutes

**Cache Invalidation**:
```python
# Automatic invalidation via Redis Pub/Sub (DD-037)
# When permission changes:
await redis.publish("permission_changed", json.dumps({
    "user_id": user.id,
    "role_name": role_name
}))

# All instances invalidate their caches
# Propagation time: <100ms
```

---

## Custom Permissions

### Define Custom Resources

```python
# E-commerce permissions
"product:read"
"product:create"
"product:update"
"product:delete"
"order:read"
"order:create"
"order:fulfill"
"order:refund"
"inventory:read"
"inventory:update"

# Healthcare permissions
"patient:read"
"patient:create"
"patient:update"
"medical_record:read"
"medical_record:create"
"prescription:read"
"prescription:write"

# Financial permissions
"account:read"
"transaction:create"
"transfer:approve"
"report:generate"
```

### Define Custom Actions

```python
# Custom actions for your domain
"document:approve"
"project:archive"
"user:ban"
"content:publish"
"invoice:send"
"campaign:launch"
```

---

## Permission Patterns

### Pattern 1: CRUD Permissions

```python
await auth.role_service.create_role(
    name="content_manager",
    permissions=[
        "post:create",
        "post:read",
        "post:update",
        "post:delete"
    ]
)
```

### Pattern 2: Read-Only Access

```python
await auth.role_service.create_role(
    name="readonly",
    permissions=["*:read"]  # Can read anything, modify nothing
)
```

### Pattern 3: Resource Admin

```python
await auth.role_service.create_role(
    name="user_admin",
    permissions=["user:*"]  # All user operations
)
```

### Pattern 4: Tiered Permissions

```python
# Free tier
await auth.role_service.create_role(
    name="free_user",
    permissions=[
        "post:read",
        "post:create",  # Limited
        "comment:read"
    ]
)

# Pro tier
await auth.role_service.create_role(
    name="pro_user",
    permissions=[
        "post:read",
        "post:create",  # Unlimited
        "post:update",
        "post:delete",
        "comment:read",
        "comment:create",
        "analytics:read"
    ]
)
```

### Pattern 5: Owner-Based Permissions

```python
@app.patch("/posts/{post_id}")
async def update_post(
    post_id: str,
    ctx = Depends(auth.deps.require_permission("post:update"))
):
    user = ctx.metadata.get("user")
    post = await get_post(post_id)

    # Additional check: owner or admin
    is_owner = post.author_id == user.id
    is_admin = "admin" in user.roles

    if not (is_owner or is_admin):
        raise HTTPException(403, "Can only update your own posts")

    # Update post...
```

---

## Testing Permissions

```python
import pytest

@pytest.mark.asyncio
async def test_permission_check():
    # Create user with role
    user = await auth.user_service.create_user(
        email="test@example.com",
        password="password"
    )

    await auth.role_service.create_role(
        name="editor",
        permissions=["post:read", "post:create"]
    )

    await auth.role_service.assign_role_to_user(user.id, "editor")

    # Test has permission
    has_read = await auth.permission_service.check_permission(
        user.id,
        "post:read"
    )
    assert has_read is True

    # Test doesn't have permission
    has_delete = await auth.permission_service.check_permission(
        user.id,
        "post:delete"
    )
    assert has_delete is False

@pytest.mark.asyncio
async def test_wildcard_permissions():
    user = await auth.user_service.create_user(...)

    await auth.role_service.create_role(
        name="admin",
        permissions=["user:*"]
    )

    await auth.role_service.assign_role_to_user(user.id, "admin")

    # Test wildcard matches
    assert await auth.permission_service.check_permission(user.id, "user:read")
    assert await auth.permission_service.check_permission(user.id, "user:create")
    assert await auth.permission_service.check_permission(user.id, "user:delete")
```

---

## Next Steps

- **[[44-Tree-Permissions|Tree Permissions]]** - Hierarchical access control
- **[[45-Context-Aware-Roles|Context-Aware Roles]]** - Role adaptation
- **[[46-ABAC-Policies|ABAC Policies]]** - Attribute-based access
- **[[72-Permission-Service|PermissionService]]** - Service API reference

---

**Previous**: [[42-EnterpriseRBAC|← EnterpriseRBAC]]
**Next**: [[44-Tree-Permissions|Tree Permissions →]]
