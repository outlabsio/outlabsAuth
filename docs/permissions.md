# Permission System Documentation

## Overview

The OutlabsAuth system implements a **unified hierarchical permission architecture** that provides intuitive, secure, and scalable access control through automatic permission inheritance. This system uses clean, business-aligned permission names with built-in hierarchical logic where higher-level permissions automatically include lower-level access rights.

### Key Architectural Decision

**Hierarchical Permission Names**: Permissions use descriptive hierarchical names (e.g., `"user:read_all"`, `"user:read_platform"`, `"user:read_client"`) with automatic inheritance logic. This approach provides:

- ✅ **Intuitive Logic** - "Manage" permissions include "Read" permissions automatically
- ✅ **Business Alignment** - Permission levels match organizational hierarchies
- ✅ **Maintainable** - Fewer permissions needed in role definitions
- ✅ **Secure** - No permission gaps or overlaps through inheritance

The system automatically resolves permission hierarchies, so a user with `"user:manage_all"` automatically has `"user:read_all"`, `"user:read_platform"`, `"user:read_client"`, and `"user:read_self"` permissions.

## Architecture

### Four-Tier Hierarchical Structure

```
SYSTEM-WIDE ACCESS (Highest Privilege)
├─ user:manage_all          # Global user management (includes all user permissions)
├─ user:read_all            # Read users system-wide (includes platform/client/self)
├─ role:manage_all          # Global role management (includes all role permissions)
└─ permission:manage_all    # Global permission management (includes all permission permissions)

PLATFORM-SCOPED ACCESS (Cross-Client Operations)
├─ user:manage_platform     # Manage users across platform (includes platform/client/self read)
├─ user:read_platform       # Read users across platform (includes client/self read)
├─ client:manage_platform   # Manage client accounts on platform (includes platform/own read)
└─ client:read_platform     # Read client accounts on platform (includes own read)

CLIENT-SCOPED ACCESS (Organization-Level)
├─ user:manage_client       # Manage users in organization (includes client/self read)
├─ user:read_client         # Read users in organization (includes self read)
├─ group:manage_client      # Manage groups in organization (includes client read)
└─ role:read_client         # Read roles in organization

SELF-ACCESS LEVEL (Individual User - Default)
├─ user:read_self           # Read own profile (granted to all users)
├─ user:update_self         # Update own profile (granted to all users)
├─ group:read_own           # View own group memberships (granted to all users)
└─ client:read_own          # View own client account (granted to all users)
```

## Hierarchical Permission Logic

### Automatic Inheritance Rules

The system implements intelligent permission inheritance:

1. **Manage includes Read**: `user:manage_client` automatically includes `user:read_client`
2. **Broader scopes include narrower**: `user:read_platform` automatically includes `user:read_client` and `user:read_self`
3. **Higher levels include lower**: `user:manage_all` includes all user permissions at every level

### Permission Hierarchy Examples

```python
# User Management Hierarchy
"user:manage_all" includes:
  ├─ "user:manage_platform"
  ├─ "user:manage_client"
  ├─ "user:read_all"
  ├─ "user:read_platform"
  ├─ "user:read_client"
  └─ "user:read_self"

"user:manage_platform" includes:
  ├─ "user:manage_client"
  ├─ "user:read_platform"
  ├─ "user:read_client"
  └─ "user:read_self"

"user:read_platform" includes:
  ├─ "user:read_client"
  └─ "user:read_self"

# Role Management Hierarchy
"role:manage_all" includes:
  ├─ "role:manage_platform"
  ├─ "role:manage_client"
  ├─ "role:read_all"
  ├─ "role:read_platform"
  └─ "role:read_client"

# Group Management Hierarchy
"group:manage_all" includes:
  ├─ "group:manage_platform"
  ├─ "group:manage_client"
  ├─ "group:read_all"
  ├─ "group:read_platform"
  └─ "group:read_client"

# Client Account Hierarchy
"client:manage_all" includes:
  ├─ "client:manage_platform"
  ├─ "client:read_all"
  ├─ "client:read_platform"
  └─ "client:read_own"
```

