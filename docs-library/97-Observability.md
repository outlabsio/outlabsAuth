# 97. Observability & Monitoring

> **Quick Reference**: Complete guide to logging, metrics, and monitoring for OutlabsAuth. Learn how to debug auth issues, track performance, and set up Grafana dashboards.

## Overview

OutlabsAuth provides **production-ready observability** out of the box with:

- **Structured Logging** - JSON logs for debugging and audit trails
- **Prometheus Metrics** - Performance monitoring and alerting
- **Correlation IDs** - Trace requests across distributed systems
- **Auto-Instrumentation** - Minimal code changes required

### Why Observability Matters

Authentication is critical infrastructure. When auth fails, you need to know:
- **What happened?** (Logs) - "User login failed: invalid password"
- **How often?** (Metrics) - "1,234 failed logins in the last hour"
- **How fast?** (Metrics) - "P95 permission checks taking 150ms"
- **Who/when/where?** (Logs) - "User john@example.com from IP 192.168.1.1"

---

## Quick Start

### Basic Setup (5 minutes)

```python
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.observability import ObservabilityConfig, create_metrics_router

app = FastAPI()

# Connect to MongoDB
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["my_database"]

# Initialize OutlabsAuth with observability
auth = SimpleRBAC(
    database=db,
    secret_key="your-secret-key",
    observability_config=ObservabilityConfig(
        # Logs - JSON format for production
        logs_format="json",          # "json" | "console" | "auto"
        logs_level="INFO",            # DEBUG, INFO, WARNING, ERROR

        # Metrics - Prometheus endpoint
        enable_metrics=True,
        metrics_path="/metrics",

        # Feature-specific logging
        log_permission_checks="failures_only",  # "all" | "failures_only" | "none"
        log_api_key_hits=False,                  # Usually too noisy
    )
)

await auth.initialize()

# Add /metrics endpoint for Prometheus scraping
app.include_router(create_metrics_router(auth.observability))

# Optional: Add correlation ID middleware for request tracing
from outlabs_auth.observability import CorrelationIDMiddleware
app.add_middleware(CorrelationIDMiddleware, obs_service=auth.observability)
```

### Verify It Works

```bash
# Start your app
uvicorn main:app --reload

# Check metrics endpoint
curl http://localhost:8000/metrics

# You should see Prometheus metrics:
# outlabs_auth_login_attempts_total{method="password",status="success"} 42
# outlabs_auth_permission_checks_total{permission="user:read",result="granted"} 1234
# ...

# Check logs (stdout)
# JSON format in production:
{"timestamp":"2025-01-24T10:15:23.456Z","level":"info","event":"user_login_success","user_id":"507f...","duration_ms":145.3}

# Console format in development:
2025-01-24 10:15:23 [INFO] user_login_success
  user_id: 507f1f77bcf86cd799439011
  email: john@example.com
  method: password
  duration_ms: 145.3
```

---

## Complete Observability Stack (Docker Compose)

**Want to see everything working together?** OutlabsAuth includes a complete Docker Compose stack with:

- ✅ **MongoDB** - Database (port 27018)
- ✅ **Redis** - Caching & activity tracking (port 6380)
- ✅ **Prometheus** - Metrics collection (port 9090)
- ✅ **Grafana** - Pre-configured dashboards (port 3011)
- ✅ **SimpleRBAC Example** - Blog API with full observability (port 8003)
- ✅ **Admin UI** - Optional web interface (port 3000)

### Quick Start (Complete Stack)

```bash
# 1. Start the complete stack
docker compose up -d

# 2. Wait for services to be ready (~30 seconds)
docker compose logs -f simple-rbac  # Watch SimpleRBAC startup

# 3. Access the services:
#    - SimpleRBAC API: http://localhost:8003/docs
#    - Prometheus:     http://localhost:9090
#    - Grafana:        http://localhost:3011 (admin/admin)
#    - Admin UI:       http://localhost:3000 (optional, run separately)

# 4. View real-time metrics in Grafana
#    - Pre-configured dashboard already imported!
#    - See login attempts, permission checks, API key usage, etc.
```

### What You Get

**Pre-configured Grafana Dashboard** (`docker/grafana/dashboards/outlabs-auth-overview.json`):
- **Authentication Metrics** - Login success/failure rates, methods used
- **Permission Checks** - Granted vs denied, by permission type
- **API Key Usage** - Active keys, usage counts, rate limits
- **Performance** - P50/P95/P99 latencies for auth operations
- **Activity Tracking** - DAU/MAU/WAU trends (if enabled)

