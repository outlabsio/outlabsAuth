# Role System Documentation

## Overview

The OutlabsAuth system implements a **scoped role architecture** with **hierarchical permissions** that provides flexible, secure, and scalable role-based access control (RBAC) across multiple organizational levels. This system combines clean MongoDB ObjectIds with scope-based tenant isolation and intelligent permission inheritance.

## 🏗️ **Architecture: Scoped Roles + Hierarchical Permissions**

### **Two-Layer System Design**

```
ROLES (Scoped Containers)
├─ System Roles    → Global roles (scope: system, scope_id: null)
├─ Platform Roles  → Platform-specific roles (scope: platform, scope_id: platform_id)
└─ Client Roles    → Client organization roles (scope: client, scope_id: client_account_id)

PERMISSIONS (Hierarchical Inheritance)
├─ manage_all     → Includes manage_platform + manage_client + all read levels
├─ manage_platform → Includes manage_client + platform/client/self read levels
├─ manage_client   → Includes client/self read levels
├─ read_all       → System-wide read access
├─ read_platform  → Platform-wide read access (includes client/self)
├─ read_client    → Client organization read access (includes self)
└─ read_self      → Individual user access (default for all users)
```

## Role Structure

### Role Properties

```javascript
{
  "id": "507f1f77bcf86cd799439011",        // MongoDB ObjectId
  "name": "admin",                         // Simple role name
  "display_name": "Administrator",         // Human-readable name
  "description": "Full administrative access within the organization",
  "permissions": [                         // Hierarchical permission names
    "user:manage_client",                  // Includes user:read_client + user:read_self
    "group:manage_client",                 // Includes group:read_client
    "role:read_client"                     // Read roles in client scope
  ],
  "scope": "client",                       // "system" | "platform" | "client"
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Foreign key to scope owner
  "is_assignable_by_main_client": false,
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9"
}
```

### Scope Ownership

| Scope        | `scope_id` Points To | Example                      | Description                             |
| ------------ | -------------------- | ---------------------------- | --------------------------------------- |
| **system**   | `null`               | System-wide roles            | Available across all platforms/clients  |
| **platform** | `platform_id`        | `"real_estate_platform"`     | Platform that owns this role            |
| **client**   | `client_account_id`  | `"685a5f2e82e92ad29111a6a9"` | Client organization that owns this role |

## Hierarchical Permission System

### **Permission Hierarchy Levels**

Each resource (users, roles, groups, client accounts, permissions) follows the same four-tier hierarchy:

```python
# User Management Hierarchy
"user:manage_all"      # Global user management across all scopes
├─ "user:manage_platform"  # Manage users across platform clients
├─ "user:manage_client"    # Manage users within client organization
├─ "user:read_all"         # Read users system-wide
├─ "user:read_platform"    # Read users across platform clients
├─ "user:read_client"      # Read users within client organization
└─ "user:read_self"        # Read own profile (granted to all users)

# Role Management Hierarchy
"role:manage_all"      # Global role management
├─ "role:manage_platform"  # Manage roles across platform
├─ "role:manage_client"    # Manage roles within client
├─ "role:read_all"         # Read roles system-wide
├─ "role:read_platform"    # Read roles across platform
└─ "role:read_client"      # Read roles within client

# Group Management Hierarchy
"group:manage_all"     # Global group management
├─ "group:manage_platform" # Manage groups across platform
├─ "group:manage_client"   # Manage groups within client
├─ "group:read_all"        # Read groups system-wide
├─ "group:read_platform"   # Read groups across platform
└─ "group:read_client"     # Read groups within client

# Client Account Hierarchy
"client:manage_all"    # Global client account management
├─ "client:manage_platform" # Manage client accounts on platform
├─ "client:read_all"       # Read all client accounts
├─ "client:read_platform"  # Read client accounts on platform
└─ "client:read_own"       # View own client account (default)
```

### **Automatic Permission Inheritance**

The system implements intelligent permission inheritance:

1. **Manage includes Read**: `user:manage_client` automatically includes `user:read_client`
2. **Broader scopes include narrower**: `user:read_platform` automatically includes `user:read_client` and `user:read_self`
3. **Higher levels include lower**: `user:manage_all` includes all user permissions at every level

