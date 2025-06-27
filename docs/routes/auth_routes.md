# Authentication Routes Documentation

## Overview

The Authentication Routes provide a comprehensive API for user authentication, session management, and password operations within the authentication system. This module handles **enriched JWT-based authentication**, **session management**, **password operations**, and **multi-source permission aggregation** with support for both JSON tokens and HTTP-only cookies.

**Base URL:** `/v1/auth`  
**Tags:** Authentication

## 🔐 **Authentication Methods**

The API supports two authentication methods:

1. **Bearer Token Authentication**: Enriched JWT tokens passed in Authorization header (includes user data and permissions)
2. **HTTP-Only Cookie Authentication**: Secure cookies for web applications (use `use_cookies=true` parameter)

## 🎯 **Core Features**

- **Enriched JWT Token Management** with user data, roles, and permissions included by default
- **Automatic Permission Optimization** using hierarchical compression
- **Multi-Device Session Management** with IP/User-Agent tracking
- **Real-Time Permission Aggregation** from roles, groups, and direct assignments
- **Password Security** with reset and change workflows
- **Platform Staff Detection** for cross-client access management
- **Cookie Security** with dynamic secure flag based on environment
- **Zero API Call Authorization** - permissions available directly in tokens

---

## 📋 **Endpoints**

### 1. User Login

**✅ ENHANCED** - Authenticates a user and returns enriched access and refresh tokens with **user data, permissions, and client account context** by default.

**Endpoint:** `POST /v1/auth/login`

**Authentication Required:** No

**Request Format:** `application/x-www-form-urlencoded` (OAuth2 standard)

**Query Parameters:**

- `use_cookies` (optional, boolean, default: false) - Use HTTP-only cookies instead of JSON response
- `use_enriched_tokens` (optional, boolean, default: true) - Include user data and permissions in access token

**Request Body (Form Data):**

```json
{
  "username": "user@example.com",
  "password": "securepassword123"
}
```

**Features:**

- **Enriched Tokens by Default**: Access tokens include user profile, roles, permissions, and session data
- **Zero Additional API Calls**: Frontend gets all authorization data immediately
- **Automatic Permission Optimization**: Hierarchical permission compression for optimal token size
- **Client Account Context**: Access tokens include client_account_id for scoped operations
- **Session Tracking**: Stores IP address and user agent for security monitoring
- **Dual Response Modes**: JSON tokens or HTTP-only cookies based on use_cookies parameter
- **Dynamic Cookie Security**: Secure flag automatically set based on environment (localhost vs production)
- **Size Management**: Automatic fallback to basic tokens if enriched token exceeds 8KB limit

**Response (JSON Mode - Enriched Token):**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

**Enriched Access Token Payload:**

```json
{
  "sub": "user_id",
  "client_account_id": "client_id",
  "jti": "refresh_token_id",
  "exp": 1719504000,
  "iat": 1719500400,

  "user": {
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "status": "active",
    "is_platform_staff": false,
    "platform_scope": null
  },

  "roles": [
    {
      "id": "role_id",
      "name": "admin",
      "scope": "client",
      "scope_id": "client_id"
    }
  ],

  "permissions": ["user:manage_client", "group:read_client", "role:read_client"],

  "scopes": ["client"],

  "session": {
    "is_main_client": true,
    "mfa_enabled": false,
    "locale": "en-US"
  }
}
```

