# Permission System Documentation

## Overview

The OutlabsAuth system implements a **three-tier scoped permission architecture** that provides granular, secure, and scalable access control across multiple organizational levels. Permissions are the foundational building blocks that define what actions users can perform, serving as the atomic units of authorization that are assigned through both roles and groups using clean MongoDB ObjectIds and scope fields for tenant isolation.

### Key Architectural Decision

**Clean Names + Scope Fields**: Permissions use clean, descriptive names (e.g., `"user:create"`, `"listings:manage"`) combined with `scope` and `scope_id` fields for tenant isolation. This approach provides:

- ✅ **Consistency** with roles and groups (all use the same naming pattern)
- ✅ **Reusability** across different scopes without name conflicts
- ✅ **Clean API** - no scope prefixes cluttering permission names
- ✅ **Proper normalization** - scope information in dedicated fields

Roles and groups reference permissions by **ObjectId**, not name, ensuring referential integrity while the permission resolution system converts IDs back to clean names for authorization checks.

## Architecture

### Three-Tier Hierarchy

```
SYSTEM PERMISSIONS (Global - scope: "system", scope_id: null)
├─ user:create              # Create users across any scope
├─ platform:create          # Create new platforms
├─ infrastructure:manage    # Manage core infrastructure
└─ admin:*                 # All system capabilities

PLATFORM PERMISSIONS (Per Platform - scope: "platform", scope_id: platform_id)
├─ analytics:view           # Platform-wide analytics
├─ billing:manage           # Platform billing management
├─ client_account:create    # Create client accounts
└─ support:cross_client     # Cross-client support

CLIENT PERMISSIONS (Per Client Organization - scope: "client", scope_id: client_account_id)
├─ listings:create          # Create property listings
├─ users:manage             # Manage client users
├─ reports:view             # View client reports
└─ settings:update          # Update client settings
```

## Permission vs Role vs Group Relationship

### Foundation Layer

```javascript
// Permissions are the atomic units (clean names + scope isolation)
permission_examples = [
  { name: "user:create", scope: "system", scope_id: null },
  { name: "listings:read", scope: "client", scope_id: "client123" },
  { name: "reports:generate", scope: "client", scope_id: "client123" },
  { name: "billing:view", scope: "platform", scope_id: "platform456" },
];

// Roles package permissions by ID (not name) for user types
role_example = {
  name: "sales_manager",
  scope: "client",
  scope_id: "client123",
  permissions: ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"], // Permission ObjectIds
};

// Groups package permissions by ID (not name) for teams
group_example = {
  name: "sales_team",
  scope: "client",
  scope_id: "client123",
  permissions: ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439013"], // Permission ObjectIds
};

// Users get permissions from both sources (resolved to permission names for checking)
user_effective_permissions = [
  "user:create",
  "listings:read",
  "listings:update",
  "reports:view", // Resolved names
];
```

### Permission Flow

```
PERMISSIONS (atomic units)
    ↓
ROLES (user identity packages) + GROUPS (team packages)
    ↓
USERS (effective permissions = roles + groups)
```

## Permission Structure

### Permission Properties

```javascript
{
  "id": "507f1f77bcf86cd799439011",        // MongoDB ObjectId
  "name": "listings:create",               // Clean action identifier (no scope prefix)
  "display_name": "Create Listings",       // Human-readable name
  "description": "Allows creating new property listings",
  "scope": "client",                       // "system" | "platform" | "client"
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Foreign key to owner (tenant isolation)
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Scope Ownership

| Scope        | `scope_id` Points To | Example                      | Description                              |
| ------------ | -------------------- | ---------------------------- | ---------------------------------------- |
| **system**   | `null`               | Core auth permissions        | Available across all platforms/clients   |
| **platform** | `platform_id`        | `"real_estate_platform"`     | Platform that owns this permission       |
| **client**   | `client_account_id`  | `"685a5f2e82e92ad29111a6a9"` | Client organization that owns permission |

### Permission Naming Conventions

| Pattern                   | Example                  | Description                    |
| ------------------------- | ------------------------ | ------------------------------ |
| `resource:action`         | `user:create`            | Basic resource-action pattern  |
| `service:resource:action` | `billing:invoice:read`   | Service-specific permissions   |
| `resource:sub:action`     | `listings:photos:upload` | Nested resource permissions    |
| `wildcard:*`              | `admin:*`                | Wildcard for broad permissions |

**Note**: Scope isolation is handled via the `scope` and `scope_id` fields, not name prefixes. This keeps permission names clean and reusable across different scopes.

## Permission Examples

### System Permissions

```javascript
// Core Authentication
{
  "id": "507f1f77bcf86cd799439011",
  "name": "user:create",
  "display_name": "Create Users",
  "description": "Create users in any scope",
  "scope": "system",
  "scope_id": null
}

