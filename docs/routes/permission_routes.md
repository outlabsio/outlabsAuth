# Permission Routes Documentation

## Overview

The Permission Routes provide a comprehensive API for managing scoped permissions within the three-tier authentication system. This module handles CRUD operations for permissions, which define granular access control capabilities across system, platform, and client organizational levels. Permissions are stored as MongoDB documents with proper scope-based isolation and validation.

**Base URL:** `/v1/permissions`  
**Tags:** ["Permission Management"]

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Read Operations:** `can_read_permissions` dependency (requires any of: `permission:read_all`, `permission:read_platform`)
- **Write Operations:** `can_manage_permissions` dependency (requires any of: `permission:manage_all`, `permission:manage_platform`)
- **Available Permissions:** `require_admin` dependency for admin-only operations

## Permission Scoping

Permissions are organized in a three-tier hierarchy using the `PermissionScope` enum:

### Scope Types

- **`system`**: Global permissions for system-wide operations
- **`platform`**: Platform-specific permissions for multi-tenant platforms
- **`client`**: Client-specific permissions for individual organizations

### Scope ID Requirements

- **System permissions**: `scope_id` is `null` (not required)
- **Platform permissions**: `scope_id` must be the platform identifier
- **Client permissions**: `scope_id` must be the client account ID (can be auto-determined from user context)

---

## Endpoints

### 1. Create Permission

Creates a new scoped permission with proper validation and uniqueness checking.

**Endpoint:** `POST /v1/permissions/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_permissions`

**Query Parameters:**

- `scope_id` (optional, string) - Platform ID or Client ID for scoped permissions (auto-determined from user context if not provided)

**Request Body:**

```json
{
  "name": "listings:create",
  "display_name": "Create Listings",
  "description": "Allows creating new property listings",
  "scope": "client"
}
```

**Field Requirements:**

- `name` (required, string) - Permission name without scope prefix
- `display_name` (required, string) - Human-readable permission name
- `description` (optional, string) - Description of what this permission allows
- `scope` (required, PermissionScope) - Permission scope: `system`, `platform`, or `client`

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "listings:create",
  "display_name": "Create Listings",
  "description": "Allows creating new property listings",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9"
}
```

**Error Responses:**

- `409 Conflict` - Permission with this name already exists in scope
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request data or missing scope requirements

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
curl -X POST "https://api.example.com/v1/permissions/?scope_id=platform_123" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "analytics:view",
       "display_name": "View Platform Analytics",
       "description": "Access platform-wide analytics and reports",
       "scope": "platform"
     }'

# Client permission (auto-scoped to user's client)
curl -X POST "https://api.example.com/v1/permissions/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "listings:create",
       "display_name": "Create Listings",
       "description": "Create property listings within client",
       "scope": "client"
     }'
```

### 2. Get Permissions

Retrieves a paginated list of permissions with optional scope filtering.

**Endpoint:** `GET /v1/permissions/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_permissions`

**Query Parameters:**

- `skip` (optional, integer, default: 0, min: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100, min: 1, max: 1000) - Maximum number of records to return
- `scope` (optional, PermissionScope) - Filter by permission scope (`system`, `platform`, `client`)
- `scope_id` (optional, string) - Filter by specific scope ID

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "_id": "507f1f77bcf86cd799439011",
    "name": "user:create",
    "display_name": "Create Users",
    "description": "Create users in any scope",
    "scope": "system",
    "scope_id": null,
    "created_by_user_id": "507f1f77bcf86cd799439012",
    "created_by_client_id": null
  },
  {
    "_id": "507f1f77bcf86cd799439013",
    "name": "listings:create",
    "display_name": "Create Listings",
    "description": "Create property listings within client",
    "scope": "client",
    "scope_id": "685a5f2e82e92ad29111a6a9",
    "created_by_user_id": "507f1f77bcf86cd799439014",
    "created_by_client_id": "685a5f2e82e92ad29111a6a9"
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
curl -X GET "https://api.example.com/v1/permissions/?scope=platform&scope_id=platform_123" \
     -H "Authorization: Bearer <access_token>"

# Get with pagination
curl -X GET "https://api.example.com/v1/permissions/?skip=10&limit=20" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Available Permissions

Retrieves permissions that the current user can assign to roles or groups, grouped by scope.

**Endpoint:** `GET /v1/permissions/available`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `require_admin`

**Note:** This is an admin-only endpoint that returns permissions based on the user's scope and access level.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "system_permissions": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "name": "user:read",
      "display_name": "Read Users",
      "description": "View user information",
      "scope": "system",
      "scope_id": null,
      "created_by_user_id": "507f1f77bcf86cd799439012",
      "created_by_client_id": null
    }
  ],
  "platform_permissions": [
    {
      "_id": "507f1f77bcf86cd799439012",
      "name": "analytics:view",
      "display_name": "View Platform Analytics",
      "description": "Access platform-wide analytics",
      "scope": "platform",
      "scope_id": "platform_123",
      "created_by_user_id": "507f1f77bcf86cd799439013",
      "created_by_client_id": null
    }
  ],
  "client_permissions": [
    {
      "_id": "507f1f77bcf86cd799439013",
      "name": "listings:create",
      "display_name": "Create Listings",
      "description": "Create property listings",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "created_by_user_id": "507f1f77bcf86cd799439014",
      "created_by_client_id": "685a5f2e82e92ad29111a6a9"
    },
    {
      "_id": "507f1f77bcf86cd799439014",
      "name": "leads:assign",
      "display_name": "Assign Leads",
      "description": "Assign leads to sales representatives",
      "scope": "client",
      "scope_id": "685a5f2e82e92ad29111a6a9",
      "created_by_user_id": "507f1f77bcf86cd799439015",
      "created_by_client_id": "685a5f2e82e92ad29111a6a9"
    }
  ]
}
```

**Authorization Logic:**

- **Super Admins**: Can see all system, platform, and client permissions
- **Platform Admins**: Can see platform permissions within their platform and client permissions
- **Client Admins**: Can see client permissions within their client account

**Error Responses:**

- `403 Forbidden` - Insufficient admin permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/available" \
     -H "Authorization: Bearer <admin_token>"
```