## Role Examples

### System Roles

```javascript
// Super Admin (system-wide access)
{
  "id": "507f1f77bcf86cd799439011",
  "name": "super_admin",
  "display_name": "Super Administrator",
  "description": "Complete system access",
  "scope": "system",
  "scope_id": null,
  "permissions": [
    "user:manage_all",      // Includes all user permissions
    "role:manage_all",      // Includes all role permissions
    "group:manage_all",     // Includes all group permissions
    "permission:manage_all", // Includes all permission permissions
    "client:manage_all",    // Includes all client permissions
    "platform:manage_all"   // Platform management
  ]
}

// Basic User (assignable by client admins)
{
  "id": "507f1f77bcf86cd799439012",
  "name": "basic_user",
  "display_name": "Basic User",
  "description": "Standard user with minimal permissions",
  "scope": "system",
  "scope_id": null,
  "is_assignable_by_main_client": true,
  "permissions": [
    "user:read_self",       // Read own profile (default)
    "user:update_self",     // Update own profile (default)
    "group:read_own",       // View own groups (default)
    "client:read_own"       // View own client (default)
  ]
}
```

### Client Roles

```javascript
// Client Admin (full client management)
{
  "id": "507f1f77bcf86cd799439013",
  "name": "admin",
  "display_name": "Administrator",
  "description": "Full administrative access within client organization",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Client account ID
  "permissions": [
    "user:manage_client",   // Manage users in client (includes read)
    "group:manage_client",  // Manage groups in client (includes read)
    "role:read_client",     // Read client roles
    "permission:read_client", // Read client permissions
    "user:add_member",      // Add team members
    "group:manage_members"  // Manage group membership
  ]
}

// Sales Manager (limited client management)
{
  "id": "507f1f77bcf86cd799439014",
  "name": "sales_manager",
  "display_name": "Sales Manager",
  "description": "Manages sales team and client relationships",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Same client
  "permissions": [
    "user:read_client",     // Read client users (includes self)
    "group:manage_client",  // Manage client groups (includes read)
    "user:add_member",      // Add new team members
    "group:manage_members"  // Manage group membership
  ]
}
```

### Platform Roles

```javascript
// Platform Admin (cross-client platform management)
{
  "id": "507f1f77bcf86cd799439015",
  "name": "platform_admin",
  "display_name": "Platform Administrator",
  "description": "Administrative access across all platform clients",
  "scope": "platform",
  "scope_id": "real_estate_platform",  // Platform ID
  "permissions": [
    "user:manage_platform", // Manage users across platform (includes all lower)
    "role:manage_all",      // Global role management
    "group:manage_all",     // Global group management
    "client:create",        // Create client accounts
    "client:manage_platform", // Manage platform clients
    "support:cross_client"  // Cross-client support
  ]
}

// Platform Support (cross-client support)
{
  "id": "507f1f77bcf86cd799439016",
  "name": "support",
  "display_name": "Support Agent",
  "description": "Customer support across platform clients",
  "scope": "platform",
  "scope_id": "real_estate_platform",  // Platform ID
  "permissions": [
    "user:read_platform",   // Read users across platform (includes client/self)
    "support:cross_client", // Cross-client support access
    "client:read_platform"  // Read client accounts (includes own)
  ]
}
```

## Permission Model

### Who Can Create Roles

| User Type          | Can Create        | Scope                            | Restrictions                 |
| ------------------ | ----------------- | -------------------------------- | ---------------------------- |
| **Super Admin**    | ✅ Any role       | `system`, `platform`, `client`   | No restrictions              |
| **Platform Admin** | ✅ Platform roles | `platform` (their platform only) | Only within their platform   |
| **Client Admin**   | ✅ Client roles   | `client` (their client only)     | Only within their client org |
| **Regular User**   | ❌ No roles       | -                                | Cannot create roles          |

### Who Can Assign Roles

| User Type          | Can Assign                         | Examples                               |
| ------------------ | ---------------------------------- | -------------------------------------- |
| **Super Admin**    | Any role to anyone                 | All system, platform, and client roles |
| **Platform Admin** | Platform + assignable system roles | Platform roles + `basic_user`          |
| **Client Admin**   | Client + assignable system roles   | Client roles + `basic_user`            |

