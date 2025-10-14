# OutlabsAuth Library - Implementation Roadmap

**Version**: 1.1
**Date**: 2025-01-14
**Total Duration**: 6-7 weeks (saved 1 week with two-preset architecture)
**Status**: Planning Phase

---

## Overview

This document breaks down the library redesign into 5 phases, each with clear deliverables and success criteria. Phases build on each other, with working software at each stage.

**Key Change**: Consolidated into TWO presets (Simple and Enterprise) instead of three, saving 1 week by eliminating middle preset.

---

## Phase Summary

| Phase | Duration | Focus | Deliverable |
|-------|----------|-------|-------------|
| Phase 1 | Week 1 | Core foundation + SimpleRBAC | Working simple RBAC |
| Phase 2 | Week 2 | Complete SimpleRBAC + Tests | Production-ready simple preset |
| Phase 3 | Week 3 | EnterpriseRBAC - Entity system | Entity hierarchy + tree permissions |
| Phase 4 | Week 4 | EnterpriseRBAC - Optional features | Context-aware roles + ABAC + caching |
| Phase 5 | Week 5 | EnterpriseRBAC complete + Testing | Production-ready enterprise preset |
| Phase 6 | Week 6-7 | Documentation + Examples + Polish | Ready for production use |

---

## Phase 1: Core Foundation + SimpleRBAC (Week 1)

### Goals
- Establish package structure
- Create base models
- Implement SimpleRBAC preset
- Basic authentication working

### Tasks

#### Day 1-2: Package Structure
- [ ] Create `outlabs_auth/` package structure
- [ ] Set up `pyproject.toml` with dependencies
- [ ] Create base configuration classes
- [ ] Set up development environment (linting, formatting)

**Deliverable**: Clean package structure, installable with `pip install -e .`

#### Day 3-4: Core Models
- [ ] Port `UserModel` from current system
  - Remove `platform_id` references
  - Add optional `tenant_id`
  - Keep status system
- [ ] Port `RoleModel` (basic version without entity_type_permissions)
- [ ] Port `PermissionModel` (basic version without conditions)
- [ ] Create `RefreshTokenModel`
- [ ] Create `BaseDocument` abstraction

**Deliverable**: Core models defined and tested

#### Day 5-7: SimpleRBAC Implementation
- [ ] Implement `OutlabsAuth` base class
- [ ] Create `AuthService`:
  - Login/logout
  - JWT token generation
  - Token validation
  - Refresh token rotation
- [ ] Create `UserService`:
  - User CRUD operations
  - Password management
- [ ] Create `RoleService` (basic):
  - Role CRUD operations
  - Assign role to user
- [ ] Create `BasicPermissionService`:
  - Check if user has permission
  - Get user's permissions
- [ ] Implement `SimpleRBAC` preset class
- [ ] Create FastAPI dependencies:
  - `get_current_user`
  - `require_permission`

**Deliverable**: Working `SimpleRBAC` that can be used in a FastAPI app

### Success Criteria
- [ ] Can install package locally
- [ ] Can create SimpleRBAC instance
- [ ] Can register and login users
- [ ] Can assign roles to users
- [ ] Can check permissions in FastAPI routes
- [ ] Basic unit tests pass (>70% coverage)

### Blockers & Risks
- **Risk**: Beanie ODM changes from current implementation
  - *Mitigation*: Start with MongoDB, defer PostgreSQL
- **Risk**: JWT implementation differs from current
  - *Mitigation*: Copy proven implementation from current system

---

## Phase 2: Complete SimpleRBAC (Week 2)

### Goals
- Production-ready SimpleRBAC
- Comprehensive testing
- First example application
- Basic documentation

### Tasks

#### Day 1-2: Enhanced Features
- [ ] Password validation and requirements
- [ ] Account lockout after failed attempts
- [ ] Email verification (optional)
- [ ] Password reset flow
- [ ] User profile management

**Deliverable**: Complete user management features