**Prometheus Scraping** (`docker/prometheus/prometheus.yml`):
- Automatically scrapes metrics from SimpleRBAC example (port 8003)
- 15-second scrape interval
- Configured targets ready to add your own apps

**Example Integration**:
The SimpleRBAC example (`examples/simple_rbac/`) demonstrates:
- Complete observability setup with `ObservabilityConfig`
- Correlation ID middleware for request tracing
- JSON structured logging (production mode)
- Console logging (development mode)
- `/metrics` endpoint for Prometheus

### Using with Your Own App

Once you've seen the stack in action, integrate it with your app:

```bash
# Keep infrastructure running
docker compose up -d mongodb redis prometheus grafana

# Run your app locally pointing to these services
MONGODB_URL="mongodb://localhost:27018" \
REDIS_URL="redis://localhost:6380" \
uvicorn your_app:app --reload

# Prometheus will scrape your app if you add it to prometheus.yml
# Grafana dashboard will show metrics from all configured apps
```

### Stack Management

```bash
# Start everything
docker compose up -d

# Start only infrastructure (no examples)
docker compose up -d mongodb redis prometheus grafana

# View logs from specific service
docker compose logs -f grafana
docker compose logs -f simple-rbac

# Stop everything
docker compose down

# Stop and remove all data (fresh start)
docker compose down -v
```

### Ports Reference

| Service | Internal Port | Host Port | URL |
|---------|--------------|-----------|-----|
| MongoDB | 27017 | 27018 | `mongodb://localhost:27018` |
| Redis | 6379 | 6380 | `redis://localhost:6380` |
| Prometheus | 9090 | 9090 | http://localhost:9090 |
| Grafana | 3000 | 3011 | http://localhost:3011 |
| SimpleRBAC API | 8003 | 8003 | http://localhost:8003 |
| Admin UI* | 3000 | 3000 | http://localhost:3000 |

*Admin UI runs separately (not in docker-compose): `cd auth-ui && bun run dev`

**Why different ports?** To avoid conflicts with local development services you might already be running.

---

## Configuration Reference

### ObservabilityConfig

```python
from outlabs_auth.observability import ObservabilityConfig

config = ObservabilityConfig(
    # ================================================================
    # Logging Configuration
    # ================================================================

    enable_logs=True,              # Enable/disable all logging
    logs_level="INFO",             # Log level: DEBUG, INFO, WARNING, ERROR
    logs_format="auto",            # Output format:
                                   #   - "auto": JSON in prod, console in dev
                                   #   - "json": Structured JSON (for log aggregation)
                                   #   - "console": Human-readable (for development)

    logs_output="stdout",          # Where to send logs:
                                   #   - "stdout": Standard output (Docker best practice)
                                   #   - "file": Write to file (requires logs_file_path)
                                   #   - "syslog": Send to syslog

    logs_file_path=None,           # File path if logs_output="file"
    logs_file_rotation="10MB",     # Rotate after 10MB (requires loguru)
    logs_file_retention="30 days", # Keep logs for 30 days

    # ================================================================
    # Metrics Configuration
    # ================================================================

    enable_metrics=True,           # Enable Prometheus metrics
    metrics_path="/metrics",       # Path for Prometheus scraping
    metrics_port=None,             # Optional: separate port for metrics (e.g., 9090)

    # ================================================================
    # Feature-Specific Logging
    # ================================================================

    log_permission_checks="auto",  # Permission check logging:
                                   #   - "all": Log every check (verbose)
                                   #   - "failures_only": Only log denied permissions
                                   #   - "slow_only": Only log checks >100ms
                                   #   - "none": Don't log (use metrics instead)
                                   #   - "auto": failures_only in prod, all in dev

    log_api_key_hits=False,        # Log every API key validation
                                   # WARNING: High volume! Use metrics instead.

    log_token_validations=False,   # Log JWT token validations
                                   # WARNING: Very high volume! Use metrics instead.

    # ================================================================
    # Privacy & Security
    # ================================================================

    redact_sensitive_data=True,    # Redact passwords, tokens, API keys from logs
    include_ip_addresses=True,     # Include client IP in auth logs
    include_user_agents=True,      # Include User-Agent in auth logs

    # ================================================================
    # Performance
    # ================================================================

    async_logging=True,            # Don't block request threads (recommended)
    log_buffer_size=1000,          # Buffer size for async logging

    # ================================================================
    # Correlation & Tracing
    # ================================================================

    enable_correlation_ids=True,   # Auto-generate correlation IDs
    correlation_id_header="X-Correlation-ID",  # Header name

    # ================================================================
    # Advanced: OpenTelemetry (optional, for distributed tracing)
    # ================================================================

    enable_tracing=False,          # Enable OpenTelemetry tracing
    tracing_exporter="jaeger",     # "jaeger" | "zipkin" | "otlp"
    tracing_endpoint=None,         # Tracing backend endpoint
)
```

