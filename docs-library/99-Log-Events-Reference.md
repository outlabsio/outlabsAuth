# 99. Log Events Reference

> **Quick Reference**: Complete catalog of all structured log events emitted by OutlabsAuth. Use this for log searching, filtering, and building alerts.

## Overview

OutlabsAuth emits structured log events for all critical authentication and authorization operations. Each event has a consistent schema with standard fields plus event-specific data.

**Standard Fields (All Events):**
- `timestamp` - ISO 8601 timestamp (UTC)
- `level` - Log level (debug, info, warning, error, critical)
- `event` - Event name (e.g., `user_login_success`)
- `correlation_id` - Request correlation ID for distributed tracing
- `service` - Service name (always `outlabs_auth`)

**Optional Fields (When Available):**
- `user_id` - User's ID
- `email` - User's email address (if not redacted)
- `ip_address` - Client IP address
- `user_agent` - Client user agent string
- `duration_ms` - Operation duration in milliseconds

---

## Authentication Events

### user_login_success

**Level:** INFO
**When:** User successfully logs in with any authentication method
**Frequency:** Per login (moderate volume)

**Fields:**
- `user_id` (string) - User's ID
- `email` (string) - User's email
- `method` (string) - Auth method: `password`, `google`, `facebook`, `apple`, `github`, `api_key`
- `duration_ms` (float) - Time taken for login operation
- `ip_address` (string, optional) - Client IP address
- `user_agent` (string, optional) - Client user agent
- `device_name` (string, optional) - Device name if provided

**Example:**
```json
{
  "timestamp": "2025-01-24T10:15:23.456Z",
  "level": "info",
  "event": "user_login_success",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "email": "john@example.com",
  "method": "password",
  "duration_ms": 145.3,
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
}
```

**Search Examples:**
```bash
# Find all logins by specific user
jq 'select(.event == "user_login_success" and .user_id == "507f...")' app.log

# Find all Google OAuth logins
jq 'select(.event == "user_login_success" and .method == "google")' app.log

# Find slow logins (>500ms)
jq 'select(.event == "user_login_success" and .duration_ms > 500)' app.log
```

---

### user_login_failed

**Level:** WARNING
**When:** Login attempt fails
**Frequency:** Per failed login (should be low, spikes indicate attacks)

**Fields:**
- `email` (string, optional) - Email attempted (may be invalid)
- `method` (string) - Auth method attempted
- `reason` (string) - Failure reason:
  - `invalid_credentials` - Wrong password
  - `user_not_found` - Email doesn't exist
  - `account_locked` - Too many failed attempts
  - `account_suspended` - Account suspended by admin
  - `account_deleted` - Account has been deleted
  - `email_not_verified` - Email verification required
  - `oauth_error` - OAuth provider error
- `duration_ms` (float) - Time taken
- `ip_address` (string, optional) - Client IP
- `user_agent` (string, optional) - Client user agent
- `failed_attempts` (int, optional) - Current failed attempt count

**Example:**
```json
{
  "timestamp": "2025-01-24T10:16:45.123Z",
  "level": "warning",
  "event": "user_login_failed",
  "correlation_id": "b2c3d4e5-f6a7-8901-bcde-f23456789abc",
  "service": "outlabs_auth",
  "email": "john@example.com",
  "method": "password",
  "reason": "invalid_credentials",
  "duration_ms": 98.2,
  "ip_address": "192.168.1.1",
  "failed_attempts": 3
}
```

**Search Examples:**
```bash
# Find all failed login attempts
jq 'select(.event == "user_login_failed")' app.log

# Find brute force attempts (multiple failures from same IP)
jq 'select(.event == "user_login_failed") | .ip_address' app.log | sort | uniq -c | sort -rn

# Find accounts being targeted
jq 'select(.event == "user_login_failed") | .email' app.log | sort | uniq -c | sort -rn
```

---

### user_logout

**Level:** INFO
**When:** User logs out (explicit or token expiry)
**Frequency:** Per logout (moderate volume)

