# 98. Metrics Reference

> **Quick Reference**: Complete catalog of all Prometheus metrics exposed by OutlabsAuth. Use this for building dashboards, alerts, and monitoring queries.

## Overview

OutlabsAuth exposes Prometheus metrics at the `/metrics` endpoint for monitoring authentication and authorization operations.

**Metric Types:**
- **Counter** - Cumulative value that only increases (e.g., total logins)
- **Histogram** - Distribution of values with buckets (e.g., latency)
- **Gauge** - Current value that can go up or down (e.g., active sessions)

**Common Labels:**
- `status` - Operation result (success, failed, denied, etc.)
- `method` - Authentication method (password, google, api_key, etc.)
- `permission` - Permission being checked (user:read, post:create, etc.)
- `result` - Permission check result (granted, denied)

---

## Authentication Metrics

### outlabs_auth_login_attempts_total

**Type:** Counter
**Description:** Total number of login attempts (successful and failed)

**Labels:**
- `status` - Login result
  - `success` - Login succeeded
  - `failed` - Login failed (invalid credentials, locked account, etc.)
- `method` - Authentication method
  - `password` - Email/password login
  - `google` - Google OAuth login
  - `facebook` - Facebook OAuth login
  - `apple` - Apple Sign In
  - `github` - GitHub OAuth login
  - `api_key` - API key authentication

**Example Queries:**

```promql
# Login success rate (last 5 minutes)
rate(outlabs_auth_login_attempts_total{status="success"}[5m])

# Login failure rate (detect attacks)
rate(outlabs_auth_login_attempts_total{status="failed"}[5m])

# Success ratio (should be high)
sum(rate(outlabs_auth_login_attempts_total{status="success"}[5m]))
/
sum(rate(outlabs_auth_login_attempts_total[5m]))

# Logins by method
sum by (method) (rate(outlabs_auth_login_attempts_total{status="success"}[1h]))
```

**Recommended Alerts:**

```yaml
# High failure rate (possible attack)
- alert: HighLoginFailureRate
  expr: rate(outlabs_auth_login_attempts_total{status="failed"}[5m]) > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High login failure rate detected"
    description: "{{ $value }} failed logins per second"

# Login success rate drop
- alert: LoginSuccessRateDrop
  expr: |
    sum(rate(outlabs_auth_login_attempts_total{status="success"}[5m]))
    /
    sum(rate(outlabs_auth_login_attempts_total[5m])) < 0.8
  for: 10m
  labels:
    severity: critical
  annotations:
    summary: "Login success rate below 80%"
```

---

### outlabs_auth_login_duration_seconds

**Type:** Histogram
**Description:** Time taken for login operations (in seconds)

**Labels:**
- `method` - Authentication method (password, google, api_key, etc.)

**Buckets:** `[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]` (1ms to 1s)

**Example Queries:**

```promql
# P50 (median) login latency
histogram_quantile(0.5, rate(outlabs_auth_login_duration_seconds_bucket[5m]))

# P95 login latency
histogram_quantile(0.95, rate(outlabs_auth_login_duration_seconds_bucket[5m]))

# P99 login latency (slowest 1%)
histogram_quantile(0.99, rate(outlabs_auth_login_duration_seconds_bucket[5m]))

# Average login duration
rate(outlabs_auth_login_duration_seconds_sum[5m])
/
rate(outlabs_auth_login_duration_seconds_count[5m])

# P95 latency by method
histogram_quantile(0.95, sum by (method, le) (rate(outlabs_auth_login_duration_seconds_bucket[5m])))
```

**Recommended Alerts:**

```yaml
# Slow logins
- alert: SlowLoginLatency
  expr: histogram_quantile(0.95, rate(outlabs_auth_login_duration_seconds_bucket[5m])) > 0.5
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "P95 login latency above 500ms"
    description: "Login operations are taking {{ $value }}s at P95"
```

