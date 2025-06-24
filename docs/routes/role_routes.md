# Role Routes Documentation

## Overview

The Role Routes provide a comprehensive API for managing roles within the three-tier authentication system. Roles serve as collections of permissions that can be assigned to users or groups, enabling flexible and scalable access control across system, platform, and client scopes. This module handles full CRUD operations for roles with proper tenant isolation and permission validation.

**Base URL:** `/v1/roles`  
**Tags:** Role Management

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Permission:** `role:read` (required for all endpoints)
- **Additional Permissions:** Specific endpoints require additional permissions as noted below

## Three-Tier Role System

The system implements a hierarchical role architecture with three distinct scopes:

### System Roles (Global)

- **Scope:** `system`
- **Access:** Available across all platforms and clients
- **Examples:** `super_admin`, `basic_user`
- **Management:** Only super admins can create/modify

### Platform Roles (Per Platform)

- **Scope:** `platform`
- **Access:** Available within a specific platform and its clients
- **Examples:** `admin`, `support`, `sales`
- **Management:** Platform admins and super admins can create/modify

### Client Roles (Per Client)

- **Scope:** `client`
- **Access:** Available only within a specific client account
- **Examples:** `admin`, `manager`, `sales_rep`
- **Management:** Client admins and higher can create/modify

### Role Identification

- **ID Format:** MongoDB ObjectId (e.g., `507f1f77bcf86cd799439011`)
- **Uniqueness:** Role names are unique within their scope + scope_id combination
- **Tenant Isolation:** Proper isolation ensures roles don't leak across boundaries

## Endpoints

### 1. Create Role

Creates a new role in the system with specified permissions and scope.

**Endpoint:** `POST /v1/roles/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`, `role:create`

**Request Body:**

```json
{
  "name": "admin",
  "display_name": "Client Administrator",
  "description": "Administrative role for client account management",
  "permissions": ["user:create", "user:read", "user:update", "group:manage_members"],
  "scope": "client",
  "is_assignable_by_main_client": true
}
```

**Scope Determination:**

- **System Scope:** Only super admins can create system roles
- **Platform Scope:** Platform admins can create platform roles (scope_id auto-detected)
- **Client Scope:** Client admins can create client roles (scope_id auto-detected from user's client account)

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "admin",
  "display_name": "Client Administrator",
  "description": "Administrative role for client account management",
  "permissions": ["user:create", "user:read", "user:update", "group:manage_members"],
  "scope": "client",
  "scope_id": "507f1f77bcf86cd799439012",
  "is_assignable_by_main_client": true,
  "created_by_user_id": "507f1f77bcf86cd799439013",
  "created_by_client_id": "507f1f77bcf86cd799439012",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Role with this name already exists in scope
- `400 Bad Request` - Invalid request data or missing scope requirements
- `403 Forbidden` - Insufficient permissions for the specified scope
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "project_manager",
       "display_name": "Project Manager",
       "description": "Can manage projects and team members within client account",
       "permissions": [
         "user:read",
         "user:update",
         "group:manage_members"
       ],
       "scope": "client",
       "is_assignable_by_main_client": true
     }'
```

### 2. Get All Roles

Retrieves roles visible to the current user based on their permissions and scope.

**Endpoint:** `GET /v1/roles/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`

**Query Parameters:**

- `scope` (optional, string) - Filter by scope: "system", "platform", or "client"
- `skip` (optional, integer, default: 0, min: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100, min: 1) - Maximum number of records to return

**Visibility Rules:**

- **Super Admins:** See all roles across all scopes
- **Platform Admins:** See system + their platform roles (not other platforms' roles)
- **Client Admins:** See system + their client roles (not other clients' roles)

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "_id": "507f1f77bcf86cd799439011",
    "name": "super_admin",
    "display_name": "Super Administrator",
    "description": "Complete system-wide access",
    "permissions": ["user:create", "user:read", "role:create", "role:read"],
    "scope": "system",
    "scope_id": null,
    "is_assignable_by_main_client": false,
    "created_by_user_id": "system",
    "created_by_client_id": null,
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  },
  {
    "_id": "507f1f77bcf86cd799439012",
    "name": "admin",
    "display_name": "Client Administrator",
    "description": "Administrative access within client account",
    "permissions": ["user:create", "user:read", "group:manage_members"],
    "scope": "client",
    "scope_id": "507f1f77bcf86cd799439013",
    "is_assignable_by_main_client": true,
    "created_by_user_id": "507f1f77bcf86cd799439014",
    "created_by_client_id": "507f1f77bcf86cd799439013",
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  }
]
```

**Error Responses:**

- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid query parameters

**Example Request:**

