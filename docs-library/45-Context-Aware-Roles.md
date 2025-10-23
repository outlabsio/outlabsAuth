# 45. Context-Aware Roles

> **Quick Reference**: Roles that adapt their permissions based on the entity type, allowing the same role to grant different permissions in departments vs. teams.

## Overview

**Context-aware roles** allow a single role to have different permissions depending on the **entity type** where it's assigned.

**Example**: A "Manager" role might grant:
- `user:manage_tree` in a **Department** (manage all users in department hierarchy)
- `user:read` in a **Team** (only read users in team)

This is an **optional feature** in EnterpriseRBAC (opt-in via `enable_context_aware_roles=True`).

---

## Why Context-Aware Roles?

### Problem: Role Explosion

Without context-aware roles, you need separate roles for each context:

```python
# Without context-aware roles - MANY roles needed!
roles = [
    "department_manager",   # Can manage users in departments
    "team_manager",         # Can manage users in teams
    "project_lead",         # Can manage users in projects
    "department_viewer",    # Can view users in departments
    "team_viewer",          # Can view users in teams
    ...
]
# 🚨 10+ roles just for manager/viewer variations!
```

### Solution: Context-Aware Roles

With context-aware roles, one role adapts to context:

```python
# With context-aware roles - ONE role adapts!
manager_role = RoleModel(
    name="manager",
    permissions=["user:read"],  # Default: read-only

    # Context-specific permissions
    entity_type_permissions={
        "department": ["user:manage_tree", "role:assign"],  # More power in departments
        "team": ["user:read", "user:update"],               # Less power in teams
        "project": ["user:read"]                            # View-only in projects
    }
)
# ✅ One role, multiple behaviors!
```

---

## How It Works

### Permission Resolution Flow

```
User has "Manager" role in Marketing Department
      ↓
User tries to access permission "user:manage_tree"
      ↓
Check entity type: "department"
      ↓
Lookup role.entity_type_permissions["department"]
      ↓
Permissions: ["user:manage_tree", "role:assign"]
      ↓
✅ Permission granted! (user:manage_tree is in list)

---

Same user has "Manager" role in Design Team
      ↓
User tries to access permission "user:manage_tree"
      ↓
Check entity type: "team"
      ↓
Lookup role.entity_type_permissions["team"]
      ↓
Permissions: ["user:read", "user:update"]
      ↓
❌ Permission denied! (user:manage_tree NOT in team permissions)
```

---

## Setup

### Enable Context-Aware Roles

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=mongo_client,
    enable_context_aware_roles=True  # 🔑 Opt-in feature
)
```

**Requirements**:
- ✅ Must use **EnterpriseRBAC** (not SimpleRBAC)
- ✅ Entity hierarchy must be enabled (automatic in EnterpriseRBAC)
- ⚠️ Cannot use with SimpleRBAC (no entity types)

---

## Creating Context-Aware Roles

### Basic Role (No Context)

```python
# Regular role - same permissions everywhere
viewer = RoleModel(
    name="viewer",
    display_name="Viewer",
    permissions=["user:read", "entity:read"]  # Same in all contexts
)
await viewer.insert()
```

### Context-Aware Role

```python
# Role with context-specific permissions
manager = RoleModel(
    name="manager",
    display_name="Manager",

    # Default permissions (when entity type not specified)
    permissions=["user:read", "entity:read"],

    # Context-specific permissions
    entity_type_permissions={
        # More permissions in departments
        "department": [
            "user:read",
            "user:create",
            "user:update",
            "user:manage_tree",  # Can manage entire department hierarchy
            "role:assign",
            "entity:update"
        ],

        # Moderate permissions in teams
        "team": [
            "user:read",
            "user:update",
            "entity:read"
        ],

        # View-only in projects
        "project": [
            "user:read",
            "entity:read"
        ]
    }
)
await manager.insert()
```

### Permission Lookup Logic

```python
def get_permissions_for_entity_type(self, entity_type: Optional[str] = None) -> List[str]:
    """
    Get permissions for a specific entity type.

    Args:
        entity_type: Entity type (e.g., "department", "team")

    Returns:
        List of permissions for that entity type, or default permissions
    """
    # If no context-aware permissions, return default
    if not self.entity_type_permissions:
        return self.permissions

    # If entity type not specified, return default
    if not entity_type:
        return self.permissions

    # Return type-specific permissions if available, else default
    return self.entity_type_permissions.get(entity_type, self.permissions)
