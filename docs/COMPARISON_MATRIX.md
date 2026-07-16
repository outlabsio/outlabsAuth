# OutlabsAuth Library - Feature Comparison Matrix

**Purpose**: Help choose the right preset for your needs
**Source of truth**: `outlabs_auth/presets/simple.py`, `outlabs_auth/presets/enterprise.py`, `outlabs_auth/database/registry.py`

**Architecture Note**: SimpleRBAC and EnterpriseRBAC are thin wrappers around a single unified `OutlabsAuth` core, and differ only by three booleans — `enable_entity_hierarchy`, `enable_context_aware_roles`, `enable_abac`. SimpleRBAC forces all three off; EnterpriseRBAC forces hierarchy on and leaves the other two configurable (both default off). Everything else is shared. Storage is PostgreSQL throughout (SQLModel + SQLAlchemy async + asyncpg): 33 tables, applied by the library's own packaged Alembic migrations via `outlabs-auth migrate` and tracked in its own `outlabs_auth_alembic_version` table so it never collides with the host app's migration history. Pass `database_schema="outlabs_auth"` to keep the tables in a dedicated schema; by default they follow the connection's search path.

---

## Quick Decision Tree

```
Start here: Do you need organizational hierarchy (departments/teams)?
│
├─ NO ──> SimpleRBAC
│         ✓ Users, roles, permissions
│         ✓ Flat structure
│         ✓ Perfect for simple apps
│         ✓ Fast setup
│
└─ YES ──> EnterpriseRBAC
           ✓ Entity hierarchy (always included)
           ✓ Tree permissions (always included)
           ✓ Roles per entity membership (always included)
           ✓ Optional: Context-aware roles (enable_context_aware_roles=True)
           ✓ Optional: ABAC conditions (enable_abac=True)
           ✓ Recommended: Redis counters + caching (redis_url)
           ✓ Entity-isolated single app (root-entity scoping)

           Configure only what you need via feature flags!
```

---

## Feature Comparison Table

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|-----------|----------------|
| **Core Features** |
| User management | ✅ | ✅ |
| Role management | ✅ | ✅ |
| Permission checking | ✅ | ✅ |
| JWT authentication | ✅ | ✅ |
| Password management | ✅ | ✅ |
| Refresh tokens | ✅ | ✅ |
| **API Key Authentication (DD-028, DD-033)** |
| API key authentication | ✅ | ✅ |
| Prefixed keys (`sk_live_...`) | ✅ (DD-028) | ✅ (DD-028) |
| API key SHA-256 hashing | ✅ (DD-028) | ✅ (DD-028) |
| Temporary locks (30-min cooldown) | ✅ (DD-028) | ✅ (DD-028) |
| Redis usage counters | ✅ (DD-033) | ✅ (DD-033) |
| API key rate limiting | ✅ (in-memory) | ✅ (in-memory + Redis optional) |
| API key IP whitelisting | ✅ | ✅ |
| API key rotation | ✅ | ✅ |
| Entity-scoped API keys | ❌ | ✅ |
| **JWT Service Tokens (DD-034)** |
| JWT service token authentication | ✅ | ✅ |
| Zero DB hits (~0.5ms validation) | ✅ | ✅ |
| Internal microservices auth | ✅ | ✅ |
| **Multi-Source Authentication** |
| Multi-source authentication | ✅ | ✅ |
| Auth result as plain dict | ✅ | ✅ |
| Unified AuthDeps class | ✅ (DD-035) | ✅ (DD-035) |
| **Hierarchy (Always Included in EnterpriseRBAC)** |
| Entity hierarchy | ❌ | ✅ |
| Tree permissions | ❌ | ✅ |
| Closure table (O(1) queries) | ❌ | ✅ (DD-036) |
| 20x tree permission performance | ❌ | ✅ (DD-036) |
| Multiple roles per user | ✅ (flat, via `user_role_memberships`) | ✅ (per entity membership) |
| Entity memberships | ❌ | ✅ |
| Access groups | ❌ | ✅ |
| **Role Scoping (DD-050)** |
| Role scoping to root entities | ❌ | ✅ |
| Organization-isolated roles | ❌ | ✅ |
| Global system-wide roles | ✅ | ✅ |
| Cross-org membership prevention | ❌ | ✅ |
| **Entity Type Configuration (DD-051)** |
| Configurable root entity types | ❌ | ✅ |
| Per-organization child type customization | ❌ | ✅ |
| System-wide type defaults | ❌ | ✅ |
| UI for entity type settings | ❌ | ✅ (superuser only) |
| **Optional Features (Feature Flags)** |
| Context-aware roles | ❌ | ⭕ `enable_context_aware_roles=True` |
| ABAC conditions | ❌ | ⭕ `enable_abac=True` |
| Redis-backed caching | ✅ via `redis_url` | ✅ via `redis_url` |
| Redis Pub/Sub cache invalidation | ✅ via `redis_url` | ✅ via `redis_url` |
| Tenant isolation mode | ❌ | ❌ (removed; use entity/root scoping) |
| Core lifecycle history | ✅ user/definition history | ✅ user/membership/definition history |
| **Performance** |
| Permission check | ~10ms | ~10ms (uncached)<br>~5ms (cached) |
| Tree permission check | N/A | ~10ms (O(1) via closure table) |
| API key validation | DB lookup-bound | DB lookup-bound |
| JWT service token validation | ~0.5ms (zero DB) | ~0.5ms (zero DB) |
| Cache invalidation | N/A | <100ms (Redis Pub/Sub) |
| Setup complexity | ⭐ | ⭐⭐ (basic)<br>⭐⭐⭐ (all features) |
| Learning curve | Easy | Medium to Advanced |
| **Use Cases** |
| Simple web apps | ✅ ✅ ✅ | ✅ |
| Multi-department orgs | ❌ | ✅ ✅ ✅ |
| Complex permissions | ❌ | ✅ ✅ ✅ |
| Enterprise apps | ❌ | ✅ ✅ ✅ |