#### Day 3-4: Testing
- [ ] Unit tests for all services (>90% coverage)
- [ ] Integration tests for SimpleRBAC flows
- [ ] Test fixtures and utilities
- [ ] CI/CD setup (GitHub Actions)

**Deliverable**: Comprehensive test suite

#### Day 5-6: Example Application
- [ ] Create `examples/simple_app/`
- [ ] FastAPI app with:
  - User registration
  - Login/logout
  - Protected routes
  - Role management
  - Permission checks
- [ ] README with setup instructions

**Deliverable**: Working example app

#### Day 7: Documentation
- [ ] API reference for SimpleRBAC
- [ ] Quick start guide
- [ ] Configuration options
- [ ] Code examples

**Deliverable**: Basic documentation

### Success Criteria
- [ ] SimpleRBAC passes all tests
- [ ] Example app runs and demonstrates features
- [ ] Documentation clear and complete
- [ ] Can be used in production for simple RBAC needs

### Blockers & Risks
- **Risk**: Test coverage is time-consuming
  - *Mitigation*: Focus on critical paths first
- **Risk**: Example app scope creep
  - *Mitigation*: Keep it minimal, just demonstrate features

---

## Phase 3: EnterpriseRBAC - Entity System (Week 3)

### Goals
- Add entity hierarchy support
- Implement entity membership
- Tree permissions foundation
- Begin EnterpriseRBAC preset

### Tasks

#### Day 1-2: Entity Models
- [ ] Port `EntityModel`:
  - Remove `platform_id`, add optional `tenant_id`
  - Keep entity_class (STRUCTURAL, ACCESS_GROUP)
  - Keep flexible entity_type
  - Hierarchy relationships
- [ ] Port `EntityMembershipModel`:
  - User-Entity-Roles relationship
  - Time-based validity
- [ ] Add database indexes for performance

**Deliverable**: Entity models defined

#### Day 3-4: Entity Service
- [ ] Create `EntityService`:
  - Create entity
  - Update entity
  - Delete entity (with cascading rules)
  - Get entity path (root to entity)
  - Get descendants
  - Validate hierarchy (no cycles, depth limits)
- [ ] Create `MembershipService`:
  - Add member to entity
  - Remove member from entity
  - Update member roles
  - Get entity members
  - Get user's entities

**Deliverable**: Entity management working

#### Day 5-7: Tree Permissions
- [ ] Enhance `PermissionService` for hierarchy:
  - Check permission in entity context
  - Check tree permissions (checks parent entities)
  - Resolve user permissions across all memberships
- [ ] Implement permission resolution algorithm:
  1. Check direct permission in target entity
  2. Check _tree permission in parent entities
  3. Check _all permission anywhere
- [ ] Add permission caching (in-memory for now)

**Deliverable**: Tree permissions working

### Success Criteria
- [ ] Can create entity hierarchies
- [ ] Can assign users to entities with roles
- [ ] Tree permissions work correctly (user with entity:update_tree in parent can update children)
- [ ] Unit tests for entity operations (>85% coverage)
- [ ] Integration tests for tree permissions

### Blockers & Risks
- **Risk**: Tree permission logic complex
  - *Mitigation*: Port existing tested implementation
- **Risk**: Performance with deep hierarchies
  - *Mitigation*: Add depth limits, optimize queries

---

## Phase 4: EnterpriseRBAC - Optional Features (Week 4)

### Goals
- Context-aware roles
- ABAC conditions foundation
- Caching with Redis

### Tasks

#### Day 1-3: Context-Aware Roles
- [ ] Add `entity_type_permissions` to RoleModel
- [ ] Update RoleService to handle context-aware roles
- [ ] Update PermissionService to apply context-aware permissions:
  - Get entity type from context
  - Use type-specific permissions if available
  - Fall back to default permissions
- [ ] Add validation for entity_type_permissions

**Deliverable**: Context-aware roles working

#### Day 4-5: ABAC Conditions
- [ ] Add `Condition` model:
  - attribute, operator, value
