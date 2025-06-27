# Group Routes Documentation

## Overview

The Group Routes provide a comprehensive API for managing scoped groups and group memberships within the three-tier authentication system. This module handles all CRUD operations for groups, group membership management, and provides endpoints for retrieving user group associations with effective permissions. Groups serve as **permission containers** that complement the role system through direct permission assignment rather than role inheritance.

**Base URL:** `/v1/groups`  
**Tags:** Group Management

## Architecture

### Three-Tier Scoped Groups

Groups are organized in a three-tier hierarchy with proper isolation and direct permission assignment:

```
SYSTEM GROUPS (Global)
├─ customer_support      # Cross-platform support team
├─ engineering          # Core development team
└─ security_team        # Security and compliance team

PLATFORM GROUPS (Per Platform)
├─ marketing_team       # Platform marketing
├─ analytics_team      # Platform analytics
└─ admin_team          # Platform administration

CLIENT GROUPS (Per Client Organization)
├─ sales_team         # Client sales representatives
├─ project_alpha_team # Project-specific team
└─ management         # Client leadership team
```

### Groups vs Roles Philosophy

| Aspect                | **Roles**                    | **Groups**                        |
| --------------------- | ---------------------------- | --------------------------------- |
| **Purpose**           | User identity & capabilities | Team organization & collaboration |
| **Permission Source** | Predefined permission sets   | Direct permission assignment      |
| **Relationship**      | User has roles               | User belongs to groups            |
| **Use Case**          | "What can this user do?"     | "Who works on this project?"      |

## Authentication & Authorization

All endpoints require authentication and are protected by dependency functions that implement hierarchical permission checking:

- **Read Access:** Requires one of: `group:read_all`, `group:read_platform`, or `group:read_client`
- **Manage Access:** Requires one of: `group:manage_all`, `group:manage_platform`, or `group:manage_client`
- **Member Management:** Uses the same manage access permissions as above

### Hierarchical Permission System

The permission system follows a hierarchical structure where higher-level permissions automatically include lower-level ones:

- `group:manage_all` → Includes all group permissions (global admin)
- `group:manage_platform` → Includes `group:manage_client`, `group:read_platform`, `group:read_client`
- `group:manage_client` → Includes `group:read_client`
- `group:read_all` → Includes `group:read_platform`, `group:read_client`
- `group:read_platform` → Includes `group:read_client`
- `group:read_client` → Base client-level read access

### Scope-Based Access Control

- **Super Admins:** Can create/manage groups at all scopes
- **Platform Admins:** Can create/manage groups within their platform only
- **Client Admins:** Can create/manage groups within their client only
- **Team Leads:** Can manage groups if granted appropriate permissions

## Endpoints

### 1. Create Scoped Group

Creates a new group within a specific scope with direct permission assignment.

**Endpoint:** `POST /v1/groups/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_groups` (requires `group:manage_all`, `group:manage_platform`, or `group:manage_client`)

**Query Parameters:**

- `scope_id` (optional, string) - Platform ID or Client ID for scoped groups (auto-determined from user context if not provided)

**Request Body:**

```json
{
  "name": "sales_team",
  "display_name": "Sales Team",
  "description": "Handles all sales activities and client relationships",
  "permissions": ["client:listings:create", "client:listings:update", "client:clients:manage", "client:reports:sales"],
  "scope": "client"
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "sales_team",
  "display_name": "Sales Team",
  "description": "Handles all sales activities and client relationships",
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "client:listings:create",
      "display_name": "Create Client Listings",
      "description": "Create new listings within client scope"
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "name": "client:listings:update",
      "display_name": "Update Client Listings",
      "description": "Update existing listings within client scope"
    }
  ],
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "is_active": true,
  "created_by_user_id": "507f1f77bcf86cd799439013",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data or scope validation failed
- `403 Forbidden` - Insufficient permissions or invalid scope access
- `401 Unauthorized` - Invalid access token
- `409 Conflict` - Group with this name already exists in scope
- `500 Internal Server Error` - Server error during group creation

**Example Requests:**

```bash
# System group (super admin only)
curl -X POST "https://api.example.com/v1/groups/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "customer_support",
       "display_name": "Customer Support Team",
       "description": "Provides support across all platforms and clients",
       "permissions": [
         "support:tickets:read",
         "support:tickets:update",
         "platform:support:all_clients"
       ],
       "scope": "system"
     }'

