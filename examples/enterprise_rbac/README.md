# EnterpriseRBAC Example - Real Estate Leads Platform

This example demonstrates OutlabsAuth's **EnterpriseRBAC** preset with real-world complexity through a multi-tenant real estate leads platform.

## 🎯 What This Demonstrates

### Entity Flexibility
- **No hardcoded entity types** - Organizations define their own structure
- **RE/MAX** uses: `corporate → state → region → brokerage → team`
- **Keller Williams** uses: `company → market_center → division`
- **Solo agents** use: `workspace` only
- **Entity type suggestions** prevent naming inconsistencies within organizations

### Tree Permissions
- Franchise executives see ALL leads across entire hierarchy
- Regional managers see leads in their region and below
- Brokers see only their brokerage's leads
- Agents see only their team's leads

### 5 Real-World Scenarios
1. **RE/MAX National** - Full 5-level franchise hierarchy
2. **RE/MAX Regional** - 3 brokerages under one account (subset of franchise)
3. **Keller Williams** - Independent brokerage with different terminology
4. **Solo Agent with Team** - Minimal 2-level hierarchy
5. **Solo Agent Only** - Flattest structure (single workspace)

### Internal Teams
- Support team with read-only global access
- Finance team for billing visibility
- Leadership with full system access

## 📋 Features

- ✅ Entity hierarchy with flexible naming
- ✅ Tree permissions (`lead:read_tree`, `lead:update_tree`)
- ✅ Entity type suggestions API
- ✅ Granular permissions (buyer vs seller specialists)
- ✅ Multiple organizational structures
- ✅ Internal teams with global access
- ✅ Lead management (CRUD operations)
- ✅ Lead assignment workflow
- ✅ Status pipeline tracking

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

The easiest way to run the example is with Docker Compose:

```bash
# Navigate to example directory
cd examples/enterprise_rbac

# Start the API (builds automatically)
docker compose up -d

# View logs
docker compose logs -f

# Stop the API
docker compose down
```

The API will be available at `http://localhost:8002` with auto-reload enabled.

**Requirements:**
- Docker Desktop running
- MongoDB running locally (port 27017)
- Redis running locally (port 6379) - optional

The Docker setup connects to your existing MongoDB and Redis instances on the host machine.

### Option 2: Local Development

```bash
# Navigate to example directory
cd examples/enterprise_rbac

# Install dependencies (from root)
cd ../..
uv sync

# Start the API
cd examples/enterprise_rbac
uv run uvicorn main:app --reload --port 8002
```

### Prerequisites (Local Development Only)

```bash
# MongoDB required
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Optional: Redis for caching
docker run -d -p 6379:6379 --name redis redis:latest
```

### Seed Demo Data

```bash
# Create all 5 scenarios with demo users and leads
python seed_data.py
```

This creates:
- **13 roles** (agent, team_lead, broker_owner, etc.)
- **18 users** across all scenarios
- **38+ entities** in various organizational structures
- **11 sample leads** demonstrating different types

### Explore the API

Visit the interactive documentation:
- **Swagger UI**: http://localhost:8002/docs
- **Health Check**: http://localhost:8002/

## 🔐 Demo Credentials

### Scenario 1: RE/MAX National (5-level hierarchy)

```
Franchise Executive:  exec@remax.com          / password123
Broker/Owner:         broker@remax-sv.com     / password123
Team Lead:            downtown@remax-sv.com   / password123
Agent:                agent1@remax-sv.com     / password123
```

**Test Tree Permissions:**
- Login as `exec@remax.com` → Can see ALL leads across entire franchise
- Login as `broker@remax-sv.com` → Can see only Silicon Valley brokerage leads
- Login as `agent1@remax-sv.com` → Can see only Downtown Team leads

### Scenario 2: RE/MAX Regional (3 brokerages)

```
Regional Manager:     manager@remax-eastbay.com / password123
Oakland Agent:        agent@remax-oakland.com   / password123
Berkeley Agent:       agent@remax-berkeley.com  / password123
```

