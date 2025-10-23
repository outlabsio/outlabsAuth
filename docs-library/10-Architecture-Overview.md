# Architecture Overview

**Tags**: #architecture #design #system-design

High-level overview of OutlabsAuth's architecture, design principles, and component organization.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Your FastAPI Application                      │
│                                                                       │
│  @app.get("/users")                                                  │
│  async def get_users(ctx = Depends(auth.deps.require_auth())):      │
│      return await auth.user_service.list_users()                    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OutlabsAuth Library                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Preset Layer (API Entry)                   │  │
│  │  ┌──────────────────────┐    ┌──────────────────────┐       │  │
│  │  │   SimpleRBAC         │    │  EnterpriseRBAC      │       │  │
│  │  │  (Thin Wrapper)      │    │  (Thin Wrapper)      │       │  │
│  │  └──────────────────────┘    └──────────────────────┘       │  │
│  │                  │                        │                   │  │
│  │                  └────────────┬───────────┘                   │  │
│  │                               ▼                               │  │
│  │                    ┌──────────────────┐                       │  │
│  │                    │  OutlabsAuth     │                       │  │
│  │                    │  (Core Class)    │                       │  │
│  │                    └──────────────────┘                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   Dependency Injection Layer                  │  │
│  │                                                               │  │
│  │                    ┌──────────────────┐                       │  │
│  │                    │    AuthDeps      │                       │  │
│  │                    │  (DD-035)        │                       │  │
│  │                    └──────────────────┘                       │  │
│  │                            │                                   │  │
│  │      ┌─────────────────────┼─────────────────────┐            │  │
│  │      ▼                     ▼                     ▼            │  │
│  │  require_auth()    require_permission()    require_role()     │  │
│  │  (DD-039: makefun dynamic signatures)                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Service Layer                            │  │
│  │                                                               │  │
│  │  ┌───────────┐  ┌───────────┐  ┌────────────────┐           │  │
│  │  │UserService│  │RoleService│  │PermissionService│           │  │
│  │  └───────────┘  └───────────┘  └────────────────┘           │  │
│  │  ┌───────────┐  ┌───────────┐  ┌────────────────┐           │  │
│  │  │AuthService│  │ApiKeyServ.│  │EntityService   │           │  │
│  │  └───────────┘  └───────────┘  └────────────────┘           │  │
│  │                                                               │  │
│  │  Features:                                                    │  │
│  │  • Lifecycle hooks (DD-040) - 23 overridable hooks           │  │
│  │  • Business logic encapsulation                              │  │
│  │  • Async/await throughout                                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                 Transport/Strategy Layer (DD-038)             │  │
│  │                                                               │  │
│  │  Transport (How)         Strategy (What)                      │  │
│  │  ┌──────────────┐       ┌──────────────┐                     │  │
│  │  │BearerTransport│◄──────│ JWTStrategy  │                     │  │
│  │  └──────────────┘       └──────────────┘                     │  │
│  │  ┌──────────────┐       ┌──────────────┐                     │  │
│  │  │ApiKeyTransport│◄──────│ApiKeyStrategy│                     │  │
│  │  └──────────────┘       └──────────────┘                     │  │
│  │  ┌──────────────┐       ┌──────────────┐                     │  │
│  │  │CookieTransport│◄──────│ServiceToken  │                     │  │
│  │  └──────────────┘       └──────────────┘                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   Router Factory Layer (DD-041)               │  │
│  │                                                               │  │
│  │  Pre-built FastAPI routers with customization hooks:          │  │
│  │  • get_auth_router()         - Register, login, refresh      │  │
│  │  • get_users_router()        - Profile management            │  │
│  │  • get_api_keys_router()     - API key CRUD                  │  │
│  │  • get_oauth_router()        - OAuth flow (DD-043)           │  │
│  │  • get_oauth_associate_router() - Account linking (DD-044)   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Data Model Layer                         │  │
│  │                                                               │  │
│  │  Beanie ODM Models (MongoDB):                                 │  │
│  │  • User              - Authentication + profile               │  │
│  │  • Role              - Context-aware roles                    │  │
│  │  • Permission        - ABAC conditions                        │  │
│  │  • Entity            - Hierarchy nodes                        │  │
│  │  • EntityMembership  - User ↔ Entity ↔ Role                  │  │
│  │  • EntityClosure     - Ancestor/descendant cache (DD-036)     │  │
│  │  • ApiKey            - API key authentication                 │  │
│  │  • SocialAccount     - OAuth account linking                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
        ┌─────────────────┐             ┌─────────────────┐
        │    MongoDB      │             │     Redis       │
        │   (Primary)     │             │   (Optional)    │
        │                 │             │                 │
        │  • Users        │             │  • Cache        │
        │  • Roles        │             │  • Counters     │
        │  • Permissions  │             │  • Pub/Sub      │
        │  • Entities     │             └─────────────────┘
        │  • Memberships  │
        │  • Closures     │
        │  • API Keys     │
        │  • Social Accts │
        └─────────────────┘
