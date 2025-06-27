# Client Account Routes Documentation

## Overview

The Client Account Routes provide a comprehensive API for managing client accounts within the authentication system with **complete hierarchical multi-platform tenancy support**. This module handles all CRUD operations for client accounts with proper authentication, **hierarchical permission controls**, and **specialized platform management workflows**.

**Base URL:** `/v1/client_accounts`  
**Tags:** Client Account Management

## 🏢 **Complete Hierarchical Multi-Platform Tenancy**

This API supports a complete three-tier permission hierarchy with platform management:

- **Super Admins**: Complete system access across all platforms (`client:manage_all`)
- **Platform Managers**: Can manage clients within their platform (`client:manage_platform`)
- **Platform Viewers**: Can read clients within their platform (`client:read_platform`)
- **Client Users**: Access only their own client account (`client:read_own`)

## 🚀 **Advanced Permission System**

**✅ Hierarchical Permissions**: Platform permissions automatically include client permissions
**✅ Dynamic Access Control**: Runtime permission checking with context-aware filtering
**✅ Multi-Tenant Isolation**: Secure data separation between platforms and clients
**✅ Scalable Architecture**: Reverse reference design for unlimited sub-clients

## 🔄 **Scalable Hierarchical Design**

The system uses a **reverse reference architecture** for optimal performance:

- **Parent-Child Relationships**: Children reference their parent via `created_by_client_id`
- **No Arrays in Parents**: Parent documents don't store child lists (avoids MongoDB document size limits)
- **Unlimited Children**: Platform roots can have thousands of sub-clients without performance degradation
- **Efficient Queries**: Child lookups use indexed queries for O(log n) performance

## Authentication & Authorization

All endpoints require authentication and are protected by dependency functions that implement hierarchical permission checking:

- **Read Access:** Requires one of: `client:read_all`, `client:read_platform` (via `can_read_client_accounts`)
- **Manage Access:** Requires one of: `client:manage_all`, `client:manage_platform` (via `can_manage_client_accounts`)
- **Individual Access:** Uses `has_hierarchical_client_access` for per-resource authorization

### Hierarchical Permission System

The permission system follows a hierarchical structure where higher-level permissions automatically include lower-level ones:

- `client:manage_all` → Includes all client permissions (global admin)
- `client:manage_platform` → Includes `client:read_platform`, `client:read_own`
- `client:read_all` → Includes `client:read_platform`, `client:read_own`
- `client:read_platform` → Includes `client:read_own`
- `client:read_own` → Base client-level read access

### Additional System Permissions

- `client:create` → Create top-level client accounts (super admin only)
- `client:create_sub` → Create sub-clients within platform scope (platform-specific)

## Endpoints

### 1. Create Client Account (Super Admin Only)

Creates a new top-level client account in the system. This is typically used for creating platform root accounts.

**Endpoint:** `POST /v1/client_accounts/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_client_accounts` (requires `client:manage_all` or `client:manage_platform`)

**Request Body:**

```json
{
  "name": "Real Estate Platform Root",
  "description": "Root client for real estate platform",
  "main_contact_user_id": "507f1f77bcf86cd799439015",
  "platform_id": "real_estate_platform",
  "is_platform_root": true
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Real Estate Platform Root",
  "description": "Root client for real estate platform",
  "status": "active",
  "main_contact_user_id": "507f1f77bcf86cd799439015",
  "data_retention_policy_days": null,
  "platform_id": "real_estate_platform",
  "created_by_client_id": null,
  "is_platform_root": true,
  "created_by_platform": false,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Client account with this name already exists
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

### 2. Create Sub-Client Account (Platform Managers)

Creates a sub-client account under the current user's client account. Available to platform managers with appropriate permissions.

**Endpoint:** `POST /v1/client_accounts/sub-clients`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_client_accounts` (requires `client:manage_all` or `client:manage_platform`)

**Request Body:**

