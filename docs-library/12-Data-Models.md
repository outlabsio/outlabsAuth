# Data Models

> **Handbook · Reference** — schema lookup for implementers.  
> Part of the [OutlabsAuth Handbook](./README.md). Not a getting-started guide.

## Overview

OutlabsAuth uses **PostgreSQL** with **SQLAlchemy/SQLModel** (async). Common
fields (`id`, timestamps) come from `outlabs_auth.database.base.BaseModel`.

This page is a **schema reference**, not a tutorial — start with
[Getting Started](./01-Getting-Started.md) if you are wiring an app.

**Database**: PostgreSQL 14+  
**ORM**: SQLAlchemy async + SQLModel (driver: asyncpg)

Not every table is created for every configuration -
`outlabs_auth/database/registry.py` selects the table set from the feature
flags (for example `entity_*` tables only when `enable_entity_hierarchy=True`,
otherwise `user_role_memberships`).

---

## Model Hierarchy

```
SQLModel
└─ BaseModel  (id, created_at, updated_at — not a table itself)
   ├─ User
   ├─ Role
   ├─ RolePermission (junction)
   ├─ RoleCondition
   ├─ RoleEntityTypePermission
   ├─ RoleDefinitionHistory
   ├─ Permission
   ├─ PermissionTag
   ├─ PermissionTagLink (junction)
   ├─ PermissionCondition
   ├─ PermissionDefinitionHistory
   ├─ ConditionGroup
   ├─ RefreshToken
   ├─ AuthChallenge
   ├─ APIKey
   ├─ APIKeyScope (junction)
   ├─ APIKeyIPWhitelist
   ├─ APIKeyUsageSyncBatch
   ├─ SocialAccount
   ├─ OAuthState
   ├─ IntegrationPrincipal
   ├─ IntegrationPrincipalRole (junction)
   ├─ UserRoleMembership (SimpleRBAC)
   ├─ UserAuditEvent
   ├─ ActivityMetric
   ├─ UserActivity
   ├─ LoginHistory
   ├─ SystemConfig
   ├─ Entity (EnterpriseRBAC)
   ├─ EntityMembership (EnterpriseRBAC)
   ├─ EntityMembershipRole (junction)
   ├─ EntityMembershipHistory (EnterpriseRBAC)
   └─ EntityClosure (EnterpriseRBAC)
```

---

## Base Model

