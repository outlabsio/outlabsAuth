# Docker Development Environment

Complete Docker Compose stack for OutlabsAuth development, testing, and observability.

## What's Included

This unified stack includes everything you need to run OutlabsAuth examples with full observability:

### Infrastructure
- **MongoDB** (port 27018) - Shared database for all examples
- **Redis** (port 6380) - Caching and activity tracking  
- **Prometheus** (port 9090) - Metrics collection from example apps
- **Grafana** (port 3011) - Pre-configured dashboards and visualization

### Example Applications
- **SimpleRBAC** (port 8003) - Blog API demonstrating flat RBAC + observability

**Note**: Ports 27018 and 6380 are used to avoid conflicts with local MongoDB and Redis instances.

## Quick Start

### Start Everything

```bash
# From the project root
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### Start Specific Services

```bash
# Just infrastructure (MongoDB + Redis)
docker-compose up -d mongodb redis

# Infrastructure + Observability stack
docker-compose up -d mongodb redis prometheus grafana

# Just SimpleRBAC example
docker-compose up -d mongodb redis simple-rbac

# Just Observability demo
docker-compose up -d mongodb redis observability-app prometheus grafana
```

## Access the Services

| Service | URL | Credentials | Notes |
|---------|-----|-------------|-------|
| **SimpleRBAC API** | http://localhost:8003 | N/A | Blog example with flat RBAC + observability |
| **SimpleRBAC Docs** | http://localhost:8003/docs | N/A | OpenAPI documentation |
| **SimpleRBAC Metrics** | http://localhost:8003/metrics | N/A | Prometheus metrics endpoint |
| **Prometheus** | http://localhost:9090 | N/A | Metrics and queries |
| **Grafana** | http://localhost:3011 | admin / admin | Dashboards and visualization |
| **MongoDB** | localhost:27018 | N/A | Direct database access |
| **Redis** | localhost:6380 | N/A | Direct cache access |

## Example Workflows

### 1. Test SimpleRBAC with Observability

```bash
# Start the stack
docker compose up -d

# Wait for services to be ready (15 seconds)
sleep 15

# Register a user
curl -X POST http://localhost:8003/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "DemoPass123!",
    "first_name": "Demo",
    "last_name": "User"
  }'

# Login (generates metrics)
curl -X POST http://localhost:8003/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "DemoPass123!"
  }'

# View metrics in Grafana
# Open http://localhost:3011 → Dashboards → OutlabsAuth Overview
```

### 2. View Prometheus Metrics

```bash
# Check raw metrics from SimpleRBAC
curl http://localhost:8003/metrics

# View in Prometheus UI
# Open http://localhost:9090 → Graph
# Try queries:
#   - outlabs_auth_login_attempts_total
#   - outlabs_auth_permission_checks_total
#   - outlabs_auth_active_sessions
```

### 3. Development with Hot Reload

The SimpleRBAC app mounts source code as volumes, so changes are reflected immediately:

```bash
# Start in development mode
docker compose up simple-rbac

# Edit code in outlabs_auth/ or examples/simple_rbac/
# Changes are automatically reloaded by uvicorn

# View logs to see reload
docker compose logs -f simple-rbac
```

### 4. Create Blog Posts

```bash
# Get access token after registering/logging in
TOKEN="your_access_token_here"

# Create a blog post
curl -X POST http://localhost:8003/posts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "This is my first blog post!",
    "status": "published",
    "tags": ["intro", "welcome"]
  }'

# List all posts (public)
curl http://localhost:8003/posts
```

## Environment Variables

Configure apps via environment variables in `docker-compose.yml`:

### SimpleRBAC Example

```yaml
environment:
  - MONGODB_URL=mongodb://mongodb:27017
  - DATABASE_NAME=blog_simple_rbac  # Separate DB for SimpleRBAC
  - REDIS_URL=redis://redis:6379
  - SECRET_KEY=simple-rbac-secret-key-change-in-production
  - ENV=development  # development or production