```json
{
  "name": "ACME Properties",
  "description": "Real estate company under platform",
  "main_contact_user_id": "507f1f77bcf86cd799439016"
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "ACME Properties",
  "description": "Real estate company under platform",
  "status": "active",
  "main_contact_user_id": "507f1f77bcf86cd799439016",
  "data_retention_policy_days": null,
  "platform_id": "real_estate_platform",
  "created_by_client_id": "507f1f77bcf86cd799439011",
  "is_platform_root": false,
  "created_by_platform": true,
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Client account with this name already exists
- `403 Forbidden` - Insufficient permissions or user not associated with client account
- `401 Unauthorized` - Invalid authentication

### 3. Get All Client Accounts (Hierarchical Filtering)

Retrieves a paginated list of client accounts with **automatic hierarchical filtering** based on user permissions.

**Endpoint:** `GET /v1/client_accounts/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** Runtime permission checking (no dependency - permissions checked in route)

**Query Parameters:**

- `skip` (optional, integer, default: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100) - Maximum number of records to return
- `platform_scope` (optional, string) - Filter hint (not currently used, filtering is automatic)

**Dynamic Authorization Logic:**

- **Super Admins** (`client:read_all` or `client:create` + `client:manage_all`): See all client accounts
- **Platform Staff** (`client:read_platform` + platform root): See all accounts in their platform
- **Platform Members** (`client:read_platform` + regular client): See accounts within same platform
- **Regular Users** (`client:read_own`): See only their own account

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "Real Estate Platform Root",
    "description": "Root client for real estate platform",
    "status": "active",
    "main_contact_user_id": "507f1f77bcf86cd799439015",
    "data_retention_policy_days": null,
    "platform_id": "real_estate_platform",
    "created_by_client_id": null,
    "is_platform_root": true,
    "created_by_platform": false,
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z"
  },
  {
    "id": "507f1f77bcf86cd799439012",
    "name": "ACME Properties",
    "description": "Real estate company under platform",
    "status": "active",
    "main_contact_user_id": "507f1f77bcf86cd799439016",
    "data_retention_policy_days": null,
    "platform_id": "real_estate_platform",
    "created_by_client_id": "507f1f77bcf86cd799439011",
    "is_platform_root": false,
    "created_by_platform": true,
    "created_at": "2024-01-15T11:00:00Z",
    "updated_at": "2024-01-15T11:00:00Z"
  }
]
```

**Note:** Child client relationships are not included in list responses for performance. Use the `/my-sub-clients` endpoint to get children.

### 4. Get My Sub-Clients

Retrieves all sub-clients created by the current user's client account using efficient reverse queries.

**Endpoint:** `GET /v1/client_accounts/my-sub-clients`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_client_accounts` (requires `client:read_all` or `client:read_platform`)

**Query Parameters:**

- `skip` (optional, integer, default: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100) - Maximum number of records to return

