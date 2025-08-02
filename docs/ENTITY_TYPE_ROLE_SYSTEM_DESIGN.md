# Context-Aware Role System Design

## Executive Summary

This document outlines a minimal enhancement to the OutlabsAuth role system that solves the fundamental problem of role rigidity. By adding a single field to the existing RoleModel, we enable roles to have different permissions based on WHERE they are assigned, matching how real organizations actually operate.

## The Core Problem

### Roles Don't Understand Context

In real organizations, the same role title means different things at different levels:
- A "Regional Manager" has full control in their region but limited access elsewhere
- A "Medical Director" has hospital-wide authority at their facility but advisory permissions when consulting at other hospitals
- A "Tech Lead" has deployment rights for their product but only review rights when helping other teams

**Current System**: One role = one fixed set of permissions everywhere

**Reality**: Authority changes based on context

### This Causes Role Explosion

Without context awareness, organizations must create multiple versions of the same role:
```
regional_manager_for_region    (full permissions)
regional_manager_for_office    (medium permissions)  
regional_manager_for_team      (limited permissions)
regional_manager_advisory      (view-only permissions)
```

**Result**: 500 entities × 5 role types × 3 permission levels = 7,500 roles!

## The Solution: Context-Aware Permissions

### Simple Enhancement to Existing System

We add ONE field to the existing RoleModel:

```python
class RoleModel(BaseDocument):
    # All existing fields remain unchanged
    name: str
    display_name: str
    permissions: List[str]  # Default permissions (backward compatible)
    entity: Link[EntityModel]
    assignable_at_types: List[str]
    
    # NEW FIELD: Context-aware permissions
    entity_type_permissions: Optional[Dict[str, List[str]]] = Field(default_factory=dict)
```

This allows one role to adapt based on where it's assigned.

### Understanding the Dual Purpose of `permissions` Field

The `permissions` field serves TWO important purposes:

#### 1. Backward Compatibility
Existing roles continue to work without any modifications:
```python
# Existing roles work perfectly without changes
existing_role = RoleModel(
    name="viewer",
    permissions=["entity:read", "user:read"],
    # No entity_type_permissions needed - works as before
)
```

#### 2. Default/Fallback Permissions
More importantly, it provides default permissions when:
- The role is assigned at an entity type not defined in `entity_type_permissions`
- You want consistent base permissions regardless of context
- The role doesn't need context awareness at all

```python
consultant_role = RoleModel(
    name="consultant",
    permissions=["entity:read", "report:view"],  # Fallback/default
    entity_type_permissions={
        "organization": ["entity:read", "entity:update", "report:generate"],
        "branch": ["entity:read", "task:view"]
        # Note: No entries for "team" or "project"
    },
    assignable_at_types=["organization", "branch", "team", "project"]
)

# When assigned at "team" or "project": Gets default permissions
# When assigned at "organization": Gets enhanced permissions
```

### How Permission Resolution Works

When a role is assigned to a user at an entity, the system:

1. Checks the entity's type (e.g., "organization", "branch", "team")
2. Looks for type-specific permissions in `entity_type_permissions`
3. Falls back to `permissions` field if:
   - No `entity_type_permissions` defined (backward compatibility)
   - Entity type not found in `entity_type_permissions` (default behavior)

```python
# Permission resolution logic
def get_role_permissions(role: RoleModel, entity: EntityModel) -> List[str]:
    # Check for entity-type specific permissions first
    if role.entity_type_permissions and entity.entity_type in role.entity_type_permissions:
        return role.entity_type_permissions[entity.entity_type]
    
    # Fall back to default permissions
    return role.permissions
```

### Practical Example: Diverse Platform Auditor Role