## Permission Categories

### Core Resource Management

#### User Management Permissions

```python
# System Level (Super Admin)
"user:manage_all"      # Global user management across all scopes
"user:read_all"        # Read users system-wide

# Platform Level (Platform Admin)
"user:manage_platform" # Manage users across platform clients
"user:read_platform"   # Read users across platform clients

# Client Level (Client Admin)
"user:manage_client"   # Manage users within client organization
"user:read_client"     # Read users within client organization

# Self Level (All Users)
"user:read_self"       # Read own profile (default)
"user:update_self"     # Update own profile (default)
```

#### Role Management Permissions

```python
# System Level
"role:manage_all"      # Global role management
"role:read_all"        # Read roles system-wide

# Platform Level
"role:manage_platform" # Manage roles across platform
"role:read_platform"   # Read roles across platform

# Client Level
"role:manage_client"   # Manage roles within client
"role:read_client"     # Read roles within client
```

#### Group Management Permissions

```python
# System Level
"group:manage_all"     # Global group management
"group:read_all"       # Read groups system-wide

# Platform Level
"group:manage_platform" # Manage groups across platform
"group:read_platform"   # Read groups across platform

# Client Level
"group:manage_client"   # Manage groups within client
"group:read_client"     # Read groups within client

# Self Level
"group:read_own"        # View own group memberships (default)
```

#### Permission Management Permissions

```python
# System Level
"permission:manage_all" # Global permission management
"permission:read_all"   # Read permissions system-wide

# Platform Level
"permission:manage_platform" # Manage permissions across platform
"permission:read_platform"   # Read permissions across platform

# Client Level
"permission:manage_client"   # Manage permissions within client
"permission:read_client"     # Read permissions within client
```

#### Client Account Management Permissions

```python
# System Level
"client:manage_all"     # Global client account management
"client:read_all"       # Read all client accounts

# Platform Level
"client:manage_platform" # Manage client accounts on platform
"client:read_platform"   # Read client accounts on platform
"client:create"          # Create new client accounts

# Self Level
"client:read_own"        # View own client account (default)
```

### Specialized Permissions

#### Infrastructure & Platform Management

```python
"platform:create"        # Create new platforms (super admin)
"platform:manage_all"    # Full platform management (super admin)
"system:infrastructure"  # System infrastructure management (super admin)
"support:cross_client"   # Cross-client support within platform
"admin:*"               # Wildcard admin access (super admin)
```

#### Business Operations

```python
# Transition permissions for legacy compatibility
"user:add_member"        # Add users to client account
"user:bulk_create"       # Bulk user creation
"group:manage_members"   # Add/remove group members
```

## Permission Structure

### Permission Properties

```python
{
    "id": "507f1f77bcf86cd799439011",        # MongoDB ObjectId
    "name": "user:read_platform",            # Hierarchical permission name
    "display_name": "Read Platform Users",   # Human-readable name
    "description": "Read users across platform clients (auth platform)",
    "scope": "system",                       # All permissions stored as system scope
    "scope_id": None,                        # No scope_id needed for hierarchical model
    "created_by_user_id": "507f1f77bcf86cd799439012",
    "created_by_client_id": None,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

### Permission Naming Conventions

| Pattern                 | Example                | Description                           |
| ----------------------- | ---------------------- | ------------------------------------- |
| `resource:action_scope` | `user:read_client`     | Resource action at specific scope     |
| `resource:action_level` | `role:manage_all`      | Resource action at hierarchical level |
| `service:action`        | `support:cross_client` | Service-specific action               |
| `wildcard:*`            | `admin:*`              | Wildcard for broad access             |

## Real-World Permission Examples

### System-Level Permissions (Super Admin)

```python
# Core system administration
{
    "name": "user:manage_all",
    "display_name": "Manage All Users",
    "description": "Global user management in auth platform (admin only)",
    "scope": "system"
}

{
    "name": "platform:create",
    "display_name": "Create Platforms",
    "description": "Create new platforms",
    "scope": "system"
}

