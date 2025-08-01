# Permission System Documentation

## Overview

OutLabs Auth uses a sophisticated hierarchical permission system that combines Role-Based Access Control (RBAC) with Attribute-Based Access Control (ABAC) capabilities. The system supports both built-in system permissions and custom permissions that can be created for domain-specific needs.

## Permission Types

### 1. System Permissions

System permissions are hardcoded and always available. They cannot be modified or deleted.

While system permissions primarily follow CRUD patterns for consistency, some non-CRUD actions are included where they represent specific operations:
- `user:invite` - Combined operation to create user and assign to entity
- Additional actions may be added as needed for system operations

#### Resource-Based Permissions
Each core resource has a standard set of permissions:

**Entity Permissions:**
- `entity:create` - Create new entities
- `entity:read` - View entities
- `entity:update` - Update entity details
- `entity:delete` - Delete entities
- `entity:create_tree` - Create entities in descendants
- `entity:read_tree` - View descendant entities
- `entity:update_tree` - Update descendant entities
- `entity:delete_tree` - Delete descendant entities
- `entity:read_all` - View all entities platform-wide

**User Permissions:**
- `user:create` - Create new users
- `user:read` - View user profiles
- `user:update` - Update user details
- `user:delete` - Delete users
- `user:invite` - Send user invitations
- `user:create_tree` - Create users in descendant entities
- `user:read_tree` - View users in descendant entities
- `user:update_tree` - Update users in descendant entities
- `user:delete_tree` - Delete users in descendant entities
- `user:invite_tree` - Invite users to descendant entities
- `user:read_all` - View all users platform-wide
- `user:create_all` - Create users anywhere
- `user:update_all` - Update users anywhere
- `user:delete_all` - Delete users anywhere
- `user:invite_all` - Invite users anywhere

**Role Permissions:**
- `role:create` - Create new roles
- `role:read` - View roles
- `role:update` - Update role permissions
- `role:delete` - Delete roles
- `role:assign` - Assign roles to users
- `role:create_tree` - Create roles in descendant entities
- `role:read_tree` - View roles in descendant entities
- `role:update_tree` - Update roles in descendant entities
- `role:delete_tree` - Delete roles in descendant entities
- `role:assign_tree` - Assign roles in descendant entities
- `role:read_all` - View all roles platform-wide
- `role:create_all` - Create roles anywhere
- `role:update_all` - Update roles anywhere
- `role:delete_all` - Delete roles anywhere
- `role:assign_all` - Assign roles anywhere

**Member Permissions:**
- `member:read` - View memberships
- `member:add` - Add new members
- `member:update` - Update member roles
- `member:remove` - Remove members
- `member:read_tree` - View memberships in descendant entities
- `member:add_tree` - Add members to descendant entities
- `member:update_tree` - Update members in descendant entities
- `member:remove_tree` - Remove members from descendant entities

#### Wildcard Permissions
- `*:read_all` - Read everything
- `*` - Absolute wildcard (system admin only)

### 2. Custom Permissions

Custom permissions can be created by platforms based on their specific needs. The system no longer creates any default custom permissions during initialization.

Custom permissions follow the `resource:action` format and can represent any operation your platform needs:
- Standard CRUD: `resource:create`, `resource:read`, `resource:update`, `resource:delete`
- Domain-specific actions: `invoice:approve`, `document:sign`, `report:generate`
- Workflow operations: `order:fulfill`, `ticket:escalate`, `lead:assign`
- Any other business logic: `commission:calculate`, `notification:send`, etc.

For hierarchical access, add the appropriate suffix:
- `resource:action_tree` - Perform action on descendants
- `resource:action_all` - Perform action platform-wide

Examples of valid custom permissions:
- `invoice:approve` - Approve invoices
- `document:sign_tree` - Sign documents in entity and descendants
- `report:export_all` - Export reports across entire platform
- `analytics:view` - View analytics dashboards
- `settings:configure` - Configure entity settings

## Permission Scoping

### Permission Scope Levels

The permission system uses three explicit scoping levels without automatic inheritance:

1. **Entity-specific permissions**: Grant access only to the specific entity
   - Format: `resource:action` (e.g., `user:create`, `role:update`)
   
2. **Tree permissions**: Grant access to all descendant entities
   - Format: `resource:action_tree` (e.g., `user:create_tree`, `role:update_tree`)
   - Note: Tree permissions do NOT apply to the entity where assigned, only descendants
   
3. **Platform-wide permissions**: Grant access across the entire platform
   - Format: `resource:action_all` (e.g., `user:read_all`, `role:create_all`)

### Examples

For a user with `user:create_tree` at the organization level:
- ❌ Cannot create users in the organization itself
- ✅ Can create users in all divisions under the organization
- ✅ Can create users in all teams under those divisions

