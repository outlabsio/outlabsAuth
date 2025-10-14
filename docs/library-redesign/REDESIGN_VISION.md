# OutlabsAuth Library Redesign - Vision Document

**Version**: 1.0
**Date**: 2025-01-14
**Status**: Planning Phase
**Branch**: `library-redesign`

---

## Executive Summary

We are transforming **OutlabsAuth** from a centralized authentication API service into a **flexible FastAPI library** that can be integrated directly into applications as a dependency. This redesign maintains our powerful entity hierarchy and permission system while dramatically simplifying deployment and reducing operational complexity.

### What's Changing
- **From**: Standalone FastAPI service → Multi-platform isolation → Centralized auth bottleneck
- **To**: Python library → Single-tenant per app → In-process auth

### What's Staying
- ✅ Unified entity model (STRUCTURAL + ACCESS_GROUP)
- ✅ Context-aware roles (permissions adapt by entity type)
- ✅ Tree permissions (hierarchical access control)
- ✅ Flexible entity types (any organizational terminology)
- ✅ Hybrid authorization (RBAC + ReBAC + ABAC)

---

## Why This Change?

### Problems with Centralized API

1. **Operational Overhead**
   - One more service to deploy, monitor, and maintain
   - Requires separate database instance
   - Network hop adds latency to every auth check
   - Single point of failure

2. **Complexity We Don't Need**
   - Multi-platform isolation when we typically work on single platforms
   - Platform switching logic that rarely gets used
   - Cross-platform concepts that add cognitive load

3. **Development Friction**
   - Can't work offline without auth service running
   - Testing requires spinning up full auth stack
   - Harder to customize per-application needs

4. **Deployment Constraints**
   - Every project needs access to centralized auth
   - Version updates affect all projects simultaneously
   - Can't have per-project auth customizations

### Benefits of Library Approach

1. **Simplicity**
   - Install as pip dependency: `pip install outlabs-auth`
   - Integrate in minutes, not hours
   - No separate service to manage

2. **Performance**
   - In-process auth checks (no network calls)
   - Direct database access
   - Cacheable at application level

3. **Flexibility**
   - Each app configures auth to its needs
   - Can customize models and logic
   - Gradual complexity (simple → hierarchical → full)

4. **Development Experience**
   - Works offline
   - Easy to test and mock
   - Fast iteration cycles

5. **Deployment Freedom**
   - Deploy independently
   - Update at own pace
   - No cross-project version conflicts

---

## Core Principles

### 1. **Gradual Complexity**

The library supports three preset modes, allowing projects to start simple and add complexity as needed:

```python
# Level 1: Simple RBAC
auth = SimpleRBAC(database=db)
# Just users, roles, and permissions

# Level 2: Hierarchical
auth = HierarchicalRBAC(database=db)
# Adds entity hierarchy and tree permissions

# Level 3: Full Featured
auth = FullFeatured(database=db)
# Adds context-aware roles and ABAC conditions
```

### 2. **Sensible Defaults**

Works out of the box with minimal configuration:
```python
from outlabs_auth import OutlabsAuth

auth = OutlabsAuth(database=mongo_client)
# That's it! Ready to use
```

### 3. **Escape Hatches**

Everything is extensible:
```python
from outlabs_auth import OutlabsAuth
from outlabs_auth.models import UserModel

# Custom user model
class MyUserModel(UserModel):
    company_id: str
    custom_field: str

auth = OutlabsAuth(database=db, user_model=MyUserModel)
```

### 4. **FastAPI Native**

Designed specifically for FastAPI:
```python
from fastapi import Depends

@app.get("/protected")
async def protected_route(
    user = Depends(auth.get_current_user),
    has_perm = Depends(auth.require_permission("resource:action"))
):
    return {"user": user}
```

---

## Success Criteria

### Must Have
- ✅ Works as drop-in pip dependency
- ✅ Three clear preset modes (Simple, Hierarchical, Full)
- ✅ Maintains current entity hierarchy capabilities
- ✅ Tree permissions work identically
- ✅ Context-aware roles preserved
- ✅ Comprehensive documentation
- ✅ Example applications for each preset
- ✅ 90%+ test coverage
- ✅ Migration guide from centralized API

### Nice to Have
- 🎯 Support for PostgreSQL (in addition to MongoDB)
- 🎯 CLI tool for bootstrapping
- 🎯 Admin UI components (optional package)
- 🎯 OpenTelemetry integration
- 🎯 Multi-tenant mode (optional)

### Out of Scope (For Now)
- ❌ Cross-application SSO (each app is independent)
- ❌ Shared user directory across apps
- ❌ Central admin panel for all apps
- ❌ OAuth2 provider functionality

---

## Design Philosophy

### Keep What Works

Our current system has several brilliant design elements:

1. **Unified Entity Model**
   - Everything is an entity (no separate groups table)
   - Two classes: STRUCTURAL and ACCESS_GROUP
   - Flexible types as strings (not enums)
   - **Decision**: Keep this design, it's elegant

2. **Context-Aware Roles**
   - Roles adapt based on entity type
   - One role definition, multiple behaviors
   - Reduces role explosion
   - **Decision**: Keep this, it's powerful

3. **Tree Permissions**
   - `resource:action` = entity-specific
   - `resource:action_tree` = all descendants
   - `resource:action_all` = platform-wide
   - **Decision**: Keep the model, simplify "all" to mean "everywhere in this app"