{
    "name": "admin:*",
    "display_name": "Admin All Access",
    "description": "Wildcard auth platform admin access",
    "scope": "system"
}
```

### Platform-Level Permissions (Platform Admin)

```python
# Cross-client platform operations
{
    "name": "user:manage_platform",
    "display_name": "Manage Platform Users",
    "description": "CRUD users across platform clients (auth platform)",
    "scope": "system"
}

{
    "name": "client:create",
    "display_name": "Create Client Accounts",
    "description": "Create new client accounts in auth platform",
    "scope": "system"
}

{
    "name": "support:cross_client",
    "display_name": "Cross-Client Support",
    "description": "Support across all platform clients in auth platform",
    "scope": "system"
}
```

### Client-Level Permissions (Client Admin)

```python
# Client organization management
{
    "name": "user:manage_client",
    "display_name": "Manage Client Users",
    "description": "CRUD users in same client (auth platform)",
    "scope": "system"
}

{
    "name": "group:manage_client",
    "display_name": "Manage Client Groups",
    "description": "CRUD groups in same client (auth platform)",
    "scope": "system"
}

{
    "name": "role:read_client",
    "display_name": "Read Client Roles",
    "description": "Read roles in same client (auth platform)",
    "scope": "system"
}
```

### Self-Access Permissions (All Users)

```python
# Individual user permissions (granted by default)
{
    "name": "user:read_self",
    "display_name": "Read Own Profile",
    "description": "Read own user profile",
    "scope": "system"
}

{
    "name": "group:read_own",
    "display_name": "View Own Groups",
    "description": "View own group memberships",
    "scope": "system"
}

{
    "name": "client:read_own",
    "display_name": "View Own Client",
    "description": "View own client account info",
    "scope": "system"
}
```

## Permission Resolution System

### How Hierarchical Checking Works

```python
def check_hierarchical_permission(user_permissions: set, required_permission: str) -> bool:
    """
    Check if user has the required permission using hierarchical logic.

    Examples:
    - User with "user:manage_all" automatically has "user:read_client"
    - User with "user:read_platform" automatically has "user:read_self"
    - User with "role:manage_client" automatically has "role:read_client"
    """
    # Direct permission match
    if required_permission in user_permissions:
        return True

    # Check hierarchical inheritance
    permission_hierarchy = {
        # User permission hierarchy
        "user:read_self": [],
        "user:read_client": ["user:read_self"],
        "user:read_platform": ["user:read_client", "user:read_self"],
        "user:read_all": ["user:read_platform", "user:read_client", "user:read_self"],

        "user:manage_client": ["user:read_client", "user:read_self"],
        "user:manage_platform": ["user:manage_client", "user:read_platform", "user:read_client", "user:read_self"],
        "user:manage_all": ["user:manage_platform", "user:manage_client", "user:read_all", "user:read_platform", "user:read_client", "user:read_self"],

        # Similar hierarchies for roles, groups, permissions, clients...
    }

    # Check if user has any higher-level permission that includes the required one
    for user_perm in user_permissions:
        included_permissions = permission_hierarchy.get(user_perm, [])
        if required_permission in included_permissions:
            return True

    return False
```

### User Effective Permissions Calculation

```python
async def get_user_effective_permissions(user_id: str) -> set:
    """
    Calculate all permissions a user has from roles and groups.
    Returns permission names (not IDs) for hierarchical checking.
    """
    user = await UserModel.get(user_id)
    permission_names = set()

    # 1. Get permissions from roles
    for role in user.roles:
        for permission in role.permissions:
            permission_names.add(permission.name)

    # 2. Get permissions from groups
    for group in user.groups:
        for permission in group.permissions:
            permission_names.add(permission.name)

    # 3. Add default self-access permissions
    permission_names.update([
        "user:read_self",
        "user:update_self",
        "group:read_own",
        "client:read_own"
    ])

    return permission_names
```

## Role-Based Permission Assignment

### System Roles (Pre-defined)

```python
# Super Admin Role - Full system access
SUPER_ADMIN_PERMISSIONS = [
    "user:manage_all",      # Includes all user permissions
    "role:manage_all",      # Includes all role permissions
    "group:manage_all",     # Includes all group permissions
    "permission:manage_all", # Includes all permission permissions
    "client:manage_all",    # Includes all client permissions
    "platform:manage_all",  # Platform management
    "admin:*"               # Wildcard access
]

