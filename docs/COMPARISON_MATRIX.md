# OutlabsAuth Library - Feature Comparison Matrix

**Version**: 1.4
**Date**: 2025-01-14
**Purpose**: Help choose the right preset for your needs

**Architecture Note (v1.4)**: SimpleRBAC and EnterpriseRBAC are thin wrappers (5-10 LOC each) around a single unified `OutlabsAuth` core. All features are controlled by configuration flags. This means zero code duplication and easy migration between presets.

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
           ✓ Multiple roles per user (always included)
           ✓ Optional: Context-aware roles (enable_context_aware_roles=True)
           ✓ Optional: ABAC conditions (enable_abac=True)
           ✓ Optional: Redis caching (enable_caching=True)
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
| **API Key Authentication (Core v1.0 - DD-028, DD-033)** |
| API key authentication | ✅ | ✅ |
| API key 12-char prefixes | ✅ (DD-028) | ✅ (DD-028) |
| API key argon2id hashing | ✅ (DD-028) | ✅ (DD-028) |
| Temporary locks (30-min cooldown) | ✅ (DD-028) | ✅ (DD-028) |
| Redis usage counters | ✅ (DD-033) | ✅ (DD-033) |
| API key rate limiting | ✅ (in-memory) | ✅ (in-memory + Redis optional) |
| API key IP whitelisting | ✅ | ✅ |
| API key rotation | ✅ | ✅ |
| Entity-scoped API keys | ❌ | ✅ |
| **JWT Service Tokens (Core v1.0 - DD-034)** |
| JWT service token authentication | ✅ | ✅ |
| Zero DB hits (~0.5ms validation) | ✅ | ✅ |
| Internal microservices auth | ✅ | ✅ |
| **Multi-Source Authentication (Core v1.0)** |
| Multi-source authentication | ✅ | ✅ |
| AuthContext abstraction | ✅ | ✅ |
| Unified AuthDeps class | ✅ (DD-035) | ✅ (DD-035) |
| **Hierarchy (Always Included in EnterpriseRBAC)** |
| Entity hierarchy | ❌ | ✅ |
| Tree permissions | ❌ | ✅ |
| Closure table (O(1) queries) | ❌ | ✅ (DD-036) |
| 20x tree permission performance | ❌ | ✅ (DD-036) |
| Multiple roles per user | ❌ | ✅ |
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
| Redis caching | ❌ | ⭕ `enable_caching=True` (requires Redis) |
| Redis Pub/Sub cache invalidation | ❌ | ⭕ `enable_caching=True` (DD-037) |
| Tenant isolation mode | ❌ | ❌ (removed; use entity/root scoping) |
| Audit logging | ❌ | ⭕ `enable_audit_log=True` |
| **Performance (Updated v1.4)** |
| Permission check | ~10ms | ~10ms (uncached)<br>~5ms (cached) |
| Tree permission check | N/A | ~10ms (O(1) via closure table) |
| API key validation | ~50-100ms (argon2id) | ~50-100ms (argon2id) |
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

## Authentication Extensions (v1.1-v1.4, Optional)

**Status**: Post-v1.0 features
**Timeline**: Weeks 8-16 (9 weeks after v1.0)
**Compatibility**: Work with **both** SimpleRBAC and EnterpriseRBAC

All authentication extensions are **optional** and can be adopted independently based on your needs. They do not block v1.0 delivery.

### Extension Feature Comparison