```

---

## Core Design Principles

### 1. Library First, Not Service (DD-001)

**Design**: OutlabsAuth is a **library** that embeds into your FastAPI application.

**Not a Service**: Unlike centralized authentication services (Auth0, Keycloak), OutlabsAuth runs in your application process.

**Benefits**:
- ✅ No network latency (local function calls)
- ✅ No external dependencies (works offline)
- ✅ Full control and customization
- ✅ Simple deployment (one application)
- ✅ Zero SaaS costs

**Trade-offs**:
- ⚠️ No cross-application SSO (each app manages auth)
- ⚠️ MongoDB required (PostgreSQL planned for v2.0)

### 2. Single-Tenant Per Application (DD-008)

**Design**: Each application instance = one tenant.

**Multi-tenancy** within an application is supported via entity hierarchy (departments, teams, projects), but not multi-platform isolation.

**Example**:
```python
# App 1: Company A
auth = SimpleRBAC(database=mongo_client["company_a"])

# App 2: Company B (separate deployment)
auth = SimpleRBAC(database=mongo_client["company_b"])
```

### 3. Unified Core with Feature Flags (DD-032)

**Design**: Single `OutlabsAuth` core class with optional features enabled via flags.

**Presets**: Thin wrappers that configure feature flags:

```python
# SimpleRBAC = OutlabsAuth with minimal flags
auth = SimpleRBAC(database=db)
# Equivalent to:
auth = OutlabsAuth(
    database=db,
    enable_entity_hierarchy=False,
    enable_context_aware_roles=False,
    enable_abac=False
)

# EnterpriseRBAC = OutlabsAuth with hierarchy enabled
auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True,  # Optional
    enable_abac=True                  # Optional
)
# Equivalent to:
auth = OutlabsAuth(
    database=db,
    enable_entity_hierarchy=True,
    enable_context_aware_roles=True,
    enable_abac=True
)
```

**Benefits**:
- ✅ Single implementation to maintain
- ✅ Easy to upgrade (SimpleRBAC → EnterpriseRBAC)
- ✅ Consistent API across presets
- ✅ Feature flags for gradual adoption

### 4. MongoDB + Beanie ODM (DD-004)

**Design**: MongoDB for flexible schema, Beanie for Pydantic integration.

**Why MongoDB**:
- ✅ Flexible schema for evolving requirements
- ✅ Native async support (motor)
- ✅ Excellent performance for hierarchical queries
- ✅ JSON-like documents match Pydantic models

**Why Beanie**:
- ✅ Pydantic-based ODM (FastAPI native)
- ✅ Type safety and validation
- ✅ Async/await throughout
- ✅ Automatic migrations

**Future**: PostgreSQL support planned for v2.0.

### 5. FastAPI Native (DD-002)

**Design**: Deeply integrated with FastAPI patterns.

**Not Framework-Agnostic**: We don't try to support Flask, Django, etc.

**FastAPI Integration**:
- ✅ Dependency injection with `Depends()`
- ✅ Async/await throughout
- ✅ Pydantic schemas for validation
- ✅ OpenAPI documentation
- ✅ Exception handling with HTTPException

---

## Layer Breakdown

### Preset Layer

**Purpose**: User-facing API entry points.

**Components**:
- `SimpleRBAC` - Flat RBAC for simple applications
- `EnterpriseRBAC` - Hierarchical RBAC for complex organizations

**Implementation**: ~5-10 lines per preset (thin wrappers)

**Example**:
```python
class SimpleRBAC:
    def __init__(self, database, **kwargs):
        self._core = OutlabsAuth(
            database=database,
            enable_entity_hierarchy=False,
            **kwargs
        )

    def __getattr__(self, name):
        return getattr(self._core, name)
