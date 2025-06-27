# Group System Documentation

## Overview

The OutlabsAuth system implements a **scoped group architecture** with **hierarchical permissions** that provides flexible team organization and direct permission management across multiple organizational levels. Groups serve as **permission containers** that complement the role system by allowing fine-grained access control through team-based organization with intelligent permission inheritance using clean MongoDB ObjectIds and scope fields for tenant isolation.

## 🏗️ **Architecture: Scoped Groups + Hierarchical Permissions**

### **Two-Layer System Design**

```
GROUPS (Scoped Containers)
├─ System Groups    → Global operational teams (scope: system, scope_id: null)
├─ Platform Groups  → Platform-specific teams (scope: platform, scope_id: platform_id)
└─ Client Groups    → Client organization teams (scope: client, scope_id: client_account_id)

PERMISSIONS (Hierarchical Direct Assignment)
├─ manage_all     → Includes manage_platform + manage_client + all read levels
├─ manage_platform → Includes manage_client + platform/client/self read levels
├─ manage_client   → Includes client/self read levels
├─ read_all       → System-wide read access
├─ read_platform  → Platform-wide read access (includes client/self)
├─ read_client    → Client organization read access (includes self)
└─ read_self      → Individual user access (default for all users)
```

## Group vs Role Philosophy

### Key Differences

| Aspect                | **Roles**                    | **Groups**                        |
| --------------------- | ---------------------------- | --------------------------------- |
| **Purpose**           | User identity & capabilities | Team organization & collaboration |
| **Permission Source** | Hierarchical permission sets | Direct hierarchical permissions   |
| **Relationship**      | User has roles               | User belongs to groups            |
| **Flexibility**       | Structured, template-based   | Dynamic, team-based               |
| **Use Case**          | "What can this user do?"     | "Who works on this project?"      |

### Complementary System

```javascript
// User effective permissions = Role permissions + Group permissions
// (All resolved using hierarchical permission inheritance)
user_permissions = [
  ...permissions_from_roles, // e.g., "user:read_client" from "manager" role
  ...permissions_from_groups, // e.g., "group:manage_client" from "project_team" group
];

// Hierarchical checking: "user:manage_client" automatically includes "user:read_client" and "user:read_self"
```

## Group Structure

### Group Properties

```javascript
{
  "id": "507f1f77bcf86cd799439011",        // MongoDB ObjectId
  "name": "sales_team",                    // Simple group name
  "display_name": "Sales Team",            // Human-readable name
  "description": "Handles all sales activities and client relationships",
  "permissions": [                         // Hierarchical permission names
    "user:read_client",                    // Read client users (includes self)
    "group:manage_client",                 // Manage client groups (includes read)
    "user:add_member",                     // Add team members
    "group:manage_members"                 // Manage group membership
  ],
  "scope": "client",                       // "system" | "platform" | "client"
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Foreign key to scope owner
  "is_active": true,
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Scope Ownership

| Scope        | `scope_id` Points To | Example                      | Description                              |
| ------------ | -------------------- | ---------------------------- | ---------------------------------------- |
| **system**   | `null`               | Global operational teams     | Available across all platforms/clients   |
| **platform** | `platform_id`        | `"real_estate_platform"`     | Platform that owns this group            |
| **client**   | `client_account_id`  | `"685a5f2e82e92ad29111a6a9"` | Client organization that owns this group |

## Hierarchical Permission System in Groups

### **Permission Hierarchy Levels**

Groups use the same hierarchical permission system as roles, with automatic inheritance:

```python
# Group Management Hierarchy (for managing groups themselves)
"group:manage_all"     # Global group management across all scopes
├─ "group:manage_platform" # Manage groups across platform clients
├─ "group:manage_client"   # Manage groups within client organization
├─ "group:read_all"        # Read groups system-wide
├─ "group:read_platform"   # Read groups across platform clients
└─ "group:read_client"     # Read groups within client organization

# User Management Hierarchy (groups can grant user permissions)
"user:manage_all"      # Global user management across all scopes
├─ "user:manage_platform"  # Manage users across platform clients
├─ "user:manage_client"    # Manage users within client organization
├─ "user:read_all"         # Read users system-wide
├─ "user:read_platform"    # Read users across platform clients
├─ "user:read_client"      # Read users within client organization
└─ "user:read_self"        # Read own profile (granted to all users)