**Response (Cookie Mode):**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "message": "Login successful",
  "token_type": "cookie"
}
```

- **Cookies Set:**
  - `access_token` - HTTP-only, expires in **30 minutes** (enriched by default)
  - `refresh_token` - HTTP-only, expires in **7 days**

**Basic Token Mode (Optional):**

For clients that prefer minimal tokens, use `use_enriched_tokens=false`:

```json
{
  "sub": "user_id",
  "client_account_id": "client_id",
  "jti": "refresh_token_id",
  "exp": 1719504000,
  "iat": 1719500400
}
```

**Error Responses:**

- `401 Unauthorized` - Incorrect email or password

**Example Request (Standard - Enriched Token):**

```bash
curl -X POST "https://api.example.com/v1/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=securepassword123"
```

**Example Request (Basic Token):**

```bash
curl -X POST "https://api.example.com/v1/auth/login?use_enriched_tokens=false" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=securepassword123"
```

**Example Request (Cookie Mode):**

```bash
curl -X POST "https://api.example.com/v1/auth/login?use_cookies=true" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=securepassword123"
```

### 2. Refresh Access Token

**✅ ENHANCED** - Refreshes access token with **automatic token rotation**, **enriched token data**, and **client context preservation**.

**Endpoint:** `POST /v1/auth/refresh`

**Authentication Required:** Yes (Refresh Token)

**Query Parameters:**

- `use_cookies` (optional, boolean, default: false) - Use HTTP-only cookies
- `use_enriched_tokens` (optional, boolean, default: true) - Include user data and permissions in access token

**Headers (JSON Mode):**

- `Authorization: Bearer <refresh_token>`

**Features:**

- **Enriched Tokens by Default**: New access tokens include fresh user data and permissions
- **Token Rotation**: Automatically issues new refresh token and revokes old one
- **Permission Refresh**: Gets latest permissions from database on each refresh
- **Client Context**: Preserves client_account_id in new tokens
- **Session Security**: Links new tokens to same session tracking information
- **Dual Input/Output**: Supports both header tokens and cookies
- **Size Management**: Automatic fallback to basic tokens if enriched token exceeds 8KB limit

**Response (JSON Mode):**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

**Response (Cookie Mode):**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "message": "Tokens refreshed",
  "token_type": "cookie"
}
```

**Error Responses:**

- `401 Unauthorized` - Refresh token not found, revoked, or invalid

**Example Request (JSON Mode):**

```bash
curl -X POST "https://api.example.com/v1/auth/refresh" \
     -H "Authorization: Bearer <refresh_token>"
```

**Example Request (Cookie Mode):**

```bash
curl -X POST "https://api.example.com/v1/auth/refresh?use_cookies=true" \
     -b "refresh_token=<refresh_token>"
```

### 3. User Logout

Revokes the current user's refresh token and optionally clears cookies.

**Endpoint:** `POST /v1/auth/logout`

**Authentication Required:** Yes (Access Token)

**Dependencies:** `get_current_user_with_token` (extracts JTI for token revocation)

**Query Parameters:**

- `use_cookies` (optional, boolean, default: false) - Clear HTTP-only cookies

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/auth/logout" \
     -H "Authorization: Bearer <access_token>"
```

### 4. Logout All Sessions

Revokes all of the current user's refresh tokens across all devices.

**Endpoint:** `POST /v1/auth/logout_all`

**Authentication Required:** Yes (Access Token)

**Dependencies:** `get_current_user`

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/auth/logout_all" \
     -H "Authorization: Bearer <access_token>"
```

### 5. Get Current User Profile

**✅ ENHANCED** - Retrieves the profile of the currently authenticated user with **real-time effective permissions**, **platform staff context**, and **multi-source permission aggregation**.

**Endpoint:** `GET /v1/auth/me`

**Authentication Required:** Yes (Access Token)

**Dependencies:** `get_current_user`

**Features:**

- **Real-Time Permissions**: Calculates effective permissions from **roles + groups + direct assignments**
- **Platform Staff Detection**: Identifies cross-client access capabilities
- **Permission Details**: Returns `PermissionDetailSchema` objects with full permission information
- **Client Context**: Includes client account information and platform scope
- **Multi-Source Aggregation**: Combines permissions from all sources for frontend authorization

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "admin@propertyhub.com",
  "first_name": "Platform",
  "last_name": "Admin",
  "status": "active",
  "client_account_id": "507f1f77bcf86cd799439012",
  "roles": ["507f1f77bcf86cd799439015"],
  "groups": ["507f1f77bcf86cd799439016"],
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439020",
      "name": "client:manage_all",
      "display_name": "Manage All Clients",
      "scope": "system",
      "scope_id": null
    },
    {
      "id": "507f1f77bcf86cd799439021",
      "name": "user:manage_platform",
      "display_name": "Manage Platform Users",
      "scope": "platform",
      "scope_id": "platform_id"
    }
  ],
  "is_platform_staff": true,
  "platform_scope": "all",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Key Response Fields:**

- **`permissions`**: Array of `PermissionDetailSchema` objects with full permission details
- **`roles`**: Array of role ObjectId strings (not role names)
- **`groups`**: Array of group ObjectId strings (not group names)
- **`is_platform_staff`**: Boolean indicating cross-client access capability
- **`platform_scope`**: Platform access level ("all", "created", or null)

