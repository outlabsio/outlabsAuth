# OutlabsAuth Grafana Dashboards

Pre-built Grafana dashboards for monitoring OutlabsAuth authentication and authorization.

## Available Dashboards

### 1. OutlabsAuth Overview (`outlabs-auth-overview.json`)

Complete auth monitoring dashboard with:
- **Authentication Metrics** - Login success/failure rates, latency
- **Authorization Metrics** - Permission checks, denials, latency
- **Session Metrics** - Active sessions, session duration
- **API Key Metrics** - Usage, validations, rate limits
- **Security Metrics** - Failed logins, suspicious activity, account lockouts
- **Performance Metrics** - Cache hit rate, DB query latency

---

## Quick Setup

### Step 1: Start Prometheus

Configure Prometheus to scrape your OutlabsAuth app:

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'outlabs-auth'
    static_configs:
      - targets: ['localhost:8000']  # Your FastAPI app with /metrics endpoint
```

```bash
docker run -d -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### Step 2: Start Grafana

```bash
docker run -d -p 3000:3000 grafana/grafana
```

### Step 3: Add Prometheus Data Source

1. Open Grafana: http://localhost:3000 (default: admin/admin)
2. Go to **Configuration** → **Data Sources**
3. Click **Add data source**
4. Select **Prometheus**
5. Set URL to `http://prometheus:9090` (or `http://localhost:9090` if running natively)
6. Click **Save & Test**

### Step 4: Import Dashboard

1. Go to **Dashboards** → **Import**
2. Click **Upload JSON file**
3. Select `outlabs-auth-overview.json`
4. Select your Prometheus data source
5. Click **Import**

Done! Your dashboard is ready.

---

## Dashboard Panels

### Authentication Overview

**Panel: Login Success Rate**
- Metric: `rate(outlabs_auth_login_attempts_total{status="success"}[5m])`
- Shows: Successful logins per second
- Alert: Should stay consistent; drops indicate issues

**Panel: Login Failure Rate**
- Metric: `rate(outlabs_auth_login_attempts_total{status="failed"}[5m])`
- Shows: Failed logins per second
- Alert: Spikes indicate attacks or password issues

**Panel: Login Success Ratio**
- Metric: `sum(rate(outlabs_auth_login_attempts_total{status="success"}[5m])) / sum(rate(outlabs_auth_login_attempts_total[5m]))`
- Shows: Percentage of successful logins
- Target: >95%

**Panel: P95 Login Latency**
- Metric: `histogram_quantile(0.95, rate(outlabs_auth_login_duration_seconds_bucket[5m]))`
- Shows: 95th percentile login time
- Target: <500ms

**Panel: Active Sessions**
- Metric: `outlabs_auth_active_sessions`
- Shows: Current number of active users
- Track: Daily patterns, growth trends

### Authorization Overview

**Panel: Permission Checks/sec**
- Metric: `rate(outlabs_auth_permission_checks_total[5m])`
- Shows: Permission checks per second
- Monitor: Load patterns

**Panel: Permission Denials**
- Metric: `rate(outlabs_auth_permission_checks_total{result="denied"}[5m])`
- Shows: Denied permissions per second
- Alert: Spikes may indicate misconfigured roles

**Panel: P95 Permission Check Latency**
- Metric: `histogram_quantile(0.95, rate(outlabs_auth_permission_check_duration_seconds_bucket[5m]))`
- Shows: Permission check latency
- Target: <10ms (simple RBAC), <100ms (enterprise with ABAC)

**Panel: Top Denied Permissions**
- Metric: `topk(10, sum by (permission) (rate(outlabs_auth_permission_checks_total{result="denied"}[1h])))`
- Shows: Most frequently denied permissions
- Use: Identify role misconfigurations

### Security Overview

**Panel: Failed Login Attempts (Last Hour)**
- Metric: `sum(increase(outlabs_auth_login_attempts_total{status="failed"}[1h]))`
- Shows: Total failed logins in last hour
- Alert: >100 may indicate attack

**Panel: Account Lockouts**
- Metric: `increase(outlabs_auth_account_locked_total[1h])`
- Shows: Accounts locked in last hour
- Alert: >10 is unusual

**Panel: Suspicious Activity**
- Metric: `sum by (type) (increase(outlabs_auth_suspicious_activity_total[24h]))`
- Shows: Suspicious activity by type
- Alert: Any non-zero value needs investigation

