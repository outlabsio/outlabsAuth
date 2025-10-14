# OutlabsAuth Library - Design Decisions Log

**Version**: 1.0
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
**Status**: Accepted
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

### Decision
Three preset classes that build on each other:
- `SimpleRBAC`: Basic RBAC
- `HierarchicalRBAC`: + Entity hierarchy
- `FullFeatured`: + Advanced features

**Reasoning**:
- Clear progression path
- Easy to understand what each level provides
- Can start simple and upgrade later
- Code reuse through inheritance

### Consequences
- **Positive**: Clear mental model, gradual complexity
- **Negative**: Some code duplication, need good inheritance design
- **Neutral**: Three entry points instead of one

### Related Decisions
- DD-001 (Library approach)
- DD-008 (Context-aware roles)

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

---

**Last Updated**: 2025-01-14
**Next Review**: End of Phase 1 (Week 2)