```

### Observability Demo

```yaml
environment:
  - MONGODB_URL=mongodb://mongodb:27017
  - DATABASE_NAME=observability_demo  # Separate DB for demo
  - REDIS_URL=redis://redis:6379
  - SECRET_KEY=observability-secret-key-change-in-production
  - ENV=production  # Uses production observability preset (JSON logs)
```

## Databases

The SimpleRBAC example uses the `blog_simple_rbac` database on the shared MongoDB instance.

When additional examples are added (like EnterpriseRBAC), each will use a separate database to avoid data conflicts.

## Grafana Dashboard

The stack includes a pre-configured Grafana dashboard:

1. **Open Grafana**: http://localhost:3011
2. **Login**: admin / admin (change password on first login)
3. **Go to**: Dashboards → OutlabsAuth Overview
4. **View**:
   - Login success/failure rates
   - Permission check performance
   - Active sessions
   - Permission check trends

The dashboard shows metrics from the SimpleRBAC example app.

## Troubleshooting

### Services won't start

```bash
# Check logs for errors
docker-compose logs mongodb
docker-compose logs redis
docker-compose logs simple-rbac

# Restart a specific service
docker-compose restart simple-rbac

# Rebuild after code changes
docker-compose up -d --build simple-rbac
```

### Port conflicts

If ports are already in use, you can change them in `docker-compose.yml`:

```yaml
ports:
  - "8004:8003"  # Change host port from 8003 to 8004
```

### Database connection errors

```bash
# Check MongoDB is healthy
docker-compose ps mongodb

# Should show "healthy" status
# If not, check logs:
docker-compose logs mongodb
```

### No metrics in Grafana

1. **Wait 30 seconds** for Prometheus to scrape
2. **Generate traffic**: Make some API requests to the apps
3. **Check Prometheus targets**: http://localhost:9090/targets
   - `simple-rbac` should be **UP**
4. **Verify metrics endpoint**: 
   ```bash
   curl http://localhost:8003/metrics | grep outlabs_auth
   ```

### Hot reload not working

```bash
# Ensure volumes are mounted correctly
docker-compose config | grep volumes

# Restart with fresh build
docker-compose up -d --build simple-rbac
```

## Cleanup

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes all data!)
docker-compose down -v

# Remove only specific service data
docker volume rm outlabs-mongodb-data
docker volume rm outlabs-redis-data
```

## Production Deployment

**DO NOT use this docker-compose.yml in production!**

For production:

1. **Use managed services** (AWS RDS, MongoDB Atlas, ElastiCache)
2. **Change all default passwords** and secrets
3. **Enable authentication** on Prometheus and Grafana
4. **Use HTTPS** with reverse proxy
5. **Set up proper logging** (CloudWatch, ELK, Datadog)
6. **Configure resource limits** and health checks
7. **Use docker-compose.prod.yml** with production settings

See [`DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) for production best practices.

## Architecture

```
    ┌─────────────────┐
    │  SimpleRBAC     │
    │  Example :8003  │
    └────────┬────────┘
             │
             │ Uses
             ▼
    ┌─────────────────┐
    │  MongoDB:27018  │
    │  Redis:6380     │
    └─────────────────┘
             │
             │ Emits /metrics
             ▼
    ┌─────────────────┐
    │ Prometheus:9090 │
    │ (Scrapes :8003) │
    └────────┬────────┘
             │
             │ Queries
             ▼
      ┌─────────────┐
      │ Grafana     │
      │  :3011      │
      └─────────────┘
```

## Next Steps

- **Try SimpleRBAC**: See [`examples/simple_rbac/README.md`](examples/simple_rbac/README.md)
- **View Observability Docs**: See [`docs-library/97-Observability.md`](docs-library/97-Observability.md)
- **View Metrics Reference**: See [`docs-library/98-Metrics-Reference.md`](docs-library/98-Metrics-Reference.md)
- **Check Roadmap**: See [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md)

## Support

- **GitHub Issues**: https://github.com/your-org/outlabs-auth/issues
- **Documentation**: `docs-library/` folder
- **Examples**: `examples/` folder