| Extension Feature | SimpleRBAC | EnterpriseRBAC | Available | Requires |
|-------------------|-----------|----------------|-----------|----------|
| **v1.1: Notification System** |
| Notification handler abstraction | ⭕ | ⭕ | v1.1 (Week 8-9) | None |
| WebhookHandler | ⭕ | ⭕ | v1.1 | None |
| QueueHandler | ⭕ | ⭕ | v1.1 | Queue service (Redis, RabbitMQ, SQS) |
| CallbackHandler | ⭕ | ⭕ | v1.1 | None |
| CompositeHandler | ⭕ | ⭕ | v1.1 | None |
| **v1.2: OAuth/Social Login** |
| Google OAuth | ⭕ | ⭕ | v1.2 (Week 10-12) | v1.1 Notifications |
| Facebook OAuth | ⭕ | ⭕ | v1.2 | v1.1 Notifications |
| Apple Sign-In | ⭕ | ⭕ | v1.2 | v1.1 Notifications |
| GitHub OAuth | ⭕ | ⭕ | v1.2 | v1.1 Notifications |
| Microsoft OAuth | ⭕ | ⭕ | v1.2 | v1.1 Notifications |
| Account linking (by verified email) | ⭕ | ⭕ | v1.2 | v1.1 Notifications |
| Custom OAuth providers | ⭕ | ⭕ | v1.2 | v1.1 Notifications |
| **v1.3: Passwordless Authentication** |
| Magic links (email) | ⭕ | ⭕ | v1.3 (Week 13-14) | v1.1 Notifications |
| Email OTP | ⭕ | ⭕ | v1.3 | v1.1 Notifications |
| SMS OTP | ⭕ | ⭕ | v1.3 | v1.1 Notifications + SMS gateway |
| Challenge management | ⭕ | ⭕ | v1.3 | v1.1 Notifications |
| Rate limiting | ⭕ | ⭕ | v1.3 | v1.1 Notifications |
| **v1.4: Advanced Features** |
| TOTP/MFA | ⭕ | ⭕ | v1.4 (Week 15-16) | None |
| Backup codes | ⭕ | ⭕ | v1.4 | None |
| WhatsApp OTP | ⭕ | ⭕ | v1.4 | v1.1 Notifications + WhatsApp Business API |
| Telegram OTP | ⭕ | ⭕ | v1.4 | v1.1 Notifications + Telegram Bot API |
| Account recovery | ⭕ | ⭕ | v1.4 | v1.1 Notifications |
| WebAuthn/Passkeys | 🔬 | 🔬 | v1.4 (research) | Browser support |

Legend:
- ⭕ = Optional extension (adopt as needed)
- 🔬 = Research/prototype phase

### Extension Configuration Example

```python
from outlabs_auth import SimpleRBAC  # or EnterpriseRBAC
from outlabs_auth.extensions.notifications import WebhookHandler
from outlabs_auth.extensions.oauth import GoogleProvider, FacebookProvider

# Configure extensions
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

# Enable extensions (works with both presets!)
auth = SimpleRBAC(  # or EnterpriseRBAC
    database=db,
    notification_handler=notification_handler,  # v1.1
    oauth_providers=oauth_providers,            # v1.2
    enable_magic_links=True,                    # v1.3
    enable_otp=True,                            # v1.3
    enable_mfa=True                             # v1.4
)
```

### Extension Dependencies

**Dependency Chain**:
```
v1.0 (Core) → v1.1 (Notifications) → v1.2 (OAuth) ┐
                                   → v1.3 (Passwordless) ┤→ v1.4 (Advanced)
```

**Key Points**:
- v1.1 (Notifications) is **prerequisite** for v1.2 (OAuth) and v1.3 (Passwordless)
- v1.4 (Advanced features) builds on previous extensions
- You can skip extensions you don't need
- All extensions work with both SimpleRBAC and EnterpriseRBAC

### Extension Use Cases

**Notification System (v1.1)**:
- Send welcome emails
- Password reset notifications
- Alert on suspicious activity
- Integration with existing notification infrastructure

**OAuth/Social Login (v1.2)**:
- "Login with Google" button
- Reduce friction for users
- Auto-link by verified email
- Support multiple providers

**Passwordless Authentication (v1.3)**:
- Magic link login (no password needed)
- SMS OTP for phone verification
- Email OTP for 2FA
- Improved UX for mobile users

**Advanced Features (v1.4)**:
- TOTP for authenticator apps (Google Authenticator, Authy)
- WhatsApp/Telegram OTP
- Multi-factor authentication
- Account recovery flows
- WebAuthn/Passkeys (future)

### Extension Timeline

