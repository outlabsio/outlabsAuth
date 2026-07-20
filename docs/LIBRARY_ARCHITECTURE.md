# OutlabsAuth Library - Technical Architecture


**Database**: PostgreSQL — SQLModel + SQLAlchemy (async) + asyncpg
**Source of truth**: `outlabs_auth/` and `examples/`. Where this document and the
code disagree, the code is right.

---

## Table of Contents

1. [Overview](#overview)
2. [Package Structure](#package-structure)
3. [Preset Architecture](#preset-architecture)
4. [Data Models](#data-models)
5. [Service Layer](#service-layer)
6. [Authentication System (API Keys & Multi-Source Auth)](#authentication-system-api-keys--multi-source-auth)
7. [Authentication Extensions (Optional)](#authentication-extensions-optional)
8. [Dependency Injection](#dependency-injection)
9. [Host Integration Queries](#host-integration-queries)
10. [Configuration System](#configuration-system)
11. [Testing Strategy](#testing-strategy)
12. [Performance Considerations](#performance-considerations)

---

## Overview

OutlabsAuth is structured as a **single unified core implementation** with thin convenience wrappers for different use cases:

```
OutlabsAuth (Single Core Implementation)
    ├── SimpleRBAC (thin wrapper - flat structure)
    └── EnterpriseRBAC (thin wrapper - entity hierarchy always on)
```

**Architecture**:
- **Single codebase**: One `OutlabsAuth` implementation (no code duplication)
- **Feature flags**: All capabilities controlled by configuration
- **Thin wrappers**: SimpleRBAC and EnterpriseRBAC are 5-10 LOC convenience classes
- **Zero migration complexity**: Switching from Simple → Enterprise is just changing the class name

**Simple vs Enterprise Decision**: Do you have departments/teams/hierarchy?
- **NO** → `SimpleRBAC(database_url=url, secret_key=key)` - disables entity hierarchy
- **YES** → `EnterpriseRBAC(database_url=url, secret_key=key)` - enables entity hierarchy + optional advanced features

---

## Package Structure

```
outlabs_auth/
├── __init__.py                 # Public API exports
├── fastapi.py                  # register_exception_handlers, instrument_fastapi
├── bootstrap.py                # first-run bootstrap
├── cli.py                      # `outlabs-auth` CLI (migrate, bootstrap, doctor, ...)
├── response_builders.py
├── core/
│   ├── auth.py                 # OutlabsAuth — the unified core class
│   ├── config.py               # AuthConfig, SimpleConfig, EnterpriseConfig
│   ├── exceptions.py           # exception hierarchy
│   └── uow.py                  # unit of work
├── database/
│   ├── base.py                 # BaseModel (UUID pk + created_at/updated_at)
│   ├── engine.py               # SQLAlchemy async engine + session factory
│   └── registry.py             # ModelRegistry — preset → models mapping
├── models/
│   └── sql/                    # 33 SQLModel tables
│       ├── user.py             # User
│       ├── role.py             # Role, RolePermission, RoleCondition, ...
│       ├── permission.py       # Permission, PermissionTag, PermissionCondition
│       ├── entity.py           # Entity                    (EnterpriseRBAC)
│       ├── closure.py          # EntityClosure             (EnterpriseRBAC)
│       ├── entity_membership.py        # EntityMembership  (EnterpriseRBAC)
│       ├── entity_membership_history.py
│       ├── user_role_membership.py     # UserRoleMembership (SimpleRBAC)
│       ├── api_key.py          # APIKey, APIKeyScope, APIKeyIPWhitelist
│       ├── api_key_usage_sync_batch.py
│       ├── integration_principal.py
│       ├── auth_challenge.py   # magic links / access codes / OTP
│       ├── social_account.py   # OAuth-linked accounts
│       ├── oauth_state.py
│       ├── token.py            # RefreshToken
│       ├── activity_metric.py  # ActivityMetric, UserActivity, LoginHistory
│       ├── user_audit_event.py
│       ├── system_config.py
│       ├── condition.py
│       └── enums.py
├── services/                   # all take an AsyncSession as first arg
│   ├── auth.py, user.py, role.py, permission.py
│   ├── entity.py, membership.py            # EnterpriseRBAC only
│   ├── api_key.py, api_key_policy.py, integration_principal.py
│   ├── service_token.py, access_scope.py, policy_engine.py
│   ├── activity_tracker.py, notification.py, config.py
│   ├── cache.py, redis_client.py, request_cache.py
│   └── user_audit.py, role_history.py, permission_history.py
├── authentication/             # Transport/Strategy split (DD-038)
│   ├── transport.py            # Bearer, ApiKey, Header, Cookie, QueryParam
│   ├── strategy.py             # JWT, ApiKey, ServiceToken, Superuser, Anonymous
│   └── backend.py              # AuthBackend = Transport + Strategy
├── dependencies/
│   └── __init__.py             # AuthDeps, create_auth_deps
├── presets/
│   ├── simple.py               # SimpleRBAC
│   └── enterprise.py           # EnterpriseRBAC
├── routers/                    # mountable FastAPI routers
│   ├── auth.py, users.py, roles.py, permissions.py
│   ├── entities.py, memberships.py
│   ├── api_keys.py, api_key_admin.py, integration_principals.py
│   ├── oauth.py, oauth_associate.py
│   └── audit.py, config.py, self_service.py, session.py
├── oauth/                      # see Authentication Extensions
├── mail/                       # transactional auth mail
├── messaging/                  # WhatsApp / SMS challenge delivery
├── observability/              # structured logs + Prometheus metrics
│   ├── config.py, service.py, middleware.py, router.py, dependencies.py
├── middleware/
│   ├── uow.py                  # commit-before-response
│   ├── request_cache.py
│   └── resource_context.py
├── integrations/
│   └── host_queries.py         # host-facing read facade for embedded apps
├── workers/
│   ├── api_key_sync.py         # durable usage-counter sync
│   └── token_cleanup.py
├── migrations/                 # packaged Alembic migrations
│   └── env.py                  # version table: outlabs_auth_alembic_version
├── schemas/                    # Pydantic request/response models
└── utils/
    ├── password.py             # argon2id
    ├── jwt.py, crypto.py, rate_limit.py, validation.py

examples/                       # the only integration reference kept honest by tests
├── simple_rbac/
├── enterprise_rbac/
├── abac_cookbook/
└── notifications/

tests/
├── unit/                       # incl. test_readme_quickstart.py — executes the README
└── integration/
```

---

## Preset Architecture

### Core Class: `OutlabsAuth`

**Single unified implementation** - all functionality in one class, controlled by feature flags:

```python
class OutlabsAuth:
    """
    Core auth implementation with all features.
    All capabilities controlled by configuration flags.
    """

    def __init__(
        self,
        database_url: str,  # PostgreSQL connection string
        secret_key: str,    # JWT signing key
        # Feature flags
        enable_entity_hierarchy: bool = False,
        enable_context_aware_roles: bool = False,
        enable_abac: bool = False,
        enable_caching: Optional[bool] = None,
        enable_audit_log: bool = False,  # Reserved for future extended/compliance capture
        # Optional dependencies
        redis_url: Optional[str] = None,
        redis_enabled: Optional[bool] = None,
        notification_service: Optional[NotificationService] = None,
        **kwargs
    ):
        self.database_url = database_url
        self.secret_key = secret_key

        # Configuration
        resolved_redis_enabled = redis_enabled if redis_enabled is not None else bool(redis_url)
        resolved_enable_caching = enable_caching if enable_caching is not None else resolved_redis_enabled
        self.config = AuthConfig(
            enable_entity_hierarchy=enable_entity_hierarchy,
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            enable_caching=resolved_enable_caching,
            enable_audit_log=enable_audit_log,
            redis_enabled=resolved_redis_enabled,
            redis_url=redis_url,
            **kwargs
        )

        # Models
        self.user_model = user_model
        self.role_model = role_model
        self.permission_model = permission_model
        self.entity_model = entity_model if enable_entity_hierarchy else None

        # Initialize all services
        self._init_services()

    def _init_services(self):
        """Initialize all services based on configuration"""
        # Core services (always available)
        self.auth_service = AuthService(self.database, self.user_model, self.config)
        self.user_service = UserService(self.database, self.user_model, self.config)
        self.role_service = RoleService(self.database, self.role_model, self.config)
        self.api_key_service = APIKeyService(self.database, self.config)
        self.service_token_service = ServiceTokenService(self.database, self.config)

        # Permission service (adapts based on features)
        if self.config.enable_entity_hierarchy:
            self.permission_service = EnterprisePermissionService(
                self.database, self.permission_model, self.config
            )
            self.entity_service = EntityService(
                self.database, self.entity_model, self.config
            )
            self.membership_service = MembershipService(
                self.database, self.config
            )
        else:
            self.permission_service = BasicPermissionService(
                self.database, self.permission_model, self.config
            )
            self.entity_service = None  # Not available
            self.membership_service = None  # Not available

        # Optional services
        self.redis_client = RedisClient(self.config) if self.config.redis_enabled else None
        if self.config.redis_enabled and self.config.enable_caching:
            self.cache_service = CacheService(self.redis_client)
        else:
            self.cache_service = None

    async def get_current_user(self, token: str) -> UserModel:
        """Get current authenticated user from JWT token"""
        return await self.auth_service.get_current_user(token)

    async def initialize(self):
        """Initialize database engine and create tables"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlmodel import SQLModel

        self.engine = create_async_engine(self.database_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)

        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
```

### Wrapper 1: SimpleRBAC

**Thin convenience wrapper** (~5 LOC) - disables entity hierarchy by default:

```python
class SimpleRBAC(OutlabsAuth):
    """
    Flat RBAC for simple applications.
    Thin wrapper that disables entity hierarchy.
    """

    def __init__(self, database_url: str, secret_key: str, **kwargs):
        super().__init__(
            database_url=database_url,
            secret_key=secret_key,
            enable_entity_hierarchy=False,  # Force flat structure
            enable_context_aware_roles=False,
            enable_abac=False,
            **kwargs
        )
```

**Purpose**: Basic role-based access control without entity hierarchy.

**Features** (always available):
- User management
- Role assignment (single role per user)
- Flat permission system
- JWT authentication
- API key authentication
- Service token authentication
- Multi-source auth via the AuthDeps backend list (JWT / API key / service token)

**Example Usage**:
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

# Use in routes
@app.get("/users/me")
async def get_me(user = Depends(lambda: auth.deps.authenticated())):
    return {"id": str(user.id), "email": user.email}

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    _ = Depends(lambda: auth.deps.require_permission("user:delete"))
):
    return await auth.user_service.delete_user(user_id)
```

**What's Available**:
- `auth.auth_service` - Login, logout, refresh
- `auth.user_service` - User CRUD
- `auth.role_service` - Role management
- `auth.permission_service` - Basic permission checks (no entity context)
- `auth.api_key_service` - API key management
- `auth.service_token_service` - JWT service tokens
- `auth.entity_service` - ❌ Not available (raises error if accessed)
- `auth.membership_service` - ❌ Not available (raises error if accessed)

### Wrapper 2: EnterpriseRBAC

**Thin convenience wrapper** (~10 LOC) - enables entity hierarchy by default:

```python
class EnterpriseRBAC(OutlabsAuth):
    """
    Hierarchical RBAC with entity system.
    Thin wrapper that enables entity hierarchy + optional advanced features.
    """

    def __init__(
        self,
        database_url: str,
        secret_key: str,
        enable_context_aware_roles: bool = False,
        enable_abac: bool = False,
        **kwargs
    ):
        super().__init__(
            database_url=database_url,
            secret_key=secret_key,
            enable_entity_hierarchy=True,  # Force entity hierarchy ON
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            **kwargs
        )
```

**Purpose**: Full-featured auth system with entity hierarchy and optional advanced features.

**Core Features** (Always Included):
- Everything from SimpleRBAC
- Entity hierarchy (organizational structure)
- Entity closure table (O(1) ancestor/descendant queries)
- Multiple roles per user (via entity memberships)
- Tree permissions (`resource:action_tree`)
- Entity context in permission checks

**Optional Features** (Opt-in via flags/config):
- Context-aware roles (permissions vary by entity type) - `enable_context_aware_roles=True`
- ABAC conditions (attribute-based access control) - `enable_abac=True`
- Permission caching (Redis) - enabled by `redis_url`; opt out with `enable_caching=False`
- Entity-isolated operation via root-entity scoping

**Core History Surfaces** (included in current runtime):
- User lifecycle timeline via `user_audit_events`
- Entity membership lifecycle via `entity_membership_history`
- Role/permission definition history via dedicated history tables

**Example - Basic Configuration** (entity hierarchy only):
```python
from outlabs_auth import EnterpriseRBAC

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mydb"
SECRET_KEY = "your-secret-key"

# Minimal configuration - just entity hierarchy
auth = EnterpriseRBAC(database_url=DATABASE_URL, secret_key=SECRET_KEY)
await auth.initialize()

# Create entity hierarchy
org = await auth.entity_service.create_entity(
    name="my_org",
    entity_class="structural",
    entity_type="organization"
)

dept = await auth.entity_service.create_entity(
    name="engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=org.id
)

# Assign user to entity with multiple roles
await auth.membership_service.add_member(
    entity_id=dept.id,
    user_id=user.id,
    role_ids=[manager_role.id, developer_role.id]
)

# Entity-scoped permission check. `require_permission` picks the entity context
# up from the `entity_id` path param automatically.
async def require_entity_update(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    dep_fn = auth.deps.require_permission("entity:update")
    return await dep_fn(request=request, session=session)


@app.put("/entities/{entity_id}")
async def update_entity(
    entity_id: UUID,
    data: EntityUpdate,
    auth_result: dict = Depends(require_entity_update),
    session: AsyncSession = Depends(get_session),
):
    return await auth.entity_service.update_entity(session, entity_id, data)
```

**Example - Full Configuration** (all optional features enabled):
```python
from outlabs_auth import EnterpriseRBAC

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mydb"
SECRET_KEY = "your-secret-key"

# Full configuration with all optional features
auth = EnterpriseRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    redis_url="redis://localhost:6379",
    enable_context_aware_roles=True,  # Opt-in
    enable_abac=True,                 # Opt-in
)

# Context-aware role
regional_manager = await auth.role_service.create_role(
    name="regional_manager",
    permissions=["entity:read", "user:read"],  # Default
    entity_type_permissions={
        "region": [
            "entity:manage_tree",
            "user:manage_tree",
            "budget:approve"
        ],
        "office": ["entity:read", "user:read"],
        "team": ["entity:read"]
    }
)

# ABAC permission with conditions
invoice_approval = await auth.permission_service.create_permission(
    name="invoice:approve",
    conditions=[
        {
            "attribute": "resource.value",
            "operator": "LESS_THAN_OR_EQUAL",
            "value": 50000
        }
    ]
)

# Check with ABAC
result = await auth.permission_service.check_permission_with_context(
    user_id=user.id,
    permission="invoice:approve",
    entity_id=entity.id,
    resource_attributes={"value": 35000}
)
```

**What's Available**:
- `auth.auth_service` - Login, logout, refresh
- `auth.user_service` - User CRUD
- `auth.role_service` - Role management
- `auth.permission_service` - Enterprise permission checks (with entity context + tree permissions)
- `auth.api_key_service` - API key management
- `auth.service_token_service` - JWT service tokens
- `auth.entity_service` - ✅ Entity hierarchy management
- `auth.membership_service` - ✅ Entity membership management
- `auth.host_query_service` - ✅ Host-facing read facade for embedded app integrations
- `auth.cache_service` - ✅ Available when Redis is enabled and permission caching is not explicitly disabled

---

## Data Models

All models are **SQLModel** classes deriving from `outlabs_auth.database.base.BaseModel`,
which supplies a UUID v4 primary key plus `created_at` / `updated_at`. There are
33 tables; the authoritative definitions live in `outlabs_auth/models/sql/` and
the preset-to-model mapping in `outlabs_auth/database/registry.py`. The sketches
below name fields and constraints — read the source for exact column types.

### Which models each preset registers

`ModelRegistry.get_models(enable_entity_hierarchy=...)` decides this.

**Core (always registered)** — `User`, `Role`, `Permission`, `RefreshToken`,
`IntegrationPrincipal`, `APIKey`, `SocialAccount`, `OAuthState`, `ActivityMetric`,
`RoleDefinitionHistory`, `PermissionDefinitionHistory`, `UserAuditEvent`.

**SimpleRBAC adds** — `UserRoleMembership`.

**EnterpriseRBAC adds** — `Entity`, `EntityMembership`, `EntityMembershipRole`,
`EntityClosure`, `EntityMembershipHistory`.

Note the class names are `User` / `Role` / `Permission`, not `UserModel` /
`RoleModel` / `PermissionModel`.

### Core Models (All Presets)

#### User → `users`
```python
class UserStatus(str, Enum):
    ACTIVE = "active"
    INVITED = "invited"      # invited but hasn't set a password yet
    SUSPENDED = "suspended"  # temporary, can be auto-lifted
    BANNED = "banned"        # permanent, manual lift required
    DELETED = "deleted"      # soft-deleted (GDPR)


class User(BaseModel, table=True):
    __tablename__ = "users"

    # Optional root-entity scoping
    root_entity_id: Optional[UUID]

    # Authentication
    email: str
    hashed_password: Optional[str]   # None for OAuth-only users
    auth_methods: List[str]

    # Profile (flat — there is no embedded UserProfile)
    first_name: Optional[str]
    last_name: Optional[str]
    avatar_url: Optional[str]
    phone: Optional[str]
    locale: Optional[str]
    timezone: Optional[str]

    # Status
    status: UserStatus = UserStatus.ACTIVE
    is_superuser: bool = False
    email_verified: bool = False
    phone_verified: bool = False
    suspended_until: Optional[datetime]
    deleted_at: Optional[datetime]

    # Security
    last_login: Optional[datetime]
    last_activity: Optional[datetime]
    last_password_change: Optional[datetime]
    failed_login_attempts: int = 0
    locked_until: Optional[datetime]

    # Token flows: password reset, email verification, invite
    # (see outlabs_auth/models/sql/user.py)
```

`full_name` is a property that combines the names and falls back to the email.

#### Role → `roles`
Role permissions are **join tables**, not embedded lists:

- `RolePermission` → `role_permissions` (role ↔ permission)
- `RoleCondition` → `role_conditions` (ABAC conditions on a role)
- `RoleEntityTypePermission` → `role_entity_type_permissions` (context-aware roles:
  permissions that vary by entity type)
- `ConditionGroup` → `condition_groups`

Role scoping fields (`scope_entity_id`, `scope`, `is_auto_assigned`) implement
DD-050 / DD-053. See `outlabs_auth/models/sql/role.py`.

#### Permission → `permissions`
Named `resource:action` (e.g. `user:create`), with `resource` and `action` parsed
out. Related tables:

- `PermissionCondition` → `permission_conditions` (ABAC)
- `PermissionTag` / `PermissionTagLink` → `permission_tags`, `permission_tag_links`

#### UserRoleMembership → `user_role_memberships` (SimpleRBAC only)
```python
class UserRoleMembership(BaseModel, table=True):
    """User-role membership for SimpleRBAC (flat, no entity context). DD-047."""
    __tablename__ = "user_role_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role_membership"),
        Index("ix_urm_role_id", "role_id"),
        Index("ix_urm_user_status", "user_id", "status"),
    )

    user_id: UUID   # FK → users.id
    role_id: UUID   # FK → roles.id

    status: MembershipStatus

    # Time-based assignment (optional)
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
```

The unique constraint is on `(user_id, role_id)`, so **a SimpleRBAC user may hold
multiple roles** — the membership row is the grant, not a single-role field.

**Why a membership table for SimpleRBAC?**
- **Audit trail**: track who assigned a role and when
- **Time-based roles**: optional validity window
- **Consistent pattern**: same shape as EnterpriseRBAC, minus entities
- **Easy migration**: trivial upgrade path to EnterpriseRBAC
- **Industry standard**: Django, Keycloak, etc. all use membership tables

### Enterprise Models (EnterpriseRBAC only)

#### Entity → `entities`
```python
class EntityClass(str, Enum):
    STRUCTURAL = "structural"      # organizational units (company, department, team)
    ACCESS_GROUP = "access_group"  # permission groupings (project, resource pool)


class Entity(BaseModel, table=True):
    __tablename__ = "entities"

    # Identity
    name: str
    display_name: str
    slug: str
    description: Optional[str]

    # Classification
    entity_class: EntityClass
    entity_type: str  # flexible: "department", "team", ...

    # Hierarchy — a plain FK, plus denormalised depth/path
    parent_id: Optional[UUID]   # FK → entities.id
    depth: int
    path: Optional[str]

    # Status
    status: str = "active"
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]

    # Limits
    max_members: Optional[int]
    max_depth: Optional[int]
```

`Entity.metadata` is future design intent only. It is intentionally absent from the
current persisted SQL model and live API contract.

#### EntityMembership → `entity_memberships`
```python
class EntityMembership(BaseModel, table=True):
    __tablename__ = "entity_memberships"

    user_id: UUID     # FK → users.id
    entity_id: UUID   # FK → entities.id

    joined_at: datetime
    joined_by_id: Optional[UUID]

    # Time-based membership
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]

    status: MembershipStatus
```

Multiple roles per membership are carried by the junction table
`EntityMembershipRole` → `entity_membership_roles`, not by a list field on the
membership.

#### EntityClosure → `entity_closure`
```python
class EntityClosure(BaseModel, table=True):
    """Stores every ancestor-descendant relationship for O(1) tree queries."""
    __tablename__ = "entity_closure"
    __table_args__ = (
        UniqueConstraint("ancestor_id", "descendant_id", name="uq_entity_closure"),
        Index("ix_closure_ancestor_depth", "ancestor_id", "depth"),
        Index("ix_closure_descendant_depth", "descendant_id", "depth"),
    )

    ancestor_id: UUID    # FK → entities.id
    descendant_id: UUID  # FK → entities.id
    depth: int           # 0 = self, 1 = direct child, ...
```

For the hierarchy `Platform → Org → Dept → Team`, the stored rows are
`(Platform, Platform, 0)`, `(Platform, Org, 1)`, `(Platform, Dept, 2)`,
`(Platform, Team, 3)`, `(Org, Org, 0)`, `(Org, Dept, 1)`, and so on.

**Closure table benefits**:
- **O(1) ancestor queries**: one query for all ancestors
- **O(1) descendant queries**: one query for all descendants
- **Tree permission performance**: 20x faster than recursive queries (DD-036)
- **Unlimited depth**: no degradation on deep hierarchies
- **Simple maintenance**: auto-maintained on entity create/move/delete

The composite `(id, depth)` indexes cover single-column lookups via their leading
prefix, so the redundant single-column btrees were dropped. Inserts cost
O(depth x subtree) rows per entity create/move — that is the trade for the O(1)
reads.

**Example queries** (SQLAlchemy):
```python
# All ancestors, nearest first
ancestors = (await session.execute(
    select(EntityClosure)
    .where(EntityClosure.descendant_id == entity_id, EntityClosure.depth > 0)
    .order_by(EntityClosure.depth)
)).scalars().all()

# All descendants
descendants = (await session.execute(
    select(EntityClosure)
    .where(EntityClosure.ancestor_id == entity_id, EntityClosure.depth > 0)
)).scalars().all()

# Is A an ancestor of B?
is_ancestor = (await session.execute(
    select(EntityClosure.id)
    .where(EntityClosure.ancestor_id == a_id, EntityClosure.descendant_id == b_id)
    .limit(1)
)).first() is not None
```

### Isolation model

There is no `platform_id` and no tenant mode. Isolation is entity-based:
`root_entity_id` scopes users and roles to a root entity (an organization), and
DD-056 scopes user-management routes to the actor's trees. See
`docs/SEC-4_TENANT_ISOLATION_INVESTIGATION.md`.

---

## Service Layer

### AuthService
```python
class AuthService:
    """Handles authentication logic"""

    async def login(self, email: str, password: str) -> TokenPair:
        """Authenticate user and return tokens"""
        pass

    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token"""
        pass

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Get new access token using refresh token"""
        pass

    async def get_current_user(self, token: str) -> UserModel:
        """Validate JWT and return user"""
        pass
```

### PermissionService

#### BasicPermissionService (Simple preset)
```python
class BasicPermissionService:
    """Simple permission checking without hierarchy"""

    async def check_permission(
        self,
        user_id: str,
        permission: str
    ) -> bool:
        """Check if user has permission"""
        # Get user's role
        # Check if role has permission
        pass

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for user"""
        pass
```

#### EnterprisePermissionService (EnterpriseRBAC)
```python
class EnterprisePermissionService(BasicPermissionService):
    """Permission checking with entity hierarchy and tree permissions"""

    async def check_permission(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check permission with entity context.
        Returns (has_permission, source)

        Handles:
        - Direct permissions in entity
        - Tree permissions from parent entities
        - Platform-wide permissions (_all suffix)
        """
        pass

    async def check_tree_permission(
        self,
        user_id: str,
        permission: str,
        target_entity_id: str
    ) -> bool:
        """
        Check if user has tree permission in any parent entity.
        Example: entity:update_tree in parent allows updating children.
        """
        pass

    async def check_permission_with_context(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
        resource_attributes: Optional[Dict[str, Any]] = None
    ) -> PolicyResult:
        """
        Full RBAC + ReBAC + ABAC evaluation (when ABAC enabled).

        Steps:
        1. Check RBAC (does user have permission in role?)
        2. Check ReBAC (is entity relationship valid?)
        3. Check ABAC (do conditions pass?) - only if enable_abac=True

        Note: Redis-backed permission caching is automatically applied when Redis is enabled.
        """
        pass
```

### EntityService (EnterpriseRBAC only)
```python
class EntityService:
    """Entity hierarchy management"""

    async def create_entity(
        self,
        name: str,
        entity_class: str,
        entity_type: str,
        parent_id: Optional[str] = None,
        **kwargs
    ) -> EntityModel:
        """Create new entity"""
        # Validate entity type
        # Check circular hierarchy
        # Validate parent relationship
        pass

    async def get_entity_path(self, entity_id: str) -> List[EntityModel]:
        """Get path from root to entity"""
        pass

    async def get_descendants(
        self,
        entity_id: str,
        entity_type: Optional[str] = None
    ) -> List[EntityModel]:
        """Get all descendants of entity"""
        pass
```

---

## Authentication System (API Keys & Multi-Source Auth)

**Compatibility**: Both SimpleRBAC and EnterpriseRBAC
**Source**: `outlabs_auth/authentication/`, `outlabs_auth/services/api_key.py`

### Overview

The authentication system provides multi-source authentication supporting users (JWT), API keys (owned by a user or by an integration principal), and service tokens for internal service-to-service calls. Every source resolves through the same ordered list of `AuthBackend`s on `AuthDeps` and yields the same plain-`dict` result shape, so one route dependency serves all of them.

**Auth Sources** (priority order):
1. **Superuser** - Admin override tokens
2. **Service accounts** - Internal service authentication
3. **API keys** - External integrations and webhooks
4. **Users** - JWT-based user authentication
5. **Anonymous** - Optional public access

### Authentication Result

There is **no `AuthContext` class** and no `outlabs_auth/auth_context.py`.
Authentication returns a **plain `dict`**, and permission enforcement happens in
the dependency (`require_permission`), not through helper methods on a context
object.

The pipeline follows the Transport/Strategy split (DD-038, borrowed from
FastAPI-Users):

- **Transport** (`outlabs_auth/authentication/transport.py`) — *how* credentials
  arrive: Bearer header, `X-API-Key` header, cookie.
- **Strategy** (`outlabs_auth/authentication/strategy.py`) — *how* they are
  validated: JWT decode, API-key lookup, service-token verify.
- **AuthBackend** (`outlabs_auth/authentication/backend.py`) — pairs one Transport
  with one Strategy under a name.

`AuthDeps` holds an ordered list of backends and tries each in turn. A cheap
`has_credentials(request)` hint lets it skip the whole pipeline for unauthenticated
requests.

The returned dict always carries `user`, `user_id`, `source`, and `metadata`. The
remaining keys depend on the source:

```python
# source="jwt"
{
    "user": User,          # ORM instance
    "user_id": "…",
    "source": "jwt",
    "metadata": {...},     # decoded JWT payload
    "jti": "…",            # token id, used for logout
}

# source="api_key", key owned by a user
{
    "user": User,
    "user_id": "…",
    "source": "api_key",
    "api_key": APIKey,
    "metadata": {...},
}

# source="api_key", key owned by an integration principal (no user account)
{
    "user": None,
    "user_id": None,
    "integration_principal": IntegrationPrincipal,
    "integration_principal_id": "…",
    "source": "api_key",
    "api_key": APIKey,
    "metadata": {...},
}

# source="service_token"
{
    "user": None,          # services have no user account
    "user_id": None,
    "source": "service_token",
    "service_id": "…",
    "service_name": "…",
    "metadata": {...},     # decoded JWT payload
}
```

**Always check `user` for `None`** before touching it — API keys held by an
integration principal and service tokens both authenticate successfully with no
user attached.

`require_auth(active=True, verified=False, optional=False)` applies the post-auth
gates: `active` rejects users failing `can_authenticate()`, `verified` requires
`email_verified`, and `optional` returns `None` instead of raising when no
credentials are present.

### API Key Models

```python
# outlabs_auth/models/api_key.py
from enum import Enum
from typing import List, Optional
from datetime import datetime

class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"  # temporarily disabled
    REVOKED = "revoked"      # permanently disabled
    EXPIRED = "expired"      # past expiration date


class APIKeyKind(str, Enum):
    PERSONAL = "personal"
    SYSTEM_INTEGRATION = "system_integration"


class APIKey(BaseModel, table=True):
    """API keys for service-to-service authentication. Table: api_keys"""
    __tablename__ = "api_keys"

    # Identification
    name: str
    description: Optional[str]
    prefix: str      # first 16 chars of the key, stored for lookup/display
    key_hash: str    # SHA-256 hex digest of the full key

    # Ownership — exactly one of these
    owner_id: Optional[UUID]                   # FK → users.id
    integration_principal_id: Optional[UUID]   # FK → integration_principals.id

    key_kind: APIKeyKind
    status: APIKeyStatus

    # Lifecycle
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: Optional[int]
    rate_limit_per_day: Optional[int]

    # Entity scoping (EnterpriseRBAC)
    entity_id: Optional[UUID]
    inherit_from_tree: bool = False
```

Scopes and IP whitelists are **separate tables**, not list columns:

- `APIKeyScope` → `api_key_scopes`
- `APIKeyIPWhitelist` → `api_key_ip_whitelist`
- `APIKeyUsageSyncBatch` → `api_key_usage_sync_batches` (idempotency receipts for
  durable usage-counter sync)

Access control is **scope-based**, not permission-based — see DD-028.

#### Key generation and hashing

```python
@staticmethod
def generate_key(prefix_type: str = "sk_live") -> tuple[str, str]:
    """Returns (full_key, prefix). Store the prefix, hash the full key."""
    key_material = secrets.token_hex(32)
    full_key = f"{prefix_type}_{key_material}"
    prefix = full_key[:16]
    return full_key, prefix

@staticmethod
def hash_key(full_key: str) -> str:
    """Hash an API key using SHA-256 (hex-encoded for storage)."""
    return hashlib.sha256(full_key.encode()).hexdigest()
```

**Why SHA-256 and not argon2id?** API keys are 32 bytes of CSPRNG output, not
user-chosen secrets. There is no dictionary to attack, so a slow KDF buys nothing
and would put ~100ms on every authenticated request. Argon2id is used for **user
passwords** (`outlabs_auth/utils/password.py`, tunable via `argon2_time_cost` /
`argon2_memory_cost_kib` / `argon2_parallelism`), where it does matter. See DD-028.

### API Key Service

`outlabs_auth/services/api_key.py`. Every method takes an `AsyncSession` as its
first argument — the service does not own a session.

```python
raw_key, api_key = await auth.api_key_service.create_api_key(
    session,
    name="production_api",
    owner_id=user_id,
    scopes=["user:read", "entity:read"],
    rate_limit_per_minute=100,
    ip_whitelist=["10.0.0.0/8"],     # optional
    entity_id=dept.id,               # optional, EnterpriseRBAC
    inherit_from_tree=True,          # key also covers descendants
    key_kind=APIKeyKind.PERSONAL,
    expires_in_days=90,
    prefix_type="sk_live",
)
# raw_key is returned ONCE and cannot be recovered.

api_key, usage_count = await auth.api_key_service.verify_api_key(
    session,
    api_key_string=raw_key,
    required_scope="user:read",
    entity_id=dept.id,
    ip_address=request.client.host,
)
```

`verify_api_key` returns `(APIKey | None, usage_count)`. Usage is tracked through
Redis `INCR` counters and synced to PostgreSQL in batches with an idempotency
receipt, so a worker failure loses neither counts nor double-counts (DD-033).

Repeated verification failures put the key in a **temporary lock** (30-minute
cooldown) rather than permanently revoking it (DD-028) — a leaked-key probe
should not let an attacker deny service to a legitimate integration.

**Fails closed**: when Redis rate limiting is configured but unavailable,
verification raises `AuthenticationInfrastructureError` (503) rather than
silently bypassing the configured limit.

### Integration Principals

There is no `ServiceAccountModel`. Non-human callers are modelled as
`IntegrationPrincipal` → `integration_principals`:

```python
class IntegrationPrincipal(BaseModel, table=True):
    __tablename__ = "integration_principals"

    name: str
    description: Optional[str]
    status: IntegrationPrincipalStatus
    scope_kind: IntegrationPrincipalScopeKind
    anchor_entity_id: Optional[UUID]   # FK → entities.id
    inherit_from_tree: bool
    allowed_scopes: List[str]
    created_by_user_id: Optional[UUID]
```

Roles attach via `IntegrationPrincipalRole` → `integration_principal_roles`. An
`APIKey` belongs to *either* a `User` (`owner_id`) or an `IntegrationPrincipal`
(`integration_principal_id`).

### Multi-Source Authentication

There is no `MultiSourceAuthService` and no `outlabs_auth/services/multi_source_auth.py`.
Multi-source auth is the ordered **backend list** on `AuthDeps`, assembled in
`OutlabsAuth._init_backends()` (`outlabs_auth/core/auth.py`):

| Backend | Transport | Strategy | Registered when |
|---------|-----------|----------|-----------------|
| `jwt` | `BearerTransport` | `JWTStrategy` | always |
| `api_key` | `ApiKeyTransport(header_name="X-API-Key")` | `ApiKeyStrategy` | `api_key_service` is present |
| `service_token` | `BearerTransport` | `ServiceTokenStrategy` | `service_token_service` is present |

`AuthDeps` tries each backend in order and returns the first result, so ordering is
precedence. Additional strategies exist in `outlabs_auth/authentication/strategy.py`
(`SuperuserStrategy`, `AnonymousStrategy`) alongside further transports
(`HeaderTransport`, `CookieTransport`, `QueryParamTransport`) — pair them into an
`AuthBackend` to use them.

`JWTStrategy` also enforces token blacklisting through Redis when
`enable_token_blacklist` is set, and rejects tokens issued before the user's last
password change (`jwt_stale_password_change`).

### Dependency Patterns

There is no `SimpleDeps` and no `MultiSourceDeps` — there is one `AuthDeps` class
(DD-035), reachable as `auth.deps` after `await auth.initialize()`.

```python
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# `auth.deps` does not exist until initialize() has run, so build the dependency
# inside a function rather than at import time.
async def require_post_create(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    dep_fn = auth.deps.require_permission("post:create")
    return await dep_fn(request=request, session=session)


@app.post("/posts")
async def create_post(
    payload: PostCreate,
    auth_result: dict = Depends(require_post_create),
    session: AsyncSession = Depends(get_session),
):
    user = auth_result["user"]      # may be None for API-key/service callers
    ...
```

Key `AuthDeps` methods:

- `require_auth(active=True, verified=False, optional=False)` — authenticate only
- `require_permission(*permissions, require_all=False, allow_entity_context_header=False, resource_context_provider=None)`
  — authenticate **and** enforce permissions. Entity context is read from the
  `entity_id` path or query param, and from the `X-Entity-Context` header only when
  `allow_entity_context_header=True` (the header is untrusted by default; see
  `trust_resource_context_header`).
- `require_in_entity(*permissions, entity_id)` — entity-scoped check
- `require_superuser()` — superuser gate (DD-051)

This is a real pattern from `examples/simple_rbac/main.py`, which is exercised by
tests.

### Rate Limiting

Two separate mechanisms, often confused:

**1. `RateLimiter`** (`outlabs_auth/utils/rate_limit.py`) — a simple in-memory
sliding window used by the challenge/password-reset request paths. It takes no
Redis client; it is per-process and therefore per-instance.

```python
class RateLimiter:
    """Simple in-memory rate limiter with sliding window. Async-safe."""

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_rate_limited(
        self,
        key: str,                  # e.g. email address or IP
        max_requests: int = 3,
        window_seconds: int = 300,
    ) -> Tuple[bool, int]:
        """Returns (is_limited, seconds_until_reset)."""
```

Note the return contract: `(is_limited, seconds_until_reset)` — **not**
`(allowed, remaining)`. `cleanup()` drops keys idle for over an hour and should be
called periodically.

For multi-instance deployments this in-memory window is per-instance, so the
effective limit is `max_requests x instance_count`. Size accordingly.

**2. API-key rate limiting** — Redis-backed counters (`rate_limit_per_minute`,
`rate_limit_per_hour`, `rate_limit_per_day` on `APIKey`), enforced inside
`verify_api_key`. This one is distributed and **fails closed**: if Redis is
configured but unreachable, verification raises
`AuthenticationInfrastructureError` (503) instead of letting the request through.

There is no `RateLimitDeps`, no per-auth-source limit table, and no
`outlabs_auth/services/rate_limiter.py`.

### Usage Examples

```python
from fastapi import Depends, FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession
from outlabs_auth import SimpleRBAC

app = FastAPI()
auth = SimpleRBAC(
    database_url=os.getenv("DATABASE_URL"),
    secret_key=os.getenv("SECRET_KEY"),   # >=32 chars
    redis_url=os.getenv("REDIS_URL"),     # optional
)


@app.on_event("startup")
async def startup():
    await auth.initialize()          # `auth.deps` exists only after this


async def require_user_delete(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    dep_fn = auth.deps.require_permission("user:delete")
    return await dep_fn(request=request, session=session)


@app.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    auth_result: dict = Depends(require_user_delete),
    session: AsyncSession = Depends(get_session),
):
    # Accepts a JWT, an API key, or a service token — same dependency.
    if auth_result["source"] == "api_key":
        await log_api_usage(auth_result["api_key"])
    return await auth.user_service.delete_user(session, user_id)
```

Creating and using an API key:

```python
# Create (raw_key is returned exactly once)
async with auth.get_session() as session:
    raw_key, key = await auth.api_key_service.create_api_key(
        session,
        name="production_api",
        owner_id=user_id,
        scopes=["api:read", "api:write"],
        rate_limit_per_minute=100,
        prefix_type="sk_live",
    )
    await session.commit()

# Use it (external service)
headers = {"X-API-Key": raw_key}
```

Rate limiting is implemented by `RateLimiter` in `outlabs_auth/utils/rate_limit.py`
and applied inside the API-key and challenge paths — it is not a separate
`RateLimitDeps` dependency you attach to routes.

The library also ships routers you can mount rather than hand-rolling: `auth`,
`users`, `roles`, `permissions`, `entities`, `memberships`, `api_keys`,
`api_key_admin`, `integration_principals`, `oauth`, `oauth_associate`, `audit`,
`config`, `self_service`, `session` (`outlabs_auth/routers/`).

### Security Best Practices

See [SECURITY.md](SECURITY.md) for comprehensive security guidelines.

**Key Security Requirements**:
1. **SHA-256 hashing for API keys** — they are 32 bytes of CSPRNG output, so a slow
   KDF buys nothing. **Argon2id for user passwords**, where it does matter.
2. **`secret_key` must be >=32 characters** — HS256 rejects anything shorter, and
   construction raises.
3. **Never log raw keys** — only prefixes. `key_hash` is all that is stored.
4. **Optional expiration** with a rotation API (90 days recommended)
5. **IP whitelisting** strictly enforced when configured
6. **Temporary locks** after repeated failures (30-minute cooldown) rather than
   permanent revocation (DD-028)
7. **Rate limiting** per key via Redis counters — and it **fails closed**: if Redis
   is configured but unavailable, requests get a retryable 503
   (`AuthenticationInfrastructureError`) rather than silently bypassing the limit
8. **`debug=False`** in `register_exception_handlers` — it is what keeps raw
   exception text out of responses
9. **Untrusted entity-context header** — `X-Entity-Context` is ignored unless
   explicitly opted into

---

## Authentication Extensions (Optional)

**Compatibility**: Work with both SimpleRBAC and EnterpriseRBAC — these are core
feature flags and injected services, not preset-specific modules.

### Overview

Authentication extensions add capabilities beyond password login. All are optional
and adopted independently.

There is **no `outlabs_auth/extensions/` package**. The real layout is:

```
outlabs_auth/
├── oauth/                       # OAuth / social login
│   ├── provider.py              # OAuthProvider base
│   ├── provider_factories.py    # httpx-oauth backed factories (optional dep)
│   ├── providers/
│   │   ├── google.py
│   │   ├── facebook.py
│   │   ├── apple.py
│   │   └── github.py
│   ├── security.py              # PKCE, nonce, state, constant-time compare
│   ├── state.py                 # server-side state records
│   ├── models.py                # transport dataclasses (not tables)
│   └── exceptions.py            # OAuthError hierarchy (NOT OutlabsAuthException)
├── mail/                        # transactional auth mail
│   ├── service.py               # ComposedAuthMailService
│   ├── composer.py
│   ├── providers.py
│   └── types.py                 # intents + delivery results
├── messaging/                   # WhatsApp / SMS challenge delivery
│   └── types.py
└── models/sql/
    ├── social_account.py        # SocialAccount    → social_accounts
    ├── oauth_state.py           # OAuthState       → oauth_states
    └── auth_challenge.py        # AuthChallenge    → auth_challenges
```

**Not implemented**: TOTP/MFA, backup codes, and WebAuthn/passkeys. There is no
`MFAMethodModel`, no `mfa` service, and no `enable_mfa` flag.

### Extension 1: Mail and Notifications

**Purpose**: Deliver auth mail without vendor lock-in. The library defines the
intent types and calls an **injected service**; it ships no vendor integration.

`outlabs_auth/mail/types.py` defines the intents:

- `InviteMailIntent`
- `ForgotPasswordMailIntent`
- `PasswordResetConfirmationMailIntent`
- `AccessGrantedMailIntent`

`ComposedAuthMailService` (`outlabs_auth/mail/service.py`) exposes the matching
coroutines — `send_invite`, `send_forgot_password`,
`send_password_reset_confirmation`, `send_access_granted` — each returning a
`MailDeliveryResult`.

Wire it in via constructor arguments:

```python
auth = SimpleRBAC(
    database_url=os.getenv("DATABASE_URL"),
    secret_key=os.getenv("SECRET_KEY"),        # >=32 chars
    notification_service=notification_service,
    transactional_mail_service=mail_service,
    transactional_messaging_service=messaging_service,  # WhatsApp/SMS
    enable_notifications=True,
)
```

### Extension 2: OAuth / Social Login

**Providers**: Google, Facebook, Apple, GitHub are implemented directly under
`outlabs_auth/oauth/providers/`. `provider_factories.py` reaches additional
providers (Microsoft, Discord, ...) through the optional `httpx-oauth` dependency.

#### SocialAccount → `social_accounts`
```python
class SocialAccount(BaseModel, table=True):
    __tablename__ = "social_accounts"

    user_id: UUID            # FK → users.id
    provider: str            # "google", "facebook", "apple", "github"
    provider_user_id: str
    provider_email: Optional[str]
    provider_email_verified: bool
    provider_username: Optional[str]

    # Provider tokens — only stored when store_oauth_provider_tokens=True,
    # encrypted with oauth_token_encryption_key
    access_token: Optional[str]
    refresh_token: Optional[str]
    token_expires_at: Optional[datetime]

    display_name: Optional[str]
    avatar_url: Optional[str]
    profile_url: Optional[str]
    last_login_at: Optional[datetime]
```

#### OAuthState → `oauth_states`
```python
class OAuthState(BaseModel, table=True):
    __tablename__ = "oauth_states"

    state: str
    provider: str
    user_id: Optional[UUID]
    redirect_uri: Optional[str]
    code_verifier: Optional[str]   # PKCE
    nonce: Optional[str]           # OIDC replay protection
    expires_at: datetime
    used_at: Optional[datetime]    # single-use enforcement
```

**Security properties** (see `CHANGELOG.md` 0.1.0a24):
- Authorization responses are **browser-bound and single-use**: signed state claims
  are backed by this server-side record plus a binding cookie, so callbacks reject
  replayed, expired, or cross-browser state.
- Apple ID tokens are verified through JWKS. Invalid provider ID tokens are
  rejected — there is no unverified-parse fallback.
- Account auto-linking requires a **provider-verified** email; otherwise it raises
  `EmailNotVerifiedError` rather than linking.

Users are `hashed_password: Optional[str]` — OAuth-only users have no password, and
`auth_methods` records how the account can authenticate. `CannotUnlinkLastMethodError`
prevents unlinking the last remaining way to log in.

### Extension 3: Passwordless Authentication

#### AuthChallenge → `auth_challenges`
```python
class AuthChallengeType(str, Enum):
    MAGIC_LINK = "magic_link"
    ACCESS_CODE = "access_code"
    WHATSAPP_OTP = "whatsapp_otp"
    SMS_OTP = "sms_otp"


class AuthChallenge(BaseModel, table=True):
    __tablename__ = "auth_challenges"

    user_id: UUID                       # FK → users.id
    challenge_type: AuthChallengeType
    token_hash: str                     # the raw token is never stored
    recipient: str                      # email address or phone number
    expires_at: datetime
    used_at: Optional[datetime]         # single-use enforcement
    redirect_url: Optional[str]
    requested_ip_address: Optional[str]
    requested_user_agent: Optional[str]
```

Enable and tune via constructor flags — note it is `enable_access_codes`, not
`enable_otp`:

```python
auth = SimpleRBAC(
    database_url=os.getenv("DATABASE_URL"),
    secret_key=os.getenv("SECRET_KEY"),

    enable_magic_links=True,
    magic_link_expire_minutes=15,
    magic_link_request_rate_limit_max=3,
    magic_link_request_rate_limit_window_seconds=300,

    enable_access_codes=True,
    access_code_expire_minutes=10,
    access_code_length=6,
    access_code_request_rate_limit_max=3,
    access_code_request_rate_limit_window_seconds=300,
    access_code_verify_rate_limit_max=10,
    access_code_verify_rate_limit_window_seconds=300,
)
```

Rate limiting is enforced on both **request** and **verify** for access codes —
request-only limiting would leave the code itself brute-forceable.

WhatsApp and SMS OTP challenge types deliver through the injected
`transactional_messaging_service`. See `examples/enterprise_rbac/challenge_messaging.py`
for a working wiring, and `docs/WHATSAPP_ACCOUNT_MESSAGING.md`.

### Key Design Principles

1. **Injected, not built in** — notification/mail/messaging services are supplied by
   the host app. The library owns the intent and the call, never the vendor.
2. **Feature-flagged** — every extension is off by default; enabling one is a
   constructor argument, not a different preset.
3. **Tokens are hashed at rest** — `AuthChallenge.token_hash`, `APIKey.key_hash`.
   Raw values are returned once and never stored or logged.
4. **Single-use and expiring** — challenges and OAuth states both carry
   `expires_at` + `used_at`.
5. **Additive schema** — enabling an extension may add tables; run
   `outlabs-auth migrate`. It never requires switching presets.

---

## Dependency Injection

FastAPI dependencies for common patterns:

### Authentication Dependencies
```python
# outlabs_auth/dependencies/auth.py

def get_current_user(auth: OutlabsAuth):
    """Dependency factory for getting current user"""
    async def _get_current_user(
        token: str = Depends(oauth2_scheme)
    ) -> UserModel:
        return await auth.get_current_user(token)
    return _get_current_user

def require_active_user(auth: OutlabsAuth):
    """Require active user status"""
    async def _check_active(
        user: UserModel = Depends(get_current_user(auth))
    ) -> UserModel:
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(403, "User account is not active")
        return user
    return _check_active
```

### Permission Dependencies
```python
# outlabs_auth/dependencies/permissions.py

def require_permission(auth: OutlabsAuth, permission: str):
    """Dependency factory for permission checks"""
    async def _check_permission(
        user: UserModel = Depends(get_current_user(auth))
    ) -> UserModel:
        has_perm = await auth.permission_service.check_permission(
            user.id, permission
        )
        if not has_perm:
            raise HTTPException(403, f"Permission denied: {permission}")
        return user
    return _check_permission

def require_any_permission(auth: OutlabsAuth, permissions: List[str]):
    """Require at least one of the permissions"""
    async def _check_any(
        user: UserModel = Depends(get_current_user(auth))
    ) -> UserModel:
        for perm in permissions:
            has_perm = await auth.permission_service.check_permission(
                user.id, perm
            )
            if has_perm:
                return user
        raise HTTPException(
            403,
            f"Permission denied: requires one of {permissions}"
        )
    return _check_any
```

### Entity Context Dependencies (EnterpriseRBAC only)
```python
# outlabs_auth/dependencies/entities.py

def require_entity_permission(
    auth: EnterpriseRBAC,
    permission: str,
    entity_param: str = "entity_id"
):
    """
    Check permission within entity context from path parameter.

    Example:
    @app.get("/entities/{entity_id}/members")
    async def get_members(
        entity_id: str,
        user = Depends(require_entity_permission(auth, "member:read", "entity_id"))
    ):
        pass
    """
    async def _check_entity_permission(
        user: UserModel = Depends(get_current_user(auth)),
        # Entity ID extracted from path
        **kwargs
    ) -> UserModel:
        entity_id = kwargs.get(entity_param)
        if not entity_id:
            raise HTTPException(400, f"Missing {entity_param}")

        has_perm = await auth.permission_service.check_permission(
            user.id, permission, entity_id
        )
        if not has_perm:
            raise HTTPException(
                403,
                f"Permission denied: {permission} in entity {entity_id}"
            )
        return user

    return _check_entity_permission
```

---

## Host Integration Queries

When OutlabsAuth is embedded into a larger FastAPI product, the host app often
needs some in-process read access to auth-owned data such as:

- entity members with user details
- roles available in one entity context
- memberships for a linked user

The supported path for that is the auth-owned query facade:

- `auth.host_query_service`

This keeps auth table ownership and filtering rules inside the library instead
of forcing each host app to invent direct SQL joins into auth tables.

For details and examples, see:

- [HOST_INTEGRATION_QUERIES.md](./HOST_INTEGRATION_QUERIES.md)

---

## Configuration System

`outlabs_auth/core/config.py`. In practice you pass these as keyword arguments to
`SimpleRBAC` / `EnterpriseRBAC` / `OutlabsAuth`, which build the config object for
you.

### Base Configuration
```python
class AuthConfig(BaseModel):
    """Base configuration shared by SimpleRBAC and EnterpriseRBAC."""

    # Database
    database_url: str          # postgresql+asyncpg://user:pass@host:5432/dbname
    database_schema: Optional[str] = None   # None → follow the connection search path

    # JWT
    secret_key: str            # >=32 chars — HS256 rejects shorter, construction raises
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    jwt_audience: Optional[str] = None

    # Service tokens — separate derived signing key for domain separation
    service_token_secret_key: Optional[str] = None   # min_length=32 when set
    service_token_audience: Optional[str] = None

    # Password policy
    password_min_length: int = 8
    require_special_char: bool = True
    require_uppercase: bool = True
    require_digit: bool = True

    # Argon2id tuning (OWASP 2023 minimums)
    argon2_time_cost: int = 2
    argon2_memory_cost_kib: int = 19456     # 19 MiB
    argon2_parallelism: int = 1

    # Security
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30

    # Feature flags (see the preset subclasses)
    enable_entity_hierarchy: bool = False
    enable_context_aware_roles: bool = False
    enable_abac: bool = False
    enable_caching: Optional[bool] = None   # defaults to True when Redis is configured
    enable_audit_log: bool = False
```

`MIN_HS_SECRET_KEY_LENGTH = 32` is enforced — a short `secret_key` raises during
construction, not at first request. This is the single most common integration
error.

### Preset-Specific Configs

The preset configs pin the feature flags with `frozen=True`, which is what makes
"SimpleRBAC cannot accidentally grow a hierarchy" a type-level guarantee rather
than a convention:

```python
class SimpleConfig(AuthConfig):
    """Configuration for SimpleRBAC. Entity hierarchy and advanced features off."""

    enable_entity_hierarchy: bool = Field(default=False, frozen=True)
    enable_context_aware_roles: bool = Field(default=False, frozen=True)
    enable_abac: bool = Field(default=False, frozen=True)


class EnterpriseConfig(AuthConfig):
    """Configuration for EnterpriseRBAC. Entity hierarchy always on."""

    enable_entity_hierarchy: bool = Field(default=True, frozen=True)

    # Entity settings
    max_entity_depth: int = 10
    allowed_entity_types: Optional[list[str]] = None   # None = any
    allow_access_groups: bool = True

    # enable_context_aware_roles / enable_abac / enable_caching / enable_audit_log
    # are inherited from AuthConfig and remain configurable (default False).
```

Note `max_entity_depth` defaults to **10**.

### Optional dependencies and background work

```python
redis_enabled: Optional[bool] = None
redis_url: Optional[str] = None
redis_key_prefix: Optional[str] = None
cache_ttl_seconds: int = 300

# Embedded schedulers are OFF by default — run one deterministic cycle with
# `outlabs-auth run-maintenance` instead, or opt in explicitly.
background_job_mode: Literal["disabled", "embedded"] = "disabled"

# Injected services — the library defines the interface and calls it
notification_service: Optional[Any] = None
transactional_mail_service: Optional[Any] = None
transactional_messaging_service: Optional[Any] = None

# Untrusted by default
trust_resource_context_header: bool = False
```

---

## Testing Strategy

Layout:

```
tests/
├── conftest.py              # shared fixtures
├── fixtures/
├── unit/
│   ├── authentication/      # transports, strategies, backends
│   ├── database/
│   ├── integrations/
│   ├── oauth/
│   ├── observability/
│   ├── services/
│   └── test_readme_quickstart.py   # extracts and EXECUTES the README block
└── integration/             # router/endpoint-level, real PostgreSQL
    └── query_budget_support.py     # asserts query counts, catching N+1 regressions
```

### Schema-per-test isolation

`test_engine` creates a **uniquely named PostgreSQL schema per test**, sets the
connection's `search_path` to it, runs `SQLModel.metadata.create_all`, and drops
the schema `CASCADE` afterwards:

```python
@pytest_asyncio.fixture(scope="function")
async def test_engine():
    schema_name = f"test_{uuid4().hex}"
    ...
```

This buys real isolation and parallelism without a database per worker. It also
means **tests need a live PostgreSQL** — there is no SQLite fallback, and there
should not be one: the library depends on PostgreSQL-specific behaviour
(`PG_UUID`, schema search paths, `SKIP LOCKED`).

### Key fixtures (`tests/conftest.py`)

| Fixture | Provides |
|---------|----------|
| `test_engine` | async engine bound to a throwaway schema |
| `test_session` | `AsyncSession` for a single test |
| `test_secret_key` | a >=32-char key (short keys raise at construction) |
| `auth_config` | `AuthConfig` built from the test key |
| `auth` | initialized `SimpleRBAC` |
| `auth_with_cache` | `SimpleRBAC` with Redis caching enabled |
| `redis_client` | Redis connection for cache/counter tests |

### The README is a test

`tests/unit/test_readme_quickstart.py` extracts the quickstart code block from
`README.md` and executes it, so the first thing a new integrator reads cannot rot.
It has caught both of the classic mistakes: a `secret_key` under 32 chars, and
mounting routers at import time while `auth.deps` only exists after the async
`initialize()`.

If you change the README quickstart, run that test.

See [TESTING_GUIDE.md](TESTING_GUIDE.md) and `docs-library/95-Testing-Guide.md`.

---

## Performance Considerations

### Caching Strategy

`outlabs_auth/services/cache.py` (`CacheService`). Keys are built through
`redis_client.make_key(...)`, so everything is namespaced by `redis_key_prefix`:

| Key shape | Built by |
|-----------|----------|
| `auth:permission-check:{user_id}:{entity_id\|global}:{permission}[:{context_hash}]` | `make_permission_check_key` |
| `auth:user-permissions:{user_id}:{all\|global}` | `make_user_permissions_key` |
| `auth:entity-relation:{version}:{ancestor_id}:{descendant_id}` | `make_entity_relation_key` |
| `auth:abac-conditions-flag` | `make_abac_conditions_flag_key` |

TTL is `cache_ttl_seconds` (default 300) with **±10% jitter** (`_jittered_ttl`) so
entries written together do not expire — and stampede a rebuild — together.

**Invalidation** is two-tier:

1. **Direct** — `invalidate_user_permissions(user_id)` publishes
   `permissions:user:{user_id}`; entity changes publish
   `permissions:entity:{entity_id}`. Redis Pub/Sub propagates to every instance
   (DD-037).
2. **Version bumps** — API-key auth snapshots carry a version counter
   (`bump_user_api_key_auth_snapshot_version`, `..._entity_...`, `..._global_...`).
   Bumping the version makes every key derived from it unreachable, which
   invalidates a whole class of entries in O(1) without scanning.

Caching is enabled by default when Redis is configured (`enable_caching` defaults
to `None` → True with Redis).

### Database Indexes

Declared in each model's `__table_args__`. The notable ones:

```python
# users
UniqueConstraint("email", name="uq_users_email")
Index("ix_users_status", "status")
Index("ix_users_root_entity_id", "root_entity_id")

# permissions
UniqueConstraint("name", name="uq_permissions_name")
Index("ix_permissions_resource", "resource")
Index("ix_permissions_status", "status")

# entities                                    (EnterpriseRBAC)
UniqueConstraint("slug", name="uq_entities_slug")
Index("ix_entities_class_type", "entity_class", "entity_type")
Index("ix_entities_parent_id", "parent_id")
Index("ix_entities_status", "status")

# entity_memberships                          (EnterpriseRBAC)
UniqueConstraint("user_id", "entity_id", name="uq_entity_membership")
Index("ix_em_entity_id", "entity_id")
Index("ix_em_user_status", "user_id", "status")

# entity_closure                              (EnterpriseRBAC)
UniqueConstraint("ancestor_id", "descendant_id", name="uq_entity_closure")
Index("ix_closure_ancestor_depth", "ancestor_id", "depth")
Index("ix_closure_descendant_depth", "descendant_id", "depth")

# user_role_memberships                       (SimpleRBAC)
UniqueConstraint("user_id", "role_id", name="uq_user_role_membership")
Index("ix_urm_user_status", "user_id", "status")
```

Composite indexes are deliberately ordered so their **leading prefix** serves
single-column lookups — that is why the redundant single-column btrees were
dropped (migration `0018`, index hygiene). Adding them back is a regression, not
an optimization.

### Query Optimization

- **Eager loading via `selectinload`** — `services/permission.py` uses it heavily to
  pull roles and their permissions in one extra query instead of one per row.
  (There is no `fetch_links`; that is not a SQLAlchemy API.)
- **Request-scoped cache** — `services/request_cache.py` +
  `middleware/request_cache.py` memoize repeated lookups within a single request,
  so two permission checks on one route do not hit Redis or PostgreSQL twice.
- **Query budgets in tests** — `tests/integration/query_budget_support.py` asserts
  query counts, so an N+1 regression fails CI rather than quietly costing latency.
- Batch permission checks when possible.
- Limit entity path traversal depth (`max_entity_depth`, default 10).

---

## Further Reading

The source is the truth. In order:

1. **`examples/`** — the only integration reference kept honest by tests
2. **`README.md`** — quickstart, executed by `tests/unit/test_readme_quickstart.py`
3. **the source** — `core/auth.py`, `routers/`, `dependencies/__init__.py`
4. **[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** — why it is built this way
5. **[CURRENT_IMPLEMENTATION_STATUS.md](CURRENT_IMPLEMENTATION_STATUS.md)** and
   **`CHANGELOG.md`** — what is actually built, and what shipped when
