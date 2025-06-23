# Role Routes Documentation

## Overview

The Role Routes provide a comprehensive API for managing roles within the authentication system. Roles serve as collections of permissions that can be assigned to users or groups, enabling flexible and scalable access control. This module handles full CRUD operations for roles with permission validation and conflict detection.

**Base URL:** `/v1/roles`  
**Tags:** Role Management

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Permission:** `role:read` (required for all endpoints)
- **Additional Permissions:** Specific endpoints require additional permissions as noted below

## Role System Overview

Roles act as permission containers that simplify access management:

- **Permission Aggregation:** Roles collect multiple permissions into logical groups
- **User Assignment:** Users can be assigned multiple roles directly or through group membership
- **Effective Permissions:** User's final permissions are calculated from all assigned roles
- **Hierarchical Control:** Main client roles can be restricted or globally assignable

## Endpoints

### 1. Create Role

Creates a new role in the system with specified permissions and configuration.

**Endpoint:** `POST /v1/roles/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`, `role:create`

**Request Body:**

```json
{
  "id": "unique_role_identifier",
  "name": "Human Readable Role Name",
  "description": "Detailed description of the role's purpose and scope",
  "permissions": ["permission:id:1", "permission:id:2"],
  "is_assignable_by_main_client": false
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "unique_role_identifier",
  "name": "Human Readable Role Name",
  "description": "Detailed description of the role's purpose and scope",
  "permissions": ["permission:id:1", "permission:id:2"],
  "is_assignable_by_main_client": false,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Role with this ID or name already exists
- `400 Bad Request` - Invalid request data or permission doesn't exist
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "id": "project_manager",
       "name": "Project Manager",
       "description": "Can manage projects and team members within assigned client accounts",
       "permissions": [
         "project:create",
         "project:read",
         "project:update",
         "user:read",
         "group:manage_members"
       ],
       "is_assignable_by_main_client": true
     }'
```

### 2. Get All Roles

Retrieves a paginated list of all roles in the system.

**Endpoint:** `GET /v1/roles/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`

**Query Parameters:**