| Version | Duration | Deliverable | Dependency |
|---------|----------|-------------|------------|
| v1.0 | Week 1-7 | Core library (SimpleRBAC + EnterpriseRBAC) | None |
| v1.1 | Week 8-9 | Notification system | v1.0 |
| v1.2 | Week 10-12 | OAuth/social login | v1.1 |
| v1.3 | Week 13-14 | Passwordless auth | v1.1 |
| v1.4 | Week 15-16 | Advanced features (MFA, etc.) | v1.1-v1.3 |

**Total Timeline**: 15-16 weeks for complete system (6-7 weeks core + 9 weeks extensions)

### When to Adopt Extensions

**Start with v1.0 (Core)**:
- ✅ Focus on delivering core functionality first
- ✅ Get production-ready auth working
- ✅ Extensions can be added later without migration

**Add v1.1 (Notifications)** when:
- Need to send auth-related notifications
- Want to decouple from specific email/SMS vendors
- Planning to add OAuth or passwordless later

**Add v1.2 (OAuth)** when:
- Want to reduce signup friction
- Users expect social login
- Need to support multiple identity providers
- Want to leverage existing social accounts

**Add v1.3 (Passwordless)** when:
- Want to eliminate passwords
- Need SMS verification
- Mobile-first authentication
- Improve security with magic links

**Add v1.4 (Advanced)** when:
- Need multi-factor authentication
- Require TOTP support
- Need additional OTP channels
- Compliance requires MFA

### Extension Pricing (Implementation Cost)

| Extension | Implementation Time | External Services Cost |
|-----------|---------------------|------------------------|
| v1.1 Notifications | 2 weeks | Free (webhook), Varies (SMS/email provider) |
| v1.2 OAuth | 3 weeks | Free (OAuth providers are free) |
| v1.3 Passwordless | 2 weeks | Varies (SMS: Twilio ~$0.0075/msg) |
| v1.4 Advanced | 2 weeks | Varies (WhatsApp Business API) |

**Note**: Extensions are designed to use your existing infrastructure. No vendor lock-in.

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

auth = SimpleRBAC(database=db)

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

# API keys (v1.0 core feature)
raw_key, api_key = await auth.api_key_service.create_api_key(
    name="Production Service",
    permissions=["user:read", "entity:read"],
    environment="production",  # sk_prod_ prefix
    allowed_ips=["10.0.1.0/24"],
    rate_limit_per_minute=60
)

# Multi-source authentication (v1.0 core feature - DD-035)
from outlabs_auth.dependencies import AuthDeps  # Unified dependency class
deps = AuthDeps(auth=auth, redis=redis)

@app.get("/users")
async def list_users(context = Depends(deps.require_auth())):
    # Accepts JWT, API key, JWT service token, or superuser token
    if not context.has_permission("user:read"):
        raise HTTPException(403)
    return await auth.user_service.list_users()
```

**Limitations:**
- No entity hierarchy
- One role per user
- No tree permissions
- No organizational structure

**Dependencies:**
- MongoDB (via Beanie)
- FastAPI
- Python 3.10+

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
auth = EnterpriseRBAC(database=db)

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

# Multi-source authentication (v1.0 core feature - DD-035)
from outlabs_auth.dependencies import AuthDeps  # Unified dependency class
deps = AuthDeps(auth=auth, redis=redis)

@app.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    context = Depends(deps.require_auth())
):
    # Accepts JWT, API key, JWT service token, or superuser token
    # Works with entity-scoped API keys automatically
    entity = await auth.entity_service.get_entity(entity_id, context)
    return entity
```

