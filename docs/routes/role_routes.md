# Role Routes Documentation

## Overview

The Role Routes provide a comprehensive API for managing roles within the three-tier authentication system. Roles serve as collections of permissions that can be assigned to users or groups, enabling flexible and scalable access control across system, platform, and client scopes. This module handles full CRUD operations for roles with proper tenant isolation and permission validation.

**Base URL:** `/v1/roles`  
**Tags:** ["roles"]

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Base Dependencies:** `can_read_roles` (for read operations) and `can_manage_roles` (for write operations)
- **Permission System:** Uses hierarchical permissions with automatic scope detection
- **Role-Based Access:** Super admins, platform admins, and client admins have different access levels

## Three-Tier Role System

The system implements a hierarchical role architecture with three distinct scopes:

### System Roles (Global)

- **Scope:** `system`
- **Access:** Available across all platforms and clients
- **Examples:** `super_admin`, `basic_user`
- **Management:** Only super admins can create/modify
- **scope_id:** Always `null`

### Platform Roles (Per Platform)

- **Scope:** `platform`
- **Access:** Available within a specific platform and its clients
- **Examples:** `admin`, `support`, `sales`
- **Management:** Platform admins and super admins can create/modify
- **scope_id:** Platform's ObjectId

### Client Roles (Per Client)

- **Scope:** `client`
- **Access:** Available only within a specific client account
- **Examples:** `admin`, `manager`, `sales_rep`
- **Management:** Client admins and higher can create/modify
- **scope_id:** Client account's ObjectId

### Role Identification

- **ID Format:** MongoDB ObjectId (e.g., `507f1f77bcf86cd799439011`)
- **Uniqueness:** Role names are unique within their scope + scope_id combination
- **Tenant Isolation:** Proper isolation ensures roles don't leak across boundaries

## Endpoints

### 1. Create Role

Creates a new role in the system with specified permissions and scope.

**Endpoint:** `POST /v1/roles/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_roles`

**Request Body:**

```json
{
  "name": "admin",
  "display_name": "Client Administrator",
  "description": "Administrative role for client account management",
  "permissions": ["user:create", "user:read", "user:update", "group:manage_members"],
  "scope": "client",
  "is_assignable_by_main_client": true
}
```

**Scope Determination Logic:**

- **System Scope:** Only super admins can create system roles
- **Platform Scope:** Platform admins can create platform roles (scope_id auto-detected from user's platform roles)
- **Client Scope:** Client admins can create client roles (scope_id auto-detected from user's client account)

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "admin",
  "display_name": "Client Administrator",
  "description": "Administrative role for client account management",
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "user:create",
      "scope": "client",
      "display_name": "Create Users",
      "description": "Create new users in client account"
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "name": "user:read",
      "scope": "client",
      "display_name": "Read Users",
      "description": "View user information"
    }
  ],
  "scope": "client",
  "scope_id": "507f1f77bcf86cd799439012",
  "is_assignable_by_main_client": true,
  "created_by_user_id": "507f1f77bcf86cd799439013",
  "created_by_client_id": "507f1f77bcf86cd799439012",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - Role with this name already exists in scope
- `400 Bad Request` - Invalid request data, missing scope requirements, or invalid permissions
- `403 Forbidden` - Insufficient permissions for the specified scope
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "project_manager",
       "display_name": "Project Manager",
       "description": "Can manage projects and team members within client account",
       "permissions": [
         "user:read",
         "user:update",
         "group:manage_members"
       ],
       "scope": "client",
       "is_assignable_by_main_client": true
     }'
