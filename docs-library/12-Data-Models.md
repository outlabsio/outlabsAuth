# 12. Data Models

> **Quick Reference**: Complete database schema reference for OutlabsAuth models including users, roles, entities, API keys, and OAuth accounts.

## Overview

OutlabsAuth uses **PostgreSQL** with **SQLAlchemy/SQLModel** (async) for data persistence. All models inherit from `SQLModel` with common fields and functionality.

**Database**: PostgreSQL 14+
**ORM**: SQLAlchemy async + SQLModel
**Tables**: 13 core tables

---

## Model Hierarchy

```
SQLModel (base)
├─ User
├─ Role
├─ Permission
├─ RolePermission (junction)
├─ RefreshToken
├─ APIKey
├─ APIKeyScope (junction)
├─ SocialAccount
├─ Entity (EnterpriseRBAC)
├─ EntityMembership (EnterpriseRBAC)
├─ EntityMembershipRole (junction)
├─ EntityClosure (EnterpriseRBAC)
└─ UserRoleMembership (SimpleRBAC)
```

---

## Base Model

**SQLModel base** for all tables with common patterns.

```python
from uuid import uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP
from sqlalchemy import Column

class User(SQLModel, table=True):
    """Example of SQLModel table definition."""

    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        sa_type=PG_UUID(as_uuid=True),
        primary_key=True
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
```

**Common Fields**:
- `id` - UUID primary key (auto-generated)
- `created_at` - Timestamp when record was created (with timezone)
- `updated_at` - Timestamp when record was last modified (with timezone)

---

## Core Models

### 1. UserModel

**User accounts and authentication.**

```python
class UserStatus(str, Enum):
    """User account status controlling authentication access.

    See DD-048 (docs-library/48-User-Status-System.md) for detailed semantics.
    """
    ACTIVE = "active"        # Can authenticate ✅
    SUSPENDED = "suspended"  # Temporary block (with optional expiry) ❌
    BANNED = "banned"        # Permanent block ❌
    DELETED = "deleted"      # Soft-deleted (with deletion timestamp) ❌

class UserModel(BaseDocument):
    # Authentication
    email: EmailStr  # Unique, indexed
    hashed_password: Optional[str]  # None for OAuth-only users
    auth_methods: List[str] = ["PASSWORD"]  # e.g., ["PASSWORD", "GOOGLE", "GITHUB"]

    # Basic Identity (optional - extend with Beanie Links for full profiles)
    first_name: Optional[str] = None  # Optional display name
    last_name: Optional[str] = None   # Optional display name

    # Status
    status: UserStatus = UserStatus.ACTIVE
    suspended_until: Optional[datetime] = None  # Auto-expiry for SUSPENDED status
    deleted_at: Optional[datetime] = None       # Timestamp for DELETED status
    is_superuser: bool = False
    email_verified: bool = False

    # Security & Activity Tracking
    last_login: Optional[datetime] = None          # Only on email/password or OAuth login
    last_activity: Optional[datetime] = None       # Any authenticated action (DD-049)
    last_password_change: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

**Indexes**:
```python
indexes = [
    [("email", 1)],           # Unique email lookup
    [("status", 1)],          # Filter by status
    [("tenant_id", 1)]        # Multi-tenant filtering
]
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

**Extending UserModel**:

The UserModel is intentionally minimal, containing only authentication and basic identity fields. For business-specific profile data (phone, avatar, preferences, job title, etc.), **use Beanie Links to separate profile collections**:

```python
from beanie import Link
from outlabs_auth.models.user import UserModel

class UserProfile(Document):
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: str = ""
    preferences: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "user_profiles"

class ExtendedUserModel(UserModel):
    """Extend UserModel with link to separate profile collection."""
    profile: Optional[Link[UserProfile]] = None

    class Settings:
        name = "users"  # Same collection as UserModel
```

See **`docs-library/96-Extending-UserModel.md`** for complete guide on extending with Beanie Links.