Legend:
- ✅ = Included
- ❌ = Not supported
- ⭕ = Optional (enable via feature flag)
- ⭐ = Complexity level (more stars = more complex)

---

## Authentication Extensions (Optional)

**Compatibility**: Work with **both** SimpleRBAC and EnterpriseRBAC — they are core
feature flags, not preset-specific.

### Extension Feature Comparison

| Extension Feature | SimpleRBAC | EnterpriseRBAC | Enabled by |
|-------------------|-----------|----------------|------------|
| **Notifications** |
| Notification service injection | ⭕ | ⭕ | `enable_notifications=True` + `notification_service=` |
| Transactional mail service | ⭕ | ⭕ | `transactional_mail_service=` |
| Transactional messaging service | ⭕ | ⭕ | `transactional_messaging_service=` |
| **OAuth / Social Login** (`outlabs_auth/oauth/`) |
| Google OAuth | ⭕ | ⭕ | provider config |
| Facebook OAuth | ⭕ | ⭕ | provider config |
| Apple Sign-In (JWKS-verified ID tokens) | ⭕ | ⭕ | provider config |
| GitHub OAuth | ⭕ | ⭕ | provider config |
| Additional providers via `httpx-oauth` | ⭕ | ⭕ | `provider_factories.py` (optional dep) |
| Account linking (by verified email) | ⭕ | ⭕ | built in |
| PKCE + nonce + browser-bound state | ⭕ | ⭕ | built in |
| Provider token storage (encrypted) | ⭕ | ⭕ | `store_oauth_provider_tokens=True` + `oauth_token_encryption_key=` |
| **Passwordless** (`auth_challenges`) |
| Magic links (email) | ⭕ | ⭕ | `enable_magic_links=True` |
| Access codes (email) | ⭕ | ⭕ | `enable_access_codes=True` |
| WhatsApp OTP | ⭕ | ⭕ | challenge type + messaging service |
| SMS OTP | ⭕ | ⭕ | challenge type + messaging service |
| Per-challenge rate limiting | ✅ | ✅ | `*_rate_limit_*` settings |

Legend:
- ✅ = Always on
- ⭕ = Optional (enable via feature flag / injected service)

**Not implemented**: TOTP/MFA, backup codes, and WebAuthn/passkeys do not exist in
the codebase. Do not plan against them.

### Extension Configuration Example

Verified against `examples/notifications/main.py`:

```python
from outlabs_auth import SimpleRBAC  # or EnterpriseRBAC

auth = SimpleRBAC(
    database_url=os.getenv("DATABASE_URL"),   # postgresql+asyncpg://...
    secret_key=os.getenv("SECRET_KEY"),       # >=32 chars, required for HS256
    notification_service=notification_service,
    enable_notifications=True,
    enable_magic_links=True,
    enable_access_codes=True,
)

await auth.initialize()
```