```

---

## Permission Checking

### Check Permission with Context

```python
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    entity_id: str,  # Context: which entity is user trying to delete in?
    auth_result = Depends(deps.require_permission("user:delete"))
):
    """
    Delete user - permission depends on entity type!
    """
    # Get entity to check type
    entity = await EntityModel.get(entity_id)

    # Check if user has permission in THIS entity type
    has_permission = await auth.permission_service.check_permission(
        user_id=auth_result["metadata"]["user"]["id"],
        permission="user:delete",
        entity_id=entity_id  # 🔑 Context matters!
    )

    if not has_permission:
        raise HTTPException(403, "Permission denied in this context")

    # Proceed with deletion
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}
```

---

## Complete Use Cases

### Use Case 1: Manager Role Across Entity Types

```python
# Create context-aware Manager role
manager = RoleModel(
    name="manager",
    display_name="Manager",
    permissions=["user:read"],  # Default fallback

    entity_type_permissions={
        "company": [
            "user:manage_tree",  # Full company hierarchy
            "department:create",
            "role:assign",
            "entity:*"  # All entity operations
        ],
        "department": [
            "user:manage_tree",  # Department hierarchy
            "team:create",
            "role:assign",
            "entity:update"
        ],
        "team": [
            "user:read",
            "user:update",  # Can update team members
            "entity:read"
        ],
        "project": [
            "user:read"  # View-only in projects
        ]
    }
)
await manager.insert()

# Assign manager to Marketing Department
await auth.membership_service.create_membership(
    user_id=john_id,
    entity_id=marketing_dept_id,
    role_ids=[manager.id]
)

# John's permissions in Marketing Department (type: department)
perms = await auth.permission_service.get_user_permissions(
    user_id=john_id,
    entity_id=marketing_dept_id
)
# Returns: ["user:manage_tree", "team:create", "role:assign", "entity:update"]

# John's permissions in Design Team (type: team)
perms = await auth.permission_service.get_user_permissions(
    user_id=john_id,
    entity_id=design_team_id
)
# Returns: ["user:read", "user:update", "entity:read"]
```

---

### Use Case 2: Different Viewer Levels

```python
# Context-aware Viewer role
viewer = RoleModel(
    name="viewer",
    display_name="Viewer",
    permissions=["entity:read"],  # Default

    entity_type_permissions={
        "department": [
            "user:read",
            "entity:read",
            "role:read",
            "report:read_tree"  # Can view all reports in dept
        ],
        "team": [
            "user:read",
            "entity:read"
        ],
        "project": [
            "entity:read"  # Can only see project info, not users
        ]
    }
)
```

---

### Use Case 3: HR Role (Company-Wide)

```python
# HR role - more permissions at company level
hr_role = RoleModel(
    name="hr",
    display_name="Human Resources",
    permissions=["user:read"],

    entity_type_permissions={
        "company": [
            "user:*",          # All user operations company-wide
            "entity:read",
            "role:read",
            "audit:read_tree"  # View all audit logs
        ],
        "department": [
            "user:read",
            "user:update",
            "entity:read"
        ],
        "team": [
            "user:read",
            "entity:read"
        ]
    }
)
```

---

## Permission Service Integration

### EnterprisePermissionService

The permission service automatically considers entity type when checking permissions:

```python
class EnterprisePermissionService:
    """Permission service with context-aware role support."""

    async def get_user_permissions(
        self,
        user_id: str,
        entity_id: Optional[str] = None
    ) -> List[str]:
        """
        Get user permissions, considering entity type.

        Args:
            user_id: User ID
            entity_id: Entity ID (context)

        Returns:
            List of permissions in this context
        """
        # Get user memberships
        memberships = await MembershipModel.find(
            MembershipModel.user_id == ObjectId(user_id),
            MembershipModel.entity_id == ObjectId(entity_id)
        ).to_list()

        # Get entity to determine type
        entity = await EntityModel.get(entity_id)

        all_permissions = set()

        for membership in memberships:
            # Get roles
            roles = await RoleModel.find(
                {"_id": {"$in": membership.role_ids}}
            ).to_list()

            for role in roles:
                # 🔑 Get context-aware permissions
                if self.config.enable_context_aware_roles:
                    perms = role.get_permissions_for_entity_type(entity.entity_type)
                else:
                    perms = role.permissions

                all_permissions.update(perms)

        return list(all_permissions)
