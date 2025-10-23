# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**OutlabsAuth** is a FastAPI authentication and authorization library with hierarchical RBAC, tree permissions, and multi-source authentication. It's distributed as a Python package (`pip install outlabs-auth`) that developers integrate directly into their FastAPI applications.

### Key Characteristics
- **Library, not a service**: Integrates directly into FastAPI apps, no separate auth service needed
- **Two presets**: SimpleRBAC (flat roles) and EnterpriseRBAC (hierarchical entities with advanced features)
- **Single-tenant**: Each application instance is independent by design
- **Production-ready**: 111 tests passing (100%), comprehensive security features

### Core Features
- **Authentication**: JWT (access + refresh tokens), API keys (argon2id hashing), service tokens (~0.022ms validation)
- **Authorization**: Hierarchical permissions, tree permissions, context-aware roles, ABAC conditions
- **Performance**: Closure table for O(1) tree queries, Redis caching, Pub/Sub invalidation
- **Multi-source auth**: JWT, API keys, service tokens, superuser, anonymous

## Technology Stack

- **Language**: Python 3.12+
- **Framework**: FastAPI 0.100+
- **Package Manager**: `uv` (modern, fast Python package manager)
- **Database**: MongoDB 4.4+ via Beanie ODM
- **Cache**: Redis 6+ (optional, for performance)
- **Testing**: pytest with asyncio support
- **Code Quality**: black, isort, flake8, mypy

## Common Commands

### Setup
```bash
# Install all dependencies
uv sync

# Install with specific optional dependencies
uv sync --extra dev      # Development tools (black, isort, mypy, flake8)
uv sync --extra test     # Testing tools (pytest, httpx, faker)
uv sync --extra redis    # Redis support for caching
uv sync --extra all      # Everything (recommended for development)
```

### Testing
```bash
# Run all tests (111 tests, expect 100% pass rate)
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_user_service.py

# Run tests with coverage
uv run pytest --cov=outlabs_auth --cov-report=html

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run tests matching a pattern
uv run pytest -k "test_tree_permission"

# Run tests with verbose output
uv run pytest -v

# Run fast tests only (skip slow tests)
uv run pytest -m "not slow"
```

### Code Quality
```bash
# Format code (required before commits)
uv run black .
uv run isort .

# Lint code
uv run flake8 .

# Type checking
uv run mypy outlabs_auth/

# Run all quality checks at once
uv run black . && uv run isort . && uv run flake8 . && uv run mypy outlabs_auth/
```

### Building & Distribution
```bash
# Build the package (creates wheel and source distribution)
uv build

# Install locally for testing in another project
pip install -e .

# Install from local build
pip install dist/outlabs_auth-1.0.0-py3-none-any.whl
```

### CLI Tool
```bash
# Initialize auth system
uv run python -m outlabs_auth.cli init --preset simple

# Create a role
uv run python -m outlabs_auth.cli create-role --name admin --permissions "user:*,entity:*"

# Create a user
uv run python -m outlabs_auth.cli create-user --email admin@example.com --role admin

# List all roles
uv run python -m outlabs_auth.cli list-roles

# Run benchmarks
uv run python -m outlabs_auth.cli benchmark
```

## Architecture

### High-Level Structure

The library uses a **unified core architecture** with thin preset wrappers:

```
OutlabsAuth (Core - ~3000 LOC)
    ├── SimpleRBAC (5-10 LOC wrapper)
    │   └── Flat structure: users → roles → permissions
    └── EnterpriseRBAC (10 LOC wrapper)
        └── Hierarchy: entities → memberships → roles → permissions
```

All features are controlled by configuration flags - no code duplication.

### Directory Structure