# Platform group
curl -X POST "https://api.example.com/v1/groups/?scope_id=real_estate_platform" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "marketing_team",
       "display_name": "Marketing Team",
       "description": "Platform marketing and growth initiatives",
       "permissions": [
         "platform:analytics:view",
         "platform:campaigns:manage",
         "client:metrics:read"
       ],
       "scope": "platform"
     }'

# Client group (auto-scoped to user's client)
curl -X POST "https://api.example.com/v1/groups/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "sales_team",
       "display_name": "Sales Team",
       "description": "Client sales representatives",
       "permissions": [
         "client:listings:create",
         "client:clients:manage"
       ],
       "scope": "client"
     }'
```

### 2. Get Groups with Scope Filtering

Retrieves a paginated list of groups with optional scope filtering.

**Endpoint:** `GET /v1/groups/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_groups` (requires `group:read_all`, `group:read_platform`, or `group:read_client`)

**Query Parameters:**

- `skip` (optional, integer, default: 0, min: 0) - Number of groups to skip for pagination
- `limit` (optional, integer, default: 100, min: 1, max: 1000) - Maximum number of groups to return
- `scope` (optional, string) - Filter by group scope (`system`, `platform`, `client`)
- `scope_id` (optional, string) - Filter by specific scope ID

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "507f1f77bcf86cd799439012",
    "name": "sales_team",
    "display_name": "Sales Team",
    "description": "Client sales representatives",
    "permissions": [
      {
        "id": "507f1f77bcf86cd799439020",
        "name": "client:listings:create",
        "display_name": "Create Client Listings",
        "description": "Create new listings within client scope"
      }
    ],
    "scope": "client",
    "scope_id": "685a5f2e82e92ad29111a6a9",
    "is_active": true,
    "created_by_user_id": "507f1f77bcf86cd799439013",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "507f1f77bcf86cd799439014",
    "name": "project_alpha_team",
    "display_name": "Project Alpha Team",
    "description": "Cross-functional team for Project Alpha",
    "permissions": ["client:project:alpha:read", "client:project:alpha:update"],
    "scope": "client",
    "scope_id": "685a5f2e82e92ad29111a6a9",
    "created_by_user_id": "507f1f77bcf86cd799439013",
    "created_at": "2024-01-15T11:00:00Z"
  }
]
```

**Error Responses:**

- `400 Bad Request` - Invalid query parameters
- `401 Unauthorized` - Invalid access token
- `403 Forbidden` - Insufficient permissions

**Example Requests:**

```bash
# Get all groups user can view
curl -X GET "https://api.example.com/v1/groups/" \
     -H "Authorization: Bearer <access_token>"

# Get only client groups for specific client
curl -X GET "https://api.example.com/v1/groups/?scope=client&scope_id=685a5f2e82e92ad29111a6a9" \
     -H "Authorization: Bearer <access_token>"

# Get platform groups
curl -X GET "https://api.example.com/v1/groups/?scope=platform&scope_id=real_estate_platform" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Available Groups for Assignment

Retrieves groups that the current user can assign to others, grouped by scope.

**Endpoint:** `GET /v1/groups/available`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `require_admin` (any admin role)

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "system_groups": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "customer_support",
      "display_name": "Customer Support Team",
      "description": "Cross-platform support team",
      "scope": "system",
      "scope_id": null,
      "is_active": true,
      "permissions": [
        {
          "id": "507f1f77bcf86cd799439030",
          "name": "support:tickets:read",
          "display_name": "Read Support Tickets",
          "description": "Read support tickets across all platforms"
        }
      ],
      "created_at": "2024-01-15T09:00:00Z",
      "updated_at": "2024-01-15T09:00:00Z"
    }
  ],
  "platform_groups": [
    {
      "id": "507f1f77bcf86cd799439013",
      "name": "analytics_team",
      "display_name": "Analytics Team",
      "description": "Platform analytics team",
      "scope": "platform",
      "scope_id": "real_estate_platform",
      "is_active": true,
      "permissions": [
        {
          "id": "507f1f77bcf86cd799439031",
          "name": "platform:analytics:view",
          "display_name": "View Platform Analytics",
          "description": "View analytics across platform"
        }
      ],
      "created_at": "2024-01-15T09:30:00Z",
      "updated_at": "2024-01-15T09:30:00Z"
    }
  ],
  "client_groups": [
    {
      "id": "507f1f77bcf86cd799439015",
      "name": "sales_team",
      "display_name": "Sales Team",
      "description": "Client sales team",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "is_active": true,
      "permissions": [
        {
          "id": "507f1f77bcf86cd799439020",
          "name": "client:listings:create",
          "display_name": "Create Client Listings",
          "description": "Create new listings within client scope"
        }
      ],
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z"
    },
    {
      "id": "507f1f77bcf86cd799439016",
      "name": "project_alpha_team",
      "display_name": "Project Alpha Team",
      "description": "Project team",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "permissions": ["client:project:alpha:read", "client:project:alpha:update"]
    }
  ]
}
```

