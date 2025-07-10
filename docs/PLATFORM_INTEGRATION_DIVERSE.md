# Diverse Platform Integration Guide

This document provides a comprehensive guide for how Diverse (a real estate lead generation platform) integrates with OutlabsAuth. It serves as both a reference implementation and a blueprint for complex platform integrations.

## Table of Contents
1. [Business Overview](#business-overview)
2. [Architecture Overview](#architecture-overview)
3. [Entity Structure Mapping](#entity-structure-mapping)
4. [User Journey Scenarios](#user-journey-scenarios)
5. [API Integration Examples](#api-integration-examples)
6. [Permission Requirements](#permission-requirements)
7. [Implementation Checklist](#implementation-checklist)

## Business Overview

### What is Diverse?
Diverse is a lead generation platform for the real estate industry that supports:
- Individual agents working independently
- Small teams led by successful agents
- Large brokerages with multiple offices and divisions
- Corporate franchises with complex hierarchies

### Key Business Requirements
1. **Flexible Structure** - Support everything from solo agents to multi-level corporations
2. **Lead Distribution** - Route leads based on territory, team, and performance
3. **Commission Tracking** - Complex commission splits based on hierarchy
4. **Performance Management** - Track and reward top performers
5. **Compliance** - Ensure proper licensing and regulatory compliance

## Architecture Overview

### Three-Layer System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OutlabsAuth Admin UI                      │
│         (Platform admins configure permissions/roles)        │
└─────────────────────────────┬───────────────────────────────┘
                              │ API
┌─────────────────────────────┴───────────────────────────────┐
│                   Diverse Admin Portal                       │
│    (Diverse staff manage agents, offices, territories)       │
└─────────────────────────────┬───────────────────────────────┘
                              │ API
┌─────────────────────────────┴───────────────────────────────┐
│                    Diverse Agent Portal                      │
│        (Agents view leads, manage teams, track sales)        │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow
1. **Authentication** - All logins go through OutlabsAuth
2. **Authorization** - Every action checks permissions via OutlabsAuth
3. **Business Logic** - Lead management, commissions, etc. stay in Diverse
4. **Identity Data** - User profiles, roles, permissions in OutlabsAuth

## Entity Structure Mapping

### Diverse Terminology → OutlabsAuth Entities

| Diverse Term | OutlabsAuth Entity | Entity Type | Notes |
|--------------|-------------------|-------------|--------|
| Platform | Platform | platform | The Diverse platform itself |
| Franchise/Brokerage | Organization | organization | Top-level client companies |
| Regional Office | Branch | branch | Geographic divisions |
| Local Office | Branch | branch | Can nest under regional |
| Agent Team | Team | team | Group led by an agent |
| Admin Group | Access Group | access_group | Cross-cutting permissions |
| Top Performers Club | Access Group | access_group | Performance-based group |

### Example Hierarchy

```
Diverse Platform
├── National Realty Corp (Organization)
│   ├── Southeast Region (Branch)
│   │   ├── Miami Office (Branch)
│   │   │   ├── Smith Team (Team)
│   │   │   │   ├── John Smith (Team Lead)
│   │   │   │   ├── Mary Johnson (Agent)
│   │   │   │   └── Bob Wilson (Agent)
│   │   │   ├── Johnson Team (Team)
│   │   │   └── Miami Top Performers (Access Group)
│   │   └── Orlando Office (Branch)
│   ├── Northeast Region (Branch)
│   └── Corporate Admins (Access Group)
├── Regional Brokers Inc (Organization)
└── Independent Agents (Organization)
    └── Solo Agents (Team) // Pseudo-team for individuals
```

## User Journey Scenarios

### Scenario 1: Individual Agent Joins Diverse

**Starting Point**: Jane Doe is a licensed real estate agent who wants to use Diverse for leads.

#### Step 1: Registration
```
Jane signs up on Diverse website
↓
Diverse Backend:
1. POST /v1/users/ (Create user in OutlabsAuth)
2. POST /v1/memberships/ (Add to "Independent Agents" org)
3. Assign "Agent" role
4. Create Diverse-specific profile (license #, territories, etc.)
```

#### Step 2: Initial Access
```json
// Jane's initial permissions
{
  "entity_memberships": [{
    "entity": "Independent Agents",
    "roles": ["agent"],
    "permissions": [
      "lead:view_assigned",
      "lead:accept",
      "lead:reject",
      "profile:update_own",
      "commission:view_own"
    ]
  }]
}
```

#### Step 3: Using the Platform
- Jane logs into Diverse Agent Portal
- Portal checks her permissions for every action
- She can only see leads assigned to her
- She cannot see other agents' performance

### Scenario 2: Agent Builds a Team

**Starting Point**: Jane has been successful and wants to recruit agents under her.

#### Step 1: Team Creation Request
```
Jane requests team creation in Agent Portal
↓
Diverse Admin Reviews:
- Verify Jane's performance metrics
- Check compliance/licensing
- Approve team creation
```

#### Step 2: Team Setup
```python
# Diverse Admin Portal executes:

# 1. Create team entity
team_response = outlabs_auth.post('/v1/entities/', {
    "name": "doe_team",
    "display_name": "Doe Real Estate Team",
    "entity_type": "team",
    "entity_class": "structural",
    "parent_entity_id": "independent_agents_org_id",
    "metadata": {
        "lead_routing_rules": "round_robin",
        "commission_split": 0.8
    }
})

# 2. Add Jane as team lead
membership_response = outlabs_auth.post('/v1/memberships/', {
    "user_id": jane_user_id,
    "entity_id": team_id,
    "role_ids": ["team_lead"]
})

# 3. Update Jane's Diverse profile
diverse_db.update_agent_profile(jane_id, {
    "is_team_lead": True,
    "team_id": team_id,
    "can_recruit": True
})
```

#### Step 3: New Permissions
```json
// Jane's new permissions in team context
{
  "entity_memberships": [{
    "entity": "Doe Real Estate Team",
    "roles": ["team_lead"],
    "permissions": [
      "lead:view_team",
      "lead:assign_team_member",
      "member:invite",
      "member:remove",
      "team:update_settings",
      "commission:view_team",
      "commission:configure_splits"
    ]
  }]
}
```

#### Step 4: Recruiting Team Members
```
Jane invites Bob to join her team
↓
1. Invitation sent via Diverse
2. Bob accepts and creates account
3. API calls:
   - Create Bob's user
   - Add Bob to "Doe Team" with "agent" role
   - Configure Bob's commission split
```

### Scenario 3: Corporate Brokerage Onboarding

**Starting Point**: "National Realty Corp" wants to join Diverse with 500+ agents across 20 offices.

#### Step 1: Initial Setup (OutlabsAuth Admin UI)
```python
# System Admin or Diverse Platform Admin creates:

# 1. Organization
org = create_entity({
    "name": "national_realty_corp",
    "display_name": "National Realty Corp",
    "entity_type": "organization",
    "parent_entity_id": diverse_platform_id
})

# 2. Create custom roles for this org
roles = [
    {
        "name": "nrc_broker",
        "display_name": "NRC Broker",
        "permissions": [
            "office:manage",
            "agent:manage",
            "lead:distribute",
            "commission:override"
        ]
    },
    {
        "name": "nrc_office_manager",
        "display_name": "NRC Office Manager",
        "permissions": [
            "agent:manage_office",
            "lead:assign_office",
            "report:view_office"
        ]
    }
]
```

#### Step 2: Building Structure
```
National Realty Admin logs into Diverse Admin Portal
↓
Creates regional/office structure:

Southeast Region (Branch)
├── Miami Office (Branch)
│   ├── Office Staff (Access Group)
│   ├── Top Performers (Access Group)
│   └── Multiple Teams
├── Orlando Office (Branch)
└── Tampa Office (Branch)
```

#### Step 3: Bulk Agent Import
```python
# Diverse implements bulk import that:
for agent in csv_import:
    # 1. Create user in OutlabsAuth
    user = outlabs_auth.create_user({
        "email": agent.email,
        "profile": {
            "first_name": agent.first_name,
            "last_name": agent.last_name
        }
    })
    
    # 2. Add to appropriate office
    outlabs_auth.add_membership({
        "user_id": user.id,
        "entity_id": agent.office_id,
        "role_ids": ["agent"]
    })
    
    # 3. Create Diverse profile
    diverse.create_agent_profile({
        "user_id": user.id,
        "license_number": agent.license,
        "territories": agent.territories,
        "commission_split": agent.split
    })
```

## API Integration Examples

### Authentication Flow

```javascript
// Diverse Agent Portal Login
async function login(email, password) {
    // 1. Authenticate with OutlabsAuth
    const authResponse = await fetch('https://auth.outlabs.com/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ 
            username: email, 
            password: password,
            platform_id: 'diverse_platform_id'
        })
    });
    
    const { access_token, refresh_token, user } = await authResponse.json();
    
    // 2. Get user's Diverse profile
    const profileResponse = await fetch('https://api.diverse.com/agent/profile', {
        headers: { 'Authorization': `Bearer ${access_token}` }
    });
    
    const diverseProfile = await profileResponse.json();
    
    // 3. Get user's permissions for UI rendering
    const permsResponse = await fetch('https://auth.outlabs.com/v1/users/me/permissions', {
        headers: { 'Authorization': `Bearer ${access_token}` }
    });
    
    const permissions = await permsResponse.json();
    
    return {
        user,
        diverseProfile,
        permissions,
        tokens: { access_token, refresh_token }
    };
}
```

### Permission Checking

```javascript
// Diverse Backend - Check before showing leads
async function getLeadsForUser(userId, authToken) {
    // 1. Get user's entity memberships
    const memberships = await outlabsAuth.get(`/v1/users/${userId}/memberships`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
    });
    
    // 2. Determine lead visibility
    const leadQuery = {};
    
    for (const membership of memberships) {
        if (membership.permissions.includes('lead:view_all')) {
            // Can see all leads in system
            leadQuery.scope = 'all';
            break;
        } else if (membership.permissions.includes('lead:view_team')) {
            // Can see team leads
            leadQuery.team_ids = leadQuery.team_ids || [];
            leadQuery.team_ids.push(membership.entity_id);
        } else if (membership.permissions.includes('lead:view_assigned')) {
            // Can only see own leads
            leadQuery.assigned_to = userId;
        }
    }
    
    // 3. Fetch leads based on permissions
    return await diverseDB.getLeads(leadQuery);
}
```

### Entity Management

```javascript
// Diverse Admin Portal - Create new office
async function createOffice(parentEntityId, officeData, adminToken) {
    // 1. Create entity in OutlabsAuth
    const entityResponse = await outlabsAuth.post('/v1/entities/', {
        name: officeData.name.toLowerCase().replace(/\s+/g, '_'),
        display_name: officeData.name,
        entity_type: 'branch',
        entity_class: 'structural',
        parent_entity_id: parentEntityId,
        metadata: {
            address: officeData.address,
            phone: officeData.phone,
            license_number: officeData.brokerLicense
        }
    }, {
        headers: { 'Authorization': `Bearer ${adminToken}` }
    });
    
    const entity = await entityResponse.json();
    
    // 2. Create office in Diverse system
    const office = await diverseDB.createOffice({
        outlabs_entity_id: entity.id,
        ...officeData,
        territories: officeData.territories,
        lead_routing_rules: officeData.leadRules
    });
    
    // 3. Assign office manager
    if (officeData.managerId) {
        await outlabsAuth.post('/v1/memberships/', {
            user_id: officeData.managerId,
            entity_id: entity.id,
            role_ids: ['office_manager']
        });
    }
    
    return { entity, office };
}
```

## Permission Requirements

### Core Permission Set for Diverse

```yaml
# Lead Management
lead:view_assigned      # View leads assigned to me
lead:view_team         # View all team leads
lead:view_office       # View all office leads  
lead:view_all          # View all platform leads
lead:accept            # Accept a lead
lead:reject            # Reject a lead
lead:transfer          # Transfer to another agent
lead:assign            # Assign leads to agents
lead:distribute        # Configure distribution rules

# Commission Management
commission:view_own    # View own commissions
commission:view_team   # View team commissions
commission:view_office # View office commissions
commission:configure   # Set commission splits
commission:override    # Override standard splits
commission:approve     # Approve commission payouts

# Agent Management  
agent:invite          # Invite new agents
agent:approve         # Approve agent applications
agent:suspend         # Suspend agent access
agent:terminate       # Remove agent
agent:view_performance # View agent metrics
agent:set_quotas      # Set performance quotas

# Office Management
office:create         # Create new offices
office:update         # Update office details
office:view_metrics   # View office performance
office:set_territories # Define office territories

# Team Management
team:create           # Create new team
team:update           # Update team settings
team:add_member       # Add team members
team:remove_member    # Remove team members
team:set_splits       # Configure team splits

# Reporting
report:view_own       # View own reports
report:view_team      # View team reports
report:view_office    # View office reports
report:view_company   # View company reports
report:export         # Export report data

# System
system:view_audit     # View audit logs
system:manage_integrations # Configure integrations
system:manage_billing # Handle billing/subscriptions
```

### Role Templates for Diverse

```yaml
# Individual Agent
agent:
  permissions:
    - lead:view_assigned
    - lead:accept
    - lead:reject
    - commission:view_own
    - report:view_own

# Team Lead
team_lead:
  includes: [agent]
  permissions:
    - lead:view_team
    - lead:transfer
    - team:update
    - team:add_member
    - team:remove_member
    - commission:view_team
    - report:view_team

# Office Manager
office_manager:
  permissions:
    - lead:view_office
    - lead:assign
    - agent:invite
    - agent:view_performance
    - commission:view_office
    - report:view_office

# Regional Manager
regional_manager:
  includes: [office_manager]
  permissions:
    - office:create
    - office:update
    - office:set_territories
    - agent:approve
    - agent:suspend

# Broker/Owner
broker:
  permissions:
    - lead:view_all
    - lead:distribute
    - commission:configure
    - commission:override
    - commission:approve
    - agent:terminate
    - office:view_metrics
    - report:view_company

# Platform Admin (Diverse Staff)
platform_admin:
  permissions:
    - "*" # All permissions within Diverse platform
```

## Implementation Checklist

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up Diverse platform in OutlabsAuth
- [ ] Create base entity structure
- [ ] Define core permissions
- [ ] Create role templates
- [ ] Implement authentication flow
- [ ] Build user registration API

### Phase 2: Core Features (Weeks 3-4)
- [ ] Individual agent workflows
- [ ] Team creation process
- [ ] Permission checking middleware
- [ ] Lead visibility rules
- [ ] Basic reporting permissions

### Phase 3: Corporate Features (Weeks 5-6)
- [ ] Multi-level entity creation
- [ ] Bulk user import
- [ ] Complex permission inheritance
- [ ] Commission split configuration
- [ ] Office management tools

### Phase 4: Advanced Features (Weeks 7-8)
- [ ] Performance-based access groups
- [ ] Temporary permission grants
- [ ] Audit logging integration
- [ ] Webhook synchronization
- [ ] Admin UI customization

### Phase 5: Optimization (Weeks 9-10)
- [ ] Permission caching strategy
- [ ] Bulk operation optimizations
- [ ] Performance monitoring
- [ ] Load testing
- [ ] Documentation completion

## Best Practices

### 1. Permission Design
- Start with minimal permissions
- Use permission inheritance wisely
- Create semantic permission names
- Group related permissions

### 2. Entity Structure
- Keep hierarchy as flat as possible
- Use access groups for cross-cutting concerns
- Plan for future growth
- Consider performance implications

### 3. Integration Architecture
- Cache permission checks aggressively
- Implement webhook sync for real-time updates
- Use batch APIs for bulk operations
- Handle failures gracefully

### 4. Security Considerations
- Always verify permissions server-side
- Implement rate limiting
- Log all permission changes
- Regular permission audits

### 5. User Experience
- Provide clear permission error messages
- Show users what they can't access and why
- Make permission requests easy
- Provide permission inheritance visualization

## Conclusion

This integration demonstrates how OutlabsAuth can support complex, hierarchical business models while maintaining clean separation between identity/permissions and business logic. The Diverse platform showcases:

1. **Flexibility** - From individual agents to large corporations
2. **Scalability** - Handles hundreds of offices and thousands of agents
3. **Security** - Granular permissions with proper inheritance
4. **Maintainability** - Clear separation of concerns

By following this pattern, other platforms can implement similarly sophisticated authorization models while keeping their business logic independent of the auth system.