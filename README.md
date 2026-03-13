# OutlabsAuth

**FastAPI authentication and authorization library with RBAC**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://www.postgresql.org/)
[![Distribution: Private](https://img.shields.io/badge/distribution-private-orange.svg)](#installation)
[![Stage: Alpha](https://img.shields.io/badge/stage-alpha-red.svg)](#development-status)

> **Alpha release** - internal multi-project distribution is now versioned, but the library and admin UI are still in active iteration.

## Overview

OutlabsAuth is a comprehensive authentication and authorization library for FastAPI applications. It is intended for private distribution across internal projects and integrates directly into your application; no separate auth service is required.

**Inspired by [FastAPI-Users](https://github.com/fastapi-users/fastapi-users)**: We've adopted their battle-tested patterns (lifecycle hooks, router factories, transport/strategy) while adding advanced authorization features like hierarchical permissions, tree permissions, and context-aware roles.

### Key Features

**Authorization (Unique to OutlabsAuth)**:
- **Two Presets**: SimpleRBAC (flat) or EnterpriseRBAC (hierarchical)
- **Hierarchical Permissions**: Tree permissions with O(1) ancestor queries (closure table)
- **Context-Aware Roles**: Permissions adapt based on organizational context
- **Entity System**: STRUCTURAL vs ACCESS_GROUP for flexible org modeling

**Authentication (Inspired by FastAPI-Users)**:
- **JWT Authentication**: Access + refresh tokens with optional rotation
- **API Key Authentication**: SHA-256 hashing (fast, secure for high-entropy secrets), rate limiting, IP whitelisting
- **Multi-Source Auth**: JWT, API keys, service tokens, superuser, anonymous
- **Lifecycle Hooks**: 20+ overrideable hooks (on_after_register, on_after_login, etc.)
- **Router Factories**: Pre-built FastAPI routers for rapid setup

**Developer Experience**:
- **FastAPI Native**: Designed specifically for FastAPI with dependency injection
- **Production-Oriented**: Redis caching, Pub/Sub invalidation, comprehensive security
- **Extensible**: Override services, add custom hooks, create custom transports
- **Observability**: Prometheus metrics, structured logging, correlation IDs

## Quick Start

### Installation

For private distribution with `uv`, use one of these patterns. For the current
internal projects, private Git tags are the default because they are the
lowest-friction option for a small team.

```toml
# Private package index (optional)
[project]
dependencies = ["outlabs-auth>=0.1.0a5,<0.2"]

[tool.uv.sources]
outlabs-auth = { index = "outlabs-private" }

[[tool.uv.index]]
name = "outlabs-private"
url = "https://<your-registry>/simple/"
publish-url = "https://<your-registry>/"
explicit = true
```

```toml
# Private Git source
[project]
dependencies = ["outlabs-auth"]

[tool.uv.sources]
outlabs-auth = { git = "ssh://git@github.com/<org>/outlabsAuth.git", tag = "v0.1.0a5" }
```

See [docs/PRIVATE_RELEASE.md](./docs/PRIVATE_RELEASE.md) for the release workflow. Run `uv run python scripts/release_version.py check` to verify the library version, UI version, and release docs stay aligned before you tag a release.

### Consumer Database Bootstrap

OutlabsAuth owns its own schema lifecycle. A host application should install the
library and then run these steps against the target database before expecting
the mounted routers or services to work:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mydb \
OUTLABS_AUTH_SCHEMA=outlabs_auth \
uv run outlabs-auth migrate

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mydb \
OUTLABS_AUTH_SCHEMA=outlabs_auth \
uv run outlabs-auth seed-system

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mydb \
OUTLABS_AUTH_SCHEMA=outlabs_auth \
uv run outlabs-auth bootstrap-admin \
  --email admin@example.com \
  --password 'ChangeMe123!'
```

`migrate` manages only the auth schema, `seed-system` provisions the library-owned
permission catalog and config defaults, and `bootstrap-admin` creates the first
superuser exactly once.

If you are migrating a host app that previously bootstrapped auth tables with
`create_all`, `migrate` will automatically adopt a fully bootstrapped legacy
schema by stamping `outlabs_auth_alembic_version` before future migrations run.

### Development Setup

For local development, use the interactive service launcher:

```bash
uv run start.py
```

Select services with arrow keys, space to toggle, enter to start:
- **simple** - SimpleRBAC API (port 8000)
- **enterprise** - EnterpriseRBAC API (port 8000)
- **ui** - Admin UI (port 3000)
- **obs** - Observability stack (Grafana, Prometheus, Loki)

### Code Quality

```bash
# Lint
uv run ruff check .

# Auto-fix lint issues where safe
uv run ruff check . --fix

# Format Python code
uv run black .
```

### Simple RBAC Example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlmodel import SQLModel
from outlabs_auth import SimpleRBAC

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mydb"
SECRET_KEY = "your-secret-key"
auth: SimpleRBAC = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global auth
    auth = SimpleRBAC(database_url=DATABASE_URL, secret_key=SECRET_KEY)
    await auth.initialize()
    async with auth.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await auth.shutdown()

app = FastAPI(lifespan=lifespan)

# Assign role to user (uses UserRoleMembership table)
await auth.role_service.assign_role(
    user_id=user.id,
    role_id=admin_role.id,
    assigned_by=current_user.id
)

# Protected route
@app.get("/users/me")
async def get_me(user = Depends(lambda: auth.deps.authenticated())):
    return {"id": str(user.id), "email": user.email}

# Permission-protected route
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    _ = Depends(lambda: auth.deps.require_permission("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"success": True}
```

**Note**: SimpleRBAC uses a `UserRoleMembership` table for role assignment, providing audit trails and time-based access control even in the simple preset. This makes migration to EnterpriseRBAC seamless. See [DD-047](docs/DESIGN_DECISIONS.md#dd-047-userrolemembership-table-for-simplerbac) for rationale.

### Enterprise RBAC Example

```python
from outlabs_auth import EnterpriseRBAC

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mydb"
SECRET_KEY = "your-secret-key"

# Enable entity hierarchy + optional features
auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    enable_context_aware_roles=True,  # Permissions adapt by entity type
    enable_abac=True,                 # Attribute-based conditions
    redis_enabled=True,               # Enable Redis features
    redis_url="redis://localhost:6379"
)

# Create hierarchical entities
org = await auth.entity_service.create_entity(
    name="acme_corp",
    entity_class="structural",
    entity_type="organization"
)

dept = await auth.entity_service.create_entity(
    name="engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=org.id
)

# Assign user with multiple roles
await auth.membership_service.add_member(
    entity_id=dept.id,
    user_id=user.id,
    role_ids=[manager_role.id, developer_role.id]
)

# Entity-scoped permission check
@app.put("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    ctx = Depends(deps.require_entity_permission(entity_id, "entity:update"))
):
    return await auth.entity_service.update(entity_id, data)
```

## Architecture

### Unified Core

OutlabsAuth has a **single core implementation** with thin convenience wrappers:

```
OutlabsAuth (Core)
    ├── SimpleRBAC (5-10 LOC wrapper)
    └── EnterpriseRBAC (10 LOC wrapper)
```

All features are controlled by configuration flags - no code duplication.

### Decision Tree

```
Do you have departments/teams/organizational hierarchy?
├─ NO  → SimpleRBAC (flat structure)
└─ YES → EnterpriseRBAC (hierarchy + optional advanced features)
```

## Features by Preset

### SimpleRBAC
- ✅ User management
- ✅ Flat role assignment (one role per user)
- ✅ Permission checking
- ✅ JWT authentication
- ✅ API key authentication
- ✅ Multi-source auth
- ✅ Rate limiting

### EnterpriseRBAC (Includes all SimpleRBAC features +)
- ✅ Entity hierarchy (organizational structure)
- ✅ Multiple roles per user (via entity memberships)
- ✅ Tree permissions (`resource:action_tree`)
- ✅ Closure table (O(1) ancestor/descendant queries)
- ✅ Context-aware roles (opt-in)
- ✅ ABAC conditions (opt-in)
- ✅ Redis caching (opt-in)
- ✅ Multi-tenant support (opt-in)

## Authentication Methods

### JWT Tokens
```python
# Login
tokens = await auth.auth_service.login("user@example.com", "password")
# Returns: TokenPair(access_token, refresh_token)

# Refresh
new_tokens = await auth.auth_service.refresh_access_token(refresh_token)

# Logout
await auth.auth_service.logout(refresh_token)
```

### API Keys
```python
# Create API key
raw_key, key_model = await auth.api_key_service.create_api_key(
    name="production_api",
    owner_id=user_id,
    scopes=["user:read", "entity:read"],
    rate_limit_per_minute=100,
    ip_whitelist=["10.0.0.0/8"]  # Optional
)

# ⚠️ Save raw_key securely - it's only shown once!

# Verify API key
api_key, usage = await auth.api_key_service.verify_api_key(
    raw_key,
    required_scope="user:read",
    ip_address=request.client.host
)

# Use in requests
headers = {"X-API-Key": raw_key}
```

### JWT Service Tokens
```python
# For internal microservices (~0.5ms authentication)
service_token = await auth.service_token_service.create_service_token(
    service_name="email_service",
    permissions=["email:send"],
    expires_days=365
)
```

## Permission System

### Basic Permissions
```python
# Entity-specific: resource:action
"user:create"     # Create users in this entity
"user:read"       # Read users in this entity
"user:update"     # Update users in this entity
"user:delete"     # Delete users in this entity
```

### Tree Permissions (EnterpriseRBAC only)
```python
# Tree: resource:action_tree (applies to descendants only)
"entity:create_tree"  # Create entities anywhere in subtree
"entity:update_tree"  # Update entities anywhere in subtree
"user:manage_tree"    # Manage users in all descendant entities

# To manage BOTH an entity AND its descendants:
role.permissions = [
    "entity:update",       # Update this entity
    "entity:update_tree"   # Update all descendants
]
```

### Context-Aware Roles (EnterpriseRBAC optional)
```python
# Permissions adapt based on entity type
regional_manager = await auth.role_service.create_role(
    name="regional_manager",
    permissions=["entity:read", "user:read"],  # Default
    entity_type_permissions={
        "region": [
            "entity:manage_tree",      # Full control in regions
            "user:manage_tree",
            "budget:approve"
        ],
        "office": ["entity:read", "user:read"],  # Read-only in offices
        "team": ["entity:read"]                  # Minimal in teams
    }
)
```

### ABAC Conditions (EnterpriseRBAC optional)
```python
# Attribute-based access control
invoice_approval = await auth.permission_service.create_permission(
    name="invoice:approve",
    conditions=[
        {
            "attribute": "resource.value",
            "operator": "LESS_THAN_OR_EQUAL",
            "value": 50000  # Can only approve invoices ≤ $50k
        }
    ]
)

# Check with resource attributes
result = await auth.permission_service.check_permission_with_context(
    user_id=user.id,
    permission="invoice:approve",
    entity_id=entity.id,
    resource_attributes={"value": 35000}  # ✅ Passes
)
```

## Performance

### v1.4 Performance Features

- **Closure Table**: O(1) tree queries (20x improvement over recursive)
- **Redis Counters**: 99%+ reduction in DB writes for API keys
- **Redis Pub/Sub**: <100ms cache invalidation across all instances
- **JWT Service Tokens**: ~0.5ms authentication (zero DB hits)

### Benchmarks

| Operation | Without Optimizations | With v1.4 |
|-----------|---------------------|-----------|
| Tree permission check | 100ms (10 queries) | 5ms (1 query) |
| API key usage tracking | 1 DB write per use | 1 write per 5 min |
| Cache invalidation | Manual/periodic | <100ms automatic |
| Service auth | 5-10ms (DB lookup) | ~0.5ms (JWT only) |

## Documentation

### Design Specifications (`docs/`)

System design and architectural decisions for maintainers:

- **[REDESIGN_VISION.md](docs/REDESIGN_VISION.md)** - Project vision and goals
- **[LIBRARY_ARCHITECTURE.md](docs/LIBRARY_ARCHITECTURE.md)** - Technical architecture
- **[API_DESIGN.md](docs/API_DESIGN.md)** - Code examples and patterns
- **[COMPARISON_MATRIX.md](docs/COMPARISON_MATRIX.md)** - Feature comparison
- **[DEPENDENCY_PATTERNS.md](docs/DEPENDENCY_PATTERNS.md)** - FastAPI dependencies
- **[SECURITY.md](docs/SECURITY.md)** - Security hardening
- **[TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** - Testing strategies
- **[DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)** - Production deployment
- **[DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)** - Architectural decisions (DD-001 to DD-037+)

### User Documentation (`docs-library/`)

Implementation-specific documentation (9 files):

- **[12-Data-Models.md](docs-library/12-Data-Models.md)** - Database models and schemas
- **[22-JWT-Tokens.md](docs-library/22-JWT-Tokens.md)** - JWT authentication
- **[48-User-Status-System.md](docs-library/48-User-Status-System.md)** - User status management
- **[49-Activity-Tracking.md](docs-library/49-Activity-Tracking.md)** - DAU/MAU/WAU tracking
- **[95-Testing-Guide.md](docs-library/95-Testing-Guide.md)** - Testing implementation
- **[96-Extending-UserModel.md](docs-library/96-Extending-UserModel.md)** - Custom user fields
- **[97-Observability.md](docs-library/97-Observability.md)** - Logging and metrics
- **[98-Metrics-Reference.md](docs-library/98-Metrics-Reference.md)** - Metrics catalog
- **[99-Log-Events-Reference.md](docs-library/99-Log-Events-Reference.md)** - Log events catalog

**Note**: User documentation is being rebuilt. See `docs/` for complete design specifications.

## Development Status

**Current Library Version**: 0.1.0a5
**Current Admin UI Version**: 0.1.0-alpha.5
**Release Stage**: Alpha
**Database**: PostgreSQL (via SQLAlchemy async)

### Delivery Status

| Preset | Status | Notes |
|--------|--------|-------|
| **SimpleRBAC** | Alpha | Flat RBAC, JWT auth, API keys, rate limiting |
| **EnterpriseRBAC** | Alpha | Entity hierarchy, tree permissions, closure table |

### What's Working

✅ **SimpleRBAC** - Full authentication and flat RBAC
✅ **EnterpriseRBAC** - Entity hierarchy with tree permissions
✅ **JWT Authentication** - Access + refresh tokens
✅ **API Key Authentication** - SHA-256 hashing, rate limiting, IP whitelisting
✅ **User Management** - CRUD, status, password reset
✅ **Role & Permission System** - Assignment, checking, audit trails
✅ **PostgreSQL** - All services use SQLAlchemy async
✅ **Observability** - Prometheus metrics, structured logging
✅ **104 Unit Tests Passing** - Core functionality verified

## Roadmap

### Alpha (Current)
- ✅ SimpleRBAC core functionality working
- ✅ EnterpriseRBAC core functionality working
- ✅ JWT + API key authentication
- ✅ PostgreSQL with SQLAlchemy async
- ✅ Entity hierarchy with closure table
- ✅ Tree permissions
- ✅ Observability (Prometheus + structured logging)

### Post-Alpha (Future)
- OAuth/social login (Google, Facebook, Apple)
- Passwordless auth (magic links, OTP)
- MFA/TOTP
- Notification system

## Requirements

- Python 3.12+
- FastAPI 0.100+
- PostgreSQL 14+ (with asyncpg driver)
- Redis 6+ (optional, for caching)

## License

Private package. Distribution and usage are governed by internal Outlabs terms.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

## Acknowledgments

OutlabsAuth is heavily inspired by [FastAPI-Users](https://github.com/fastapi-users/fastapi-users) and adopts many of their excellent patterns:

- **Lifecycle Hooks**: Extensibility through overrideable async hooks
- **Router Factories**: Pre-built routers for common auth flows
- **Transport/Strategy Pattern**: Clean separation of credential delivery vs validation
- **Dynamic Dependencies**: makefun integration for perfect OpenAPI schemas

We extend these patterns with advanced authorization features:
- Hierarchical entity system
- Tree permissions with closure table
- Context-aware roles
- Multi-tenant support

Special thanks to the FastAPI-Users team for pioneering these patterns in the FastAPI ecosystem.

## Support

- **Documentation**: `docs/` and `docs-library/`
- **Release workflow**: `docs/PRIVATE_RELEASE.md`
- **Support**: internal Outlabs engineering channels

---

**Built with ❤️ by Outlabs**