```python
# Compliance auditor needs different access at different levels
# BUT should have basic audit rights everywhere
compliance_auditor = RoleModel(
    name="compliance_auditor",
    display_name="Compliance Auditor",
    
    # Default permissions - ALWAYS has these as minimum
    permissions=[
        "entity:read", 
        "audit:basic", 
        "compliance:view_reports"
    ],
    
    # Enhanced permissions at specific levels
    entity_type_permissions={
        "organization": [
            "entity:read_tree", "user:read_tree",
            "audit:full", "audit:schedule",
            "compliance:generate_reports", "compliance:enforce",
            "violation:create", "violation:escalate"
        ],
        "branch": [
            "entity:read_tree", "user:read",
            "audit:standard", "compliance:view_reports",
            "violation:report"
        ]
        # Note: No specific permissions for "team" or "agent_team"
    },
    
    # Can be assigned anywhere
    assignable_at_types=["organization", "branch", "team", "agent_team"]
)

# Results:
# - At Organization: Full audit powers
# - At Branch: Standard audit capabilities
# - At Team/Agent_team: Falls back to basic read-only audit rights
```

This design ensures the auditor can always perform basic compliance checks (the default permissions) while getting enhanced capabilities at higher organizational levels.

## Real-World Examples from Our Platform Scenarios

### Example 1: Diverse - Real Estate Lead Generation Platform

**The Challenge**: In the Diverse platform, we have complex hierarchies where managers need different permissions at different organizational levels.

#### Platform Structure
```
Diverse Platform
├── National Brokerage A (Organization)
│   ├── Florida Division (Branch)
│   │   ├── Miami Team (Team)
│   │   │   ├── Agent Smith (Individual Agent Entity)
│   │   │   └── Top Performers Group (Access Group)
│   │   └── Orlando Team (Team)
│   └── Texas Division (Branch)
└── Individual Agents (Direct Platform Members)
```

#### Branch Manager Role - Context-Aware Permissions
```python
branch_manager_role = RoleModel(
    name="branch_manager",
    display_name="Branch Manager",
    entity=diverse_platform,  # Owned at platform level
    assignable_at_types=["organization", "branch", "team", "agent_team"],
    
    # Default permissions (fallback)
    permissions=["entity:read", "user:read", "lead:view"],
    
    # Context-aware permissions
    entity_type_permissions={
        "organization": [
            # Corporate oversight role
            "entity:read_tree", "entity:create_tree", "entity:update_tree",
            "user:read_tree", "user:create_tree", "user:update_tree",
            "branch:create", "branch:manage_all",
            "report:view_organizational", "budget:approve",
            "policy:create", "commission:set_structure"
        ],
        "branch": [
            # Full branch management
            "entity:manage", "entity:manage_tree",
            "user:manage", "user:manage_tree",
            "team:create", "team:manage_all",
            "lead:distribute", "lead:reassign",
            "report:generate_branch", "commission:override",
            "agent:recruit", "agent:terminate"
        ],
        "team": [
            # Advisory/support role at team level
            "entity:read", "entity:update",
            "user:read", "user:view_performance",
            "lead:view_assigned", "report:view_team",
            "agent:mentor", "best_practice:share"
        ],
        "agent_team": [
            # Minimal oversight for individual agent teams
            "entity:read", "user:read",
            "report:view_basic", "compliance:audit"
        ]
    }
)
```

**Use Case**: Maria Rodriguez is Branch Manager for:
- **National Brokerage A** (organization level): Strategic oversight, can create branches
- **Florida Division** (branch level): Full operational control, manages all teams
- **Miami Team** (team level): Advisory role, mentors agents
- **Agent Smith's Team** (agent_team level): Compliance oversight only

One role, four contexts, appropriate permissions at each level!

#### Supporting Individual Agents and Teams in Diverse

The Diverse platform has a unique challenge - supporting both:
1. **Individual agents** working directly under platform/organization
2. **Primary agents** who build their own teams

