# Grafana Dashboards for OutlabsAuth

## Overview

Pre-configured Grafana dashboards for monitoring OutlabsAuth authentication and authorization systems.

## Available Dashboards

### 1. OutlabsAuth Overview (`outlabs-auth-overview.json`)

Comprehensive monitoring dashboard with metrics across authentication, authorization, performance, and errors.

**Sections:**

#### Authentication Metrics
- Login Success Rate
- Login Failure Rate  
- Active Sessions
- Permission Check Rate

#### Error Tracking (NEW - 2025-01-26)
- **500 Error Rate** - HTTP 500 errors per second
- **Error Types** - Breakdown by exception class
- **Errors by Endpoint** - Which endpoints are failing
- **Error Rate Heatmap** - Visual representation of error hotspots

#### Authorization Metrics
- Permission Checks (Granted vs Denied)
- Role Assignments
- API Key Validations

#### Performance Metrics
- Login Latency (P50, P95, P99)
- Permission Check Latency
- Cache Hit Rate
- Database Query Duration

#### Logs Integration (NEW - with Loki)
- Recent 500 Errors with full logs
- Error logs with stack traces
- Searchable by correlation_id

## Accessing Dashboards

### Quick Start

```bash
# Start the complete observability stack
docker compose up -d

# Wait for services to be ready (~30 seconds)
docker compose logs -f grafana

# Access Grafana
open http://localhost:3011
```

**Login Credentials:**
- Username: `admin`
- Password: `admin`

### Dashboard Location

Once logged in:
1. Go to **Dashboards** (left sidebar)
2. Select **OutlabsAuth Overview**

Or direct link:
```
http://localhost:3011/d/outlabs-auth-overview
```

## Data Sources

The dashboard queries three datasources (auto-configured):

### 1. Prometheus (Metrics)
- **URL:** http://prometheus:9090
- **Usage:** Time-series metrics (counters, histograms, gauges)
- **Examples:** Login rates, error counts, latencies

### 2. Loki (Logs)
- **URL:** http://loki:3100
- **Usage:** Structured log aggregation
- **Examples:** Error messages, stack traces, audit logs

### 3. Tempo (Traces)
- **URL:** http://tempo:3200
- **Usage:** Distributed tracing
- **Examples:** Request flows, span durations

## Key Panels

### Error Monitoring Panels (NEW)

#### 500 Error Rate
**Query:**
```promql
sum(rate(outlabs_auth_500_errors_total[5m])) * 60
```
Shows HTTP 500 errors per minute. Should be zero in healthy system.

#### Top Error Types
**Query:**
```promql
topk(10, sum by (error_type) (increase(outlabs_auth_errors_total[1h])))
```
Shows which exception types are most common.

#### Errors by Endpoint
**Query:**
```promql
sum by (endpoint) (rate(outlabs_auth_500_errors_total[5m]))
```
Identifies which API endpoints are failing.

#### Recent 500 Errors (Logs)
**Query (LogQL):**
```logql
{service="simple-rbac"} |= "http_500_internal_server_error" | json
```
Shows recent 500 errors with full log context.

### Authentication Panels

#### Login Success Rate
**Query:**
```promql
rate(outlabs_auth_login_attempts_total{status="success"}[5m]) * 60
```

#### Login Latency (P95)
**Query:**
```promql
histogram_quantile(0.95, rate(outlabs_auth_login_duration_seconds_bucket[5m]))
```

### Authorization Panels

#### Permission Checks
**Query:**
```promql
sum by (result) (rate(outlabs_auth_permission_checks_total[5m]))
```

#### Permission Denial Rate
**Query:**
```promql
sum(rate(outlabs_auth_permission_checks_total{result="denied"}[5m]))
```

## Alerts

### Pre-configured Alerts

The dashboard includes visual alerts (thresholds):

1. **Login Failure Rate > 5/min** → Red
2. **500 Error Rate > 0** → Red (critical)
3. **Permission Denial Rate > 10/sec** → Yellow (warning)

### Setting Up Prometheus Alertmanager

For production, configure Prometheus Alertmanager:

