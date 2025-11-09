# 23. User Management API

This document describes the API endpoints for managing users and their role assignments in OutlabsAuth.

## Overview

The User Management API provides endpoints for:
- Retrieving user details
- Managing user role assignments
- Querying user permissions

All endpoints require authentication via JWT access token and appropriate permissions.

**Base Path**: `/v1/users`

---

## Endpoints

### 1. Get User by ID

Retrieve detailed information about a specific user.

**Endpoint**: `GET /v1/users/{user_id}`

**Required Permission**: `user:read`

**Path Parameters**:
- `user_id` (string, required): The unique identifier of the user

**Request Example**:
```bash
GET /v1/users/69109a6e73bc51988f730c04
Authorization: Bearer eyJhbGc...
```

**Response** (200 OK):
```json
{
  "id": "69109a6e73bc51988f730c04",
  "email": "admin@test.com",
  "first_name": "Admin",
  "last_name": "User",
  "status": "active",
  "email_verified": false,
  "is_superuser": true
}
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User lacks `user:read` permission
- `404 Not Found`: User with specified ID does not exist
- `500 Internal Server Error`: Server-side error occurred

---

### 2. Get User's Roles

Retrieve all roles assigned to a specific user.

**Endpoint**: `GET /v1/users/{user_id}/roles`

**Required Permission**: `user:read`

**Path Parameters**:
- `user_id` (string, required): The unique identifier of the user

**Query Parameters**:
- `include_inactive` (boolean, optional, default: `false`): Include inactive role memberships in the response

**Request Example**:
```bash
GET /v1/users/69109a6e73bc51988f730c04/roles?include_inactive=false
Authorization: Bearer eyJhbGc...
```

**Response** (200 OK):
```json
[
  {
    "id": "role_abc123",
    "name": "admin",
    "display_name": "Administrator",
    "description": "Full system access",
    "permissions": ["user:*", "role:*", "permission:*"],
    "is_active": true,
    "is_system": true,
    "created_at": "2025-01-09T12:00:00Z",
    "updated_at": "2025-01-09T12:00:00Z"
  },
  {
    "id": "role_def456",
    "name": "editor",
    "display_name": "Content Editor",
    "description": "Can manage content",
    "permissions": ["post:*", "comment:*"],
    "is_active": true,
    "is_system": false,
    "created_at": "2025-01-09T12:00:00Z",
    "updated_at": "2025-01-09T12:00:00Z"
  }
]
```

**Empty Response** (200 OK):
```json
[]
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User lacks `user:read` permission
- `404 Not Found`: User with specified ID does not exist
- `500 Internal Server Error`: Server-side error occurred

**Notes**:
- Returns an empty array `[]` if the user has no roles assigned
- Only returns active memberships by default; use `include_inactive=true` to see all
- Roles returned do not include the `entity` field (SimpleRBAC has flat role assignments)

---

### 3. Assign Role to User

Assign a role to a user, granting them all permissions associated with that role.

**Endpoint**: `POST /v1/users/{user_id}/roles`

**Required Permission**: `user:update`

**Path Parameters**:
- `user_id` (string, required): The unique identifier of the user

**Request Body**:
```json
{
  "role_id": "role_abc123",
  "valid_from": "2025-01-09T00:00:00Z",  // Optional: When membership becomes active
  "valid_until": "2025-12-31T23:59:59Z"  // Optional: When membership expires
}
```

**Request Example**:
```bash
POST /v1/users/69109a6e73bc51988f730c04/roles
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "role_id": "role_abc123"
}
```

**Response** (201 Created):
```json
{
  "id": "membership_xyz789",
  "user_id": "69109a6e73bc51988f730c04",
  "role_id": "role_abc123",
  "status": "active",
  "assigned_by": "admin_user_id",
  "assigned_at": "2025-01-09T12:30:00Z",
  "valid_from": null,
  "valid_until": null,
  "revoked_at": null,
  "revoked_by": null
}
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User lacks `user:update` permission
- `404 Not Found`: User or role with specified ID does not exist
- `409 Conflict`: User already has this role assigned
- `500 Internal Server Error`: Server-side error occurred

**Notes**:
- The `assigned_by` field is automatically set to the ID of the authenticated user making the request
- `status` is automatically set to `active` for new assignments
- Time-bound memberships: Use `valid_from` and `valid_until` for temporary role assignments
- Observability: Logs `role_assigned` event with user_id and role_id

---

### 4. Remove Role from User

Revoke a role assignment from a user, removing all associated permissions.

**Endpoint**: `DELETE /v1/users/{user_id}/roles/{role_id}`

**Required Permission**: `user:update`

**Path Parameters**:
- `user_id` (string, required): The unique identifier of the user
- `role_id` (string, required): The unique identifier of the role to remove

**Request Example**:
```bash
DELETE /v1/users/69109a6e73bc51988f730c04/roles/role_abc123
Authorization: Bearer eyJhbGc...
```

**Response** (204 No Content):
```
(Empty response body)
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User lacks `user:update` permission
- `404 Not Found`:
  - User with specified ID does not exist
  - User does not have the specified role assigned
- `500 Internal Server Error`: Server-side error occurred

**Notes**:
- Successfully removing a role returns `204 No Content` with an empty body
- The `revoked_by` field is automatically set to the ID of the authenticated user
- The `revoked_at` timestamp is set to the current time
- Observability: Logs `role_revoked` event with user_id and role_id

