# OutlabsAuth Library - Design Decisions Log

**Version**: 1.4
**Date**: 2025-01-14
**Purpose**: Document key architectural decisions and trade-offs

---

## Decision Log Format

Each decision follows this template:

```markdown
## DD-NNN: Decision Title

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Rejected | Superseded
**Deciders**: Who made the decision
**Context**: Why this decision was needed

### Options Considered
1. Option A
   - Pros: ...
   - Cons: ...

2. Option B
   - Pros: ...
   - Cons: ...

### Decision
What we chose and why

### Consequences
- Positive: ...
- Negative: ...
- Neutral: ...

### Related Decisions
- Links to related decisions
```

---

## DD-001: Library vs Centralized Service

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Need to simplify deployment and reduce operational complexity

### Options Considered

1. **Keep Centralized API**
   - Pros: Single source of truth, easy updates, centralized logging
   - Cons: Extra service to maintain, network latency, single point of failure

2. **Convert to Library**
   - Pros: No separate service, faster (in-process), easier development, offline work
   - Cons: Updates require app redeployment, no cross-app user sharing

3. **Hybrid Approach**
   - Pros: Best of both worlds
   - Cons: Complexity, confusing for developers

### Decision
Convert to library. Each application embeds auth directly.

**Reasoning**:
- We rarely need cross-application auth
- Operational simplicity more important than centralization
- Faster permission checks (no network calls)
- Better developer experience

### Consequences
- **Positive**: Simpler deployment, faster auth, offline development
- **Negative**: Each app has its own user database
- **Neutral**: Need good migration guides for existing projects

### Related Decisions
- DD-002 (Multi-tenant support)
- DD-004 (Database choice)

---

## DD-002: Multi-Tenant Support

**Date**: 2025-01-14
**Status**: Accepted (Optional)
**Deciders**: Core team
**Context**: Some apps need multi-tenancy, but most don't

### Options Considered

1. **Always Multi-Tenant**
   - Pros: Consistent model, powerful
   - Cons: Complexity for single-tenant apps, performance overhead

2. **Never Multi-Tenant**
   - Pros: Simplest implementation
   - Cons: Locks out valid use cases

3. **Optional Multi-Tenant**
   - Pros: Flexible, pay-for-what-you-use
   - Cons: Need to maintain two code paths

### Decision
Make multi-tenant optional via configuration.

**Implementation**:
```python
# Single tenant (default)
auth = SimpleRBAC(database=db)

# Multi-tenant
auth = SimpleRBAC(database=db, multi_tenant=True)
```

**Reasoning**:
- Most of our apps are single-tenant
- Don't force complexity on simple use cases
- Enable it for apps that need it

### Consequences
- **Positive**: Flexibility, simpler for most cases
- **Negative**: Two code paths to test
- **Neutral**: Models include optional `tenant_id` field

### Related Decisions
- DD-001 (Library approach)
- DD-003 (Preset architecture)

---

## DD-003: Preset Architecture (Simple, Hierarchical, Full)

**Date**: 2025-01-14
**Status**: Superseded by DD-015
**Deciders**: Core team
**Context**: Need gradual complexity without feature explosion

### Options Considered

1. **Single Monolithic Class**
   - Pros: Everything in one place
   - Cons: Overwhelming for beginners, hard to understand

2. **Feature Flags**
   - Pros: Single class with toggles
   - Cons: Complex configuration, all features always loaded

3. **Preset Classes**
   - Pros: Clear progression, pay-for-what-you-use
   - Cons: Code duplication, need inheritance strategy

4. **Modular Plugin System**
   - Pros: Maximum flexibility
   - Cons: High complexity, confusing API

### Decision (Original)
Three preset classes that build on each other:
- `SimpleRBAC`: Basic RBAC
- `HierarchicalRBAC`: + Entity hierarchy
- `FullFeatured`: + Advanced features

**Status**: This decision was superseded by DD-015 after colleague feedback identified the "middle child problem."

### Related Decisions
- DD-001 (Library approach)
- DD-015 (Two-preset architecture - SUPERSEDES THIS)

---

## DD-004: Database Support (MongoDB First)

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Need to choose primary database, possibly support others

### Options Considered

1. **MongoDB Only**
   - Pros: Already using Beanie, simple implementation
   - Cons: Limits some users

2. **PostgreSQL Only**
   - Pros: SQL familiarity, ACID guarantees
   - Cons: Don't know it as well, more complex queries

3. **Database Agnostic (SQLAlchemy + Beanie)**
   - Pros: Maximum flexibility
   - Cons: High complexity, abstraction leaks

4. **MongoDB First, PostgreSQL Later**
   - Pros: Ship faster, can add PostgreSQL in v1.1
   - Cons: Delayed PostgreSQL support

### Decision
MongoDB primary, PostgreSQL in future version.

**Reasoning**:
- Team expertise in MongoDB
- Beanie ODM is excellent
- Can ship faster
- Most internal projects use MongoDB anyway
- PostgreSQL support deferred to v1.1

### Consequences
- **Positive**: Faster development, leverage existing knowledge
- **Negative**: No PostgreSQL support initially
- **Neutral**: Architecture should allow PostgreSQL later

### Implementation
```python
# v1.0
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=mongo_client)

# v1.1 (planned)
auth = SimpleRBAC(database=postgres_url, backend="postgres")
```

### Related Decisions
- DD-011 (Beanie ODM)

---

## DD-005: Remove platform_id, Add Optional tenant_id

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Simplify multi-platform → single-platform model

### Options Considered

1. **Keep platform_id**
   - Pros: No migration needed
   - Cons: Adds complexity we don't need

2. **Remove Completely**
   - Pros: Simplest
   - Cons**: Can't support multi-tenant later

3. **Replace with tenant_id (Optional)**
   - Pros: Simpler than platform_id, enables multi-tenant
   - Cons: Still some complexity

### Decision
Remove `platform_id`, add optional `tenant_id`.

**Reasoning**:
- `platform_id` was for multi-platform isolation we don't need
- `tenant_id` is simpler and more standard
- Making it optional keeps single-tenant apps simple

### Schema Changes
```python
# BEFORE
class EntityModel:
    platform_id: str  # Required, always present

# AFTER
class EntityModel:
    tenant_id: Optional[str] = None  # Optional
```

### Consequences
- **Positive**: Simpler model, standard naming
- **Negative**: Requires database migration
- **Neutral**: Models slightly changed

### Migration
See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for details.

### Related Decisions
- DD-001 (Library approach)
- DD-002 (Multi-tenant support)

---

## DD-006: Preserve Entity Hierarchy Design

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Current entity system is elegant and powerful

### Options Considered

1. **Simplify to Flat Structure**
   - Pros: Easier to understand
   - Cons: Loses flexibility, no tree permissions

2. **Keep Current Design**
   - Pros: Proven, powerful, flexible
   - Cons: Some complexity

3. **Redesign from Scratch**
   - Pros: Clean slate
   - Cons: High risk, uncertain outcome

### Decision
Keep current entity hierarchy design:
- Unified entity model (STRUCTURAL + ACCESS_GROUP)
- Flexible entity types (strings, not enums)
- Tree permissions
- Parent-child relationships

**Reasoning**:
- Design is battle-tested
- Provides unique flexibility
- Users like it
- No compelling reason to change

### What We're Keeping
- `EntityClass` enum (STRUCTURAL, ACCESS_GROUP)
- Flexible `entity_type` strings
- Parent-child hierarchy
- Tree permissions (`resource:action_tree`)
- Time-based validity

### Consequences
- **Positive**: Proven design, no re-learning
- **Negative**: Still somewhat complex for simple use cases
- **Neutral**: Good documentation critical

### Related Decisions
- DD-007 (Tree permissions)
- DD-003 (Preset architecture - SimpleRBAC hides this complexity)

---

## DD-007: Keep Tree Permissions

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Tree permissions are powerful but complex

### Options Considered

1. **Remove Tree Permissions**
   - Pros: Simpler permission model
   - Cons: Lose hierarchical access control

2. **Keep Tree Permissions**
   - Pros: Powerful, matches real organizational models
   - Cons: Complex to understand initially

3. **Make Optional/Modular**
   - Pros: Gradual complexity
   - Cons: Confusing when available vs not

### Decision
Keep tree permissions in Hierarchical+ presets.

**Permission Scopes**:
- `resource:action` - Entity-specific
- `resource:action_tree` - All descendants
- `resource:action_all` - Entire app (replaces platform-wide)

**Reasoning**:
- Tree permissions solve real problems
- Matches how organizations work
- SimpleRBAC users never see them
- HierarchicalRBAC users need them

### Consequences
- **Positive**: Powerful hierarchical access control
- **Negative**: Need excellent documentation
- **Neutral**: Hidden from SimpleRBAC users

### Related Decisions
- DD-006 (Entity hierarchy)
- DD-003 (Preset architecture)

---

## DD-008: Preserve Context-Aware Roles

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Context-aware roles are unique and powerful

### Options Considered

1. **Remove Context-Aware Roles**
   - Pros: Simpler role model
   - Cons: Lose unique feature, role explosion

2. **Keep in FullFeatured Only**
   - Pros: Advanced feature for advanced users
   - Cons: None, this makes sense

3. **Always Available**
   - Pros: Consistent
   - Cons: Confusing for simple use cases

### Decision
Keep context-aware roles in FullFeatured preset.

**Design**:
```python
role = {
    "permissions": ["entity:read"],  # Default
    "entity_type_permissions": {     # Context-specific
        "region": ["entity:manage_tree"],
        "office": ["entity:read"],
    }
}
```

**Reasoning**:
- Unique feature that prevents role explosion
- Matches real-world scenarios
- Not needed for simple RBAC
- FullFeatured users benefit greatly

### Consequences
- **Positive**: Powerful feature preserved
- **Negative**: Adds complexity to FullFeatured
- **Neutral**: Hidden from Simple/Hierarchical users

### Related Decisions
- DD-003 (Preset architecture)
- DD-006 (Entity hierarchy)

---

## DD-009: ABAC in FullFeatured Only

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: ABAC conditions are powerful but add complexity

### Options Considered

1. **No ABAC Support**
   - Pros: Simpler
   - Cons: Can't handle attribute-based rules

2. **ABAC Everywhere**
   - Pros: Consistent
   - Cons: Overkill for simple use cases

3. **ABAC in FullFeatured**
   - Pros: Available when needed, hidden when not
   - Cons: None

### Decision
ABAC conditions only in FullFeatured preset.

**Features**:
- Conditions on permissions
- Policy evaluation engine
- Context building
- Operator support (EQUALS, LESS_THAN, IN, etc.)

**Reasoning**:
- Not everyone needs ABAC
- Adds significant complexity
- Perfect for FullFeatured users
- SimpleRBAC stays simple

### Consequences
- **Positive**: Powerful conditional access when needed
- **Negative**: More code to maintain
- **Neutral**: Clear separation of complexity levels

### Related Decisions
- DD-003 (Preset architecture)

---

## DD-010: Redis Caching Optional

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Caching improves performance but adds dependency

### Options Considered

1. **Always Require Redis**
   - Pros: Best performance
   - Cons: Extra dependency, deployment complexity

2. **Never Use Redis**
   - Pros: Simpler
   - Cons: Performance impact

3. **Optional Redis with In-Memory Fallback**
   - Pros: Best of both, graceful degradation
   - Cons: Two cache implementations

### Decision
Redis optional with in-memory fallback.

**Implementation**:
```python
# No caching
auth = SimpleRBAC(database=db)

# In-memory caching
auth = SimpleRBAC(database=db, enable_caching=True)

# Redis caching
auth = FullFeatured(
    database=db,
    redis_url="redis://localhost:6379"
)
```

**Reasoning**:
- Redis not required for small apps
- In-memory cache sufficient for many use cases
- FullFeatured users get Redis benefits
- Graceful degradation

### Consequences
- **Positive**: Flexible, no forced dependency
- **Negative**: Two cache implementations
- **Neutral**: Performance varies by configuration

### Related Decisions
- DD-003 (Preset architecture)

---

## DD-011: Beanie ODM for MongoDB

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Need ODM for MongoDB, Beanie is current choice

### Options Considered

1. **Beanie ODM**
   - Pros: Modern, async, Pydantic integration
   - Cons: Smaller community than MongoEngine

2. **MongoEngine**
   - Pros: Mature, large community
   - Cons: Sync-only, older design

3. **Motor (Raw)**
   - Pros: No abstraction layer
   - Cons: More boilerplate, no typing

### Decision
Continue using Beanie ODM.

**Reasoning**:
- Already using it successfully
- Async-native
- Great Pydantic integration
- Clean API
- FastAPI native

### Consequences
- **Positive**: Modern, async, type-safe
- **Negative**: Smaller community than MongoEngine
- **Neutral**: Specific to MongoDB

### Related Decisions
- DD-004 (Database choice)

---

## DD-012: FastAPI-First Design

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Library could be framework-agnostic or FastAPI-specific

### Options Considered

1. **Framework Agnostic**
   - Pros: Works with Flask, Django, etc.
   - Cons: Harder to design, less integrated

2. **FastAPI First**
   - Pros: Deep integration, better DX, leverages Depends()
   - Cons: Doesn't work with other frameworks