Notification, mail, and messaging services are **injected instances**, not classes
the library constructs for you. See `outlabs_auth/mail/` and
`outlabs_auth/messaging/` for the expected shapes, and
`examples/enterprise_rbac/challenge_messaging.py` for a working challenge-delivery
wiring.

### Extension Dependencies

**Key Points**:
- Notification/mail/messaging services are injected by the host app — the library
  defines the interface and calls it; it does not ship a vendor integration.
- Magic links and access codes deliver through the injected mail service, so they
  need `enable_notifications` + a `transactional_mail_service`.
- WhatsApp/SMS OTP challenge types need an injected
  `transactional_messaging_service`.
- OAuth stands alone — it does not require the notification system.
- Every extension works with both SimpleRBAC and EnterpriseRBAC. Enabling one
  later needs no migration between presets, but may add tables — run
  `outlabs-auth migrate`.

### Extension Use Cases

**Notifications**:
- Welcome emails, password-reset mail, invite delivery
- Integration with existing notification infrastructure, no vendor lock-in

**OAuth/Social Login**:
- "Login with Google" and similar
- Auto-link by verified email (blocked when the provider does not verify it)
- Reduce signup friction

**Passwordless**:
- Magic-link login (no password)
- Email access codes
- WhatsApp/SMS OTP for phone-first users

### When to Adopt Extensions

**Add Notifications** when:
- You need to send auth-related mail
- You want to decouple from a specific email/SMS vendor
- You plan to use magic links or access codes (they depend on it)

**Add OAuth** when:
- Users expect social login
- You need multiple identity providers
- You want to leverage existing social accounts

**Add Passwordless** when:
- You want to eliminate passwords
- You need phone verification
- Mobile-first authentication

**External service cost**: OAuth providers are free. Mail and SMS/WhatsApp cost
whatever your chosen provider charges — the library is agnostic.

---

## Detailed Feature Breakdown

### SimpleRBAC

**Best For:**
- Small to medium web applications
- Flat organizational structure
- Simple role-based access control
- Getting started quickly

**What You Get:**
```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key=os.getenv("SECRET_KEY"),  # >=32 chars
)

# Users
user = await auth.user_service.create_user(email, password)

# Roles (one per user)
role = await auth.role_service.create_role(
    name="admin",
    permissions=["user:create", "user:delete"]
)
await auth.user_service.assign_role(user.id, role.id)

# Permission check
has_perm = await auth.permission_service.check_permission(
    user.id, "user:delete"
)

# API keys
raw_key, api_key = await auth.api_key_service.create_api_key(
    name="Production Service",
    permissions=["user:read", "entity:read"],
    environment="production",  # sk_prod_ prefix
    allowed_ips=["10.0.1.0/24"],
    rate_limit_per_minute=60
)

# Multi-source authentication. `auth.deps` only exists after `await auth.initialize()`,
# so build route dependencies at request time rather than at import time.
async def require_user_read(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    dep_fn = auth.deps.require_permission("user:read")
    return await dep_fn(request=request, session=session)

@app.get("/users")
async def list_users(auth_result: dict = Depends(require_user_read)):
    # Accepts JWT, API key, JWT service token, or superuser token.
    # Permission is already enforced; auth_result is a plain dict.
    async with auth.get_session() as session:
        return await auth.user_service.list_users(session)
```

**Limitations:**
- No entity hierarchy
- No tree permissions
- No organizational structure
- Roles are flat and global — no scoping to a root entity

**Models added by this preset** (on top of the shared core models):
- `UserRoleMembership` → `user_role_memberships`

**Dependencies:**
- PostgreSQL (via SQLModel + SQLAlchemy async + asyncpg)
- FastAPI
- Python 3.12+

**Performance:**
- Permission check: ~10ms (database query)
- Login: ~50ms
- User creation: ~30ms

---

### EnterpriseRBAC

**Best For:**
- Organizations with departments/teams/hierarchy
- Multi-level permission inheritance
- Users with different roles in different contexts
- Real estate, enterprise software, government
- Optionally: Complex permissions, ABAC, high performance

