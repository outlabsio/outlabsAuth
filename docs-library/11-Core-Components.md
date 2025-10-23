# 11. Core Components

> **Quick Reference**: Understanding the main building blocks of OutlabsAuth - the unified core, services, models, and presets that power authentication and authorization.

## Overview

OutlabsAuth is built with a **unified architecture**: a single core implementation (`OutlabsAuth`) with feature flags that control capabilities.

```
┌────────────────────────────────────────────────────┐
│           OutlabsAuth (Core)                       │
│  Single implementation with feature flags          │
│  • Authentication                                  │
│  • Authorization                                   │
│  • Entity hierarchy (optional)                     │
│  • ABAC policies (optional)                        │
│  • Caching (optional)                              │
└────────────────────────────────────────────────────┘
           │                          │
           ▼                          ▼
    ┌─────────────┐          ┌──────────────────┐
    │ SimpleRBAC  │          │ EnterpriseRBAC   │
    │ (Thin wrap) │          │ (Thin wrap)      │
    │ Flat RBAC   │          │ + Hierarchy      │
    └─────────────┘          └──────────────────┘
```

---

## Component Hierarchy

```
1. Core
   └─ OutlabsAuth (unified implementation)

2. Presets (thin wrappers)
   ├─ SimpleRBAC (flat RBAC)
   └─ EnterpriseRBAC (hierarchical RBAC)

3. Services (business logic)
   ├─ UserService
   ├─ AuthService
   ├─ RoleService
   ├─ PermissionService
   ├─ ApiKeyService
   ├─ ServiceTokenService
   ├─ OAuthService
   ├─ EntityService (EnterpriseRBAC only)
   ├─ MembershipService (EnterpriseRBAC only)
   └─ PolicyEngine (ABAC only)

4. Models (data layer)
   ├─ UserModel
   ├─ RoleModel
   ├─ PermissionModel
   ├─ RefreshTokenModel
   ├─ ApiKeyModel
   ├─ SocialAccount
   ├─ EntityModel (EnterpriseRBAC only)
   ├─ MembershipModel (EnterpriseRBAC only)
   └─ ClosureTable (EnterpriseRBAC only)

5. Dependencies (FastAPI integration)
   ├─ AuthDeps
   ├─ Transport/Strategy Pattern
   └─ Router Factories

6. Utilities
   ├─ JWT utils
   ├─ Password hashing
   ├─ Validation
   └─ Security helpers
```

---

## 1. Core: OutlabsAuth Class

### Single Unified Implementation

**Design Decision (DD-032)**: Unified architecture with thin preset wrappers.

```python
from outlabs_auth import OutlabsAuth

# Core class with all features
auth = OutlabsAuth(
    database=mongo_db,
    secret_key="your-secret-key",

    # Feature flags (all optional)
    enable_entity_hierarchy=True,      # Enable entity system
    enable_context_aware_roles=True,   # Context-based role permissions
    enable_abac=True,                  # ABAC policies
    enable_caching=True,               # Redis caching
    redis_url="redis://localhost:6379"
)
```

### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Configuration** | Validate and store configuration |
| **Service Initialization** | Create and wire services based on config |
| **Database Setup** | Initialize Beanie ODM with models |
| **Lifecycle Management** | Startup/shutdown hooks |
| **Feature Coordination** | Enable/disable features via flags |

### Key Methods

```python
class OutlabsAuth:
    async def initialize():
        """Initialize database and services."""

    async def get_current_user(token: str):
        """Get user from JWT token."""

    async def authenticate(email: str, password: str):
        """Authenticate user with email/password."""

    def get_info():
        """Get auth system information and enabled features."""
```

**See**: [[10-Architecture-Overview]] for architectural details.

---

## 2. Presets

### SimpleRBAC