**Fields:**
- `user_id` (string) - User's ID
- `email` (string) - User's email
- `method` (string) - Logout trigger:
  - `explicit` - User clicked logout
  - `token_expiry` - Refresh token expired
  - `admin_revoke` - Admin revoked session
  - `security_revoke` - Revoked for security reasons
- `session_duration_seconds` (int) - How long user was logged in

**Example:**
```json
{
  "timestamp": "2025-01-24T12:30:15.789Z",
  "level": "info",
  "event": "user_logout",
  "correlation_id": "c3d4e5f6-a7b8-9012-cdef-34567890abcd",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "email": "john@example.com",
  "method": "explicit",
  "session_duration_seconds": 7892
}
```

---

### token_refreshed

**Level:** INFO
**When:** Access token successfully refreshed
**Frequency:** High volume (every 15 minutes per active user)
**Default:** Not logged (use metrics instead)

**Fields:**
- `user_id` (string) - User's ID
- `duration_ms` (float) - Refresh operation duration

**Example:**
```json
{
  "timestamp": "2025-01-24T10:30:00.123Z",
  "level": "info",
  "event": "token_refreshed",
  "correlation_id": "d4e5f6a7-b8c9-0123-def4-567890abcdef",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "duration_ms": 12.5
}
```

---

### token_refresh_failed

**Level:** WARNING
**When:** Token refresh fails (invalid or expired refresh token)
**Frequency:** Low (users need to re-login when this happens)

**Fields:**
- `reason` (string) - Failure reason:
  - `invalid_token` - Token malformed or doesn't exist
  - `expired_token` - Refresh token expired
  - `revoked_token` - Token was revoked
  - `user_not_found` - User deleted

**Example:**
```json
{
  "timestamp": "2025-01-24T10:31:00.456Z",
  "level": "warning",
  "event": "token_refresh_failed",
  "correlation_id": "e5f6a7b8-c9d0-1234-ef56-7890abcdef01",
  "service": "outlabs_auth",
  "reason": "expired_token"
}
```

---

### account_locked

**Level:** WARNING
**When:** Account locked due to failed login attempts
**Frequency:** Low (should be rare, spikes indicate attacks)

**Fields:**
- `user_id` (string) - User's ID
- `email` (string) - User's email
- `failed_attempts` (int) - Number of failed attempts that triggered lockout
- `locked_until` (string, optional) - ISO timestamp when lock expires (if temporary)
- `ip_address` (string, optional) - Last IP address that attempted login

**Example:**
```json
{
  "timestamp": "2025-01-24T10:20:00.789Z",
  "level": "warning",
  "event": "account_locked",
  "correlation_id": "f6a7b8c9-d0e1-2345-f678-90abcdef0123",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "email": "john@example.com",
  "failed_attempts": 5,
  "locked_until": "2025-01-24T11:20:00.000Z",
  "ip_address": "192.168.1.1"
}
```

**Search Examples:**
```bash
# Find all locked accounts today
jq 'select(.event == "account_locked")' app.log | jq -r '.email' | sort | uniq

# Find IPs causing lockouts
jq 'select(.event == "account_locked") | .ip_address' app.log | sort | uniq -c
```

---

## Authorization Events

### permission_check_granted

**Level:** DEBUG
**When:** Permission check allows access
**Frequency:** Very high volume
**Default:** Not logged (use `log_permission_checks="all"` to enable)

**Fields:**
- `user_id` (string) - User's ID
- `permission` (string) - Permission checked (e.g., `user:read`)
- `resource_id` (string, optional) - Specific resource being accessed
- `entity_id` (string, optional) - Entity context (EnterpriseRBAC)
- `duration_ms` (float) - Time taken for check

**Example:**
```json
{
  "timestamp": "2025-01-24T10:15:30.123Z",
  "level": "debug",
  "event": "permission_check_granted",
  "correlation_id": "a7b8c9d0-e1f2-3456-789a-bcdef0123456",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "permission": "user:read",
  "duration_ms": 2.3
}
```

---

### permission_check_denied

