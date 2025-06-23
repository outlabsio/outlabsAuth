# Group Routes Documentation

## Overview

The Group Routes provide a comprehensive API for managing groups and group memberships within the authentication system. This module handles all CRUD operations for groups, group membership management, and provides endpoints for retrieving user group associations with effective roles and permissions.

**Base URL:** `/v1/groups`  
**Tags:** groups

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Permission:** `group:read` (required for all endpoints)
- **Additional Permissions:** Specific endpoints require additional permissions as noted below

### Client Account Isolation

Non-admin users are restricted to groups within their own client account:

- Admin users (main client) can access all groups across client accounts
- Regular users can only access groups within their assigned client account

## Endpoints

### 1. Create Group

Creates a new group in the system.

**Endpoint:** `POST /v1/groups/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:create`

**Request Body:**

```json
{
  "name": "string",
  "description": "string",
  "client_account_id": "507f1f77bcf86cd799439011",
  "roles": []
}
```

**Note:** The `roles` field is optional and defaults to an empty list if not provided.

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "Development Team",
  "description": "Main development team group",
  "client_account_id": "507f1f77bcf86cd799439011",
  "roles": [],
  "is_active": true,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data
- `403 Forbidden` - Insufficient permissions or client account access denied
- `401 Unauthorized` - Invalid access token
- `500 Internal Server Error` - Server error during group creation

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/groups/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Development Team",
       "description": "Main development team group",
       "client_account_id": "507f1f77bcf86cd799439011",
       "roles": ["developer", "team_member"]
     }'
```

### 2. List Groups

Retrieves a paginated list of groups with optional client account filtering.

**Endpoint:** `GET /v1/groups/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:read`

**Query Parameters:**

- `skip` (optional, integer, default: 0, min: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100, min: 1, max: 1000) - Maximum number of records to return
- `client_account_id` (optional, string) - Filter groups by client account ID

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "507f1f77bcf86cd799439012",
    "name": "Development Team",
    "description": "Main development team group",
    "client_account_id": "507f1f77bcf86cd799439011",
    "roles": [],
    "is_active": true,
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  }
]
```

**Error Responses:**

- `400 Bad Request` - Invalid query parameters
- `401 Unauthorized` - Invalid access token
- `403 Forbidden` - Insufficient permissions

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/?skip=0&limit=50&client_account_id=507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Group by ID

Retrieves a specific group by its ID.

**Endpoint:** `GET /v1/groups/{group_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:read`

**Path Parameters:**

- `group_id` (required, string) - The unique identifier of the group

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "Development Team",
  "description": "Main development team group",
  "client_account_id": "507f1f77bcf86cd799439011",
  "roles": [],
  "is_active": true,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid group ID format
- `404 Not Found` - Group not found or access denied
- `401 Unauthorized` - Invalid access token
- `403 Forbidden` - Insufficient permissions

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/507f1f77bcf86cd799439012" \
     -H "Authorization: Bearer <access_token>"
