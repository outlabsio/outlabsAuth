# OutlabsAuth Library - Technical Architecture

**Version**: 2.0
**Date**: 2025-01-14
**Status**: PostgreSQL Migration Complete
**Database**: PostgreSQL with SQLAlchemy/SQLModel (async)

---

## Table of Contents

1. [Overview](#overview)
2. [Package Structure](#package-structure)
3. [Preset Architecture](#preset-architecture)
4. [Data Models](#data-models)
5. [Service Layer](#service-layer)
6. [Authentication System (API Keys & Multi-Source Auth)](#authentication-system-api-keys--multi-source-auth)
7. [Authentication Extensions (v1.1-v1.4, Optional)](#authentication-extensions-v11-v14-optional)
8. [Dependency Injection](#dependency-injection)
9. [Configuration System](#configuration-system)
10. [Testing Strategy](#testing-strategy)

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
├── core/
│   ├── __init__.py
│   ├── base.py                 # Base OutlabsAuth class
│   ├── config.py               # Configuration management
│   ├── engine.py               # SQLAlchemy async engine
│   └── exceptions.py           # Custom exceptions
├── models/
│   ├── __init__.py
│   └── sql/                    # PostgreSQL models (SQLModel)
│       ├── base.py             # Base SQL model
│       ├── user.py             # User model
│       ├── role.py             # Role model
│       ├── permission.py       # Permission model
│       ├── entity.py           # Entity model (EnterpriseRBAC)
│       ├── entity_closure.py   # Closure table for tree queries
│       ├── entity_membership.py # User-entity memberships
│       └── api_key.py          # API key model
├── services/
│   ├── __init__.py
│   ├── auth.py                 # AuthService
│   ├── user.py                 # UserService
│   ├── role.py                 # RoleService
│   ├── permission.py           # PermissionService
│   ├── entity.py               # EntityService (enterprise only)
│   └── membership.py           # MembershipService (enterprise only)
├── presets/
│   ├── __init__.py
│   ├── simple.py               # SimpleRBAC preset
│   └── enterprise.py           # EnterpriseRBAC preset
├── dependencies/
│   ├── __init__.py
│   ├── auth.py                 # FastAPI auth dependencies
│   ├── permissions.py          # Permission checking dependencies
│   └── entities.py             # Entity context dependencies (enterprise only)
├── middleware/
│   ├── __init__.py
│   ├── auth.py                 # JWT middleware
│   └── entity_context.py       # Entity context middleware (optional)
├── utils/
│   ├── __init__.py
│   ├── password.py             # Password hashing
│   ├── jwt.py                  # JWT utilities
│   └── validation.py           # Input validation
└── schemas/
    ├── __init__.py
    ├── auth.py                 # Auth request/response schemas
    ├── user.py                 # User schemas
    ├── role.py                 # Role schemas
    ├── permission.py           # Permission schemas
    └── entity.py               # Entity schemas (enterprise only)

examples/                       # Example applications
├── simple_app/
├── enterprise_app/             # EnterpriseRBAC with various configurations
└── migration_example/

tests/                          # Comprehensive test suite
├── unit/
├── integration/
└── examples/
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
        enable_caching: bool = False,
        enable_audit_log: bool = False,  # Reserved for future extended/compliance capture
        # Optional dependencies
        redis_url: Optional[str] = None,
        redis_enabled: bool = False,
        notification_service: Optional[NotificationService] = None,
        **kwargs
    ):
        self.database_url = database_url
        self.secret_key = secret_key

        # Configuration
        self.config = AuthConfig(
            enable_entity_hierarchy=enable_entity_hierarchy,
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            enable_caching=enable_caching,
            enable_audit_log=enable_audit_log,
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
        if self.config.enable_caching and self.config.redis_url:
            self.cache_service = CacheService(self.config.redis_url)
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
- Multi-source auth via AuthContext

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

**Optional Features** (Opt-in via flags):
- Context-aware roles (permissions vary by entity type) - `enable_context_aware_roles=True`
- ABAC conditions (attribute-based access control) - `enable_abac=True`
- Permission caching (Redis) - `enable_caching=True` (requires `redis_url`)
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

# Entity-scoped permission check
@app.put("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    ctx: AuthContext = Depends(deps.require_entity_permission(entity_id, "entity:update"))
):
    return await auth.entity_service.update(entity_id, data)
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
    redis_enabled=True,
    enable_context_aware_roles=True,  # Opt-in
    enable_abac=True,                 # Opt-in
    enable_caching=True               # Opt-in
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
- `auth.cache_service` - ✅ Available if `enable_caching=True` and `redis_url` provided

---

## Data Models

### Core Models (All Presets)

#### UserModel
```python
class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"
    TERMINATED = "terminated"

class UserModel(BaseDocument):
    # Authentication
    email: EmailStr
    hashed_password: str

    # Profile
    profile: UserProfile

    # Status
    status: UserStatus = UserStatus.ACTIVE
    is_system_user: bool = False
    email_verified: bool = False

    # Security
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
```

#### RoleModel
```python
class RoleModel(BaseDocument):
    # Identity
    name: str
    display_name: str
    description: Optional[str] = None

    # Permissions (default for all contexts)
    permissions: List[str] = Field(default_factory=list)

    # Context-aware permissions (EnterpriseRBAC only - optional feature)
    entity_type_permissions: Optional[Dict[str, List[str]]] = None

    # Configuration
    is_system_role: bool = False
```

#### PermissionModel
```python
class PermissionModel(BaseDocument):
    # Identity
    name: str  # e.g., "user:create"
    display_name: str
    description: str

    # Structure (auto-parsed from name)
    resource: str  # "user"
    action: str    # "create"

    # ABAC conditions (EnterpriseRBAC only - optional feature)
    conditions: List[Condition] = Field(default_factory=list)

    # Status
    is_active: bool = True
```

#### UserRoleMembership (SimpleRBAC only)
```python
class UserRoleMembership(BaseDocument):
    """
    User-role membership for SimpleRBAC (flat, no entity context).

    Provides audit trail and consistency with EnterpriseRBAC's membership pattern.
    See DD-047 for rationale.
    """

    # Relationships
    user: Link[UserModel]
    role: Link[RoleModel]

    # Audit trail
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_by: Optional[Link[UserModel]] = None

    # Time-based assignment (optional)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status
    is_active: bool = True

    # Indexes
    class Settings:
        name = "user_role_memberships"
        indexes = [
            [("user", 1), ("role", 1)],  # Unique constraint
            "user",                       # Get user's roles
            "role",                       # Get users with role
            "is_active",                  # Filter active memberships
            [("root_entity_id", 1)]       # Entity isolation support
        ]
```

**Why Membership Table for SimpleRBAC?**
- **Audit Trail**: Track who assigned roles and when
- **Time-Based Roles**: Optional validity periods
- **Consistent Pattern**: Same approach as EnterpriseRBAC, just without entities
- **Easy Migration**: Trivial upgrade path to EnterpriseRBAC
- **Industry Standard**: Django, Keycloak, etc. all use membership tables

**vs Direct Links** (`user.roles = [...]`):
- ✅ Membership table: Audit trail, time-based, consistent
- ❌ Direct links: No audit, no time-based, inconsistent with Enterprise

### Enterprise Models (EnterpriseRBAC only)

#### EntityModel
```python
class EntityClass(str, Enum):
    STRUCTURAL = "structural"      # Organizational hierarchy
    ACCESS_GROUP = "access_group"  # Cross-cutting groups

class EntityModel(BaseDocument):
    # Identity
    name: str
    display_name: str
    slug: str
    description: Optional[str] = None

    # Classification
    entity_class: EntityClass
    entity_type: str  # Flexible: "department", "team", etc.

    # Hierarchy
    parent_entity: Optional[Link["EntityModel"]] = None

    # Optional: root-entity scoping
    root_entity_id: Optional[str] = None

    # Status
    status: str = "active"
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Configuration
    allowed_child_classes: List[EntityClass] = []
    allowed_child_types: List[str] = []
    max_members: Optional[int] = None
```

`Entity.metadata` is future design intent only. It is intentionally absent from the current persisted SQL model and live API contract.

#### EntityMembershipModel
```python
class EntityMembershipModel(BaseDocument):
    """User's membership in an entity with roles"""

    user: Link[UserModel]
    entity: Link[EntityModel]

    # Multiple roles per membership
    roles: List[Link[RoleModel]] = Field(default_factory=list)

    # Time-based membership
    joined_at: datetime
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status
    is_active: bool = True
```

#### EntityClosureModel (NEW)
```python
class EntityClosureModel(BaseDocument):
    """
    Stores all ancestor-descendant relationships for O(1) queries.

    Uses the closure table pattern for efficient tree permission checks.
    """

    ancestor_id: str      # Ancestor entity ID
    descendant_id: str    # Descendant entity ID
    depth: int           # Distance (0 = self, 1 = direct child, etc.)

    class Settings:
        name = "entity_closure"
        indexes = [
            [("ancestor_id", 1), ("descendant_id", 1)],  # Unique constraint
            [("descendant_id", 1), ("depth", 1)],        # Find ancestors
            [("ancestor_id", 1), ("depth", 1)]           # Find descendants
        ]
```

**Closure Table Benefits**:
- **O(1) Ancestor Queries**: Single database query to get all ancestors
- **O(1) Descendant Queries**: Single query to get all descendants
- **Tree Permission Performance**: 20x faster than recursive queries
- **Unlimited Depth**: No performance degradation with deep hierarchies
- **Simple Maintenance**: Auto-maintained on entity create/move/delete

**Example Queries**:
```python
# Get all ancestors (single query)
ancestors = await EntityClosure.find(
    {"descendant_id": entity_id, "depth": {"$gt": 0}}
).sort("depth").to_list()

# Get all descendants (single query)
descendants = await EntityClosure.find(
    {"ancestor_id": entity_id, "depth": {"$gt": 0}}
).to_list()

# Check if A is ancestor of B (single query)
is_ancestor = await EntityClosure.find_one({
    "ancestor_id": A,
    "descendant_id": B
}) is not None
```

### Model Changes from Current System

#### Removed Fields
- ❌ `platform_id` (no longer needed)
- ❌ Platform-specific isolation logic

#### Added Fields
- ✅ `root_entity_id` (optional, for entity-scoped isolation)

#### Preserved Fields
- ✅ All entity hierarchy logic
- ✅ Tree permission support
- ✅ Context-aware role support
- ✅ Time-based validity

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

        Note: Caching automatically applied when enable_caching=True
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

**Status**: Core v1.0 Feature
**Timeline**: Phase 2 (SimpleRBAC - Week 2)
**Compatibility**: Both SimpleRBAC and EnterpriseRBAC

### Overview

The authentication system provides multi-source authentication supporting users (JWT), API keys (service-to-service), service accounts (internal), superusers (admin overrides), and anonymous access. All authentication sources are unified through a consistent `AuthContext` abstraction.

**Auth Sources** (priority order):
1. **Superuser** - Admin override tokens
2. **Service accounts** - Internal service authentication
3. **API keys** - External integrations and webhooks
4. **Users** - JWT-based user authentication
5. **Anonymous** - Optional public access

### AuthContext Model

Universal authentication context that works across all auth sources:

```python
# outlabs_auth/auth_context.py
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class AuthSource(str, Enum):
    """Where the authentication came from"""
    USER = "user"
    API_KEY = "api_key"
    SERVICE = "service"
    SUPERUSER = "superuser"
    IMPERSONATION = "impersonation"
    ANONYMOUS = "anonymous"

class AuthContext(BaseModel):
    """Universal authentication context for all auth sources"""

    # Core identity
    source: AuthSource
    identity: str  # user_id, api_key_id, service_name, etc.

    # Permissions & access
    permissions: List[str] = []
    roles: List[str] = []
    groups: List[str] = []
    entities: Dict[str, List[str]] = {}

    # Special flags
    is_superuser: bool = False
    is_service_account: bool = False
    is_impersonating: bool = False

    # Metadata
    metadata: Dict[str, Any] = {}

    # Rate limiting
    rate_limit: Optional[int] = None
    rate_limit_remaining: Optional[int] = None

    # Helper methods
    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        return permission in self.permissions

    def has_all_permissions(self, *permissions: str) -> bool:
        if self.is_superuser:
            return True
        return all(p in self.permissions for p in permissions)
```

### API Key Models

```python
# outlabs_auth/models/api_key.py
from enum import Enum
from typing import List, Optional
from datetime import datetime

class APIKeyScope(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

class APIKeyModel(BaseDocument):
    """API keys for service-to-service authentication"""

    # Identification
    name: str
    description: Optional[str] = None
    key_hash: str  # argon2id hash (NOT SHA256)
    key_prefix: str  # First 8 chars (sk_prod_)

    # Access control
    permissions: List[str] = []
    scopes: List[APIKeyScope] = []
    is_superuser: bool = False

    # Restrictions
    allowed_ips: List[str] = []  # Empty = all IPs
    allowed_origins: List[str] = []
    allowed_endpoints: List[str] = []

    # Rate limiting
    rate_limit_per_minute: Optional[int] = 60
    rate_limit_per_hour: Optional[int] = 1000

    # Metadata
    service_name: Optional[str] = None
    environment: str = "production"  # production, staging, development
    created_by: str  # User ID who created it

    # Lifecycle
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revoked_reason: Optional[str] = None

    # Status
    is_active: bool = True

    # Stats
    usage_count: int = 0
    error_count: int = 0
```

### API Key Service

```python
# outlabs_auth/services/api_key_service.py
from passlib.hash import argon2
import secrets

class APIKeyService:
    """Manage API key lifecycle"""

    KEY_PREFIX_MAP = {
        "production": "sk_prod",
        "staging": "sk_stag",
        "development": "sk_dev",
        "test": "sk_test"
    }

    @staticmethod
    def generate_key(environment: str = "production") -> str:
        """Generate new API key with 8-char prefix + 32 bytes random"""
        prefix = APIKeyService.KEY_PREFIX_MAP.get(environment, "sk_prod")
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_{random_part}"

    @staticmethod
    def hash_key(key: str) -> str:
        """
        Hash key using argon2id (NOT SHA256).

        Security: argon2id with recommended parameters:
        - time_cost=2
        - memory_cost=102400 (100 MB)
        - parallelism=8
        """
        return argon2.using(
            time_cost=2,
            memory_cost=102400,
            parallelism=8
        ).hash(key)

    async def create_api_key(
        self,
        name: str,
        created_by: str,
        permissions: List[str] = None,
        **kwargs
    ) -> Tuple[str, APIKeyModel]:
        """
        Create new API key.

        Returns: (raw_key, key_model)

        ⚠️  The raw key is ONLY returned once - it cannot be recovered!
        """
        raw_key = self.generate_key(kwargs.get("environment", "production"))

        api_key = APIKeyModel(
            name=name,
            key_hash=self.hash_key(raw_key),
            key_prefix=raw_key[:8],
            permissions=permissions or [],
            created_by=created_by,
            **kwargs
        )

        await api_key.save()

        # Current runtime does not expose a generic audit_service here.
        # API key lifecycle is retained through status changes plus
        # service-level notification/observability hooks.

        return raw_key, api_key

    async def validate(
        self,
        key: str,
        required_permissions: List[str] = None
    ) -> Optional[APIKeyModel]:
        """Validate API key and check permissions"""
        if not key or len(key) < 8:
            return None

        prefix = key[:8]
        api_key = await APIKeyModel.find_one(
            APIKeyModel.key_prefix == prefix,
            APIKeyModel.is_active == True
        )

        if not api_key:
            return None

        # Verify hash (constant-time comparison via argon2)
        if not argon2.verify(key, api_key.key_hash):
            api_key.error_count += 1
            await api_key.save()

            # Auto-revoke after 10 failures
            if api_key.error_count >= 10:
                await self.revoke(
                    str(api_key.id),
                    "system",
                    "Too many failed validation attempts"
                )
            return None

        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None

        # Check permissions
        if required_permissions and not api_key.is_superuser:
            missing = set(required_permissions) - set(api_key.permissions)
            if missing:
                return None

        # Update usage stats
        api_key.last_used_at = datetime.utcnow()
        api_key.usage_count += 1
        await api_key.save()

        return api_key

    async def rotate(
        self,
        old_key_id: str,
        rotated_by: str
    ) -> Tuple[str, APIKeyModel]:
        """Rotate API key (revoke old, create new with same permissions)"""
        old_key = await APIKeyModel.get(old_key_id)
        if not old_key:
            raise ValueError("API key not found")

        # Create new with same permissions
        new_raw_key, new_key = await self.create_api_key(
            name=f"{old_key.name} (rotated)",
            created_by=rotated_by,
            permissions=old_key.permissions,
            service_name=old_key.service_name,
            environment=old_key.environment,
            allowed_ips=old_key.allowed_ips
        )

        # Revoke old
        await self.revoke(old_key_id, rotated_by, "Key rotation")

        return new_raw_key, new_key

    async def revoke(
        self,
        key_id: str,
        revoked_by: str,
        reason: str = "Manual revocation"
    ) -> bool:
        """Revoke API key"""
        api_key = await APIKeyModel.get(key_id)
        if not api_key:
            return False

        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()
        api_key.revoked_by = revoked_by
        api_key.revoked_reason = reason
        await api_key.save()

        # Current runtime does not expose a generic audit_service here.
        # API key revocation is represented by status lifecycle on the key.

        return True
```

### Service Account Model & Service

```python
# outlabs_auth/models/service_account.py
class ServiceAccountModel(BaseDocument):
    """Internal service account for microservices"""

    name: str  # "email_service", "notification_service", etc.
    description: Optional[str] = None
    token_hash: str  # argon2id hash

    permissions: List[str] = []
    is_active: bool = True

    created_at: datetime
    last_used_at: Optional[datetime] = None

# outlabs_auth/services/service_account_service.py
class ServiceAccountService:
    """Manage service accounts for internal services"""

    async def create(
        self,
        name: str,
        permissions: List[str]
    ) -> Tuple[str, ServiceAccountModel]:
        """Create service account and return token"""
        token = secrets.token_urlsafe(32)

        service = ServiceAccountModel(
            name=name,
            token_hash=argon2.hash(token),
            permissions=permissions,
            created_at=datetime.utcnow()
        )

        await service.save()
        return token, service

    async def validate_token(self, token: str) -> Optional[ServiceAccountModel]:
        """Validate service account token"""
        # Similar validation logic as API keys
        pass
```

### Multi-Source Authentication

```python
# outlabs_auth/services/multi_source_auth.py
class MultiSourceAuthService:
    """Resolve authentication from multiple sources"""

    def __init__(self, auth: OutlabsAuth):
        self.auth = auth

    async def get_context(
        self,
        request: Request,
        authorization: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None),
        x_service_token: Optional[str] = Header(None),
        x_superuser_token: Optional[str] = Header(None),
        api_key: Optional[str] = Query(None),
    ) -> AuthContext:
        """
        Extract auth context from any source.

        Priority: Superuser > Service > API Key > User > Anonymous
        """

        # 1. Superuser token (admin override)
        if x_superuser_token:
            if await self._validate_superuser_token(x_superuser_token):
                return AuthContext(
                    source=AuthSource.SUPERUSER,
                    identity="superuser",
                    is_superuser=True,
                    metadata={"ip": request.client.host}
                )

        # 2. Service account (internal services)
        if x_service_token:
            service = await self.auth.service_account_service.validate_token(
                x_service_token
            )
            if service:
                return AuthContext(
                    source=AuthSource.SERVICE,
                    identity=service.name,
                    permissions=service.permissions,
                    is_service_account=True,
                    metadata={"service": service.name}
                )

        # 3. API key (external integrations)
        api_key_value = x_api_key or api_key
        if api_key_value:
            key = await self.auth.api_key_service.validate(api_key_value)
            if key:
                # Check IP restrictions
                if key.allowed_ips and request.client.host not in key.allowed_ips:
                    raise HTTPException(403, "IP not allowed for this API key")

                return AuthContext(
                    source=AuthSource.API_KEY,
                    identity=str(key.id),
                    permissions=key.permissions,
                    rate_limit=key.rate_limit_per_minute,
                    metadata={
                        "key_name": key.name,
                        "service": key.service_name
                    }
                )

        # 4. User JWT token
        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
            try:
                user = await self.auth.get_current_user(token)
                perms = await self.auth.permission_service.get_user_permissions(
                    user.id
                )

                return AuthContext(
                    source=AuthSource.USER,
                    identity=str(user.id),
                    permissions=perms,
                    is_superuser=user.is_superuser,
                    metadata={"user": user}
                )
            except:
                pass

        # 5. Anonymous
        return AuthContext(
            source=AuthSource.ANONYMOUS,
            identity="anonymous"
        )
```

### Dependency Patterns

See [DEPENDENCY_PATTERNS.md](DEPENDENCY_PATTERNS.md) for comprehensive dependency injection patterns.

```python
# outlabs_auth/dependencies/simple.py
class SimpleDeps:
    """Simple authentication dependencies"""

    def __init__(self, auth: OutlabsAuth):
        self.auth = auth

    def authenticated(self):
        """Require any authentication"""
        async def get_user(authorization: Optional[str] = Header(None)):
            if not authorization:
                raise HTTPException(401, "Not authenticated")
            token = authorization.replace("Bearer ", "")
            return await self.auth.get_current_user(token)
        return Depends(get_user)

    def requires(self, *permissions: str):
        """Require all listed permissions"""
        async def check(user = Depends(self.authenticated())):
            for perm in permissions:
                if not await self.auth.permission_service.check_permission(
                    user.id, perm
                ):
                    raise HTTPException(403, f"Missing permission: {perm}")
            return user
        return Depends(check)

    @property
    def user(self):
        """Shortcut for authenticated user"""
        return self.authenticated()

    @property
    def admin(self):
        """Shortcut for admin role"""
        return self.role("admin", "superuser")

# outlabs_auth/dependencies/multi_source.py
class MultiSourceDeps:
    """Handle authentication from all sources"""

    def __init__(self, auth: OutlabsAuth):
        self.auth = auth
        self.multi_source = MultiSourceAuthService(auth)

    async def get_context(self, request: Request, ...) -> AuthContext:
        """Extract AuthContext from any source"""
        return await self.multi_source.get_context(request, ...)

    def permission(self, *perms: str):
        """Require permissions (works with all auth sources)"""
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source == AuthSource.ANONYMOUS:
                raise HTTPException(401, "Authentication required")
            if not ctx.has_all_permissions(*perms):
                raise HTTPException(403, f"Missing permissions: {perms}")
            return ctx
        return Depends(check)

    def source(self, *allowed_sources: AuthSource):
        """Restrict to specific auth sources"""
        async def check(ctx: AuthContext = Depends(self.get_context)):
            if ctx.source not in allowed_sources:
                raise HTTPException(
                    403,
                    f"Auth source {ctx.source} not allowed"
                )
            return ctx
        return Depends(check)
```

### Rate Limiting

```python
# outlabs_auth/services/rate_limiter.py
class RateLimiter:
    """In-memory rate limiter with optional Redis backend"""

    def __init__(self, redis: Optional[Redis] = None):
        self.redis = redis
        self.memory_store: Dict[str, List[datetime]] = {}

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int = 60
    ) -> Tuple[bool, int]:
        """
        Check rate limit.
        Returns (allowed, remaining)
        """
        if self.redis:
            # Use Redis for distributed rate limiting
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, window)
            allowed = current <= limit
            remaining = max(0, limit - current)
        else:
            # Fallback to in-memory
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=window)

            # Clean old entries
            if key in self.memory_store:
                self.memory_store[key] = [
                    ts for ts in self.memory_store[key]
                    if ts > window_start
                ]
            else:
                self.memory_store[key] = []

            current_count = len(self.memory_store[key])
            allowed = current_count < limit

            if allowed:
                self.memory_store[key].append(now)

            remaining = limit - current_count - (1 if allowed else 0)

        return allowed, remaining

class RateLimitDeps:
    """Rate limiting based on auth source"""

    def __init__(self, auth: OutlabsAuth, redis: Optional[Redis] = None):
        self.auth = auth
        self.limiter = RateLimiter(redis)

    def rate_limit(self, default_limit: int = 60, window: int = 60):
        """Apply rate limits based on auth source"""
        async def check(ctx: AuthContext = Depends(multi.get_context)):
            # Different limits by source
            limits = {
                AuthSource.ANONYMOUS: 10,
                AuthSource.USER: default_limit,
                AuthSource.API_KEY: ctx.rate_limit or default_limit,
                AuthSource.SERVICE: 1000,
                AuthSource.SUPERUSER: float('inf')
            }

            limit = limits.get(ctx.source, default_limit)

            if limit != float('inf'):
                key = f"rate_limit:{ctx.source}:{ctx.identity}"
                allowed, remaining = await self.limiter.check_rate_limit(
                    key, limit, window
                )

                if not allowed:
                    raise HTTPException(429, "Rate limit exceeded")

                ctx.rate_limit_remaining = remaining

            return ctx
        return Depends(check)
```

### Usage Examples

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import SimpleDeps, MultiSourceDeps, RateLimitDeps

app = FastAPI()
auth = SimpleRBAC(database=db)

# Simple usage - users only
require = SimpleDeps(auth)

@app.delete("/users/{id}")
async def delete_user(id: str, user = require.requires("user:delete")):
    return await service.delete(id)

# Multi-source - users, API keys, services
multi = MultiSourceDeps(auth)

@app.get("/api/data")
async def get_data(ctx: AuthContext = multi.permission("data:read")):
    if ctx.source == AuthSource.API_KEY:
        await log_api_usage(ctx)
    return data

# Rate limiting
rate_limit = RateLimitDeps(auth, redis=redis_client)

@app.post("/expensive")
async def expensive_op(ctx: AuthContext = rate_limit.rate_limit(10, 60)):
    return {"remaining": ctx.rate_limit_remaining}

# Create API key
raw_key, key = await auth.api_key_service.create_api_key(
    name="production_api",
    created_by=user_id,
    permissions=["api:read", "api:write"],
    environment="production",
    rate_limit_per_minute=100
)

# Use API key (external service)
headers = {"X-API-Key": raw_key}
response = requests.get("/api/data", headers=headers)
```

### Security Best Practices

See [SECURITY.md](SECURITY.md) for comprehensive security guidelines.

**Key Security Requirements**:
1. **argon2id hashing** (NOT SHA256) for all keys
2. **Never log raw keys** - only prefixes
3. **Optional expiration** with manual rotation API (recommended 90 days)
4. **IP whitelisting** strictly enforced
5. **Temporary locks** after 10 failed attempts in 10 minutes (30-min cooldown)
6. **Rate limiting** per key and per source via Redis counters
7. **Operational visibility** for key lifecycle operations

**API Key Security Checklist**:
- [ ] Keys use argon2id hashing
- [ ] Raw keys never logged or stored
- [ ] Optional expiration configured (recommended ≤90 days)
- [ ] IP whitelisting enabled for production
- [ ] Rate limiting configured per key (Redis counters)
- [ ] Key create/revoke procedures are observable and operationally reviewable
- [ ] Temporary locks on repeated failures (not permanent revocation)
- [ ] Keys scoped to minimum permissions

### Package Structure Updates

```python
outlabs_auth/
├── models/
│   ├── api_key.py              # NEW: APIKeyModel
│   ├── service_account.py      # NEW: ServiceAccountModel
│   └── auth_context.py         # NEW: AuthContext, AuthSource
├── services/
│   ├── api_key_service.py      # NEW: API key lifecycle
│   ├── service_account_service.py  # NEW: Service accounts
│   ├── multi_source_auth.py    # NEW: Multi-source resolution
│   └── rate_limiter.py         # NEW: Rate limiting
├── dependencies/
│   ├── simple.py               # NEW: SimpleDeps
│   ├── multi_source.py         # NEW: MultiSourceDeps
│   ├── groups.py               # NEW: GroupDeps (Enterprise)
│   ├── entities.py             # NEW: EntityDeps (Enterprise)
│   └── rate_limit.py           # NEW: RateLimitDeps
└── routes/
    └── api_keys.py             # NEW: API key management
```

---

## Authentication Extensions (v1.1-v1.4, Optional)

**Status**: Post-v1.0 features
**Timeline**: Weeks 8-16 (9 weeks total)
**Compatibility**: Work with both SimpleRBAC and EnterpriseRBAC

### Overview

Authentication extensions add modern auth capabilities beyond password-based authentication. All extensions are **optional** and can be adopted independently based on application needs.

**Extension Phases**:
- **v1.1 (Week 8-9)**: Notification system (prerequisite)
- **v1.2 (Week 10-12)**: OAuth/social login
- **v1.3 (Week 13-14)**: Passwordless authentication
- **v1.4 (Week 15-16)**: Advanced features (MFA, WebAuthn)

### Extension 1: Notification Handler Abstraction (v1.1)

**Purpose**: Pluggable system for sending auth-related notifications without vendor lock-in.

#### NotificationHandler Interface
```python
class NotificationEvent(BaseModel):
    """Event emitted when notification needs to be sent"""
    type: str  # "welcome", "magic_link", "otp", "password_reset", etc.
    recipient: str  # Email or phone number
    data: Dict[str, Any]  # Event-specific payload
    metadata: Optional[Dict[str, Any]] = None

class NotificationHandler(ABC):
    """Abstract base class for notification handlers"""

    @abstractmethod
    async def send(self, event: NotificationEvent) -> bool:
        """
        Send notification event.
        Returns True if sent successfully, False otherwise.
        """
        pass
```

#### Pre-built Handlers
```python
# Default handler (logs but doesn't send)
class NoOpHandler(NotificationHandler):
    async def send(self, event: NotificationEvent) -> bool:
        logger.info(f"Notification event: {event.type} to {event.recipient}")
        return True

# Webhook handler (send to HTTP endpoint)
class WebhookHandler(NotificationHandler):
    def __init__(self, webhook_url: str, headers: Optional[Dict] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {}

    async def send(self, event: NotificationEvent) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json=event.dict(),
                headers=self.headers
            )
            return response.status_code == 200

# Queue handler (push to message queue)
class QueueHandler(NotificationHandler):
    def __init__(self, queue_client: Any, queue_name: str):
        self.queue_client = queue_client
        self.queue_name = queue_name

    async def send(self, event: NotificationEvent) -> bool:
        await self.queue_client.send_message(
            self.queue_name,
            event.json()
        )
        return True

# Callback handler (direct function call)
class CallbackHandler(NotificationHandler):
    def __init__(self, callback: Callable[[NotificationEvent], Awaitable[bool]]):
        self.callback = callback

    async def send(self, event: NotificationEvent) -> bool:
        return await self.callback(event)

# Composite handler (combine multiple handlers)
class CompositeHandler(NotificationHandler):
    def __init__(self, handlers: List[NotificationHandler], parallel: bool = True):
        self.handlers = handlers
        self.parallel = parallel

    async def send(self, event: NotificationEvent) -> bool:
        if self.parallel:
            results = await asyncio.gather(
                *[h.send(event) for h in self.handlers],
                return_exceptions=True
            )
            return all(r is True for r in results if not isinstance(r, Exception))
        else:
            for handler in self.handlers:
                if not await handler.send(event):
                    return False
            return True
```

#### Usage Example
```python
# Configure notification handler
notification_handler = WebhookHandler(
    webhook_url="https://api.internal/notifications",
    headers={"X-API-Key": os.getenv("NOTIFICATION_API_KEY")}
)

auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler
)

# Notification is sent automatically
await auth.user_service.send_welcome_email(user)
```

### Extension 2: OAuth/Social Login (v1.2)

**Purpose**: Enable "Login with Google/Facebook/Apple" functionality.
**Requires**: Notification system (v1.1) for welcome emails

#### OAuth Provider Interface
```python
class OAuthToken(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None

class OAuthUserInfo(BaseModel):
    provider_user_id: str
    email: Optional[EmailStr] = None
    email_verified: bool = False
    name: Optional[str] = None
    picture: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None

class OAuthProvider(ABC):
    """Abstract base class for OAuth providers"""

    @abstractmethod
    def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None
    ) -> str:
        """Generate OAuth authorization URL"""
        pass

    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str
    ) -> OAuthToken:
        """Exchange authorization code for tokens"""
        pass

    @abstractmethod
    async def get_user_info(self, token: OAuthToken) -> OAuthUserInfo:
        """Get user information from provider"""
        pass
```

#### New Models
```python
class AuthMethod(str, Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    MAGIC_LINK = "magic_link"
    SMS_OTP = "sms_otp"
    EMAIL_OTP = "email_otp"
    TOTP = "totp"

class SocialAccountModel(BaseDocument):
    """Social account linked to user"""
    user: Link[UserModel]
    provider: str  # "google", "facebook", "apple", etc.
    provider_user_id: str
    email: Optional[EmailStr] = None
    email_verified: bool = False
    profile_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

class UserModel(BaseDocument):
    # ... existing fields ...
    hashed_password: Optional[str] = None  # Optional now
    auth_methods: List[AuthMethod] = Field(default_factory=lambda: [AuthMethod.PASSWORD])
    phone_number: Optional[str] = None  # For SMS OTP
```

#### OAuth Service
```python
class OAuthService:
    """OAuth authentication service"""

    async def get_authorization_url(
        self,
        provider: str,
        redirect_uri: str
    ) -> str:
        """Generate OAuth authorization URL with state validation"""
        pass

    async def authenticate_with_provider(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
        auto_link_by_email: bool = True
    ) -> Tuple[UserModel, TokenPair, bool]:
        """
        Authenticate user with OAuth provider.
        Returns (user, tokens, is_new_user)

        Rules:
        - If social email is verified: auto-link to existing user
        - If social email is unverified: create separate account
        - If no existing user: create new user
        """
        pass

    async def link_provider_to_user(
        self,
        user_id: str,
        provider: str,
        code: str,
        redirect_uri: str
    ) -> SocialAccountModel:
        """Link social account to existing user"""
        pass

    async def unlink_provider(
        self,
        user_id: str,
        provider: str
    ) -> None:
        """Unlink social account (must have alternative auth method)"""
        pass
```

#### Usage Example
```python
oauth_providers = {
    "google": GoogleProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    ),
    "facebook": FacebookProvider(
        client_id=os.getenv("FACEBOOK_CLIENT_ID"),
        client_secret=os.getenv("FACEBOOK_CLIENT_SECRET")
    )
}

auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler,
    oauth_providers=oauth_providers
)

# Get authorization URL
auth_url = await auth.oauth_service.get_authorization_url(
    provider="google",
    redirect_uri="https://myapp.com/auth/callback"
)

# Handle callback
user, tokens, is_new = await auth.oauth_service.authenticate_with_provider(
    provider="google",
    code=request.query_params["code"],
    redirect_uri="https://myapp.com/auth/callback"
)
```

### Extension 3: Passwordless Authentication (v1.3)

**Purpose**: Magic links and OTP-based authentication.
**Requires**: Notification system (v1.1) for sending links/codes

#### Challenge Management
```python
class ChallengeType(str, Enum):
    MAGIC_LINK = "magic_link"
    EMAIL_OTP = "email_otp"
    SMS_OTP = "sms_otp"
    WHATSAPP_OTP = "whatsapp_otp"
    TELEGRAM_OTP = "telegram_otp"

class AuthenticationChallengeModel(BaseDocument):
    """Temporary authentication challenge"""
    challenge_type: ChallengeType
    recipient: str  # Email or phone
    code: str  # Magic link token or OTP
    user_id: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    expires_at: datetime
    created_at: datetime
```

#### Passwordless Service
```python
class PasswordlessService:
    """Passwordless authentication service"""

    # Magic Links
    async def send_magic_link(
        self,
        email: EmailStr,
        create_user_if_not_exists: bool = False
    ) -> None:
        """
        Generate magic link and send via notification handler.
        Magic link expires in 15 minutes.
        """
        pass

    async def verify_magic_link(
        self,
        code: str
    ) -> TokenPair:
        """Verify magic link and return JWT tokens"""
        pass

    # OTP
    async def send_otp(
        self,
        recipient: str,
        channel: str = "email",  # "email", "sms", "whatsapp", "telegram"
        create_user_if_not_exists: bool = False
    ) -> None:
        """
        Generate 6-digit OTP and send via notification handler.
        OTP expires in 5 minutes.
        """
        pass

    async def verify_otp(
        self,
        recipient: str,
        code: str
    ) -> TokenPair:
        """Verify OTP code and return JWT tokens"""
        pass
```

#### Usage Example
```python
auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler
)

# Magic link
await auth.passwordless_service.send_magic_link("user@example.com")
tokens = await auth.passwordless_service.verify_magic_link(code)

# SMS OTP
await auth.passwordless_service.send_otp("+1234567890", channel="sms")
tokens = await auth.passwordless_service.verify_otp("+1234567890", "123456")
```

### Extension 4: Advanced Features (v1.4)

**Purpose**: MFA, TOTP, extended OTP channels, and WebAuthn research.

#### TOTP/MFA
```python
class MFAMethodModel(BaseDocument):
    """Multi-factor authentication method"""
    user: Link[UserModel]
    method_type: str  # "totp", "sms", "email"
    totp_secret: Optional[str] = None  # For authenticator apps
    is_primary: bool = False
    created_at: datetime
    last_used_at: Optional[datetime] = None

class MFAService:
    """Multi-factor authentication service"""

    async def enable_totp(self, user_id: str) -> Tuple[str, str]:
        """
        Enable TOTP for user.
        Returns (secret, qr_code_uri)
        """
        pass

    async def verify_totp(self, user_id: str, code: str) -> bool:
        """Verify TOTP code from authenticator app"""
        pass

    async def generate_backup_codes(self, user_id: str) -> List[str]:
        """Generate recovery codes for lost authenticator"""
        pass

    async def require_mfa(self, user_id: str) -> None:
        """Enforce MFA for user"""
        pass
```

### Package Structure Changes (Extensions)

```python
outlabs_auth/
├── extensions/                  # NEW: Extension modules
│   ├── __init__.py
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── base.py             # NotificationHandler ABC
│   │   ├── webhook.py          # WebhookHandler
│   │   ├── queue.py            # QueueHandler
│   │   └── callback.py         # CallbackHandler
│   ├── oauth/
│   │   ├── __init__.py
│   │   ├── base.py             # OAuthProvider ABC
│   │   ├── google.py           # GoogleProvider
│   │   ├── facebook.py         # FacebookProvider
│   │   └── apple.py            # AppleProvider
│   ├── passwordless/
│   │   ├── __init__.py
│   │   ├── service.py          # PasswordlessService
│   │   └── challenge.py        # Challenge management
│   └── mfa/
│       ├── __init__.py
│       ├── service.py          # MFAService
│       └── totp.py             # TOTP implementation
├── models/
│   ├── social_account.py       # NEW
│   ├── auth_challenge.py       # NEW
│   └── mfa_method.py           # NEW
└── services/
    ├── oauth.py                # NEW
    ├── passwordless.py         # NEW
    └── mfa.py                  # NEW
```

### Configuration Changes

```python
class SimpleConfig(AuthConfig):
    """Configuration with optional extensions"""

    # Notification system (v1.1)
    notification_handler: Optional[NotificationHandler] = None

    # OAuth providers (v1.2)
    oauth_providers: Optional[Dict[str, OAuthProvider]] = None

    # Passwordless (v1.3)
    enable_magic_links: bool = False
    enable_otp: bool = False
    magic_link_expire_minutes: int = 15
    otp_expire_minutes: int = 5

    # MFA (v1.4)
    enable_mfa: bool = False
    mfa_required_for_users: List[str] = Field(default_factory=list)
```

### Extension Integration Example

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.extensions.notifications import WebhookHandler
from outlabs_auth.extensions.oauth import GoogleProvider, FacebookProvider

# Full configuration with all extensions
notification_handler = WebhookHandler(
    webhook_url="https://api.internal/notifications",
    headers={"X-API-Key": os.getenv("API_KEY")}
)

oauth_providers = {
    "google": GoogleProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    ),
    "facebook": FacebookProvider(
        client_id=os.getenv("FACEBOOK_CLIENT_ID"),
        client_secret=os.getenv("FACEBOOK_CLIENT_SECRET")
    )
}

auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler,
    oauth_providers=oauth_providers,
    enable_magic_links=True,
    enable_otp=True,
    enable_mfa=True
)

# All auth methods now available:
# 1. Password (built-in)
tokens = await auth.auth_service.login("user@example.com", "password")

# 2. OAuth (v1.2)
tokens = await auth.oauth_service.authenticate_with_provider("google", code, redirect_uri)

# 3. Magic link (v1.3)
await auth.passwordless_service.send_magic_link("user@example.com")
tokens = await auth.passwordless_service.verify_magic_link(code)

# 4. OTP (v1.3)
await auth.passwordless_service.send_otp("+1234567890", channel="sms")
tokens = await auth.passwordless_service.verify_otp("+1234567890", "123456")

# 5. TOTP/MFA (v1.4)
secret, qr_code = await auth.mfa_service.enable_totp(user.id)
is_valid = await auth.mfa_service.verify_totp(user.id, totp_code)
```

### Key Design Principles

1. **Optional**: All extensions are opt-in
2. **Independent**: Extensions can be adopted separately
3. **Compatible**: Work with both SimpleRBAC and EnterpriseRBAC
4. **No Vendor Lock-in**: Use pluggable abstractions (notification handlers, OAuth providers)
5. **Security First**: Rate limiting, expiration, state validation built-in
6. **Documented**: Comprehensive guides in AUTH_EXTENSIONS.md and SECURITY.md

### Testing Extensions

```python
# Test notification handler
async def test_webhook_handler():
    handler = WebhookHandler("https://webhook.site/...")
    event = NotificationEvent(
        type="welcome",
        recipient="test@example.com",
        data={"name": "Test User"}
    )
    assert await handler.send(event) is True

# Test OAuth flow
async def test_google_oauth(auth_with_oauth):
    # Mock OAuth provider
    auth_url = await auth_with_oauth.oauth_service.get_authorization_url(
        "google", "http://localhost/callback"
    )
    assert "accounts.google.com" in auth_url

# Test magic link
async def test_magic_link(auth_with_notifications):
    await auth_with_notifications.passwordless_service.send_magic_link("test@example.com")
    # Verify notification was sent
    # Verify challenge created in database
```

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

## Configuration System

### Base Configuration
```python
class AuthConfig(BaseModel):
    """Base configuration for all presets"""

    # JWT settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Password settings
    password_min_length: int = 8
    require_special_char: bool = True
    require_uppercase: bool = True
    require_digit: bool = True

    # Security
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
```

### Preset-Specific Configs
```python
class SimpleConfig(AuthConfig):
    """Configuration for SimpleRBAC"""

    # Simple mode has no additional config
    pass

class EnterpriseConfig(AuthConfig):
    """Configuration for EnterpriseRBAC"""

    # Entity settings (always enabled)
    max_entity_depth: int = 5
    allowed_entity_types: Optional[List[str]] = None
    allow_access_groups: bool = True

    # Optional features (opt-in)
    enable_context_aware_roles: bool = False
    enable_abac: bool = False
    enable_caching: bool = False
    enable_audit_log: bool = False  # Reserved for future extended/compliance capture

    # Caching settings (only used when enable_caching=True)
    redis_url: Optional[str] = None
    cache_ttl_seconds: int = 300
```

---

## Testing Strategy

### Unit Tests
```python
# Test each service independently
tests/unit/services/test_auth_service.py
tests/unit/services/test_permission_service.py
tests/unit/services/test_entity_service.py

# Test models
tests/unit/models/test_user_model.py
tests/unit/models/test_entity_model.py

# Test utilities
tests/unit/utils/test_jwt.py
tests/unit/utils/test_password.py
```

### Integration Tests
```python
# Test preset configurations
tests/integration/test_simple_rbac.py
tests/integration/test_enterprise_rbac.py

# Test complex scenarios
tests/integration/test_tree_permissions.py
tests/integration/test_context_aware_roles.py
tests/integration/test_abac_conditions.py
tests/integration/test_root_entity_isolation.py
```

### Example Tests
```python
# Test example applications work
tests/examples/test_simple_app.py
tests/examples/test_enterprise_app.py
```

### Test Fixtures
```python
@pytest.fixture
async def test_db():
    """Test database connection"""
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/test_outlabs_auth"
    )
    yield engine
    await engine.dispose()

@pytest.fixture
async def simple_auth(test_db):
    """SimpleRBAC instance for testing"""
    auth = SimpleRBAC(
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_outlabs_auth",
        secret_key="test-secret-key"
    )
    await auth.initialize()
    return auth

@pytest.fixture
async def test_user(simple_auth):
    """Create test user"""
    return await simple_auth.user_service.create_user(
        email="test@example.com",
        password="Test123!@#"
    )
```

---

## Migration Path from Current System

### Phase 1: Parallel Development
- Keep current API running
- Develop library alongside
- Test library in isolated projects

### Phase 2: Selective Migration
- New projects use library
- Existing projects stay on API
- No forced migration

### Phase 3: Gradual Deprecation
- Document API deprecation timeline
- Provide migration tools
- Support both for transition period

### Phase 4: API Sunset
- After all projects migrated
- Archive API code
- Maintain library only

---

## Performance Considerations

### Caching Strategy (EnterpriseRBAC with caching enabled)
```python
# Redis cache keys
user_permissions:{user_id}:{entity_id}  # TTL: 5 minutes
entity_path:{entity_id}                 # TTL: 10 minutes
role_permissions:{role_id}              # TTL: 15 minutes

# Cache invalidation on:
- Role permissions changed
- User membership changed
- Entity hierarchy changed
```

### Database Indexes
```python
# User collection
{"email": 1}  # Unique
{"status": 1}

# Role collection
{"name": 1}

# Permission collection
{"name": 1}
{"resource": 1, "action": 1}

# Entity collection (EnterpriseRBAC only)
{"slug": 1}  # Unique
{"parent_entity": 1}
{"entity_type": 1}

# EntityMembership collection (EnterpriseRBAC only)
{"user": 1, "entity": 1}  # Unique
{"entity": 1}
{"user": 1}
```

### Query Optimization
- Eager loading of relationships (use `fetch_links=True`)
- Batch permission checks when possible
- Limit entity path traversal depth
- Cache expensive queries

---

## Next Steps

1. ✅ Architecture defined
2. 🔄 Create implementation roadmap (next)
3. ⏭️ Design public API
4. ⏭️ Begin Phase 1 implementation

---

**Last Updated**: 2025-01-14 (PostgreSQL migration complete, SQLAlchemy async, closure table for tree queries)
**Next Review**: After testing all examples