# Platform Admin Role - Cross-client platform management
PLATFORM_ADMIN_PERMISSIONS = [
    "user:manage_platform",    # Manage users across platform
    "role:manage_all",         # Global role management
    "group:manage_all",        # Global group management
    "client:create",           # Create client accounts
    "client:manage_platform",  # Manage platform clients
    "support:cross_client"     # Cross-client support
]

# Client Admin Role - Organization management
CLIENT_ADMIN_PERMISSIONS = [
    "user:manage_client",      # Manage users in client
    "group:manage_client",     # Manage groups in client
    "role:read_client",        # Read client roles
    "permission:read_client",  # Read client permissions
    "user:add_member",         # Add team members
    "group:manage_members"     # Manage group membership
]

# Basic User Role - Self-access only
BASIC_USER_PERMISSIONS = [
    "user:read_self",          # Read own profile (default)
    "user:update_self",        # Update own profile (default)
    "group:read_own",          # View own groups (default)
    "client:read_own"          # View own client (default)
]
```

### Custom Role Creation

```python
# Sales Manager Role (Client-specific)
sales_manager_role = RoleCreateSchema(
    name="sales_manager",
    display_name="Sales Manager",
    description="Manages sales team and client relationships",
    permissions=[
        "user:read_client",        # Read client users (includes self)
        "group:manage_client",     # Manage client groups (includes read)
        "user:add_member",         # Add new team members
        "group:manage_members"     # Manage group membership
    ],
    scope="client"
)

# Platform Support Role (Cross-client)
support_role = RoleCreateSchema(
    name="platform_support",
    display_name="Platform Support",
    description="Provides support across all platform clients",
    permissions=[
        "user:read_platform",     # Read users across platform (includes client/self)
        "support:cross_client",   # Cross-client support access
        "client:read_platform"    # Read client accounts (includes own)
    ],
    scope="platform"
)
```

## Integration with Dependencies

### Named Dependencies Using Hierarchical Permissions

The dependency system uses hierarchical permissions for access control:

```python
# User Management Dependencies
can_read_users = require_permissions(any_of=[
    "user:read_all",      # System admin access
    "user:read_platform", # Platform admin access
    "user:read_client"    # Client admin access
])

can_manage_users = require_permissions(any_of=[
    "user:manage_all",      # System management
    "user:manage_platform", # Platform management
    "user:manage_client"    # Client management
])

# Role Management Dependencies
can_read_roles = require_permissions(any_of=[
    "role:read_all",
    "role:read_platform",
    "role:read_client"
])

can_manage_roles = require_permissions(any_of=[
    "role:manage_all",
    "role:manage_platform",
    "role:manage_client"
])
```

### Automatic Scope Resolution in Services

```python
# Service layer automatically handles data scoping based on user permissions
async def get_users(current_user: UserModel, skip: int = 0, limit: int = 100) -> List[UserModel]:
    user_permissions = await get_user_effective_permissions(current_user.id)

    if check_hierarchical_permission(user_permissions, "user:read_all"):
        # System admin: can see all users
        return await UserModel.find().skip(skip).limit(limit).to_list()

    elif check_hierarchical_permission(user_permissions, "user:read_platform"):
        # Platform admin: can see all users on their platform
        platform_clients = await get_platform_client_ids(current_user)
        return await UserModel.find({
            "$or": [
                {"client_account": {"$in": platform_clients}},
                {"client_account": None}  # Platform users
            ]
        }).skip(skip).limit(limit).to_list()

    elif check_hierarchical_permission(user_permissions, "user:read_client"):
        # Client admin: can see users in their client organization only
        return await UserModel.find({
            "client_account": current_user.client_account.id
        }).skip(skip).limit(limit).to_list()

    else:
        # Regular user: can only see themselves
        return [current_user]
```

## Frontend Integration

### Permission Checking in UI

```javascript
// Frontend permission checking using hierarchical logic
const userPermissions = userStore.effectivePermissions;

