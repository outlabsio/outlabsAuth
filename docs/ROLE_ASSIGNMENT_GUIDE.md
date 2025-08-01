# Role Assignment Guide

## Overview

OutlabsAuth uses a flexible role assignment system that allows roles to be assigned in three different ways. This guide explains how role assignment works, the restrictions that apply, and common patterns for different use cases.

## Understanding Role Model Fields

The `RoleModel` has several key fields that control how and where a role can be assigned:

```python
class RoleModel:
    name: str                              # Unique identifier (e.g., "team_lead")
    display_name: str                      # User-friendly name (e.g., "Team Lead")
    permissions: List[str]                 # List of permissions this role grants
    entity: Link[EntityModel]              # The entity that OWNS this role
    assignable_at_types: List[str]         # Entity types where this role can be assigned
    is_global: bool                        # Whether this is a platform-wide role
    is_system_role: bool                   # Whether this is a system-defined role
```

## The Three Ways a Role Can Be Assigned

### 1. Global Roles (Platform-Wide)

Global roles can be assigned to users in ANY entity across the entire platform.

**Characteristics:**
- `is_global = True`
- Can be assigned at any entity regardless of ownership
- Typically created at the platform level
- Examples: "System Administrator", "Platform Auditor"

**Example:**
```python
# Creating a global role
global_viewer = RoleModel(
    name="global_viewer",
    display_name="Global Viewer",
    permissions=["entity:read_all", "user:read_all"],
    entity=platform_entity,  # Usually owned by the platform
    is_global=True
)

# This role can be assigned to users in ANY entity
```

### 2. Entity-Specific Roles

These roles can only be assigned to users within the entity that owns the role.

**Characteristics:**
- `is_global = False`
- `entity` field determines where it can be assigned
- Most restrictive assignment scope
- Examples: "Miami Office Manager", "Finance Team Lead"

**Example:**
```python
# Creating an entity-specific role
miami_manager = RoleModel(
    name="miami_manager",
    display_name="Miami Office Manager",
    permissions=["entity:update", "user:manage", "report:view"],
    entity=miami_office_entity,  # Owned by Miami office
    is_global=False,
    assignable_at_types=[]  # Empty or omitted
)

# This role can ONLY be assigned to users in the Miami office entity
```

### 3. Type-Specific Roles (Flexible Assignment)

These roles can be assigned at any entity of specific types, regardless of which entity owns the role.

**Characteristics:**
- `is_global = False`
- `assignable_at_types` contains list of entity types
- Allows cross-entity assignment within type constraints
- Examples: "Branch Manager" (assignable at any branch), "Team Lead" (assignable at any team)

**Example:**
```python
# Creating a type-specific role
branch_manager = RoleModel(
    name="branch_manager",
    display_name="Branch Manager",
    permissions=["entity:manage", "user:manage", "report:view_branch"],
    entity=headquarters_entity,  # Owned by headquarters
    is_global=False,
    assignable_at_types=["branch", "office"]  # Can be assigned at any branch or office
)

# This role can be assigned to users in ANY entity with type "branch" or "office"
```

## Assignment Logic

When assigning a role to a user in an entity, the system checks these conditions in order:

```python
def can_assign_role(role, target_entity):
    # 1. Global roles can always be assigned
    if role.is_global:
        return True
    
    # 2. Check if role belongs to the target entity
    if role.entity.id == target_entity.id:
        return True
    
    # 3. Check if target entity's type is in assignable_at_types
    if target_entity.entity_type in role.assignable_at_types:
        return True
    
    return False
```

## Common Patterns and Use Cases

### Pattern 1: Hierarchical Organization with Shared Roles

**Scenario:** A company with multiple branches wants consistent roles across all branches.

```python
# Create roles at the platform/company level
company = EntityModel(name="acme_corp", entity_type="company")

# Branch-specific roles that can be used at any branch
branch_admin = RoleModel(
    name="branch_admin",
    display_name="Branch Administrator",
    entity=company,
    assignable_at_types=["branch"],
    permissions=["entity:manage", "user:manage", "report:view"]
)

branch_agent = RoleModel(
    name="branch_agent",
    display_name="Branch Agent",
    entity=company,
    assignable_at_types=["branch"],
    permissions=["user:read", "report:view_own"]
)

# Now these roles can be assigned at any branch
miami_branch = EntityModel(name="miami", entity_type="branch", parent=company)
ny_branch = EntityModel(name="new_york", entity_type="branch", parent=company)

# Both branches can use the same role definitions
```

### Pattern 2: Platform-Wide Administrative Roles

**Scenario:** System administrators who need access across all entities.

```python
# Create global roles for platform administration
system_admin = RoleModel(
    name="system_admin",
    display_name="System Administrator",
    entity=platform_entity,
    is_global=True,
    permissions=["*"]  # All permissions
)

platform_auditor = RoleModel(
    name="platform_auditor",
    display_name="Platform Auditor",
    entity=platform_entity,
    is_global=True,
    permissions=["*:read_all"]  # Read-only access everywhere
)
```

### Pattern 3: Entity-Specific Custom Roles

**Scenario:** Each department needs unique roles that shouldn't be used elsewhere.

