# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: This project is undergoing a major architectural change from a centralized API service to a FastAPI library. Always check `docs/` for the current vision and implementation plan.

## Project Overview

**OutlabsAuth** is being redesigned as a **FastAPI library** that can be installed via pip (`pip install outlabs-auth`) and integrated directly into applications. This replaces the previous centralized API service approach.

**Inspired by FastAPI-Users**: We've adopted many excellent patterns from [FastAPI-Users](https://github.com/fastapi-users/fastapi-users) including lifecycle hooks, router factories, and transport/strategy patterns (see DD-038 to DD-046).

### What Changed
- **From**: Standalone FastAPI service with multi-platform isolation
- **To**: Python library with single-tenant per application

### What Stayed (Core OutlabsAuth Features)
- ✅ Entity hierarchy (STRUCTURAL + ACCESS_GROUP)
- ✅ Tree permissions (hierarchical access control)
- ✅ Context-aware roles
- ✅ Flexible entity types
- ✅ Hybrid authorization (RBAC + ReBAC + ABAC)

### What We Borrowed from FastAPI-Users
- ✅ Lifecycle hooks (on_after_register, on_after_login, etc.)
- ✅ Router factory pattern
- ✅ Transport/Strategy pattern
- ✅ Dynamic dependency injection with makefun
- ✅ Service-based architecture

## Current Project Status

**Branch**: `library-redesign`
**Status**: Planning Phase → Starting Implementation
**Version**: 1.4 (Unified Architecture + Performance Improvements)

### Documentation Structure

**IMPORTANT**: There are TWO documentation folders with different purposes:

#### `docs/` - System Specifications (For Maintainers)
Complete design specs and architectural decisions (13 files):
1. **REDESIGN_VISION.md** - Main vision document (start here)
2. **LIBRARY_ARCHITECTURE.md** - Technical architecture details
3. **IMPLEMENTATION_ROADMAP.md** - 15-16 week implementation plan
4. **API_DESIGN.md** - Developer experience and code examples
5. **COMPARISON_MATRIX.md** - SimpleRBAC vs EnterpriseRBAC
6. **DEPENDENCY_PATTERNS.md** - FastAPI dependency injection patterns
7. **SECURITY.md** - Security hardening guide
8. **TESTING_GUIDE.md** - Testing strategies
9. **DEPLOYMENT_GUIDE.md** - Production deployment
10. **ERROR_HANDLING.md** - Exception hierarchy
11. **DESIGN_DECISIONS.md** - 37+ architectural decisions (DD-001 to DD-037+)
12. **AUTH_EXTENSIONS.md** - Optional OAuth, passwordless, MFA (v1.1-v1.4)
13. **MIGRATION_GUIDE.md** - For external users migrating from centralized API

**Use these as source of truth for architectural decisions.**

#### `docs-library/` - User Documentation (Implementation-Specific)
Currently only 9 files - being rebuilt to match actual implementation:
- Data models, JWT, user status, activity tracking
- Testing, observability, metrics, log events
- Extending user model

**Note**: Most user documentation was deleted (48 files) due to inconsistencies with actual implementation. User docs are being rewritten from scratch based on real code, not design specs.

## Architecture Overview

### Unified Core with Thin Wrappers

The library has a **single `OutlabsAuth` core implementation** with thin convenience wrappers:

```python
# Core class with all functionality
from outlabs_auth import OutlabsAuth

auth = OutlabsAuth(
    database=mongo_client,
    enable_entity_hierarchy=True,      # Feature flags
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)
```

**Two Presets**:

1. **SimpleRBAC** - Thin wrapper (5-10 LOC) for flat RBAC
   ```python
   from outlabs_auth import SimpleRBAC
   auth = SimpleRBAC(database=db)
   # Flat structure: users → roles → permissions
   ```

2. **EnterpriseRBAC** - Thin wrapper with entity hierarchy always enabled
   ```python
   from outlabs_auth import EnterpriseRBAC
   auth = EnterpriseRBAC(
       database=db,
       enable_context_aware_roles=True,  # Optional features
       enable_abac=True
   )
   # Hierarchy: entities → memberships → roles → permissions
   ```

### Decision: Do You Have Departments/Teams?
- **NO** → Use `SimpleRBAC`
- **YES** → Use `EnterpriseRBAC`

## Essential Commands

### Setup
```bash
# Install dependencies
uv sync

# Install with optional dependencies
uv sync --extra dev     # Development tools
uv sync --extra test    # Testing tools
uv sync --extra all     # Everything
```