**Error Responses:**

- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/available" \
     -H "Authorization: Bearer <access_token>"
```

### 4. Get Group by ID

Retrieves a specific group by its MongoDB ObjectId.

**Endpoint:** `GET /v1/groups/{group_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_groups` (requires `group:read_all`, `group:read_platform`, or `group:read_client`)

**Path Parameters:**

- `group_id` (required, string) - The MongoDB ObjectId of the group

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "sales_team",
  "display_name": "Sales Team",
  "description": "Client sales representatives",
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "client:listings:create",
      "display_name": "Create Client Listings",
      "description": "Create new listings within client scope"
    }
  ],
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "is_active": true,
  "created_by_user_id": "507f1f77bcf86cd799439013",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid group ID format
- `404 Not Found` - Group not found or not accessible by user
- `401 Unauthorized` - Invalid access token
- `403 Forbidden` - Insufficient permissions

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/507f1f77bcf86cd799439012" \
     -H "Authorization: Bearer <access_token>"
```

### 5. Update Group

Updates an existing group's information and permissions.

**Endpoint:** `PUT /v1/groups/{group_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_groups` (requires `group:manage_all`, `group:manage_platform`, or `group:manage_client`)

**Path Parameters:**

- `group_id` (required, string) - The MongoDB ObjectId of the group

**Request Body:**

```json
{
  "display_name": "Senior Sales Team",
  "description": "Updated sales team description",
  "permissions": ["client:listings:create", "client:listings:update", "client:clients:manage", "client:reports:sales", "client:contracts:create"]
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "sales_team",
  "display_name": "Senior Sales Team",
  "description": "Updated sales team description",
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "client:listings:create",
      "display_name": "Create Client Listings",
      "description": "Create new listings within client scope"
    },
    {
      "id": "507f1f77bcf86cd799439025",
      "name": "client:contracts:create",
      "display_name": "Create Client Contracts",
      "description": "Create contracts within client scope"
    }
  ],
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "is_active": true,
  "created_by_user_id": "507f1f77bcf86cd799439013",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T15:30:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data or group ID format
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid access token
- `500 Internal Server Error` - Server error during update

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/groups/507f1f77bcf86cd799439012" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "display_name": "Senior Sales Team",
       "description": "Updated sales team description",
       "permissions": [
         "client:listings:create",
         "client:listings:update",
         "client:clients:manage",
         "client:reports:sales",
         "client:contracts:create"
       ]
     }'
```

### 6. Delete Group

Deletes a group and removes all users from the group.

**Endpoint:** `DELETE /v1/groups/{group_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_groups` (requires `group:manage_all`, `group:manage_platform`, or `group:manage_client`)

**Path Parameters:**

- `group_id` (required, string) - The MongoDB ObjectId of the group

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `400 Bad Request` - Invalid group ID format
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/groups/507f1f77bcf86cd799439012" \
     -H "Authorization: Bearer <access_token>"
```

### 7. Add Users to Group

Adds users to a specific group for team collaboration.

**Endpoint:** `POST /v1/groups/{group_id}/members`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_groups` (requires `group:manage_all`, `group:manage_platform`, or `group:manage_client`)

**Path Parameters:**

- `group_id` (required, string) - The MongoDB ObjectId of the group

**Request Body:**

```json
{
  "user_ids": ["507f1f77bcf86cd799439013", "507f1f77bcf86cd799439014"]
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "message": "Successfully added 2 users to group"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data or group ID format
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid access token
- `500 Internal Server Error` - Server error during operation

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/groups/507f1f77bcf86cd799439012/members" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "user_ids": [
         "507f1f77bcf86cd799439013",
         "507f1f77bcf86cd799439014"
       ]
     }'
```

### 8. Remove Users from Group

Removes users from a specific group.

**Endpoint:** `DELETE /v1/groups/{group_id}/members`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_groups` (requires `group:manage_all`, `group:manage_platform`, or `group:manage_client`)

**Path Parameters:**

- `group_id` (required, string) - The MongoDB ObjectId of the group

**Request Body:**

```json
{
  "user_ids": ["507f1f77bcf86cd799439013"]
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "message": "Successfully removed 1 users from group"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data or group ID format
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid access token
- `500 Internal Server Error` - Server error during operation

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/groups/507f1f77bcf86cd799439012/members" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "user_ids": [
         "507f1f77bcf86cd799439013"
       ]
     }'