---

### outlabs_auth_logout_total

**Type:** Counter
**Description:** Total number of logout operations

**Labels:**
- `method` - How logout was triggered
  - `explicit` - User clicked logout
  - `token_expiry` - Token expired
  - `admin_revoke` - Admin revoked session

**Example Queries:**

```promql
# Logout rate
rate(outlabs_auth_logout_total[5m])

# Logouts by method
sum by (method) (rate(outlabs_auth_logout_total[1h]))
```

---

### outlabs_auth_token_refresh_total

**Type:** Counter
**Description:** Total number of access token refresh operations

**Labels:**
- `status` - Refresh result
  - `success` - Token refreshed successfully
  - `failed` - Refresh failed (invalid/expired refresh token)

**Example Queries:**

```promql
# Token refresh rate
rate(outlabs_auth_token_refresh_total{status="success"}[5m])

# Failed refresh rate (users need to re-login)
rate(outlabs_auth_token_refresh_total{status="failed"}[5m])
```

**Recommended Alerts:**

```yaml
# High refresh failure rate
- alert: HighTokenRefreshFailureRate
  expr: rate(outlabs_auth_token_refresh_total{status="failed"}[5m]) > 5
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High token refresh failure rate"
    description: "Many users unable to refresh tokens (forced re-login)"
```

---

### outlabs_auth_account_locked_total

**Type:** Counter
**Description:** Total number of accounts locked due to failed login attempts

**Labels:** None

**Example Queries:**

```promql
# Account lockout rate
rate(outlabs_auth_account_locked_total[1h])

# Total locked accounts today
increase(outlabs_auth_account_locked_total[24h])
```

**Recommended Alerts:**

```yaml
# Spike in account lockouts (possible attack)
- alert: HighAccountLockoutRate
  expr: rate(outlabs_auth_account_locked_total[5m]) > 2
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Unusual number of account lockouts"
    description: "Possible brute force attack"
```

---

## Authorization Metrics

### outlabs_auth_permission_checks_total

**Type:** Counter
**Description:** Total number of permission checks performed

**Labels:**
- `result` - Permission check result
  - `granted` - Permission allowed
  - `denied` - Permission denied
- `permission` - Permission being checked (e.g., `user:read`, `post:create`, `*:*`)

**Example Queries:**

```promql
# Permission check rate
rate(outlabs_auth_permission_checks_total[5m])

# Denied permission rate
rate(outlabs_auth_permission_checks_total{result="denied"}[5m])

# Top denied permissions
topk(10, sum by (permission) (rate(outlabs_auth_permission_checks_total{result="denied"}[1h])))

# Permission grant ratio (should be high)
sum(rate(outlabs_auth_permission_checks_total{result="granted"}[5m]))
/
sum(rate(outlabs_auth_permission_checks_total[5m]))
```

**Recommended Alerts:**

```yaml
# Sudden spike in denied permissions
- alert: HighPermissionDenialRate
  expr: rate(outlabs_auth_permission_checks_total{result="denied"}[5m]) > 50
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Unusual number of permission denials"
    description: "Possible misconfigured roles or unauthorized access attempts"
```

---

### outlabs_auth_permission_check_duration_seconds

**Type:** Histogram
**Description:** Time taken for permission checks (in seconds)

**Labels:** None

**Buckets:** `[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]` (0.1ms to 100ms)

**Example Queries:**

```promql
# P95 permission check latency
histogram_quantile(0.95, rate(outlabs_auth_permission_check_duration_seconds_bucket[5m]))

# P99 permission check latency
histogram_quantile(0.99, rate(outlabs_auth_permission_check_duration_seconds_bucket[5m]))

# Average permission check duration
rate(outlabs_auth_permission_check_duration_seconds_sum[5m])
/
rate(outlabs_auth_permission_check_duration_seconds_count[5m])
```

**Recommended Alerts:**