**Example**:
```python
# Create active user
user = UserModel(
    email="john@example.com",
    hashed_password=hashed_pw,
    first_name="John",
    last_name="Doe",
    status=UserStatus.ACTIVE,
    email_verified=True
)
await user.insert()

# Suspend user temporarily (with auto-expiry)
user.status = UserStatus.SUSPENDED
user.suspended_until = datetime.now(timezone.utc) + timedelta(days=7)
await user.save()

# Soft delete user
user.status = UserStatus.DELETED
user.deleted_at = datetime.now(timezone.utc)
await user.save()
```

---

### 2. RoleModel

**Roles with permissions and optional ABAC conditions.**

```python
class RoleModel(BaseDocument):
    # Identity
    name: str  # Unique role name, indexed
    display_name: str
    description: Optional[str] = None

    # Permissions
    permissions: List[str] = Field(default_factory=list)

    # Context-aware permissions (EnterpriseRBAC optional)
    entity_type_permissions: Optional[Dict[str, List[str]]] = None
    # Example: {"department": ["user:manage_tree"], "team": ["user:read"]}

    # Entity scope (EnterpriseRBAC)
    entity: Optional[Link["EntityModel"]] = None
    assignable_at_types: List[str] = Field(default_factory=list)

    # Role configuration
    is_system_role: bool = False  # Cannot be modified
    is_global: bool = False  # Can be assigned anywhere

    # ABAC conditions (optional)
    conditions: List[Condition] = Field(default_factory=list)
    condition_groups: Optional[List[ConditionGroup]] = None
```

**Indexes**:
```python
indexes = [
    [("name", 1)],         # Unique name lookup
    [("is_global", 1)],    # Filter global roles
    [("entity", 1)],       # Scoped roles
    [("tenant_id", 1)]     # Multi-tenant
]
```

**Key Methods**:
```python
def get_permissions_for_entity_type(entity_type: Optional[str]) -> List[str]:
    """Get context-aware permissions for entity type"""

def is_assignable_at_type(entity_type: str) -> bool:
    """Check if role can be assigned at entity type"""
```

**Example**:
```python
# Simple role
editor = RoleModel(
    name="editor",
    display_name="Editor",
    permissions=["post:create", "post:update", "post:read"]
)

# Context-aware role
manager = RoleModel(
    name="manager",
    display_name="Manager",
    permissions=["user:read"],
    entity_type_permissions={
        "department": ["user:manage_tree", "budget:approve"],
        "team": ["user:read", "user:update"]
    }
)

# ABAC role
budget_approver = RoleModel(
    name="budget_approver",
    display_name="Budget Approver",
    permissions=["budget:approve"],
    conditions=[
        Condition(
            attribute="resource.amount",
            operator="less_than",
            value=100000
        )
    ]
)
```

---

### 3. PermissionModel

**Permission definitions (optional collection).**

```python
class PermissionModel(BaseDocument):
    name: str  # e.g., "post:create"
    resource: str  # e.g., "post"
    action: str  # e.g., "create"
    description: Optional[str] = None
    category: Optional[str] = None  # e.g., "content", "admin"
```

**Indexes**:
```python
indexes = [
    [("name", 1)],  # Unique permission name
    [("resource", 1), ("action", 1)]  # Resource + action lookup
]
```

**Note**: Permissions are typically just strings (`"post:create"`). This model is optional for permission management UI.

---

### 4. RefreshTokenModel

**Refresh tokens for JWT authentication.**

**Note**: Refresh token JWTs now include a `jti` (JWT ID) claim to ensure uniqueness and prevent token collisions when multiple sessions are created simultaneously. This JTI is not stored in the database - only the hash of the full JWT is stored.

```python
class RefreshTokenModel(BaseDocument):
    # User relationship
    user: Link[UserModel]

    # Token (hashed)
    token_hash: str  # SHA256 hash of JWT (includes JTI for uniqueness)

    # Expiration
    expires_at: datetime

    # Revocation
    is_revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None  # "User logout", "Admin action", etc.

    # Device/Session info
    device_name: Optional[str] = None  # "iPhone 12", "Chrome on MacOS"
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Usage tracking
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
```