- [ ] Add `conditions` field to PermissionModel
- [ ] Create `PolicyEvaluationEngine`:
  - Build evaluation context
  - Evaluate conditions
  - Support operators (EQUALS, LESS_THAN, IN, etc.)
- [ ] Update PermissionService:
  - `check_permission_with_context()` method
  - RBAC → ReBAC → ABAC flow

**Deliverable**: ABAC conditions working

#### Day 6-7: Performance & Caching
- [ ] Integrate Redis for caching (optional)
- [ ] Cache user permissions
- [ ] Cache entity paths
- [ ] Cache invalidation strategies
- [ ] In-memory cache fallback (if Redis not available)
- [ ] Performance benchmarks

**Deliverable**: Caching implemented

### Success Criteria
- [ ] Context-aware roles work correctly (tests verify permissions change by entity type)
- [ ] ABAC conditions evaluate properly
- [ ] Caching improves performance measurably
- [ ] Unit tests for new features (>85% coverage)

### Blockers & Risks
- **Risk**: ABAC complexity explodes
  - *Mitigation*: Start with basic operators, expand gradually
- **Risk**: Caching adds complexity
  - *Mitigation*: Make Redis optional, provide fallback
- **Risk**: Context-aware roles hard to understand
  - *Mitigation*: Excellent documentation with examples

---

## Phase 5: EnterpriseRBAC Complete + Testing (Week 5)

### Goals
- Complete EnterpriseRBAC preset with all optional features
- Comprehensive testing across all configurations
- Performance benchmarks
- Enterprise example app

### Tasks

#### Day 1-2: EnterpriseRBAC Implementation
- [ ] Create `EnterpriseRBAC` preset class
- [ ] Integrate all features:
  - Entity hierarchy (always enabled)
  - Context-aware roles (optional)
  - ABAC conditions (optional)
  - Redis caching (optional)
  - Multi-tenant support (optional)
  - Audit logging (optional)
- [ ] Create `EnterprisePermissionService`:
  - Inherits from BasicPermissionService
  - Adds entity hierarchy + tree permissions
  - Optionally adds ABAC evaluation
  - Optionally adds caching
- [ ] Full configuration options with feature flags

**Deliverable**: EnterpriseRBAC preset complete

#### Day 3-4: Comprehensive Testing
- [ ] Unit tests for all EnterpriseRBAC features
- [ ] Unit tests for context-aware roles
- [ ] Unit tests for ABAC engine
- [ ] Integration tests:
  - Entity hierarchy scenarios
  - Tree permission scenarios
  - Context-aware role scenarios
  - ABAC policy evaluation
  - Cache hit/miss scenarios
  - Multi-tenant isolation (if enabled)
- [ ] Performance tests (cached vs uncached)
- [ ] Test all feature flag combinations

**Deliverable**: Comprehensive test coverage (>90%)

#### Day 5-6: Example Application
- [ ] Create `examples/enterprise_app/`
- [ ] FastAPI app demonstrating:
  - Basic configuration (entity hierarchy only)
  - Full configuration (all optional features enabled)
  - Organization → Department → Team hierarchy
  - Entity management UI (basic)
  - Context-aware roles
  - ABAC conditions (e.g., invoice approval with amount limits)
  - Cached permission checks
  - Performance comparison
- [ ] Multiple configuration examples
- [ ] README with setup instructions

**Deliverable**: Enterprise example app

#### Day 7: Documentation & Polish
- [ ] EnterpriseRBAC API reference
- [ ] Configuration guide (feature flags explained)
- [ ] Entity system guide
- [ ] Tree permissions explained
- [ ] Context-aware roles guide
- [ ] ABAC conditions guide
- [ ] Performance tuning guide
- [ ] Migration from SimpleRBAC to EnterpriseRBAC

**Deliverable**: Complete EnterpriseRBAC documentation