```

### 2. Get All Roles

Retrieves roles visible to the current user based on their permissions and scope.

**Endpoint:** `GET /v1/roles/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_roles`

**Query Parameters:**

- `scope` (optional, RoleScope enum) - Filter by scope: "system", "platform", or "client"
- `skip` (optional, integer, default: 0, min: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100, min: 1, max: 1000) - Maximum number of records to return

**Visibility Rules:**

- **Super Admins:** See all roles across all scopes
- **Platform Admins:** See system + their platform roles + client roles in their platform
- **Client Admins:** See system + their client roles

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "_id": "507f1f77bcf86cd799439011",
    "name": "super_admin",
    "display_name": "Super Administrator",
    "description": "Complete system-wide access",
    "permissions": [
      {
        "id": "507f1f77bcf86cd799439020",
        "name": "user:create",
        "scope": "system",
        "display_name": "Create Users",
        "description": "Create new users system-wide"
      }
    ],
    "scope": "system",
    "scope_id": null,
    "is_assignable_by_main_client": false,
    "created_by_user_id": "system",
    "created_by_client_id": null,
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  },
  {
    "_id": "507f1f77bcf86cd799439012",
    "name": "admin",
    "display_name": "Client Administrator",
    "description": "Administrative access within client account",
    "permissions": [
      {
        "id": "507f1f77bcf86cd799439021",
        "name": "user:create",
        "scope": "client",
        "display_name": "Create Users",
        "description": "Create new users in client account"
      }
    ],
    "scope": "client",
    "scope_id": "507f1f77bcf86cd799439013",
    "is_assignable_by_main_client": true,
    "created_by_user_id": "507f1f77bcf86cd799439014",
    "created_by_client_id": "507f1f77bcf86cd799439013",
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
# Get all visible roles
curl -X GET "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <access_token>"

# Get only client-scoped roles
curl -X GET "https://api.example.com/v1/roles/?scope=client" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Get Available Roles for Assignment

Retrieves roles that the current user can assign to others, grouped by scope.

**Endpoint:** `GET /v1/roles/available`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `require_admin`

**Note:** Only admin users can assign roles to others.

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "system_roles": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "name": "basic_user",
      "display_name": "Basic User",
      "description": "Basic user access with minimal permissions",
      "permissions": [
        {
          "id": "507f1f77bcf86cd799439025",
          "name": "user:read",
          "scope": "system",
          "display_name": "Read Users",
          "description": "View user information"
        }
      ],
      "scope": "system",
      "scope_id": null,
      "is_assignable_by_main_client": true,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ],
  "platform_roles": [
    {
      "_id": "507f1f77bcf86cd799439012",
      "name": "support",
      "display_name": "Platform Support",
      "description": "Platform support representative",
      "permissions": [
        {
          "id": "507f1f77bcf86cd799439026",
          "name": "platform:support_users",
          "scope": "platform",
          "display_name": "Support Users",
          "description": "Provide support to platform users"
        }
      ],
      "scope": "platform",
      "scope_id": "507f1f77bcf86cd799439013",
      "is_assignable_by_main_client": false,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ],
  "client_roles": [
    {
      "_id": "507f1f77bcf86cd799439014",
      "name": "manager",
      "display_name": "Manager",
      "description": "Team management role",
      "permissions": [
        {
          "id": "507f1f77bcf86cd799439027",
          "name": "user:read",
          "scope": "client",
          "display_name": "Read Users",
          "description": "View user information in client account"
        }
      ],
      "scope": "client",
      "scope_id": "507f1f77bcf86cd799439015",
      "is_assignable_by_main_client": true,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ]
}
```

### 4. Get Role by ID

Retrieves a specific role by its MongoDB ObjectId.

**Endpoint:** `GET /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_roles`

**Path Parameters:**

- `role_id` (required, PydanticObjectId) - MongoDB ObjectId of the role

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "admin",
  "display_name": "Client Administrator",
  "description": "Administrative access within client account",
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "user:create",
      "scope": "client",
      "display_name": "Create Users",
      "description": "Create new users in client account"
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "name": "user:read",
      "scope": "client",
      "display_name": "Read Users",
      "description": "View user information"
    }
  ],
  "scope": "client",
  "scope_id": "507f1f77bcf86cd799439013",
  "is_assignable_by_main_client": true,
  "created_by_user_id": "507f1f77bcf86cd799439014",
  "created_by_client_id": "507f1f77bcf86cd799439013",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Role not found or not visible to user
