---
description: Start Grafana, Prometheus, Loki observability stack
---

Start the observability stack (Grafana, Prometheus, Loki, Tempo):

1. Run from project root:
   ```bash
   docker compose -f docker-compose.observability.yml up -d
   ```
2. Wait a few seconds for services to be healthy
3. Confirm services are running with `docker ps`

**Access points:**
- Grafana: http://localhost:3011 (admin/admin)
- Prometheus: http://localhost:9090
- Loki: http://localhost:3100

Note: The example APIs expose metrics at /metrics which Prometheus scrapes automatically.
Pre-built dashboard "OutlabsAuth Overview" is auto-loaded in Grafana.