```

### 9. Get Group Members

Retrieves all members of a specific group with their basic information.

**Endpoint:** `GET /v1/groups/{group_id}/members`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_groups` (requires `group:read_all`, `group:read_platform`, or `group:read_client`)

**Path Parameters:**

- `group_id` (required, string) - The MongoDB ObjectId of the group

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "group_id": "507f1f77bcf86cd799439012",
  "group_name": "Sales Team",
  "group_scope": "client",
  "members": [
    {
      "id": "507f1f77bcf86cd799439013",
      "email": "sarah@acme.com",
      "first_name": "Sarah",
      "last_name": "Johnson",
      "status": "active"
    },
    {
      "id": "507f1f77bcf86cd799439014",
      "email": "mike@acme.com",
      "first_name": "Mike",
      "last_name": "Chen",
      "status": "active"
    }
  ]
}
```

**Error Responses:**

- `400 Bad Request` - Invalid group ID format
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/507f1f77bcf86cd799439012/members" \
     -H "Authorization: Bearer <access_token>"
```

### 10. Get User Groups

Retrieves all groups that a user belongs to, along with their effective permissions from group memberships.

**Endpoint:** `GET /v1/groups/users/{user_id}/groups`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_groups` (requires `group:read_all`, `group:read_platform`, or `group:read_client`)

**Path Parameters:**

- `user_id` (required, string) - The MongoDB ObjectId of the user

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "user_id": "507f1f77bcf86cd799439013",
  "groups": [
    {
      "id": "507f1f77bcf86cd799439012",
      "name": "sales_team",
      "display_name": "Sales Team",
      "description": "Client sales representatives",
      "permissions": [
        {
          "id": "507f1f77bcf86cd799439020",
          "name": "client:listings:create",
          "display_name": "Create Client Listings",
          "description": "Create new listings within client scope"
        }
      ],
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "507f1f77bcf86cd799439016",
      "name": "project_alpha_team",
      "display_name": "Project Alpha Team",
      "description": "Cross-functional project team",
      "permissions": ["client:project:alpha:read", "client:project:alpha:update"],
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "created_at": "2024-01-15T11:00:00Z"
    }
  ],
  "effective_permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "client:listings:create",
      "display_name": "Create Client Listings",
      "description": "Create new listings within client scope"
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "name": "client:project:alpha:read",
      "display_name": "Read Project Alpha",
      "description": "Read access to Project Alpha resources"
    }
  ]
}
```

**Error Responses:**

- `400 Bad Request` - Invalid user ID format
- `404 Not Found` - User not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid access token

**Access Control:**

- Users can view their own groups
- Admin users can view any user's groups within their scope
- Proper scope isolation is enforced

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/users/507f1f77bcf86cd799439013/groups" \
     -H "Authorization: Bearer <access_token>"
