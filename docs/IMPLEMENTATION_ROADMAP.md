# OutlabsAuth Library - Implementation Roadmap

**Version**: 1.4
**Date**: 2025-01-14
**Total Duration**: 15-16 weeks (6-7 weeks core + 9 weeks extensions)
**Status**: Planning Phase

**Key Architectural Improvements (v1.4)**:
- **Unified Architecture**: Single `OutlabsAuth` core with thin wrappers (DD-032)
- **Closure Table**: O(1) tree permission queries (DD-036)
- **Redis Counters**: 99%+ reduction in DB writes for API keys (DD-033)
- **Redis Pub/Sub**: <100ms cache invalidation (DD-037)
- **Temporary Locks**: 30-min cooldown instead of permanent revocation (DD-028)
- **JWT Service Tokens**: Internal microservice authentication (DD-034)
- **Single AuthDeps**: Unified dependency injection class (DD-035)

---

## Overview

This document breaks down the library redesign into 10 phases:
- **Phases 1-6**: Core library (v1.0) - SimpleRBAC and EnterpriseRBAC presets
- **Phases 7-10**: Optional authentication extensions (v1.1-v1.4) - Notifications, OAuth, passwordless, advanced features

Each phase has clear deliverables and success criteria. Phases build on each other, with working software at each stage.

**Architecture**: Single `OutlabsAuth` core with thin wrappers (5-10 LOC each) for SimpleRBAC and EnterpriseRBAC presets. All features controlled by configuration flags.

**Extensions Model**: Post-v1.0 features are optional and work with both presets.

---

## Phase Summary

### Core Library (v1.0)

| Phase | Duration | Focus | Deliverable |
|-------|----------|-------|-------------|
| Phase 1 | Week 1 | Core foundation + SimpleRBAC | Working simple RBAC |
| Phase 2 | Week 2 | Complete SimpleRBAC + Tests | Production-ready simple preset |
| Phase 3 | Week 3 | EnterpriseRBAC - Entity system | Entity hierarchy + tree permissions |
| Phase 4 | Week 4 | EnterpriseRBAC - Optional features | Context-aware roles + ABAC + caching |
| Phase 5 | Week 5 | EnterpriseRBAC complete + Testing | Production-ready enterprise preset |
| Phase 6 | Week 6-7 | Documentation + Examples + Polish | Ready for production use |

### Optional Extensions (v1.1-v1.4)

| Phase | Duration | Focus | Deliverable |
|-------|----------|-------|-------------|
| Phase 7 | Week 8-9 | Notification system (v1.1) | Pluggable notification handlers |
| Phase 8 | Week 10-12 | OAuth/social login (v1.2) | Google, Facebook, Apple providers |
| Phase 9 | Week 13-14 | Passwordless auth (v1.3) | Magic links + OTP (email/SMS) |
| Phase 10 | Week 15-16 | Advanced features (v1.4) | TOTP/MFA, WebAuthn research |

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

#### Day 2-3: API Key System (Core v1.0 Feature - DD-028, DD-033, DD-034, DD-035)
- [ ] Create `APIKeyModel`:
  - key_hash (argon2id hashed, NOT SHA256)
  - **key_prefix (first 12 chars: sk_prod_abc1_, sk_stag_abc1_)** - DD-028
  - permissions (list of allowed permissions)
  - allowed_ips (IP whitelist)
  - rate_limit_per_minute (default 60)
  - environment (production, staging, development, test)
  - **expires_at (optional, not mandatory)** - DD-028
  - is_active
  - **usage_count (synced from Redis every 5 minutes)** - DD-033
  - **last_synced_at (when Redis counters were last synced)** - DD-033
  - **No error_count field** (tracked in Redis with TTL) - DD-028
- [ ] Create `APIKeyService`:
  - **Generate API keys (12-char prefix + 32 bytes random)** - DD-028
  - Hash keys with argon2id (time_cost=2, memory_cost=102400, parallelism=8)
  - Validate API keys
  - **Check temporary locks in Redis** (api_key:lock:{prefix}) - DD-028
  - **Track failures in Redis** (10 failures in 10 min → 30-min lock) - DD-028
  - **Track usage in Redis** (INCR api_key:usage:{prefix}) - DD-033
  - **Background task to sync Redis counters to MongoDB** (every 5 minutes) - DD-033
  - Key rotation with optional expiration (create new, revoke old)
  - **Manual rotation API** (no automatic rotation) - DD-028