```python
# The Agent role adapts to support both paths
agent_role = RoleModel(
    name="agent",
    display_name="Real Estate Agent",
    entity=diverse_platform,
    assignable_at_types=["platform", "organization", "branch", "team", "agent_team"],
    
    entity_type_permissions={
        "platform": [
            # Solo agent - full autonomy
            "lead:receive", "lead:work", "lead:update_status",
            "entity:create",  # Can create their own team!
            "commission:view_own", "report:view_own"
        ],
        "organization": [
            # Agent under brokerage but not in a team
            "lead:receive", "lead:work", "lead:update_status",
            "brokerage:access_tools", "training:access",
            "entity:create",  # Can still create their own team
            "commission:view_own"
        ],
        "agent_team": [
            # Primary agent (owns the team)
            "lead:receive", "lead:distribute", "lead:work",
            "team:invite_members", "team:manage_assignments",
            "entity:manage", "member:manage",
            "commission:set_splits", "report:view_team"
        ]
    }
)

# When an agent creates their team, they get the SAME role but in their new entity
# This automatically upgrades their permissions from solo agent to team leader!
```

#### Real Estate Agent Role - Adapts to Context
```python
agent_role = RoleModel(
    name="agent",
    display_name="Real Estate Agent",
    entity=diverse_platform,
    assignable_at_types=["platform", "organization", "branch", "team", "agent_team"],
    
    # Default permissions
    permissions=["lead:view", "client:contact"],
    
    # Context-aware permissions
    entity_type_permissions={
        "platform": [
            # Individual agent working directly under platform
            "lead:receive", "lead:work", "lead:update_status",
            "client:contact", "appointment:schedule",
            "commission:view_own", "report:view_own"
        ],
        "organization": [
            # Agent under large brokerage - gets brokerage tools
            "lead:receive", "lead:work", "lead:update_status",
            "client:contact", "appointment:schedule",
            "brokerage:access_tools", "training:access",
            "commission:view_own", "report:view_own"
        ],
        "branch": [
            # Similar to organization but with branch-specific resources
            "lead:receive", "lead:work", "lead:update_status",
            "client:contact", "branch:access_resources",
            "team:view_available", "report:view_own"
        ],
        "team": [
            # Team member - gets assigned leads
            "lead:work_assigned", "lead:update_status",
            "client:contact", "team:collaborate",
            "team:access_shared_resources", "report:view_own"
        ],
        "agent_team": [
            # Member of individual agent's team
            "lead:work_assigned", "lead:update_status",
            "client:contact", "team:collaborate",
            "primary_agent:report_to"
        ]
    }
)
```

### Example 2: qdarte - Multi-Sided Marketplace Platform

**The Challenge**: qdarte connects real estate developments with influencers. Users need different permissions based on which side of the marketplace they're on.

#### Platform Structure
```
qdarte Platform
├── Client Organizations (Structural)
│   ├── Sunset Developments (Organization)
│   │   ├── Marketing Team (Team)
│   │   └── Analytics Team (Team)
│   └── Vineyard Estates (Organization)
└── Influencer Network (Access Group)
    ├── Tier 1 Influencers (Access Group)
    └── Micro Influencers (Access Group)
```

#### Campaign Manager Role - Client vs Influencer Context
```python
campaign_manager_role = RoleModel(
    name="campaign_manager",
    display_name="Campaign Manager",
    entity=qdarte_platform,
    assignable_at_types=["platform", "organization", "team", "access_group"],
    
    entity_type_permissions={
        "organization": [
            # Client-side campaign manager
            "campaign:create", "campaign:edit", "campaign:launch",
            "budget:allocate", "influencer:invite", "influencer:negotiate",
            "content:approve", "analytics:view_client",
            "lead:track", "roi:calculate"
        ],
        "team": [
            # Marketing team member
            "campaign:view", "campaign:suggest_edits",
            "influencer:research", "content:review",
            "analytics:view_team", "report:generate"
        ],
        "access_group": [
            # Influencer-side permissions (when in influencer groups)
            "campaign:view_available", "campaign:apply",
            "content:create", "content:submit",
            "link:generate", "analytics:view_own",
            "commission:track", "payout:request"
        ]
    }
)
```

**Use Case**: Different users, same role, different contexts:
- **Sarah (Sunset Dev)**: Creates campaigns, manages budgets, approves content
- **Mike (Tier 1 Influencer)**: Views campaigns, creates content, tracks commissions
- Same "Campaign Manager" role adapts to their context!