---

### 5. Get User's Effective Permissions

Retrieve all effective permissions for a user (deduplicated from all assigned roles).

**Endpoint**: `GET /v1/users/{user_id}/permissions`

**Required Permission**: `user:read`

**Path Parameters**:
- `user_id` (string, required): The unique identifier of the user

**Request Example**:
```bash
GET /v1/users/69109a6e73bc51988f730c04/permissions
Authorization: Bearer eyJhbGc...
```

**Response** (200 OK):
```json
[
  "apikey:create",
  "apikey:delete",
  "apikey:read",
  "apikey:update",
  "comment:create",
  "comment:delete",
  "comment:read",
  "comment:update",
  "permission:create",
  "permission:delete",
  "permission:read",
  "permission:update",
  "post:create",
  "post:delete",
  "post:read",
  "post:update",
  "role:create",
  "role:delete",
  "role:read",
  "role:update",
  "user:create",
  "user:delete",
  "user:read",
  "user:update"
]
```

**Empty Response** (200 OK):
```json
[]
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User lacks `user:read` permission
- `404 Not Found`: User with specified ID does not exist
- `500 Internal Server Error`: Server-side error occurred

**Notes**:
- Returns a sorted, deduplicated list of permission names
- Aggregates permissions from all active roles assigned to the user
- Empty array `[]` indicates the user has no permissions (no roles assigned)
- Permissions are returned in alphabetical order for consistency

---

## Common Patterns

### Authentication Header

All endpoints require a valid JWT access token in the Authorization header:

```bash
Authorization: Bearer <access_token>
```

To obtain an access token, use the `/v1/auth/login` endpoint (see `22-JWT-Tokens.md`).

### Permission Checking

Before calling these endpoints, ensure the authenticated user has the required permissions:
- **Read operations** (`GET`): Require `user:read` permission
- **Write operations** (`POST`, `DELETE`): Require `user:update` permission

Superusers automatically have all permissions and bypass permission checks.

### Error Handling

Standard HTTP status codes are used:
- `2xx`: Success
- `4xx`: Client error (bad request, unauthorized, forbidden, not found)
- `5xx`: Server error

Error responses include a `detail` field with a human-readable message:

```json
{
  "detail": "User not found"
}
```

### Observability

All successful write operations (POST, DELETE) trigger observability events:
- `role_assigned`: When a role is assigned to a user
- `role_revoked`: When a role is removed from a user

These events include:
- `user_id`: The user being modified
- `role_id`: The role being assigned/revoked
- `timestamp`: When the operation occurred
- `performed_by`: The authenticated user who performed the action

See `97-Observability.md` for details on monitoring and logging.

---

## Complete Example Workflow

### Scenario: Grant Editor Role to a New User

```bash
# Step 1: Get the user's current details
GET /v1/users/new_user_id
Authorization: Bearer <access_token>

# Response: User has no roles yet

# Step 2: Check what roles are available (from Roles API)
GET /v1/roles
Authorization: Bearer <access_token>

# Response: List of roles including "editor" role

# Step 3: Assign the "editor" role
POST /v1/users/new_user_id/roles
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "role_id": "role_editor_123"
}

# Response 201: Role assigned successfully

# Step 4: Verify the user's effective permissions
GET /v1/users/new_user_id/permissions
Authorization: Bearer <access_token>

# Response: ["post:create", "post:read", "post:update", "comment:create"]

# Step 5: List all roles assigned to the user
GET /v1/users/new_user_id/roles
Authorization: Bearer <access_token>

# Response: Array with "editor" role details
```

### Scenario: Temporary Role Assignment

```bash
# Assign a role that expires after 30 days
POST /v1/users/consultant_user_id/roles
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "role_id": "role_consultant_123",
  "valid_from": "2025-01-09T00:00:00Z",
  "valid_until": "2025-02-09T23:59:59Z"
}

# The role will automatically become inactive after 2025-02-09
```

### Scenario: Revoke Access

```bash
# Remove a user's role when they leave the project
DELETE /v1/users/former_member_id/roles/role_editor_123
Authorization: Bearer <access_token>

# Response 204: Role removed, user no longer has editor permissions

# Verify permissions are gone
GET /v1/users/former_member_id/permissions
Authorization: Bearer <access_token>

# Response: [] (empty array if no other roles)
```

---

## Related Documentation

- **22-JWT-Tokens.md**: Authentication and token management
- **13-Core-Authorization-Concepts.md**: Understanding users, roles, and permissions
- **12-Data-Models.md**: Database models for User, Role, and UserRoleMembership
- **97-Observability.md**: Monitoring role assignment events
- **95-Testing-Guide.md**: Testing user management functionality

---

## Notes for EnterpriseRBAC

This documentation describes the SimpleRBAC preset where roles are assigned globally to users.

In **EnterpriseRBAC**, role assignments are scoped to entities (departments, teams, etc.). The API endpoints will be different:
- `POST /v1/entities/{entity_id}/members` - Assign role to user within an entity
- `GET /v1/entities/{entity_id}/members/{user_id}` - Get user's roles in an entity
- `DELETE /v1/entities/{entity_id}/members/{user_id}/roles/{role_id}` - Remove role from user in entity

See the EnterpriseRBAC API documentation (coming soon) for entity-scoped role management.