3. **Core + Adapters**
   - Pros: Best of both
   - Cons: More complex, more code

### Decision
FastAPI-first design, core could work elsewhere.

**Design**:
- Dependency injection using FastAPI's `Depends()`
- Type hints throughout
- Pydantic schemas
- Async/await

**Reasoning**:
- All our projects use FastAPI
- Tighter integration = better experience
- Can add adapters later if needed

### Consequences
- **Positive**: Excellent FastAPI integration
- **Negative**: Not usable with Flask/Django
- **Neutral**: Core logic is framework-independent

### Related Decisions
- DD-011 (Beanie ODM)

---

## DD-013: No OAuth Provider (Initially)

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Should library act as OAuth provider?

### Options Considered

1. **Include OAuth Provider**
   - Pros: Complete auth solution
   - Cons: Significant scope increase

2. **No OAuth Provider**
   - Pros: Focused scope, faster delivery
   - Cons: Users implement their own or use other libraries

3. **OAuth Client Support**
   - Pros: Common need (login with Google)
   - Cons: Still adds complexity

### Decision
No OAuth provider in v1.0. Library handles internal auth only.

**Out of Scope**:
- Acting as OAuth provider
- Social login integration
- SAML support
- LDAP integration

**Reasoning**:
- OAuth provider is complex and separate concern
- Users can add social login themselves
- Many good OAuth libraries exist
- Keep scope manageable

### Consequences
- **Positive**: Focused scope, faster delivery
- **Negative**: Users need separate solution for social login
- **Neutral**: Could add in v2.0 if needed

### Related Decisions
- DD-001 (Library approach)

---

## DD-014: No Admin UI (Initially)

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Should library include admin UI components?

### Options Considered

1. **Include Admin UI**
   - Pros: Complete solution
   - Cons: Opinionated, large scope, maintenance

2. **No Admin UI**
   - Pros: Backend focus, faster delivery
   - Cons: Users build their own

3. **Separate Admin UI Package**
   - Pros: Optional, modular
   - Cons: More repositories to maintain

### Decision
No admin UI in v1.0. Provide examples only.

**What We Provide**:
- Backend library only
- Example admin UIs in example apps
- Documentation on building admin UIs

**Reasoning**:
- UI is opinionated (React? Vue? Svelte?)
- Each app has different design needs
- Maintaining UI is significant work
- Backend is the core value

### Consequences
- **Positive**: Focused on backend, faster delivery
- **Negative**: Users build their own UI
- **Neutral**: Example apps show how to build admin UI

### Future
Could create separate `outlabs-auth-admin-ui` package later.

### Related Decisions
- DD-001 (Library approach)

---

## DD-015: Two Presets Instead of Three

**Date**: 2025-01-14 (Revised)
**Status**: Accepted (Supersedes DD-003)
**Deciders**: Core team
**Context**: Colleague feedback identified "middle child problem" with three presets

### The Problem
Original three-preset design (SimpleRBAC → HierarchicalRBAC → FullFeatured) had an issue:
- Users would likely skip HierarchicalRBAC and jump from Simple → Full
- Middle preset added unnecessary decision fatigue
- Three options when the real question is binary: "Do you need hierarchy?"

### Options Considered

1. **Keep Three Presets**
   - Pros: Already designed
   - Cons: Middle child problem, confusing progression

2. **Two Presets with Feature Flags**
   - Pros: Simpler decision, flexible advanced features
   - Cons: Need to redesign EnterpriseRBAC configuration

3. **Four Presets (Add more)**
   - Pros: More granular
   - Cons: Makes problem worse

### Decision
Two presets only:
- **SimpleRBAC**: Flat structure, single role per user
- **EnterpriseRBAC**: Entity hierarchy (always) + optional advanced features

**Key Design**:
```python
# Simple: For flat structures
auth = SimpleRBAC(database=db)

# Enterprise: Basic (entity hierarchy always included)
auth = EnterpriseRBAC(database=db)

# Enterprise: With optional features
auth = EnterpriseRBAC(
    database=db,
    redis_url="redis://localhost:6379",
    enable_context_aware_roles=True,  # Opt-in
    enable_abac=True,                 # Opt-in
    enable_caching=True,              # Opt-in
    multi_tenant=True,                # Opt-in
    enable_audit_log=True             # Opt-in
)
```

**Reasoning**:
- Binary decision: flat vs hierarchical
- EnterpriseRBAC always includes entity hierarchy + tree permissions
- Advanced features are opt-in via feature flags
- Avoids middle child problem
- Clearer mental model

### Consequences
- **Positive**: Simpler decision tree, clearer options, saved 1 week of development
- **Negative**: Need to redesign configuration, update all documentation
- **Neutral**: Feature flags add some complexity to EnterpriseRBAC

### Timeline Impact
- Saved 1 week by consolidating phases
- 7-8 weeks → 6-7 weeks total

### Related Decisions
- DD-003 (Original three-preset design - SUPERSEDED)
- DD-016 (Optional features via flags)
- DD-017 (Entity hierarchy always enabled)

---

## DD-016: Optional Features via Feature Flags

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team
**Context**: EnterpriseRBAC needs flexible advanced features without complexity explosion

### Options Considered

1. **All Features Always Enabled**
   - Pros: Consistent behavior
   - Cons: Unnecessary complexity for users who don't need it

2. **Separate Classes for Each Feature**
   - Pros: Clear separation
   - Cons: Class explosion, confusing

3. **Feature Flags (Opt-In)**
   - Pros: Pay-for-what-you-use, flexible
   - Cons: Configuration complexity

### Decision
Optional features in EnterpriseRBAC via feature flags (opt-in):
- `enable_context_aware_roles`: Context-aware role permissions
- `enable_abac`: Attribute-based access control
- `enable_caching`: Redis caching (requires Redis)
- `multi_tenant`: Multi-tenant isolation
- `enable_audit_log`: Comprehensive audit logging

**Design Principle**: Start with basic EnterpriseRBAC (entity hierarchy), enable features as needed.

**Reasoning**:
- Users enable only what they need
- Keeps basic EnterpriseRBAC simple
- Advanced users get full power
- Clear opt-in model

### Consequences
- **Positive**: Flexible, pay-for-what-you-use, gradual complexity
- **Negative**: Need to maintain feature flag logic
- **Neutral**: Documentation must be clear about what's core vs optional

### Related Decisions
- DD-015 (Two-preset architecture)
- DD-017 (Entity hierarchy always enabled)

---

## DD-017: Entity Hierarchy Always Enabled in EnterpriseRBAC

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team
**Context**: Define what's core vs optional in EnterpriseRBAC

### Options Considered

1. **Make Entity Hierarchy Optional**
   - Pros: Maximum flexibility
   - Cons: Defeats purpose of Enterprise preset

2. **Entity Hierarchy Always Enabled**
   - Pros: Clear distinction from SimpleRBAC
   - Cons: Users can't disable it

### Decision
EnterpriseRBAC **always includes** these core features:
- Entity hierarchy (STRUCTURAL + ACCESS_GROUP)
- Tree permissions (`resource:action_tree`)
- Multiple roles per user (via entity memberships)
- Entity path traversal
- Access groups

**Reasoning**:
- This is what defines "Enterprise"
- If you don't need hierarchy, use SimpleRBAC
- Clear boundary between presets
- Simplifies decision tree

### Decision Tree
```
Do you need organizational hierarchy?
├─ NO  → SimpleRBAC
└─ YES → EnterpriseRBAC (hierarchy always included)
          ├─ Basic: Just hierarchy + tree permissions
          └─ Advanced: + optional features via flags
```

### Consequences
- **Positive**: Clear preset boundaries, simple decision
- **Negative**: Can't use Enterprise without hierarchy (by design)
- **Neutral**: Users who want hierarchy but not features still get value

### Related Decisions
- DD-015 (Two-preset architecture)
- DD-016 (Optional features)

---

## DD-018: CLI Tools in v1.0

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team
**Context**: Need operational tools for common admin tasks

### Options Considered

1. **No CLI Tools**
   - Pros: Less to build
   - Cons: Users write their own scripts

2. **CLI Tools in v1.1**
   - Pros: Focus on core first
   - Cons: Users need them for production

3. **CLI Tools in v1.0**
   - Pros: Production-ready from day one
   - Cons: Adds to scope

### Decision
Include CLI tools in v1.0 (Week 6).

**Planned Commands**:
```bash
# User management
outlabs-auth users list
outlabs-auth users create --email user@example.com
outlabs-auth users reset-password user@example.com

# Role management
outlabs-auth roles list
outlabs-auth roles create --name admin --permissions user:*

# Entity management (Enterprise only)
outlabs-auth entities list
outlabs-auth entities create --name engineering --type department

# Health checks
outlabs-auth health check
outlabs-auth health migrations

# Permissions debugging
outlabs-auth permissions explain user@example.com entity:update
```

**Reasoning**:
- Production deployments need admin tools
- Common operations should be scriptable
- Improves developer experience
- Not much extra work (1-2 days)

### Consequences
- **Positive**: Production-ready from v1.0, better DX
- **Negative**: Adds to initial scope
- **Neutral**: Week 6 has capacity for this

### Related Decisions
- DD-019 (Health checks)
- DD-020 (Permission explainer)

---

## DD-019: Health Check System

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team
**Context**: Production deployments need health monitoring

### Options Considered

1. **No Built-in Health Checks**
   - Pros: Less to build
   - Cons: Users implement their own

2. **Basic Health Checks**
   - Pros: Essential monitoring
   - Cons: Minimal scope

3. **Comprehensive Health System**
   - Pros: Production-ready
   - Cons: More work

### Decision
Comprehensive health check system in v1.0 (Week 6).

**Features**:
```python
# HTTP endpoint
@app.get("/health")
async def health():
    return await auth.health.check_all()

# Programmatic checks
health = await auth.health.check_database()
health = await auth.health.check_redis()  # If caching enabled
health = await auth.health.check_migrations()

# CLI commands
outlabs-auth health check
outlabs-auth health migrations
```

**Health Checks**:
- Database connectivity
- Redis connectivity (if enabled)
- Schema migrations status
- Index status
- Performance metrics

**Reasoning**:
- Essential for production
- Kubernetes/Docker health probes
- Early problem detection
- Low implementation cost (1 day)

### Consequences
- **Positive**: Production-ready monitoring
- **Negative**: Small scope addition
- **Neutral**: Fits naturally into Week 6

### Related Decisions
- DD-018 (CLI tools)

---

## DD-020: Permission Explainer Debugger

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team
**Context**: Debugging permission issues is hard

### Options Considered

1. **No Debugging Tools**
   - Pros: Less to build
   - Cons: Hard to debug permissions

2. **Basic Logging**
   - Pros: Simple
   - Cons: Not structured

3. **Permission Explainer**
   - Pros: Clear explanation of permission resolution
   - Cons: More work

### Decision
Include permission explainer/debugger in v1.0 (Week 6).

**Features**:
```python
# Programmatic
explanation = await auth.permissions.explain(
    user_id=user.id,
    permission="entity:update",
    entity_id=entity.id
)

# Returns:
{
    "allowed": True,
    "source": "role:department_manager",
    "entity": "engineering",
    "resolution_path": [
        "User membership in 'engineering'",
        "Role 'department_manager' grants 'entity:update'",
        "Permission allowed"
    ],
    "tree_permissions_checked": ["platform > organization > engineering"],
    "time_ms": 23.4
}

# CLI
outlabs-auth permissions explain user@example.com entity:update --entity engineering
```

**Reasoning**:
- Permission debugging is common pain point
- Improves developer experience
- Helps understand complex hierarchies
- Low cost (1-2 days)

### Consequences
- **Positive**: Easier debugging, better DX, great for learning
- **Negative**: Small scope addition
- **Neutral**: Naturally fits with permission system

### Related Decisions
- DD-018 (CLI tools)
- DD-007 (Tree permissions)

---

## DD-021: Comprehensive Production Guides

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team
**Context**: Library needs production deployment documentation

### Options Considered

1. **Basic Documentation Only**
   - Pros: Less writing
   - Cons: Users struggle in production

2. **Comprehensive Production Guides**
   - Pros: Production-ready from day one
   - Cons: More documentation work

### Decision
Create comprehensive production guides in Week 7:
- **SECURITY.md**: Security hardening, best practices, threat model
- **TESTING_GUIDE.md**: Testing utilities, patterns, fixtures
- **DEPLOYMENT_GUIDE.md**: Scaling, performance, production deployment
- **ERROR_HANDLING.md**: Exception hierarchy, error patterns

**Content**:
- SECURITY.md: JWT security, rate limiting, password policies, secret management, threat model, security checklist
- TESTING_GUIDE.md: Test fixtures, unit testing, integration testing, mocking, CI/CD patterns
- DEPLOYMENT_GUIDE.md: Docker, Kubernetes, scaling patterns, performance tuning, monitoring, backup/restore
- ERROR_HANDLING.md: Exception hierarchy, error codes, error handling patterns, logging

**Reasoning**:
- Users need this for production deployments
- Security is critical for auth library
- Testing patterns improve adoption
- Deployment guide reduces support burden

### Timeline Impact
These fit naturally into Week 7 (Documentation + Polish).