**Thin wrapper** (5-10 LOC) for flat role-based access control.

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db)
# Automatically sets:
# - enable_entity_hierarchy=False
# - enable_context_aware_roles=False
# - enable_abac=False
```

**Features**:
- ✅ User management
- ✅ Role-based permissions
- ✅ JWT authentication
- ✅ API keys
- ✅ OAuth (optional)
- ❌ Entity hierarchy
- ❌ Tree permissions
- ❌ Context-aware roles

**See**: [[41-SimpleRBAC]] for complete guide.

### EnterpriseRBAC

**Thin wrapper** for hierarchical RBAC with entity system.

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True,  # Optional
    enable_abac=True                  # Optional
)
# Automatically sets:
# - enable_entity_hierarchy=True (always enabled)
```

**Features**:
- ✅ All SimpleRBAC features
- ✅ Entity hierarchy
- ✅ Tree permissions
- ✅ Multiple memberships
- ✅ Context-aware roles (opt-in)
- ✅ ABAC policies (opt-in)

**See**: [[42-EnterpriseRBAC]] for complete guide.

---

## 3. Services

Services implement business logic and are initialized by `OutlabsAuth` core.

### UserService

**Manages user accounts and profiles.**

```python
auth.user_service.create_user(
    email="user@example.com",
    password="secure_password",
    full_name="John Doe"
)

auth.user_service.get_user(user_id)
auth.user_service.update_user(user_id, updates)
auth.user_service.delete_user(user_id)
```

**Responsibilities**:
- User CRUD operations
- Password management
- Email verification
- Profile management
- User search and filtering

**See**: [[70-User-Service]] for API reference.

### AuthService

**Handles authentication logic.**

```python
auth.auth_service.authenticate(
    email="user@example.com",
    password="password123"
)

auth.auth_service.verify_password(plain_password, hashed_password)
auth.auth_service.hash_password(password)
```

**Responsibilities**:
- Email/password authentication
- Password hashing (argon2id)
- JWT token generation
- Token validation
- Refresh token management

**See**: [[74-Auth-Service]] for API reference.

### RoleService

**Manages roles and role assignments.**

```python
auth.role_service.create_role(
    name="editor",
    permissions=["post:create", "post:update", "post:read"]
)

auth.role_service.get_role(role_id)
auth.role_service.update_role(role_id, updates)
auth.role_service.delete_role(role_id)
```

**Responsibilities**:
- Role CRUD operations
- Permission assignment to roles
- Role assignment to users (SimpleRBAC)
- Context-aware role configuration (optional)

**See**: [[71-Role-Service]] for API reference.

### PermissionService

**Checks permissions and manages permission policies.**

```python
# SimpleRBAC version
auth.permission_service.check_permission(
    user_id=user_id,
    permission="post:delete"
)

# EnterpriseRBAC version
auth.permission_service.check_permission(
    user_id=user_id,
    permission="user:manage_tree",
    entity_id=entity_id
)

# ABAC version
auth.permission_service.check_permission(
    user_id=user_id,
    permission="budget:approve",
    context={
        "user": {"department": "finance"},
        "resource": {"amount": 75000}
    }
)
```

**Responsibilities**:
- Permission checking (RBAC + ABAC)
- Tree permission evaluation
- Permission aggregation from roles
- ABAC policy evaluation (if enabled)

**See**: [[72-Permission-Service]] for API reference.

### ApiKeyService

**Manages API keys for programmatic access.**

```python
auth.api_key_service.create_api_key(
    user_id=user_id,
    name="Production API Key",
    scopes=["api:read", "api:write"]
)

auth.api_key_service.validate_api_key(raw_key)
auth.api_key_service.revoke_api_key(key_id)
```

**Responsibilities**:
- API key generation (with prefixes)
- API key validation (argon2id hashing)
- Rate limiting (Redis counters)
- Temporary locks on abuse
- Key rotation and revocation

**See**: [[73-API-Key-Service]] for API reference.

### ServiceTokenService

**Manages JWT service tokens for microservices.**

