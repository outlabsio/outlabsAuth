# Migration Guide: Context-Aware Roles

## Overview

This guide helps you migrate existing roles to use the new context-aware permissions feature. Context-aware roles allow a single role to have different permissions based on WHERE it's assigned in your entity hierarchy.

## What's Changed

### Before (Fixed Permissions)
```python
role = RoleModel(
    name="regional_manager",
    permissions=["entity:read", "entity:update", "user:read"],  # Same everywhere
    assignable_at_types=["region", "office", "team"]
)
```

### After (Context-Aware Permissions)
```python
role = RoleModel(
    name="regional_manager",
    permissions=["entity:read", "user:read"],  # Default/fallback
    entity_type_permissions={
        "region": ["entity:manage_tree", "user:manage_tree"],  # Full control at region
        "office": ["entity:read", "entity:update", "user:read"],  # Limited at office
        "team": ["entity:read", "user:read"]  # View-only at team
    },
    assignable_at_types=["region", "office", "team"]
)
```

## Migration Strategies

### Strategy 1: Gradual Migration (Recommended)

Keep existing roles working while gradually adding context awareness:

1. **No immediate changes required** - Existing roles continue to work with their default permissions
2. **Add entity_type_permissions to key roles** as needed
3. **Test thoroughly** before removing duplicate roles

```python
# Step 1: Identify a role that needs context awareness
existing_role = await RoleModel.find_one({"name": "branch_manager"})

# Step 2: Add entity_type_permissions (role still works with default permissions)
existing_role.entity_type_permissions = {
    "branch": [
        "entity:manage", "entity:manage_tree",
        "user:manage", "user:manage_tree",
        "role:assign", "member:manage"
    ],
    "team": [
        "entity:read", "user:read", "member:read"
    ]
}
await existing_role.save()

# Step 3: Test the role at different entity types
# Step 4: Once verified, update role assignments as needed
```

### Strategy 2: Role Consolidation

If you have multiple similar roles (e.g., `branch_manager_full`, `branch_manager_limited`), consolidate them:

```python
# Before: Multiple roles
branch_manager_full = RoleModel(name="branch_manager_full", ...)
branch_manager_limited = RoleModel(name="branch_manager_limited", ...)
branch_manager_viewer = RoleModel(name="branch_manager_viewer", ...)

# After: One context-aware role
branch_manager = RoleModel(
    name="branch_manager",
    display_name="Branch Manager",
    permissions=["entity:read", "user:read"],  # Minimum permissions
    entity_type_permissions={
        "branch": ["entity:manage", "user:manage", "role:assign"],
        "team": ["entity:read", "entity:update", "user:read"],
        "project": ["entity:read", "user:read"]
    }
)
```

## Migration Steps

### 1. Audit Existing Roles

First, identify roles that would benefit from context awareness:

```python
# Find roles assigned at multiple entity types
from collections import defaultdict

role_usage = defaultdict(set)
memberships = await EntityMembershipModel.find_all().to_list()

for membership in memberships:
    entity = await membership.entity.fetch()
    for role in membership.roles:
        role_obj = await role.fetch()
        role_usage[role_obj.name].add(entity.entity_type)

# Roles used at multiple entity types are candidates
for role_name, entity_types in role_usage.items():
    if len(entity_types) > 1:
        print(f"Role '{role_name}' used at: {entity_types}")
```

### 2. Update Role Definitions

Add entity_type_permissions to roles that need context awareness:

```python
async def migrate_role_to_context_aware(role_name: str, type_permissions: dict):
    """Migrate a role to use context-aware permissions"""
    role = await RoleModel.find_one({"name": role_name})
    if not role:
        print(f"Role {role_name} not found")
        return
    
    # Keep existing permissions as default
    if not role.entity_type_permissions:
        role.entity_type_permissions = {}
    
    # Add new context-aware permissions
    role.entity_type_permissions.update(type_permissions)
    
    await role.save()
    print(f"Updated {role_name} with context-aware permissions")

# Example migration
await migrate_role_to_context_aware(
    "team_lead",
    {
        "organization": ["entity:read_tree", "user:read_tree"],
        "division": ["entity:read_tree", "user:read_tree", "report:view"],
        "team": ["entity:manage", "user:manage", "task:assign", "report:generate"]
    }
)
```

### 3. Verify Permissions

Test that permissions work correctly at each entity type:

```python
async def verify_role_permissions(user_id: str, role_name: str):
    """Verify role permissions across different entity types"""
    from api.services.permission_service import permission_service
    
    memberships = await EntityMembershipModel.find(
        {"user.id": user_id}
    ).to_list()
    
    for membership in memberships:
        entity = await membership.entity.fetch()
        role = next((r for r in membership.roles if r.name == role_name), None)
        
        if role:
            permissions = await permission_service._get_role_permissions(
                str(role.id), 
                str(entity.id)
            )
            print(f"\nEntity: {entity.name} (type: {entity.entity_type})")
            print(f"Permissions: {permissions}")
```

### 4. Clean Up Duplicate Roles

Once context-aware roles are working, remove duplicates:

```python
# Identify duplicate roles to remove
roles_to_remove = [
    "regional_manager_full",
    "regional_manager_limited", 
    "regional_manager_advisory"
]

# First, update memberships to use the new consolidated role
new_role = await RoleModel.find_one({"name": "regional_manager"})

for old_role_name in roles_to_remove:
    old_role = await RoleModel.find_one({"name": old_role_name})
    if not old_role:
        continue
        
    # Find memberships using the old role
    memberships = await EntityMembershipModel.find(
        {"roles": old_role.id}
    ).to_list()
    
    for membership in memberships:
        # Replace old role with new role
        membership.roles = [r for r in membership.roles if r.id != old_role.id]
        membership.roles.append(new_role)
        await membership.save()
    
    # Delete the old role
    await old_role.delete()
    print(f"Removed duplicate role: {old_role_name}")
```

## Common Patterns

### Pattern 1: Hierarchical Degradation
Permissions decrease as you go down the hierarchy:

```python
entity_type_permissions={
    "platform": ["*"],  # Full access
    "organization": ["entity:manage_tree", "user:manage_tree", "role:manage"],
    "division": ["entity:manage", "user:manage", "role:assign"],
    "team": ["entity:read", "user:read", "task:manage"]
}
```

### Pattern 2: Specialized Contexts
Different permissions for different contexts:

```python
entity_type_permissions={
    "hospital": ["patient:admit", "staff:schedule", "equipment:order"],
    "clinic": ["patient:treat", "prescription:write"],
    "lab": ["test:order", "result:approve"],
    "pharmacy": ["prescription:fill", "inventory:manage"]
}
```

### Pattern 3: Cross-Functional Access
Limited permissions when working outside primary area:

```python
entity_type_permissions={
    "engineering": ["code:deploy", "infrastructure:manage", "team:lead"],
    "product": ["feature:approve", "roadmap:view", "metrics:analyze"],
    "support": ["ticket:view", "issue:escalate"],
    "sales": ["deal:view", "forecast:read"]
}
```

## Testing Checklist

- [ ] Existing roles still work with default permissions
- [ ] Context-aware permissions apply correctly at each entity type
- [ ] Permission inheritance works as expected
- [ ] No users lost access they should have
- [ ] Audit logs show correct permission sources
- [ ] API responses include proper permission sets
- [ ] Cache invalidation works when roles are updated

## Rollback Plan

If issues arise, you can quickly rollback:

1. **Remove entity_type_permissions** from roles:
```python
role.entity_type_permissions = {}
await role.save()
```

2. **Restore duplicate roles** if consolidated too early

3. **Clear permission cache**:
```python
await permission_service.invalidate_entity_cache(entity_id)
```

## API Changes

### Creating Roles with Context-Aware Permissions

```bash
POST /v1/roles
{
  "name": "project_manager",
  "display_name": "Project Manager",
  "permissions": ["entity:read", "user:read"],
  "entity_type_permissions": {
    "organization": ["project:create", "budget:view"],
    "project": ["project:manage", "task:assign", "budget:manage"],
    "team": ["task:view", "member:read"]
  },
  "assignable_at_types": ["organization", "project", "team"]
}
```

### Updating Existing Roles

```bash
PATCH /v1/roles/{role_id}
{
  "entity_type_permissions": {
    "branch": ["entity:manage", "user:manage"],
    "team": ["entity:read", "user:read"]
  }
}
```

## Support

If you encounter issues during migration:

1. Check role assignments are properly linked
2. Verify entity types match exactly (case-sensitive)
3. Clear Redis cache if permissions seem stale
4. Review audit logs for permission resolution details

Remember: The migration is backward compatible. Take your time and test thoroughly at each step.