```yaml
# Slow permission checks
- alert: SlowPermissionChecks
  expr: histogram_quantile(0.95, rate(outlabs_auth_permission_check_duration_seconds_bucket[5m])) > 0.1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "P95 permission check latency above 100ms"
    description: "Permission checks are slow (possible complex hierarchy or ABAC policies)"
```

---

### outlabs_auth_tree_permission_depth

**Type:** Histogram
**Description:** Depth of entity hierarchy traversed during tree permission checks

**Labels:** None

**Buckets:** `[1, 2, 3, 5, 10, 20, 50]`

**Example Queries:**

```promql
# Average hierarchy depth
rate(outlabs_auth_tree_permission_depth_sum[5m])
/
rate(outlabs_auth_tree_permission_depth_count[5m])

# P95 hierarchy depth
histogram_quantile(0.95, rate(outlabs_auth_tree_permission_depth_bucket[5m]))
```

---

## Session Metrics

### outlabs_auth_active_sessions

**Type:** Gauge
**Description:** Current number of active user sessions

**Labels:** None

**Example Queries:**

```promql
# Current active sessions
outlabs_auth_active_sessions

# Peak sessions in last 24 hours
max_over_time(outlabs_auth_active_sessions[24h])

# Average sessions in last hour
avg_over_time(outlabs_auth_active_sessions[1h])
```

**Recommended Alerts:**

```yaml
# Unusual session spike
- alert: UnusualSessionSpike
  expr: outlabs_auth_active_sessions > 10000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Unusual number of active sessions"
    description: "{{ $value }} active sessions (possible attack or viral growth)"
```

---

### outlabs_auth_session_duration_seconds

**Type:** Histogram
**Description:** Session duration from login to logout (in seconds)

**Labels:** None

**Buckets:** `[60, 300, 900, 1800, 3600, 7200, 14400, 28800]` (1min to 8hrs)

**Example Queries:**

```promql
# Median session duration
histogram_quantile(0.5, rate(outlabs_auth_session_duration_seconds_bucket[1h]))

# Average session duration
rate(outlabs_auth_session_duration_seconds_sum[1h])
/
rate(outlabs_auth_session_duration_seconds_count[1h])
```

---

## API Key Metrics

### outlabs_auth_api_key_validations_total

**Type:** Counter
**Description:** Total number of API key validation attempts

**Labels:**
- `status` - Validation result
  - `valid` - API key is valid
  - `invalid` - API key doesn't exist or is malformed
  - `expired` - API key has expired
  - `rate_limited` - API key hit rate limit
  - `disabled` - API key has been disabled

**Example Queries:**

```promql
# API key validation rate
rate(outlabs_auth_api_key_validations_total{status="valid"}[5m])

# Invalid API key rate (possible attacks)
rate(outlabs_auth_api_key_validations_total{status="invalid"}[5m])

# Success ratio
sum(rate(outlabs_auth_api_key_validations_total{status="valid"}[5m]))
/
sum(rate(outlabs_auth_api_key_validations_total[5m]))
```

**Recommended Alerts:**

```yaml
# High invalid API key rate
- alert: HighInvalidApiKeyRate
  expr: rate(outlabs_auth_api_key_validations_total{status="invalid"}[5m]) > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High rate of invalid API keys"
    description: "Possible API key scanning attack"
```

---

### outlabs_auth_api_key_usage_total

**Type:** Counter
**Description:** Total number of requests authenticated with API keys (by key prefix)

**Labels:**
- `prefix` - API key prefix (first 12 characters, e.g., `sk_live_abc1`)

**Example Queries:**

```promql
# API key usage rate
rate(outlabs_auth_api_key_usage_total[5m])

# Top API keys by usage
topk(10, sum by (prefix) (rate(outlabs_auth_api_key_usage_total[1h])))

# Usage by specific key
rate(outlabs_auth_api_key_usage_total{prefix="sk_live_abc1"}[5m])
```