### Example 3: The Referral Brokerage - Flexible Growth Platform

**The Challenge**: Agents start as individuals but may grow into team leaders. Their permissions need to evolve with their business.

#### Evolution Path
```
Referral Brokerage Platform
├── Individual Agents (start here)
└── Agent Teams (agents can create these)
    └── Smith Team
        ├── Senior Agents (Access Group)
        └── Junior Agents (Access Group)
```

#### Referral Agent Role - Grows with the User
```python
referral_agent_role = RoleModel(
    name="referral_agent",
    display_name="Referral Agent",
    entity=referral_platform,
    assignable_at_types=["platform", "team", "access_group"],
    
    entity_type_permissions={
        "platform": [
            # Solo agent permissions
            "referral:send", "referral:receive",
            "commission:view_own", "commission:negotiate",
            "profile:manage_own", "availability:set",
            "rating:view_received", "dispute:file"
        ],
        "team": [
            # Team leader permissions (when they create a team)
            "referral:send", "referral:receive", "referral:distribute",
            "team:invite_members", "team:remove_members",
            "commission:view_team", "commission:set_splits",
            "member:assign_referrals", "performance:track",
            "report:generate_team"
        ],
        "access_group": [
            # Team member permissions
            "referral:receive_assigned", "referral:work",
            "commission:view_own", "team:collaborate",
            "report:submit_to_lead"
        ]
    }
)
```

**Evolution Example**:
1. **John starts solo**: Gets platform-level permissions
2. **John creates team**: Same role now gives team management permissions
3. **John's team members**: Get appropriate team member permissions
4. **No new roles needed** - context handles everything!

### Example 4: uaya - Simple Flat Platform

**The Challenge**: Not all platforms need hierarchy, but roles should still be flexible for future growth.

#### Minimal Structure
```
uaya Platform
├── Platform Administrators (Access Group)
├── Professional Interpreters (Access Group)
└── General Users (no group needed)
```

#### Interpreter Role - Simple but Extensible
```python
interpreter_role = RoleModel(
    name="interpreter",
    display_name="Professional Interpreter",
    entity=uaya_platform,
    assignable_at_types=["platform", "access_group"],
    
    # Most users get these permissions
    permissions=[
        "reading:provide", "calendar:manage",
        "payment:receive", "profile:professional"
    ],
    
    # But we can extend for special groups
    entity_type_permissions={
        "platform": [
            # Standard interpreter
            "reading:provide", "calendar:manage",
            "payment:receive", "profile:professional",
            "client:communicate", "rating:receive"
        ],
        "access_group": [
            # Premium interpreter group - additional permissions
            "reading:provide", "reading:premium_types",
            "calendar:manage", "calendar:priority_booking",
            "payment:receive", "payment:premium_rates",
            "profile:professional", "profile:featured",
            "workshop:create", "content:publish"
        ]
    }
)
```

**Future-Proof**: Even simple platforms benefit from context awareness for growth

## Why This Approach?

### 1. **Matches Reality**
Look at our Diverse platform - in real estate, a Branch Manager's authority at the organization level (strategic planning) is vastly different from their role when mentoring a specific team. Our system should reflect this reality.

### 2. **Prevents Role Explosion**
Take the Diverse platform example:
- **Without context awareness**: National Brokerage A alone would need:
  - `branch_manager_corporate` (organization level)
  - `branch_manager_full` (branch level)  
  - `branch_manager_advisory` (team level)
  - `branch_manager_compliance` (agent_team level)
  - Multiply by 50+ branches = 200+ roles just for branch managers!
- **With context awareness**: Just ONE `branch_manager` role that adapts

### 3. **Simplifies Administration**
- Diverse platform: One "Branch Manager" role works across all 4 levels
- qdarte platform: Same "Campaign Manager" role for both clients and influencers
- Referral Brokerage: Agents keep the same role as they grow from solo to team lead
- No confusion about which variant to assign

### 4. **Improves Security**
- Branch managers at Diverse automatically get limited permissions at team level
- qdarte influencers can't access client-side analytics even with same role name
- Permissions scope appropriately without manual configuration
- Clear audit trail: "User X has role Y in context Z"

