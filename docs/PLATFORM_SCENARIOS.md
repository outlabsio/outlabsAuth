# Platform Deployment Scenarios - Complete Set

This document outlines the five initial business platforms that outlabsAuth will support, demonstrating how the flexible entity system accommodates diverse organizational structures—from simple flat models to complex multi-level hierarchies.

## Overview of Platform Types

1. **Complex Hierarchical** - Diverse (multi-level real estate lead generation)
2. **Flat Structure** - uaya (simple role-based platform) 
3. **Multi-Sided Marketplace** - qdarte (separate client and influencer portals)
4. **Hybrid Optional Hierarchy** - The Referral Brokerage (individual agents with optional teams)
5. **Comprehensive Marketplace** - Property Hub (full-spectrum real estate platform)

## Platform 1: Diverse (Lead Generation Platform) - Updated

### Business Model
A lead generation service for the real estate industry supporting diverse organizational structures, from individual agents to large multi-level brokerages.

### Entity Structure (Updated)

#### Full Spectrum Support
```
Diverse Platform
├── National Brokerage A (Organization)
│   ├── Florida Division (Branch)
│   │   ├── Miami Team (Team)
│   │   │   ├── Agent Smith (Individual Agent Entity - Primary Agent)
│   │   │   │   ├── Junior Agent Jones (Team Member - Agent role)
│   │   │   │   └── Admin Assistant Brown (Team Member - Assistant role)
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
├── Individual Agents (Direct Platform Members)
│   ├── Agent Wilson (User only - no entity needed)
│   ├── Agent Davis (User only - no entity needed)
│   └── Agent Taylor (Primary Agent with Team Entity)
│       ├── Agent Rodriguez (Team Member - Agent role)
│       ├── Agent Kim (Team Member - Agent role)
│       └── Virtual Assistant Lopez (Team Member - Assistant role)
└── Platform Support Team (Access Group)
```

### User Roles (Expanded)

#### Organizational Roles
- **Organization Administrator**: Full control over entire organization
- **Branch Manager**: Manages specific division/branch
- **Team Lead**: Manages team members and assignments

#### Individual Agent Roles
- **Individual Agent**: Solo agent working directly under platform/organization
  - No entity creation needed
  - Can receive and work leads independently
  - May later upgrade to Primary Agent if they want to build a team

- **Primary Agent**: Individual agent who has created their own team entity
  - Can create and manage their own team entity
  - Can invite team members (agents and assistants)
  - Has leadership permissions within their entity
  - Can manage lead distribution to team members

#### Team Member Roles
- **Team Agent**: Licensed agent working under a Primary Agent
  - Can work leads assigned by Primary Agent
  - May have limited lead generation access
  - Can communicate with clients on behalf of team

- **Administrative Assistant**: Support staff for agents/teams
  - Can manage calendars and basic lead data
  - Cannot work leads directly (not licensed)
  - Can handle initial client communications

#### Platform Roles
- **Platform Administrator**: System-wide management
- **Platform Support**: Customer service and technical support

### Key Requirements (Updated)

#### Flexible Agent Models
1. **Solo Agent Path**: Users can work as individual agents without entity creation
2. **Team Building Path**: Solo agents can create entities and become Primary Agents
3. **Team Composition**: Teams can include both licensed agents and support staff
4. **Role Evolution**: Users can transition between role types as their business grows

#### Permission Patterns
- **Individual Agents**: Get platform-level agent permissions
- **Primary Agents**: Get agent permissions + team management permissions within their entity
- **Team Members**: Get role-specific permissions scoped to their team entity

### Implementation Examples

#### Solo Agent (User Only)
```python
# Agent joins platform directly - no entity needed
solo_agent_membership = await EntityMembershipService.add_member(
    entity_id=platform.id,  # Direct platform membership
    user_id=agent_user.id,
    role_id=individual_agent_role.id
)

individual_agent_role = await RoleService.create_role(
    name="individual_agent",
    permissions=[
        "lead:receive", "lead:work", "lead:update_status",
        "client:contact", "appointment:schedule", "report:view_own"
    ],
    assignable_at_types=["platform", "organization", "branch", "team"]
)
```

#### Agent Creates Team (Becomes Primary Agent)
```python
# Agent decides to build a team
agent_team = await EntityService.create_entity(
    name="taylor_team",
    entity_type="agent_team",  # New entity type for individual agent teams
    entity_class="structural",
    parent_entity_id=platform.id,  # Or under organization if agent belongs to one
    metadata={
        "primary_agent_id": agent_user.id,
        "team_type": "individual_agent_team"
    }
)

# Agent becomes Primary Agent of their new entity
primary_agent_membership = await EntityMembershipService.add_member(
    entity_id=agent_team.id,
    user_id=agent_user.id,
    role_id=primary_agent_role.id
)

primary_agent_role = await RoleService.create_role(
    name="primary_agent",
    permissions=[
        "lead:receive", "lead:work", "lead:distribute",
        "team:invite_members", "team:manage_assignments",
        "entity:manage", "report:view_team"
    ],
    assignable_at_types=["agent_team"]
)
```

