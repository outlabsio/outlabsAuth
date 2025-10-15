# Library Redesign Documentation

**Version**: 1.4 (Unified Architecture + Closure Table + Redis Patterns + JWT Service Tokens)
**Date**: 2025-01-14

This directory contains all planning and design documentation for converting OutlabsAuth from a centralized API service to a FastAPI library.

**Key v1.4 Improvements**:
- **Unified Architecture** (DD-032): Single core with 5-10 LOC wrappers, zero code duplication
- **Closure Table** (DD-036): O(1) tree permission queries, 20x performance improvement
- **Redis Counters** (DD-033): 99%+ reduction in database writes for API keys
- **JWT Service Tokens** (DD-034): ~0.5ms authentication, zero DB hits for microservices
- **Redis Pub/Sub** (DD-037): <100ms cache invalidation across all instances
- **Single AuthDeps** (DD-035): Unified dependency injection class

---

## 📋 Documentation Index

### Start Here
1. **[REDESIGN_VISION.md](REDESIGN_VISION.md)** - Main hub document
   - Executive summary
   - Why we're doing this (library vs centralized API)
   - Two-preset architecture (SimpleRBAC, EnterpriseRBAC)
   - Core principles and goals
   - Success criteria

### Technical Design
2. **[LIBRARY_ARCHITECTURE.md](LIBRARY_ARCHITECTURE.md)** - Technical architecture
   - Package structure
   - Two preset designs (Simple, Enterprise)
   - Data models
   - Service layer architecture
   - Performance considerations

3. **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)** - 15-16 week implementation plan
   - 10 phases total (6 core + 4 optional extensions)
   - Week-by-week tasks
   - Milestones and checkpoints
   - Success metrics
   - Core: 6-7 weeks, Extensions: 9 weeks (optional)

### Developer Resources
4. **[API_DESIGN.md](API_DESIGN.md)** - Developer experience and examples
   - Installation and quick start
   - Code examples for SimpleRBAC and EnterpriseRBAC
   - Optional features via feature flags
   - FastAPI integration patterns
   - Configuration options

5. **[COMPARISON_MATRIX.md](COMPARISON_MATRIX.md)** - Feature comparison
   - Binary decision tree (SimpleRBAC vs EnterpriseRBAC)
   - Feature comparison table with optional features
   - API key authentication features
   - Use case examples
   - Performance benchmarks
   - Migration paths

6. **[DEPENDENCY_PATTERNS.md](DEPENDENCY_PATTERNS.md)** - FastAPI dependency injection patterns (NEW)
   - AuthContext: Universal authentication abstraction
   - Multi-source authentication (JWT, API keys, service tokens, superuser)
   - SimpleDeps, MultiSourceDeps, GroupDeps, EntityDeps patterns
   - API Key Service architecture (argon2id hashing, rate limiting, IP whitelisting)
   - Permission checking across all auth sources
   - Complete FastAPI integration examples
   - Service-to-service authentication patterns

### Production Guides
7. **[SECURITY.md](SECURITY.md)** - Security hardening and best practices
   - Threat model and attack vectors
   - JWT security and token management
   - API key security (argon2id hashing, rotation, IP whitelisting)
   - Password security and policies
   - Network and database security
   - Secrets management
   - Rate limiting and abuse prevention
   - Audit logging
   - Security checklist

8. **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Testing utilities and patterns
   - Testing philosophy and structure
   - Built-in test utilities and fixtures
   - Unit and integration testing patterns
   - Permission and entity hierarchy testing
   - API key and multi-source authentication testing
   - Mocking strategies
   - Performance testing
   - CI/CD integration

9. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Scaling and production deployment
   - Docker and Kubernetes deployments
   - Scaling strategies (vertical, horizontal, auto-scaling)
   - Performance tuning
   - High availability (MongoDB replica sets, Redis sentinel)
   - Monitoring and observability (Prometheus, Grafana)
   - Backup and recovery
   - Production checklist

10. **[ERROR_HANDLING.md](ERROR_HANDLING.md)** - Exception hierarchy and patterns
    - Complete exception hierarchy
    - Error codes and standard formats
    - Error handling patterns
    - API error responses
    - Logging and monitoring errors
    - User-friendly error messages
    - Debugging tools