---

### outlabs_auth_api_key_rate_limit_hits_total

**Type:** Counter
**Description:** Total number of API key rate limit hits

**Labels:**
- `prefix` - API key prefix

**Example Queries:**

```promql
# Rate limit hit rate
rate(outlabs_auth_api_key_rate_limit_hits_total[5m])

# Keys hitting rate limits
sum by (prefix) (rate(outlabs_auth_api_key_rate_limit_hits_total[1h]))
```

**Recommended Alerts:**

```yaml
# API key hitting rate limits frequently
- alert: ApiKeyRateLimitExceeded
  expr: rate(outlabs_auth_api_key_rate_limit_hits_total[5m]) > 1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "API key {{ $labels.prefix }} hitting rate limits"
    description: "Consider increasing limits or investigating usage patterns"
```

---

## Security Metrics

### outlabs_auth_suspicious_activity_total

**Type:** Counter
**Description:** Total number of suspicious activity detections

**Labels:**
- `type` - Type of suspicious activity
  - `brute_force` - Multiple failed login attempts
  - `session_hijack` - IP or user agent changed mid-session
  - `rate_limit_abuse` - Excessive requests
  - `invalid_token_flood` - Many invalid token attempts

**Example Queries:**

```promql
# Suspicious activity rate
rate(outlabs_auth_suspicious_activity_total[5m])

# Activity by type
sum by (type) (rate(outlabs_auth_suspicious_activity_total[1h]))
```

**Recommended Alerts:**

```yaml
# Brute force attack detected
- alert: BruteForceAttackDetected
  expr: rate(outlabs_auth_suspicious_activity_total{type="brute_force"}[5m]) > 5
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Brute force attack detected"
    description: "Multiple users experiencing failed login attempts"
```

---

## Error Metrics

### outlabs_auth_errors_total

**Type:** Counter
**Description:** Total errors by type and location

**Labels:**
- `error_type` - Exception class name (e.g., `DatabaseError`, `ValueError`)
- `location` - Where error occurred (e.g., `users_router`, `auth_service`)

**Example Queries:**

```promql
# Total error rate
sum(rate(outlabs_auth_errors_total[5m]))

# Errors by type
sum by (error_type) (rate(outlabs_auth_errors_total[5m]))

# Top 10 error types
topk(10, sum by (error_type) (increase(outlabs_auth_errors_total[1h])))

# Database errors
sum(rate(outlabs_auth_errors_total{error_type=~".*Database.*"}[5m]))

# Errors by location
sum by (location) (rate(outlabs_auth_errors_total[5m]))
```

**Recommended Alerts:**

```yaml
# High error rate
- alert: HighErrorRate
  expr: sum(rate(outlabs_auth_errors_total[5m])) > 1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High error rate detected"
    description: "{{ $value }} errors per second"

# Specific error type spike
- alert: DatabaseErrorSpike
  expr: sum(rate(outlabs_auth_errors_total{error_type=~".*Database.*"}[5m])) > 0.5
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Database errors increasing"
    description: "Database errors: {{ $value }}/sec"
```

---

### outlabs_auth_500_errors_total

**Type:** Counter
**Description:** Total HTTP 500 Internal Server Errors

**Labels:**
- `endpoint` - API endpoint (e.g., `/v1/users`, `/v1/auth/login`)
- `error_class` - Exception class (e.g., `DatabaseConnectionError`)

**Example Queries:**

```promql
# 500 error rate
sum(rate(outlabs_auth_500_errors_total[5m]))

# 500 errors by endpoint
sum by (endpoint) (rate(outlabs_auth_500_errors_total[5m]))

# Top endpoints with 500s
topk(5, sum by (endpoint) (increase(outlabs_auth_500_errors_total[1h])))

# 500 errors by error type
sum by (error_class) (rate(outlabs_auth_500_errors_total[5m]))

# Specific endpoint error rate
rate(outlabs_auth_500_errors_total{endpoint="/v1/users"}[5m])
```

