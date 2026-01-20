---
description: Stop the observability stack
---

Stop the observability stack (Grafana, Prometheus, Loki, Tempo):

```bash
docker compose -f docker-compose.observability.yml down
```

This stops and removes the containers but preserves the data volumes.
To also remove volumes (lose all metrics/logs history), add `-v` flag.