```

### Dependency Injection Layer

**Purpose**: FastAPI route protection via dependencies.

**Key Pattern**: Dynamic function signatures (DD-039) using `makefun`.

**Components**:
- `AuthDeps` - Single dependency injection class (DD-035)
- `require_auth()` - Require authenticated user
- `require_permission()` - Require specific permission
- `require_role()` - Require specific role

**Example**:
```python
@app.get("/users")
async def get_users(ctx = Depends(auth.deps.require_permission("user:read"))):
    # ctx contains user_id, permissions, roles, etc.
    return await auth.user_service.list_users()
```

**How It Works** (DD-039):
```python
# makefun creates function with proper signature for FastAPI
def require_permission(self, permission: str):
    def dependency(user_id: str = Depends(get_current_user)):
        # Check permission
        if not has_permission(user_id, permission):
            raise HTTPException(403)
        return {"user_id": user_id, "permissions": [...]}

    # makefun ensures FastAPI sees correct signature
    return with_signature(f"(user_id: str = Depends(...))")(dependency)
```

### Service Layer

**Purpose**: Business logic and data operations.

**Services**:

1. **UserService** (13 hooks)
   - Registration, login, profile updates
   - Email verification
   - Password reset
   - Lifecycle hooks for custom logic

2. **AuthService**
   - JWT token generation/validation
   - Multi-source authentication (DD-034)
   - Refresh token rotation

3. **RoleService** (7 hooks)
   - Role CRUD operations
   - Role assignment
   - Context-aware role resolution

4. **PermissionService**
   - Permission checking (flat + hierarchical)
   - Tree permission resolution (DD-036)
   - ABAC policy evaluation
   - Redis caching

5. **ApiKeyService** (6 hooks)
   - API key generation (argon2id hashing)
   - Key validation
   - Rate limiting
   - Temporary locks
   - Redis counters (DD-033)

6. **EntityService** (EnterpriseRBAC only)
   - Entity hierarchy management
   - Closure table maintenance (DD-036)
   - Membership management

**Lifecycle Hooks** (DD-040):

All services expose overrideable hooks for custom business logic:

```python
class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        # Custom logic: send welcome email, create workspace, etc.
        await email_service.send_welcome(user.email)
```

### Transport/Strategy Layer (DD-038)

**Purpose**: Separation of credential delivery from validation.

**Pattern**: Inspired by FastAPI-Users.

**Transport**: How credentials are delivered
- `BearerTransport` - Authorization: Bearer {token}
- `ApiKeyTransport` - X-API-Key: {key}
- `CookieTransport` - Cookies
- `HeaderTransport` - Custom headers

**Strategy**: How credentials are validated
- `JWTStrategy` - Decode and validate JWT
- `ApiKeyStrategy` - Hash and compare API key
- `ServiceTokenStrategy` - Validate service token

**Composition**:
```python
backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret="secret")
)
```

**Multi-Source Authentication**:
```python
backends = [
    AuthBackend("jwt", BearerTransport(), JWTStrategy()),
    AuthBackend("api_key", ApiKeyTransport(), ApiKeyStrategy()),
    AuthBackend("service", HeaderTransport(), ServiceTokenStrategy()),
]

# Try each backend in order until one succeeds
```

### Router Factory Layer (DD-041)

**Purpose**: Pre-built FastAPI routers with minimal configuration.

**Pattern**: Functions that return configured `APIRouter` instances.

**Router Factories**:

1. **get_auth_router()** - Authentication endpoints
   ```python
   router = get_auth_router(auth)
   # POST /register, /login, /refresh, /logout, /forgot-password, /reset-password
   ```

2. **get_users_router()** - User management
   ```python
   router = get_users_router(auth)
   # GET /me, PATCH /me, POST /me/change-password
   ```

3. **get_api_keys_router()** - API key management
   ```python
   router = get_api_keys_router(auth)
   # POST /, GET /, DELETE /{key_id}, POST /{key_id}/rotate
   ```

4. **get_oauth_router()** (DD-043) - OAuth authentication
   ```python
   router = get_oauth_router(google_client, auth, state_secret)
   # GET /authorize, GET /callback
   ```

5. **get_oauth_associate_router()** (DD-044) - Account linking
   ```python
   router = get_oauth_associate_router(google_client, auth, state_secret)
   # GET /authorize, GET /callback (requires authentication)
   ```

**Benefits**:
- ✅ 2-line integration
- ✅ Consistent API across applications
- ✅ Production-ready out of the box
- ✅ Customizable via parameters

### Data Model Layer

**Purpose**: MongoDB document models with Beanie ODM.

**Core Models**:

1. **User**
   ```python
   class User(Document):
       email: str
       hashed_password: str
       is_active: bool = True
       is_verified: bool = False
       is_superuser: bool = False
   ```

2. **Role**
   ```python
   class Role(Document):
       name: str
       permissions: List[str]
       context_permissions: Dict[str, List[str]]  # Entity type → permissions
   ```

3. **Entity** (EnterpriseRBAC)
   ```python
   class Entity(Document):
       name: str
       entity_type: str
       parent_id: Optional[str]
       is_structural: bool  # STRUCTURAL vs ACCESS_GROUP
   ```

4. **EntityClosure** (DD-036)
   ```python
   class EntityClosure(Document):
       ancestor_id: str
       descendant_id: str
       depth: int
   ```
   - Pre-computed ancestor/descendant relationships
   - O(1) tree queries (vs O(n) recursive)
   - ~20x performance improvement

5. **ApiKey**
   ```python
   class ApiKey(Document):
       user_id: str
       name: str
       prefix: str  # "ola_" + 12-char ID
       hashed_key: str  # argon2id
       last_used_at: datetime
       failed_attempts: int
       locked_until: Optional[datetime]
   ```

6. **SocialAccount** (OAuth)
   ```python
   class SocialAccount(Document):
       user_id: str
       provider: str
       provider_user_id: str
       email: str
       email_verified: bool
   ```

---

## Data Flow Examples

### Example 1: User Login (JWT)

```
1. Client sends credentials
   POST /auth/login
   {"email": "user@example.com", "password": "secret"}