```

---

## API Examples

### Endpoint with Context-Aware Permission

```python
from fastapi import FastAPI, Depends, HTTPException
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
deps = AuthDeps(auth)

@app.post("/entities/{entity_id}/users")
async def create_user_in_entity(
    entity_id: str,
    user_data: dict,
    auth_result = Depends(deps.require_auth())
):
    """
    Create user in specific entity - permission depends on entity type!
    """
    current_user_id = auth_result["metadata"]["user"]["id"]

    # Check if user has permission IN THIS ENTITY TYPE
    has_permission = await auth.permission_service.check_permission(
        user_id=current_user_id,
        permission="user:create",
        entity_id=entity_id  # Context!
    )

    if not has_permission:
        # Get entity to show helpful error
        entity = await EntityModel.get(entity_id)
        raise HTTPException(
            403,
            f"You don't have 'user:create' permission in {entity.entity_type}s"
        )

    # Create user
    new_user = await auth.user_service.create_user(**user_data)

    # Link to entity
    await auth.membership_service.create_membership(
        user_id=new_user.id,
        entity_id=entity_id,
        role_ids=[]  # No roles initially
    )

    return {"user_id": str(new_user.id)}
```

---

## Combining with Tree Permissions

Context-aware roles work beautifully with tree permissions:

```python
# Manager role with tree permissions
manager = RoleModel(
    name="manager",
    display_name="Manager",

    entity_type_permissions={
        "department": [
            "user:manage_tree",    # Manage all users in department tree
            "entity:read_tree",    # View all child entities
            "role:assign"
        ],
        "team": [
            "user:read",           # Only read users in team (no tree)
            "user:update",
            "entity:read"          # No tree access
        ]
    }
)

# User is manager in Marketing Department
# ✅ Can manage users in all teams under Marketing (tree permission)

# User is manager in Design Team
# ❌ Cannot manage users in other teams (no tree permission)
```

**See Also**: [52. Entity Hierarchy](./52-Entity-Hierarchy.md) for tree permissions.

---

## Configuration

### Enable/Disable Context-Aware Roles

```python
# Enable (EnterpriseRBAC)
auth = EnterpriseRBAC(
    database=mongo_client,
    enable_context_aware_roles=True  # Opt-in
)

# Disable (EnterpriseRBAC - uses only default permissions)
auth = EnterpriseRBAC(
    database=mongo_client,
    enable_context_aware_roles=False  # Default
)

# SimpleRBAC - not available
auth = SimpleRBAC(database=mongo_client)
# No entity types, so context-aware roles don't make sense
```

### Validation

```python
# OutlabsAuth validates configuration
try:
    auth = OutlabsAuth(
        database=mongo_client,
        enable_entity_hierarchy=False,  # No hierarchy
        enable_context_aware_roles=True  # But wants context-aware?
    )
except ValueError as e:
    print(e)
    # "enable_context_aware_roles requires enable_entity_hierarchy=True"