### Success Criteria
- [ ] EnterpriseRBAC passes all tests
- [ ] Example app demonstrates all features and configurations
- [ ] Tree permissions thoroughly tested
- [ ] Documentation clear with examples
- [ ] Performance benchmarks show caching benefits
- [ ] Feature flags work correctly (can enable/disable features)
- [ ] Ready for production use

### Blockers & Risks
- **Risk**: Too many optional features, complex configuration
  - *Mitigation*: Excellent defaults, clear documentation, configuration validator
- **Risk**: Feature flag combinations create too many test scenarios
  - *Mitigation*: Focus on common configurations, document limitations
- **Risk**: ABAC edge cases not covered
  - *Mitigation*: Thorough testing, document limitations

---

## Phase 6: Documentation, Examples & Polish (Weeks 6-7)

### Goals
- Complete comprehensive documentation
- CLI tools for common operations
- Health check system
- Permission explanation debugger
- Security hardening guide
- Testing and deployment guides
- Migration guides
- Package for distribution
- Internal rollout preparation

### Tasks

#### Week 6, Day 1-2: CLI Tools & Health Checks
- [ ] Create `outlabs-auth` CLI:
  - User management commands
  - Role management commands
  - Entity management commands (EnterpriseRBAC)
  - Database initialization
  - Permission listing/debugging
  - Health check command
- [ ] Implement health check system:
  - Database connectivity
  - Redis connectivity (if enabled)
  - Permission service health
  - Entity service health (EnterpriseRBAC)
- [ ] Create "explain permission" debugger:
  - Shows why user has/doesn't have permission
  - Traces permission resolution path
  - Shows all applicable roles and memberships
  - Tree permission visualization

**Deliverable**: CLI tools and health checks

#### Week 6, Day 3-5: Comprehensive Documentation Guides
- [ ] Create `SECURITY.md`:
  - JWT best practices
  - Password requirements
  - Rate limiting setup
  - CORS configuration
  - SQL injection prevention (if PostgreSQL)
  - Security audit checklist
  - Common vulnerabilities and mitigations
- [ ] Create `TESTING_GUIDE.md`:
  - AuthTestCase base class
  - Test fixtures and utilities
  - Testing isolation patterns
  - Performance testing scenarios
  - Testing with different configurations
- [ ] Create `DEPLOYMENT_GUIDE.md`:
  - Horizontal scaling patterns
  - State management
  - Redis configuration
  - Load balancing considerations
  - Database connection pooling
  - Monitoring and logging
- [ ] Create `ERROR_HANDLING.md`:
  - Exception hierarchy
  - Error codes
  - Retry strategies
  - Graceful degradation patterns

**Deliverable**: Comprehensive production guides

#### Week 6, Day 6-7: Core Documentation
- [ ] Complete API reference for all presets
- [ ] Quick start guides (5-minute, 15-minute, 1-hour)
- [ ] Conceptual guides:
  - Entity hierarchy explained
  - Tree permissions visualized
  - Context-aware roles examples
  - ABAC use cases
- [ ] Configuration reference
- [ ] Troubleshooting guide
- [ ] FAQ

**Deliverable**: Comprehensive documentation site

#### Week 7, Day 1-2: Migration Guides
- [ ] Complete MIGRATION_GUIDE.md (mark as reference, de-emphasize since starting fresh internally)
- [ ] Create `examples/migration_example/`:
  - Before: centralized API
  - After: library integration
  - Step-by-step migration
- [ ] Before/after code examples
- [ ] Migration checklist (for external users)

**Deliverable**: Migration resources

#### Week 7, Day 3-4: Package Distribution
- [ ] Finalize `pyproject.toml`
- [ ] Set up PyPI publishing (private initially)
- [ ] Version tagging strategy
- [ ] Changelog format
- [ ] Release process documentation
- [ ] CI/CD pipeline finalization

**Deliverable**: Publishable package

#### Week 7, Day 5-6: Additional Examples & Extensions
- [ ] Create `examples/multi_tenant_app/` (if multi-tenant implemented)
- [ ] Create `examples/custom_extension/` (how to extend the library)
- [ ] Document extension points and hooks
- [ ] Custom middleware examples
- [ ] Custom validation examples

