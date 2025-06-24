# Permission Routes Documentation

## Overview

The Permission Routes provide a comprehensive API for managing scoped permissions within the three-tier authentication system. This module handles CRUD operations for permissions, which define granular access control capabilities across system, platform, and client organizational levels. Permissions use human-readable string identifiers with scope-based isolation and validation.

**Base URL:** `/v1/permissions`  
**Tags:** Permission Management

## Architecture

### Three-Tier Scoped Permissions

Permissions are organized in a three-tier hierarchy with proper isolation:

```
SYSTEM PERMISSIONS (Global)
├─ user:create              # Create users across any scope
├─ platform:create          # Create new platforms
└─ system:infrastructure    # Manage core infrastructure

PLATFORM PERMISSIONS (Per Platform)
├─ platform:analytics       # Platform-wide analytics
├─ client_account:create     # Create client accounts
└─ platform:support         # Cross-client support

CLIENT PERMISSIONS (Per Client Organization)
├─ client:listings:create    # Create property listings
├─ client:users:manage       # Manage client users
└─ client:reports:view       # View client reports
```

## Authentication & Authorization

All endpoints require authentication and specific scoped permissions:

- **Base Permission:** `system:permission:read` (required for all endpoints)
- **Additional Permissions:** Specific endpoints require additional permissions as noted below

### Scope-Based Access Control

- **Super Admins:** Can create/manage permissions at all scopes
- **Platform Admins:** Can create/manage permissions within their platform only
- **Client Admins:** Can create/manage permissions within their client only
- **Regular Users:** Cannot create permissions

## Permission Naming Convention

Permissions follow a structured naming pattern with scope prefixes:

### System Permissions

- `user:create` - Create users across any scope
- `platform:create` - Create new platforms
- `system:infrastructure:manage` - Manage core infrastructure

### Platform Permissions

- `platform:analytics:view` - View platform analytics
- `platform:support:all_clients` - Support across all platform clients
- `client_account:create` - Create client accounts

### Client Permissions

- `client:listings:create` - Create listings within client
- `client:users:manage` - Manage users within client
- `client:reports:view` - View client-specific reports

## Endpoints

### 1. Create Scoped Permission

Creates a new permission within a specific scope with proper validation and isolation.

**Endpoint:** `POST /v1/permissions/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `system:permission:create`

**Query Parameters:**

- `scope_id` (optional, string) - Platform ID or Client ID for scoped permissions (auto-determined from user context if not provided)

**Request Body:**

```json
{
  "name": "client:listings:create",
  "display_name": "Create Listings",
  "description": "Allows creating new property listings",
  "scope": "client"
}
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "client:listings:create",
  "display_name": "Create Listings",
  "description": "Allows creating new property listings",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Permission with this name already exists in scope
- `403 Forbidden` - Insufficient permissions or invalid scope access
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request data or scope validation failed

**Example Requests:**

```bash
# System permission (super admin only)
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "user:create",
       "display_name": "Create Users",
       "description": "Create users in any scope",
       "scope": "system"
     }'

# Platform permission
curl -X POST "https://api.example.com/v1/permissions/?scope_id=real_estate_platform" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "platform:analytics:view",
       "display_name": "View Platform Analytics",
       "description": "Access platform-wide analytics and reports",
       "scope": "platform"
     }'

# Client permission (auto-scoped to user's client)
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "client:listings:create",
       "display_name": "Create Listings",
       "description": "Create property listings within client",
       "scope": "client"
     }'
```

### 2. Get Permissions with Scope Filtering

Retrieves a paginated list of permissions with optional scope filtering.

**Endpoint:** `GET /v1/permissions/`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `system:permission:read`

**Query Parameters:**

- `skip` (optional, integer, default: 0, min: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100, min: 1, max: 1000) - Maximum number of records to return
- `scope` (optional, string) - Filter by permission scope (`system`, `platform`, `client`)
- `scope_id` (optional, string) - Filter by specific scope ID

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "user:create",
    "display_name": "Create Users",
    "description": "Create users in any scope",
    "scope": "system",
    "scope_id": null,
    "created_by_user_id": "507f1f77bcf86cd799439012",
    "created_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "507f1f77bcf86cd799439013",
    "name": "client:listings:create",
    "display_name": "Create Listings",
    "description": "Create property listings within client",
    "scope": "client",
    "scope_id": "685a5f2e82e92ad29111a6a9",
    "created_by_user_id": "507f1f77bcf86cd799439014",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