// Platform Management
{
  "id": "507f1f77bcf86cd799439012",
  "name": "platform:create",
  "display_name": "Create Platforms",
  "description": "Create new platform instances",
  "scope": "system",
  "scope_id": null
}

// Infrastructure Access
{
  "id": "507f1f77bcf86cd799439013",
  "name": "infrastructure:manage",
  "display_name": "Manage Infrastructure",
  "description": "Full infrastructure management access",
  "scope": "system",
  "scope_id": null
}

// Admin Wildcard
{
  "id": "507f1f77bcf86cd799439014",
  "name": "admin:*",
  "display_name": "Admin All Access",
  "description": "Complete system access",
  "scope": "system",
  "scope_id": null
}
```

### Platform Permissions

```javascript
// Platform Analytics
{
  "id": "507f1f77bcf86cd799439015",
  "name": "analytics:view",
  "display_name": "View Platform Analytics",
  "description": "Access platform-wide analytics and reports",
  "scope": "platform",
  "scope_id": "real_estate_platform"
}

// Client Account Management
{
  "id": "507f1f77bcf86cd799439016",
  "name": "client_account:create",
  "display_name": "Create Client Accounts",
  "description": "Create new client organizations on this platform",
  "scope": "platform",
  "scope_id": "real_estate_platform"
}

// Cross-Client Support
{
  "id": "507f1f77bcf86cd799439017",
  "name": "support:cross_client",
  "display_name": "Support All Clients",
  "description": "Provide support across all platform clients",
  "scope": "platform",
  "scope_id": "real_estate_platform"
}

// Platform Configuration
{
  "id": "507f1f77bcf86cd799439018",
  "name": "settings:manage",
  "display_name": "Manage Platform Settings",
  "description": "Configure platform-wide settings and features",
  "scope": "platform",
  "scope_id": "real_estate_platform"
}
```

### Client Permissions

```javascript
// Listing Management (Real Estate)
{
  "id": "507f1f77bcf86cd799439019",
  "name": "listings:create",
  "display_name": "Create Listings",
  "description": "Create new property listings",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9"  // Acme Real Estate
}

// Client User Management
{
  "id": "507f1f77bcf86cd799439020",
  "name": "users:manage",
  "display_name": "Manage Client Users",
  "description": "Manage users within the client organization",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9"
}

// Lead Management (Lead Gen Company)
{
  "id": "507f1f77bcf86cd799439021",
  "name": "leads:assign",
  "display_name": "Assign Leads",
  "description": "Assign leads to sales representatives",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9"
}

// Custom Business Logic
{
  "id": "507f1f77bcf86cd799439022",
  "name": "contracts:esign",
  "display_name": "E-Sign Contracts",
  "description": "Electronically sign client contracts",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9"
}
```

## Permission Model

### Who Can Create Permissions

| User Type          | Can Create        | Scope                            | Restrictions                 |
| ------------------ | ----------------- | -------------------------------- | ---------------------------- |
| **Super Admin**    | ✅ Any permission | `system`, `platform`, `client`   | No restrictions              |
| **Platform Admin** | ✅ Platform perms | `platform` (their platform only) | Only within their platform   |
| **Client Admin**   | ✅ Client perms   | `client` (their client only)     | Only within their client org |
| **Regular User**   | ❌ No permissions | -                                | Cannot create permissions    |

### Permission Assignment

| User Type          | Can Assign Permissions Through    | Examples                               |
| ------------------ | --------------------------------- | -------------------------------------- |
| **Super Admin**    | Any role or group                 | All system, platform, and client perms |
| **Platform Admin** | Platform roles/groups             | Platform permissions only              |
| **Client Admin**   | Client roles/groups               | Client permissions only                |
| **Team Lead**      | Client groups (if granted access) | Limited client permissions             |

### Permission Visibility

| User Type          | Can View                                        |
| ------------------ | ----------------------------------------------- |
| **Super Admin**    | All permissions across all scopes               |
| **Platform Admin** | System permissions + their platform permissions |
| **Client Admin**   | System permissions + their client permissions   |
| **Regular User**   | Permissions they have (read-only)               |

## Usage Patterns

### 1. Creating Business-Specific Permissions

When a client needs custom permissions for their business:

```python
# Real estate client creating listing permissions
listing_create_permission = PermissionCreateSchema(
    name="listings:create",
    display_name="Create Property Listings",
    description="Create new property listings in the MLS system",
    scope=PermissionScope.CLIENT
)