- `403 Forbidden` - Insufficient permissions to view this role
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/roles/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

### 5. Update Role

Updates an existing role's information. Scope and scope_id cannot be changed after creation.

**Endpoint:** `PUT /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_roles`

**Path Parameters:**

- `role_id` (required, PydanticObjectId) - MongoDB ObjectId of the role

**Request Body:**

All fields are optional. Only provided fields will be updated.

```json
{
  "name": "senior_admin",
  "display_name": "Senior Administrator",
  "description": "Enhanced administrative role with additional permissions",
  "permissions": ["user:create", "user:read", "user:update", "user:delete", "group:manage_members"],
  "is_assignable_by_main_client": false
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "senior_admin",
  "display_name": "Senior Administrator",
  "description": "Enhanced administrative role with additional permissions",
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "user:create",
      "scope": "client",
      "display_name": "Create Users",
      "description": "Create new users in client account"
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "name": "user:read",
      "scope": "client",
      "display_name": "Read Users",
      "description": "View user information"
    }
  ],
  "scope": "client",
  "scope_id": "507f1f77bcf86cd799439013",
  "is_assignable_by_main_client": false,
  "created_by_user_id": "507f1f77bcf86cd799439014",
  "created_by_client_id": "507f1f77bcf86cd799439013",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T12:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Role not found
- `400 Bad Request` - Invalid request data or invalid permissions
- `403 Forbidden` - Insufficient permissions to modify this role
- `401 Unauthorized` - Invalid authentication

### 6. Delete Role

Deletes a role from the system. Critical system roles cannot be deleted.

**Endpoint:** `DELETE /v1/roles/{role_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_roles`

**Path Parameters:**

- `role_id` (required, PydanticObjectId) - MongoDB ObjectId of the role

**Protection:** Critical system roles (`super_admin`, `platform_admin`, `client_admin`) cannot be deleted.

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `404 Not Found` - Role not found
- `400 Bad Request` - Cannot delete critical system roles
- `403 Forbidden` - Insufficient permissions to delete this role
- `401 Unauthorized` - Invalid authentication

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/roles/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

## Data Models

### RoleCreateSchema

```python
class RoleCreateSchema(BaseModel):
    name: str                                    # Role name (e.g., 'admin', 'manager')
    display_name: str                           # Human-readable role name
    description: Optional[str] = None           # Role purpose and capabilities
    permissions: List[str] = []                 # List of permission names
    scope: RoleScope                           # Role scope: system, platform, or client
    is_assignable_by_main_client: bool = False # Can client admins assign this role?
```

### RoleUpdateSchema

```python
class RoleUpdateSchema(BaseModel):
    name: Optional[str] = None                  # Role name
    display_name: Optional[str] = None          # Human-readable role name
    description: Optional[str] = None           # Role description
    permissions: Optional[List[str]] = None     # List of permission names
    is_assignable_by_main_client: Optional[bool] = None # Assignment control
```

**Note:** `scope` and `scope_id` cannot be updated after creation.

### RoleResponseSchema

```python
class RoleResponseSchema(BaseModel):
    id: PydanticObjectId                        # Role ID (aliased from _id)
    name: str                                   # Role name
    display_name: str                          # Human-readable role name
    description: Optional[str]                 # Role description
    permissions: List[PermissionDetailSchema]  # Full permission details
    scope: RoleScope                           # Role scope
    scope_id: Optional[str]                    # Scope owner ID
    is_assignable_by_main_client: bool         # Assignment control flag
    created_by_user_id: Optional[str]          # Creator user ID
    created_by_client_id: Optional[str]        # Creator client ID
    created_at: datetime                       # Creation timestamp
    updated_at: datetime                       # Last update timestamp
```

### PermissionDetailSchema

```python
class PermissionDetailSchema(BaseModel):
    id: str                                    # Permission ObjectId
    name: str                                  # Permission name (e.g., 'user:create')
    scope: PermissionScope                     # Permission scope
    display_name: str                          # Human-readable permission name
    description: Optional[str]                 # What this permission allows
```

### AvailableRolesResponseSchema

```python
class AvailableRolesResponseSchema(BaseModel):
    system_roles: List[RoleResponseSchema] = []    # Assignable system roles
    platform_roles: List[RoleResponseSchema] = [] # Assignable platform roles
    client_roles: List[RoleResponseSchema] = []    # Assignable client roles
```

## Authorization Logic

### Role Management Permissions

The system uses these permission checks for role management:

1. **View Roles (`user_can_view_role`)**:

   - Super admins: View all roles
   - System roles: Everyone can view
   - Platform roles: Users in same platform can view
   - Client roles: Users in same client can view

2. **Manage Roles (`user_can_manage_role`)**:
   - Super admins: Manage all roles
   - System roles: Only super admins
   - Platform roles: Platform admins in same platform
   - Client roles: Client admins in same client

### Scope Detection Logic

When creating roles, the system automatically detects scope_id:

- **System roles**: `scope_id = null`
- **Platform roles**: Extracted from user's platform admin roles
- **Client roles**: Extracted from user's client account

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
- `400 Bad Request` - Invalid request data or invalid permissions
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions or scope access denied
- `404 Not Found` - Role not found or not visible
- `409 Conflict` - Role name already exists in scope

### Specific Error Messages

**409 Conflict (Duplicate Name in Scope):**

```json
{
  "detail": "Role 'admin' already exists in client scope (507f1f77bcf86cd799439013)"
}
```

**403 Forbidden (Insufficient Scope Permissions):**

```json
{
  "detail": "Only platform admins can create platform roles"
}
```

**400 Bad Request (Missing Scope Requirements):**

```json
{
  "detail": "Client ID required for client-scoped roles"
}
```

**400 Bad Request (Invalid Permissions):**

```json
{
  "detail": "Invalid permission: nonexistent:permission"
}
```

**400 Bad Request (Protected Role Deletion):**

```json
{
  "detail": "Cannot delete critical system role: super_admin"
}
```

## Dependencies and Services

### Core Dependencies Used

The role routes utilize these key dependencies:

1. **Authentication Dependencies**:

   - `get_current_user` - Authenticates and retrieves current user context

2. **Authorization Dependencies**:

   - `can_read_roles` - Checks permissions for reading roles
   - `can_manage_roles` - Checks permissions for creating/updating/deleting roles
   - `require_admin` - Requires admin role for role assignment operations

3. **Permission System Integration**:
   - Uses hierarchical permission checking
   - Automatic scope detection based on user roles
   - Cross-client access control

### Services Integration

1. **RoleService**:

   - `create_role()` - Creates new roles with scope validation
   - `get_roles_by_scope()` - Retrieves roles filtered by scope
   - `role_to_response_schema()` - Converts models to response format with permission details
   - `user_can_view_role()` - Checks role viewing permissions
   - `user_can_manage_role()` - Checks role management permissions

2. **PermissionService**:
   - `convert_permission_names_to_links()` - Converts permission names to Link objects
   - `resolve_permissions_to_details()` - Resolves permission ObjectIds to detailed information

## Best Practices

### Role Design

1. **Scope Selection:** Choose appropriate scope based on role's intended usage area
2. **Naming Consistency:** Use consistent role names across scopes (e.g., "admin" in each scope)
3. **Clear Display Names:** Use descriptive display names that include scope context
4. **Minimal Permissions:** Follow least privilege principle - assign only necessary permissions
5. **Documentation:** Provide clear descriptions explaining role scope and purpose

### Permission Management

1. **Valid Permissions:** Ensure all permission names exist in the system before assignment
2. **Scope Matching:** Ensure permissions match the intended role scope
3. **Regular Audits:** Review role permissions across all scopes
4. **Cross-Scope Permissions:** Carefully consider permissions that span scopes

### Three-Tier Strategy

1. **System Roles:** Keep minimal - only for truly global functionality
2. **Platform Roles:** Design for platform-wide operations and management
3. **Client Roles:** Focus on client-specific business functions
4. **Role Inheritance:** Consider how permissions flow through the hierarchy
5. **Tenant Isolation:** Ensure proper boundaries between scopes

### Security Considerations

1. **Critical Role Protection:** System protects critical roles from deletion
2. **Scope Isolation:** Roles are properly isolated within their scopes
3. **Permission Validation:** Invalid permissions are rejected during role creation/update
4. **Access Control:** Fine-grained access control based on user roles and scope

## Usage Examples

### Creating Three-Tier Role Hierarchy

```bash
# Create system roles (super admin only)
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <super_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "basic_user",
       "display_name": "Basic User",
       "description": "Minimal system access for all users",
       "permissions": ["user:read"],
       "scope": "system",
       "is_assignable_by_main_client": true
     }'