**What You Get (Always Included):**
```python
from outlabs_auth import EnterpriseRBAC

# Basic setup: Entity hierarchy + tree permissions
auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key=os.getenv("SECRET_KEY"),  # >=32 chars
)

# Entity hierarchy (always included)
company = await auth.entity_service.create_entity(
    name="acme",
    entity_class="structural",
    entity_type="company"
)

dept = await auth.entity_service.create_entity(
    name="engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=company.id
)

# User membership with multiple roles (always included)
await auth.membership_service.add_member(
    entity_id=dept.id,
    user_id=user.id,
    role_ids=[manager_role.id, developer_role.id]  # Multiple roles!
)

# Tree permissions (always included)
role = await auth.role_service.create_role(
    name="dept_manager",
    permissions=[
        "entity:read",        # Read department itself
        "entity:update",      # Update department itself
        "entity:create_tree", # Create teams below
        "user:manage_tree"    # Manage users in all teams below
    ]
)

# Entity-scoped API keys (always included - EnterpriseRBAC only)
raw_key, api_key = await auth.api_key_service.create_api_key(
    name="Department Service",
    permissions=["user:read_tree", "entity:read_tree"],
    environment="production",
    entity_id=dept.id,  # Scoped to department and all descendants
    allowed_ips=["10.0.1.0/24"]
)

# Entity-scoped permission checks. `require_permission` picks the entity context up
# from the `entity_id` path/query param automatically.
async def require_entity_read(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    dep_fn = auth.deps.require_permission("entity:read")
    return await dep_fn(request=request, session=session)

@app.get("/entities/{entity_id}")
async def get_entity(
    entity_id: UUID,
    auth_result: dict = Depends(require_entity_read),
    session: AsyncSession = Depends(get_session),
):
    # Accepts JWT, API key, JWT service token, or superuser token.
    # Works with entity-scoped API keys and tree permissions automatically.
    return await auth.entity_service.get_entity(session, entity_id)
```

**Optional Features (Enable as Needed):**
```python
# Full-featured setup with all options
auth = EnterpriseRBAC(
    database_url=os.getenv("DATABASE_URL"),
    secret_key=os.getenv("SECRET_KEY"),  # >=32 chars
    redis_url="redis://localhost:6379",
    enable_context_aware_roles=True,  # Opt-in
    enable_abac=True,                 # Opt-in
)

# Context-aware roles (opt-in feature)
regional_manager = await auth.role_service.create_role(
    name="regional_manager",
    permissions=["entity:read"],  # Default

    # Different permissions by entity type
    entity_type_permissions={
        "region": ["entity:manage_tree", "user:manage_tree"],
        "office": ["entity:read", "user:read"],
        "team": ["entity:read"]
    }
)

# ABAC permissions with conditions (opt-in feature)
invoice_approval = await auth.permission_service.create_permission(
    name="invoice:approve",
    conditions=[
        {"attribute": "resource.amount", "operator": "<=", "value": 50000}
    ]
)
```

**Core Features (Always Included):**
- Entity hierarchy with flexible types
- Tree permissions (`resource:action_tree`)
- Multiple roles per user
- Access groups (cross-cutting permissions)
- Entity path traversal and descendant queries

**Optional Features (Feature Flags):**
- Context-aware roles (`enable_context_aware_roles=True`)
- ABAC conditions (`enable_abac=True`)
- Redis counters and permission caching (`redis_url`)
- Entity/root scoping isolation

**Core History (Current Runtime):**
- User lifecycle timeline via `user_audit_events`
- Entity membership lifecycle via `entity_membership_history`
- Role/permission definition history via dedicated history tables

**Limitations:**
- More complex than SimpleRBAC
- Optional features add complexity
- Redis recommended for production API-key counters and permission caching
- Steeper learning curve with all features enabled

**Models added by this preset** (on top of the shared core models):
- `Entity` → `entities`
- `EntityMembership` → `entity_memberships`
- `EntityMembershipRole` → `entity_membership_roles` (junction)
- `EntityClosure` → `entity_closure`
- `EntityMembershipHistory` → `entity_membership_history`

**Dependencies:**
- PostgreSQL (via SQLModel + SQLAlchemy async + asyncpg)
- FastAPI
- Python 3.12+
- Redis (recommended in production when using API keys)

