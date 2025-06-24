# Role System Documentation

## Overview

The OutlabsAuth system implements a **three-tier scoped role architecture** that provides flexible, secure, and scalable role-based access control (RBAC) across multiple organizational levels using clean MongoDB ObjectIds and scope fields for tenant isolation.

## Architecture

### Three-Tier Hierarchy

```
SYSTEM ROLES (Global)
├─ super_admin          # Complete system access
├─ basic_user          # Minimal system access

PLATFORM ROLES (Per Platform)
├─ admin               # Platform admin
├─ support            # Platform support
└─ sales              # Platform sales

CLIENT ROLES (Per Client Organization)
├─ admin              # Client admin
├─ manager            # Client manager
├─ user               # Client user
└─ sales_rep          # Client sales rep
```

## Role Structure

### Role Properties

```javascript
{
  "id": "507f1f77bcf86cd799439011",        // MongoDB ObjectId
  "name": "admin",                         // Simple role name
  "display_name": "Administrator",         // Human-readable name
  "description": "Full administrative access within the organization",
  "permissions": ["user:create", "user:read", "user:update", ...],
  "scope": "client",                       // "system" | "platform" | "client"
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Foreign key to owner
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
  "permissions": ["*"]  // All permissions
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
  "permissions": ["user:read"]
}
```

### Client Roles

```javascript
// Client Admin (for Qdarte)
{
  "id": "507f1f77bcf86cd799439013",
  "name": "admin",
  "display_name": "Administrator",
  "description": "Full administrative access within Qdarte",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Qdarte's client_account_id
  "permissions": ["user:create", "user:read", "user:update", "user:delete", ...]
}

// Sales Rep (for Qdarte)
{
  "id": "507f1f77bcf86cd799439014",
  "name": "sales_rep",
  "display_name": "Sales Representative",
  "description": "Access to CRM and sales tools",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Same client
  "permissions": ["crm:clients:read", "crm:records:create", ...]
}
```

### Platform Roles

```javascript
// Platform Support
{
  "id": "507f1f77bcf86cd799439015",
  "name": "support",
  "display_name": "Support Agent",
  "description": "Customer support across platform clients",
  "scope": "platform",
  "scope_id": "real_estate_platform",  // Platform ID
  "permissions": ["support:tickets:read", "user:read", "client_account:read"]
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

### Role Visibility

| User Type          | Can View                                      |
| ------------------ | --------------------------------------------- |
| **Super Admin**    | All roles across all scopes                   |
| **Platform Admin** | System roles + their platform roles           |
| **Client Admin**   | System roles + their client roles             |
| **Regular User**   | System roles + their client roles (read-only) |

## Usage Patterns

### 1. Creating a Client Organization

When a new client organization is created:

```python
# 1. Create client account
client_account = await client_service.create_client_account(...)

# 2. Create client admin role
admin_role_data = RoleCreateSchema(
    name="admin",
    display_name="Administrator",
    description="Full administrative access within the organization",
    permissions=["user:create", "user:read", "user:update", "group:create", ...],
    scope=RoleScope.CLIENT
)

admin_role = await role_service.create_role(
    role_data=admin_role_data,
    current_user_id=super_admin_id,
    current_client_id=None,
    scope_id=client_account.id  # Client account ID
)
# Results in role with scope="client", scope_id=client_account.id