**Indexes**:
```python
indexes = [
    [("token_hash", 1)],   # Unique token lookup
    [("user", 1)],         # User's tokens
    [("expires_at", 1)],   # Cleanup expired tokens
    [("is_revoked", 1)],   # Filter revoked
    [("tenant_id", 1)]
]
```

**Key Methods**:
```python
def is_valid(self) -> bool:
    """Check if token is valid (not expired, not revoked)"""
```

**Example**:
```python
refresh_token = RefreshTokenModel(
    user=user,
    token_hash=hashed_token,
    expires_at=datetime.utcnow() + timedelta(days=30),
    device_name="Chrome on MacOS",
    ip_address="192.168.1.100"
)
```

---

### 5. APIKeyModel

**API keys for programmatic authentication.**

```python
class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"

class APIKeyModel(BaseDocument):
    # Key information
    name: str  # Human-readable name
    prefix: str  # First 12 chars (e.g., "sk_live_abc1")
    key_hash: str  # SHA256 hash of full key

    # Ownership
    owner: Link[UserModel]

    # Status
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    # Usage tracking (synced from Redis)
    usage_count: int = 0

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None

    # Permissions
    scopes: List[str] = Field(default_factory=list)
    entity_ids: Optional[List[str]] = None  # Restrict to entities

    # Security
    ip_whitelist: Optional[List[str]] = None

    # Metadata
    description: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
```

**Indexes**:
```python
indexes = [
    "prefix",        # Fast prefix lookup
    "owner",         # User's API keys
    "status",        # Active keys
    "expires_at"     # Cleanup expired
]
```

**Key Methods**:
```python
@staticmethod
def generate_key(prefix_type: str = "sk_live") -> tuple[str, str]:
    """Generate new API key with prefix"""

@staticmethod
def hash_key(full_key: str) -> str:
    """Hash API key for storage"""

def is_active(self) -> bool:
    """Check if key is active and not expired"""

def has_scope(scope: str) -> bool:
    """Check if key has permission"""

def has_entity_access(entity_id: str) -> bool:
    """Check if key can access entity"""

def check_ip(ip_address: str) -> bool:
    """Check if IP is whitelisted"""
```

**Example**:
```python
# Generate key
full_key, prefix = APIKeyModel.generate_key("sk_live")
# full_key: "sk_live_abc123def456..."
# prefix: "sk_live_abc1"

# Create API key
api_key = APIKeyModel(
    name="Production API",
    prefix=prefix,
    key_hash=APIKeyModel.hash_key(full_key),
    owner=user,
    scopes=["user:read", "entity:read"],
    rate_limit_per_minute=100
)
await api_key.insert()

# Return full_key to user (only shown once!)
```

**See**: [[23-API-Keys]] for complete guide.

---

### 6. SocialAccount

**OAuth/social login accounts.**

```python
class SocialAccount(Document):
    # User relationship
    user_id: ObjectId

    # Provider info
    provider: str  # "google", "github", "facebook", "apple"
    provider_user_id: str

    # User data (cached)
    email: str
    email_verified: bool = False
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    # OAuth tokens (should be encrypted at rest)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

    # Provider data
    provider_data: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    linked_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
```

**Indexes**:
```python
indexes = [
    "user_id",                               # User's OAuth accounts
    [("provider", 1), ("provider_user_id", 1)],  # Unique per provider
    [("provider", 1), ("email", 1)]          # Provider + email lookup
]
```

**Example**:
```python
social = SocialAccount(
    user_id=user.id,
    provider="google",
    provider_user_id="107353926327...",
    email="john@gmail.com",
    email_verified=True,
    display_name="John Doe",
    avatar_url="https://lh3.googleusercontent.com/...",
    access_token=encrypted_token,
    refresh_token=encrypted_refresh
)
```

