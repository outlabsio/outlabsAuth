# OutlabsAuth Library - Design Decisions Log

**Version**: 1.3
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
- Automatic rotation policies (90 days recommended)
- IP whitelisting strictly enforced
- Auto-revoke after 10 failed validation attempts

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

4. **Rotation**: Automatic policies
   - Rotate every 90 days (configurable)
   - Grace period for zero-downtime rotation
   - Audit all rotations

5. **IP Whitelisting**: Strictly enforced
   - Optional but recommended
   - Support CIDR notation
   - Log all unauthorized access attempts

6. **Auto-Revocation**:
   - After 10 failed validation attempts
   - On expiration
   - On detected abuse (unusual patterns)

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
- [ ] Key rotation policy configured (≤90 days)
- [ ] IP whitelisting enabled for production keys
- [ ] Rate limiting per key configured
- [ ] Audit logging captures all key operations
- [ ] Automatic revocation on repeated failures
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
| 2025-01-14 | DD-003 | Superseded by DD-015 |

---

**Last Updated**: 2025-01-14 (Added API key system, multi-source authentication, and dependency patterns)
**Next Review**: End of Phase 1 (Week 2)