```python
# Engineering department with specific roles
eng_dept = EntityModel(name="engineering", entity_type="department")

eng_architect = RoleModel(
    name="eng_architect",
    display_name="Engineering Architect",
    entity=eng_dept,
    is_global=False,
    assignable_at_types=[],  # Only for engineering dept
    permissions=["code:review", "architecture:approve", "team:lead"]
)

# Finance department with different roles
finance_dept = EntityModel(name="finance", entity_type="department")

finance_controller = RoleModel(
    name="finance_controller",
    display_name="Finance Controller",
    entity=finance_dept,
    is_global=False,
    assignable_at_types=[],  # Only for finance dept
    permissions=["invoice:approve", "budget:manage", "report:financial"]
)
```

### Pattern 4: Cross-Functional Access Groups

**Scenario:** Access groups that span multiple entities need consistent roles.

```python
# Create roles that can be assigned to any access group
platform = EntityModel(name="platform", entity_type="platform")

access_viewer = RoleModel(
    name="access_viewer",
    display_name="Access Group Viewer",
    entity=platform,
    assignable_at_types=["access_group", "committee", "project_team"],
    permissions=["entity:read", "member:read"]
)

access_contributor = RoleModel(
    name="access_contributor",
    display_name="Access Group Contributor",
    entity=platform,
    assignable_at_types=["access_group", "committee", "project_team"],
    permissions=["entity:read", "entity:update", "document:create", "document:update"]
)
```

## Best Practices

### 1. Choose the Right Scope

- **Use Global Roles** for platform-wide administrative functions
- **Use Entity-Specific Roles** for unique organizational responsibilities
- **Use Type-Specific Roles** for consistent roles across similar entities

### 2. Role Naming Conventions

```python
# Global roles: prefix with "global_"
"global_admin", "global_viewer", "global_auditor"

# Type-specific roles: include the type in the name
"branch_manager", "team_lead", "dept_head"

# Entity-specific roles: include entity identifier
"miami_coordinator", "finance_approver", "hr_specialist"
```

### 3. Permission Design

- Keep permissions granular and specific
- Use consistent naming: `resource:action` or `resource:action_scope`
- Avoid overlapping permissions between roles
- Document what each permission allows

### 4. Role Hierarchies

While roles don't inherit from each other, you can create hierarchical permission sets:

```python
# Base permissions for all team members
team_member_perms = ["task:read", "task:create_own", "comment:create"]

# Team lead has member permissions plus more
team_lead_perms = team_member_perms + ["task:assign", "report:view_team"]

# Manager has lead permissions plus more
manager_perms = team_lead_perms + ["team:manage", "budget:view"]
```

## Troubleshooting

### Issue: "Role cannot be assigned to this entity"

**Possible Causes:**
1. Role is not global and doesn't belong to the target entity
2. Target entity's type is not in `assignable_at_types`
3. Role might be inactive or deleted

**Debugging Steps:**
```python
# Check role properties
print(f"Role is_global: {role.is_global}")
print(f"Role entity: {role.entity.id}")
print(f"Role assignable_at_types: {role.assignable_at_types}")
print(f"Target entity type: {target_entity.entity_type}")
```

### Issue: "User's roles not showing in UI"

**Possible Causes:**
1. Roles not being fetched when loading user
2. Frontend not including existing roles in selection
3. Role assignment not persisted properly

**Solution:** Ensure the frontend includes existing roles when in edit mode and that the backend properly checks all three assignment criteria.

## API Examples

### Creating Roles

```bash
# Global role
POST /v1/roles
{
  "name": "global_reporter",
  "display_name": "Global Reporter",
  "permissions": ["report:view_all", "analytics:read"],
  "is_global": true
}

# Type-specific role
POST /v1/roles
{
  "name": "office_manager",
  "display_name": "Office Manager",
  "permissions": ["entity:manage", "user:manage"],
  "assignable_at_types": ["office", "branch"]
}

# Entity-specific role
POST /v1/roles
{
  "name": "miami_lead",
  "display_name": "Miami Team Lead",
  "permissions": ["team:manage", "report:view"],
  "entity_id": "ent_miami_office"
}
```

### Assigning Roles to Users

```bash
# During user creation
POST /v1/users
{
  "email": "user@example.com",
  "profile": {
    "first_name": "John",
    "last_name": "Doe"
  },
  "entity_assignments": [
    {
      "entity_id": "ent_miami_office",
      "role_ids": ["role_office_manager", "role_global_viewer"]
    }
  ]
}

# Updating existing user
PUT /v1/users/{user_id}/entities
{
  "entity_assignments": [
    {
      "entity_id": "ent_miami_office",
      "role_ids": ["role_office_manager", "role_branch_agent"]
    }
  ]
}
```

## Summary

The three-criteria role assignment system provides maximum flexibility:

1. **Global Roles** (`is_global=true`) - Assignable anywhere
2. **Entity-Specific Roles** (owned by entity) - Assignable only in that entity
3. **Type-Specific Roles** (`assignable_at_types`) - Assignable at specific entity types

This design allows organizations to:
- Maintain consistent roles across similar entities
- Create unique roles for specific departments
- Implement platform-wide administrative roles
- Scale their permission system as they grow

Always test role assignments thoroughly and document your role strategy for your organization.