**Performance:**
- Permission check: ~10ms (uncached with closure table), ~5ms (cached)
- **Tree permission check: ~10ms (O(1) via closure table - DD-036)** - 20x improvement
- **API key validation: DB lookup-bound** — keys are SHA-256 hashed (DD-028), so the hash is negligible; the cost is the indexed lookup on `key_hash`
- **JWT service token: ~0.5ms (zero DB hits - DD-034)**
- **Cache invalidation: <100ms across all instances (Redis Pub/Sub - DD-037)**
- ABAC evaluation: +5-10ms per condition (if enabled)
- Entity creation: ~25ms
- Member add: ~35ms
- Cache hit rate: ~95% (when caching enabled)

---

## Use Case Examples

### SimpleRBAC Use Cases

#### 1. Blog Platform
```
Users:
- Admin: Can manage all posts and users
- Editor: Can create and edit posts
- Author: Can create own posts
- Reader: Can read posts

No hierarchy needed - perfect for SimpleRBAC
```

#### 2. SaaS Tool
```
Users:
- Owner: Full access
- Admin: Manage users and settings
- Member: Use features
- Guest: View only

Flat structure - SimpleRBAC works great
```

#### 3. Internal Tool
```
Users:
- Developer: Access dev features
- QA: Access testing features
- Manager: View reports

No organizational structure - SimpleRBAC sufficient
```

---

### EnterpriseRBAC Use Cases

#### 1. Real Estate Platform (Basic Hierarchy)
```
Diverse Platform
├── Organization: Diverse Leads
    ├── Region: West Coast
    │   ├── Office: Los Angeles
    │   │   ├── Team: Luxury Properties
    │   │   └── Team: Commercial
    │   └── Office: Seattle
    └── Region: East Coast

Agents belong to offices/teams
Managers have tree permissions over regions

EnterpriseRBAC (basic setup):
- Entity hierarchy ✅
- Tree permissions ✅
- No additional features needed
```

#### 2. Enterprise Software (Basic Hierarchy)
```
Company
├── Division: Engineering
│   ├── Department: Backend
│   │   ├── Team: API Team
│   │   └── Team: Database Team
│   └── Department: Frontend
└── Division: Sales
    ├── Department: Enterprise Sales
    └── Department: SMB Sales

Department heads manage all teams below

EnterpriseRBAC (basic setup):
- Entity hierarchy ✅
- Tree permissions ✅
- Multiple roles per user ✅
```

#### 3. Government Agency (Basic Hierarchy)
```
Agency
├── Bureau: Transportation
│   ├── Section: Roads
│   └── Section: Public Transit
└── Bureau: Public Safety
    ├── Section: Fire
    └── Section: Police

Hierarchical command structure
Tree permissions essential

EnterpriseRBAC (basic setup):
- Entity hierarchy ✅
- Tree permissions ✅
```

#### 4. Financial Platform (Advanced Features)
```
Need:
- Invoice approval limits by amount
- Access restricted to same department
- Manager role varies by level

Example:
- Regional VP: Approve up to $1M at region level
- Office Manager: Approve up to $50K at office level
- Team Lead: Approve up to $10K at team level

EnterpriseRBAC with optional features:
- Entity hierarchy ✅ (core)
- Context-aware roles ⭕ (enable_context_aware_roles=True)
- ABAC conditions ⭕ (enable_abac=True)
- Redis caching ✅ (via `redis_url`)
```

#### 5. Healthcare System (Advanced Features)
```
Need:
- Doctor access varies by department
- Patient record access rules
- Prescription limits by classification
- Audit trail

EnterpriseRBAC with optional features:
- Entity hierarchy ✅ (core)
- Context-aware roles ⭕ (enable_context_aware_roles=True)
- ABAC conditions ⭕ (enable_abac=True)
- Core lifecycle history ✅
- Redis caching ✅ (via `redis_url`)
```

#### 6. Multi-Tenant SaaS (Advanced Features)
```
Need:
- Tenant isolation
- Complex org structure per tenant
- Conditional feature access
- High performance

EnterpriseRBAC with optional features:
- Entity hierarchy ✅ (core)
- Tenant mode ❌ (removed)
- ABAC for feature flags ⭕ (enable_abac=True)
- Redis caching ✅ (via `redis_url`)
```

---

## Migration Paths

### From SimpleRBAC → EnterpriseRBAC

**When to Upgrade:**
- You need departmental/organizational structure
- Users need different roles in different contexts
- You want tree permissions for hierarchical access control

**Migration Steps:**
1. Switch from `SimpleRBAC` to `EnterpriseRBAC`
2. Create entity hierarchy for your organization
3. Convert user-role assignments to entity memberships
4. Update permission checks to include entity context
5. Add tree permissions where needed