For a user with `entity:update` and `entity:update_tree` at the division level:
- ✅ Can update the division itself (due to `entity:update`)
- ✅ Can update all teams under the division (due to `entity:update_tree`)
- ❌ Cannot update the parent organization

## Creating Custom Permissions

### Via API

```bash
POST /v1/permissions/
Authorization: Bearer <token>

{
    "name": "document:sign",
    "display_name": "Sign Documents",
    "description": "Allows signing official documents",
    "resource": "document",
    "action": "sign",
    "tags": ["document", "signature"],
    "metadata": {
        "requires_2fa": true,
        "audit_level": "high"
    }
}
```

### Via Code

```python
from api.services.permission_management_service import permission_management_service

permission = await permission_management_service.create_permission(
    name="report:generate",
    display_name="Generate Reports",
    description="Generate custom reports",
    entity_id=entity_id,  # Optional: scope to specific entity
    created_by=current_user,
    tags=["reporting"],
    metadata={"report_types": ["financial", "operational"]}
)
```

## Permission Checking

### In Routes

```python
from api.dependencies import require_permission

@router.post("/", dependencies=[Depends(require_permission("user:create"))])
async def create_user(user_data: UserCreate):
    # Route is protected by permission check
    pass
```

### In Services

```python
from api.services.permission_service import permission_service

# Check single permission
has_permission, reason = await permission_service.check_permission(
    user_id=str(user.id),
    permission="document:sign",
    entity_id=entity_id
)

if not has_permission:
    raise HTTPException(403, f"Permission denied: {reason}")
```

### Batch Permission Checking

```python
# Check multiple permissions at once
permissions_to_check = ["user:read", "user:create", "role:read"]
results = await permission_service.check_permissions_batch(
    user_id=str(user.id),
    permissions=permissions_to_check,
    entity_id=entity_id
)

# Results: {"user:read": True, "user:create": False, "role:read": True}
```

## Role Assignment

Roles in OutlabsAuth can be assigned in three different ways, providing flexibility for various organizational structures:

1. **Global Roles** - Can be assigned to users in any entity
2. **Entity-Specific Roles** - Can only be assigned within the entity that owns them
3. **Type-Specific Roles** - Can be assigned at any entity of specified types

For detailed information about role assignment, see the [Role Assignment Guide](ROLE_ASSIGNMENT_GUIDE.md).

## Role Templates and Permissions

When creating roles, you can use predefined templates that include common permission sets:

### Viewer Template
```python
permissions = [
    "entity:read",
    "user:read", 
    "role:read",
    "member:read"
]
```

### Editor Template
```python
permissions = [
    "entity:read", "entity:create", "entity:update",
    "user:read", "user:create", "user:update",
    "role:read", 
    "member:read", "member:add", "member:update"
]
```

### Administrator Template
```python
permissions = [
    "entity:read", "entity:create", "entity:update", "entity:delete",
    "user:read", "user:create", "user:update", "user:delete",
    "role:read", "role:create", "role:update", "role:delete", "role:assign",
    "member:read", "member:add", "member:update", "member:remove"
]
```

## Best Practices

1. **Use Least Privilege**: Grant only the minimum permissions needed
2. **Leverage Inheritance**: Use higher-level permissions when appropriate
3. **Create Domain-Specific Permissions**: Don't overload system permissions
4. **Document Custom Permissions**: Always provide clear descriptions
5. **Use Permission Tags**: Tag permissions for easier management
6. **Audit Permission Usage**: Monitor which permissions are actually used
7. **Test Permission Boundaries**: Ensure permissions are properly enforced

## Troubleshooting

### Common Issues

1. **"Invalid permission" error when creating roles**
   - Ensure the permission exists (check /v1/permissions/available)
   - Verify the permission name format (resource:action)
   - Check if using correct system permission names

2. **Permission denied despite having role**
   - Check entity context (permissions may be scoped)
   - Verify role is active and assigned properly
   - Check for permission inheritance

3. **Custom permissions not appearing**
   - Ensure permission is active
   - Check entity scope if applicable
   - Verify include_inherited parameter in queries

### Debug Commands

```python
# List all available permissions for a user
from api.services.permission_service import permission_service

permissions = await permission_service.get_user_permissions(
    user_id=str(user.id),
    entity_id=entity_id
)
print(f"User has {len(permissions)} permissions:")
for perm in permissions:
    print(f"  - {perm}")

# Check why a permission was denied
has_perm, reason = await permission_service.check_permission(
    user_id=str(user.id),
    permission="role:create",
    entity_id=entity_id,
    debug=True  # Enable debug mode
)
print(f"Permission check: {has_perm}")
print(f"Reason: {reason}")
```