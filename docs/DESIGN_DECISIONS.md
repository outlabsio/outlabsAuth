# OutlabsAuth Library - Design Decisions Log

**Version**: 2.0
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
- DD-002 (Entity-isolated model)
- DD-004 (Database choice)

---

## DD-002: Entity-Isolated Deployment Model

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Keep deployment simple and isolate by entity hierarchy/root assignment.

### Options Considered

1. **Tenant Mode**
   - Pros: Explicit tenant boundary model
   - Cons: Extra complexity and additional code paths

2. **Single-App Entity Isolation**
   - Pros: Simplest implementation
   - Cons: Requires clear root-entity scoping rules

### Decision
Use single-app deployments with entity/root scoping as the isolation model.

**Implementation**:
```python
# Single app (default)
auth = SimpleRBAC(database=db)
```

**Reasoning**:
- Most apps benefit from the simpler single-app model
- Avoid dual behavior and tenant-mode drift
- Keep isolation explicit through entities/root assignment

### Consequences
- **Positive**: Lower complexity and fewer edge cases
- **Negative**: No tenant-mode abstraction
- **Neutral**: Isolation is explicit in entity/root data

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
**Status**: ~~Accepted~~ **SUPERSEDED by DD-049**
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

### Decision (Original - Superseded)
MongoDB primary, PostgreSQL in future version.

**UPDATE 2025-01-14**: This decision has been superseded by DD-049. The library now uses PostgreSQL as the primary (and only) database.

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

## DD-005: Remove platform_id, Keep Entity-Based Isolation

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
   - Cons**: Requires explicit isolation boundaries in app logic

### Decision
Remove `platform_id` and avoid adding tenant-mode fields.

**Reasoning**:
- `platform_id` was for multi-platform isolation we don't need
- Root-entity scoping already provides practical isolation boundaries
- Avoid carrying a second isolation abstraction

### Schema Changes
```python
# BEFORE
class EntityModel:
    platform_id: str  # Required, always present

# AFTER
class EntityModel:
    root_entity_id: Optional[str] = None  # Optional, per-user assignment
```

### Consequences
- **Positive**: Simpler model, standard naming
- **Negative**: Requires database migration
- **Neutral**: Models slightly changed

### Migration
See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for details.

### Related Decisions
- DD-001 (Library approach)
- DD-002 (Entity-isolated model)

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
    enable_caching=True               # Opt-in
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
- `enable_audit_log`: Reserved for future extended/compliance capture; core lifecycle history is now built into the runtime instead of being behind this flag

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

**Date**: 2025-01-14 (Updated: 2025-01-26 - Corrected hashing algorithm)
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
- Prefixed keys (12 characters): `sk_live_abc1`, `sk_test_xyz2`
- **SHA-256 hashing** (fast hashing appropriate for high-entropy secrets)
- Key lifecycle: create, rotate, revoke
- Scope-based access control (not permission-based - simpler)
- IP whitelisting (optional)
- Rate limiting per key (Redis counters for performance)
- Usage tracking and audit logging
- Temporary lock after abuse detection

**Design**:
```python
# Create API key
raw_key, key = await auth.api_key_service.create_api_key(
    name="production_api",
    owner_id=user_id,
    scopes=["user:read", "entity:read"],
    rate_limit_per_minute=100,
    ip_whitelist=["10.0.0.0/8"]  # Optional
)

# Verify API key
api_key, usage = await auth.api_key_service.verify_api_key(
    raw_key,
    required_scope="user:read",
    ip_address=request.client.host
)
```

**Reasoning**:
- Essential for modern APIs (webhooks, integrations, service-to-service)
- Industry standard pattern (Stripe, GitHub, Twilio all use this)
- Simpler than OAuth for machine-to-machine
- Critical for production deployments
- Should be available from v1.0, not an extension

**Security Requirements**:
- **SHA-256 hashing** (see "Design Correction" below)
- Never log raw keys, only prefixes
- Optional expiration (recommended 90 days) with manual rotation API
- IP whitelisting (optional but recommended)
- Temporary lock after 10 failed attempts in 10 minutes (30-min cooldown)
- Rate limiting enforced per key

### Design Correction: Why SHA-256 Instead of Argon2id?

**Original Decision (INCORRECT)**: Use argon2id for API key hashing  
**Corrected Decision**: Use SHA-256 for API key hashing

**Rationale**:
API keys are **NOT passwords**. They are cryptographically secure random secrets with 256 bits of entropy.

**Why argon2id is wrong here**:
- Argon2id is designed to slow down brute force attacks on **low-entropy human passwords**
- API keys cannot be brute-forced (2^256 possible values = 10^77 combinations)
- Argon2id would add ~100ms overhead to **every API request** for zero security benefit
- No attacker can guess a 256-bit random secret through trial and error

**Where security actually comes from**:
1. ✅ Cryptographically secure random generation (`secrets.token_hex(32)`)
2. ✅ Rate limiting per key (60/min, 1000/hour via Redis counters)
3. ✅ Temporary locks after repeated failures (10 in 10 min → 30-min cooldown)
4. ✅ HTTPS transmission (user responsibility)
5. ✅ IP whitelisting (optional)
6. ❌ **NOT from slow hashing** (unnecessary for high-entropy secrets)

**Industry precedent**:
- **GitHub**: Fast hashing for API tokens
- **Stripe**: Fast hashing for API keys
- **AWS**: Fast hashing for access keys
- All use slow hashing (bcrypt/argon2) **only for passwords**

**Performance impact**:
- SHA-256: ~0.1ms per API request (✅ acceptable)
- Argon2id: ~100ms per API request (❌ 1000x slower, no benefit)

**What we DO use argon2id for**:
- ✅ User passwords (correct - passwords have low entropy)
- ❌ API keys (incorrect - keys have high entropy)

### Refresh Token Rotation (Optional Feature)

**Decision**: Make refresh token rotation **optional**, default OFF.

**Rationale**:
- Rotation adds complexity for marginal security benefit
- Can break concurrent refresh attempts from same client
- If client loses connection after receiving new token but before saving it, they're locked out
- Most apps are fine with: 30-day refresh token + manual "revoke all sessions"