**Panel: Invalid API Keys**
- Metric: `sum(increase(outlabs_auth_api_key_validations_total{status="invalid"}[1h]))`
- Shows: Invalid API key attempts
- Alert: >50 may indicate scanning attack

### Performance Overview

**Panel: Cache Hit Rate**
- Metric: `sum(rate(outlabs_auth_cache_hits_total[5m])) / (sum(rate(outlabs_auth_cache_hits_total[5m])) + sum(rate(outlabs_auth_cache_misses_total[5m])))`
- Shows: Percentage of cache hits
- Target: >90%

**Panel: P95 DB Query Latency**
- Metric: `histogram_quantile(0.95, rate(outlabs_auth_db_query_duration_seconds_bucket[5m]))`
- Shows: Database query latency
- Target: <50ms
- Alert: >100ms indicates indexing issues

**Panel: API Key Usage (Top 10)**
- Metric: `topk(10, sum by (prefix) (rate(outlabs_auth_api_key_usage_total[1h])))`
- Shows: Most used API keys
- Use: Identify high-traffic integrations

---

## Recommended Alert Rules

Create alert rules in Prometheus for critical conditions:

```yaml
# prometheus-alerts.yml
groups:
  - name: outlabs_auth_alerts
    interval: 1m
    rules:
      # Authentication Alerts
      - alert: HighLoginFailureRate
        expr: rate(outlabs_auth_login_attempts_total{status="failed"}[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High login failure rate detected"
          description: "{{ $value }} failed logins per second"

      - alert: SlowLoginLatency
        expr: histogram_quantile(0.95, rate(outlabs_auth_login_duration_seconds_bucket[5m])) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 login latency above 500ms"

      - alert: LoginSuccessRateDrop
        expr: sum(rate(outlabs_auth_login_attempts_total{status="success"}[5m])) / sum(rate(outlabs_auth_login_attempts_total[5m])) < 0.8
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Login success rate below 80%"

      # Security Alerts
      - alert: BruteForceAttackDetected
        expr: rate(outlabs_auth_account_locked_total[5m]) > 2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Possible brute force attack"

      - alert: SuspiciousActivityDetected
        expr: rate(outlabs_auth_suspicious_activity_total[5m]) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Suspicious activity detected"

      # Performance Alerts
      - alert: SlowPermissionChecks
        expr: histogram_quantile(0.95, rate(outlabs_auth_permission_check_duration_seconds_bucket[5m])) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 permission check latency above 100ms"

      - alert: LowCacheHitRate
        expr: sum(rate(outlabs_auth_cache_hits_total[5m])) / (sum(rate(outlabs_auth_cache_hits_total[5m])) + sum(rate(outlabs_auth_cache_misses_total[5m]))) < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate below 70%"

      - alert: SlowDatabaseQueries
        expr: histogram_quantile(0.95, rate(outlabs_auth_db_query_duration_seconds_bucket[5m])) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 database query latency above 100ms"
```

---

## Customization

### Add Custom Panels

1. Click **Add Panel** in Grafana
2. Select visualization type (Graph, Gauge, Table, etc.)
3. Enter PromQL query
4. Configure display options
5. Save dashboard

### Common Customizations

**Filter by environment:**
```promql
outlabs_auth_login_attempts_total{environment="production"}
```

**Filter by application:**
```promql
outlabs_auth_login_attempts_total{app="my-api"}
```

**Aggregate across instances:**
```promql
sum(rate(outlabs_auth_login_attempts_total[5m]))
```

---

## Troubleshooting

**Problem: Dashboard shows "No data"**

Check:
1. Prometheus is scraping your app (`/metrics` endpoint accessible)
2. Data source is configured correctly in Grafana
3. Time range is appropriate (try "Last 5 minutes")

**Problem: Metrics missing**

Check:
1. `ObservabilityConfig(enable_metrics=True)` in your app
2. `/metrics` endpoint added to FastAPI app
3. Prometheus scrape job includes correct target

**Problem: Incorrect values**

Check:
1. Time range and step interval
2. PromQL query syntax
3. Label selectors match your setup

---

## Next Steps

- **[97-Observability.md](../docs-library/97-Observability.md)** - Main observability guide
- **[98-Metrics-Reference.md](../docs-library/98-Metrics-Reference.md)** - Complete metrics catalog
- **[Observability Example](../examples/observability/)** - Full Docker Compose stack

---

**Last Updated:** 2025-01-24