#### Adding Team Members
```python
# Add another agent to the team
team_agent_membership = await EntityMembershipService.add_member(
    entity_id=agent_team.id,
    user_id=team_agent_user.id,
    role_id=team_agent_role.id
)

# Add administrative assistant
assistant_membership = await EntityMembershipService.add_member(
    entity_id=agent_team.id,
    user_id=assistant_user.id,
    role_id=admin_assistant_role.id
)

team_agent_role = await RoleService.create_role(
    name="team_agent",
    permissions=[
        "lead:work", "lead:update_status",
        "client:contact", "appointment:schedule",
        "report:view_own"
    ],
    assignable_at_types=["agent_team", "team"]
)

admin_assistant_role = await RoleService.create_role(
    name="admin_assistant",
    permissions=[
        "lead:view_assigned", "calendar:manage",
        "client:initial_contact", "appointment:schedule",
        "report:view_basic"
    ],
    assignable_at_types=["agent_team", "team", "organization"]
)
```

### Context-Aware Role Applications

Using the context-aware role system, roles adapt based on where they're assigned:

#### Example: Agent Role with Context Awareness
```python
agent_role = await RoleService.create_role(
    name="agent",
    display_name="Real Estate Agent",
    entity=platform,
    assignable_at_types=["platform", "organization", "branch", "team", "agent_team"],
    
    # Default permissions (fallback)
    permissions=["lead:view", "client:contact"],
    
    # Context-aware permissions
    entity_type_permissions={
        "platform": [
            # Individual agent working directly under platform
            "lead:receive", "lead:work", "lead:update_status",
            "client:contact", "report:view_own"
        ],
        "organization": [
            # Agent working under large brokerage
            "lead:receive", "lead:work", "lead:update_status",
            "client:contact", "report:view_own", "brokerage:access_tools"
        ],
        "agent_team": [
            # Team member under Primary Agent
            "lead:work_assigned", "lead:update_status",
            "client:contact", "team:collaborate"
        ],
        "team": [
            # Member of larger organizational team
            "lead:work_assigned", "lead:update_status",
            "client:contact", "team:collaborate", "team:access_shared_resources"
        ]
    }
)
```

### Business Flow Examples

#### Scenario 1: Solo Agent
1. Agent registers on platform
2. Gets `individual_agent` role at platform level
3. Can immediately start receiving and working leads
4. No entity creation needed

#### Scenario 2: Agent Builds Team
1. Solo agent decides to expand
2. Creates `agent_team` entity (becomes Primary Agent)
3. Invites team members (agents and assistants)
4. Can distribute leads among team members
5. Maintains oversight of team performance

#### Scenario 3: Brokerage Integration
1. Large brokerage joins platform
2. Creates organizational hierarchy (organization → branches → teams)
3. Existing agents can join at appropriate level
4. Can have mix of individual agents and team structures within brokerage

### Validation Points

#### Entity Flexibility ✓
- Supports users without entities (solo agents)
- Supports user-created entities (agent teams)
- Supports organizational entities (brokerages)

#### Role Evolution ✓
- Individual Agent → Primary Agent (when creating team)
- Agent → Team Lead (within organizational structure)
- Assistant → Agent (if they get licensed)

#### Permission Scoping ✓
- Platform-level permissions for solo agents
- Entity-specific permissions for team management
- Inherited permissions through organizational hierarchy

#### Team Composition ✓
- Licensed agents as team members
- Non-licensed assistants as team members
- Mixed skill levels and responsibilities

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

## Platform 5: Property Hub (Comprehensive Real Estate Marketplace)

### Business Model
A full-spectrum real estate platform connecting buyers, sellers, agents, and property managers in one integrated ecosystem.

### Entity Structure

