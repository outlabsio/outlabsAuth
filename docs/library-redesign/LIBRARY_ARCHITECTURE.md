# OutlabsAuth Library - Technical Architecture

**Version**: 1.0
**Date**: 2025-01-14
**Status**: Design Phase

---

## Table of Contents

1. [Overview](#overview)
2. [Package Structure](#package-structure)
3. [Preset Architecture](#preset-architecture)
4. [Data Models](#data-models)
5. [Service Layer](#service-layer)
6. [Dependency Injection](#dependency-injection)
7. [Configuration System](#configuration-system)
8. [Testing Strategy](#testing-strategy)

---

## Overview

OutlabsAuth is structured as a modular Python library with three preset configurations that build on each other:

```
Simple RBAC (Core)
    ↓
Hierarchical RBAC (+ Entity System)
    ↓
Full Featured (+ Advanced Features)
```

Each preset is a fully functional auth system that can be used independently.

---

## Package Structure

```
outlabs_auth/
├── __init__.py                 # Public API exports
├── core/
│   ├── __init__.py
│   ├── base.py                 # Base OutlabsAuth class
│   ├── config.py               # Configuration management
│   └── exceptions.py           # Custom exceptions
├── models/
│   ├── __init__.py
│   ├── base.py                 # BaseDocument
│   ├── user.py                 # UserModel
│   ├── role.py                 # RoleModel
│   ├── permission.py           # PermissionModel
│   ├── entity.py               # EntityModel
│   ├── membership.py           # EntityMembershipModel
│   └── token.py                # RefreshTokenModel
├── services/
│   ├── __init__.py
│   ├── auth.py                 # AuthService
│   ├── user.py                 # UserService
│   ├── role.py                 # RoleService
│   ├── permission.py           # PermissionService
│   ├── entity.py               # EntityService (hierarchical+)
│   └── membership.py           # MembershipService (hierarchical+)
├── presets/
│   ├── __init__.py
│   ├── simple.py               # SimpleRBAC preset
│   ├── hierarchical.py         # HierarchicalRBAC preset
│   └── full.py                 # FullFeatured preset
├── dependencies/
│   ├── __init__.py
│   ├── auth.py                 # FastAPI auth dependencies
│   ├── permissions.py          # Permission checking dependencies
│   └── entities.py             # Entity context dependencies (hierarchical+)
├── middleware/
│   ├── __init__.py
│   ├── auth.py                 # JWT middleware
│   └── tenant.py               # Multi-tenant middleware (optional)
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
    └── entity.py               # Entity schemas (hierarchical+)

examples/                       # Example applications
├── simple_app/
├── hierarchical_app/
├── full_featured_app/
└── migration_example/

tests/                          # Comprehensive test suite
├── unit/
├── integration/
└── examples/
```

---

## Preset Architecture

### Base Class: `OutlabsAuth`

All presets inherit from a base class that provides core functionality:

```python
class OutlabsAuth:
    """Base class for all OutlabsAuth presets"""

    def __init__(
        self,
        database: Any,
        config: Optional[AuthConfig] = None,
        user_model: Type[UserModel] = UserModel,
        role_model: Type[RoleModel] = RoleModel,
        permission_model: Type[PermissionModel] = PermissionModel,
    ):
        self.database = database
        self.config = config or AuthConfig()

        # Models
        self.user_model = user_model
        self.role_model = role_model
        self.permission_model = permission_model

        # Services (initialized in subclasses)
        self.auth_service: Optional[AuthService] = None
        self.user_service: Optional[UserService] = None
        self.role_service: Optional[RoleService] = None
        self.permission_service: Optional[PermissionService] = None

    # Core dependency methods (implemented in subclasses)
    async def get_current_user(self, token: str) -> UserModel:
        raise NotImplementedError

    def require_permission(self, permission: str):
        raise NotImplementedError

    # Utility methods
    async def initialize(self):
        """Initialize database collections/tables"""
        raise NotImplementedError
```

### Preset 1: SimpleRBAC

**Purpose**: Basic role-based access control without entity hierarchy.

**Features**:
- User management
- Role assignment (single role per user)
- Flat permission system
- JWT authentication

**Models Used**:
- UserModel
- RoleModel
- PermissionModel
- RefreshTokenModel

**Services**:
- AuthService
- UserService
- RoleService
- PermissionService (basic)

**Example**:
```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=mongo_client)

# Initialize database
await auth.initialize()

# Use in routes
@app.get("/users/me")
async def get_me(user = Depends(auth.get_current_user)):
    return user

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user = Depends(auth.require_permission("user:delete"))
):
    return await auth.user_service.delete_user(user_id)
```

**Implementation**:
```python
class SimpleRBAC(OutlabsAuth):
    """Simple role-based access control"""

    def __init__(self, database: Any, config: Optional[SimpleConfig] = None):
        super().__init__(database, config)

        # Initialize services
        self.auth_service = AuthService(database, self.user_model)
        self.user_service = UserService(database, self.user_model)
        self.role_service = RoleService(database, self.role_model)
        self.permission_service = BasicPermissionService(
            database, self.permission_model
        )

    async def get_current_user(self, token: str = Depends(oauth2_scheme)):
        """Get current authenticated user"""
        return await self.auth_service.get_current_user(token)

    def require_permission(self, permission: str):
        """Dependency that requires a specific permission"""
        async def _check_permission(
            user: UserModel = Depends(self.get_current_user)
        ):
            has_perm = await self.permission_service.check_permission(
                user.id, permission
            )
            if not has_perm:
                raise HTTPException(403, f"Permission denied: {permission}")
            return user

        return Depends(_check_permission)
```

### Preset 2: HierarchicalRBAC

**Purpose**: Role-based access with entity hierarchy and tree permissions.

**Features**:
- Everything from SimpleRBAC
- Entity hierarchy (organizational structure)
- Multiple roles per user (via entity memberships)
- Tree permissions (`resource:action_tree`)
- Entity context in permission checks

**Additional Models**:
- EntityModel
- EntityMembershipModel

**Additional Services**:
- EntityService
- MembershipService
- PermissionService (hierarchical)

**Example**:
```python
from outlabs_auth import HierarchicalRBAC

auth = HierarchicalRBAC(
    database=mongo_client,
    entity_types=["department", "team"]  # Custom types
)

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

# Assign user to entity with role
await auth.membership_service.add_member(
    entity_id=dept.id,
    user_id=user.id,
    role_id=manager_role.id
)

# Check permission with entity context
@app.post("/entities/{entity_id}/members")
async def add_member(
    entity_id: str,
    user = Depends(auth.require_permission_in_entity("member:create", entity_id))
):
    # user has member:create permission in this entity
    pass
```

**Implementation Highlights**:
```python
class HierarchicalRBAC(OutlabsAuth):
    """Hierarchical RBAC with entity system"""

    def __init__(
        self,
        database: Any,
        config: Optional[HierarchicalConfig] = None,
        entity_types: Optional[List[str]] = None
    ):
        super().__init__(database, config)

        # Entity configuration
        self.allowed_entity_types = entity_types or [
            "organization", "division", "department", "team"
        ]

        # Add entity-related models
        self.entity_model = EntityModel
        self.membership_model = EntityMembershipModel

        # Initialize all services including entity services
        self._init_services()

    def require_permission_in_entity(
        self,
        permission: str,
        entity_id: str
    ):
        """Check permission within specific entity context"""
        async def _check_permission(
            user: UserModel = Depends(self.get_current_user)
        ):
            has_perm = await self.permission_service.check_permission(
                user_id=user.id,
                permission=permission,
                entity_id=entity_id
            )
            if not has_perm:
                raise HTTPException(
                    403,
                    f"Permission denied: {permission} in entity {entity_id}"
                )
            return user

        return Depends(_check_permission)

    def require_tree_permission(
        self,
        permission: str,
        target_entity_id: str
    ):
        """Check tree permission (checks parent entities)"""
        # Implementation checks if user has permission_tree in any parent
        pass
```

### Preset 3: FullFeatured

**Purpose**: Complete auth system with all advanced features.

**Features**:
- Everything from HierarchicalRBAC
- Context-aware roles (permissions vary by entity type)
- ABAC conditions (attribute-based access control)
- Permission caching (Redis)
- Advanced audit logging

**Additional Features**:
- Role permissions adapt based on entity type
- Conditional permissions with policy engine
- Performance optimizations
- Enhanced logging and monitoring

**Example**:
```python
from outlabs_auth import FullFeatured

auth = FullFeatured(
    database=mongo_client,
    redis_url="redis://localhost:6379",
    enable_caching=True,
    enable_abac=True
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

    # Context-aware permissions (FullFeatured only)
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

    # ABAC conditions (FullFeatured only)
    conditions: List[Condition] = Field(default_factory=list)

    # Status
    is_active: bool = True
```

### Hierarchical Models (Hierarchical + Full)

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

    # Optional: Multi-tenant support
    tenant_id: Optional[str] = None

    # Status
    status: str = "active"
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Direct permissions (optional)
    direct_permissions: List[str] = Field(default_factory=list)

    # Configuration
    allowed_child_classes: List[EntityClass] = []
    allowed_child_types: List[str] = []
    max_members: Optional[int] = None
```

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

### Model Changes from Current System

#### Removed Fields
- ❌ `platform_id` (no longer needed)
- ❌ Platform-specific isolation logic

#### Added Fields
- ✅ `tenant_id` (optional, for multi-tenant mode)

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

#### HierarchicalPermissionService (Hierarchical + Full)
```python
class HierarchicalPermissionService(BasicPermissionService):
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
```

#### FullPermissionService (Full preset)
```python
class FullPermissionService(HierarchicalPermissionService):
    """Permission checking with ABAC and caching"""

    async def check_permission_with_context(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
        resource_attributes: Optional[Dict[str, Any]] = None
    ) -> PolicyResult:
        """
        Full RBAC + ReBAC + ABAC evaluation.

        Steps:
        1. Check RBAC (does user have permission in role?)
        2. Check ReBAC (is entity relationship valid?)
        3. Check ABAC (do conditions pass?)
        """
        pass
```

### EntityService (Hierarchical + Full)
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

### Entity Context Dependencies (Hierarchical + Full)
```python
# outlabs_auth/dependencies/entities.py

def require_entity_permission(
    auth: HierarchicalRBAC,
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

class HierarchicalConfig(AuthConfig):
    """Configuration for HierarchicalRBAC"""

    # Entity settings
    max_entity_depth: int = 5
    allowed_entity_types: Optional[List[str]] = None
    allow_access_groups: bool = True

    # Permission settings
    enable_tree_permissions: bool = True

class FullConfig(HierarchicalConfig):
    """Configuration for FullFeatured"""

    # Caching
    enable_caching: bool = True
    redis_url: Optional[str] = None
    cache_ttl_seconds: int = 300

    # ABAC
    enable_abac: bool = True

    # Advanced features
    enable_audit_log: bool = False
    enable_rate_limiting: bool = False
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
tests/integration/test_hierarchical_rbac.py
tests/integration/test_full_featured.py

# Test complex scenarios
tests/integration/test_tree_permissions.py
tests/integration/test_context_aware_roles.py
tests/integration/test_abac_conditions.py
```

### Example Tests
```python
# Test example applications work
tests/examples/test_simple_app.py
tests/examples/test_hierarchical_app.py
tests/examples/test_full_app.py
```

### Test Fixtures
```python
@pytest.fixture
async def mongo_db():
    """Test database connection"""
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_outlabs_auth"]
    yield db
    await client.drop_database("test_outlabs_auth")

@pytest.fixture
async def simple_auth(mongo_db):
    """SimpleRBAC instance for testing"""
    auth = SimpleRBAC(database=mongo_db)
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

### Caching Strategy (FullFeatured)
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

# Entity collection (Hierarchical+)
{"slug": 1}  # Unique
{"parent_entity": 1}
{"entity_type": 1}

# EntityMembership collection (Hierarchical+)
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

**Last Updated**: 2025-01-14
**Next Review**: After Phase 1 prototype