# Other Resource Hierarchies (roles, permissions, client accounts)
"role:manage_client"   # Manage roles within client (includes role:read_client)
"permission:read_platform" # Read permissions across platform
"client:read_own"      # View own client account (default)
```

### **Automatic Permission Inheritance in Groups**

Groups benefit from the same intelligent permission inheritance:

1. **Manage includes Read**: `user:manage_client` in a group automatically includes `user:read_client`
2. **Broader scopes include narrower**: `user:read_platform` automatically includes `user:read_client` and `user:read_self`
3. **Higher levels include lower**: `user:manage_all` includes all user permissions at every level

## Group Examples

### System Groups

```javascript
// Customer Support (cross-platform operations)
{
  "id": "507f1f77bcf86cd799439011",
  "name": "customer_support",
  "display_name": "Customer Support Team",
  "description": "Provides support across all platforms and clients",
  "scope": "system",
  "scope_id": null,
  "permissions": [
    "user:read_platform",      // Read users across platform (includes client/self)
    "support:cross_client",    // Cross-client support access
    "client:read_platform",    // Read client accounts (includes own)
    "group:read_platform"      // Read groups across platform (includes client)
  ]
}

// Engineering Team (system-wide infrastructure)
{
  "id": "507f1f77bcf86cd799439012",
  "name": "engineering",
  "display_name": "Engineering Team",
  "description": "Core development and infrastructure team",
  "scope": "system",
  "scope_id": null,
  "permissions": [
    "system:infrastructure",   // System infrastructure management
    "platform:manage_all",     // Full platform management
    "user:read_all",          // Read all users (includes all lower levels)
    "client:read_all"         // Read all client accounts (includes all lower)
  ]
}
```

### Platform Groups

```javascript
// Platform Marketing Team (cross-client marketing)
{
  "id": "507f1f77bcf86cd799439013",
  "name": "marketing_team",
  "display_name": "Marketing Team",
  "description": "Platform marketing and growth initiatives",
  "scope": "platform",
  "scope_id": "real_estate_platform",
  "permissions": [
    "client:read_platform",    // Read platform clients (includes own)
    "user:read_platform",      // Read platform users (includes client/self)
    "group:read_platform",     // Read platform groups (includes client)
    "support:cross_client"     // Cross-client support for marketing
  ]
}

// Platform Sales Team (client acquisition)
{
  "id": "507f1f77bcf86cd799439014",
  "name": "sales_team",
  "display_name": "Platform Sales Team",
  "description": "Responsible for acquiring new client organizations",
  "scope": "platform",
  "scope_id": "real_estate_platform",
  "permissions": [
    "client:create",           // Create new client accounts
    "client:manage_platform",  // Manage platform clients (includes read)
    "user:read_platform",      // Read platform users (includes client/self)
    "user:add_member"          // Add users to client accounts
  ]
}
```

### Client Groups

```javascript
// Client Sales Team (organization sales)
{
  "id": "507f1f77bcf86cd799439015",
  "name": "sales_team",
  "display_name": "Sales Team",
  "description": "Client organization sales representatives",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Client account ID
  "permissions": [
    "user:read_client",        // Read client users (includes self)
    "group:read_client",       // Read client groups
    "user:add_member",         // Add new team members
    "group:manage_members",    // Manage group membership
    "client:read_own"          // View own client account (default)
  ]
}

