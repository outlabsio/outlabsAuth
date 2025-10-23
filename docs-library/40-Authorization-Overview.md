# 40. Authorization Overview

> **Quick Reference**: Understand how OutlabsAuth controls what authenticated users can do with Role-Based Access Control (RBAC), tree permissions, and optional Attribute-Based Access Control (ABAC).

## Overview

**Authorization** determines **what** an authenticated user can do. After authentication proves **who** you are, authorization answers **what** you're allowed to access.

OutlabsAuth provides three authorization models:
1. **SimpleRBAC** - Flat role-based access control
2. **EnterpriseRBAC** - Hierarchical RBAC with tree permissions
3. **ABAC** (Optional) - Attribute-based access control policies

---

## Authorization vs Authentication

| Aspect | Authentication | Authorization |
|--------|---------------|---------------|
| **Question** | Who are you? | What can you do? |
| **Verifies** | Identity | Permissions |
| **Methods** | Password, JWT, OAuth, API Key | Roles, Permissions, Policies |
| **Result** | User object | Boolean (allow/deny) |
| **Example** | Login with email + password | Can user delete this post? |

**Flow**:
```
1. Authentication: "Who are you?"
   → User logs in with password
   → Receives JWT access token
   → User identified as john@example.com

2. Authorization: "What can you do?"
   → User tries to delete post
   → Check: Does john@example.com have "post:delete"?
   → Result: Allow or Deny
```

---

## Authorization Models

### Model Comparison

| Model | Structure | Use Cases | Complexity | Power |
|-------|-----------|-----------|------------|-------|
| **SimpleRBAC** | Flat | Simple apps, APIs | ⭐ Low | Basic |
| **EnterpriseRBAC** | Hierarchical | Organizations, SaaS | ⭐⭐ Medium | Strong |
| **ABAC** (Optional) | Policy-based | Complex rules | ⭐⭐⭐ High | Maximum |

---

## 1. SimpleRBAC

### Overview

**Flat role-based access control** for applications without organizational hierarchy.

```
Users → Roles → Permissions
```

**Example Structure**:
```
User: john@example.com
  ├─ Role: editor
  │   ├─ Permission: post:create
  │   ├─ Permission: post:update
  │   └─ Permission: post:read
  └─ Role: moderator
      ├─ Permission: comment:delete
      └─ Permission: comment:moderate
```

### When to Use SimpleRBAC

**✅ Use SimpleRBAC when**:
- Flat organizational structure (no departments/teams)
- Simple role-based permissions (admin, editor, viewer)
- Want fastest setup and simplest API
- Building APIs, internal tools, simple web apps
- Don't need hierarchical access control

**❌ Don't use when**:
- Need organizational hierarchy (company → departments → teams)
- Need tree permissions (access entire subtrees)
- Need context-aware roles (different permissions per entity type)
- Building multi-tenant SaaS with complex permissions

### Quick Example

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db)

# Create roles
admin_role = await auth.role_service.create_role(
    name="admin",
    permissions=["user:*", "post:*", "comment:*"]
)

editor_role = await auth.role_service.create_role(
    name="editor",
    permissions=["post:read", "post:create", "post:update"]
)

# Check permission
has_permission = await auth.permission_service.check_permission(
    user_id=user_id,
    permission="post:delete"
)
```

**See**: [[41-SimpleRBAC]] for complete guide.

---

## 2. EnterpriseRBAC

### Overview

**Hierarchical role-based access control** for organizations with structure (companies, departments, teams, projects).

```
Entity Hierarchy → Memberships → Roles → Permissions (+ Tree Permissions)
```

**Example Structure**:
```
Acme Corp (company)
  └─ Engineering (department)
      └─ Backend Team (team)
          └─ Project Alpha (project)

User: jane@acme.com
  ├─ Membership in Engineering Department
  │   └─ Role: manager
  │       ├─ Permission: user:manage_tree (all users in dept)
  │       └─ Permission: budget:approve
  └─ Membership in Backend Team
      └─ Role: lead
          ├─ Permission: code:review
          └─ Permission: deploy:staging