**Deliverable**: Extension examples

#### Week 7, Day 7: Final Polish & Security Review
- [ ] Code cleanup and refactoring
- [ ] Performance optimization
- [ ] Security audit (follow SECURITY.md checklist)
- [ ] Final test run on all examples
- [ ] Documentation proofreading
- [ ] Dependency audit
- [ ] Version 1.0.0 release candidate

**Deliverable**: Production-ready library v1.0.0-rc1

### Success Criteria
- [ ] CLI tools working and documented
- [ ] Health check system operational
- [ ] Permission explainer debugger functional
- [ ] SECURITY.md, TESTING_GUIDE.md, DEPLOYMENT_GUIDE.md, ERROR_HANDLING.md complete
- [ ] Documentation is clear and comprehensive
- [ ] Package can be installed and used
- [ ] All examples work (simple_app, enterprise_app, migration_example)
- [ ] Test coverage >90%
- [ ] Performance benchmarks meet targets
- [ ] Security audit passed
- [ ] Version 1.0.0 ready for release

### Blockers & Risks
- **Risk**: CLI tool development takes longer than expected
  - *Mitigation*: Start with essential commands only, expand later
- **Risk**: Documentation takes longer than expected
  - *Mitigation*: Started documenting during implementation
- **Risk**: Security issues discovered
  - *Mitigation*: Week 7 buffer for fixes

---

## Milestones & Checkpoints

### Milestone 1: SimpleRBAC Working (End of Week 2)
**Demo**: Show SimpleRBAC in a basic FastAPI app
- Register user
- Login
- Assign role
- Check permission
- Access protected route

**Deliverables**:
- ✅ SimpleRBAC preset complete
- ✅ Example app running
- ✅ >90% test coverage
- ✅ Basic documentation

### Milestone 2: EnterpriseRBAC - Entity System (End of Week 3)
**Demo**: Show entity hierarchy and tree permissions
- Create organization → department → team
- Assign user to entity with multiple roles
- Show tree permission access
- Demonstrate permission inheritance

**Deliverables**:
- ✅ Entity models and services
- ✅ Tree permissions working
- ✅ Entity example scenarios
- ✅ >85% test coverage for entity system

### Milestone 3: EnterpriseRBAC - Optional Features (End of Week 4)
**Demo**: Show context-aware roles, ABAC, and caching
- Context-aware role (different permissions at different entity types)
- ABAC condition (approve invoice under amount limit)
- Cached vs uncached performance comparison
- Feature flag configuration examples

**Deliverables**:
- ✅ Context-aware roles implemented
- ✅ ABAC engine working
- ✅ Redis caching integrated
- ✅ Feature flags functional

### Milestone 4: EnterpriseRBAC Complete (End of Week 5)
**Demo**: Full EnterpriseRBAC with all configurations
- Basic configuration (entity hierarchy only)
- Full configuration (all optional features)
- Performance benchmarks
- Enterprise example app

**Deliverables**:
- ✅ EnterpriseRBAC preset complete
- ✅ Enterprise example app
- ✅ >90% test coverage
- ✅ Complete documentation

### Milestone 5: Production Ready (End of Week 7)
**Demo**: Complete package ready for use
- Install from package
- Use CLI tools
- Run health checks
- Deploy example apps
- Follow quick start guides

**Deliverables**:
- ✅ CLI tools functional
- ✅ Health check system
- ✅ Permission explainer debugger
- ✅ SECURITY.md, TESTING_GUIDE.md, DEPLOYMENT_GUIDE.md, ERROR_HANDLING.md
- ✅ All examples working
- ✅ Version 1.0.0 released

---

## Weekly Status Updates

Each Friday, document:
1. **Completed**: What was finished this week
2. **In Progress**: What's ongoing
3. **Blocked**: Any blockers encountered
4. **Next Week**: Focus for next week
5. **Risks**: New risks identified
6. **Decisions**: Key decisions made