// Project Team (specific project collaboration)
{
  "id": "507f1f77bcf86cd799439016",
  "name": "project_alpha_team",
  "display_name": "Project Alpha Team",
  "description": "Cross-functional team for Project Alpha initiative",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "permissions": [
    "user:read_client",        // Read client users (includes self)
    "group:manage_client",     // Manage client groups (includes read)
    "user:add_member",         // Add project team members
    "group:manage_members",    // Manage project team membership
    "permission:read_client"   // Read client permissions for project setup
  ]
}
```

## Permission Model

### Who Can Create Groups

| User Type          | Can Create         | Scope                            | Permissions Required    | Restrictions                 |
| ------------------ | ------------------ | -------------------------------- | ----------------------- | ---------------------------- |
| **Super Admin**    | ✅ Any group       | `system`, `platform`, `client`   | `group:manage_all`      | No restrictions              |
| **Platform Admin** | ✅ Platform groups | `platform` (their platform only) | `group:manage_platform` | Only within their platform   |
| **Client Admin**   | ✅ Client groups   | `client` (their client only)     | `group:manage_client`   | Only within their client org |
| **Team Lead**      | ✅ Client groups   | `client` (their client only)     | `group:manage_client`   | If granted group management  |

### Who Can Assign Group Membership

| User Type          | Can Add Members To            | Permissions Required    | Examples                                |
| ------------------ | ----------------------------- | ----------------------- | --------------------------------------- |
| **Super Admin**    | Any group                     | `group:manage_all`      | All system, platform, and client groups |
| **Platform Admin** | Platform + some system groups | `group:manage_platform` | Platform groups + customer_support      |
| **Client Admin**   | Client groups                 | `group:manage_client`   | All groups within their client          |
| **Group Manager**  | Groups they manage            | `group:manage_members`  | If granted group membership management  |

### Group Visibility (Using Hierarchical Permissions)

| User Type          | Can View                              | Permission Required                    |
| ------------------ | ------------------------------------- | -------------------------------------- |
| **Super Admin**    | All groups across all scopes          | `group:read_all`                       |
| **Platform Admin** | System + platform groups              | `group:read_platform`                  |
| **Client Admin**   | System + client groups                | `group:read_client`                    |
| **Regular User**   | Groups they belong to + client groups | `group:read_own` + `group:read_client` |

## Usage Patterns

### 1. Creating Departmental Groups

When organizing teams within a client organization:

```python
# Create sales team group with hierarchical permissions
sales_group_data = GroupCreateSchema(
    name="sales_team",
    display_name="Sales Team",
    description="Handles all sales activities and client relationships",
    permissions=[
        "user:read_client",        // Hierarchical: includes user:read_self
        "group:read_client",       // Read client groups
        "user:add_member",         // Add new team members
        "group:manage_members",    // Manage group membership
        "client:read_own"          // View own client account (default)
    ],
    scope=GroupScope.CLIENT
)

sales_group = await group_service.create_group(
    group_data=sales_group_data,
    current_user_id=client_admin_id,
    current_client_id=client_admin.client_account_id
    # scope_id automatically set to client_admin.client_account_id
)

# Add sales representatives to the group
await group_service.add_users_to_group(
    group_id=sales_group.id,
    user_ids=["user_1", "user_2", "user_3"]
)
```

### 2. Project-Based Groups

Creating temporary groups for specific projects:

```python
# Create project-specific group with hierarchical permissions
project_group_data = GroupCreateSchema(
    name="project_alpha_team",
    display_name="Project Alpha Team",
    description="Cross-functional team for Project Alpha",
    permissions=[
        "user:read_client",        // Hierarchical: includes user:read_self
        "group:manage_client",     // Manage client groups (includes read)
        "user:add_member",         // Add project team members
        "group:manage_members",    // Manage project team membership
        "permission:read_client"   // Read client permissions for project setup
    ],
    scope=GroupScope.CLIENT
)

project_group = await group_service.create_group(
    group_data=project_group_data,
    current_user_id=project_manager_id,
    current_client_id=project_manager.client_account_id
)

# Add team members from different departments
await group_service.add_users_to_group(
    group_id=project_group.id,
    user_ids=[sales_rep_id, developer_id, designer_id, analyst_id]
)
```

### 3. Platform Operational Groups

Platform administrators creating cross-client operational teams:

```python
# Create platform analytics group with hierarchical permissions
analytics_group_data = GroupCreateSchema(
    name="analytics_team",
    display_name="Analytics Team",
    description="Platform-wide analytics and reporting team",
    permissions=[
        "user:read_platform",      // Hierarchical: includes user:read_client + user:read_self
        "client:read_platform",    // Hierarchical: includes client:read_own
        "group:read_platform",     // Hierarchical: includes group:read_client
        "support:cross_client"     // Cross-client support access
    ],
    scope=GroupScope.PLATFORM
)