2. AuthDeps extracts credentials
   → No Depends() needed (public route)

3. Router calls AuthService.login()
   → UserService.get_by_email(email)
   → Verify password hash
   → Generate JWT tokens

4. Return tokens to client
   {"access_token": "eyJ...", "refresh_token": "eyJ..."}
```

### Example 2: Protected Route (Permission Check)

```
1. Client sends request with JWT
   GET /users
   Authorization: Bearer eyJ...

2. AuthDeps.require_permission("user:read")
   → BearerTransport extracts token
   → JWTStrategy validates signature and expiration
   → Extract user_id from token

3. PermissionService.check_permission(user_id, "user:read")
   → Check Redis cache (if enabled)
   → Get user roles from database
   → Get role permissions from database
   → Check if "user:read" in permissions
   → Cache result in Redis

4. Dependency returns context
   {"user_id": "123", "permissions": ["user:read", ...]}

5. Route handler executes
   → UserService.list_users()
   → Return response
```

### Example 3: OAuth Login (Google)

```
1. Client requests authorization URL
   GET /auth/google/authorize

2. OAuth router generates state token (DD-042)
   → generate_state_token({}, state_secret, 600 seconds)
   → JWT with aud="outlabs-auth:oauth-state"
   → NO database write (stateless!)

3. Return authorization URL
   {"authorization_url": "https://accounts.google.com/...&state=eyJ..."}

4. User authenticates with Google
   → Google redirects to callback

5. OAuth callback validates state
   GET /auth/google/callback?code=...&state=eyJ...
   → decode_state_token(state, state_secret)
   → Validate aud and expiration
   → Exchange code for access token
   → Get user info from Google

6. Create or update user
   → Check if SocialAccount exists
   → If associate_by_email=True, link to existing user
   → Create User if new

7. Return JWT tokens
   {"access_token": "eyJ...", "refresh_token": "eyJ..."}
```

### Example 4: Tree Permission Check (EnterpriseRBAC)

```
1. Client requests access to resource
   GET /projects/project_a
   Authorization: Bearer eyJ...

2. AuthDeps.require_permission("project:read", entity_id="project_a")
   → Extract user_id from JWT
   → Get project's entity_id

3. PermissionService.check_tree_permission(user_id, "project:read", "project_a")
   → Get user's entity memberships
   → For each membership:
     a) Check direct permission in project's entity
     b) Check tree permissions in ancestor entities

4. Query EntityClosure for ancestors (O(1)!)
   SELECT ancestor_id FROM entity_closure WHERE descendant_id = 'project_a'
   → Returns: ['engineering_dept', 'company_root']

5. Check if user has "project:read_tree" in any ancestor
   → User is member of "engineering_dept" with "manager" role
   → "manager" role has "project:read_tree" permission
   → ✅ Access granted!

6. Cache result in Redis (10 min TTL)

7. Route handler executes
   → Return project data