Template:
```markdown
## Week N Status (YYYY-MM-DD)

### Completed ✅
- Task 1
- Task 2

### In Progress 🔄
- Task 3 (60% complete)

### Blocked 🚫
- None

### Next Week Focus
- Task 4
- Task 5

### Risks Identified
- Risk description

### Decisions Made
- Decision 1: Why we chose X over Y
```

---

## Dependencies & Prerequisites

### Required Tools
- Python 3.10+
- MongoDB 4.4+ (for testing)
- Redis 6.0+ (for caching, optional)
- FastAPI 0.100+
- Beanie ODM
- PyTest for testing

### Development Environment
- `uv` or `pip` for dependency management
- `black` for code formatting
- `isort` for import sorting
- `flake8` for linting
- `mypy` for type checking

---

## Resource Allocation

### Developer Time
- **Primary Developer**: Full-time for 6-7 weeks
- **Code Reviews**: 2-3 hours per week
- **Testing Support**: As needed

### Infrastructure
- Dev MongoDB instance
- Dev Redis instance
- CI/CD pipeline (GitHub Actions)
- Documentation hosting (GitHub Pages or similar)

---

## Success Metrics

### Technical Metrics
- [ ] Test coverage >90% overall
- [ ] All presets have example apps
- [ ] Performance: Permission checks <10ms (cached), <50ms (uncached)
- [ ] No critical bugs in issue tracker

### Adoption Metrics
- [ ] At least 2 internal projects using the library
- [ ] Positive feedback from internal teams
- [ ] Migration guides successfully used

### Quality Metrics
- [ ] Documentation rated 4+/5 by users
- [ ] <5 support questions per week after launch
- [ ] Zero security vulnerabilities

---

## Contingency Plans

### If Running Behind Schedule
1. **Defer multi-tenant**: Not essential for MVP
2. **Simplify examples**: Focus on demonstrating features, not polished UI
3. **Reduce ABAC operators**: Start with basic operators, add more later
4. **Delay PostgreSQL support**: MongoDB only for initial release

### If Technical Blockers Arise
1. **Beanie limitations**: Consider switching to SQLAlchemy + Alembic
2. **Performance issues**: Add more aggressive caching
3. **Test failures**: Reduce coverage requirement temporarily

### If Scope Creeps
1. **Document but defer**: Add to backlog for v2.0
2. **Remove from MVP**: Focus on core functionality
3. **Simplify implementation**: Choose simpler approach

---

## Post-Launch Roadmap (v1.1+)

### Version 1.1 (4 weeks after v1.0)
- PostgreSQL support
- Multi-tenant mode refinements
- Additional ABAC operators
- Performance optimizations

### Version 1.2 (8 weeks after v1.0)
- Admin UI component library
- Enhanced CLI tools
- Enhanced audit logging
- OpenTelemetry integration

### Version 2.0 (6 months after v1.0)
- Plugin system for extensions
- Additional database backends
- Advanced analytics
- Open source release

---

## Questions & Open Issues

Track open questions that need resolution:

1. **Multi-tenant**: Include in v1.0 or defer to v1.1?
   - *Status*: Open
   - *Decision by*: End of Week 2

2. **Database abstraction**: Support PostgreSQL in v1.0?
   - *Status*: Open
   - *Decision by*: End of Week 1

3. **Admin UI**: Separate package or examples only?
   - *Status*: Open
   - *Decision by*: Week 6

---

## Change Log

Track changes to the roadmap:

| Date | Change | Reason |
|------|--------|--------|
| 2025-01-14 | Revised to two-preset architecture | Consolidated HierarchicalRBAC and FullFeatured into EnterpriseRBAC with feature flags; added CLI tools, health checks, and comprehensive production guides |
| 2025-01-14 | Initial roadmap created | Project kickoff |

---

**Last Updated**: 2025-01-14 (Revised to two presets, 6-7 weeks)
**Next Review**: End of Week 2 (after Milestone 1)