**Recommended approach**:
- Default: Refresh tokens valid for 30 days, reusable
- Implement "revoke all sessions" feature (already have it)
- Add detection for refresh token reuse **after revocation** (indicates theft)
- High-security apps can enable rotation via `enable_refresh_token_rotation=True`

**Configuration**:
```python
# Default (no rotation - simpler, fewer edge cases)
auth = SimpleRBAC(database=db, secret_key="secret")

# High-security apps (rotation enabled)
auth = SimpleRBAC(
    database=db,
    secret_key="secret",
    enable_refresh_token_rotation=True
)
```

### Consequences
- **Positive**: Production-ready from day one, industry standard, enables integrations, fast performance
- **Negative**: Adds ~500 LOC to core
- **Neutral**: Both SimpleRBAC and EnterpriseRBAC support API keys equally

### Timeline Impact
- Add to Phase 2 (SimpleRBAC completion - Week 2)
- ~2 days of development time
- No delay to overall timeline

### Related Decisions
- DD-029 (Multi-source authentication)
- DD-030 (Dependency patterns)
- DD-031 (API key security model - superseded by this correction)

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

**Date**: 2025-01-14 (Updated: 2025-01-26)
**Status**: Superseded by DD-028 (Corrected)
**Deciders**: Core team, Security review
**Context**: API keys are sensitive credentials requiring strong security

> **⚠️ SUPERSEDED**: This decision has been superseded by the corrected DD-028.
> The original recommendation to use argon2id for API keys was incorrect.
> See DD-028 for the corrected approach using SHA-256 for high-entropy secrets.

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
- [ ] Key lifecycle operations are operationally visible and reviewable
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

## DD-038 to DD-046: FastAPI-Users Inspired Patterns

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Adopt battle-tested patterns from FastAPI-Users library