### Simplify What's Complex

1. **Remove Platform Abstraction**
   - **Old**: Multiple platforms per deployment
   - **New**: One "tenant" per application (optional multi-tenant mode)
   - **Change**: Remove `platform_id`, optionally add `tenant_id`

2. **Simplify Permission System**
   - **Old**: System permissions vs custom permissions distinction
   - **New**: All permissions are equal, some are built-in
   - **Change**: Remove platform-scoped permission logic

3. **Remove Cross-Platform Features**
   - **Old**: Platform admins, platform switching, isolation
   - **New**: App-level admin, single context
   - **Change**: Remove platform management entirely

### Make Optional What's Advanced

1. **ABAC Conditions**
   - Powerful but not always needed
   - Add complexity only when required
   - **Change**: Make this opt-in per preset

2. **Multi-Tenant**
   - Most apps are single-tenant
   - Add tenant isolation only if needed
   - **Change**: Off by default, enable with flag

3. **Permission Caching**
   - Great for performance
   - Adds Redis dependency
   - **Change**: Optional, with in-memory fallback

---

## Target Audience

### Primary: Internal Projects

1. **Property Management Platform** (Diverse)
   - Needs: Hierarchical RBAC with office/team structure
   - Preset: Hierarchical mode
   - Custom: Real estate specific permissions

2. **Social Media Platform** (qdarte)
   - Needs: Simple RBAC with user roles
   - Preset: Simple mode
   - Custom: Content moderation permissions

3. **Referral Platform**
   - Needs: Entity hierarchy for agent teams
   - Preset: Hierarchical mode
   - Custom: Commission and lead permissions

4. **Future Projects**
   - Unknown requirements
   - Need flexibility to adapt
   - Should work for 80% of use cases out of the box

### Secondary: Open Source Community

If we open source this (likely), users need:
- Clear documentation
- Example applications
- Active maintenance
- Responsive to issues
- Good test coverage

---

## Non-Goals

To maintain focus, we explicitly are NOT trying to:

1. **Compete with Auth0/Clerk**
   - We're building for our own needs, not a SaaS product
   - No hosted service, no monetization
   - Not trying to be feature-complete with commercial offerings

2. **Support Every Database**
   - MongoDB primary, PostgreSQL stretch goal
   - Not trying to support MySQL, SQLite, etc.

3. **Be Framework Agnostic**
   - FastAPI first and foremost
   - Not trying to work with Flask, Django, etc.

4. **Provide Social Login**
   - OAuth2 client is out of scope (for now)
   - Apps can add this themselves if needed

5. **Build an Admin UI**
   - Library provides backend logic only
   - Example admin UI as separate package (maybe)
   - Each app can build their own UI

---

## Timeline

**Total Duration**: 7-8 weeks

- **Weeks 1-2**: Core library + Simple preset
- **Weeks 3-4**: Hierarchical preset + entity system
- **Weeks 5-6**: Full featured preset + advanced features
- **Week 7**: Documentation, examples, testing
- **Week 8**: Migration guides, polish, release prep

See [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) for detailed phase breakdown.

---

## Documentation Structure

This vision document is the hub. Related documents:

1. **[LIBRARY_ARCHITECTURE.md](LIBRARY_ARCHITECTURE.md)** - Technical architecture details
2. **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)** - Week-by-week implementation plan
3. **[API_DESIGN.md](API_DESIGN.md)** - Developer experience and code examples
4. **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Converting from centralized API
5. **[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** - Why we made specific choices
6. **[COMPARISON_MATRIX.md](COMPARISON_MATRIX.md)** - Feature comparison across modes

---

## Questions to Address

As we implement, we need to answer:

1. **Database Migrations**: How do apps handle schema changes?
2. **Multi-Tenancy**: Do we support it from day one or add later?
3. **Admin UI**: Separate package or include examples?
4. **Testing Utilities**: What helpers do we provide for testing?
5. **Plugin System**: Should we support custom extensions?

These will be documented in [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) as we progress.

---

## Risk Assessment

### Technical Risks

1. **Beanie Limitations**
   - May not support all database backends
   - Mitigation: Document limitations clearly

2. **Breaking Changes**
   - Existing projects need migration path
   - Mitigation: Comprehensive migration guide + tools

3. **Complexity Creep**
   - Feature requests could balloon scope
   - Mitigation: Clear non-goals, disciplined roadmap

### Organizational Risks

1. **Time Investment**
   - 7-8 weeks is significant
   - Mitigation: Phased approach, working software at each phase

2. **Adoption**
   - Internal teams need to migrate
   - Mitigation: Show clear benefits, provide migration support

3. **Maintenance**
   - Library needs ongoing support
   - Mitigation: Good documentation, comprehensive tests

---

## Next Steps

1. ✅ **This Document**: Vision and goals defined
2. 🔄 **Architecture**: Define technical implementation (next)
3. ⏭️ **Roadmap**: Break down into actionable tasks
4. ⏭️ **API Design**: Mock up developer experience
5. ⏭️ **Prototype**: Build Simple preset MVP

---

## Feedback and Iteration

This is a living document. As we learn during implementation:

- Update design decisions
- Adjust timeline as needed
- Clarify scope based on discoveries
- Document trade-offs made

**Last Updated**: 2025-01-14
**Next Review**: After Phase 1 completion