### Consequences
- **Positive**: Production-ready documentation, reduces support burden, improves trust
- **Negative**: More documentation to write and maintain
- **Neutral**: Week 7 allocated for documentation

### Related Decisions
- DD-001 (Library approach)
- DD-019 (Health checks)

---

## DD-022: OAuth as Optional Extension (v1.2)

**Date**: 2025-01-14 (Post-v1.0)
**Status**: Accepted
**Deciders**: Core team
**Context**: Social login is valuable but not needed for v1.0

### Options Considered

1. **Include OAuth in v1.0**
   - Pros: Complete solution from day one
   - Cons: Delays v1.0 release, adds complexity, most internal apps don't need it

2. **OAuth in v1.2 as Extension**
   - Pros: Focused v1.0, flexible adoption, works with both presets
   - Cons: Users wait for social login support

3. **Never Support OAuth**
   - Pros: Simplest
   - Cons: Common feature request, competitive disadvantage

### Decision
Implement OAuth/social login as optional extension in v1.2 (Week 10-12).

**Features**:
- Provider abstraction (Google, Facebook, Apple, GitHub, Microsoft)
- Account linking and unlinking
- Auto-registration flow
- Email verification before linking
- State validation and PKCE security

**Design**:
```python
oauth_providers = {
    "google": GoogleProvider(client_id=..., client_secret=...),
    "facebook": FacebookProvider(client_id=..., client_secret=...)
}

auth = SimpleRBAC(
    database=db,
    oauth_providers=oauth_providers
)
```

**Reasoning**:
- v1.0 focuses on core authentication (email/password)
- OAuth is common but not universal requirement
- Extension model allows adoption when needed
- Works equally with SimpleRBAC and EnterpriseRBAC

### Consequences
- **Positive**: Focused v1.0, flexible adoption, no forced dependencies
- **Negative**: Users wait 3 weeks after v1.0 for social login
- **Neutral**: Extension architecture proves out with real feature

### Related Decisions
- DD-013 (No OAuth provider initially - updated)
- DD-023 (Notification handler - needed for OAuth welcome emails)
- DD-026 (Account linking strategy)

---

## DD-023: Notification Handler Abstraction (v1.1)

**Date**: 2025-01-14 (Post-v1.0)
**Status**: Accepted
**Deciders**: Core team
**Context**: Auth events need to trigger notifications, but apps have their own notification infrastructure

### Options Considered

1. **Built-in Email/SMS Service**
   - Pros: Works out of the box
   - Cons: Vendor lock-in, forces specific providers, most apps already have notification systems

2. **No Notification Support**
   - Pros: Simplest
   - Cons: Critical auth flows need notifications (password reset, magic links)

3. **Pluggable Notification Handler**
   - Pros: No vendor lock-in, works with existing infrastructure, flexible
   - Cons: Requires user configuration

### Decision
Implement pluggable notification system in v1.1 (Week 8-9).

**Design**:
```python
class NotificationHandler(ABC):
    @abstractmethod
    async def send(self, event: NotificationEvent) -> bool:
        pass

# Pre-built handlers
- WebhookHandler: Send to webhook endpoint
- QueueHandler: Push to message queue
- CallbackHandler: Direct function callback
- CompositeHandler: Combine multiple handlers
```

**Usage**:
```python
notification_handler = WebhookHandler(
    webhook_url="https://api.internal/notifications",
    headers={"X-API-Key": ...}
)

auth = SimpleRBAC(
    database=db,
    notification_handler=notification_handler
)
```

**Reasoning**:
- Apps already have notification infrastructure (email services, SMS gateways)
- Don't force specific vendors (SendGrid, Twilio, etc.)
- Flexible: webhook, queue, or direct callback
- Required before OAuth (welcome emails) and passwordless (magic links, OTP)

### Consequences
- **Positive**: No vendor lock-in, works with existing infrastructure, highly flexible
- **Negative**: Requires configuration, no "just works" for beginners
- **Neutral**: NoOpHandler default for testing

### Related Decisions
- DD-022 (OAuth - needs notification handler)
- DD-024 (Passwordless - needs notification handler)
- DD-025 (No built-in email/SMS service)

---

## DD-024: Passwordless Authentication (v1.3)

**Date**: 2025-01-14 (Post-v1.0)
**Status**: Accepted
**Deciders**: Core team
**Context**: Growing demand for passwordless authentication methods

### Options Considered

1. **No Passwordless Support**
   - Pros: Simpler codebase
   - Cons: Missing modern auth methods, competitive disadvantage

2. **Magic Links Only**
   - Pros: Simpler than OTP
   - Cons: Incomplete (no SMS option)

3. **Magic Links + OTP (Multiple Channels)**
   - Pros: Complete solution, flexible channels
   - Cons: More complexity, requires notification system

### Decision
Implement magic links and OTP in v1.3 (Week 13-14).

**Features**:
- Magic links (email)
- Email OTP (6-digit codes)
- SMS OTP
- WhatsApp/Telegram OTP (v1.4)
- Challenge management system
- Rate limiting and abuse prevention

**Design**:
```python
# Magic links
await auth.passwordless_service.send_magic_link("user@example.com")
tokens = await auth.passwordless_service.verify_magic_link(code)

# OTP
await auth.passwordless_service.send_otp("+1234567890", channel="sms")
tokens = await auth.passwordless_service.verify_otp("+1234567890", code)
```

**Reasoning**:
- Passwordless is growing trend (better UX, security)
- Magic links are common for onboarding
- OTP enables phone-based authentication
- Notification system (v1.1) is prerequisite

### Consequences
- **Positive**: Modern auth methods, better UX, competitive feature
- **Negative**: Added complexity, requires notification handler
- **Neutral**: Optional feature, doesn't affect core

### Related Decisions
- DD-023 (Notification handler - prerequisite)
- DD-025 (No built-in SMS - use notification handler)

---

## DD-025: No Built-in Email/SMS Service

**Date**: 2025-01-14 (Post-v1.0)
**Status**: Accepted
**Deciders**: Core team
**Context**: How to handle email and SMS delivery for auth events

### Options Considered

1. **Built-in SMTP + SMS Gateway**
   - Pros: Works out of the box
   - Cons: Vendor lock-in, forces specific services, duplicate infrastructure

2. **Require External Configuration**
   - Pros: Works with any provider
   - Cons: More setup, not "just works"

3. **Notification Handler Abstraction**
   - Pros: Maximum flexibility, no vendor lock-in
   - Cons: Requires understanding of pattern

### Decision
No built-in email/SMS services. Use NotificationHandler abstraction.

**Approach**:
- Library emits NotificationEvent objects
- User provides NotificationHandler implementation
- Handler delivers via their existing infrastructure
- Pre-built handlers for common patterns (webhook, queue)

**Example**:
```python
# Library code (emits event)
await notification_handler.send(NotificationEvent(
    type="magic_link",
    recipient="user@example.com",
    data={"link": "https://...", "expires_in_minutes": 15}
))

# User code (handles event)
class MyNotificationHandler(NotificationHandler):
    async def send(self, event: NotificationEvent):
        if event.type == "magic_link":
            await my_email_service.send_magic_link(
                event.recipient,
                event.data["link"]
            )
```

**Reasoning**:
- Apps already have email/SMS infrastructure
- SendGrid, AWS SES, Twilio, etc. - many options
- Don't force specific vendor
- Don't duplicate functionality
- More flexible than built-in

### Consequences
- **Positive**: No vendor lock-in, works with any provider, no duplicate infrastructure
- **Negative**: Not "just works" for beginners
- **Neutral**: Pre-built handlers reduce friction

### Related Decisions
- DD-023 (Notification handler abstraction)
- DD-024 (Passwordless - needs notifications)

---

## DD-026: Social Account Linking Strategy

**Date**: 2025-01-14 (Post-v1.0)
**Status**: Accepted
**Deciders**: Core team
**Context**: How to handle users with multiple auth methods (email + social)

### Options Considered

1. **Separate Accounts**
   - Pros: Simple, no security concerns
   - Cons: Poor UX, duplicate users

2. **Auto-Link by Email (Always)**
   - Pros: Good UX, single user identity
   - Cons: Security risk if email not verified

3. **Auto-Link by Verified Email Only**
   - Pros: Good UX, secure
   - Cons: Slightly more complex

### Decision
Auto-link by verified email only.

**Rules**:
- If social account email is verified by provider: auto-link
- If social account email is unverified: create separate account, require email verification before linking
- Users can manually link accounts from settings
- Unlinking requires at least one auth method remaining

**Design**:
```python
# OAuth flow
user, tokens, is_new = await auth.oauth_service.authenticate_with_provider(
    "google",
    code,
    redirect_uri,
    auto_link_by_email=True  # Only if verified
)

# Manual linking
await auth.oauth_service.link_provider_to_user(
    user_id,
    "facebook",
    code,
    redirect_uri
)

# Unlinking
await auth.oauth_service.unlink_provider(user_id, "google")
```

**Security Considerations**:
- Email verification prevents account takeover
- Provider must verify email (Google, Facebook do this)
- Users can link/unlink from settings
- Cannot unlink if no alternative auth method

**Reasoning**:
- Balance UX and security
- Prevents account takeover via unverified social account
- Allows single user identity across auth methods
- Follows industry best practices (Auth0, Firebase, etc.)

### Consequences
- **Positive**: Secure account linking, good UX, prevents takeover
- **Negative**: Complex logic, edge cases to handle
- **Neutral**: Users expect this behavior from modern auth

### Related Decisions
- DD-022 (OAuth support)

---

## DD-027: Extension Roadmap

**Date**: 2025-01-14 (Post-v1.0)
**Status**: Accepted
**Deciders**: Core team
**Context**: Define post-v1.0 extension delivery timeline

### Extension Phases

**Phase 7 (v1.1)**: Notification System
- **Timeline**: Week 8-9 (2 weeks)
- **Deliverables**: NotificationHandler abstraction, pre-built handlers
- **Prerequisite for**: OAuth, passwordless

**Phase 8 (v1.2)**: OAuth/Social Login
- **Timeline**: Week 10-12 (3 weeks)
- **Deliverables**: Provider abstraction, Google/Facebook/Apple providers
- **Requires**: Notification system (v1.1)

**Phase 9 (v1.3)**: Passwordless Auth
- **Timeline**: Week 13-14 (2 weeks)
- **Deliverables**: Magic links, Email OTP, SMS OTP
- **Requires**: Notification system (v1.1)

**Phase 10 (v1.4)**: Advanced Features
- **Timeline**: Week 15-16 (2 weeks)
- **Deliverables**: TOTP/MFA, WhatsApp/Telegram OTP, WebAuthn research

### Total Timeline
- **v1.0 Core**: 6-7 weeks (SimpleRBAC + EnterpriseRBAC)
- **Extensions**: 9 weeks (v1.1 through v1.4)
- **Total**: 15-16 weeks

### Decision
Phased delivery of extensions, each independent and optional.

**Principles**:
- Each extension is optional
- Extensions work with both SimpleRBAC and EnterpriseRBAC
- Dependencies: v1.2 and v1.3 require v1.1 (notifications)
- Can skip extensions you don't need

**Reasoning**:
- Deliver v1.0 quickly (6-7 weeks)
- Extensions don't block v1.0
- Users adopt extensions as needed
- Validates extension architecture with real features

### Consequences
- **Positive**: Focused v1.0, flexible adoption, no forced features
- **Negative**: Extended timeline for full feature set
- **Neutral**: Extension model must work well (proven with v1.1-v1.4)

### Related Decisions
- DD-022 (OAuth - v1.2)
- DD-023 (Notifications - v1.1)
- DD-024 (Passwordless - v1.3)

---

## DD-028: API Key System for Service Authentication (Core v1.0)

**Date**: 2025-01-14
**Status**: Accepted (Core Feature)
**Deciders**: Core team
**Context**: Need service-to-service authentication for API integrations and webhooks

### Options Considered

1. **No API Key Support**
   - Pros: Simpler codebase
   - Cons: No way to authenticate services, missing essential feature

2. **JWT Service Tokens**
   - Pros: Reuse existing JWT infrastructure
   - Cons: Less flexible, harder to revoke, not standard for API keys

3. **API Key System (Stripe-style)**
   - Pros: Industry standard, easy to use, flexible permissions
   - Cons: Additional models and services to maintain

4. **OAuth Client Credentials**
   - Pros: Standards-based
   - Cons: Too complex for simple use cases, overkill

### Decision
Implement full API key system in core v1.0 (Phase 2 - SimpleRBAC).

**Features**:
- Prefixed keys (8 characters): `sk_prod_`, `sk_stag_`, `sk_dev_`, `sk_test_`
- argon2id hashing (NOT SHA256 - security requirement)
- Key lifecycle: create, rotate, revoke
- Permission-based access control
- IP whitelisting
- Rate limiting per key
- Usage tracking and audit logging
- Automatic revocation on abuse detection

**Design**:
```python
# Create API key
raw_key, key = await auth.api_key_service.create_api_key(
    name="production_api",
    created_by=user_id,
    permissions=["api:read", "api:write"],
    environment="production",
    rate_limit_per_minute=100,
    allowed_ips=["10.0.0.0/8"]
)

# Use in requests
headers = {"X-API-Key": raw_key}
```

