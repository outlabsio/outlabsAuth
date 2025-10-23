# Service Layer

**Complete reference for OutlabsAuth business logic services**

---

## Table of Contents

- [Overview](#overview)
- [Service Architecture](#service-architecture)
- [Core Services](#core-services)
  - [AuthService](#authservice)
  - [UserService](#userservice)
  - [RoleService](#roleservice)
  - [PermissionService](#permissionservice)
- [EnterpriseRBAC Services](#enterpriserbac-services)
  - [EntityService](#entityservice)
  - [MembershipService](#membershipservice)
  - [EnterprisePermissionService](#enterprisepermissionservice)
- [Authentication Services](#authentication-services)
  - [ApiKeyService](#apikeyservice)
  - [ServiceTokenService](#servicetokenservice)
  - [OAuthService](#oauthservice)
- [Support Services](#support-services)
  - [NotificationService](#notificationservice)
  - [PolicyEvaluationEngine](#policyevaluationengine)
  - [RedisClient](#redisclient)
- [Lifecycle Hooks Pattern](#lifecycle-hooks-pattern)
- [See Also](#see-also)

---

## Overview

The **Service Layer** contains all business logic for OutlabsAuth. Services orchestrate operations across models, enforce business rules, emit lifecycle hooks, and manage caching.

### Service Responsibilities

```
┌─────────────────────────────────────────────────────────┐
│                    Service Layer                         │
├─────────────────────────────────────────────────────────┤
│  ✓ Business logic enforcement                           │
│  ✓ Multi-model orchestration                            │
│  ✓ Transaction management                               │
│  ✓ Lifecycle hook emission                              │
│  ✓ Cache management (Redis)                             │
│  ✓ Notification coordination                            │
│  ✓ Input validation and sanitization                    │
│  ✓ Exception handling and error messages                │
└─────────────────────────────────────────────────────────┘
```

### Service Hierarchy

```
BaseService (lifecycle hooks)
    │
    ├── UserService (user management + hooks)
    ├── RoleService (role management + hooks)
    ├── ApiKeyService (API key management + hooks)
    │
    ├── AuthService (authentication)
    │
    ├── BasicPermissionService (flat RBAC)
    │   └── EnterprisePermissionService (hierarchical RBAC + tree perms)
    │
    ├── EntityService (hierarchy management)
    ├── MembershipService (entity-user-role relationships)
    │
    ├── OAuthService (social login)
    ├── ServiceTokenService (JWT service tokens)
    │
    └── NotificationService (event coordinator)
```

---

## Service Architecture

### Service Initialization

Services are initialized by the `OutlabsAuth` core class based on configuration:

```python
# In OutlabsAuth.__init__()
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.user_service import UserService
from outlabs_auth.services.permission import BasicPermissionService

# Initialize services
self.auth_service = AuthService(
    database=database,
    config=config,
    notification_service=notification_service
)

self.user_service = UserService(database=database)

self.permission_service = BasicPermissionService(
    database=database,
    config=config
)

# For EnterpriseRBAC
if config.enable_entity_hierarchy:
    from outlabs_auth.services.entity import EntityService
    from outlabs_auth.services.permission import EnterprisePermissionService

    self.entity_service = EntityService(
        config=config,
        redis_client=redis_client
    )

    self.permission_service = EnterprisePermissionService(
        database=database,
        config=config,
        redis_client=redis_client
    )
```

### Service Dependencies

```python
# Example: AuthService dependencies
class AuthService:
    def __init__(
        self,
        database: AsyncIOMotorDatabase,      # MongoDB access
        config: AuthConfig,                  # Configuration
        notification_service: Optional[NotificationService] = None  # Optional
    ):
        self.database = database
        self.config = config
        self.notifications = notification_service
```

**Common dependencies:**
- `database`: MongoDB database instance (Motor)
- `config`: AuthConfig with settings
- `redis_client`: Optional RedisClient for caching
- `notification_service`: Optional NotificationService for events

---

## Core Services

### AuthService

**Handles user authentication operations.**

**Location:** `outlabs_auth/services/auth.py`

#### Responsibilities
- Email/password authentication
- JWT token creation and verification
- Refresh token management
- Account lockout after failed attempts
- Multi-device session support

#### Key Methods

##### `login()`
Authenticate user with email and password.

```python
async def login(
    self,
    email: str,
    password: str,
    device_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[UserModel, TokenPair]
```

**Features:**
- Email validation and normalization
- Password verification with argon2id
- Account lockout after max failed attempts
- Failed login tracking
- Refresh token creation with device info
- Notification emission (`user.login`, `user.login_failed`, `user.locked`)

**Example:**
```python
from outlabs_auth.services.auth import AuthService

auth_service = AuthService(
    database=db,
    config=config,
    notification_service=notifications
)

try:
    user, tokens = await auth_service.login(
        email="user@example.com",
        password="MyPassword123!",
        device_name="iPhone 14 Pro",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0..."
    )

    # Return tokens to client
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": "bearer"
    }

except InvalidCredentialsError:
    # Wrong email or password
    return {"error": "Invalid credentials"}

except AccountLockedError as e:
    # Account locked due to failed attempts
    return {
        "error": "Account locked",
        "locked_until": e.details["locked_until"]
    }

except AccountInactiveError:
    # Account is not active
    return {"error": "Account inactive"}
```

##### `logout()`
Revoke refresh token.

```python
async def logout(self, refresh_token: str) -> bool
```

**Example:**
```python
# Revoke refresh token (logout from device)
revoked = await auth_service.logout(refresh_token)
```

##### `refresh_access_token()`
Get new access token using refresh token.

```python
async def refresh_access_token(
    self, refresh_token: str
) -> TokenPair
```

**Example:**
```python
# Get new access token
tokens = await auth_service.refresh_access_token(old_refresh_token)

# Return new access token (same refresh token)
return {
    "access_token": tokens.access_token,
    "refresh_token": tokens.refresh_token  # Same as before
}
```

##### `get_current_user()`
Get user from access token.

```python
async def get_current_user(
    self, access_token: str
) -> UserModel
```

**Example:**
```python
# Verify access token and get user
user = await auth_service.get_current_user(access_token)
print(user.email)  # user@example.com
```

##### `revoke_all_user_tokens()`
Logout from all devices.

```python
async def revoke_all_user_tokens(
    self, user_id: str
) -> int
```

**Example:**
```python
# Security incident: logout from all devices
count = await auth_service.revoke_all_user_tokens(user_id)
print(f"Revoked {count} active sessions")
```

#### TokenPair Class

```python
class TokenPair:
    access_token: str    # JWT access token (15 min default)
    refresh_token: str   # JWT refresh token (30 days default)
    token_type: str      # "bearer"

    def to_dict(self):
        """Convert to API response format."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type
        }
```

---

### UserService

**User management with lifecycle hooks.**

**Location:** `outlabs_auth/services/user_service.py`

#### Responsibilities
- User CRUD operations
- Lifecycle hook emission
- Password management
- Email verification
- User status management

#### Lifecycle Hooks

Override these methods to add custom logic:

```python
class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        """Called after user registration."""
        await email_service.send_welcome(user.email)
        logger.info(f"New user: {user.email}")

    async def on_after_login(self, user, request=None, response=None):
        """Called after successful login."""
        await analytics.track("login", user.id)

    async def on_after_update(self, user, update_dict, request=None):
        """Called after profile update."""
        await audit_log.log("user_updated", user.id, update_dict)

    async def on_before_delete(self, user, request=None):
        """Called before deletion (can prevent by raising)."""
        if user.is_superuser:
            raise ValueError("Cannot delete superuser")

    async def on_after_delete(self, user, request=None):
        """Called after deletion."""
        await cleanup_service.delete_user_data(user.id)

    async def on_failed_login(self, email, request=None):
        """Called after failed login."""
        await security_monitor.track_failed_login(email)
```

**Available Hooks:**
- `on_after_register`: After user registration
- `on_after_login`: After successful login
- `on_after_update`: After profile update
- `on_before_delete`: Before deletion (can prevent)
- `on_after_delete`: After deletion
- `on_after_request_verify`: After email verification request
- `on_after_verify`: After email verification
- `on_after_forgot_password`: After password reset request
- `on_after_reset_password`: After password reset
- `on_failed_login`: After failed login
- `on_after_oauth_register`: After OAuth registration (v1.2)
- `on_after_oauth_login`: After OAuth login (v1.2)
- `on_after_oauth_associate`: After account linking (v1.2)

#### Core Methods

```python
class UserService(BaseService):
    async def get_user(self, user_id: str) -> Optional[UserModel]:
        """Get user by ID."""

    async def create_user(self, email: str, password: str, **kwargs) -> UserModel:
        """Create user (calls on_after_register)."""

    async def update_user(self, user_id: str, update_dict: Dict) -> UserModel:
        """Update user (calls on_after_update)."""

    async def delete_user(self, user_id: str) -> None:
        """Delete user (calls on_before/after_delete)."""
```

---

### RoleService

**Role management with lifecycle hooks.**

**Location:** `outlabs_auth/services/role_service.py`

#### Lifecycle Hooks

```python
class MyRoleService(RoleService):
    async def on_after_role_assigned(
        self, user, role, entity_id=None, request=None
    ):
        """Called after role assigned."""
        await notifications.send_role_assigned(user.email, role.name)
        await cache_service.invalidate_user_permissions(user.id)

    async def on_after_permission_changed(
        self, role, old_permissions, new_permissions, request=None
    ):
        """Called after role permissions changed."""
        # Invalidate cache for all users with this role
        await cache_service.invalidate_role_permissions(role.id)
```

**Available Hooks:**
- `on_after_role_created`: After role creation
- `on_after_role_updated`: After role update
- `on_before_role_deleted`: Before deletion (can prevent)
- `on_after_role_deleted`: After deletion
- `on_after_role_assigned`: After role assigned to user
- `on_after_role_removed`: After role removed from user
- `on_after_permission_changed`: After role permissions changed

---

### PermissionService

**Permission checking and management.**

**Location:** `outlabs_auth/services/permission.py`

#### BasicPermissionService

For **SimpleRBAC** - flat permission system.

##### `check_permission()`

```python
async def check_permission(
    self, user_id: str, permission: str
) -> bool
```

**Features:**
- Direct permission checking
- Wildcard support (`user:*`, `*:*`)
- Superuser bypass

**Example:**
```python
# Check if user can create users
has_perm = await perm_service.check_permission(
    user_id="507f1f77bcf86cd799439011",
    permission="user:create"
)

if has_perm:
    await create_user(...)
else:
    raise PermissionDeniedError("user:create")
```

##### `get_user_permissions()`

```python
async def get_user_permissions(
    self, user_id: str
) -> List[str]
```

**Example:**
```python
# Get all permissions for user
permissions = await perm_service.get_user_permissions(user_id)
# ['user:create', 'user:read', 'role:read']
```

##### `require_permission()`

```python
async def require_permission(
    self, user_id: str, permission: str
) -> None
```

**Raises:** `PermissionDeniedError` if user lacks permission.

**Example:**
```python
# Require permission (raises if denied)
await perm_service.require_permission(user_id, "user:delete")
# If we reach here, user has permission
```

##### `require_any_permission()`

```python
async def require_any_permission(
    self, user_id: str, permissions: List[str]
) -> None
```

**Example:**
```python
# User needs at least one of these permissions
await perm_service.require_any_permission(
    user_id,
    ["user:update", "user:delete"]
)
```

##### `require_all_permissions()`

```python
async def require_all_permissions(
    self, user_id: str, permissions: List[str]
) -> None
```

**Example:**
```python
# User needs ALL of these permissions
await perm_service.require_all_permissions(
    user_id,
    ["user:create", "role:assign", "permission:grant"]
)
```

##### Permission CRUD

```python
# Create permission
perm = await perm_service.create_permission(
    name="invoice:approve",
    display_name="Approve Invoices",
    description="Can approve invoices up to $10,000"
)

# Get permission by name
perm = await perm_service.get_permission_by_name("user:create")

# List permissions
perms, total = await perm_service.list_permissions(
    page=1,
    limit=50,
    resource="user"  # Filter by resource
)

# Delete permission
deleted = await perm_service.delete_permission(permission_id)
```

---

## EnterpriseRBAC Services

### EntityService

**Entity hierarchy management for EnterpriseRBAC.**

**Location:** `outlabs_auth/services/entity.py`

#### Responsibilities
- Entity CRUD operations
- Hierarchy validation (cycles, depth, allowed types)
- Closure table maintenance (O(1) queries)
- Path and tree traversal
- Redis caching for paths/descendants

#### Key Methods

##### `create_entity()`

```python
async def create_entity(
    self,
    name: str,
    display_name: str,
    entity_class: EntityClass,
    entity_type: str,
    parent_id: Optional[str] = None,
    description: Optional[str] = None,
    slug: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs
) -> EntityModel
```

**Features:**
- Hierarchy validation (no ACCESS_GROUP → STRUCTURAL)
- Depth limit enforcement
- Slug auto-generation
- Closure table creation

**Example:**
```python
from outlabs_auth.models.entity import EntityClass

# Create organization (root entity)
org = await entity_service.create_entity(
    name="acme_corp",
    display_name="ACME Corporation",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="organization"
)

# Create department under organization
dept = await entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(org.id)
)

# Create team under department
team = await entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(dept.id)
)

# Create access group (for special permissions)
group = await entity_service.create_entity(
    name="senior_engineers",
    display_name="Senior Engineers",
    entity_class=EntityClass.ACCESS_GROUP,
    entity_type="group",
    parent_id=str(team.id)
)
```

##### `get_entity_path()`

Get path from root to entity (uses closure table, O(1)).

```python
async def get_entity_path(
    self, entity_id: str
) -> List[EntityModel]
```

**Example:**
```python
# Get path from root to team
path = await entity_service.get_entity_path(team_id)

# path = [org, dept, team]
for entity in path:
    print(f"{entity.display_name} ({entity.entity_type})")

# Output:
# ACME Corporation (organization)
# Engineering Department (department)
# Backend Team (team)
```

##### `get_descendants()`

Get all descendant entities (uses closure table, O(1)).

```python
async def get_descendants(
    self,
    entity_id: str,
    entity_type: Optional[str] = None
) -> List[EntityModel]
```

**Example:**
```python
# Get all descendants of organization
descendants = await entity_service.get_descendants(org_id)
# Returns: [dept, team, team2, group, ...]

# Get only teams under organization
teams = await entity_service.get_descendants(
    org_id,
    entity_type="team"
)
```

##### `get_children()`

Get direct children only.

```python
async def get_children(
    self, entity_id: str
) -> List[EntityModel]
```

**Example:**
```python
# Get departments directly under organization
departments = await entity_service.get_children(org_id)
```

##### `delete_entity()`

Soft delete entity (sets status to 'archived').

```python
async def delete_entity(
    self,
    entity_id: str,
    cascade: bool = False
) -> bool
```

**Example:**
```python
# Delete entity (fails if has children)
await entity_service.delete_entity(team_id)

# Delete entity and all descendants
await entity_service.delete_entity(
    dept_id,
    cascade=True  # Delete all children recursively
)
```

#### Cache Management

##### `invalidate_entity_cache()`

```python
async def invalidate_entity_cache(
    self, entity_id: str
) -> int
```

**When to call:**
- Entity updated
- Entity deleted
- Hierarchy changed

**Example:**
```python
# Update entity
entity = await entity_service.update_entity(
    entity_id,
    display_name="New Name"
)

# Invalidate cache
await entity_service.invalidate_entity_cache(entity_id)
```

##### `invalidate_entity_tree_cache()`

Invalidate cache for entity and all ancestors/descendants.

```python
async def invalidate_entity_tree_cache(
    self, entity_id: str
) -> int
```

**Example:**
```python
# Major hierarchy change - invalidate entire tree
deleted = await entity_service.invalidate_entity_tree_cache(org_id)
print(f"Invalidated {deleted} cache entries")
```

---

### MembershipService

**Entity membership management (user-entity-role relationships).**

**Location:** `outlabs_auth/services/membership.py`

#### Responsibilities
- Add/remove members from entities
- Assign multiple roles per membership
- Time-based validity management
- Member listing and filtering

#### Key Methods

##### `add_member()`

```python
async def add_member(
    self,
    entity_id: str,
    user_id: str,
    role_ids: List[str],
    joined_by: Optional[str] = None,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
) -> EntityMembershipModel
```

**Example:**
```python
# Add user to team with multiple roles
membership = await membership_service.add_member(
    entity_id=team_id,
    user_id=user_id,
    role_ids=[developer_role_id, team_lead_role_id],
    joined_by=admin_user_id
)

# Add user with time-based membership
from datetime import datetime, timedelta

membership = await membership_service.add_member(
    entity_id=project_id,
    user_id=contractor_id,
    role_ids=[contractor_role_id],
    valid_from=datetime.utcnow(),
    valid_until=datetime.utcnow() + timedelta(days=90)  # 90-day contract
)
```

##### `remove_member()`

```python
async def remove_member(
    self, entity_id: str, user_id: str
) -> bool
```

**Example:**
```python
# Remove user from team
await membership_service.remove_member(team_id, user_id)
```

##### `update_member_roles()`

```python
async def update_member_roles(
    self,
    entity_id: str,
    user_id: str,
    role_ids: List[str]
) -> EntityMembershipModel
```

**Example:**
```python
# Promote user: add team lead role
membership = await membership_service.update_member_roles(
    entity_id=team_id,
    user_id=user_id,
    role_ids=[developer_role_id, team_lead_role_id, architect_role_id]
)
```

##### `get_entity_members()`

```python
async def get_entity_members(
    self,
    entity_id: str,
    page: int = 1,
    limit: int = 50,
    active_only: bool = True
) -> tuple[List[EntityMembershipModel], int]
```

**Example:**
```python
# Get team members
members, total = await membership_service.get_entity_members(
    entity_id=team_id,
    page=1,
    limit=20
)

for membership in members:
    user = await membership.user.fetch()
    roles = await membership.fetch_all_links()
    print(f"{user.email}: {[r.name for r in roles]}")
```

##### `get_user_entities()`

```python
async def get_user_entities(
    self,
    user_id: str,
    page: int = 1,
    limit: int = 50,
    entity_type: Optional[str] = None,
    active_only: bool = True
) -> tuple[List[EntityMembershipModel], int]
```

**Example:**
```python
# Get all teams user belongs to
memberships, total = await membership_service.get_user_entities(
    user_id=user_id,
    entity_type="team"
)

for membership in memberships:
    entity = await membership.entity.fetch()
    print(f"Member of: {entity.display_name}")
```

##### `is_member()`

```python
async def is_member(
    self,
    entity_id: str,
    user_id: str,
    active_only: bool = True
) -> bool
```

**Example:**
```python
# Check if user is team member
if await membership_service.is_member(team_id, user_id):
    # User is a member
    pass
```

---

### EnterprisePermissionService

**Permission checking with entity hierarchy and tree permissions.**

**Location:** `outlabs_auth/services/permission.py`

Extends `BasicPermissionService` with:
- Entity-scoped permissions
- Tree permissions (`_tree` suffix)
- Permission inheritance via closure table
- Context-aware roles
- ABAC condition evaluation
- Redis caching

#### Key Methods

##### `check_permission()`

```python
async def check_permission(
    self,
    user_id: str,
    permission: str,
    entity_id: Optional[str] = None,
) -> tuple[bool, str]
```

**Returns:** `(has_permission, source)` where source is:
- `"direct"`: Permission from membership in target entity
- `"tree"`: Tree permission from ancestor
- `"all"`: Platform-wide permission (`_all` suffix)
- `"superuser"`: User is superuser

**Permission Resolution Algorithm:**
1. Check Redis cache (if enabled)
2. Check direct permission in target entity
3. Check tree permission (`_tree`) in ancestors (via closure table)
4. Check platform-wide permission (`_all`)
5. Cache result

**Example:**
```python
# Check if user can update entity
has_perm, source = await perm_service.check_permission(
    user_id,
    "entity:update",
    entity_id=team_id
)

if has_perm:
    print(f"Permission granted via: {source}")
    # source could be:
    # - "direct" (user is member of team with entity:update)
    # - "tree" (user has entity:update_tree in parent dept)
    # - "all" (user has entity:update_all from any membership)
    # - "superuser" (user.is_superuser)
```

**Tree Permission Example:**
```python
# User is member of DEPARTMENT with "project:delete_tree" permission
# This allows them to delete ALL projects under that department

# Check permission for team under department
has_perm, source = await perm_service.check_permission(
    user_id,
    "project:delete",
    entity_id=team_project_id  # Team is descendant of department
)

# has_perm = True, source = "tree"
```

**Platform-Wide Example:**
```python
# User has "user:read_all" permission in ANY entity
# This allows them to read users across the entire platform

has_perm, source = await perm_service.check_permission(
    user_id,
    "user:read",
    entity_id=any_entity_id
)

# has_perm = True, source = "all"
```

##### `has_permission()`

Convenience method that returns only bool.

```python
async def has_permission(
    self,
    user_id: str,
    permission: str,
    entity_id: Optional[str] = None,
) -> bool
```

**Example:**
```python
# Simple boolean check
if await perm_service.has_permission(user_id, "entity:update", entity_id):
    await update_entity(...)
```

##### `get_user_permissions_in_entity()`

```python
async def get_user_permissions_in_entity(
    self,
    user_id: str,
    entity_id: str
) -> List[str]
```

**Example:**
```python
# Get all permissions user has in specific team
permissions = await perm_service.get_user_permissions_in_entity(
    user_id,
    team_id
)
# ['entity:read', 'entity:update', 'project:create', 'project:delete_tree']
```

##### `check_permission_with_context()` (ABAC)

Check permission with ABAC condition evaluation.

```python
async def check_permission_with_context(
    self,
    user_id: str,
    permission: str,
    entity_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> tuple[bool, str]
```

**Example:**
```python
# Department-based access control
context = {
    "user": {"department": "engineering"},
    "resource": {"department": "engineering", "budget": 50000}
}

has_perm, source = await perm_service.check_permission_with_context(
    user_id,
    "project:approve",
    entity_id,
    context
)

# If role has condition: resource.department == user.department
# Permission granted only if both are "engineering"
```

#### Cache Management

##### `invalidate_user_permissions()`

```python
async def invalidate_user_permissions(
    self, user_id: str
) -> int
```

**When to call:**
- User's roles changed
- User's memberships changed
- User deleted

**Example:**
```python
# After assigning new role
await membership_service.update_member_roles(...)
await perm_service.invalidate_user_permissions(user_id)
```

##### `invalidate_entity_permissions()`

```python
async def invalidate_entity_permissions(
    self, entity_id: str
) -> int
```

**When to call:**
- Entity permissions changed
- Entity roles changed
- Entity deleted

**Example:**
```python
# After updating entity roles
await role_service.update_role_permissions(...)
await perm_service.invalidate_entity_permissions(entity_id)
```

---

## Authentication Services

### ApiKeyService

**API key management with lifecycle hooks.**

**Location:** `outlabs_auth/services/api_key_service.py`

#### Lifecycle Hooks

```python
class MyApiKeyService(ApiKeyService):
    async def on_api_key_created(
        self, api_key, plain_key, request=None
    ):
        """Called after API key creation."""
        # ONLY time to show full key!
        await email_service.send_api_key(user.email, plain_key)

    async def on_api_key_locked(
        self, api_key, reason, request=None
    ):
        """Called after temporary lock (DD-028)."""
        await security_alert.send(
            f"API key {api_key.key_prefix} locked: {reason}"
        )

    async def on_failed_verification(
        self, key_prefix, reason, request=None
    ):
        """Called after failed verification."""
        await security_monitor.track_api_key_failure(key_prefix)
```

**Available Hooks:**
- `on_api_key_created`: After creation (with plain key!)
- `on_api_key_revoked`: After revocation
- `on_api_key_locked`: After temporary lock
- `on_api_key_unlocked`: After unlock
- `on_api_key_rotated`: After rotation
- `on_failed_verification`: After failed verification

---

### ServiceTokenService

**JWT service token management for service-to-service authentication.**

**Location:** `outlabs_auth/services/service_token.py`

#### Features
- Ultra-fast validation (~0.5ms, zero DB hits)
- Service identity verification
- Token expiration management
- No database lookups

**Example:**
```python
from outlabs_auth.services.service_token import ServiceTokenService

service_token_service = ServiceTokenService(
    secret_key="your-secret",
    algorithm="HS256"
)

# Create service token
token = service_token_service.create_service_token(
    service_id="email-service",
    service_name="Email Service",
    expires_in_days=365
)

# Verify token (no DB lookup)
service_info = service_token_service.verify_service_token(token)
# service_info = {"service_id": "email-service", "service_name": "Email Service"}
```

---

### OAuthService

**OAuth social login and account linking.**

**Location:** `outlabs_auth/services/oauth_service.py`

#### Responsibilities
- Authorization URL generation with security (state, PKCE, nonce)
- OAuth callback processing
- Account linking by verified email
- User creation for new OAuth users
- Account unlinking with safety checks

#### Key Methods

##### `get_authorization_url()`

```python
async def get_authorization_url(
    self,
    provider: str,
    redirect_uri: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str
```

**Example:**
```python
# Start OAuth login flow
auth_url = await oauth_service.get_authorization_url(
    provider="google",
    redirect_uri="http://localhost:3000/auth/google/callback"
)

# Redirect user to auth_url
return RedirectResponse(url=auth_url)
```

##### `handle_callback()`

Process OAuth callback and create/link user.

```python
async def handle_callback(
    self,
    provider: str,
    code: str,
    state: str,
    redirect_uri: str,
) -> OAuthCallbackResult
```

**Example:**
```python
# Handle OAuth callback
result = await oauth_service.handle_callback(
    provider="google",
    code=request.query_params["code"],
    state=request.query_params["state"],
    redirect_uri="http://localhost:3000/auth/google/callback"
)

# result.user: UserModel
# result.tokens: TokenPair
# result.is_new_user: bool
# result.linked_account: bool

if result.is_new_user:
    print("New user registered via Google")
elif result.linked_account:
    print("Google account linked to existing user")
else:
    print("Existing user logged in via Google")
```

---

## Support Services

### NotificationService

**Central coordinator for auth-related notifications.**

**Location:** `outlabs_auth/services/notification.py`

#### Responsibilities
- Route events to appropriate channels (RabbitMQ, Email, SMS, Webhooks)
- Fire-and-forget execution (non-blocking)
- Event validation and enrichment

#### Event Types

**Authentication:**
- `user.login`: Successful login
- `user.login_failed`: Failed login attempt
- `user.locked`: Account locked
- `user.logout`: User logged out

**User Lifecycle:**
- `user.created`: New user registered
- `user.email_verified`: Email verified
- `user.deleted`: User deleted

**Password:**
- `user.password_changed`: Password updated
- `user.password_reset_requested`: Reset initiated

**Authorization:**
- `role.assigned`: Role added to user
- `role.revoked`: Role removed
- `permission.denied`: Access denied

**System:**
- `auth.error`: Auth system error
- `security.threat_detected`: Suspicious activity
- `api_key.created`: API key created
- `api_key.revoked`: API key revoked

#### Usage

```python
from outlabs_auth.services.notification import NotificationService
from outlabs_auth.services.channels import RabbitMQChannel

# Configure channels
rabbitmq = RabbitMQChannel(url="amqp://localhost")
await rabbitmq.connect()

notification_service = NotificationService(
    enabled=True,
    channels=[rabbitmq]
)

# Emit event (fire-and-forget, non-blocking)
await notification_service.emit(
    "user.login",
    data={
        "user_id": str(user.id),
        "email": user.email
    },
    metadata={
        "ip": "192.168.1.100",
        "device": "iPhone 14"
    }
)

# Notification is sent asynchronously
# Auth operations never block on notifications
```

---

### PolicyEvaluationEngine

**ABAC policy and condition evaluation.**

**Location:** `outlabs_auth/services/policy_engine.py`

#### Responsibilities
- Evaluate conditions with 20+ operators
- Evaluate condition groups (AND/OR logic)
- Build context from user/resource models
- Support dynamic attribute comparisons

#### Key Methods

##### `evaluate_condition()`

```python
def evaluate_condition(
    self,
    condition: Condition,
    context: Dict[str, Any]
) -> bool
```

**Example:**
```python
from outlabs_auth.models.condition import Condition

engine = PolicyEvaluationEngine()

# Condition: resource.department == user.department
condition = Condition(
    attribute="resource.department",
    operator="equals",
    value="user.department"  # Dynamic comparison
)

context = {
    "user": {"department": "engineering"},
    "resource": {"department": "engineering"}
}

passes = engine.evaluate_condition(condition, context)
# passes = True (both are "engineering")
```

##### `create_context()`

```python
def create_context(
    self,
    user: Optional[Dict[str, Any]] = None,
    resource: Optional[Dict[str, Any]] = None,
    env: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Example:**
```python
# Create ABAC context
context = engine.create_context(
    user={"id": "123", "department": "engineering", "role": "senior"},
    resource={"id": "456", "type": "project", "budget": 100000},
    env={"location": "US", "network": "internal"}
)

# Context includes auto-generated time attributes:
# context["time"]["hour"] = 14
# context["time"]["day_of_week"] = "monday"
# context["time"]["is_business_hours"] = True
```

---

### RedisClient

**Redis connection and operation wrapper.**

**Location:** `outlabs_auth/services/redis_client.py`

#### Responsibilities
- Redis connection management
- Key generation with namespacing
- Caching operations
- Pub/Sub for cache invalidation
- Pattern-based deletion

#### Key Methods

```python
class RedisClient:
    async def get(self, key: str) -> Any:
        """Get value from Redis."""

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set value in Redis with TTL."""

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""

    async def publish(self, channel: str, message: str) -> None:
        """Publish message to channel."""

    def make_key(self, *parts: str) -> str:
        """Generate namespaced key."""
```

**Example:**
```python
# Generate namespaced key
cache_key = redis_client.make_key(
    "auth", "perm", user_id, permission, entity_id
)
# "outlabs:auth:perm:507f...:entity:update:507f..."

# Set with TTL
await redis_client.set(cache_key, result, ttl=3600)

# Get
cached = await redis_client.get(cache_key)

# Delete pattern
deleted = await redis_client.delete_pattern("outlabs:auth:perm:*")

# Pub/Sub for multi-instance cache invalidation
await redis_client.publish(
    "cache_invalidation",
    f"user:{user_id}:permissions"
)
```

---

## Lifecycle Hooks Pattern

**From DD-040: FastAPI-Users lifecycle hooks pattern**

### What Are Lifecycle Hooks?

Lifecycle hooks are **optional methods** that services call at key points in the execution flow. You can override these methods to add custom logic without modifying the core service code.

### BaseService

All services that support hooks extend `BaseService`:

```python
# outlabs_auth/services/base.py

class BaseService:
    """
    Base class for all services with lifecycle hook support.

    Services can override hook methods to add custom logic:
    - Send emails
    - Trigger webhooks
    - Log events
    - Update analytics
    - Enforce business rules
    """
    pass
```

### Hook Pattern Example

```python
# 1. Core service defines hooks
class UserService(BaseService):
    async def create_user(self, email: str, password: str) -> UserModel:
        # Create user in database
        user = UserModel(email=email, hashed_password=hash_password(password))
        await user.save()

        # Call hook (does nothing by default)
        await self.on_after_register(user)

        return user

    async def on_after_register(self, user: UserModel, request=None):
        """Override this to add custom logic."""
        pass  # Default: do nothing

# 2. You extend the service and override hooks
class MyUserService(UserService):
    async def on_after_register(self, user: UserModel, request=None):
        # Send welcome email
        await email_service.send_welcome(user.email)

        # Track in analytics
        await analytics.track("user_registered", {
            "user_id": str(user.id),
            "email": user.email
        })

        # Trigger webhook
        await webhook.post("https://api.example.com/webhooks/new_user", {
            "event": "user.registered",
            "user": {"id": str(user.id), "email": user.email}
        })
```

### Hook Characteristics

1. **Non-blocking**: Hooks are called with `await` but don't block the main operation
2. **Optional**: Default implementation does nothing
3. **Exception-safe**: Hook exceptions shouldn't crash the operation (use try/except in hooks)
4. **Contextual**: Hooks receive the relevant objects and optional `Request`

### Common Hook Use Cases

**Send Notifications:**
```python
async def on_after_register(self, user, request=None):
    await email_service.send_welcome(user.email)
```

**Track Analytics:**
```python
async def on_after_login(self, user, request=None, response=None):
    await analytics.track("login", user.id, {
        "ip": request.client.host if request else None
    })
```

**Audit Logging:**
```python
async def on_after_delete(self, user, request=None):
    await audit_log.log("user_deleted", {
        "user_id": str(user.id),
        "email": user.email,
        "deleted_by": request.state.user.id if request else None
    })
```

**Business Rules:**
```python
async def on_before_delete(self, user, request=None):
    # Prevent deletion of important users
    if user.is_superuser:
        raise ValueError("Cannot delete superuser")

    # Check for dependencies
    if await has_active_subscriptions(user.id):
        raise ValueError("User has active subscriptions")
```

**Cache Invalidation:**
```python
async def on_after_role_assigned(self, user, role, entity_id=None, request=None):
    # Invalidate permission cache
    await cache_service.invalidate_user_permissions(user.id)
```

---

## See Also

- **[11. Core Components](11-Core-Components.md** - OutlabsAuth unified class
- **[12. Data Models](12-Data-Models.md)** - Database schema and models
- **[14. FastAPI Integration](14-FastAPI-Integration.md)** - Router patterns and dependencies
- **[40. Authorization Overview](40-Authorization-Overview.md)** - Permission checking patterns
- **[42. Entity Hierarchy](42-Entity-Hierarchy.md)** - Organizational structure
- **[43. Tree Permissions](43-Tree-Permissions.md)** - Hierarchical permission inheritance

---

**Last Updated:** 2025-01-23
**Applies To:** OutlabsAuth v1.0+
**Related Design Decisions:** DD-040 (Lifecycle Hooks), DD-036 (Closure Table), DD-033 (Redis Counters)