analytics_group = await group_service.create_group(
    group_data=analytics_group_data,
    current_user_id=platform_admin_id,
    current_client_id=None,
    scope_id="real_estate_platform"
)
```

## Multi-Role + Group Permissions

### Permission Aggregation with Hierarchical Inheritance

Users can have both roles and group memberships, with permissions combined using hierarchical logic:

```python
# User has "manager" role + belongs to "sales_team" group
user_effective_permissions = await user_service.get_user_effective_permissions(user_id)

# Returns combined permissions with hierarchical inheritance:
# From "manager" role: ["user:manage_client"] -> includes ["user:read_client", "user:read_self"]
# From "sales_team" group: ["group:manage_client"] -> includes ["group:read_client"]
# Final effective: ["user:manage_client", "user:read_client", "user:read_self",
#                  "group:manage_client", "group:read_client", "user:add_member"]
```

### Real-World Example

```javascript
// Sarah is a Team Manager who also works on special projects
{
  "user": {
    "id": "507f1f77bcf86cd799439020",
    "email": "sarah@acme.com",
    "roles": ["manager"],                    // Role: Team management capabilities
    "groups": ["sales_team", "project_alpha_team"]  // Groups: Sales access + project access
  },

  "effective_permissions": [
    // From "manager" role (hierarchical):
    "user:manage_client",      // Includes user:read_client, user:read_self
    "group:read_client",       // Read client groups
    "client:read_own",         // View own client account

    // From "sales_team" group:
    "user:add_member",         // Add new team members
    "group:manage_members",    // Manage group membership

    // From "project_alpha_team" group:
    "permission:read_client"   // Read client permissions for project setup
  ]
}
```

## Integration with Dependencies

### Named Dependencies Using Hierarchical Permissions

The dependency system uses hierarchical permissions for clean group access control:

```python
# Group Management Dependencies
can_read_groups = require_permissions(any_of=["group:read_all", "group:read_platform", "group:read_client"])
can_manage_groups = require_permissions(any_of=["group:manage_all", "group:manage_platform", "group:manage_client"])

# Route Usage Example
@router.get("/", response_model=List[GroupResponseSchema])
async def get_all_groups(
    current_user: UserModel = Depends(can_read_groups),  // Hierarchical permission check
    skip: int = 0, limit: int = 100
):
    groups = await group_service.get_groups(current_user=current_user, skip=skip, limit=limit)
    return [await group_service.group_to_response_schema(group) for group in groups]
```

### Automatic Data Scoping

The service layer automatically handles data scoping based on user permissions:

```python
async def get_groups(self, current_user: UserModel, skip: int = 0, limit: int = 100) -> List[GroupModel]:
    """
    Get groups with automatic scoping based on user's hierarchical permissions.
    """
    user_permissions = await get_user_effective_permissions(current_user.id)

    if "group:read_all" in user_permissions:
        # Super admin - see all groups
        return await GroupModel.find().skip(skip).limit(limit).to_list()
    elif "group:read_platform" in user_permissions:
        # Platform admin - see system + platform groups
        return await GroupModel.find({
            "$or": [
                {"scope": "system"},
                {"scope": "platform", "scope_id": current_user.platform_id}
            ]
        }).skip(skip).limit(limit).to_list()
    elif "group:read_client" in user_permissions:
        # Client admin - see system + client groups
        return await GroupModel.find({
            "$or": [
                {"scope": "system"},
                {"scope": "client", "scope_id": current_user.client_account_id}
            ]
        }).skip(skip).limit(limit).to_list()
    else:
        # No group read permissions - only own groups
        return await GroupModel.find({
            "members": current_user.id
        }).skip(skip).limit(limit).to_list()
```

## Frontend Integration

### Group Creation UI

The frontend provides intuitive group management with hierarchical permission selection:

```javascript
// Frontend form data
{
  name: "marketing_team",
  display_name: "Marketing Team",
  description: "Handles marketing campaigns and brand management",
  permissions: [
    "user:read_client",         // Hierarchical: includes user:read_self
    "group:read_client",        // Read client groups
    "user:add_member",          // Add team members
    "group:manage_members",     // Manage group membership
    "client:read_own"           // View own client account (default)
  ],
  scope: "client"  // User selects scope level
}