**Reasoning**:
- Essential for modern APIs (webhooks, integrations, service-to-service)
- Industry standard pattern (Stripe, GitHub, Twilio all use this)
- Simpler than OAuth for machine-to-machine
- Critical for production deployments
- Should be available from v1.0, not an extension

**Security Requirements**:
- argon2id hashing with time_cost=2, memory_cost=102400, parallelism=8
- Never log raw keys, only prefixes
- Optional expiration (recommended 90 days) with manual rotation API
- IP whitelisting strictly enforced
- Temporary lock after 10 failed attempts in 10 minutes (30-min cooldown)

### Consequences
- **Positive**: Production-ready from day one, industry standard, enables integrations
- **Negative**: Adds ~500 LOC to core, requires argon2 dependency
- **Neutral**: Both SimpleRBAC and EnterpriseRBAC support API keys equally

### Timeline Impact
- Add to Phase 2 (SimpleRBAC completion - Week 2)
- ~2 days of development time
- No delay to overall timeline

### Related Decisions
- DD-029 (Multi-source authentication)
- DD-030 (Dependency patterns)
- DD-031 (API key security model)

---

## DD-029: Multi-Source Authentication with AuthContext

**Date**: 2025-01-14
**Status**: Accepted (Core Feature)
**Deciders**: Core team
**Context**: APIs need flexible authentication from multiple sources

### Options Considered

1. **User Authentication Only**
   - Pros: Simplest
   - Cons: Can't handle API keys, service accounts, admin overrides

2. **Separate Auth Per Source**
   - Pros: Clear separation
   - Cons: Code duplication, inconsistent patterns

3. **Unified AuthContext**
   - Pros: Single pattern for all sources, composable, type-safe
   - Cons: More upfront design work

### Decision
Implement unified `AuthContext` supporting multiple authentication sources.

**Auth Sources** (priority order):
1. Superuser (admin override)
2. Service accounts (internal services)
3. API keys (external integrations)
4. Users (JWT tokens)
5. Anonymous (optional)

**Design**:
```python
class AuthContext(BaseModel):
    source: AuthSource  # USER, API_KEY, SERVICE, SUPERUSER, ANONYMOUS
    identity: str
    permissions: List[str]
    is_superuser: bool
    metadata: Dict[str, Any]
    rate_limit_remaining: Optional[int]

# Usage in endpoints
@app.get("/api/data")
async def get_data(ctx: AuthContext = Depends(multi.permission("data:read"))):
    # Works with users, API keys, or service accounts
    if ctx.source == AuthSource.API_KEY:
        await log_api_usage(ctx.metadata["key_name"])
    return data
```

**Reasoning**:
- APIs need flexibility (webhooks use API keys, admins use JWT, services use service tokens)
- Single pattern easier to test and maintain
- Priority chain prevents ambiguity
- Type-safe via Pydantic
- Composable via FastAPI dependencies

### Consequences
- **Positive**: Flexible, type-safe, single pattern, easy to test
- **Negative**: More complex than user-only auth
- **Neutral**: Hidden complexity in `get_context()` method

### Related Decisions
- DD-028 (API keys)
- DD-030 (Dependency patterns)
- DD-012 (FastAPI-first design)

---

## DD-030: FastAPI Dependency Injection Patterns

**Date**: 2025-01-14
**Status**: Accepted (Core Feature)
**Deciders**: Core team
**Context**: Need simple, composable way to protect endpoints

### Options Considered

1. **Decorators**
   - Pros: Familiar pattern from Flask
   - Cons: Less flexible, harder to compose, not FastAPI-native

2. **Middleware**
   - Pros: Centralized auth logic
   - Cons: Harder to test, less granular, all-or-nothing

3. **Dependency Injection (FastAPI Depends)**
   - Pros: Native FastAPI, composable, testable, type-safe
   - Cons: Requires understanding of dependency injection

### Decision
Use FastAPI dependency injection with factory classes.

**Dependency Factories**:
- `SimpleDeps`: Basic patterns (authenticated, requires, role)
- `MultiSourceDeps`: Multi-source auth with AuthContext
- `GroupDeps`: Group-based authorization
- `EntityDeps`: Entity-scoped permissions

**Design**:
```python
# Simple usage
require = SimpleDeps(auth)

@app.delete("/users/{id}")
async def delete_user(id: str, user = require.requires("user:delete")):
    return await service.delete(id)

# Multi-source
multi = MultiSourceDeps(auth)

@app.get("/api/data")
async def get_data(ctx: AuthContext = multi.permission("data:read")):
    return data

# Combine requirements
@app.post("/admin/action")
async def admin_action(
    user = require.requires("admin:write"),
    is_admin = require.role("admin"),
    ctx: AuthContext = multi.source(AuthSource.USER)
):
    # Must have permission + role + be a user (not API key)
    return {"performed": True}
```

**Reasoning**:
- FastAPI-native approach (leverages Depends())
- Dead simple for common cases: `user = require.user`
- Composable for complex requirements
- Type-safe with full IDE support
- Easy to test (override dependencies in tests)
- Declarative (function signature declares requirements)

### Consequences
- **Positive**: Excellent DX, type-safe, testable, composable
- **Negative**: Requires understanding dependency injection
- **Neutral**: Slightly different from Flask decorators

### Testing Benefits
```python
# Easy to mock
def test_endpoint(client, mock_auth):
    mock_auth(permissions=["data:read"])
    response = client.get("/api/data")
    assert response.status_code == 200
```

### Related Decisions
- DD-029 (Multi-source auth)
- DD-012 (FastAPI-first design)

---

## DD-031: API Key Security Model

**Date**: 2025-01-14
**Status**: Accepted (Core Feature)
**Deciders**: Core team, Security review
**Context**: API keys are sensitive credentials requiring strong security

### Options Considered

1. **SHA256 Hashing**
   - Pros: Fast, widely supported
   - Cons: Too fast = vulnerable to brute force attacks

2. **bcrypt**
   - Pros: Battle-tested, slow hashing
   - Cons: Limited output size, older algorithm

3. **argon2id**
   - Pros: Modern, winner of Password Hashing Competition 2015, resistant to side-channel attacks
   - Cons: Requires additional dependency

### Decision
Use argon2id for API key hashing with specific parameters.

**Security Requirements**:

1. **Hashing**: argon2id with recommended parameters
   ```python
   argon2.using(
       time_cost=2,        # Iterations
       memory_cost=102400, # 100 MB memory
       parallelism=8       # Threads
   ).hash(key)
   ```

2. **Key Format**: 8-character prefix + 32 bytes random
   - `sk_prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
   - Prefix identifies environment (prod, stag, dev, test)
   - 32 bytes = 256 bits of entropy

3. **Storage**: Never store raw keys
   - Store: key_hash (argon2), key_prefix (8 chars), metadata
   - Never log raw keys (only prefixes)

4. **Rotation**: Optional expiration with manual rotation
   - Optional expiration (recommended 90 days, configurable)
   - Manual rotation API with grace period for zero-downtime
   - Audit all rotations

5. **IP Whitelisting**: Strictly enforced
   - Optional but recommended
   - Support CIDR notation
   - Log all unauthorized access attempts

6. **Temporary Locks** (not permanent revocation):
   - 10 failed validation attempts in 10 minutes → 30-minute cooldown lock
   - Automatic revocation only on expiration (if configured)
   - Log all lock events for abuse detection

7. **Rate Limiting**: Per-key quotas
   - Default: 60/minute, 1000/hour
   - Configurable per key
   - In-memory fallback (no Redis requirement)

8. **Audit Logging**: All key operations
   - Creation, rotation, revocation, usage
   - Include: timestamp, actor, reason, IP
   - Alert on suspicious patterns

**Reasoning**:
- argon2id is state-of-the-art (2015 PHC winner)
- Resistant to GPU attacks, side-channel attacks
- Configurable parameters for future-proofing
- Industry best practice (OWASP recommended)
- 8-character prefix faster to type than Stripe's 12

**Security Checklist**:
```markdown
- [ ] API keys use argon2id hashing (not SHA256)
- [ ] Raw keys never logged or stored
- [ ] Optional expiration configured (recommended ≤90 days)
- [ ] IP whitelisting enabled for production keys
- [ ] Rate limiting per key configured
- [ ] Audit logging captures all key operations
- [ ] Temporary lock on repeated failures (10 in 10 min → 30-min cooldown)
- [ ] Keys scoped to minimum required permissions
```

### Consequences
- **Positive**: Strong security, industry best practices, future-proof
- **Negative**: Requires passlib[argon2] dependency, slower hashing (by design)
- **Neutral**: Security overhead acceptable for auth library

### Related Decisions
- DD-028 (API key system)
- DD-029 (Multi-source auth)

---

## DD-032: Single System with Convenience Wrappers

**Date**: 2025-01-14 (Revised)
**Status**: Accepted (Supersedes Two-Preset Implementation)
**Deciders**: Core team
**Context**: Avoid maintaining duplicate codebases for SimpleRBAC and EnterpriseRBAC

### The Problem
Original design planned two separate implementations:
- Code duplication between SimpleRBAC and EnterpriseRBAC
- Maintenance burden of two codebases
- Complex migration path from Simple → Enterprise
- Testing two separate implementations

### Options Considered

1. **Keep Two Separate Implementations**
   - Pros: Clean separation, no shared complexity
   - Cons: Code duplication, harder to maintain, complex migration

2. **Single System with Feature Flags Only**
   - Pros: One codebase, no duplication
   - Cons: No clear entry points, all features visible in docs

3. **Single System with Thin Convenience Wrappers** (Hybrid)
   - Pros: One codebase, clear entry points, simple migration
   - Cons: Slightly more abstract internal design

### Decision
Single `OutlabsAuth` core implementation with thin convenience wrappers.

**Architecture**:
```python
# Core implementation (single codebase)
class OutlabsAuth:
    def __init__(
        self,
        database: AsyncIOMotorClient,
        enable_entity_hierarchy: bool = False,
        enable_context_aware_roles: bool = False,
        enable_abac: bool = False,
        enable_caching: bool = False,
        multi_tenant: bool = False,
        redis_url: Optional[str] = None,
        **kwargs
    ):
        self.config = AuthConfig(
            enable_entity_hierarchy=enable_entity_hierarchy,
            enable_context_aware_roles=enable_context_aware_roles,
            # ... other features
        )
        # Single unified implementation
        self._init_services()

# Thin convenience wrappers (5-10 LOC each)
class SimpleRBAC(OutlabsAuth):
    """Flat RBAC for simple applications."""
    def __init__(self, database: AsyncIOMotorClient, **kwargs):
        super().__init__(
            database,
            enable_entity_hierarchy=False,
            enable_context_aware_roles=False,
            enable_abac=False,
            **kwargs
        )

class EnterpriseRBAC(OutlabsAuth):
    """Hierarchical RBAC with optional advanced features."""
    def __init__(
        self,
        database: AsyncIOMotorClient,
        enable_context_aware_roles: bool = False,
        enable_abac: bool = False,
        **kwargs
    ):
        super().__init__(
            database,
            enable_entity_hierarchy=True,  # Always enabled
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            **kwargs
        )
```

**Reasoning**:
- Zero code duplication (single core implementation)
- Easy maintenance (one codebase to update)
- Simple migration path (just change class name + add config)
- Clear entry points (SimpleRBAC vs EnterpriseRBAC)
- All features controlled by `AuthConfig`
- Wrappers are documentation (convey intent)

### Consequences
- **Positive**: No code duplication, easy maintenance, simple migration, single test suite
- **Negative**: Slightly more abstract internal design
- **Neutral**: Wrappers are thin (5-10 LOC each), no performance overhead

### Implementation Details
- All services check `auth.config.enable_*` flags
- Entity services no-op if `enable_entity_hierarchy=False`
- ABAC evaluator no-op if `enable_abac=False`
- Documentation shows wrapper usage (hides core class)

### Related Decisions
- DD-015 (Two-preset architecture)
- DD-016 (Optional features via flags)
- DD-017 (Entity hierarchy always in Enterprise)

---

## DD-033: Redis Counters for API Key Metrics

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team, Performance review
**Context**: Database writes on every API request create bottleneck

### The Problem
Original design wrote `usage_count` and `error_count` to MongoDB on every API key request:
```python
# BAD: DB write on every request
api_key.usage_count += 1
await api_key.save()  # Bottleneck!
```

At 1000 req/sec, this means 1000 MongoDB writes/sec just for counters.

### Options Considered

1. **MongoDB Writes on Every Request**
   - Pros: Real-time counts, simple implementation
   - Cons: Massive bottleneck, doesn't scale

2. **In-Memory Counters Only**
   - Pros: Fast, no Redis dependency
   - Cons: Lose counts on restart, no shared state

3. **Redis Counters with Periodic Sync**
   - Pros: Fast, persistent, scales horizontally
   - Cons: Requires Redis for API keys (but already needed for caching)

### Decision
Use Redis counters with periodic sync to MongoDB.

**Architecture**:
```python
# Fast path (every request)
await redis.incr(f"api_key:usage:{key_id}")
await redis.incr(f"api_key:usage:{key_id}:hour:{hour}")