**Recommended Alerts:**

```yaml
# Any 500 errors
- alert: InternalServerErrors
  expr: sum(rate(outlabs_auth_500_errors_total[5m])) > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "500 errors detected"
    description: "{{ $value }} 500 errors per second"

# Specific endpoint failing
- alert: EndpointFailing
  expr: rate(outlabs_auth_500_errors_total{endpoint="/v1/auth/login"}[5m]) > 0.1
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Login endpoint failing"
    description: "Login returning 500s: {{ $value }}/sec"
```

---

### outlabs_auth_router_errors_total

**Type:** Counter
**Description:** Total router-level errors

**Labels:**
- `router` - Router name (e.g., `users`, `roles`, `auth`)
- `endpoint` - Full endpoint path

**Example Queries:**

```promql
# Errors by router
sum by (router) (rate(outlabs_auth_router_errors_total[5m]))

# Most error-prone router
topk(1, sum by (router) (increase(outlabs_auth_router_errors_total[1h])))

# Users router error rate
sum(rate(outlabs_auth_router_errors_total{router="users"}[5m]))

# Error rate heatmap (by router and endpoint)
sum by (router, endpoint) (rate(outlabs_auth_router_errors_total[5m]))
```

**Recommended Alerts:**

```yaml
# Router error spike
- alert: RouterErrorSpike
  expr: sum by (router) (rate(outlabs_auth_router_errors_total[5m])) > 0.5
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "{{ $labels.router }} router errors spiking"
    description: "{{ $value }} errors/sec in {{ $labels.router }} router"
```

---

### outlabs_auth_service_errors_total

**Type:** Counter
**Description:** Total service-level errors

**Labels:**
- `service` - Service name (e.g., `auth`, `user`, `role`, `permission`)
- `operation` - Operation being performed (e.g., `login`, `create_user`)

**Example Queries:**

```promql
# Errors by service
sum by (service) (rate(outlabs_auth_service_errors_total[5m]))

# Errors by operation
sum by (operation) (rate(outlabs_auth_service_errors_total[5m]))

# Auth service errors
sum(rate(outlabs_auth_service_errors_total{service="auth"}[5m]))

# Login operation errors
sum(rate(outlabs_auth_service_errors_total{operation="login"}[5m]))

# Most error-prone operations
topk(10, sum by (operation) (increase(outlabs_auth_service_errors_total[1h])))
```

**Recommended Alerts:**

```yaml
# Service error spike
- alert: ServiceErrorSpike
  expr: sum by (service) (rate(outlabs_auth_service_errors_total[5m])) > 0.5
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "{{ $labels.service }} service errors spiking"
    description: "{{ $value }} errors/sec in {{ $labels.service }} service"

# Login failures
- alert: LoginServiceFailing
  expr: sum(rate(outlabs_auth_service_errors_total{operation="login"}[5m])) > 0.1
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Login service experiencing errors"
    description: "{{ $value }} login errors per second"
```

---

## Performance Metrics

### outlabs_auth_cache_hits_total

**Type:** Counter
**Description:** Total number of cache hits (Redis)

**Labels:**
- `cache_type` - Type of cache
  - `permission` - Permission check results
  - `role` - Role lookups
  - `user` - User data
  - `entity` - Entity data

**Example Queries:**

```promql
# Cache hit rate
sum(rate(outlabs_auth_cache_hits_total[5m]))
/
(sum(rate(outlabs_auth_cache_hits_total[5m])) + sum(rate(outlabs_auth_cache_misses_total[5m])))

# Hits by cache type
sum by (cache_type) (rate(outlabs_auth_cache_hits_total[5m]))
```

---

### outlabs_auth_cache_misses_total

**Type:** Counter
**Description:** Total number of cache misses (Redis)

