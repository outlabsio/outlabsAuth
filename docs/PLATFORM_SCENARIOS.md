# Platform Deployment Scenarios

This document outlines the four initial business platforms that outlabsAuth will support, demonstrating how the flexible entity system accommodates diverse organizational structures—from simple flat models to complex multi-level hierarchies.

## Overview of Platform Types

1. **Complex Hierarchical** - Diverse (multi-level real estate organizations)
2. **Flat Structure** - uaya (simple role-based platform)
3. **Multi-Sided Marketplace** - qdarte (separate client and influencer portals)
4. **Hybrid Optional Hierarchy** - The Referral Brokerage (individual agents with optional teams)

## Platform 1: Diverse (Lead Generation Platform)

### Business Model
A lead generation service for the real estate industry supporting large brokerages with complex organizational structures.

### Entity Structure
```
Diverse Platform
├── National Brokerage A (Organization)
│   ├── Florida Division (Branch)
│   │   ├── Miami Team (Team)
│   │   │   └── Top Performers Group (Access Group)
│   │   ├── Orlando Team (Team)
│   │   └── Admin Staff Group (Access Group)
│   ├── Texas Division (Branch)
│   │   ├── Houston Team (Team)
│   │   └── Dallas Team (Team)
│   └── Corporate Admin Group (Access Group)
├── Regional Brokerage B (Organization)
│   ├── North Region (Branch)
│   └── South Region (Branch)
└── Platform Support Team (Access Group)
```

### Key Requirements
- **Deep Hierarchy**: 3+ levels of structural entities
- **Mixed Entity Types**: Both structural (divisions/teams) and access groups
- **Inheritance**: Permissions cascade down the hierarchy
- **Flexibility**: Managers can create ad-hoc access groups at any level

### User Roles
- **Organization Administrator**: Full control over entire organization
- **Branch Manager**: Manages specific division/branch
- **Team Lead**: Manages team members and assignments
- **Agent**: Basic user with lead access
- **Admin Staff**: Support role with specific permissions

### Implementation in outlabsAuth
```python
# Entity creation example
platform = await EntityService.create_entity(
    name="diverse_platform",
    entity_type="platform",
    entity_class="structural"
)

org = await EntityService.create_entity(
    name="national_brokerage_a",
    entity_type="organization",
    entity_class="structural",
    parent_entity_id=platform.id
)

branch = await EntityService.create_entity(
    name="florida_division",
    entity_type="branch",
    entity_class="structural",
    parent_entity_id=org.id
)

team = await EntityService.create_entity(
    name="miami_team",
    entity_type="team",
    entity_class="structural",
    parent_entity_id=branch.id
)

# Access group for top performers
access_group = await EntityService.create_entity(
    name="top_performers",
    entity_type="access_group",
    entity_class="access_group",
    parent_entity_id=team.id,
    metadata={"criteria": "monthly_sales > 100000"}
)
```

## Platform 2: uaya (Spiritual Readings Platform)

### Business Model
A simple platform for users to perform iChing readings and connect with professional interpreters.

### Entity Structure
```
uaya Platform
├── Platform Administrators (Access Group)
├── Professional Interpreters (Access Group)
└── General Users (implicit - no group needed)
```

### Key Requirements
- **Flat Structure**: No organizational hierarchy needed
- **Role-Based Access**: Permissions based on user roles, not entity membership
- **Simple Groups**: Only functional access groups for special permissions

### User Roles
- **Platform Administrator**: System management
- **Interpreter**: Provides professional reading services
- **General User**: Can perform self-readings and book interpreters

### Implementation in outlabsAuth
```python
# Minimal entity setup
platform = await EntityService.create_entity(
    name="uaya_platform",
    entity_type="platform",
    entity_class="structural"
)

# Access groups for special roles
admin_group = await EntityService.create_entity(
    name="platform_admins",
    entity_type="access_group",
    entity_class="access_group",
    parent_entity_id=platform.id
)

interpreter_group = await EntityService.create_entity(
    name="professional_interpreters",
    entity_type="access_group",
    entity_class="access_group",
    parent_entity_id=platform.id,
    metadata={"verified": true, "service_provider": true}
)

# Roles with specific permissions
interpreter_role = await RoleService.create_role(
    name="interpreter",
    permissions=["reading:provide", "calendar:manage", "payment:receive"],
    assignable_at_types=["platform"]
)
```

## Platform 3: qdarte (Lifestyle & Real Estate Marketing)

### Business Model
A two-sided marketplace connecting real estate developments/businesses with social media influencers for marketing campaigns.

### Entity Structure
```
qdarte Platform
├── Client Organizations (Structural)
│   ├── Sunset Developments (Organization)
│   │   ├── Marketing Team (Team)
│   │   └── Analytics Team (Team)
│   ├── Vineyard Estates (Organization)
│   │   └── Admin Team (Team)
│   └── Beach Resort Properties (Organization)
├── Influencer Network (Access Group)
│   ├── Tier 1 Influencers (Access Group)
│   ├── Tier 2 Influencers (Access Group)
│   └── Micro Influencers (Access Group)
└── Platform Operations (Access Group)
```