---

## Environment-Specific Configurations

### Development

```python
ObservabilityConfig(
    logs_format="console",        # Pretty printed for readability
    logs_level="DEBUG",            # Verbose logging
    log_permission_checks="all",   # See every permission check
    log_api_key_hits=True,         # Debug API key issues
    redact_sensitive_data=False,   # See actual values for debugging
)
```

### Staging

```python
ObservabilityConfig(
    logs_format="json",            # Structured logs
    logs_level="DEBUG",            # Still verbose for testing
    log_permission_checks="all",   # Debug permission issues
    log_api_key_hits=False,        # Reduce noise
    redact_sensitive_data=True,    # Protect data
)
```

### Production

```python
ObservabilityConfig(
    logs_format="json",                # For log aggregation (ELK, CloudWatch, Datadog)
    logs_level="INFO",                 # Standard level
    log_permission_checks="failures_only",  # Only log problems
    log_api_key_hits=False,            # Too noisy, use metrics instead
    log_token_validations=False,       # Too noisy, use metrics instead
    redact_sensitive_data=True,        # GDPR/compliance
    async_logging=True,                # Don't block requests
)
```

---

## What Gets Logged

OutlabsAuth logs all critical authentication and authorization events. See **[99-Log-Events-Reference.md](99-Log-Events-Reference.md)** for complete catalog.

### Common Log Events

**Authentication:**
- `user_login_success` - Successful login
- `user_login_failed` - Failed login (with reason)
- `user_logout` - User logout
- `token_refreshed` - Access token refreshed
- `account_locked` - Account locked after failed attempts

**Authorization:**
- `permission_check_granted` - Permission granted
- `permission_check_denied` - Permission denied
- `permission_check_slow` - Check took >100ms (performance issue)

**API Keys:**
- `api_key_validated` - API key successfully validated
- `api_key_validation_failed` - Invalid, expired, or rate-limited key

**Security:**
- `suspicious_activity_detected` - Rate limit exceeded, brute force attempt
- `session_hijack_suspected` - IP or user agent change during session

### Example Log Output

**JSON Format (Production):**
```json
{
  "timestamp": "2025-01-24T10:15:23.456Z",
  "level": "info",
  "event": "user_login_success",
  "user_id": "507f1f77bcf86cd799439011",
  "email": "john@example.com",
  "method": "password",
  "duration_ms": 145.3,
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Console Format (Development):**
```
2025-01-24 10:15:23 [INFO] user_login_success
  user_id: 507f1f77bcf86cd799439011
  email: john@example.com
  method: password
  duration_ms: 145.3
  ip_address: 192.168.1.1
  correlation_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## What Gets Measured

OutlabsAuth exposes Prometheus metrics for monitoring and alerting. See **[98-Metrics-Reference.md](98-Metrics-Reference.md)** for complete catalog.

### Key Metrics

**Login Metrics:**
- `outlabs_auth_login_attempts_total{status, method}` - Total login attempts
- `outlabs_auth_login_duration_seconds{method}` - Login latency histogram

**Permission Metrics:**
- `outlabs_auth_permission_checks_total{result, permission}` - Permission checks
- `outlabs_auth_permission_check_duration_seconds` - Check latency histogram

**Session Metrics:**
- `outlabs_auth_active_sessions` - Current active sessions (gauge)
- `outlabs_auth_token_refresh_total` - Token refresh operations

**API Key Metrics:**
- `outlabs_auth_api_key_validations_total{status}` - API key validations
- `outlabs_auth_api_key_rate_limit_hits_total` - Rate limit hits

### Example Prometheus Queries

```promql
# Login success rate (last 5 minutes)
rate(outlabs_auth_login_attempts_total{status="success"}[5m])

# Failed login rate (detect attacks)
rate(outlabs_auth_login_attempts_total{status="failed"}[5m]) > 10

# P95 login latency
histogram_quantile(0.95, rate(outlabs_auth_login_duration_seconds_bucket[5m]))

# P99 permission check latency
histogram_quantile(0.99, rate(outlabs_auth_permission_check_duration_seconds_bucket[5m]))

# Active sessions
outlabs_auth_active_sessions
```