**Permission Calculation Process:**

1. **Direct Role Permissions**: Permissions from user's assigned roles (via Links)
2. **Group Role Permissions**: Permissions from user's group memberships (via Links)
3. **Real-Time Resolution**: Resolves ObjectIds to full permission details via `permission_service.resolve_permissions_to_details()`

**Platform Staff Levels:**

- **`platform_scope: "all"`**: Can access all clients (admins, support)
- **`platform_scope: "created"`**: Can access only created clients (sales)
- **`is_platform_staff: false`**: Regular client users (no cross-client access)

**Error Responses:**

- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/auth/me" \
     -H "Authorization: Bearer <access_token>"
```

**Example Response (Regular Client User):**

```json
{
  "id": "507f1f77bcf86cd799439014",
  "email": "john.agent@acmerealestate.com",
  "first_name": "John",
  "last_name": "Agent",
  "status": "active",
  "client_account_id": "507f1f77bcf86cd799439015",
  "roles": ["507f1f77bcf86cd799439017"],
  "groups": ["507f1f77bcf86cd799439018"],
  "permissions": [
    {
      "id": "507f1f77bcf86cd799439025",
      "name": "user:read_client",
      "display_name": "Read Client Users",
      "scope": "client",
      "scope_id": "507f1f77bcf86cd799439015"
    }
  ],
  "is_platform_staff": false,
  "platform_scope": null,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Frontend Integration:**

```javascript
// Check if user has specific permission
function hasPermission(userProfile, permissionName) {
  return userProfile.permissions.some((p) => p.name === permissionName);
}

// Check if user is platform staff
function isPlatformStaff(userProfile) {
  return userProfile.is_platform_staff === true;
}

// Check platform scope level
function canAccessAllClients(userProfile) {
  return userProfile.platform_scope === "all";
}

// Usage examples
const user = await getCurrentUser();
const canCreateClients = hasPermission(user, "client:manage_all");
const canViewAnalytics = hasPermission(user, "platform:view_analytics");
const isPlatformUser = isPlatformStaff(user);
```

### 6. Request Password Reset

Initiates a password reset process. In production, this would send an email with a reset token.

**Endpoint:** `POST /v1/auth/password/reset-request`

**Authentication Required:** No

**Request Body Schema:** `PasswordResetRequestSchema`

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "message": "If a user with this email exists, a password reset link has been sent.",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Important Security Notes:**

- The `token` field is included **for testing purposes only**
- In production, this token would be sent via email and **not returned** in the response
- The response is identical regardless of whether the email exists (prevents user enumeration)

**Error Responses:**

- `422 Unprocessable Entity` - Invalid email format

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/auth/password/reset-request" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}'
```

### 7. Confirm Password Reset

Confirms a password reset using the token from the reset request with **automatic session revocation**.

**Endpoint:** `POST /v1/auth/password/reset-confirm`

**Authentication Required:** No

**Request Body Schema:** `PasswordResetConfirmSchema`

**Request Body:**

```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "new_password": "newSecurePassword123"
}
```

**Features:**

- **Automatic Session Revocation**: All user's existing sessions are revoked for security
- **Token Usage Tracking**: Reset token is marked as used with timestamp
- **Password Validation**: New password must meet security requirements

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `400 Bad Request` - Invalid or expired password reset token
- `422 Unprocessable Entity` - Password validation errors

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/auth/password/reset-confirm" \
     -H "Content-Type: application/json" \
     -d '{
       "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
       "new_password": "newSecurePassword123"
     }'
```

### 8. Get Active Sessions

**✅ ENHANCED** - Retrieves all active sessions for the current user with **detailed session information**.

**Endpoint:** `GET /v1/auth/sessions`

**Authentication Required:** Yes (Access Token)

**Dependencies:** `get_current_user`

**Response Schema:** `List[SessionResponseSchema]`

**Features:**

- **Session Tracking**: Shows IP address, user agent, and timestamps for each session
- **Security Monitoring**: Helps users identify unauthorized access
- **Multi-Device Management**: Shows sessions across all devices

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
[
  {
    "jti": "550e8400-e29b-41d4-a716-446655440000",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "created_at": "2023-01-01T00:00:00Z",
    "expires_at": "2023-01-08T00:00:00Z"
  }
]
```

**Error Responses:**

- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/auth/sessions" \
     -H "Authorization: Bearer <access_token>"
```