// Check permissions using the same hierarchical logic as backend
const canManageUsers = userPermissions.some((perm) => ["user:manage_all", "user:manage_platform", "user:manage_client"].includes(perm));

const canReadAllUsers = userPermissions.includes("user:read_all");
const canReadPlatformUsers = userPermissions.some((perm) => ["user:read_all", "user:read_platform"].includes(perm));

// Conditional UI rendering
{
  canManageUsers && <UserManagementPanel />;
}
{
  canReadAllUsers && <SystemUsersList />;
}
{
  canReadPlatformUsers && <PlatformUsersList />;
}
```

### Available Permissions API Response

```javascript
// GET /permissions/available - Returns permissions grouped by level
{
    "system_permissions": [
        {
            "name": "user:manage_all",
            "display_name": "Manage All Users",
            "description": "Global user management in auth platform (admin only)",
            "level": "system"
        }
    ],
    "platform_permissions": [
        {
            "name": "user:manage_platform",
            "display_name": "Manage Platform Users",
            "description": "CRUD users across platform clients (auth platform)",
            "level": "platform"
        }
    ],
    "client_permissions": [
        {
            "name": "user:manage_client",
            "display_name": "Manage Client Users",
            "description": "CRUD users in same client (auth platform)",
            "level": "client"
        }
    ],
    "self_permissions": [
        {
            "name": "user:read_self",
            "display_name": "Read Own Profile",
            "description": "Read own user profile",
            "level": "self"
        }
    ]
}
```

## Security Features

### Hierarchical Access Control

- **Automatic Inheritance**: Higher permissions include lower ones automatically
- **Scope Isolation**: Users can only access data within their permission scope
- **No Permission Gaps**: Hierarchical logic prevents security holes
- **Business Alignment**: Permission levels match organizational structures

### Permission Validation

- **Naming Validation**: Permissions must follow hierarchical naming conventions
- **Level Validation**: Permissions must be appropriate for their hierarchical level
- **Uniqueness Enforcement**: No duplicate permission names
- **Assignment Validation**: Users can only assign permissions they have access to

### Wildcard Handling

```python
def has_wildcard_permission(user_permissions: set, required_permission: str) -> bool:
    """Handle wildcard permissions like 'admin:*'"""
    for permission in user_permissions:
        if permission.endswith(":*"):
            prefix = permission[:-1]  # Remove "*"
            if required_permission.startswith(prefix):
                return True
    return False

# Example usage
user_permissions = {"admin:*", "user:read_self"}
has_wildcard_permission(user_permissions, "admin:settings:update")  # True
has_wildcard_permission(user_permissions, "user:read_self")         # False (direct match)
has_wildcard_permission(user_permissions, "billing:view")          # False
```

## Database Queries

### Efficient Permission Lookups

```python
# Get all system permissions (hierarchical model stores all as system scope)
all_permissions = await PermissionModel.find(
    PermissionModel.scope == "system"
).to_list()

# Get user's effective permissions (resolved to names for hierarchical checking)
user_effective_permissions = await get_user_effective_permissions(user_id)

# Check if user has specific permission using hierarchical logic
from services.permission_service import check_hierarchical_permission
has_permission = check_hierarchical_permission(user_effective_permissions, "user:read_client")