**Level:** WARNING
**When:** Permission check denies access
**Frequency:** Should be low (high rates indicate misconfigured roles)
**Default:** Always logged (can disable with `log_permission_checks="none"`)

**Fields:**
- `user_id` (string) - User's ID
- `email` (string, optional) - User's email
- `permission` (string) - Permission checked
- `resource_id` (string, optional) - Specific resource
- `entity_id` (string, optional) - Entity context
- `duration_ms` (float) - Time taken
- `reason` (string, optional) - Denial reason:
  - `no_permission` - User doesn't have permission
  - `abac_denied` - ABAC condition failed
  - `entity_denied` - Not member of required entity
  - `inactive_user` - User account inactive

**Example:**
```json
{
  "timestamp": "2025-01-24T10:16:00.456Z",
  "level": "warning",
  "event": "permission_check_denied",
  "correlation_id": "b8c9d0e1-f2a3-4567-890b-cdef01234567",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "email": "john@example.com",
  "permission": "user:delete",
  "reason": "no_permission",
  "duration_ms": 3.1
}
```

**Search Examples:**
```bash
# Find all denied permissions
jq 'select(.event == "permission_check_denied")' app.log

# Top denied permissions
jq 'select(.event == "permission_check_denied") | .permission' app.log | sort | uniq -c | sort -rn

# Users experiencing denials
jq 'select(.event == "permission_check_denied") | .email' app.log | sort | uniq -c
```

---

### permission_check_slow

**Level:** WARNING
**When:** Permission check takes >100ms (performance issue)
**Frequency:** Should be rare
**Default:** Always logged

**Fields:**
- `user_id` (string) - User's ID
- `permission` (string) - Permission checked
- `entity_id` (string, optional) - Entity context
- `duration_ms` (float) - Time taken (>100ms)
- `hierarchy_depth` (int, optional) - Entity hierarchy depth traversed
- `abac_conditions_evaluated` (int, optional) - Number of ABAC conditions

**Example:**
```json
{
  "timestamp": "2025-01-24T10:17:00.789Z",
  "level": "warning",
  "event": "permission_check_slow",
  "correlation_id": "c9d0e1f2-a3b4-5678-901c-def012345678",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "permission": "lead:read_tree",
  "entity_id": "ent_workspace_abc123",
  "duration_ms": 156.7,
  "hierarchy_depth": 8,
  "abac_conditions_evaluated": 3
}
```

---

## API Key Events

### api_key_validated

**Level:** DEBUG
**When:** API key successfully validated
**Frequency:** Very high volume
**Default:** Not logged (use `log_api_key_hits=True` to enable)

**Fields:**
- `api_key_prefix` (string) - First 12 chars of API key (e.g., `sk_live_abc1`)
- `api_key_id` (string) - API key ID
- `user_id` (string, optional) - Associated user ID
- `duration_ms` (float) - Validation time

**Example:**
```json
{
  "timestamp": "2025-01-24T10:18:00.123Z",
  "level": "debug",
  "event": "api_key_validated",
  "correlation_id": "d0e1f2a3-b4c5-6789-012d-ef0123456789",
  "service": "outlabs_auth",
  "api_key_prefix": "sk_live_abc1",
  "api_key_id": "key_123456",
  "duration_ms": 1.2
}
```

---

### api_key_validation_failed

**Level:** WARNING
**When:** API key validation fails
**Frequency:** Should be low (spikes indicate scanning attacks)

**Fields:**
- `api_key_prefix` (string, optional) - Prefix if key format is valid
- `reason` (string) - Failure reason:
  - `invalid_format` - Malformed API key
  - `not_found` - API key doesn't exist
  - `expired` - API key expired
  - `disabled` - API key was disabled
  - `rate_limited` - Rate limit exceeded
- `ip_address` (string, optional) - Client IP

**Example:**
```json
{
  "timestamp": "2025-01-24T10:19:00.456Z",
  "level": "warning",
  "event": "api_key_validation_failed",
  "correlation_id": "e1f2a3b4-c5d6-7890-123e-f01234567890",
  "service": "outlabs_auth",
  "api_key_prefix": "sk_live_xyz9",
  "reason": "not_found",
  "ip_address": "203.0.113.42"
}
```