**Optional Features (Enable as Needed):**
```python
# Full-featured setup with all options
auth = EnterpriseRBAC(
    database=db,
    redis_url="redis://localhost:6379",
    enable_context_aware_roles=True,  # Opt-in
    enable_abac=True,                 # Opt-in
    enable_caching=True,              # Opt-in (requires Redis)
    enable_audit_log=True             # Opt-in
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
- Redis caching (`enable_caching=True`, requires Redis)
- Entity/root scoping isolation
- Audit logging (`enable_audit_log=True`)

**Limitations:**
- More complex than SimpleRBAC
- Optional features add complexity
- Redis required for caching (optional)
- Steeper learning curve with all features enabled

**Dependencies:**
- MongoDB (via Beanie)
- FastAPI
- Python 3.10+
- Redis (optional, only if `enable_caching=True`)

**Performance (Updated v1.4):**
- Permission check: ~10ms (uncached with closure table), ~5ms (cached)
- **Tree permission check: ~10ms (O(1) via closure table - DD-036)** - 20x improvement
- **API key validation: ~50-100ms (argon2id hashing - DD-028)**
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
- Redis caching ⭕ (enable_caching=True)
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
- Audit logging ⭕ (enable_audit_log=True)
- Redis caching ⭕ (enable_caching=True)
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
- Redis caching ⭕ (enable_caching=True)
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

auth = SimpleRBAC(database=db)

# Users have one role
await auth.user_service.assign_role(user.id, manager_role.id)

# AFTER (EnterpriseRBAC - basic setup)
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(database=db)

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
- **Redis caching**: Performance is critical (high traffic)
- **Entity isolation**: Need strict root-entity boundaries
- **Audit logging**: Need comprehensive audit trails

**Migration Steps:**
1. Add feature flags to existing `EnterpriseRBAC` configuration
2. Set up Redis if enabling caching
3. Update roles to use context-aware permissions (if needed)
4. Add ABAC conditions to permissions (if needed)
5. Test thoroughly before production deployment

**Effort**: ~1-2 days per feature

**Example:**
```python
# BEFORE (EnterpriseRBAC - basic)
auth = EnterpriseRBAC(database=db)

# AFTER (EnterpriseRBAC - with optional features)
auth = EnterpriseRBAC(
    database=db,
    redis_url="redis://localhost:6379",
    enable_context_aware_roles=True,  # Enable as needed
    enable_abac=True,                 # Enable as needed
    enable_caching=True,              # Enable as needed
    enable_audit_log=True             # Enable as needed
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

## Performance Comparison (Updated v1.4)

### Permission Check Latency

| Preset | Basic Check | Tree Check | Cached Check | API Key | JWT Service Token |
|--------|-------------|------------|--------------|---------|-------------------|
| SimpleRBAC | ~10ms | N/A | N/A | ~50-100ms | ~0.5ms |
| EnterpriseRBAC (basic) | ~10ms | **~10ms (O(1))** | ~10ms | ~50-100ms | ~0.5ms |
| EnterpriseRBAC (cached) | ~5ms | **~5ms** | ~5ms | ~50-100ms | ~0.5ms |
| EnterpriseRBAC (ABAC) | ~10ms + 5-10ms/condition | **~10ms** + 5-10ms/condition | ~5ms + 5-10ms/condition | ~50-100ms | ~0.5ms |

**Key Improvements (v1.4)**:
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

*Benchmarks on MacBook Pro M1, MongoDB local, Redis local (when caching enabled)*

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
- ⭐⭐⭐ Best performance when caching enabled

**Cons:**
- ⭐ More complex than SimpleRBAC
- ⭐ Slower permission checks than SimpleRBAC (without caching)
- ⭐ Steeper learning curve with all features enabled
- ⭐ Requires Redis for caching (optional)

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
| Audit requirements | EnterpriseRBAC | + audit logging |

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
- ⭕ **Audit logging**: Compliance or audit trail requirements

**Pro Tip**: Start with basic EnterpriseRBAC (just hierarchy) and enable optional features incrementally as needed!

---

## Next Steps

1. **Chosen a preset?** → See [API_DESIGN.md](API_DESIGN.md) for code examples
2. **Ready to implement?** → See [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)
3. **Migrating from API?** → See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
4. **Have questions?** → See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)

---

**Last Updated**: 2026-01-22 (DD-050 role scoping, DD-051 entity type configuration with frontend UI)
**Next Review**: After Phase 1 implementation