```

## Permission Requirements

### Required Permissions by Endpoint

| Endpoint                            | Method | Required Dependencies |
| ----------------------------------- | ------ | --------------------- |
| `/v1/groups/`                       | GET    | `can_read_groups`     |
| `/v1/groups/`                       | POST   | `can_manage_groups`   |
| `/v1/groups/available`              | GET    | `require_admin`       |
| `/v1/groups/{group_id}`             | GET    | `can_read_groups`     |
| `/v1/groups/{group_id}`             | PUT    | `can_manage_groups`   |
| `/v1/groups/{group_id}`             | DELETE | `can_manage_groups`   |
| `/v1/groups/{group_id}/members`     | POST   | `can_manage_groups`   |
| `/v1/groups/{group_id}/members`     | DELETE | `can_manage_groups`   |
| `/v1/groups/{group_id}/members`     | GET    | `can_read_groups`     |
| `/v1/groups/users/{user_id}/groups` | GET    | `can_read_groups`     |

### Dependency Function Mappings

- `can_read_groups` requires any of: `group:read_all`, `group:read_platform`, `group:read_client`
- `can_manage_groups` requires any of: `group:manage_all`, `group:manage_platform`, `group:manage_client`
- `require_admin` requires any admin role: `super_admin`, `admin`, or `client_admin`

## Scope-Based Access Control

### Super Admins (`group:manage_all`)

- Can access and manage groups across all scopes
- No restrictions on group operations
- Can view and manage any user's group memberships

### Platform Admins (`group:manage_platform`)

- Can manage groups within their platform scope only
- Can access system groups for assignment
- Cannot access other platform's groups

### Client Admins (`group:manage_client`)

- Can manage groups within their client scope only
- Can access system groups for assignment
- Cannot access other client's groups

### Team Members (`group:read_client`)

- Can view groups they belong to
- Cannot modify group memberships (requires manage permissions)
- Can view their own effective permissions through groups

## Data Models

### GroupCreateSchema

```json
{
  "name": "string (required)",
  "display_name": "string (required)",
  "description": "string (optional)",
  "permissions": ["string"] (required),
  "scope": "system | platform | client (required)"
}
```

### GroupUpdateSchema

```json
{
  "name": "string (optional)",
  "display_name": "string (optional)",
  "description": "string (optional)",
  "permissions": ["string"] (optional),
  "is_active": "bool (optional)"
}
```

### GroupResponseSchema

```json
{
  "id": "string (MongoDB ObjectId)",
  "name": "string",
  "display_name": "string",
  "description": "string",
  "permissions": [
    {
      "id": "string (MongoDB ObjectId)",
      "name": "string",
      "display_name": "string",
      "description": "string"
    }
  ],
  "scope": "system | platform | client",
  "scope_id": "string | null",
  "is_active": "bool",
  "created_by_user_id": "string | null",
  "created_by_client_id": "string | null",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

### AvailableGroupsResponseSchema

```json
{
  "system_groups": ["GroupResponseSchema"],
  "platform_groups": ["GroupResponseSchema"],
  "client_groups": ["GroupResponseSchema"]
}
```

### GroupMembershipSchema

```json
{
  "user_ids": ["string (MongoDB ObjectId)"]
}
```

### GroupMembersResponseSchema

```json
{
  "group_id": "string",
  "group_name": "string",
  "group_scope": "string",
  "members": [
    {
      "id": "string",
      "email": "string",
      "first_name": "string",
      "last_name": "string",
      "status": "string"
    }
  ]
}
```

### UserGroupsResponseSchema

```json
{
  "user_id": "string",
  "groups": ["GroupResponseSchema"],
  "effective_permissions": [
    {
      "id": "string (MongoDB ObjectId)",
      "name": "string",
      "display_name": "string",
      "description": "string"
    }
  ]
}
```

## Error Handling

All endpoints follow consistent error response format:

```json
{
  "detail": "Error message description"
}
```

### Common HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Group created or members added successfully
- `204 No Content` - Group deleted successfully
- `400 Bad Request` - Invalid request data or parameters
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions or scope access denied
- `404 Not Found` - Group or user not found
- `409 Conflict` - Group with name already exists in scope
- `500 Internal Server Error` - Server error

### Scope-Specific Error Scenarios

**403 Forbidden (Scope Access):**

```json
{
  "detail": "Cannot create platform groups - insufficient platform access"
}
```

**409 Conflict (Scoped Uniqueness):**

```json
{
  "detail": "Group 'sales_team' already exists in this client scope"
}
```

**400 Bad Request (Permission Validation):**

```json
{
  "detail": "Permission 'invalid:permission' is not valid for client scope"
}
```

## Best Practices

### Group Design

1. **Purpose-Driven:** Create groups for specific team functions or projects
2. **Scope Appropriately:** Use the most restrictive scope that meets needs
3. **Permission Focus:** Assign permissions directly rather than through roles
4. **Lifecycle Management:** Archive groups when projects complete

### Team Organization

1. **Departmental Groups:** For ongoing organizational functions (sales_team, marketing_team)
2. **Project Groups:** For temporary cross-functional teams (project_alpha_team)
3. **Operational Groups:** For ongoing operational functions (support_team)
4. **Clear Naming:** Use descriptive, functional names

### Permission Management

1. **Direct Assignment:** Assign permissions directly to groups
2. **Principle of Least Privilege:** Only assign necessary permissions
3. **Regular Audits:** Review group permissions as business needs change
4. **Documentation:** Clearly describe group purpose and permissions

### API Usage

1. **Use Available Endpoint:** Check `/available` to get groups user can assign
2. **Handle Scope Contexts:** Let backend auto-determine scope_id when possible
3. **Bulk Operations:** Use bulk member add/remove for efficiency
4. **Error Handling:** Handle scope-related 403 errors gracefully

## Real-World Examples

### Lead Generation Company Group Setup

```bash
# System Level: Global operational teams
curl -X POST "https://api.example.com/v1/groups/" \
     -d '{
       "name": "customer_support",
       "display_name": "Customer Support Team",
       "permissions": ["support:tickets:read", "platform:support:all_clients"],
       "scope": "system"
     }'

# Platform Level: RE/MAX corporate teams
curl -X POST "https://api.example.com/v1/groups/?scope_id=remax_platform" \
     -d '{
       "name": "marketing_team",
       "display_name": "RE/MAX Marketing Team",
       "permissions": ["platform:brand:manage", "client:analytics:all_franchises"],
       "scope": "platform"
     }'

# Client Level: Individual franchise teams
curl -X POST "https://api.example.com/v1/groups/" \
     -d '{
       "name": "sales_team",
       "display_name": "Sales Team",
       "permissions": ["client:listings:create", "client:leads:manage"],
       "scope": "client"
     }'
```

### Project Team Management

```bash
# 1. Create project-specific group
curl -X POST "https://api.example.com/v1/groups/" \
     -d '{
       "name": "project_alpha_team",
       "permissions": ["client:project:alpha:read", "client:project:alpha:update"],
       "scope": "client"
     }'

# 2. Add cross-functional team members
curl -X POST "https://api.example.com/v1/groups/507f1f77bcf86cd799439012/members" \
     -d '{"user_ids": ["dev_id", "designer_id", "analyst_id"]}'

# 3. When project completes, remove group
curl -X DELETE "https://api.example.com/v1/groups/507f1f77bcf86cd799439012"
```

## Integration Notes

### User Permission Aggregation

Groups work alongside roles to provide comprehensive permission management:

```javascript
// User effective permissions = Role permissions + Group permissions
const userEffectivePermissions = [
  ...permissionsFromRoles, // e.g., "user:read" from "manager" role
  ...permissionsFromGroups, // e.g., "client:project:alpha:edit" from project group
];
```

### Frontend Integration

```javascript
// Check user's group-based permissions
const userPermissions = userStore.effectivePermissions;
const userGroups = userStore.groups;

// Project-specific access
const canEditProjectAlpha = userPermissions.some((p) => p.name === "client:project:alpha:update");
const isProjectAlphaMember = userGroups.some((g) => g.name === "project_alpha_team");

// Team-based UI
{
  isProjectAlphaMember && <ProjectAlphaTools />;
}
```

### Role vs Group Strategy

- **Roles:** Define "what kind of user" someone is (manager, developer, sales_rep)
- **Groups:** Define "who works together" on specific functions/projects
- **Combined:** Users get comprehensive permissions for their role + team responsibilities