```

---

## Common Patterns

### Pattern 1: Progressive Permissions

More permissions at higher levels, less at lower levels:

```python
role = RoleModel(
    name="supervisor",
    permissions=["user:read"],

    entity_type_permissions={
        "company": ["user:*", "entity:*", "role:*"],        # Full power
        "division": ["user:manage_tree", "entity:update"],  # Strong power
        "department": ["user:update", "entity:read"],       # Moderate power
        "team": ["user:read"],                              # View-only
    }
)
```

### Pattern 2: Specialization by Type

Different capabilities based on entity purpose:

```python
role = RoleModel(
    name="lead",
    permissions=["user:read"],

    entity_type_permissions={
        "development_team": [
            "user:update",
            "code:review",
            "deploy:staging"
        ],
        "design_team": [
            "user:update",
            "asset:upload",
            "design:approve"
        ],
        "qa_team": [
            "user:update",
            "bug:manage",
            "test:run"
        ]
    }
)
```

### Pattern 3: Inheritance with Override

Default permissions, with overrides for specific types:

```python
role = RoleModel(
    name="contributor",

    # Default for all entity types
    permissions=["user:read", "entity:read", "content:create"],

    # Override for specific types
    entity_type_permissions={
        "archive": ["entity:read"],  # View-only in archives
        "public_entity": ["content:create", "content:publish"]  # Can publish in public
    }
)
```

---

## Debugging Context-Aware Roles

### Inspect Role Permissions

```python
# Get role
role = await RoleModel.find_one(RoleModel.name == "manager")

# Check default permissions
print(f"Default: {role.permissions}")

# Check type-specific permissions
if role.entity_type_permissions:
    for entity_type, perms in role.entity_type_permissions.items():
        print(f"{entity_type}: {perms}")

# Example output:
# Default: ['user:read']
# department: ['user:manage_tree', 'role:assign', 'entity:update']
# team: ['user:read', 'user:update', 'entity:read']
# project: ['user:read']
```

### Check User Permissions in Context

```python
# Check what permissions user has in specific entity
entity = await EntityModel.get(entity_id)

permissions = await auth.permission_service.get_user_permissions(
    user_id=user_id,
    entity_id=entity_id
)

print(f"User permissions in {entity.name} ({entity.entity_type}):")
for perm in permissions:
    print(f"  - {perm}")

# Example output:
# User permissions in Marketing Department (department):
#   - user:manage_tree
#   - role:assign
#   - entity:update
```

---

## Performance Considerations

### Caching Context-Aware Permissions

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=mongo_client,
    enable_context_aware_roles=True,
    enable_caching=True,  # Cache context-aware permission results
    redis_url="redis://localhost:6379"
)
```

**Cache Key Format**:
```
auth:perms:{user_id}:{entity_id}:{entity_type}
```

**Cache Invalidation**:
- When role permissions updated
- When user membership changes
- When role assignment changes

---

## Migration Guide

### From Regular Roles to Context-Aware Roles

**Before** (separate roles for each context):

```python
# Old approach - many roles
dept_manager = RoleModel(
    name="department_manager",
    permissions=["user:manage_tree", "role:assign"]
)

team_manager = RoleModel(
    name="team_manager",
    permissions=["user:read", "user:update"]
)

project_viewer = RoleModel(
    name="project_viewer",
    permissions=["user:read"]
)

# Assign appropriate role per entity type
if entity.entity_type == "department":
    role_id = dept_manager.id
elif entity.entity_type == "team":
    role_id = team_manager.id
else:
    role_id = project_viewer.id
```

**After** (one context-aware role):

```python
# New approach - one role
manager = RoleModel(
    name="manager",
    permissions=["user:read"],

    entity_type_permissions={
        "department": ["user:manage_tree", "role:assign"],
        "team": ["user:read", "user:update"],
        "project": ["user:read"]
    }
)

# Single role works everywhere!
await auth.membership_service.create_membership(
    user_id=user_id,
    entity_id=entity_id,
    role_ids=[manager.id]  # Same role, different behavior per entity type
)
```

---

## Limitations

### 1. Requires Entity Hierarchy

Context-aware roles ONLY work with entity hierarchy:

```python
# ❌ Cannot use with SimpleRBAC
auth = SimpleRBAC(database=db)
# No entity types → no context-aware roles

# ✅ Must use EnterpriseRBAC
auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True
)
```

### 2. Entity Type Must Exist

Permission lookup requires valid entity type:

