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
**Status**: In Progress - Phases 1-2 Complete, Phase 1.5 Complete, Phase 3+ Pending
**Version**: 1.5 (SimpleRBAC Complete + Enhanced Membership System)

**Progress**:
- ✅ Phase 1 Complete (Core foundation + SimpleRBAC)
- ✅ Phase 2 Complete (API Keys + Multi-source Auth + Testing)
- ✅ Phase 1.5 Complete (Beyond Plan: MembershipStatus, User Status, Activity Tracking, Observability)
- ✅ Frontend Integration Verified (SimpleRBAC login working)
- ⏸️ Phase 3+ Pending (EnterpriseRBAC - planned after observability implementation)

**PROJECT MANAGEMENT**: We use [IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md) as the primary project management tool. All phase tracking, status updates, and task breakdowns are maintained in the roadmap. Always update the roadmap when completing phases or tasks.

**For complete implementation status and detailed task breakdown, see [IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md)**

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
    redis_enabled=True,                # Enable Redis features
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

## Local Development Infrastructure

**IMPORTANT**: All local development uses these containers:

```bash
# Check running containers
docker ps

# You should see:
# - outlabs-mongodb (mongo:8) - Host port 27018 → Container port 27017
# - outlabs-redis (redis:latest) - Host port 6380 → Container port 6379
# - local-redis (redis:latest) - Host port 6379 → Container port 6379 (legacy)

# If they're not running, start them:
docker start outlabs-mongodb outlabs-redis
```

### Port Reference

**SimpleRBAC Example** (`examples/simple_rbac/`):
- Backend API: `http://localhost:8003`
- MongoDB: `mongodb://localhost:27018` (database: `blog_simple_rbac`)
- Redis: `redis://localhost:6380`
- Admin UI: `http://localhost:3000` (when running `auth-ui`)

**EnterpriseRBAC Example** (`examples/enterprise_rbac/`):
- Backend API: `http://localhost:8004` (when implemented)
- MongoDB: `mongodb://localhost:27018` (database: `realestate_enterprise_rbac`)
- Redis: `redis://localhost:6380`

**Connection Strings**:
```bash
# SimpleRBAC example startup
MONGODB_URL="mongodb://localhost:27018" \
DATABASE_NAME="blog_simple_rbac" \
SECRET_KEY="simple-rbac-secret-key-change-in-production" \
REDIS_URL="redis://localhost:6380" \
uv run uvicorn main:app --port 8003 --reload
```

These containers are shared across all examples and development work.

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

## Development Testing Utilities

### Quick Test Environment Reset (SimpleRBAC Example)

When testing auth features, you'll often need a clean database with known test users. The **reset script** provides instant reset to a known-good state:

```bash
cd examples/simple_rbac
python reset_test_env.py
```

**What it does:**
- ✅ Clears all test data (users, roles, permissions, memberships)
- ✅ Creates 21 permissions (user:*, role:*, permission:*, apikey:*, post:*, comment:*)
- ✅ Creates 4 default roles (reader, writer, editor, admin) with appropriate permissions
- ✅ Creates 3 test users with different permission levels
- ✅ Takes ~2 seconds to complete

**Test Users Created:**

| Email | Password | Role | Permissions |
|-------|----------|------|-------------|
| `admin@test.com` | `Test123!!` | Admin | Full system access (user:*, role:*, post:*, comment:*) |
| `editor@test.com` | `Test123!!` | Editor | Content management (post:*, comment:*) |
| `writer@test.com` | `Test123!!` | Writer | Content creation (post:read/create/update, comment:create) |

**When to use this:**
- 🔄 After breaking auth/permissions during development
- 🧪 Before running integration tests on the frontend (auth-ui)
- 🚀 Setting up a demo environment
- 🐛 Debugging auth issues with known-good credentials
- 🎨 Testing the admin UI with a fresh slate

**Configuration:**
Uses environment variables (can override):
- `MONGODB_URL` (default: `mongodb://localhost:27018`)
- `DATABASE_NAME` (default: `blog_simple_rbac`)