### 5. **Enables Business Evolution**
- **Referral Brokerage**: Agents start solo, create teams, no role changes needed
- **Diverse**: New individual agents can join at any level with appropriate permissions
- **qdarte**: Can add new entity types (e.g., "agency") without creating new roles
- **uaya**: Simple now but ready for future complexity

## Implementation Details

### Minimal Changes Required

1. **Add one field to RoleModel**
   ```python
   entity_type_permissions: Optional[Dict[str, List[str]]] = Field(default_factory=dict)
   ```

2. **Update permission resolution**
   ```python
   def get_effective_permissions(membership):
       role = membership.role
       entity = membership.entity
       
       # Use context-aware permissions if available
       if role.entity_type_permissions and entity.entity_type in role.entity_type_permissions:
           return role.entity_type_permissions[entity.entity_type]
       
       # Fall back to default permissions
       return role.permissions
   ```

3. **Backward compatible**
   - Existing roles continue to work with their default permissions
   - Can gradually migrate to context-aware permissions

### Custom Permissions Still Supported

Platforms can still create custom permissions:
- Use existing PermissionModel for business-specific permissions
- Examples: `lead:assign`, `patient:discharge`, `trade:execute`
- These work seamlessly with context-aware roles

### Access Groups Remain Simple

For access groups (committees, project teams), the existing `direct_permissions` field is perfect:
- Members get these permissions just by being in the group
- No complex role assignments needed
- Ideal for temporary or cross-functional access

## Migration Path

### For New Platforms
1. Define your entity types (organization, division, team, etc.)
2. Create context-aware roles from the start
3. Assign roles normally - permissions adjust automatically

### For Existing Platforms
1. Keep existing roles working as-is (backward compatible)
2. Gradually add `entity_type_permissions` to key roles
3. Simplify by consolidating duplicate roles into context-aware ones

## API Examples

### Creating a Context-Aware Role
```http
POST /v1/roles
{
  "name": "regional_manager",
  "display_name": "Regional Manager",
  "entity_id": "corporate_hq",
  "assignable_at_types": ["region", "office", "team"],
  "permissions": ["entity:read", "report:view"],  // Fallback permissions
  "entity_type_permissions": {
    "region": [
      "entity:manage_tree", "user:manage_tree",
      "budget:approve", "hire:authorize"
    ],
    "office": [
      "entity:read", "user:read",
      "report:generate", "schedule:view"
    ],
    "team": [
      "entity:read", "report:view"
    ]
  }
}
```

### Assigning the Role
```http
POST /v1/entities/{entity_id}/members
{
  "user_id": "user_123",
  "role_ids": ["role_regional_manager"]
}

// If entity is type "region" → User gets full regional permissions
// If entity is type "office" → User gets limited office permissions
// If entity is type "team" → User gets minimal team permissions
```

## Comparison with Alternatives

### Alternative 1: Create Multiple Roles
```
regional_manager_full
regional_manager_limited  
regional_manager_advisory
regional_manager_temp
```
**Problems**: Confusing, hard to maintain, role explosion

### Alternative 2: Use Permission Conditions
```
if (user.role == "manager" && entity.type == "region") {
  // Complex conditional logic everywhere
}
```
**Problems**: Logic scattered throughout codebase, hard to audit

### Alternative 3: Dynamic Permission Calculation
```
permissions = calculateBasedOnContext(user, entity, time, phase_of_moon)
```
**Problems**: Unpredictable, hard to debug, performance issues

### Our Solution: Context-Aware Roles
```
role.entity_type_permissions[entity.type]
```
**Benefits**: Simple, predictable, auditable, performant

## Summary

By adding a single field to our existing RoleModel, we solve the fundamental problem of role rigidity. This minimal change:

- Eliminates role explosion
- Matches how organizations actually work  
- Maintains backward compatibility
- Requires no new models or complex systems
- Leverages all existing infrastructure

The result is a system that's both powerful and simple - roles that understand context and adapt accordingly.