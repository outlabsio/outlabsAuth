# Client Account Routes Documentation

## Overview

The Client Account Routes provide a comprehensive API for managing client accounts within the authentication system with **hierarchical multi-platform tenancy support**. This module handles all CRUD operations for client accounts with proper authentication and **platform-scoped authorization controls**.

**Base URL:** `/v1/client_accounts`  
**Tags:** Client Account Management

## 🏢 **Hierarchical Multi-Platform Tenancy**

This API supports a three-tier permission hierarchy:

- **Super Admins**: Complete system access across all platforms
- **Platform Creators**: Can create sub-clients and access all clients within their platform
- **Platform Viewers**: Can only access clients they created within their platform
- **Client Admins**: Access only their own client account (standard behavior)

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Permission:** `client_account:read` (required for all endpoints)
- **Platform-Scoped Permissions:**
  - `client_account:create_sub` - Create sub-clients within platform scope
  - `client_account:read_platform` - Read all clients within platform scope
  - `client_account:read_created` - Read only clients you created
- **Additional Permissions:** Specific endpoints require additional permissions as noted below

## Endpoints

### 1. Create Client Account (Super Admin Only)

Creates a new top-level client account in the system. This is typically used for creating platform root accounts.

**Endpoint:** `POST /v1/client_accounts/`

**Required Permission:** `client_account:create`

**Request Body:**

```json
{
  "name": "string",
  "description": "string",
  "main_contact_user_id": "string",
  "platform_id": "string",
  "is_platform_root": false
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "status": "active",
  "main_contact_user_id": "string",
  "data_retention_policy_days": null,
  "platform_id": "string",
  "created_by_client_id": null,
  "is_platform_root": false,
  "child_clients": [],
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Client account with this name already exists
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/client_accounts/" \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Real Estate Platform Root",
       "description": "Root client for real estate platform",
       "platform_id": "real_estate_platform",
       "is_platform_root": true
     }'
```

### 2. Create Sub-Client Account (Platform Admins)

Creates a sub-client account under the current user's client account. Available to platform admins with appropriate permissions.

**Endpoint:** `POST /v1/client_accounts/sub-clients`

**Required Permission:** `client_account:create_sub`

**Request Body:**

```json
{
  "name": "string",
  "description": "string",
  "main_contact_user_id": "string"
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "status": "active",
  "main_contact_user_id": "string",
  "data_retention_policy_days": null,
  "platform_id": "inherited_from_parent",
  "created_by_client_id": "parent_client_id",
  "is_platform_root": false,
  "child_clients": [],
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Client account with this name already exists
- `403 Forbidden` - Insufficient permissions or user not associated with client account
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/client_accounts/sub-clients" \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "ACME Properties",
       "description": "Real estate company under platform"
     }'
```

### 3. Get All Client Accounts (Hierarchical Filtering)

Retrieves a paginated list of client accounts with automatic hierarchical filtering based on user permissions.

**Endpoint:** `GET /v1/client_accounts/`

**Required Permission:** `client_account:read`

**Query Parameters:**

- `skip` (optional, integer, default: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100) - Maximum number of records to return
- `platform_scope` (optional, string) - Filter hint (not currently used, filtering is automatic)

**Authorization Logic:**

- **Super Admins**: See all client accounts
- **Platform Creators** (`client_account:read_platform`): See all accounts in their platform
- **Platform Viewers** (`client_account:read_created`): See only accounts they created
- **Regular Users**: See only their own account

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "string",
    "name": "string",
    "description": "string",
    "status": "active",
    "main_contact_user_id": "string",
    "data_retention_policy_days": null,
    "platform_id": "string",
    "created_by_client_id": "string",
    "is_platform_root": false,
    "child_clients": ["child_id_1", "child_id_2"],
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  }
]
```

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/client_accounts/?skip=0&limit=50" \
     -H "Authorization: Bearer <token>"
```

### 4. Get My Sub-Clients

Retrieves all sub-clients created by the current user's client account.

**Endpoint:** `GET /v1/client_accounts/my-sub-clients`

**Required Permission:** `client_account:read_created`

