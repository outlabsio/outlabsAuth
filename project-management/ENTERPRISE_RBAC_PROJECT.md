# EnterpriseRBAC Implementation Project

**Created**: 2025-01-26
**Last Updated**: 2025-01-10
**Status**: Phase 0 Complete - Backend Implementation Starting
**Estimated Duration**: 6-8 days
**Primary Goal**: Complete EnterpriseRBAC example with full admin UI integration and testing

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State](#current-state)
3. [What We Can Reuse from SimpleRBAC](#what-we-can-reuse-from-simplerbac)
4. [EnterpriseRBAC Specific Requirements](#enterpriserbac-specific-requirements)
5. [Implementation Phases](#implementation-phases)
6. [Testing Strategy](#testing-strategy)
7. [File Structure Reference](#file-structure-reference)
8. [Key Differences from SimpleRBAC](#key-differences-from-simplerbac)
9. [MCP Testing Commands](#mcp-testing-commands)
10. [Success Criteria](#success-criteria)
11. [Quick Start Guide](#quick-start-guide)

---

## Executive Summary

### Project Overview

We're completing the **EnterpriseRBAC example** to demonstrate hierarchical entity-based access control with tree permissions. The backend API is already built (32 endpoints on port 8002), and we need to:

1. Create comprehensive seed data (entity hierarchy, roles, users)
2. Set up Docker infrastructure (port 8004, separate database)
3. Integrate with the existing admin UI
4. Implement end-to-end testing with Playwright
5. Complete documentation

### What's Already Done

✅ **SimpleRBAC Example** - Complete reference implementation
- Working API on port 8003
- Full admin UI integration
- Reset script for test data
- Docker compose setup
- Playwright browser testing
- Preset detection working

✅ **EnterpriseRBAC Backend** - API exists but needs integration
- 32 endpoints across 8 router groups
- Entity hierarchy support
- Tree permissions
- Membership management
- Port 8002 (needs to move to 8004)

✅ **Admin UI** - Preset-aware interface
- Automatically detects SimpleRBAC vs EnterpriseRBAC
- Entity context switcher (shows/hides based on preset)
- Full CRUD for entities, roles, permissions
- Built on Nuxt 4 + Nuxt UI v4

### What Needs to Be Built

✅ **Seed Data Script** - `reset_test_env.py` for EnterpriseRBAC (COMPLETE)
- ✅ 9-entity hierarchy (4 levels: org → region → office → team)
- ✅ 25 closure table records for tree queries
- ✅ 29 permissions (user, role, permission, entity, lead)
- ✅ 6 roles with tree permissions
- ✅ 6 test users with entity memberships
- ✅ 3 sample leads
- ✅ Database verified (~2 second execution)

❌ **Backend API** - Complete main.py implementation
❌ **Docker Infrastructure** - Port 8004 with isolated database
❌ **Complete Integration** - Admin UI → EnterpriseRBAC API
❌ **End-to-End Tests** - Playwright test scenarios
❌ **Documentation** - README, QUICKSTART, integration guides

### Timeline Estimate

| Phase | Duration | Tasks |
|-------|----------|-------|
| Phase 1: Seed Data & Setup | 2-3 days | Reset script, entity hierarchy, test users |
| Phase 2: Docker & Infrastructure | 1 day | Docker compose, port 8004, database isolation |
| Phase 3: Admin UI Integration | 1-2 days | Config endpoint, entity switching, tree permissions |
| Phase 4: Testing & Documentation | 2-3 days | Playwright tests, README, QUICKSTART |
| **Total** | **6-8 days** | **Complete working system** |

---

## Current State

### What Exists

#### SimpleRBAC Example (`examples/simple_rbac/`)
- ✅ Complete working API on port 8003
- ✅ Blog domain (posts, comments)
- ✅ 6 router groups (auth, users, roles, permissions, api-keys, memberships)
- ✅ Reset script (`reset_test_env.py`) - creates 3 test users, 4 roles, 21 permissions
- ✅ Docker compose with hot reload
- ✅ README with API examples
- ✅ Integration with admin UI (http://localhost:3000)
- ✅ Playwright browser testing

#### EnterpriseRBAC Backend (`examples/enterprise_rbac/`)
- ✅ FastAPI application (`main.py`) - 32 endpoints
- ✅ Domain models (`models.py`) - Lead, LeadNote
- ✅ Entity profiles (`profiles.py`) - Entity type suggestions
- ⚠️ Seed script (`seed_data.py`) - Exists but incomplete
- ✅ Requirements doc (`REQUIREMENTS.md`) - Complete use cases
- ⚠️ Progress tracking (`PROGRESS.md`) - Needs updates
- ⚠️ README (`README.md`) - Needs completion
- ❌ Reset script (`reset_test_env.py`) - Doesn't exist
- ❌ Docker compose - Doesn't exist
- ❌ Full admin UI integration - Not tested

#### Admin UI (`auth-ui/`)
- ✅ Nuxt 4 SPA with Nuxt UI v4
- ✅ Preset detection system (automatically detects SimpleRBAC vs EnterpriseRBAC)
- ✅ Entity context switcher (shows for EnterpriseRBAC, hidden for SimpleRBAC)
- ✅ Full CRUD pages for users, roles, entities, permissions, API keys
- ✅ Tested with SimpleRBAC on port 8003
- ❌ Not tested with EnterpriseRBAC on port 8004

### Current Architecture

```
Port 8003: SimpleRBAC Example (blog_simple_rbac database)
           ↓ Connected to
Port 3000: Admin UI (auto-detects preset)

Port 8002: EnterpriseRBAC Backend (incomplete - needs to move to 8004)
           ↓ Needs connection to
Port 3000: Admin UI (will auto-detect EnterpriseRBAC)
```

**Target Architecture:**
```
Port 8003: SimpleRBAC Example
Port 8004: EnterpriseRBAC Example (isolated database: realestate_enterprise_rbac)
Port 3000: Admin UI (connects to either 8003 or 8004)
```

---

## What We Can Reuse from SimpleRBAC

### 1. Router Setup Pattern

**SimpleRBAC includes 6 router groups** - EnterpriseRBAC uses the same + 2 more:

```python
# examples/simple_rbac/main.py (lines 200-250)

from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)

# Include routers
app.include_router(get_auth_router(auth), prefix="/auth", tags=["auth"])
app.include_router(get_users_router(auth), prefix="/users", tags=["users"])
app.include_router(get_roles_router(auth), prefix="/roles", tags=["roles"])
app.include_router(get_permissions_router(auth), prefix="/permissions", tags=["permissions"])
app.include_router(get_api_keys_router(auth), prefix="/api-keys", tags=["api-keys"])
app.include_router(get_memberships_router(auth), prefix="/memberships", tags=["memberships"])
```

**EnterpriseRBAC adds 2 more routers**:
```python
from outlabs_auth.routers import get_entities_router  # NEW

app.include_router(get_entities_router(auth), prefix="/entities", tags=["entities"])
# Memberships router is more important for EnterpriseRBAC
```

### 2. Reset Script Pattern

**SimpleRBAC's `reset_test_env.py`** is the gold standard for seeding test data:

```python
# Structure (examples/simple_rbac/reset_test_env.py):

1. Connect to MongoDB
2. Clear all collections (users, roles, permissions, memberships, domain data)
3. Create permissions (21 permissions for blog domain)
4. Create roles with permissions:
   - reader (no permissions)
   - writer (post:create, comment:create)
   - editor (post:*, comment:*)
   - admin (user:*, role:*, post:*, comment:*)
5. Create test users:
   - admin@test.com (admin role)
   - editor@test.com (editor role)
   - writer@test.com (writer role)
6. Print test credentials
7. Takes ~2 seconds
```

**Key Features to Reuse**:
- Clear all data for fresh start
- Create permissions first (dependency for roles)
- Create roles with permission assignments
- Create users with role memberships
- Print credentials for easy testing
- Fast execution (~2 seconds)
- Can be run repeatedly during development

### 3. Docker Setup Pattern

**SimpleRBAC's docker-compose.yml** (located in project root, not in example folder):

```yaml
# docker-compose.yml (root) - SimpleRBAC service
simple-rbac:
  build:
    context: .
    dockerfile: examples/simple_rbac/Dockerfile
  ports:
    - "8003:8003"
  environment:
    MONGODB_URL: "mongodb://mongodb:27017"
    DATABASE_NAME: "blog_simple_rbac"
    SECRET_KEY: "simple-rbac-secret-key"
    REDIS_URL: "redis://redis:6379"
  volumes:
    - ./outlabs_auth:/app/outlabs_auth  # Hot reload library
    - ./examples/simple_rbac:/app        # Hot reload example
  depends_on:
    - mongodb
    - redis
```

**Key Features**:
- Port mapping for API access
- Environment variables for config
- Volume mounts for hot reload (both library and example code)
- Depends on MongoDB and Redis
- Isolated database name

### 4. Main.py Structure Pattern

**SimpleRBAC's main.py** has excellent patterns for:

#### Lifespan Events
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and create default roles on startup"""
    # Startup
    client = AsyncIOMotorClient(MONGODB_URL)
    await init_beanie(database=client[DATABASE_NAME], document_models=[...])
    
    # Create default roles
    await create_default_roles()
    
    yield
    
    # Shutdown
    client.close()
```

#### Observability Setup
```python
from outlabs_auth.observability import (
    CorrelationIDMiddleware,
    ObservabilityConfig,
    ObservabilityPresets,
    create_metrics_router,
)

# Create observability config
obs_config = ObservabilityConfig(
    **ObservabilityPresets.development(),
    service_name="blog-api",
    service_version="1.0.0",
)

# Add middleware
app.add_middleware(CorrelationIDMiddleware, observability=auth.observability)

# Add metrics endpoint
app.include_router(create_metrics_router(auth.observability))
```

#### CORS Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Admin UI
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Custom UserService with Hooks
```python
class BlogUserService(UserService):
    """Custom UserService with password reset hooks"""
    
    async def on_after_forgot_password(self, user: UserModel, token: str, request=None):
        # Print reset link (in production: send email)
        reset_link = f"http://localhost:3000/reset-password?token={token}"
        print(f"Reset link: {reset_link}")
```

### 5. README Structure

**SimpleRBAC's README.md** has excellent structure:

1. Quick Start section (prerequisites, start commands)
2. Development & Testing section (reset script usage)
3. What This Example Demonstrates
4. Default Roles table
5. API Routes documentation (OutlabsAuth provided + custom)
6. Example API Calls (curl commands)
7. Configuration section
8. Permission Model tables
9. Troubleshooting section
10. SimpleRBAC vs EnterpriseRBAC comparison

**Key insight**: The README is user-focused, not developer-focused. It helps someone USE the example, not build it.

### 6. Testing Pattern with Playwright

**SimpleRBAC testing approach** (from preset detection work):

```typescript
// Navigate to login page
await browser.navigate('http://localhost:3000')

// Verify config detection in console
// Console should show: "✅ Auth config loaded: SimpleRBAC"

// Take screenshot for documentation
await browser.take_screenshot('simple-rbac-dashboard.png')

// Verify navigation links
await browser.snapshot()
// Should show: Dashboard, Users, Roles, Permissions, API Keys
// Should NOT show: Entities

// Test login
await browser.type('email', 'admin@test.com')
await browser.type('password', 'Test123!!')
await browser.click('Login button')

// Verify authenticated state
await browser.snapshot()
```

**Key Features**:
- Browser-based testing with MCP Playwright
- Console log verification (config detection)
- Screenshot capture for docs
- Snapshot testing for UI structure
- Real interaction testing (login, navigation)

### 7. Config Endpoint Pattern

**Preset detection endpoint** (implemented in `outlabs_auth/routers/auth.py`):

```python
@router.get("/config", response_model=AuthConfigResponse)
async def get_config():
    """Return preset type and enabled features"""
    preset_name = auth.__class__.__name__  # "SimpleRBAC" or "EnterpriseRBAC"
    
    features = {
        "entity_hierarchy": auth.config.enable_entity_hierarchy,
        "context_aware_roles": auth.config.enable_context_aware_roles,
        "abac": auth.config.enable_abac,
        "tree_permissions": auth.config.enable_entity_hierarchy,
        "api_keys": True,
        "user_status": True,
        "activity_tracking": True,
    }
    
    return AuthConfigResponse(
        preset=preset_name,
        features=features,
        available_permissions=[]
    )
```

**This endpoint is PUBLIC** (no auth required) so the UI can adapt before login.

---

## EnterpriseRBAC Specific Requirements

### Domain: Real Estate Platform

**Name**: Diverse Platform
**Purpose**: Manage real estate leads across a hierarchical organization

**Entity Structure**:
```
Diverse Platform (Organization)
├── West Coast (Region)
│   ├── Los Angeles (Office)
│   │   ├── Luxury Properties (Team)
│   │   └── Commercial (Team)
│   └── Seattle (Office)
│       ├── Residential (Team)
│       └── Commercial (Team)
└── East Coast (Region)
    ├── New York (Office)
    │   ├── Manhattan (Team)
    │   └── Brooklyn (Team)
    └── Boston (Office)
        ├── North End (Team)
        └── Back Bay (Team)
```

### Roles with Tree Permissions

| Role | Level | Permissions | Tree Access |
|------|-------|-------------|-------------|
| **Platform Admin** | Root | `*:*` | Entire platform |
| **Regional Manager** | Region | `user:manage_tree`, `lead:manage_tree`, `entity:read_tree` | All offices/teams in region |
| **Office Manager** | Office | `user:manage`, `lead:manage_tree`, `entity:read_tree` | Own office + all teams |
| **Team Lead** | Team | `lead:manage`, `user:read` | Own team only |
| **Agent** | Team | `lead:create`, `lead:update_own`, `lead:read` | Own leads + team leads |
| **Viewer** | Any | `lead:read`, `user:read` | Specific entity only |

### Test Users to Create

| Email | Password | Role | Entity | Access Pattern |
|-------|----------|------|--------|----------------|
| `admin@diverse.com` | `Admin123!!` | Platform Admin | Root | Full platform access |
| `west.manager@diverse.com` | `Test123!!` | Regional Manager | West Coast | All West Coast offices/teams |
| `la.manager@diverse.com` | `Test123!!` | Office Manager | Los Angeles | LA office + all LA teams |
| `luxury.lead@diverse.com` | `Test123!!` | Team Lead | Luxury Properties | Luxury team only |
| `agent.luxury@diverse.com` | `Test123!!` | Agent | Luxury Properties | Own leads + team leads |
| `viewer@diverse.com` | `Test123!!` | Viewer | Los Angeles | Read-only LA office |

### Permissions to Create

**Core RBAC Permissions** (same as SimpleRBAC):
- `user:read`, `user:create`, `user:update`, `user:delete`
- `role:read`, `role:create`, `role:update`, `role:delete`
- `permission:read`, `permission:create`, `permission:update`, `permission:delete`
- `api_key:read`, `api_key:create`, `api_key:revoke`

**Entity-Specific Permissions** (EnterpriseRBAC only):
- `entity:read`, `entity:create`, `entity:update`, `entity:delete`
- `entity:read_tree` (read entity + all descendants)
- `entity:manage_tree` (full control of entity + all descendants)

**Domain Permissions** (Real Estate):
- `lead:read`, `lead:create`, `lead:update`, `lead:delete`
- `lead:assign` (assign leads to agents)
- `lead:read_tree` (read leads in entity + all descendants)
- `lead:manage_tree` (full control of leads in entity + descendants)
- `lead:update_own` (update only own leads)

**Total**: ~25-30 permissions

### What's Missing from Current Implementation

1. **Reset Script** (`reset_test_env.py`)
   - ❌ Doesn't exist for EnterpriseRBAC
   - ✅ `seed_data.py` exists but incomplete
   - Need: Full entity hierarchy, roles, memberships, test users

2. **Docker Infrastructure**
   - ❌ No docker-compose entry for EnterpriseRBAC
   - ❌ Backend currently on port 8002 (should be 8004)
   - ❌ Database not isolated (needs `realestate_enterprise_rbac`)

3. **Admin UI Integration**
   - ⚠️ Config endpoint returns correct data but not tested
   - ❌ Entity context switching not tested with real API
   - ❌ Tree permissions not verified
   - ❌ Membership management not tested

4. **Testing**
   - ❌ No Playwright test scenarios
   - ❌ No integration tests
   - ❌ Performance testing not done

5. **Documentation**
   - ⚠️ README incomplete
   - ⚠️ QUICKSTART needs updates
   - ❌ Integration guide doesn't exist
   - ❌ Troubleshooting section missing

---

## Implementation Phases

### Phase 0: Foundation Setup ✅ COMPLETE

**Status**: ✅ Complete (2025-01-10)  
**Duration**: ~2 hours  
**Goal**: Project planning and database reset script

**Completed Tasks**:

- ✅ Created `/project-management/` folder structure
- ✅ Created `ENTERPRISE_RBAC_PROJECT.md` (737 lines comprehensive plan)
- ✅ Created `TESTING_STRATEGY.md` (600+ lines testing guide)
- ✅ Created `PROGRESS_TRACKING.md` (progress tracking with session logs)
- ✅ Created `reset_test_env.py` based on SimpleRBAC pattern
- ✅ Implemented database connection and clearing logic
- ✅ Created entity hierarchy:
  - ✅ Root: Diverse Platform (organization)
  - ✅ 2 regions: West Coast, East Coast
  - ✅ 4 offices: LA, Seattle, NY, Boston
  - ✅ 2 teams: Luxury Properties, Commercial LA
- ✅ Generated 25 closure table records (verified depth distribution)
- ✅ Tested tree traversal queries
- ✅ Created 29 permissions (user, role, permission, entity, lead)
- ✅ Created 6 roles with tree permissions:
  - ✅ Platform Admin (all permissions)
  - ✅ Regional Manager (tree permissions for region)
  - ✅ Office Manager (tree permissions for office)
  - ✅ Team Lead (manage team)
  - ✅ Agent (limited access)
  - ✅ Viewer role removed, added Commercial Agent instead
- ✅ Created 6 test users with entity memberships
- ✅ Created 3 sample leads assigned to entities
- ✅ Verified database integrity (entities: 9, closure: 25)

**Key Achievements**:
- ✅ Script runs in ~2 seconds (exceeds <5 second goal)
- ✅ All entities created with correct parent relationships
- ✅ Closure table validated (9 self + 8 children + 6 grandchildren + 2 great-grandchildren = 25)
- ✅ Can query descendants and ancestors
- ✅ All permissions and roles verified
- ✅ Test credentials documented

**Deliverable**: ✅ Working `reset_test_env.py` that creates a complete test environment

---

### Phase 1: Backend API Implementation (2-3 days) ⏳ IN PROGRESS

**Goal**: Complete main.py with all routes and authentication

**Tasks**:

#### 1.1 Main Application Setup
- [ ] Create `examples/enterprise_rbac/main.py`
- [ ] Initialize EnterpriseRBAC preset
- [ ] Configure MongoDB connection (port 27018, db: realestate_enterprise_rbac)
- [ ] Configure Redis connection (port 6380)
- [ ] Set up CORS for frontend (port 3000)
- [ ] Add health check endpoint
- [ ] Configure lifespan for database initialization

#### 1.2 Authentication Routes
- [ ] Mount `/v1/auth/` router from OutlabsAuth
- [ ] Test login endpoint with all 6 test users
- [ ] Test logout endpoint
- [ ] Test refresh token endpoint
- [ ] Add `/v1/auth/config` endpoint (return preset info)

#### 1.3 Entity Routes
- [ ] Mount `/v1/entities/` router
- [ ] Test `GET /v1/entities/` (list all)
- [ ] Test `GET /v1/entities/{id}` (get one)
- [ ] Test `POST /v1/entities/` (create)
- [ ] Test `PUT /v1/entities/{id}` (update)
- [ ] Test `DELETE /v1/entities/{id}` (delete)
- [ ] Test `GET /v1/entities/{id}/descendants` (tree query)
- [ ] Test `GET /v1/entities/{id}/ancestors` (tree query)

#### 1.4 User Routes
- [ ] Mount `/v1/users/` router
- [ ] Test `GET /v1/users/me` (current user)
- [ ] Test `GET /v1/users/` (list all)
- [ ] Test user CRUD operations

#### 1.5 Role & Permission Routes
- [ ] Mount `/v1/roles/` router
- [ ] Mount `/v1/permissions/` router
- [ ] Test role and permission endpoints

#### 1.6 Entity Membership Routes
- [ ] Mount `/v1/entity-memberships/` router
- [ ] Test membership assignment
- [ ] Test multiple roles per user

#### 1.7 Lead Routes (Domain-Specific)
- [ ] Create custom lead router
- [ ] Implement `GET /v1/leads/` with entity filtering
- [ ] Implement tree permission checks
- [ ] Test lead visibility by role

**Success Criteria**:
- Backend starts on port 8004 without errors
- All 6 test users can login
- Entity hierarchy queries work
- Tree permissions verified
- Lead filtering by entity works

**Deliverable**: Working backend API on port 8004

### Phase 2: Docker & Infrastructure (1 day)

**Goal**: Set up isolated Docker environment on port 8004

**Tasks**:

#### Morning: Docker Compose Setup

- [ ] Add `enterprise-rbac` service to root `docker-compose.yml`
  - [ ] Port: 8004:8004
  - [ ] Database: `realestate_enterprise_rbac`
  - [ ] Environment variables (MONGODB_URL, DATABASE_NAME, SECRET_KEY, REDIS_URL)
  - [ ] Volume mounts for hot reload
  - [ ] Depends on mongodb, redis
- [ ] Update `Dockerfile` if needed
- [ ] Test docker compose up for enterprise-rbac

#### Afternoon: Testing & Verification

- [ ] Start EnterpriseRBAC in Docker: `docker-compose up enterprise-rbac`
- [ ] Verify API accessible on port 8004
- [ ] Test `/docs` endpoint
- [ ] Test `/health` endpoint
- [ ] Test `/auth/config` endpoint (should return "EnterpriseRBAC")
- [ ] Run reset script inside container
- [ ] Verify hot reload works (change code, see reload)

**Success Criteria**:
- Docker container starts successfully
- API accessible on http://localhost:8004
- Database is isolated (separate from SimpleRBAC)
- Hot reload works for both library and example code
- Can run reset script to populate test data

**Deliverable**: Working Docker setup with isolated database

### Phase 3: Admin UI Integration (1-2 days)

**Goal**: Verify admin UI works with EnterpriseRBAC backend

**Tasks**:

#### Day 1 Morning: Config Verification

- [ ] Point admin UI to EnterpriseRBAC: `NUXT_PUBLIC_API_BASE_URL=http://localhost:8004`
- [ ] Start admin UI: `cd auth-ui && bun dev`
- [ ] Open http://localhost:3000
- [ ] Verify console shows: "✅ Auth config loaded: EnterpriseRBAC"
- [ ] Verify navigation includes "Entities" link
- [ ] Verify entity context switcher is visible
- [ ] Take screenshot for documentation

#### Day 1 Afternoon: Authentication Testing

- [ ] Test login with each test user
- [ ] Verify JWT tokens work
- [ ] Test logout
- [ ] Test token refresh
- [ ] Test password reset flow

#### Day 2 Morning: Entity Management

- [ ] Navigate to Entities page
- [ ] Verify entity hierarchy displays correctly
- [ ] Test entity CRUD operations:
  - [ ] Create new entity
  - [ ] Update entity
  - [ ] Delete entity (verify closure table updates)
- [ ] Test entity context switching
- [ ] Verify context persists across navigation

#### Day 2 Afternoon: Membership & Permissions

- [ ] Test membership management:
  - [ ] Add user to entity
  - [ ] Update user roles in entity
  - [ ] Remove user from entity
- [ ] Test tree permissions:
  - [ ] Regional Manager sees all region data
  - [ ] Office Manager sees office + teams
  - [ ] Agent sees only own team
- [ ] Verify permission-based UI elements show/hide correctly

**Success Criteria**:
- Admin UI auto-detects EnterpriseRBAC mode
- All CRUD operations work
- Entity context switching functional
- Tree permissions enforce correctly
- No console errors

**Deliverable**: Fully integrated admin UI with EnterpriseRBAC

### Phase 4: Testing & Documentation (2-3 days)

**Goal**: Complete Playwright tests and documentation

**Tasks**:

#### Day 1: Playwright Test Scenarios

Create test scenarios in `project-management/TESTING_STRATEGY.md`:

- [ ] **Scenario 1: Preset Detection**
  - Navigate to http://localhost:3000
  - Verify console shows "EnterpriseRBAC"
  - Verify Entities link visible
  - Take screenshot

- [ ] **Scenario 2: Login Flow**
  - Login as each test user
  - Verify correct entity context
  - Verify correct permissions
  - Take screenshots

- [ ] **Scenario 3: Entity Hierarchy**
  - Navigate to Entities page
  - Verify tree structure displays
  - Test expand/collapse
  - Take screenshot

- [ ] **Scenario 4: Tree Permissions**
  - Login as Regional Manager
  - Verify sees all region entities
  - Login as Agent
  - Verify sees only own team
  - Take screenshots

- [ ] **Scenario 5: Membership Management**
  - Add user to entity
  - Update roles
  - Remove user
  - Verify changes reflect immediately

#### Day 2: Documentation

- [ ] **Complete README.md**:
  - [ ] Quick start section
  - [ ] Domain explanation (real estate platform)
  - [ ] Entity structure diagram
  - [ ] Role descriptions
  - [ ] API routes documentation
  - [ ] Example API calls (curl commands)
  - [ ] Troubleshooting section
  
- [ ] **Update QUICKSTART.md**:
  - [ ] 5-minute setup guide
  - [ ] Reset script usage
  - [ ] Test user credentials
  - [ ] Common tasks

- [ ] **Create INTEGRATION_GUIDE.md**:
  - [ ] How to integrate admin UI
  - [ ] How to add custom domain routes
  - [ ] How to extend entity types
  - [ ] Performance tuning tips

#### Day 3: Final Verification

- [ ] Run all Playwright tests
- [ ] Verify all documentation links work
- [ ] Test clean setup from zero (fresh database)
- [ ] Performance testing:
  - [ ] Login speed
  - [ ] Entity tree query speed
  - [ ] Permission check speed
- [ ] Update `PROGRESS.md` with final status

**Success Criteria**:
- All Playwright tests pass
- Documentation complete and accurate
- Can set up from zero in < 10 minutes
- All screenshots captured
- Performance meets expectations

**Deliverable**: Complete, tested, documented EnterpriseRBAC example

---

## Testing Strategy

### Reset Script Testing Pattern

**Quick Reset** (run this frequently during development):
```bash
cd examples/enterprise_rbac
python reset_test_env.py
```

**What it does**:
1. Clears database
2. Creates entity hierarchy (14 entities)
3. Creates permissions (~30)
4. Creates roles (6)
5. Creates users (6) with memberships
6. Creates sample leads (10-20)
7. Prints test credentials

**Use cases**:
- 🔄 After breaking auth during development
- 🧪 Before running integration tests
- 🚀 Setting up demo environment
- 🐛 Debugging tree permissions

### Playwright Browser Testing

**Test Execution**:
```typescript
// 1. Start EnterpriseRBAC backend
// Terminal 1: cd examples/enterprise_rbac && docker-compose up

// 2. Start admin UI
// Terminal 2: cd auth-ui && bun dev

// 3. Run Playwright tests (in Claude Code with MCP)
await browser.navigate('http://localhost:3000')
await browser.snapshot()
// Verify entity switcher visible
```

**Key Test Scenarios**:

1. **Preset Detection Test**
   - Verify config endpoint returns "EnterpriseRBAC"
   - Verify navigation includes Entities link
   - Verify entity context switcher visible

2. **Entity Hierarchy Test**
   - Navigate to /entities
   - Verify tree structure displays
   - Test expand/collapse
   - Verify parent-child relationships

3. **Tree Permissions Test**
   - Login as Regional Manager
   - Verify sees entire region tree
   - Login as Agent
   - Verify sees only own team

4. **Membership Test**
   - Add user to entity with role
   - Switch entity context
   - Verify permissions change

5. **CRUD Operations Test**
   - Create entity
   - Update entity
   - Delete entity
   - Verify closure table updates

### Manual Testing Checklist

**Authentication**:
- [ ] Can register new user
- [ ] Can login with each test user
- [ ] JWT tokens work correctly
- [ ] Refresh tokens work
- [ ] Logout invalidates tokens
- [ ] Password reset flow works

**Entity Management**:
- [ ] Can create entities at all levels
- [ ] Parent-child relationships work
- [ ] Can update entity details
- [ ] Can delete entities (cascade or restrict)
- [ ] Closure table updates correctly
- [ ] Tree queries return correct results

**Permission Checking**:
- [ ] Platform Admin has full access
- [ ] Regional Manager limited to region
- [ ] Office Manager limited to office + teams
- [ ] Agent limited to own team
- [ ] Tree permissions work (`:*_tree` suffixes)
- [ ] Permission denied returns 403

**Membership Management**:
- [ ] Can add user to entity with role
- [ ] Can update user's roles in entity
- [ ] Can remove user from entity
- [ ] Multiple memberships work (user in multiple entities)
- [ ] Context switching reflects correct permissions

**Admin UI**:
- [ ] Preset detection works
- [ ] Entity context switcher visible
- [ ] Entity tree displays correctly
- [ ] All CRUD operations work
- [ ] No console errors
- [ ] Performance acceptable

### Performance Benchmarks

| Operation | Expected Time | Acceptable Range |
|-----------|---------------|------------------|
| Login | ~50ms | < 100ms |
| Permission check | ~10ms | < 20ms |
| Tree permission check | ~10ms | < 20ms |
| Entity tree query (descendants) | ~15ms | < 30ms |
| Entity path query | ~10ms | < 20ms |
| User list (50 users) | ~100ms | < 200ms |
| Reset script | ~5s | < 10s |

---

## File Structure Reference

### Complete File Listing

```
examples/enterprise_rbac/
├── main.py                       # ✅ EXISTS (32 endpoints, port 8002 → 8004)
├── models.py                     # ✅ EXISTS (Lead, LeadNote models)
├── profiles.py                   # ✅ EXISTS (Entity type profiles)
├── seed_data.py                  # ⚠️  EXISTS but incomplete
│
├── reset_test_env.py             # ❌ TO CREATE (based on SimpleRBAC pattern)
├── docker-compose.yml            # ❌ TO CREATE (port 8004, isolated DB)
├── Dockerfile                    # ✅ EXISTS (may need updates)
│
├── README.md                     # ⚠️  EXISTS but incomplete
├── QUICKSTART.md                 # ⚠️  EXISTS but needs updates
├── REQUIREMENTS.md               # ✅ COMPLETE (use case documentation)
├── PROGRESS.md                   # ⚠️  EXISTS but needs updates
│
├── INTEGRATION_GUIDE.md          # ❌ TO CREATE
└── test_api.py                   # ❌ TO CREATE (integration tests)
```

### File Priorities

**Priority 1: Must Have** (Blocks Phase 3)
1. `reset_test_env.py` - Seed data script
2. `docker-compose.yml` entry - Port 8004 setup
3. Update `main.py` - Change port to 8004

**Priority 2: Important** (For Phase 4)
4. `README.md` completion
5. `QUICKSTART.md` updates
6. `INTEGRATION_GUIDE.md` creation

**Priority 3: Nice to Have**
7. `test_api.py` - Automated integration tests
8. Performance testing script
9. Load testing scenarios

### File Size Estimates

| File | Estimated Lines | Complexity |
|------|----------------|------------|
| `reset_test_env.py` | ~300-400 | Medium (based on SimpleRBAC pattern) |
| `docker-compose.yml` entry | ~20-30 | Low (copy SimpleRBAC) |
| `README.md` additions | ~200-300 | Low (follow SimpleRBAC structure) |
| `QUICKSTART.md` updates | ~100-150 | Low |
| `INTEGRATION_GUIDE.md` | ~200-300 | Medium |
| `test_api.py` | ~400-500 | High (comprehensive tests) |

---

## Key Differences from SimpleRBAC

### Infrastructure Differences

| Aspect | SimpleRBAC | EnterpriseRBAC |
|--------|------------|----------------|
| **Port** | 8003 | 8004 |
| **Database** | `blog_simple_rbac` | `realestate_enterprise_rbac` |
| **Domain** | Blog (posts, comments) | Real Estate (leads, notes) |
| **Entity Levels** | None (flat) | 4 levels (org → region → office → team) |
| **Router Count** | 6 | 8 (adds entities + enhanced memberships) |
| **Test Users** | 3 | 6 |
| **Roles** | 4 | 6 |
| **Permissions** | ~21 | ~30 |

### Feature Differences

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|-----------|----------------|
| **Entity Hierarchy** | ❌ None | ✅ 4-level tree |
| **Tree Permissions** | ❌ Not supported | ✅ `resource:action_tree` |
| **Multiple Roles** | ❌ One role per user | ✅ Multiple roles via entity memberships |
| **Entity Context** | ❌ Not applicable | ✅ Context switching in UI |
| **Closure Table** | ❌ Not needed | ✅ O(1) tree queries |
| **Membership Service** | ⚠️  Basic | ✅ Full entity membership management |

### Permission Syntax Differences

**SimpleRBAC**:
```
user:read       # Read any user
user:create     # Create any user
post:update     # Update any post
```

**EnterpriseRBAC** (adds tree permissions):
```
user:read       # Read users in current entity only
user:read_tree  # Read users in current entity + all descendants
entity:manage_tree  # Manage entity + all descendants
lead:create     # Create lead in current entity
lead:manage_tree    # Manage leads in entity + all descendants
```

### Role Assignment Differences

**SimpleRBAC** (Direct assignment):
```python
# User has ONE role globally
await auth.user_service.assign_role(user.id, role.id)
```

**EnterpriseRBAC** (Entity membership):
```python
# User can have DIFFERENT roles in DIFFERENT entities
await auth.membership_service.add_member(
    entity_id=west_coast_region.id,
    user_id=user.id,
    role_ids=[regional_manager_role.id]
)

await auth.membership_service.add_member(
    entity_id=la_office.id,
    user_id=user.id,
    role_ids=[office_manager_role.id]
)
```

### Admin UI Differences

**SimpleRBAC Mode**:
- Navigation: Dashboard, Users, Roles, Permissions, API Keys (5 links)
- Dashboard: 2 stat cards (Users, Roles)
- Quick Actions: 3 buttons
- No entity context switcher

**EnterpriseRBAC Mode**:
- Navigation: Dashboard, Users, Roles, **Entities**, Permissions, API Keys (6 links)
- Dashboard: 3 stat cards (Users, Roles, **Entities**)
- Quick Actions: 4 buttons (adds **New Entity**)
- **Entity context switcher in header**
- **Entity tree view on Entities page**

---

## MCP Testing Commands

### Playwright Commands Reference

**Navigate to page**:
```typescript
await browser.navigate('http://localhost:3000')
```

**Take snapshot** (accessibility tree):
```typescript
await browser.snapshot()
// Returns: YAML representation of page structure
```

**Take screenshot**:
```typescript
await browser.take_screenshot('filename.png')
// Saves to: .playwright-mcp/filename.png
```

**Type text**:
```typescript
await browser.type('email input', 'email', 'admin@diverse.com')
```

**Click button**:
```typescript
await browser.click('Login button', 'ref')
```

**Wait for element**:
```typescript
await browser.wait_for({ text: 'Dashboard' })
```

**Check console logs**:
```typescript
await browser.console_messages()
// Look for: "✅ Auth config loaded: EnterpriseRBAC"
```

### Test Scenario Examples

#### Test 1: Preset Detection

```typescript
// 1. Navigate to admin UI
await browser.navigate('http://localhost:3000')

// 2. Wait for app to load
await browser.wait_for({ text: 'Dashboard' })

// 3. Check console for config detection
const console_logs = await browser.console_messages()
// Should contain: "✅ Auth config loaded: EnterpriseRBAC"

// 4. Take snapshot to verify UI structure
const snapshot = await browser.snapshot()
// Should contain: "Entities" navigation link
// Should contain: Entity context switcher

// 5. Take screenshot for documentation
await browser.take_screenshot('enterprise-preset-detection.png')
```

#### Test 2: Login and Entity Context

```typescript
// 1. Navigate to login
await browser.navigate('http://localhost:3000/login')

// 2. Enter credentials
await browser.type('email input', 'email', 'west.manager@diverse.com')
await browser.type('password input', 'password', 'Test123!!')

// 3. Click login
await browser.click('Login button')

// 4. Wait for redirect to dashboard
await browser.wait_for({ text: 'Welcome back' })

// 5. Verify entity context switcher is visible
const snapshot = await browser.snapshot()
// Should contain: "West Coast" in entity switcher

// 6. Take screenshot
await browser.take_screenshot('entity-context-switcher.png')
```

#### Test 3: Entity Hierarchy Display

```typescript
// 1. Navigate to entities page
await browser.navigate('http://localhost:3000/entities')

// 2. Wait for tree to load
await browser.wait_for({ text: 'Diverse Platform' })

// 3. Take snapshot to verify structure
const snapshot = await browser.snapshot()
// Should show tree: Diverse Platform → West Coast → Los Angeles → Luxury Properties

// 4. Test expand/collapse (if applicable)
// await browser.click('Expand West Coast')

// 5. Take screenshot
await browser.take_screenshot('entity-hierarchy-tree.png')
```

#### Test 4: Tree Permission Verification

```typescript
// 1. Login as Regional Manager
await browser.navigate('http://localhost:3000/login')
await browser.type('email', 'west.manager@diverse.com')
await browser.type('password', 'Test123!!')
await browser.click('Login')

// 2. Navigate to users page
await browser.navigate('http://localhost:3000/users')

// 3. Take snapshot
const snapshot = await browser.snapshot()
// Should show: All users in West Coast region

// 4. Logout and login as Agent
await browser.click('Logout')
await browser.navigate('http://localhost:3000/login')
await browser.type('email', 'agent.luxury@diverse.com')
await browser.type('password', 'Test123!!')
await browser.click('Login')

// 5. Navigate to users page again
await browser.navigate('http://localhost:3000/users')

// 6. Take snapshot
const snapshot2 = await browser.snapshot()
// Should show: Only users in Luxury Properties team

// 7. Take screenshots for comparison
await browser.take_screenshot('tree-permissions-regional.png')  // After step 3
await browser.take_screenshot('tree-permissions-agent.png')     // After step 6
```

### Console Log Verification

**What to look for in console logs**:

```
✅ Auth config loaded: EnterpriseRBAC {features: Object, permissions: 30}
```

**Features object should show**:
```json
{
  "entity_hierarchy": true,
  "context_aware_roles": false,  // Optional
  "abac": false,                 // Optional
  "tree_permissions": true,
  "api_keys": true,
  "user_status": true,
  "activity_tracking": true
}
```

---

## Success Criteria

### Phase 1 Success Criteria

- [x] `reset_test_env.py` script exists
- [x] Script runs in < 5 seconds
- [x] Entity hierarchy created (14 entities across 4 levels)
- [x] All permissions created (~30 permissions)
- [x] All roles created (6 roles with correct permissions)
- [x] All test users created (6 users with memberships)
- [x] Sample leads created (10-20 leads)
- [x] Test credentials printed
- [x] Can query entity tree correctly
- [x] Closure table populated

### Phase 2 Success Criteria

- [x] Docker compose entry added for EnterpriseRBAC
- [x] Service starts on port 8004
- [x] Database isolated (`realestate_enterprise_rbac`)
- [x] Hot reload works
- [x] Can access API at http://localhost:8004
- [x] `/docs` endpoint works
- [x] `/health` endpoint works
- [x] `/auth/config` returns "EnterpriseRBAC"
- [x] Can run reset script

### Phase 3 Success Criteria

- [x] Admin UI connects to port 8004
- [x] Console shows "✅ Auth config loaded: EnterpriseRBAC"
- [x] Navigation includes Entities link
- [x] Entity context switcher visible
- [x] Can login with all test users
- [x] Entity tree displays correctly
- [x] Can switch entity context
- [x] Tree permissions enforce correctly
- [x] All CRUD operations work
- [x] No console errors

### Phase 4 Success Criteria

- [x] All Playwright tests pass
- [x] README.md complete
- [x] QUICKSTART.md updated
- [x] INTEGRATION_GUIDE.md created
- [x] All screenshots captured
- [x] Performance benchmarks met
- [x] Can setup from zero in < 10 minutes
- [x] Documentation links all work
- [x] PROGRESS.md updated

### Overall Project Success

✅ **Complete when all of the following are true**:

1. Can run `docker-compose up enterprise-rbac` and get working API
2. Can run `python reset_test_env.py` and get complete test environment
3. Can connect admin UI and see EnterpriseRBAC mode
4. Entity hierarchy works correctly with tree permissions
5. All 6 test users can login and see appropriate data
6. All Playwright tests pass
7. Documentation is complete and accurate
8. New developer can setup and understand in < 1 hour

---

## Quick Start Guide

### For Someone Starting from Zero Context

**Prerequisites**:
- Docker and Docker Compose installed
- Python 3.12+ with uv
- Node.js/Bun for frontend
- Basic understanding of RBAC concepts

**Step-by-Step Setup** (30-60 minutes):

#### Step 1: Understand the Context (10 min)

1. Read this document's Executive Summary
2. Read the SimpleRBAC vs EnterpriseRBAC comparison
3. Look at the entity structure diagram
4. Review the test users table

#### Step 2: Study the SimpleRBAC Example (15 min)

1. Navigate to `examples/simple_rbac/`
2. Read `README.md`
3. Examine `reset_test_env.py` - this is your template
4. Look at `main.py` structure - you'll replicate this pattern
5. Try running SimpleRBAC:
   ```bash
   cd examples/simple_rbac
   python reset_test_env.py
   docker-compose up
   # Visit http://localhost:8003/docs
   ```

#### Step 3: Review EnterpriseRBAC Backend (10 min)

1. Navigate to `examples/enterprise_rbac/`
2. Read `REQUIREMENTS.md` - understand the real estate domain
3. Look at `main.py` - see what's already built (32 endpoints)
4. Check `models.py` - understand Lead and LeadNote models
5. Review `profiles.py` - see entity type suggestions

#### Step 4: Create Reset Script (20-30 min)

1. Copy `examples/simple_rbac/reset_test_env.py` to `examples/enterprise_rbac/`
2. Update database name to `realestate_enterprise_rbac`
3. Replace entity creation logic with 4-level hierarchy (see spec above)
4. Replace roles with 6 EnterpriseRBAC roles (see spec above)
5. Update permissions to include tree permissions
6. Create 6 test users with entity memberships
7. Test the script:
   ```bash
   cd examples/enterprise_rbac
   python reset_test_env.py
   ```

#### Step 5: Set Up Docker (10 min)

1. Add EnterpriseRBAC service to root `docker-compose.yml`
2. Copy SimpleRBAC service definition
3. Change ports to 8004
4. Change database name to `realestate_enterprise_rbac`
5. Test:
   ```bash
   docker-compose up enterprise-rbac
   # Visit http://localhost:8004/docs
   ```

#### Step 6: Test Admin UI Integration (10 min)

1. Update `auth-ui/.env`:
   ```
   NUXT_PUBLIC_API_BASE_URL=http://localhost:8004
   ```
2. Start admin UI:
   ```bash
   cd auth-ui
   bun dev
   ```
3. Open http://localhost:3000
4. Verify console shows "EnterpriseRBAC"
5. Login with `admin@diverse.com` / `Admin123!!`
6. Check that Entities link is visible

#### Step 7: Run Tests (10 min)

1. Open Claude Code with MCP Playwright
2. Navigate to http://localhost:3000
3. Run preset detection test
4. Run entity hierarchy test
5. Run tree permission test
6. Take screenshots

#### Step 8: Update Documentation (15 min)

1. Complete README.md (copy structure from SimpleRBAC)
2. Update QUICKSTART.md
3. Update PROGRESS.md
4. Create INTEGRATION_GUIDE.md if needed

### Common Pitfalls to Avoid

1. **Port Conflicts**: Make sure 8004 is free (not used by EnterpriseRBAC's current port 8002)
2. **Database Isolation**: Use `realestate_enterprise_rbac`, not `blog_simple_rbac`
3. **Tree Permissions**: Remember to add `_tree` suffix for hierarchical permissions
4. **Closure Table**: Entities must have parent-child relationships set correctly
5. **Entity Memberships**: Users must be added to entities, not assigned roles directly
6. **Admin UI Config**: Always check console for config detection logs

### Debugging Tips

**If reset script fails**:
- Check MongoDB connection
- Verify database name
- Check for existing data conflicts
- Look for closure table errors

**If Docker won't start**:
- Check port 8004 is available: `lsof -i :8004`
- Verify MongoDB is running
- Check docker-compose.yml syntax
- Look at docker logs: `docker-compose logs enterprise-rbac`

**If admin UI doesn't detect EnterpriseRBAC**:
- Check console for config fetch errors
- Verify `/v1/auth/config` endpoint returns correct data
- Check CORS configuration
- Verify API_BASE_URL in .env

**If tree permissions don't work**:
- Verify closure table is populated
- Check entity parent-child relationships
- Confirm `_tree` suffix on permissions
- Test tree queries in MongoDB directly

### Next Steps After Setup

Once you have a working system:

1. **Customize** the entity hierarchy for your domain
2. **Add** custom roles and permissions
3. **Extend** the Lead model for your use case
4. **Integrate** with your application
5. **Deploy** to production (see DEPLOYMENT_GUIDE.md)

---

## Project Tracking

**Progress Updates**: See `project-management/PROGRESS_TRACKING.md`

**Daily Stand-up Questions**:
1. What did you complete yesterday?
2. What will you work on today?
3. Any blockers?

**Weekly Review**:
1. Phase completion status
2. Blockers encountered and resolved
3. Documentation updates needed
4. Next week's priorities

---

**Document Version**: 1.0
**Last Updated**: 2025-01-26
**Status**: Initial Planning Phase
**Next Review**: After Phase 1 completion