### Role Visibility (Using Hierarchical Permissions)

| User Type          | Can View                          | Permission Required  |
| ------------------ | --------------------------------- | -------------------- |
| **Super Admin**    | All roles across all scopes       | `role:read_all`      |
| **Platform Admin** | System + platform roles           | `role:read_platform` |
| **Client Admin**   | System + client roles             | `role:read_client`   |
| **Regular User**   | System + client roles (read-only) | `role:read_client`   |

## Usage Patterns

### 1. Creating a Client Organization

When a new client organization is created:

```python
# 1. Create client account
client_account = await client_service.create_client_account(...)

# 2. Create client admin role with hierarchical permissions
admin_role_data = RoleCreateSchema(
    name="admin",
    display_name="Administrator",
    description="Full administrative access within the organization",
    permissions=[
        "user:manage_client",   # Hierarchical: includes user:read_client + user:read_self
        "group:manage_client",  # Hierarchical: includes group:read_client
        "role:read_client",     # Read client roles
        "permission:read_client", # Read client permissions
        "user:add_member",      # Add team members
        "group:manage_members"  # Manage group membership
    ],
    scope=RoleScope.CLIENT
)

admin_role = await role_service.create_role(
    role_data=admin_role_data,
    current_user_id=super_admin_id,
    current_client_id=None,
    scope_id=client_account.id  # Client account ID
)

# 3. Create admin user with the role
admin_user = await user_service.create_user(
    user_data=UserCreateSchema(...),
    roles=[str(admin_role.id)]  # Use MongoDB ObjectId
)
```

### 2. Client Admin Creating Team Roles

A client admin can create custom roles for their organization:

```python
# Create a sales representative role with hierarchical permissions
sales_role_data = RoleCreateSchema(
    name="sales_rep",
    display_name="Sales Representative",
    description="Access to sales tools and client management",
    permissions=[
        "user:read_client",     # Hierarchical: includes user:read_self
        "group:read_client",    # Read client groups
        "user:add_member",      # Add new team members
        "group:manage_members"  # Manage group membership
    ],
    scope=RoleScope.CLIENT
)

sales_role = await role_service.create_role(
    role_data=sales_role_data,
    current_user_id=client_admin_id,
    current_client_id=client_admin.client_account_id
    # scope_id automatically set to client_admin.client_account_id
)
```

### 3. Platform Admin Creating Platform Roles

Platform administrators can create roles for their platform:

```python
# Create platform support role with hierarchical permissions
support_role_data = RoleCreateSchema(
    name="support",
    display_name="Support Representative",
    description="Customer support access across all platform clients",
    permissions=[
        "user:read_platform",   # Hierarchical: includes user:read_client + user:read_self
        "support:cross_client", # Cross-client support access
        "client:read_platform"  # Hierarchical: includes client:read_own
    ],
    scope=RoleScope.PLATFORM
)

support_role = await role_service.create_role(
    role_data=support_role_data,
    current_user_id=platform_admin_id,
    current_client_id=None,
    scope_id="real_estate_platform"  # Platform ID
)
```

## Integration with Dependencies

### Named Dependencies Using Hierarchical Permissions

The dependency system uses hierarchical permissions for clean access control:

```python
# User Management Dependencies
can_read_users = require_permissions(any_of=["user:read_all", "user:read_platform", "user:read_client"])
can_manage_users = require_permissions(any_of=["user:manage_all", "user:manage_platform", "user:manage_client"])

# Role Management Dependencies
can_read_roles = require_permissions(any_of=["role:read_all", "role:read_platform", "role:read_client"])
can_manage_roles = require_permissions(any_of=["role:manage_all", "role:manage_platform", "role:manage_client"])

# Route Usage Example
@router.get("/", response_model=List[RoleResponseSchema])
async def get_all_roles(
    current_user: UserModel = Depends(can_read_roles),  # Hierarchical permission check
    skip: int = 0, limit: int = 100
):
    roles = await role_service.get_roles(current_user=current_user, skip=skip, limit=limit)
    return [await role_service.role_to_response_schema(role) for role in roles]
```