### Development
```bash
# Run tests (new library tests, not old ones)
uv run pytest

# Code quality
uv run black .
uv run isort .
uv run flake8 .
uv run mypy .

# Build package
uv build

# Install locally for testing
pip install -e .
```

## Directory Structure

```
outlabsAuth/
├── docs/                           # 📋 SYSTEM SPECS (for maintainers)
│   ├── README.md                   # Explains design docs vs user docs
│   ├── REDESIGN_VISION.md          # Project vision
│   ├── LIBRARY_ARCHITECTURE.md     # Technical architecture
│   ├── DESIGN_DECISIONS.md         # DD-001 to DD-037+ decisions
│   ├── API_DESIGN.md               # API design patterns
│   ├── COMPARISON_MATRIX.md        # SimpleRBAC vs EnterpriseRBAC
│   ├── IMPLEMENTATION_ROADMAP.md   # Development phases
│   └── ... (13 design spec files)
│
├── docs-library/                   # 📚 USER DOCS (implementation-specific)
│   ├── 12-Data-Models.md           # Database models
│   ├── 22-JWT-Tokens.md            # JWT authentication
│   ├── 48-User-Status-System.md    # User status
│   ├── 49-Activity-Tracking.md     # DAU/MAU tracking
│   ├── 95-Testing-Guide.md         # Testing implementation
│   ├── 96-Extending-UserModel.md   # Extending users
│   ├── 97-Observability.md         # Logging & metrics
│   ├── 98-Metrics-Reference.md     # Metrics catalog
│   └── 99-Log-Events-Reference.md  # Log events catalog
│   # Note: Only 9 files - user docs being rebuilt from scratch
│
├── _reference/                     # 📁 Archived reference code
│   ├── models/                     # Old Beanie models from centralized API
│   └── services/                   # Old service logic from centralized API
│
├── _archive/                       # 📁 Archived old UI
│   └── frontend-old/               # Old Nuxt 3 admin UI (for reference)
│
├── outlabs_auth/                   # 📦 THE LIBRARY PACKAGE
│   ├── __init__.py
│   ├── core/                       # Base OutlabsAuth class
│   ├── models/                     # Beanie ODM models
│   ├── services/                   # Business logic services
│   ├── presets/                    # SimpleRBAC, EnterpriseRBAC
│   ├── dependencies/               # FastAPI dependency injection
│   ├── middleware/                 # Auth middleware
│   ├── utils/                      # JWT, password hashing, etc.
│   └── schemas/                    # Pydantic request/response schemas
│
├── examples/                       # 📁 Example applications
│   ├── enterprise_rbac/            # EnterpriseRBAC demo (real estate)
│   └── notifications/              # Notification system demo
│   # Note: SimpleRBAC example deleted (had broken metadata hack)
│
├── tests/                          # 📁 Library tests
│   ├── unit/
│   └── integration/
│
├── pyproject.toml                  # Package configuration
├── README.md                       # Library README
└── CLAUDE.md                       # This file - Claude Code guidance
```

## Key Features (Core v1.0)

### Authentication System
- **JWT Authentication**: Access tokens (15 min) + refresh tokens (30 days)
- **API Keys**: argon2id hashing, 12-char prefixes, temporary locks
- **JWT Service Tokens**: ~0.5ms authentication for internal services
- **Multi-Source Auth**: JWT, API keys, service tokens, superuser, anonymous

### Permission System
- **SimpleRBAC**: Flat role-based access control
- **EnterpriseRBAC**: Hierarchical permissions with entity context
  - Entity hierarchy with closure table (O(1) ancestor/descendant queries)
  - Tree permissions (`resource:action_tree`) for hierarchical access
  - Context-aware roles (permissions adapt by entity type)
  - Optional ABAC conditions

### Performance Features (v1.4)
- **Closure Table** (DD-036): O(1) tree queries, 20x improvement
- **Redis Counters** (DD-033): 99%+ reduction in DB writes for API keys
- **Redis Pub/Sub** (DD-037): <100ms cache invalidation across instances
- **Unified AuthDeps** (DD-035): Single dependency injection class

## Reference Code (`_reference/`)

The `_reference/` directory contains well-designed code from the old centralized API:

### Models (`_reference/models/`)
- `entity_model.py` - Unified entity system (STRUCTURAL + ACCESS_GROUP)
- `user_model.py` - User authentication and profile
- `role_model.py` - Context-aware roles
- `permission_model.py` - ABAC conditions
- **Use**: Starting point for library models (will need modifications)

### Services (`_reference/services/`)
- `permission_service.py` - Complex permission resolution (977 lines)
  - Tree permission checking
  - ABAC policy evaluation
  - Redis caching
  - Hierarchical permission inheritance