permission = await permission_service.create_permission(
    permission_data=listing_create_permission,
    current_user_id=client_admin_id,
    current_client_id=client_admin.client_account_id
    # scope_id automatically set to client_admin.client_account_id
)

# Add to sales role (uses permission ID, not name)
sales_role.permissions.append(str(permission.id))
await role_service.update_role(sales_role.id, sales_role)
```

### 2. Platform Feature Permissions

Platform administrators creating permissions for new features:

```python
# New analytics feature permission
analytics_permission = PermissionCreateSchema(
    name="analytics:advanced",
    display_name="Advanced Analytics",
    description="Access to advanced analytics dashboards and reports",
    scope=PermissionScope.PLATFORM
)

permission = await permission_service.create_permission(
    permission_data=analytics_permission,
    current_user_id=platform_admin_id,
    current_client_id=None,
    scope_id="real_estate_platform"
)

# Add to platform analytics group (uses permission ID, not name)
analytics_group.permissions.append(str(permission.id))
await group_service.update_group(analytics_group.id, analytics_group)
```

### 3. System-Level Operational Permissions

Super admins creating permissions for system operations:

```python
# Infrastructure monitoring permission
monitoring_permission = PermissionCreateSchema(
    name="monitoring:infrastructure",
    display_name="Monitor Infrastructure",
    description="Monitor system infrastructure and performance metrics",
    scope=PermissionScope.SYSTEM
)

permission = await permission_service.create_permission(
    permission_data=monitoring_permission,
    current_user_id=super_admin_id,
    current_client_id=None
    # scope_id automatically null for system permissions
)

# Add to engineering group (uses permission ID, not name)
engineering_group.permissions.append(str(permission.id))
await group_service.update_group(engineering_group.id, engineering_group)
```

## Permission Aggregation

### Multi-Source Permission Calculation

Users receive permissions from multiple sources:

```python
# User effective permissions calculation
async def get_user_effective_permissions(user_id):
    user = await UserModel.get(user_id)

    # 1. Get permission IDs from roles
    permission_ids = set()
    for role_id in user.roles:
        role = await RoleModel.get(role_id)
        permission_ids.update(role.permissions)  # Permission ObjectIds

    # 2. Get permission IDs from groups
    user_groups = await GroupModel.find(
        In(GroupModel.id, user.groups)
    ).to_list()
    for group in user_groups:
        permission_ids.update(group.permissions)  # Permission ObjectIds

    # 3. Resolve permission IDs to permission names
    permission_names = set()
    for permission_id in permission_ids:
        permission = await PermissionModel.get(permission_id)
        if permission:
            permission_names.add(permission.name)

    # 4. Return permission names for checking
    return permission_names
```

### Real-World Permission Flow

```javascript
// Sarah - Sales Manager + Project Alpha Team Member
{
  "user": {
    "id": "507f1f77bcf86cd799439020",
    "email": "sarah@acme.com",
    "roles": ["685ad307d90302d2b653199a"],           // Role ObjectId
    "groups": ["685ad307d90302d2b653199b", "685ad307d90302d2b653199c"] // Group ObjectIds
  },

  "permission_sources": {
    "from_sales_manager_role": {
      "permission_ids": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"],
      "resolved_names": ["user:read", "user:update", "reports:view"]
    },
    "from_sales_team_group": {
      "permission_ids": ["507f1f77bcf86cd799439019", "507f1f77bcf86cd799439020"],
      "resolved_names": ["listings:create", "listings:update", "clients:manage"]
    },
    "from_project_alpha_group": {
      "permission_ids": ["507f1f77bcf86cd799439021", "507f1f77bcf86cd799439022"],
      "resolved_names": ["project:alpha:read", "project:alpha:update", "documents:alpha:manage"]
    }
  },

  "effective_permissions": [
    "user:read", "user:update", "reports:view",
    "listings:create", "listings:update", "clients:manage",
    "project:alpha:read", "project:alpha:update", "documents:alpha:manage"
  ]
}
```

## Frontend Integration

### Permission Creation UI

The frontend provides intuitive permission management:

```javascript
// Frontend form data for permission creation
{
  name: "campaigns:create",
  display_name: "Create Marketing Campaigns",
  description: "Create and launch marketing campaigns for client",
  scope: "client"  // User selects scope level
}

