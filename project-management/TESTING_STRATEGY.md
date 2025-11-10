# Testing Strategy for EnterpriseRBAC

**Created**: 2025-01-10  
**Status**: Active  
**Related**: [ENTERPRISE_RBAC_PROJECT.md](./ENTERPRISE_RBAC_PROJECT.md)

## Overview

This document outlines the comprehensive testing strategy for the EnterpriseRBAC implementation, covering database seeding, API testing, frontend integration testing, and end-to-end workflows.

---

## Table of Contents

1. [Testing Layers](#testing-layers)
2. [Database Reset & Seeding](#database-reset--seeding)
3. [API Testing](#api-testing)
4. [Frontend Integration Testing](#frontend-integration-testing)
5. [MCP Browser Testing (Playwright)](#mcp-browser-testing-playwright)
6. [Tree Permission Testing](#tree-permission-testing)
7. [Test Users & Scenarios](#test-users--scenarios)
8. [Testing Checklist](#testing-checklist)

---

## Testing Layers

EnterpriseRBAC testing follows a multi-layer approach:

```
┌─────────────────────────────────────────────────────┐
│  Layer 4: E2E Browser Tests (Playwright via MCP)   │
│  - Full user workflows                              │
│  - Tree permission verification                     │
│  - Entity context switching                         │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Layer 3: Frontend Integration (auth-ui)           │
│  - Login flows                                      │
│  - Entity CRUD operations                           │
│  - Role/permission management                       │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Layer 2: API Testing (curl/HTTP clients)          │
│  - Authentication endpoints                         │
│  - Entity hierarchy endpoints                       │
│  - Permission checking endpoints                    │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Layer 1: Database Verification                     │
│  - Entity structure                                 │
│  - Closure table integrity                          │
│  - Role/permission assignments                      │
└─────────────────────────────────────────────────────┘
```

---

## Database Reset & Seeding

### Quick Reset Script

**Location**: `examples/enterprise_rbac/reset_test_env.py`

**Usage**:
```bash
cd examples/enterprise_rbac
python reset_test_env.py
```

**What It Creates**:

| Resource | Count | Details |
|----------|-------|---------|
| **Permissions** | 29 | user:*, role:*, permission:*, entity:*, lead:* |
| **Entities** | 9 | 4-level hierarchy (org → region → office → team) |
| **Closure Records** | 25 | Pre-computed ancestor-descendant relationships |
| **Roles** | 6 | Platform Admin, Regional Manager, Office Manager, Team Lead, Agent, Viewer |
| **Users** | 6 | One per role with entity membership |
| **Leads** | 3 | Sample real estate leads |

**Execution Time**: ~2 seconds

**When to Run**:
- After breaking auth/permissions during development
- Before running integration tests
- Setting up a demo environment
- Debugging tree permission issues

### Entity Hierarchy Created

```
Diverse Platform (Organization)
├── West Coast (Region)
│   ├── Los Angeles (Office)
│   │   ├── Luxury Properties (Team)
│   │   └── Commercial LA (Team)
│   └── Seattle (Office)
└── East Coast (Region)
    ├── New York (Office)
    └── Boston (Office)
```

### Verifying Database State

**Quick verification script**:
```bash
cd examples/enterprise_rbac
MONGODB_URL="mongodb://localhost:27018" \
DATABASE_NAME="realestate_enterprise_rbac" \
python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from outlabs_auth.models.entity import EntityModel
from outlabs_auth.models.closure import EntityClosureModel

async def verify():
    client = AsyncIOMotorClient('mongodb://localhost:27018')
    await init_beanie(
        database=client['realestate_enterprise_rbac'],
        document_models=[EntityModel, EntityClosureModel]
    )
    
    print(f'Entities: {await EntityModel.count()}')
    print(f'Closure records: {await EntityClosureModel.count()}')
    print(f'Depth 0 (self): {await EntityClosureModel.find({\"depth\": 0}).count()}')
    print(f'Depth 1 (children): {await EntityClosureModel.find({\"depth\": 1}).count()}')
    print(f'Depth 2 (grandchildren): {await EntityClosureModel.find({\"depth\": 2}).count()}')
    print(f'Depth 3 (great-grandchildren): {await EntityClosureModel.find({\"depth\": 3}).count()}')
    
    client.close()

asyncio.run(verify())
"
```

**Expected output**:
```
Entities: 9
Closure records: 25
Depth 0 (self): 9
Depth 1 (children): 8
Depth 2 (grandchildren): 6
Depth 3 (great-grandchildren): 2
```

---

## API Testing

### Starting the Backend

```bash
cd examples/enterprise_rbac

# Start dependencies (MongoDB + Redis)
docker compose up -d

# Start backend API
MONGODB_URL="mongodb://localhost:27018" \
DATABASE_NAME="realestate_enterprise_rbac" \
SECRET_KEY="enterprise-rbac-secret-change-in-prod" \
REDIS_URL="redis://localhost:6380" \
uv run uvicorn main:app --port 8004 --reload
```

**Verify backend is running**:
```bash
curl http://localhost:8004/health
# Expected: {"status":"ok"}
```

### Authentication Flow

**1. Login and get access token**:
```bash
curl -X POST "http://localhost:8004/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@diverse.com",
    "password": "Admin123!!"
  }'
```

**Expected response**:
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**2. Store token for subsequent requests**:
```bash
export TOKEN="eyJhbGc..."
```

**3. Test authenticated endpoint**:
```bash
curl "http://localhost:8004/v1/users/me" \
  -H "Authorization: Bearer $TOKEN"
```

### Entity Hierarchy Endpoints

**Get all entities**:
```bash
curl "http://localhost:8004/v1/entities/" \
  -H "Authorization: Bearer $TOKEN"
```

**Get entity with descendants**:
```bash
# Get LA Office and all its descendant teams
curl "http://localhost:8004/v1/entities/{la_office_id}/descendants" \
  -H "Authorization: Bearer $TOKEN"
```

**Get entity with ancestors**:
```bash
# Get Luxury Properties Team and all its ancestors
curl "http://localhost:8004/v1/entities/{luxury_team_id}/ancestors" \
  -H "Authorization: Bearer $TOKEN"
```

### Permission Testing Endpoints

**Check user permission in entity context**:
```bash
curl "http://localhost:8004/v1/permissions/check" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "permission": "lead:read_tree",
    "entity_id": "{la_office_id}"
  }'
```

**Expected response**:
```json
{
  "allowed": true,
  "reason": "User has lead:read_tree permission in entity hierarchy"
}
```

---

## Frontend Integration Testing

### Starting the Admin UI

```bash
cd auth-ui
bun install
bun run dev
# Runs on http://localhost:3000
```

### Configuration

**Ensure `.env` is configured**:
```bash
# auth-ui/.env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8004
```

### Manual Testing Checklist

#### 1. Login Flow
- [ ] Open http://localhost:3000
- [ ] Login with `admin@diverse.com` / `Admin123!!`
- [ ] Verify JWT token stored in localStorage
- [ ] Verify user info displayed in UI

#### 2. Entity Management
- [ ] Navigate to Entities page
- [ ] Verify 9 entities displayed
- [ ] Verify hierarchy tree structure
- [ ] Create new entity
- [ ] Edit entity details
- [ ] Delete entity (verify cascade)

#### 3. User Management
- [ ] Navigate to Users page
- [ ] Verify 6 test users displayed
- [ ] View user detail page
- [ ] Check user's entity memberships
- [ ] Check user's roles and permissions

#### 4. Role Management
- [ ] Navigate to Roles page
- [ ] Verify 6 roles displayed
- [ ] View role permissions
- [ ] Create new role
- [ ] Assign permissions to role

#### 5. Entity Context Switching
- [ ] Switch current entity context
- [ ] Verify UI updates to show context-specific data
- [ ] Verify tree permissions apply correctly

---

## MCP Browser Testing (Playwright)

Claude Code can use the MCP Playwright integration for automated browser testing.

### Basic Workflow Test

```javascript
// Example: Test login flow
await mcp__playwright__browser_navigate({
  url: "http://localhost:3000"
});

await mcp__playwright__browser_snapshot();

// Fill login form
await mcp__playwright__browser_fill_form({
  fields: [
    {
      name: "Email",
      type: "textbox",
      ref: "input[type='email']",
      value: "admin@diverse.com"
    },
    {
      name: "Password",
      type: "textbox",
      ref: "input[type='password']",
      value: "Admin123!!"
    }
  ]
});

// Submit login
await mcp__playwright__browser_click({
  element: "Login button",
  ref: "button[type='submit']"
});

// Wait for redirect
await mcp__playwright__browser_wait_for({
  text: "Dashboard"
});

// Take screenshot
await mcp__playwright__browser_take_screenshot({
  filename: "dashboard-after-login.png"
});
```

### Tree Permission Test Scenarios

**Scenario 1: Regional Manager sees all descendant leads**

```javascript
// Login as West Coast Regional Manager
await loginAs("west.manager@diverse.com", "Test123!!");

// Navigate to Leads
await navigateToLeads();

// Verify Regional Manager sees:
// - LA Office leads (luxury + commercial)
// - Seattle Office leads
// But NOT East Coast leads
```

**Scenario 2: Team Lead sees only team leads**

```javascript
// Login as Luxury Team Lead
await loginAs("luxury.lead@diverse.com", "Test123!!");

// Navigate to Leads
await navigateToLeads();

// Verify Team Lead sees:
// - Only Luxury Properties team leads
// NOT Commercial LA leads
```

**Scenario 3: Platform Admin sees everything**

```javascript
// Login as Platform Admin
await loginAs("admin@diverse.com", "Admin123!!");

// Navigate to Leads
await navigateToLeads();

// Verify Platform Admin sees:
// - All leads across all teams
```

---

## Tree Permission Testing

### Understanding Tree Permissions

Tree permissions (`resource:action_tree`) grant access to:
1. The entity where permission is granted
2. All descendant entities in the hierarchy

**Example**:
- User has `lead:read_tree` on **LA Office**
- User can read leads from:
  - LA Office itself
  - Luxury Properties Team (descendant)
  - Commercial LA Team (descendant)
- User CANNOT read leads from:
  - Seattle Office (sibling)
  - West Coast Region (ancestor)

### Testing Tree Permission Scenarios

#### Scenario 1: Office Manager with Tree Permissions

**Setup**:
- User: `la.manager@diverse.com` (Office Manager role)
- Entity: Los Angeles Office
- Permission: `lead:read_tree`

**Expected Behavior**:
```bash
# Can read leads from LA Office
✅ GET /v1/leads?entity_id={la_office_id}

# Can read leads from Luxury Team (descendant)
✅ GET /v1/leads?entity_id={luxury_team_id}

# Can read leads from Commercial Team (descendant)
✅ GET /v1/leads?entity_id={commercial_team_id}

# CANNOT read leads from Seattle Office (sibling)
❌ GET /v1/leads?entity_id={seattle_office_id}
```

#### Scenario 2: Team Lead with Non-Tree Permissions

**Setup**:
- User: `luxury.lead@diverse.com` (Team Lead role)
- Entity: Luxury Properties Team
- Permission: `lead:read` (NOT `lead:read_tree`)

**Expected Behavior**:
```bash
# Can read leads from own team
✅ GET /v1/leads?entity_id={luxury_team_id}

# CANNOT read leads from parent office
❌ GET /v1/leads?entity_id={la_office_id}

# CANNOT read leads from sibling team
❌ GET /v1/leads?entity_id={commercial_team_id}
```

---

## Test Users & Scenarios

### Test User Matrix

| User | Email | Role | Entity | Tree Permissions | Use Cases |
|------|-------|------|--------|------------------|-----------|
| **Platform Admin** | `admin@diverse.com` | Platform Admin | Diverse Platform | All resources | Full system access testing |
| **Regional Manager** | `west.manager@diverse.com` | Regional Manager | West Coast | `lead:read_tree`, `entity:read_tree` | Multi-office management testing |
| **Office Manager** | `la.manager@diverse.com` | Office Manager | Los Angeles | `lead:*_tree`, `user:read_tree` | Office-level permissions testing |
| **Team Lead** | `luxury.lead@diverse.com` | Team Lead | Luxury Properties | `lead:*`, `user:read` | Team-level management testing |
| **Luxury Agent** | `agent.luxury@diverse.com` | Agent | Luxury Properties | `lead:read/create/update` | Basic agent operations |
| **Commercial Agent** | `agent.commercial@diverse.com` | Agent | Commercial LA | `lead:read/create/update` | Entity isolation testing |

### Testing Scenarios

#### Scenario 1: Regional Manager Visibility

**Login**: `west.manager@diverse.com` / `Test123!!`

**Expected Visibility**:
- ✅ See LA Office entities
- ✅ See Seattle Office entities
- ✅ See all West Coast leads
- ❌ Cannot see East Coast entities
- ❌ Cannot see East Coast leads

#### Scenario 2: Cross-Team Isolation

**Login**: `agent.luxury@diverse.com` / `Test123!!`

**Expected Behavior**:
- ✅ See only Luxury Properties leads
- ❌ Cannot see Commercial LA leads
- ❌ Cannot create entities
- ❌ Cannot manage users

#### Scenario 3: Office Manager Hierarchy

**Login**: `la.manager@diverse.com` / `Test123!!`

**Expected Behavior**:
- ✅ See LA Office + both teams
- ✅ Manage leads across both teams (`lead:*_tree`)
- ✅ View users across both teams (`user:read_tree`)
- ❌ Cannot manage users in parent entities
- ❌ Cannot see Seattle Office

---

## Testing Checklist

### Phase 1: Database Setup
- [x] Reset script executes without errors
- [x] 9 entities created in correct hierarchy
- [x] 25 closure records created (correct depth distribution)
- [x] 29 permissions created
- [x] 6 roles created with correct permissions
- [x] 6 users created with entity memberships
- [x] 3 sample leads created

### Phase 2: Backend API
- [ ] Health endpoint responds
- [ ] Login endpoint works for all test users
- [ ] JWT tokens are valid and contain correct claims
- [ ] `/v1/entities/` returns all entities
- [ ] Entity descendants endpoint works
- [ ] Entity ancestors endpoint works
- [ ] Permission check endpoint works
- [ ] Tree permission logic verified

### Phase 3: Frontend Integration
- [ ] Login flow works
- [ ] User info displayed correctly
- [ ] Entity list displays hierarchy
- [ ] Entity CRUD operations work
- [ ] User management UI works
- [ ] Role management UI works
- [ ] Entity context switching works

### Phase 4: Tree Permissions
- [ ] Platform Admin sees all entities
- [ ] Regional Manager sees only West Coast entities
- [ ] Office Manager sees only LA Office + teams
- [ ] Team Lead sees only own team
- [ ] Cross-team isolation verified
- [ ] Tree permission inheritance verified

### Phase 5: E2E Workflows
- [ ] User login → view leads → filter by entity
- [ ] Create new lead → assign to team → verify visibility
- [ ] Switch entity context → verify data updates
- [ ] Manager views descendant team leads
- [ ] Agent cannot access sibling team data

---

## Troubleshooting

### Common Issues

**Issue**: "Cannot connect to MongoDB"
```bash
# Check MongoDB is running
docker ps | grep mongo

# If not running, start it
docker start outlabs-mongodb
```

**Issue**: "Authentication failed"
```bash
# Reset database and try again
cd examples/enterprise_rbac
python reset_test_env.py
```

**Issue**: "Closure table empty"
```bash
# Verify closure records
MONGODB_URL="mongodb://localhost:27018" \
DATABASE_NAME="realestate_enterprise_rbac" \
python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    client = AsyncIOMotorClient('mongodb://localhost:27018')
    db = client['realestate_enterprise_rbac']
    count = await db.entity_closure.count_documents({})
    print(f'Closure records: {count}')
    client.close()

asyncio.run(check())
"
```

**Issue**: "Tree permissions not working"
```bash
# Verify role permissions include _tree suffix
curl "http://localhost:8004/v1/roles/" -H "Authorization: Bearer $TOKEN" | jq '.[].permissions'
```

---

## Next Steps

1. ✅ Database reset script complete
2. ✅ Entity hierarchy verified
3. ✅ Closure table validated
4. ⏳ Backend API implementation (Phase 1 of ENTERPRISE_RBAC_PROJECT.md)
5. ⏳ Frontend integration testing
6. ⏳ MCP Playwright E2E tests

---

**Last Updated**: 2025-01-10  
**Version**: 1.0
