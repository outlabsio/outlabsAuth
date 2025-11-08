# OutlabsAuth

**FastAPI authentication and authorization library with hierarchical RBAC**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.4+-green.svg)](https://www.mongodb.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

OutlabsAuth is a comprehensive authentication and authorization library for FastAPI applications. Install it via pip and integrate powerful auth capabilities directly into your application - no separate auth service required.

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
- **Production Ready**: Redis caching, Pub/Sub invalidation, comprehensive security
- **Extensible**: Override services, add custom hooks, create custom transports

## Quick Start

### Installation

```bash
pip install outlabs-auth
```

### Simple RBAC Example

```python
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
auth = SimpleRBAC(database=mongo_client)
deps = AuthDeps(auth)

# Initialize database
await auth.initialize()

# Assign role to user (uses UserRoleMembership table)
await auth.role_service.assign_role(
    user_id=user.id,
    role_id=admin_role.id,
    assigned_by=current_user.id
)

# Protected route
@app.get("/users/me")
async def get_me(ctx = Depends(deps.require_auth())):
    return ctx.metadata.get("user")

# Permission-protected route
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx = Depends(deps.require_permission("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"success": True}
```

**Note**: SimpleRBAC uses a `UserRoleMembership` table for role assignment, providing audit trails and time-based access control even in the simple preset. This makes migration to EnterpriseRBAC seamless. See [DD-047](docs/DESIGN_DECISIONS.md#dd-047-userrolemembership-table-for-simplerbac) for rationale.

### Enterprise RBAC Example

```python
from outlabs_auth import EnterpriseRBAC

# Enable entity hierarchy + optional features
auth = EnterpriseRBAC(
    database=mongo_client,
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

**Current Version**: 1.5 (SimpleRBAC Complete + Enhanced Membership System)
**Branch**: `library-redesign`
**Status**: Phases 1-2 Complete, Phase 1.5 Complete (Beyond Plan), Phase 3+ Pending

### Progress Summary

✅ **Phase 1 Complete** - Core foundation + SimpleRBAC
✅ **Phase 2 Complete** - API Keys + Multi-source Auth + Testing
✅ **Phase 1.5 Complete** - MembershipStatus Enum, User Status System, Activity Tracking, Observability Docs
⏸️ **Phase 3+ Pending** - EnterpriseRBAC Entity System (planned after observability implementation)

**See [IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md) for detailed progress, implementation status, and phase breakdowns.**

## Roadmap

### Core Library (v1.0) - 6-7 weeks
- ✅ **Phase 1**: Core foundation + SimpleRBAC
- ✅ **Phase 2**: Complete SimpleRBAC + API keys
- ⏸️ **Phase 3**: EnterpriseRBAC entity system
- ⏸️ **Phase 4**: Optional features (context-aware, ABAC)
- ⏸️ **Phase 5**: Complete testing + Redis patterns
- ⏸️ **Phase 6**: CLI tools, docs, examples

### Optional Extensions (post-v1.0) - 9 weeks
- **v1.1**: Notification system
- **v1.2**: OAuth/social login (Google, Facebook, Apple)
- **v1.3**: Passwordless auth (magic links, OTP)
- **v1.4**: MFA/TOTP

**For complete roadmap with task breakdowns, see [IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md)**

## Requirements

- Python 3.12+
- FastAPI 0.100+
- MongoDB 4.4+ (with transaction support)
- Redis 6+ (optional, for caching)

## License

MIT License - see LICENSE file for details

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

- **Documentation**: `docs/`
- **Issues**: [GitHub Issues](https://github.com/outlabs/outlabs-auth/issues)
- **Discussions**: [GitHub Discussions](https://github.com/outlabs/outlabs-auth/discussions)

---

**Built with ❤️ by Outlabs**