```python
# Entity type must be set
entity = EntityModel(
    name="Marketing",
    entity_type="department",  # 🔑 Required for context-aware roles
    classification="STRUCTURAL"
)

# ❌ Entity without type - falls back to default permissions
entity = EntityModel(
    name="Orphan",
    entity_type=None  # No context!
)
```

### 3. No Circular Context

Context is based on entity type, not entity instance:

```python
# ❌ Cannot do: "More permissions in THIS specific department"
# ✅ Can do: "More permissions in ALL departments"

entity_type_permissions={
    "department": ["user:manage_tree"],  # All departments
    # Cannot specify: "marketing_department_only"
}
```

---

## Best Practices

### 1. Use Consistent Entity Types

Define standard entity types and stick to them:

```python
# Good - consistent types
ENTITY_TYPES = [
    "company",
    "division",
    "department",
    "team",
    "project"
]

# Bad - inconsistent types
# "dept", "department", "dpt" → confusion!
```

### 2. Document Permission Matrix

Create a table showing permissions per type:

```markdown
| Role    | Company | Department | Team | Project |
|---------|---------|------------|------|---------|
| Admin   | user:*  | user:*     | user:* | user:* |
| Manager | user:manage_tree | user:manage_tree | user:update | user:read |
| Viewer  | user:read | user:read | user:read | user:read |
```

### 3. Default to Least Privilege

Set `permissions` (default) to minimum permissions:

```python
role = RoleModel(
    name="manager",
    permissions=["user:read"],  # Default: least privilege

    entity_type_permissions={
        "department": ["user:manage_tree"],  # More in specific contexts
        ...
    }
)
```

### 4. Test All Contexts

Test role behavior in each entity type:

```python
async def test_manager_role_context_aware():
    """Test manager role in different entity types."""
    manager = await RoleModel.find_one(RoleModel.name == "manager")

    # Test in department
    dept = await EntityModel.find_one(EntityModel.entity_type == "department")
    perms = manager.get_permissions_for_entity_type("department")
    assert "user:manage_tree" in perms

    # Test in team
    team = await EntityModel.find_one(EntityModel.entity_type == "team")
    perms = manager.get_permissions_for_entity_type("team")
    assert "user:manage_tree" not in perms
    assert "user:update" in perms
```

---

## Summary

| Aspect | Without Context-Aware Roles | With Context-Aware Roles |
|--------|---------------------------|--------------------------|
| **Role Count** | Many (one per context) | Few (one role, many contexts) |
| **Flexibility** | Low (fixed permissions) | High (permissions adapt) |
| **Complexity** | Simple (one role = one permission set) | Medium (role has multiple permission sets) |
| **Maintenance** | High (update many roles) | Low (update one role) |
| **Use Case** | Flat organizations | Hierarchical organizations |
| **Preset** | SimpleRBAC or EnterpriseRBAC | EnterpriseRBAC only |

**When to Use**:
- ✅ You have different entity types (departments, teams, projects)
- ✅ Same role should behave differently per type
- ✅ You want to reduce role proliferation
- ✅ Using EnterpriseRBAC

**When to Skip**:
- ❌ Using SimpleRBAC (flat structure)
- ❌ All entities are the same type
- ❌ Permissions don't vary by entity type

---

## Next Steps

- **[52. Entity Hierarchy →](./52-Entity-Hierarchy.md)** - Understand entity types and hierarchy
- **[53. Tree Permissions →](./53-Tree-Permissions.md)** - Hierarchical permission inheritance
- **[54. Entity Memberships →](./54-Entity-Memberships.md)** - Assign roles to users in entities
- **[44. Role Management →](./44-Role-Management.md)** - Create and manage roles

---

## Further Reading

### Context-Aware Access Control
- [Attribute-Based Access Control (ABAC)](https://en.wikipedia.org/wiki/Attribute-based_access_control)
- [Context-Aware Security](https://www.nist.gov/publications/guide-attribute-based-access-control-abac-definition-and-considerations)

### Design Decisions
- [DD-016: Optional Features in EnterpriseRBAC](../docs/DESIGN_DECISIONS.md#dd-016)
- [DD-017: Entity Hierarchy Always Enabled](../docs/DESIGN_DECISIONS.md#dd-017)
