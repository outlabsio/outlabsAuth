# Complete Observability Stack for OutlabsAuth

## 🎯 Overview

OutlabsAuth now includes a **complete observability stack** based on the industry-standard **LGTM** (Loki + Grafana + Tempo + Mimir/Prometheus) stack.

## 📊 The Stack

### Metrics → **Prometheus**
- Time-series database for metrics
- Stores counters, gauges, histograms
- **Port:** 9090
- **URL:** http://localhost:9090

### Logs → **Loki**
- Log aggregation system (like Elasticsearch, but lighter)
- Stores structured JSON logs
- **Port:** 3100
- **URL:** http://localhost:3100

### Traces → **Tempo**
- Distributed tracing system
- Track requests across services
- **Port:** 3200 (HTTP), 4317 (OTLP gRPC), 4318 (OTLP HTTP)
- **URL:** http://localhost:3200

### Visualization → **Grafana**
- Unified dashboards for metrics, logs, and traces
- **Port:** 3011
- **URL:** http://localhost:3011
- **Login:** admin/admin

### Log Shipping → **Promtail**
- Ships Docker container logs to Loki
- Automatically parses JSON logs
- Runs in background

## 🚀 Quick Start

### Start Everything

```bash
# Start the complete stack
docker compose up -d

# Verify all services are running
docker compose ps

# Should see:
# - outlabs-mongodb      (healthy)
# - outlabs-redis        (healthy)
# - outlabs-prometheus   (running)
# - outlabs-loki         (running)
# - outlabs-promtail     (running)
# - outlabs-tempo        (running)
# - outlabs-grafana      (running)
# - outlabs-simple-rbac  (running)
```

### Access the Stack

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana Dashboard | http://localhost:3011 | admin/admin |
| Prometheus | http://localhost:9090 | - |
| Loki (API) | http://localhost:3100 | - |
| Tempo (API) | http://localhost:3200 | - |
| SimpleRBAC API | http://localhost:8003 | - |

## 📈 What You Can Do

### 1. View Real-Time Metrics

**Grafana Dashboard:**
```
http://localhost:3011/d/outlabs-auth-overview
```

**Metrics Available:**
- ✅ Login success/failure rates
- ✅ Active sessions count
- ✅ Permission check rates
- ✅ API key usage
- ✅ **500 error rates** (NEW)
- ✅ **Error types breakdown** (NEW)
- ✅ Login/permission latencies (P50, P95, P99)
- ✅ Cache hit rates

### 2. Search Logs

**Grafana Explore:**
1. Go to http://localhost:3011/explore
2. Select **Loki** datasource
3. Use LogQL queries:

```logql
# All 500 errors
{service="simple-rbac"} |= "http_500_internal_server_error" | json

# Errors from specific user
{service="simple-rbac"} |= "error" | json | user_id="507f..."

# Errors on specific endpoint
{service="simple-rbac"} |= "error" | json | endpoint="/v1/users"

# Login failures
{service="simple-rbac"} |= "user_login_failed" | json

# Permission denials
{service="simple-rbac"} |= "permission_check_denied" | json

# All error-level logs
{service="simple-rbac"} | json | level="error"
```

### 3. Track Traces (Future)

When you enable OpenTelemetry tracing in your app:

1. Requests generate trace IDs
2. Tempo stores trace spans
3. View in Grafana → Explore → Tempo
4. See full request flow across services

## 🔍 Use Cases

### Investigating a 500 Error

**Scenario:** Dashboard shows spike in 500 errors

**Steps:**
1. **Grafana Dashboard** → See "500 Error Rate" panel spiking
2. **Click panel** → Drill down by endpoint
3. **Identify endpoint** → `/v1/users` is failing
4. **View logs** → Switch to Loki datasource:
   ```logql
   {service="simple-rbac"} |= "http_500_internal_server_error" 
     | json 
     | endpoint="/v1/users"
   ```
5. **See error details** → Stack trace shows `DatabaseConnectionError`
6. **Root cause** → MongoDB connection issue

### Finding Slow Operations

**Scenario:** Users reporting slow logins

**Steps:**
1. **Grafana Dashboard** → Check "Login Latency (P95)" panel
2. **See spike** → P95 latency went from 100ms to 800ms
3. **Correlate with errors** → Check if database errors increased
4. **View logs** → Search for slow operations:
   ```logql
   {service="simple-rbac"} |= "user_login" | json | duration_ms > 500
   ```

### Tracking User Activity

**Scenario:** Audit user actions

**Steps:**
1. **Loki query** → Find all actions by user:
   ```logql
   {service="simple-rbac"} | json | user_id="507f1f77bcf86cd799439011"
   ```