### Automatic Data Scoping

The service layer automatically handles data scoping based on user permissions:

```python
async def get_roles(self, current_user: UserModel, skip: int = 0, limit: int = 100) -> List[RoleModel]:
    """
    Get roles with automatic scoping based on user's hierarchical permissions.
    """
    user_permissions = await get_user_effective_permissions(current_user.id)

    if "role:read_all" in user_permissions:
        # Super admin - see all roles
        return await RoleModel.find().skip(skip).limit(limit).to_list()
    elif "role:read_platform" in user_permissions:
        # Platform admin - see system + platform roles
        return await RoleModel.find({
            "$or": [
                {"scope": "system"},
                {"scope": "platform", "scope_id": current_user.platform_id}
            ]
        }).skip(skip).limit(limit).to_list()
    elif "role:read_client" in user_permissions:
        # Client admin - see system + client roles
        return await RoleModel.find({
            "$or": [
                {"scope": "system"},
                {"scope": "client", "scope_id": current_user.client_account_id}
            ]
        }).skip(skip).limit(limit).to_list()
    else:
        # No role read permissions
        return []
```

## Frontend Integration

### Role Creation UI

The frontend provides a clean interface with hierarchical permission selection:

```javascript
// Frontend form data
{
  name: "manager",              // Simple name
  display_name: "Team Manager", // User-friendly name
  description: "Manages team members and projects",
  permissions: [
    "user:read_client",         // Hierarchical: includes user:read_self
    "group:manage_client",      // Hierarchical: includes group:read_client
    "user:add_member",          // Add team members
    "group:manage_members"      // Manage group membership
  ],
  scope: "client"              // User selects scope level
}

// Backend creates role with proper scope_id automatically
```

### Available Roles API

Use the `/roles/available` endpoint to get roles a user can assign:

```javascript
// GET /roles/available
{
  "system_roles": [
    {
      "id": "507f1f77bcf86cd799439012",
      "name": "basic_user",
      "display_name": "Basic User",
      "scope": "system",
      "scope_id": null,
      "permissions": [
        {"name": "user:read_self", "display_name": "Read Own Profile"},
        {"name": "client:read_own", "display_name": "View Own Client"}
      ]
    }
  ],
  "platform_roles": [],
  "client_roles": [
    {
      "id": "507f1f77bcf86cd799439013",
      "name": "admin",
      "display_name": "Administrator",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "permissions": [
        {"name": "user:manage_client", "display_name": "Manage Client Users"},
        {"name": "group:manage_client", "display_name": "Manage Client Groups"}
      ]
    }
  ]
}
```

## Security Features

### Namespace Isolation + Hierarchical Security

- **No role collisions**: Roles are isolated by scope + scope_id
- **Tenant isolation**: Client A's "admin" role is completely separate from Client B's "admin" role
- **Permission inheritance**: Higher-level permissions automatically include lower levels
- **Automatic scoping**: Service layer filters data based on user's permission hierarchy

### Unique Constraints

- **Name uniqueness**: Role names must be unique within their scope (name + scope + scope_id)
- **Proper isolation**: Same role name can exist in different scopes without conflict
- **Permission validation**: Only valid hierarchical permissions can be assigned

### Validation

- **Scope validation**: Users can only create roles in scopes they have permission for
- **Permission checks**: Users can only create/assign roles they have permission for
- **Hierarchical validation**: Permission inheritance is automatically validated

## Database Queries

### Efficient Role Lookups

```python
# Get all client roles for a specific client
client_roles = await RoleModel.find(
    RoleModel.scope == RoleScope.CLIENT,
    RoleModel.scope_id == client_id,
    fetch_links=True  # Fetch permission details
).to_list()

# Get system roles assignable by client admins
assignable_system_roles = await RoleModel.find(
    RoleModel.scope == RoleScope.SYSTEM,
    RoleModel.is_assignable_by_main_client == True,
    fetch_links=True
).to_list()

# Check if role name exists in scope
existing_role = await RoleModel.find_one(
    RoleModel.name == "admin",
    RoleModel.scope == RoleScope.CLIENT,
    RoleModel.scope_id == client_id
)
```