// Backend creates permission with proper scope_id automatically
// Clean name + scope fields provide proper isolation
```

### Available Permissions API

Use the `/permissions/available` endpoint to get permissions a user can assign:

```javascript
// GET /permissions/available
{
  "system_permissions": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "user:read",
      "display_name": "Read Users",
      "scope": "system",
      "scope_id": null
    }
  ],
  "platform_permissions": [
    {
      "id": "507f1f77bcf86cd799439015",
      "name": "analytics:view",
      "display_name": "View Platform Analytics",
      "scope": "platform",
      "scope_id": "real_estate_platform"
    }
  ],
  "client_permissions": [
    {
      "id": "507f1f77bcf86cd799439019",
      "name": "listings:create",
      "display_name": "Create Listings",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "name": "leads:assign",
      "display_name": "Assign Leads",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
    }
  ]
}
```

### Permission Checker Integration

Frontend components can check permissions:

```javascript
// Frontend permission checking (uses resolved permission names)
const userPermissions = userStore.effectivePermissions;

const canCreateListings = userPermissions.includes("listings:create");
const canViewAnalytics = userPermissions.includes("analytics:view");
const canManageUsers = userPermissions.includes("user:create");

// Conditional UI rendering
{
  canCreateListings && <CreateListingButton />;
}
{
  canViewAnalytics && <AnalyticsDashboard />;
}
{
  canManageUsers && <UserManagementPanel />;
}
```

## Security Features

### Namespace Isolation

- **No permission collisions**: Permissions are isolated by scope + scope_id
- **Tenant isolation**: Client A's "listings:create" is separate from Client B's "listings:create"
- **Clear boundaries**: Platform permissions cannot access client data without explicit scoping

### Permission Validation

- **Naming validation**: Permissions must follow naming conventions
- **Scope validation**: Permissions must be appropriate for their scope
- **Uniqueness enforcement**: No duplicate permissions within scope + scope_id
- **Assignment validation**: Users can only assign permissions they have access to

### Unique Constraints

- **Name uniqueness**: Permission names must be unique within their scope (name + scope + scope_id)
- **Proper isolation**: Same permission name can exist in different scopes without conflict

### Wildcard Handling

```python
# Wildcard permission checking
def has_permission(user_permissions, required_permission):
    # Direct permission match
    if required_permission in user_permissions:
        return True

    # Check for wildcard permissions
    for permission in user_permissions:
        if permission.endswith(":*"):
            prefix = permission[:-1]  # Remove "*"
            if required_permission.startswith(prefix):
                return True

    return False

# Example usage
user_permissions = ["admin:*", "user:read"]
has_permission(user_permissions, "admin:settings:update")  # True (wildcard match)
has_permission(user_permissions, "user:read")             # True (direct match)
has_permission(user_permissions, "billing:view")          # False (no match)
```

## Database Queries

### Efficient Permission Lookups

```python
# Get all client permissions for a specific client
client_permissions = await PermissionModel.find(
    PermissionModel.scope == PermissionScope.CLIENT,
    PermissionModel.scope_id == client_id
).to_list()

# Get user's effective permissions (from roles and groups)
user_effective_permissions = await user_service.get_user_effective_permissions(user_id)

# Check if permission name exists in scope
existing_permission = await PermissionModel.find_one(
    PermissionModel.name == "listings:create",
    PermissionModel.scope == PermissionScope.CLIENT,
    PermissionModel.scope_id == client_id
)

