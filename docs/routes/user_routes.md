# User Management Routes Documentation

## Overview

The User Management Routes provide a comprehensive API for managing users within the authentication system with **complete hierarchical multi-platform tenancy support**. This module handles all CRUD operations for users with proper authentication, **platform-scoped authorization controls**, and **cross-client management capabilities**.

**Base URL:** `/v1/users`  
**Tags:** User Management

## 🏢 **Complete Hierarchical Multi-Platform Tenancy**

This API supports a complete three-tier user management hierarchy:

- **Super Admins**: Complete system access across all platforms and users
- **Platform Staff**: Can view and manage users across all clients within their platform scope
- **Client Admins**: Can manage users within their own client account
- **Regular Users**: Can view their own profile and limited user information

## 🚀 **Platform Features Implemented**

**✅ Cross-Client User Management**: Platform staff can view and manage users across multiple client companies
**✅ Platform Staff Hierarchy**: Different platform access levels (all, created, none)
**✅ Hierarchical Access Control**: Secure user management with proper isolation
**✅ Real-Time Permissions**: Dynamic permission calculation from multiple sources

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Permission:** `user:read` (required for most endpoints)
- **Platform-Specific Permissions:**
  - `user:create` - Create new users
  - `user:update` - Update user information
  - `user:delete` - Delete users
  - `user:add_member` - Add users to client accounts
  - `user:bulk_create` - Bulk user creation operations

## Hierarchical Access Logic

### User Visibility Rules

**Super Admins (`is_super_admin: true`)**:

- Can see all users across all platforms and clients

**Platform Staff (`is_platform_staff: true`)**:

- **`platform_scope: "all"`**: Can see users across all clients in their platform
- **`platform_scope: "created"`**: Can see users only in clients they created
- **Platform filtering**: Automatically filtered to their platform scope

**Regular Users**:

- Can see only users within their own client account
- Cannot access cross-client user data

---

## Endpoints

### 1. Get All Users (Hierarchical Filtering)

Retrieves a paginated list of users with automatic hierarchical filtering based on user permissions and platform access.

**Endpoint:** `GET /v1/users/`

**Required Permission:** `user:read`

**Query Parameters:**

- `skip` (optional, integer, default: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100) - Maximum number of records to return
- `client_filter` (optional, string) - Filter by specific client account ID (platform staff only)
- `include_permissions` (optional, boolean, default: false) - Include effective permissions in response

**Authorization Logic:**

- **Super Admins**: See all users across all platforms
- **Platform Staff (`platform_scope: "all"`)**: See users across all clients in their platform
- **Platform Staff (`platform_scope: "created"`)**: See users in clients they created
- **Regular Users**: See only users in their client account

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "email": "admin@propertyhub.com",
    "first_name": "Platform",
    "last_name": "Admin",
    "client_account_id": "507f1f77bcf86cd799439012",
    "roles": ["platform_admin"],
    "groups": ["507f1f77bcf86cd799439013"],
    "permissions": ["client_account:create", "user:create", "platform:manage_clients"],
    "is_main_client": true,
    "is_platform_staff": true,
    "platform_scope": "all",
    "status": "active",
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z",
    "last_login_at": "2023-01-01T00:00:00Z",
    "locale": "en-US"
  }
]
```

**Example Request (Platform Staff):**

```bash
curl -X GET "https://api.example.com/v1/users/?client_filter=507f1f77bcf86cd799439015&include_permissions=true" \
     -H "Authorization: Bearer <platform_staff_token>"
```

**Example Request (Regular Client Admin):**

```bash
curl -X GET "https://api.example.com/v1/users/?skip=0&limit=50" \
     -H "Authorization: Bearer <client_admin_token>"
```

### 2. Get User by ID (Hierarchical Access Control)

Retrieves a specific user by their ID with hierarchical access control.

**Endpoint:** `GET /v1/users/{user_id}`

**Required Permission:** `user:read`

**Path Parameters:**

- `user_id` (required, string) - The unique identifier of the user

**Query Parameters:**

- `include_permissions` (optional, boolean, default: false) - Include effective permissions in response

**Authorization:** Uses hierarchical access control to ensure users can only access user data they have permission to view.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "john.agent@acmerealestate.com",
  "first_name": "John",
  "last_name": "Agent",
  "client_account_id": "507f1f77bcf86cd799439015",
  "roles": ["real_estate_agent"],
  "groups": ["507f1f77bcf86cd799439016"],
  "permissions": ["user:read", "group:read", "client_account:read"],
  "is_main_client": false,
  "is_platform_staff": false,
  "platform_scope": null,
  "status": "active",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z",
  "last_login_at": "2023-01-01T00:00:00Z",
  "locale": "en-US"
}
```

**Error Responses:**

- `404 Not Found` - User not found or access denied (prevents information disclosure)
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid user ID format

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/users/507f1f77bcf86cd799439011?include_permissions=true" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Create User (Platform Staff & Client Admins)

