# Group System Documentation

## Overview

The OutlabsAuth system implements a **three-tier scoped group architecture** that provides flexible team organization and direct permission management across multiple organizational levels. Groups serve as **permission containers** that complement the role system by allowing fine-grained access control through team-based organization using clean MongoDB ObjectIds and scope fields for tenant isolation.

## Architecture

### Three-Tier Hierarchy

```
SYSTEM GROUPS (Global)
├─ customer_support      # Cross-platform support team
├─ engineering          # Core development team
└─ security_team        # Security and compliance team

PLATFORM GROUPS (Per Platform)
├─ marketing_team       # Platform marketing
├─ sales_team          # Platform sales
├─ analytics_team      # Platform analytics
└─ admin_team          # Platform administration

CLIENT GROUPS (Per Client Organization)
├─ management          # Client leadership team
├─ sales_team         # Client sales representatives
├─ support_staff      # Client customer support
└─ project_managers   # Client project management
```

## Group vs Role Philosophy

### Key Differences

| Aspect                | **Roles**                    | **Groups**                        |
| --------------------- | ---------------------------- | --------------------------------- |
| **Purpose**           | User identity & capabilities | Team organization & collaboration |
| **Permission Source** | Predefined permission sets   | Direct permission assignment      |
| **Relationship**      | User has roles               | User belongs to groups            |
| **Flexibility**       | Structured, template-based   | Dynamic, team-based               |
| **Use Case**          | "What can this user do?"     | "Who works on this project?"      |

### Complementary System

```javascript
// User effective permissions = Role permissions + Group permissions
// (All resolved from ObjectIds to permission names for checking)
user_permissions = [
  ...permissions_from_roles, // e.g., "user:read" from "manager" role
  ...permissions_from_groups, // e.g., "project:alpha:edit" from "project_alpha_team" group
];
```

## Group Structure

### Group Properties

```javascript
{
  "id": "507f1f77bcf86cd799439011",        // MongoDB ObjectId
  "name": "sales_team",                    // Simple group name
  "display_name": "Sales Team",            // Human-readable name
  "description": "Handles all sales activities and client relationships",
  "permissions": [                         // Permission ObjectIds (resolved to names for checking)
    "507f1f77bcf86cd799439015",            // crm:clients:read
    "507f1f77bcf86cd799439016",            // crm:clients:update
    "507f1f77bcf86cd799439017",            // crm:deals:create
    "507f1f77bcf86cd799439018"             // crm:reports:read
  ],
  "scope": "client",                       // "system" | "platform" | "client"
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Foreign key to owner
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

## Group Examples

### System Groups

```javascript
// Customer Support (cross-platform)
{
  "id": "507f1f77bcf86cd799439011",
  "name": "customer_support",
  "display_name": "Customer Support Team",
  "description": "Provides support across all platforms and clients",
  "scope": "system",
  "scope_id": null,
  "permissions": [
    "507f1f77bcf86cd799439019",  // support:tickets:read
    "507f1f77bcf86cd799439020",  // support:tickets:update
    "507f1f77bcf86cd799439021",  // user:read
    "507f1f77bcf86cd799439022",  // client_account:read
    "507f1f77bcf86cd799439023"   // support:cross_client
  ]
}

// Engineering Team (system-wide access)
{
  "id": "507f1f77bcf86cd799439012",
  "name": "engineering",
  "display_name": "Engineering Team",
  "description": "Core development and infrastructure team",
  "scope": "system",
  "scope_id": null,
  "permissions": [
    "system:infrastructure:manage",
    "system:deploy:production",
    "system:logs:read",
    "platform:*",
    "client:*"
  ]
}
```

### Platform Groups

```javascript
// Platform Marketing Team
{
  "id": "507f1f77bcf86cd799439013",
  "name": "marketing_team",
  "display_name": "Marketing Team",
  "description": "Platform marketing and growth initiatives",
  "scope": "platform",
  "scope_id": "real_estate_platform",
  "permissions": [
    "platform:analytics:view",
    "platform:campaigns:manage",
    "platform:reports:create",
    "client:metrics:read"
  ]
}

// Platform Sales Team
{
  "id": "507f1f77bcf86cd799439014",
  "name": "sales_team",
  "display_name": "Platform Sales Team",
  "description": "Responsible for acquiring new client organizations",
  "scope": "platform",
  "scope_id": "real_estate_platform",
  "permissions": [
    "platform:leads:manage",
    "client_account:create",
    "client_account:read",
    "platform:pricing:view"
  ]
}
```

### Client Groups

```javascript
// Client Sales Team (for Acme Real Estate)
{
  "id": "507f1f77bcf86cd799439015",
  "name": "sales_team",
  "display_name": "Sales Team",
  "description": "Acme Real Estate sales representatives",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",  // Acme's client_account_id
  "permissions": [
    "client:listings:create",
    "client:listings:update",
    "client:clients:manage",
    "client:contracts:create",
    "client:reports:sales"
  ]
}