# Create platform roles (platform admin)
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <platform_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "support",
       "display_name": "Platform Support",
       "description": "Customer support across all platform clients",
       "permissions": ["platform:support_users", "user:read"],
       "scope": "platform",
       "is_assignable_by_main_client": false
     }'

# Create client roles (client admin)
curl -X POST "https://api.example.com/v1/roles/" \
     -H "Authorization: Bearer <client_admin_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "manager",
       "display_name": "Team Manager",
       "description": "Manage team members and projects within client",
       "permissions": ["user:read", "user:update", "group:manage_members"],
       "scope": "client",
       "is_assignable_by_main_client": true
     }'
```

### Querying Roles by Scope

```bash
# Get system roles only
curl -X GET "https://api.example.com/v1/roles/?scope=system" \
     -H "Authorization: Bearer <access_token>"

# Get platform roles only
curl -X GET "https://api.example.com/v1/roles/?scope=platform" \
     -H "Authorization: Bearer <access_token>"

# Get client roles only
curl -X GET "https://api.example.com/v1/roles/?scope=client" \
     -H "Authorization: Bearer <access_token>"

# Get available roles for assignment
curl -X GET "https://api.example.com/v1/roles/available" \
     -H "Authorization: Bearer <access_token>"
```

## Integration Notes

### User Assignment

Roles are assigned to users via ObjectId references in user creation/update:

```json
{
  "user_id": "507f1f77bcf86cd799439020",
  "roles": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"]
}
```

### Permission Calculation

The system calculates effective permissions by:

1. **Role Resolution:** Converting ObjectId role references to role objects (Beanie Links)
2. **Permission Aggregation:** Combining permissions from all assigned roles
3. **Scope Consideration:** Respecting role scope boundaries
4. **Permission Details:** Resolving permission ObjectIds to full permission information
5. **Deduplication:** Removing duplicate permissions

### Database Structure

Roles are stored with efficient indexes:

```javascript
// Unique compound index for role uniqueness within scope
{ "name": 1, "scope": 1, "scope_id": 1 }

// Query index for scope-based filtering
{ "scope": 1, "scope_id": 1 }

// Creator tracking index
{ "created_by_client_id": 1 }

// Assignment queries index
{ "scope": 1, "is_assignable_by_main_client": 1 }
```

## Dependencies

This module depends on:

- `role_service`: Business logic for role operations with scope handling
- `permission_service`: Permission validation and Link conversion
- `can_read_roles`: Dependency for role read operations
- `can_manage_roles`: Dependency for role write operations
- `require_admin`: Dependency for role assignment operations
- `RoleModel`: MongoDB document model with proper indexes and Beanie Links
- `UserModel`: For determining user's scope and permissions
- `PermissionModel`: For role permission management via Beanie Links

## Related Documentation

- [Permission Routes](permission_routes.md) - For permission management
- [User Routes](user_routes.md) - For user role assignment
- [Group Routes](group_routes.md) - For group role assignment
- [Dependencies Documentation](../dependencies.md) - For authentication and permission dependencies