```

### Key Features

#### 1. Entity Hierarchy

Organizational structure with parent-child relationships:

```
Company
  └─ Division
      └─ Department
          └─ Team
              └─ Project
```

#### 2. Tree Permissions

Grant access to entire subtrees with `_tree` suffix:

```python
# Grant "report:read_tree" at Engineering Department
# → User can read ALL reports in:
#   • Backend Team
#   • Frontend Team
#   • All projects under Engineering
```

#### 3. Context-Aware Roles (Optional)

Roles adapt permissions based on entity type:

```python
manager_role = RoleModel(
    name="manager",
    entity_type_permissions={
        "department": ["user:manage_tree", "budget:approve"],
        "team": ["user:read", "task:assign"],
        "project": ["settings:update"]
    }
)
# Same role, different permissions per entity type!
```

#### 4. Multiple Memberships

Users can have different roles in different parts of the hierarchy:

```
john@acme.com:
  • "developer" in Backend Team
  • "lead" in Project Alpha
  • "reviewer" in Project Beta
```

### When to Use EnterpriseRBAC

**✅ Use EnterpriseRBAC when**:
- Hierarchical organization (company → departments → teams)
- Need tree permissions (access entire subtrees)
- Context-aware roles (different permissions per entity type)
- Multi-tenant SaaS applications
- Complex authorization requirements

**❌ Don't use when**:
- Flat organizational structure
- Simple role-based permissions
- Want simplest possible API
- Building simple apps or APIs

### Quick Example

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True  # Optional
)

# Create entity hierarchy
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_type="company",
    classification="STRUCTURAL"
)

engineering = await auth.entity_service.create_entity(
    name="Engineering",
    entity_type="department",
    classification="STRUCTURAL",
    parent_id=company.id
)

# Create membership with roles
await auth.membership_service.create_membership(
    user_id=user_id,
    entity_id=engineering.id,
    role_ids=[manager_role.id]
)

# Check permission with context
has_permission = await auth.permission_service.check_permission(
    user_id=user_id,
    permission="user:manage_tree",  # Tree permission!
    entity_id=engineering.id
)
# Returns True - can manage all users in Engineering + children
```

**See**: [[42-EnterpriseRBAC]] for complete guide.

---

## 3. ABAC (Attribute-Based Access Control)

### Overview

**Policy-based access control** with conditional rules. Optional feature in EnterpriseRBAC.

**Enable with**:
```python
auth = EnterpriseRBAC(
    database=db,
    enable_abac=True  # Opt-in
)
```

### Example Policies

```python
# Role with ABAC conditions
role = RoleModel(
    name="time_restricted_admin",
    permissions=["user:*", "data:*"],
    conditions=[
        Condition(
            attribute="time.hour",
            operator=">=",
            value=9
        ),
        Condition(
            attribute="time.hour",
            operator="<",
            value=17
        ),
        # Only during business hours (9 AM - 5 PM)
    ]
)

# Complex condition groups
role = RoleModel(
    name="regional_manager",
    permissions=["sales:approve"],
    condition_groups=[
        ConditionGroup(
            operator="AND",
            conditions=[
                Condition(attribute="user.department", operator="==", value="sales"),
                Condition(attribute="user.region", operator="==", value="west"),
                # Must be in sales department AND west region
            ]
        )
    ]
)
```

### Use Cases

- **Time-based access**: Only during business hours
- **Location-based access**: Only from specific IP ranges
- **Attribute matching**: Only if user.department == resource.department
- **Dynamic policies**: Permissions based on runtime conditions

**See**: [[46-ABAC-Policies]] for complete guide.

---

## Permission System

### Permission Format

```
resource:action
```

**Examples**:
```python
"user:read"       # View users
"user:create"     # Create users
"user:update"     # Update users
"user:delete"     # Delete users
"user:*"          # All user operations (wildcard)
```

