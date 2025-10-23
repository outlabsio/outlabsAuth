# FastAPI-Users Pattern Analysis & Integration

**Date**: 2025-01-23
**Version**: 1.0
**Status**: Reference Document

---

## Executive Summary

This document analyzes the FastAPI-Users library (v14.0.1) and identifies patterns to integrate into OutlabsAuth. FastAPI-Users is a mature, production-proven library with **14,000+ GitHub stars** and **81 contributors**, making it an excellent source of battle-tested patterns.

**Key Finding**: FastAPI-Users excels at **developer experience** patterns, while OutlabsAuth provides **richer authorization** (hierarchical permissions, entity trees, ABAC). Combining their strengths creates a superior library.

---

## Table of Contents

1. [FastAPI-Users Overview](#fastapi-users-overview)
2. [Architecture Comparison](#architecture-comparison)
3. [Patterns We Adopted](#patterns-we-adopted)
4. [Patterns We Rejected](#patterns-we-rejected)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Code Examples](#code-examples)

---

## FastAPI-Users Overview

### What It Is
FastAPI-Users is a ready-to-use authentication library for FastAPI:
- **Focus**: User authentication & basic user management
- **Scope**: Authentication (who are you?) NOT authorization (what can you do?)
- **Architecture**: Library-based (not a service)
- **Database Support**: SQLAlchemy, Beanie (MongoDB)
- **Auth Methods**: JWT, OAuth, Database sessions, Redis

### Key Strengths
✅ **Excellent developer experience** - 5-minute setup
✅ **Clean architecture** - Transport/Strategy separation
✅ **Production-proven** - Used by thousands of projects
✅ **Extensible** - Lifecycle hooks for customization
✅ **Well-documented** - Clear examples and guides
✅ **OpenAPI integration** - Perfect Swagger UI support

### Limitations
❌ **No authorization** - No roles, permissions, RBAC
❌ **Flat user model** - No entity hierarchy
❌ **No tree permissions** - No hierarchical access control
❌ **No ABAC** - No attribute-based access control
❌ **No API keys** - Only JWT and OAuth
❌ **No multi-source auth** - One backend at a time

---

## Architecture Comparison

### FastAPI-Users Architecture

```
┌─────────────────────────────────────────────────┐
│            FastAPIUsers (Main Class)            │
│  - Ties components together                     │
│  - Generates routers                            │
└────────────┬────────────────────────────────────┘
             │
     ┌───────┴──────┐
     │              │
┌────▼─────┐   ┌───▼────────┐
│BaseUser  │   │BaseUser    │
│Manager   │   │Database    │
│          │   │            │
│- create  │   │- get       │
│- update  │   │- create    │
│- delete  │   │- update    │
│- verify  │   │- delete    │
│- hooks   │   │            │
└──────────┘   └────────────┘

┌─────────────────────────────────────────────────┐
│         Authentication Backends                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Transport │  │Strategy  │  │Backend   │      │
│  │          │  │          │  │          │      │
│  │- Bearer  │  │- JWT     │  │Combines  │      │
│  │- Cookie  │  │- Redis   │  │T+S       │      │
│  │- Header  │  │- DB      │  │          │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│            Router Factories                     │
│  - get_auth_router()                            │
│  - get_register_router()                        │
│  - get_users_router()                           │
│  - get_verify_router()                          │
│  - get_reset_password_router()                  │
│  - get_oauth_router()                           │
└─────────────────────────────────────────────────┘
```

### OutlabsAuth Architecture (Enhanced)

```
┌─────────────────────────────────────────────────┐
│    OutlabsAuth / SimpleRBAC / EnterpriseRBAC   │
│  - Core auth system                             │
│  - Entity hierarchy (Enterprise)                │
│  - Tree permissions (Enterprise)                │
└────────────┬────────────────────────────────────┘
             │
     ┌───────┴──────────────────┐
     │                           │
┌────▼─────────┐   ┌─────────────▼──────────┐
│Services      │   │Models                  │
│              │   │                        │
│- UserService │   │- User (Beanie)         │
│- RoleService │   │- Role (Beanie)         │
│- PermService │   │- Permission (Beanie)   │
│- EntitySvc   │   │- Entity (Beanie)       │
│- ApiKeySvc   │   │- ApiKey (Beanie)       │
│- AuthSvc     │   │- EntityClosure         │
│              │   │                        │
│+ Hooks! NEW  │   │                        │
└──────────────┘   └────────────────────────┘

┌─────────────────────────────────────────────────┐
│    Authentication (NEW - Transport/Strategy)    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Transport │  │Strategy  │  │Backend   │      │
│  │          │  │          │  │          │      │
│  │- Bearer  │  │- JWT     │  │- jwt     │      │
│  │- ApiKey  │  │- ApiKey  │  │- api_key │      │
│  │- Header  │  │- Service │  │- service │      │
│  │          │  │- Superuser│ │- superuser│     │
│  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│   AuthDeps (NEW - Dynamic Dependency)           │
│  - require_auth() - Any valid auth              │
│  - require_permission(perm) - Check permission  │
│  - require_role(role) - Check role              │
│  - require_entity_access(entity) - Tree perms   │
│  - Uses makefun for OpenAPI                     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│      Router Factories (NEW - Optional)          │
│  SimpleRBAC:                                    │
│  - get_auth_router()                            │
│  - get_users_router()                           │
│  - get_api_keys_router()                        │
│                                                  │
│  EnterpriseRBAC (additional):                   │
│  - get_roles_router()                           │
│  - get_permissions_router()                     │
│  - get_entities_router()                        │
└─────────────────────────────────────────────────┘
```

---

## Patterns We Adopted

### Pattern 1: Transport/Strategy Separation (DD-038)

**From FastAPI-Users**: Clean separation between credential delivery (Transport) and validation (Strategy).

**Why**:
- Makes multi-source auth cleaner (JWT + API keys + service tokens)
- Easier to test
- More extensible

**Example**:
```python
# Define backends
jwt_backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret=SECRET)
)

api_key_backend = AuthBackend(
    name="api_key",
    transport=ApiKeyTransport(header_name="X-API-Key"),
    strategy=ApiKeyStrategy()
)

# Initialize with multiple backends
auth = SimpleRBAC(
    database=db,
    auth_backends=[jwt_backend, api_key_backend]
)
```

**Status**: ✅ Accepted (DD-038)

---

### Pattern 2: Dynamic Dependency Injection with makefun (DD-039)

**From FastAPI-Users**: Use `makefun` library to dynamically generate FastAPI dependencies with correct signatures.

**Why**:
- Multiple auth backends appear correctly in OpenAPI schema
- Users see all auth options in Swagger UI
- Scales to any number of auth methods
- Cleaner than manual dependency creation

**Example**:
```python
from makefun import with_signature
from inspect import Parameter, Signature

class AuthDeps:
    def require_auth(self):
        """Generate dependency that tries all backends."""
        # Build dynamic signature with parameter for each backend
        parameters = [...]  # One param per backend
        signature = Signature(parameters)

        @with_signature(signature)
        async def dependency(*args, **kwargs):
            # Try each backend in order
            for backend in self.backends:
                credentials = kwargs[f"{backend.name}_credentials"]
                if credentials:
                    user = await backend.authenticate(credentials)
                    if user:
                        return user
            raise HTTPException(401)

        return dependency
```

**OpenAPI Result**:
```yaml
# Swagger UI shows ALL auth options!
security:
  - jwt: []
  - api_key: []
  - service: []
```

**Status**: ✅ Accepted (DD-039)

---

### Pattern 3: Service Lifecycle Hooks (DD-040)

**From FastAPI-Users**: Overrideable async methods for custom logic.

**Why**:
- Users can inject custom logic (emails, webhooks, logging)
- No library modification needed
- Simple to understand and use
- Production-proven pattern

**Example**:
```python
class MyUserService(UserService):
    async def on_after_register(self, user: User, request=None):
        # Send welcome email
        await email_service.send_welcome(user.email)

        # Log event
        logger.info(f"New user: {user.email}")

        # Trigger webhook
        await webhook_service.trigger("user.registered", {...})

    async def on_after_login(self, user: User, request=None):
        # Track login analytics
        await analytics.track("user_login", user.id)

# Use custom service
auth = SimpleRBAC(
    database=db,
    user_service_class=MyUserService
)
```

**Hook Categories**:
1. **User Lifecycle**: `on_after_register`, `on_after_login`, `on_before_delete`
2. **Permission Changes**: `on_after_role_assigned`, `on_after_permission_changed`
3. **Security Events**: `on_after_forgot_password`, `on_failed_login`
4. **API Key Events**: `on_api_key_created`, `on_api_key_revoked`

**Status**: ✅ Accepted (DD-040)

---

### Pattern 4: Router Factory Pattern (DD-041)

**From FastAPI-Users**: Functions that generate FastAPI routers on-demand.

**Why**:
- Fast 5-minute setup for new users
- Flexibility to customize or replace routes
- Educational (users learn from code)
- Best practices by default

**Example**:
```python
# Option 1: Use default routers (fastest)
from outlabs_auth.routers import get_auth_router, get_users_router

app.include_router(get_auth_router(auth))
app.include_router(get_users_router(auth))
# Done! You have /auth/login, /auth/register, /users/me, etc.

# Option 2: Customize routers
app.include_router(
    get_auth_router(auth, prefix="/api/auth", tags=["authentication"])
)

# Option 3: Cherry-pick routes
router = APIRouter(prefix="/auth")
router.add_api_route("/login", create_login_route(auth), methods=["POST"])

# Option 4: Full custom (ignore routers)
@app.post("/custom/signup")
async def signup(email: str, password: str):
    user = await auth.user_service.create_user(email, password)
    return user
```

**Router Catalog**:
- **SimpleRBAC**: auth, users, api_keys
- **EnterpriseRBAC**: + roles, permissions, entities, memberships

**Status**: ✅ Accepted (DD-041)

---

## Patterns We Rejected

### ❌ Simplified Permission Model

**What**: FastAPI-Users has no permissions, roles, or authorization.

**Why We Rejected**: OutlabsAuth's core value is **hierarchical permissions** and **entity-based access control**. Removing this would make us just another JWT library.

**Our Advantage**:
- Tree permissions (`resource:action_tree`)
- Entity hierarchy with closure table
- Context-aware roles
- ABAC with conditions
- Role inheritance

---

### ❌ Flat User Model

**What**: FastAPI-Users uses minimal user model (id, email, hashed_password, is_active, is_superuser, is_verified).

**Why We Rejected**: Our user model is richer for real-world apps:
- Profile data (first_name, last_name, avatar, etc.)
- Status tracking (active, inactive, pending, suspended)
- Metadata (created_at, updated_at, last_login)
- Entity memberships (for EnterpriseRBAC)

---

### ❌ Single Authentication Backend

**What**: FastAPI-Users tries backends sequentially but typical usage is one backend.

**Why We Rejected**: We need **true multi-source authentication** where JWT, API keys, service tokens, and superuser auth all work simultaneously. This is critical for our use case.

**Our Advantage**: All auth methods work together seamlessly.

---

### ❌ No Database Abstraction

**What**: FastAPI-Users has separate packages for each database (fastapi-users-db-beanie, fastapi-users-db-sqlalchemy).

**Why We're Different**: We're MongoDB-first with Beanie. We may add database abstraction later (v2.0), but for v1.0 we optimize for Beanie.

---

## Implementation Roadmap

### Phase 1: Week 1-2 (Transport/Strategy + Hooks)

**Transport/Strategy Pattern** (DD-038):
```
outlabs_auth/
├── authentication/
│   ├── transport.py        # Transport base + implementations
│   ├── strategy.py         # Strategy base + implementations
│   ├── backend.py          # AuthBackend combinator
│   └── __init__.py
```

**Lifecycle Hooks** (DD-040):
```
outlabs_auth/services/
├── user_service.py         # Add hooks to UserService
├── role_service.py         # Add hooks to RoleService
├── permission_service.py   # Add hooks to PermissionService
└── api_key_service.py      # Add hooks to ApiKeyService
```

**Tasks**:
- [ ] Create `Transport` base class
- [ ] Implement `BearerTransport`, `ApiKeyTransport`, `HeaderTransport`
- [ ] Create `Strategy` base class
- [ ] Implement `JWTStrategy`, `ApiKeyStrategy`, `ServiceTokenStrategy`
- [ ] Create `AuthBackend` combinator
- [ ] Add lifecycle hooks to all services
- [ ] Write hook examples (email, webhooks, logging)
- [ ] Add tests

---

### Phase 2: Week 2-3 (Dynamic Dependencies)

**Dynamic Dependency Injection** (DD-039):
```
outlabs_auth/
├── dependencies.py         # AuthDeps with makefun
├── pyproject.toml          # Add makefun dependency
```

**Tasks**:
- [ ] Add `makefun>=1.15.0` to dependencies
- [ ] Refactor `AuthDeps` to use dynamic signature generation
- [ ] Test OpenAPI schema generation
- [ ] Verify Swagger UI shows all auth options
- [ ] Add examples to docs
- [ ] Add tests for signature generation

---

### Phase 3: Week 3-4 (Router Factories)

**Router Factories** (DD-041):
```
outlabs_auth/routers/
├── __init__.py
├── auth.py                 # get_auth_router()
├── users.py                # get_users_router()
├── api_keys.py             # get_api_keys_router()
├── roles.py                # get_roles_router() (Enterprise)
├── permissions.py          # get_permissions_router() (Enterprise)
└── entities.py             # get_entities_router() (Enterprise)
```

**Tasks**:
- [ ] Create router factory module
- [ ] Implement `get_auth_router()` (login, register, refresh, logout)
- [ ] Implement `get_users_router()` (CRUD, profile)
- [ ] Implement `get_api_keys_router()` (API key management)
- [ ] Implement `get_roles_router()` (EnterpriseRBAC)
- [ ] Implement `get_permissions_router()` (EnterpriseRBAC)
- [ ] Implement `get_entities_router()` (EnterpriseRBAC)
- [ ] Add customization examples
- [ ] Add tests

---

## Code Examples

### Example 1: Complete Setup with All Patterns

```python
from fastapi import FastAPI
from outlabs_auth import SimpleRBAC
from outlabs_auth.authentication import (
    AuthBackend,
    BearerTransport,
    ApiKeyTransport,
    JWTStrategy,
    ApiKeyStrategy,
    ServiceTokenStrategy
)
from outlabs_auth.routers import (
    get_auth_router,
    get_users_router,
    get_api_keys_router
)
from outlabs_auth.services import UserService
from motor.motor_asyncio import AsyncIOMotorClient

# Custom user service with hooks
class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        await email_service.send_welcome(user.email)
        logger.info(f"New user: {user.email}")

    async def on_after_login(self, user, request=None):
        await analytics.track("login", user.id)

# Initialize database
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
database = mongo_client["myapp"]

# Define authentication backends
jwt_backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret="SECRET", lifetime_seconds=3600)
)

api_key_backend = AuthBackend(
    name="api_key",
    transport=ApiKeyTransport(header_name="X-API-Key"),
    strategy=ApiKeyStrategy()
)

service_backend = AuthBackend(
    name="service",
    transport=BearerTransport(),
    strategy=ServiceTokenStrategy(secret="SERVICE_SECRET")
)

# Initialize auth
auth = SimpleRBAC(
    database=database,
    auth_backends=[jwt_backend, api_key_backend, service_backend],
    user_service_class=MyUserService,  # Use custom service with hooks
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Initialize FastAPI
app = FastAPI()

@app.on_event("startup")
async def startup():
    await auth.initialize()

# Include pre-built routers (fast setup!)
app.include_router(get_auth_router(auth))
app.include_router(get_users_router(auth))
app.include_router(get_api_keys_router(auth))

# Custom routes using auth dependencies
@app.get("/admin/dashboard")
async def admin_dashboard(
    user = Depends(auth.deps.require_permission("admin:dashboard"))
):
    return {"message": f"Welcome admin {user.email}"}

# Run with: uvicorn app:app --reload
```

**What This Gives You**:
- ✅ JWT authentication (Bearer token)
- ✅ API key authentication (X-API-Key header)
- ✅ Service token authentication (microservices)
- ✅ Pre-built routes (/auth/login, /auth/register, /users/me, etc.)
- ✅ Custom hooks (welcome emails, analytics)
- ✅ Permission checking
- ✅ Redis caching
- ✅ Perfect OpenAPI schema (all auth methods in Swagger)

**Lines of Code**: ~40 lines for complete auth system!

---

### Example 2: EnterpriseRBAC with Entity Hierarchy

```python
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.routers import (
    get_auth_router,
    get_users_router,
    get_roles_router,
    get_entities_router
)

# Initialize EnterpriseRBAC
auth = EnterpriseRBAC(
    database=database,
    auth_backends=[jwt_backend, api_key_backend],
    enable_context_aware_roles=True,  # Roles adapt by entity type
    enable_abac=True,                 # ABAC conditions
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Include routers
app.include_router(get_auth_router(auth))
app.include_router(get_users_router(auth))
app.include_router(get_roles_router(auth))      # NEW - Role management
app.include_router(get_entities_router(auth))   # NEW - Entity hierarchy

# Tree permissions example
@app.get("/projects/{project_id}/reports")
async def get_reports(
    project_id: str,
    user = Depends(auth.deps.require_entity_access(
        entity_id=project_id,
        permission="project:read_tree"  # Hierarchical permission!
    ))
):
    # User can read this project AND all child entities
    return await get_project_reports(project_id)
```

---

## Benefits Summary

### For Developers

**FastAPI-Users Strengths We Adopted**:
✅ 5-minute setup with router factories
✅ Clean architecture (Transport/Strategy)
✅ Perfect OpenAPI integration
✅ Extensibility via hooks
✅ Production-proven patterns

**OutlabsAuth Unique Strengths**:
✅ Hierarchical permissions (tree permissions)
✅ Entity-based access control
✅ Context-aware roles
✅ ABAC with conditions
✅ Multi-source auth (JWT + API keys + service tokens)
✅ API key management with rate limiting
✅ Redis caching with Pub/Sub invalidation

### The Best of Both Worlds

| Feature | FastAPI-Users | OutlabsAuth |
|---------|---------------|-------------|
| **Developer Experience** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (now!) |
| **Setup Speed** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (with routers) |
| **Authorization** | ❌ None | ⭐⭐⭐⭐⭐ Hierarchical |
| **Entity Hierarchy** | ❌ | ⭐⭐⭐⭐⭐ |
| **Tree Permissions** | ❌ | ⭐⭐⭐⭐⭐ |
| **ABAC** | ❌ | ⭐⭐⭐⭐⭐ |
| **API Keys** | ❌ | ⭐⭐⭐⭐⭐ |
| **Multi-Source Auth** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **OpenAPI Integration** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (with DD-039) |
| **Extensibility** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (with DD-040) |

---

## Conclusion

**FastAPI-Users** taught us how to build **excellent developer experience**. We've adopted their best patterns for DX while keeping our **superior authorization features**.

**Result**: OutlabsAuth v1.0 will offer:
- ⚡ **5-minute setup** (router factories)
- 🏗️ **Clean architecture** (Transport/Strategy)
- 📚 **Perfect OpenAPI** (dynamic dependencies)
- 🎣 **Extensibility** (lifecycle hooks)
- 🔐 **Powerful authorization** (our unique strength)

**Status**: Ready to implement in Phases 1-3 (Weeks 1-4)

---

**References**:
- FastAPI-Users: https://github.com/fastapi-users/fastapi-users
- Our Design Decisions: DD-038, DD-039, DD-040, DD-041
- Implementation Roadmap: IMPLEMENTATION_ROADMAP.md

**Last Updated**: 2025-01-23
