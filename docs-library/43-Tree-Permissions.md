# Tree Permissions

**Complete guide to hierarchical permission inheritance in EnterpriseRBAC**

---

## Table of Contents

- [Overview](#overview)
- [How Tree Permissions Work](#how-tree-permissions-work)
- [Tree Permission Syntax](#tree-permission-syntax)
- [Permission Resolution Algorithm](#permission-resolution-algorithm)
- [Common Use Cases](#common-use-cases)
- [Tree vs Direct vs Platform-Wide](#tree-vs-direct-vs-platform-wide)
- [Implementation Examples](#implementation-examples)
- [Performance](#performance)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [See Also](#see-also)

---

## Overview

**Tree Permissions** enable **hierarchical permission inheritance** in EnterpriseRBAC, allowing permissions granted at a parent entity to apply to all descendant entities.

### The Problem

Without tree permissions:

```
CEO (member of Organization)
└── Permissions: project:approve

Engineering Department (child of Organization)
├── Backend Team (grandchild)
│   └── Project Alpha (great-grandchild)
└── Frontend Team

❌ CEO can approve projects in Organization
❌ CEO CANNOT approve projects in Backend Team (different entity)
❌ CEO CANNOT approve projects in Project Alpha (different entity)
```

With tree permissions:

```
CEO (member of Organization with "project:approve_tree")

Engineering Department (child)
├── Backend Team (grandchild)
│   └── Project Alpha (great-grandchild)
└── Frontend Team

✅ CEO can approve projects in Organization
✅ CEO can approve projects in Backend Team (inherited)
✅ CEO can approve projects in Project Alpha (inherited)
✅ CEO can approve projects in Frontend Team (inherited)
```

### Architecture

```
┌────────────────────────────────────────────────────────┐
│  Tree Permission Inheritance                            │
├────────────────────────────────────────────────────────┤
│  Organization (CEO has project:approve_tree)            │
│  ├── ✅ Engineering (inherited)                         │
│  │   ├── ✅ Backend (inherited)                         │
│  │   │   └── ✅ Project Alpha (inherited)               │
│  │   └── ✅ Frontend (inherited)                        │
│  └── ✅ Sales (inherited)                               │
│      └── ✅ Sales Project (inherited)                   │
└────────────────────────────────────────────────────────┘
```

---

## How Tree Permissions Work

### Core Concept

A **tree permission** (suffix `_tree`) grants the permission in:
1. The entity where the user is a member
2. **ALL descendant entities** (children, grandchildren, etc.)

### Example Scenario

```python
from outlabs_auth.models.entity import EntityClass

# Create hierarchy
org = create_entity("ACME Corp", type="organization")
engineering = create_entity("Engineering", type="department", parent=org)
backend = create_entity("Backend Team", type="team", parent=engineering)
project = create_entity("Project Alpha", type="project", parent=backend)

# Create role with tree permission
manager_role = await auth.role_service.create_role(
    name="engineering_manager",
    permissions=[
        "project:read",
        "project:approve_tree",  # Tree permission
        "budget:view_tree"       # Tree permission
    ]
)

# Assign manager to Engineering department
await auth.membership_service.add_member(
    entity_id=str(engineering.id),
    user_id=str(manager.id),
    role_ids=[str(manager_role.id)]
)

# Check permissions in Backend Team (descendant of Engineering)
has_perm, source = await auth.permission_service.check_permission(
    str(manager.id),
    "project:approve",
    entity_id=str(backend.id)
)
# has_perm = True, source = "tree"

# Check permissions in Project Alpha (nested descendant)
has_perm, source = await auth.permission_service.check_permission(
    str(manager.id),
    "project:approve",
    entity_id=str(project.id)
)
# has_perm = True, source = "tree"
```

### Key Points

1. **User must be a member** of an ancestor entity
2. **Permission must have `_tree` suffix** in the ancestor
3. **Checked permission DOES NOT need `_tree`** suffix
4. **Uses closure table** for O(1) performance

---

## Tree Permission Syntax

### Format

```
resource:action_tree
```

**Components:**
- `resource`: The thing being acted upon
- `action`: The operation
- `_tree`: Suffix indicating hierarchical scope

### Standard Tree Permissions

```python
# Project permissions
"project:read_tree"       # Read projects in hierarchy
"project:create_tree"     # Create projects in hierarchy
"project:update_tree"     # Update projects in hierarchy
"project:delete_tree"     # Delete projects in hierarchy
"project:approve_tree"    # Approve projects in hierarchy

# Budget permissions
"budget:view_tree"        # View budgets in hierarchy
"budget:approve_tree"     # Approve budgets in hierarchy

# Member permissions
"member:view_tree"        # View members in hierarchy
"member:invite_tree"      # Invite members to any descendant

# Code permissions
"code:review_tree"        # Review code in hierarchy
"code:merge_tree"         # Merge code in hierarchy

# Audit permissions
"audit:view_tree"         # View audit logs in hierarchy
```

### Wildcard Tree Permissions

```python
# Resource wildcard + tree
"project:*_tree"          # All project actions in hierarchy
"budget:*_tree"           # All budget actions in hierarchy

# Full wildcard (NOT recommended except for top-level admins)
"*:*_tree"                # All actions on all resources in hierarchy
```

---

## Permission Resolution Algorithm

When checking a permission with an entity context:

```
┌─────────────────────────────────────────────────────────┐
│  check_permission(user_id, "project:approve", entity_id) │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  1. Superuser Check  │
          │  user.is_superuser?  │
          └──────────┬───────────┘
                     │ Yes → GRANT (source: "superuser")
                     │
                     │ No
                     ▼
          ┌──────────────────────────────┐
          │  2. Direct Permission        │
          │  User member of TARGET entity │
          │  with "project:approve"?     │
          └──────────┬───────────────────┘
                     │ Yes → GRANT (source: "direct")
                     │
                     │ No
                     ▼
          ┌──────────────────────────────┐
          │  3. Tree Permission          │
          │  User member of ANCESTOR     │
          │  with "project:approve_tree"?│
          └──────────┬───────────────────┘
                     │ Yes → GRANT (source: "tree")
                     │
                     │ No
                     ▼
          ┌──────────────────────────────┐
          │  4. Platform-Wide Permission │
          │  User has "project:approve_all"│
          │  from ANY membership?        │
          └──────────┬───────────────────┘
                     │ Yes → GRANT (source: "all")
                     │
                     │ No
                     ▼
                  DENY
```

### How Tree Permission Check Works

```python
# 1. Get all ancestors of target entity using closure table
ancestors = await EntityClosureModel.find(
    descendant_id == target_entity_id,
    depth > 0  # Exclude self
).to_list()

# 2. For each ancestor, check if user is member
for ancestor in ancestors:
    membership = await EntityMembershipModel.find_one(
        user_id == user_id,
        entity_id == ancestor.id
    )

    if membership:
        # 3. Check if any role has tree permission
        for role in membership.roles:
            tree_permission = f"{resource}:{action}_tree"

            if tree_permission in role.permissions:
                return True, "tree"

return False, "none"
```

**Performance:** O(1) thanks to closure table + Redis caching

---

## Common Use Cases

### Use Case 1: Department Manager

**Scenario:** Manager can approve projects in their department and all sub-teams.

```python
# Hierarchy
company = create_entity("Company", type="organization")
engineering = create_entity("Engineering", type="department", parent=company)
backend = create_entity("Backend Team", type="team", parent=engineering)
frontend = create_entity("Frontend Team", type="team", parent=engineering)

# Manager role with tree permission
manager_role = create_role(
    name="dept_manager",
    permissions=[
        "project:approve_tree",  # Can approve in department + teams
        "budget:view_tree",      # Can view budgets in hierarchy
        "member:invite_tree"     # Can invite to any team
    ]
)

# Assign manager to Engineering
add_member(engineering, manager_user, [manager_role])

# Manager can now:
# ✅ Approve projects in Engineering department
# ✅ Approve projects in Backend Team
# ✅ Approve projects in Frontend Team
# ❌ CANNOT approve projects in Sales (different department)
```

### Use Case 2: Regional Administrator

**Scenario:** Regional admin manages all offices in their region.

```python
# Hierarchy
global_org = create_entity("Global Corp", type="organization")
na_region = create_entity("North America", type="region", parent=global_org)
usa = create_entity("USA", type="country", parent=na_region)
sf_office = create_entity("San Francisco", type="office", parent=usa)
ny_office = create_entity("New York", type="office", parent=usa)

# Regional admin role
regional_admin = create_role(
    name="regional_admin",
    permissions=[
        "office:manage_tree",    # Manage all offices in region
        "employee:view_tree",    # View all employees
        "report:generate_tree"   # Generate reports for region
    ]
)

# Assign to North America region
add_member(na_region, admin_user, [regional_admin])

# Admin can:
# ✅ Manage San Francisco office
# ✅ Manage New York office
# ✅ View all employees in North America
# ❌ CANNOT manage Europe offices
```

### Use Case 3: Security Audit

**Scenario:** Security team can audit all entities below Security department.

```python
# Hierarchy
company = create_entity("Company", type="organization")
security = create_entity("Security", type="department", parent=company)

# Security auditor role
auditor_role = create_role(
    name="security_auditor",
    permissions=[
        "audit:view_tree",       # View audit logs everywhere
        "access:review_tree",    # Review access everywhere
        "compliance:check_tree"  # Check compliance everywhere
    ]
)

# Assign to Security department
add_member(security, auditor_user, [auditor_role])

# Auditor can:
# ✅ View audit logs in ALL departments
# ✅ Review access in ALL teams
# ✅ Check compliance across ENTIRE company
```

### Use Case 4: Project Portfolio Manager

**Scenario:** Portfolio manager oversees all projects in their portfolio.

```python
# Hierarchy
company = create_entity("Company", type="organization")
portfolio = create_entity("Digital Portfolio", type="portfolio", parent=company)
proj_a = create_entity("Project A", type="project", parent=portfolio)
proj_b = create_entity("Project B", type="project", parent=portfolio)

# Portfolio manager role
pm_role = create_role(
    name="portfolio_manager",
    permissions=[
        "project:view_tree",     # View all projects
        "project:report_tree",   # Generate reports
        "milestone:track_tree",  # Track milestones
        "risk:assess_tree"       # Assess risks
    ]
)

# Assign to portfolio
add_member(portfolio, pm_user, [pm_role])

# PM can:
# ✅ View Project A and Project B
# ✅ Generate reports for all projects
# ✅ Track milestones across portfolio
```

---

## Tree vs Direct vs Platform-Wide

### Comparison Matrix

| Aspect | Direct | Tree | Platform-Wide |
|--------|--------|------|---------------|
| **Suffix** | None | `_tree` | `_all` |
| **Scope** | Single entity | Entity + descendants | ALL entities |
| **Membership** | Must be member of target | Member of ancestor | Member of ANY entity |
| **Use Case** | Team-level access | Department-level management | Global admin |
| **Example** | `project:approve` | `project:approve_tree` | `project:approve_all` |

### Example Comparison

```python
# Hierarchy
company
├── Engineering
│   ├── Backend
│   └── Frontend
└── Sales

# User A: Member of Backend with "code:write"
check_permission(user_a, "code:write", backend)
# ✅ DIRECT - member of backend

check_permission(user_a, "code:write", frontend)
# ❌ DENIED - not member of frontend

# User B: Member of Engineering with "code:review_tree"
check_permission(user_b, "code:review", backend)
# ✅ TREE - inherited from engineering

check_permission(user_b, "code:review", frontend)
# ✅ TREE - inherited from engineering

check_permission(user_b, "code:review", sales)
# ❌ DENIED - sales not under engineering

# User C: Member of Company with "user:manage_all"
check_permission(user_c, "user:manage", backend)
# ✅ PLATFORM-WIDE - works everywhere

check_permission(user_c, "user:manage", sales)
# ✅ PLATFORM-WIDE - works everywhere

check_permission(user_c, "user:manage", any_entity)
# ✅ PLATFORM-WIDE - works in ANY entity
```

### When to Use Each

**Direct Permission** (`resource:action`):
- ✅ Team member access
- ✅ Project contributor permissions
- ✅ Department-specific access
- ❌ Multi-department access

**Tree Permission** (`resource:action_tree`):
- ✅ Manager of department
- ✅ Director overseeing multiple teams
- ✅ Regional administrator
- ❌ Global admin

**Platform-Wide** (`resource:action_all`):
- ✅ Platform administrator
- ✅ Security team (audit everywhere)
- ✅ Support team (help any customer)
- ❌ Department-specific roles

---

## Implementation Examples

### Example 1: Department Manager

```python
# Create role
dept_manager = await auth.role_service.create_role(
    name="department_manager",
    display_name="Department Manager",
    permissions=[
        # Direct permissions (in department)
        "department:update",
        "budget:manage",

        # Tree permissions (in department + teams)
        "project:approve_tree",
        "code:review_tree",
        "member:invite_tree",
        "timesheet:approve_tree"
    ]
)

# Assign to Engineering department
await auth.membership_service.add_member(
    entity_id=str(engineering.id),
    user_id=str(manager.id),
    role_ids=[str(dept_manager.id)]
)
```

### Example 2: Check Tree Permission in Route

```python
from fastapi import Depends, HTTPException

@app.post("/entities/{entity_id}/projects/approve")
async def approve_project(
    entity_id: str,
    project_id: str,
    user = Depends(deps.authenticated())
):
    """
    Approve project.

    Requires project:approve permission in entity.
    Can be granted via:
    - Direct: Member of entity with project:approve
    - Tree: Member of ancestor with project:approve_tree
    """
    # Check permission (tree permission checked automatically)
    has_perm, source = await auth.permission_service.check_permission(
        str(user.id),
        "project:approve",
        entity_id
    )

    if not has_perm:
        raise HTTPException(
            403,
            f"Permission denied: project:approve in entity {entity_id}"
        )

    # Approve project
    await approve_project_logic(project_id)

    return {
        "message": "Project approved",
        "permission_source": source  # "direct", "tree", "all", or "superuser"
    }
```

### Example 3: Combine Direct and Tree

```python
# Engineering manager role
eng_manager = create_role(
    name="engineering_manager",
    permissions=[
        # Direct permissions (engineering dept only)
        "department:update",
        "budget:manage",
        "hiring:approve",

        # Tree permissions (all engineering teams)
        "project:approve_tree",
        "code:review_tree",
        "deployment:approve_tree",

        # Platform-wide (entire company)
        "audit:view_all"  # Can audit anywhere
    ]
)

# User is member of Engineering
add_member(engineering, manager, [eng_manager])

# Permission checks:
check_permission(manager, "department:update", engineering)
# ✅ DIRECT

check_permission(manager, "project:approve", backend_team)
# ✅ TREE (backend is child of engineering)

check_permission(manager, "audit:view", sales_dept)
# ✅ PLATFORM-WIDE (audit:view_all)

check_permission(manager, "department:update", sales_dept)
# ❌ DENIED (not member of sales, no tree permission)
```

### Example 4: Wildcard Tree Permissions

```python
# CTO role - all engineering permissions in hierarchy
cto_role = create_role(
    name="cto",
    permissions=[
        "engineering:*_tree",  # All engineering actions in hierarchy
        "budget:*_tree",       # All budget actions in hierarchy
        "hiring:*_tree"        # All hiring actions in hierarchy
    ]
)

# Assign to Engineering
add_member(engineering, cto, [cto_role])

# CTO can do ANY engineering action in ANY team
check_permission(cto, "engineering:approve", backend)  # ✅
check_permission(cto, "engineering:plan", frontend)    # ✅
check_permission(cto, "engineering:review", any_team)  # ✅
```

---

## Performance

### Closure Table Optimization

Tree permissions use **closure table** (DD-036) for O(1) ancestor lookups:

```python
# Get ancestors - O(1) single query
ancestors = await EntityClosureModel.find(
    descendant_id == target_entity_id,
    depth > 0
).to_list()

# vs naive recursive approach - O(n) queries
parent = await get_parent(entity)
while parent:
    ancestors.append(parent)
    parent = await get_parent(parent)  # Another query!
```

**Performance:** 20x faster for deep hierarchies

### Redis Caching

Permission checks are cached in Redis:

```python
# First check - queries database + closure table
has_perm, source = check_permission(user_id, "project:approve", entity_id)

# Second check - from Redis (instant)
has_perm, source = check_permission(user_id, "project:approve", entity_id)

# Cache key format:
# outlabs:auth:perm:{user_id}:{permission}:{entity_id}
```

### Cache Invalidation

```python
# After role changes
await auth.permission_service.invalidate_user_permissions(user_id)

# After entity hierarchy changes
await auth.entity_service.invalidate_entity_tree_cache(entity_id)
```

---

## Best Practices

### 1. Use Tree Permissions for Managers

```python
# ✅ Good: Tree permission for manager
dept_manager = {
    "permissions": [
        "project:approve_tree",
        "member:manage_tree"
    ]
}

# ❌ Bad: Separate memberships in every team
# Don't assign manager to every single team individually
```

### 2. Combine with Direct Permissions

```python
# ✅ Good: Mix direct and tree
manager_role = {
    "permissions": [
        "department:update",      # Direct (dept only)
        "budget:manage",          # Direct (dept only)
        "project:approve_tree",   # Tree (dept + teams)
        "code:review_tree"        # Tree (dept + teams)
    ]
}
```

### 3. Document Tree Permission Scope

```python
await auth.role_service.create_role(
    name="regional_manager",
    description="Manages all offices in region. Tree permissions apply to all child entities.",
    permissions=[
        "office:manage_tree",     # Applies to all offices in region
        "employee:view_tree",     # Applies to all employees
        "report:generate_tree"    # Applies to all reports
    ]
)
```

### 4. Test Tree Permission Inheritance

```python
async def test_tree_permission_inheritance():
    """Test that tree permissions inherit correctly."""
    # Create hierarchy
    org = await create_entity("Org")
    dept = await create_entity("Dept", parent=org)
    team = await create_entity("Team", parent=dept)

    # Create role with tree permission
    role = await create_role(
        permissions=["project:approve_tree"]
    )

    # Assign to dept
    await add_member(dept, user, [role])

    # Check in team (should inherit)
    has_perm, source = await check_permission(
        user.id,
        "project:approve",
        team.id
    )

    assert has_perm is True
    assert source == "tree"
```

### 5. Avoid Over-Use of Tree Permissions

```python
# ❌ Bad: Too many tree permissions
junior_dev = {
    "permissions": [
        "code:write_tree",     # Too broad for junior
        "deploy:prod_tree",    # Too dangerous
        "delete:*_tree"        # Way too broad
    ]
}

# ✅ Good: Minimal tree permissions
junior_dev = {
    "permissions": [
        "code:write",          # Direct only
        "pull_request:create"  # Direct only
    ]
}

# ✅ Good: Tree for senior/manager only
tech_lead = {
    "permissions": [
        "code:write",
        "code:review_tree",    # Can review in team
        "deploy:staging_tree"  # Can deploy to staging
    ]
}
```

---

## Troubleshooting

### Permission Not Inherited

**Problem:** Tree permission not working.

```python
# Check these:

# 1. Is user a member of ancestor?
membership = await auth.membership_service.get_member(ancestor_id, user_id)
assert membership is not None

# 2. Does role have _tree suffix?
role = await auth.role_service.get_role(role_id)
assert "project:approve_tree" in role.permissions

# 3. Is checked permission correct? (no _tree suffix when checking)
has_perm, source = await check_permission(
    user_id,
    "project:approve",  # ✅ Correct - no _tree
    entity_id
)

# ❌ Wrong - don't add _tree when checking
has_perm = await check_permission(user_id, "project:approve_tree", entity_id)

# 4. Is entity actually a descendant?
path = await auth.entity_service.get_entity_path(target_entity_id)
assert any(e.id == ancestor_id for e in path)
```

### Performance Issues

**Problem:** Permission checks are slow.

```python
# Solutions:

# 1. Enable Redis caching
auth = EnterpriseRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# 2. Invalidate cache appropriately
# Don't invalidate too often, don't keep stale too long
await auth.permission_service.invalidate_user_permissions(user_id)

# 3. Check closure table indexes
# Ensure indexes exist on ancestor_id and descendant_id
```

---

## See Also

- **[41. RBAC Patterns](41-RBAC-Patterns.md)** - Role-based access control
- **[42. Entity Hierarchy](42-Entity-Hierarchy.md)** - Organizational structure
- **[40. Authorization Overview](40-Authorization-Overview.md)** - Complete authorization guide
- **[13. Service Layer](13-Service-Layer.md)** - Permission service API
- **[12. Data Models](12-Data-Models.md)** - Closure table schema

---

**Last Updated:** 2025-01-23
**Applies To:** OutlabsAuth v1.0+ (EnterpriseRBAC only)
**Related Design Decisions:** DD-036 (Closure Table), DD-037 (Redis Pub/Sub), DD-005 (Entity Hierarchy)