- [ ] Create `MultiSourceAuthService`:
  - AuthContext abstraction (universal auth for all sources)
  - Priority chain: Superuser > **JWT Service Token** > API Key > User > Anonymous - DD-034
  - Extract auth from headers: X-Superuser-Token, **X-Service-Token** (JWT), X-API-Key, Authorization
  - **JWT Service Token validation** (stateless, ~0.5ms, zero DB hits) - DD-034
- [ ] Create FastAPI dependencies (**AuthDeps - unified class**) - DD-035:
  - `require_auth()` - Any auth source
  - `require_permission(*permissions)` - Permission checking
  - `require_source(source)` - Specific auth source (e.g., API key only, service token only)
  - `require_entity_permission(permission, entity_id)` - Entity-scoped permissions
- [ ] In-memory rate limiting (no Redis requirement for SimpleRBAC)
- [ ] API key CRUD endpoints (/v1/api-keys)

**Deliverable**: API key system functional with SimpleRBAC

#### Day 4-5: Testing
- [ ] Unit tests for all services (>90% coverage)
- [ ] Integration tests for SimpleRBAC flows
- [ ] API key system tests:
  - Key generation and validation
  - argon2id hashing verification
  - API key authentication flow
  - Multi-source authentication priority chain
  - Rate limiting tests
  - IP whitelist enforcement
  - Auto-revocation after failures
- [ ] Test fixtures and utilities
- [ ] CI/CD setup (GitHub Actions)

**Deliverable**: Comprehensive test suite including API keys

#### Day 5-6: Example Application
- [ ] Create `examples/simple_app/`
- [ ] FastAPI app with:
  - User registration
  - Login/logout
  - Protected routes
  - Role management
  - Permission checks
  - API key creation and management
  - Service-to-service authentication demo
  - Multi-source auth examples (user JWT + API key)
- [ ] README with setup instructions

**Deliverable**: Working example app with API keys

#### Day 7: Documentation
- [ ] API reference for SimpleRBAC
- [ ] Quick start guide
- [ ] Configuration options
- [ ] Code examples

**Deliverable**: Basic documentation

### Success Criteria
- [ ] SimpleRBAC passes all tests
- [ ] API key system functional and tested
- [ ] Multi-source authentication working (JWT + API keys)
- [ ] Example app runs and demonstrates features (including API keys)
- [ ] Documentation clear and complete
- [ ] Can be used in production for simple RBAC needs and service-to-service auth

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

#### Day 5-6: Tree Permissions + Closure Table (DD-036)
- [ ] Create `EntityClosureModel`:
  - ancestor_id (ancestor entity ID)
  - descendant_id (descendant entity ID)
  - depth (distance: 0 = self, 1 = direct child, etc.)
  - Indexes: [(ancestor_id, descendant_id)], [(descendant_id, depth)], [(ancestor_id, depth)]
- [ ] Implement closure table maintenance:
  - On entity creation: Create closure records for all ancestors
  - On entity move: Recalculate affected closure records
  - On entity deletion: Remove closure records
- [ ] Enhance `PermissionService` for hierarchy:
  - Check permission in entity context
  - **Check tree permissions using closure table** (O(1) query, not recursive) - DD-036
  - Resolve user permissions across all memberships
- [ ] Implement permission resolution algorithm:
  1. Check direct permission in target entity
  2. **Check _tree permission in ancestors (single query via closure table)** - DD-036
  3. Check _all permission anywhere
- [ ] Add permission caching (in-memory for now)
- [ ] **Add cache invalidation via Redis Pub/Sub** (DD-037)

**Deliverable**: Tree permissions working with O(1) queries

#### Day 7: Entity-Scoped API Keys
- [ ] Extend `APIKeyModel`:
  - Add optional `entity_id` field (scope API key to specific entity)
  - Add `inherit_from_tree` flag (use tree permissions)
- [ ] Update `APIKeyService`:
  - Validate API key has permission in entity context
  - Support tree permissions for API keys (key in parent entity can access descendants)
- [ ] Update `MultiSourceAuthService`:
  - Include entity context in AuthContext when using API keys
  - Support entity-scoped permission checking for API keys
- [ ] Create FastAPI dependencies (EntityDeps):
  - `entity_context(entity_id)` - Set entity context
  - `requires_in_entity(*permissions)` - Check permission in entity
  - `api_key_in_entity()` - API key with entity scope

