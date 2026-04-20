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
│   MongoDB      │  (Shared database)
└───────┬────────┘
        │
┌───────▼────────┐
│   Redis        │  (Shared cache - optional)
└────────────────┘
```

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

- **Python**: 3.11+
- **MongoDB**: 6.0+
- **Redis**: 7.0+ recommended for production API-key counters, rate limits, and permission caching
- **Docker**: 24.0+ (for containerized deployments)
- **Kubernetes**: 1.28+ (for K8s deployments)

---

## Docker Deployment

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
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
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mongodb://mongodb:27017/outlabs_auth
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
      - ENVIRONMENT=development
    depends_on:
      - mongodb
      - redis
    volumes:
      - ./:/app
    restart: unless-stopped

  mongodb:
    image: mongo:6.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_PASSWORD}
    restart: unless-stopped

  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  mongo_data:
  redis_data:
```

### Docker Compose (Production)

```yaml
# docker-compose.prod.yml
version: '3.8'

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
      - DATABASE_URL=mongodb://mongodb:27017/outlabs_auth
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
      - ENVIRONMENT=production
    depends_on:
      - mongodb
      - redis
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3

  mongodb:
    image: mongo:6.0
    volumes:
      - /data/mongodb:/data/db
    environment:
      - MONGO_INITDB_ROOT_USERNAME=${MONGO_USERNAME}
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_PASSWORD}
    restart: always
    command: mongod --auth --replSet rs0

  redis:
    image: redis:7.0-alpine
    volumes:
      - /data/redis:/data
    restart: always
    command: redis-server --appendonly yes
```

### Building and Running

```bash
# Build image
docker build -t outlabs-auth-app:latest .

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f app

# Scale app instances
docker-compose up -d --scale app=3

# Stop services
docker-compose down

# Production deployment
docker-compose -f docker-compose.prod.yml up -d
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
  DATABASE_URL: "mongodb://mongodb-service:27017/outlabs_auth"
  REDIS_URL: "redis://redis-service:6379"
  LOG_LEVEL: "INFO"
```

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
  SECRET_KEY: <base64-encoded-secret-key>
  MONGO_USERNAME: <base64-encoded-username>
  MONGO_PASSWORD: <base64-encoded-password>
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
  --from-literal=MONGO_USERNAME=$MONGO_USERNAME \
  --from-literal=MONGO_PASSWORD=$MONGO_PASSWORD

# Apply configurations
kubectl apply -f configmap.yaml
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
```python
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(
    DATABASE_URL,
    maxPoolSize=50,        # Max connections
    minPoolSize=10,        # Min connections
    maxIdleTimeMS=45000,   # Close idle connections after 45s
    serverSelectionTimeoutMS=3000
)
```

**Indexes** (critical for performance):
```python
# Create indexes on startup
async def create_indexes():
    # User indexes
    await UserModel.get_motor_collection().create_index("email", unique=True)
    await UserModel.get_motor_collection().create_index("is_active")

    # Role indexes
    await RoleModel.get_motor_collection().create_index("name")
    await RoleModel.get_motor_collection().create_index("is_global")

    # Entity indexes (EnterpriseRBAC)
    await EntityModel.get_motor_collection().create_index("slug", unique=True)
    await EntityModel.get_motor_collection().create_index("parent_entity")
    await EntityModel.get_motor_collection().create_index("entity_class")
```

### Caching Strategy

**Redis Configuration**:
```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=db,
    redis_url="redis://redis:6379",
    cache_ttl_seconds=300  # 5 minutes
)
```

`redis_url` enables both Redis counters and the permission cache by default. If
you need Redis counters/rate limits but want to disable permission caching while
debugging an integration, pass `enable_caching=False` explicitly.

For API-key protected FastAPI routes that use
`auth.deps.require_permission(...)`, Redis cache mode also enables a short-lived
compiled auth snapshot. The warm path validates the API key, scopes, owner
permissions, usage counter, and rate limits from Redis without issuing SQL for
non-ABAC, non-entity permission dependencies. The default snapshot TTL is 60
seconds and can be tuned with `api_key_auth_snapshot_ttl`. Snapshots also carry
Redis version counters for global RBAC state, user state, integration-principal
state, and entity state. Role, permission, membership, user status,
integration-principal, and API-key lifecycle mutations invalidate matching warm
snapshots before the TTL expires.

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
    database=db,
    redis_url="redis://redis:6379",
    cache_ttl_seconds=300
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
      - mongodb

  app2:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - ENABLE_PUBSUB_INVALIDATION=true
    depends_on:
      - redis
      - mongodb

  app3:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - ENABLE_PUBSUB_INVALIDATION=true
    depends_on:
      - redis
      - mongodb

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
```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=db,
    redis_url="redis://redis-master:6379",
    redis_sentinel_hosts=[
        ("redis-sentinel-1", 26379),
        ("redis-sentinel-2", 26379),
        ("redis-sentinel-3", 26379)
    ],
    redis_sentinel_master="mymaster",
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
    database=db,
    redis_url="redis://redis:6379",  # Enables Redis counters + permission cache
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

### MongoDB Replica Set

**Configuration**:
```yaml
# docker-compose.prod.yml
services:
  mongodb-primary:
    image: mongo:6.0
    command: mongod --replSet rs0 --bind_ip_all
    volumes:
      - mongo_data_primary:/data/db

  mongodb-secondary1:
    image: mongo:6.0
    command: mongod --replSet rs0 --bind_ip_all
    volumes:
      - mongo_data_secondary1:/data/db

  mongodb-secondary2:
    image: mongo:6.0
    command: mongod --replSet rs0 --bind_ip_all
    volumes:
      - mongo_data_secondary2:/data/db