### Tree Permissions (EnterpriseRBAC)

Add `_tree` suffix for hierarchical access:

```python
"user:read_tree"       # Read user + all descendants
"user:manage_tree"     # Manage user + all descendants
"project:read_tree"    # Read project + all child projects
"entity:delete_tree"   # Delete entity + all children
```

### Wildcard Permissions

```python
"user:*"          # All user operations
"*:read"          # Read all resources (not recommended)
"*:*"             # All operations (superuser)
```

**See**: [[43-Permissions-System]] for complete guide.

---

## Permission Checking Flow

### SimpleRBAC Flow

```
1. User makes request
   ↓
2. Get user's roles
   ↓
3. Aggregate permissions from all roles
   ↓
4. Check if required permission is in list
   ↓
5. Allow or Deny
```

**Example**:
```python
User: john@example.com
  Roles: [editor, moderator]
    editor → [post:create, post:update, post:read]
    moderator → [comment:delete, comment:moderate]

  Aggregated permissions:
    [post:create, post:update, post:read, comment:delete, comment:moderate]

Check: Does user have "post:update"?
  → YES ✅ (in aggregated list)

Check: Does user have "post:delete"?
  → NO ❌ (not in aggregated list)
```

### EnterpriseRBAC Flow

```
1. User makes request with entity context
   ↓
2. Get user's memberships in this entity
   ↓
3. Get roles from memberships
   ↓
4. Get permissions from roles (context-aware if enabled)
   ↓
5. Check tree permissions (if _tree permission)
   ↓
6. Evaluate ABAC conditions (if enabled)
   ↓
7. Allow or Deny
```

**Example**:
```python
User: jane@acme.com
  Entity: Engineering Department
  Membership: manager role
    manager (in department) → [user:manage_tree, budget:approve]

Check: Does user have "user:manage_tree" in Engineering?
  → YES ✅

Check tree: Can user manage users in Backend Team?
  → YES ✅ (Backend Team is child of Engineering)

Check tree: Can user manage users in Sales Department?
  → NO ❌ (Sales is not under Engineering)
```

---

## FastAPI Integration

### Basic Permission Check

```python
from fastapi import Depends, HTTPException
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    auth_result = Depends(deps.require_permission("post:delete"))
):
    """
    Only users with post:delete permission can access.
    """
    await delete_post_from_db(post_id)
    return {"message": "Post deleted"}
```

### Multiple Permission Check

```python
@app.post("/posts/{post_id}/publish")
async def publish_post(
    post_id: str,
    auth_result = Depends(deps.require_all_permissions([
        "post:update",
        "post:publish"
    ]))
):
    """
    Requires BOTH post:update AND post:publish.
    """
    await publish_post_to_db(post_id)
    return {"message": "Post published"}
```

### Any Permission Check

```python
@app.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    auth_result = Depends(deps.require_any_permission([
        "post:read",
        "post:*"
    ]))
):
    """
    Requires EITHER post:read OR post:* (wildcard).
    """
    post = await get_post_from_db(post_id)
    return post
```

### Role-Based Check

```python
@app.get("/admin/dashboard")
async def admin_dashboard(
    auth_result = Depends(deps.require_role("admin"))
):
    """
    Only users with 'admin' role can access.
    """
    return {"dashboard": "admin_data"}
```

---

## Decision Tree: Which Model to Use?

```
Do you need organizational hierarchy?
│
├─ NO → SimpleRBAC
│        └─ Flat roles, simple permissions
│
└─ YES → EnterpriseRBAC
         ├─ Core features (always included):
         │   • Entity hierarchy
         │   • Tree permissions
         │   • Multiple memberships
         │
         └─ Optional features (opt-in):
             ├─ Context-aware roles? (enable_context_aware_roles)
             ├─ ABAC policies? (enable_abac)
             └─ Redis caching? (enable_caching)
```

---

## Common Patterns

### Pattern 1: Admin + User Roles (SimpleRBAC)