**Effort**: ~2-3 days

**Example:**
```python
# BEFORE (SimpleRBAC)
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key=os.getenv("SECRET_KEY"),  # >=32 chars
)

# Users have one role
await auth.user_service.assign_role(user.id, manager_role.id)

# AFTER (EnterpriseRBAC - basic setup)
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key=os.getenv("SECRET_KEY"),  # >=32 chars
)

# Create entity hierarchy
department = await auth.entity_service.create_entity(
    name="engineering",
    entity_class="structural",
    entity_type="department"
)

# Users can have multiple roles via entity memberships
await auth.membership_service.add_member(
    entity_id=department.id,
    user_id=user.id,
    role_ids=[manager_role.id, developer_role.id]
)
```

---

### EnterpriseRBAC: Enabling Optional Features

**When to Enable:**
- **Context-aware roles**: Role permissions need to vary by entity type
- **ABAC conditions**: Need attribute-based access control
- **Redis**: Production API-key counters, rate limits, and permission-cache performance
- **Entity isolation**: Need strict root-entity boundaries
- **Additional compliance overlays**: Core lifecycle history is included; add host-specific compliance/export handling only if needed

**Migration Steps:**
1. Add feature flags to existing `EnterpriseRBAC` configuration
2. Provide `redis_url` for production Redis counters/rate limits and permission caching
3. Update roles to use context-aware permissions (if needed)
4. Add ABAC conditions to permissions (if needed)
5. Test thoroughly before production deployment

**Effort**: ~1-2 days per feature

**Example:**
```python
# BEFORE (EnterpriseRBAC - basic)
auth = EnterpriseRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key=os.getenv("SECRET_KEY"),  # >=32 chars
)

# AFTER (EnterpriseRBAC - with optional features)
auth = EnterpriseRBAC(
    database_url=os.getenv("DATABASE_URL"),
    secret_key=os.getenv("SECRET_KEY"),  # >=32 chars
    redis_url="redis://localhost:6379",
    enable_context_aware_roles=True,  # Enable as needed
    enable_abac=True,                 # Enable as needed
)

# Context-aware role (optional feature)
manager_role = await auth.role_service.create_role(
    name="regional_manager",
    permissions=["entity:read"],  # Default
    entity_type_permissions={
        "region": ["entity:manage_tree", "user:manage_tree"],
        "office": ["entity:read", "user:read"]
    }
)
```

---

## Performance Comparison

### Permission Check Latency

| Preset | Basic Check | Tree Check | Cached Check | API Key | JWT Service Token |
|--------|-------------|------------|--------------|---------|-------------------|
| SimpleRBAC | ~10ms | N/A | N/A | lookup-bound | ~0.5ms |
| EnterpriseRBAC (basic) | ~10ms | **~10ms (O(1))** | ~10ms | lookup-bound | ~0.5ms |
| EnterpriseRBAC (cached) | ~5ms | **~5ms** | ~5ms | lookup-bound | ~0.5ms |
| EnterpriseRBAC (ABAC) | ~10ms + 5-10ms/condition | **~10ms** + 5-10ms/condition | ~5ms + 5-10ms/condition | lookup-bound | ~0.5ms |

**Key Improvements**:
- **Closure table (DD-036)**: 20x improvement in tree permission queries
- **JWT service tokens (DD-034)**: Zero DB hits for internal services
- **Redis Pub/Sub (DD-037)**: <100ms cache invalidation across all instances
- **Redis counters (DD-033)**: 99%+ reduction in DB writes for API keys

### Throughput (requests/second)

| Preset | Login | Permission Check | Tree Check | Entity Create | JWT Service Token |
|--------|-------|------------------|------------|---------------|-------------------|
| SimpleRBAC | ~200 | ~500 | N/A | N/A | ~2000 |
| EnterpriseRBAC (uncached) | ~200 | **~500** | **~500** | ~150 | ~2000 |
| EnterpriseRBAC (cached) | ~200 | **~1000** | **~1000** | ~150 | ~2000 |

*Benchmarks on MacBook Pro M1, PostgreSQL local, Redis local (when configured)*

---

## Cost-Benefit Analysis

### SimpleRBAC

**Pros:**
- ⭐⭐⭐ Easiest to understand
- ⭐⭐⭐ Fastest to implement
- ⭐⭐⭐ Fewest dependencies
- ⭐⭐ Good performance

