# Generic RBAC Microservice Specification

This document details the technical specification for a standalone, generic Role-Based Access Control (RBAC) microservice. This service will centralize user authentication, authorization, and multi-tenant (organization/client) user management, making it reusable across various client applications and services.

## 1. Project Overview

### Purpose

To provide a single, secure, and scalable source of truth for user identity, authentication, and granular access control across multiple decoupled applications.

### Benefits

- **Centralized Authentication**: One login system for all consuming applications.
- **Reusable Authorization**: Consistent permission enforcement logic for all APIs.
- **Multi-Tenancy Support**: Enables organizations (clients) to manage their own sub-users.
- **Streamlined User Management**: Simplifies user onboarding, role assignment, and offboarding.
- **Enhanced Security**: Dedicated focus on security for identity and access management.
- **Scalability**: Can be scaled independently of other business logic services.
- **Portability**: Facilitates modularization for potential divestiture of business units.
- **Advanced Auth Methods**: Single point to implement OAuth, OTP, MFA, etc., including acting as an OAuth2 authorization server or integrating with external Identity Providers (IdPs).

### Technology Stack

- **Backend Framework**: FastAPI (Python, using Pydantic V2)
- **Database**: MongoDB
- **Caching/Blacklisting**: Redis (Recommended for performance-critical components)
- **Authentication**: JSON Web Tokens (JWT) with Refresh Tokens
- **Password Hashing**: Passlib (bcrypt or argon2)

## 1.1. Project Structure

The project follows a structured layout to separate concerns and improve maintainability.

- `api/routes/`: Contains lightweight FastAPI endpoint definitions. The primary role of this layer is to handle HTTP requests and responses, delegating all business logic to the services layer.
- `api/services/`: Holds the core business logic of the application. Services are responsible for orchestrating operations, interacting with the database (via models), and implementing the logic described in the API endpoint specifications.
- `api/models/`: Defines the Pydantic models that directly map to MongoDB collections. These models are the single source of truth for the database document structure.
- `api/schemas/`: Contains Pydantic models used for API data transfer objects (DTOs), such as request bodies and response models. This keeps the API contract separate from the underlying database structure, allowing them to evolve independently.

## 2. Database Schema (MongoDB Collections)

### 2.1. `users` Collection

Stores core user information and links to their organizational context.