### 9. Revoke Specific Session

Revokes a specific session by its JTI (JWT ID) with **user ownership validation**.

**Endpoint:** `DELETE /v1/auth/sessions/{jti}`

**Authentication Required:** Yes (Access Token)

**Dependencies:** `get_current_user`

**Path Parameters:**

- `jti` (required, string) - The unique JWT identifier of the session to revoke

**Features:**

- **Ownership Validation**: Users can only revoke their own sessions
- **Immediate Revocation**: Session is immediately invalidated
- **Security Control**: Allows users to remotely log out compromised devices

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `404 Not Found` - Session not found or already revoked
- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X DELETE "https://api.example.com/v1/auth/sessions/550e8400-e29b-41d4-a716-446655440000" \
     -H "Authorization: Bearer <access_token>"
```

### 10. Change Password

**✅ ENHANCED** - Changes the current user's password with **automatic session revocation** and **password verification**.

**Endpoint:** `POST /v1/auth/password/change`

**Authentication Required:** Yes (Access Token)

**Dependencies:** `get_current_user`

**Request Body Schema:** `PasswordChangeSchema`

**Request Body:**

```json
{
  "current_password": "currentPassword123",
  "new_password": "newSecurePassword123"
}
```

**Features:**

- **Current Password Verification**: Requires current password for security
- **Automatic Session Revocation**: All user's sessions are revoked after password change
- **Password Validation**: New password must meet security requirements
- **Immediate Effect**: Forces re-authentication on all devices

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `400 Bad Request` - Current password is incorrect
- `422 Unprocessable Entity` - Password validation errors
- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/auth/password/change" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "current_password": "currentPassword123",
       "new_password": "newSecurePassword123"
     }'
```

### 11. Get Token Information

**✅ NEW** - Returns detailed information about the current access token, including capabilities and embedded data.

**Endpoint:** `GET /v1/auth/token-info`

**Authentication Required:** Yes (Access Token)

**Features:**

- **Token Type Detection**: Identifies whether token is enriched or basic
- **Capability Analysis**: Shows what data is available in the token
- **Frontend Optimization**: Helps frontend determine if additional API calls are needed
- **Debug Information**: Useful for troubleshooting token issues

**Response (Enriched Token):**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "token_type": "enriched",
  "user_id": "507f1f77bcf86cd799439011",
  "client_account_id": "507f1f77bcf86cd799439012",
  "permissions_count": 15,
  "roles_count": 2,
  "scopes": ["client", "platform"],
  "expires_at": 1719504000,
  "issued_at": 1719500400,
  "user_email": "admin@example.com",
  "mfa_enabled": false,
  "locale": "en-US"
}
```

**Response (Basic Token):**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "token_type": "basic",
  "user_id": "507f1f77bcf86cd799439011",
  "client_account_id": "507f1f77bcf86cd799439012",
  "message": "Token contains minimal data - use default login for enriched features"
}
```

**Error Responses:**

- `401 Unauthorized` - Invalid access token

**Frontend Usage:**

```javascript
// Check token capabilities
const tokenInfo = await fetch("/v1/auth/token-info", {
  headers: { Authorization: `Bearer ${accessToken}` },
}).then((r) => r.json());

if (tokenInfo.token_type === "enriched") {
  // All user data available in token - no additional API calls needed
  const userData = jwt.decode(accessToken);
  console.log("Permissions:", userData.permissions);
  console.log("Roles:", userData.roles);
} else {
  // Need to make API calls to get user data
  const userData = await fetch("/v1/auth/me").then((r) => r.json());
}
```

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/auth/token-info" \
     -H "Authorization: Bearer <access_token>"
```

---

## 🔒 **Security Features**

### **Enriched Token Management**

- **Default Enriched Format**: Access tokens include user data, roles, and permissions by default
- **Permission Optimization**: Automatic hierarchical permission compression for optimal size
- **Size Management**: 8KB limit with automatic fallback to basic tokens if exceeded
- **Fresh Data**: Permissions and roles refreshed on each token refresh
- **Access Token Expiry:** **30 minutes** (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh Token Expiry:** **7 days** (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`)
- **Token Rotation:** New refresh tokens are issued on each refresh with old token revocation
- **Automatic Revocation:** All tokens are revoked on password change for security
- **Client Context:** Access tokens include `client_account_id` for scoped operations

