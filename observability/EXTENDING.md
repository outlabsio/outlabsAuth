# Extending the Observability Stack

This guide explains how to add custom metrics, dashboards, and alerts for your business-specific needs while building on top of the OutlabsAuth base observability.

## Overview

The observability stack provides:
- **Prometheus**: Metrics collection and querying
- **Grafana**: Visualization and dashboards
- **Loki**: Log aggregation
- **Tempo**: Distributed tracing

OutlabsAuth comes with pre-built auth metrics. This guide shows how to add your own.

## Adding Custom Metrics

### 1. Define Metrics in Your Application

Use the `prometheus_client` library (already included with OutlabsAuth):

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter - things that only go up
orders_total = Counter(
    'orders_total',
    'Total orders placed',
    ['status', 'payment_method']
)

# Histogram - for measuring distributions (latency, sizes)
order_processing_seconds = Histogram(
    'order_processing_seconds',
    'Time to process an order',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Gauge - values that go up and down
active_carts = Gauge(
    'active_carts',
    'Number of active shopping carts'
)
```

### 2. Instrument Your Code

```python
from contextlib import contextmanager
import time

# Increment counters
@app.post("/orders")
async def create_order(order: OrderCreate):
    result = await process_order(order)
    orders_total.labels(
        status=result.status,
        payment_method=order.payment_method
    ).inc()
    return result

# Time operations with histograms
@app.post("/orders/{order_id}/process")
async def process_order(order_id: str):
    with order_processing_seconds.time():
        return await do_processing(order_id)

# Track current values with gauges
@app.post("/cart")
async def add_to_cart(item: CartItem):
    active_carts.inc()
    # ...

@app.delete("/cart/{cart_id}")
async def delete_cart(cart_id: str):
    active_carts.dec()
    # ...
```

### 3. Expose Metrics Endpoint

OutlabsAuth automatically exposes `/metrics` when you call `auth.instrument_fastapi(app)`. Your custom metrics will be included.

If you need a custom path, configure it in `.env`:
```bash
API_METRICS_PATH=/custom/metrics
```

## Adding Custom Dashboards

### 1. Create Dashboard JSON

Create your dashboard in Grafana UI, then export as JSON:

1. Open Grafana (http://localhost:3011)
2. Create a new dashboard
3. Add panels for your metrics
4. Settings > JSON Model > Copy

### 2. Save Dashboard File

Save the JSON to `observability/grafana/dashboards/`:

```bash
observability/grafana/dashboards/
├── outlabs-auth.json      # Base auth dashboard (included)
├── orders.json            # Your custom dashboard
└── inventory.json         # Another custom dashboard
```

### 3. Dashboard Auto-Discovery

All `.json` files in the dashboards folder are automatically loaded by Grafana on startup.

### Example Dashboard Panel (PromQL)

```json
{
  "title": "Orders per Minute",
  "type": "timeseries",
  "targets": [
    {
      "expr": "rate(orders_total[1m])",
      "legendFormat": "{{status}}"
    }
  ]
}
```

## Adding Prometheus Alerts

### 1. Create Alert Rules File

Create `observability/prometheus/alerts/business.yml`:

```yaml
groups:
  - name: business_alerts
    rules:
      # Alert when order processing is slow
      - alert: SlowOrderProcessing
        expr: histogram_quantile(0.95, rate(order_processing_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Order processing is slow"
          description: "95th percentile order processing time is {{ $value }}s"

      # Alert when orders are failing
      - alert: HighOrderFailureRate
        expr: |
          rate(orders_total{status="failed"}[5m]) 
          / rate(orders_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High order failure rate"
          description: "{{ $value | humanizePercentage }} of orders are failing"
```

### 2. Update Prometheus Config Template

Edit `prometheus/prometheus.yml.template`:

```yaml
rule_files:
  - /etc/prometheus/alerts/*.yml
```

### 3. Mount Alerts Directory

Add to `docker-compose.yml` under prometheus service:

```yaml
volumes:
  - ./prometheus/alerts:/etc/prometheus/alerts:ro
```

## Adding Custom Log Fields

### 1. Configure Structured Logging

OutlabsAuth uses structlog. Add custom fields:

```python
import structlog

logger = structlog.get_logger()

# Add fields to specific log entries
logger.info(
    "order_created",
    order_id=order.id,
    customer_id=order.customer_id,
    total=order.total,
    items_count=len(order.items)
)
```

### 2. Query Custom Fields in Grafana

Use Loki queries to filter by your custom fields:

```logql
{app="myproject"} | json | order_id != ""
{app="myproject"} | json | total > 1000
{app="myproject"} | json | event="order_created" | line_format "Order {{.order_id}}: ${{.total}}"
```

## Adding Tracing

### 1. Configure OpenTelemetry

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure tracing
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(
    endpoint="localhost:4317",  # Tempo OTLP endpoint
    insecure=True
))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
```

### 2. Add Custom Spans

```python
@app.post("/orders")
async def create_order(order: OrderCreate):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("customer_id", order.customer_id)
        
        with tracer.start_as_current_span("validate_order"):
            await validate_order(order)
        
        with tracer.start_as_current_span("process_payment"):
            await process_payment(order)
        
        with tracer.start_as_current_span("save_order"):
            result = await save_order(order)
        
        span.set_attribute("order_id", result.id)
        return result
```

## Environment Variables Reference

Add to `.env` for customization:

```bash
# Project identification (used in metric labels)
PROJECT_NAME=myproject
ENVIRONMENT=production

# Your API
API_HOST=host.docker.internal
API_PORT=8000
API_METRICS_PATH=/metrics

# Service ports (change if conflicts)
GRAFANA_PORT=3011
PROMETHEUS_PORT=9090
LOKI_PORT=3100
TEMPO_PORT=3200

# Prometheus settings
PROMETHEUS_RETENTION=30d           # How long to keep metrics
PROMETHEUS_SCRAPE_INTERVAL=15s     # How often to scrape

# Grafana settings
GRAFANA_ADMIN_PASSWORD=secure-password
```

## Multi-Service Setup

If your project has multiple services, update `prometheus/prometheus.yml.template`:

```yaml
scrape_configs:
  # Main API
  - job_name: "${PROJECT_NAME}-api"
    static_configs:
      - targets: ["${API_HOST}:${API_PORT}"]
        labels:
          service: "api"

  # Worker service
  - job_name: "${PROJECT_NAME}-worker"
    static_configs:
      - targets: ["${API_HOST}:8001"]
        labels:
          service: "worker"

  # Scheduler service
  - job_name: "${PROJECT_NAME}-scheduler"
    static_configs:
      - targets: ["${API_HOST}:8002"]
        labels:
          service: "scheduler"
```

Then re-run `./setup.sh` to regenerate configs.

## Best Practices

### Metric Naming
- Use snake_case: `order_total`, not `orderTotal`
- Include unit in name: `request_duration_seconds`, `response_size_bytes`
- Use `_total` suffix for counters: `requests_total`

### Labels
- Keep cardinality low (avoid user IDs, request IDs as labels)
- Good labels: `status`, `method`, `endpoint`, `service`
- Bad labels: `user_id`, `request_id`, `timestamp`

### Dashboard Organization
- Group related metrics in rows
- Use consistent time ranges
- Add documentation panels explaining metrics
- Include drill-down links between dashboards

### Alerting
- Alert on symptoms, not causes
- Include runbook links in annotations
- Set appropriate `for` durations to avoid flapping
- Use severity labels consistently

## Troubleshooting

### Metrics not appearing in Prometheus

1. Check your API is exposing `/metrics`:
   ```bash
   curl http://localhost:8000/metrics
   ```

2. Check Prometheus targets:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

3. Check Prometheus can reach your API (from inside Docker):
   ```bash
   docker exec outlabs-prometheus wget -qO- http://host.docker.internal:8000/metrics
   ```

### Dashboard not loading

1. Check JSON syntax:
   ```bash
   python3 -c "import json; json.load(open('grafana/dashboards/your-dashboard.json'))"
   ```

2. Restart Grafana to reload dashboards:
   ```bash
   docker compose restart grafana
   ```

### Logs not appearing in Loki

1. Check Promtail is running:
   ```bash
   docker compose logs promtail
   ```

2. Verify log format is JSON for structured queries

3. Check Loki is receiving data:
   ```bash
   curl http://localhost:3100/loki/api/v1/labels
   ```