# Slow path (every 5 minutes via background task)
async def sync_api_key_metrics():
    for key_id in active_keys:
        usage = await redis.get(f"api_key:usage:{key_id}")
        await api_key_model.update(key_id, usage_count=usage)
        await redis.set(f"api_key:usage:{key_id}", 0)  # Reset counter
```

**Features**:
- Redis INCR for O(1) counter updates
- Hourly breakdown: `api_key:usage:{key_id}:hour:{hour}`
- Periodic sync to MongoDB (every 5 minutes)
- Background task handles sync automatically
- In-memory fallback if Redis unavailable

**Reasoning**:
- Redis counters are extremely fast (100k+ ops/sec per instance)
- Periodic sync reduces MongoDB load by 99%+
- Hourly breakdowns enable rate limiting
- Analytics still available in MongoDB (slightly delayed)
- In-memory fallback for development without Redis

### Consequences
- **Positive**: Massive performance improvement, scales horizontally, enables rate limiting
- **Negative**: Requires Redis for API keys, counts slightly delayed (up to 5 min)
- **Neutral**: Background task overhead is minimal

### Implementation
- `RedisCounterService` handles all counter operations
- `MongoDBSyncService` runs background sync every 5 minutes
- Graceful degradation to in-memory if Redis unavailable
- Metrics available via `/api/keys/{id}/metrics` endpoint

### Related Decisions
- DD-028 (API key system)
- DD-010 (Redis caching optional)
- DD-037 (Redis Pub/Sub cache invalidation)

---

## DD-034: JWT Service Tokens for Internal Microservices

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team
**Context**: API keys require database lookups; internal services need zero-overhead auth

### The Problem
API keys are great for external integrations, but:
- Require database lookup on every request (even with Redis)
- argon2id hashing adds latency (~50-100ms)
- Internal microservices make thousands of requests/sec

### Options Considered

1. **API Keys Only**
   - Pros: Single authentication method
   - Cons: Database overhead for internal services, doesn't scale

2. **JWT Service Tokens Only**
   - Pros: Stateless, zero DB overhead
   - Cons: Can't revoke individual tokens, not suitable for external use

3. **Both API Keys and JWT Service Tokens**
   - Pros: Right tool for each use case
   - Cons: Two auth methods to maintain

### Decision
Support both API keys (external) and JWT service tokens (internal).

**Use Cases**:
- **API Keys**: External integrations, webhooks, third-party services (need revocation)
- **JWT Service Tokens**: Internal microservices, high-volume service-to-service (need speed)

**Design**:
```python
# Create service token (long-lived JWT)
service_token = await auth.service_token_service.create_service_token(
    name="analytics_service",
    permissions=["analytics:write", "events:read"],
    expires_in_days=365  # Long-lived
)

# Use in requests
headers = {"Authorization": f"Bearer {service_token}"}

# Validation (zero DB hits)
ctx = await auth.get_context(request)
# ctx.source == AuthSource.SERVICE
# ctx.permissions == ["analytics:write", "events:read"]
```

**JWT Claims**:
```json
{
  "sub": "service:analytics_service",
  "type": "service_token",
  "permissions": ["analytics:write", "events:read"],
  "exp": 1735689600,
  "iat": 1704153600
}
```

**Reasoning**:
- Internal services don't need per-request revocation
- JWT validation is 1000x faster than argon2id hashing
- Zero database hits (stateless)
- Suitable for high-volume service-to-service communication
- API keys still available for external use (need revocation)

### Consequences
- **Positive**: Zero overhead for internal services, scales to millions of req/sec
- **Negative**: Can't revoke individual tokens (rotate secret to revoke all)
- **Neutral**: Two auth methods increases API surface slightly

### Security Considerations
- Service tokens are long-lived (30-365 days)
- Cannot revoke individual tokens (only by rotating secret)
- Should only be used for trusted internal services
- Include `type: service_token` claim to prevent confusion with user JWTs
- Audit all service token creation

### Related Decisions
- DD-028 (API key system)
- DD-029 (Multi-source authentication)
- DD-030 (Dependency patterns)

---

## DD-035: Single AuthDeps Class for Dependency Injection

**Date**: 2025-01-14 (Revised)
**Status**: Accepted (Supersedes Multi-Class Pattern)
**Deciders**: Core team
**Context**: Simplify dependency injection patterns

### The Problem
Original design had 5 separate dependency classes:
- `SimpleDeps`: Basic patterns
- `MultiSourceDeps`: Multi-source auth
- `GroupDeps`: Group-based auth
- `EntityDeps`: Entity-scoped auth
- `RateLimitDeps`: Rate limiting

This created confusion:
- Which class to use when?
- How to combine multiple requirements?
- Inconsistent patterns across codebase

### Options Considered

1. **Keep 5 Separate Classes**
   - Pros: Clear separation of concerns
   - Cons: Confusing, hard to discover, inconsistent

2. **Single Monolithic Class**
   - Pros: One place for everything
   - Cons: Large class, many methods

3. **Single Class with Clear Method Names**
   - Pros: Easy to discover, consistent, composable
   - Cons: Single class has many methods (acceptable)

### Decision
Single `AuthDeps` class with clear, descriptive method names.

**Design**:
```python
class AuthDeps:
    """Unified dependency injection for all auth patterns."""

    def __init__(self, auth: OutlabsAuth):
        self.auth = auth

    # Authentication (who are you?)
    def require_auth(self) -> Callable:
        """Require any authenticated user/service."""

    def require_user(self) -> Callable:
        """Require authenticated user (not API key/service)."""

    def require_source(self, source: AuthSource) -> Callable:
        """Require specific auth source."""

    # Authorization (what can you do?)
    def require_permission(self, *permissions: str) -> Callable:
        """Require one or more permissions."""

    def require_all_permissions(self, *permissions: str) -> Callable:
        """Require ALL specified permissions."""

    def require_role(self, *roles: str) -> Callable:
        """Require one or more roles."""

    # Entity-based (where can you do it?)
    def require_entity_access(self, entity_id: str) -> Callable:
        """Require access to specific entity."""

    def require_entity_permission(self, entity_id: str, permission: str) -> Callable:
        """Require permission within specific entity."""

    # Superuser
    def require_superuser(self) -> Callable:
        """Require superuser access."""

# Usage
deps = AuthDeps(auth)

@app.get("/api/data")
async def get_data(ctx: AuthContext = Depends(deps.require_permission("data:read"))):
    return data

@app.delete("/api/data/{id}")
async def delete_data(
    id: str,
    ctx: AuthContext = Depends(deps.require_all_permissions("data:delete", "data:write"))
):
    await service.delete(id)
```

**Reasoning**:
- Single class is easier to discover and learn
- Clear method names convey intent
- Composable via FastAPI's Depends()
- Consistent patterns across entire codebase
- Easy to document and test

### Consequences
- **Positive**: Simple, discoverable, consistent, easy to learn
- **Negative**: Single class with ~10 methods (acceptable)
- **Neutral**: Deprecates old 5-class pattern

### Migration
```python
# OLD (5 classes)
simple = SimpleDeps(auth)
multi = MultiSourceDeps(auth)
entity = EntityDeps(auth)

# NEW (single class)
deps = AuthDeps(auth)
```

### Related Decisions
- DD-030 (Dependency patterns - UPDATED)
- DD-029 (Multi-source auth)
- DD-012 (FastAPI-first design)

---

## DD-036: Closure Table for Tree Permissions

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team, Performance review
**Context**: Recursive tree queries don't scale with deep hierarchies

### The Problem
Original design used recursive queries for tree permissions:
```python
# BAD: N database queries for depth N
async def get_ancestors(entity_id: str) -> List[Entity]:
    ancestors = []
    current = await Entity.get(entity_id)
    while current.parent_id:
        current = await Entity.get(current.parent_id)  # N queries!
        ancestors.append(current)
    return ancestors
```

At depth 10, this means 10 sequential database queries per permission check.

### Options Considered

1. **Keep Recursive Queries**
   - Pros: Simple implementation, easy to understand
   - Cons: O(N) queries for depth N, doesn't scale, latency issues

2. **Materialized Path**
   - Pros: Single query, fast reads
   - Cons: Complex updates, path length limits, harder to query

3. **Closure Table**
   - Pros: O(1) reads, fast updates, unlimited depth, industry standard
   - Cons: Extra table, more storage

### Decision
Use closure table pattern for tree permissions.

**Schema**:
```python
class EntityClosureModel(BaseModel):
    """Stores all ancestor-descendant relationships."""
    ancestor_id: str      # Ancestor entity ID
    descendant_id: str    # Descendant entity ID
    depth: int           # Distance (0 = self, 1 = direct child, etc.)

    class Settings:
        indexes = [
            ("ancestor_id", "descendant_id"),  # Unique
            ("descendant_id", "depth"),        # Find ancestors
            ("ancestor_id", "depth")           # Find descendants
        ]
```

**Queries**:
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

**Maintenance**:
```python
# On entity creation
async def create_entity(entity: Entity):
    await entity.save()

    # Add self-reference (depth 0)
    await EntityClosure(
        ancestor_id=entity.id,
        descendant_id=entity.id,
        depth=0
    ).save()

    # Copy parent's ancestors + add direct parent
    if entity.parent_id:
        parent_closures = await EntityClosure.find(
            {"descendant_id": entity.parent_id}
        ).to_list()

        for closure in parent_closures:
            await EntityClosure(
                ancestor_id=closure.ancestor_id,
                descendant_id=entity.id,
                depth=closure.depth + 1
            ).save()
```

**Reasoning**:
- O(1) ancestor/descendant queries (vs O(N) recursive)
- Industry standard pattern (used by PostgreSQL ltree, Django MPTT)
- Handles unlimited depth
- Fast permission checking across entire hierarchy
- Modest storage overhead (acceptable for auth system)

### Consequences
- **Positive**: Massive performance improvement, O(1) queries, unlimited depth
- **Negative**: Extra table, more complex inserts/moves
- **Neutral**: Storage overhead ~2x entity count (acceptable)

### Performance
- **Before**: 10 sequential queries for depth 10 (~100ms)
- **After**: 1 indexed query for any depth (~5ms)
- **Improvement**: 20x faster

### Related Decisions
- DD-007 (Tree permissions)
- DD-006 (Entity hierarchy)

---

## DD-037: Redis Pub/Sub Cache Invalidation

**Date**: 2025-01-14 (Revised)
**Status**: Accepted
**Deciders**: Core team, Security review
**Context**: TTL-only cache invalidation is too slow for security changes

### The Problem
Original design used 5-minute TTL for permission caching:
```python
# BAD: Revoked permissions cached for up to 5 minutes
await redis.setex(f"perms:{user_id}", 300, json.dumps(permissions))
```

Security issues:
- Revoked user stays cached for 5 minutes
- Removed permission still works for 5 minutes
- No way to invalidate across multiple instances

### Options Considered

1. **TTL Only (No Invalidation)**
   - Pros: Simple, no coordination
   - Cons: Security risk (5-min delay), no immediate revocation

2. **Short TTL (30 seconds)**
   - Pros: Faster invalidation
   - Cons: More database load, still not immediate, cache less effective

3. **Redis Pub/Sub Invalidation**
   - Pros: Immediate invalidation, works across instances, secure
   - Cons: Requires Redis, slightly more complex

### Decision
Use Redis Pub/Sub for immediate cache invalidation across all instances.

**Architecture**:
```python
# On permission change (any instance)
await auth.cache.invalidate_user(user_id)
# Publishes: {"type": "user", "id": user_id}

# All instances subscribe and clear local cache
async def handle_invalidation_event(message):
    data = json.loads(message)
    if data["type"] == "user":
        await local_cache.delete(f"perms:{data['id']}")
        await local_cache.delete(f"roles:{data['id']}")
    elif data["type"] == "entity":
        # Invalidate all users in entity
        await local_cache.delete_pattern(f"perms:*:entity:{data['id']}")
```

**Invalidation Events**:
- `user:permissions_changed` - User permissions/roles changed
- `user:revoked` - User account disabled/deleted
- `role:permissions_changed` - Role permissions changed
- `entity:access_changed` - Entity membership changed
- `api_key:revoked` - API key revoked

**Features**:
- Immediate invalidation (< 100ms across all instances)
- Granular events (only invalidate what changed)
- Fallback to TTL if Pub/Sub fails
- Background subscription with auto-reconnect
- Works with horizontal scaling

**Reasoning**:
- Security requires immediate permission revocation
- 5-minute TTL is too slow for security changes
- Pub/Sub enables real-time invalidation
- Works across multiple instances (horizontal scaling)
- Minimal overhead (publish = ~1ms)

### Consequences
- **Positive**: Immediate security changes, works across instances, better cache hit rate
- **Negative**: Requires Redis, slightly more complex
- **Neutral**: Graceful degradation to TTL-only if Redis unavailable

### Implementation
```python
class AuthCacheService:
    async def start_subscription(self):
        """Start background Pub/Sub listener."""
        await redis.subscribe("auth:invalidate")
        asyncio.create_task(self._listen_for_events())

    async def invalidate_user(self, user_id: str):
        """Invalidate user cache across all instances."""
        await redis.publish("auth:invalidate", json.dumps({
            "type": "user",
            "id": user_id,
            "timestamp": time.time()
        }))