**Error Responses:**

- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid query parameters

**Example Requests:**

```bash
# Get all permissions user can view
curl -X GET "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>"

# Get only client permissions for specific client
curl -X GET "https://api.example.com/v1/permissions/?scope=client&scope_id=685a5f2e82e92ad29111a6a9" \
     -H "Authorization: Bearer <access_token>"

# Get platform permissions
curl -X GET "https://api.example.com/v1/permissions/?scope=platform&scope_id=real_estate_platform" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Available Permissions for Assignment

Retrieves permissions that the current user can assign to roles or groups, grouped by scope.

**Endpoint:** `GET /v1/permissions/available`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `system:permission:read`

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "system_permissions": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "user:read",
      "display_name": "Read Users",
      "description": "View user information",
      "scope": "system",
      "scope_id": null
    }
  ],
  "platform_permissions": [
    {
      "id": "507f1f77bcf86cd799439012",
      "name": "platform:analytics:view",
      "display_name": "View Platform Analytics",
      "description": "Access platform-wide analytics",
      "scope": "platform",
      "scope_id": "real_estate_platform"
    }
  ],
  "client_permissions": [
    {
      "id": "507f1f77bcf86cd799439013",
      "name": "client:listings:create",
      "display_name": "Create Listings",
      "description": "Create property listings",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
    },
    {
      "id": "507f1f77bcf86cd799439014",
      "name": "client:leads:assign",
      "display_name": "Assign Leads",
      "description": "Assign leads to sales representatives",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9"
    }
  ]
}
```

**Error Responses:**

- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/available" \
     -H "Authorization: Bearer <access_token>"