#### Multi-Faceted Organization
```
Property Hub Platform
├── Real Estate Agencies (Structural)
│   ├── Century Properties (Organization)
│   │   ├── Residential Division (Branch)
│   │   │   ├── Sales Team (Team)
│   │   │   └── Leasing Team (Team)
│   │   └── Commercial Division (Branch)
│   ├── Premier Realty (Organization)
│   │   └── City Office (Branch)
│   └── Agency Admin Group (Access Group)
├── Property Management Companies (Structural)
│   ├── Urban Living Management (Organization)
│   │   ├── Downtown Portfolio (Team)
│   │   └── Suburban Portfolio (Team)
│   └── Property Manager Network (Access Group)
├── Individual Service Providers (Direct Platform Members)
│   ├── Independent Agents (Users with optional entities)
│   ├── Freelance Photographers (Users only)
│   ├── Home Inspectors (Users only)
│   └── Mortgage Brokers (Users only)
├── Buyer/Seller Portal (Access Groups)
│   ├── Verified Buyers (Access Group)
│   ├── Pre-Approved Buyers (Access Group)
│   ├── Property Sellers (Access Group)
│   └── Investor Network (Access Group)
└── Platform Operations (Access Group)
    ├── Customer Support (Access Group)
    ├── Compliance Team (Access Group)
    └── Marketing Team (Access Group)
```

### User Roles (Comprehensive)

#### Agency Roles
- **Agency Owner**: Full control over agency and all subdivisions
- **Branch Manager**: Manages specific office/division
- **Team Lead**: Manages sales or leasing team
- **Licensed Agent**: Can list properties, work with clients
- **Agent Assistant**: Administrative support, cannot transact

#### Property Management Roles
- **Property Management Company Owner**: Full control over PM company
- **Portfolio Manager**: Manages specific property portfolios
- **Property Manager**: Manages individual properties
- **Leasing Agent**: Shows properties, processes applications
- **Maintenance Coordinator**: Manages repair requests

#### Service Provider Roles
- **Independent Agent**: Can list properties independently
- **Photographer**: Can upload property photos/videos
- **Inspector**: Can submit inspection reports
- **Mortgage Broker**: Can provide financing options

#### Client Roles
- **Buyer**: Can search, save properties, make offers
- **Seller**: Can list properties, review offers
- **Tenant**: Can apply for rentals, pay rent
- **Investor**: Access to investment properties and analytics

#### Platform Roles
- **Super Administrator**: Full platform control
- **Compliance Officer**: Reviews listings, ensures regulations
- **Support Agent**: Handles user inquiries
- **Marketing Manager**: Manages platform promotions

### Key Requirements

#### Multiple Business Models
1. **Traditional Agencies**: Hierarchical structure with teams
2. **Independent Professionals**: Direct platform access
3. **Property Management**: Separate operational structure
4. **Client Portals**: Self-service for buyers/sellers

#### Complex Permission Requirements
- Agents can only edit their own listings
- Agency owners can manage all agency listings
- Property managers need different permissions than sales agents
- Clients have limited, portal-specific permissions

#### Cross-Entity Collaboration
- Agents can collaborate on deals across agencies
- Service providers can be assigned to any listing
- Shared commission structures between entities

### Implementation Examples

#### Multi-Type Platform Setup
```python
# Create main platform
platform = await EntityService.create_entity(
    name="property_hub",
    entity_type="marketplace_platform",
    entity_class="structural",
    metadata={
        "supported_services": ["sales", "rentals", "property_management", "services"],
        "commission_model": "platform_based"
    }
)

# Real estate agency
agency = await EntityService.create_entity(
    name="century_properties",
    entity_type="real_estate_agency",
    entity_class="structural",
    parent_entity_id=platform.id,
    metadata={
        "license_number": "RE123456",
        "agency_type": "full_service"
    }
)

# Property management company
pm_company = await EntityService.create_entity(
    name="urban_living_management",
    entity_type="property_management_company",
    entity_class="structural",
    parent_entity_id=platform.id,
    metadata={
        "managed_units": 500,
        "service_areas": ["downtown", "midtown"]
    }
)

# Service provider groups (not structural)
service_providers = await EntityService.create_entity(
    name="service_provider_network",
    entity_type="access_group",
    entity_class="access_group",
    parent_entity_id=platform.id
)

buyer_portal = await EntityService.create_entity(
    name="verified_buyers",
    entity_type="access_group",
    entity_class="access_group",
    parent_entity_id=platform.id,
    metadata={"verification_required": true}
)
```

