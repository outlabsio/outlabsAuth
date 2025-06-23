# Permission Routes Documentation

## Overview

The Permission Routes provide a comprehensive API for managing permissions within the authentication system. This module handles CRUD operations for permissions, which define granular access control capabilities throughout the system. Permissions use human-readable string identifiers following a structured naming convention.

**Base URL:** `/v1/permissions`  
**Tags:** Permission Management

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Permission:** `permission:read` (required for all endpoints)
- **Additional Permissions:** Specific endpoints require additional permissions as noted below

## Permission Naming Convention

Permissions follow a structured naming pattern: `service:resource:action`

**Examples:**

- `user:read` - Read user information
- `user:create` - Create new users
- `group:manage_members` - Manage group memberships
- `billing:invoice:read` - Read billing invoices
- `admin:system:configure` - System configuration access

## Endpoints

### 1. Create Permission

Creates a new permission in the system. This endpoint is primarily used for seeding and administrative purposes.

**Endpoint:** `POST /v1/permissions/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `permission:read`, `permission:create`

**Request Body:**

```json
{
  "id": "service:resource:action",
  "description": "Human-readable description of the permission"
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "service:resource:action",
  "description": "Human-readable description of the permission"
}
```

**Error Responses:**

- `409 Conflict` - Permission with this ID already exists
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request data

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "id": "billing:invoice:read",
       "description": "Permission to read billing invoices"
     }'
```

### 2. Get All Permissions

Retrieves a paginated list of all permissions in the system.

**Endpoint:** `GET /v1/permissions/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `permission:read`

**Query Parameters:**

- `skip` (optional, integer, default: 0, min: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100, min: 1) - Maximum number of records to return

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "user:read",
    "description": "Permission to read user information"
  },
  {
    "id": "user:create",
    "description": "Permission to create new users"
  },
  {
    "id": "billing:invoice:read",
    "description": "Permission to read billing invoices"
  }
]
```

**Error Responses:**

- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid query parameters

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/?skip=0&limit=50" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Permission by ID

Retrieves a specific permission by its string identifier.

**Endpoint:** `GET /v1/permissions/{permission_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `permission:read`

**Path Parameters:**

- `permission_id` (required, string) - The unique string identifier of the permission (e.g., "user:create")

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "user:create",
  "description": "Permission to create new users"
}
```

**Error Responses:**

- `404 Not Found` - Permission not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/user:create" \
     -H "Authorization: Bearer <access_token>"
```

## Permission Categories

### Core System Permissions

**User Management:**

- `user:read` - View user information
- `user:create` - Create new users
- `user:update` - Update user information
- `user:delete` - Delete users

**Group Management:**

- `group:read` - View groups
- `group:create` - Create new groups
- `group:update` - Update group information
- `group:delete` - Delete groups
- `group:manage_members` - Add/remove group members

**Permission Management:**

- `permission:read` - View permissions
- `permission:create` - Create new permissions

**Client Account Management:**

- `client_account:read` - View client accounts
- `client_account:create` - Create new client accounts
- `client_account:update` - Update client account information
- `client_account:delete` - Delete client accounts

**Role Management:**

- `role:read` - View roles
- `role:create` - Create new roles
- `role:update` - Update role information
- `role:delete` - Delete roles

## Data Models

### PermissionCreateSchema

```json
{
  "id": "string (required, unique)",
  "description": "string (optional)"
}
```

**Field Constraints:**

- `id`: Must be a unique string identifier, recommended format: `service:resource:action`
- `description`: Optional human-readable description

### PermissionResponseSchema

```json
{
  "id": "string",
  "description": "string"
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
- `201 Created` - Permission created successfully
- `400 Bad Request` - Invalid request data or parameters
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Permission not found
- `409 Conflict` - Permission with ID already exists

### Specific Error Scenarios

**409 Conflict (Permission Creation):**

```json
{
  "detail": "Permission with ID 'user:create' already exists."
}
```

**404 Not Found (Permission Retrieval):**

```json
{
  "detail": "Permission with ID 'nonexistent:permission' not found."
}
```

## Best Practices

### Permission Design

1. **Consistent Naming:** Use the `service:resource:action` pattern consistently
2. **Granular Control:** Create specific permissions rather than broad ones
3. **Descriptive IDs:** Use clear, self-explanatory permission identifiers
4. **Documentation:** Always provide meaningful descriptions

### API Usage

1. **Pagination:** Use appropriate `skip` and `limit` values for large permission lists
2. **Error Handling:** Handle 409 conflicts gracefully when creating permissions
3. **Caching:** Consider caching permission lists as they change infrequently
4. **Validation:** Validate permission IDs against your naming convention

### Security Considerations

1. **Access Control:** Ensure only authorized users can create/manage permissions
2. **Audit Logging:** Log all permission creation and modification events
3. **Regular Review:** Periodically review permissions for relevance and security
4. **Principle of Least Privilege:** Grant only necessary permissions

## Usage Examples

### Creating Permissions for a New Feature

```bash
# Create read permission
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "id": "reports:financial:read",
       "description": "Permission to view financial reports"
     }'

# Create write permission
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "id": "reports:financial:create",
       "description": "Permission to create financial reports"
     }'
```

### Retrieving All Permissions with Pagination

```bash
# Get first 25 permissions
curl -X GET "https://api.example.com/v1/permissions/?limit=25" \
     -H "Authorization: Bearer <access_token>"

# Get next 25 permissions
curl -X GET "https://api.example.com/v1/permissions/?skip=25&limit=25" \
     -H "Authorization: Bearer <access_token>"
```

## Integration Notes

### Role Assignment

Permissions created through this API can be assigned to roles, which are then assigned to users or groups. The permission system supports:

- Direct role assignment to users
- Role inheritance through group membership
- Effective permission calculation combining direct and inherited permissions

### Access Control Validation

The system uses these permissions for:

- API endpoint access control (via `has_permission` dependency)
- UI feature visibility
- Resource-level access restrictions
- Administrative function authorization

## Rate Limiting

Permission endpoints are subject to standard rate limiting policies. Excessive requests may result in `429 Too Many Requests` responses.

## Dependencies

This module depends on:

- `permission_service`: Business logic for permission operations
- `has_permission`: Authorization dependency for permission checking
- Authentication middleware for token validation