```
outlabs_auth/                # Main library package
├── core/                    # Core classes and configuration
│   ├── auth.py              # OutlabsAuth base class
│   ├── config.py            # AuthConfig, SimpleConfig, EnterpriseConfig
│   └── exceptions.py        # Custom exception hierarchy
├── models/                  # Beanie ODM models (MongoDB)
│   ├── base.py              # BaseDocument (created_at, updated_at)
│   ├── user.py              # UserModel + UserStatus enum
│   ├── role.py              # RoleModel with context-aware permissions
│   ├── permission.py        # PermissionModel with ABAC conditions
│   ├── condition.py         # Condition + ConditionGroup (ABAC)
│   ├── token.py             # RefreshTokenModel (multi-device sessions)
│   ├── entity.py            # EntityModel + EntityClass enum
│   ├── membership.py        # EntityMembershipModel (users in entities)
│   ├── closure.py           # EntityClosureModel (O(1) tree queries)
│   └── api_key.py           # ApiKeyModel
├── services/                # Business logic services
│   ├── auth.py              # AuthService (login, logout, refresh)
│   ├── user.py              # UserService (CRUD, password management)
│   ├── role.py              # RoleService (CRUD operations)
│   ├── permission.py        # BasicPermissionService + EnterprisePermissionService
│   ├── policy_engine.py     # PolicyEvaluationEngine (ABAC)
│   ├── entity.py            # EntityService (hierarchy management)
│   ├── membership.py        # MembershipService (user-entity-role assignments)
│   ├── service_token.py     # ServiceTokenService (long-lived JWT for microservices)
│   ├── api_key.py           # ApiKeyService (API key management)
│   └── redis_client.py      # RedisClient (caching + Pub/Sub)
├── presets/                 # Convenience wrappers
│   ├── simple.py            # SimpleRBAC preset
│   └── enterprise.py        # EnterpriseRBAC preset
├── dependencies/            # FastAPI dependency injection
│   └── auth.py              # AuthDeps class
├── middleware/              # FastAPI middleware (future)
├── utils/                   # Utility functions
│   ├── jwt.py               # JWT token generation/validation
│   ├── password.py          # Password hashing (bcrypt) + validation
│   └── validation.py        # Input validation helpers
├── workers/                 # Background workers
│   └── api_key_sync.py      # Syncs Redis counters to MongoDB (every 5 min)
├── schemas/                 # Pydantic request/response schemas (future)
└── cli.py                   # CLI tool (init, create-role, create-user, etc.)
```

### Key Design Patterns

#### 1. Closure Table Pattern (DD-036)
- **Purpose**: O(1) ancestor/descendant queries for tree permissions
- **Implementation**: `EntityClosureModel` stores all ancestor-descendant pairs with depth
- **Performance**: 20x faster than recursive queries
- **Used by**: `EntityService`, `EnterprisePermissionService`

#### 2. Tree Permissions
- **Format**: `resource:action_tree` (e.g., `entity:update_tree`)
- **Behavior**: Permission applies to all descendants, NOT the entity itself
- **Example**: `entity:update_tree` on parent → can update all children
- **Resolution**: Direct permission → Tree permission in ancestors → Platform-wide permission

#### 3. Context-Aware Roles (Optional)
- **Purpose**: Permissions vary based on entity type
- **Implementation**: `RoleModel.entity_type_permissions` field
- **Example**: Regional manager has different permissions in regions vs offices vs teams
- **Enabled**: Only in EnterpriseRBAC with `enable_context_aware_roles=True`

#### 4. ABAC Conditions (Optional)
- **Purpose**: Attribute-based access control (e.g., budget limits, department matching)
- **Implementation**: `Condition` + `ConditionGroup` + `PolicyEvaluationEngine`
- **Operators**: 16 operators (EQUALS, LESS_THAN, IN, CONTAINS, STARTS_WITH, etc.)
- **Enabled**: Only in EnterpriseRBAC with `enable_abac=True`

#### 5. Redis Performance Patterns
- **Counter Pattern (DD-033)**: 99%+ reduction in DB writes for API key usage
- **Pub/Sub Pattern (DD-037)**: <100ms cache invalidation across instances
- **Service Tokens (DD-034)**: 0.022ms authentication with embedded permissions

## Working with This Codebase

### Critical Rules from CLAUDE.md

1. **This is a library, not a service**: Users install it via pip and integrate it into their FastAPI apps
2. **Two presets, one core**: All code is in `OutlabsAuth` core, presets are thin wrappers
3. **Reference code is reference only**: `_reference/` contains old centralized API code - use for patterns, not copy-paste
4. **Entity hierarchy always in Enterprise**: EnterpriseRBAC always has hierarchy, SimpleRBAC never does
5. **Follow docs first**: All design decisions documented in `docs/` - read before implementing

### Key Documentation Files

Must-read for understanding the system:
- **`docs/REDESIGN_VISION.md`**: Overall project vision and goals
- **`docs/LIBRARY_ARCHITECTURE.md`**: Technical architecture details
- **`docs/DESIGN_DECISIONS.md`**: 37 architectural decisions (DD-001 to DD-037)
- **`docs/API_DESIGN.md`**: Code examples and usage patterns
- **`docs/PRESET_SELECTION_GUIDE.md`**: When to use SimpleRBAC vs EnterpriseRBAC

### Testing Approach

The codebase has **111 tests with 100% pass rate**:
- **Unit tests** (`tests/unit/`): Test individual services and utilities in isolation
- **Integration tests** (`tests/integration/`): Test complete flows across services

#### Test Organization
- **SimpleRBAC**: 56 tests (authentication, roles, permissions, multi-device sessions)
- **EnterpriseRBAC**: 15 tests (hierarchy, tree permissions, memberships)
- **Context-Aware Roles**: 8 tests
- **ABAC Conditions**: 17 tests
- **Service Tokens**: 15 tests