---

## Integration Guides

### Prometheus + Grafana

#### Step 1: Configure Prometheus

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'outlabs-auth'
    static_configs:
      - targets: ['localhost:8000']  # Your FastAPI app
        labels:
          app: 'my-app'
          environment: 'production'
```

#### Step 2: Start Prometheus

```bash
# Docker
docker run -d -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Or native
prometheus --config.file=prometheus.yml
```

#### Step 3: Import Grafana Dashboard

1. Open Grafana (http://localhost:3000)
2. Go to Dashboards → Import
3. Upload `grafana-dashboards/outlabs-auth-overview.json`
4. Select Prometheus data source
5. Click "Import"

You now have a complete auth monitoring dashboard! See **[Grafana Dashboard Guide](../grafana-dashboards/README.md)** for panel descriptions.

---

### ELK Stack (Elasticsearch + Kibana)

#### Step 1: Configure Logstash

Create `logstash.conf`:

```ruby
input {
  # Read from Docker logs
  tcp {
    port => 5000
    codec => json_lines
  }
}

filter {
  # Parse OutlabsAuth JSON logs
  if [event] {
    mutate {
      add_tag => ["outlabs_auth"]
    }
  }
}

output {
  if "outlabs_auth" in [tags] {
    elasticsearch {
      hosts => ["elasticsearch:9200"]
      index => "outlabs-auth-%{+YYYY.MM.dd}"
    }
  }
}
```

#### Step 2: Ship Logs to Logstash

```python
# Configure OutlabsAuth to output JSON
ObservabilityConfig(
    logs_format="json",
    logs_output="stdout"
)
```

```bash
# Configure Docker to send logs to Logstash
docker run -d \
  --log-driver=syslog \
  --log-opt syslog-address=tcp://localhost:5000 \
  --log-opt syslog-format=rfc5424 \
  your-app
```

#### Step 3: Create Kibana Dashboards

1. Open Kibana (http://localhost:5601)
2. Management → Index Patterns → Create `outlabs-auth-*`
3. Discover → Filter by `event:user_login_failed`
4. Visualize → Create dashboard with auth events

---

### AWS CloudWatch

#### Step 1: Install CloudWatch Agent

```bash
# Install CloudWatch agent on EC2/ECS
wget https://s3.amazonaws.com/amazoncloudwatch-agent/...
```

#### Step 2: Configure Log Collection

```json
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/app/auth.log",
            "log_group_name": "/aws/app/outlabs-auth",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
```

#### Step 3: Create CloudWatch Insights Queries

```sql
# Failed logins in last hour
fields @timestamp, user_id, email, ip_address
| filter event = "user_login_failed"
| sort @timestamp desc
| limit 100

# Slow permission checks
fields @timestamp, user_id, permission, duration_ms
| filter event = "permission_check_slow"
| stats avg(duration_ms) by permission
```

---

### Datadog

#### Step 1: Install Datadog Agent

```bash
DD_API_KEY=<your-api-key> DD_SITE="datadoghq.com" bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script.sh)"
```

#### Step 2: Configure Log Collection

```yaml
# /etc/datadog-agent/conf.d/outlabs_auth.yaml
logs:
  - type: file
    path: "/var/log/app/*.log"
    service: outlabs-auth
    source: python
    sourcecategory: auth
```

#### Step 3: Enable Metrics Collection

OutlabsAuth metrics are auto-detected by Datadog via Prometheus endpoint.

```yaml
# /etc/datadog-agent/conf.d/prometheus.yaml
init_config:

instances:
  - prometheus_url: http://localhost:8000/metrics
    namespace: outlabs_auth
    metrics:
      - outlabs_auth_*
```

---

## Correlation IDs

OutlabsAuth automatically generates correlation IDs for tracing requests across distributed systems.

### How It Works

```python
# Client sends request with optional correlation ID
GET /api/users/me
X-Correlation-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890

# OutlabsAuth logs include correlation ID
{
  "event": "permission_check_granted",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  ...
}

# All related logs share the same correlation ID
# Search logs by correlation_id to see entire request flow
```

### Custom Correlation ID Header

```python
ObservabilityConfig(
    correlation_id_header="X-Request-ID",  # Use your custom header
)
```

---

## Best Practices

### 1. Start with Defaults, Tune Later

```python
# Start simple
auth = SimpleRBAC(database=db)