**Search Examples:**
```bash
# Find invalid API key attempts
jq 'select(.event == "api_key_validation_failed")' app.log

# Find API key scanning attacks (invalid formats)
jq 'select(.event == "api_key_validation_failed" and .reason == "invalid_format")' app.log

# IPs attempting invalid keys
jq 'select(.event == "api_key_validation_failed") | .ip_address' app.log | sort | uniq -c
```

---

### api_key_rate_limit_exceeded

**Level:** WARNING
**When:** API key hits rate limit
**Frequency:** Depends on usage patterns

**Fields:**
- `api_key_prefix` (string) - API key prefix
- `api_key_id` (string) - API key ID
- `rate_limit` (int) - Configured rate limit (requests per minute)
- `current_rate` (int) - Current request rate

**Example:**
```json
{
  "timestamp": "2025-01-24T10:20:00.789Z",
  "level": "warning",
  "event": "api_key_rate_limit_exceeded",
  "correlation_id": "f2a3b4c5-d6e7-8901-234f-012345678901",
  "service": "outlabs_auth",
  "api_key_prefix": "sk_live_abc1",
  "api_key_id": "key_123456",
  "rate_limit": 1000,
  "current_rate": 1247
}
```

---

## Security Events

### suspicious_activity_detected

**Level:** WARNING / ERROR
**When:** Suspicious activity patterns detected
**Frequency:** Should be rare

**Fields:**
- `type` (string) - Activity type:
  - `brute_force` - Multiple failed logins
  - `session_hijack` - IP/user agent changed mid-session
  - `rate_limit_abuse` - Excessive requests
  - `invalid_token_flood` - Many invalid tokens
  - `api_key_scanning` - Scanning for valid API keys
- `user_id` (string, optional) - Affected user
- `email` (string, optional) - User email
- `ip_address` (string, optional) - Suspicious IP
- `details` (object) - Additional context

**Example:**
```json
{
  "timestamp": "2025-01-24T10:21:00.123Z",
  "level": "error",
  "event": "suspicious_activity_detected",
  "correlation_id": "a3b4c5d6-e7f8-9012-345a-123456789012",
  "service": "outlabs_auth",
  "type": "brute_force",
  "email": "target@example.com",
  "ip_address": "203.0.113.42",
  "details": {
    "failed_attempts": 50,
    "time_window_minutes": 5,
    "accounts_targeted": 12
  }
}
```

---

### session_hijack_suspected

**Level:** ERROR
**When:** Session shows signs of hijacking
**Frequency:** Should be very rare

**Fields:**
- `user_id` (string) - User's ID
- `email` (string) - User's email
- `reason` (string) - Detection reason:
  - `ip_changed` - IP address changed during session
  - `user_agent_changed` - User agent changed
  - `location_anomaly` - Geographic location jumped
- `original_ip` (string, optional) - Original IP
- `new_ip` (string, optional) - New IP
- `original_user_agent` (string, optional) - Original user agent
- `new_user_agent` (string, optional) - New user agent

**Example:**
```json
{
  "timestamp": "2025-01-24T10:22:00.456Z",
  "level": "error",
  "event": "session_hijack_suspected",
  "correlation_id": "b4c5d6e7-f8a9-0123-456b-234567890123",
  "service": "outlabs_auth",
  "user_id": "507f1f77bcf86cd799439011",
  "email": "john@example.com",
  "reason": "ip_changed",
  "original_ip": "192.168.1.1",
  "new_ip": "203.0.113.99"
}
```

---

## Performance Events

### cache_invalidated

**Level:** DEBUG
**When:** Cache entry invalidated (Redis pub/sub)
**Frequency:** Per cache invalidation

**Fields:**
- `cache_type` (string) - Type: `permission`, `role`, `user`, `entity`
- `cache_key` (string) - Invalidated key
- `reason` (string) - Invalidation reason:
  - `update` - Data was updated
  - `delete` - Data was deleted
  - `ttl_expired` - TTL expired
  - `manual_flush` - Manually flushed