```

### Related Decisions
- DD-010 (Redis caching optional)
- DD-033 (Redis counters)

---

## DD-038: Transport/Strategy Pattern for Authentication

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: Inspired by FastAPI-Users architecture analysis. Need clean separation between how authentication credentials are delivered vs how they are validated.

### The Problem
Current approach mixes credential extraction with validation:
```python
# Mixed concerns - hard to extend
async def authenticate_user(authorization: str):
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        return await validate_jwt(token)
    elif authorization.startswith("ApiKey "):
        key = authorization[7:]
        return await validate_api_key(key)
```

Issues:
- Hard to add new auth methods (service tokens, cookies, etc.)
- Can't reuse JWT validation with different transports
- OpenAPI schema generation is manual
- Testing is complex

### Options Considered

1. **Keep Mixed Approach**
   - Pros: Simple, direct
   - Cons: Hard to extend, tight coupling, poor testability

2. **Transport/Strategy Separation (FastAPI-Users Pattern)**
   - Pros: Clean separation of concerns, extensible, testable
   - Cons: More abstraction layers, learning curve

3. **Plugin System**
   - Pros: Ultimate flexibility
   - Cons: Overcomplicated for our needs, harder to maintain

### Decision
Adopt Transport/Strategy pattern from FastAPI-Users.

**Architecture**:
```python
# Transport: HOW credentials are delivered
class Transport:
    """Defines how to extract credentials from request."""
    async def get_credentials(self, request: Request) -> Optional[str]:
        raise NotImplementedError()

class BearerTransport(Transport):
    async def get_credentials(self, request: Request) -> Optional[str]:
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            return auth[7:]
        return None

class ApiKeyTransport(Transport):
    async def get_credentials(self, request: Request) -> Optional[str]:
        # Check header, query param, or custom location
        return request.headers.get("X-API-Key")

# Strategy: HOW credentials are validated
class Strategy:
    """Defines how to validate credentials and return user."""
    async def authenticate(
        self,
        credentials: str,
        user_manager: UserManager
    ) -> Optional[User]:
        raise NotImplementedError()

class JWTStrategy(Strategy):
    async def authenticate(self, token: str, user_manager) -> Optional[User]:
        payload = decode_jwt(token)
        return await user_manager.get(payload["sub"])

class ApiKeyStrategy(Strategy):
    async def authenticate(self, key: str, user_manager) -> Optional[User]:
        # Find API key, check hash, return user
        api_key = await api_key_service.verify(key)
        return await user_manager.get(api_key.user_id)

# Backend: Combines transport + strategy
class AuthBackend:
    def __init__(self, name: str, transport: Transport, strategy: Strategy):
        self.name = name
        self.transport = transport
        self.strategy = strategy
```

**Usage**:
```python
# Define backends
jwt_backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret=SECRET)
)

api_key_backend = AuthBackend(
    name="api_key",
    transport=ApiKeyTransport(header_name="X-API-Key"),
    strategy=ApiKeyStrategy()
)

service_token_backend = AuthBackend(
    name="service",
    transport=BearerTransport(),
    strategy=ServiceTokenStrategy(secret=SERVICE_SECRET)
)

# Initialize auth with multiple backends
auth = OutlabsAuth(
    database=db,
    auth_backends=[jwt_backend, api_key_backend, service_token_backend]
)
```

**Benefits**:
- Clean separation of concerns
- Easy to add new transports (Cookie, Custom Header)
- Easy to add new strategies (Redis-backed JWT, LDAP)
- Mix-and-match (JWT via Bearer OR Cookie)
- Better testability (test transport and strategy separately)
- Clearer code organization

**Reasoning**:
- FastAPI-Users proves this pattern works well
- Aligns with our multi-source auth vision (DD-029, DD-034)
- Makes adding new auth methods trivial
- Better matches FastAPI's dependency injection model
- Improves testability

### Consequences
- **Positive**: Extensible, testable, clean architecture, easy to add auth methods
- **Negative**: More abstraction layers, slightly more complex initial setup
- **Neutral**: Need to update dependency injection (see DD-039)

### Implementation Plan
**Phase 1** (Week 1):
- Create `Transport` base class and implementations
- Create `Strategy` base class and implementations
- Create `AuthBackend` combinator class

**Phase 2** (Week 2):
- Integrate with `AuthDeps` (DD-039)
- Update user-facing API
- Add tests

### Related Decisions
- DD-029 (Multi-source auth)
- DD-034 (JWT service tokens)
- DD-035 (Single AuthDeps)
- DD-039 (Dynamic dependency injection)

---

## DD-039: Dynamic Dependency Injection with makefun

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: Inspired by FastAPI-Users. Need multiple auth backends to appear correctly in OpenAPI schema without manual duplication.

### The Problem
With multiple auth backends, manually creating dependencies is tedious:
```python
# BAD: Manual dependencies for each combination
async def get_user_jwt(
    token: str = Depends(bearer_scheme),
    user_manager = Depends(get_user_manager)
):
    return await jwt_strategy.authenticate(token, user_manager)

async def get_user_api_key(
    key: str = Depends(api_key_scheme),
    user_manager = Depends(get_user_manager)
):
    return await api_key_strategy.authenticate(key, user_manager)

# How to try both? Manual mess...
```

Issues:
- OpenAPI schema only shows last `Depends()` used
- Manual code for each backend combination
- Hard to support dynamic backend lists
- Users don't see all auth options in Swagger UI

### Options Considered

1. **Manual Dependencies**
   - Pros: Simple, explicit
   - Cons: Doesn't scale, poor OpenAPI support, duplicated code

2. **Dynamic Dependency Generation (makefun)**
   - Pros: Generates correct signatures, OpenAPI works, scales perfectly
   - Cons: Requires `makefun` library, more "magic"

3. **Custom OpenAPI Schema Manipulation**
   - Pros: Full control over schema
   - Cons: Very complex, fragile, bypasses FastAPI's system

### Decision
Use `makefun` library to dynamically generate dependency signatures.

**How It Works**:
```python
from makefun import with_signature
from inspect import Parameter, Signature

class AuthDeps:
    def __init__(self, backends: list[AuthBackend], get_user_manager):
        self.backends = backends
        self.get_user_manager = get_user_manager

    def require_auth(self):
        """Generate dependency that tries all backends."""
        # Build dynamic signature
        parameters = [
            Parameter(
                name="user_manager",
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                default=Depends(self.get_user_manager)
            )
        ]

        # Add parameter for each backend
        for backend in self.backends:
            parameters.extend([
                Parameter(
                    name=f"{backend.name}_credentials",
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    default=Depends(backend.transport.get_credentials)
                ),
                Parameter(
                    name=f"{backend.name}_strategy",
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    default=Depends(lambda: backend.strategy)
                )
            ])

        signature = Signature(parameters)

        # Create dependency with dynamic signature
        @with_signature(signature)
        async def dependency(*args, **kwargs):
            user_manager = kwargs["user_manager"]

            # Try each backend
            for backend in self.backends:
                credentials = kwargs[f"{backend.name}_credentials"]
                strategy = kwargs[f"{backend.name}_strategy"]

                if credentials:
                    user = await strategy.authenticate(credentials, user_manager)
                    if user:
                        return user

            raise HTTPException(status_code=401, detail="Not authenticated")

        return dependency
```

**OpenAPI Result**:
```yaml
# Swagger UI now shows ALL auth options!
security:
  - jwt: []       # Bearer token
  - api_key: []   # X-API-Key header
  - service: []   # Service token
```

**Reasoning**:
- FastAPI-Users proves this works well at scale
- Only way to get correct OpenAPI schema with multiple backends
- Cleaner than manual approach
- Better developer experience (users see all options)
- `makefun` is well-tested library (used by pytest-mock, etc.)

### Consequences
- **Positive**: Perfect OpenAPI schema, scales to any number of backends, clean code
- **Negative**: Adds `makefun` dependency, signature generation is "magical"
- **Neutral**: More advanced Python technique (but well-encapsulated)

### Implementation
**Dependencies**:
```toml
# pyproject.toml
dependencies = [
    "fastapi>=0.100.0",
    "makefun>=1.15.0",  # ← New dependency
    # ...
]
```

**Testing**:
```python
def test_dynamic_signature_generation():
    """Verify dependency has correct signature."""
    backends = [jwt_backend, api_key_backend]
    deps = AuthDeps(backends, get_user_manager)

    dependency = deps.require_auth()
    sig = inspect.signature(dependency)

    # Should have parameters for both backends
    assert "jwt_credentials" in sig.parameters
    assert "api_key_credentials" in sig.parameters
```

### Related Decisions
- DD-038 (Transport/Strategy pattern)
- DD-035 (Single AuthDeps)
- DD-029 (Multi-source auth)

---

## DD-040: Service Lifecycle Hooks

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: Inspired by FastAPI-Users. Users need to inject custom logic (emails, logging, webhooks) without modifying library code.

### The Problem
Users want to add custom logic around auth events:
- Send welcome email after registration
- Log security events (login, password change)
- Trigger webhooks for integrations
- Audit trail for compliance

Current approach requires modifying library code or wrapper functions.

### Options Considered

1. **No Hooks (Users Wrap Functions)**
   - Pros: Simple, no additional API
   - Cons: Breaks library abstraction, hard to maintain, messy code

2. **Event System (Pub/Sub)**
   - Pros: Very flexible, decoupled
   - Cons: Overcomplicated for common use cases, harder to debug

3. **Lifecycle Hooks (FastAPI-Users Pattern)**
   - Pros: Simple, explicit, easy to override, common pattern
   - Cons: Requires subclassing services

### Decision
Add lifecycle hooks to all major services using overrideable async methods.

**Architecture**:
```python
class UserService:
    # === Lifecycle Hooks (Override These) ===

    async def on_after_register(
        self,
        user: User,
        request: Optional[Request] = None
    ) -> None:
        """Called after successful user registration.

        Override to send welcome emails, trigger webhooks, etc.
        """
        pass  # Default: do nothing

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None
    ) -> None:
        """Called after successful login."""
        pass

    async def on_before_delete(
        self,
        user: User,
        request: Optional[Request] = None
    ) -> None:
        """Called before user deletion. Can raise exception to prevent."""
        pass

    async def on_after_delete(
        self,
        user: User,
        request: Optional[Request] = None
    ) -> None:
        """Called after user deletion."""
        pass

    async def on_after_update(
        self,
        user: User,
        update_dict: dict[str, Any],
        request: Optional[Request] = None
    ) -> None:
        """Called after user update."""
        pass

    async def on_after_request_verify(
        self,
        user: User,
        token: str,
        request: Optional[Request] = None
    ) -> None:
        """Called after email verification request."""
        pass

    async def on_after_verify(
        self,
        user: User,
        request: Optional[Request] = None
    ) -> None:
        """Called after successful email verification."""
        pass

    async def on_after_forgot_password(
        self,
        user: User,
        token: str,
        request: Optional[Request] = None
    ) -> None:
        """Called after password reset request."""
        pass

    async def on_after_reset_password(
        self,
        user: User,
        request: Optional[Request] = None
    ) -> None:
        """Called after successful password reset."""
        pass
```

**Usage**:
```python
# Custom service with email integration
class MyUserService(UserService):
    async def on_after_register(self, user: User, request=None):
        # Send welcome email
        await email_service.send_welcome(user.email, user.first_name)

        # Log event
        logger.info(f"New user registered: {user.email}")

        # Trigger webhook
        await webhook_service.trigger("user.registered", {
            "user_id": str(user.id),
            "email": user.email
        })

    async def on_after_login(self, user: User, request=None):
        # Track last login
        await analytics.track("user_login", user.id)

        # Security notification
        if user.security_alerts_enabled:
            await email_service.send_login_notification(user.email)

    async def on_before_delete(self, user: User, request=None):
        # Prevent deletion of admin users
        if user.is_superuser:
            raise ValueError("Cannot delete superuser")

        # Require confirmation
        if not request.state.deletion_confirmed:
            raise ValueError("Deletion not confirmed")