```bash
# Get all visible roles
curl -X GET "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>"

# Get only client-scoped roles
curl -X GET "https://api.example.com/v1/roles/?scope=client" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Available Roles for Assignment

Retrieves roles that the current user can assign to others, grouped by scope.

**Endpoint:** `GET /v1/roles/available`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "system_roles": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "name": "basic_user",
      "display_name": "Basic User",
      "description": "Basic user access with minimal permissions",
      "permissions": ["user:read"],
      "scope": "system",
      "scope_id": null,
      "is_assignable_by_main_client": true,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ],
  "platform_roles": [
    {
      "_id": "507f1f77bcf86cd799439012",
      "name": "support",
      "display_name": "Platform Support",
      "description": "Platform support representative",
      "permissions": ["platform:support_users"],
      "scope": "platform",
      "scope_id": "507f1f77bcf86cd799439013",
      "is_assignable_by_main_client": false,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ],
  "client_roles": [
    {
      "_id": "507f1f77bcf86cd799439014",
      "name": "manager",
      "display_name": "Manager",
      "description": "Team management role",
      "permissions": ["user:read", "group:manage_members"],
      "scope": "client",
      "scope_id": "507f1f77bcf86cd799439015",
      "is_assignable_by_main_client": true,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ]
}
```

### 4. Get Role by ID

Retrieves a specific role by its MongoDB ObjectId.

**Endpoint:** `GET /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`

**Path Parameters:**

- `role_id` (required, string) - MongoDB ObjectId of the role (e.g., "507f1f77bcf86cd799439011")

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "admin",
  "display_name": "Client Administrator",
  "description": "Administrative access within client account",
  "permissions": ["user:create", "user:read", "group:manage_members"],
  "scope": "client",
  "scope_id": "507f1f77bcf86cd799439013",
  "is_assignable_by_main_client": true,
  "created_by_user_id": "507f1f77bcf86cd799439014",
  "created_by_client_id": "507f1f77bcf86cd799439013",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Role not found or not visible to user
- `403 Forbidden` - Insufficient permissions to view this role
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/roles/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

### 5. Update Role

Updates an existing role's information. Scope and scope_id cannot be changed after creation.

**Endpoint:** `PUT /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`, `role:update`

**Path Parameters:**

- `role_id` (required, string) - MongoDB ObjectId of the role

**Request Body:**

All fields are optional. Only provided fields will be updated.