Creates a new user within the appropriate client account scope.

**Endpoint:** `POST /v1/users/`

**Required Permission:** `user:create`

**Request Body:**

```json
{
  "email": "newuser@acmerealestate.com",
  "password": "securePassword123",
  "first_name": "New",
  "last_name": "User",
  "client_account_id": "507f1f77bcf86cd799439015",
  "roles": ["real_estate_agent"],
  "groups": ["507f1f77bcf86cd799439016"],
  "is_main_client": false,
  "is_platform_staff": false,
  "platform_scope": null,
  "locale": "en-US"
}
```

**Platform Staff Features:**

- Can create users in any client account within their platform scope
- Can set `is_platform_staff` and `platform_scope` for platform users
- Can assign platform-specific roles

**Client Admin Features:**

- Can create users only within their own client account
- Cannot create platform staff users
- Limited to client-specific roles

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439017",
  "email": "newuser@acmerealestate.com",
  "first_name": "New",
  "last_name": "User",
  "client_account_id": "507f1f77bcf86cd799439015",
  "roles": ["real_estate_agent"],
  "groups": ["507f1f77bcf86cd799439016"],
  "is_main_client": false,
  "is_platform_staff": false,
  "platform_scope": null,
  "status": "active",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z",
  "last_login_at": null,
  "locale": "en-US"
}
```

**Error Responses:**

- `409 Conflict` - User with this email already exists
- `403 Forbidden` - Insufficient permissions or invalid client account access
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request body or validation errors

**Example Request (Platform Staff):**

```bash
curl -X POST "https://api.example.com/v1/users/" \
     -H "Authorization: Bearer <platform_staff_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "support@propertyhub.com",
       "password": "platformPassword123",
       "first_name": "Customer",
       "last_name": "Support",
       "client_account_id": "507f1f77bcf86cd799439012",
       "roles": ["platform_support"],
       "is_platform_staff": true,
       "platform_scope": "all"
     }'
```

### 4. Update User (Hierarchical Access Control)

Updates an existing user with hierarchical access control.

**Endpoint:** `PUT /v1/users/{user_id}`

**Required Permission:** `user:update`

**Path Parameters:**

- `user_id` (required, string) - The unique identifier of the user

**Request Body:**

```json
{
  "email": "updated@example.com",
  "first_name": "Updated",
  "last_name": "Name",
  "roles": ["updated_role"],
  "groups": ["507f1f77bcf86cd799439018"],
  "status": "active",
  "locale": "en-US"
}
```

**Platform Staff Features:**

- Can update users across all clients within their platform scope
- Can modify platform staff fields (`is_platform_staff`, `platform_scope`)
- Can assign platform-specific roles

**Client Admin Features:**

- Can update users only within their own client account
- Cannot modify platform staff fields
- Limited to client-specific roles

**Response:**

- **Status Code:** `200 OK`
- **Response Body:** Updated user object (same format as GET response)

**Error Responses:**

- `404 Not Found` - User not found or access denied
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid request body or validation errors
- `409 Conflict` - Email already exists (if email is being updated)

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/users/507f1f77bcf86cd799439017" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "first_name": "Updated",
       "last_name": "User",
       "roles": ["senior_agent"]
     }'
```

### 5. Delete User (Hierarchical Access Control)

Deletes a user from the system with hierarchical access control.

**Endpoint:** `DELETE /v1/users/{user_id}`

**Required Permission:** `user:delete`

**Path Parameters:**

- `user_id` (required, string) - The unique identifier of the user

**Authorization:** Uses hierarchical access control to ensure users can only delete users they have permission to access.

**Response:**

- **Status Code:** `204 No Content`
- **Response Body:** Empty

**Error Responses:**

- `404 Not Found` - User not found or access denied
- `403 Forbidden` - Insufficient permissions or cannot delete self
- `401 Unauthorized` - Invalid authentication
- `400 Bad Request` - Invalid user ID format

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/users/507f1f77bcf86cd799439017" \
     -H "Authorization: Bearer <access_token>"
```

---

## Platform Staff Use Cases

### Cross-Client Customer Support

**Scenario**: PropertyHub support staff helping users across multiple real estate companies

```bash
# Platform support views all users across clients
curl -X GET "https://api.example.com/v1/users/?limit=100" \
     -H "Authorization: Bearer <platform_support_token>"

# Platform support helps specific user in ACME Real Estate
curl -X GET "https://api.example.com/v1/users/?client_filter=507f1f77bcf86cd799439015" \
     -H "Authorization: Bearer <platform_support_token>"