# Initialize with custom service
auth = SimpleRBAC(
    database=db,
    user_service_class=MyUserService  # Use custom class
)
```

**Hook Categories**:

1. **User Lifecycle**
   - `on_after_register` - Welcome emails, analytics
   - `on_after_login` - Security logs, analytics
   - `on_after_update` - Profile change notifications
   - `on_before_delete` / `on_after_delete` - Data cleanup, confirmations

2. **Permission Changes**
   - `on_after_role_assigned` - Notify user of new permissions
   - `on_after_role_removed` - Permission revocation alerts
   - `on_after_permission_changed` - Audit logging

3. **Security Events**
   - `on_after_forgot_password` - Password reset emails
   - `on_after_reset_password` - Password changed notifications
   - `on_after_verify` - Email verification success
   - `on_failed_login` - Brute force detection

4. **API Key Events**
   - `on_api_key_created` - Log new key creation
   - `on_api_key_revoked` - Security notification
   - `on_api_key_locked` - Alert user to suspicious activity

**Reasoning**:
- FastAPI-Users proves this pattern works well in production
- Simple to understand and use
- Doesn't require complex event system
- Easy to test (override and verify hook was called)
- Common pattern in frameworks (Django signals, SQLAlchemy events)

### Consequences
- **Positive**: Easy customization, no library modification needed, testable, production-proven
- **Negative**: Requires subclassing services, hooks can't prevent operations (except `on_before_*`)
- **Neutral**: Need good documentation showing common use cases

### Implementation Plan
**Phase 1** (Week 1-2):
- Add hooks to `UserService`
- Document hook usage patterns
- Add examples (email, webhooks, logging)

**Phase 2** (Week 3):
- Add hooks to `RoleService`
- Add hooks to `PermissionService`
- Add hooks to `ApiKeyService`

**Phase 3** (Week 4):
- Add hooks to `EntityService` (EnterpriseRBAC only)
- Create hook testing guide
- Add integration examples

### Related Decisions
- DD-041 (Router factories - use hooks in default routers)

---

## DD-041: Router Factory Pattern

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: Inspired by FastAPI-Users. Users want quick setup but also flexibility to customize routes.

### The Problem
Users have two needs:
1. **Quick setup**: Get auth working in 5 minutes
2. **Customization**: Customize endpoints, validation, responses

Current approaches:
- **Provide no routers**: Users write everything (slow, error-prone)
- **Provide fixed routers**: Users can't customize without copying code

### Options Considered

1. **No Built-in Routers**
   - Pros: Maximum flexibility
   - Cons: Slow setup, users reinvent the wheel, inconsistent APIs

2. **Fixed Routers (Must Use As-Is)**
   - Pros: Fast setup
   - Cons: Can't customize, users copy-paste to modify

3. **Router Factories (FastAPI-Users Pattern)**
   - Pros: Fast setup AND customizable, users can cherry-pick routes
   - Cons: More API surface to maintain

### Decision
Provide optional router factories that generate FastAPI routers on-demand.

**Architecture**:
```python
# outlabs_auth/routers/auth.py
def get_auth_router(
    auth: OutlabsAuth,
    prefix: str = "/auth",
    tags: list[str] = None
) -> APIRouter:
    """Generate authentication router with login/logout/refresh routes."""
    router = APIRouter(prefix=prefix, tags=tags or ["auth"])

    @router.post("/register")
    async def register(data: RegisterRequest):
        user = await auth.user_service.create_user(
            email=data.email,
            password=data.password,
            **data.extra_fields
        )
        return {"user_id": str(user.id), "email": user.email}

    @router.post("/login")
    async def login(data: LoginRequest):
        tokens = await auth.auth_service.login(
            email=data.email,
            password=data.password
        )
        return tokens

    @router.post("/refresh")
    async def refresh(data: RefreshRequest):
        tokens = await auth.auth_service.refresh_token(data.refresh_token)
        return tokens

    @router.post("/logout")
    async def logout(user = Depends(auth.deps.require_auth())):
        # Invalidate token (Redis strategy)
        return {"message": "Logged out"}

    return router

# outlabs_auth/routers/users.py
def get_users_router(
    auth: OutlabsAuth,
    prefix: str = "/users",
    tags: list[str] = None,
    require_verification: bool = False
) -> APIRouter:
    """Generate user management router."""
    router = APIRouter(prefix=prefix, tags=tags or ["users"])

    @router.get("/me")
    async def get_me(user = Depends(auth.deps.require_auth())):
        return user

    @router.patch("/me")
    async def update_me(
        data: UserUpdateRequest,
        user = Depends(auth.deps.require_auth())
    ):
        updated = await auth.user_service.update_user(user.id, data.dict())
        return updated

    @router.get("/{user_id}")
    async def get_user(
        user_id: str,
        current_user = Depends(auth.deps.require_permission("user:read"))
    ):
        user = await auth.user_service.get_user(user_id)
        return user

    return router

# outlabs_auth/routers/roles.py  (EnterpriseRBAC only)
def get_roles_router(
    auth: EnterpriseRBAC,
    prefix: str = "/roles",
    tags: list[str] = None
) -> APIRouter:
    """Generate role management router."""
    router = APIRouter(prefix=prefix, tags=tags or ["roles"])

    @router.get("/")
    async def list_roles(
        entity_id: Optional[str] = None,
        user = Depends(auth.deps.require_permission("role:read"))
    ):
        roles = await auth.role_service.list_roles(entity_id=entity_id)
        return roles

    @router.post("/")
    async def create_role(
        data: RoleCreateRequest,
        user = Depends(auth.deps.require_permission("role:create"))
    ):
        role = await auth.role_service.create_role(**data.dict())
        return role

    return router
```

**Usage Options**:

**Option 1: Use all default routers (fastest)**
```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router, get_users_router

app = FastAPI()
auth = SimpleRBAC(database=db)

# Include pre-built routers
app.include_router(get_auth_router(auth))
app.include_router(get_users_router(auth))

# Done! You have /auth/login, /auth/register, /users/me, etc.
```

**Option 2: Customize routers**
```python
# Use some defaults, customize others
app.include_router(get_auth_router(auth, prefix="/api/auth", tags=["authentication"]))

# Custom user router
router = APIRouter(prefix="/api/users")

@router.get("/me")
async def get_me(user = Depends(auth.deps.require_auth())):
    # Custom response format
    return {
        "data": user,
        "meta": {"version": "1.0"}
    }

app.include_router(router)
```

**Option 3: Cherry-pick routes**
```python
# Import individual route functions
from outlabs_auth.routers.auth import create_login_route, create_register_route

router = APIRouter(prefix="/auth")

# Add only login (skip register)
router.add_api_route(
    "/login",
    create_login_route(auth),
    methods=["POST"]
)

# Custom register with extra validation
@router.post("/register")
async def custom_register(data: RegisterRequest):
    # Custom validation
    if not is_corporate_email(data.email):
        raise HTTPException(400, "Corporate email required")

    # Use service directly
    user = await auth.user_service.create_user(
        email=data.email,
        password=data.password
    )
    return user
```

**Option 4: No routers (full custom)**
```python
# Don't use routers at all, just use services
@app.post("/custom/signup")
async def signup(email: str, password: str):
    user = await auth.user_service.create_user(email, password)
    tokens = await auth.auth_service.create_tokens(user)
    return tokens