# Get permissions available for role assignment based on user's level
available_permissions = await get_available_permissions_for_user(
    current_user=current_user,
    include_system=is_super_admin,
    include_platform=is_platform_admin,
    include_client=is_client_admin
)
```

## Best Practices

### 1. Permission Design

- **Use hierarchical levels**: Design permissions that follow the four-tier hierarchy
- **Business alignment**: Match permission levels to organizational structures
- **Clear naming**: Use consistent `resource:action_level` pattern
- **Avoid over-granularity**: Don't create `user:read_first_name` when `user:read_client` suffices

### 2. Role Assignment Strategy

- **Assign at appropriate level**: Give users the lowest level that meets their needs
- **Use manage permissions sparingly**: Only for users who truly need write access
- **Leverage inheritance**: A user with `user:manage_client` automatically gets `user:read_client`
- **Regular audits**: Review and cleanup permission assignments periodically

### 3. Hierarchical Logic

- **Trust the hierarchy**: Don't assign both `user:read_all` and `user:read_client` to the same role
- **Test inheritance**: Verify that higher permissions include expected lower permissions
- **Document custom permissions**: If creating new permissions, document their hierarchical relationships
- **Use service layer scoping**: Let services handle data filtering based on permission levels

### 4. Development Workflow

- **Start with named dependencies**: Use `can_read_users`, `can_manage_roles` etc.
- **Add custom permissions as needed**: Create new hierarchical permissions for business requirements
- **Test permission inheritance**: Ensure hierarchical logic works as expected
- **Monitor permission usage**: Track which permissions are actually used vs. assigned

## API Endpoints

The permission system provides comprehensive CRUD operations for managing hierarchical permissions. All endpoints use the unified hierarchical permission architecture and named dependencies for access control.

**Base URL:** `/v1/permissions`  
**Tags:** Permission Management

### Authentication & Authorization

All endpoints require authentication and use hierarchical permission checking:

- **Read Access:** Uses `can_read_permissions` dependency with hierarchical permissions `["permission:read_all", "permission:read_platform"]`
- **Management Access:** Uses `can_manage_permissions` dependency with hierarchical permissions `["permission:manage_all", "permission:manage_platform"]`

### Endpoint Summary

| Endpoint                    | Method | Purpose                    | Required Dependencies    | Hierarchical Access Control                |
| --------------------------- | ------ | -------------------------- | ------------------------ | ------------------------------------------ |
| `/v1/permissions/`          | POST   | Create permission          | `can_manage_permissions` | Based on user's management level           |
| `/v1/permissions/`          | GET    | List permissions           | `can_read_permissions`   | Filtered by user's read level              |
| `/v1/permissions/available` | GET    | Get assignable permissions | `require_admin`          | Returns permissions user can assign        |
| `/v1/permissions/{id}`      | GET    | Get specific permission    | `can_read_permissions`   | Checked using hierarchical logic           |
| `/v1/permissions/{id}`      | PUT    | Update permission          | `can_manage_permissions` | Requires appropriate management permission |
| `/v1/permissions/{id}`      | DELETE | Delete permission          | `can_manage_permissions` | Requires appropriate management permission |

### 1. Create Permission

Creates a new permission using the hierarchical naming system.

**Endpoint:** `POST /v1/permissions/`

**Authentication:** Bearer token required

**Access Control:** `can_manage_permissions` - Requires one of:

- `permission:manage_all` (system-wide management)
- `permission:manage_platform` (platform-wide management)

**Query Parameters:**

- `scope_id` (optional, string) - Platform ID or Client ID for scoped permissions (auto-determined from user context if not provided)

**Request Body:**

```json
{
  "name": "user:read_client",
  "display_name": "Read Client Users",
  "description": "View users within the same client organization",
  "scope": "system"
}
```

**Response:**

- **Status Code:** `201 Created`
- **Content-Type:** `application/json`

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "user:read_client",
  "display_name": "Read Client Users",
  "description": "View users within the same client organization",
  "scope": "system",
  "scope_id": null,
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": null
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Invalid authentication
- `403 Forbidden` - Insufficient permissions
- `409 Conflict` - Permission name already exists

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "user:read_client",
       "display_name": "Read Client Users",
       "description": "View users within the same client organization",
       "scope": "system"
     }'
```

### 2. List Permissions

Retrieves permissions with pagination and optional filtering.

**Endpoint:** `GET /v1/permissions/`

**Authentication:** Bearer token required

**Access Control:** `can_read_permissions` - Requires one of:

- `permission:read_all` (system-wide read access)
- `permission:read_platform` (platform-wide read access)

**Query Parameters:**

- `skip` (optional, integer, default: 0, min: 0) - Number of permissions to skip
- `limit` (optional, integer, default: 100, min: 1, max: 1000) - Number of permissions to return
- `scope` (optional, string) - Filter by permission scope (`system`, `platform`, `client`)
- `scope_id` (optional, string) - Filter by specific scope ID

