# Tree Permissions Guide

## Critical Concept: Tree Permissions Apply to Descendants Only

**Tree permissions grant access to manage entities BELOW the assigned entity, not the entity itself.**

This is a fundamental design principle that often causes confusion. This guide explains how tree permissions work and provides clear examples.

## Understanding Permission Scopes

### 1. Regular Permissions (`resource:action`)
- **Scope**: The specific entity where assigned
- **Example**: `entity:update` in Organization A allows updating Organization A only

### 2. Tree Permissions (`resource:action_tree`)
- **Scope**: All descendants of the entity where assigned (children, grandchildren, etc.)
- **Example**: `entity:update_tree` in Organization A allows updating all divisions, departments, and teams under Organization A
- **Critical**: Does NOT allow updating Organization A itself

### 3. Platform Permissions (`resource:action_all`)
- **Scope**: All entities across the entire platform
- **Example**: `entity:update_all` allows updating any entity in the platform

## Common Scenarios and Solutions

### Scenario 1: Organization Admin
**Need**: Manage the organization and all its sub-entities

**Wrong Approach**:
```json
{
  "role": "org_admin",
  "permissions": [
    "entity:manage_tree"  // ❌ Only manages sub-entities, not the org itself
  ]
}
```

**Correct Approach**:
```json
{
  "role": "org_admin",
  "permissions": [
    "entity:manage",      // ✅ Manage the organization itself
    "entity:manage_tree"  // ✅ Manage all sub-entities
  ]
}
```

### Scenario 2: Division Manager
**Need**: Read the division info and manage all departments below

**Wrong Approach**:
```json
{
  "role": "division_manager",
  "permissions": [
    "entity:read_tree",   // ❌ Only reads sub-entities
    "entity:update_tree"  // ❌ Only updates sub-entities
  ]
}
```

**Correct Approach**:
```json
{
  "role": "division_manager",
  "permissions": [
    "entity:read",        // ✅ Read the division itself
    "entity:read_tree",   // ✅ Read all departments and teams below
    "entity:update_tree"  // ✅ Update all departments and teams below
  ]
}
```

### Scenario 3: Platform Administrator
**Need**: Full control over the platform and all entities

**Correct Approach**:
```json
{
  "role": "platform_admin",
  "permissions": [
    "entity:manage",      // ✅ Manage the platform entity
    "entity:manage_tree"  // ✅ Manage all organizations, divisions, etc.
    // OR simply use:
    "entity:manage_all"   // ✅ Manage everything (includes both above)
  ]
}
```

## Visual Representation

```
Platform (entity:manage + entity:manage_tree assigned here)
├── Can manage: Platform ✅ (due to entity:manage)
└── Can manage: Everything below ✅ (due to entity:manage_tree)
    ├── Organization A
    ├── Organization B
    └── Organization C
        ├── Division 1
        └── Division 2
            ├── Department A
            └── Department B
```

```
Organization C (entity:update_tree assigned here)
├── Can update: Organization C ❌ (no entity:update)
└── Can update: Everything below ✅ (due to entity:update_tree)
    ├── Division 1
    └── Division 2
        ├── Department A
        └── Department B
```

## Permission Inheritance Rules

1. **Tree permissions cascade down the hierarchy**
   - If you have `entity:update_tree` at Organization level, you can update all divisions, departments, and teams below
   - The permission check traverses up the ancestor chain looking for tree permissions

2. **Tree permissions do NOT apply to the assignment entity**
   - `entity:update_tree` at Organization level does NOT let you update the Organization
   - You need `entity:update` for that

3. **Manage permissions include sub-permissions**
   - `entity:manage` includes `create`, `read`, `update`, `delete`
   - `entity:manage_tree` includes `create_tree`, `read_tree`, `update_tree`, `delete_tree`

## Best Practices

### 1. Role Design
When creating roles, always consider whether users need to:
- Access only the entity itself → Use regular permissions
- Access only sub-entities → Use tree permissions
- Access both → Use both regular and tree permissions

### 2. Common Role Templates

**Organization Administrator**:
```json
{
  "permissions": [
    "entity:manage",          // Full control of the organization
    "entity:manage_tree",     // Full control of all sub-entities
    "user:manage",            // Manage users in the organization
    "user:manage_tree",       // Manage users in all sub-entities
    "role:manage",            // Manage roles in the organization
    "role:manage_tree"        // Manage roles in all sub-entities
  ]
}
```

**Read-Only Auditor** (can view everything in their assigned entity and below):
```json
{
  "permissions": [
    "entity:read",            // Read the assigned entity
    "entity:read_tree",       // Read all sub-entities
    "user:read",              // Read users in the assigned entity
    "user:read_tree",         // Read users in all sub-entities
    "role:read",              // Read roles in the assigned entity
    "role:read_tree"          // Read roles in all sub-entities
  ]
}
```

**Team Lead** (manages their team only, no sub-teams):
```json
{
  "permissions": [
    "entity:read",            // Read team info
    "entity:update",          // Update team info
    "user:manage",            // Manage team members
    "member:manage"           // Manage team membership
  ]
}
```

### 3. Testing Permissions
Always test your permission setup:
1. Can the user access the entity where they're assigned?
2. Can they access child entities as expected?
3. Are they properly restricted from parent entities?

## API Examples

### Creating a Role with Both Regular and Tree Permissions
```bash
curl -X POST http://localhost:8030/v1/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "regional_manager",
    "display_name": "Regional Manager",
    "entity_id": "REGION_ENTITY_ID",
    "permissions": [
      "entity:read",        
      "entity:update",      
      "entity:read_tree",   
      "entity:update_tree",
      "entity:create_tree",
      "user:read",
      "user:read_tree",
      "user:manage_tree"
    ]
  }'
```

### Checking Effective Permissions
When debugging, remember:
- A user with only `entity:update_tree` at Region level can update any Office, Department, or Team below
- But they CANNOT update the Region itself
- To update the Region, they need `entity:update` (without _tree)

## Common Mistakes to Avoid

1. **Assuming tree permissions include the current entity**
   - ❌ Wrong: "I have entity:manage_tree so I can manage this entity"
   - ✅ Right: "I have entity:manage_tree so I can manage entities below this one"

2. **Forgetting to assign regular permissions for entity access**
   - ❌ Wrong: Only assigning tree permissions to an admin
   - ✅ Right: Assigning both regular and tree permissions

3. **Misunderstanding permission checking direction**
   - Tree permissions are checked UP the hierarchy (from target entity to root)
   - When checking if a user can update Department X, the system checks:
     1. Does the user have `entity:update` in Department X?
     2. Does the user have `entity:update_tree` in any parent of Department X?
     3. Does the user have `entity:update_all` anywhere?

## Summary

**Remember**: Tree permissions (`_tree`) grant cascading access to all descendants but NOT to the entity where they're assigned. To manage both an entity and its descendants, you need both types of permissions.

This design provides fine-grained control over who can manage organizational structure versus who can manage the contents within that structure.