// Backend creates group with proper scope_id automatically
```

### Available Groups API

Use the `/groups/available` endpoint to get groups a user can assign:

```javascript
// GET /groups/available
{
  "system_groups": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "customer_support",
      "display_name": "Customer Support Team",
      "scope": "system",
      "scope_id": null,
      "permissions": [
        {"name": "user:read_platform", "display_name": "Read Platform Users"},
        {"name": "support:cross_client", "display_name": "Cross-Client Support"}
      ]
    }
  ],
  "platform_groups": [
    {
      "id": "507f1f77bcf86cd799439013",
      "name": "analytics_team",
      "display_name": "Analytics Team",
      "scope": "platform",
      "scope_id": "real_estate_platform",
      "permissions": [
        {"name": "user:read_platform", "display_name": "Read Platform Users"},
        {"name": "client:read_platform", "display_name": "Read Platform Clients"}
      ]
    }
  ],
  "client_groups": [
    {
      "id": "507f1f77bcf86cd799439015",
      "name": "sales_team",
      "display_name": "Sales Team",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "permissions": [
        {"name": "user:read_client", "display_name": "Read Client Users"},
        {"name": "group:read_client", "display_name": "Read Client Groups"}
      ]
    }
  ]
}
```

### Group Membership UI

```javascript
// GET /groups/{group_id}/members
{
  "group_id": "507f1f77bcf86cd799439015",
  "group_name": "Sales Team",
  "group_scope": "client",
  "members": [
    {
      "id": "507f1f77bcf86cd799439020",
      "email": "sarah@acme.com",
      "first_name": "Sarah",
      "last_name": "Johnson",
      "status": "active"
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "email": "mike@acme.com",
      "first_name": "Mike",
      "last_name": "Chen",
      "status": "active"
    }
  ]
}
```

## Security Features

### Namespace Isolation + Hierarchical Security

- **No group collisions**: Groups are isolated by scope + scope_id
- **Tenant isolation**: Client A's "sales_team" is completely separate from Client B's "sales_team"
- **Permission inheritance**: Higher-level permissions automatically include lower levels
- **Automatic scoping**: Service layer filters data based on user's permission hierarchy

### Permission Validation

- **Hierarchical validation**: Only valid hierarchical permissions can be assigned to groups
- **Scope validation**: Group permissions must be appropriate for the group's scope
- **Context awareness**: Backend validates permissions against user's hierarchical capabilities

### Unique Constraints

- **Name uniqueness**: Group names must be unique within their scope (name + scope + scope_id)
- **Proper isolation**: Same group name can exist in different scopes without conflict
- **Permission inheritance**: Automatic validation of permission hierarchy

## Database Queries

### Efficient Group Lookups

```python
# Get all client groups for a specific client
client_groups = await GroupModel.find(
    GroupModel.scope == GroupScope.CLIENT,
    GroupModel.scope_id == client_id,
    fetch_links=True  # Fetch permission details
).to_list()

# Get user's group memberships with hierarchical permissions
user_groups = await group_service.get_user_groups(user_id)
user_group_permissions = await group_service.get_user_effective_permissions(user_id)