// Project Team (for specific project)
{
  "id": "507f1f77bcf86cd799439016",
  "name": "project_alpha_team",
  "display_name": "Project Alpha Team",
  "description": "Team working on the Alpha project initiative",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "permissions": [
    "client:project:alpha:read",
    "client:project:alpha:update",
    "client:documents:alpha:manage",
    "client:meetings:alpha:schedule"
  ]
}
```

## Permission Model

### Who Can Create Groups

| User Type          | Can Create         | Scope                            | Restrictions                 |
| ------------------ | ------------------ | -------------------------------- | ---------------------------- |
| **Super Admin**    | ✅ Any group       | `system`, `platform`, `client`   | No restrictions              |
| **Platform Admin** | ✅ Platform groups | `platform` (their platform only) | Only within their platform   |
| **Client Admin**   | ✅ Client groups   | `client` (their client only)     | Only within their client org |
| **Team Lead**      | ✅ Client groups   | `client` (their client only)     | If granted group:create      |

### Who Can Assign Group Membership

| User Type          | Can Add Members To                   | Examples                                   |
| ------------------ | ------------------------------------ | ------------------------------------------ |
| **Super Admin**    | Any group                            | All system, platform, and client groups    |
| **Platform Admin** | Platform groups + some system groups | Platform groups + customer_support         |
| **Client Admin**   | Client groups                        | All groups within their client             |
| **Group Manager**  | Groups they manage                   | If granted group:manage_members permission |

### Group Visibility

| User Type          | Can View                                     |
| ------------------ | -------------------------------------------- |
| **Super Admin**    | All groups across all scopes                 |
| **Platform Admin** | System groups + their platform groups        |
| **Client Admin**   | System groups + their client groups          |
| **Regular User**   | Groups they belong to + public client groups |

## Usage Patterns

### 1. Creating Departmental Groups

When organizing teams within a client organization:

```python
# Create sales team group
sales_group_data = GroupCreateSchema(
    name="sales_team",
    display_name="Sales Team",
    description="Handles all sales activities and client relationships",
    permissions=[
        "client:listings:create",
        "client:listings:update",
        "client:clients:manage",
        "client:reports:sales"
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
# Create project-specific group
project_group_data = GroupCreateSchema(
    name="project_alpha_team",
    display_name="Project Alpha Team",
    description="Cross-functional team for Project Alpha",
    permissions=[
        "client:project:alpha:read",
        "client:project:alpha:update",
        "client:documents:alpha:manage",
        "client:meetings:alpha:schedule"
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
# Create platform analytics group
analytics_group_data = GroupCreateSchema(
    name="analytics_team",
    display_name="Analytics Team",
    description="Platform-wide analytics and reporting team",
    permissions=[
        "platform:analytics:view",
        "platform:reports:create",
        "client:metrics:read",
        "platform:dashboard:manage"
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

### Permission Aggregation

Users can have both roles and group memberships, with permissions combined:

```python
# User has "manager" role + belongs to "sales_team" group
user_effective_permissions = await user_service.get_user_effective_permissions(user_id)

# Returns combined permissions:
# From "manager" role: ["user:read", "user:update", "reports:view"]
# From "sales_team" group: ["client:listings:create", "client:clients:manage"]
# Final: ["user:read", "user:update", "reports:view", "client:listings:create", "client:clients:manage"]
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
    // From "manager" role:
    "user:read", "user:update", "reports:view",

    // From "sales_team" group:
    "client:listings:create", "client:clients:manage",

    // From "project_alpha_team" group:
    "client:project:alpha:update", "client:documents:alpha:manage"
  ]
}
```

## Frontend Integration

### Group Creation UI

The frontend provides intuitive group management:

```javascript
// Frontend form data
{
  name: "marketing_team",
  display_name: "Marketing Team",
  description: "Handles marketing campaigns and brand management",
  permissions: [
    "client:campaigns:create",
    "client:campaigns:manage",
    "client:social_media:post",
    "client:analytics:marketing"
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
      "scope_id": null
    }
  ],
  "platform_groups": [
    {
      "id": "507f1f77bcf86cd799439013",
      "name": "analytics_team",
      "display_name": "Analytics Team",
      "scope": "platform",
      "scope_id": "real_estate_platform"
    }
  ],
  "client_groups": [
    {
      "id": "507f1f77bcf86cd799439015",
      "name": "sales_team",
      "display_name": "Sales Team",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
    },
    {
      "id": "507f1f77bcf86cd799439016",
      "name": "project_alpha_team",
      "display_name": "Project Alpha Team",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
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

### Namespace Isolation

- **No group collisions**: Groups are isolated by scope + scope_id
- **Tenant isolation**: Client A's "sales_team" is completely separate from Client B's "sales_team"
- **Clear boundaries**: Platform groups cannot access client data without explicit permissions

### Permission Validation

- **Permission checks**: Only valid permissions can be assigned to groups
- **Scope validation**: Group permissions must be appropriate for the group's scope
- **Context awareness**: Backend validates permissions against user's capabilities

### Unique Constraints

- **Name uniqueness**: Group names must be unique within their scope (name + scope + scope_id)
- **Proper isolation**: Same group name can exist in different scopes without conflict

## Database Queries

### Efficient Group Lookups

```python
# Get all client groups for a specific client
client_groups = await GroupModel.find(
    GroupModel.scope == GroupScope.CLIENT,
    GroupModel.scope_id == client_id
).to_list()

# Get user's group memberships with permissions
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

### 1. Group Naming

- **Functional names**: `"sales_team"`, `"project_alpha_team"`, `"marketing_team"`
- **Clear display names**: `"Sales Team"`, `"Project Alpha Team"`, `"Marketing Department"`
- **Consistent patterns**: Use similar naming conventions across scopes

### 2. Permission Assignment

- **Principle of least privilege**: Only assign necessary permissions to groups
- **Purpose-driven**: Align permissions with the group's specific function
- **Regular audits**: Review group permissions as projects evolve

### 3. Group Lifecycle

- **Create as needed**: Groups should serve a clear organizational purpose
- **Archive completed projects**: Remove project groups when projects complete
- **Update membership**: Keep group membership current with team changes

### 4. Scope Design

- **System groups**: Only for global operational teams (support, engineering)
- **Platform groups**: For cross-client platform functionality
- **Client groups**: For organization-specific teams and projects

### 5. Role + Group Strategy

- **Roles for identity**: Use roles to define "what kind of user" someone is
- **Groups for collaboration**: Use groups to define "who works together"
- **Combined permissions**: Leverage both systems for comprehensive access control

## API Endpoints

| Endpoint                        | Purpose               | Example                                          |
| ------------------------------- | --------------------- | ------------------------------------------------ |
| `POST /groups/`                 | Create group          | Creates group in specified scope                 |
| `GET /groups/`                  | List groups           | Returns groups visible to user                   |
| `GET /groups/available`         | Get assignable groups | Returns groups user can assign, grouped by scope |
| `GET /groups/{group_id}`        | Get specific group    | Returns group details if user can view           |
| `PUT /groups/{group_id}`        | Update group          | Updates group if user can manage                 |
| `DELETE /groups/{group_id}`     | Delete group          | Deletes group if user can manage                 |
| `POST /groups/{id}/members`     | Add group members     | Adds users to group                              |
| `DELETE /groups/{id}/members`   | Remove group members  | Removes users from group                         |
| `GET /groups/{id}/members`      | Get group members     | Returns list of group members                    |
| `GET /groups/users/{id}/groups` | Get user's groups     | Returns groups user belongs to + effective perms |

## Complete Example

### Lead Generation Company Scenario

```python
# System Level: Lead company internal teams
customer_support_group = await group_service.create_group(
    group_data=GroupCreateSchema(
        name="customer_support",
        display_name="Customer Support Team",
        description="Provides support across all platforms and clients",
        permissions=[
            "support:tickets:read",
            "support:tickets:update",
            "platform:support:all_clients"
        ],
        scope=GroupScope.SYSTEM
    ),
    current_user_id=super_admin_id
)

# Platform Level: Corporate client teams (RE/MAX HQ)
remax_marketing_group = await group_service.create_group(
    group_data=GroupCreateSchema(
        name="marketing_team",
        display_name="RE/MAX Marketing Team",
        description="Corporate marketing team for RE/MAX brand",
        permissions=[
            "platform:brand:manage",
            "platform:campaigns:corporate",
            "client:analytics:all_franchises"
        ],
        scope=GroupScope.PLATFORM
    ),
    current_user_id=platform_admin_id,
    scope_id="remax_platform"
)

# Client Level: Individual franchise teams (RE/MAX Downtown)
franchise_sales_group = await group_service.create_group(
    group_data=GroupCreateSchema(
        name="sales_team",
        display_name="Sales Team",
        description="RE/MAX Downtown sales representatives",
        permissions=[
            "client:listings:create",
            "client:listings:update",
            "client:leads:manage",
            "client:reports:sales"
        ],
        scope=GroupScope.CLIENT
    ),
    current_user_id=franchise_admin_id,
    current_client_id=franchise_client_id
)

# Perfect isolation: Each level operates independently
# Customer support can help all clients
# RE/MAX HQ marketing can manage corporate campaigns
# Downtown franchise can only manage their own listings
```

This creates a complete, isolated multi-tier group environment with proper permission boundaries and collaborative team organization using clean MongoDB ObjectIds and scope-based isolation.