```

### 4. Update Group

Updates an existing group's information.

**Endpoint:** `PUT /v1/groups/{group_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:update`

**Path Parameters:**

- `group_id` (required, string) - The unique identifier of the group

**Request Body:**

```json
{
  "name": "string",
  "description": "string",
  "roles": [],
  "is_active": true
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "Senior Development Team",
  "description": "Updated development team group",
  "client_account_id": "507f1f77bcf86cd799439011",
  "roles": ["senior_developer", "team_lead"],
  "is_active": true,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T12:00:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or client account access denied
- `401 Unauthorized` - Invalid access token
- `500 Internal Server Error` - Server error during update

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/groups/507f1f77bcf86cd799439012" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Senior Development Team",
       "description": "Updated development team group",
       "roles": ["senior_developer", "team_lead"],
       "is_active": true
     }'
```

### 5. Delete Group

Deletes a group and removes all users from the group.

**Endpoint:** `DELETE /v1/groups/{group_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:delete`

**Path Parameters:**

- `group_id` (required, string) - The unique identifier of the group

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or client account access denied
- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/groups/507f1f77bcf86cd799439012" \
     -H "Authorization: Bearer <access_token>"
```

### 6. Add Users to Group

Adds users to a specific group.

**Endpoint:** `POST /v1/groups/{group_id}/members`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:manage_members`

**Path Parameters:**

- `group_id` (required, string) - The unique identifier of the group

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

- `400 Bad Request` - Invalid request data
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or client account access denied
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

### 7. Remove Users from Group

Removes users from a specific group.

**Endpoint:** `DELETE /v1/groups/{group_id}/members`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:manage_members`

**Path Parameters:**

- `group_id` (required, string) - The unique identifier of the group

**Request Body:**

```json
{
  "user_ids": ["507f1f77bcf86cd799439013", "507f1f77bcf86cd799439014"]
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "message": "Successfully removed 2 users from group"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request data
- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or client account access denied
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

### 8. Get Group Members

Retrieves all members of a specific group.

**Endpoint:** `GET /v1/groups/{group_id}/members`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:read`

**Path Parameters:**

- `group_id` (required, string) - The unique identifier of the group

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "group_id": "507f1f77bcf86cd799439012",
  "group_name": "Development Team",
  "members": [
    {
      "id": "507f1f77bcf86cd799439013",
      "email": "john.doe@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "client_account_id": "507f1f77bcf86cd799439011",
      "roles": ["developer"],
      "groups": [],
      "is_main_client": false,
      "status": "active",
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z",
      "last_login_at": "2023-01-01T00:00:00Z",
      "locale": "en-US"
    }
  ]
}
```

**Error Responses:**

- `404 Not Found` - Group not found
- `403 Forbidden` - Insufficient permissions or client account access denied
- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/507f1f77bcf86cd799439012/members" \
     -H "Authorization: Bearer <access_token>"
```

### 9. Get User Groups

Retrieves all groups that a user belongs to, along with their effective roles and permissions.

**Endpoint:** `GET /v1/groups/users/{user_id}/groups`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `group:read`

**Path Parameters:**

- `user_id` (required, string) - The unique identifier of the user

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "user_id": "507f1f77bcf86cd799439013",
  "groups": [
    {
      "id": "507f1f77bcf86cd799439012",
      "name": "Development Team",
      "description": "Main development team group",
      "client_account_id": "507f1f77bcf86cd799439011",
      "roles": ["developer"],
      "is_active": true,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ],
  "effective_roles": ["developer", "team_member"],
  "effective_permissions": ["user:read", "group:read", "project:read", "project:write"]
}
```

**Error Responses:**

- `404 Not Found` - User not found
- `403 Forbidden` - Insufficient permissions or client account access denied
- `401 Unauthorized` - Invalid access token

**Access Control:**

- Users can view their own groups
- Admin users can view any user's groups
- Regular users can only view group memberships within their own client account

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/groups/users/507f1f77bcf86cd799439013/groups" \
     -H "Authorization: Bearer <access_token>"
```

## Permission Requirements

### Required Permissions by Endpoint

| Endpoint                            | Method | Required Permissions                 |
| ----------------------------------- | ------ | ------------------------------------ |
| `/v1/groups/`                       | GET    | `group:read`                         |
| `/v1/groups/`                       | POST   | `group:read`, `group:create`         |
| `/v1/groups/{group_id}`             | GET    | `group:read`                         |
| `/v1/groups/{group_id}`             | PUT    | `group:read`, `group:update`         |
| `/v1/groups/{group_id}`             | DELETE | `group:read`, `group:delete`         |
| `/v1/groups/{group_id}/members`     | POST   | `group:read`, `group:manage_members` |
| `/v1/groups/{group_id}/members`     | DELETE | `group:read`, `group:manage_members` |
| `/v1/groups/{group_id}/members`     | GET    | `group:read`                         |
| `/v1/groups/users/{user_id}/groups` | GET    | `group:read`                         |

## Client Account Access Control

### Admin Users (Main Client)

- Can access and manage groups across all client accounts
- No restrictions on group operations
- Can view and manage any user's group memberships

### Regular Users

- Can only access groups within their assigned client account
- Cannot create groups in other client accounts
- Cannot view or manage groups outside their client account
- Can only view group memberships within their client account

### Self-Service Operations

- Users can always view their own group memberships
- Users cannot modify their own group memberships (requires `group:manage_members` permission)

## Error Handling

All endpoints follow consistent error response format:

```json
{
  "detail": "Error message description"
}
```

### Common HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `204 No Content` - Request successful, no response body
- `400 Bad Request` - Invalid request data or parameters
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions or access denied
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

### Client Account Access Errors

When a user attempts to access a group outside their client account:

- Returns `404 Not Found` instead of `403 Forbidden` to prevent information disclosure
- Generic error message: "Group not found"

## Data Models

### Group Object

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "client_account_id": "string",
  "roles": ["string"],
  "is_active": true,
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

### Group Membership Request

```json
{
  "user_ids": ["string"]
}
```

### Group Members Response

```json
{
  "group_id": "string",
  "group_name": "string",
  "members": [
    {
      "id": "string",
      "email": "string",
      "first_name": "string",
      "last_name": "string",
      "client_account_id": "string",
      "roles": ["string"],
      "groups": ["string"],
      "is_main_client": false,
      "status": "active",
      "created_at": "string (ISO 8601)",
      "updated_at": "string (ISO 8601)",
      "last_login_at": "string (ISO 8601)",
      "locale": "string"
    }
  ]
}
```

### User Groups Response

```json
{
  "user_id": "string",
  "groups": ["Group Object"],
  "effective_roles": ["string"],
  "effective_permissions": ["string"]
}
```

## Best Practices

### Group Management

1. Use descriptive group names and descriptions
2. Regularly audit group memberships
3. Implement proper metadata for organizational purposes
4. Use client account filtering for better performance

### Security

1. Always validate user permissions before group operations
2. Implement proper error handling to prevent information disclosure
3. Log all group membership changes for auditing
4. Regularly review effective permissions for users

### Performance

1. Use pagination for large group lists
2. Filter by client account when possible
3. Consider caching frequently accessed group data
4. Monitor group membership query performance

### API Usage

1. Handle 404 errors gracefully for missing groups
2. Implement retry logic for transient errors
3. Use bulk operations for adding/removing multiple users
4. Validate user IDs before membership operations