```python
auth.service_token_service.create_service_token(
    service_id="analytics-api",
    service_name="Analytics API",
    permissions=["analytics:read", "data:export"],
    expires_days=365
)

auth.service_token_service.validate_service_token(token)
auth.service_token_service.check_service_permission(payload, "analytics:read")
```

**Responsibilities**:
- Service token generation (~0.5ms validation)
- Embedded permissions (zero DB hits)
- Long-lived tokens (default 365 days)
- Service-to-service authentication

**See**: [[24-Service-Tokens]] for complete guide.

### OAuthService

**Handles OAuth/social login flows.**

```python
auth.oauth_service.get_authorization_url(
    provider="google",
    redirect_uri="http://localhost:3000/auth/google/callback"
)

auth.oauth_service.handle_callback(
    provider="google",
    code=code,
    state=state,
    redirect_uri=redirect_uri
)

auth.oauth_service.link_provider(user_id, provider, user_info)
auth.oauth_service.unlink_provider(user_id, provider)
```

**Responsibilities**:
- OAuth flow management (state, PKCE, nonce)
- Provider integration (Google, GitHub, Facebook, Apple)
- Account linking (auto + manual)
- Token exchange and refresh
- Account unlinking with safety checks

**See**: [[30-OAuth-Overview]] for complete guide.

### EntityService (EnterpriseRBAC only)

**Manages entity hierarchy.**

```python
auth.entity_service.create_entity(
    name="Engineering",
    entity_type="department",
    classification="STRUCTURAL",
    parent_id=company_id
)

auth.entity_service.get_ancestors(entity_id)
auth.entity_service.get_descendants(entity_id)
auth.entity_service.move_entity(entity_id, new_parent_id)
```

**Responsibilities**:
- Entity CRUD operations
- Entity hierarchy management
- Closure table updates (O(1) queries)
- Ancestor/descendant queries
- Entity movement and validation

**See**: [[75-Entity-Service]] for API reference.

### MembershipService (EnterpriseRBAC only)

**Manages user memberships in entities.**

```python
auth.membership_service.create_membership(
    user_id=user_id,
    entity_id=entity_id,
    role_ids=[manager_role.id, viewer_role.id]
)

auth.membership_service.get_user_memberships(user_id)
auth.membership_service.get_entity_members(entity_id)
auth.membership_service.remove_membership(membership_id)
```

**Responsibilities**:
- Membership CRUD operations
- Role assignment in entities
- Multiple role support
- Membership queries and filtering

**See**: [[54-Entity-Memberships]] for complete guide.

### PolicyEngine (ABAC only)

**Evaluates ABAC conditions.**

```python
engine = PolicyEvaluationEngine()

context = {
    "user": {"id": "123", "department": "engineering"},
    "resource": {"id": "456", "department": "engineering"},
    "time": {"hour": 14, "is_business_hours": True}
}

condition = Condition(
    attribute="resource.department",
    operator="equals",
    value="user.department"
)

result = engine.evaluate_condition(condition, context)
# Returns True if condition passes
```

**Responsibilities**:
- Condition evaluation (20+ operators)
- Condition group evaluation (AND/OR logic)
- Context management (user, resource, env, time)
- Attribute resolution with dot notation

**See**: [[46-ABAC-Policies]] for complete guide.

---

## 4. Models (Data Layer)

### UserModel

```python
class UserModel(Document):
    email: str                    # Unique email
    hashed_password: Optional[str]  # Nullable for OAuth-only users
    full_name: str
    is_active: bool = True
    is_verified: bool = False
    is_superuser: bool = False
    auth_methods: List[str]       # ["PASSWORD", "GOOGLE", "GITHUB"]
    profile: UserProfile          # Nested profile data
    security: SecuritySettings    # Login attempts, locks
    created_at: datetime
    updated_at: datetime
```

**See**: [[12-Data-Models]] for complete schema.

### RoleModel

