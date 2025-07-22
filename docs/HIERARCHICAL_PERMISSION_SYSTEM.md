# Hierarchical Permission System

## Overview

OutlabsAuth implements a sophisticated three-tier permission scoping model that provides flexible access control across entity hierarchies. This system allows permissions to be granted at specific entities, across entire subtrees, or platform-wide.

## Permission Scoping Levels

### 1. Entity-Specific Permissions (`resource:action`)
- **Scope**: Access only within the specific entity where the permission is granted
- **Example**: `entity:update` - Can only update the specific entity
- **Use Case**: Team lead who can only manage their own team

### 2. Tree/Hierarchical Permissions (`resource:action_tree`)
- **Scope**: Access within the entity and all its descendants
- **Example**: `entity:create_tree` - Can create entities anywhere in the subtree
- **Use Case**: Regional manager who can manage all offices and teams in their region

### 3. Platform-Wide Permissions (`resource:action_all`)
- **Scope**: Access across the entire platform
- **Example**: `user:manage_all` - Can manage users anywhere in the platform
- **Use Case**: Platform administrator with full access

## How Tree Permissions Work

### Permission Checking Algorithm

When checking if a user has permission to perform an action on an entity:

1. **Direct Check**: First checks if the user has the exact permission in the target entity
2. **Tree Permission Check**: If not found, checks all ancestor entities for `_tree` permissions
3. **Platform Check**: Finally checks for `_all` permissions

```python
# Example: Checking if user can create an entity under "division"
# The system checks:
1. entity:create in division (direct)
2. entity:create_tree in organization (parent)
3. entity:create_tree in platform (grandparent)
4. entity:create_all (platform-wide)
```

### Implementation Details

Tree permissions are implemented in:
- `api/services/permission_service.py` - Core permission checking logic
- `api/dependencies.py` - Request-level permission dependencies
- `api/routes/entity_routes.py` - Route handlers that use tree permissions

## Common Permission Patterns

### Resource Management Hierarchy

For each resource (entity, user, role, member), permissions follow this pattern:

```
resource:manage_tree
├── resource:create_tree
├── resource:read_tree
├── resource:update_tree
└── resource:delete_tree
```

### Action Inheritance

The `manage` action includes all other actions:
- `entity:manage` → `create`, `read`, `update`, `delete`
- `entity:manage_tree` → `create_tree`, `read_tree`, `update_tree`, `delete_tree`

## Real-World Examples

### 1. Regional Office Structure
```
Platform (OutlabsAuth)
└── Organization (ACME Corp)
    ├── West Region
    │   ├── Seattle Office
    │   │   ├── Sales Team
    │   │   └── Support Team
    │   └── Portland Office
    └── East Region
```

**Regional Manager** with `entity:manage_tree` at "West Region":
- ✅ Can create new offices in West Region
- ✅ Can update Seattle Office details
- ✅ Can create teams under any West Region office
- ❌ Cannot access East Region entities

### 2. Platform Administrator
```
Platform Admin with permissions at platform level:
- entity:manage_tree
- user:manage_tree
- role:manage_tree
```

**Can**:
- ✅ Create organizations
- ✅ Manage any entity in the platform
- ✅ Create users anywhere
- ✅ Assign roles at any level

### 3. Cross-Functional Access Groups
```
Engineering Dept
└── Frontend Team

Marketing Dept
└── Content Team

Product Launch Group (ACCESS_GROUP)
├── Frontend Team member
└── Content Team member
```

**Project Member** with `entity:update` in "Product Launch Group":
- ✅ Can update the access group
- ✅ Can see other members
- ❌ Cannot modify Engineering or Marketing departments

## Current Implementation Status

### ✅ Working Features
- Entity creation with tree permissions
- Member management with tree permissions
- Permission checking traverses full ancestor chain
- Deep hierarchy support (unlimited levels)
- Entity visibility respects tree permissions

### ⚠️ Known Issues
1. **Entity Update Tree Permissions** (Partially Working)
   - Platform admins with `entity:update_tree` cannot update child organizations
   - The `require_entity_update_with_tree` dependency has bugs
   - Affects 3 tests in complex scenarios

2. **No Circular Hierarchy Prevention**
   - System doesn't prevent A→B→C→A circular references
   - Marked as known limitation in tests

## API Examples

### Creating an Entity (Tree Permission Check)
```python
# POST /v1/entities
# Headers: Authorization: Bearer <token>
{
    "name": "new_team",
    "display_name": "New Team",
    "entity_type": "team",
    "entity_class": "STRUCTURAL",
    "parent_entity_id": "division_id"
}

# System checks:
# 1. entity:create (direct permission)
# 2. entity:create_tree in division
# 3. entity:create_tree in organization (parent of division)
# 4. entity:create_tree in platform (parent of organization)
# 5. entity:create_all (platform-wide)
```

### Checking Permissions
```python
# POST /v1/entities/{entity_id}/check-permissions
{
    "permissions": [
        "entity:read",
        "entity:update",
        "entity:create_tree",
        "member:manage_tree"
    ]
}

# Response:
{
    "entity_id": "...",
    "permissions": {
        "entity:read": true,
        "entity:update": false,
        "entity:create_tree": true,
        "member:manage_tree": true
    },
    "source": {
        "entity:read": "direct",
        "entity:create_tree": "role_tree",
        "member:manage_tree": "role_tree"
    }
}
```

## Best Practices

### 1. Use Appropriate Scoping
- Grant the minimum scope needed
- Prefer `_tree` permissions for hierarchical management
- Reserve `_all` permissions for system administrators

### 2. Role Design
```python
# Good: Regional Manager Role
{
    "name": "regional_manager",
    "permissions": [
        "entity:read_tree",      # See all sub-entities
        "entity:create_tree",    # Create offices/teams
        "entity:update_tree",    # Update any sub-entity
        "member:manage_tree",    # Manage all members
        "user:read_tree"         # View all users
    ]
}

# Bad: Over-permissioned Role
{
    "name": "team_lead",
    "permissions": [
        "entity:manage_all",     # Too broad!
        "user:manage_all"        # Too broad!
    ]
}
```

### 3. Testing Tree Permissions
Always test:
- Permission works at the exact level granted
- Permission works for all descendants
- Permission doesn't work for siblings or ancestors
- Permission doesn't work outside the tree

## Troubleshooting

### Common Issues

1. **"Missing required permission" errors**
   - Check if you need a `_tree` variant
   - Verify the entity hierarchy is correct
   - Ensure user has membership in the right entity

2. **Tree permissions not working**
   - Confirm the permission includes `_tree` suffix
   - Check parent-child relationships are properly set
   - Verify role is assigned at the correct level

3. **Update operations failing**
   - Known issue with `entity:update_tree`
   - Workaround: Grant direct `entity:update` permission
   - Fix in progress

## Future Enhancements

1. **Conditional Tree Permissions**
   - Add ABAC conditions to tree permissions
   - Example: `entity:update_tree` only for entities with specific attributes

2. **Permission Delegation**
   - Allow users to delegate their tree permissions to others
   - Time-limited delegation support

3. **Audit Trail**
   - Track how permissions were resolved (direct vs tree vs all)
   - Log permission check paths for debugging

## Related Documentation
- [Permission Model](./PERMISSION_MODEL.md)
- [Entity Hierarchy](./ENTITY_HIERARCHY.md)
- [Platform Scenarios](./PLATFORM_SCENARIOS.md)
- [API Integration Patterns](./API_INTEGRATION_PATTERNS.md)