**Query Parameters:**

- `skip` (optional, integer, default: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100) - Maximum number of records to return

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "string",
    "name": "string",
    "description": "string",
    "status": "active",
    "main_contact_user_id": "string",
    "platform_id": "string",
    "created_by_client_id": "current_user_client_id",
    "is_platform_root": false,
    "child_clients": [],
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  }
]
```

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/client_accounts/my-sub-clients" \
     -H "Authorization: Bearer <token>"
```

### 5. Get Client Account by ID (Hierarchical Access Control)

Retrieves a specific client account by its ID with hierarchical access control.

**Endpoint:** `GET /v1/client_accounts/{account_id}`

**Required Permission:** `client_account:read`

**Path Parameters:**

- `account_id` (required, string) - The unique identifier of the client account

**Authorization:** Uses hierarchical access control to ensure users can only access accounts they have permission to view.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "status": "active",
  "main_contact_user_id": "string",
  "data_retention_policy_days": null,
  "platform_id": "string",
  "created_by_client_id": "string",
  "is_platform_root": false,
  "child_clients": ["child_id_1", "child_id_2"],
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Client account not found or access denied (prevents information disclosure)
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid account ID format

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/client_accounts/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <token>"
```

### 6. Update Client Account (Hierarchical Access Control)

Updates an existing client account with hierarchical access control.

**Endpoint:** `PUT /v1/client_accounts/{account_id}`

**Required Permission:** `client_account:update`

**Path Parameters:**

- `account_id` (required, string) - The unique identifier of the client account

**Request Body:**

```json
{
  "name": "string",
  "description": "string",
  "status": "active",
  "main_contact_user_id": "string",
  "data_retention_policy_days": 30,
  "platform_id": "string",
  "is_platform_root": false
}
```

**Note:** `created_by_client_id` and `child_clients` are not directly updatable for security reasons.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "status": "active",
  "main_contact_user_id": "string",
  "data_retention_policy_days": 30,
  "platform_id": "string",
  "created_by_client_id": "string",
  "is_platform_root": false,
  "child_clients": ["child_id_1"],
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Client account not found or access denied
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid account ID format or request body

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/client_accounts/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Updated Platform Client",
       "description": "Updated description",
       "status": "active",
       "data_retention_policy_days": 90
     }'
```

### 7. Delete Client Account (Hierarchical Access Control)

Deletes a client account from the system with hierarchical access control.

**Endpoint:** `DELETE /v1/client_accounts/{account_id}`

**Required Permission:** `client_account:delete`

**Path Parameters:**

- `account_id` (required, string) - The unique identifier of the client account

**Authorization:** Uses hierarchical access control to ensure users can only delete accounts they have permission to access.

**Note:** Deleting a client account will also remove it from the parent's `child_clients` list if it's a sub-client.

**Response:**

- **Status Code:** `204 No Content`
- **Response Body:** Empty

**Error Responses:**