- `_id`: ObjectId (Primary Key, unique user ID)
- `email`: String (Unique, indexed, used for login)
- `password_hash`: String (Hashed password)
- `first_name`: String (Optional)
- `last_name`: String (Optional)
- `client_account_id`: ObjectId (Index. Reference to `client_accounts` collection. Identifies the organization/client the user belongs to.)
- `roles`: Array of String (Array of `_id`s from the `roles` collection. Indexed.)
- `is_main_client`: Boolean (True if this user can manage other users within their `client_account_id`. Default: `false`.)
- `status`: String (e.g., "active", "inactive", "pending", "suspended". Default: "pending".)
- `created_at`: Date (Timestamp of user creation)
- `updated_at`: Date (Timestamp of last update)
- `last_login_at`: Date (Timestamp of last successful login)
- `metadata`: Object (Optional, flexible field for additional user-specific data)
- `mfa_enabled`: Boolean (True if MFA is enabled for this user. Default: `false`.)
- `mfa_secret`: String (Hashed/encrypted MFA secret for TOTP. Optional.)
- `recovery_codes`: Array of String (Hashed/encrypted one-time recovery codes for MFA. Optional.)
- `failed_login_attempts`: Integer (Counter for failed login attempts. Default: 0.)
- `lockout_until`: Date (Timestamp until which account is locked. Optional.)
- `locale`: String (User's preferred locale, e.g., "en-US", "es-MX". Default: "en-US".)

### 2.2. `client_accounts` Collection

Defines top-level organizations or client accounts.

- `_id`: ObjectId (Primary Key, unique client account ID)
- `name`: String (Unique, indexed, human-readable organization name)
- `description`: String (Optional)
- `status`: String (e.g., "active", "suspended". Default: "active".)
- `created_at`: Date
- `updated_at`: Date
- `main_contact_user_id`: ObjectId (Reference to `users` collection, the primary admin user for this account)
- `data_retention_policy_days`: Integer (Optional, days to retain data for this client, overrides global policy)

### 2.3. `roles` Collection

Defines roles and their associated permissions.

- `_id`: String (Primary Key, unique role ID, e.g., "platform_admin", "service_manager", "basic_user". Consider using consistent naming conventions across all applications.)
- `name`: String (Unique, human-readable role name, e.g., "Platform Administrator", "Application Service Manager")
- `description`: String (Optional)
- `permissions`: Array of String (Array of `_id`s from the `permissions` collection. Indexed.)
- `is_assignable_by_main_client`: Boolean (True if `is_main_client` users can assign this role to sub-users within their `client_account_id`. Default: `false`. Critical for security.)
- `created_at`: Date
- `updated_at`: Date

### 2.4. `permissions` Collection

Defines granular permissions. Storing them in the DB allows for more dynamic management through the admin UI.

- `_id`: String (Primary Key, unique permission ID, e.g., "serviceA:resourceX:read", "serviceB:resourceY:edit_own", "user:manage". Use `<service_identifier>:<resource>:<action>[_scope]` convention.)
- `description`: String (Human-readable description of the permission)
- `created_at`: Date
- `updated_at`: Date

### 2.5. `refresh_tokens` Collection

Stores refresh tokens for token rotation and revocation.

- `_id`: ObjectId (Primary Key)
- `user_id`: ObjectId (Reference to `users` collection)
- `jti`: String (JWT ID of the refresh token. Indexed for fast lookup during revocation.)
- `expires_at`: Date (Expiration timestamp)
- `issued_at`: Date
- `device_info`: String (Optional, e.g., "Chrome on Windows", "Mobile App")
- `ip_address`: String (IP address from which token was issued/last used)
- `user_agent`: String (User-Agent string from which token was issued/last used)
- `is_revoked`: Boolean (Flag for immediate revocation. Default: `false`.)

### 2.6. `token_blacklist` Collection / Redis Set

Stores `jti` of revoked access tokens for immediate invalidation. For high performance, this is best implemented with Redis.

- `jti`: String (JWT ID of the blacklisted access token)
- `expires_at`: Date (When the token was originally supposed to expire; for cleanup)

### 2.7. `audit_logs` Collection

Records significant actions and events for security and compliance.

- `_id`: ObjectId (Primary Key)
- `user_id`: ObjectId (Optional, null for unauthenticated actions like failed login)
- `client_account_id`: ObjectId (Optional, context of the action)
- `action`: String (e.g., "user_login_success", "user_login_failure", "password_reset", "user_created", "role_assigned", "mfa_enabled")
- `resource_type`: String (e.g., "user", "role", "client_account", "permission")
- `resource_id`: ObjectId (Optional, ID of the resource affected)
- `ip_address`: String
- `user_agent`: String
- `timestamp`: Date
- `metadata`: Object (Optional, additional context like old/new values, error messages)

### 2.8. `resource_permissions` Collection (For Resource-Level Permissions/ABAC Context)

Extends RBAC by allowing direct permissions on specific resources.

- `_id`: ObjectId (Primary Key)
- `user_id`: ObjectId (Reference to `users` collection)
- `resource_type`: String (e.g., "document", "project", "folder")
- `resource_id`: ObjectId (ID of the specific resource instance)
- `permissions`: Array of String (Permissions specific to this resource for this user, e.g., ["view", "edit"])
- `context_attributes`: Object (Optional, for ABAC, e.g., `{"time_of_day": {"start": "09:00", "end": "17:00"}, "ip_range": "192.168.1.0/24"}`)
- `expires_at`: Date (Optional, for temporary permissions)
- `created_at`: Date
- `updated_at`: Date

### 2.9. `webhooks` Collection

Stores webhook configurations for event notifications.

- `_id`: ObjectId (Primary Key)
- `client_account_id`: ObjectId (Optional, webhook can be global or client-specific)
- `url`: String (Webhook endpoint URL)
- `events`: Array of String (List of event types to subscribe to, e.g., "user.created", "user.deleted", "role.changed", "client_account.suspended")
- `secret`: String (Secret for signing webhook payloads for verification)
- `is_active`: Boolean (Default: `true`)
- `created_at`: Date
- `updated_at`: Date

## 3. API Endpoints (FastAPI)

All endpoints should be protected appropriately with authentication and authorization. API versioning should be implemented from the start (e.g., `/v1/auth/login`).

### 3.1. Authentication & Authorization

#### `POST /v1/auth/register`

- **Description**: Registers a new user. Can be restricted to internal admins or public for self-registration of `main_client` accounts.
- **Request**:
  ```json
  {
    "email": "string",
    "password": "string",
    "first_name": "string",
    "last_name": "string",
    "client_account_id": "ObjectId",
    "roles": "Array[String]",
    "is_main_client": "boolean"
  }
  ```
- **Response**: `{"user_id": "ObjectId", "message": "User registered successfully"}`
- **Auth**: No auth (for public self-registration) or `rbac:user:create` permission for internal admin use.
- **Logic**: Hashes password, creates user record, assigns default roles/`client_account_id` if public. Logs to `audit_logs`.

#### `POST /v1/auth/login`

- **Description**: Authenticates a user.
- **Request**: `{"email": "string", "password": "string"}`
- **Response**: `{"access_token": "string", "refresh_token": "string", "token_type": "bearer", "expires_in": "integer"}`
- **Auth**: No auth.
- **Logic**: Verifies credentials, checks for account lockout, handles `failed_login_attempts`. If successful, generates short-lived access token and long-lived refresh token, stores refresh token in `refresh_tokens` collection, updates `last_login_at` in `users`. Logs to `audit_logs` (success/failure).

#### `POST /v1/auth/refresh`

- **Description**: Obtains a new access token using a valid refresh token.
- **Request**: `{"refresh_token": "string"}`
- **Response**: `{"access_token": "string", "token_type": "bearer", "expires_in": "integer"}`
- **Auth**: Valid refresh token required.
- **Logic**: Validates refresh token, checks if not revoked/expired, issues new access token, rotates refresh token (optional, but good security practice), updates `ip_address` and `user_agent` on `refresh_token` record.

#### `POST /v1/auth/logout`

- **Description**: Revokes the current refresh token (logs out current device).
- **Request**: (No body, refresh token in header or cookie)
- **Response**: `{"message": "Logged out successfully"}`
- **Auth**: Valid access token required.
- **Logic**: Retrieves refresh token `jti` from `refresh_tokens` collection, marks it as `is_revoked: true` or deletes it. Adds current access token's `jti` to blacklist. Logs to `audit_logs`.

#### `POST /v1/auth/logout_all`

- **Description**: Revokes all refresh tokens for the authenticated user (logs out all devices).
- **Request**: (No body)
- **Response**: `{"message": "Logged out from all devices successfully"}`
- **Auth**: Valid access token required.
- **Logic**: Marks all `refresh_tokens` for `user_id` as `is_revoked: true` or deletes them. Adds current access token's `jti` to blacklist. Logs to `audit_logs`.

#### `GET /v1/auth/me`

- **Description**: Returns details of the authenticated user.
- **Response**: `{"user_id": "ObjectId", "email": "string", "first_name": "string", "last_name": "string", "client_account_id": "ObjectId", "roles": "Array[String]", "is_main_client": "boolean", "status": "string", "last_login_at": "Date", "mfa_enabled": "boolean"}`
- **Auth**: Valid access token required.

#### `POST /v1/auth/authorize`

- **Description**: (Internal endpoint for consuming services to confirm permissions) Checks if a given user has a specific permission. This is for consuming services that choose not to cache role-permission mappings.
- **Request**: `{"user_id": "ObjectId", "permission": "string"}`
- **Response**: `{"authorized": "boolean"}`
- **Auth**: API Key or internal trusted access.
- **Logic**: Retrieves user's roles, then roles' permissions, checks for specified permission.

#### `POST /v1/auth/password/reset-request`

- **Description**: Initiates a password reset process by sending a token to the user's email.
- **Request**: `{"email": "string"}`
- **Response**: `{"message": "Password reset email sent"}`
- **Auth**: No auth.
- **Logic**: Generates a unique, time-limited token, stores its hash in a temporary collection. Publishes a `password_reset_email` event to a message queue (e.g., RabbitMQ) with the user's email and the raw token. Logs to `audit_logs`.

#### `POST /v1/auth/password/reset-confirm`

- **Description**: Confirms a password reset using the token from the email.
- **Request**: `{"token": "string", "new_password": "string"}`
- **Response**: `{"message": "Password reset successfully"}`
- **Auth**: No auth (uses the token for authentication).
- **Logic**: Validates token, hashes new password, updates user's password, invalidates token. Revokes all refresh tokens for the user. Logs to `audit_logs`.

#### `POST /v1/auth/password/change`

- **Description**: Allows an authenticated user to change their password.
- **Request**: `{"current_password": "string", "new_password": "string"}`
- **Response**: `{"message": "Password changed successfully"}`
- **Auth**: Valid access token required.
- **Logic**: Verifies `current_password`, hashes `new_password`, updates user's password. Revokes all refresh tokens for the user. Logs to `audit_logs`.

#### `POST /v1/auth/mfa/setup/initiate`

- **Description**: Initiates MFA setup (e.g., generates TOTP secret or sends SMS for verification).
- **Request**: (Optional, e.g., `{"method": "totp"}` or `{"phone_number": "string"}`)
- **Response**: `{"qr_code_url": "string", "secret_key": "string"}` (for TOTP) or `{"message": "OTP sent"}` (for SMS/Email). Also returns `recovery_codes`.
- **Auth**: Valid access token required.
- **Logic**: Generates MFA secret, saves it (hashed/encrypted) to user profile, generates recovery codes, sends OTP/QR code. Logs to `audit_logs`.

#### `POST /v1/auth/mfa/setup/verify`

- **Description**: Verifies MFA setup after user provides the OTP.
- **Request**: `{"otp_code": "string"}`
- **Response**: `{"message": "MFA enabled successfully"}`
- **Auth**: Valid access token required.
- **Logic**: Verifies OTP, sets `mfa_enabled: true` for the user. Logs to `audit_logs`.

#### `POST /v1/auth/mfa/verify`

- **Description**: Verifies an OTP during login when MFA is enabled.
- **Request**: `{"email": "string", "otp_code": "string"}`
- **Response**: `{"access_token": "string", "refresh_token": "string", ...}` (Full login response if OTP valid)
- **Auth**: No auth (called after initial password verification).
- **Logic**: Validates OTP, proceeds with token generation. Logs to `audit_logs`.

#### `POST /v1/auth/mfa/disable`

- **Description**: Disables MFA for the authenticated user.
- **Request**: `{"password": "string"}` (to confirm identity)
- **Response**: `{"message": "MFA disabled successfully"}`
- **Auth**: Valid access token required.
- **Logic**: Verifies password, sets `mfa_enabled: false`, clears `mfa_secret` and `recovery_codes`. Logs to `audit_logs`.

#### `GET /v1/auth/sessions`

- **Description**: Lists active sessions for the authenticated user (from `refresh_tokens`).
- **Response**: `Array[{"jti": "string", "issued_at": "Date", "expires_at": "Date", "device_info": "string", "ip_address": "string", "user_agent": "string"}]`
- **Auth**: Valid access token required.

#### `DELETE /v1/auth/sessions/{jti}`

- **Description**: Revokes a specific session (refresh token) by its JTI.
- **Auth**: Valid access token required, user can only revoke their own session or admin can revoke any.
- **Logic**: Marks specific refresh token as revoked. Logs to `audit_logs`.

### 3.2. User Management (Admin / `is_main_client`)

#### `POST /v1/users`

- **Description**: Create a new user (primarily for internal admins or authorized automated systems).
- **Request**: Same as `/v1/auth/register` with full details.
- **Auth**: `rbac:user:create` permission.
- **Logic**: Creates user, assigns roles, sets `client_account_id`. Logs to `audit_logs`.

#### `POST /v1/users/bulk-create`

- **Description**: Creates multiple users in a single request.
- **Request**: `Array[{"email": "string", "password": "string", ...}]`
- **Auth**: `rbac:user:bulk_create` permission.
- **Logic**: Processes user creations, handles errors for individual entries. Logs to `audit_logs`.

#### `GET /v1/users`

- **Description**: List all users (for internal admins) or all sub-users within `client_account_id` (for `is_main_client`).
- **Query Params**: `client_account_id`, `role`, `status`, `search`, `page`, `limit`.
- **Response**: `Array[UserObject]`
- **Auth**: `rbac:user:read` permission.
- **Logic**: Filters by `client_account_id` based on authenticated user's context if not a global admin.

#### `GET /v1/users/{user_id}`

- **Description**: Get a single user's details.
- **Auth**: `rbac:user:read` permission, with data scoping. Users can always read their own profile (`/v1/auth/me`).
- **Logic**: Ensures `user_id` belongs to `client_account_id` if not global admin.

#### `PUT /v1/users/{user_id}`

- **Description**: Update a user's details, roles, or status.
- **Request**: `{"email": "string", "first_name": "string", "last_name": "string", "roles": "Array[String]", "status": "string"}` (fields are optional)
- **Auth**: `rbac:user:update` permission. `is_main_client` users can only update sub-users within their `client_account_id` and can only assign roles that are `is_assignable_by_main_client: true`.
- **Logic**: Updates user record. Reissues new refresh token for user if roles change significantly (to force re-login or refresh). Logs to `audit_logs`.

#### `PUT /v1/users/bulk-update`

- **Description**: Updates multiple user properties in a single request.
- **Request**: `Array[{"user_id": "ObjectId", "roles": "Array[String]", ...}]`
- **Auth**: `rbac:user:bulk_update` permission.
- **Logic**: Processes user updates, handles errors. Logs to `audit_logs`.

#### `POST /v1/users/bulk-assign-roles`

- **Description**: Assigns specific roles to multiple users.
- **Request**: `{"user_ids": "Array[ObjectId]", "roles_to_add": "Array[String]", "roles_to_remove": "Array[String]"}`
- **Auth**: `rbac:user:bulk_assign_roles` permission.
- **Logic**: Updates roles for specified users. Logs to `audit_logs`.

#### `DELETE /v1/users/{user_id}`

- **Description**: Deactivates/Deletes a user.
- **Auth**: `rbac:user:delete` permission. `is_main_client` users can only delete sub-users within their `client_account_id`.
- **Logic**: Sets user status to "inactive" or "deleted". Revokes all refresh tokens for the user. Logs to `audit_logs`.

#### `POST /v1/users/create_sub_user`

- **Description**: Allows a `is_main_client` user to create a new user directly linked to their `client_account_id`.
- **Request**: `{"email": "string", "password": "string", "first_name": "string", "last_name": "string", "roles": "Array[String]"}`
- **Auth**: `rbac:user:create_sub` permission AND `is_main_client: true` for the authenticated user.
- **Logic**: Automatically sets `client_account_id` to authenticated user's `client_account_id`. Validates roles against `is_assignable_by_main_client` flag. Logs to `audit_logs`.

#### `POST /v1/users/{user_id}/data/export`

- **Description**: Initiates export of all user-related data for compliance (e.g., GDPR Right to Data Portability).
- **Auth**: `rbac:user:data_export` or user's own access token.
- **Logic**: Collects user's data from RBAC service, triggers webhook or message queue for other services to export their user data, compiles into a package.

#### `DELETE /v1/users/{user_id}/data/erase`

- **Description**: Initiates permanent erasure of all user-related data for compliance (e.g., GDPR Right to Be Forgotten).
- **Auth**: `rbac:user:data_erase` permission.
- **Logic**: Marks user for deletion/anonymization in RBAC, triggers webhook or message queue for other services to delete/anonymize their user data.

### 3.3. Client Account Management (Admin Only)

#### `POST /v1/client_accounts`

- **Description**: Create a new client account.
- **Request**: `{"name": "string", "description": "string", "main_contact_user_id": "ObjectId"}`
- **Auth**: `rbac:client_account:create` permission.
- **Logic**: Logs to `audit_logs`.

#### `GET /v1/client_accounts`

- **Description**: List all client accounts.
- **Query Params**: `status`, `search`, `page`, `limit`.
- **Response**: `Array[ClientAccountObject]`
- **Auth**: `rbac:client_account:read` permission.

#### `GET /v1/client_accounts/{client_account_id}`

- **Description**: Get details of a single client account.
- **Auth**: `rbac:client_account:read` permission.

#### `PUT /v1/client_accounts/{client_account_id}`

- **Description**: Update client account details.
- **Auth**: `rbac:client_account:update` permission.
- **Logic**: Logs to `audit_logs`.

#### `DELETE /v1/client_accounts/{client_account_id}`

- **Description**: Deactivates/Deletes a client account.
- **Auth**: `rbac:client_account:delete` permission.
- **Logic**: Sets client account status to "inactive" or "deleted". Triggers deactivation/deletion of all associated users. Logs to `audit_logs`.

### 3.4. Role Management (Admin Only)

#### `POST /v1/roles`

- **Description**: Create a new role.
- **Request**: `{"_id": "string", "name": "string", "description": "string", "permissions": "Array[String]", "is_assignable_by_main_client": "boolean"}`
- **Auth**: `rbac:role:create` permission.
- **Logic**: Logs to `audit_logs`.

#### `GET /v1/roles`

- **Description**: List all roles.
- **Response**: `Array[RoleObject]`
- **Auth**: `rbac:role:read` permission. (This is also the endpoint consuming services will use to cache permissions.)

#### `GET /v1/roles/{role_id}`

- **Description**: Get details of a single role.
- **Auth**: `rbac:role:read` permission.

#### `PUT /v1/roles/{role_id}`

- **Description**: Update a role's permissions or properties.
- **Auth**: `rbac:role:update` permission.
- **Logic**: Logs to `audit_logs`. Triggers role cache invalidation in consuming services via webhook/message queue.

#### `DELETE /v1/roles/{role_id}`

- **Description**: Delete a role. (Careful: ensure no users are assigned to this role first.)
- **Auth**: `rbac:role:delete` permission.
- **Logic**: Logs to `audit_logs`. Triggers role cache invalidation in consuming services via webhook/message queue.

### 3.5. Permission Management (Admin Only)

#### `POST /v1/permissions`

- **Description**: Create a new permission.
- **Request**: `{"_id": "string", "description": "string"}`
- **Auth**: `rbac:permission:create` permission.
- **Logic**: Logs to `audit_logs`.

#### `GET /v1/permissions`

- **Description**: List all permissions.
- **Response**: `Array[PermissionObject]`
- **Auth**: `rbac:permission:read` permission.

### 3.6. Audit Log Endpoints (Admin Only)

#### `GET /v1/audit_logs`

- **Description**: Retrieve audit logs.
- **Query Params**: `user_id`, `client_account_id`, `action`, `resource_type`, `start_date`, `end_date`, `ip_address`, `page`, `limit`.
- **Response**: `Array[AuditLogObject]`
- **Auth**: `rbac:audit_log:read` permission.

### 3.7. Health & Monitoring Endpoints

#### `GET /health`

- **Description**: Basic health check (service is running).
- **Response**: `{"status": "ok"}`
- **Auth**: No auth.

#### `GET /health/live`

- **Description**: Liveness probe (service is healthy and ready for traffic).
- **Response**: `{"status": "ok"}`
- **Auth**: No auth.

#### `GET /health/ready`

- **Description**: Readiness probe (service is initialized and ready to serve requests, e.g., database connection established).
- **Response**: `{"status": "ok"}`
- **Auth**: No auth.

## 4. Core Logic & Implementation Details

### 4.1. Password Hashing

- Use Passlib with a strong, modern hashing algorithm like bcrypt or argon2.
- Do not store plain text passwords.
- **Password Policy Enforcement**: Implement rules for password complexity (minimum length, special characters, numbers), history (preventing reuse of recent passwords), and maximum password age.

### 4.2. JWT Generation & Validation

- **Library**: PyJWT
- **Secret Key**: Use a strong, securely stored secret key for signing JWTs.
- **Payload (Access Token)**:
  ```json
  {
    "user_id": "ObjectId",
    "client_account_id": "ObjectId",
    "roles": ["String"],
    "is_main_client": "Boolean",
    "exp": "timestamp",
    "iat": "timestamp",
    "jti": "string"
  }
  ```
- **Payload (Refresh Token)**:
  ```json
  {
    "user_id": "ObjectId",
    "client_account_id": "ObjectId",
    "exp": "timestamp",
    "iat": "timestamp",
    "jti": "string"
  }
  ```
- **Validation** (in RBAC service and consuming services):
  - Check for `Authorization: Bearer <token>` header.
  - Decode and verify signature using the secret key (or public key if asymmetric).
  - Check `exp` (expiration).
  - Check `jti` against the `token_blacklist` (Redis) if blacklisting is implemented.
  - Extract payload for downstream use.

### 4.3. Authorization Logic (PermissionsService / AuthService)

- **Function**: `check_permission(user_roles: List[str], required_permission: str) -> bool`
- **Mechanism**:
  - Retrieve all roles' permissions from cache (or DB if no cache).
  - For each `user_role` in `user_roles`, collect all associated permissions.
  - Check if `required_permission` is in the collected set of permissions.
- **FastAPI Integration**: Use `Depends` to inject `UserContext` (parsed from JWT) into endpoints and then use `check_permission`.
- **Attribute-Based Access Control (ABAC)**:
  - **Mechanism**: Beyond roles, authorization can consider attributes of the user (e.g., IP address, time of day), resource (`resource_permissions` collection), and environment.
  - **Implementation**: The `check_permission` function or a subsequent authorization layer can query `resource_permissions` and evaluate `context_attributes` against the current request context (e.g., `request.client.host`, current time).
  - **Policy Engine**: For complex ABAC, consider integrating a dedicated policy engine (e.g., OPA).

### 4.4. User & Client Account Management

- `create_sub_user` logic:
  - Ensures the caller is `is_main_client` and has `rbac:user:create_sub` permission.
  - Sets the new user's `client_account_id` to the caller's `client_account_id`.
  - Validates that requested roles for the new user are marked `is_assignable_by_main_client: true`.
- **Account Lockout**: Implement logic to increment `failed_login_attempts` on failed logins. If attempts exceed a threshold, set `lockout_until` in the `users` collection.
- **Concurrent Session Limits**: During login, check the number of active `refresh_tokens` for a `user_id`. If a limit is exceeded, prompt the user or automatically revoke the oldest session.

### 4.5. Data Scoping

- Crucial for multi-tenancy.
- In consuming services, all database queries inherently filter by `client_account_id` extracted from the authenticated user's JWT.
- Special logic for "global" roles (e.g., `platform_admin`) that might bypass `client_account_id` filtering.
- For "ownership-based" permissions (e.g., `blog:edit_own`), filter by `user_id` as well (e.g., `{"created_by_rbac_user_id": current_user.user_id}`).

### 4.6. Cache for Roles and Permissions (in Consuming Services)

- **Strategy**: Consuming services should have an in-memory cache (e.g., using `functools.lru_cache` or a dedicated library like `cachetools`) for role -> permissions mappings.
- **Refresh**: Periodically pull updated mappings from RBAC's `GET /v1/roles` endpoint (e.g., every 5-10 minutes).
- **Event-Driven Refresh (Advanced)**: RBAC service publishes "role.updated" or "permission.updated" events to a message queue (e.g., Kafka, RabbitMQ). Consuming services subscribe and refresh their cache immediately upon receiving such events.

### 4.7. Multi-Factor Authentication (MFA) Flows

- **TOTP (Time-Based One-Time Password)**:
  - **Setup**: Generate a secret, store it securely (e.g., encrypted), present QR code (with `otpauth://` URI) and manual key to user. User verifies with first OTP.
  - **Verification**: User provides OTP, RBAC service verifies against stored secret and current time.
  - **Recovery Codes**: Generate a set of unique recovery codes, hash them, store them for the user. Allow one-time use per code.
- **SMS/Email OTP**:
  - **Setup**: Store verified phone/email, send OTP via external service, verify user input.
  - **Verification**: User provides OTP, RBAC service verifies.
- **Device Trust**: Track successful logins from specific device/IP/user-agent combinations. Prompt for MFA less frequently on trusted devices (within a configurable timeframe).

### 4.8. Webhook System

- **Event Publishing**: RBAC service publishes events (e.g., `user.created`, `user.deleted`, `role.changed`, `client_account.suspended`, `user.password_reset`) to configured webhook URLs.
- **Payloads**: Include relevant data in the webhook payload (e.g., `user_id`, `client_account_id`, `old_roles`, `new_roles`).
- **Security**: Sign webhook payloads with a shared secret (HMAC) so consuming services can verify authenticity. Implement retry mechanisms for failed deliveries.

### 4.9. Asynchronous Task Queues

- **Message Broker**: RabbitMQ will be used as the message broker for handling asynchronous tasks that should not block API response times.
- **Use Cases**:
  - **Email Dispatch**: Sending transactional emails (e.g., password resets, welcome emails) will be handled by a dedicated worker consuming messages from a queue. This provides resilience and improves API performance.
  - **Event Notifications**: Publishing events for other internal services to consume (as an alternative or supplement to webhooks).
- **Implementation**: A worker process will be created alongside the main FastAPI application to consume messages. The `pika` or `aio-pika` library will be used for interacting with RabbitMQ.

## 5. Security Considerations

- **Environment Variables**: Store all sensitive configurations (secret keys, database credentials, external API keys) in environment variables, not in code.
- **HTTPS/SSL**: All communication with the RBAC service (and between services) must be over HTTPS/TLS.
- **Rate Limiting**: Implement robust rate limiting on login attempts, registration, password reset, and MFA verification endpoints to prevent brute-force and denial-of-service attacks.
- **Input Validation**: Strictly validate and sanitize all input to prevent injection attacks (e.g., MongoDB injection) and ensure data integrity.
- **Error Handling**: Provide generic error messages to clients (e.g., "Invalid credentials") without revealing specific reasons for failure (e.g., "User not found"). Log detailed errors internally.
- **HttpOnly Cookies (Frontend)**: For maximum security, consider setting JWT (access token and refresh token) in `HttpOnly` cookies from the backend. This prevents client-side JavaScript from accessing the token, mitigating XSS attacks.
- **CORS**: Configure Cross-Origin Resource Sharing (CORS) appropriately to allow only authorized frontends to communicate with the API.
- **Security Headers**: Implement appropriate HTTP security headers (CSP, X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security, X-XSS-Protection).
- **Account Lockout Policy**: Automatically lock accounts for a configurable duration after N failed login attempts.
- **Password Policies**: Enforce password complexity (min length, uppercase, lowercase, numbers, symbols), disallow common/breached passwords, and mandate periodic password changes.
- **GDPR/Privacy**: Design with privacy by design principles. Implement endpoints for data export (Right to Data Portability) and data erasure (Right to Be Forgotten). Ensure data minimization.

## 6. Deployment & Scalability Notes

- **Containerization**: Dockerize the FastAPI application for easy deployment and scaling.
- **Orchestration**: Deploy using Kubernetes or similar orchestration platforms for high availability, automatic scaling, and self-healing capabilities.
- **Database Scaling**: MongoDB can scale horizontally with sharding for high read/write loads. Implement replica sets for high availability.
- **Redis**: Deploy Redis separately for caching and blacklist, ensuring it's highly available (e.g., Sentinel or Cluster mode).
- **Monitoring**: Implement robust logging (structured logging with ELK stack or similar), tracing (Jaeger/OpenTelemetry), and metrics collection (Prometheus/Grafana) for performance, errors, security events, and API usage.
- **Key Metrics to Track**:
  - Authentication success/failure rates.
  - Token refresh rates and expiry.
  - Permission check latency.
  - API endpoint response times and error rates.
  - Active sessions per user/client.
  - Resource utilization (CPU, memory, network, disk I/O).
  - Database query performance.
- **Backup & Recovery**: Implement automated, regular backups of the MongoDB and Redis data. Plan for point-in-time recovery capabilities. Test backup restoration procedures regularly.
- **Data Retention Policies**: Configure policies for automatic cleanup of `audit_logs`, `refresh_tokens`, and potentially `deleted_users` records after a defined period (e.g., using TTL indexes in MongoDB or scheduled cleanup jobs).
  ```python
  # Example configuration (can be stored in a config service or DB)
  retention_policies = {
      "audit_logs_days": 365,
      "expired_tokens_days": 30, # How long to keep expired refresh token records
      "deleted_users_anonymization_days": 90 # Days before truly anonymizing/purging deleted user data
  }
  ```
- **Zero-Downtime Deployments**: Design deployment pipelines to allow for zero-downtime updates and rollbacks.

## 7. Developer Experience & Documentation

- **OpenAPI/Swagger Documentation**: Leverage FastAPI's automatic generation of OpenAPI (Swagger UI) documentation. Ensure endpoints, request/response models, and security schemes are well-documented.
- **Client Libraries**: Provide official client libraries (e.g., Python, JavaScript) that encapsulate API interactions, JWT handling, and authorization helpers. This reduces integration effort for consuming services.
- **SDK Generation**: Explore tools to generate client SDKs from the OpenAPI specification for various languages.
- **Admin UI Specification**:
  - **Purpose**: A dedicated web-based UI for managing the RBAC service itself (users, client accounts, roles, permissions, audit logs).
  - **Technology**: Recommended to use Nuxt.js for consistency with your existing stack.
  - **Features**:
    - Dashboard for overall system health and key metrics.
    - User management (create, view, edit, delete, assign roles, reset password, manage MFA settings, view sessions, manage lockout).
    - Client account management (create, view, edit, suspend/activate).
    - Role management (create, view, edit permissions for roles, assign roles to users).
    - Permission viewing (list all defined permissions).
    - Audit log viewer with filters and search.
    - Webhook configuration.
    - Password policy settings.
    - MFA configuration for the system.
  - **Auth**: Requires highly privileged `platform_admin` role.
- **Runbooks**: Create comprehensive operational runbooks for common scenarios (e.g., password resets, account lockouts, user support, deployment, incident response).

## 8. Industry Standards Compliance

The specification aligns well with industry standards:

- ✅ OAuth 2.0/JWT standards for authentication and token management.
- ✅ RBAC model follows NIST (National Institute of Standards and Technology) guidelines.
- ✅ RESTful API design principles.
- ✅ Security best practices (OWASP guidelines, principle of least privilege).
- ✅ Compliance considerations for GDPR (Right to Data Portability, Right to Be Forgotten).

**Additional Standards to Consider**:

- SOC 2: For security, availability, processing integrity, confidentiality, and privacy.
- ISO 27001: For information security management systems.
- FIDO2/WebAuthn: For advanced passwordless authentication mechanisms.
- HIPAA (if dealing with health data): Ensure proper safeguards for protected health information.

## Conclusion

This enhanced specification provides a robust foundation for a generic RBAC microservice. By centralizing user identity and access management, it offers significant security, scalability, and reusability benefits across your entire application portfolio. Implementing the detailed features, particularly around advanced authentication, audit logging, and comprehensive data management, will ensure its long-term sustainability and compliance readiness.

---

## Development Phases

This project will be developed in phases to ensure the most critical components are built first, allowing for iterative development and feedback.

### Phase 1: Core RBAC Foundation (MVP)

The goal of this phase is to establish the fundamental authentication and authorization capabilities.

- **Technology Stack Setup:**
  - ✅ Initialize FastAPI project structure.
  - ✅ Connect to MongoDB.
- **Core Database Schema:**
  - ✅ `users` collection.
  - ✅ `roles` collection.
  - ✅ `permissions` collection.
- **Core Authentication API:**
  - ✅ `POST /v1/auth/register`: A simplified version for admins to create the first users. (Implemented via `POST /v1/users`)
  - ✅ `POST /v1/auth/login`: User authentication and JWT generation.
  - ✅ `GET /v1/auth/me`: Retrieve authenticated user's details.
- **Core Authorization Logic:**
  - ✅ Implement JWT validation middleware.
  - ✅ Create dependency for checking permissions based on roles.
  - `POST /v1/auth/authorize`: Internal endpoint for services to verify permissions.
- **Basic Management APIs (Admin-only):**
  - ✅ **Users:** `POST /v1/users`, `GET /v1/users`, `GET /v1/users/{user_id}`, `PUT /v1/users/{user_id}`, `DELETE /v1/users/{user_id}`.
  - ✅ **Roles:** `POST /v1/roles`, `GET /v1/roles`, `GET /v1/roles/{role_id}`, `PUT /v1/roles/{role_id}`, `DELETE /v1/roles/{role_id}`.
  - ✅ **Permissions:** `POST /v1/permissions`, `GET /v1/permissions`.
- **Core Logic Implementation:**
  - ✅ Password hashing with Passlib.
  - ✅ Basic JWT generation (Access Token only) and validation.
- **Documentation:**
  - ✅ Auto-generated OpenAPI/Swagger docs for the implemented endpoints.

### Phase 2: Enhanced User Experience & Security

This phase builds on the MVP by adding user self-service features and strengthening security.

- **Database Schema:**
  - ✅ `refresh_tokens` collection.
  - `token_blacklist` collection (using Redis).
  - Add `failed_login_attempts` and `lockout_until` to `users` collection.
- **Enhanced Authentication API:**
  - ✅ `POST /v1/auth/refresh`: Implement refresh tokens.
  - ✅ `POST /v1/auth/logout`: Revoke current refresh token.
  - ✅ `POST /v1/auth/logout_all`: Revoke all user's refresh tokens.
- **Password Management API:**
  - `POST /v1/auth/password/reset-request`.
  - `POST /v1/auth/password/reset-confirm`.
  - `POST /v1/auth/password/change`.
- **Security Hardening:**
  - Implement account lockout logic.
  - ✅ Implement token blacklisting for immediate access token revocation on logout. (Implemented via DB-backed refresh token revocation).
  - Implement basic rate limiting on authentication endpoints.

### Phase 3: Multi-Tenancy and Client Management

This phase introduces organizational accounts, a core feature for B2B SaaS applications.

- **Database Schema:**
  - ✅ `client_accounts` collection.
  - ✅ Update `users` schema to include `client_account_id` and `is_main_client`.
  - ✅ Update `roles` schema to include `is_assignable_by_main_client`.
- **Multi-Tenancy Logic:**
  - ✅ Implement data scoping across all relevant APIs to ensure clients can only access their own data.
  - ✅ `POST /v1/users/create_sub_user`: Allow `is_main_client` users to create users within their own organization.
  - ✅ Update user/role management endpoints to respect multi-tenancy rules.
- **Client Account Management API (Admin-only):**
  - ✅ Full CRUD for `client_accounts`: `POST`, `GET`, `PUT`, `DELETE`.

### Phase 4: Advanced Features

This phase includes features that provide comprehensive security, compliance, and integration capabilities.

- **Database Schema:**
  - `audit_logs` collection.
  - `resource_permissions` collection (for ABAC).
  - `webhooks` collection.
- **Feature Implementation:**
  - **MFA:** Full suite of `/v1/auth/mfa/*` endpoints and logic.
  - **Audit Logging:** Integrate logging into all sensitive operations and expose `GET /v1/audit_logs`.
  - **Bulk Operations:** Implement all `bulk-*` endpoints for user management.
  - **GDPR/Compliance:** Implement `data/export` and `data/erase` endpoints.
  - **Session Management:** Implement `GET /v1/auth/sessions` and `DELETE /v1/auth/sessions/{jti}`.
  - **Webhooks:** Implement the webhook publishing system.

### Phase 5: Production Readiness & Developer Experience

This phase focuses on non-functional requirements and making the service easy to operate, scale, and integrate with.

- **Deployment & Scalability:**
  - ✅ Create `Dockerfile` for containerization.
  - ✅ Set up configuration for orchestration (e.g., Docker Compose for local, Kubernetes manifests for prod).
  - ✅ Implement health check endpoints: `/health`, `/health/live`, `/health/ready`.
- **Monitoring & Observability:**
  - Integrate structured logging.
  - Set up metrics collection (e.g., Prometheus) and tracing (e.g., OpenTelemetry).
- **Developer Experience:**
  - Develop and publish client SDKs for key languages (e.g., Python, JavaScript).
  - Develop a full-featured Admin UI (Nuxt.js).
  - Write comprehensive runbooks for operations.
- **Caching Strategy:**
  - Implement and document the recommended caching strategy for roles/permissions in consuming services.
- **Advanced Security:**
  - Conduct a thorough security review.
  - Implement all security headers, advanced CORS policies, and other items from "Security Considerations".
