# OutlabsAuth Observability Stack

A portable, per-project observability stack for applications using OutlabsAuth.

## What's Included

| Component | Port | Description |
|-----------|------|-------------|
| **Prometheus** | 9090 | Metrics collection and storage |
| **Grafana** | 3011 | Dashboards and visualization |
| **Loki** | 3100 | Log aggregation |
| **Tempo** | 3200 | Distributed tracing |
| **Promtail** | - | Ships logs to Loki |

## Quick Start

### 1. Configure

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your project settings
nano .env  # or use your preferred editor
```

Key settings to customize:
- `PROJECT_NAME` - Your project name (used for container names)
- `API_PORT` - Port your FastAPI app runs on
- `GRAFANA_ADMIN_PASSWORD` - Change for production!

### 2. Generate Configs

```bash
./setup.sh
```

This generates `prometheus/prometheus.yml` and `promtail/promtail.yml` from templates.

### 3. Start the Stack

```bash
docker compose up -d
```

### 4. Access

- **Grafana**: http://localhost:3011 (admin / your password)
- **Prometheus**: http://localhost:9090

## Pre-Built Dashboard

The stack includes an OutlabsAuth dashboard showing:

- Login success/failure rates
- Active sessions
- Permission check rates
- Error rates and types
- Recent error logs

## Adding Custom Metrics

### In Your FastAPI App

The OutlabsAuth observability service is extensible:

```python
from outlabs_auth import OutlabsAuth
from outlabs_auth.observability import ObservabilityPresets

# Initialize with observability
auth = OutlabsAuth(
    database_url="...",
    secret_key="...",
    observability_config=ObservabilityPresets.production()
)

# Instrument FastAPI (adds /metrics endpoint)
auth.instrument_fastapi(app)

# Add custom metrics
from prometheus_client import Counter

orders_total = Counter(
    "myapp_orders_total",
    "Total orders processed",
    ["status", "payment_method"]
)

# Use in your routes
@app.post("/orders")
async def create_order(data: OrderCreate):
    # ... create order ...
    orders_total.labels(status="created", payment_method=data.payment_method).inc()
```

### Adding More Scrape Targets

Edit `prometheus/prometheus.yml` after running setup:

```yaml
scrape_configs:
  # ... existing config ...

  # Add a worker service
  - job_name: "myproject-worker"
    static_configs:
      - targets: ["host.docker.internal:8001"]
        labels:
          app: "myproject"
          service: "worker"
```

Then restart Prometheus:
```bash
docker compose restart prometheus
```

## Running Multiple Projects

Each project gets its own stack with isolated data:

```bash
# Project A
cd project-a/observability
PROJECT_NAME=project-a GRAFANA_PORT=3011 PROMETHEUS_PORT=9090 ./setup.sh
docker compose up -d

# Project B (different ports)
cd project-b/observability
PROJECT_NAME=project-b GRAFANA_PORT=3012 PROMETHEUS_PORT=9091 ./setup.sh
docker compose up -d
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_NAME` | outlabs | Prefix for containers/volumes |
| `ENVIRONMENT` | development | Added to all metrics |
| `API_HOST` | host.docker.internal | Where your API runs |
| `API_PORT` | 8000 | Your API's port |
| `API_METRICS_PATH` | /metrics | Metrics endpoint path |
| `GRAFANA_PORT` | 3011 | Grafana external port |
| `PROMETHEUS_PORT` | 9090 | Prometheus external port |
| `LOKI_PORT` | 3100 | Loki external port |
| `TEMPO_PORT` | 3200 | Tempo external port |
| `GRAFANA_ADMIN_PASSWORD` | admin | Grafana admin password |
| `PROMETHEUS_RETENTION` | 15d | How long to keep metrics |
| `PROMETHEUS_SCRAPE_INTERVAL` | 10s | How often to collect |

### Files

```
observability/
├── docker-compose.yml           # Main compose file
├── .env.example                 # Configuration template
├── .env                         # Your configuration (git-ignored)
├── setup.sh                     # Setup script
├── prometheus/
│   ├── prometheus.yml.template  # Template
│   └── prometheus.yml           # Generated (git-ignored)
├── grafana/
│   ├── provisioning/            # Auto-provisioning configs
│   └── dashboards/              # Dashboard JSON files
├── promtail/
│   ├── promtail.yml.template    # Template
│   └── promtail.yml             # Generated (git-ignored)
└── tempo/
    └── tempo.yml                # Tempo configuration
```

## Maintenance

### Backup Grafana Dashboards

Dashboards are stored in the `grafana-data` volume. To export:

```bash
# Export all dashboards via API
curl -u admin:$GRAFANA_ADMIN_PASSWORD \
  "http://localhost:3011/api/dashboards/uid/outlabs-auth" \
  | jq '.dashboard' > backup-dashboard.json
```

### Clear All Data

```bash
docker compose down -v  # Removes volumes
./setup.sh              # Regenerate configs
docker compose up -d    # Fresh start
```

### Update Stack

```bash
docker compose pull     # Get latest images
docker compose up -d    # Restart with new images
```

## Troubleshooting

### "No data" in Grafana

1. Check your API is running: `curl http://localhost:$API_PORT/metrics`
2. Check Prometheus targets: http://localhost:9090/targets
3. Verify API_HOST and API_PORT in .env match your app

### Port conflicts

Change ports in `.env` and re-run `./setup.sh`:

```bash
GRAFANA_PORT=3012
PROMETHEUS_PORT=9091
```

### Prometheus can't reach API

If using Docker Desktop, `host.docker.internal` should work. Otherwise:
- Linux: Use `172.17.0.1` (docker0 bridge IP)
- Or run your API in Docker on the same network