### 4. Get Permission by ID

Retrieves a specific permission by its MongoDB ObjectId.

**Endpoint:** `GET /v1/permissions/{permission_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_permissions`

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "listings:create",
  "display_name": "Create Listings",
  "description": "Create property listings within client",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9"
}
```

**Error Responses:**

- `404 Not Found` - Permission with ID not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

### 5. Update Permission

Updates an existing permission's information.

**Endpoint:** `PUT /v1/permissions/{permission_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_permissions`

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Request Body:**

All fields are optional for updates:

```json
{
  "name": "listings:manage",
  "display_name": "Manage Property Listings",
  "description": "Updated description for managing property listings"
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "listings:manage",
  "display_name": "Manage Property Listings",
  "description": "Updated description for managing property listings",
  "scope": "client",
  "scope_id": "685a5f2e82e92ad29111a6a9",
  "created_by_user_id": "507f1f77bcf86cd799439012",
  "created_by_client_id": "685a5f2e82e92ad29111a6a9"
}
```

**Error Responses:**

- `404 Not Found` - Permission with ID not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request data

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "display_name": "Manage Property Listings",
       "description": "Updated description for managing property listings"
     }'
```

### 6. Delete Permission

Deletes a permission from the system.

**Endpoint:** `DELETE /v1/permissions/{permission_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_permissions`

**Path Parameters:**

- `permission_id` (required, string) - The MongoDB ObjectId of the permission

**Response:**

- **Status Code:** `204 No Content`
- **Response Body:** Empty

**Error Responses:**

- `404 Not Found` - Permission with ID not found
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/permissions/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

---

## Data Models

### PermissionCreateSchema

```python
class PermissionCreateSchema(BaseModel):
    name: str                                      # Permission name without scope prefix (required)
    display_name: str                              # Human-readable permission name (required)
    description: Optional[str] = None              # What this permission allows (optional)
    scope: PermissionScope                         # Permission scope: system, platform, or client (required)
```

### PermissionUpdateSchema

```python
class PermissionUpdateSchema(BaseModel):
    name: Optional[str] = None                     # Permission name without scope prefix
    display_name: Optional[str] = None             # Human-readable permission name
    description: Optional[str] = None              # What this permission allows
```

### PermissionResponseSchema

```python
class PermissionResponseSchema(BaseModel):
    id: PydanticObjectId                           # Permission ID (aliased from _id)
    name: str                                      # Permission name
    display_name: str                              # Human-readable permission name
    description: Optional[str] = None              # Permission description
    scope: PermissionScope                         # Permission scope
    scope_id: Optional[str] = None                 # Scope identifier (platform/client ID)
    created_by_user_id: Optional[str] = None       # User who created this permission
    created_by_client_id: Optional[str] = None     # Client that created this permission
```

### PermissionDetailSchema

```python
class PermissionDetailSchema(BaseModel):
    id: str                                        # Permission ObjectId
    name: str                                      # Permission name (e.g., 'user:create')
    scope: PermissionScope                         # Permission scope
    display_name: str                              # Human-readable permission name
    description: Optional[str] = None              # What this permission allows
```

### AvailablePermissionsResponseSchema

```python
class AvailablePermissionsResponseSchema(BaseModel):
    system_permissions: List[PermissionResponseSchema] = []    # System-level permissions
    platform_permissions: List[PermissionResponseSchema] = [] # Platform-level permissions
    client_permissions: List[PermissionResponseSchema] = []   # Client-level permissions
```

### PermissionScope Enum

```python
class PermissionScope(str, Enum):
    SYSTEM = "system"      # Global/system level permissions
    PLATFORM = "platform"  # Platform level permissions
    CLIENT = "client"      # Client level permissions
```

---

## Permission Naming Conventions

### System Permissions

System permissions control global operations and are typically assigned to super admins:

- `user:create` - Create users across any scope
- `user:read` - View users across any scope
- `user:manage_all` - Full user management across all scopes
- `platform:create` - Create new platform instances
- `system:infrastructure` - Manage core infrastructure

### Platform Permissions

Platform permissions control platform-wide operations within a specific platform:

- `analytics:view` - View platform-wide analytics
- `client_account:create` - Create client accounts
- `support:all_clients` - Support across all platform clients
- `reports:platform` - Generate platform reports

### Client Permissions

Client permissions control operations within a specific client organization:

- `listings:create` - Create property listings
- `listings:update` - Update listings
- `leads:assign` - Assign leads to agents
- `reports:view` - View client-specific reports
- `users:manage` - Manage users within client

---

## Scope-Based Access Control

### Permission Creation Rules

1. **System Permissions**:

   - Can only be created by super admins
   - `scope_id` is always `null`
   - Apply globally across all platforms and clients

2. **Platform Permissions**:

   - Can be created by super admins or platform admins
   - Require `scope_id` to specify the platform
   - Apply to all clients within the specified platform

3. **Client Permissions**:
   - Can be created by super admins, platform admins, or client admins
   - `scope_id` can be provided or auto-determined from user's client account
   - Apply only within the specified client organization

### Uniqueness Constraints

Permissions must be unique within their scope:

- **System scope**: Permission name must be unique globally
- **Platform scope**: Permission name must be unique within the platform (`scope_id`)
- **Client scope**: Permission name must be unique within the client (`scope_id`)

This allows different platforms or clients to have permissions with the same name but different implementations.

---

## Error Handling

### Common Error Responses

**409 Conflict - Duplicate Permission**:

```json
{
  "detail": "Permission 'listings:create' already exists in client scope (685a5f2e82e92ad29111a6a9)"
}
```

**400 Bad Request - Missing Scope ID**:

```json
{
  "detail": "Client ID required for client-scoped permissions"
}
```

**400 Bad Request - Platform Scope ID Required**:

```json
{
  "detail": "Platform ID required for platform-scoped permissions"
}
```

**404 Not Found - Permission Not Found**:

```json
{
  "detail": "Permission with ID '507f1f77bcf86cd799439011' not found."
}
```

**403 Forbidden - Insufficient Permissions**:

```json
{
  "detail": "Insufficient permissions to manage permissions"
}
```

---

## Integration Examples

### Python Client Example

```python
import requests

class PermissionManagementClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def get_permissions(self, scope=None, scope_id=None, skip=0, limit=100):
        """Get permissions with optional filtering"""
        params = {"skip": skip, "limit": limit}
        if scope:
            params["scope"] = scope
        if scope_id:
            params["scope_id"] = scope_id

        response = requests.get(
            f"{self.base_url}/v1/permissions/",
            headers=self.headers,
            params=params
        )
        return response.json() if response.status_code == 200 else None

    def create_permission(self, permission_data, scope_id=None):
        """Create new permission with optional scope_id"""
        params = {}
        if scope_id:
            params["scope_id"] = scope_id

        response = requests.post(
            f"{self.base_url}/v1/permissions/",
            headers=self.headers,
            json=permission_data,
            params=params
        )
        return response.json() if response.status_code == 201 else None

    def get_available_permissions(self):
        """Get permissions available for assignment (admin only)"""
        response = requests.get(
            f"{self.base_url}/v1/permissions/available",
            headers=self.headers
        )
        return response.json() if response.status_code == 200 else None

    def update_permission(self, permission_id, update_data):
        """Update existing permission"""
        response = requests.put(
            f"{self.base_url}/v1/permissions/{permission_id}",
            headers=self.headers,
            json=update_data
        )
        return response.json() if response.status_code == 200 else None

    def delete_permission(self, permission_id):
        """Delete permission"""
        response = requests.delete(
            f"{self.base_url}/v1/permissions/{permission_id}",
            headers=self.headers
        )
        return response.status_code == 204

# Usage
client = PermissionManagementClient("http://localhost:8030", access_token)

# Create client permission
new_permission = client.create_permission({
    "name": "listings:create",
    "display_name": "Create Listings",
    "description": "Create property listings",
    "scope": "client"
})

# Get available permissions for role assignment
available = client.get_available_permissions()

# Get client permissions
client_perms = client.get_permissions(scope="client", scope_id="client_123")
```

### JavaScript Frontend Example

```javascript
class PermissionAPI {
  constructor(baseUrl, accessToken) {
    this.baseUrl = baseUrl;
    this.headers = {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    };
  }

  async getPermissions(scope = null, scopeId = null, skip = 0, limit = 100) {
    const params = new URLSearchParams({ skip, limit });
    if (scope) params.append("scope", scope);
    if (scopeId) params.append("scope_id", scopeId);

    const response = await fetch(`${this.baseUrl}/v1/permissions/?${params}`, {
      headers: this.headers,
    });
    return response.ok ? await response.json() : null;
  }

  async createPermission(permissionData, scopeId = null) {
    const params = scopeId ? `?scope_id=${scopeId}` : "";
    const response = await fetch(`${this.baseUrl}/v1/permissions/${params}`, {
      method: "POST",
      headers: this.headers,
      body: JSON.stringify(permissionData),
    });
    return response.ok ? await response.json() : null;
  }

  async getAvailablePermissions() {
    const response = await fetch(`${this.baseUrl}/v1/permissions/available`, {
      headers: this.headers,
    });
    return response.ok ? await response.json() : null;
  }

  async updatePermission(permissionId, updateData) {
    const response = await fetch(`${this.baseUrl}/v1/permissions/${permissionId}`, {
      method: "PUT",
      headers: this.headers,
      body: JSON.stringify(updateData),
    });
    return response.ok ? await response.json() : null;
  }

  async deletePermission(permissionId) {
    const response = await fetch(`${this.baseUrl}/v1/permissions/${permissionId}`, {
      method: "DELETE",
      headers: this.headers,
    });
    return response.ok;
  }
}

// Usage
const permissionAPI = new PermissionAPI("http://localhost:8030", accessToken);

// Create system permission (admin only)
const systemPerm = await permissionAPI.createPermission({
  name: "user:create",
  display_name: "Create Users",
  description: "Create users in any scope",
  scope: "system",
});

// Get available permissions for UI
const available = await permissionAPI.getAvailablePermissions();
```

---

## Dependencies and Services

### Core Services Used

The permission routes utilize these key services:

1. **PermissionService**:

   - `create_permission()` - Creates new permissions with scope validation
   - `get_permissions()` - Retrieves permissions with filtering
   - `get_permission_by_id()` - Retrieves individual permissions
   - `get_permission_by_name()` - Finds permissions by name and scope
   - `get_available_permissions_for_user()` - Gets assignable permissions
   - `update_permission()` - Updates permissions
   - `delete_permission()` - Deletes permissions
   - `convert_permission_names_to_links()` - Converts names to Beanie Links
   - `resolve_permissions_to_details()` - Converts IDs to detailed schemas

2. **Dependencies Integration**:
   - Permission checking via `can_read_permissions`, `can_manage_permissions`
   - Admin-only operations via `require_admin`
   - Automatic scope handling in service layer

### Database Integration

- **MongoDB via Beanie ODM**: Efficient permission storage with proper indexing
- **Unique Constraints**: Prevents duplicate permissions within scope
- **Scope Indexing**: Optimized queries for scope-based filtering
- **Creator Tracking**: Tracks who created each permission

---

## Best Practices

### Permission Design

1. **Scope Appropriately**: Use the most restrictive scope that meets business needs
2. **Consistent Naming**: Follow `resource:action` naming convention
3. **Granular Control**: Create specific permissions rather than broad ones
4. **Business Alignment**: Match permissions to actual business processes

### Scope Management

1. **System Permissions**: Only for truly global capabilities
2. **Platform Permissions**: For cross-client platform features
3. **Client Permissions**: For organization-specific business logic
4. **Avoid Scope Creep**: Don't make client permissions when platform would suffice

### API Usage

1. **Use Available Endpoint**: Check `/available` to get permissions user can assign
2. **Handle Scope Contexts**: Let backend auto-determine scope_id when possible
3. **Filter Appropriately**: Use scope and scope_id filters for performance
4. **Error Handling**: Handle scope-related errors gracefully

### Security Considerations

1. **Scope Isolation**: Ensure permissions are properly isolated by scope
2. **Validation**: Validate scope_id matches user's access context
3. **Audit Logging**: Log all permission creation and modification events
4. **Regular Review**: Audit permissions within each scope periodically

---

## Related Documentation

- [Role Routes](role_routes.md) - For role-based access control and permission assignment
- [Group Routes](group_routes.md) - For team organization and group-based permissions
- [User Routes](user_routes.md) - For user management and permission inheritance
- [Client Account Routes](client_account_routes.md) - For client account management
- [Dependencies Documentation](../dependencies.md) - For authentication and permission dependencies