**Example:**
```json
{
  "timestamp": "2025-01-24T10:23:00.789Z",
  "level": "debug",
  "event": "cache_invalidated",
  "correlation_id": "c5d6e7f8-a9b0-1234-567c-345678901234",
  "service": "outlabs_auth",
  "cache_type": "permission",
  "cache_key": "perm:507f1f77bcf86cd799439011:user:read",
  "reason": "update"
}
```

---

### slow_database_query

**Level:** WARNING
**When:** Database query takes >100ms
**Frequency:** Should be rare

**Fields:**
- `operation` (string) - Operation type: `find`, `insert`, `update`, `delete`
- `collection` (string) - MongoDB collection
- `duration_ms` (float) - Query duration
- `query_filter` (object, optional) - Query filter (sanitized)

**Example:**
```json
{
  "timestamp": "2025-01-24T10:24:00.123Z",
  "level": "warning",
  "event": "slow_database_query",
  "correlation_id": "d6e7f8a9-b0c1-2345-678d-456789012345",
  "service": "outlabs_auth",
  "operation": "find",
  "collection": "users",
  "duration_ms": 156.3,
  "query_filter": {
    "email": "***REDACTED***"
  }
}
```

---

## Error Events

### authentication_error

**Level:** ERROR
**When:** Unexpected error during authentication
**Frequency:** Should be very rare

**Fields:**
- `error_type` (string) - Error class name
- `error_message` (string) - Error message
- `stack_trace` (string, optional) - Stack trace (if enabled)
- `user_id` (string, optional) - User ID if available
- `method` (string, optional) - Auth method being attempted

**Example:**
```json
{
  "timestamp": "2025-01-24T10:25:00.456Z",
  "level": "error",
  "event": "authentication_error",
  "correlation_id": "e7f8a9b0-c1d2-3456-789e-567890123456",
  "service": "outlabs_auth",
  "error_type": "DatabaseConnectionError",
  "error_message": "Unable to connect to MongoDB",
  "method": "password"
}
```

---

### authorization_error

**Level:** ERROR
**When:** Unexpected error during permission check
**Frequency:** Should be very rare

**Fields:**
- `error_type` (string) - Error class name
- `error_message` (string) - Error message
- `user_id` (string, optional) - User ID
- `permission` (string, optional) - Permission being checked

**Example:**
```json
{
  "timestamp": "2025-01-24T10:26:00.789Z",
  "level": "error",
  "event": "authorization_error",
  "correlation_id": "f8a9b0c1-d2e3-4567-890f-678901234567",
  "service": "outlabs_auth",
  "error_type": "ABACEvaluationError",
  "error_message": "Failed to evaluate ABAC condition",
  "user_id": "507f1f77bcf86cd799439011",
  "permission": "lead:read"
}
```

---

## Filtering & Searching

### Common jq Patterns

```bash
# All events for specific user
jq 'select(.user_id == "507f1f77bcf86cd799439011")' app.log

# All events with specific correlation ID
jq 'select(.correlation_id == "a1b2c3d4-...")' app.log

# All WARNING and ERROR level events
jq 'select(.level == "warning" or .level == "error")' app.log

# Events in time range
jq 'select(.timestamp >= "2025-01-24T10:00:00Z" and .timestamp <= "2025-01-24T11:00:00Z")' app.log

# Group events by type
jq -r '.event' app.log | sort | uniq -c | sort -rn

# Count events per user
jq -r '.user_id' app.log | sort | uniq -c | sort -rn

# Find slow operations (>100ms)
jq 'select(.duration_ms > 100)' app.log
```

---

## Next Steps

- **[97-Observability.md](97-Observability.md)** - Main observability guide
- **[98-Metrics-Reference.md](98-Metrics-Reference.md)** - Complete metrics catalog
- **[Grafana Dashboard](../grafana-dashboards/README.md)** - Pre-built dashboard

---

**Last Updated:** 2025-01-24
**Related:** [97-Observability.md](97-Observability.md), [98-Metrics-Reference.md](98-Metrics-Reference.md)
