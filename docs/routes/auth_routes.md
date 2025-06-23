# Authentication Routes Documentation

## Overview

The Authentication Routes provide a comprehensive API for user authentication, session management, and password operations within the authentication system. This module handles login, logout, token refresh, password reset, and session management with support for both JSON tokens and HTTP-only cookies.

**Base URL:** `/v1/auth`  
**Tags:** Authentication

## Authentication Methods

The API supports two authentication methods:

1. **Bearer Token Authentication:** Traditional JWT tokens passed in Authorization header
2. **HTTP-Only Cookie Authentication:** Secure cookies for web applications (use `use_cookies=true` parameter)

## Endpoints

### 1. User Login

Authenticates a user and returns access and refresh tokens.

**Endpoint:** `POST /v1/auth/login`

**Authentication Required:** No

**Query Parameters:**

- `use_cookies` (optional, boolean, default: false) - Use HTTP-only cookies instead of JSON response

**Request Body (Form Data):**

```json
{
  "username": "user@example.com",
  "password": "securepassword123"
}
```

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
  "message": "Login successful",
  "token_type": "cookie"
}
```

- **Cookies Set:**
  - `access_token` - HTTP-only, expires in 15 minutes
  - `refresh_token` - HTTP-only, expires in 7 days

**Error Responses:**

- `401 Unauthorized` - Incorrect email or password

**Example Request (JSON Mode):**

```bash
curl -X POST "https://api.example.com/v1/auth/login" \
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

Refreshes an access token using a valid refresh token with automatic token rotation.

**Endpoint:** `POST /v1/auth/refresh`

**Authentication Required:** Yes (Refresh Token)

**Query Parameters:**

- `use_cookies` (optional, boolean, default: false) - Use HTTP-only cookies

**Headers (JSON Mode):**

- `Authorization: Bearer <refresh_token>`

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

Retrieves the profile of the currently authenticated user.

**Endpoint:** `GET /v1/auth/me`

**Authentication Required:** Yes (Access Token)

**Response:**

- **Status Code:** `200 OK`
- **Response Body:**

```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "john.doe@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "client_account_id": "507f1f77bcf86cd799439012",
  "roles": ["user"],
  "groups": [],
  "is_main_client": false,
  "status": "active",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z",
  "last_login_at": "2023-01-01T00:00:00Z",
  "locale": "en-US"
}
```

**Error Responses:**

- `401 Unauthorized` - Invalid access token

**Example Request:**

```bash
curl -X GET "https://api.example.com/v1/auth/me" \
     -H "Authorization: Bearer <access_token>"
```

### 6. Request Password Reset

Initiates a password reset process. In production, this would send an email with a reset token.

**Endpoint:** `POST /v1/auth/password/reset-request`

**Authentication Required:** No

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

**Note:** The `token` field is included for testing purposes. In production, this token would be sent via email and not returned in the response.

**Important:** The response is the same regardless of whether the email exists or not to prevent user enumeration attacks.

**Error Responses:**

- `400 Bad Request` - Invalid email format

**Example Request:**

```bash
curl -X POST "https://api.example.com/v1/auth/password/reset-request" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}'
```

### 7. Confirm Password Reset

Confirms a password reset using the token from the reset request.

**Endpoint:** `POST /v1/auth/password/reset-confirm`

**Authentication Required:** No

**Request Body:**

```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "new_password": "newSecurePassword123"
}
```

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `400 Bad Request` - Invalid or expired password reset token
- `400 Bad Request` - Password validation errors

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

Retrieves all active sessions for the current user.

**Endpoint:** `GET /v1/auth/sessions`

**Authentication Required:** Yes (Access Token)

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

Revokes a specific session by its JTI (JWT ID).

**Endpoint:** `DELETE /v1/auth/sessions/{jti}`

**Authentication Required:** Yes (Access Token)

**Path Parameters:**

- `jti` (required, string) - The unique JWT identifier of the session to revoke

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

Changes the current user's password.

**Endpoint:** `POST /v1/auth/password/change`

**Authentication Required:** Yes (Access Token)

**Request Body:**

```json
{
  "current_password": "currentPassword123",
  "new_password": "newSecurePassword123"
}
```

**Response:**

- **Status Code:** `204 No Content`

**Error Responses:**

- `400 Bad Request` - Current password is incorrect
- `400 Bad Request` - Password validation errors
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

## Security Features

### Token Management

- **Access Token Expiry:** 15 minutes
- **Refresh Token Expiry:** 7 days
- **Token Rotation:** New refresh tokens are issued on each refresh
- **Automatic Revocation:** All tokens are revoked on password change

### Cookie Security

When using `use_cookies=true`:

- **HTTP-Only:** Cookies cannot be accessed via JavaScript
- **Secure Flag:** Dynamically set based on environment (false for localhost/HTTP, true for production/HTTPS)
- **SameSite:** Set to "strict" for CSRF protection
- **Proper Expiry:** Matches token expiration times

### Session Security

- **IP Tracking:** Sessions track the originating IP address
- **User Agent Tracking:** Sessions track the client user agent
- **Session Management:** Users can view and revoke individual sessions
- **Bulk Revocation:** Support for revoking all sessions at once

## Error Handling

All endpoints follow consistent error response format:

```json
{
  "detail": "Error message description"
}
```

Common HTTP status codes:

- `200 OK` - Request successful
- `204 No Content` - Request successful, no response body
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict

## Rate Limiting

Authentication endpoints may be subject to rate limiting to prevent brute force attacks. Check the response headers for rate limit information:

- `X-RateLimit-Limit` - Maximum requests allowed
- `X-RateLimit-Remaining` - Remaining requests in current window
- `X-RateLimit-Reset` - Time when the rate limit resets

## Best Practices

### For Web Applications

1. Use `use_cookies=true` for browser-based applications
2. Implement proper CSRF protection
3. Use HTTPS in production
4. Handle token refresh automatically

### For Mobile/API Applications

1. Use JSON token responses
2. Store tokens securely (Keychain/Keystore)
3. Implement automatic token refresh
4. Handle network errors gracefully

### General Security

1. Always use HTTPS in production
2. Implement proper error handling
3. Log authentication events
4. Monitor for suspicious activity
5. Regularly rotate secrets and keys