```

**Router Catalog**:

**SimpleRBAC**:
- `get_auth_router()` - login, register, refresh, logout, password reset
- `get_users_router()` - CRUD operations, profile management
- `get_api_keys_router()` - API key management

**EnterpriseRBAC**:
- All SimpleRBAC routers
- `get_roles_router()` - Role management
- `get_permissions_router()` - Permission management
- `get_entities_router()` - Entity hierarchy management
- `get_memberships_router()` - Entity membership management

**Reasoning**:
- FastAPI-Users proves this pattern is very popular
- Gives users both speed AND flexibility
- Library provides best practices by default
- Users can learn by reading router code
- Easy to mix default + custom routes

### Consequences
- **Positive**: Fast setup, flexibility, educational (users learn from code), best practices included
- **Negative**: More API surface to maintain, need good documentation
- **Neutral**: Optional (users can ignore if they want full control)

### Implementation Plan
**Phase 1** (Week 2):
- Create `outlabs_auth/routers/` module
- Implement `get_auth_router()`
- Implement `get_users_router()`
- Add examples to docs

**Phase 2** (Week 3):
- Implement `get_api_keys_router()`
- Add advanced customization examples
- Add testing guide for router-based apps

**Phase 3** (Week 4 - EnterpriseRBAC):
- Implement `get_roles_router()`
- Implement `get_permissions_router()`
- Implement `get_entities_router()`

**Phase 4** (Week 5 - Polish):
- Add middleware examples
- Add rate limiting integration
- Add CORS configuration examples

### Related Decisions
- DD-040 (Lifecycle hooks - routers trigger hooks)
- DD-039 (Dynamic dependencies - routers use them)

---

## DD-042: JWT State Tokens for OAuth Flow

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: OAuth requires CSRF protection via state parameter. Original design used database-stored OAuthState model. FastAPI-Users uses JWT tokens instead.

### The Problem
OAuth CSRF protection traditionally requires:
1. Generate random state parameter
2. Store state in database (with user_id, redirect_url, etc.)
3. Include state in authorization URL
4. Validate state exists in database on callback
5. Delete state from database

This requires database writes for every OAuth flow, even though state is short-lived (10 minutes).

### Options Considered

1. **Database-Stored State (Original Plan)**
   - Pros: Familiar pattern, can store complex data, queryable
   - Cons: Database write/read/delete for every OAuth flow, cleanup job needed, doesn't scale

2. **JWT State Tokens (FastAPI-Users Pattern)**
   - Pros: Stateless (no DB!), self-expiring, tamper-proof, scales infinitely
   - Cons: Can't revoke before expiration, limited payload size (~1KB)

3. **Redis State Tokens**
   - Pros: Fast, TTL built-in, no cleanup needed
   - Cons: Requires Redis, still a database operation, overkill for 10-minute tokens

### Decision
Use JWT tokens for OAuth state (FastAPI-Users pattern).

**Implementation**:
```python
# outlabs_auth/oauth/state.py
def generate_state_token(data: dict, secret: str, lifetime_seconds: int = 600) -> str:
    """Generate JWT state token (no database write!)"""
    payload = {
        **data,
        "aud": "outlabs-auth:oauth-state",
        "exp": datetime.utcnow() + timedelta(seconds=lifetime_seconds)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def decode_state_token(token: str, secret: str) -> dict:
    """Validate JWT state token (no database read!)"""
    return jwt.decode(token, secret, audience="outlabs-auth:oauth-state")
```

**Usage**:
```python
# New user registration (empty state)
state = generate_state_token({}, state_secret)

# Account linking (include user_id for security)
state = generate_state_token({"sub": user.id}, state_secret)

# Callback validation
state_data = decode_state_token(state, state_secret)
user_id = state_data.get("sub")  # For account linking
```

### Consequences
- **Positive**: No database writes, 100% stateless, scales infinitely, self-expiring
- **Positive**: Eliminates OAuthState model and cleanup jobs
- **Positive**: Works across load balancers without sticky sessions
- **Negative**: Can't revoke tokens before expiration (10 min is acceptable)
- **Negative**: Limited payload size (~1KB, plenty for state data)

### Security Notes
- Use separate secret from JWT auth tokens (prevents reuse attacks)
- Include audience claim to prevent token reuse in other contexts
- Short expiration (10 min) limits replay attack window
- Signature validation prevents tampering

### Related Decisions
- DD-043 (OAuth Router - uses JWT state)
- DD-044 (OAuth Associate - embeds user_id in state)

---

## DD-043: OAuth Router Factory Pattern

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: Need simple way to add OAuth providers (Google, Facebook, etc.) to applications. FastAPI-Users has excellent router factory pattern.

### The Problem
Adding OAuth requires:
- Authorization endpoint (redirect user to provider)
- Callback endpoint (handle provider response)
- State generation and validation (CSRF protection)
- Token exchange with provider
- User creation/lookup/update logic
- Social account linking
- Hook triggering

This is ~200 lines of boilerplate per provider. FastAPI-Users solves this with router factories.

### Options Considered

1. **Manual OAuth Implementation**
   - Pros: Maximum flexibility
   - Cons: 200+ lines per provider, error-prone, inconsistent

2. **Single OAuth Service Class**
   - Pros: Reusable logic
   - Cons: Still need to write routes, harder to customize

3. **Router Factory (FastAPI-Users Pattern)**
   - Pros: 2 lines to add any provider, consistent API, battle-tested
   - Cons: Less flexibility than manual implementation

### Decision
Provide `get_oauth_router()` factory function that generates ready-to-use OAuth routes.

**Architecture**:
```python
# outlabs_auth/routers/oauth.py
def get_oauth_router(
    oauth_client: BaseOAuth2,  # httpx-oauth client
    auth: OutlabsAuth,  # SimpleRBAC or EnterpriseRBAC
    state_secret: str,  # For JWT state tokens
    associate_by_email: bool = False,  # Auto-link by email?
    is_verified_by_default: bool = False,  # Trust provider email?
) -> APIRouter:
    """Generate OAuth router with /authorize and /callback routes."""

    router = APIRouter()

    @router.get("/authorize")
    async def authorize(request: Request):
        state = generate_state_token({}, state_secret)
        authorization_url = await oauth_client.get_authorization_url(
            callback_url, state, scopes
        )
        return {"authorization_url": authorization_url}

    @router.get("/callback")
    async def callback(access_token_state = Depends(oauth2_callback)):
        token, state = access_token_state
        # Validate state
        # Get user info from provider
        # Create/update user
        # Link social account
        # Trigger hooks
        # Return auth tokens
        return tokens

    return router
```

**Usage**:
```python
from httpx_oauth.clients.google import GoogleOAuth2
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_oauth_router

google = GoogleOAuth2(client_id="...", client_secret="...")
auth = SimpleRBAC(database=db)

# Add Google login in 2 lines!
app.include_router(
    get_oauth_router(google, auth, state_secret="..."),
    prefix="/auth/google",
    tags=["auth"]
)
```

### Consequences
- **Positive**: Add any OAuth provider in 2 lines of code
- **Positive**: Consistent OAuth API across all providers
- **Positive**: Battle-tested pattern (FastAPI-Users has 14K+ projects)
- **Positive**: Configurable security flags (associate_by_email, is_verified_by_default)
- **Negative**: Less flexibility than manual implementation (acceptable trade-off)

### Routes Generated
- `GET /authorize` - Start OAuth flow, returns authorization_url
- `GET /callback` - Handle OAuth callback, returns JWT tokens

### Hooks Triggered
- `on_after_register()` - If new user created
- `on_after_oauth_register()` - Always for new OAuth users
- `on_after_login()` - Always after successful auth
- `on_after_oauth_login()` - Always for OAuth login

### Related Decisions
- DD-042 (JWT State Tokens - used for CSRF protection)
- DD-044 (OAuth Associate Router - for authenticated users)
- DD-045 (httpx-oauth Integration - provides oauth_client)
- DD-046 (associate_by_email Flag - security configuration)

---

## DD-044: OAuth Associate Router for Authenticated Users

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: Users should be able to link OAuth providers to existing accounts. FastAPI-Users provides separate associate router with security checks.

### The Problem
Two OAuth scenarios:
1. **New user registration**: User has no account, OAuth creates one
2. **Account linking**: User has account, wants to add OAuth login

The main OAuth router (DD-043) handles scenario 1. We need a separate flow for scenario 2.

**Security Risk**: Without proper validation, an attacker could:
1. Start OAuth flow for their account
2. Trick victim into completing the callback
3. Victim's OAuth account gets linked to attacker's account
4. Attacker gains access to victim's OAuth identity

### Options Considered

1. **Same Router for Both Scenarios**
   - Pros: Simpler API
   - Cons: Complex logic, harder to secure, confusing state management

2. **Separate Associate Router (FastAPI-Users Pattern)**
   - Pros: Clear separation, easier to secure, explicit user_id validation
   - Cons: Two routers to maintain

3. **Mode Parameter**
   - Pros: One router
   - Cons: Complex conditional logic, error-prone

### Decision
Provide separate `get_oauth_associate_router()` for authenticated users.

**Architecture**:
```python
# outlabs_auth/routers/oauth_associate.py
def get_oauth_associate_router(
    oauth_client: BaseOAuth2,
    auth: OutlabsAuth,
    state_secret: str,
    requires_verification: bool = False,
) -> APIRouter:
    """Generate OAuth account linking router (requires authentication)."""

    router = APIRouter()
    get_current_user = auth.deps.require_auth(verified=requires_verification)

    @router.get("/authorize")
    async def authorize(request: Request, user = Depends(get_current_user)):
        # SECURITY: Embed user_id in state token
        state = generate_state_token({"sub": str(user.id)}, state_secret)
        authorization_url = await oauth_client.get_authorization_url(
            callback_url, state, scopes
        )
        return {"authorization_url": authorization_url}

    @router.get("/callback")
    async def callback(
        user = Depends(get_current_user),
        access_token_state = Depends(oauth2_callback)
    ):
        token, state = access_token_state
        state_data = decode_state_token(state, state_secret)

        # SECURITY: Validate state user_id matches authenticated user
        if state_data.get("sub") != str(user.id):
            raise HTTPException(400, "User mismatch (security)")

        # Link OAuth account to user
        # Trigger on_after_oauth_associate hook
        return social_account

    return router
```

**Usage**:
```python
from outlabs_auth.routers import get_oauth_associate_router

# Authenticated users can link Google
app.include_router(
    get_oauth_associate_router(
        google,
        auth,
        state_secret="...",
        requires_verification=True  # Only verified users
    ),
    prefix="/auth/associate/google",
    tags=["auth"]
)
```

### Consequences
- **Positive**: Clear separation between registration and linking
- **Positive**: Security validation prevents account hijacking
- **Positive**: Explicit user authentication requirement
- **Positive**: Users can have multiple auth methods
- **Negative**: Two routers to maintain (acceptable for security)

### Security Features
1. **Requires Authentication**: Both authorize and callback require JWT token
2. **State Validation**: State includes user_id, validated in callback
3. **User Mismatch Protection**: Callback fails if state user_id != authenticated user_id
4. **Duplicate Prevention**: Checks if OAuth account already linked

### Use Cases
- User registered with email/password, wants to add Google login
- User has Google login, wants to add GitHub login
- User wants backup authentication methods
- User wants to unify multiple OAuth accounts

### Related Decisions
- DD-042 (JWT State Tokens - includes user_id for security)
- DD-043 (OAuth Router - handles new user registration)

---

## DD-045: httpx-oauth Library Integration

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: Need OAuth client library. FastAPI-Users uses httpx-oauth. Alternative is authlib.

### The Problem
OAuth implementation requires:
- Authorization URL generation
- Token exchange (code → access token)
- User info retrieval
- Provider-specific quirks (scopes, endpoints, response formats)
- PKCE support
- Token refresh

We could implement this ourselves or use a library.

### Options Considered

1. **Manual OAuth Implementation**
   - Pros: No dependencies, full control
   - Cons: 500+ lines per provider, bugs, maintenance burden

2. **authlib**
   - Pros: Feature-rich, supports OAuth 1.0 + 2.0, well-documented
   - Cons: Synchronous (not FastAPI-native), larger dependency, more complex

3. **httpx-oauth (FastAPI-Users Choice)**
   - Pros: Pure async, FastAPI-native, lightweight, pre-built clients, maintained by FastAPI-Users author
   - Cons: OAuth 2.0 only (acceptable), smaller community than authlib

### Decision
Use `httpx-oauth` library (FastAPI-Users pattern).

**Installation**:
```bash
pip install outlabs-auth[oauth]  # Includes httpx-oauth>=0.13.0
```

**Pre-built Clients**:
- GoogleOAuth2
- FacebookOAuth2
- GitHubOAuth2
- MicrosoftGraphOAuth2
- DiscordOAuth2
- LinkedInOAuth2
- SpotifyOAuth2
- And more...

**Usage**:
```python
from httpx_oauth.clients.google import GoogleOAuth2

google = GoogleOAuth2(
    client_id="your-id.apps.googleusercontent.com",
    client_secret="your-secret"
)

# Get authorization URL
auth_url = await google.get_authorization_url(
    redirect_uri,
    state,
    scopes=["openid", "email", "profile"]
)

# Exchange code for tokens
token = await google.get_access_token(code, redirect_uri)

# Get user info
account_id, email = await google.get_id_email(token["access_token"])
```

**Provider Factory**:
```python
# outlabs_auth/oauth/providers.py
def get_google_client(client_id: str, client_secret: str) -> GoogleOAuth2:
    """Get pre-configured Google OAuth client."""
    return GoogleOAuth2(
        client_id,
        client_secret,
        scopes=["openid", "email", "profile"]
    )

def get_github_client(client_id: str, client_secret: str) -> GitHubOAuth2:
    """Get pre-configured GitHub OAuth client."""
    return GitHubOAuth2(client_id, client_secret, scopes=["user:email"])
```

### Consequences
- **Positive**: Battle-tested (used by 14K+ FastAPI-Users projects)
- **Positive**: Pure async, FastAPI-native integration
- **Positive**: Pre-built clients for all major providers
- **Positive**: Lightweight dependency (~100KB)
- **Positive**: Maintained by FastAPI-Users author (Frankie567)
- **Negative**: OAuth 2.0 only (OAuth 1.0 not supported, rarely needed)
- **Negative**: Smaller community than authlib (but FastAPI-specific is advantage)

### Supported Providers (Out of the Box)
✅ Google, Facebook, GitHub, Microsoft, Discord, LinkedIn, Spotify, Twitch, Reddit, GitLab, Bitbucket, Apple, Twitter (OAuth 2.0), Okta, Auth0

### Related Decisions
- DD-043 (OAuth Router - uses httpx-oauth clients)
- DD-044 (OAuth Associate - uses httpx-oauth clients)

---

## DD-046: associate_by_email Security Flag

**Date**: 2025-01-23
**Status**: Accepted
**Deciders**: Core team
**Context**: When user logs in with OAuth, should we auto-link to existing user with same email? FastAPI-Users provides configurable flag.

### The Problem
**Scenario**: User registers with email/password `user@example.com`. Later, they try to login with Google OAuth using same email.

**Question**: Should we:
1. **Reject**: "User with this email already exists" (secure default)
2. **Auto-link**: Link Google account to existing user (convenience)

**Security Risk**: If OAuth provider doesn't verify emails:
1. Attacker creates account on provider with `victim@example.com` (unverified)
2. Attacker authenticates with OAuth
3. If auto-link enabled, attacker's OAuth links to victim's account
4. Attacker gains full access to victim's account 😱

### Options Considered

1. **Always Reject (Most Secure)**
   - Pros: No security risk, forces explicit account linking
   - Cons: Poor UX (user must login with password, then link OAuth)

2. **Always Auto-Link (Most Convenient)**
   - Pros: Best UX, seamless experience
   - Cons: Security risk with unverified email providers

3. **Configurable Flag (FastAPI-Users Pattern)**
   - Pros: Flexibility, secure default, opt-in convenience
   - Cons: Users might enable without understanding risk

### Decision
Provide `associate_by_email` configuration flag, **default to False** (secure).

**Implementation**:
```python
def get_oauth_router(
    oauth_client: BaseOAuth2,
    auth: OutlabsAuth,
    state_secret: str,
    associate_by_email: bool = False,  # Secure default!
    is_verified_by_default: bool = False,
):
    # ...OAuth logic
    if user_exists_with_email and not associate_by_email:
        raise HTTPException(400, "User with this email already exists")
```

**Safe Usage** (Google verifies emails):
```python
google = GoogleOAuth2(client_id, client_secret)
app.include_router(
    get_oauth_router(
        google,
        auth,
        state_secret,
        associate_by_email=True,  # Safe: Google verifies emails ✅
        is_verified_by_default=True  # Trust Google's verification
    ),
    prefix="/auth/google"
)
```

**Unsafe Usage** (Unknown provider):
```python
random_oauth = SomeOAuth2(client_id, client_secret)
app.include_router(
    get_oauth_router(
        random_oauth,
        auth,
        state_secret,
        associate_by_email=False,  # Keep False for unknown providers ❌
    ),
    prefix="/auth/random"
)
```

### Consequences
- **Positive**: Secure by default (prevents account hijacking)
- **Positive**: Opt-in convenience for trusted providers
- **Positive**: Clear documentation of security implications
- **Negative**: Users might enable without understanding (mitigated by docs)

### Provider Trust Guide

**✅ Safe to enable** (these providers verify emails):
- Google (`associate_by_email=True, is_verified_by_default=True`)
- Microsoft (`associate_by_email=True, is_verified_by_default=True`)
- Apple (`associate_by_email=True, is_verified_by_default=True`)
- GitHub (with `user:email` scope for verified email)
- Facebook (`associate_by_email=True`)

**❌ Keep disabled** (unless you verify email_verified claim):
- Custom OAuth providers
- Unknown providers
- Development/testing providers

### Security Best Practices
1. Default to `associate_by_email=False`
2. Only enable for major providers (Google, Microsoft, Apple)
3. Check provider's `email_verified` claim if available
4. Document security implications in code comments
5. Consider requiring email verification before linking

### Related Decisions
- DD-043 (OAuth Router - uses this flag)
- DD-042 (JWT State Tokens - CSRF protection)

---

## Questions Still Open

Track questions that need decisions:

### Q-001: PostgreSQL Support in v1.0?
**Status**: Open
**Proposed Decision**: Defer to v1.1
**Needs Decision By**: End of Week 1

### Q-002: Multi-Tenant in v1.0 or v1.1?
**Status**: Open
**Proposed Decision**: Optional in v1.0
**Needs Decision By**: End of Week 2

### Q-003: CLI Tools for Management?
**Status**: Open
**Proposed Decision**: v1.1 or v2.0
**Needs Decision By**: Week 4

---

## Change Log

| Date | Decision | Status |
|------|----------|--------|
| 2025-01-14 | DD-001 through DD-014 | All Accepted |
| 2025-01-14 | DD-015 through DD-021 | All Accepted |
| 2025-01-14 | DD-022 through DD-027 | All Accepted (Post-v1.0 Extensions) |
| 2025-01-14 | DD-028 through DD-031 | All Accepted (Core v1.0 - API Keys & Auth Dependencies) |
| 2025-01-14 | DD-032 through DD-037 | All Accepted (Architectural Improvements) |
| 2025-01-23 | DD-038 through DD-041 | All Accepted (FastAPI-Users Patterns - Core) |
| 2025-01-23 | DD-042 through DD-046 | All Accepted (FastAPI-Users Patterns - OAuth) |
| 2025-01-14 | DD-003 | Superseded by DD-015 |
| 2025-01-14 | DD-028, DD-031 | Updated (removed automatic rotation, added temp locks) |
| 2025-01-14 | DD-030 | Superseded by DD-035 |

---

**Last Updated**: 2025-01-23 (Added FastAPI-Users OAuth patterns: JWT State Tokens, OAuth Router Factory, OAuth Associate Router, httpx-oauth Integration, associate_by_email Security Flag)
**Next Review**: End of Phase 1 (Week 2)