**Response:**

- **Status Code:** `200 OK`
- **Content-Type:** `application/json`

```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "user:read_client",
    "display_name": "Read Client Users",
    "description": "View users within the same client organization",
    "scope": "system",
    "scope_id": null,
    "created_by_user_id": "507f1f77bcf86cd799439012",
    "created_by_client_id": null
  },
  {
    "id": "507f1f77bcf86cd799439013",
    "name": "user:manage_all",
    "display_name": "Manage All Users",
    "description": "Global user management across all scopes",
    "scope": "system",
    "scope_id": null,
    "created_by_user_id": "507f1f77bcf86cd799439012",
    "created_by_client_id": null
  }
]
```

**Error Responses:**

- `400 Bad Request` - Invalid query parameters
- `401 Unauthorized` - Invalid authentication
- `403 Forbidden` - Insufficient permissions

**Example Request:**

```bash
# Get all permissions with pagination
curl -X GET "https://api.example.com/v1/permissions/?skip=0&limit=50" \
     -H "Authorization: Bearer <access_token>"

# Filter by scope
curl -X GET "https://api.example.com/v1/permissions/?scope=system" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Available Permissions

Retrieves permissions that the current user can assign to roles or groups, organized by hierarchical levels.

**Endpoint:** `GET /v1/permissions/available`

**Authentication:** Bearer token required

**Access Control:** `require_admin` - Requires admin role

**Query Parameters:** None

**Response:**

- **Status Code:** `200 OK`
- **Content-Type:** `application/json`

```json
{
  "system_permissions": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "user:manage_all",
      "display_name": "Manage All Users",
      "description": "Global user management across all scopes",
      "scope": "system",
      "scope_id": null,
      "created_by_user_id": "507f1f77bcf86cd799439012",
      "created_by_client_id": null
    }
  ],
  "platform_permissions": [
    {
      "id": "507f1f77bcf86cd799439013",
      "name": "user:manage_platform",
      "display_name": "Manage Platform Users",
      "description": "Manage users across platform clients",
      "scope": "system",
      "scope_id": null,
      "created_by_user_id": "507f1f77bcf86cd799439012",
      "created_by_client_id": null
    }
  ],
  "client_permissions": [
    {
      "id": "507f1f77bcf86cd799439014",
      "name": "user:manage_client",
      "display_name": "Manage Client Users",
      "description": "Manage users within client organization",
      "scope": "system",
      "scope_id": null,
      "created_by_user_id": "507f1f77bcf86cd799439012",
      "created_by_client_id": null
    }
  ]
}
```

**Error Responses:**

- `401 Unauthorized` - Invalid authentication
- `403 Forbidden` - User is not an admin

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/available" \
     -H "Authorization: Bearer <access_token>"
```

### 4. Get Permission by ID

Retrieves a specific permission by its MongoDB ObjectId.

**Endpoint:** `GET /v1/permissions/{permission_id}`

**Authentication:** Bearer token required

**Access Control:** `can_read_permissions` - Requires one of:

- `permission:read_all` (system-wide read access)
- `permission:read_platform` (platform-wide read access)

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Response:**

- **Status Code:** `200 OK`
- **Content-Type:** `application/json`

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "user:read_client",
  "display_name": "Read Client Users",
  "description": "View users within the same client organization",
  "scope": "system",
  "scope_id": null,
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": null
}
```

**Error Responses:**

- `400 Bad Request` - Invalid permission ID format
- `401 Unauthorized` - Invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Permission not found

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

### 5. Update Permission

Updates an existing permission's display name and description.

**Endpoint:** `PUT /v1/permissions/{permission_id}`

**Authentication:** Bearer token required

**Access Control:** `can_manage_permissions` - Requires one of:

- `permission:manage_all` (system-wide management)
- `permission:manage_platform` (platform-wide management)

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Request Body:**

```json
{
  "display_name": "Read Client Organization Users",
  "description": "Updated description for reading users within client organization"
}
```

**Response:**

- **Status Code:** `200 OK`
- **Content-Type:** `application/json`

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "user:read_client",
  "display_name": "Read Client Organization Users",
  "description": "Updated description for reading users within client organization",
  "scope": "system",
  "scope_id": null,
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": null
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data or permission ID format
- `401 Unauthorized` - Invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Permission not found

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "display_name": "Read Client Organization Users",
       "description": "Updated description for reading users within client organization"
     }'
```