# Metrics and basic logging are enabled by default
# Tune later based on actual volume
```

### 2. Use Metrics for High-Volume Events

```python
# DON'T log every token validation (too noisy)
ObservabilityConfig(
    log_token_validations=False,  # Use metrics instead
    log_api_key_hits=False,        # Use metrics instead
)

# DO log problems
ObservabilityConfig(
    log_permission_checks="failures_only",  # Debug denied permissions
)
```

### 3. Redact Sensitive Data in Production

```python
ObservabilityConfig(
    redact_sensitive_data=True,  # ALWAYS in production
)

# Logs will show:
# "password": "***REDACTED***"
# "token": "***REDACTED***"
# "api_key": "sk_live_abc...***"  # Shows prefix only
```

### 4. Use Structured Logging

```python
# JSON logs are searchable and aggregatable
ObservabilityConfig(
    logs_format="json",  # In production
)

# Easy to search:
# jq '.event == "user_login_failed"' app.log
# kubectl logs pod-name | jq '.user_id == "507f..."'
```

### 5. Monitor the Right Metrics

**Key Alerts:**
- Login failure rate > 10/min (possible attack)
- P95 login latency > 500ms (performance issue)
- P95 permission check > 100ms (slow hierarchy/ABAC)
- Failed permission checks spike (misconfigured roles)

---

## Troubleshooting

### Issue: No metrics at /metrics endpoint

**Check:**
```python
# Ensure metrics are enabled
ObservabilityConfig(enable_metrics=True)

# Ensure router is added
app.include_router(create_metrics_router(auth.observability))
```

### Issue: Logs not appearing

**Check:**
```python
# Ensure logs are enabled
ObservabilityConfig(enable_logs=True)

# Check log level
ObservabilityConfig(logs_level="DEBUG")  # More verbose

# Check output
ObservabilityConfig(logs_output="stdout")  # Should go to console
```

### Issue: Too many logs (high volume)

**Solution:**
```python
ObservabilityConfig(
    log_permission_checks="failures_only",  # Reduce volume
    log_api_key_hits=False,                  # Disable high-volume events
    log_token_validations=False,
)
```

### Issue: Can't find specific event in logs

**Use correlation ID:**
```bash
# Search for correlation ID across all logs
grep "a1b2c3d4-e5f6-7890-abcd" /var/log/app/*.log

# Or with jq
cat app.log | jq 'select(.correlation_id == "a1b2c3d4-...")'
```

---

## Next Steps

- **[98-Metrics-Reference.md](98-Metrics-Reference.md)** - Complete metrics catalog
- **[99-Log-Events-Reference.md](99-Log-Events-Reference.md)** - Complete log events catalog
- **[Docker Compose Stack](../docker-compose.yml)** - Complete observability stack (MongoDB + Redis + Prometheus + Grafana + SimpleRBAC example)
- **[Grafana Dashboard](../docker/grafana/dashboards/outlabs-auth-overview.json)** - Pre-built dashboard (auto-loaded in Docker Compose stack)
- **[SimpleRBAC Example](../examples/simple_rbac/)** - Working example with full observability integration

---

## FAQ

**Q: Do I need to install anything extra?**
A: No! Observability works out-of-box. Optional dependencies like `structlog` are included in the core package.

**Q: Will logging slow down my app?**
A: No. OutlabsAuth uses async logging by default (`async_logging=True`), which doesn't block request threads.

**Q: Can I disable observability entirely?**
A: Yes. Set `enable_logs=False` and `enable_metrics=False` in `ObservabilityConfig`.

**Q: Can I send logs to multiple destinations?**
A: Yes. Use `logs_output="stdout"` and let your infrastructure (Docker, K8s, log shipper) handle routing to multiple destinations.

**Q: How much disk space do logs use?**
A: None! Logs go to `stdout` by default. Docker/K8s handles rotation and retention. If you use `logs_output="file"`, configure rotation: `logs_file_rotation="10MB"`.

**Q: Are correlation IDs unique across instances?**
A: Yes. UUIDs are globally unique. If client sends `X-Correlation-ID`, OutlabsAuth uses it; otherwise generates a new UUID.

---

**Last Updated:** 2025-01-24
**Related:** [98-Metrics-Reference.md](98-Metrics-Reference.md), [99-Log-Events-Reference.md](99-Log-Events-Reference.md)