```

---

## Performance Optimizations

### 1. Closure Table (DD-036)

**Problem**: Recursive tree queries are O(n) and slow.

**Solution**: Pre-compute all ancestor/descendant relationships.

**Performance**: O(1) queries, ~20x improvement.

**Trade-off**: Additional writes when entity hierarchy changes (rare).

### 2. Redis Caching

**Cached Data**:
- Permission checks (95%+ hit rate)
- Role lookups (98%+ hit rate)
- Entity hierarchies (90%+ hit rate)

**Impact**: 10x-100x faster permission checks.

### 3. Redis Counters (DD-033)

**Problem**: API key usage tracking generates write on every request.

**Solution**: Increment counter in Redis, flush to MongoDB periodically.

**Performance**: 99%+ reduction in database writes.

### 4. Redis Pub/Sub Cache Invalidation (DD-037)

**Problem**: Multi-instance deployments have stale caches.

**Solution**: Publish cache invalidation messages on permission changes.

**Performance**: <100ms cache invalidation across all instances.

---

## Security Architecture

### Defense in Depth

Multiple layers of security:

1. **JWT Signature Validation**
   - HS256/RS256 algorithms
   - Secret rotation support

2. **Token Expiration**
   - Short access tokens (15 min)
   - Long refresh tokens (30 days)

3. **Permission Verification**
   - Every protected route checked
   - Redis cache for performance

4. **Rate Limiting**
   - Per-API-key limits
   - Temporary locks after failed attempts

5. **CSRF Protection**
   - OAuth state tokens (DD-042)
   - SameSite cookies

6. **Password Security**
   - argon2id hashing (best practice)
   - Configurable complexity requirements

7. **API Key Security**
   - argon2id hashing (not bcrypt!)
   - 12-character prefixes (scannable)
   - Temporary locks

### Secure by Default

- `associate_by_email` defaults to False (prevents account hijacking)
- JWT expiration enforced
- CSRF protection enabled
- API keys hashed at rest
- OAuth state tokens signed

See [[110-Security-Best-Practices|Security Best Practices]] for detailed guidance.

---

## Scalability

### Horizontal Scaling

**Supported**: Multiple application instances with Redis.

**Requirements**:
- Redis Pub/Sub for cache invalidation (DD-037)
- Shared MongoDB database

**Not Supported**: Cross-application SSO (by design, DD-008).

### Vertical Scaling

**MongoDB**: Handles millions of users/permissions.

**Redis**: Optional but recommended for production.

### Performance Benchmarks

**Without Redis**:
- Simple permission check: ~5-10ms
- Tree permission check: ~20-50ms

**With Redis**:
- Simple permission check: ~0.5-1ms (cache hit)
- Tree permission check: ~1-5ms (cache hit)

**API Key Authentication** (DD-034):
- JWT token validation: ~0.5ms
- API key validation: ~50ms (argon2id)
- Service token validation: ~0.3ms (faster than JWT)

---

## Extension Points

### 1. Lifecycle Hooks (DD-040)

Override service methods to add custom logic:

```python
class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        await email_service.send_welcome(user.email)
        await analytics.track("user_registered", user.id)
```

**23 hooks** across UserService, RoleService, ApiKeyService.

### 2. Custom Transports/Strategies (DD-038)

Create custom authentication methods:

```python
class HeaderApiKeyTransport(Transport):
    async def get_credentials(self, request: Request) -> Optional[str]:
        return request.headers.get("X-Custom-Auth")

backend = AuthBackend(
    "custom",
    HeaderApiKeyTransport(),
    CustomStrategy()
)
```

### 3. Custom Router Factories (DD-041)

Wrap or extend pre-built routers:

```python
def get_custom_auth_router(auth):
    router = get_auth_router(auth)

    @router.post("/custom-endpoint")
    async def custom_endpoint():
        # Your logic
        pass

    return router
```

### 4. ABAC Policies

Add attribute-based conditions:

```python
policy = {
    "name": "Allow if owner or manager",
    "condition": {
        "or": [
            {"user.id": {"eq": "resource.owner_id"}},
            {"user.role": {"eq": "manager"}}
        ]
    }
}
```

---

## Next Steps

Now that you understand the architecture:

1. **[[41-SimpleRBAC|SimpleRBAC Guide]]** - Flat RBAC implementation
2. **[[42-EnterpriseRBAC|EnterpriseRBAC Guide]]** - Hierarchical RBAC
3. **[[100-Transport-Strategy-Pattern|Transport/Strategy Pattern]]** - Deep dive
4. **[[180-Deep-Dive-Permissions|Permission Resolution]]** - How permissions work

---

**Previous**: [[04-Basic-Concepts|← Basic Concepts]]
**Next**: [[11-Core-Components|Core Components →]]