# 3. Create admin user with the role
admin_user = await user_service.create_user(
    user_data=UserCreateSchema(...),
    roles=[str(admin_role.id)]  # Use MongoDB ObjectId
)
```

### 2. Client Admin Creating Team Roles

A client admin can create custom roles for their organization:

```python
# Create a sales representative role
sales_role_data = RoleCreateSchema(
    name="sales_rep",
    display_name="Sales Representative",
    description="Access to sales tools and client management",
    permissions=["crm:clients:read", "crm:clients:update", "crm:records:create"],
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
# Create platform support role
support_role_data = RoleCreateSchema(
    name="support",
    display_name="Support Representative",
    description="Customer support access across all platform clients",
    permissions=["support:tickets:read", "user:read", "client_account:read"],
    scope=RoleScope.PLATFORM
)

support_role = await role_service.create_role(
    role_data=support_role_data,
    current_user_id=platform_admin_id,
    current_client_id=None,
    scope_id="real_estate_platform"  # Platform ID
)
```

## Frontend Integration

### Role Creation UI

The frontend provides a clean interface:

```javascript
// Frontend form data
{
  name: "manager",              // Simple name
  display_name: "Team Manager", // User-friendly name
  description: "Manages team members and projects",
  permissions: ["user:read", "user:update", "group:manage_members"],
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
      "scope_id": null
    }
  ],
  "platform_roles": [],
  "client_roles": [
    {
      "id": "507f1f77bcf86cd799439013",
      "name": "admin",
      "display_name": "Administrator",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
    },
    {
      "id": "507f1f77bcf86cd799439014",
      "name": "manager",
      "display_name": "Team Manager",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
    }
  ]
}
```

## Security Features

### Namespace Isolation

- **No role collisions**: Roles are isolated by scope + scope_id
- **Tenant isolation**: Client A's "admin" role is completely separate from Client B's "admin" role
- **Clear boundaries**: Platform roles cannot access client data without explicit permissions

### Unique Constraints

- **Name uniqueness**: Role names must be unique within their scope (name + scope + scope_id)
- **Proper isolation**: Same role name can exist in different scopes without conflict

### Validation

- **Scope validation**: Users can only create roles in scopes they have permission for
- **Permission checks**: Users can only create/assign roles they have permission for
- **Context awareness**: Backend automatically determines appropriate scope based on user context

## Database Queries

### Efficient Role Lookups

```python
# Get all client roles for a specific client
client_roles = await RoleModel.find(
    RoleModel.scope == RoleScope.CLIENT,
    RoleModel.scope_id == client_id
).to_list()

# Get system roles assignable by client admins
assignable_system_roles = await RoleModel.find(
    RoleModel.scope == RoleScope.SYSTEM,
    RoleModel.is_assignable_by_main_client == True
).to_list()

# Check if role name exists in scope
existing_role = await RoleModel.find_one(
    RoleModel.name == "admin",
    RoleModel.scope == RoleScope.CLIENT,
    RoleModel.scope_id == client_id
)
```

## Best Practices

### 1. Role Naming

- **Keep role names simple**: `"admin"`, `"manager"`, `"user"`
- **Use descriptive display names**: `"Administrator"`, `"Team Manager"`, `"End User"`
- **Consistent naming**: Use same role names across different scopes for similar functions

### 2. Permission Assignment

- **Principle of least privilege**: Only assign necessary permissions
- **Use permission groups**: Group related permissions logically
- **Regular audits**: Review role permissions periodically

### 3. Scope Design

- **System roles**: Only for truly global roles or commonly assignable ones
- **Platform roles**: For cross-client platform functionality
- **Client roles**: For organization-specific roles and permissions

### 4. Frontend UX

- **Group by scope**: Show roles organized by their scope
- **Clear context**: Display scope information clearly in UI
- **Simple creation**: Let users focus on role name/permissions, handle scoping in backend

## API Endpoints

| Endpoint                  | Purpose              | Example                                         |
| ------------------------- | -------------------- | ----------------------------------------------- |
| `POST /roles/`            | Create role          | Creates role in specified scope                 |
| `GET /roles/`             | List roles           | Returns roles visible to user                   |
| `GET /roles/available`    | Get assignable roles | Returns roles user can assign, grouped by scope |
| `GET /roles/{role_id}`    | Get specific role    | Returns role details if user can view           |
| `PUT /roles/{role_id}`    | Update role          | Updates role if user can manage                 |
| `DELETE /roles/{role_id}` | Delete role          | Deletes role if user can manage                 |

## Complete Example

### Client Setup with Roles

```python
# 1. Super admin creates new client
client_data = ClientAccountCreateSchema(
    organization_name="Acme Corporation",
    contact_email="admin@acme.com"
)
client = await client_service.create_client_account(client_data)

# 2. Create client admin role
admin_role_data = RoleCreateSchema(
    name="admin",
    display_name="Administrator",
    description="Full administrative access within Acme Corporation",
    permissions=["user:create", "user:read", "user:update", "user:delete",
                "group:create", "group:read", "group:update", "group:delete",
                "role:create", "role:read", "role:update", "role:delete"],
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

# 4. Client admin can now create additional roles
manager_role_data = RoleCreateSchema(
    name="manager",
    display_name="Team Manager",
    description="Manages team members and projects",
    permissions=["user:read", "user:update", "group:read", "group:manage_members"],
    scope=RoleScope.CLIENT
)

manager_role = await role_service.create_role(
    role_data=manager_role_data,
    current_user_id=admin_user.id,
    current_client_id=admin_user.client_account_id
    # Automatically scoped to their client
)
```

This creates a complete, isolated client environment with proper role hierarchy and permissions using clean MongoDB ObjectIds and scope-based isolation.