**Cons:**
- ❌ No hierarchy
- ❌ One role per user
- ❌ Can't scale to complex orgs

**When to Choose:**
- Small team (< 50 users)
- Flat organizational structure
- Simple permissions
- Fast deployment needed

---

### EnterpriseRBAC

**Pros:**
- ⭐⭐⭐ Flexible entity hierarchy (always included)
- ⭐⭐⭐ Tree permissions (always included)
- ⭐⭐ Multiple roles per user (always included)
- ⭐⭐ Scales to any size organization
- ⭐⭐ Optional advanced features (enable as needed)
- ⭐⭐⭐ Best performance when Redis is configured

**Cons:**
- ⭐ More complex than SimpleRBAC
- ⭐ Slower permission checks than SimpleRBAC (without caching)
- ⭐ Steeper learning curve with all features enabled
- ⭐ Redis recommended for production; no-Redis mode is mainly for early integration

**When to Choose:**
- Medium to large organization
- Departmental/hierarchical structure
- Need tree permissions
- Users have multiple responsibilities
- Optionally: Complex permissions, ABAC, high performance requirements

**Complexity by Configuration:**
- **Basic** (just hierarchy): ⭐⭐ Medium complexity
- **With context-aware roles**: ⭐⭐⭐ Advanced complexity
- **With all features**: ⭐⭐⭐⭐ Expert complexity

---

## Recommendation Matrix

| Your Situation | Recommended Preset | Optional Features |
|----------------|-------------------|-------------------|
| Building MVP | SimpleRBAC | N/A |
| Simple web app | SimpleRBAC | N/A |
| < 50 users | SimpleRBAC | N/A |
| Flat structure | SimpleRBAC | N/A |
| Department structure | EnterpriseRBAC | Basic setup |
| Multi-location | EnterpriseRBAC | Basic setup |
| Tree permissions needed | EnterpriseRBAC | Basic setup |
| > 100 users | EnterpriseRBAC | Basic setup + caching |
| Complex permissions | EnterpriseRBAC | + context-aware roles |
| Enterprise app | EnterpriseRBAC | + context-aware roles + caching |
| Need ABAC | EnterpriseRBAC | + ABAC |
| Performance critical | EnterpriseRBAC | + caching (requires Redis) |
| Context-dependent roles | EnterpriseRBAC | + context-aware roles |
| Entity-isolated SaaS | EnterpriseRBAC | + root-entity scoping + caching |
| Audit requirements | EnterpriseRBAC | Core history + any host-specific compliance layer |

---

## Still Not Sure?

### Start with SimpleRBAC if:
- ✅ You're unsure of requirements
- ✅ You want to ship quickly
- ✅ You can upgrade later
- ✅ Complexity is a concern
- ✅ Flat organizational structure

### Start with EnterpriseRBAC (basic) if:
- ✅ You know you need hierarchy
- ✅ You have organizational structure (departments/teams)
- ✅ SimpleRBAC is definitely insufficient
- ✅ Users need different roles in different contexts
- ✅ You want tree permissions

### Enable Optional Features in EnterpriseRBAC when:
- ⭕ **Context-aware roles**: Role permissions need to vary by entity type
- ⭕ **ABAC conditions**: Complex access rules based on attributes
- ⭕ **Redis caching**: Performance is critical (high traffic)
- ✅ **Entity isolation**: Use root-entity scoping

### Use Core History when:
- ✅ **Audit or investigation needs**: User lifecycle history, membership history, and definition history are already part of the runtime contract

**Pro Tip**: Start with basic EnterpriseRBAC (just hierarchy) and enable optional features incrementally as needed!

---

## Next Steps

1. **Chosen a preset?** → See `examples/simple_rbac/` or `examples/enterprise_rbac/` — the only integration reference kept honest by tests
2. **Ready to implement?** → `README.md` for the quickstart, then the source (`core/auth.py`, `routers/`, `dependencies/__init__.py`)
3. **What's actually built?** → See [CURRENT_IMPLEMENTATION_STATUS.md](CURRENT_IMPLEMENTATION_STATUS.md) and `CHANGELOG.md`
4. **Why is it built this way?** → See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)

---

**Last Updated**: 2026-01-22 (DD-050 role scoping, DD-051 entity type configuration with frontend UI)
**Next Review**: After Phase 1 implementation