**Performance Note:** This endpoint uses an indexed query on `created_by_client_id` for optimal performance even with thousands of sub-clients.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "507f1f77bcf86cd799439012",
    "name": "ACME Properties",
    "description": "Real estate company under platform",
    "status": "active",
    "main_contact_user_id": "507f1f77bcf86cd799439016",
    "data_retention_policy_days": null,
    "platform_id": "real_estate_platform",
    "created_by_client_id": "507f1f77bcf86cd799439011",
    "is_platform_root": false,
    "created_by_platform": true,
    "created_at": "2024-01-15T11:00:00Z",
    "updated_at": "2024-01-15T11:00:00Z"
  }
]
```

### 5. Get Client Account by ID (Hierarchical Access Control)

Retrieves a specific client account by its ID with hierarchical access control.

**Endpoint:** `GET /v1/client_accounts/{account_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `has_hierarchical_client_access("account_id")` (context-aware access control)

**Path Parameters:**

- `account_id` (required, string) - The MongoDB ObjectId of the client account (validated by `valid_account_id`)

**Authorization:** Uses hierarchical access control to ensure users can only access accounts they have permission to view.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Real Estate Platform Root",
  "description": "Root client for real estate platform",
  "status": "active",
  "main_contact_user_id": "507f1f77bcf86cd799439015",
  "data_retention_policy_days": null,
  "platform_id": "real_estate_platform",
  "created_by_client_id": null,
  "is_platform_root": true,
  "created_by_platform": false,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Client account not found or access denied (prevents information disclosure)
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid account ID format

### 6. Update Client Account (Hierarchical Access Control)

Updates an existing client account with hierarchical access control.

**Endpoint:** `PUT /v1/client_accounts/{account_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:**

- `can_manage_client_accounts` (requires `client:manage_all` or `client:manage_platform`)
- `has_hierarchical_client_access("account_id")` (context-aware access control)

**Path Parameters:**

- `account_id` (required, string) - The MongoDB ObjectId of the client account (validated by `valid_account_id`)

**Request Body:**

```json
{
  "name": "Updated Platform Client",
  "description": "Updated description",
  "status": "active",
  "main_contact_user_id": "507f1f77bcf86cd799439017",
  "data_retention_policy_days": 90,
  "platform_id": "real_estate_platform",
  "is_platform_root": false
}
```

**Note:** `created_by_client_id` is not updatable for security reasons. Child relationships are managed automatically through reverse references.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Updated Platform Client",
  "description": "Updated description",
  "status": "active",
  "main_contact_user_id": "507f1f77bcf86cd799439017",
  "data_retention_policy_days": 90,
  "platform_id": "real_estate_platform",
  "created_by_client_id": null,
  "is_platform_root": false,
  "created_by_platform": false,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T12:30:00Z"
}
```

### 7. Delete Client Account (Hierarchical Access Control)

Deletes a client account from the system with hierarchical access control.

**Endpoint:** `DELETE /v1/client_accounts/{account_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:**

- `can_manage_client_accounts` (requires `client:manage_all` or `client:manage_platform`)
- `has_hierarchical_client_access("account_id")` (context-aware access control)

**Path Parameters:**

- `account_id` (required, string) - The MongoDB ObjectId of the client account (validated by `valid_account_id`)

**Authorization:** Uses hierarchical access control to ensure users can only delete accounts they have permission to access.

**Note:** Parent-child relationships are automatically maintained through reverse references - no additional cleanup needed.

**Response:**

- **Status Code:** `204 No Content`
- **Response Body:** Empty

### 8. Onboard New Client (Platform Staff)

**✅ SPECIALIZED ENDPOINT** - Platform staff onboarding workflow with enhanced validation and tracking.

**Endpoint:** `POST /v1/client_accounts/onboard-client`

**Authentication Required:** Yes (Access Token)

**Required Validation:**

- User must have `is_platform_staff: true`
- User must have `client_account:create` permission (note: legacy permission check)

**Request Body:**

```json
{
  "name": "Elite Properties Real Estate",
  "description": "Luxury real estate firm joining PropertyHub platform",
  "main_contact_user_id": "507f1f77bcf86cd799439018"
}
```

**Features:**

- **Platform Staff Validation**: Only platform staff can access this endpoint
- **Enhanced Tracking**: Automatically sets hierarchical relationship tracking
- **Permission Validation**: Checks for appropriate creation permissions
- **Business Intelligence**: Integrates with platform analytics for client lifecycle tracking

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439013",
  "name": "Elite Properties Real Estate",
  "description": "Luxury real estate firm joining PropertyHub platform",
  "status": "active",
  "main_contact_user_id": "507f1f77bcf86cd799439018",
  "data_retention_policy_days": null,
  "platform_id": "real_estate_platform",
  "created_by_client_id": "507f1f77bcf86cd799439011",
  "is_platform_root": false,
  "created_by_platform": true,
  "created_at": "2024-01-15T13:00:00Z",
  "updated_at": "2024-01-15T13:00:00Z"
}
```

**Error Responses:**

- `403 Forbidden` - User is not platform staff or lacks creation permissions
- `409 Conflict` - Client account with this name already exists
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request body or missing required fields

## Permission Requirements

### Required Dependencies by Endpoint

| Endpoint                             | Method | Required Dependencies                                           |
| ------------------------------------ | ------ | --------------------------------------------------------------- |
| `/v1/client_accounts/`               | GET    | Runtime permission checking                                     |
| `/v1/client_accounts/`               | POST   | `can_manage_client_accounts`                                    |
| `/v1/client_accounts/sub-clients`    | POST   | `can_manage_client_accounts`                                    |
| `/v1/client_accounts/my-sub-clients` | GET    | `can_read_client_accounts`                                      |
| `/v1/client_accounts/{account_id}`   | GET    | `has_hierarchical_client_access`                                |
| `/v1/client_accounts/{account_id}`   | PUT    | `can_manage_client_accounts` + `has_hierarchical_client_access` |
| `/v1/client_accounts/{account_id}`   | DELETE | `can_manage_client_accounts` + `has_hierarchical_client_access` |
| `/v1/client_accounts/onboard-client` | POST   | Platform staff validation + custom permission check             |

### Dependency Function Mappings

- `can_read_client_accounts` requires any of: `client:read_all`, `client:read_platform`
- `can_manage_client_accounts` requires any of: `client:manage_all`, `client:manage_platform`
- `has_hierarchical_client_access` provides context-aware resource-level access control
- `valid_account_id` validates MongoDB ObjectId format

## Scope-Based Access Control

### Super Admins (`client:manage_all`)

- Can access and manage client accounts across all platforms
- No restrictions on client operations
- Can create top-level platform root accounts

### Platform Managers (`client:manage_platform`)

- Can manage client accounts within their platform scope only
- Can create sub-clients under their platform
- Cannot access other platform's clients

### Platform Viewers (`client:read_platform`)

- Can read client accounts within their platform scope only
- Cannot modify client accounts
- Automatic filtering based on platform context

### Client Users (`client:read_own`)

- Can read only their own client account
- Cannot modify client accounts (requires manage permissions)
- Most restrictive access level

## Data Models

### ClientAccountCreateSchema

```json
{
  "name": "string (required, 1-100 chars)",
  "description": "string (optional)",
  "main_contact_user_id": "string (optional, MongoDB ObjectId)",
  "platform_id": "string (optional)",
  "created_by_client_id": "string (optional, auto-set)",
  "is_platform_root": "boolean (optional, default: false)"
}
```

### ClientAccountUpdateSchema

```json
{
  "name": "string (optional, 1-100 chars)",
  "description": "string (optional)",
  "status": "active | suspended (optional)",
  "main_contact_user_id": "string (optional, MongoDB ObjectId)",
  "data_retention_policy_days": "integer (optional)",
  "platform_id": "string (optional)",
  "is_platform_root": "boolean (optional)"
}
```

**Note:** `created_by_client_id` is managed automatically and not directly updatable for security reasons.

### ClientAccountResponseSchema

```json
{
  "id": "string (MongoDB ObjectId)",
  "name": "string",
  "description": "string",
  "status": "active | suspended",
  "main_contact_user_id": "string (MongoDB ObjectId)",
  "data_retention_policy_days": "integer",
  "platform_id": "string",
  "created_by_client_id": "string (MongoDB ObjectId)",
  "is_platform_root": "boolean",
  "created_by_platform": "boolean (computed field)",
  "created_at": "datetime (ISO 8601)",
  "updated_at": "datetime (ISO 8601)"
}
```

**Performance Note:** Child client lists are not included in individual responses. Use the `/my-sub-clients` endpoint for efficient child queries.

## 🔒 **Security & Access Control**

### Hierarchical Authorization

The API implements sophisticated hierarchical access control:

1. **Information Disclosure Prevention**: Returns `404 Not Found` instead of `403 Forbidden` when users attempt to access accounts outside their scope
2. **Dynamic Permission Checking**: The `GET /` endpoint performs runtime permission evaluation for flexible access control
3. **Platform Isolation**: Users cannot access accounts from other platforms unless they're super admins
4. **Context-Aware Dependencies**: `has_hierarchical_client_access` validates per-resource access rights

### Access Patterns

- **Super Admin Access**: Can access any client account across all platforms
- **Platform Manager Access**: Can access and manage all accounts within their `platform_id`
- **Platform Viewer Access**: Can read all accounts within their `platform_id`
- **Regular User Access**: Can access only their own client account

## 🚀 **Performance & Scalability**

### Reverse Reference Architecture

The system uses a **reverse reference design** for optimal MongoDB performance:

- **No Document Size Limits**: Parent documents don't store child arrays, avoiding MongoDB's 16MB document limit
- **Concurrent Write Performance**: Multiple sub-clients can be created simultaneously without write contention
- **Indexed Queries**: Child lookups use the `created_by_client_id` index for O(log n) performance
- **Efficient Pagination**: Child listing supports proper pagination even with thousands of sub-clients

### Query Performance

```json
// Fast child lookup using indexed field
{
  "created_by_client_id": "parent_id"
}

// Compound queries for filtered results
{
  "created_by_client_id": "parent_id",
  "status": "active",
  "platform_id": "real_estate"
}
```

### Scalability Metrics

- **Unlimited Children**: Platform roots can have thousands of sub-clients
- **Fast Child Queries**: O(log n) lookup performance with proper indexing
- **Concurrent Creation**: No parent document locking during sub-client creation
- **Efficient Pagination**: Full pagination support for large child sets

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

- `client_account_service`: Enhanced business logic for hierarchical client account operations with reverse reference queries
- `can_read_client_accounts`: Read permission dependency (requires `client:read_all` or `client:read_platform`)
- `can_manage_client_accounts`: Manage permission dependency (requires `client:manage_all` or `client:manage_platform`)
- `has_hierarchical_client_access`: Context-aware resource-level access control dependency
- `get_current_user`: User context for authorization decisions
- `valid_account_id`: Validation dependency for MongoDB ObjectId format
- `user_service`: For retrieving user effective permissions
- `permission_service`: For hierarchical permission checking

## Usage Notes

### Hierarchical Relationships

- When creating sub-clients via `/sub-clients`, the `platform_id` is automatically inherited from the parent
- The `created_by_client_id` is automatically set to the current user's client account ID
- Child relationships are maintained through reverse references for optimal performance
- Use `/my-sub-clients` endpoint to efficiently query child accounts

### Platform Scoping

- Account IDs are MongoDB ObjectIds and must be valid 24-character hexadecimal strings
- Platform IDs are string identifiers (e.g., "real_estate_platform", "crm_platform")
- Platform root accounts should have `is_platform_root: true` for proper identification
- All timestamps are in ISO 8601 format with UTC timezone

### Real-World Examples

**Real Estate Platform Scenario:**

1. Create platform root: `POST /v1/client_accounts/` with `platform_id: "real_estate"`
2. Platform manager creates property companies: `POST /v1/client_accounts/sub-clients`
3. Platform manager views all real estate clients: `GET /v1/client_accounts/`
4. Platform manager views their sub-clients: `GET /v1/client_accounts/my-sub-clients`

**CRM Platform Scenario:**

1. Create platform root: `POST /v1/client_accounts/` with `platform_id: "crm_platform"`
2. Platform manager creates business clients: `POST /v1/client_accounts/sub-clients`
3. Platform manager views only their platform clients: `GET /v1/client_accounts/`

**Large Scale Example:**

- Platform with 5,000+ sub-clients: `/my-sub-clients?skip=0&limit=50` provides efficient pagination
- Child count queries: Use MongoDB aggregation for counting without loading all documents
- Filtered searches: Combine `created_by_client_id` with other filters for targeted results