#### Test Database
- Uses MongoDB test database (`outlabs_auth_test`)
- Each test gets a clean database via `test_db` fixture
- Database automatically dropped after each test
- Requires MongoDB running on `localhost:27017`

#### Running Tests
```bash
# Run all tests
uv run pytest

# Expect output like:
# ===================== 111 passed in 15.23s =====================
```

### Common Development Tasks

#### Adding a New Service
1. Create model in `outlabs_auth/models/`
2. Create service in `outlabs_auth/services/`
3. Add service initialization to `OutlabsAuth.__init__()` in `outlabs_auth/core/auth.py`
4. Write unit tests in `tests/unit/`
5. Write integration tests in `tests/integration/`
6. Update exports in `outlabs_auth/__init__.py`

#### Adding a New Permission Type
1. Add permission constant to relevant model
2. Update `EnterprisePermissionService` in `outlabs_auth/services/permission.py`
3. Add tests for permission resolution
4. Update documentation in `docs/API_DESIGN.md`

#### Modifying Entity Hierarchy Logic
1. Review closure table implementation in `outlabs_auth/models/closure.py`
2. Update `EntityService` in `outlabs_auth/services/entity.py`
3. Ensure closure table maintenance still works (create, delete, move)
4. Run entity hierarchy integration tests: `uv run pytest tests/integration/test_enterprise_rbac.py -k hierarchy`

#### Adding ABAC Operator
1. Add operator to `ConditionOperator` enum in `outlabs_auth/models/condition.py`
2. Implement evaluation logic in `PolicyEvaluationEngine._evaluate_condition()`
3. Add unit tests in `tests/unit/test_policy_engine.py`
4. Add integration tests in `tests/integration/test_abac_conditions.py`

### Security Considerations

This is an auth library - security is paramount:
- **Never log passwords or tokens**: Use redacted versions
- **Always hash passwords**: Use `password.py` utilities (bcrypt)
- **Validate input**: Use `validation.py` helpers
- **Rate limiting**: Implement for auth endpoints
- **Token expiration**: Access tokens: 15 min, Refresh tokens: 30 days
- **Account lockout**: 5 failed attempts → 30 min lockout
- **API key security**: argon2id hashing, 12-char prefixes, temporary locks

### Common Pitfalls

1. **Don't mix SimpleRBAC and EnterpriseRBAC concepts**: They have different models and services
2. **Don't query entities by id directly**: Use `EntityService.get_entity()` to handle ObjectId conversion
3. **Don't bypass closure table**: Always use `EntityService` methods to maintain closure table integrity
4. **Don't cache permissions without invalidation**: Use Redis Pub/Sub for multi-instance deployments
5. **Don't hardcode secret keys**: Use environment variables or config files
6. **Don't assume MongoDB is running**: Tests will fail without MongoDB on localhost:27017

### Branch Strategy

- **Main branch**: `library-redesign` (active development)
- **Version**: 1.9 (Phase 6 complete)
- **Status**: Production-ready core library (v1.0)

## Integration Examples

### SimpleRBAC (Flat Roles)
```python
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps

app = FastAPI()
auth = SimpleRBAC(database=mongo_client, secret_key="your-secret")
deps = AuthDeps(auth)

await auth.initialize()

@app.get("/users/me")
async def get_me(ctx = Depends(deps.require_auth())):
    return ctx.metadata.get("user")

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx = Depends(deps.require_permission("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"success": True}
```

### EnterpriseRBAC (Hierarchical)
```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=mongo_client,
    secret_key="your-secret",
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Create hierarchy
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
```

## Performance Targets

Achieved performance metrics:
- **Service Token Validation**: 0.022ms (96% faster than 0.5ms target)
- **Tree Permission Query**: <5ms (1 query via closure table)
- **API Key Usage Tracking**: 99%+ reduction in DB writes (Redis counters)
- **Cache Invalidation**: <100ms across all instances (Redis Pub/Sub)

## Environment Variables

Required for local development (see `.env.example`):
```bash
# MongoDB
DATABASE_URL=mongodb://localhost:27017
MONGO_DATABASE=outlabs_auth

# JWT
SECRET_KEY=your-super-secret-key-change-this
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis (optional, for caching)
REDIS_URL=redis://localhost:6379
```

## References

- **Examples**: See `examples/simple_rbac/` and `examples/enterprise_rbac/` for complete FastAPI applications
- **Design Docs**: See `docs/` for comprehensive design documentation (16 files)
- **Reference Code**: See `_reference/` for archived code from centralized API (patterns only, don't copy-paste)
- **Project Status**: See `PROJECT_STATUS.md` for implementation status (111/111 tests passing)