```python
class RoleModel(Document):
    name: str                     # Unique role name
    display_name: str
    permissions: List[str]        # Default permissions

    # Optional: Context-aware roles
    entity_type_permissions: Optional[Dict[str, List[str]]]

    # Optional: ABAC conditions
    conditions: List[Condition]
    condition_groups: Optional[List[ConditionGroup]]

    # Enterprise: Entity scope
    entity: Optional[Link["EntityModel"]]
    assignable_at_types: List[str]
```

**See**: [[12-Data-Models]] for complete schema.

### PermissionModel

```python
class PermissionModel(Document):
    name: str                     # e.g., "post:create"
    resource: str                 # e.g., "post"
    action: str                   # e.g., "create"
    description: Optional[str]
```

### RefreshTokenModel

```python
class RefreshTokenModel(Document):
    token: str                    # Hashed refresh token
    user_id: ObjectId
    expires_at: datetime
    created_at: datetime
    revoked: bool = False
```

### ApiKeyModel

```python
class ApiKeyModel(Document):
    user_id: ObjectId
    name: str
    prefix: str                   # First 12 chars (visible)
    hashed_key: str               # argon2id hash
    scopes: List[str]
    expires_at: Optional[datetime]
    is_active: bool = True

    # Rate limiting (Redis counters)
    request_count: int = 0        # Cached in Redis
    last_used_at: Optional[datetime]

    # Security
    is_temporarily_locked: bool = False
    locked_until: Optional[datetime]
```

**See**: [[23-API-Keys]] for complete guide.

### SocialAccount

```python
class SocialAccount(Document):
    user_id: ObjectId
    provider: str                 # "google", "github", "facebook", "apple"
    provider_user_id: str
    email: str
    email_verified: bool
    display_name: Optional[str]
    avatar_url: Optional[str]

    # OAuth tokens (should be encrypted)
    access_token: Optional[str]
    refresh_token: Optional[str]
    token_expires_at: Optional[datetime]

    # Metadata
    provider_data: Dict[str, Any]
    linked_at: datetime
    last_used_at: Optional[datetime]
```

**See**: [[33-OAuth-Account-Linking]] for account linking.

### EntityModel (EnterpriseRBAC only)

```python
class EntityModel(Document):
    name: str
    entity_type: str              # "company", "department", "team", etc.
    classification: str           # "STRUCTURAL" or "ACCESS_GROUP"
    parent: Optional[Link["EntityModel"]]

    # Metadata
    metadata: Dict[str, Any]
    description: Optional[str]
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
```

**See**: [[50-Entity-System]] for entity system.

### MembershipModel (EnterpriseRBAC only)

```python
class MembershipModel(Document):
    user_id: ObjectId
    entity_id: ObjectId
    role_ids: List[ObjectId]      # Multiple roles per entity

    # Metadata
    joined_at: datetime
    updated_at: datetime
```

**See**: [[54-Entity-Memberships]] for memberships.

### ClosureTable (EnterpriseRBAC only)

```python
class ClosureTable(Document):
    ancestor_id: ObjectId
    descendant_id: ObjectId
    depth: int                    # 0 = self, 1 = parent, 2 = grandparent, etc.
```

**See**: [[53-Closure-Table]] for closure table pattern.

---

## 5. Dependencies (FastAPI Integration)

### AuthDeps

**Unified dependency injection** for FastAPI routes (DD-035).

```python
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

@app.get("/protected")
async def protected_route(auth_result = Depends(deps.require_auth())):
    """Require authentication."""
    user = auth_result["metadata"]["user"]
    return {"user_id": user["id"]}

@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    auth_result = Depends(deps.require_permission("post:delete"))
):
    """Require specific permission."""
    await delete_post_from_db(post_id)
    return {"message": "Post deleted"}

@app.get("/admin")
async def admin_only(auth_result = Depends(deps.require_role("admin"))):
    """Require specific role."""
    return {"dashboard": "admin_data"}
```