### Migration & Decisions
11. **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Reference for external users
    - **Note**: For external users migrating from centralized API
    - **Skip if starting fresh** - use API_DESIGN.md instead
    - Database migration scripts
    - Code migration examples
    - Testing strategy
    - Rollback plan

12. **[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** - Architectural decisions log
    - **37 major decisions documented (DD-001 to DD-037)** - Updated v1.4
    - Rationale and trade-offs
    - Alternatives considered
    - Latest decisions: Unified architecture (DD-032), Redis counters (DD-033), JWT service tokens (DD-034), single AuthDeps (DD-035), closure table (DD-036), Redis Pub/Sub (DD-037)

### Authentication Extensions (Optional, Post-v1.0)
13. **[AUTH_EXTENSIONS.md](AUTH_EXTENSIONS.md)** - Authentication extensions (v1.1-v1.4)
    - OAuth/social login (Google, Facebook, Apple, GitHub)
    - Passwordless authentication (magic links, OTP)
    - Pluggable notification system
    - Advanced features (TOTP/MFA, WebAuthn research)
    - Extension architecture and integration patterns
    - Timeline: 9 weeks after v1.0 (optional)

---

## 🗂️ Quick Reference

### Choosing a Preset (SIMPLIFIED)
```
Do you need organizational hierarchy (departments/teams)?
├─ NO  → SimpleRBAC (flat structure)
└─ YES → EnterpriseRBAC (entity hierarchy always included)
          ├─ Basic: Just hierarchy + tree permissions
          └─ Advanced: + optional features (context-aware roles, ABAC, caching, etc.)
```

**Key Question**: Do you have departments, teams, or any organizational structure?
- **NO** → Use SimpleRBAC
- **YES** → Use EnterpriseRBAC (enable optional features as needed)

### Timeline (UPDATED)

#### Core Library (v1.0)
- **Phase 1** (Week 1): Core foundation + SimpleRBAC
- **Phase 2** (Week 2): Complete SimpleRBAC + Tests
- **Phase 3** (Week 3): EnterpriseRBAC - Entity system
- **Phase 4** (Week 4): EnterpriseRBAC - Optional features
- **Phase 5** (Week 5): EnterpriseRBAC complete + Testing
- **Phase 6** (Week 6-7): CLI tools, health checks, documentation, examples

**Core Duration**: 6-7 weeks (production-ready library)

#### Optional Extensions (Post-v1.0)
- **Phase 7** (Week 8-9): Notification system (v1.1) - Prerequisite for auth extensions
- **Phase 8** (Week 10-12): OAuth/social login (v1.2) - Google, Facebook, Apple, GitHub
- **Phase 9** (Week 13-14): Passwordless auth (v1.3) - Magic links, OTP (email/SMS)
- **Phase 10** (Week 15-16): Advanced features (v1.4) - TOTP/MFA, WebAuthn research

**Extension Duration**: 9 weeks (optional, can be adopted as needed)

**Total Duration**: 15-16 weeks (6-7 weeks core + 9 weeks extensions)

### Key Changes
- ❌ Remove: `platform_id`, multi-platform complexity, middle preset
- ✅ Keep: Entity hierarchy, tree permissions, context-aware roles (opt-in)
- 🔄 Simplify: Two presets (Simple, Enterprise) with feature flags
- ➕ Add: Optional `tenant_id`, CLI tools, health checks, production guides
- 🎯 New: Permission explainer debugger for troubleshooting

### Optional Features (EnterpriseRBAC)
```python
auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True,  # Opt-in
    enable_abac=True,                 # Opt-in
    enable_caching=True,              # Opt-in (requires Redis)
    multi_tenant=True,                # Opt-in
    enable_audit_log=True             # Opt-in
)
```

---

## 📊 Documentation Stats

- **Total Lines**: ~18,500+ lines of comprehensive documentation (updated v1.4)
- **Documents**: 13 comprehensive markdown files
  - 6 core design documents (including DEPENDENCY_PATTERNS.md)
  - 4 production guides
  - 1 authentication extensions guide
  - 2 reference documents
- **Timeline**: 15-16 weeks total (6-7 weeks core + 9 weeks optional extensions)
- **Presets**: 2 (SimpleRBAC, EnterpriseRBAC) with unified core architecture
- **Design Decisions**: **37 documented (DD-001 to DD-037)** - Updated v1.4
- **Example Apps**: 3 planned (simple_app, enterprise_basic, enterprise_full)
- **Auth Extensions**: 4 versions (v1.1 Notifications, v1.2 OAuth, v1.3 Passwordless, v1.4 Advanced)
- **Core Features**: JWT auth, API keys (argon2id), JWT service tokens, closure table, Redis patterns

---

## 🚀 How to Use This Documentation

### For Project Planning
1. Start with **REDESIGN_VISION.md** (vision and goals)
2. Review **IMPLEMENTATION_ROADMAP.md** (timeline and phases)
3. Check **DESIGN_DECISIONS.md** (understand trade-offs)

### For Development
1. Reference **LIBRARY_ARCHITECTURE.md** (technical design)
2. Use **API_DESIGN.md** (code examples and patterns)
3. Follow **TESTING_GUIDE.md** (testing strategies)

### For Production Deployment
1. Review **SECURITY.md** (security hardening)
2. Follow **DEPLOYMENT_GUIDE.md** (Docker, Kubernetes, scaling)
3. Implement **ERROR_HANDLING.md** (exception handling)
4. Set up monitoring from **DEPLOYMENT_GUIDE.md**

### For Users/Adopters
1. Share **COMPARISON_MATRIX.md** (choose the right preset)
2. Follow **API_DESIGN.md** (getting started)
3. Skip **MIGRATION_GUIDE.md** (only for existing centralized API users)

### For Troubleshooting
1. Check **ERROR_HANDLING.md** (exception types and debugging)
2. Use permission explainer: `outlabs-auth permissions explain`
3. Review **DEPLOYMENT_GUIDE.md** troubleshooting section

### For Authentication Extensions (Optional)
1. Review **AUTH_EXTENSIONS.md** (complete extension guide)
2. Start with v1.1 Notification system (prerequisite for others)
3. Choose extensions based on needs (OAuth, passwordless, MFA)
4. Check **DESIGN_DECISIONS.md** for DD-022 to DD-027 (extension rationale)
5. Extensions work with both SimpleRBAC and EnterpriseRBAC

---

## 📅 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-14 | Initial comprehensive documentation (3 presets) |
| 1.1 | 2025-01-14 | Revised to 2 presets + 4 production guides |
| 1.2 | 2025-01-14 | Added authentication extensions (v1.1-v1.4) |
| 1.3 | 2025-01-14 | Added API key system and multi-source authentication (core v1.0) |
| **1.4** | **2025-01-14** | **Architectural improvements: unified architecture (DD-032), closure table (DD-036), Redis counters (DD-033), JWT service tokens (DD-034), Redis Pub/Sub (DD-037), single AuthDeps (DD-035); 6 new design decisions; updated all 13 documentation files** |

**Key Changes in v1.4**:
- **Unified Architecture (DD-032)**: Single `OutlabsAuth` core with thin wrappers (5-10 LOC each)
  - SimpleRBAC and EnterpriseRBAC are now just convenience wrappers
  - Zero code duplication, easy migration between presets
  - All features controlled by configuration flags
- **Closure Table for Tree Permissions (DD-036)**:
  - O(1) tree permission queries instead of recursive lookups
  - 20x performance improvement (1 query @ 5ms vs 10 queries @ 100ms)
  - `EntityClosureModel` tracks all ancestor-descendant pairs with depths
- **Redis Counters for API Keys (DD-033)**:
  - 99%+ reduction in database writes
  - Redis INCR for every API key usage
  - Background sync to database every 5 minutes
- **JWT Service Tokens (DD-034)**:
  - Stateless authentication for internal microservices
  - ~0.5ms validation time (zero DB hits)
  - Long-lived tokens (365 days) with embedded permissions
- **Redis Pub/Sub Cache Invalidation (DD-037)**:
  - <100ms cache invalidation across all distributed instances
  - Immediate propagation vs periodic polling
  - Event-driven invalidation (role changes, permission updates)
- **Single AuthDeps Class (DD-035)**:
  - Replaced 5 separate dependency classes with one unified `AuthDeps`
  - Clear method names: `require_auth()`, `require_permission()`, `optional_auth()`
  - Easier to discover and learn
- **API Key Improvements (DD-028 updates)**:
  - 12-character prefixes (increased from 8)
  - Temporary locks instead of permanent revocation (30-min cooldown)
  - Optional expiration dates (removed "required" constraint)
- **Updated All 13 Documentation Files**:
  - DESIGN_DECISIONS.md: Added DD-032 to DD-037, updated DD-028
  - LIBRARY_ARCHITECTURE.md: Unified architecture, EntityClosureModel, Redis patterns
  - DEPENDENCY_PATTERNS.md: Complete rewrite with single AuthDeps class
  - API_DESIGN.md: JWT Service Tokens section with examples
  - SECURITY.md: Redis counters, temporary locks, cache invalidation security
  - IMPLEMENTATION_ROADMAP.md: Simplified phases, closure table integration
  - REDESIGN_VISION.md: Unified architecture, clarified v1.0 vs post-v1.0 features
  - COMPARISON_MATRIX.md: Architecture notes, updated features, performance metrics
  - TESTING_GUIDE.md: Updated tests for AuthDeps, temporary locks, Redis counters
  - README.md: This file (v1.4 stats and descriptions)
  - Remaining: DEPLOYMENT_GUIDE.md (Redis Pub/Sub), AUTH_EXTENSIONS.md
- **Total Documentation**: ~18,500+ lines across 13 files
- **Design Decisions**: 37 (DD-001 to DD-037)

**Key Changes in v1.3**:
- Added DEPENDENCY_PATTERNS.md (comprehensive FastAPI dependency injection guide)
- Added API key authentication system as core v1.0 feature
- Added multi-source authentication (JWT, API keys, service tokens, superuser)
- Added AuthContext universal authentication abstraction
- Added 4 new design decisions (DD-028 to DD-031) for API key system
- Updated LIBRARY_ARCHITECTURE.md with Authentication System section
- Updated IMPLEMENTATION_ROADMAP.md with API key integration (Phases 2, 3, 6)
- Updated SECURITY.md with comprehensive API key security (argon2id hashing)
- Updated TESTING_GUIDE.md with API key and multi-source authentication testing
- Updated API_DESIGN.md with API key usage examples and patterns
- Updated COMPARISON_MATRIX.md with API key feature comparison
- Total documentation: ~16,000+ lines across 13 files
- Design decisions: 31 (DD-001 to DD-031)

**Key Changes in v1.2**:
- Added AUTH_EXTENSIONS.md (comprehensive authentication extensions guide)
- Added 6 new design decisions (DD-022 to DD-027)
- Extended implementation roadmap with Phases 7-10 (9 weeks of optional extensions)
- Added OAuth/social login support (Google, Facebook, Apple, GitHub)
- Added passwordless authentication (magic links, OTP)
- Added pluggable notification system
- Added advanced features (TOTP/MFA, WebAuthn research)
- Timeline extended: 15-16 weeks total (6-7 weeks core + 9 weeks optional)
- Updated all related documentation for extension integration

**Key Changes in v1.1**:
- Consolidated to 2 presets (SimpleRBAC, EnterpriseRBAC)
- Added 4 production guides (Security, Testing, Deployment, Error Handling)
- Added CLI tools, health checks, permission explainer
- Timeline reduced from 7-8 weeks to 6-7 weeks
- Updated all documentation for consistency

---

**Branch**: `library-redesign`
**Status**: Planning Phase
**Version**: 1.4 (Unified Architecture + Closure Table + Redis Patterns + JWT Service Tokens)
**Next Milestone**: Phase 1 - Core Foundation with unified architecture (Week 1)
**Core v1.0 Features**: JWT auth, API keys (argon2id, 12-char prefixes, temporary locks), JWT service tokens (~0.5ms), closure table (O(1) queries), Redis counters (99%+ write reduction), Redis Pub/Sub cache invalidation (<100ms), single AuthDeps class
**Optional Extensions**: v1.1 Notifications (Week 8) → v1.2 OAuth (Week 10) → v1.3 Passwordless (Week 13) → v1.4 Advanced MFA (Week 15)
**Architecture**: Single `OutlabsAuth` core + thin SimpleRBAC/EnterpriseRBAC wrappers (5-10 LOC)