- `404 Not Found` - Client account not found or access denied
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid account ID format

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/client_accounts/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <token>"
```

## 🔐 **Hierarchical Permissions**

### Platform-Scoped Permissions

| Permission                     | Description                                   | Use Case                                       |
| ------------------------------ | --------------------------------------------- | ---------------------------------------------- |
| `client_account:create`        | Create top-level client accounts              | Super admins creating platform roots           |
| `client_account:create_sub`    | Create sub-clients within platform scope      | Platform admins creating sub-clients           |
| `client_account:read_platform` | Read all clients within platform scope        | Platform creators viewing all platform clients |
| `client_account:read_created`  | Read only clients you created                 | Platform viewers with limited scope            |
| `client_account:read`          | Basic read access with hierarchical filtering | All authenticated users                        |
| `client_account:update`        | Update client accounts (with access control)  | Authorized users modifying accounts            |
| `client_account:delete`        | Delete client accounts (with access control)  | Super admins and authorized users              |

### Role Examples

**Platform Creator Role:**

- `client_account:read`, `client_account:create_sub`, `client_account:read_platform`, `client_account:update`
- Can create sub-clients and see all clients in their platform

**Platform Viewer Role:**

- `client_account:read`, `client_account:read_created`
- Can only see clients they created

## Data Models

### ClientAccountCreateSchema

```json
{
  "name": "string (required)",
  "description": "string (optional)",
  "main_contact_user_id": "string (optional)",
  "platform_id": "string (optional)",
  "is_platform_root": "boolean (optional, default: false)"
}
```

### ClientAccountUpdateSchema

```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "status": "string (optional, enum: 'active'|'suspended')",
  "main_contact_user_id": "string (optional)",
  "data_retention_policy_days": "integer (optional)",
  "platform_id": "string (optional)",
  "is_platform_root": "boolean (optional)"
}
```

**Note:** `created_by_client_id` and `child_clients` are managed automatically and not directly updatable.

### ClientAccountResponseSchema

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "status": "string (enum: 'active'|'suspended')",
  "main_contact_user_id": "string",
  "data_retention_policy_days": "integer",
  "platform_id": "string",
  "created_by_client_id": "string",
  "is_platform_root": "boolean",
  "child_clients": ["string"],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## 🔒 **Security & Access Control**

### Hierarchical Authorization

The API implements sophisticated hierarchical access control:

1. **Information Disclosure Prevention**: Returns `404 Not Found` instead of `403 Forbidden` when users attempt to access accounts outside their scope
2. **Automatic Filtering**: The `GET /v1/client_accounts/` endpoint automatically filters results based on user permissions
3. **Platform Isolation**: Users cannot access accounts from other platforms unless they're super admins
4. **Parent-Child Validation**: Sub-client operations validate proper hierarchical relationships

### Access Patterns

- **Super Admin Access**: Can access any client account across all platforms
- **Platform Creator Access**: Can access all accounts within their `platform_id`
- **Platform Viewer Access**: Can access only accounts where `created_by_client_id` matches their client account
- **Regular User Access**: Can access only their own client account

## Error Handling

All endpoints follow standard HTTP status codes and return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common error scenarios:

- **401 Unauthorized**: Invalid or missing authentication token
- **403 Forbidden**: Valid token but insufficient permissions
- **404 Not Found**: Resource not found or access denied (prevents information disclosure)
- **409 Conflict**: Resource already exists (for creation operations)
- **400 Bad Request**: Invalid request data or parameters

## Rate Limiting

All endpoints are subject to rate limiting middleware. Exceeding rate limits will result in `429 Too Many Requests` responses.

## Dependencies

This module depends on:

- `client_account_service`: Enhanced business logic for hierarchical client account operations
- `has_permission`: Authorization dependency for permission checking
- `has_hierarchical_client_access`: Hierarchical access control dependency
- `get_current_user`: User context for authorization decisions
- `valid_account_id`: Validation dependency for account ID format
- `group_service`: For retrieving user effective permissions

## Usage Notes

### Hierarchical Relationships

- When creating sub-clients via `/sub-clients`, the `platform_id` is automatically inherited from the parent
- The `created_by_client_id` is automatically set to the current user's client account ID
- Parent accounts automatically have the sub-client ID added to their `child_clients` array
- Deleting a sub-client automatically removes it from the parent's `child_clients` array

### Platform Scoping

- Account IDs are MongoDB ObjectIds and must be valid 24-character hexadecimal strings
- Platform IDs are string identifiers (e.g., "real_estate_platform", "crm_platform")
- Platform root accounts should have `is_platform_root: true` for proper identification
- All timestamps are in ISO 8601 format with UTC timezone

### Real-World Examples

**Real Estate Platform Scenario:**

1. Create platform root: `POST /v1/client_accounts/` with `platform_id: "real_estate"`
2. Platform admin creates property companies: `POST /v1/client_accounts/sub-clients`
3. Platform admin views all real estate clients: `GET /v1/client_accounts/`

**CRM Platform Scenario:**

1. Create platform root: `POST /v1/client_accounts/` with `platform_id: "crm_platform"`
2. Platform admin creates business clients: `POST /v1/client_accounts/sub-clients`
3. Platform admin views only their created clients: `GET /v1/client_accounts/my-sub-clients`