**Methods**:
- `require_auth(active=True, verified=False, optional=False)`
- `require_permission(permission, entity_id=None)`
- `require_all_permissions(permissions, entity_id=None)`
- `require_any_permission(permissions, entity_id=None)`
- `require_role(role_name)`
- `require_source(source)`  # "jwt", "api_key", "service"

**See**: [[80-Auth-Dependencies]] for complete reference.

### Transport/Strategy Pattern

**Separation of credential delivery from validation** (DD-038).

```python
# Transport: HOW credentials are delivered
class BearerTransport:
    """Extract token from Authorization: Bearer header."""

class ApiKeyTransport:
    """Extract API key from X-API-Key header."""

# Strategy: WHAT validation to perform
class JWTStrategy:
    """Validate JWT token."""

class ApiKeyStrategy:
    """Validate API key against database."""

# Backend: Combines Transport + Strategy
backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret=SECRET_KEY)
)
```

**See**: [[100-Transport-Strategy-Pattern]] for pattern details.

### Router Factories

**Pre-built FastAPI routers** (DD-041).

```python
from outlabs_auth.routers import (
    get_auth_router,
    get_users_router,
    get_api_keys_router,
    get_oauth_router,
    get_oauth_associate_router
)

# Auth endpoints (login, register, refresh)
app.include_router(get_auth_router(auth), prefix="/auth", tags=["auth"])

# User profile endpoints
app.include_router(get_users_router(auth), prefix="/users", tags=["users"])

# API key management
app.include_router(get_api_keys_router(auth), prefix="/api-keys", tags=["api-keys"])

# OAuth login
app.include_router(get_oauth_router(auth), prefix="/oauth", tags=["oauth"])

# OAuth account linking
app.include_router(get_oauth_associate_router(auth), prefix="/oauth/associate", tags=["oauth"])
```

**See**: [[90-Router-Factories-Overview]] for complete reference.

---

## 6. Utilities

### JWT Utils

```python
from outlabs_auth.utils.jwt import (
    generate_tokens,
    decode_access_token,
    decode_refresh_token
)

# Generate access + refresh tokens
access_token, refresh_token = generate_tokens(
    user_id="507f...",
    secret_key=SECRET_KEY,
    access_expire_minutes=15,
    refresh_expire_days=30
)

# Decode and validate
payload = decode_access_token(access_token, secret_key=SECRET_KEY)
```

### Password Hashing

```python
from outlabs_auth.utils.password import (
    hash_password,
    verify_password
)

# Hash password (argon2id)
hashed = hash_password("secure_password")

# Verify password
is_valid = verify_password("secure_password", hashed)
```

### Validation

```python
from outlabs_auth.utils.validation import (
    validate_email,
    validate_password,
    validate_permission_name
)

# Validate email format
validate_email("user@example.com")  # Raises ValueError if invalid

# Validate password strength
validate_password("Secure123!", min_length=8, require_special=True)

# Validate permission format
validate_permission_name("post:create")  # "resource:action"
```

### Security Helpers

```python
from outlabs_auth.oauth.security import (
    generate_state,
    generate_nonce,
    generate_pkce_pair
)

# OAuth state parameter
state = generate_state()  # Cryptographically secure random string

# OIDC nonce
nonce = generate_nonce()

# PKCE code challenge/verifier
code_verifier, code_challenge = generate_pkce_pair(method="S256")
```

---

## Component Interaction Flow

### Authentication Flow

```
1. User provides credentials
   ↓
2. AuthService.authenticate()
   • Validate credentials
   • Check user status (active, not locked)
   ↓
3. AuthService.generate_tokens()
   • Create JWT access token (15 min)
   • Create refresh token (30 days)
   ↓
4. Return tokens to user
```

### Authorization Flow (SimpleRBAC)

```
1. User makes request with JWT
   ↓
2. AuthDeps.require_permission()
   • Extract token from header (Transport)
   • Validate token (Strategy)
   • Get user from token
   ↓
3. PermissionService.check_permission()
   • Get user's roles
   • Aggregate permissions from roles
   • Check if required permission exists
   ↓
4. Allow or Deny
```