```

### 4. Get Permission by ID

Retrieves a specific permission by its MongoDB ObjectId.

**Endpoint:** `GET /v1/permissions/{permission_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `system:permission:read`

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "client:listings:create",
  "display_name": "Create Listings",
  "description": "Create property listings within client",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Permission not found or not accessible by user
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid permission ID format

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

### 5. Update Permission

Updates an existing permission's information.

**Endpoint:** `PUT /v1/permissions/{permission_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `system:permission:update`

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Request Body:**

```json
{
  "display_name": "Create Property Listings",
  "description": "Updated description for creating property listings"
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "client:listings:create",
  "display_name": "Create Property Listings",
  "description": "Updated description for creating property listings",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T12:30:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Permission not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request data

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "display_name": "Create Property Listings",
       "description": "Updated description for creating property listings"
     }'
```

### 6. Delete Permission

Deletes a permission from the system.

**Endpoint:** `DELETE /v1/permissions/{permission_id}`

**Authentication Required:** Yes (Access Token)

**Required Permissions:** `system:permission:delete`

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `404 Not Found` - Permission not found
- `403 Forbidden` - Insufficient permissions or scope access denied
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

## Scope-Based Permission Categories

### System Permissions (Global)

**Core Authentication:**

- `user:create` - Create users across any scope
- `user:read` - View users across any scope
- `user:update` - Update users across any scope
- `user:delete` - Delete users across any scope

**Platform Management:**

- `platform:create` - Create new platform instances
- `platform:read` - View platform information
- `platform:update` - Update platform settings
- `platform:delete` - Delete platforms

**Infrastructure:**

- `system:infrastructure:manage` - Full infrastructure access
- `system:monitoring:view` - View system monitoring
- `system:logs:read` - Access system logs

### Platform Permissions (Per Platform)

**Analytics & Reporting:**

- `platform:analytics:view` - View platform-wide analytics
- `platform:reports:create` - Create platform reports
- `platform:dashboard:manage` - Manage platform dashboards

**Client Management:**

- `client_account:create` - Create client accounts
- `client_account:read` - View client accounts
- `client_account:update` - Update client accounts
- `client_account:delete` - Delete client accounts

**Support:**

- `platform:support:all_clients` - Support across all platform clients
- `platform:support:escalate` - Escalate support tickets

### Client Permissions (Per Client Organization)

**Business Operations:**

- `client:listings:create` - Create property listings
- `client:listings:update` - Update listings
- `client:listings:delete` - Delete listings
- `client:leads:assign` - Assign leads to agents

**User Management:**

- `client:users:manage` - Manage users within client
- `client:roles:assign` - Assign roles within client
- `client:groups:manage` - Manage groups within client

**Reporting:**

- `client:reports:view` - View client-specific reports
- `client:analytics:access` - Access client analytics
- `client:metrics:export` - Export client metrics

## Data Models

### PermissionCreateSchema

```json
{
  "name": "string (required)",
  "display_name": "string (optional)",
  "description": "string (optional)",
  "scope": "system | platform | client (required)"
}
```

### PermissionUpdateSchema

```json
{
  "display_name": "string (optional)",
  "description": "string (optional)"
}
```

### PermissionResponseSchema

```json
{
  "id": "string (MongoDB ObjectId)",
  "name": "string",
  "display_name": "string",
  "description": "string",
  "scope": "system | platform | client",
  "scope_id": "string | null",
  "created_by_user_id": "string",
  "created_by_client_id": "string | null",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

### AvailablePermissionsResponseSchema

```json
{
  "system_permissions": ["PermissionResponseSchema"],
  "platform_permissions": ["PermissionResponseSchema"],
  "client_permissions": ["PermissionResponseSchema"]
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
- `204 No Content` - Permission deleted successfully
- `400 Bad Request` - Invalid request data or parameters
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions or scope access denied
- `404 Not Found` - Permission not found
- `409 Conflict` - Permission with name already exists in scope

### Scope-Specific Error Scenarios

**403 Forbidden (Scope Access):**

```json
{
  "detail": "Cannot create platform permissions - insufficient platform access"
}
```

**409 Conflict (Scoped Uniqueness):**

```json
{
  "detail": "Permission 'client:listings:create' already exists in this client scope"
}
```

**400 Bad Request (Scope Validation):**

```json
{
  "detail": "scope_id required for platform and client permissions"
}
```

## Best Practices

### Permission Design

1. **Scope Appropriately:** Use the most restrictive scope that meets business needs
2. **Consistent Naming:** Follow naming conventions within each scope
3. **Granular Control:** Create specific permissions rather than broad ones
4. **Business Alignment:** Match permissions to actual business processes

### Scope Management

1. **System Permissions:** Only for truly global capabilities
2. **Platform Permissions:** For cross-client platform features
3. **Client Permissions:** For organization-specific business logic
4. **Avoid Scope Creep:** Don't make client permissions when platform would suffice

### API Usage

1. **Use Available Endpoint:** Check `/available` to get permissions user can assign
2. **Handle Scope Contexts:** Let backend auto-determine scope_id when possible
3. **Filter Appropriately:** Use scope and scope_id filters for performance
4. **Error Handling:** Handle scope-related 403 errors gracefully

### Security Considerations

1. **Scope Isolation:** Ensure permissions are properly isolated by scope
2. **Validation:** Validate scope_id matches user's access context
3. **Audit Logging:** Log all permission creation and modification events
4. **Regular Review:** Audit permissions within each scope periodically

## Real-World Examples

### Lead Generation Company Permission Setup

```bash
# System Level: Core auth permissions
curl -X POST "https://api.example.com/v1/permissions/" \
     -d '{"name": "user:create", "scope": "system"}'

# Platform Level: RE/MAX corporate permissions
curl -X POST "https://api.example.com/v1/permissions/?scope_id=remax_platform" \
     -d '{"name": "platform:brand:manage", "scope": "platform"}'

# Client Level: Individual franchise permissions
curl -X POST "https://api.example.com/v1/permissions/" \
     -d '{"name": "client:listings:create", "scope": "client"}'
```

### Permission Assignment Workflow

```bash
# 1. Check available permissions for role assignment
curl -X GET "https://api.example.com/v1/permissions/available"

# 2. Create business-specific permission
curl -X POST "https://api.example.com/v1/permissions/" \
     -d '{"name": "client:commissions:calculate", "scope": "client"}'

# 3. Assign to role or group (handled by role/group APIs)
```

## Integration Notes

### Role & Group Assignment

Permissions created through this API are assigned to users through:

- **Roles:** Template-based permission packages for user types
- **Groups:** Team-based permission packages for collaboration
- **Aggregation:** Users receive combined permissions from both sources

### Access Control Validation

The system uses scoped permissions for:

- API endpoint access control with scope awareness
- UI feature visibility based on user's scope context
- Resource-level access restrictions with tenant isolation
- Multi-tier organizational authorization

### Frontend Integration

```javascript
// Check user's effective permissions (includes scope context)
const userPermissions = userStore.effectivePermissions;

const canCreateListings = userPermissions.includes("client:listings:create");
const canViewPlatformAnalytics = userPermissions.includes("platform:analytics:view");
const canManageUsers = userPermissions.includes("user:create");
```
