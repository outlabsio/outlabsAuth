# User Management Routes Documentation

## Overview

The User Management Routes provide a comprehensive API for managing users within the authentication system with **hierarchical access control and permission-based authorization**. This module handles all CRUD operations for users with proper authentication, **scoped authorization controls**, and **bulk user management capabilities**.

**Base URL:** `/v1/users`  
**Tags:** ["User Management"]

## Authentication & Authorization

All endpoints require authentication and specific permissions:

- **Read Operations:** `can_read_users` dependency (requires any of: `user:read_all`, `user:read_platform`, `user:read_client`)
- **Write Operations:** `can_manage_users` dependency (requires any of: `user:manage_all`, `user:manage_platform`, `user:manage_client`)
- **Admin Operations:** `require_admin` dependency for bulk operations
- **Individual Access:** `can_access_user` dependency for accessing specific users

## Hierarchical Access Control

### User Visibility and Management Rules

**Super Admins**:

- Can see and manage all users across all client accounts
- Have `user:read_all` and `user:manage_all` permissions

**Client Admins**:

- Can see and manage users only within their own client account
- Automatically scoped to their client account by the service layer
- Cannot access users from other client accounts

**Regular Users**:

- Can access their own user data via `can_access_user` dependency
- Limited read access based on assigned permissions

### Automatic Scoping

The user service automatically applies scoping based on the current user's context:

- **Super admins**: No scoping applied - see all users
- **Client-scoped users**: Automatically filtered to their client account
- **Access control**: Prevents cross-client data access

---

## Endpoints

### 1. Get All Users

Retrieves a paginated list of users with automatic hierarchical filtering based on user permissions.

**Endpoint:** `GET /v1/users/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_read_users`

**Query Parameters:**

- `skip` (optional, integer, default: 0) - Number of records to skip for pagination
- `limit` (optional, integer, default: 100) - Maximum number of records to return

**Authorization Logic:**

- **Super Admins**: See all users across all client accounts
- **Client Users**: See only users in their client account (automatically scoped)

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "_id": "507f1f77bcf86cd799439011",
    "email": "admin@acmerealestate.com",
    "first_name": "John",
    "last_name": "Admin",
    "status": "active",
    "client_account_id": "507f1f77bcf86cd799439012",
    "roles": ["507f1f77bcf86cd799439020", "507f1f77bcf86cd799439021"],
    "groups": ["507f1f77bcf86cd799439013"],
    "permissions": [
      {
        "id": "507f1f77bcf86cd799439025",
        "name": "user:create",
        "scope": "client",
        "display_name": "Create Users",
        "description": "Create new users in client account"
      }
    ],
    "is_platform_staff": false,
    "platform_scope": null,
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
curl -X GET "https://api.example.com/v1/users/?skip=0&limit=50" \
     -H "Authorization: Bearer <access_token>"