# Check if group name exists in scope
existing_group = await GroupModel.find_one(
    GroupModel.name == "sales_team",
    GroupModel.scope == GroupScope.CLIENT,
    GroupModel.scope_id == client_id
)
```

## Best Practices

### 1. Group Design with Hierarchical Permissions

- **Use hierarchical permissions**: Prefer `user:manage_client` over multiple individual permissions
- **Leverage inheritance**: `user:manage_client` automatically includes `user:read_client` and `user:read_self`
- **Scope appropriately**: Use the narrowest scope that meets team requirements

### 2. Permission Assignment Strategy

- **Start with higher-level permissions**: `group:manage_client` is better than listing all individual permissions
- **Use named dependencies**: `can_manage_groups` is cleaner than manual permission checks
- **Follow hierarchy**: Respect the `all > platform > client > self` hierarchy

### 3. Group Lifecycle

- **Create as needed**: Groups should serve a clear organizational or project purpose
- **Archive completed projects**: Remove project groups when projects complete
- **Update membership**: Keep group membership current with team changes

### 4. Scope Design

- **System groups**: Only for global operational teams (`customer_support`, `engineering`)
- **Platform groups**: For cross-client platform functionality (`platform_marketing`, `platform_support`)
- **Client groups**: For organization-specific teams and projects (`sales_team`, `project_alpha_team`)

### 5. Role + Group Strategy

- **Roles for identity**: Use roles to define "what kind of user" someone is
- **Groups for collaboration**: Use groups to define "who works together"
- **Combined permissions**: Leverage both systems with hierarchical inheritance for comprehensive access control

## API Endpoints

| Endpoint                        | Purpose               | Permissions Required   | Example                                          |
| ------------------------------- | --------------------- | ---------------------- | ------------------------------------------------ |
| `POST /groups/`                 | Create group          | `group:manage_*`       | Creates group in specified scope                 |
| `GET /groups/`                  | List groups           | `group:read_*`         | Returns groups visible to user with auto-scoping |
| `GET /groups/available`         | Get assignable groups | `group:read_*`         | Returns groups user can assign, grouped by scope |
| `GET /groups/{group_id}`        | Get specific group    | `group:read_*`         | Returns group details if user can view           |
| `PUT /groups/{group_id}`        | Update group          | `group:manage_*`       | Updates group if user can manage                 |
| `DELETE /groups/{group_id}`     | Delete group          | `group:manage_*`       | Deletes group if user can manage                 |
| `POST /groups/{id}/members`     | Add group members     | `group:manage_members` | Adds users to group                              |
| `DELETE /groups/{id}/members`   | Remove group members  | `group:manage_members` | Removes users from group                         |
| `GET /groups/{id}/members`      | Get group members     | `group:read_*`         | Returns list of group members                    |
| `GET /groups/users/{id}/groups` | Get user's groups     | `group:read_own`       | Returns groups user belongs to + effective perms |

## Complete Example

### Client Setup with Hierarchical Group Permissions

```python
# 1. Client admin creates departmental sales group
sales_group_data = GroupCreateSchema(
    name="sales_team",
    display_name="Sales Team",
    description="Client organization sales representatives",
    permissions=[
        "user:read_client",        // Hierarchical: includes user:read_self
        "group:read_client",       // Read client groups
        "user:add_member",         // Add new team members
        "group:manage_members",    // Manage group membership
        "client:read_own"          // View own client account (default)
    ],
    scope=GroupScope.CLIENT
)

sales_group = await group_service.create_group(
    group_data=sales_group_data,
    current_user_id=client_admin_id,
    current_client_id=client_admin.client_account_id
)

# 2. Create project-specific group with hierarchical permissions
project_group_data = GroupCreateSchema(
    name="project_alpha_team",
    display_name="Project Alpha Team",
    description="Cross-functional team for Project Alpha initiative",
    permissions=[
        "user:read_client",        // Hierarchical: includes user:read_self
        "group:manage_client",     // Manage client groups (includes read)
        "user:add_member",         // Add project team members
        "group:manage_members",    // Manage project team membership
        "permission:read_client"   // Read client permissions for project setup
    ],
    scope=GroupScope.CLIENT
)

project_group = await group_service.create_group(
    group_data=project_group_data,
    current_user_id=client_admin_id,
    current_client_id=client_admin.client_account_id
)

# 3. Add users to groups (users get permissions from both roles and groups)
await group_service.add_users_to_group(
    group_id=sales_group.id,
    user_ids=[sales_rep_1_id, sales_rep_2_id, sales_manager_id]
)

await group_service.add_users_to_group(
    group_id=project_group.id,
    user_ids=[sales_manager_id, developer_id, designer_id, analyst_id]
)

# 4. Users now have combined permissions:
# - sales_manager_id: Role permissions + Sales Team permissions + Project Alpha permissions
# - All with hierarchical inheritance automatically applied
```

This creates a complete, isolated multi-tier group environment with proper permission boundaries, hierarchical inheritance, and collaborative team organization using clean MongoDB ObjectIds and scope-based isolation.