### Scenario 3: Keller Williams (Different naming)

```
Market Center Leader: leader@kw-paloalto.com  / password123
Luxury Agent:         luxury@kw-paloalto.com  / password123
FTB Agent:            ftb@kw-paloalto.com     / password123
```

### Scenario 4: Solo Agent with Team

```
Solo Agent:           jane@janesrealestate.com / password123
Assistant:            assistant@janesrealestate.com / password123
```

### Scenario 5: Solo Agent Only

```
Solo Agent:           mike@mikesproperties.com / password123
```

### Internal Teams (Global Access)

```
Support:              support@outlabs.com     / password123
Finance:              finance@outlabs.com     / password123
System Admin:         ceo@outlabs.com         / password123
```

## 📚 API Endpoints

### Standard OutlabsAuth Routes

All implementations include these standardized routes:

#### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login with email/password
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user info

#### Entity Management ⭐
- `GET /api/entities` - List entities
- `POST /api/entities` - Create entity
- `GET /api/entities/suggestions` - **Get entity type suggestions** ⭐
- `GET /api/entities/{entity_id}` - Get entity details
- `GET /api/entities/{entity_id}/children` - Get child entities
- `GET /api/entities/{entity_id}/descendants` - Get descendant tree
- `PUT /api/entities/{entity_id}` - Update entity
- `DELETE /api/entities/{entity_id}` - Delete entity

#### User, Role, Membership, Permission Management
- Full CRUD for users, roles, memberships
- Membership lifecycle controls:
  - add entity memberships with scoped roles
  - suspend one entity membership without suspending the whole account
  - apply membership validity windows (`valid_from`, `valid_until`)
  - remove one entity membership with audit-preserving soft revoke
- Permission checking endpoints
- See Swagger UI for complete list

### Domain-Specific Routes (Lead Management)

- `POST /api/leads` - Create new lead
- `GET /api/leads` - List leads (filtered by permissions)
- `GET /api/leads/{lead_id}` - Get lead details
- `PUT /api/leads/{lead_id}` - Update lead
- `DELETE /api/leads/{lead_id}` - Delete lead
- `POST /api/leads/{lead_id}/assign` - Assign lead to agent
- `POST /api/leads/{lead_id}/notes` - Add note to lead

## 🧪 Test Scenarios

### 1. Test Entity Type Suggestions

```bash
# Get suggestions for entities under RE/MAX California
curl -X GET "http://localhost:8002/entities/suggestions?parent_id={remax_ca_id}" \
  -H "Authorization: Bearer {TOKEN}"
```

**Expected**: Shows "region" as existing type with count and examples

**Why It Matters**: Prevents creating "reigon" (typo) or "area" instead of consistent "region"

### 2. Test Tree Permissions

**Franchise executive sees ALL leads:**

```bash
# Login as exec@remax.com
# GET /api/leads
```

**Expected**: Sees leads from all teams in entire franchise

**Agent sees only their team:**

```bash
# Login as agent1@remax-sv.com
# GET /api/leads
```

**Expected**: Sees only Downtown Team leads

### 3. Test Entity Hierarchy Differences

Compare RE/MAX vs Keller Williams entity structures via `/api/entities/{id}/children`

**Key Insight**: Different organizations use different terminology, but the system handles it seamlessly

### 4. Test Internal Team Global Access

```bash
# Login as support@outlabs.com
# GET /api/leads
```

**Expected**: Sees ALL leads from all clients (RE/MAX, Keller Williams, solo agents)

## 🏗️ Architecture

### Entity Structure Examples

#### RE/MAX National (5 levels)
```
RE/MAX Corporate (STRUCTURAL)
└── RE/MAX California (STRUCTURAL)
    └── RE/MAX Bay Area (STRUCTURAL)
        └── RE/MAX Silicon Valley (STRUCTURAL)
            └── Downtown Team (ACCESS_GROUP) ← Leads stored here
```