### **Cookie Security**

When using `use_cookies=true`:

- **HTTP-Only:** Cookies cannot be accessed via JavaScript (XSS protection)
- **Dynamic Secure Flag:** Automatically set based on environment:
  - `false` for localhost/HTTP (development)
  - `true` for production/HTTPS
- **SameSite:** Set to "strict" for CSRF protection
- **Proper Expiry:** Matches token expiration times exactly
- **Path Restriction:** Cookies scoped to appropriate paths

### **Session Security**

- **IP Tracking:** All sessions track originating IP address
- **User Agent Tracking:** Sessions track client user agent for device identification
- **Session Management:** Users can view and revoke individual sessions
- **Bulk Revocation:** Support for revoking all sessions at once
- **JTI Linking:** Access and refresh tokens share JTI for session correlation

### **Password Security**

- **Bcrypt Hashing:** Passwords hashed using bcrypt with proper salt rounds
- **Current Password Verification:** Required for password changes
- **Session Invalidation:** All sessions revoked on password change
- **Reset Token Security:** Time-limited tokens for password reset
- **Usage Tracking:** Reset tokens marked as used to prevent reuse

---

## 📊 **Authentication Schemas**

### **TokenSchema**

```python
{
  "access_token": str,
  "refresh_token": str,
  "token_type": str
}
```

### **EnrichedTokenDataSchema** (Standard Access Token Payload)

```python
{
  "sub": str,                              # user_id
  "client_account_id": Optional[str],      # client account ID
  "jti": Optional[str],                    # JWT ID for session tracking
  "exp": int,                              # expiration timestamp
  "iat": int,                              # issued at timestamp

  "user": {                                # User profile data
    "email": str,
    "first_name": Optional[str],
    "last_name": Optional[str],
    "status": str,
    "is_platform_staff": bool,
    "platform_scope": Optional[str]
  },

  "roles": [                               # User roles with scope info
    {
      "id": str,
      "name": str,
      "scope": str,
      "scope_id": Optional[str]
    }
  ],

  "permissions": [str],                    # Permission names for quick access
  "scopes": [str],                         # Available scopes

  "session": {                             # Session metadata
    "is_main_client": bool,
    "mfa_enabled": bool,
    "locale": str
  }
}
```

### **TokenDataSchema** (Basic Token Payload - Fallback)

```python
{
  "user_id": Optional[str],
  "jti": Optional[str],
  "client_account_id": Optional[str]
}
```

### **SessionResponseSchema**

```python
{
  "jti": str,
  "ip_address": Optional[str],
  "user_agent": Optional[str],
  "created_at": datetime,
  "expires_at": datetime
}
```

### **PasswordResetRequestSchema**

```python
{
  "email": EmailStr
}
```

### **PasswordResetConfirmSchema**

```python
{
  "token": str,
  "new_password": str
}
```

### **PasswordChangeSchema**

```python
{
  "current_password": str,
  "new_password": str
}
```

---

## ⚠️ **Error Handling**

All endpoints follow consistent error response format:

```json
{
  "detail": "Error message description"
}
```

**Common HTTP Status Codes:**

- `200 OK` - Request successful
- `204 No Content` - Request successful, no response body
- `400 Bad Request` - Invalid request data or business logic error
- `401 Unauthorized` - Authentication failed or token invalid
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict
- `422 Unprocessable Entity` - Validation errors

---

## 🚀 **Best Practices**

### **For Web Applications**

1. **Use Enriched Tokens**: Default behavior provides all user data without additional API calls
2. **Use Cookie Mode**: Set `use_cookies=true` for browser-based applications
3. **CSRF Protection**: Implement proper CSRF protection with SameSite cookies
4. **HTTPS Required**: Always use HTTPS in production for cookie security
5. **Automatic Refresh**: Implement automatic token refresh before expiration
6. **Permission Caching**: Cache decoded token data to avoid repeated JWT parsing

### **For Mobile/API Applications**

1. **Use JSON Tokens**: Standard bearer token authentication with enriched data
2. **Secure Storage**: Store tokens in Keychain (iOS) or Keystore (Android)
3. **Automatic Refresh**: Implement background token refresh
4. **Network Error Handling**: Handle token refresh failures gracefully
5. **Local Permission Checking**: Use embedded permissions for instant authorization decisions

### **Security Best Practices**

