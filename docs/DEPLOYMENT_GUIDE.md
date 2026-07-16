# OutlabsAuth Deployment Guide


**Version**: 1.4
**Date**: 2025-01-14
**Audience**: DevOps engineers and system administrators
**Status**: Production Reference

**Key v1.4 Updates**:
- **Redis Pub/Sub** (DD-037): <100ms cache invalidation across distributed instances
- **Redis Counters** (DD-033): Background sync for API key usage tracking
- **Closure Table** (DD-036): O(1) tree permission queries (20x faster)
- **JWT Service Tokens** (DD-034): Zero-DB authentication for microservices

---

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Prerequisites](#prerequisites)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Scaling Strategies](#scaling-strategies)
6. [Performance Tuning](#performance-tuning)
7. [High Availability](#high-availability)
8. [Monitoring & Observability](#monitoring--observability)
9. [Backup & Recovery](#backup--recovery)
10. [Security Hardening](#security-hardening)
11. [Troubleshooting](#troubleshooting)
12. [Production Checklist](#production-checklist)

---

## Deployment Overview

OutlabsAuth is a library, not a service, so it gets embedded in your application. This guide covers deploying applications that use OutlabsAuth.

### Deployment Models

1. **Single Instance**: Simplest, suitable for small applications
2. **Multi-Instance**: Multiple app instances behind load balancer
3. **Kubernetes**: Container orchestration for production scale
4. **Serverless**: AWS Lambda, Google Cloud Functions (with limitations)

### Architecture Components

```
┌─────────────────┐
│  Load Balancer  │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼───┐
│ App1 │  │ App2 │  (Your FastAPI apps with OutlabsAuth)
└───┬──┘  └──┬───┘
    │        │
    └───┬────┘
        │
┌───────▼────────┐
│   PostgreSQL   │  (Shared database)
└───────┬────────┘
        │
┌───────▼────────┐
│   Redis        │  (Shared cache - optional)
└────────────────┘
```

### Schema ownership

OutlabsAuth ships its own Alembic migrations **inside the package**
(`outlabs_auth/migrations/versions/`) and applies them with its own CLI:

```bash
outlabs-auth migrate
```

It tracks its revisions in a namespaced version table,
**`outlabs_auth_alembic_version`**, so it cannot collide with a host
application's `alembic_version`. Your application's own `alembic upgrade head`
does **not** touch the auth schema, and `outlabs-auth migrate` does not touch
yours. The two histories are independent — deploy both.

---

## Prerequisites

### System Requirements

**Minimum**:
- CPU: 2 cores
- RAM: 2 GB
- Disk: 10 GB SSD
- OS: Linux (Ubuntu 20.04+, Debian 11+)

**Recommended (Production)**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB SSD
- OS: Linux (Ubuntu 22.04 LTS)

### Software Dependencies

- **Python**: 3.12+ (the package requires `>=3.12`)
- **PostgreSQL**: 16+ (what CI runs against)
- **Redis**: 7.0+ recommended for production API-key counters, rate limits, and permission caching
- **Docker**: 24.0+ (for containerized deployments)
- **Kubernetes**: 1.28+ (for K8s deployments)

---

## Docker Deployment

### Dockerfile

> **Note**: OutlabsAuth is a library — it ships no image and no Dockerfile of its
> own. The `docker-compose.yml` at the root of *this repository* exists only to
> develop the library: it starts Postgres and Redis, nothing else, and the examples
> run directly via `uv`. Everything below is a template for **your** application.

```dockerfile
# Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Running Migrations

The auth schema is deployed by the library's CLI, which reads `DATABASE_URL` and
`OUTLABS_AUTH_SCHEMA` from the environment. Run it as a **release/init step
before the app starts** — not from application code:

```bash
# Apply the library's migrations up to head
outlabs-auth migrate

# Verify connectivity, schema, revision, and core tables
outlabs-auth doctor

# Inspect revision state
outlabs-auth current
outlabs-auth heads
outlabs-auth history
```

Other subcommands: `seed-system`, `bootstrap-admin`, `init-db`, `downgrade`,
`adopt-existing-schema` (stamp an already-populated schema), and
`run-maintenance`.

`auto_migrate=True` exists as a config field and is convenient for local
development. **Do not use it in production** — concurrent instances starting at
once will race on the same migration. Use the CLI as a discrete step, so a
failed migration fails the deploy instead of a subset of your pods.

In compose, that's a one-shot service the app waits on:

```yaml
  migrate:
    image: your-registry.com/outlabs-auth-app:latest
    command: outlabs-auth migrate
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/appdb
      - OUTLABS_AUTH_SCHEMA=auth
    depends_on:
      postgres:
        condition: service_healthy
    restart: "no"
```

In Kubernetes, the same thing is an init container or a `Job` gating the rollout.

### Docker Compose (Development)

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/appdb
      - OUTLABS_AUTH_SCHEMA=auth
      - REDIS_URL=redis://redis:6379
      - REDIS_KEY_PREFIX=myapp:development
      - SECRET_KEY=${SECRET_KEY}
      - ENVIRONMENT=development
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
    restart: unless-stopped

  postgres:
    image: postgres:16
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=appdb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

### Docker Compose (Production)

```yaml
# docker-compose.prod.yml
services:
  app:
    image: your-registry.com/outlabs-auth-app:latest
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://app:${POSTGRES_PASSWORD}@postgres:5432/appdb?ssl=verify-full
      - OUTLABS_AUTH_SCHEMA=auth
      - REDIS_URL=redis://redis:6379
      - REDIS_KEY_PREFIX=myapp:production
      - SECRET_KEY=${SECRET_KEY}
      - ENVIRONMENT=production
    depends_on:
      - postgres
      - redis
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3

  postgres:
    image: postgres:16
    volumes:
      - /data/postgres:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=appdb
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - /data/redis:/data
    restart: always
    command: redis-server --appendonly yes
```

> For anything beyond a single box, prefer a managed Postgres (RDS/Aurora, Cloud
> SQL, Neon) over a compose-managed database. Replication, failover, backups, and
> PITR are the whole job, and a single-container Postgres gives you none of them.

### Building and Running

```bash
# Build image
docker build -t outlabs-auth-app:latest .

# Run with Docker Compose
docker compose up -d

# Apply the auth schema (one-shot, before first app start)
docker compose run --rm app outlabs-auth migrate

# View logs
docker compose logs -f app

# Scale app instances
docker compose up -d --scale app=3

# Stop services
docker compose down

# Production deployment
docker compose -f docker-compose.prod.yml up -d
```

---

## Kubernetes Deployment

### Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: outlabs-auth
```

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: outlabs-auth-config
  namespace: outlabs-auth
data:
  ENVIRONMENT: "production"
  OUTLABS_AUTH_SCHEMA: "auth"
  REDIS_URL: "redis://redis-service:6379"
  REDIS_KEY_PREFIX: "myapp:production"
  LOG_LEVEL: "INFO"
```

`DATABASE_URL` carries a password, so it belongs in the Secret below — not in a
ConfigMap.

### Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: outlabs-auth-secrets
  namespace: outlabs-auth
type: Opaque
data:
  # Base64 encoded values
  # SECRET_KEY must be >= 32 chars under HS256: openssl rand -hex 32
  SECRET_KEY: <base64-encoded-secret-key>
  # Full SQLAlchemy/asyncpg URL, including credentials:
  #   postgresql+asyncpg://app:PASSWORD@postgres-service:5432/appdb?ssl=verify-full
  DATABASE_URL: <base64-encoded-database-url>
```

### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: outlabs-auth-app
  namespace: outlabs-auth
spec:
  replicas: 3
  selector:
    matchLabels:
      app: outlabs-auth
  template:
    metadata:
      labels:
        app: outlabs-auth
    spec:
      containers:
      - name: app
        image: your-registry.com/outlabs-auth-app:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: outlabs-auth-config
        - secretRef:
            name: outlabs-auth-secrets
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 1
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Migration Job

Run the auth migrations as a `Job` before rolling out the Deployment, so a
failed migration blocks the release rather than half-starting your pods:

```yaml
# migrate-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: outlabs-auth-migrate
  namespace: outlabs-auth
spec:
  backoffLimit: 2
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migrate
        image: your-registry.com/outlabs-auth-app:latest
        command: ["outlabs-auth", "migrate"]
        envFrom:
        - configMapRef:
            name: outlabs-auth-config
        - secretRef:
            name: outlabs-auth-secrets
```

`outlabs-auth migrate` is idempotent — re-running it when the schema is already
at head is a no-op, which is what makes it safe as a release step.

### Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: outlabs-auth-service
  namespace: outlabs-auth
spec:
  selector:
    app: outlabs-auth
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: outlabs-auth-ingress
  namespace: outlabs-auth
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - auth.yourdomain.com
    secretName: outlabs-auth-tls
  rules:
  - host: auth.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: outlabs-auth-service
            port:
              number: 80
```

### HorizontalPodAutoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: outlabs-auth-hpa
  namespace: outlabs-auth
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: outlabs-auth-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Deploying to Kubernetes

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Create secrets (from environment variables)
kubectl create secret generic outlabs-auth-secrets \
  --namespace=outlabs-auth \
  --from-literal=SECRET_KEY=$SECRET_KEY \
  --from-literal=DATABASE_URL=$DATABASE_URL

# Apply configurations
kubectl apply -f configmap.yaml

# Migrate the auth schema BEFORE rolling out the app
kubectl apply -f migrate-job.yaml
kubectl wait --for=condition=complete --timeout=300s \
  job/outlabs-auth-migrate -n outlabs-auth

kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml

# Check status
kubectl get pods -n outlabs-auth
kubectl get services -n outlabs-auth
kubectl get ingress -n outlabs-auth

# View logs
kubectl logs -f deployment/outlabs-auth-app -n outlabs-auth

# Scale manually
kubectl scale deployment outlabs-auth-app --replicas=5 -n outlabs-auth
```

---

## Scaling Strategies

### Vertical Scaling

**When to Use**: Small to medium applications, simpler operations

**Configuration**:
```yaml
# Increase resources per pod
resources:
  requests:
    cpu: 2
    memory: 4Gi
  limits:
    cpu: 4
    memory: 8Gi
```

**Pros**:
- Simpler setup
- Less network overhead

**Cons**:
- Limited by node size
- Single point of failure

### Horizontal Scaling

**When to Use**: Production applications, high availability needs

**Configuration**:
```yaml
# Increase number of replicas
replicas: 5

# Or use HPA
minReplicas: 3
maxReplicas: 20
```

**Pros**:
- Better fault tolerance
- No upper limit
- Cost-effective

**Cons**:
- Need load balancer
- More complex

### Autoscaling Configuration

**CPU-Based**:
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70
```

**Memory-Based**:
```yaml
metrics:
- type: Resource
  resource:
    name: memory
    target:
      type: Utilization
      averageUtilization: 80
```

**Custom Metrics** (requests per second):
```yaml
metrics:
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "1000"
```

---

## Performance Tuning

### Application Configuration

**Uvicorn Workers**:
```python
# main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,  # CPU cores * 2 + 1
        loop="uvloop",  # Faster event loop
        http="httptools",  # Faster HTTP parser
        log_level="info"
    )
```

**Or via Gunicorn**:
```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Database Optimization

**Connection Pooling**:

The library builds its own async engine from `database_url`. Pool sizing is a
deployment decision — the constraint is that **every instance holds its own
pool**, so total connections is `replicas x (pool_size + max_overflow)`, which
must stay under Postgres's `max_connections` (default 100).

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
)
```

Three pods at `pool_size=20, max_overflow=10` is already 90 connections. For
high replica counts or serverless, put **PgBouncer** (transaction pooling) in
front and keep each app's pool small. Note that transaction-mode pooling is
incompatible with prepared-statement caching — asyncpg needs
`statement_cache_size=0` behind PgBouncer.

**Indexes**:

Indexes are **created by the library's own migrations** — do not hand-create
them on startup. `outlabs-auth migrate` brings the schema, including all
indexes, to the current head. The migration history contains dedicated index
work (for example `20260422_0015_add_api_key_status_expires_at_compound_index`,
`20260422_0016_drop_redundant_unique_indexes`, and `20260611_0018_index_hygiene`).

Verify the deployed schema matches the code's expectations:

```bash
outlabs-auth doctor    # checks connectivity, schema, revision, core tables
outlabs-auth current   # the revision the database is actually on
outlabs-auth heads     # the revision the installed code expects
```

If `current` lags `heads`, you have shipped code ahead of its schema.

### Caching Strategy

**Redis Configuration**:
```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    redis_url="redis://redis:6379",
    redis_key_prefix="myapp:production",  # REQUIRED when Redis is enabled
    cache_ttl_seconds=300,  # 5 minutes
)
```

**`redis_key_prefix` is required whenever Redis is enabled** (0.1.0a24+) —
construction raises without it. Use a namespace that is unique per application
*and* per environment (`myapp:production`, `myapp:staging`). Two deployments
sharing one Redis database without distinct prefixes will consume and discard
each other's counters and cached authorization state.

`redis_url` enables both Redis counters and the permission cache by default. If
you need Redis counters/rate limits but want to disable permission caching while
debugging an integration, pass `enable_caching=False` explicitly.

For API-key protected FastAPI routes that use
`auth.deps.require_permission(...)`, and for host code calling
`auth.authorize_api_key(..., required_scope=...)` without ABAC, Redis cache mode
also enables a short-lived compiled auth snapshot. The warm path validates the
API key, scopes, owner permissions, usage counter, rate limits, and cached
Enterprise entity/tree relation checks from Redis without issuing SQL. The
default snapshot TTL is 60 seconds and can be tuned with
`api_key_auth_snapshot_ttl`. Snapshots also carry Redis version counters for
global RBAC state, user state, integration-principal state, and entity state.
Role, permission, membership, user status, integration-principal, and API-key
lifecycle mutations invalidate matching warm snapshots before the TTL expires.

Current local benchmark smoke for Redis cache mode shows the warm SimpleRBAC
worker-style API-key paths issuing `0.00` SQL queries/request:

| scenario | q/req | p95 ms |
|---|---:|---:|
| direct `auth.authorize_api_key(...)` | 0.00 | 8.53 |
| `auth.deps.require_permission(...)` | 0.00 | 4.49 |

**Cache Invalidation**:
```python
# Automatic invalidation on changes
await auth.user_service.update_user(user_id, name="New Name")
# Cache automatically cleared

# Manual cache clearing
await auth.cache.clear_user_cache(user_id)
await auth.cache.clear_permission_cache(user_id)
```

### Redis Pub/Sub for Cache Invalidation (v1.4 - DD-037)

**Why Redis Pub/Sub**: In multi-instance deployments, caches can become stale. Redis Pub/Sub provides <100ms cache invalidation across all instances.

**Architecture**:
```
Instance 1          Instance 2          Instance 3
    |                   |                   |
    |------- Pub/Sub Channel: cache_invalidation -------|
    |                   |                   |
    v                   v                   v
Redis Master (Pub/Sub + Cache)
```

**Configuration**:
```python
# Initialize with Redis Pub/Sub
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    redis_url="redis://redis:6379",
    redis_key_prefix="myapp:production",
    cache_ttl_seconds=300,
)

# Start Pub/Sub subscriber in background
import asyncio

async def start_pubsub_subscriber():
    """Background task for listening to cache invalidation events"""
    await auth.cache.start_pubsub_subscriber()

# Run in background (e.g., in FastAPI startup event)
@app.on_event("startup")
async def startup():
    asyncio.create_task(start_pubsub_subscriber())
```

**Docker Compose with Redis Pub/Sub**:
```yaml
# docker-compose.yml
services:
  app1:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - ENABLE_PUBSUB_INVALIDATION=true
    depends_on:
      - redis
      - postgres

  app2:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - ENABLE_PUBSUB_INVALIDATION=true
    depends_on:
      - redis
      - postgres

  app3:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - ENABLE_PUBSUB_INVALIDATION=true
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --notify-keyspace-events AKE
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

**Kubernetes Deployment with Redis Pub/Sub**:
```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: outlabs-auth
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7.0-alpine
        args:
          - redis-server
          - --appendonly
          - "yes"
          - --notify-keyspace-events
          - AKE  # Enable keyspace events for Pub/Sub
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: outlabs-auth
spec:
  selector:
    app: redis
  ports:
  - protocol: TCP
    port: 6379
    targetPort: 6379
  type: ClusterIP
```

**Testing Cache Invalidation**:
```python
# Test cache invalidation across instances
import asyncio
import redis.asyncio as aioredis

async def test_cache_invalidation():
    # Connect to Redis
    redis_client = await aioredis.from_url("redis://redis:6379")

    # Subscribe to invalidation channel
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("cache_invalidation")

    # Listen for messages
    async for message in pubsub.listen():
        if message["type"] == "message":
            print(f"Cache invalidation event: {message['data']}")
            # Handle cache invalidation
            await handle_cache_invalidation(message["data"])

# In another instance, trigger invalidation
await auth.cache.invalidate_user_cache(user_id)
# This publishes to "cache_invalidation" channel
# All instances receive the event and clear their caches
```

**Monitoring Pub/Sub**:
```bash
# Monitor Redis Pub/Sub activity
redis-cli

# Check active channels
PUBSUB CHANNELS

# Monitor all messages (debugging)
PSUBSCRIBE *

# Check number of subscribers
PUBSUB NUMSUB cache_invalidation
```

**Performance Impact**:
- **Message Delivery**: <5ms within datacenter
- **Cross-instance Propagation**: <100ms total (including processing)
- **Overhead**: Negligible (~0.1% CPU per 1000 messages/sec)

**High Availability**:
```yaml
# Redis Sentinel for Pub/Sub HA
services:
  redis-master:
    image: redis:7.0-alpine
    command: redis-server --appendonly yes --notify-keyspace-events AKE

  redis-sentinel-1:
    image: redis:7.0-alpine
    command: >
      redis-sentinel /etc/redis/sentinel.conf
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 5000
      --sentinel failover-timeout mymaster 10000

  redis-sentinel-2:
    image: redis:7.0-alpine
    command: >
      redis-sentinel /etc/redis/sentinel.conf
      --sentinel monitor mymaster redis-master 6379 2

  redis-sentinel-3:
    image: redis:7.0-alpine
    command: >
      redis-sentinel /etc/redis/sentinel.conf
      --sentinel monitor mymaster redis-master 6379 2
```

**Application Configuration with Sentinel**:

The library does not take Sentinel topology directly — it accepts a `redis_url`.
Point that URL at a proxy or a service address that resolves to the current
master (for example HAProxy fronting the Sentinel set, or a Kubernetes Service
managed by your Redis operator), and let the failover machinery live outside the
application:

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    redis_url="redis://redis-master-proxy:6379",
    redis_key_prefix="myapp:production",
)
```

### Background Sync for API Keys (v1.4 - DD-033)

**Why Background Sync**: API key usage tracking generates heavy database load. Redis counters reduce writes by 99%+.

> **Production recommendation**: Enable Redis for any deployment that expects concurrent requests sharing a single API key (scrapers, batch importers, worker fleets, machine-to-machine integrations). The failure mode without Redis is severe, not just "slower" — see below.

**Why the DB fallback wedges under concurrency**:

Without Redis, every authenticated request executes roughly:

```sql
UPDATE api_keys
SET    last_used_at = now(),
       usage_count  = usage_count + 1
WHERE  id = <api_key_id>
```

This runs inside the auth middleware on the request's database session. Every worker that presents the same API key is writing to the *same row*, so Postgres serializes them on a row-level tuple lock. Observed behavior from a real migration workload (32 concurrent ingest requests, one shared scraper key):

- `pg_stat_activity` shows most connections blocked on `wait_event_type=Lock, wait_event=tuple`, all stuck on the same `UPDATE api_keys SET ... last_used_at, usage_count ...` statement.
- Per-request latency balloons from ~20 ms to ~200 ms even though the ingest queries themselves are fast — the middleware UPDATE is the wall.
- Scaling out API workers (more uvicorn processes) and client concurrency does **not** help, because the contention is on a single Postgres row, not on the app.

Providing `redis_url` enables Redis by default. That moves the usage counter to `INCR apikey:{id}:usage`, stores the timestamp in Redis, and enables the permission-check cache. The hot-row serialization disappears, and repeated permission checks avoid most role/permission aggregation queries.

**Heads-up: enabling Redis also activates the rate limiter.** `_check_rate_limits` in `services/api_key.py` is guarded by `if self.redis_client and self.redis_client.is_available`, so it's silently a no-op when Redis is absent. The first time you turn Redis on, audit every row in `api_keys` — the default `rate_limit_per_minute` of 60 will cause batch workloads to start getting `InvalidInputError: Rate limit exceeded` after the first ~60 requests. For service keys used by importers or scrapers, set `rate_limit_per_minute` to a high value (or configure a dedicated service key) before flipping Redis on.

**Configuration**:
```python
# Enable Redis counters for API keys
auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    redis_url="redis://redis:6379",  # Enables Redis counters + permission cache
    redis_key_prefix="myapp:production",
)

# Start background sync task
@app.on_event("startup")
async def startup():
    from outlabs_auth.workers import start_api_key_sync_worker

    app.state.api_key_usage_sync = await start_api_key_sync_worker(
        auth.api_key_service,
        auth.config,
        session_factory=auth.session_factory,
        interval_seconds=300,
    )

@app.on_event("shutdown")
async def shutdown():
    await app.state.api_key_usage_sync.stop()
```

**How It Works**:
```
API Request → Redis INCR apikey:{key_id}:usage → Every 5 min → Batch update Postgres
100 requests/sec → 100 Redis writes (fast) → 1 DB write/5min (instead of 30,000)
```

**Monitoring Counter Sync**:
```python
# Custom metric for monitoring sync status
from prometheus_client import Gauge

api_key_pending_syncs = Gauge(
    'api_key_pending_syncs',
    'Number of API keys with pending usage syncs'
)

# Check pending syncs
async def check_pending_syncs():
    keys = await redis.keys("api_key_usage:*")
    api_key_pending_syncs.set(len(keys))
```

### Load Balancing

**Nginx Configuration**:
```nginx
upstream outlabs_auth_backend {
    least_conn;  # Load balancing method
    server app1:8000 max_fails=3 fail_timeout=30s;
    server app2:8000 max_fails=3 fail_timeout=30s;
    server app3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name auth.yourdomain.com;

    location / {
        proxy_pass http://outlabs_auth_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

---

## High Availability

### PostgreSQL High Availability

**Use a managed Postgres for this.** Replication, automatic failover, backups,
and point-in-time recovery are the substance of database HA, and hand-rolling
them in compose is a reliable way to discover you have none of them during an
incident. RDS/Aurora Multi-AZ, Cloud SQL HA, and Neon all provide a single
endpoint that survives a failover — point `DATABASE_URL` at it and you are done.

If you must self-manage, the shape is streaming replication plus a failover
manager (Patroni, or the CloudNativePG operator on Kubernetes) that owns leader
election and moves a stable endpoint across nodes. The application requirement is
the same either way: **`DATABASE_URL` must resolve to whatever is currently
primary**, without an app redeploy.

What the application must tolerate, whichever route you take:

- **Failover drops in-flight connections.** The pool must recycle them rather
  than serve errors from dead sockets — `pool_pre_ping` is what makes a stale
  connection get discarded instead of raising.
- **Read replicas are not a target for this library.** The auth path writes
  (usage counters, refresh-token rotation, audit events). Routing it at a
  read-only replica fails at runtime, not at startup.
- **Migrations run against the primary**, as a discrete step — see
  [Running Migrations](#running-migrations).

### Redis Sentinel (High Availability)

```yaml
# docker-compose.prod.yml
services:
  redis-master:
    image: redis:7.0-alpine
    command: redis-server --appendonly yes

  redis-slave1:
    image: redis:7.0-alpine
    command: redis-server --slaveof redis-master 6379 --appendonly yes

  redis-sentinel1:
    image: redis:7.0-alpine
    command: >
      redis-sentinel /etc/redis/sentinel.conf
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 5000
      --sentinel parallel-syncs mymaster 1
      --sentinel failover-timeout mymaster 10000
```

### Health Checks

**Application Health Endpoint**:

The library does not ship a health router — health is your application's
endpoint, since it owns the other dependencies too. Probe the database through
a real session:

```python
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}

@app.get("/health/ready")
async def readiness_check():
    """Readiness check (includes dependencies)"""
    try:
        async with auth.get_session() as session:
            await session.execute(text("SELECT 1"))

        # Check Redis only if it's actually configured
        if auth.config.redis_enabled:
            await auth.cache.redis_client.ping()

        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(503, f"Not ready: {str(e)}")

@app.get("/health/live")
async def liveness_check():
    """Liveness check (app is running)"""
    return {"status": "alive"}
```

Keep `/health/live` free of dependency checks. If liveness fails when Postgres
blips, Kubernetes restarts every pod during a database incident — turning a
recoverable outage into a crash loop. Dependencies belong in readiness, which
pulls a pod out of the load balancer without killing it.

To assert the *schema* is correct — not merely reachable — use
`outlabs-auth doctor` as a deploy-time check rather than a request-path probe.

---

## Monitoring & Observability

### Prometheus Metrics

**Install Dependencies**:
```bash
pip install prometheus-fastapi-instrumentator
```

**Configuration**:
```python
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI

app = FastAPI()

# Add Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Custom metrics
from prometheus_client import Counter, Histogram

login_counter = Counter('auth_logins_total', 'Total login attempts')
login_failures = Counter('auth_login_failures_total', 'Failed login attempts')
permission_check_duration = Histogram(
    'auth_permission_check_duration_seconds',
    'Permission check duration'
)

@app.post("/auth/login")
async def login(credentials: LoginRequest):
    login_counter.inc()
    try:
        tokens = await auth.auth_service.login(
            email=credentials.email,
            password=credentials.password
        )
        return tokens
    except InvalidCredentialsException:
        login_failures.inc()
        raise
```

**Scraping Configuration** (prometheus.yml):
```yaml
scrape_configs:
  - job_name: 'outlabs-auth'
    static_configs:
      - targets: ['app1:8000', 'app2:8000', 'app3:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Grafana Dashboards

**Key Metrics to Monitor**:
1. Request rate (requests/second)
2. Error rate (errors/second)
3. Response time (p50, p95, p99)
4. Login success/failure rate
5. Permission check duration
6. Database query time
7. Cache hit ratio
8. Active sessions

**Sample Grafana Dashboard JSON**: See appendix

### Logging

**Structured Logging**:
```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
```

**Log Aggregation** (ELK Stack):
```yaml
# docker-compose.monitoring.yml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
```

### Alerting

**Prometheus Alerts** (alerts.yml):
```yaml
groups:
  - name: outlabs_auth_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: HighLoginFailureRate
        expr: rate(auth_login_failures_total[5m]) > 10
        for: 2m
        annotations:
          summary: "High login failure rate"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        annotations:
          summary: "PostgreSQL is down"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        annotations:
          summary: "95th percentile response time > 1s"
```

---

## Backup & Recovery

### PostgreSQL Backup

On a managed instance, use the provider's automated backups and PITR — they are
better than a cron'd dump and do not compete with your database for I/O. The
script below is for self-managed deployments.

**Automated Backup Script**:
```bash
#!/bin/bash
# backup.sh
set -euo pipefail

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.dump"

mkdir -p "$BACKUP_DIR"

# Create backup. --format=custom is compressed and restores selectively.
# Credentials come from the environment / ~/.pgpass, never the command line.
pg_dump "$DATABASE_DSN" \
  --format=custom \
  --no-owner --no-privileges \
  --file="$BACKUP_FILE"

# Upload to S3
aws s3 cp "$BACKUP_FILE" "s3://backups/postgres/" --sse AES256

# Cleanup old backups (keep last 30 days)
find "$BACKUP_DIR" -name "backup_*.dump" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
```

Set `DATABASE_DSN` to a libpq URL (`postgresql://user@host:5432/appdb`) — note
this is the **plain libpq form, without the `+asyncpg` driver suffix** that
`DATABASE_URL` carries. `pg_dump` is a standard client and does not understand
the SQLAlchemy dialect prefix.

A dump only captures the database. If you have set `OUTLABS_AUTH_SCHEMA`, the
auth tables are inside that schema and are included in a full-database dump —
use `--schema=auth` if you want that schema alone.

**`pg_dump` is not point-in-time recovery.** A nightly dump means up to 24h of
loss. If that is unacceptable, run continuous WAL archiving (pgBackRest, WAL-G)
or use a managed provider's PITR.

**Cron Job**:
```bash
# Run daily at 2 AM
0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1
```

### Restore from Backup

```bash
#!/bin/bash
# restore.sh
set -euo pipefail

BACKUP_FILE=${1:-}

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore.sh <backup_file.dump>"
    exit 1
fi

# Download from S3
aws s3 cp "s3://backups/postgres/$BACKUP_FILE" .

# Restore. --clean --if-exists drops existing objects first.
# Stop the application before running this.
pg_restore \
  --dbname="$DATABASE_DSN" \
  --clean --if-exists \
  --no-owner --no-privileges \
  --jobs=4 \
  "$BACKUP_FILE"

echo "Restore completed"
```

After restoring, confirm the schema matches the running code before serving
traffic:

```bash
outlabs-auth doctor
outlabs-auth current   # must match `outlabs-auth heads`
```

A restore from an older dump can land the database on an **earlier Alembic
revision** than the deployed code expects. Run `outlabs-auth migrate` to bring
it back to head.

### Disaster Recovery Plan

1. **Regular Backups**: Daily automated backups
2. **Off-site Storage**: S3 or equivalent
3. **Tested Recovery**: Monthly restore tests
4. **Documentation**: Clear recovery procedures
5. **RTO/RPO Targets**:
   - RTO (Recovery Time Objective): 1 hour
   - RPO (Recovery Point Objective): 24 hours (daily backups)

---

## Security Hardening

### Network Security

**Firewall Rules**:
```bash
# Allow only necessary ports
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable
```

**Private Networking**:
- Keep PostgreSQL and Redis on a private network
- Don't expose 5432 or 6379 publicly
- Use VPN for administrative access

### Application Security

**Environment Variables**:
```bash
# Never commit these
# SECRET_KEY must be >= 32 chars under HS256 — construction fails otherwise
export SECRET_KEY="$(openssl rand -hex 32)"
export POSTGRES_PASSWORD="$(openssl rand -base64 32)"
export REDIS_PASSWORD="$(openssl rand -base64 32)"
```

**HTTPS Only**:
```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app.add_middleware(HTTPSRedirectMiddleware)
```

**Security Headers**:
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response
```

### Database Security

**PostgreSQL Authentication**:
```sql
-- Migration role: owns the schema, has DDL. Used by `outlabs-auth migrate`.
CREATE ROLE outlabs_auth_owner LOGIN PASSWORD 'REDACTED';
CREATE SCHEMA auth AUTHORIZATION outlabs_auth_owner;

-- Runtime role: what the application connects as. No DDL.
CREATE ROLE outlabs_auth_app LOGIN PASSWORD 'REDACTED';

GRANT USAGE ON SCHEMA auth TO outlabs_auth_app;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA auth TO outlabs_auth_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA auth TO outlabs_auth_app;

-- Keep the grant true for tables future migrations add.
ALTER DEFAULT PRIVILEGES FOR ROLE outlabs_auth_owner IN SCHEMA auth
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO outlabs_auth_app;
```

Splitting the roles means a leaked application credential cannot drop or alter
the auth schema. Ensure `pg_hba.conf` requires `scram-sha-256` and never
`trust` for non-local connections.

**TLS/SSL**:

TLS is configured in the URL; asyncpg honours the standard parameters:

```python
auth = EnterpriseRBAC(
    database_url=(
        "postgresql+asyncpg://outlabs_auth_app:PASSWORD@db.internal:5432/appdb"
        "?ssl=verify-full"
    ),
    secret_key=SECRET_KEY,
)
```

Use `ssl=verify-full`. It validates the certificate chain **and** the hostname;
`ssl=require` encrypts the connection but authenticates nothing, so it does not
stop an active MITM. For a private CA, point at the root cert:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@db.internal:5432/appdb?ssl=verify-full&sslrootcert=/path/to/ca.pem"
```

---

## Troubleshooting

### Common Issues

#### High Memory Usage

**Symptoms**: OOM kills, slow performance

**Diagnosis**:
```bash
# Check memory usage
kubectl top pods -n outlabs-auth

# Check memory leaks
python -m memory_profiler app.py
```

**Solutions**:
- Increase memory limits
- Fix memory leaks
- Optimize queries
- Add caching

#### Database Connection Issues

**Symptoms**: Connection refused, timeout errors

**Diagnosis**:
```bash
# The single best first command — checks connectivity, schema,
# the version table, revision state, and core tables in one pass.
outlabs-auth doctor

# Test raw connectivity (libpq form — no +asyncpg suffix)
psql "postgresql://user@host:5432/appdb" -c "SELECT 1"
```

```sql
-- Connection count vs the server limit
SELECT count(*) FROM pg_stat_activity;
SHOW max_connections;

-- Who is holding connections
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
```

**Solutions**:
- Check network connectivity and that TLS settings match the server
- Verify credentials and `pg_hba.conf` rules
- **Check total pool demand**: `replicas x (pool_size + max_overflow)` must stay
  under `max_connections`. "Too many connections" is usually too many pools, not
  too small a pool — adding replicas makes it worse. Put PgBouncer in front.
- Confirm the URL uses the `postgresql+asyncpg://` scheme; a bare
  `postgresql://` will try to load a sync driver

#### Schema / Migration Issues

**Symptoms**: `UndefinedTableError`, `UndefinedColumnError`, or errors naming a
column that exists in the code but not the database.

**Diagnosis**:
```bash
outlabs-auth current   # revision the database is on
outlabs-auth heads     # revision the installed code expects
outlabs-auth doctor
```

**Solutions**:
- If `current` lags `heads`, code shipped ahead of its schema — run
  `outlabs-auth migrate`
- If the schema exists but was never stamped, use
  `outlabs-auth adopt-existing-schema`
- Remember the auth history is tracked in `outlabs_auth_alembic_version`, and
  your application's `alembic upgrade head` does **not** advance it — the auth
  migration is its own deploy step

#### Slow Performance

**Symptoms**: High response times, timeouts

**Diagnosis**:
```sql
-- Currently blocked queries and what they're waiting on
SELECT pid, state, wait_event_type, wait_event, left(query, 80)
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY query_start;

-- Slowest statements (requires the pg_stat_statements extension)
SELECT calls, round(mean_exec_time::numeric, 2) AS avg_ms, left(query, 80)
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Solutions**:
- If you see many connections with `wait_event_type=Lock, wait_event=tuple` all
  on `UPDATE api_keys SET ... usage_count ...`, that is the API-key hot-row
  contention described under
  [Background Sync for API Keys](#background-sync-for-api-keys-v14---dd-033).
  **Enable Redis** — scaling out workers cannot fix it, because the contention is
  on a single Postgres row.
- Confirm the schema is at head (`outlabs-auth doctor`) — the migrations carry
  the library's index work; a lagging schema can be missing indexes entirely
- Enable caching (`redis_url` + `redis_key_prefix`)
- Scale horizontally, *after* confirming the bottleneck is not a single row

---

## Production Checklist

### Pre-Deployment

- [ ] All tests passing
- [ ] Security audit reviewed (see `docs/SECURITY_AUDIT_2026-06-10.md` and
      `docs/ARCHITECTURE_SECURITY_PERFORMANCE_AUDIT_2026-07-15.md`)
- [ ] Load testing completed
- [ ] `SECRET_KEY` is >= 32 chars and unique per environment
- [ ] `DATABASE_URL` uses `postgresql+asyncpg://` and `ssl=verify-full`
- [ ] Auth schema migrated with `outlabs-auth migrate` as a discrete deploy step
- [ ] `auto_migrate` is **off** in production
- [ ] `outlabs-auth doctor` green; `current` == `heads`
- [ ] `OUTLABS_AUTH_SCHEMA` set if isolating auth tables
- [ ] `redis_key_prefix` set and unique per app+environment (if Redis is on)
- [ ] Before first enabling Redis: audited `rate_limit_per_minute` on every row
      in `api_keys` (the limiter is a silent no-op without Redis — see
      [Background Sync for API Keys](#background-sync-for-api-keys-v14---dd-033))
- [ ] Total connection demand (`replicas x pool`) under `max_connections`
- [ ] Backup strategy in place, and a restore actually tested
- [ ] Monitoring configured
- [ ] Secrets properly managed
- [ ] HTTPS configured
- [ ] Error handling tested

### Post-Deployment

- [ ] Health checks passing
- [ ] Metrics flowing to Prometheus
- [ ] Logs aggregated in ELK/CloudWatch
- [ ] Alerts configured
- [ ] Backup job running
- [ ] SSL certificate valid
- [ ] Performance acceptable
- [ ] Zero downtime deployment works
- [ ] Rollback tested
- [ ] Documentation updated

### Ongoing Operations

- [ ] Monitor metrics daily
- [ ] Review logs weekly
- [ ] Test backups monthly
- [ ] Security updates quarterly
- [ ] Performance review quarterly
- [ ] Disaster recovery drill annually

---

## Appendix

### Sample Grafana Dashboard

```json
{
  "dashboard": {
    "title": "OutlabsAuth Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

### Useful Commands

```bash
# Docker
docker logs -f <container-id>
docker exec -it <container-id> /bin/bash
docker stats

# Kubernetes
kubectl get pods -n outlabs-auth
kubectl logs -f deployment/outlabs-auth-app -n outlabs-auth
kubectl describe pod <pod-name> -n outlabs-auth
kubectl exec -it <pod-name> -n outlabs-auth -- /bin/bash

# OutlabsAuth CLI (reads DATABASE_URL + OUTLABS_AUTH_SCHEMA from env)
outlabs-auth doctor              # connectivity, schema, revision, core tables
outlabs-auth migrate             # apply migrations to head
outlabs-auth current             # revision the database is on
outlabs-auth heads               # revision the code expects
outlabs-auth history             # full revision history
outlabs-auth downgrade           # step back a revision
outlabs-auth seed-system         # seed system permissions/config
outlabs-auth bootstrap-admin     # create the initial admin user
outlabs-auth adopt-existing-schema  # stamp an already-populated schema
outlabs-auth run-maintenance     # one-off maintenance pass
outlabs-auth --version

# PostgreSQL
psql "postgresql://user@host:5432/appdb"
\dt auth.*                       # list auth tables (if using a schema)
SELECT * FROM pg_stat_activity;
SELECT count(*) FROM pg_stat_activity;

# Redis
redis-cli
INFO
MONITOR
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.4 | 2025-01-14 | Added Redis Pub/Sub for cache invalidation (DD-037); added background sync for API keys (DD-033); added Redis Sentinel configuration; updated monitoring for new features |
| 1.0 | 2025-01-14 | Initial deployment guide |

---

**Last Updated**: 2025-01-14 (v1.4 - Added Redis Pub/Sub and background sync sections)
**Next Review**: Quarterly
**Owner**: DevOps Team