# Get available permissions for role/group assignment
available_permissions = await permission_service.get_available_permissions_for_user(
    current_user_client_id=client_id,
    current_user_platform_id=platform_id,
    is_super_admin=False,
    is_platform_admin=False
)
```

## Best Practices

### 1. Permission Naming

- **Clear action verbs**: `create`, `read`, `update`, `delete`, `manage`, `view`
- **Logical hierarchy**: `resource:action` or `service:resource:action`
- **Consistent patterns**: Use same conventions across all scopes
- **Avoid ambiguity**: `user:read` not `user:see` or `user:view`

### 2. Scope Design

- **System permissions**: Only for truly global capabilities
- **Platform permissions**: For cross-client platform features
- **Client permissions**: For organization-specific business logic
- **Avoid scope creep**: Don't make client permissions when platform would suffice

### 3. Granularity Balance

- **Not too broad**: Avoid `admin:*` unless truly needed
- **Not too narrow**: Don't create `user:read:first_name` when `user:read` suffices
- **Business-aligned**: Match your business processes and workflows
- **Future-proof**: Design for extensibility

### 4. Permission Lifecycle

- **Create as needed**: Don't pre-create unused permissions
- **Regular audits**: Review and cleanup unused permissions
- **Version control**: Document permission changes
- **Migration strategy**: Plan for permission updates

### 5. Assignment Strategy

- **Use roles for identity**: Assign common permissions through roles
- **Use groups for collaboration**: Assign project/team permissions through groups
- **Minimize direct assignment**: Avoid directly assigning permissions to users
- **Regular review**: Audit permission assignments periodically

## API Endpoints

| Endpoint                     | Purpose                    | Example                                               |
| ---------------------------- | -------------------------- | ----------------------------------------------------- |
| `POST /permissions/`         | Create permission          | Creates permission in specified scope                 |
| `GET /permissions/`          | List permissions           | Returns permissions visible to user                   |
| `GET /permissions/available` | Get assignable permissions | Returns permissions user can assign, grouped by scope |
| `GET /permissions/{id}`      | Get specific permission    | Returns permission details if user can view           |
| `PUT /permissions/{id}`      | Update permission          | Updates permission if user can manage                 |
| `DELETE /permissions/{id}`   | Delete permission          | Deletes permission if user can manage                 |

## Complete Example

### Lead Generation Company Permission Hierarchy

```python
# System Level: Core auth and infrastructure
system_permissions = [
    {
        "name": "user:create",
        "display_name": "Create Users",
        "description": "Create users in any scope",
        "scope": "system",
        "scope_id": null
    },
    {
        "name": "platform:create",
        "display_name": "Create Platforms",
        "description": "Create new platform instances",
        "scope": "system",
        "scope_id": null
    },
    {
        "name": "infrastructure:manage",
        "display_name": "Manage Infrastructure",
        "description": "Full infrastructure access",
        "scope": "system",
        "scope_id": null
    }
]

# Platform Level: RE/MAX corporate capabilities
remax_platform_permissions = [
    {
        "name": "brand:manage",
        "display_name": "Manage Brand",
        "description": "Manage RE/MAX corporate branding",
        "scope": "platform",
        "scope_id": "remax_platform"
    },
    {
        "name": "franchises:view",
        "display_name": "View All Franchises",
        "description": "View analytics across all RE/MAX franchises",
        "scope": "platform",
        "scope_id": "remax_platform"
    },
    {
        "name": "franchise:create",
        "display_name": "Create Franchise",
        "description": "Create new RE/MAX franchise accounts",
        "scope": "platform",
        "scope_id": "remax_platform"
    }
]

# Client Level: Individual franchise operations
franchise_permissions = [
    {
        "name": "listings:create",
        "display_name": "Create Listings",
        "description": "Create property listings for this franchise",
        "scope": "client",
        "scope_id": "remax_downtown_franchise"
    },
    {
        "name": "agents:manage",
        "display_name": "Manage Agents",
        "description": "Manage real estate agents in this franchise",
        "scope": "client",
        "scope_id": "remax_downtown_franchise"
    },
    {
        "name": "leads:assign",
        "display_name": "Assign Leads",
        "description": "Assign leads to franchise agents",
        "scope": "client",
        "scope_id": "remax_downtown_franchise"
    },
    {
        "name": "commissions:calculate",
        "display_name": "Calculate Commissions",
        "description": "Calculate and process agent commissions",
        "scope": "client",
        "scope_id": "remax_downtown_franchise"
    }
]

# Perfect permission isolation:
# - Lead company staff: system permissions for infrastructure
# - RE/MAX HQ: platform permissions for corporate oversight
# - Downtown franchise: client permissions for local operations
# - No cross-contamination between different franchises
```

This creates a complete, isolated permission system with proper scope boundaries and business-aligned authorization using clean MongoDB ObjectIds and scope-based tenant isolation.