- `skip` (optional, integer, default: 0, min: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100, min: 1) - Maximum number of records to return

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "project_manager",
    "name": "Project Manager",
    "description": "Can manage projects and team members",
    "permissions": ["project:create", "project:read", "user:read"],
    "is_assignable_by_main_client": true,
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  },
  {
    "id": "developer",
    "name": "Developer",
    "description": "Standard development team member permissions",
    "permissions": ["project:read", "code:read", "code:write"],
    "is_assignable_by_main_client": false,
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
curl -X GET "https://api.example.com/v1/roles/?skip=0&limit=25" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Role by ID

Retrieves a specific role by its string identifier.

**Endpoint:** `GET /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`

**Path Parameters:**

- `role_id` (required, string) - The unique string identifier of the role (e.g., "project_manager")

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "project_manager",
  "name": "Project Manager",
  "description": "Can manage projects and team members",
  "permissions": ["project:create", "project:read", "user:read"],
  "is_assignable_by_main_client": true,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Role not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/roles/project_manager" \
     -H "Authorization: Bearer <access_token>"
```

### 4. Update Role

Updates an existing role's information, including permissions and configuration.

**Endpoint:** `PUT /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`, `role:update`

**Path Parameters:**

- `role_id` (required, string) - The unique string identifier of the role

**Request Body:**

All fields are optional. Only provided fields will be updated.

```json
{
  "name": "Updated Role Name",
  "description": "Updated description",
  "permissions": ["permission:id:1", "permission:id:3"],
  "is_assignable_by_main_client": true
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "project_manager",
  "name": "Updated Role Name",
  "description": "Updated description",
  "permissions": ["permission:id:1", "permission:id:3"],
  "is_assignable_by_main_client": true,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T12:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Role not found
- `400 Bad Request` - Invalid request data or permission doesn't exist
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/roles/project_manager" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Senior Project Manager",
       "description": "Enhanced project management role with additional permissions",
       "permissions": [
         "project:create",
         "project:read",
         "project:update",
         "project:delete",
         "user:read",
         "group:manage_members",
         "reports:read"
       ]
     }'
```

### 5. Delete Role

Deletes a role from the system. This operation will fail if the role is currently assigned to any users.

**Endpoint:** `DELETE /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `role:read`, `role:delete`

**Path Parameters:**

- `role_id` (required, string) - The unique string identifier of the role

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `404 Not Found` - Role not found
- `409 Conflict` - Role is currently assigned to users (if implemented)
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/roles/deprecated_role" \
     -H "Authorization: Bearer <access_token>"
```

## Role Configuration

### Main Client Assignment Control

The `is_assignable_by_main_client` field controls role assignment behavior:

- **`true`:** Role can be assigned by main client administrators to users across all client accounts
- **`false`:** Role assignment is restricted within client account boundaries

This setting is crucial for:

- **Global Roles:** Platform-wide administrative roles
- **Client-Specific Roles:** Roles that should remain within client account boundaries
- **Security Boundaries:** Preventing unauthorized cross-client access

## Common Role Examples

### Administrative Roles

```json
{
  "id": "platform_admin",
  "name": "Platform Administrator",
  "description": "Full platform administration access",
  "permissions": ["admin:*", "user:*", "role:*", "permission:*"],
  "is_assignable_by_main_client": true
}
```

### Client-Specific Roles

```json
{
  "id": "client_admin",
  "name": "Client Administrator",
  "description": "Administrative access within client account",
  "permissions": ["user:read", "user:create", "group:*", "client_account:read"],
  "is_assignable_by_main_client": false
}
```

### Functional Roles

```json
{
  "id": "billing_manager",
  "name": "Billing Manager",
  "description": "Access to billing and financial information",
  "permissions": ["billing:*", "reports:financial:read", "user:read"],
  "is_assignable_by_main_client": true
}
```

## Data Models

### RoleCreateSchema

```json
{
  "id": "string (required, unique)",
  "name": "string (required, unique)",
  "description": "string (optional)",
  "permissions": ["string"] (optional, default: []),
  "is_assignable_by_main_client": "boolean (optional, default: false)"
}
```

**Field Constraints:**

- `id`: Must be unique string identifier, recommend snake_case
- `name`: Must be unique human-readable name
- `permissions`: List of valid permission IDs (validated against existing permissions)
- `is_assignable_by_main_client`: Controls cross-client assignment capability

### RoleUpdateSchema

```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "permissions": ["string"] (optional),
  "is_assignable_by_main_client": "boolean (optional)"
}
```

**Note:** Role ID cannot be updated after creation.

### RoleResponseSchema

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "permissions": ["string"],
  "is_assignable_by_main_client": "boolean",
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
- `400 Bad Request` - Invalid request data or nonexistent permission
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Role not found
- `409 Conflict` - Role ID/name already exists or role in use

### Specific Error Scenarios

**409 Conflict (Duplicate ID):**

```json
{
  "detail": "Role with ID 'project_manager' already exists."
}
```

**409 Conflict (Duplicate Name):**

```json
{
  "detail": "Role with name 'Project Manager' already exists."
}
```

**400 Bad Request (Invalid Permission):**

```json
{
  "detail": "Permission 'nonexistent:permission' does not exist."
}
```

**404 Not Found (Role Retrieval):**

```json
{
  "detail": "Role with ID 'nonexistent_role' not found."
}
```

## Best Practices

### Role Design

1. **Meaningful IDs:** Use descriptive, consistent ID naming (snake_case recommended)
2. **Clear Names:** Use human-readable names that clearly describe the role's purpose
3. **Granular Permissions:** Include only necessary permissions following least privilege principle
4. **Logical Grouping:** Group related permissions together in coherent roles
5. **Documentation:** Always provide clear descriptions explaining the role's scope

### Permission Management

1. **Validation:** Ensure all assigned permissions exist before role creation/update
2. **Regular Audits:** Periodically review role permissions for relevance and security
3. **Permission Cleanup:** Remove obsolete permissions from roles when permissions are deprecated
4. **Testing:** Validate role functionality after permission changes

### Client Account Strategy

1. **Global vs Local:** Carefully consider `is_assignable_by_main_client` based on role scope
2. **Security Boundaries:** Respect client isolation requirements
3. **Administrative Hierarchy:** Establish clear role hierarchies for different admin levels

### API Usage

1. **Pagination:** Use appropriate pagination for large role lists
2. **Error Handling:** Handle all error scenarios gracefully
3. **Validation:** Validate role assignments against business rules
4. **Caching:** Consider caching frequently accessed roles

## Usage Examples

### Creating a Complete Role Hierarchy

```bash
# Create admin role
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "id": "admin",
       "name": "Administrator",
       "description": "Full system administration access",
       "permissions": ["user:*", "role:*", "group:*", "permission:*"],
       "is_assignable_by_main_client": true
     }'

# Create manager role
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "id": "manager",
       "name": "Manager",
       "description": "Team and project management access",
       "permissions": ["user:read", "user:update", "group:read", "project:*"],
       "is_assignable_by_main_client": false
     }'

# Create standard user role
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "id": "user",
       "name": "Standard User",
       "description": "Basic user access permissions",
       "permissions": ["user:read", "project:read"],
       "is_assignable_by_main_client": false
     }'
```

### Updating Role Permissions

```bash
# Add new permissions to existing role
curl -X PUT "https://api.example.com/v1/roles/manager" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "permissions": [
         "user:read",
         "user:update",
         "group:read",
         "project:*",
         "reports:read"
       ]
     }'
```

## Integration Notes

### User Assignment

Roles created through this API are assigned to users via:

- **Direct Assignment:** Users can have roles assigned directly to their account
- **Group Membership:** Users inherit roles from groups they belong to
- **Effective Permissions:** System calculates combined permissions from all user's roles

### Permission Validation

The system enforces:

- **Permission Existence:** All role permissions must exist in the permission system
- **Real-time Validation:** Permission changes are validated during role creation/update
- **Consistency Checks:** System prevents assignment of non-existent permissions

### Access Control Integration

Roles integrate with the access control system through:

- **Endpoint Protection:** API endpoints use role-based permission checking
- **UI Authorization:** Frontend components show/hide features based on user's effective permissions
- **Resource Access:** Fine-grained resource access control based on role permissions

## Dependencies

This module depends on:

- `role_service`: Business logic for role operations
- `permission_service`: Validation of assigned permissions
- `has_permission`: Authorization dependency for permission checking
- Authentication middleware for token validation