`BaseModel` (`outlabs_auth/database/base.py`) is the common base for all
tables. It is **not** a table itself - child classes must set `table=True`.

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class BaseModel(SQLModel):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_type=PG_UUID(as_uuid=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=TIMESTAMP(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=TIMESTAMP(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )
```

Table models then inherit it:

```python
class User(BaseModel, table=True):
    __tablename__ = "users"
    ...
```

**Common Fields**:
- `id` - UUID v4 primary key (auto-generated)
- `created_at` - Timestamp when record was created (UTC, `server_default now()`)
- `updated_at` - Timestamp when record was last modified (UTC, `onupdate now()`)

---

## Core Models

### 1. User

**User accounts and authentication.** Table: `users`

```python
class UserStatus(str, Enum):
    """User account status controlling authentication access.

    See DD-048 (docs-library/48-User-Status-System.md) for detailed semantics.
    """
    ACTIVE = "active"        # Can authenticate ✅
    SUSPENDED = "suspended"  # Temporary block (with optional expiry) ❌
    BANNED = "banned"        # Permanent block ❌
    DELETED = "deleted"      # Soft-deleted (with deletion timestamp) ❌

class User(BaseModel, table=True):
    __tablename__ = "users"

    # Authentication
    email: EmailStr  # Unique (uq_users_email)
    hashed_password: Optional[str]  # None for OAuth-only users
    auth_methods: List[str] = ["PASSWORD"]  # e.g., ["PASSWORD", "GOOGLE", "GITHUB"]

    # Basic Identity (optional - see "Extending User" below for full profiles)
    first_name: Optional[str] = None  # Optional display name
    last_name: Optional[str] = None   # Optional display name

    # Organization Binding (EnterpriseRBAC) - See DD-050
    root_entity_id: Optional[UUID] = None  # Root entity this user belongs to
    # NULL for superusers or unassigned users
    # Set automatically on first membership assignment
    # Users can only belong to ONE root entity (organization)

    # Profile
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    locale: Optional[str] = None        # e.g. "en-US"
    timezone: Optional[str] = None      # e.g. "America/New_York"

    # Status
    status: UserStatus = UserStatus.ACTIVE
    suspended_until: Optional[datetime] = None  # Auto-expiry for SUSPENDED status
    deleted_at: Optional[datetime] = None       # Timestamp for DELETED status
    is_superuser: bool = False
    email_verified: bool = False
    phone_verified: bool = False

    # Security & Activity Tracking
    last_login: Optional[datetime] = None          # Only on email/password or OAuth login
    last_activity: Optional[datetime] = None       # Any authenticated action (DD-049)
    last_password_change: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None

    # Password Reset
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None

    # Email Verification
    email_verification_token: Optional[str] = None
    email_verification_expires: Optional[datetime] = None

    # Invitation
    invite_token: Optional[str] = None          # SHA-256 hash of the invite token
    invite_token_expires: Optional[datetime] = None
    invited_by_id: Optional[UUID] = None        # FK -> users.id
```

**Relationships**: `refresh_tokens`, `api_keys`, `social_accounts`,
`role_memberships`, `created_integration_principals`.

**Constraints & Indexes** (`__table_args__`):
```python
UniqueConstraint("email", name="uq_users_email")   # also serves as the email index
Index("ix_users_status", "status")                 # filter by status
Index("ix_users_root_entity_id", "root_entity_id") # organization scoping

# Partial indexes — reset-password / accept-invite are unauthenticated
# endpoints that look tokens up by value.
Index("ix_users_password_reset_token", "password_reset_token",
      postgresql_where=text("password_reset_token IS NOT NULL"))
Index("ix_users_invite_token", "invite_token",
      postgresql_where=text("invite_token IS NOT NULL"))
```

**Key Methods**:
```python
@property
def full_name(self) -> str:
    """Get user's full name.

    Returns first_name + last_name if available, otherwise email username.
    """
    if self.first_name or self.last_name:
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts)
    return self.email.split("@")[0]

@property
def is_locked(self) -> bool:
    """Check if account is locked due to failed login attempts."""
    if not self.locked_until:
        return False
    return datetime.now(timezone.utc) < self.locked_until

def can_authenticate(self) -> bool:
    """Check if user can authenticate.

    Returns True only if:
    - status == ACTIVE (not suspended, banned, or deleted)
    - account is not locked (locked_until expired or None)

    See DD-048 for user status semantics.
    """
    return (
        self.status == UserStatus.ACTIVE
        and not self.is_locked
    )
```

**Extending User**:

`User` already carries the common profile fields - `first_name`, `last_name`,
`avatar_url`, `phone`, `locale`, `timezone`. Check that list before adding
anything.

For business-specific data beyond those fields, the pattern used by the
library's own example (`examples/enterprise_rbac/models.py`) is to declare a
**separate application table in your own app** that references the user by id:

```python
from uuid import UUID
from sqlmodel import Field, SQLModel

class Lead(SQLModel, table=True):
    __tablename__ = "leads"

    assigned_to: Optional[UUID] = Field(
        default=None,
        sa_type=PG_UUID(as_uuid=True),
        description="Agent user_id (optional)",
    )
```

Note that the reference is a **plain `UUID` column with no `ForeignKey`** - the
app's tables and the `outlabs_auth` tables are migrated independently, so the
example deliberately keeps them decoupled and resolves the user in application
code.

There is **no supported subclass-extension hook** on `User` - the library
constructs and queries `User` directly, so a subclass of it will not be used by
the library's own services.

**Example**:
```python
# Create active user
user = User(
    email="john@example.com",
    hashed_password=hashed_pw,
    first_name="John",
    last_name="Doe",
    status=UserStatus.ACTIVE,
    email_verified=True,
)
session.add(user)
await session.commit()

# Suspend user temporarily (with auto-expiry)
user.status = UserStatus.SUSPENDED
user.suspended_until = datetime.now(timezone.utc) + timedelta(days=7)
await session.commit()

# Soft delete user
user.status = UserStatus.DELETED
user.deleted_at = datetime.now(timezone.utc)
await session.commit()
```

---

### 2. Role

**Roles with permissions and optional ABAC conditions.** Table: `roles`

Unlike the other models here, a role's permissions and conditions are **not**
columns - they are normalized into their own tables:

| Related table | Model | Holds |
|---------------|-------|-------|
| `role_permissions` | `RolePermission` | Role -> Permission junction |
| `role_conditions` | `RoleCondition` | ABAC conditions on the role |
| `role_entity_type_permissions` | `RoleEntityTypePermission` | Context-aware (per entity type) permissions |
| `condition_groups` | `ConditionGroup` | AND/OR grouping of conditions |
| `role_definition_history` | `RoleDefinitionHistory` | Definition change history |

```python
class Role(BaseModel, table=True):
    __tablename__ = "roles"

    # Identity
    name: str                        # System name (lowercase, e.g. "admin")
    display_name: str                # Human-readable name
    description: Optional[str] = None

    # Root Entity Scope (EnterpriseRBAC) - See DD-050
    root_entity_id: Optional[UUID] = None  # FK -> entities.id (SET NULL)
    # NULL = system-wide role available everywhere

    # Configuration
    is_system_role: bool = False     # System roles cannot be modified/deleted
    is_global: bool = False          # Can be assigned anywhere in hierarchy
    status: DefinitionStatus = DefinitionStatus.ACTIVE

    # Entity-Local Role Configuration (DD-053)
    scope_entity_id: Optional[UUID] = None  # FK -> entities.id (CASCADE)
    scope: RoleScope = RoleScope.HIERARCHY  # entity_only | hierarchy
    is_auto_assigned: bool = False   # Auto-assigned to all members within scope
    assignable_at_types: List[str] = []  # Empty = no entity-type restriction

    # Relationships
    permissions: List["Permission"]  # via role_permissions junction
    conditions: List["RoleCondition"]
    entity_type_permissions: List["RoleEntityTypePermission"]
```

**Indexes**:
```python
Index("ix_roles_name", "name")
Index("ix_roles_is_global", "is_global")
Index("ix_roles_status", "status")
Index("ix_roles_root_entity_id", "root_entity_id")
Index("ix_roles_scope_entity_id", "scope_entity_id")
Index("ix_roles_is_auto_assigned", "is_auto_assigned")
```

Note: `name` is **indexed but not unique** at the table level - the same role
name can exist in different root entities.

**Key Methods**:
```python
def get_permission_names(self) -> List[str]:
    """Get list of permission names assigned to this role."""

def has_conditions(self) -> bool:
    """Check if role has ABAC conditions."""

def is_entity_local(self) -> bool:
    """Check if this is an entity-local role (has scope_entity_id)."""

def is_hierarchy_scoped(self) -> bool:
    """Check if role permissions cascade to descendants."""

def is_entity_only_scoped(self) -> bool:
    """Check if role permissions are limited to the scope entity only."""

def can_grant_permissions(self) -> bool:
    """Only active role definitions grant access."""
```

**Example**:
```python
# Simple role
editor = Role(
    name="editor",
    display_name="Editor",
)
session.add(editor)
await session.flush()  # populate editor.id

# Permissions attach via the role_permissions junction table
session.add(RolePermission(role_id=editor.id, permission_id=post_create.id))
session.add(RolePermission(role_id=editor.id, permission_id=post_update.id))

# Context-aware permissions attach per entity type
session.add(
    RoleEntityTypePermission(
        role_id=manager.id,
        entity_type="department",
        permission_id=budget_approve.id,
    )
)

# ABAC conditions are rows in role_conditions
session.add(
    RoleCondition(
        role_id=budget_approver.id,
        attribute="resource.amount",
        operator=ConditionOperator.LESS_THAN,
        value="100000",
        value_type="int",
    )
)
await session.commit()
```

Note that `RoleCondition.value` is a **string column** with a companion
`value_type` discriminator - values are serialized, not stored natively typed.

---

### 3. Permission

**Permission definitions.** Table: `permissions`

```python
class Permission(BaseModel, table=True):
    __tablename__ = "permissions"

    name: str                        # e.g. "post:create"
    display_name: str
    description: Optional[str] = None

    resource: Optional[str] = None   # e.g. "post"
    action: Optional[str] = None     # e.g. "create"
    scope: Optional[str] = None

    is_system: bool = False
    status: DefinitionStatus = DefinitionStatus.ACTIVE
    is_active: bool = True

    # Relationships
    tags: List["PermissionTag"]              # via permission_tag_links
    conditions: List["PermissionCondition"]
```

**Constraints & Indexes**:
```python
UniqueConstraint("name", name="uq_permissions_name")
Index("ix_permissions_resource", "resource")
Index("ix_permissions_is_system", "is_system")
Index("ix_permissions_status", "status")
Index("ix_permissions_is_active", "is_active")
```

**Related tables**: `permission_tags` / `permission_tag_links` (tagging),
`permission_conditions` (ABAC conditions on the permission itself), and
`permission_definition_history` (definition change history).

**Note**: `Permission` rows are real - roles reference them by id through the
`role_permissions` junction, not by string.

---

### 4. RefreshToken

**Refresh tokens for JWT authentication.**

**Note**: Refresh token JWTs now include a `jti` (JWT ID) claim to ensure uniqueness and prevent token collisions when multiple sessions are created simultaneously. This JTI is not stored in the database - only the hash of the full JWT is stored.

```python
class RefreshToken(BaseModel, table=True):
    __tablename__ = "refresh_tokens"

    # User
    user_id: UUID                    # FK -> users.id (CASCADE)

    # Token (hashed)
    token_hash: str                  # SHA-256 hash of the token (never the plain token)

    # Rotation family
    family_id: UUID                  # Family used to detect replay after rotation
    replaced_by_token_id: Optional[UUID] = None  # FK -> refresh_tokens.id (SET NULL)

    # Expiration
    expires_at: datetime

    # Revocation
    is_revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None  # logout, security, password_change

    # Device/Session info
    device_name: Optional[str] = None  # e.g. "iPhone 14 Pro"
    device_fingerprint: Optional[str] = None  # Hashed device id for session binding
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Usage tracking
    last_used_at: Optional[datetime] = None
    usage_count: int = 0

    # Relationship
    user: "User"
```

**Rotation families**: on refresh, the old token is marked revoked and points at
its replacement via `replaced_by_token_id`, while both share a `family_id`.
Re-use of an already-rotated token is therefore detectable as replay across the
whole family.

**Constraints & Indexes**:
```python
UniqueConstraint("token_hash", name="uq_refresh_tokens_hash")
Index("ix_refresh_tokens_user_id", "user_id")
Index("ix_refresh_tokens_expires_at", "expires_at")   # cleanup expired tokens
Index("ix_refresh_tokens_is_revoked", "is_revoked")
Index("ix_refresh_tokens_device", "device_fingerprint")
Index("ix_refresh_tokens_family_id", "family_id")
```

**Key Methods**:
```python
def is_valid(self) -> bool:
    """Check if token is valid (not revoked and not expired)."""

def is_expired(self) -> bool:
    """Check if token has expired."""

def revoke(self, reason: str = "manual") -> None:
    """Mark token as revoked (sets revoked_at and revoked_reason)."""

def record_usage(self) -> None:
    """Record token usage (bumps last_used_at and usage_count)."""
```

**Example**:
```python
refresh_token = RefreshToken(
    user_id=user.id,
    token_hash=hashed_token,
    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    device_name="Chrome on MacOS",
    ip_address="192.168.1.100",
)
session.add(refresh_token)
await session.commit()
```

---

### 5. APIKey

**API keys for programmatic authentication.** Table: `api_keys`

Scopes and IP whitelist entries are **child tables**, not array columns:

| Related table | Model | Holds |
|---------------|-------|-------|
| `api_key_scopes` | `APIKeyScope` | One row per granted scope |
| `api_key_ip_whitelist` | `APIKeyIPWhitelist` | One row per allowed IP |
| `api_key_usage_sync_batches` | `APIKeyUsageSyncBatch` | Redis -> Postgres usage-sync bookkeeping |

```python
class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"   # Temporarily disabled
    REVOKED = "revoked"       # Permanently disabled
    EXPIRED = "expired"       # Past expiration date

class APIKeyKind(str, Enum):
    PERSONAL = "personal"
    SYSTEM_INTEGRATION = "system_integration"

class APIKey(BaseModel, table=True):
    __tablename__ = "api_keys"

    # Key information
    name: str
    description: Optional[str] = None
    prefix: str                      # Unique; e.g. "sk_live_abc1"
    key_hash: str                    # Hash of the full key

    # Ownership — exactly one of these two
    owner_id: Optional[UUID] = None                   # FK -> users.id
    integration_principal_id: Optional[UUID] = None   # FK -> integration_principals.id
    key_kind: APIKeyKind = APIKeyKind.PERSONAL

    # Status
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: int = 0             # Synced from Redis

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None

    # Entity scoping (EnterpriseRBAC)
    entity_id: Optional[UUID] = None
    inherit_from_tree: bool = ...
```

**Constraints & Indexes**:
```python
UniqueConstraint("prefix", name="uq_api_keys_prefix")
Index("ix_api_keys_owner_id", "owner_id")
Index("ix_api_keys_integration_principal_id", "integration_principal_id")
Index("ix_api_keys_key_kind", "key_kind")
Index("ix_api_keys_status_expires_at", "status", "expires_at")  # cleanup/expiry sweeps
```

**Key Methods**:
```python
@staticmethod
def generate_key(prefix_type: str = "sk_live") -> tuple[str, str]:
    """Generate new API key with prefix."""

@staticmethod
def hash_key(full_key: str) -> str:
    """Hash API key for storage."""

@staticmethod
def hash_key_bytes(full_key: str) -> bytes:
    """Hash API key for storage, as raw bytes."""

def is_active(self) -> bool:
    """Check if key is active and not expired."""

def record_usage(self) -> None:
    """Bump last_used_at and usage_count."""

def revoke(self) -> None: ...
def suspend(self) -> None: ...
def reactivate(self) -> None: ...

@property
def owner_type(self) -> str: ...

@property
def resolved_owner_id(self) -> Optional[UUID]: ...
```

Scope and IP checks are **not** methods on the model - they are resolved from
the `api_key_scopes` / `api_key_ip_whitelist` tables by the API key service.

**Example**:
```python
# Generate key
full_key, prefix = APIKey.generate_key("sk_live")
# full_key: "sk_live_abc123def456..."
# prefix: "sk_live_abc1"

# Create API key
api_key = APIKey(
    name="Production API",
    prefix=prefix,
    key_hash=APIKey.hash_key(full_key),
    owner_id=user.id,
    rate_limit_per_minute=100,
)
session.add(api_key)
await session.flush()

# Scopes are separate rows
session.add(APIKeyScope(api_key_id=api_key.id, scope="user:read"))
session.add(APIKeyScope(api_key_id=api_key.id, scope="entity:read"))
await session.commit()

# Return full_key to user (only shown once!)
```

**See**: [[23-API-Keys]] for complete guide.

---

### 6. SocialAccount

**OAuth/social login accounts.**

```python
class SocialAccount(BaseModel, table=True):
    __tablename__ = "social_accounts"

    # User relationship
    user_id: UUID                    # FK -> users.id

    # Provider info
    provider: str                    # "google", "github", "facebook", "apple"
    provider_user_id: str
    provider_email: Optional[str] = None
    provider_email_verified: bool = False
    provider_username: Optional[str] = None

    # OAuth tokens (stored only when store_oauth_provider_tokens is enabled)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

    # Cached profile
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    profile_url: Optional[str] = None

    # Metadata
    last_login_at: Optional[datetime] = None
    token_refreshed_at: Optional[datetime] = None

    # Relationship
    user: "User"
```

**Constraints & Indexes**:
```python
UniqueConstraint("provider", "provider_user_id", name="uq_social_provider_user")
Index("ix_social_accounts_user_id", "user_id")
Index("ix_social_accounts_provider", "provider")
```

**Example**:
```python
social = SocialAccount(
    user_id=user.id,
    provider="google",
    provider_user_id="107353926327...",
    provider_email="john@gmail.com",
    provider_email_verified=True,
    display_name="John Doe",
    avatar_url="https://lh3.googleusercontent.com/...",
)
session.add(social)
await session.commit()
```

**See**: [[33-OAuth-Account-Linking]] for account linking.

---

## EnterpriseRBAC Models

### 7. Entity

**Organizational entities and access groups.** Table: `entities`

```python
class EntityClass(str, Enum):
    STRUCTURAL = "structural"      # Organizational units (company, department, team)
    ACCESS_GROUP = "access_group"  # Permission groupings (project, resource pool)

class Entity(BaseModel, table=True):
    __tablename__ = "entities"

    # Identity
    name: str                        # System name
    display_name: str                # User-friendly name
    slug: str                        # URL-friendly, unique
    description: Optional[str] = None

    # Classification
    entity_class: EntityClass
    entity_type: str                 # "company", "department", "team", etc.

    # Hierarchy
    parent_id: Optional[UUID] = None  # FK -> entities.id
    depth: int = ...                  # Materialized depth in the tree
    path: Optional[str] = None        # Materialized path

    # Lifecycle
    status: str = "active"           # active, inactive, archived
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Configuration (per-entity child type customization - DD-051)
    max_members: Optional[int] = None
    max_depth: Optional[int] = None
    allowed_child_types: List[str] = []
    # If empty, uses system default child types from SystemConfig

    allowed_child_classes: List[str] = []
    # Entity classes allowed as children (e.g., ["structural", "access_group"])

    # Child naming guidance
    child_name_pattern: Optional[str] = None
    child_display_name_pattern: Optional[str] = None
    child_slug_pattern: Optional[str] = None
    child_naming_guidance: Optional[str] = None

    # Relationships
    parent: Optional["Entity"]
    children: List["Entity"]
    memberships: List["EntityMembership"]
    scoped_roles: List["Role"]
    users: List["User"]
```

Note the hierarchy link is a plain `parent_id` FK plus materialized `depth` /
`path` columns; ancestor-descendant queries go through the `entity_closure`
table (section 9).

`Entity.metadata` is reserved for a future persisted feature. It is not part of the live SQL entity model or API contract today.

**Child Type Configuration (DD-051)**:
Root entities can define their own allowed child types, which override the system defaults:

```python
# Root entity with custom child types
brokerage = Entity(
    name="acme_realty",
    display_name="ACME Realty",
    entity_type="brokerage",
    parent_id=None,  # Root entity
    allowed_child_types=["branch", "team", "agent"],  # Custom for this brokerage
)

# Child entities under this root can only use these types
branch = Entity(
    name="downtown_branch",
    parent_id=brokerage.id,
    entity_type="branch",  # Must be in parent's allowed_child_types
)
```

If `allowed_child_types` is empty on the root entity, the system defaults from SystemConfig are used.

**Constraints & Indexes**:
```python
UniqueConstraint("slug", name="uq_entities_slug")
Index("ix_entities_name", "name")
Index("ix_entities_class_type", "entity_class", "entity_type")
Index("ix_entities_parent_id", "parent_id")
Index("ix_entities_status", "status")
```

**Key Methods**:
```python
@property
def is_structural(self) -> bool:
    """Check if entity is structural."""

@property
def is_access_group(self) -> bool:
    """Check if entity is an access group."""

@property
def is_root(self) -> bool:
    """Check if entity has no parent."""

def is_active(self) -> bool:
    """Check if entity is currently active."""

def update_path(self, parent_path: Optional[str] = None) -> None:
    """Recompute the materialized path from the parent's path."""
```

Ancestor checks are not a method on `Entity` - query `entity_closure` instead
(section 9).

**Example**:
```python
company = Entity(
    name="acme_corp",
    display_name="Acme Corp",
    slug="acme-corp",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company",
    status="active",
)
session.add(company)
await session.flush()

engineering = Entity(
    name="engineering",
    display_name="Engineering",
    slug="acme-corp-engineering",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=company.id,
)
session.add(engineering)
await session.commit()
```

**See**: [[50-Entity-System]] for entity system overview.

---

### 8. EntityMembership

**User memberships in entities with roles.**

Roles are attached through the `entity_membership_roles` junction table
(`EntityMembershipRole`), not an embedded list.

```python
from outlabs_auth.models.sql.enums import MembershipStatus

class EntityMembership(BaseModel, table=True):
    __tablename__ = "entity_memberships"

    # Relationships
    user_id: UUID                    # FK -> users.id
    entity_id: UUID                  # FK -> entities.id

    # Membership metadata
    joined_at: datetime
    joined_by_id: Optional[UUID] = None   # FK -> users.id

    # Time-based membership
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status
    status: MembershipStatus = MembershipStatus.ACTIVE

    # Revocation metadata (when status=REVOKED)
    revoked_at: Optional[datetime] = None
    revoked_by_id: Optional[UUID] = None  # FK -> users.id
    revocation_reason: Optional[str] = None

    # Relationships
    user: "User"
    entity: "Entity"
    roles: List["Role"]              # via entity_membership_roles
```

**Constraints & Indexes**:
```python
UniqueConstraint("user_id", "entity_id", name="uq_entity_membership")
Index("ix_em_entity_id", "entity_id")
Index("ix_em_user_status", "user_id", "status")
Index("ix_em_status", "status")
Index("ix_em_valid_until", "valid_until")
```

Membership changes are also recorded in `entity_membership_history`
(`EntityMembershipHistory`).

**Key Methods**:
```python
def is_currently_valid(self) -> bool:
    """Check if membership is currently valid (time-based)."""

def can_grant_permissions(self) -> bool:
    """Check if membership can currently grant permissions (status + time)."""

def get_role_names(self) -> List[str]:
    """Get list of role names attached to this membership."""
```

**Example**:
```python
# Create active membership
membership = EntityMembership(
    user_id=john.id,
    entity_id=engineering_dept.id,
    status=MembershipStatus.ACTIVE,
    joined_by_id=admin_user.id,
)
session.add(membership)
await session.flush()

# Attach roles via the junction table
session.add(EntityMembershipRole(membership_id=membership.id, role_id=manager_role.id))
session.add(EntityMembershipRole(membership_id=membership.id, role_id=developer_role.id))
await session.commit()

# Revoke membership (soft delete)
membership.status = MembershipStatus.REVOKED
membership.revoked_at = datetime.now(timezone.utc)
membership.revoked_by_id = admin_user.id
await session.commit()
```

**See**: [[54-Entity-Memberships]] for membership management.

---

### 9. EntityClosure

**Closure table for O(1) ancestor/descendant queries.** Table: `entity_closure`

```python
class EntityClosure(BaseModel, table=True):
    __tablename__ = "entity_closure"

    ancestor_id: UUID     # FK -> entities.id (CASCADE)
    descendant_id: UUID   # FK -> entities.id (CASCADE)

    # Depth (0 = self, 1 = direct child, 2 = grandchild, etc.)
    depth: int
```

**Constraints & Indexes**:
```python
UniqueConstraint("ancestor_id", "descendant_id", name="uq_entity_closure")
Index("ix_closure_ancestor_depth", "ancestor_id", "depth")     # find descendants
Index("ix_closure_descendant_depth", "descendant_id", "depth") # find ancestors
```

The composite `(id, depth)` indexes cover single-column lookups via their
leading prefix, so no redundant single-column indexes exist - closure inserts
are O(depth x subtree) rows per entity create/move, and each extra index would
be paid on every one.

**Example**:
```python
# For hierarchy: Company → Dept → Team
# Closure records:
[
    (company_id, company_id, 0),  # Self
    (company_id, dept_id, 1),     # Direct child
    (company_id, team_id, 2),     # Grandchild
    (dept_id, dept_id, 0),        # Self
    (dept_id, team_id, 1),        # Direct child
    (team_id, team_id, 0)         # Self
]
```

**Query Examples**:
```python
from sqlmodel import select

# Get all ancestors (single indexed lookup)
result = await session.execute(
    select(EntityClosure)
    .where(EntityClosure.descendant_id == team_id, EntityClosure.depth > 0)
    .order_by(EntityClosure.depth)
)
ancestors = result.scalars().all()

# Get all descendants
result = await session.execute(
    select(EntityClosure)
    .where(EntityClosure.ancestor_id == company_id, EntityClosure.depth > 0)
)
descendants = result.scalars().all()

# Check if ancestor
result = await session.execute(
    select(EntityClosure).where(
        EntityClosure.ancestor_id == company_id,
        EntityClosure.descendant_id == team_id,
    )
)
is_ancestor = result.scalar_one_or_none() is not None
```

**See**: [[53-Closure-Table]] for closure table pattern.

---

### 10. SystemConfigModel

**System configuration key-value store (EnterpriseRBAC).**

```python
class SystemConfig(SQLModel, table=True):
    """System-wide configuration stored as key-value pairs."""
    __tablename__ = "system_config"

    # Primary key is the config key (e.g., "entity_types")
    key: str = Field(sa_column=Column(String(100), primary_key=True))
    
    # JSON-encoded value
    value: str = Field(sa_column=Column(Text, nullable=False))
    
    # Optional description for documentation
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Audit fields
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    updated_by_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    )
```

**Configuration Keys**:
```python
class ConfigKeys:
    ENTITY_TYPES = "entity_types"  # Allowed root/child entity types
    FEATURE_FLAGS = "feature_flags"  # System feature flags (future)