### Authorization Flow (EnterpriseRBAC)

```
1. User makes request with JWT + entity context
   ↓
2. AuthDeps.require_permission()
   • Extract token, validate, get user
   ↓
3. PermissionService.check_permission()
   • Get user's memberships in entity
   • Get roles from memberships
   • Get permissions from roles (context-aware if enabled)
   • Check tree permissions (if _tree suffix)
   • Evaluate ABAC conditions (if enabled)
   ↓
4. Allow or Deny
```

---

## Configuration

### Feature Flags

| Flag | Description | Default | Preset |
|------|-------------|---------|--------|
| `enable_entity_hierarchy` | Entity system | False | EnterpriseRBAC: True |
| `enable_context_aware_roles` | Context-based roles | False | Opt-in |
| `enable_abac` | ABAC policies | False | Opt-in |
| `enable_caching` | Redis caching | False | Opt-in |
| `multi_tenant` | Multi-tenant isolation | False | Opt-in |
| `enable_audit_log` | Audit logging | False | Opt-in |
| `enable_notifications` | Notification system | False | Opt-in |

### Complete Configuration Example

```python
auth = OutlabsAuth(
    database=mongo_db,

    # Core settings
    secret_key="your-secret-key-min-32-chars",
    algorithm="HS256",
    access_token_expire_minutes=15,
    refresh_token_expire_days=30,

    # Password requirements
    password_min_length=8,
    require_special_char=True,
    require_uppercase=True,
    require_digit=True,

    # Security
    max_login_attempts=5,
    lockout_duration_minutes=30,

    # API Keys
    api_key_prefix_length=12,
    api_key_rate_limit_per_minute=60,
    api_key_temporary_lock_minutes=30,

    # Feature flags
    enable_entity_hierarchy=True,
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    enable_notifications=False,

    # Optional dependencies
    redis_url="redis://localhost:6379",
    cache_ttl_seconds=300,

    # Enterprise settings
    max_entity_depth=10,
    allowed_entity_types=["company", "department", "team", "project"],
    allow_access_groups=True
)

await auth.initialize()
```

---

## Summary

**Core Components**:
1. ✅ **OutlabsAuth** - Unified core with feature flags
2. ✅ **Presets** - SimpleRBAC, EnterpriseRBAC (thin wrappers)
3. ✅ **Services** - Business logic (User, Auth, Role, Permission, etc.)
4. ✅ **Models** - Data layer (Beanie ODM)
5. ✅ **Dependencies** - FastAPI integration (AuthDeps)
6. ✅ **Utilities** - JWT, password, validation, security

**Key Principles**:
- Single codebase (no duplication)
- Feature flags control capabilities
- Services initialized based on config
- Thin preset wrappers for convenience
- FastAPI-native integration

---

## Next Steps

- **[12. Data Models →](./12-Data-Models.md)** - Complete database schema
- **[10. Architecture Overview →](./10-Architecture-Overview.md)** - System design
- **[41. SimpleRBAC →](./41-SimpleRBAC.md)** - Flat RBAC guide
- **[42. EnterpriseRBAC →](./42-EnterpriseRBAC.md)** - Hierarchical RBAC guide

---

## Further Reading

### Design Decisions
- [DD-032: Unified Architecture](../docs/DESIGN_DECISIONS.md#dd-032)
- [DD-035: Single AuthDeps Class](../docs/DESIGN_DECISIONS.md#dd-035)
- [DD-038: Transport/Strategy Pattern](../docs/DESIGN_DECISIONS.md#dd-038)
- [DD-041: Router Factory Pattern](../docs/DESIGN_DECISIONS.md#dd-041)

### Architecture Patterns
- [Service Layer Pattern](https://martinfowler.com/eaaCatalog/serviceLayer.html)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