**Deliverable**: Entity-scoped API keys working with tree permissions

### Success Criteria
- [ ] Can create entity hierarchies
- [ ] Can assign users to entities with roles
- [ ] Tree permissions work correctly (user with entity:update_tree in parent can update children)
- [ ] Entity-scoped API keys functional
- [ ] API keys can use tree permissions to access descendant entities
- [ ] Unit tests for entity operations (>85% coverage)
- [ ] Integration tests for tree permissions
- [ ] Integration tests for entity-scoped API keys

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
  - **API key management commands**:
    - `outlabs-auth keys create` - Create new API key
    - `outlabs-auth keys list` - List all API keys
    - `outlabs-auth keys rotate` - Rotate API key (create new, revoke old)
    - `outlabs-auth keys revoke` - Revoke API key
    - `outlabs-auth keys info` - Show API key details
    - `outlabs-auth keys test` - Test API key authentication
  - Database initialization
  - Permission listing/debugging
  - Health check command
- [ ] Implement health check system:
  - Database connectivity
  - Redis connectivity (if enabled)
  - Permission service health
  - Entity service health (EnterpriseRBAC)
  - **API key service health** (key validation, rate limiting)
- [ ] Create "explain permission" debugger:
  - Shows why user has/doesn't have permission
  - Traces permission resolution path
  - Shows all applicable roles and memberships
  - Tree permission visualization
  - **Multi-source auth debugging** (show which auth source was used)

**Deliverable**: CLI tools and health checks including API key management

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
- [ ] CLI tools working and documented (including API key management)
- [ ] Health check system operational (including API key service)
- [ ] Permission explainer debugger functional (including multi-source auth debugging)
- [ ] SECURITY.md, TESTING_GUIDE.md, DEPLOYMENT_GUIDE.md, ERROR_HANDLING.md complete
- [ ] Documentation is clear and comprehensive
- [ ] Package can be installed and used
- [ ] All examples work (simple_app, enterprise_app, migration_example)
- [ ] Test coverage >90%
- [ ] Performance benchmarks meet targets
- [ ] Security audit passed (including API key security)
- [ ] Version 1.0.0 ready for release

### Blockers & Risks
- **Risk**: CLI tool development takes longer than expected
  - *Mitigation*: Start with essential commands only, expand later
- **Risk**: Documentation takes longer than expected
  - *Mitigation*: Started documenting during implementation
- **Risk**: Security issues discovered
  - *Mitigation*: Week 7 buffer for fixes

---

## Phase 7: Notification System (v1.1, Weeks 8-9)

### Goals
- Implement pluggable notification handler abstraction
- Pre-built handlers for common patterns
- Notification event system
- Testing utilities for notifications
- **Prerequisite for**: OAuth (v1.2) and passwordless authentication (v1.3)

### Tasks

#### Week 8, Day 1-3: NotificationHandler Abstraction
- [ ] Design `NotificationHandler` abstract base class:
  ```python
  class NotificationHandler(ABC):
      @abstractmethod
      async def send(self, event: NotificationEvent) -> bool:
          pass
  ```
- [ ] Create `NotificationEvent` model:
  - type (welcome, magic_link, otp, password_reset, etc.)
  - recipient (email or phone)
  - data (payload specific to event type)
  - metadata (priority, expiration, etc.)
