# Client Account Routes Documentation

## Overview

The Client Account Routes provide a comprehensive API for managing client accounts within the authentication system. This module handles all CRUD operations for client accounts with proper authentication and authorization controls.

**Base URL:** `/v1/client_accounts`  
**Tags:** Client Account Management

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Permission:** `client_account:read` (required for all endpoints)
- **Additional Permissions:** Specific endpoints require additional permissions as noted below

## Endpoints

### 1. Create Client Account

Creates a new client account in the system.

**Endpoint:** `POST /v1/client_accounts/`

**Required Permission:** `client_account:create`

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
       "name": "Acme Corporation",
       "description": "Main client account for Acme Corp",
       "main_contact_user_id": "507f1f77bcf86cd799439012"
     }'
```

### 2. Get All Client Accounts

Retrieves a paginated list of all client accounts.

**Endpoint:** `GET /v1/client_accounts/`

**Required Permission:** `client_account:read`

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
    "data_retention_policy_days": null,
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  }
]
```

**Error Responses:**

- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/client_accounts/?skip=0&limit=50" \
     -H "Authorization: Bearer <token>"
```

### 3. Get Client Account by ID

Retrieves a specific client account by its ID.

**Endpoint:** `GET /v1/client_accounts/{account_id}`

**Required Permission:** `client_account:read`

**Path Parameters:**

- `account_id` (required, string) - The unique identifier of the client account

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
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Client account not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid account ID format

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/client_accounts/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <token>"
```

### 4. Update Client Account

Updates an existing client account.

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
  "data_retention_policy_days": 30
}
```

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
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Client account not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid account ID format or request body

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/client_accounts/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Updated Acme Corporation",
       "description": "Updated description for Acme Corp",
       "status": "suspended",
       "main_contact_user_id": "507f1f77bcf86cd799439013",
       "data_retention_policy_days": 90
     }'
```

### 5. Delete Client Account

Deletes a client account from the system.

**Endpoint:** `DELETE /v1/client_accounts/{account_id}`

**Required Permission:** `client_account:delete`

**Path Parameters:**

- `account_id` (required, string) - The unique identifier of the client account

**Response:**

- **Status Code:** `204 No Content`
- **Response Body:** Empty

**Error Responses:**

- `404 Not Found` - Client account not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid account ID format

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/client_accounts/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <token>"
```

## Data Models

### ClientAccountCreateSchema

```json
{
  "name": "string (required)",
  "description": "string (optional)",
  "main_contact_user_id": "string (optional)"
}
```

### ClientAccountUpdateSchema

```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "status": "string (optional, enum: 'active'|'suspended')",
  "main_contact_user_id": "string (optional)",
  "data_retention_policy_days": "integer (optional)"
}
```

### ClientAccountResponseSchema

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "status": "string (enum: 'active'|'suspended')",
  "main_contact_user_id": "string",
  "data_retention_policy_days": "integer",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

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
- **404 Not Found**: Resource not found
- **409 Conflict**: Resource already exists (for creation operations)
- **400 Bad Request**: Invalid request data or parameters

## Rate Limiting

All endpoints are subject to rate limiting middleware. Exceeding rate limits will result in `429 Too Many Requests` responses.

## Dependencies

This module depends on:

- `client_account_service`: Business logic for client account operations
- `has_permission`: Authorization dependency for permission checking
- `valid_account_id`: Validation dependency for account ID format

## Security Considerations

1. All endpoints require authentication via Bearer token
2. Permission-based access control is enforced
3. Input validation is performed on all request data
4. Rate limiting prevents abuse
5. Audit logging may be implemented for account modifications

## Usage Notes

- Account IDs are MongoDB ObjectIds and must be valid 24-character hexadecimal strings
- Pagination is supported on the list endpoint with `skip` and `limit` parameters
- Status field uses enum values: `"active"` or `"suspended"`
- Main contact user ID must reference a valid user in the system
- Data retention policy is specified in days (optional field)
- All timestamps are in ISO 8601 format with UTC timezone