```

### Platform Administration

**Scenario**: Platform admin managing multiple real estate companies

```bash
# Create new platform staff member
curl -X POST "https://api.example.com/v1/users/" \
     -H "Authorization: Bearer <platform_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "sales@propertyhub.com",
       "password": "platformSales123",
       "first_name": "Platform",
       "last_name": "Sales",
       "client_account_id": "507f1f77bcf86cd799439012",
       "roles": ["platform_sales"],
       "is_platform_staff": true,
       "platform_scope": "created"
     }'
```

### Client Company Management

**Scenario**: Real estate company admin managing their agents

```bash
# Client admin views only their company users
curl -X GET "https://api.example.com/v1/users/" \
     -H "Authorization: Bearer <acme_admin_token>"

# Client admin creates new agent
curl -X POST "https://api.example.com/v1/users/" \
     -H "Authorization: Bearer <acme_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "newagent@acmerealestate.com",
       "password": "agentPassword123",
       "first_name": "New",
       "last_name": "Agent",
       "roles": ["real_estate_agent"]
     }'
```

---

## Security & Access Control

### Hierarchical Filtering

All user endpoints implement automatic hierarchical filtering:

1. **Authentication Verification**: Valid JWT token required
2. **Permission Check**: User must have appropriate `user:*` permissions
3. **Scope Filtering**: Results automatically filtered based on user's access level
4. **Platform Isolation**: Platform staff can only access users within their platform
5. **Client Isolation**: Regular users can only access users within their client account

### Data Protection

- **Information Disclosure Prevention**: Users cannot see users outside their access scope
- **Permission-Based Access**: Granular permissions control what user operations are allowed
- **Audit Trail**: All user management operations are logged for security compliance
- **Password Security**: Passwords are properly hashed and never returned in responses

---

## Error Handling

### Common Error Responses

**403 Forbidden - Cross-Client Access Denied**:

```json
{
  "detail": "Access denied. User not found in your accessible scope."
}
```

**403 Forbidden - Insufficient Permissions**:

```json
{
  "detail": "Insufficient permissions. Required: user:create"
}
```

**409 Conflict - Duplicate Email**:

```json
{
  "detail": "User with this email already exists"
}
```

---

## Integration Examples

### Python Client Example

```python
import requests

class UserManagementClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def get_users_in_scope(self, client_filter=None, include_permissions=False):
        """Get users accessible to current user"""
        params = {}
        if client_filter:
            params["client_filter"] = client_filter
        if include_permissions:
            params["include_permissions"] = "true"

        response = requests.get(
            f"{self.base_url}/v1/users/",
            headers=self.headers,
            params=params
        )
        return response.json() if response.status_code == 200 else None

    def create_platform_staff(self, email, password, first_name, last_name, role, platform_scope="all"):
        """Create new platform staff member (platform admin only)"""
        data = {
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "roles": [role],
            "is_platform_staff": True,
            "platform_scope": platform_scope
        }

        response = requests.post(
            f"{self.base_url}/v1/users/",
            headers=self.headers,
            json=data
        )
        return response.json() if response.status_code == 201 else None

# Usage
client = UserManagementClient("http://localhost:8030", platform_admin_token)
users = client.get_users_in_scope(include_permissions=True)
new_staff = client.create_platform_staff(
    "support@propertyhub.com",
    "password123",
    "Customer",
    "Support",
    "platform_support"
)
```

### JavaScript Frontend Example

```javascript
class UserManagementAPI {
  constructor(baseUrl, accessToken) {
    this.baseUrl = baseUrl;
    this.headers = {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    };
  }

  async getUsersInScope(clientFilter = null, includePermissions = false) {
    const params = new URLSearchParams();
    if (clientFilter) params.append("client_filter", clientFilter);
    if (includePermissions) params.append("include_permissions", "true");

    const response = await fetch(`${this.baseUrl}/v1/users/?${params}`, { headers: this.headers });

    return response.ok ? await response.json() : null;
  }

  async createClientUser(userData) {
    const response = await fetch(`${this.baseUrl}/v1/users/`, {
      method: "POST",
      headers: this.headers,
      body: JSON.stringify(userData),
    });

    return response.ok ? await response.json() : null;
  }

  // Helper to check if current user can manage cross-client users
  canManageCrossClient(userProfile) {
    return userProfile.is_platform_staff && userProfile.platform_scope === "all";
  }
}

// Usage
const userAPI = new UserManagementAPI("http://localhost:8030", accessToken);
const users = await userAPI.getUsersInScope(null, true);
const canManageAll = userAPI.canManageCrossClient(currentUserProfile);
```

---

## Related Documentation

- [Platform Routes](platform_routes.md) - For platform analytics and business intelligence
- [Client Account Routes](client_account_routes.md) - For client onboarding and management
- [Auth Routes](auth_routes.md) - For enhanced authentication with permissions
- [Group Routes](group_routes.md) - For team organization and group-based permissions
- [Role Routes](role_routes.md) - For role-based access control
- [Permission Routes](permission_routes.md) - For granular permission management