- [ ] Integrate notification handler into `OutlabsAuth` base class
- [ ] Add `NoOpHandler` (default, logs events but doesn't send)

**Deliverable**: Core notification abstraction working

#### Week 8, Day 4-7: Pre-built Handlers
- [ ] `WebhookHandler`:
  - Send notification events to webhook endpoint
  - Configurable HTTP headers and authentication
  - Retry logic with exponential backoff
- [ ] `QueueHandler`:
  - Push to message queue (Redis, RabbitMQ, SQS)
  - Support for different queue backends
  - Message serialization
- [ ] `CallbackHandler`:
  - Direct function callback
  - Async and sync callback support
- [ ] `CompositeHandler`:
  - Combine multiple handlers
  - Parallel or sequential execution

**Deliverable**: Pre-built handlers implemented

#### Week 9, Day 1-3: Testing & Documentation
- [ ] Unit tests for all handlers (>90% coverage)
- [ ] Integration tests with mock services
- [ ] Test utilities for verifying notifications sent
- [ ] Handler configuration examples
- [ ] Documentation:
  - NotificationHandler guide
  - Building custom handlers
  - Handler selection guide
  - Testing notifications

**Deliverable**: Complete notification system documentation

#### Week 9, Day 4-5: Example Implementation
- [ ] Update `examples/simple_app/` and `examples/enterprise_app/`:
  - Add notification handler configuration
  - Demonstrate webhook handler
  - Demonstrate callback handler
- [ ] Create example email service integration
- [ ] Example SMS gateway integration

**Deliverable**: Working examples with notifications

### Success Criteria
- [ ] NotificationHandler abstraction complete
- [ ] All pre-built handlers working and tested
- [ ] Test utilities available for notification testing
- [ ] Documentation clear with examples
- [ ] Example apps demonstrate notification integration
- [ ] Ready for OAuth and passwordless authentication

### Blockers & Risks
- **Risk**: Too many handler types, complexity explosion
  - *Mitigation*: Start with webhook and callback, add others as needed
- **Risk**: Queue handler requires external services
  - *Mitigation*: Make queue backends optional, document setup
- **Risk**: Testing notifications is complex
  - *Mitigation*: Provide test utilities that capture sent notifications

---

## Phase 8: OAuth/Social Login (v1.2, Weeks 10-12)

### Goals
- Provider abstraction for OAuth 2.0
- Google, Facebook, Apple provider implementations
- Account linking and unlinking
- OAuth security (PKCE, state validation)
- **Requires**: Notification system (v1.1)

### Tasks

#### Week 10, Day 1-3: OAuth Provider Abstraction
- [ ] Design `OAuthProvider` abstract base class:
  ```python
  class OAuthProvider(ABC):
      @abstractmethod
      def get_authorization_url(state, redirect_uri, scopes) -> str
      @abstractmethod
      async def exchange_code(code, redirect_uri) -> OAuthToken
      @abstractmethod
      async def get_user_info(token) -> OAuthUserInfo
  ```
- [ ] Create `SocialAccount` model:
  - provider (google, facebook, apple, etc.)
  - provider_user_id
  - email (from provider)
  - email_verified
  - profile_data
  - created_at, updated_at
- [ ] Create `AuthenticationChallenge` model (for state validation):
  - code, challenge_type, user_id, expires_at
- [ ] Update `UserModel`:
  - Make `hashed_password` optional
  - Add `auth_methods` list (PASSWORD, GOOGLE, FACEBOOK, etc.)
  - Add `social_accounts` relationship

**Deliverable**: OAuth foundation in place

#### Week 10, Day 4-7: OAuth Service
- [ ] Create `OAuthService`:
  - `get_authorization_url()` - Generate OAuth URL with state
  - `authenticate_with_provider()` - Exchange code, get/create user
  - `link_provider_to_user()` - Link social account to existing user
  - `unlink_provider()` - Remove social account (validate at least one auth method remains)
- [ ] Implement account linking strategy:
  - Auto-link by verified email only
  - Create separate account if email unverified
  - Manual linking from user settings
- [ ] State validation with PKCE
- [ ] Welcome email via notification handler for new users

**Deliverable**: OAuth service complete

#### Week 11, Day 1-4: Provider Implementations
- [ ] `GoogleProvider`:
  - Google OAuth 2.0 configuration
  - Scopes: profile, email
  - User info endpoint
  - Token validation
- [ ] `FacebookProvider`:
  - Facebook Login configuration
  - Scopes: public_profile, email
  - Graph API integration
  - Token validation
- [ ] `AppleProvider`:
  - Sign in with Apple configuration
  - JWT token validation (Apple uses JWT)
  - User info extraction
  - Handle Apple's email relay

**Deliverable**: Google, Facebook, Apple providers working

#### Week 11, Day 5-7: Testing
- [ ] Unit tests for OAuthService (>90% coverage)
- [ ] Unit tests for each provider (mocked)
- [ ] Integration tests:
  - Authorization URL generation
  - Code exchange
  - Account linking scenarios
  - Unlinking validation
- [ ] Security tests:
  - State validation
  - PKCE flow
  - Token validation
  - Account takeover prevention

**Deliverable**: Comprehensive OAuth testing

#### Week 12, Day 1-3: Documentation & Examples
- [ ] Create `AUTH_EXTENSIONS.md` or update existing docs:
  - OAuth configuration guide
  - Provider setup (credentials, redirect URIs)
  - Account linking rules
  - Security best practices
- [ ] Update `SECURITY.md`:
  - OAuth security considerations
  - State and PKCE
  - Preventing account takeover
- [ ] Update example apps:
  - Add OAuth configuration
  - "Login with Google" buttons
  - Social account management UI

**Deliverable**: OAuth documentation and examples

#### Week 12, Day 4-5: Additional Providers (Optional)
- [ ] `GitHubProvider` (if time permits)
- [ ] `MicrosoftProvider` (if time permits)
- [ ] Document how to add custom providers

**Deliverable**: Additional providers and extension guide

### Success Criteria
- [ ] OAuth abstraction works with multiple providers
- [ ] Google, Facebook, Apple providers functional
- [ ] Account linking follows security best practices
- [ ] State validation and PKCE working
- [ ] Test coverage >90%
- [ ] Documentation complete with examples
- [ ] Example apps demonstrate social login

### Blockers & Risks
- **Risk**: OAuth provider APIs change
  - *Mitigation*: Abstract provider interface, make providers pluggable
- **Risk**: Account linking edge cases
  - *Mitigation*: Comprehensive testing, clear documentation of rules
- **Risk**: Apple Sign-In complexity (JWT validation)
  - *Mitigation*: Use PyJWT library, start with Google/Facebook first

---

## Phase 9: Passwordless Authentication (v1.3, Weeks 13-14)

### Goals
- Magic link authentication (email)
- OTP authentication (email and SMS)
- Challenge management system
- Rate limiting and abuse prevention
- **Requires**: Notification system (v1.1)

### Tasks

#### Week 13, Day 1-3: Challenge Management
- [ ] Enhance `AuthenticationChallenge` model:
  - challenge_type (magic_link, otp)
  - recipient (email or phone)
  - code (magic link token or OTP)
  - attempts (for rate limiting)
  - expires_at (15 minutes for magic link, 5 minutes for OTP)
- [ ] Create `ChallengeService`:
  - Generate secure codes (magic link: 32 bytes, OTP: 6 digits)
  - Store challenge with expiration
  - Verify challenge (check code, expiration, attempts)
  - Rate limiting (max 3 attempts per challenge, max 5 challenges per hour)
  - Cleanup expired challenges

**Deliverable**: Challenge management working

#### Week 13, Day 4-7: Passwordless Service
- [ ] Create `PasswordlessService`:
  - `send_magic_link(email)`:
    - Generate magic link token
    - Store challenge
    - Send via notification handler
  - `verify_magic_link(code)`:
    - Validate challenge
    - Return JWT tokens
    - Create user if doesn't exist (optional)
  - `send_otp(recipient, channel)`:
    - Generate 6-digit OTP
    - Store challenge
    - Send via notification handler (email or SMS)
  - `verify_otp(recipient, code)`:
    - Validate challenge and code
    - Return JWT tokens
    - Create user if doesn't exist (optional)
- [ ] Integrate with notification system:
  - magic_link event
  - otp event (email, SMS, future: WhatsApp, Telegram)
- [ ] Update `UserModel`:
  - Add MAGIC_LINK and OTP to auth_methods enum
  - Optional phone_number field (for SMS OTP)

**Deliverable**: Passwordless authentication working

#### Week 14, Day 1-3: Rate Limiting & Security
- [ ] Implement rate limiting:
  - Per-recipient limits (5 challenges per hour)
  - Per-IP limits (10 challenges per hour)
  - Challenge attempt limits (3 attempts before invalidation)
  - Exponential backoff for repeated failures
- [ ] Security measures:
  - Secure random code generation
  - Challenge expiration (magic link: 15 min, OTP: 5 min)
  - One-time use (challenge invalidated after verification)
  - Prevent enumeration attacks (same response for valid/invalid recipient)
- [ ] Audit logging:
  - Log all challenge requests
  - Log verification attempts (success and failure)

**Deliverable**: Security hardening complete

#### Week 14, Day 4-5: Testing
- [ ] Unit tests for ChallengeService (>90% coverage)
- [ ] Unit tests for PasswordlessService (>90% coverage)
- [ ] Integration tests:
  - Magic link flow
  - Email OTP flow
  - SMS OTP flow (mocked)
  - Rate limiting tests
  - Expiration tests
  - Abuse prevention tests
- [ ] Security tests:
  - Enumeration attack prevention
  - Brute force prevention
  - Code guessing prevention

**Deliverable**: Comprehensive passwordless testing

#### Week 14, Day 6-7: Documentation & Examples
- [ ] Update `AUTH_EXTENSIONS.md`:
  - Magic link authentication guide
  - OTP authentication guide
  - Channel configuration (email, SMS)
  - Rate limiting configuration
  - Security considerations
- [ ] Update `SECURITY.md`:
  - Passwordless security best practices
  - Rate limiting and abuse prevention
  - Challenge expiration
- [ ] Update example apps:
  - "Login with magic link" option
  - "Login with OTP" option
  - Phone number input for SMS OTP

**Deliverable**: Passwordless documentation and examples

### Success Criteria
- [ ] Magic link authentication working
- [ ] Email OTP working
- [ ] SMS OTP working (with external service)
- [ ] Challenge management secure and tested
- [ ] Rate limiting prevents abuse
- [ ] Test coverage >90%
- [ ] Documentation complete with examples
- [ ] Example apps demonstrate passwordless login

### Blockers & Risks
- **Risk**: SMS OTP requires external service
  - *Mitigation*: Use notification handler abstraction, document Twilio setup
- **Risk**: Rate limiting too strict or too lenient
  - *Mitigation*: Make limits configurable, document recommended values
- **Risk**: Challenge enumeration attacks
  - *Mitigation*: Same response for valid/invalid recipients, rate limiting

---

## Phase 10: Advanced Features (v1.4, Weeks 15-16)

### Goals
- TOTP/MFA (Time-based One-Time Password)
- Extended OTP channels (WhatsApp, Telegram)
- WebAuthn research and prototype
- Account recovery flows

### Tasks

#### Week 15, Day 1-3: TOTP/MFA
- [ ] Add `MFAMethod` model:
  - user_id
  - method_type (TOTP, SMS, EMAIL)
  - totp_secret (for authenticator apps)
  - is_primary
  - created_at, last_used_at
- [ ] Create `MFAService`:
  - `enable_totp(user_id)` - Generate TOTP secret, return QR code
  - `verify_totp(user_id, code)` - Validate TOTP code
  - `generate_backup_codes(user_id)` - Generate recovery codes
  - `require_mfa(user_id)` - Enforce MFA for user
- [ ] Update authentication flow:
  - After password/social login, check if MFA required
  - Challenge for MFA verification
  - Issue final JWT tokens after MFA verification
- [ ] Recovery codes for lost authenticators

**Deliverable**: TOTP/MFA working

#### Week 15, Day 4-5: Extended OTP Channels
- [ ] WhatsApp OTP:
  - Integrate with WhatsApp Business API (via notification handler)
  - Send OTP via WhatsApp message
- [ ] Telegram OTP:
  - Integrate with Telegram Bot API (via notification handler)
  - Send OTP via Telegram message
- [ ] Update `PasswordlessService`:
  - Support whatsapp and telegram channels
  - Channel selection based on user preference

**Deliverable**: WhatsApp and Telegram OTP working

#### Week 15, Day 6-7: Account Recovery
- [ ] Account recovery flows:
  - Forgot password with email verification
  - Account recovery with backup codes
  - Account recovery with support verification
- [ ] Update `AuthService`:
  - `initiate_password_reset(email)` - Send reset link
  - `reset_password(code, new_password)` - Complete reset
  - `verify_backup_code(user_id, code)` - Bypass MFA with backup code

**Deliverable**: Account recovery flows

#### Week 16, Day 1-3: WebAuthn Research & Prototype
- [ ] Research WebAuthn/FIDO2 standards
- [ ] Evaluate Python libraries (py_webauthn)
- [ ] Create proof-of-concept:
  - Credential registration
  - Authentication with passkey
  - Biometric authentication support
- [ ] Document findings and recommendations
- [ ] Decide if WebAuthn should be in v1.4 or deferred to v2.0

**Deliverable**: WebAuthn prototype and decision

#### Week 16, Day 4-5: Testing & Documentation
- [ ] Unit tests for MFA features (>90% coverage)
- [ ] Integration tests for TOTP flow
- [ ] Integration tests for extended OTP channels
- [ ] Update `AUTH_EXTENSIONS.md`:
  - TOTP/MFA setup guide
  - WhatsApp and Telegram OTP configuration
  - Account recovery guides
  - WebAuthn findings (if implemented)
- [ ] Update example apps:
  - MFA enrollment UI
  - TOTP verification UI
  - Backup code management

**Deliverable**: Advanced features documentation

#### Week 16, Day 6-7: Final Polish & Release
- [ ] Code review and refactoring
- [ ] Performance testing for all auth flows
- [ ] Security audit for all extensions
- [ ] Update all documentation
- [ ] Version tagging (v1.4.0)
- [ ] Release notes for extensions

**Deliverable**: v1.4 release

### Success Criteria
- [ ] TOTP/MFA working and tested
- [ ] WhatsApp and Telegram OTP functional
- [ ] Account recovery flows complete
- [ ] WebAuthn prototype (or deferral decision)
- [ ] Test coverage >90%
- [ ] Documentation updated
- [ ] All extensions working together
- [ ] Ready for production use

### Blockers & Risks
- **Risk**: WebAuthn complexity too high for v1.4
  - *Mitigation*: Defer to v2.0 if needed, focus on TOTP/MFA
- **Risk**: WhatsApp/Telegram require business accounts
  - *Mitigation*: Document setup requirements, make optional
- **Risk**: MFA adds significant UX complexity
  - *Mitigation*: Make MFA optional, provide good defaults

---

## Milestones & Checkpoints

### Milestone 1: SimpleRBAC Working (End of Week 2)
**Demo**: Show SimpleRBAC in a basic FastAPI app
- Register user
- Login
- Assign role
- Check permission
- Access protected route
- **Create API key**
- **Authenticate with API key**
- **Multi-source auth (JWT + API key)**

**Deliverables**:
- ✅ SimpleRBAC preset complete
- ✅ **API key system functional**
- ✅ **Multi-source authentication working**
- ✅ Example app running
- ✅ >90% test coverage
- ✅ Basic documentation

### Milestone 2: EnterpriseRBAC - Entity System (End of Week 3)
**Demo**: Show entity hierarchy and tree permissions
- Create organization → department → team
- Assign user to entity with multiple roles
- Show tree permission access
- Demonstrate permission inheritance
- **Create entity-scoped API key**
- **API key with tree permissions**

**Deliverables**:
- ✅ Entity models and services
- ✅ Tree permissions working
- ✅ **Entity-scoped API keys functional**
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
- **Manage API keys via CLI** (`outlabs-auth keys create/list/rotate/revoke`)
- Run health checks
- Deploy example apps
- Follow quick start guides

**Deliverables**:
- ✅ CLI tools functional (including **API key management**)
- ✅ Health check system
- ✅ Permission explainer debugger (including **multi-source auth debugging**)
- ✅ SECURITY.md, TESTING_GUIDE.md, DEPLOYMENT_GUIDE.md, ERROR_HANDLING.md
- ✅ All examples working
- ✅ Version 1.0.0 released

### Milestone 6: Notification System (End of Week 9)
**Demo**: Pluggable notification handlers
- Configure webhook handler
- Configure callback handler
- Send notification events (welcome, password reset)
- Test notification delivery
- Demonstrate custom handler

**Deliverables**:
- ✅ NotificationHandler abstraction complete
- ✅ WebhookHandler, QueueHandler, CallbackHandler, CompositeHandler
- ✅ Test utilities for notifications
- ✅ Documentation complete
- ✅ Example apps updated with notifications
- ✅ Version 1.1.0 released

### Milestone 7: OAuth/Social Login (End of Week 12)
**Demo**: Social login with multiple providers
- Login with Google
- Login with Facebook
- Login with Apple
- Account linking (by verified email)
- Account management (unlink provider)

**Deliverables**:
- ✅ OAuth provider abstraction complete
- ✅ Google, Facebook, Apple providers working
- ✅ Account linking secure and functional
- ✅ State validation and PKCE
- ✅ Test coverage >90%
- ✅ Documentation and examples complete
- ✅ Version 1.2.0 released

### Milestone 8: Passwordless Authentication (End of Week 14)
**Demo**: Passwordless login flows
- Login with magic link (email)
- Login with email OTP
- Login with SMS OTP
- Rate limiting demonstration
- Security measures active

**Deliverables**:
- ✅ Magic link authentication working
- ✅ Email and SMS OTP working
- ✅ Challenge management secure
- ✅ Rate limiting and abuse prevention
- ✅ Test coverage >90%
- ✅ Documentation and examples complete
- ✅ Version 1.3.0 released

### Milestone 9: Advanced Features Complete (End of Week 16)
**Demo**: Complete authentication system
- TOTP/MFA enrollment and verification
- WhatsApp/Telegram OTP
- Account recovery flows
- WebAuthn prototype (if implemented)
- All auth methods working together

**Deliverables**:
- ✅ TOTP/MFA working
- ✅ Extended OTP channels (WhatsApp, Telegram)
- ✅ Account recovery flows
- ✅ WebAuthn prototype or deferral decision
- ✅ All extensions working together
- ✅ Complete documentation
- ✅ Version 1.4.0 released

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
- **Core Library (v1.0)**: Full-time for 6-7 weeks
- **Extensions (v1.1-v1.4)**: Full-time for 9 weeks (optional)
- **Total**: 15-16 weeks for complete system
- **Code Reviews**: 2-3 hours per week
- **Testing Support**: As needed

### Infrastructure
- Dev MongoDB instance
- Dev Redis instance (for caching and queue handlers)
- CI/CD pipeline (GitHub Actions)
- Documentation hosting (GitHub Pages or similar)
- External service accounts for testing (optional):
  - Google/Facebook/Apple OAuth apps
  - Twilio for SMS testing
  - WhatsApp Business API (optional)
  - Telegram Bot API (optional)

---

## Success Metrics

### Technical Metrics (Updated v1.4)
- [ ] Test coverage >90% overall
- [ ] All presets have example apps
- [ ] **Performance: Permission checks <5ms (cached), <10ms (uncached with closure table)** - DD-036
- [ ] **Tree permission queries: <5ms (O(1) via closure table, 20x improvement)** - DD-036
- [ ] **API key validation: ~50-100ms (argon2id hashing, secure but slower)** - DD-028
- [ ] **JWT service token validation: <0.5ms (no DB, pure cryptographic validation)** - DD-034
- [ ] **Cache invalidation: <100ms across all distributed instances (Redis Pub/Sub)** - DD-037
- [ ] **Rate limiting: <1ms per check (in-memory), <3ms (Redis)**
- [ ] **API key usage tracking: 99%+ reduction in DB writes (Redis counters)** - DD-033
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

## Post-Launch Roadmap (v1.5+)

**Note**: v1.1-v1.4 authentication extensions are now part of the main roadmap (Phases 7-10).

### Version 1.5 (Weeks 17-20, optional)
- PostgreSQL support
- Multi-tenant mode refinements
- Additional ABAC operators
- Performance optimizations
- Admin UI component library (optional)

### Version 1.6 (Weeks 21-24, optional)
- Enhanced CLI tools
- Enhanced audit logging
- OpenTelemetry integration
- Advanced analytics dashboard

### Version 2.0 (6 months after v1.0)
- Plugin system for extensions
- Additional database backends (PostgreSQL, MySQL)
- SAML and LDAP support
- Open source release (if approved)

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
| 2025-01-14 | **v1.4 Architectural improvements** | Unified architecture with thin wrappers (DD-032), closure table for O(1) queries (DD-036), Redis counters for API keys (DD-033), Redis Pub/Sub cache invalidation (DD-037), temporary locks instead of revocation (DD-028), JWT service tokens (DD-034), single AuthDeps class (DD-035) |
| 2025-01-14 | **Added API key system to core v1.0** | Integrated API key authentication, multi-source auth, and dependency patterns into Phases 2, 3, and 6; API keys now core feature for service-to-service authentication |
| 2025-01-14 | Added authentication extensions (Phases 7-10) | Integrated OAuth, passwordless auth, notifications, and advanced features into main roadmap; total timeline now 15-16 weeks (6-7 weeks core + 9 weeks extensions) |
| 2025-01-14 | Revised to two-preset architecture | Consolidated HierarchicalRBAC and FullFeatured into EnterpriseRBAC with feature flags; added CLI tools, health checks, and comprehensive production guides |
| 2025-01-14 | Initial roadmap created | Project kickoff |

---

**Last Updated**: 2025-01-14 (v1.4 - Architectural improvements: unified architecture, closure table, Redis patterns, JWT service tokens)
**Next Review**: End of Week 2 (after Milestone 1)