```

**Default Entity Type Configuration**:
```python
DEFAULT_ENTITY_TYPE_CONFIG = {
    "allowed_root_types": ["organization"],
    "default_child_types": {
        "structural": ["department", "team", "branch"],
        "access_group": ["permission_group", "admin_group"],
    },
}
```

**Example**:
```python
# Get entity type configuration
config = await config_service.get_entity_type_config(session)
# Returns EntityTypeConfig with allowed_root_types and default_child_types

# Update entity type configuration (superuser only)
new_config = EntityTypeConfig(
    allowed_root_types=["brokerage", "solo_agent", "internal_team"],
    default_child_types=DefaultChildTypes(
        structural=["branch", "team", "agent"],
        access_group=["permission_group"],
    )
)
await config_service.set_entity_type_config(session, new_config, updated_by_id=user.id)
```

**API Endpoints**:
- `GET /v1/config/entity-types` - Get current configuration (public)
- `PUT /v1/config/entity-types` - Update configuration (superuser only)

**See**: DD-051 in `docs/DESIGN_DECISIONS.md` for the full design rationale.

---

## Critical: Entity Hierarchy Design (DD-050)

> **⚠️ IMPORTANT**: This section describes a critical architectural constraint that affects how you should structure your entity hierarchy in EnterpriseRBAC.

### The Constraint

**Users can only belong to ONE root entity (organization).** When a user is added as a member to any entity, they are automatically bound to that entity's root (the top-level entity with `parent_id = NULL`). Subsequent membership additions to entities under a *different* root will be **rejected**.

### Why This Matters

If you create multiple root entities expecting users to work across them, you will encounter errors like:

```
InvalidInputError: User belongs to a different organization
```

### Correct vs Incorrect Hierarchy Design

```
❌ WRONG - Multiple root entities (users can't belong to both):

├── ACME Realty (root, parent_id=NULL)
│   ├── Sales Team
│   └── Marketing Team
│
└── Keller Williams (root, parent_id=NULL)    
    ├── West Branch
    └── East Branch

# Problem: A user in ACME Realty CANNOT be added to Keller Williams
```

```
✅ CORRECT - Single root with child organizations:

└── Platform (root, parent_id=NULL)           # The "umbrella" entity
    │
    ├── ACME Realty (child organization)
    │   ├── Sales Team
    │   └── Marketing Team
    │
    ├── Keller Williams (child organization)
    │   ├── West Branch
    │   └── East Branch
    │
    └── Internal Teams (child organization)
        ├── Engineering
        └── Support

# Solution: All entities share the same root, so users can have
# memberships in ACME Realty AND Keller Williams AND Internal Teams
```

### When to Use Each Pattern

| Pattern | Use Case | Example |
|---------|----------|---------|
| **Multiple root entities** | Completely separate organizations that should NEVER share users | Different companies using the same SaaS platform as isolated tenants |
| **Single root with children** | Related organizations where users might need access to multiple | A platform with multiple clients, a franchise with multiple locations, a company with multiple divisions |

### Role Scoping with Root Entities

Roles can be scoped to specific root entities:

```python
# Global role - available everywhere
admin_role = await role_service.create_role(
    session=session,
    name="admin",
    display_name="Administrator",
    permission_names=["*"],
    is_global=True,  # Available in ALL organizations
    root_entity_id=None,
)

# Organization-scoped role - only available in ACME hierarchy
acme_agent_role = await role_service.create_role(
    session=session,
    name="agent",
    display_name="Real Estate Agent",
    permission_names=["listing:*", "client:read"],
    is_global=False,
    root_entity_id=acme_realty.id,  # Only for ACME Realty
)

# When assigning roles to memberships, only roles scoped to that
# organization (or global roles) will be accepted
```

### Querying Available Roles

Use the entity-scoped roles endpoint to get roles available for a specific entity:

```python
# API: Get roles available for a specific entity
GET /v1/roles/entity/{entity_id}

# Returns:
# - Global roles (is_global=True, root_entity_id=NULL)
# - Roles scoped to the entity's root organization
# - Entity-local roles available in the entity context
```

### Migration Considerations

If you have an existing deployment with multiple root entities and need to restructure:

1. Create a new umbrella root entity
2. Update existing "root" entities to have the new umbrella as their parent
3. Update closure table entries
4. Users' `root_entity_id` will need to be updated to the new umbrella

**See**: DD-050 in `docs/DESIGN_DECISIONS.md` for the full design rationale.

---

## ABAC Models

### 10. Condition

**Embedded model for ABAC conditions.**

```python
class ConditionOperator(str, Enum):
    # Equality
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"

    # Comparison
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"

    # Collection
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"

    # String
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # Regex

    # Existence
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"

    # Boolean
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"

    # Time
    BEFORE = "before"
    AFTER = "after"

class Condition(BaseModel):
    attribute: str  # e.g., "resource.department", "user.role"
    operator: ConditionOperator
    value: Optional[Union[str, int, float, bool, List[Any]]] = None
    description: Optional[str] = None
```

**Example**:
```python
# Department-based access
Condition(
    attribute="resource.department",
    operator=ConditionOperator.EQUALS,
    value="engineering"
)

# Budget threshold
Condition(
    attribute="resource.amount",
    operator=ConditionOperator.LESS_THAN,
    value=100000
)

# Business hours
Condition(
    attribute="time.hour",
    operator=ConditionOperator.GREATER_THAN_OR_EQUAL,
    value=9
)
```

**See**: [26 — ABAC](./26-ABAC.md) for the implementer guide.

---

### 11. ConditionGroup

**Group of conditions with logical operators.**

```python
class ConditionGroup(BaseModel):
    conditions: List[Condition] = Field(min_length=1)
    operator: str = "AND"  # "AND" or "OR"
    description: Optional[str] = None
```

**Example**:
```python
# Manager in engineering department
ConditionGroup(
    conditions=[
        Condition(attribute="user.role", operator="equals", value="manager"),
        Condition(attribute="user.department", operator="equals", value="engineering")
    ],
    operator="AND"
)

# Admin OR owner
ConditionGroup(
    conditions=[
        Condition(attribute="user.role", operator="equals", value="admin"),
        Condition(attribute="user.role", operator="equals", value="owner")
    ],
    operator="OR"
)
```

---

## OAuth Models

### 12. OAuthState

**OAuth state parameter storage (JWT-based alternative available).**

```python
class OAuthState(Document):
    state: str  # Unique state parameter
    provider: str  # "google", "github", etc.

    # PKCE
    code_verifier: Optional[str] = None
    code_challenge: Optional[str] = None

    # OIDC
    nonce: Optional[str] = None

    # Redirect
    redirect_uri: str

    # User context (for manual linking)
    user_id: Optional[UUID] = None

    # Security
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Expiration
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**Note**: OutlabsAuth uses **JWT-based state tokens** (DD-042) by default instead of database storage. This model is for reference.

---

### 13. ActivityMetric

**Historical snapshots for DAU/MAU/WAU/QAU tracking (DD-049).**

```python
class ActivityMetric(BaseModel, table=True):
    __tablename__ = "activity_metrics"

    metric_date: date       # Date for this metric
    metric_type: str        # "dau", "mau", "qau", "logins", "registrations", "api_calls"
    count: int = 0          # Count for this metric
    unique_users: int = 0   # Unique user count (for DAU/MAU)
    snapshot_at: datetime   # When this snapshot was taken
```

**Constraints & Indexes**:
```python
UniqueConstraint("metric_date", "metric_type", name="uq_activity_metric_date_type")
Index("ix_activity_metrics_date", "metric_date")
Index("ix_activity_metrics_type", "metric_type")
```

**Purpose**: Historical activity tracking for analytics and growth monitoring.

**Data Flow**:
1. Real-time tracking in **Redis Sets** (O(1) operations)
2. `ActivityTracker.sync_to_database()` upserts one row per
   `(metric_date, metric_type)` on the sync interval (default: 30 minutes)
3. Rows older than 90 days are deleted on each sync

The table stores **counts only** - there is no user-id column, so
cohort/retention analysis is not supported from this table.

**See**: `docs-library/49-Activity-Tracking.md` for complete implementation details.

---

### 14. UserActivity and LoginHistory

Two further activity tables are **declared and migrated, but no library service
writes to them** - `ActivityTracker` only writes `activity_metrics`. They are
available for host applications to populate.

```python
class UserActivity(BaseModel, table=True):
    __tablename__ = "user_activities"

    user_id: UUID           # FK -> users.id (CASCADE)
    activity_date: date
    login_count: int = 0
    api_call_count: int = 0
    action_count: int = 0
    first_activity_at: datetime
    last_activity_at: datetime

class LoginHistory(BaseModel, table=True):
    __tablename__ = "login_history"

    user_id: UUID           # FK -> users.id (CASCADE)
    login_at: datetime
    success: bool
    auth_method: str        # password, oauth, api_key, ...
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_fingerprint: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    failure_reason: Optional[str] = None
```

---

## Table Summary

`outlabs_auth/database/registry.py` is the authority for which tables a given
configuration creates. The base set is created for every configuration; the
hierarchy flag then switches the last group.

**Always created**:

| Table | Purpose |
|-------|---------|
| **users** | User accounts |
| **roles** | Role definitions |
| **permissions** | Permission registry |
| **refresh_tokens** | JWT refresh tokens |
| **integration_principals** | Non-human (system integration) principals |
| **api_keys** | API key authentication |
| **social_accounts** | OAuth accounts |
| **oauth_states** | OAuth state storage |
| **activity_metrics** | DAU/MAU tracking (DD-049) |
| **role_definition_history** | Role definition change history |
| **permission_definition_history** | Permission definition change history |
| **user_audit_events** | User audit log |

**With `enable_entity_hierarchy=True`** (EnterpriseRBAC):

| Table | Purpose |
|-------|---------|
| **entities** | Entity hierarchy |
| **entity_memberships** | User memberships |
| **entity_membership_roles** | Membership -> Role junction |
| **entity_closure** | Closure table |
| **entity_membership_history** | Membership change history |

**With `enable_entity_hierarchy=False`** (SimpleRBAC):

| Table | Purpose |
|-------|---------|
| **user_role_memberships** | Direct user -> role assignment |

Supporting tables backing the models above - `role_permissions`,
`role_conditions`, `role_entity_type_permissions`, `condition_groups`,
`permission_tags`, `permission_tag_links`, `permission_conditions`,
`api_key_scopes`, `api_key_ip_whitelist`, `api_key_usage_sync_batches`,
`integration_principal_roles`, `auth_challenges`, `system_config`,
`user_activities`, `login_history` - bring the full schema to **33 tables**.

---

## Indexes Summary

### Critical Indexes

**User**:
```python
UniqueConstraint("email", name="uq_users_email")   # UNIQUE — also the email index
Index("ix_users_status", "status")                 # Filter by status
```

**Role**:
```python
Index("ix_roles_name", "name")                     # Role name lookup (not unique)
```

**APIKey**:
```python
UniqueConstraint("prefix", name="uq_api_keys_prefix")  # UNIQUE — prefix lookup
Index("ix_api_keys_owner_id", "owner_id")              # User's API keys
```

**SocialAccount**:
```python
UniqueConstraint("provider", "provider_user_id", name="uq_social_provider_user")
Index("ix_social_accounts_user_id", "user_id")     # User's OAuth accounts
```

**Entity** (EnterpriseRBAC):
```python
UniqueConstraint("slug", name="uq_entities_slug")  # UNIQUE — slug lookup
Index("ix_entities_parent_id", "parent_id")        # Hierarchy queries
```

**EntityMembership** (EnterpriseRBAC):
```python
UniqueConstraint("user_id", "entity_id", name="uq_entity_membership")
Index("ix_em_entity_id", "entity_id")              # Entity members
Index("ix_em_user_status", "user_id", "status")    # User memberships by status
```

**EntityClosure** (EnterpriseRBAC):
```python
UniqueConstraint("ancestor_id", "descendant_id", name="uq_entity_closure")
Index("ix_closure_descendant_depth", "descendant_id", "depth")  # Ancestor queries
Index("ix_closure_ancestor_depth", "ancestor_id", "depth")      # Descendant queries
```

**Note on index hygiene**: several "obvious" single-column indexes are
deliberately absent - a `UniqueConstraint` already materializes a btree, and
composite indexes cover single-column lookups through their leading prefix. See
migration `20260611_0018_index_hygiene.py`.

---

## Database Initialization

### Setup with SQLAlchemy/SQLModel

```python
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from outlabs_auth import SimpleRBAC  # or EnterpriseRBAC

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mydb"
SECRET_KEY = "your-secret-key"

@asynccontextmanager
async def lifespan(app):
    # Initialize auth
    auth = SimpleRBAC(database_url=DATABASE_URL, secret_key=SECRET_KEY)
    await auth.initialize()

    # Create all tables
    async with auth.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield

    await auth.shutdown()
```

### Initialize with OutlabsAuth

```python
from outlabs_auth import SimpleRBAC  # or EnterpriseRBAC

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key="your-secret-key"
)
await auth.initialize()  # Creates engine and session factory
```

---

## Migration Considerations

### From Centralized API

If migrating from OutlabsAuth's old centralized API:

**Changed**:
- ❌ Removed `platform_id` (no multi-platform)
- ✅ Added optional `tenant_id` (for multi-tenant mode)
- ✅ Simplified entity hierarchy (single collection)

**Preserved**:
- ✅ User model structure
- ✅ Role/permission model
- ✅ Entity hierarchy structure
- ✅ Closure table pattern

### Schema Versioning

Schema changes are managed with **Alembic**. Migrations live in
`outlabs_auth/migrations/versions/` and are named `YYYYMMDD_NNNN_<slug>.py`
(for example `20260715_0020_add_refresh_token_families.py`).

Hosts can either run migrations themselves or pass `auto_migrate=True` to
`OutlabsAuth`.

---

## Best Practices

### 1. Use Indexes

```python
from sqlmodel import select

# ✅ Good - unique/indexed column
result = await session.execute(select(User).where(User.email == email))
user = result.scalar_one_or_none()

# ❌ Bad - unindexed column forces a sequential scan
result = await session.execute(select(User).where(User.timezone == tz))
```

### 2. Avoid N+1 Queries

```python
from sqlalchemy.orm import selectinload

# ❌ Bad - lazy-loads each user separately
result = await session.execute(select(EntityMembership))
for membership in result.scalars():
    user = membership.user  # N queries

# ✅ Good - eager-load the relationship in one round trip
result = await session.execute(
    select(EntityMembership).options(selectinload(EntityMembership.user))
)
```

### 3. Let the Model Validate

```python
# ✅ Good - SQLModel validates on construction
user = User(email="user@example.com", ...)
session.add(user)
await session.commit()

# ❌ Bad - skips validation
user = User.model_construct(email="invalid")
```

### 4. Use Transactions for Critical Operations

The session is the transaction - commit once, so a failure rolls back the whole
unit of work.

```python
# ✅ Good - entity + membership commit together or not at all
async with auth.get_session() as session:
    entity = Entity(...)
    session.add(entity)
    await session.flush()          # populate entity.id without committing

    session.add(EntityMembership(entity_id=entity.id, ...))
    await session.commit()         # single atomic commit
```

---

## Summary

**Core Models**:
- ✅ **User** - User accounts and authentication
- ✅ **Role** - Roles (permissions via the `role_permissions` junction)
- ✅ **Permission** - Permission definitions
- ✅ **RefreshToken** - JWT refresh tokens with rotation families
- ✅ **APIKey** - API key authentication
- ✅ **SocialAccount** - OAuth/social login accounts
- ✅ **IntegrationPrincipal** - Non-human principals

**EnterpriseRBAC Models**:
- ✅ **Entity** - Organizational entities
- ✅ **EntityMembership** - User memberships (roles via `entity_membership_roles`)
- ✅ **EntityClosure** - Closure table for ancestor/descendant queries

**ABAC Models**:
- ✅ **RoleCondition** / **PermissionCondition** - ABAC conditions (own tables)
- ✅ **ConditionGroup** - Condition groups with AND/OR

**Database**: PostgreSQL with SQLAlchemy/SQLModel (async, asyncpg)
**Tables**: 33 in the `outlabs_auth` schema; the created subset depends on the feature flags
**Migrations**: Alembic (`outlabs_auth/migrations/versions/`)

---

## Related

- [Getting Started](./01-Getting-Started.md)
- [Core Authorization Concepts](./13-Core-Authorization-Concepts.md)
- [JWT Tokens](./22-JWT-Tokens.md)
- [Entities](./51-Entities.md)
- [ABAC](./26-ABAC.md)
- Maintainer architecture: [`docs/LIBRARY_ARCHITECTURE.md`](../docs/LIBRARY_ARCHITECTURE.md)

### Further reading

- [PostgreSQL docs](https://www.postgresql.org/docs/)
- [SQLAlchemy](https://docs.sqlalchemy.org/) · [SQLModel](https://sqlmodel.tiangolo.com/)
- [Closure table pattern](https://www.slideshare.net/billkarwin/models-for-hierarchical-data) (hierarchy background)