**See**: [[33-OAuth-Account-Linking]] for account linking.

---

## EnterpriseRBAC Models

### 7. EntityModel

**Organizational entities and access groups.**

```python
class EntityClass(str, Enum):
    STRUCTURAL = "structural"  # Org hierarchy (dept, team)
    ACCESS_GROUP = "access_group"  # Cross-cutting groups

class EntityModel(BaseDocument):
    # Identity
    name: str  # System name
    display_name: str  # User-friendly name
    slug: str  # URL-friendly, unique
    description: Optional[str] = None

    # Classification
    entity_class: EntityClass
    entity_type: str  # "company", "department", "team", etc.

    # Hierarchy
    parent_entity: Optional[Link["EntityModel"]] = None

    # Lifecycle
    status: str = "active"  # active, inactive, archived
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Permissions (optional)
    direct_permissions: List[str] = Field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Configuration
    allowed_child_classes: List[EntityClass] = Field(default_factory=list)
    allowed_child_types: List[str] = Field(default_factory=list)
    max_members: Optional[int] = None
```

**Indexes**:
```python
indexes = [
    "name",
    "slug",  # Unique
    [("entity_class", 1), ("entity_type", 1)],
    "parent_entity",
    [("tenant_id", 1)],
    "status"
]
```

**Key Methods**:
```python
@property
def is_structural(self) -> bool:
    """Check if entity is structural"""

@property
def is_access_group(self) -> bool:
    """Check if entity is access group"""

def is_active(self) -> bool:
    """Check if entity is currently active"""

async def is_ancestor_of(entity: "EntityModel") -> bool:
    """Check if this is ancestor of another entity"""
```

**Example**:
```python
company = EntityModel(
    name="acme_corp",
    display_name="Acme Corp",
    slug="acme-corp",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company",
    status="active"
)

engineering = EntityModel(
    name="engineering",
    display_name="Engineering",
    slug="acme-corp-engineering",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_entity=company
)
```

**See**: [[50-Entity-System]] for entity system overview.

---

### 8. EntityMembershipModel

**User memberships in entities with roles.**

```python
from outlabs_auth.models.membership_status import MembershipStatus

class EntityMembershipModel(BaseDocument):
    # Relationships
    user: Link[UserModel]
    entity: Link[EntityModel]

    # Multiple roles per membership
    roles: List[Link[RoleModel]] = Field(default_factory=list)

    # Membership metadata
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    joined_by: Optional[Link[UserModel]] = None

    # Time-based membership
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status (uses MembershipStatus enum)
    status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE,
        description="Current status of the membership"
    )

    # Revocation metadata (when status=REVOKED)
    revoked_at: Optional[datetime] = Field(default=None)
    revoked_by: Optional[Link[UserModel]] = Field(default=None)
```

**Indexes**:
```python
indexes = [
    [("user", 1), ("entity", 1)],  # Unique constraint
    "entity",                       # Entity members
    "user",                         # User memberships
    "status",                       # Filter by status
    [("tenant_id", 1)]
]
```

**Key Methods**:
```python
def is_currently_valid(self) -> bool:
    """Check if membership is currently valid (time-based)"""

def can_grant_permissions(self) -> bool:
    """Check if membership can currently grant permissions (status + time)"""
```

**Example**:
```python
# Create active membership
membership = EntityMembershipModel(
    user=john,
    entity=engineering_dept,
    roles=[manager_role, developer_role],
    status=MembershipStatus.ACTIVE,
    joined_by=admin_user
)
await membership.insert()

# Revoke membership (soft delete)
membership.status = MembershipStatus.REVOKED
membership.revoked_at = datetime.now(timezone.utc)
membership.revoked_by = admin_user
await membership.save()
```

**See**: [[54-Entity-Memberships]] for membership management.

---

### 9. EntityClosureModel

**Closure table for O(1) ancestor/descendant queries.**