- `entity_service.py` - Entity hierarchy management
- `user_service.py` - User management
- `auth_service.py` - JWT authentication
- **Use**: Reference implementation for business logic

**Important**: These are **reference only** - they're designed for the centralized API approach. The library will need simplified versions adapted to the new architecture.

## Implementation Phases

Following **IMPLEMENTATION_ROADMAP.md**:

### Core Library (6-7 weeks)
- **Phase 1** (Week 1): Core foundation + SimpleRBAC
- **Phase 2** (Week 2): Complete SimpleRBAC + API keys
- **Phase 3** (Week 3): EnterpriseRBAC entity system + closure table
- **Phase 4** (Week 4): Optional features (context-aware roles, ABAC)
- **Phase 5** (Week 5): Complete testing + Redis patterns
- **Phase 6** (Week 6-7): CLI tools, documentation, examples

### Optional Extensions (9 weeks, post-v1.0)
- **v1.1** (Week 8-9): Notification system
- **v1.2** (Week 10-12): OAuth/social login
- **v1.3** (Week 13-14): Passwordless auth
- **v1.4** (Week 15-16): MFA/TOTP

## FastAPI Integration Example

```python
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
auth = SimpleRBAC(database=mongo_client)
deps = AuthDeps(auth)

# Initialize database
await auth.initialize()

# Use in routes
@app.get("/users/me")
async def get_me(ctx = Depends(deps.require_auth())):
    return ctx.metadata.get("user")

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx = Depends(deps.require_permission("user:delete"))
):
    return await auth.user_service.delete_user(user_id)
```

## Testing

### Test Structure
```
tests/
├── unit/                          # Unit tests for services
│   ├── services/
│   ├── models/
│   └── utils/
└── integration/                   # Integration tests for presets
    ├── test_simple_rbac.py
    ├── test_enterprise_rbac.py
    ├── test_tree_permissions.py
    └── test_api_keys.py
```

### Testing Goals
- 90%+ code coverage
- Test both SimpleRBAC and EnterpriseRBAC
- Test entity hierarchy and tree permissions
- Test API key authentication
- Test multi-source authentication

## Key Design Decisions

All 37 design decisions documented in **DESIGN_DECISIONS.md**:

### Latest (v1.4+)
- **DD-032**: Unified architecture (single core + thin wrappers)
- **DD-033**: Redis counters for API keys (99%+ write reduction)
- **DD-034**: JWT service tokens (~0.5ms auth)
- **DD-035**: Single AuthDeps class
- **DD-036**: Closure table for tree permissions (O(1) queries)
- **DD-037**: Redis Pub/Sub cache invalidation (<100ms)
- **DD-038 to DD-046**: FastAPI-Users patterns integration (hooks, router factories, transport/strategy)

### Core Decisions
- **DD-001**: MongoDB with Beanie ODM
- **DD-002**: FastAPI native (not framework-agnostic)
- **DD-003**: Two presets (Simple, Enterprise)
- **DD-005**: Entity hierarchy always in Enterprise
- **DD-008**: No cross-app SSO (each app is independent)

## Common Pitfalls to Avoid

1. **Don't reference old centralized API docs** - Use `docs/` only
2. **Reference code is for inspiration** - Don't copy-paste without adapting
3. **Library is backend-only** - No admin UI in v1.0 (that's v1.6)
4. **Each app is independent** - No multi-platform/multi-tenant by default
5. **Start simple** - SimpleRBAC first, then EnterpriseRBAC features

## Development Workflow

1. **Read the vision**: Start with `docs/REDESIGN_VISION.md`
2. **Check the roadmap**: Follow phases in `IMPLEMENTATION_ROADMAP.md`
3. **Reference models**: Look at `_reference/models/` for structure
4. **Reference services**: Look at `_reference/services/` for logic patterns
5. **Follow API design**: Use patterns from `API_DESIGN.md`
6. **Test everything**: Follow `TESTING_GUIDE.md`
7. **Security first**: Implement per `SECURITY.md`

## Questions?

- **Vision**: `docs/REDESIGN_VISION.md`
- **Architecture**: `docs/LIBRARY_ARCHITECTURE.md`
- **Implementation**: `docs/IMPLEMENTATION_ROADMAP.md`
- **API Examples**: `docs/API_DESIGN.md`
- **Decisions**: `docs/DESIGN_DECISIONS.md`

---

**Last Updated**: 2025-01-14
**Status**: Starting Phase 1 - Core Foundation
**Branch**: library-redesign
