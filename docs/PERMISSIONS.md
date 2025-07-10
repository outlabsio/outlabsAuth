# Permission System Documentation

## Overview

OutLabs Auth uses a sophisticated hierarchical permission system that combines Role-Based Access Control (RBAC) with Attribute-Based Access Control (ABAC) capabilities. The system supports both built-in system permissions and custom permissions that can be created for domain-specific needs.

## Permission Types

### 1. System Permissions

System permissions are hardcoded and always available. They cannot be modified or deleted.

#### Core System Permissions
- `system:manage_all` - Full system administration
- `system:read_all` - Read all system configuration
- `platform:manage` - Platform-level management
- `platform:manage_platform` - Manage platform entities
- `platform:read_platform` - Read platform data

#### Resource-Based Permissions
Each core resource has a standard set of permissions:

**Entity Permissions:**
- `entity:manage_all` - Manage all entities
- `entity:manage` - Manage entities within scope
- `entity:create` - Create new entities
- `entity:read` - View entities
- `entity:update` - Update entity details
- `entity:delete` - Delete entities

**User Permissions:**
- `user:manage_all` - Full user management
- `user:manage_client` - Manage users within client
- `user:manage` - Standard user management
- `user:create` - Create new users
- `user:read` - View user profiles
- `user:update` - Update user details
- `user:delete` - Delete users
- `user:invite` - Send user invitations

**Role Permissions:**
- `role:manage_all` - Full role management
- `role:manage` - Manage roles
- `role:create` - Create new roles
- `role:read` - View roles
- `role:update` - Update role permissions
- `role:delete` - Delete roles
- `role:assign` - Assign roles to users

**Member Permissions:**
- `member:manage` - Manage entity members
- `member:read` - View memberships
- `member:add` - Add new members
- `member:update` - Update member roles
- `member:remove` - Remove members

#### Wildcard Permissions
- `*:manage_all` - All permissions
- `*:read_all` - Read everything
- `*` - Absolute wildcard (system admin only)

### 2. Custom Permissions

Custom permissions are created during system initialization and can be extended based on your needs.

#### Default Custom Permissions

**Organization Management:**
```
organization:manage_all - Full control over all organizations
organization:create - Create new organizations
organization:read - View organization details
organization:update - Update organization settings
organization:delete - Remove organizations
```

**Team/Branch Management:**
```
team:create - Create new teams or branches
team:manage - Manage team settings and members
team:read - View team information
```

**Project Permissions (Future):**
```
project:create - Create new projects
project:manage - Full project management
project:read - View project details
```

**Analytics & Reporting:**
```
analytics:view - Access analytics and reports
analytics:export - Export analytics data
```

**Audit & Compliance:**
```
audit:view - Access audit logs
audit:export - Export audit data
```

**API & Integration:**
```
api:manage - Manage API keys and integrations
api:create - Create new API keys
```

**Settings:**
```
settings:manage - Manage entity settings
settings:view - View entity settings
```

## Permission Inheritance

### Hierarchical Inheritance

The permission system uses automatic inheritance based on permission names:

1. **Action-based inheritance:**
   - `manage` → includes `read`
   - `manage` → includes `create`, `update`, `delete`
   
2. **Scope-based inheritance:**
   - `*:manage_all` → `*:manage_platform` → `*:manage_client` → `*:manage`
   - `*:read_all` → `*:read_platform` → `*:read`

### Examples

```
user:manage_all (granted)
├── user:manage_platform ✓ (inherited)
├── user:manage_client ✓ (inherited)
├── user:manage ✓ (inherited)
├── user:create ✓ (inherited)
├── user:read ✓ (inherited)
├── user:update ✓ (inherited)
└── user:delete ✓ (inherited)
```

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
from api.dependencies import check_hierarchical_permissions

@router.post("/", dependencies=[Depends(check_hierarchical_permissions("user:manage"))])
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
    "entity:read", "entity:create", "entity:manage",
    "user:read", "user:create", "user:manage",
    "role:read", 
    "member:read", "member:manage"
]
```

### Administrator Template
```python
permissions = [
    "entity:read", "entity:create", "entity:manage", "entity:delete",
    "user:read", "user:create", "user:manage", "user:delete",
    "role:read", "role:create", "role:manage",
    "member:read", "member:manage"
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