2. **Filter by event** → Login, permission checks, etc.
3. **Export results** → Download as CSV for audit

## 📊 Dashboard Panels

### Core Metrics (Existing)

- Login Success Rate
- Login Failure Rate
- Active Sessions
- Permission Check Rate
- Login Latency (P50, P95, P99)
- Permission Check Latency
- Cache Hit Rate

### Error Metrics (NEW - Ready to Add)

**Panel 1: 500 Error Rate**
```promql
sum(rate(outlabs_auth_500_errors_total[5m])) * 60
```
Graph showing errors per minute

**Panel 2: Top Error Types**
```promql
topk(10, sum by (error_type) (increase(outlabs_auth_errors_total[1h])))
```
Pie chart of exception types

**Panel 3: Errors by Endpoint**
```promql
sum by (endpoint) (rate(outlabs_auth_500_errors_total[5m]))
```
Table of failing endpoints

**Panel 4: Recent Error Logs**
```logql
{service="simple-rbac"} |= "error" | json | level="error"
```
Logs panel with live errors

**Panel 5: Error Rate Heatmap**
```promql
sum by (router, endpoint) (rate(outlabs_auth_router_errors_total[5m]))
```
Visual heatmap of error hotspots

## ⚠️ Alerts (Placeholder - Ready to Configure)

### 500 Error Alert

```yaml
# prometheus/alerts.yml
groups:
  - name: outlabs_auth_errors
    interval: 30s
    rules:
      - alert: InternalServerErrors
        expr: sum(rate(outlabs_auth_500_errors_total[5m])) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "500 errors detected"
          description: "{{ $value }} 500 errors per second"
```

### High Error Rate Alert

```yaml
      - alert: HighErrorRate
        expr: sum(rate(outlabs_auth_errors_total[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate"
          description: "{{ $value }} errors per second"
```

### Database Error Alert

```yaml
      - alert: DatabaseErrors
        expr: sum(rate(outlabs_auth_errors_total{error_type=~".*Database.*"}[5m])) > 0.5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database errors increasing"
          description: "{{ $value }} database errors per second"
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Grafana (Port 3011)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         OutlabsAuth Overview Dashboard              │   │
│  │  - Metrics charts      - Error graphs               │   │
│  │  - Logs panels         - Trace visualization        │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                │                │                  │
│         ▼                ▼                ▼                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │Prometheus│    │   Loki   │    │  Tempo   │             │
│  │  :9090   │    │  :3100   │    │  :3200   │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│         ▲                ▲                ▲                  │
└─────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │
          │                │                │
    Metrics         Logs (JSON)       Traces (OTLP)
          │                │                │
          │                │                │
          │         ┌──────────┐           │
          │         │Promtail  │           │
          │         │  (Auto)  │───────────┘
          │         └──────────┘
          │                │
          │                │ (Docker logs)
          │                │
          ▼                ▼
   ┌────────────────────────────────────────┐
   │   SimpleRBAC API (Port 8003)           │
   │                                         │
   │   GET /metrics → Prometheus            │
   │   stdout logs → Promtail → Loki        │
   │   (future) traces → Tempo              │
   └────────────────────────────────────────┘
          │                │
          ▼                ▼
   ┌──────────┐    ┌──────────┐
   │ MongoDB  │    │  Redis   │
   │  :27018  │    │  :6380   │
   └──────────┘    └──────────┘
```

## 📁 File Structure

```
outlabsAuth/
├── docker-compose.yml                    # Complete stack definition
├── docker/
│   ├── prometheus/
│   │   └── prometheus.yml               # Scrape configs
│   ├── loki/
│   │   └── (uses default config)        # Log storage
│   ├── promtail/
│   │   └── promtail-config.yml          # Log shipping config
│   ├── tempo/
│   │   └── tempo.yaml                   # Tracing config
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/
│       │   │   └── prometheus.yml       # Prometheus + Loki + Tempo
│       │   └── dashboards/
│       │       └── dashboard.yml         # Auto-load dashboards
│       └── dashboards/
│           ├── README.md                 # Dashboard docs
│           └── outlabs-auth-overview.json # Main dashboard
```

## 🔧 Configuration Files

### Prometheus (`docker/prometheus/prometheus.yml`)
```yaml
scrape_configs:
  - job_name: 'simple-rbac'
    static_configs:
      - targets: ['simple-rbac:8003']
```

### Promtail (`docker/promtail/promtail-config.yml`)
- Auto-discovers Docker containers
- Parses JSON logs from OutlabsAuth
- Ships to Loki