```python
# Create roles
admin = await auth.role_service.create_role(
    name="admin",
    permissions=["*:*"]  # All permissions
)

user = await auth.role_service.create_role(
    name="user",
    permissions=["post:read", "post:create", "comment:read", "comment:create"]
)

# Assign role to user
user.role_ids = [user_role.id]
await user.save()
```

### Pattern 2: Department Hierarchy (EnterpriseRBAC)

```python
# Create hierarchy
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_type="company",
    classification="STRUCTURAL"
)

engineering = await auth.entity_service.create_entity(
    name="Engineering",
    entity_type="department",
    classification="STRUCTURAL",
    parent_id=company.id
)

backend_team = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_type="team",
    classification="STRUCTURAL",
    parent_id=engineering.id
)

# Create manager role with tree permissions
manager = await auth.role_service.create_role(
    name="manager",
    permissions=["user:manage_tree", "entity:read_tree"]
)

# Assign manager at Engineering level
await auth.membership_service.create_membership(
    user_id=manager_user_id,
    entity_id=engineering.id,
    role_ids=[manager.id]
)

# Manager can now manage users in:
# • Engineering Department
# • Backend Team (child of Engineering)
# • All future teams created under Engineering
```

### Pattern 3: Time-Restricted Admin (ABAC)

```python
# Admin role with time restrictions
admin = RoleModel(
    name="business_hours_admin",
    permissions=["user:*", "data:*"],
    conditions=[
        Condition(attribute="time.hour", operator=">=", value=9),
        Condition(attribute="time.hour", operator="<", value=17),
        Condition(attribute="time.weekday", operator="<", value=5)
        # Monday-Friday, 9 AM - 5 PM
    ]
)
await admin.insert()
```

---

## Performance Considerations

### Caching

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)
```

**What's Cached**:
- User permissions
- Role permissions
- Tree permission results
- Entity hierarchy paths

**Cache Invalidation**:
- Automatic via Redis Pub/Sub (<100ms across instances)
- Manual: `await auth.cache_service.invalidate_user(user_id)`

### Permission Check Performance

| Operation | SimpleRBAC | EnterpriseRBAC | With Redis Cache |
|-----------|------------|----------------|------------------|
| **Simple permission** | ~10ms | ~20ms | ~0.5ms |
| **Tree permission** | N/A | ~50ms | ~1ms |
| **ABAC permission** | N/A | ~100ms | ~2ms |

---

## Security Best Practices

### 1. Principle of Least Privilege

Grant minimum permissions needed:

```python
# ❌ Bad - overly permissive
editor = RoleModel(
    name="editor",
    permissions=["*:*"]  # All permissions!
)

# ✅ Good - specific permissions
editor = RoleModel(
    name="editor",
    permissions=["post:read", "post:create", "post:update"]
)
```

### 2. Avoid Wildcard Permissions

Use specific permissions instead of wildcards:

```python
# ❌ Bad
permissions=["*:read"]  # Read everything!

# ✅ Good
permissions=["post:read", "comment:read", "user:read"]
```

### 3. Validate Permission Format

OutlabsAuth validates permission format:

```python
# ✅ Valid
"user:create"
"post:read_tree"
"entity:*"

# ❌ Invalid
"user"           # Missing action
"create:user"    # Wrong order
"user::create"   # Double colon
```

### 4. Use Tree Permissions Carefully

Tree permissions are powerful - use with caution:

```python
# ✅ Good - specific tree permission
"project:read_tree"  # Read projects in subtree

# ⚠️ Use carefully
"entity:delete_tree"  # Can delete entire subtree!
```

### 5. Test Permission Logic

```python
async def test_editor_permissions():
    """Test editor role has correct permissions."""
    # Create test user with editor role
    user = await create_test_user(role="editor")

    # Should allow
    assert await auth.permission_service.check_permission(user.id, "post:create")
    assert await auth.permission_service.check_permission(user.id, "post:update")

    # Should deny
    assert not await auth.permission_service.check_permission(user.id, "post:delete")
    assert not await auth.permission_service.check_permission(user.id, "user:delete")