```

**Initialize Replica Set**:
```javascript
// Connect to primary
mongo mongodb://mongodb-primary:27017

// Initialize replica set
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongodb-primary:27017", priority: 2 },
    { _id: 1, host: "mongodb-secondary1:27017", priority: 1 },
    { _id: 2, host: "mongodb-secondary2:27017", priority: 1 }
  ]
})

// Check status
rs.status()
```

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
```python
from fastapi import FastAPI

@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}

@app.get("/health/ready")
async def readiness_check():
    """Readiness check (includes dependencies)"""
    try:
        # Check database
        await auth.health.check_database()

        # Check Redis (if enabled)
        if auth.config.enable_caching:
            await auth.health.check_redis()

        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(503, f"Not ready: {str(e)}")

@app.get("/health/live")
async def liveness_check():
    """Liveness check (app is running)"""
    return {"status": "alive"}
```

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
        expr: up{job="mongodb"} == 0
        for: 1m
        annotations:
          summary: "MongoDB is down"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        annotations:
          summary: "95th percentile response time > 1s"
```

---

## Backup & Recovery

### MongoDB Backup

**Automated Backup Script**:
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$DATE"

# Create backup
mongodump \
  --uri="mongodb://username:password@localhost:27017/outlabs_auth" \
  --out="$BACKUP_PATH"

# Compress backup
tar -czf "$BACKUP_PATH.tar.gz" "$BACKUP_PATH"
rm -rf "$BACKUP_PATH"

# Upload to S3
aws s3 cp "$BACKUP_PATH.tar.gz" "s3://backups/mongodb/" --sse AES256

# Cleanup old backups (keep last 30 days)
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_PATH.tar.gz"
```

**Cron Job**:
```bash
# Run daily at 2 AM
0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1
```

### Restore from Backup

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore.sh <backup_file.tar.gz>"
    exit 1
fi

# Download from S3
aws s3 cp "s3://backups/mongodb/$BACKUP_FILE" .

# Extract backup
tar -xzf "$BACKUP_FILE"

# Restore to MongoDB
mongorestore \
  --uri="mongodb://username:password@localhost:27017/outlabs_auth" \
  --drop \
  backup_*

echo "Restore completed"
```

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
- Keep MongoDB and Redis on private network
- Don't expose database ports publicly
- Use VPN for administrative access

### Application Security

**Environment Variables**:
```bash
# Never commit these
export SECRET_KEY="$(openssl rand -hex 32)"
export MONGO_PASSWORD="$(openssl rand -base64 32)"
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

**MongoDB Authentication**:
```javascript
// Create admin user
use admin
db.createUser({
  user: "admin",
  pwd: passwordPrompt(),
  roles: [{ role: "root", db: "admin" }]
})

// Create application user
use outlabs_auth
db.createUser({
  user: "outlabs_auth_app",
  pwd: passwordPrompt(),
  roles: [{ role: "readWrite", db: "outlabs_auth" }]
})
```

**TLS/SSL**:
```python
client = AsyncIOMotorClient(
    DATABASE_URL,
    tls=True,
    tlsCAFile="/path/to/ca.pem",
    tlsCertificateKeyFile="/path/to/client.pem"
)
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
# Test MongoDB connection
mongosh mongodb://localhost:27017

# Check connection pool
db.serverStatus().connections
```

**Solutions**:
- Check network connectivity
- Verify credentials
- Increase connection pool size
- Check MongoDB status

#### Slow Performance

**Symptoms**: High response times, timeouts

**Diagnosis**:
```python
# Enable query profiling
db.setProfilingLevel(1, { slowms: 100 })

# View slow queries
db.system.profile.find().sort({ ts: -1 }).limit(10)
```

**Solutions**:
- Add database indexes
- Enable caching
- Optimize queries
- Scale horizontally

---

## Production Checklist

### Pre-Deployment

- [ ] All tests passing (90%+ coverage)
- [ ] Security audit completed
- [ ] Load testing completed
- [ ] Database indexes created
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Secrets properly managed
- [ ] HTTPS configured
- [ ] Rate limiting enabled
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

# MongoDB
mongosh "mongodb://localhost:27017"
db.serverStatus()
db.currentOp()

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