OutlabsAuth borrows several excellent patterns from [FastAPI-Users](https://github.com/fastapi-users/fastapi-users), a mature authentication library for FastAPI:

### DD-038: Lifecycle Hooks Pattern
**Feature**: Overrideable async hooks for extensibility
```python
class UserService(BaseService):
    async def on_after_register(self, user: UserModel, request: Request):
        """Override to send welcome email, etc."""
        pass

    async def on_after_login(self, user: UserModel, request: Request):
        """Override to log login events, etc."""
        pass
```

### DD-039: Router Factories
**Feature**: Pre-built FastAPI routers for common auth flows
```python
# FastAPI-Users pattern
auth_router = get_auth_router(backend)
register_router = get_register_router(user_manager)

# OutlabsAuth adaptation
from outlabs_auth.routers import get_auth_router, get_user_router
app.include_router(get_auth_router(auth))
app.include_router(get_user_router(auth))
```

### DD-040: Transport/Strategy Pattern
**Feature**: Separation of credential delivery vs validation
- **Transport**: How credentials are delivered (cookie, bearer, header)
- **Strategy**: How credentials are validated (JWT, database session, API key)

```python
# FastAPI-Users pattern
backend = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(),
    get_strategy=get_jwt_strategy
)

# OutlabsAuth adaptation
auth = SimpleRBAC(
    database=db,
    jwt_transport="bearer",  # or "cookie"
    jwt_algorithm="HS256"
)
```

### DD-041: Dynamic Dependencies (makefun)
**Feature**: Generate dependencies with perfect OpenAPI schemas
```python
# Uses makefun to create dependencies with proper type hints
def get_current_user(required: bool = True):
    # Generates dependency with correct signature for OpenAPI
    pass
```

### DD-042: User Manager Pattern
**Feature**: Centralized user management service with hooks
```python
class UserManager:
    async def create(self, user_create: UserCreate) -> User:
        # Validation
        user = await self.user_db.create(user_create)
        await self.on_after_register(user, request)
        return user
```

### DD-043: Verification Token System
**Feature**: Secure token generation for email verification, password reset
```python
# Generate verification token
token = generate_token()
await send_verification_email(user.email, token)

# Verify token
user = await verify_token(token)
```

### DD-044: Multiple Authentication Backends
**Feature**: Support multiple auth methods simultaneously
```python
# FastAPI-Users allows JWT + Cookie backends
# OutlabsAuth extends this to JWT + API Keys + Service Tokens
```

### DD-045: Request Context Awareness
**Feature**: Access to Request object in lifecycle hooks
```python
async def on_after_login(self, user: UserModel, request: Request):
    # Can access request headers, IP, user agent
    ip = request.client.host
    await log_login(user.id, ip)
```

### DD-046: Pluggable Password Validation
**Feature**: Customizable password requirements
```python
class PasswordValidator:
    def validate(self, password: str) -> None:
        # Custom rules
        if len(password) < 12:
            raise InvalidPasswordException()
```

### What We Added Beyond FastAPI-Users

While FastAPI-Users excels at authentication, OutlabsAuth adds:
- **Authorization**: RBAC, tree permissions, entity hierarchy
- **Context-Aware Roles**: Permissions that adapt by entity type
- **ABAC**: Attribute-based access control
- **API Keys**: argon2id-hashed keys with rate limiting
- **Service Tokens**: Zero-overhead JWT authentication for microservices
- **Multi-Tenant**: Optional tenant isolation
- **Closure Table**: O(1) tree queries for hierarchical permissions

### Consequences
- **Positive**: Battle-tested patterns, proven developer experience, familiar to FastAPI-Users users
- **Negative**: Dependency on makefun library, learning curve for lifecycle hooks
- **Neutral**: Patterns well-documented in FastAPI-Users docs

### Acknowledgment
We are grateful to the FastAPI-Users team for pioneering these excellent patterns in the FastAPI ecosystem. OutlabsAuth builds on their foundation while adding advanced authorization features.

### Related Decisions
- DD-012 (FastAPI-first design)
- DD-030 (Dependency patterns)
- DD-035 (AuthDeps class)

---

## DD-047: UserRoleMembership Table for SimpleRBAC

**Date**: 2025-01-14 (Updated: 2025-01-25 - Added MembershipStatus enum)
**Status**: Accepted
**Deciders**: Core team
**Context**: SimpleRBAC needs user-role assignment mechanism with rich lifecycle tracking

### The Problem
SimpleRBAC preset needs a way to assign roles to users. Three approaches were considered, each with different trade-offs.

### Options Considered

1. **Direct Links (user.roles: List[Link[RoleModel]])**
   - Pros: Simplest data model, one less collection
   - Cons: No audit trail, no time-based assignments, no extensibility, inconsistent with EnterpriseRBAC

2. **Metadata Hack (user.metadata["role_ids"])**
   - Pros: Fastest to implement, no schema changes
   - Cons: Bypasses Beanie ORM, no type safety, no audit trail, loses all ORM features

3. **Membership Table (UserRoleMembership collection)**
   - Pros: Full audit trail, time-based assignments, consistent with EnterpriseRBAC, extensible
   - Cons: One extra collection, one extra query (~5ms)

### Decision
Use dedicated `UserRoleMembership` collection for SimpleRBAC.

**Schema**:
```python
class MembershipStatus(str, Enum):
    """
    Status of a role membership assignment.

    - ACTIVE: Membership is currently active and grants permissions
    - SUSPENDED: Temporarily paused, does not grant permissions
    - REVOKED: Manually removed by admin, does not grant permissions
    - EXPIRED: Automatically expired based on valid_until timestamp
    - PENDING: Awaiting approval (future feature for approval workflows)
    - REJECTED: Request denied (future feature for approval workflows)
    """
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"
    REJECTED = "rejected"

class UserRoleMembership(BaseDocument):
    """
    User-role membership for SimpleRBAC (flat, no entity context).
    Provides audit trail and consistency with EnterpriseRBAC's membership pattern.
    """
    user: Link[UserModel]
    role: Link[RoleModel]
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_by: Optional[Link[UserModel]] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status lifecycle tracking (replaces is_active bool)
    status: MembershipStatus = Field(default=MembershipStatus.ACTIVE)
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[Link[UserModel]] = None

    def can_grant_permissions(self) -> bool:
        """Check if membership can currently grant permissions."""
        if self.status != MembershipStatus.ACTIVE:
            return False
        return self.is_currently_valid()  # Time-based check

    class Settings:
        name = "user_role_memberships"
        indexes = [
            ("user", "role"),      # Unique assignment
            ("user", "status"),    # Active/suspended roles for user
            ("valid_until",),      # Expire cleanup
        ]
```

**Usage**:
```python
# Assign role
membership = await auth.role_service.assign_role(
    user_id=user.id,
    role_id=role.id,
    assigned_by=admin.id,
    valid_from=datetime.now(timezone.utc),
    valid_until=datetime.now(timezone.utc) + timedelta(days=90)
)

# Get user's roles
roles = await auth.role_service.get_user_roles(user.id)

# Revoke role
await auth.role_service.revoke_role(user.id, role.id)
```

### Reasoning

#### 1. Architectural Consistency (Primary Reason)
This is the most compelling reason. The core architectural principle (DD-032) is a **single `OutlabsAuth` implementation with thin wrappers**.

- **Without membership table**: SimpleRBAC stores roles in `user.roles` and EnterpriseRBAC uses `EntityMembership`, creating fundamental divergence in the data model. Core services need `if/else` logic to handle two different ways of fetching user roles.
- **With membership table**: The only difference becomes the `entity_id` context. Core logic for fetching, checking, and managing roles is virtually identical.

This makes migration from SimpleRBAC → EnterpriseRBAC trivial—it's a configuration change, not a data migration project. This perfectly aligns with the goal of "gradual complexity."

#### 2. Audit Trail is Essential
For any application with security or compliance requirements (most of them), knowing **who** granted a role and **when** is critical for:
- Security audits
- Incident response
- Compliance reporting (SOC 2, HIPAA, GDPR)
- Debugging permission issues

Building this in from the start is a massive win over retrofitting it later.

#### 3. Time-Based Roles Enable Real Use Cases
Even "simple" applications need temporary access:
- **Contractors**: Grant "editor" role for project duration (3 months)
- **Seasonal staff**: Temporary access for holiday season
- **Trial periods**: 30-day access to premium features
- **Onboarding**: Temporary elevated permissions for setup

Without a membership table, implementing this cleanly is very difficult.

#### 4. Industry Standard Pattern
The membership table pattern is used by:
- **Django**: `User ↔ UserGroup ↔ Group`
- **Keycloak**: `UserRoleMapping` table
- **Auth0**: Role assignments with audit trails
- **AWS IAM**: Policy attachments with metadata

This pattern has been battle-tested at scale for decades.

#### 5. Performance Impact is Negligible
The extra query on `UserRoleMembership`:
- Runs on indexed fields (`user`, `is_active`)
- Returns small result sets (user typically has 1-3 roles)
- Executes in ~5ms with proper indexes
- Can be cached aggressively (roles don't change frequently)

For 99% of applications, this performance impact is imperceptible. The architectural inconsistency and lack of features from direct links would cause far more significant problems.

#### 6. Extensibility
The `UserRoleMembership` collection becomes a natural place for metadata:
- `reason`: Why role was granted
- `approved_by`: Secondary approval for sensitive roles
- `conditions`: Custom business logic (e.g., "only during business hours")
- `notification_sent`: Track if user was notified

Without a membership table, this metadata has nowhere to live.

#### 7. MembershipStatus Enum (Updated 2025-01-25)
The initial implementation used `is_active: bool` for soft delete. This was updated to `status: MembershipStatus` enum for:

**Why Enum over Boolean**:
- **Rich lifecycle tracking**: Distinguish between manual revocation, expiration, suspension, and pending approval
- **Better audit trail**: Know *why* a membership is inactive (revoked vs expired vs suspended)
- **Future-ready**: Supports approval workflows (PENDING/REJECTED states) without schema changes
- **Consistency**: Matches UserModel's UserStatus enum pattern
- **Compliance**: Security audits require knowing *how* access was removed

**Use Cases**:
- **ACTIVE**: Normal operating state, grants permissions
- **SUSPENDED**: Temporarily pause access (user on leave, pending investigation)
- **REVOKED**: Admin manually removed role (security incident, user left team)
- **EXPIRED**: Role automatically expired via valid_until (contractor role after 90 days)
- **PENDING**: Role request awaiting approval (future feature)
- **REJECTED**: Role request denied (future feature)

This provides much richer information than a binary active/inactive flag, essential for production systems with compliance requirements.

### Consequences

**Positive**:
- ✅ Full audit trail from day one (who, when, why)
- ✅ Time-based access control built-in
- ✅ Architectural consistency (single core implementation)
- ✅ Seamless migration path: SimpleRBAC → EnterpriseRBAC
- ✅ Industry standard pattern
- ✅ Extensible for future needs
- ✅ Security & compliance ready
- ✅ Rich status lifecycle tracking (6 states vs boolean)
- ✅ Revocation audit trail (who revoked, when, why)
- ✅ Approval workflow ready (PENDING/REJECTED states)

**Negative**:
- ❌ One extra collection (negligible in MongoDB)
- ❌ One extra query (~5ms with indexes, cacheable)
- ❌ Slightly more complex than boolean flag

**Neutral**:
- Both SimpleRBAC and EnterpriseRBAC use membership pattern
- Migration from Simple → Enterprise only adds `entity_id` column

### Migration Path: SimpleRBAC → EnterpriseRBAC

```python
# Step 1: Change class (no code changes)
# OLD
auth = SimpleRBAC(database=db)

# NEW
auth = EnterpriseRBAC(database=db)

# Step 2: Add entities to existing memberships
for membership in await UserRoleMembership.find_all().to_list():
    # Convert to EntityMembership
    await EntityMembership(
        user=membership.user,
        role=membership.role,
        entity=default_entity,  # Migrate to default entity
        assigned_at=membership.assigned_at,
        assigned_by=membership.assigned_by,
        valid_from=membership.valid_from,
        valid_until=membership.valid_until,
        is_active=membership.is_active
    ).save()
```

The data is already structured correctly—just add entity context.

### Comparison with EnterpriseRBAC

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|-----------|----------------|
| Collection | `UserRoleMembership` | `EntityMembership` |
| User ↔ Role | ✅ Direct | ✅ Via entity |
| Entity Context | ❌ No | ✅ Yes |
| Multiple Roles | ✅ Yes | ✅ Yes |
| Audit Trail | ✅ Yes | ✅ Yes |
| Time-Based | ✅ Yes | ✅ Yes |
| Tree Permissions | ❌ No | ✅ Yes |

### Related Decisions
- DD-003 (Original preset architecture)
- DD-015 (Two presets instead of three)
- DD-032 (Single core with thin wrappers)
- DD-006 (Entity hierarchy design)

---

## DD-048: Redis Configuration Simplification

**Date**: 2025-01-26
**Status**: Accepted (Clarification)
**Deciders**: Core team
**Context**: Simplify Redis enablement to reduce configuration confusion

### The Problem
Current implementation has confusing dual-flag system:
- `enable_caching` flag (config parameter)
- `redis_enabled` flag (internal config)
- `redis_url` parameter (connection string)

**Confusion**:
- Users provide `redis_url` but Redis doesn't connect (forgot `enable_caching=True`)
- Why have both `enable_caching` AND `redis_enabled`?
- Unclear which features require Redis

### Decision
Simplify to single `redis_enabled` flag as source of truth.

**Simple Rules**:
1. User provides `redis_enabled=True` → Use Redis for all features
2. User provides `redis_url` but `redis_enabled=False` → Redis available but not used (user's explicit choice)
3. Redis unavailable → Graceful degradation to in-memory/direct DB

**Configuration**:
```python
# Redis disabled (default - in-memory only)
auth = SimpleRBAC(
    database=db,
    secret_key="secret"
)

# Redis enabled
auth = SimpleRBAC(
    database=db,
    secret_key="secret",
    redis_enabled=True,
    redis_url="redis://localhost:6379"
)
```

**Features Requiring Redis** (gracefully degrade if unavailable):
- ✅ Permission caching (falls back to direct DB queries)
- ✅ API key usage counters (falls back to direct DB writes)
- ✅ API key rate limiting (falls back to in-memory counters)
- ✅ JWT token blacklist (falls back to DB-only revocation with 15-min window)
- ✅ Activity tracking DAU/MAU (falls back to disabled)
- ✅ Entity path caching (falls back to direct closure table queries)

**Why Not Auto-Enable on redis_url?**
- User may provide `redis_url` for future use but not want it active yet
- Explicit is better than implicit (Zen of Python)
- Allows configuration via environment variables without auto-activation
- User maintains control over when Redis features activate

### Implementation
```python
# In OutlabsAuth.__init__
if redis_url and redis_enabled:
    self.redis_client = RedisClient(config)
else:
    self.redis_client = None

# In RedisClient.connect()
if not self.config.redis_enabled:
    logger.info("Redis disabled in configuration")
    return False
```

**Remove**:
- `enable_caching` parameter (redundant with `redis_enabled`)
- Automatic Redis enablement on `redis_url` presence

### Consequences
- **Positive**: Clearer configuration, single source of truth, explicit control
- **Negative**: Requires `redis_enabled=True` even when `redis_url` provided
- **Neutral**: One-line change for users (add `redis_enabled=True`)

### Migration for Existing Code
```python
# OLD (confusing)
auth = SimpleRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# NEW (clear)
auth = SimpleRBAC(
    database=db,
    redis_enabled=True,
    redis_url="redis://localhost:6379"
)
```

### Related Decisions
- DD-010 (Redis caching optional)
- DD-033 (Redis counters for API keys)
- DD-037 (Redis Pub/Sub cache invalidation)

---

## DD-049: PostgreSQL as Primary Database

**Date**: 2025-01-14
**Status**: Accepted
**Deciders**: Core team
**Context**: Need a robust, production-ready database with strong SQL support for hierarchical queries

### Options Considered

1. **Keep MongoDB with Beanie**
   - Pros: Already implemented, document flexibility
   - Cons: Closure table queries less efficient, harder to reason about relationships

2. **PostgreSQL with SQLAlchemy/SQLModel**
   - Pros: ACID compliance, native recursive CTE support, mature ecosystem, better for hierarchical data
   - Cons: Migration effort required, different query patterns

3. **Support Both**
   - Pros: Maximum flexibility
   - Cons: Double maintenance, abstraction complexity, testing burden

### Decision
Migrate fully to PostgreSQL with SQLAlchemy async and SQLModel.

**Implementation**:
```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(
    database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
    secret_key="your-secret-key"
)
await auth.initialize()
```

**Reasoning**:
- PostgreSQL excels at hierarchical data with closure table pattern
- SQLAlchemy async provides mature, production-ready ORM
- SQLModel simplifies model definitions with Pydantic integration
- Better tooling for migrations (Alembic)
- ACID compliance for authentication data
- Recursive CTEs for tree queries if needed
- Industry standard for enterprise applications

### Consequences
- **Positive**: Better performance for tree queries, ACID compliance, mature ecosystem, industry standard
- **Negative**: Migration effort required, MongoDB users need to migrate
- **Neutral**: Different query patterns to learn

### Migration Details
All services migrated from Beanie to SQLAlchemy async:
- `auth.py` - User authentication
- `user.py` - User management
- `role.py` - Role management
- `permission.py` - Permission management
- `entity.py` - Entity hierarchy with closure table
- `membership.py` - User-entity memberships
- `api_key.py` - API key management

### Related Decisions
- DD-004 (MongoDB First - SUPERSEDED by this decision)
- DD-036 (Closure table for tree permissions)

---

## DD-050: Role Scoping to Root Entities

**Date**: 2026-01-22
**Status**: Accepted
**Deciders**: Core team
**Context**: Different organizations need isolated role sets. A brokerage's "Agent" role should be separate from another brokerage's "Agent" role.

### Options Considered

1. **Role scoping by entity type**
   - Pros: Simple to implement, roles tied to types like "brokerage", "team"
   - Cons: Entity types are freeform strings, drift risk, doesn't match organizational boundaries

2. **Role scoping by entity hierarchy (root entities)**
   - Pros: Natural organizational boundaries, clear ownership, prevents cross-org confusion
   - Cons: Users can only belong to one organization, requires "umbrella" entity for multi-org scenarios

3. **Role categories/namespaces**
   - Pros: Flexible grouping
   - Cons: Another concept to manage, doesn't enforce organizational isolation

### Decision
Scope roles to root entities (top-level organizations with `parent_id = NULL`).

**Implementation**:
- Added `root_entity_id` to User model (nullable, for superusers/unassigned users)
- Renamed `entity_id` to `root_entity_id` on Role model
- Roles with `root_entity_id = NULL` and `is_global = TRUE` are available everywhere
- Roles with `root_entity_id` set are only available within that organization's hierarchy
- Users are bound to ONE root entity on first membership assignment
- Cross-organization membership is prevented at the service layer

### Consequences
- **Positive**: Clear organizational isolation, roles don't leak across organizations
- **Positive**: Superusers and system accounts can exist without root_entity_id
- **Negative**: Users cannot belong to multiple top-level organizations
- **Neutral**: Requires "umbrella" entity pattern for multi-domain deployments

### Critical Architecture Constraint

**IMPORTANT**: If you need users to operate across what would naturally be separate organizations (e.g., a consultant working with multiple brokerages), you MUST structure your entity hierarchy with a single root entity:

```
❌ WRONG - Multiple root entities (users can't belong to both):
├── ACME Realty (root)          # User can belong here
└── Keller Williams (root)      # OR here, but NOT both

✅ CORRECT - Single root with child organizations:
└── Platform (root)             # The "umbrella" entity
    ├── ACME Realty (child)     # User can have membership here
    ├── Keller Williams (child) # AND here (same root organization)
    └── Internal Teams (child)  # AND here
```

**When to use each pattern**:
- **Multiple root entities**: Completely separate organizations that should never share users (e.g., different companies using the same software)
- **Single root with children**: Related organizations where users might need access to multiple (e.g., a platform with multiple clients, a franchise with multiple locations)

### Related Decisions
- DD-005 (Entity hierarchy in EnterpriseRBAC)
- DD-036 (Closure table for O(1) tree queries)

---

## DD-051: System Configuration for Entity Types

**Date**: 2026-01-22
**Status**: Accepted
**Deciders**: Core team
**Context**: Different deployments need different entity type vocabularies. Hardcoding "organization" as the only root type limits flexibility.

### Options Considered

1. **Hardcoded entity types**
   - Pros: Simplest implementation, no configuration needed
   - Cons: Forces specific vocabulary ("organization"), cannot adapt to different domains

2. **Config file/environment variables**
   - Pros: Simple to implement, no database changes
   - Cons: Requires code deployment to change, not UI-editable

3. **Database-stored configuration with UI**
   - Pros: Runtime configurable, UI-editable by superusers, flexible per deployment
   - Cons: Additional model and service, migration required

### Decision
Store entity type configuration in database with a SystemConfig model.

**Implementation**:

1. **SystemConfig Model** (`outlabs_auth/models/sql/system_config.py`):
```python
class SystemConfig(SQLModel, table=True):
    __tablename__ = "system_config"
    
    key: str = Field(sa_column=Column(String(100), primary_key=True))
    value: str = Field(sa_column=Column(Text, nullable=False))  # JSON encoded
    description: Optional[str] = None
    updated_at: datetime
    updated_by_id: Optional[UUID] = None
```

2. **ConfigService** (`outlabs_auth/services/config.py`):
   - `get_entity_type_config()` - Returns allowed root types and default child types
   - `set_entity_type_config()` - Updates configuration (superuser only)
   - `seed_defaults()` - Seeds default configuration on first run

3. **Config Router** (`outlabs_auth/routers/config.py`):
   - `GET /v1/config/entity-types` - Public, returns current configuration
   - `PUT /v1/config/entity-types` - Superuser only, updates configuration

4. **Default Configuration**:
```python
DEFAULT_ENTITY_TYPE_CONFIG = {
    "allowed_root_types": ["organization"],  # Backward compatible
    "default_child_types": {
        "structural": ["department", "team", "branch"],
        "access_group": ["permission_group", "admin_group"],
    },
}
```

5. **Entity Model Extension** (`outlabs_auth/models/sql/entity.py`):
```python
# Added to Entity model for per-root-entity customization
allowed_child_types: List[str] = Field(default_factory=list)
allowed_child_classes: List[str] = Field(default_factory=list)
```

**Use Cases**:

| Platform Type | Allowed Root Types | Example Child Types |
|---------------|-------------------|---------------------|
| Real Estate | `brokerage`, `solo_agent`, `internal_team` | `branch`, `team`, `agent` |
| Corporate | `organization`, `division` | `department`, `team`, `project` |
| Franchise | `franchise`, `independent_location` | `region`, `store` |
| Default | `organization` | `department`, `team`, `branch` |

**Reasoning**:
- Database storage allows runtime configuration without code deployment
- UI configuration empowers platform admins without developer involvement
- Per-root-entity customization allows each organization to define their own vocabulary
- Default configuration maintains backward compatibility

### Consequences
- **Positive**: Flexible vocabulary per deployment, UI-configurable, empowers admins
- **Positive**: Per-root-entity child type customization
- **Negative**: Additional database table and migration
- **Neutral**: Requires superuser access to configure

### Frontend Integration
- New settings page at `/settings/entity-types` (superuser only)
- EntityCreateModal fetches config for dynamic type options
- Root entities can configure their own `allowed_child_types`
- Child entity creation uses parent/root's allowed types

### Related Decisions
- DD-050 (Role scoping to root entities)
- DD-005 (Entity hierarchy in EnterpriseRBAC)
- DD-049 (PostgreSQL as primary database)

---

## DD-052: Entity Type Configuration CRUD Operations

**Date**: 2026-01-22
**Status**: Accepted
**Deciders**: Core team
**Context**: DD-051 added `allowed_child_types` and `allowed_child_classes` fields to entities, configurable at creation. Users need to edit these after creation, but removing types could orphan existing children.

### Options Considered

1. **Full CRUD (add and remove)**
   - Pros: Complete flexibility
   - Cons: Removing types could orphan existing children, backend has no validation

2. **Add-only mode (no removal)**
   - Pros: Safe - adding types never breaks existing entities
   - Cons: Cannot remove types without backend changes

3. **Full CRUD with backend validation**
   - Pros: Safe and flexible
   - Cons: Requires additional backend work, more complex

### Decision
Implement **add-only mode** in the UI for now. Removal will be added later when backend validation is implemented.

**Implementation**:

1. **EntityUpdateModal.vue** - Added child type configuration section:
   - Only shown for root entities (no parent)
   - Displays existing types as read-only badges (no remove button)
   - Input field to add new types
   - Suggestions from system defaults
   - Help text explaining add-only limitation

2. **Backend (unchanged)** - Already supports `allowed_child_types` in PATCH:
   - `EntityUpdateRequest` includes `allowed_child_types` and `allowed_child_classes`
   - No validation when types are removed (gap to address later)

**Current State**:
| Operation | UI Support | Backend Support | Notes |
|-----------|-----------|-----------------|-------|
| CREATE (set types) | Yes | Yes | Full support in EntityCreateModal |
| READ (view types) | Yes | Yes | Displayed in entity details |
| UPDATE (add types) | Yes | Yes | New in EntityUpdateModal |
| UPDATE (remove types) | No | Yes* | *No validation - could orphan children |
| DELETE | N/A | N/A | Types are strings, not records |

**Reasoning**:
- Adding types is always safe - it only expands options
- Removing types is risky without validation - could leave existing children invalid
- Better to ship safe functionality now, add removal later with proper safeguards

### Consequences
- **Positive**: Users can expand allowed child types after entity creation
- **Positive**: No risk of accidentally orphaning children
- **Negative**: Cannot remove types through UI (must use API directly or wait for backend validation)
- **Neutral**: Clear UX messaging about add-only limitation

### TODO: Future Enhancement
1. Add backend validation in `EntityService.update_entity()`:
   - When `allowed_child_types` changes, query existing children
   - If children exist with types being removed, either:
     - Reject the update with list of affected children
     - Return warning and allow (soft constraint)
     - Cascade: archive/reassign affected children
2. Once backend validation exists:
   - Enable removal in UI with confirmation dialog
   - Show affected children count before removal
   - Provide options for handling orphaned children

### Related Decisions
- DD-051 (System configuration for entity types)
- DD-050 (Role scoping to root entities)

---

## DD-053: Entity-Local Roles with Scope Control

**Date**: 2026-01-22
**Status**: Accepted
**Deciders**: Core team
**Context**: Users need roles that are defined at specific entities (not just organization root), with control over whether permissions cascade to child entities and whether roles are auto-assigned to members.

### Problem Statement
The existing role system has limitations:
1. Roles can only be created at the organization (root entity) level
2. No concept of entity-specific roles for teams/departments
3. No auto-assignment when users join an entity
4. No scope control (entity-only vs cascading to children)

### Requirements
1. **Entity-defined roles**: Allow roles to be created at any entity level
2. **Scope options**: Control whether role permissions apply only at the defining entity or cascade to descendants
3. **Auto-assignment**: Some roles should be automatically assigned when a user joins an entity
4. **Retroactive auto-assignment**: When a role becomes auto-assigned, existing members should receive it

### Decision
Extend the existing `Role` model with 3 new fields rather than creating a separate table:

```python
class RoleScope(str, Enum):
    ENTITY_ONLY = "entity_only"   # Permissions + auto-assign only at scope_entity
    HIERARCHY = "hierarchy"        # Permissions + auto-assign at scope_entity + all descendants

class Role(BaseModel, table=True):
    # EXISTING FIELDS (unchanged):
    root_entity_id: Optional[UUID]  # Organization that owns this role
    is_global: bool                  # Available everywhere in hierarchy
    is_system_role: bool             # Protected from modification
    
    # NEW FIELDS:
    scope_entity_id: Optional[UUID]  # Entity where this role is defined (NULL = root/system level)
    scope: RoleScope = HIERARCHY     # Controls BOTH permissions AND auto-assignment scope
    is_auto_assigned: bool = False   # Auto-assign to members within scope
```

### Behavior Matrix

| `scope` | `is_auto_assigned` | Permissions Apply To | Auto-Assigned To |
|---------|-------------------|---------------------|------------------|
| `entity_only` | `false` | scope_entity only | Nobody (manual) |
| `entity_only` | `true` | scope_entity only | All members of scope_entity |
| `hierarchy` | `false` | scope_entity + descendants | Nobody (manual) |
| `hierarchy` | `true` | scope_entity + descendants | All members of scope_entity + descendants |

### Role Availability Rules
A role is available for assignment at entity X if:
1. **System-wide**: `is_global=true` AND `root_entity_id=NULL`
2. **Org-scoped**: `root_entity_id` matches X's root AND `scope_entity_id=NULL`
3. **Entity-local (hierarchy)**: `scope_entity_id` is X or an ancestor AND `scope=hierarchy`
4. **Entity-local (entity_only)**: `scope_entity_id = X` AND `scope=entity_only`

### Implementation Details

**Backend Changes**:
- `outlabs_auth/models/sql/enums.py` - Added `RoleScope` enum
- `outlabs_auth/models/sql/role.py` - Added 3 new fields with FK to entities
- `outlabs_auth/services/role.py` - Updated `get_roles_for_entity()`, `create_role()`, `update_role()`
- `outlabs_auth/services/membership.py` - Added auto-assignment in `add_member()`, `apply_auto_assigned_role()`
- `outlabs_auth/services/permission.py` - Updated scope checking in `_check_permission_in_entity()`
- `outlabs_auth/schemas/role.py` - Added new fields to request/response schemas
- `outlabs_auth/schemas/membership.py` - Added `EntityMemberResponse` with user details
- `outlabs_auth/routers/roles.py` - Updated to handle new fields
- `outlabs_auth/routers/memberships.py` - Added `/entity/{id}/details` endpoint

**Frontend Changes**:
- External UI repo (`OutlabsAuthUI`) received the matching frontend changes
  for role scope types, membership types, membership API/query wiring, the
  entity members tab, and the add-member modal.

**Migration**: New columns with safe defaults (`scope_entity_id=NULL`, `scope=hierarchy`, `is_auto_assigned=false`)

### Example Scenario
```
Marketing Team (entity)
├── Auto-assigned roles (scope=hierarchy, is_auto_assigned=true):
│   - "marketing-viewer" → Everyone in Marketing + all child entities gets this
├── Auto-assigned roles (scope=entity_only, is_auto_assigned=true):
│   - "marketing-member" → Only direct Marketing members get this
├── Selectable roles (is_auto_assigned=false):
│   - "marketing-manager" (scope=hierarchy) → Manual, permissions cascade
│   - "content-approver" (scope=entity_only) → Manual, permissions don't cascade
└── Children:
    ├── Social Media Sub-team
    └── Content Sub-team
```

### Consequences
- **Positive**: Teams can define their own roles without admin intervention
- **Positive**: Auto-assignment reduces manual role management
- **Positive**: Scope control allows fine-grained permission boundaries
- **Positive**: Retroactive auto-assignment ensures consistency
- **Negative**: Increased complexity in role availability logic
- **Neutral**: Role names are unique per `scope_entity_id` (allows "member" role in multiple entities)

### Related Decisions
- DD-050 (Role scoping to root entities) - This extends that concept further
- DD-036 (Closure table) - Used for efficient ancestor/descendant queries

---

## DD-054: Permission Scope Enforcement

**Date**: 2026-01-22
**Status**: Accepted
**Category**: Security / Permission System

**Context**: After implementing entity-local roles (DD-053), a permission scope leakage issue was discovered where entity-local roles grant permissions globally when no entity context is provided.

### Problem Statement

When `check_permission(user_id, "permission")` is called WITHOUT an `entity_id`:
- Permissions from ALL roles were aggregated (global + entity-local)
- Entity-local roles (with `scope_entity_id` set) granted their permissions globally
- This violated the intended scope - a role "scoped to Marketing" shouldn't grant system-wide permissions

**Example of Broken Behavior (Before Fix)**:
```python
# Setup:
# - Role "team-admin" at Marketing (scope_entity_id=marketing_id, scope=entity_only)
# - Role has "user:create" permission
# - User has "team-admin" role via UserRoleMembership

check_permission(user_id, "user:create")  # No entity_id
# → Returned TRUE (WRONG - role is entity-scoped!)

check_permission(user_id, "user:create", entity_id=marketing_id)
# → Returned TRUE (CORRECT - checked in entity context)
```

### Decision: Role-Based Filtering

The ROLE's scope determines when its permissions apply, not the permission itself.

**Behavior Matrix**:

| Role Type | `entity_id` provided? | Permissions granted? |
|-----------|----------------------|---------------------|
| Global role (`is_global=true`) | No | ✅ Yes |
| Global role (`is_global=true`) | Yes | ✅ Yes |
| Org-scoped role (`root_entity_id` set, `scope_entity_id=NULL`) | No | ✅ Yes |
| Org-scoped role | Yes | ✅ Yes (if entity in org) |
| Entity-local role (`scope_entity_id` set) | No | ❌ No |
| Entity-local role | Yes | ✅ Yes (if scope matches) |

**Mental Model for Developers**:
- **Global role** → permissions work everywhere
- **Org-scoped role** → permissions work globally within the org
- **Entity-local role** → permissions only work in entity context

### Implementation

**`outlabs_auth/services/permission.py`**:

1. **Added `include_entity_local` parameter to `get_user_permissions()`**:
   ```python
   async def get_user_permissions(
       self,
       session: AsyncSession,
       user_id: UUID,
       include_entity_local: bool = True,  # NEW
   ) -> List[str]:
   ```
   When `False`, excludes permissions from entity-local roles.

2. **Added `_get_global_role_permissions()` helper**:
   Returns only permissions from global and org-scoped roles (excludes entity-local).

3. **Modified `check_permission()`**:
   - When `entity_id is None`: Uses `include_entity_local=False` to exclude entity-local roles
   - When `entity_id is provided`: Uses `include_entity_local=True` (full check)

4. **Updated `_check_permission_via_user_roles_with_abac()`**:
   Added `include_entity_local` parameter for ABAC path consistency.

**`outlabs_auth/dependencies/__init__.py`**:
- Already correctly extracts `entity_id` from request (path params, query params, or `X-Entity-Context` header)
- Passes `None` when no entity context found, triggering the new filtering behavior

### Test Coverage

New test file: `tests/unit/services/test_permission_scope.py` (12 tests)

1. Global role grants permission without entity context ✅
2. Global role grants permission with entity context ✅
3. Entity-local role DENIES permission without entity context ✅
4. Entity-local role GRANTS permission with matching entity context ✅
5. Entity-local role DENIES permission with wrong entity context ✅
6. Entity-local role (scope=hierarchy) grants in descendant entity ✅
7. Entity-local role (scope=entity_only) denies in descendant entity ✅
8. Org-scoped role grants without entity context ✅
9. Mixed roles: only global applies without context ✅
10. Mixed roles: both apply with entity context ✅
11. Superuser bypasses all scope checks ✅
12. `get_user_permissions(include_entity_local=False)` filters correctly ✅

### Migration / Breaking Change Notes

This is a **potentially breaking change** for code that:
1. Uses entity-local roles but checks permissions without entity context
2. Relies on the previous "leaked" behavior

**Mitigation**:
- If you need a permission to work globally, assign it to a global role
- If you need entity-scoped permissions, ensure you pass `entity_id` to permission checks
- Use `require_entity_permission()` for endpoints that require entity context

### Consequences

- **Positive**: Fixes security hole where entity-scoped permissions leaked globally
- **Positive**: Behavior now matches developer mental model
- **Positive**: No schema changes required (purely behavioral fix)
- **Positive**: Backwards compatible for global roles (SimpleRBAC unaffected)
- **Negative**: May break code relying on leaked permissions (intentional fix)

### Related Decisions

- DD-053 (Entity-Local Roles) - Introduced entity-local roles that this decision fixes
- DD-035 (Unified AuthDeps) - Provides the entity context extraction logic

---

## DD-055: Entity Authorization Remains Role-Only

**Date**: 2026-03-17
**Status**: Accepted
**Deciders**: Core team
**Context**: The live entity schemas and docs advertised `entity.direct_permissions` and `entity.metadata`, but the runtime system already grants entity access through roles and memberships only. Keeping placeholder entity-owned permissions would create a second authorization model without a clear use case.

### Options Considered

1. **Implement entity direct permissions**
   - Pros: Fewer records for trivial cases, possible shortcut for simple grants
   - Cons: Duplicates the role model, weakens auditability, complicates inheritance and UI explainability

2. **Keep placeholders in the live contract**
   - Pros: Avoids a breaking API correction
   - Cons: Leaves the runtime contract dishonest and encourages unsupported integrations

3. **Keep entity authorization role-only**
   - Pros: Single grant model, clearer audit trail, matches DD-053/DD-054, keeps entities as scope containers rather than raw permission bags
   - Cons: Some simple admin workflows may require managed roles instead of direct toggles

### Decision

Entity authorization remains role-only.

Entities do not store live direct permission grants. Access is granted through:

- direct user role memberships
- entity membership roles
- entity-local roles with `entity_only` or `hierarchy` scope
- auto-assigned entity-local roles

`entity.direct_permissions` is removed from the live model, schemas, and frontend types.

`entity.metadata` is also removed from the live entity contract until it becomes a real persisted feature with explicit storage, API behavior, and tests.

### Consequences

- **Positive**: Preserves a single authorization model centered on roles
- **Positive**: Improves explainability and auditability for entity access
- **Positive**: Aligns the entity API with the persisted SQL model
- **Negative**: Any UI that wants per-entity permission toggles must express them through managed roles instead of raw permission arrays
- **Neutral**: Future entity metadata is still possible, but only as a fully implemented persisted feature

### Related Decisions

- DD-053 (Entity-Local Roles with Scope Control)
- DD-054 (Permission Scope Enforcement)

---

## Questions Still Open

Track questions that need decisions:

### Q-001: PostgreSQL Support in v1.0?
**Status**: ~~Open~~ **RESOLVED** (DD-049)
**Resolution**: PostgreSQL is now the primary and only database.

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
| 2025-01-14 | DD-038 through DD-046 | All Accepted (FastAPI-Users Inspired Patterns) |
| 2025-01-14 | DD-047 | Accepted (UserRoleMembership for SimpleRBAC) |
| 2025-01-26 | DD-048 | Accepted (Redis Configuration Simplification) |
| 2025-01-14 | **DD-049** | **Accepted (PostgreSQL as Primary Database)** |
| 2025-01-14 | DD-003 | Superseded by DD-015 |
| 2025-01-14 | DD-004 | **Superseded by DD-049** |
| 2025-01-26 | DD-028 | **CORRECTED** - Changed from argon2id to SHA-256 for API keys; made refresh token rotation optional |
| 2025-01-26 | DD-031 | Superseded by DD-028 (corrected) |
| 2025-01-14 | DD-030 | Superseded by DD-035 |
| 2026-01-22 | **DD-050** | **Accepted (Role Scoping to Root Entities)** |
| 2026-01-22 | **DD-051** | **Accepted (System Configuration for Entity Types)** |
| 2026-01-22 | **DD-052** | **Accepted (Entity Type Configuration CRUD Operations)** |
| 2026-01-22 | **DD-053** | **Accepted (Entity-Local Roles with Scope Control)** |
| 2026-01-22 | **DD-054** | **Accepted (Permission Scope Enforcement)** |
| 2026-03-17 | **DD-055** | **Accepted (Entity Authorization Remains Role-Only)** |

---

**Last Updated**: 2026-03-17 (DD-055 added: entity authorization remains role-only)
**Next Review**: After testing all examples