```

### 2. Get User by ID

Retrieves a specific user by their ID with hierarchical access control.

**Endpoint:** `GET /v1/users/{user_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_access_user()`

**Path Parameters:**

- `user_id` (required, PydanticObjectId) - The unique identifier of the user

**Authorization:** Uses hierarchical access control to ensure users can only access user data they have permission to view:

- **Admins**: Can access any user data
- **Regular users**: Can only access their own data
- **Client scoping**: Enforced for non-super admins

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "email": "john.agent@acmerealestate.com",
  "first_name": "John",
  "last_name": "Agent",
  "status": "active",
  "client_account_id": "507f1f77bcf86cd799439015",
  "roles": ["507f1f77bcf86cd799439022"],
  "groups": ["507f1f77bcf86cd799439016"],
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439026",
      "name": "user:read",
      "scope": "client",
      "display_name": "Read Users",
      "description": "View user information in client account"
    }
  ],
  "is_platform_staff": false,
  "platform_scope": null,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - User not found or access denied (prevents information disclosure)
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `422 Unprocessable Entity` - Invalid user ID format

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/users/507f1f77bcf86cd799439011" \
     -H "Authorization: Bearer <access_token>"
```

### 3. Create User

Creates a new user with proper scoping and validation.

**Endpoint:** `POST /v1/users/`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_users`

**Request Body:**

```json
{
  "email": "newuser@acmerealestate.com",
  "password": "securePassword123",
  "first_name": "New",
  "last_name": "User",
  "status": "active",
  "client_account_id": "507f1f77bcf86cd799439015",
  "roles": ["507f1f77bcf86cd799439022"],
  "groups": ["507f1f77bcf86cd799439016"],
  "is_main_client": false,
  "is_platform_staff": false,
  "platform_scope": null
}
```

**Field Requirements:**

- `email` (required, EmailStr) - Must be unique across the system
- `password` (required, string, min 8 chars) - Will be hashed before storage
- `first_name` (required, string) - User's first name
- `last_name` (required, string) - User's last name
- `status` (optional, UserStatus, default: "active") - Account status
- `client_account_id` (optional, string) - Client account assignment
- `roles` (optional, List[str]) - List of role ObjectIds
- `groups` (optional, List[str]) - List of group ObjectIds
- `is_main_client` (optional, bool, default: false) - Main client admin flag
- `is_platform_staff` (optional, bool, default: false) - Platform staff flag
- `platform_scope` (optional, string) - Platform scope for staff members

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "_id": "507f1f77bcf86cd799439017",
  "email": "newuser@acmerealestate.com",
  "first_name": "New",
  "last_name": "User",
  "status": "active",
  "client_account_id": "507f1f77bcf86cd799439015",
  "roles": ["507f1f77bcf86cd799439022"],
  "groups": ["507f1f77bcf86cd799439016"],
  "permissions": [],
  "is_platform_staff": false,
  "platform_scope": null,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Error Responses:**

- `409 Conflict` - User with this email already exists
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `422 Unprocessable Entity` - Invalid request body or validation errors

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/users/" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "newuser@example.com",
       "password": "securePassword123",
       "first_name": "New",
       "last_name": "User",
       "roles": ["507f1f77bcf86cd799439022"]
     }'
```

### 4. Create Sub-User

Allows a main client user to create a new user within their own client account.

**Endpoint:** `POST /v1/users/create_sub_user`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_users`

**Authorization:**

- User must have `is_main_client: true`
- User must have a client account
- Created user will be assigned to the same client account

**Request Body:**

Same as regular user creation, but `client_account_id` will be automatically set to the creator's client account.

**Response:**

- **Status Code:** `201 Created`
- **Response Body:** Same format as regular user creation

**Error Responses:**

- `403 Forbidden` - User is not a main client or lacks permissions
- Other standard user creation errors

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/users/create_sub_user" \
     -H "Authorization: Bearer <main_client_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "subuser@acmerealestate.com",
       "password": "password123",
       "first_name": "Sub",
       "last_name": "User",
       "roles": ["507f1f77bcf86cd799439022"]
     }'
```

### 5. Update User

Updates an existing user with hierarchical access control and validation.

**Endpoint:** `PUT /v1/users/{user_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_users`

**Path Parameters:**

- `user_id` (required, string) - The unique identifier of the user

**Request Body:**

All fields are optional for updates:

```json
{
  "email": "updated@example.com",
  "first_name": "Updated",
  "last_name": "Name",
  "status": "active",
  "roles": ["507f1f77bcf86cd799439023"],
  "groups": ["507f1f77bcf86cd799439018"]
}
```

**Authorization:**

- Super admins can update any user
- Non-super admins can only update users within their client account
- Main client role validation for role assignments

**Response:**

- **Status Code:** `200 OK`
- **Response Body:** Updated user object (same format as GET response)

**Error Responses:**

- `404 Not Found` - User not found or access denied
- `403 Forbidden` - Insufficient permissions or invalid role assignment
- `401 Unauthorized` - Invalid authentication
- `422 Unprocessable Entity` - Invalid request body or user ID format
- `409 Conflict` - Email already exists (if email is being updated)

**Example Request:**

```bash
curl -X PUT "https://api.example.com/v1/users/507f1f77bcf86cd799439017" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "first_name": "Updated",
       "last_name": "User",
       "status": "active"
     }'
```

### 6. Delete User

Deletes a user from the system with hierarchical access control.

**Endpoint:** `DELETE /v1/users/{user_id}`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `can_manage_users`

**Path Parameters:**

- `user_id` (required, string) - The unique identifier of the user

**Authorization:**

- Super admins can delete any user
- Non-super admins can only delete users within their client account
- Service layer enforces scoping automatically

**Response:**

- **Status Code:** `204 No Content`
- **Response Body:** Empty

**Error Responses:**

- `404 Not Found` - User not found or access denied
- `403 Forbidden` - Insufficient permissions
- `401 Unauthorized` - Invalid authentication
- `422 Unprocessable Entity` - Invalid user ID format

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/users/507f1f77bcf86cd799439017" \
     -H "Authorization: Bearer <access_token>"
```

### 7. Bulk Create Users

Creates multiple users in a single request with detailed success/failure reporting.

**Endpoint:** `POST /v1/users/bulk-create`

**Authentication Required:** Yes (Access Token)

**Required Dependencies:** `require_admin`

**Note:** This is an admin-only endpoint for bulk user operations.

**Request Body:**

```json
[
  {
    "email": "user1@example.com",
    "password": "password123",
    "first_name": "User",
    "last_name": "One",
    "roles": ["507f1f77bcf86cd799439022"]
  },
  {
    "email": "user2@example.com",
    "password": "password123",
    "first_name": "User",
    "last_name": "Two",
    "roles": ["507f1f77bcf86cd799439022"]
  }
]
```

**Response:**

- **Status Code:** `201 Created`
- **Response Body:**

```json
{
  "successful_creates": [
    {
      "_id": "507f1f77bcf86cd799439018",
      "email": "user1@example.com",
      "first_name": "User",
      "last_name": "One",
      "status": "active",
      "roles": ["507f1f77bcf86cd799439022"],
      "groups": [],
      "permissions": [],
      "is_platform_staff": false,
      "platform_scope": null,
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    }
  ],
  "failed_creates": [
    {
      "user_data": {
        "email": "user2@example.com",
        "password": "password123",
        "first_name": "User",
        "last_name": "Two"
      },
      "error": "User with this email already exists."
    }
  ]
}
```

**Error Responses:**

- `403 Forbidden` - Insufficient admin permissions
- `401 Unauthorized` - Invalid authentication
- `422 Unprocessable Entity` - Invalid request body

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/users/bulk-create" \
     -H "Authorization: Bearer <admin_token>" \
     -H "Content-Type: application/json" \
     -d '[
       {
         "email": "bulkuser1@example.com",
         "password": "password123",
         "first_name": "Bulk",
         "last_name": "User1"
       }
     ]'
```

---

## Data Models

### UserCreateSchema

```python
class UserCreateSchema(BaseModel):
    email: EmailStr                                 # User's email address (required)
    password: str                                  # User's password, min 8 characters (required)
    first_name: str                                # User's first name (required)
    last_name: str                                 # User's last name (required)
    status: UserStatus = UserStatus.ACTIVE        # Account status (optional)
    client_account_id: Optional[str] = None       # Client account ID (optional)
    roles: Optional[List[str]] = []               # List of role ObjectIds (optional)
    groups: Optional[List[str]] = []              # List of group ObjectIds (optional)
    is_main_client: Optional[bool] = False        # Main client admin flag (optional)
    is_platform_staff: Optional[bool] = False    # Platform staff flag (optional)
    platform_scope: Optional[str] = None         # Platform scope for staff (optional)
```

### UserUpdateSchema

```python
class UserUpdateSchema(BaseModel):
    email: Optional[EmailStr] = None              # User's email address
    first_name: Optional[str] = None              # User's first name
    last_name: Optional[str] = None               # User's last name
    status: Optional[UserStatus] = None           # Account status
    roles: Optional[List[str]] = None             # List of role ObjectIds to assign
    groups: Optional[List[str]] = None            # List of group ObjectIds to assign
```

### UserResponseSchema

```python
class UserResponseSchema(BaseModel):
    id: PydanticObjectId                          # User ID (aliased from _id)
    email: EmailStr                               # User's email address
    first_name: str                               # User's first name
    last_name: str                                # User's last name
    status: UserStatus                            # Account status
    client_account_id: Optional[str] = None      # Client account ID
    roles: List[str] = []                         # Role ObjectIds
    groups: List[str] = []                        # Group ObjectIds
    permissions: Optional[List[PermissionDetailSchema]] = []  # Effective permissions
    is_platform_staff: bool = False              # Platform staff flag
    platform_scope: Optional[str] = None         # Platform scope
    created_at: datetime                          # Creation timestamp
    updated_at: datetime                          # Last update timestamp
```

### UserStatus Enum

```python
class UserStatus(str, Enum):
    ACTIVE = "active"       # User is active and can log in
    INACTIVE = "inactive"   # User is inactive
    PENDING = "pending"     # User account is pending activation
    SUSPENDED = "suspended" # User account is suspended
```

### UserBulkCreateResponseSchema

```python
class UserBulkCreateResponseSchema(BaseModel):
    successful_creates: List[UserResponseSchema]  # Successfully created users
    failed_creates: List[FailedUserCreationSchema]  # Failed user creations
```

### FailedUserCreationSchema

```python
class FailedUserCreationSchema(BaseModel):
    user_data: UserCreateSchema                   # Original user data that failed
    error: str                                    # Error message describing the failure
```

---

## Security & Access Control

### Hierarchical Filtering

All user endpoints implement automatic hierarchical filtering:

1. **Authentication Verification**: Valid JWT token required
2. **Permission Check**: User must have appropriate `user:*` permissions via dependencies
3. **Scope Filtering**: Results automatically filtered based on user's access level
4. **Client Isolation**: Non-super admins can only access users within their client account
5. **Information Disclosure Prevention**: Users cannot see users outside their access scope

### Data Protection

- **Password Security**: Passwords are properly hashed and never returned in responses
- **Permission-Based Access**: Granular permissions control what user operations are allowed
- **Audit Trail**: All user management operations are logged for security compliance
- **Role Validation**: Main client role assignment validation for enhanced security

### Dependencies Used

1. **Authentication Dependencies**:

   - `get_current_user_with_token` - Authenticates and retrieves user with token data
   - `get_current_user` - Authenticates and retrieves current user context

2. **Authorization Dependencies**:

   - `can_read_users` - Checks permissions for reading users
   - `can_manage_users` - Checks permissions for creating/updating/deleting users
   - `can_access_user()` - Checks permissions for accessing specific users
   - `require_admin` - Requires admin role for admin-only operations

3. **Utility Functions**:
   - `convert_user_to_response()` - Converts UserModel to consistent response format

---

## Error Handling

### Common Error Responses

**409 Conflict - Duplicate Email**:

```json
{
  "detail": "User with this email already exists."
}
```

**403 Forbidden - Insufficient Permissions**:

```json
{
  "detail": "You do not have permission to create sub-users."
}
```

**404 Not Found - User Not Found or Access Denied**:

```json
{
  "detail": "User not found or access denied."
}
```

**422 Unprocessable Entity - Invalid Data**:

```json
{
  "detail": "Invalid ObjectId: invalid-id"
}
```

**403 Forbidden - Invalid Role Assignment**:

```json
{
  "detail": "Role 'platform_admin' cannot be assigned by a client administrator."
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

    def get_users_in_scope(self, skip=0, limit=100):
        """Get users accessible to current user with automatic scoping"""
        params = {"skip": skip, "limit": limit}

        response = requests.get(
            f"{self.base_url}/v1/users/",
            headers=self.headers,
            params=params
        )
        return response.json() if response.status_code == 200 else None

    def create_user(self, user_data):
        """Create new user with validation and scoping"""
        response = requests.post(
            f"{self.base_url}/v1/users/",
            headers=self.headers,
            json=user_data
        )
        return response.json() if response.status_code == 201 else None

    def create_sub_user(self, user_data):
        """Create sub-user within current client account"""
        response = requests.post(
            f"{self.base_url}/v1/users/create_sub_user",
            headers=self.headers,
            json=user_data
        )
        return response.json() if response.status_code == 201 else None

    def bulk_create_users(self, users_data):
        """Bulk create users (admin only)"""
        response = requests.post(
            f"{self.base_url}/v1/users/bulk-create",
            headers=self.headers,
            json=users_data
        )
        return response.json() if response.status_code == 201 else None

# Usage
client = UserManagementClient("http://localhost:8030", access_token)
users = client.get_users_in_scope(limit=50)
new_user = client.create_user({
    "email": "newuser@example.com",
    "password": "securePassword123",
    "first_name": "New",
    "last_name": "User"
})
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

  async getUsersInScope(skip = 0, limit = 100) {
    const params = new URLSearchParams({ skip, limit });
    const response = await fetch(`${this.baseUrl}/v1/users/?${params}`, {
      headers: this.headers,
    });
    return response.ok ? await response.json() : null;
  }

  async createUser(userData) {
    const response = await fetch(`${this.baseUrl}/v1/users/`, {
      method: "POST",
      headers: this.headers,
      body: JSON.stringify(userData),
    });
    return response.ok ? await response.json() : null;
  }

  async updateUser(userId, updateData) {
    const response = await fetch(`${this.baseUrl}/v1/users/${userId}`, {
      method: "PUT",
      headers: this.headers,
      body: JSON.stringify(updateData),
    });
    return response.ok ? await response.json() : null;
  }

  async deleteUser(userId) {
    const response = await fetch(`${this.baseUrl}/v1/users/${userId}`, {
      method: "DELETE",
      headers: this.headers,
    });
    return response.ok;
  }
}

// Usage
const userAPI = new UserManagementAPI("http://localhost:8030", accessToken);
const users = await userAPI.getUsersInScope(0, 50);
const newUser = await userAPI.createUser({
  email: "newuser@example.com",
  password: "securePassword123",
  first_name: "New",
  last_name: "User",
});
```

---

## Dependencies and Services

### Core Services Used

The user routes utilize these key services:

1. **UserService**:

   - `create_user()` - Creates new users with validation
   - `create_sub_user()` - Creates users within client account scope
   - `get_users()` - Retrieves users with automatic scoping
   - `get_user_by_id()` - Retrieves individual users
   - `get_user_by_email()` - Finds users by email
   - `update_user()` - Updates users with access control
   - `delete_user()` - Deletes users with access control
   - `bulk_create_users()` - Bulk user creation with error handling
   - `get_user_effective_permissions()` - Calculates effective permissions

2. **Dependencies Integration**:
   - Hierarchical permission checking via `can_read_users`, `can_manage_users`
   - Individual access control via `can_access_user()`
   - Admin-only operations via `require_admin`
   - Automatic client scoping in service layer

### Database Integration

- **MongoDB via Beanie ODM**: Efficient user storage with proper indexing
- **Unique Email Constraint**: Prevents duplicate user emails
- **Link References**: Roles and groups stored as Beanie Links for efficient querying
- **Client Account Relationships**: Proper relationship modeling with client accounts

---

## Best Practices

### User Management

1. **Email Uniqueness**: Ensure emails are unique across the entire system
2. **Password Security**: Use strong passwords (minimum 8 characters enforced)
3. **Status Management**: Use appropriate user status values for account lifecycle
4. **Role Assignment**: Validate role assignments based on user permissions
5. **Client Scoping**: Always consider client account boundaries for data access

### Security Considerations

1. **Permission Validation**: Always use appropriate dependencies for access control
2. **Data Scoping**: Let the service layer handle automatic scoping
3. **Password Handling**: Never return passwords or password hashes in responses
4. **Input Validation**: Validate all input data using Pydantic schemas
5. **Error Messages**: Use consistent error messages that don't leak information

### Performance Optimization

1. **Pagination**: Always use pagination for user lists
2. **Efficient Queries**: Service layer optimizes database queries
3. **Link Fetching**: Beanie Links are fetched efficiently when needed
4. **Index Usage**: Proper database indexes for common query patterns

---

## Related Documentation

- [Role Routes](role_routes.md) - For role-based access control
- [Group Routes](group_routes.md) - For team organization and group-based permissions
- [Permission Routes](permission_routes.md) - For granular permission management
- [Client Account Routes](client_account_routes.md) - For client account management
- [Auth Routes](auth_routes.md) - For authentication and login
- [Dependencies Documentation](../dependencies.md) - For authentication and permission dependencies
