# Real Estate Leads Platform - Requirements & Use Cases

**Created**: 2025-01-23
**Purpose**: Demonstrate OutlabsAuth's entity flexibility through real-world complex scenarios
**Preset**: EnterpriseRBAC

---

## Table of Contents
1. [Project Vision](#project-vision)
2. [The Core Challenge](#the-core-challenge)
3. [Real-World Scenarios](#real-world-scenarios)
4. [Internal Team Structure](#internal-team-structure)
5. [Permission Model](#permission-model)
6. [Entity Type Flexibility](#entity-type-flexibility)
7. [Domain Model](#domain-model)
8. [Technical Implementation](#technical-implementation)

---

## Project Vision

Demonstrate how OutlabsAuth accommodates wildly different organizational structures in the real estate industry **without prescriptive hierarchy patterns or hardcoded entity types**.

### The Key Insight

Real estate businesses structure themselves in fundamentally different ways:
- **National franchises**: Complex 5-level hierarchies
- **Regional accounts**: Subset of franchise locations
- **Independent brokerages**: 2-3 level structures
- **Solo agents with teams**: Minimal hierarchy
- **Solo agents only**: Flat structure

**Our system must accommodate ALL of these patterns with the same codebase.**

### Goals

1. **Demonstrate flexibility**: Show 5 completely different client structures
2. **Maintain consistency**: Entity type suggestions prevent naming chaos
3. **Real-world complexity**: Tree permissions, granular roles, internal team access
4. **Production-ready**: This example mimics actual SaaS deployment patterns

---

## The Core Challenge: Organizational Variability

### Traditional Rigid Systems ❌

```
Franchise → Regional Office → Brokerage → Branch → Agent
```

**Problems**:
- Only works for franchises
- Doesn't work for independent brokerages
- Doesn't work for solo agents
- Forces artificial hierarchy on simple structures
- Can't adapt to different naming conventions

### Our Flexible System ✅

**Entity types are just strings. The system doesn't care what you call them.**

```python
# RE/MAX might use:
"franchise" → "state_office" → "brokerage" → "team"

# Keller Williams might use:
"market_center" → "team"

# Solo agent might use:
"agent_workspace"

# Independent brokerage might use:
"brokerage" → "office" → "team"
```

**Every client defines their own hierarchy and naming.**

---

## Real-World Scenarios

### Scenario 1: National Franchise (RE/MAX)

**Client**: RE/MAX Corporate
**Contract**: Nationwide account, all states

**Structure**:
```
RE/MAX National (structural: "franchise")
├── RE/MAX California (structural: "state_office")
│   ├── RE/MAX San Francisco (structural: "brokerage")
│   │   ├── Team Smith (access_group: "team")
│   │   │   ├── John Smith (team_lead)
│   │   │   ├── Junior Agent 1 (agent)
│   │   │   ├── Junior Agent 2 (buyer_specialist)
│   │   │   └── Assistant (view_only)
│   │   └── Solo Agent Jones (access_group: "agent_workspace")
│   │       └── Mike Jones (agent_owner)
│   └── RE/MAX Los Angeles (structural: "brokerage")
│       └── Team Anderson (access_group: "team")
└── RE/MAX Texas (structural: "state_office")
    └── RE/MAX Austin (structural: "brokerage")
```

**Key Features**:
- **5-level hierarchy**: franchise → state → brokerage → team → lead
- **Tree permissions**: Franchise exec sees ALL leads nationwide
- **Regional management**: State managers see their state only
- **Mixed structures**: Teams AND solo agents under same brokerage

**Roles & Permissions**:
```python
# Franchise Executive (at "RE/MAX National")
permissions = [
    "lead:read_tree",        # See ALL leads nationwide
    "analytics:view_tree",   # Analytics across all states
    "agent:read_tree"        # View all agents
]

# Regional Manager (at "RE/MAX California")
permissions = [
    "lead:read_tree",        # See all California leads
    "analytics:view_tree",   # California analytics
    "agent:manage_tree"      # Manage California agents
]

# Broker (at "RE/MAX San Francisco")
permissions = [
    "lead:read_tree",        # See all brokerage leads
    "agent:manage_tree",     # Manage brokerage agents
    "billing:view"           # View brokerage billing
]

# Team Lead (at "Team Smith")
permissions = [
    "lead:*",                # Full lead access in team
    "agent:manage",          # Manage team members (not tree)
    "lead:assign"            # Assign leads within team
]

# Agent (member of "Team Smith")
permissions = [
    "lead:read",             # View team leads
    "lead:update",           # Update lead status
    "lead:create"            # Create new leads
]

# Buyer Specialist (member of "Team Smith")
permissions = [
    "lead:read",             # View all leads
    "lead:update_buyers"     # Can ONLY update buyer leads
]

# Assistant (member of "Team Smith")
permissions = [
    "lead:read"              # View only, no updates
]

# Solo Agent Owner (at "Solo Agent Jones")
permissions = [
    "lead:*",                # Full control of own leads
    "agent:manage"           # Can add assistants
]
```

**Demonstrates**:
- Deep hierarchy (5 levels)
- Tree permissions flowing down
- Different roles at different levels
- Mixed team/solo structures
- Granular permissions (buyer specialist)

---

### Scenario 2: Regional Account (3 Brokerages)

**Client**: RE/MAX Regional Texas
**Contract**: Only 3 brokerages in Texas, not entire franchise

**Structure**:
```
RE/MAX Regional Texas (structural: "regional_account")
├── RE/MAX Austin (structural: "brokerage")
│   ├── Team Rodriguez (access_group: "team")
│   └── Team Garcia (access_group: "team")
├── RE/MAX Houston (structural: "brokerage")
│   └── Team Martinez (access_group: "team")
└── RE/MAX Dallas (structural: "brokerage")
    └── Solo Agent Chen (access_group: "agent_workspace")
```

**Key Differences from Scenario 1**:
- **Different root**: "regional_account" not "franchise"
- **No state level**: Goes directly to brokerages
- **Smaller scope**: 3 brokerages only
- **Same franchise, different account**: This is a separate client from Scenario 1

**Why This Matters**:
- Shows flexibility of root entity
- Different organizational scope
- Same franchise name, different structure
- Entity types reflect business reality ("regional_account" vs "franchise")

**Roles**:
```python
# Regional Director (at "RE/MAX Regional Texas")
permissions = [
    "lead:read_tree",        # See all 3 brokerages' leads
    "analytics:view_tree",   # Regional analytics
    "agent:manage_tree"      # Manage all agents in region
]

# Brokers (at each brokerage)
permissions = [
    "lead:read_tree",        # See brokerage leads
    "agent:manage_tree"      # Manage brokerage agents
]
```

**Demonstrates**:
- Flexible root entities
- Different organizational scopes
- Same system accommodates subset accounts

---

### Scenario 3: Independent Brokerage (Keller Williams)

**Client**: Keller Williams Bay Area Market Center
**Contract**: Single independent brokerage

**Structure**:
```
KW Bay Area Market Center (structural: "market_center")
├── Team Alpha (access_group: "team")
│   ├── Lead Agent (team_lead)
│   ├── Agent 1 (agent)
│   └── Agent 2 (agent)
├── Team Beta (access_group: "team")
└── Solo Agent Sarah Chen (access_group: "agent_workspace")
```

**Key Differences**:
- **Different naming**: "market_center" instead of "brokerage"
- **Flatter hierarchy**: Only 2 levels
- **No franchise/regional levels**: Independent operation
- **Different company**: Keller Williams, not RE/MAX

**Why "market_center"?**:
Keller Williams uses different terminology than RE/MAX. The system doesn't care—entity types are just strings.

**Demonstrates**:
- Naming flexibility (different companies use different terms)
- Flatter hierarchy (not everything needs 5 levels)
- Same permissions model works with different structures

---

### Scenario 4: Solo Agent with Team

**Client**: Sarah Chen Real Estate
**Contract**: Individual agent with small team

**Structure**:
```
Sarah Chen Real Estate (structural: "agent_workspace")
└── Chen Team (access_group: "team")
    ├── Sarah Chen (owner)
    ├── Junior Agent (buyer_specialist)
    │   └── Permissions: lead:read, lead:update_buyers
    └── Assistant (view_only)
        └── Permissions: lead:read
```

**Key Differences**:
- **Minimal hierarchy**: Just 2 levels
- **Different entity types**: "agent_workspace" not "brokerage"
- **Individual ownership**: One person owns the whole structure
- **Specific role assignments**: Buyer specialist can't touch seller leads

**Roles**:
```python
# Owner (Sarah Chen)
permissions = [
    "lead:*",                # Full lead control
    "agent:manage"           # Can add/remove team members
]

# Buyer Specialist
permissions = [
    "lead:read",             # View all leads
    "lead:update_buyers"     # Update ONLY buyer leads
]

# Assistant
permissions = [
    "lead:read"              # View only
]
```

**Demonstrates**:
- Minimal viable hierarchy
- Granular permissions (buyer vs seller)
- Individual entrepreneur pattern
- Team member specialization

---

### Scenario 5: Solo Agent Only

**Client**: Mike Jones - Independent Agent
**Contract**: Single agent, no team

**Structure**:
```
Mike Jones Real Estate (access_group: "agent_workspace")
├── Mike Jones (owner)
├── Assistant 1 (view_only)
└── Assistant 2 (buyers_only)
```

**Key Differences**:
- **Flattest structure**: Single entity
- **No sub-teams**: All members directly in workspace
- **Different assistance levels**: One view-only, one can update buyers
- **ACCESS_GROUP as root**: No structural parent needed

**Roles**:
```python
# Owner (Mike Jones)
permissions = [
    "lead:*",                # Full control
    "agent:manage"           # Can add assistants
]

# Assistant 1 (view_only)
permissions = [
    "lead:read"              # View only
]

# Assistant 2 (buyers_only)
permissions = [
    "lead:read",             # View leads
    "lead:update_buyers"     # Update only buyer leads
]
```

**Demonstrates**:
- Absolute minimal structure
- ACCESS_GROUP as root (no structural parent required)
- Per-assistant permission differences
- Simplest possible deployment

---

## Comparison Matrix

| Aspect | Scenario 1 | Scenario 2 | Scenario 3 | Scenario 4 | Scenario 5 |
|--------|-----------|-----------|-----------|-----------|-----------|
| **Client** | RE/MAX National | RE/MAX Regional TX | KW Bay Area | Sarah Chen RE | Mike Jones RE |
| **Hierarchy Depth** | 5 levels | 3 levels | 2 levels | 2 levels | 1 level |
| **Root Entity Type** | "franchise" | "regional_account" | "market_center" | "agent_workspace" | "agent_workspace" |
| **Organizational Scope** | Nationwide | Regional | Single location | Small team | Individual |
| **Team Structure** | Teams + solo agents | Teams | Teams + solo | Single team | No team |
| **Tree Permissions** | Yes (executives) | Yes (regional dir) | Yes (broker) | No | No |
| **Naming Convention** | RE/MAX terms | RE/MAX terms | KW terms | Generic | Generic |
| **Complexity** | Very High | High | Medium | Low | Very Low |

---

## Internal Team Structure (Your Company)

Your company (the leads platform provider) needs its own access across all client accounts for support, billing, and management.

**Structure**:
```
Internal Teams (structural: "internal_org")
├── Customer Support (structural: "department")
│   ├── Phone Support (access_group: "team")
│   │   └── Support agents (support_agent role)
│   └── Technical Support (access_group: "team")
│       └── Tech specialists (tech_support role)
├── Finance (access_group: "department")
│   └── Finance staff (finance_admin role)
├── Marketing (access_group: "department")
│   └── Marketing team (marketing_analyst role)
├── Sales (access_group: "department")
│   └── Sales reps (sales_admin role)
└── Leadership (access_group: "department")
    └── Executives (executive role)
```

**Internal Roles**:
```python
# Phone Support Agent
permissions = [
    "lead:read",             # View any client's leads (global)
    "support:add_notes",     # Add support notes
    "client:view"            # View client account info
]

# Technical Support
permissions = [
    "lead:read",             # View leads
    "support:*",             # Full support actions
    "entity:read",           # View client structures
    "user:read"              # View user info for debugging
]

# Finance Admin
permissions = [
    "billing:*",             # Full billing access (global)
    "client:view",           # View all clients
    "analytics:billing"      # Billing analytics
]

# Marketing Analyst
permissions = [
    "analytics:view",        # View platform analytics (global)
    "campaign:manage"        # Manage marketing campaigns
]

# Sales Admin
permissions = [
    "client:*",              # Full client management
    "account:onboard",       # Onboard new clients
    "demo:create"            # Create demo accounts
]

# Executive
permissions = [
    "*:*"                    # Full platform access
]
```

**Key Points**:
- Internal team permissions are **global**, not entity-scoped
- Support can see any client's leads (for helping them)
- Finance can see all billing across clients
- Different levels of access within support (phone vs technical)
- Executives have full access for oversight

---

## Permission Model

### Lead Permissions

**Basic Permissions**:
```python
"lead:read"              # View lead details
"lead:create"            # Create new leads
"lead:update"            # Update lead status, notes, details
"lead:delete"            # Delete/archive leads
"lead:assign"            # Reassign leads to other agents
"lead:export"            # Export lead data
```

**Granular Permissions** (for specialists):
```python
"lead:update_buyers"     # Can ONLY update buyer leads
"lead:update_sellers"    # Can ONLY update seller leads
```

**Tree Permissions** (for managers):
```python
"lead:read_tree"         # View all descendant leads
"lead:update_tree"       # Update all descendant leads
"lead:assign_tree"       # Reassign across hierarchy
```

### Agent Management Permissions

```python
"agent:read"             # View agent information
"agent:manage"           # Add/remove agents in own entity
"agent:manage_tree"      # Manage agents across hierarchy
"agent:read_tree"        # View all descendant agents
```

### Analytics Permissions

```python
"analytics:view"         # View analytics for own entity
"analytics:view_tree"    # View analytics for entire hierarchy
"analytics:export"       # Export analytics data
```

### Billing Permissions (Internal)

```python
"billing:view"           # View billing information
"billing:manage"         # Create invoices, process payments
"billing:*"              # Full billing access (finance team)
```

### Support Permissions (Internal)

```python
"support:read_leads"     # Support can view client leads
"support:add_notes"      # Add support notes to leads
"support:*"              # Full support actions (tech support)
```

---

## Entity Type Flexibility

### The Problem Without Suggestions

```
RE/MAX California (creating new children)
├── brokerage_sf          ← lowercase
├── Brokerage_LA          ← mixed case
├── broker_san_diego      ← different word
├── SanJoseOffice         ← completely different
└── borkerage_sacramento  ← typo!
```

**Issues**:
- Inconsistent naming within same organization
- Hard to query/report ("brokerage" vs "broker" vs "office")
- Looks unprofessional
- Confusing for users

### The Solution: Entity Type Suggestions API

When creating entity under "RE/MAX California":

**API Request**:
```http
GET /api/entities/suggestions?parent_id=remax_california_id

Response:
{
  "suggestions": [
    {
      "entity_type": "brokerage",
      "count": 15,
      "examples": ["RE/MAX San Francisco", "RE/MAX Los Angeles", "RE/MAX San Diego"]
    },
    {
      "entity_type": "regional_office",
      "count": 2,
      "examples": ["North Region HQ", "South Region HQ"]
    }
  ],
  "parent_entity": {
    "id": "abc123",
    "name": "remax_california",
    "display_name": "RE/MAX California",
    "entity_type": "state_office"
  },
  "total_children": 17
}
```

**UI Presentation**:
```
Create Entity under "RE/MAX California"

Name: [_______________________]

What kind of entity is this?
○ brokerage (15 existing)
  Examples: RE/MAX San Francisco, RE/MAX Los Angeles, RE/MAX San Diego

○ regional_office (2 existing)
  Examples: North Region HQ, South Region HQ

○ Custom: [_____________]
```

**Benefits**:
- ✅ Maintains consistency (all use "brokerage")
- ✅ Prevents typos
- ✅ Shows what already exists
- ✅ Still allows custom types when truly different
- ✅ Scoped to parent (RE/MAX vs KW can use different names)

### Scoping: Per-Parent, Not Global

**Key**: Suggestions are scoped to **parent entity**, not entire system.

```
Platform
├── RE/MAX Organization
│   └── RE/MAX California
│       └── Suggestions: "brokerage" (15 times)
└── Keller Williams
    └── Suggestions: "market_center" (different term!)
```

Each organization maintains its own naming conventions.

---

## Domain Model

### Lead (Primary Resource)

```python
class Lead(Document):
    """
    A potential buyer or seller in the real estate pipeline.
    """

    # Ownership
    entity_id: str                    # Which entity owns this lead
    assigned_to: Optional[str] = None # Agent user_id

    # Lead Classification
    lead_type: Literal["buyer", "seller", "both"]

    # Contact Information
    first_name: str
    last_name: str
    email: str
    phone: str

    # Lead Details
    status: Literal["new", "contacted", "qualified", "showing", "closed", "dead"]
    source: str                       # Website, referral, ad, Zillow, etc.
    budget: Optional[int] = None      # Budget range
    location: Optional[str] = None    # Desired location
    property_type: Optional[str] = None  # House, condo, land, etc.
    timeline: Optional[str] = None    # Immediate, 3-6 months, etc.

    # Interaction History
    notes: List[str] = []
    last_contact: Optional[datetime] = None
    next_followup: Optional[datetime] = None

    # Metadata
    created_at: datetime
    updated_at: datetime
    created_by: str                   # User ID who created (agent or support)

    class Settings:
        name = "leads"
        indexes = [
            "entity_id",              # Fast lookups by entity
            "assigned_to",            # Agent's leads
            "status",                 # Filter by status
            "lead_type",              # Filter by type
            [("entity_id", 1), ("status", 1)],  # Compound
            "created_at"              # Time-based queries
        ]
```

### Lead Permissions Check

```python
# Check if user can update a specific lead
def can_update_lead(user, lead):
    # Get user's permissions in lead's entity
    perms = get_user_permissions(user.id, lead.entity_id)

    # Check general update permission
    if "lead:update" in perms:
        return True

    # Check type-specific permission
    if lead.lead_type == "buyer" and "lead:update_buyers" in perms:
        return True

    if lead.lead_type == "seller" and "lead:update_sellers" in perms:
        return True

    # Check tree permission (from ancestor entities)
    if "lead:update_tree" in perms:
        return True

    return False
```

---

## Technical Implementation

### Standard OutlabsAuth Routers

All standard routers included at `/api/*`:

```python
from outlabs_auth.routers import (
    get_auth_router,           # /api/auth
    get_users_router,          # /api/users
    get_roles_router,          # /api/roles
    get_entities_router,       # /api/entities (includes /suggestions)
    get_memberships_router,    # /api/memberships
    get_permissions_router,    # /api/permissions
    get_api_keys_router,       # /api/api-keys
    get_system_router,         # /api/system
)

app.include_router(get_auth_router(auth), prefix="/api/auth")
app.include_router(get_users_router(auth), prefix="/api/users")
# ... etc
```

### Domain-Specific Routes

Custom routes for lead management at `/api/leads`:

```python
# Lead CRUD
POST   /api/leads                    # Create lead
GET    /api/leads                    # List leads (filtered by permissions)
GET    /api/leads/{id}               # Get lead details
PUT    /api/leads/{id}               # Update lead
DELETE /api/leads/{id}               # Delete lead
POST   /api/leads/{id}/assign        # Assign to agent
POST   /api/leads/{id}/notes         # Add note

# Lead Filtering
GET    /api/leads?entity_id={id}     # Leads in specific entity
GET    /api/leads?status=new         # By status
GET    /api/leads?lead_type=buyer    # By type
GET    /api/leads?assigned_to={id}   # By agent
```

### Entity Type Suggestions (NEW)

```python
# Get suggestions for entity types
GET /api/entities/suggestions?parent_id={id}&entity_class=structural

# Returns:
{
  "suggestions": [...],
  "parent_entity": {...},
  "total_children": 17
}
```

### Permission Checking

```python
# Check if user has permission in entity context
POST /api/permissions/check
{
  "user_id": "user123",
  "permission": "lead:update",
  "entity_id": "entity456"
}

# Response:
{
  "allowed": true,
  "source": "direct",  # or "tree" if inherited
  "role": "team_lead"
}
```

---

## Testing Scenarios

### Test 1: Franchise Executive View
1. Login as franchise executive
2. Navigate to leads dashboard
3. Should see ALL leads across all states
4. Filter by state → Should show subset
5. Filter by brokerage → Should show smaller subset
6. Permission source: `lead:read_tree` from "RE/MAX National"

### Test 2: Broker Cannot See Other Brokerages
1. Login as RE/MAX San Francisco broker
2. Navigate to leads
3. Should see only SF brokerage leads
4. Try to view LA leads → Denied
5. Permission source: `lead:read_tree` from "RE/MAX San Francisco"

### Test 3: Buyer Specialist Cannot Update Sellers
1. Login as buyer specialist on Team Smith
2. View leads
3. Try to update buyer lead → Success
4. Try to update seller lead → Denied (403)
5. Permission check: Has `lead:update_buyers` but NOT `lead:update_sellers`

### Test 4: Entity Type Suggestions Work
1. Login as admin
2. Navigate to "RE/MAX California" entity
3. Click "Create Child Entity"
4. Modal shows suggestions: "brokerage" (15 existing)
5. Select "brokerage" → Pre-fills type field
6. Can still type custom if needed

### Test 5: Internal Support Sees All Leads
1. Login as phone support agent
2. Search for any client's leads → Can view
3. Permission source: `lead:read` (global, not entity-scoped)
4. Can add notes but not update status
5. Demonstrates internal team global access

---

## Success Criteria

✅ **All 5 client scenarios work**:
- National franchise (5 levels)
- Regional account (3 levels)
- Independent brokerage (2 levels)
- Solo with team (2 levels)
- Solo only (1 level)

✅ **Entity type suggestions maintain consistency**:
- Shows existing types at same level
- Counts occurrences
- Provides examples
- Allows custom when needed

✅ **Tree permissions work correctly**:
- Franchise exec sees all leads
- Broker sees brokerage leads only
- Team lead sees team leads only
- No permission leakage

✅ **Granular permissions work**:
- Buyer specialist can't touch seller leads
- View-only assistants can't update
- Permissions correctly scoped

✅ **Internal team has global access**:
- Support can view any client's leads
- Finance can see all billing
- Properly separated from client entities

✅ **Different naming conventions coexist**:
- RE/MAX uses "brokerage"
- KW uses "market_center"
- Both work in same system

---

## Future Enhancements

### Phase 2: Advanced Features
- **Lead routing rules**: Auto-assign based on location/type
- **Lead scoring**: ML-based lead quality scoring
- **Email integration**: Track email communications
- **Calendar integration**: Schedule showings

### Phase 3: Analytics
- **Conversion funnels**: Track lead → showing → closed
- **Agent performance**: Leads per agent, close rates
- **Brokerage dashboards**: Executive overview
- **Predictive analytics**: Forecast closings

### Phase 4: Client Portal
- **Custom dashboards**: Clients build their own views
- **White-label**: Rebrand for each franchise
- **Mobile app**: iOS/Android clients

---

**Last Updated**: 2025-01-23
**Status**: Requirements Complete - Ready for Implementation
**Next Step**: Implement `main.py` with all routes