```python
class EntityClosureModel(BaseDocument):
    # Relationships
    ancestor_id: str  # Ancestor entity ID
    descendant_id: str  # Descendant entity ID

    # Depth (0 = self, 1 = direct child, 2 = grandchild, etc.)
    depth: int = Field(ge=0)
```

**Indexes**:
```python
indexes = [
    [("ancestor_id", 1), ("descendant_id", 1)],  # Unique
    [("descendant_id", 1), ("depth", 1)],  # Find ancestors
    [("ancestor_id", 1), ("depth", 1)],    # Find descendants
    "ancestor_id",
    "descendant_id",
    [("tenant_id", 1)]
]
```

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
# Get all ancestors (O(1))
ancestors = await EntityClosureModel.find(
    EntityClosureModel.descendant_id == team_id,
    EntityClosureModel.depth > 0
).sort("depth").to_list()

# Get all descendants (O(1))
descendants = await EntityClosureModel.find(
    EntityClosureModel.ancestor_id == company_id,
    EntityClosureModel.depth > 0
).to_list()

# Check if ancestor (O(1))
is_ancestor = await EntityClosureModel.find_one(
    EntityClosureModel.ancestor_id == company_id,
    EntityClosureModel.descendant_id == team_id
) is not None
```

**See**: [[53-Closure-Table]] for closure table pattern.

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

**See**: [[46-ABAC-Policies]] for ABAC guide.

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
    user_id: Optional[ObjectId] = None

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
class ActivityMetric(Document):
    period_type: str            # "daily", "monthly", "quarterly"
    period: str                 # "2025-01-24", "2025-01", "2025-Q1"
    active_users: int           # Count of unique active users
    unique_user_ids: Optional[List[str]] = None  # For cohort analysis (optional)

    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "activity_metrics"
        indexes = [
            [("period_type", 1), ("period", -1)],  # Query by type + time
            [("created_at", 1)],                   # Cleanup old records
            [("period_type", 1), ("period", 1)],   # Unique constraint
        ]
```

**Purpose**: Historical activity tracking for analytics and growth monitoring.

**Data Flow**:
1. Real-time tracking in **Redis Sets** (O(1) operations)
2. Background worker syncs to MongoDB every 30-60 minutes
3. TTL-based cleanup (default: 90 days)

**Storage Modes**:
- **Count only** (`activity_store_user_ids=False`): ~100 bytes per record
- **With user IDs** (`activity_store_user_ids=True`): ~16 bytes per user per day

**See**: `docs-library/49-Activity-Tracking.md` for complete implementation details.

---

## Collection Summary

| Collection | SimpleRBAC | EnterpriseRBAC | Purpose |
|------------|------------|----------------|---------|
| **users** | ✅ | ✅ | User accounts |
| **roles** | ✅ | ✅ | Role definitions |
| **permissions** | ⚠️ Optional | ⚠️ Optional | Permission registry |
| **refresh_tokens** | ✅ | ✅ | JWT refresh tokens |
| **api_keys** | ✅ | ✅ | API key authentication |
| **social_accounts** | ✅ | ✅ | OAuth accounts |
| **oauth_states** | ⚠️ Optional | ⚠️ Optional | OAuth state (JWT alternative) |
| **entities** | ❌ | ✅ | Entity hierarchy |
| **entity_memberships** | ❌ | ✅ | User memberships |
| **entity_closure** | ❌ | ✅ | Closure table |
| **activity_metrics** | ⚠️ Optional | ⚠️ Optional | DAU/MAU tracking (DD-049) |

**Total Collections**:
- SimpleRBAC: 5-8 collections (6-8 with activity tracking)
- EnterpriseRBAC: 8-11 collections (9-11 with activity tracking)

---

## Indexes Summary

### Critical Indexes

**UserModel**:
```python
[("email", 1)]           # UNIQUE - email lookup
[("status", 1)]          # Filter by status
```

**RoleModel**:
```python
[("name", 1)]            # UNIQUE - role name lookup
```

**APIKeyModel**:
```python
[("prefix", 1)]          # Fast prefix lookup
[("owner", 1)]           # User's API keys
```