**Labels:**
- `cache_type` - Type of cache (permission, role, user, entity)

**Example Queries:**

```promql
# Cache miss rate
rate(outlabs_auth_cache_misses_total[5m])

# Cache efficiency (should be >90%)
sum(rate(outlabs_auth_cache_hits_total[5m]))
/
(sum(rate(outlabs_auth_cache_hits_total[5m])) + sum(rate(outlabs_auth_cache_misses_total[5m])))
```

**Recommended Alerts:**

```yaml
# Low cache hit rate
- alert: LowCacheHitRate
  expr: |
    sum(rate(outlabs_auth_cache_hits_total[5m]))
    /
    (sum(rate(outlabs_auth_cache_hits_total[5m])) + sum(rate(outlabs_auth_cache_misses_total[5m]))) < 0.7
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Cache hit rate below 70%"
    description: "Cache may need tuning or TTL adjustment"
```

---

### outlabs_auth_db_query_duration_seconds

**Type:** Histogram
**Description:** MongoDB query duration (in seconds)

**Labels:**
- `operation` - Type of operation (find, insert, update, delete)
- `collection` - MongoDB collection (users, roles, permissions, etc.)

**Buckets:** `[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]`

**Example Queries:**

```promql
# P95 database query latency
histogram_quantile(0.95, rate(outlabs_auth_db_query_duration_seconds_bucket[5m]))

# Slow queries by collection
histogram_quantile(0.95, sum by (collection, le) (rate(outlabs_auth_db_query_duration_seconds_bucket[5m])))
```

**Recommended Alerts:**

```yaml
# Slow database queries
- alert: SlowDatabaseQueries
  expr: histogram_quantile(0.95, rate(outlabs_auth_db_query_duration_seconds_bucket[5m])) > 0.1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "P95 database query latency above 100ms"
    description: "Database queries are slow (check indexes)"
```

---

## Example Grafana Dashboard Queries

### Authentication Dashboard

```promql
# Login Success Rate (last 24h)
sum(increase(outlabs_auth_login_attempts_total{status="success"}[24h]))

# Failed Logins (last 24h)
sum(increase(outlabs_auth_login_attempts_total{status="failed"}[24h]))

# P95 Login Latency (5m)
histogram_quantile(0.95, rate(outlabs_auth_login_duration_seconds_bucket[5m]))

# Active Sessions
outlabs_auth_active_sessions
```

### Authorization Dashboard

```promql
# Permission Checks/sec
rate(outlabs_auth_permission_checks_total[5m])

# Permission Denial Rate
rate(outlabs_auth_permission_checks_total{result="denied"}[5m])

# P95 Permission Check Latency
histogram_quantile(0.95, rate(outlabs_auth_permission_check_duration_seconds_bucket[5m]))

# Top Denied Permissions
topk(10, sum by (permission) (increase(outlabs_auth_permission_checks_total{result="denied"}[1h])))
```

### Security Dashboard

```promql
# Failed Login Attempts (last hour)
sum(increase(outlabs_auth_login_attempts_total{status="failed"}[1h]))

# Account Lockouts (last hour)
increase(outlabs_auth_account_locked_total[1h])

# Suspicious Activity (last 24h)
sum by (type) (increase(outlabs_auth_suspicious_activity_total[24h]))

# Invalid API Keys (last hour)
sum(increase(outlabs_auth_api_key_validations_total{status="invalid"}[1h]))
```

---

## Next Steps

- **[97-Observability.md](97-Observability.md)** - Main observability guide
- **[99-Log-Events-Reference.md](99-Log-Events-Reference.md)** - Complete log events catalog
- **[Grafana Dashboard](../grafana-dashboards/README.md)** - Pre-built dashboard using these metrics

---

**Last Updated:** 2025-01-24
**Related:** [97-Observability.md](97-Observability.md), [99-Log-Events-Reference.md](99-Log-Events-Reference.md)