**Important:** This script is designed for development/testing only. Never run in production!

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
│   ├── AUTH_UI.md                  # Admin UI documentation (NEW)
│   └── ... (14 design spec files)
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
├── auth-ui/                        # 🎨 ADMIN UI (pluggable Nuxt 4 SPA)
│   ├── app/
│   │   ├── components/             # UI components (modals, forms)
│   │   ├── stores/                 # Pinia stores (auth, users, roles, etc.)
│   │   ├── pages/                  # Routes (users, roles, entities, etc.)
│   │   └── types/                  # TypeScript types
│   ├── nuxt.config.ts              # Nuxt configuration
│   ├── .env                        # API URL configuration
│   └── package.json                # Nuxt UI v4.0.1
│   # Pluggable admin interface for any OutlabsAuth-powered app
│   # Auto-detects SimpleRBAC vs EnterpriseRBAC mode
│   # See docs/AUTH_UI.md for full documentation
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
│   ├── simple_rbac/                # SimpleRBAC demo (blog application)
│   │   ├── main.py                 # FastAPI app with SimpleRBAC preset
│   │   ├── reset_test_env.py       # Quick test environment reset script
│   │   ├── README.md               # Example documentation
│   │   └── ...
│   ├── enterprise_rbac/            # EnterpriseRBAC demo (real estate)
│   └── notifications/              # Notification system demo
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
- **JWT Authentication**: Access tokens (15 min) + refresh tokens (30 days), optional rotation
- **API Keys**: SHA-256 hashing (fast for high-entropy secrets), 12-char prefixes, temporary locks
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
- **DD-047**: UserRoleMembership with MembershipStatus enum
- **DD-048**: Redis configuration simplification (single `redis_enabled` flag)

### Corrections (2025-01-26)
- **DD-028 CORRECTED**: API keys use SHA-256 (not argon2id) - fast hashing appropriate for high-entropy secrets
- **DD-028 UPDATED**: Refresh token rotation is OPTIONAL (not automatic) - simpler default, high-security apps can enable
- **DD-031**: Superseded by corrected DD-028

### Core Decisions
- **DD-001**: MongoDB with Beanie ODM
- **DD-002**: FastAPI native (not framework-agnostic)
- **DD-003**: Two presets (Simple, Enterprise)
- **DD-005**: Entity hierarchy always in Enterprise
- **DD-008**: No cross-app SSO (each app is independent)

## Admin UI (`auth-ui/`)

**IMPORTANT**: The admin UI is NOT part of the core library - it's a **separate pluggable component** that can be integrated into any app using OutlabsAuth.

### What It Is
- **Nuxt 4 SPA** (not part of the Python package)
- **Nuxt UI v4** components (Radix UI primitives)
- **Pinia state management** with auto-syncing to backend
- **Preset-aware**: Auto-detects SimpleRBAC vs EnterpriseRBAC

### Key Features
- ✅ Full CRUD for users, roles, permissions, entities, API keys
- ✅ Context switching (EnterpriseRBAC)
- ✅ JWT authentication with auto-refresh
- ✅ Keyboard shortcuts (`g-u` for users, `g-r` for roles, etc.)
- ✅ Mock data mode for UI development

### Location & Structure
```
auth-ui/
├── app/
│   ├── components/    # Modals, forms (RoleCreateModal.vue, etc.)
│   ├── stores/        # auth.store.ts, users.store.ts, roles.store.ts
│   ├── pages/         # Routes: /users, /roles, /entities
│   └── types/         # TypeScript types
├── .env               # NUXT_PUBLIC_API_BASE_URL=http://localhost:8003
└── package.json       # Nuxt UI v4.0.1
```

### Running the Admin UI
```bash
cd auth-ui
bun install
bun run dev  # Runs on http://localhost:3000
```

**Must point to a running OutlabsAuth API** (SimpleRBAC or EnterpriseRBAC example)

### Config Detection (NEW - In Progress)
The UI fetches `/v1/auth/config` to determine:
- Which preset is running (SimpleRBAC vs EnterpriseRBAC)
- Which features are enabled (entity_hierarchy, context_aware_roles, etc.)
- Available permissions for that preset

This allows the UI to **hide/show features** based on backend capabilities.

### Testing with Examples
```bash
# Terminal 1: Run SimpleRBAC example
cd examples/simple_rbac
docker compose up -d  # MongoDB + Redis
uv run uvicorn main:app --port 8003 --reload

# Terminal 2: Run admin UI
cd auth-ui
bun run dev

# Login at http://localhost:3000
# system@outlabs.io / Asd123$$
```

### Full Documentation
See **`docs/AUTH_UI.md`** for complete architecture, stores, API integration, and customization.

---

## Common Pitfalls to Avoid

1. **Don't reference old centralized API docs** - Use `docs/` only
2. **Reference code is for inspiration** - Don't copy-paste without adapting
3. **Admin UI is separate** - It's NOT in the Python package (it's a Nuxt app in `auth-ui/`)
4. **Each app is independent** - No multi-platform/multi-tenant by default
5. **Start simple** - SimpleRBAC first, then EnterpriseRBAC features
6. **Getting auth errors during testing?** - Use `python reset_test_env.py` to quickly reset to known-good state with test users
7. **Backend is source of truth** - Frontend schemas must exactly match backend Pydantic models; remove any extra fields

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