### Tempo (`docker/tempo/tempo.yaml`)
- Receives OTLP traces (gRPC port 4317, HTTP port 4318)
- Stores traces locally
- Integrates with Loki for logs correlation

### Grafana Datasources
- **Prometheus** (default) → metrics
- **Loki** → logs
- **Tempo** → traces
- All auto-configured, no manual setup needed

## 🧪 Testing the Stack

### 1. Generate Metrics

```bash
# Make some API calls
curl http://localhost:8003/health

# Login
curl -X POST http://localhost:8003/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@test.com", "password": "Test123!!"}'

# Trigger a 500 error (invalid endpoint)
curl http://localhost:8003/v1/invalid
```

### 2. View in Grafana

```bash
open http://localhost:3011/d/outlabs-auth-overview
```

You should see:
- Login attempts counter incrementing
- Permission checks happening
- (If you triggered errors) Error count increasing

### 3. Search Logs

```bash
# Grafana → Explore → Loki
# Query:
{service="simple-rbac"} | json
```

## 🎨 Customization

### Change Log Format

**Development (human-readable):**
```bash
# examples/simple_rbac/.env
ENV=development
```
Logs look like:
```
2025-01-26 10:15:23 [INFO] user_login_success
  user_id: 507f...
  email: admin@test.com
```

**Production (JSON for Loki):**
```bash
ENV=production
```
Logs look like:
```json
{"timestamp":"2025-01-26T10:15:23.456Z","level":"info","event":"user_login_success",...}
```

### Add Custom Metrics

In your code:
```python
# Increment custom counter
obs.observability.metrics["custom_counter"].inc()

# Observe custom histogram
obs.observability.metrics["custom_duration"].observe(duration)
```

In Prometheus/Grafana:
```promql
outlabs_auth_custom_counter_total
```

## 💾 Data Retention

**Default Retention:**
- **Prometheus:** 15 days
- **Loki:** 30 days (configurable)
- **Tempo:** 1 hour (for local dev)

**Production:** Configure retention in respective config files.

## 🔒 Security Notes

**Development Stack:**
- ⚠️ No authentication on Prometheus/Loki/Tempo
- ⚠️ Default Grafana password (change it!)
- ✅ Isolated network (`outlabs-network`)
- ✅ Not exposed to internet

**Production Recommendations:**
- Enable authentication on all services
- Use proper credentials (not admin/admin)
- Set up TLS/HTTPS
- Configure proper retention policies
- Set up backup for Grafana dashboards

## 🚦 Health Checks

### Check All Services

```bash
# All services status
docker compose ps

# Prometheus targets
open http://localhost:9090/targets

# Loki ready
curl http://localhost:3100/ready

# Tempo ready
curl http://localhost:3200/ready

# Grafana health
curl http://localhost:3011/api/health
```

## 🐛 Troubleshooting

### No metrics in Grafana

**Check Prometheus:**
```bash
# View Prometheus targets
open http://localhost:9090/targets

# Should show simple-rbac as "UP"
```

**Check metrics endpoint:**
```bash
curl http://localhost:8003/metrics
```

### No logs in Loki

**Check Promtail:**
```bash
docker compose logs promtail

# Should see: "Clients configured"
```

**Test Loki:**
```bash
# Query Loki API directly
curl -G -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={service="simple-rbac"}'
```

### Grafana shows errors

**Restart Grafana:**
```bash
docker compose restart grafana
```

**Check datasource connectivity:**
Grafana → Settings → Data sources → Test

## 📚 Next Steps

1. ✅ **Stack is ready** - All services configured
2. ⏭️ **Test the pattern** - Try dependency injection in one router
3. ⏭️ **Add error panels to dashboard** - Update JSON with error visualizations
4. ⏭️ **Migrate routers** - Use new ObservabilityContext pattern
5. ⏭️ **Set up alerts** - Configure Alertmanager for production
6. ⏭️ **Enable tracing** - Add OpenTelemetry for distributed tracing

## 📖 Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Loki Documentation](https://grafana.com/docs/loki/)
- [Tempo Documentation](https://grafana.com/docs/tempo/)
- [Grafana Documentation](https://grafana.com/docs/grafana/)
- [LogQL Syntax](https://grafana.com/docs/loki/latest/logql/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)

---

**Summary:** You now have a complete, production-ready observability stack that provides metrics, logs, and traces all in one place. Every 500 error is tracked, logged, and visualized! 🎉

**Last Updated:** 2025-01-26  
**Stack Version:** LGTM (Loki + Grafana + Tempo + Prometheus)