#### Context-Aware Roles for Multi-Use Platform
```python
# Agent role that works differently in different contexts
agent_role = await RoleService.create_role(
    name="real_estate_professional",
    display_name="Real Estate Professional",
    entity=platform,
    assignable_at_types=["platform", "real_estate_agency", "property_management_company", "team"],
    
    # Base permissions
    permissions=["listing:view", "client:communicate"],
    
    # Context-specific permissions
    entity_type_permissions={
        "platform": [
            # Independent agent
            "listing:create_own", "listing:edit_own",
            "client:manage_own", "commission:track_own",
            "calendar:manage_own"
        ],
        "real_estate_agency": [
            # Agency agent with more tools
            "listing:create_agency", "listing:edit_agency",
            "client:manage_agency", "commission:track_team",
            "mls:access", "agency:use_resources",
            "showing:schedule"
        ],
        "property_management_company": [
            # PM-focused agent
            "rental:list", "tenant:screen",
            "lease:prepare", "maintenance:request",
            "rent:collect", "property:inspect"
        ],
        "team": [
            # Team member with collaborative features
            "listing:view_team", "listing:collaborate",
            "client:share_team", "commission:split",
            "calendar:view_team"
        ]
    }
)

# Client role with portal-specific permissions
buyer_role = await RoleService.create_role(
    name="buyer",
    display_name="Property Buyer",
    entity=platform,
    permissions=[
        "listing:search", "listing:save_favorites",
        "offer:submit", "document:upload",
        "agent:contact", "showing:request",
        "mortgage:calculate"
    ],
    assignable_at_types=["platform"]  # Only at platform level
)

# Service provider role
photographer_role = await RoleService.create_role(
    name="property_photographer",
    display_name="Property Photographer",
    entity=platform,
    permissions=[
        "listing:view_assigned", "media:upload",
        "media:edit_own", "invoice:submit",
        "calendar:manage_appointments"
    ],
    assignable_at_types=["platform", "real_estate_agency"]
)
```

#### Complex Permission Scenarios
```python
# Listing permissions with ownership rules
class ListingPermissionService:
    @staticmethod
    async def can_edit_listing(user_id: str, listing_id: str) -> bool:
        # Get user's role and context
        user_membership = await EntityMembershipService.get_user_memberships(user_id)
        listing = await ListingService.get_listing(listing_id)
        
        for membership in user_memberships:
            role = await membership.role.fetch()
            
            # Check direct ownership
            if listing.agent_id == user_id and "listing:edit_own" in role.permissions:
                return True
            
            # Check agency ownership
            if listing.agency_id == membership.entity_id and "listing:edit_agency" in role.permissions:
                return True
            
            # Check team collaboration
            if listing.team_id == membership.entity_id and "listing:collaborate" in role.permissions:
                return True
                
        return False

# Cross-entity collaboration
collaboration = await CollaborationService.create_collaboration(
    listing_id=listing.id,
    primary_agent_id=agent1.id,
    collaborating_agent_id=agent2.id,
    commission_split={"agent1": 0.6, "agent2": 0.4},
    terms="Co-listing agreement"
)
```

### Business Flow Examples

#### Scenario 1: Traditional Agency Operations
1. Agency owner creates organizational structure
2. Assigns branch managers and team leads
3. Agents join teams and get agency resources
4. Listings are managed at agency level with team collaboration

#### Scenario 2: Independent Agent Journey
1. Agent joins platform directly (no agency)
2. Creates own listings and manages own clients
3. Can later join an agency or create own team
4. Maintains ownership of existing clients/listings

#### Scenario 3: Property Management Operations
1. PM company creates portfolio structure
2. Assigns property managers to buildings
3. Leasing agents handle tenant placement
4. Maintenance coordinators manage work orders
5. Different permission set than sales operations

#### Scenario 4: Client Self-Service
1. Buyer registers and gets verified
2. Searches properties across all agencies
3. Contacts agents directly through platform
4. Submits offers and uploads documents
5. Tracks transaction progress

### Validation Points

#### Multi-Business Support ✓
- Sales agencies with traditional hierarchy
- Property management with different structure
- Independent professionals without entities
- Client portals with limited access

#### Permission Complexity ✓
- Ownership-based permissions (own vs agency)
- Role context awareness (same role, different permissions)
- Cross-entity collaboration permissions
- Portal-specific client permissions

#### Scalability ✓
- Supports thousands of agencies
- Millions of client users
- Flexible entity creation at any level
- Performance optimized for marketplace scale

#### Integration Points ✓
- MLS integration per agency
- Payment processing for transactions
- Document management system
- Communication platform
- Analytics and reporting

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

## Summary of Platform Diversity

The five platforms demonstrate outlabsAuth's ability to support:

1. **Diverse** - Complex hierarchical lead generation with individual agents, teams, and large brokerages
2. **uaya** - Simple flat structure for role-based access
3. **qdarte** - Multi-sided marketplace with segregated portals
4. **The Referral Brokerage** - Hybrid model supporting both individual agents and optional teams
5. **Property Hub** - Comprehensive marketplace with multiple business types and complex permissions

Each platform validates different aspects of the system:
- Entity flexibility (structural vs access groups, optional entities)
- Permission complexity (context-aware roles, ownership-based access)
- Organizational models (flat, hierarchical, hybrid, multi-sided)
- User evolution (individual → team lead → organization owner)
- Cross-entity collaboration and marketplace dynamics