# RBAC Patterns

**Complete guide to Role-Based Access Control patterns in OutlabsAuth**

---

## Table of Contents

- [Overview](#overview)
- [SimpleRBAC (Flat RBAC)](#simplerbac-flat-rbac)
  - [When to Use](#when-to-use-simplerbac)
  - [Basic Setup](#basic-setup)
  - [Role Management](#role-management)
  - [Permission Checking](#permission-checking)
- [EnterpriseRBAC (Hierarchical RBAC)](#enterpriserbac-hierarchical-rbac)
  - [When to Use](#when-to-use-enterpriserbac)
  - [Entity Hierarchy](#entity-hierarchy)
  - [Entity Memberships](#entity-memberships)
  - [Permission Scopes](#permission-scopes)
- [Permission Naming Conventions](#permission-naming-conventions)
- [Role Design Patterns](#role-design-patterns)
- [Common RBAC Scenarios](#common-rbac-scenarios)
- [Migration Path](#migration-path)
- [Best Practices](#best-practices)
- [See Also](#see-also)

---

## Overview

OutlabsAuth provides **two RBAC presets** based on your organizational structure:

```
┌─────────────────────────────────────────────────────────┐
│  Do you have departments/teams/hierarchy?                │
├─────────────────────────────────────────────────────────┤
│  NO  → SimpleRBAC      (Flat structure)                  │
│  YES → EnterpriseRBAC  (Hierarchical structure)          │
└─────────────────────────────────────────────────────────┘
```

### Architecture Comparison

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|------------|----------------|
| **Structure** | Flat (users → roles → permissions) | Hierarchical (entities → memberships → roles → permissions) |
| **Use Case** | Simple apps, SaaS tools | Enterprise apps, multi-department orgs |
| **Entities** | None | Organizations, departments, teams, projects |
| **Memberships** | Users have roles globally | Users have roles per entity |
| **Permission Scope** | Global only | Global, entity-scoped, tree, platform-wide |
| **Context-Aware Roles** | No | Optional |
| **Tree Permissions** | No | Yes (`_tree` suffix) |
| **Complexity** | Low | Medium-High |

---

## SimpleRBAC (Flat RBAC)

### When to Use SimpleRBAC

Use **SimpleRBAC** when:
- ✅ No organizational hierarchy (departments, teams)
- ✅ All users in single shared space
- ✅ Permissions are global (not entity-scoped)
- ✅ Simple role assignment (user → role)
- ✅ SaaS tools, small teams, personal projects

**Examples:**
- Blog platform (admin, author, viewer)
- Todo app (admin, user)
- API service (admin, developer, read-only)

### Basic Setup

```python
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps

# Initialize FastAPI
app = FastAPI()

# Initialize MongoDB
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["my_app"]

# Initialize SimpleRBAC
auth = SimpleRBAC(
    database=db,
    secret_key="your-secret-key-here",
    access_token_expire_minutes=15,
    refresh_token_expire_days=30
)

# Initialize database
@app.on_event("startup")
async def startup():
    await auth.initialize()

# Create dependency factory
deps = AuthDeps(auth)
```

### Role Management

#### Create Roles

```python
# Admin role - full access
admin_role = await auth.role_service.create_role(
    name="admin",
    display_name="Administrator",
    description="Full system access",
    permissions=[
        "user:read", "user:create", "user:update", "user:delete",
        "role:read", "role:create", "role:update", "role:delete",
        "permission:read", "permission:create", "permission:delete",
        "*:*"  # Wildcard: all permissions
    ]
)

# Editor role - content management
editor_role = await auth.role_service.create_role(
    name="editor",
    display_name="Content Editor",
    description="Can create and edit content",
    permissions=[
        "post:create",
        "post:read",
        "post:update",
        "post:delete",  # Can delete any post
        "comment:read",
        "comment:moderate"
    ]
)

# Author role - own content only
author_role = await auth.role_service.create_role(
    name="author",
    display_name="Author",
    description="Can create and edit own content",
    permissions=[
        "post:create",
        "post:read",
        "post:update_own",  # Can only update own posts
        "post:delete_own",  # Can only delete own posts
        "comment:read"
    ]
)

# Viewer role - read-only
viewer_role = await auth.role_service.create_role(
    name="viewer",
    display_name="Viewer",
    description="Read-only access",
    permissions=[
        "post:read",
        "comment:read"
    ]
)
```

#### Assign Roles to Users

```python
# Create user
user = await auth.user_service.create_user(
    email="john@example.com",
    password="SecurePassword123!"
)

# Assign role
await auth.role_service.assign_role(
    user_id=str(user.id),
    role_id=str(editor_role.id)
)

# Assign multiple roles
await auth.role_service.assign_roles(
    user_id=str(user.id),
    role_ids=[str(editor_role.id), str(author_role.id)]
)

# Remove role
await auth.role_service.remove_role(
    user_id=str(user.id),
    role_id=str(editor_role.id)
)

# Get user's roles
roles = await auth.role_service.get_user_roles(str(user.id))
# [RoleModel(name="editor"), RoleModel(name="author")]
```

### Permission Checking

#### Basic Permission Checks

```python
# Check single permission
has_perm = await auth.permission_service.check_permission(
    user_id=str(user.id),
    permission="post:delete"
)

if has_perm:
    await delete_post(post_id)
else:
    raise PermissionDeniedError()
```

#### Wildcard Permissions

```python
# Resource wildcard: user:*
# Grants ALL permissions for "user" resource
admin_role = await auth.role_service.create_role(
    name="user_admin",
    permissions=["user:*"]
)

# Check any user action
await auth.permission_service.check_permission(user_id, "user:create")  # ✅ True
await auth.permission_service.check_permission(user_id, "user:delete")  # ✅ True
await auth.permission_service.check_permission(user_id, "user:update")  # ✅ True

# Full wildcard: *:*
# Grants ALL permissions (superuser-like)
super_admin = await auth.role_service.create_role(
    name="super_admin",
    permissions=["*:*"]
)

await auth.permission_service.check_permission(user_id, "anything")  # ✅ True
```

#### FastAPI Route Protection

```python
from fastapi import Depends, HTTPException

# Require authentication
@app.get("/profile")
async def get_profile(user = Depends(deps.authenticated())):
    return {"email": user.email}

# Require specific permission
@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    user = Depends(deps.requires("post:delete"))
):
    await delete_post_logic(post_id)
    return {"message": "Post deleted"}

# Require ANY of multiple permissions
@app.put("/posts/{post_id}")
async def update_post(
    post_id: str,
    user = Depends(deps.requires_any("post:update", "post:update_own"))
):
    # Additional logic for "own" permissions
    if "post:update_own" in await get_user_permissions(user.id):
        post = await get_post(post_id)
        if post.author_id != user.id:
            raise HTTPException(403, "Can only update own posts")

    await update_post_logic(post_id)
    return {"message": "Post updated"}

# Require ALL of multiple permissions
@app.post("/admin/roles")
async def create_role(
    data: RoleCreate,
    user = Depends(deps.requires("role:create", "permission:grant"))
):
    # User must have BOTH permissions
    return await auth.role_service.create_role(**data.dict())
```

---

## EnterpriseRBAC (Hierarchical RBAC)

### When to Use EnterpriseRBAC

Use **EnterpriseRBAC** when:
- ✅ You have organizational hierarchy (departments, teams, projects)
- ✅ Need entity-scoped permissions (different access per department)
- ✅ Need tree permissions (permission inheritance down hierarchy)
- ✅ Users have different roles in different entities
- ✅ Enterprise apps, multi-tenant systems

**Examples:**
- Company with departments and teams
- Multi-project management system
- SaaS platform with organizations and workspaces
- Healthcare system with hospitals, departments, units

### Basic Setup

```python
from outlabs_auth import EnterpriseRBAC

# Initialize EnterpriseRBAC
auth = EnterpriseRBAC(
    database=db,
    secret_key="your-secret-key-here",
    enable_context_aware_roles=True,
    enable_abac=False,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Initialize database
@app.on_event("startup")
async def startup():
    await auth.initialize()

deps = AuthDeps(auth)
```

### Entity Hierarchy

#### Create Entity Structure

```python
from outlabs_auth.models.entity import EntityClass

# Root: Organization
org = await auth.entity_service.create_entity(
    name="acme_corp",
    display_name="ACME Corporation",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="organization"
)

# Level 1: Departments
engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(org.id)
)

sales = await auth.entity_service.create_entity(
    name="sales",
    display_name="Sales Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(org.id)
)

# Level 2: Teams
backend_team = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(engineering.id)
)

frontend_team = await auth.entity_service.create_entity(
    name="frontend_team",
    display_name="Frontend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(engineering.id)
)

# Level 3: Projects
project_a = await auth.entity_service.create_entity(
    name="project_a",
    display_name="Project Alpha",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="project",
    parent_id=str(backend_team.id)
)

# Access Group (special permissions)
senior_engineers = await auth.entity_service.create_entity(
    name="senior_engineers",
    display_name="Senior Engineers",
    entity_class=EntityClass.ACCESS_GROUP,
    entity_type="group",
    parent_id=str(engineering.id)
)
```

**Resulting Hierarchy:**
```
ACME Corporation (org)
├── Engineering Department (dept)
│   ├── Backend Team (team)
│   │   └── Project Alpha (project)
│   ├── Frontend Team (team)
│   └── Senior Engineers (access group)
└── Sales Department (dept)
```

### Entity Memberships

#### Add Users to Entities with Roles

```python
# Create roles
developer_role = await auth.role_service.create_role(
    name="developer",
    display_name="Developer",
    permissions=[
        "code:read",
        "code:write",
        "issue:create",
        "issue:update"
    ]
)

team_lead_role = await auth.role_service.create_role(
    name="team_lead",
    display_name="Team Lead",
    permissions=[
        "code:read",
        "code:write",
        "code:approve",
        "issue:create",
        "issue:update",
        "issue:assign",
        "member:read"
    ]
)

# Add user to backend team with developer role
await auth.membership_service.add_member(
    entity_id=str(backend_team.id),
    user_id=str(user.id),
    role_ids=[str(developer_role.id)]
)

# User can have MULTIPLE roles in same entity
await auth.membership_service.add_member(
    entity_id=str(backend_team.id),
    user_id=str(senior_dev.id),
    role_ids=[str(developer_role.id), str(team_lead_role.id)]
)

# User can have DIFFERENT roles in different entities
await auth.membership_service.add_member(
    entity_id=str(backend_team.id),
    user_id=str(alice.id),
    role_ids=[str(team_lead_role.id)]  # Team lead in backend
)

await auth.membership_service.add_member(
    entity_id=str(frontend_team.id),
    user_id=str(alice.id),
    role_ids=[str(developer_role.id)]  # Developer in frontend
)
```

#### Time-Based Memberships

```python
from datetime import datetime, timedelta

# Contractor with 90-day membership
await auth.membership_service.add_member(
    entity_id=str(project_a.id),
    user_id=str(contractor.id),
    role_ids=[str(contractor_role.id)],
    valid_from=datetime.utcnow(),
    valid_until=datetime.utcnow() + timedelta(days=90)
)

# Check if membership is currently valid
membership = await auth.membership_service.get_member(
    entity_id=str(project_a.id),
    user_id=str(contractor.id)
)

if membership.is_currently_valid():
    # Membership is active
    pass
```

### Permission Scopes

EnterpriseRBAC supports **4 permission scopes**:

#### 1. Direct Permission (entity-scoped)

Permission applies **only in the specific entity** where user is a member.

```python
# Role with entity-scoped permission
developer_role = await auth.role_service.create_role(
    name="developer",
    permissions=["code:write"]  # Normal permission
)

# User is member of "backend_team" with developer role
await auth.membership_service.add_member(
    entity_id=str(backend_team.id),
    user_id=str(user.id),
    role_ids=[str(developer_role.id)]
)

# Check permission in backend team
has_perm, source = await auth.permission_service.check_permission(
    str(user.id),
    "code:write",
    entity_id=str(backend_team.id)
)
# has_perm = True, source = "direct"

# Check permission in frontend team (user is NOT a member)
has_perm, source = await auth.permission_service.check_permission(
    str(user.id),
    "code:write",
    entity_id=str(frontend_team.id)
)
# has_perm = False
```

#### 2. Tree Permission (hierarchical)

Permission applies to **entity AND all descendants** (via `_tree` suffix).

```python
# Manager role with tree permission
manager_role = await auth.role_service.create_role(
    name="engineering_manager",
    permissions=[
        "project:read",
        "project:approve_tree",  # _tree suffix
        "budget:view_tree"
    ]
)

# Manager is member of "engineering" department
await auth.membership_service.add_member(
    entity_id=str(engineering.id),
    user_id=str(manager.id),
    role_ids=[str(manager_role.id)]
)

# Check permission in engineering department itself
has_perm, source = await auth.permission_service.check_permission(
    str(manager.id),
    "project:approve",
    entity_id=str(engineering.id)
)
# has_perm = True, source = "tree"

# Check permission in backend_team (descendant of engineering)
has_perm, source = await auth.permission_service.check_permission(
    str(manager.id),
    "project:approve",
    entity_id=str(backend_team.id)
)
# has_perm = True, source = "tree" (inherited from engineering)

# Check permission in project_a (nested descendant)
has_perm, source = await auth.permission_service.check_permission(
    str(manager.id),
    "project:approve",
    entity_id=str(project_a.id)
)
# has_perm = True, source = "tree" (inherited from engineering)
```

#### 3. Platform-Wide Permission (global)

Permission applies **across ALL entities** (via `_all` suffix).

```python
# Admin role with platform-wide permissions
admin_role = await auth.role_service.create_role(
    name="platform_admin",
    permissions=[
        "user:read_all",    # _all suffix
        "user:update_all",
        "audit:view_all"
    ]
)

# Admin is member of ANY entity (even just one)
await auth.membership_service.add_member(
    entity_id=str(org.id),
    user_id=str(admin.id),
    role_ids=[str(admin_role.id)]
)

# Check permission in ANY entity
has_perm, source = await auth.permission_service.check_permission(
    str(admin.id),
    "user:read",
    entity_id=str(random_entity.id)  # ANY entity
)
# has_perm = True, source = "all"
```

#### 4. Superuser (bypass all checks)

Superuser bypasses ALL permission checks.

```python
# Set user as superuser
user = await auth.user_service.get_user(user_id)
user.is_superuser = True
await user.save()

# Check ANY permission
has_perm, source = await auth.permission_service.check_permission(
    str(user.id),
    "anything:anywhere",
    entity_id=any_entity
)
# has_perm = True, source = "superuser"
```

### Permission Resolution Flow

```
┌─────────────────────────────────────────────────────────┐
│  Permission Check: user_id + permission + entity_id      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  1. Is Superuser?    │
          └──────────┬───────────┘
                     │ Yes → Grant (source: "superuser")
                     │
                     │ No
                     ▼
          ┌──────────────────────────────┐
          │  2. Direct Permission        │
          │     (in target entity)       │
          └──────────┬───────────────────┘
                     │ Yes → Grant (source: "direct")
                     │
                     │ No
                     ▼
          ┌──────────────────────────────┐
          │  3. Tree Permission          │
          │     (from ancestors)         │
          └──────────┬───────────────────┘
                     │ Yes → Grant (source: "tree")
                     │
                     │ No
                     ▼
          ┌──────────────────────────────┐
          │  4. Platform-Wide Permission │
          │     (_all suffix)            │
          └──────────┬───────────────────┘
                     │ Yes → Grant (source: "all")
                     │
                     │ No
                     ▼
                  DENY
```

---

## Permission Naming Conventions

### Format

```
resource:action[_modifier]
```

**Components:**
- `resource`: The thing being acted upon (user, post, project)
- `action`: The operation (create, read, update, delete, approve)
- `_modifier`: Optional scope modifier

### Standard Actions

```
resource:create   - Create new resource
resource:read     - Read/view resource
resource:update   - Modify resource
resource:delete   - Remove resource
resource:list     - List resources
resource:approve  - Approve/authorize resource
resource:assign   - Assign to others
```

### Scope Modifiers

```
resource:action          - Normal permission (entity-scoped in EnterpriseRBAC)
resource:action_own      - Own resources only
resource:action_tree     - Permission + descendants (EnterpriseRBAC)
resource:action_all      - Platform-wide (EnterpriseRBAC)
```

### Examples

```python
# Standard permissions
"user:create"           # Create users
"user:read"             # Read user data
"user:update"           # Update any user
"user:delete"           # Delete any user

# Own-only permissions
"post:update_own"       # Update only own posts
"post:delete_own"       # Delete only own posts
"profile:edit_own"      # Edit only own profile

# Tree permissions (EnterpriseRBAC)
"project:approve_tree"  # Approve in entity + descendants
"budget:view_tree"      # View budget in hierarchy
"member:manage_tree"    # Manage members in subtree

# Platform-wide permissions (EnterpriseRBAC)
"user:read_all"         # Read users across all entities
"audit:view_all"        # View audits everywhere
"backup:create_all"     # Create backups globally

# Wildcards
"user:*"                # All user actions
"*:read"                # Read any resource
"*:*"                   # All permissions (superuser)
```

---

## Role Design Patterns

### Pattern 1: Functional Roles

Roles based on job function.

```python
# Developer
developer = {
    "name": "developer",
    "permissions": [
        "code:read",
        "code:write",
        "issue:create",
        "issue:update_own",
        "pull_request:create"
    ]
}

# QA Engineer
qa_engineer = {
    "name": "qa_engineer",
    "permissions": [
        "code:read",
        "issue:create",
        "issue:update",
        "test:create",
        "test:run"
    ]
}

# Product Manager
product_manager = {
    "name": "product_manager",
    "permissions": [
        "feature:create",
        "feature:update",
        "feature:prioritize",
        "roadmap:edit"
    ]
}
```

### Pattern 2: Hierarchical Roles

Roles that build on each other.

```python
# Base: Viewer
viewer = {
    "name": "viewer",
    "permissions": ["*:read"]
}

# Extends Viewer: Editor
editor = {
    "name": "editor",
    "permissions": [
        "*:read",
        "content:create",
        "content:update_own",
        "content:delete_own"
    ]
}

# Extends Editor: Moderator
moderator = {
    "name": "moderator",
    "permissions": [
        "*:read",
        "content:create",
        "content:update",  # Not just own
        "content:delete",  # Not just own
        "comment:moderate"
    ]
}

# Extends Moderator: Admin
admin = {
    "name": "admin",
    "permissions": [
        "*:*"  # All permissions
    ]
}
```

### Pattern 3: Composite Roles

Users with multiple roles for different responsibilities.

```python
# User is both developer AND team lead
await auth.membership_service.add_member(
    entity_id=str(team.id),
    user_id=str(user.id),
    role_ids=[
        str(developer_role.id),
        str(team_lead_role.id)
    ]
)

# Effective permissions = union of all role permissions
effective_permissions = (
    developer_role.permissions +
    team_lead_role.permissions
)
```

### Pattern 4: Temporary/Emergency Roles

Roles granted for limited time.

```python
from datetime import datetime, timedelta

# Grant incident commander role for 24 hours
await auth.membership_service.add_member(
    entity_id=str(ops_team.id),
    user_id=str(on_call_engineer.id),
    role_ids=[str(incident_commander_role.id)],
    valid_from=datetime.utcnow(),
    valid_until=datetime.utcnow() + timedelta(hours=24)
)
```

---

## Common RBAC Scenarios

### Scenario 1: Blog Platform (SimpleRBAC)

```python
# Roles
admin = ["post:*", "user:*", "comment:*", "category:*"]
editor = ["post:create", "post:update", "post:delete", "comment:moderate"]
author = ["post:create", "post:update_own", "post:delete_own", "comment:read"]
subscriber = ["post:read", "comment:create", "comment:update_own"]

# Routes
@app.post("/posts")
async def create_post(user = Depends(deps.requires("post:create"))):
    # Authors and editors can create

@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    user = Depends(deps.requires_any("post:delete", "post:delete_own"))
):
    # Check ownership for "own" permissions
    if "post:delete_own" in await get_permissions(user.id):
        post = await get_post(post_id)
        if post.author_id != user.id:
            raise HTTPException(403)

    await delete_post_logic(post_id)
```

### Scenario 2: Company with Departments (EnterpriseRBAC)

```python
# Structure
company = create_entity("ACME Corp", type="organization")
engineering = create_entity("Engineering", type="department", parent=company)
sales = create_entity("Sales", type="department", parent=company)
backend = create_entity("Backend Team", type="team", parent=engineering)

# Roles
cto = {
    "permissions": [
        "project:approve_tree",    # Approve all engineering projects
        "budget:manage_tree",      # Manage all engineering budgets
        "hire:approve_tree"        # Approve all engineering hires
    ]
}

eng_manager = {
    "permissions": [
        "project:manage",          # Manage projects in own department
        "code:review_tree",        # Review code in subtree
        "member:manage"            # Manage team members
    ]
}

developer = {
    "permissions": [
        "code:write",
        "issue:create",
        "pull_request:create"
    ]
}

# Assignments
await add_member(engineering, cto_user, [cto_role])           # CTO of engineering
await add_member(backend, manager_user, [eng_manager_role])  # Manager of backend
await add_member(backend, dev_user, [developer_role])        # Developer in backend

# Permission checks
# CTO can approve projects in backend (tree permission from engineering)
has_perm, source = check_permission(cto_user, "project:approve", backend)
# has_perm = True, source = "tree"

# Manager can manage backend team members (direct permission)
has_perm, source = check_permission(manager_user, "member:manage", backend)
# has_perm = True, source = "direct"

# Developer can write code in backend (direct permission)
has_perm, source = check_permission(dev_user, "code:write", backend)
# has_perm = True, source = "direct"
```

### Scenario 3: Multi-Tenant SaaS (EnterpriseRBAC)

```python
# Each customer is an organization
customer_a = create_entity("Customer A", type="organization")
customer_b = create_entity("Customer B", type="organization")

workspace_a1 = create_entity("Workspace A1", type="workspace", parent=customer_a)
workspace_a2 = create_entity("Workspace A2", type="workspace", parent=customer_a)

# Roles
org_admin = {
    "permissions": [
        "workspace:create",
        "workspace:delete",
        "member:invite_tree",      # Invite to any workspace
        "billing:manage"
    ]
}

workspace_admin = {
    "permissions": [
        "member:invite",
        "settings:manage",
        "data:export"
    ]
}

workspace_member = {
    "permissions": [
        "data:read",
        "data:create",
        "data:update_own"
    ]
}

# User roles vary by organization
await add_member(customer_a, user, [org_admin_role])         # Admin in Customer A
await add_member(customer_b, user, [workspace_member_role])  # Member in Customer B
```

---

## Migration Path

### From SimpleRBAC to EnterpriseRBAC

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

**Migration steps:**

1. **Change class** (no breaking changes)
   ```python
   auth = EnterpriseRBAC(database=db)
   ```

2. **Create root entity** (organization)
   ```python
   org = await auth.entity_service.create_entity(
       name="my_org",
       display_name="My Organization",
       entity_class=EntityClass.STRUCTURAL,
       entity_type="organization"
   )
   ```

3. **Convert global role assignments to entity memberships**
   ```python
   # Old (SimpleRBAC): Global role
   await auth.role_service.assign_role(user_id, role_id)

   # New (EnterpriseRBAC): Entity membership
   await auth.membership_service.add_member(
       entity_id=str(org.id),
       user_id=user_id,
       role_ids=[role_id]
   )
   ```

4. **Add entity structure** as needed
   ```python
   engineering = await auth.entity_service.create_entity(
       name="engineering",
       display_name="Engineering",
       entity_type="department",
       parent_id=str(org.id)
   )
   ```

---

## Best Practices

### 1. Principle of Least Privilege

Grant minimum permissions needed.

```python
# ❌ Bad: Over-permissioned
junior_dev = {
    "permissions": [
        "code:*",         # Too broad
        "deploy:*",       # Too dangerous
        "*:delete"        # Way too broad
    ]
}

# ✅ Good: Minimal permissions
junior_dev = {
    "permissions": [
        "code:read",
        "code:write",
        "issue:create",
        "pull_request:create"
    ]
}
```

### 2. Use Descriptive Role Names

```python
# ❌ Bad
"role1", "role2", "power_user"

# ✅ Good
"content_editor", "billing_admin", "support_agent"
```

### 3. Document Permission Purpose

```python
await auth.role_service.create_role(
    name="accountant",
    display_name="Accountant",
    description="Can manage invoices and financial reports. Cannot access payroll.",
    permissions=[
        "invoice:create",
        "invoice:approve",  # Up to $10,000
        "report:financial:view",
        "report:financial:export"
    ]
)
```

### 4. Separate System from Custom Permissions

```python
# System permissions (managed by OutlabsAuth)
SYSTEM_PERMISSIONS = [
    "user:create",
    "user:delete",
    "role:assign"
]

# Your domain permissions
DOMAIN_PERMISSIONS = [
    "invoice:approve",
    "shipment:track",
    "inventory:update"
]
```

### 5. Use Permission Wildcards Sparingly

```python
# ❌ Avoid for non-admin roles
regular_user = {"permissions": ["*:*"]}

# ✅ Use for admin roles only
admin = {"permissions": ["*:*"]}

# ✅ Or use resource-specific wildcards
user_admin = {"permissions": ["user:*"]}  # All user operations only
```

### 6. Design for Auditing

```python
# Track permission changes
@app.post("/roles/{role_id}/permissions")
async def update_permissions(
    role_id: str,
    permissions: List[str],
    user = Depends(deps.requires("role:update"))
):
    role = await auth.role_service.get_role(role_id)
    old_permissions = role.permissions

    # Update
    role.permissions = permissions
    await role.save()

    # Audit log
    await audit_log.log(
        action="role.permissions.updated",
        user_id=str(user.id),
        role_id=role_id,
        old_value=old_permissions,
        new_value=permissions
    )
```

### 7. Test Permission Logic

```python
# Test suite for RBAC
async def test_editor_can_create_posts():
    user = await create_user_with_role("editor")
    has_perm = await auth.permission_service.check_permission(
        str(user.id),
        "post:create"
    )
    assert has_perm is True

async def test_viewer_cannot_delete_posts():
    user = await create_user_with_role("viewer")
    has_perm = await auth.permission_service.check_permission(
        str(user.id),
        "post:delete"
    )
    assert has_perm is False
```

---

## See Also

- **[40. Authorization Overview](40-Authorization-Overview.md)** - Complete authorization guide
- **[42. Entity Hierarchy](42-Entity-Hierarchy.md)** - Organizational structure
- **[43. Tree Permissions](43-Tree-Permissions.md)** - Hierarchical permission inheritance
- **[46. ABAC Policies](46-ABAC-Policies.md)** - Attribute-based access control
- **[13. Service Layer](13-Service-Layer.md)** - Permission service APIs
- **[14. FastAPI Integration](14-FastAPI-Integration.md)** - Route protection patterns

---

**Last Updated:** 2025-01-23
**Applies To:** OutlabsAuth v1.0+
**Related Design Decisions:** DD-003 (Two Presets), DD-005 (Entity Hierarchy), DD-032 (Unified Architecture)