#### Keller Williams (Different naming)
```
Keller Williams Realty (STRUCTURAL)
└── Palo Alto Market Center (STRUCTURAL) ← Different term!
    └── Luxury Division (ACCESS_GROUP) ← Different term!
```

#### Solo Agent (Flattest)
```
Mike's Properties (ACCESS_GROUP) ← Single entity, leads stored here
```

### Entity Classifications

**STRUCTURAL** - Organizational containers:
- Cannot have leads directly
- Used for hierarchical organization
- Examples: corporate, state, brokerage, market_center

**ACCESS_GROUP** - Work locations:
- Where leads are created and stored
- Where users actually work
- Examples: team, division, workspace

### Permission Model

#### Basic Lead Permissions
- `lead:read` - Read leads in user's entities
- `lead:create` - Create new leads
- `lead:update` - Update leads
- `lead:delete` - Delete leads
- `lead:assign` - Assign leads to agents

#### Tree Permissions (Hierarchical)
- `lead:read_tree` - Read leads in entire subtree
- `lead:update_tree` - Update leads in entire subtree
- `lead:delete_tree` - Delete leads in entire subtree

**Example**: Broker with `lead:read_tree` at brokerage level sees ALL team leads below

#### Granular Permissions (Specialist Roles)
- `lead:update_buyers` - Can only update buyer leads
- `lead:update_sellers` - Can only update seller leads

#### Internal Team Permissions (Global)
- `support:read_leads` - Read ALL leads across ALL clients
- `finance:read_all` - Read-only global access

## 🔗 Connect Admin UI

The universal Nuxt admin UI can connect to this example:

```bash
# In auth-ui directory
cd ../../auth-ui

# The .env is already configured to point to port 8002

# Start Nuxt dev server
bun dev
```

Visit `http://localhost:3000` and login with any demo credentials.

The UI will automatically:
- Detect EnterpriseRBAC features
- Show entity hierarchy management
- Display entity type suggestions
- Adapt based on system capabilities

## 📖 Key Concepts

### 1. Entity Type Flexibility

Entity types are **just strings** - not hardcoded. This allows each organization to use their own terminology.

**Problem**: Without guidance → inconsistent names like "brokerage", "broker", "office", "borkerage" (typo)

**Solution**: Entity Type Suggestions API returns existing types at that level

### 2. Tree Permissions

Permissions with `_tree` suffix apply to entire subtree:
- Agent: `lead:read` → Only their team
- Broker: `lead:read_tree` → Entire brokerage tree

### 3. Multiple Organizational Models

The same system handles:
- Deep hierarchies (5+ levels)
- Flat structures (1 entity)
- Different naming conventions
- Hybrid models

## 🛠️ Development

### Environment Variables

```bash
# MongoDB connection
MONGODB_URL=mongodb://localhost:27017

# Database name
DATABASE_NAME=realestate_leads_platform

# JWT secret (CHANGE IN PRODUCTION!)
SECRET_KEY=your-secret-key-change-in-production-please

# Optional: Redis for caching
REDIS_URL=redis://localhost:6379
```

### Adding New Scenarios

1. Create function in `seed_data.py`
2. Add entities with `create_entity()`
3. Create users and memberships
4. Create sample leads
5. Call from `seed_all()`

## 🐛 Troubleshooting

### MongoDB Connection Failed
```bash
docker ps | grep mongodb
docker start mongodb
```

### "Entity not found" errors
```bash
python seed_data.py  # Re-seed
```

### Permission denied
- Check user has correct role
- Verify entity membership
- Check tree permissions for child entities

## 📝 Next Steps

1. Test all scenarios in Swagger UI
2. Connect the admin UI
3. Try entity suggestions
4. Test tree permissions with different roles
5. Explore the API

## 📄 Related Documentation

- **REQUIREMENTS.md** - Detailed use case analysis
- **PROGRESS.md** - Implementation progress
- **IMPLEMENTATION_PLAN.md** (root) - Project vision

---

**Built with OutlabsAuth EnterpriseRBAC** 🚀