1. **HTTPS Only**: Never use HTTP in production
2. **Token Storage**: Never store tokens in localStorage (web apps)
3. **Session Monitoring**: Monitor active sessions for suspicious activity
4. **Regular Rotation**: Encourage users to change passwords regularly
5. **Rate Limiting**: Implement rate limiting on authentication endpoints
6. **Token Size Monitoring**: Monitor enriched token sizes and optimize permissions
7. **Fallback Handling**: Gracefully handle basic tokens when enriched tokens are too large

### **Frontend Integration with Enriched Tokens**

```javascript
// Enriched token utility class
class AuthService {
  constructor() {
    this.tokenData = null;
  }

  // Decode and cache token data
  setToken(accessToken) {
    this.accessToken = accessToken;
    this.tokenData = jwt.decode(accessToken);

    // Check if token is enriched
    this.isEnriched = !!(this.tokenData.permissions && this.tokenData.user);
  }

  // Get user profile from token (no API call needed)
  getUserProfile() {
    if (this.isEnriched) {
      return this.tokenData.user;
    }
    // Fallback to API call for basic tokens
    return this.fetchUserProfile();
  }

  // Check permissions locally (no API call needed)
  hasPermission(permissionName) {
    if (this.isEnriched) {
      return this.checkHierarchicalPermission(this.tokenData.permissions, permissionName);
    }
    // Fallback to API call for basic tokens
    return this.checkPermissionViaAPI(permissionName);
  }

  // Check roles locally (no API call needed)
  hasRole(roleName) {
    if (this.isEnriched) {
      return this.tokenData.roles.some((role) => role.name === roleName);
    }
    // Fallback to API call for basic tokens
    return this.checkRoleViaAPI(roleName);
  }

  // Hierarchical permission checking
  checkHierarchicalPermission(userPermissions, required) {
    // Direct permission match
    if (userPermissions.includes(required)) return true;

    // Hierarchical checking logic
    const hierarchies = {
      "user:read_self": [],
      "user:read_client": ["user:read_self"],
      "user:manage_client": ["user:read_client", "user:read_self"],
      // ... more hierarchies
    };

    for (const userPerm of userPermissions) {
      const included = hierarchies[userPerm] || [];
      if (included.includes(required)) return true;
    }

    return false;
  }

  // Check if platform staff
  isPlatformStaff() {
    return this.isEnriched ? this.tokenData.user.is_platform_staff : false;
  }

  // Get available scopes
  getScopes() {
    return this.isEnriched ? this.tokenData.scopes : [];
  }
}

// Usage example
const auth = new AuthService();
auth.setToken(accessToken);

// All these work without API calls if token is enriched
const userProfile = auth.getUserProfile();
const canManageUsers = auth.hasPermission("user:manage_client");
const isAdmin = auth.hasRole("admin");
const isPlatformUser = auth.isPlatformStaff();
```

---

## 🔧 **Configuration**

### **Environment Variables**

```bash
# Token Configuration
ACCESS_TOKEN_EXPIRE_MINUTES=30    # Access token lifetime
REFRESH_TOKEN_EXPIRE_DAYS=7       # Refresh token lifetime

# Enriched Token Settings
MAX_JWT_SIZE_BYTES=8192           # Maximum JWT token size (8KB limit)
ENABLE_ENRICHED_TOKENS_BY_DEFAULT=true  # Enable enriched tokens by default
PERMISSION_CACHE_TTL_SECONDS=300  # Permission cache TTL (5 minutes)

# Security
SECRET_KEY=your-secret-key        # JWT signing key
ALGORITHM=HS256                   # JWT algorithm

# Database
MONGODB_URL=mongodb://localhost:27017/outlabsauth
```

### **Rate Limiting**

Authentication endpoints support rate limiting to prevent brute force attacks:

- **Login Endpoint**: Limited attempts per IP/email combination
- **Password Reset**: Limited requests per email per time window
- **Refresh Token**: Limited refresh attempts per user

Check response headers for rate limit information:

- `X-RateLimit-Limit` - Maximum requests allowed
- `X-RateLimit-Remaining` - Remaining requests in current window
- `X-RateLimit-Reset` - Time when rate limit resets

---

_Documentation Updated: 2024-01-16_  
_API Version: v1_  
_Token Format: Enriched by default_  
_Token Expiry: Access 30min, Refresh 7 days_