```

---

## Debugging Authorization

### Check User Permissions

```python
# Get all permissions for user
permissions = await auth.permission_service.get_user_permissions(user_id)
print(f"User permissions: {permissions}")

# EnterpriseRBAC - with entity context
permissions = await auth.permission_service.get_user_permissions(
    user_id=user_id,
    entity_id=entity_id
)
print(f"User permissions in {entity.name}: {permissions}")
```

### Check Specific Permission

```python
has_perm = await auth.permission_service.check_permission(
    user_id=user_id,
    permission="post:delete"
)
print(f"Can delete posts: {has_perm}")

# With explanation (if logging enabled)
# Logs:
# [INFO] Checking permission 'post:delete' for user '507f...'
# [INFO] User roles: ['editor', 'moderator']
# [INFO] Aggregated permissions: ['post:create', 'post:read', ...]
# [INFO] Permission check result: False
```

### CLI Tools

```bash
# List user permissions
outlabs-auth permissions list user@example.com

# Explain permission check
outlabs-auth permissions explain user@example.com post:delete

# Output:
# User: user@example.com
# Permission: post:delete
# Result: DENIED
# Reason: User has roles [editor], which grant [post:create, post:update]
#         Permission 'post:delete' not found
```

---

## Comparison Matrix

| Feature | SimpleRBAC | EnterpriseRBAC | EnterpriseRBAC + ABAC |
|---------|------------|----------------|-----------------------|
| **Flat permissions** | ✅ | ✅ | ✅ |
| **Entity hierarchy** | ❌ | ✅ | ✅ |
| **Tree permissions** | ❌ | ✅ | ✅ |
| **Context-aware roles** | ❌ | ✅ (opt-in) | ✅ (opt-in) |
| **Multiple memberships** | ❌ | ✅ | ✅ |
| **ABAC policies** | ❌ | ❌ | ✅ (opt-in) |
| **Complexity** | ⭐ Low | ⭐⭐ Medium | ⭐⭐⭐ High |
| **Setup time** | 5 min | 15 min | 30 min |
| **Permission check** | ~10ms | ~20ms | ~100ms |

---

## Summary

**Authorization in OutlabsAuth**:
- ✅ **SimpleRBAC**: Flat roles for simple apps
- ✅ **EnterpriseRBAC**: Hierarchical roles for organizations
- ✅ **ABAC**: Conditional policies for complex rules
- ✅ **Tree Permissions**: Hierarchical access control
- ✅ **Context-Aware Roles**: Adapt permissions by entity type
- ✅ **FastAPI Integration**: Dependency injection for permissions
- ✅ **Performance**: Redis caching, optimized queries
- ✅ **Security**: Least privilege, validation, testing

---

## Next Steps

- **[41. SimpleRBAC →](./41-SimpleRBAC.md)** - Flat role-based access control
- **[42. EnterpriseRBAC →](./42-EnterpriseRBAC.md)** - Hierarchical RBAC
- **[43. Permissions System →](./43-Permissions-System.md)** - Permission format and checking
- **[44. Tree Permissions →](./44-Tree-Permissions.md)** - Hierarchical access
- **[45. Context-Aware Roles →](./45-Context-Aware-Roles.md)** - Role adaptation
- **[46. ABAC Policies →](./46-ABAC-Policies.md)** - Attribute-based access control

---

## Further Reading

### Authorization Concepts
- [Role-Based Access Control (RBAC)](https://en.wikipedia.org/wiki/Role-based_access_control)
- [Attribute-Based Access Control (ABAC)](https://en.wikipedia.org/wiki/Attribute-based_access_control)
- [NIST RBAC Standard](https://csrc.nist.gov/projects/role-based-access-control)

### Implementation Guides
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [OAuth 2.0 Scopes vs Permissions](https://auth0.com/docs/get-started/apis/scopes)