**SocialAccount**:
```python
[("user_id", 1)]                           # User's OAuth accounts
[("provider", 1), ("provider_user_id", 1)] # UNIQUE - provider lookup
```

**EntityModel** (EnterpriseRBAC):
```python
[("slug", 1)]            # UNIQUE - slug lookup
[("parent_entity", 1)]   # Hierarchy queries
```

**EntityMembershipModel** (EnterpriseRBAC):
```python
[("user", 1), ("entity", 1)]  # UNIQUE - user in entity
[("entity", 1)]               # Entity members
[("user", 1)]                 # User memberships
```

**EntityClosureModel** (EnterpriseRBAC):
```python
[("ancestor_id", 1), ("descendant_id", 1)]  # UNIQUE
[("descendant_id", 1), ("depth", 1)]        # Ancestor queries
[("ancestor_id", 1), ("depth", 1)]          # Descendant queries
```

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

**Current Version**: 1.0
**Future Migrations**: Will use Beanie migrations or custom migration scripts.

---

## Best Practices

### 1. Use Indexes

```python
# ✅ Good - indexed field
user = await UserModel.find_one(UserModel.email == email)

# ❌ Bad - non-indexed field
users = await UserModel.find(UserModel.metadata.custom_field == value)
```

### 2. Avoid N+1 Queries

```python
# ❌ Bad - N+1 queries
memberships = await EntityMembershipModel.find(...).to_list()
for membership in memberships:
    user = await membership.user.fetch()  # N database calls!

# ✅ Good - use fetch_links or aggregation
memberships = await EntityMembershipModel.find(...).fetch_links().to_list()
```

### 3. Validate Before Saving

```python
# ✅ Good - validate before save
user = UserModel(email="user@example.com", ...)
await user.insert()  # Automatic validation

# ❌ Bad - skip validation
user = UserModel.construct(email="invalid")  # Skips validation!
await user.save()  # May save invalid data
```

### 4. Use Transactions for Critical Operations

```python
# ✅ Good - use transaction for entity + membership creation
async with await mongo_client.start_session() as session:
    async with session.start_transaction():
        entity = await EntityModel(...).insert(session=session)
        membership = await EntityMembershipModel(...).insert(session=session)
```

---

## Summary

**Core Models**:
- ✅ **UserModel** - User accounts and authentication
- ✅ **RoleModel** - Roles with permissions and ABAC
- ✅ **PermissionModel** - Permission definitions (optional)
- ✅ **RefreshTokenModel** - JWT refresh tokens
- ✅ **APIKeyModel** - API key authentication
- ✅ **SocialAccount** - OAuth/social login accounts

**EnterpriseRBAC Models**:
- ✅ **EntityModel** - Organizational entities
- ✅ **EntityMembershipModel** - User memberships with roles
- ✅ **EntityClosureModel** - Closure table for O(1) queries

**ABAC Models**:
- ✅ **Condition** - ABAC condition (embedded)
- ✅ **ConditionGroup** - Condition groups with AND/OR

**Database**: PostgreSQL with SQLAlchemy/SQLModel (async)
**Tables**: 5-12 depending on preset
**Indexes**: 25+ for optimal query performance

---

## Next Steps

- **[11. Core Components →](./11-Core-Components.md)** - Services and architecture
- **[10. Architecture Overview →](./10-Architecture-Overview.md)** - System design
- **[13. Authentication Flow →](./13-Authentication-Flow.md)** - How authentication works
- **[14. Authorization Flow →](./14-Authorization-Flow.md)** - How permissions are checked

---

## Further Reading

### PostgreSQL & SQLAlchemy
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)

### Data Modeling
- [PostgreSQL Schema Design Best Practices](https://www.postgresql.org/docs/current/ddl.html)
- [Closure Table Pattern](https://www.slideshare.net/billkarwin/models-for-hierarchical-data)
- [Pydantic Documentation](https://docs.pydantic.dev/)