```json
{
  "name": "senior_admin",
  "display_name": "Senior Administrator",
  "description": "Enhanced administrative role with additional permissions",
  "permissions": ["user:create", "user:read", "user:update", "user:delete", "group:manage_members"],
  "is_assignable_by_main_client": false
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "senior_admin",
  "display_name": "Senior Administrator",
  "description": "Enhanced administrative role with additional permissions",
  "permissions": ["user:create", "user:read", "user:update", "user:delete", "group:manage_members"],
  "scope": "client",
  "scope_id": "507f1f77bcf86cd799439013",
  "is_assignable_by_main_client": false,
  "created_by_user_id": "507f1f77bcf86cd799439014",
  "created_by_client_id": "507f1f77bcf86cd799439013",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T12:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Role not found
- `400 Bad Request` - Invalid request data
- `403 Forbidden` - Insufficient permissions to modify this role
- `401 Unauthorized` - Invalid authentication

### 6. Delete Role

Deletes a role from the system. System roles cannot be deleted.

**Endpoint:** `DELETE /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`, `role:delete`

**Path Parameters:**

- `role_id` (required, string) - MongoDB ObjectId of the role

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `404 Not Found` - Role not found
- `400 Bad Request` - Cannot delete system roles
- `403 Forbidden` - Insufficient permissions to delete this role
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/roles/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

## Role Scope Details

### System Scope

- **Purpose:** Global roles that apply across all platforms and clients
- **Examples:**
  - `super_admin`: Complete system access
  - `basic_user`: Minimal system access
- **Creation:** Only super admins can create system roles
- **scope_id:** Always `null`

### Platform Scope

- **Purpose:** Roles specific to a platform that apply to that platform and its clients
- **Examples:**
  - `admin`: Platform administration
  - `support`: Platform customer support
  - `sales`: Platform sales team
- **Creation:** Platform admins and super admins can create platform roles
- **scope_id:** Platform's ObjectId

### Client Scope

- **Purpose:** Roles specific to a client account
- **Examples:**
  - `admin`: Client account administration
  - `manager`: Team/project management
  - `sales_rep`: Client sales representative
- **Creation:** Client admins and higher can create client roles
- **scope_id:** Client account's ObjectId

## Data Models

### RoleCreateSchema

```json
{
  "name": "string (required)",
  "display_name": "string (required)",
  "description": "string (optional)",
  "permissions": ["string"] (optional, default: []),
  "scope": "system|platform|client (required)",
  "is_assignable_by_main_client": "boolean (optional, default: false)"
}
```

**Field Constraints:**

- `name`: Must be unique within scope + scope_id combination
- `display_name`: Human-readable role name
- `permissions`: List of permission IDs (not validated by default - TODO: implement validation)
- `scope`: One of "system", "platform", or "client"
- `is_assignable_by_main_client`: Controls cross-client assignment capability

### RoleUpdateSchema

```json
{
  "name": "string (optional)",
  "display_name": "string (optional)",
  "description": "string (optional)",
  "permissions": ["string"] (optional),
  "is_assignable_by_main_client": "boolean (optional)"
}
```

**Note:** `scope` and `scope_id` cannot be updated after creation.

### RoleResponseSchema

```json
{
  "_id": "string (MongoDB ObjectId)",
  "name": "string",
  "display_name": "string",
  "description": "string",
  "permissions": ["string"],
  "scope": "system|platform|client",
  "scope_id": "string (ObjectId or null)",
  "is_assignable_by_main_client": "boolean",
  "created_by_user_id": "string (ObjectId)",
  "created_by_client_id": "string (ObjectId or null)",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
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
- `201 Created` - Role created successfully
- `204 No Content` - Role deleted successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions or scope access denied
- `404 Not Found` - Role not found or not visible
- `409 Conflict` - Role name already exists in scope

### Specific Error Scenarios

**409 Conflict (Duplicate Name in Scope):**

```json
{
  "detail": "Role 'admin' already exists in client scope (507f1f77bcf86cd799439013)"
}
```

**403 Forbidden (Insufficient Scope Permissions):**

```json
{
  "detail": "Only platform admins can create platform roles"
}
```

**400 Bad Request (Missing Scope Requirements):**

```json
{
  "detail": "Client ID required for client-scoped roles"
}
```

## Best Practices

### Role Design

1. **Scope Selection:** Choose appropriate scope based on role's intended usage area
2. **Naming Consistency:** Use consistent role names across scopes (e.g., "admin" in each scope)
3. **Clear Display Names:** Use descriptive display names that include scope context
4. **Minimal Permissions:** Follow least privilege principle - assign only necessary permissions
5. **Documentation:** Provide clear descriptions explaining role scope and purpose

### Three-Tier Strategy

1. **System Roles:** Keep minimal - only for truly global functionality
2. **Platform Roles:** Design for platform-wide operations and management
3. **Client Roles:** Focus on client-specific business functions
4. **Role Inheritance:** Consider how permissions flow through the hierarchy
5. **Tenant Isolation:** Ensure proper boundaries between scopes

### Permission Management

1. **Validation:** Implement permission validation in role service (currently TODO)
2. **Scope Matching:** Ensure permissions match the intended scope
3. **Regular Audits:** Review role permissions across all scopes
4. **Cross-Scope Permissions:** Carefully consider permissions that span scopes

## Usage Examples

### Creating Three-Tier Role Hierarchy

```bash
# Create system roles (super admin only)
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <super_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "basic_user",
       "display_name": "Basic User",
       "description": "Minimal system access for all users",
       "permissions": ["user:read"],
       "scope": "system",
       "is_assignable_by_main_client": true
     }'

# Create platform roles (platform admin)
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <platform_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "support",
       "display_name": "Platform Support",
       "description": "Customer support across all platform clients",
       "permissions": ["platform:support_users", "user:read"],
       "scope": "platform",
       "is_assignable_by_main_client": false
     }'

# Create client roles (client admin)
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <client_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "manager",
       "display_name": "Team Manager",
       "description": "Manage team members and projects within client",
       "permissions": ["user:read", "user:update", "group:manage_members"],
       "scope": "client",
       "is_assignable_by_main_client": true
     }'
```

### Querying Roles by Scope

```bash
# Get system roles only
curl -X GET "https://api.example.com/v1/roles/?scope=system" \
     -H "Authorization: Bearer <access_token>"

# Get platform roles only
curl -X GET "https://api.example.com/v1/roles/?scope=platform" \
     -H "Authorization: Bearer <access_token>"

# Get client roles only
curl -X GET "https://api.example.com/v1/roles/?scope=client" \
     -H "Authorization: Bearer <access_token>"

# Get available roles for assignment
curl -X GET "https://api.example.com/v1/roles/available" \
     -H "Authorization: Bearer <access_token>"
```

## Integration Notes

### User Assignment

Roles are assigned to users via ObjectId references:

```json
{
  "user_id": "507f1f77bcf86cd799439020",
  "roles": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"]
}
```

### Permission Calculation

The system calculates effective permissions by:

1. **Role Resolution:** Converting ObjectId role references to role objects
2. **Permission Aggregation:** Combining permissions from all assigned roles
3. **Scope Consideration:** Respecting role scope boundaries
4. **Deduplication:** Removing duplicate permissions

### Database Structure

Roles are stored with efficient indexes:

```javascript
// Unique compound index for role uniqueness within scope
{ "name": 1, "scope": 1, "scope_id": 1 }

// Query index for scope-based filtering
{ "scope": 1, "scope_id": 1 }
```

## Dependencies

This module depends on:

- `role_service`: Business logic for role operations with scope handling
- `permission_service`: Permission validation (TODO: implement in role service)
- `get_current_user`: Authentication dependency for user context
- `RoleModel`: MongoDB document model with proper indexes
- `UserModel`: For determining user's scope and permissions