## Best Practices

### 1. Role Design with Hierarchical Permissions

- **Use hierarchical permissions**: Prefer `user:manage_client` over multiple individual permissions
- **Leverage inheritance**: `user:manage_client` automatically includes `user:read_client` and `user:read_self`
- **Scope appropriately**: Use the narrowest scope that meets requirements

### 2. Permission Assignment Strategy

- **Start with higher-level permissions**: `user:manage_client` is better than listing all individual permissions
- **Use named dependencies**: `can_manage_users` is cleaner than manual permission checks
- **Follow hierarchy**: Respect the `all > platform > client > self` hierarchy

### 3. Scope Design

- **System roles**: Only for truly global roles or commonly assignable ones (`basic_user`)
- **Platform roles**: For cross-client platform functionality (`platform_support`)
- **Client roles**: For organization-specific roles and permissions (`client_admin`, `sales_manager`)

### 4. Frontend UX

- **Group by scope**: Show roles organized by their scope
- **Show permission hierarchy**: Display inherited permissions clearly
- **Simple creation**: Let users focus on role name/permissions, handle scoping in backend

## API Endpoints

| Endpoint                  | Purpose              | Permissions Required | Example                                         |
| ------------------------- | -------------------- | -------------------- | ----------------------------------------------- |
| `POST /roles/`            | Create role          | `role:manage_*`      | Creates role in specified scope                 |
| `GET /roles/`             | List roles           | `role:read_*`        | Returns roles visible to user with auto-scoping |
| `GET /roles/available`    | Get assignable roles | `role:read_*`        | Returns roles user can assign, grouped by scope |
| `GET /roles/{role_id}`    | Get specific role    | `role:read_*`        | Returns role details if user can view           |
| `PUT /roles/{role_id}`    | Update role          | `role:manage_*`      | Updates role if user can manage                 |
| `DELETE /roles/{role_id}` | Delete role          | `role:manage_*`      | Deletes role if user can manage                 |

## Complete Example

### Client Setup with Hierarchical Permissions

```python
# 1. Super admin creates new client
client_data = ClientAccountCreateSchema(
    organization_name="Acme Corporation",
    contact_email="admin@acme.com"
)
client = await client_service.create_client_account(client_data)

# 2. Create client admin role with hierarchical permissions
admin_role_data = RoleCreateSchema(
    name="admin",
    display_name="Administrator",
    description="Full administrative access within Acme Corporation",
    permissions=[
        "user:manage_client",   # Hierarchical: includes user:read_client + user:read_self
        "group:manage_client",  # Hierarchical: includes group:read_client
        "role:read_client",     # Read client roles
        "permission:read_client", # Read client permissions
        "user:add_member",      # Add team members
        "group:manage_members"  # Manage group membership
    ],
    scope=RoleScope.CLIENT
)

admin_role = await role_service.create_role(
    role_data=admin_role_data,
    current_user_id=super_admin_id,
    scope_id=client.id
)

# 3. Create client admin user
admin_user_data = UserCreateSchema(
    email="admin@acme.com",
    password="secure_password",
    first_name="Admin",
    last_name="User",
    roles=[str(admin_role.id)],  # MongoDB ObjectId as string
    client_account_id=client.id
)
admin_user = await user_service.create_user(admin_user_data)

# 4. Client admin can now create additional roles with hierarchical permissions
manager_role_data = RoleCreateSchema(
    name="manager",
    display_name="Team Manager",
    description="Manages team members and projects",
    permissions=[
        "user:read_client",     # Hierarchical: includes user:read_self
        "group:read_client",    # Read client groups
        "user:add_member",      # Add new team members
        "group:manage_members"  # Manage group membership
    ],
    scope=RoleScope.CLIENT
)

manager_role = await role_service.create_role(
    role_data=manager_role_data,
    current_user_id=admin_user.id,
    current_client_id=admin_user.client_account_id
    # Automatically scoped to their client
)
```

This creates a complete, isolated client environment with proper role hierarchy and hierarchical permissions using clean MongoDB ObjectIds and scope-based isolation with intelligent permission inheritance.