### 6. Delete Permission

Deletes a permission from the system.

**Endpoint:** `DELETE /v1/permissions/{permission_id}`

**Authentication:** Bearer token required

**Access Control:** `can_manage_permissions` - Requires one of:

- `permission:manage_all` (system-wide management)
- `permission:manage_platform` (platform-wide management)

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `400 Bad Request` - Invalid permission ID format
- `401 Unauthorized` - Invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Permission not found

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

## Hierarchical Permission Integration

### Named Dependencies

The permission endpoints use the unified hierarchical permission system through named dependencies:

```python
# Permission Management Dependencies (from dependencies.py)
can_read_permissions = require_permissions(any_of=[
    "permission:read_all",      # System-wide permission read access
    "permission:read_platform"  # Platform-wide permission read access
])

can_manage_permissions = require_permissions(any_of=[
    "permission:manage_all",      # System-wide permission management
    "permission:manage_platform"  # Platform-wide permission management
])
```

### Automatic Hierarchical Logic

All permission checks use the hierarchical logic where:

- Users with `permission:manage_all` automatically have `permission:read_all`, `permission:read_platform`
- Users with `permission:manage_platform` automatically have `permission:read_platform`
- Users with `permission:read_all` automatically have `permission:read_platform`

### Service Layer Integration

The permission service automatically handles:

- **Scope Resolution:** Determines appropriate permissions based on user's hierarchy level
- **Data Filtering:** Returns only permissions the user has access to view/manage
- **Validation:** Ensures users can only create/modify permissions within their scope

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message description"
}
```

### Common Error Scenarios

**403 Forbidden - Insufficient Permissions:**

```json
{
  "detail": "Access denied. Required permissions: permission:read_all, permission:read_platform"
}
```

**404 Not Found - Permission Not Found:**

```json
{
  "detail": "Permission with ID '507f1f77bcf86cd799439011' not found."
}
```

**409 Conflict - Duplicate Permission:**

```json
{
  "detail": "Permission with name 'user:read_client' already exists in system scope"
}
```

## Usage Examples

### Creating Hierarchical Permissions

```bash
# Create system-level permission (super admin only)
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <super_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "user:manage_all",
       "display_name": "Manage All Users",
       "description": "Global user management across all scopes",
       "scope": "system"
     }'

# Create platform-level permission (platform admin)
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <platform_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "user:manage_platform",
       "display_name": "Manage Platform Users",
       "description": "Manage users across platform clients",
       "scope": "system"
     }'

# Create client-level permission (client admin)
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <client_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "user:manage_client",
       "display_name": "Manage Client Users",
       "description": "Manage users within client organization",
       "scope": "system"
     }'
```

### Checking Available Permissions

```bash
# Get permissions available for role assignment
curl -X GET "https://api.example.com/v1/permissions/available" \
     -H "Authorization: Bearer <admin_token>"

# Response shows permissions grouped by hierarchical level
{
  "system_permissions": [...],      # Only for super admins
  "platform_permissions": [...],   # For platform admins and above
  "client_permissions": [...]      # For client admins and above
}
```

### Frontend Integration

```javascript
// Check user's effective permissions using hierarchical logic
const userPermissions = userStore.effectivePermissions;

// Permission checking with hierarchical inheritance
const canReadPermissions = userPermissions.some((perm) => ["permission:read_all", "permission:read_platform"].includes(perm));

const canManagePermissions = userPermissions.some((perm) => ["permission:manage_all", "permission:manage_platform"].includes(perm));

// Conditional UI rendering based on hierarchical permissions
{
  canReadPermissions && <PermissionsList />;
}
{
  canManagePermissions && <PermissionManagement />;
}
```