```yaml
# prometheus/alerts.yml
groups:
  - name: outlabs_auth
    interval: 30s
    rules:
      - alert: InternalServerErrors
        expr: sum(rate(outlabs_auth_500_errors_total[5m])) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "500 errors detected in OutlabsAuth"
          description: "{{ $value }} errors per second"

      - alert: HighErrorRate
        expr: sum(rate(outlabs_auth_errors_total[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in OutlabsAuth"
          description: "{{ $value }} errors per second"
```

## Viewing Logs in Grafana

### Method 1: Explore View

1. Go to **Explore** (compass icon in left sidebar)
2. Select **Loki** datasource
3. Use LogQL queries:

```logql
# All 500 errors
{service="simple-rbac"} |= "http_500_internal_server_error" | json

# Errors by user
{service="simple-rbac"} |= "error" | json | user_id="507f..."

# Errors by endpoint
{service="simple-rbac"} |= "error" | json | endpoint="/v1/users"

# Errors with stack traces
{service="simple-rbac"} |= "stack_trace" | json
```

### Method 2: Dashboard Logs Panel

The dashboard includes a "Recent Errors" logs panel that shows:
- Timestamp
- Error type
- Error message
- Endpoint
- User ID (if available)
- Stack trace (click to expand)

## Correlating Metrics, Logs, and Traces

### Workflow: Investigating a 500 Error

1. **Dashboard Alert** → 500 Error Rate panel shows spike
2. **Click panel** → Drill down to see which endpoint
3. **View Logs** → Click "Explore" to see actual error messages
4. **Check Traces** (if enabled) → See full request flow
5. **Find correlation_id** → Track request across all systems

### Example: Finding Related Data

**In Prometheus (Metrics):**
```promql
outlabs_auth_500_errors_total{endpoint="/v1/users"}
```

**In Loki (Logs):**
```logql
{service="simple-rbac"} |= "http_500_internal_server_error" 
  | json 
  | endpoint="/v1/users"
```

**In Tempo (Traces):**
Search by `correlation_id` from logs

## Customizing Dashboards

### Adding a New Panel

1. Click **Add panel** (top right)
2. Choose visualization type (Graph, Stat, Table, etc.)
3. Add query (PromQL for metrics, LogQL for logs)
4. Configure display options
5. Click **Apply**

### Example: Add "Database Errors" Panel

**Panel Type:** Stat  
**Query:**
```promql
sum(rate(outlabs_auth_errors_total{error_type=~".*Database.*"}[5m]))
```
**Threshold:** > 0.1 = Red

### Exporting Dashboards

```bash
# From Grafana UI
Dashboard → Share → Export → Save to file

# Or use the JSON directly
cp docker/grafana/dashboards/outlabs-auth-overview.json my-custom-dashboard.json
```

## Troubleshooting

### Dashboard shows "No Data"

**Check Prometheus:**
```bash
# Verify Prometheus is scraping metrics
open http://localhost:9090/targets

# Should show:
# simple-rbac (up)
```

**Check metrics endpoint:**
```bash
curl http://localhost:8003/metrics
```

### Logs not appearing in Loki

**Check Promtail:**
```bash
docker compose logs promtail

# Should show: "Clients configured"
```

**Check Loki:**
```bash
curl http://localhost:3100/ready
```

### Grafana shows "Unable to connect to datasource"

**Restart Grafana:**
```bash
docker compose restart grafana
```

**Check datasource health in Grafana:**
Settings → Data sources → Click datasource → Save & test

## Performance Considerations

### Dashboard Refresh Rate

Default: **10 seconds**

For production with many panels:
- Change to 30s or 1m
- Edit dashboard → Settings → Refresh rate

### Query Performance

If queries are slow:
- Reduce time range (e.g., last 6 hours instead of 24 hours)
- Use recording rules in Prometheus for complex queries
- Enable query caching in Grafana

## Next Steps

1. **View the dashboard** → http://localhost:3011
2. **Generate some traffic** → Use the API or admin UI
3. **Trigger a 500 error** → See error panels populate
4. **Explore logs** → Use Loki to search error logs
5. **Set up alerts** → Configure Alertmanager for production

## Additional Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [LogQL Documentation](https://grafana.com/docs/loki/latest/logql/)
- [Tempo Tracing](https://grafana.com/docs/tempo/latest/)

---

**Last Updated:** 2025-01-26  
**Dashboard Version:** 2.0 (with error tracking)