### Key Requirements
- **Multi-Sided**: Separate portals for clients and influencers
- **Isolated Entities**: Clients cannot see each other's data
- **Individual + Organization**: Support both individual influencers and client organizations
- **Analytics Segregation**: Each side has different analytics views

### User Roles
- **Platform Administrator**: Manages entire platform
- **Client Administrator**: Manages client organization and campaigns
- **Client Team Member**: Limited access within client organization
- **Influencer**: Individual user with campaign management
- **Affiliate Manager**: Platform role managing influencer relationships

### Implementation in outlabsAuth
```python
# Client side setup
client_org = await EntityService.create_entity(
    name="sunset_developments",
    entity_type="organization",
    entity_class="structural",
    parent_entity_id=platform.id,
    metadata={"client_type": "real_estate", "tier": "premium"}
)

# Influencer access groups (not structural entities)
influencer_network = await EntityService.create_entity(
    name="influencer_network",
    entity_type="access_group",
    entity_class="access_group",
    parent_entity_id=platform.id
)

tier1_group = await EntityService.create_entity(
    name="tier_1_influencers",
    entity_type="access_group",
    entity_class="access_group",
    parent_entity_id=influencer_network.id,
    metadata={"min_followers": 100000, "commission_rate": 0.15}
)

# Different permission sets for each side
client_permissions = ["campaign:create", "lead:view", "analytics:client"]
influencer_permissions = ["campaign:participate", "link:generate", "analytics:influencer", "payout:view"]
```

## Platform 4: The Referral Brokerage (Agent-to-Agent Referrals)

### Business Model
A marketplace where real estate agents pass referrals to other agents for commission sharing.

### Entity Structure
```
Referral Brokerage Platform
├── Individual Agents (Direct platform members)
├── Agent Teams (Optional - Future)
│   ├── Smith Team (Team)
│   │   ├── Senior Agents (Access Group)
│   │   └── Junior Agents (Access Group)
│   └── Johnson Group (Team)
└── Platform Support (Access Group)
```

### Key Requirements
- **Primarily Flat**: Most users are individual agents
- **Optional Hierarchy**: Some agents may form small teams
- **Flexible Growth**: Must support transition from individual to team
- **Marketplace Features**: Both referrer and receiver roles

### User Roles
- **Platform Administrator**: System management
- **Individual Agent**: Can send and receive referrals
- **Team Lead**: Manages team of agents (future)
- **Team Member**: Part of an agent team (future)

### Implementation in outlabsAuth
```python
# Start with flat structure
platform = await EntityService.create_entity(
    name="referral_brokerage",
    entity_type="platform",
    entity_class="structural"
)

# Individual agents join platform directly
membership = await EntityMembershipService.add_member(
    entity_id=platform.id,
    user_id=agent_user.id,
    role_id=individual_agent_role.id
)

# Future: Agent creates a team
agent_team = await EntityService.create_entity(
    name="smith_team",
    entity_type="team",
    entity_class="structural",
    parent_entity_id=platform.id,
    metadata={"team_lead": agent_user.id, "commission_split": 0.8}
)

# Flexible role that works for both individual and team contexts
agent_role = await RoleService.create_role(
    name="referral_agent",
    permissions=["referral:send", "referral:receive", "commission:view"],
    assignable_at_types=["platform", "team"]
)
```

## System Design Validation

### Flexibility Requirements Met

1. **Deep Hierarchy Support** ✓
   - Diverse demonstrates 3+ level nesting
   - Proper permission inheritance through levels

2. **Flat Structure Support** ✓
   - uaya shows minimal entity requirements
   - Role-based access without hierarchy

3. **Multi-Tenant Isolation** ✓
   - qdarte clients are isolated organizations
   - Platform-level access groups for influencers

4. **Dynamic Structure Evolution** ✓
   - Referral Brokerage can start flat and add teams
   - Access groups can be added at any level

### Permission Patterns

Each platform demonstrates different permission needs:

- **Hierarchical Inheritance** (Diverse): Permissions flow down the organization tree
- **Role-Based** (uaya): Simple role assignments at platform level
- **Segregated** (qdarte): Different permission sets for different user types
- **Flexible** (Referral Brokerage): Same permissions work at multiple levels

### Key Entity Types Used

1. **Structural Entities**
   - Platform (root level)
   - Organization (client/company level)
   - Branch/Division (regional/functional divisions)
   - Team (smallest structural unit)

2. **Access Groups**
   - Functional groups (Admin Staff, Support)
   - Performance-based groups (Top Performers)
   - Service groups (Interpreters, Influencers)
   - Tier-based groups (Influencer levels)

This architecture ensures outlabsAuth can handle the full spectrum of organizational needs, from the simplest flat structure to complex multi-level hierarchies with mixed entity types.