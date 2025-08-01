# Property Hub Integration Guide

This guide specifically covers integrating a property hub platform (like Zillow, Realtor.com, or similar real estate marketplaces) with OutlabsAuth. It includes industry-specific patterns, entity structures, and permission models tailored for real estate platforms.

## Table of Contents

1. [Property Hub Overview](#property-hub-overview)
2. [Entity Hierarchy for Real Estate](#entity-hierarchy-for-real-estate)
3. [Role Definitions](#role-definitions)
4. [Permission Model](#permission-model)
5. [User Onboarding Flows](#user-onboarding-flows)
6. [Property Management Integration](#property-management-integration)
7. [Lead Distribution System](#lead-distribution-system)
8. [Multi-Brokerage Support](#multi-brokerage-support)
9. [Implementation Examples](#implementation-examples)
10. [Best Practices](#best-practices)

## Property Hub Overview

A property hub platform typically needs to support:

- **Multiple Brokerages**: Each with their own organizational structure
- **Agent Management**: Individual agents with varying permission levels
- **Property Listings**: Create, edit, and manage property listings
- **Lead Distribution**: Route leads to appropriate agents/teams
- **Commission Tracking**: Visibility controls for sensitive financial data
- **MLS Integration**: Sync with Multiple Listing Services
- **Client Portals**: Separate access for buyers/sellers

## Entity Hierarchy for Real Estate

### Recommended Structure

```
Property Hub Platform
├── Brokerage A
│   ├── Regional Office 1
│   │   ├── Team Alpha
│   │   │   └── Agents
│   │   ├── Team Beta
│   │   │   └── Agents
│   │   └── Office Staff (Access Group)
│   ├── Regional Office 2
│   │   └── Teams...
│   └── Brokerage Admins (Access Group)
├── Brokerage B
│   └── (Similar structure)
├── Independent Agents (Organization)
│   └── Individual Agent "Teams"
└── Platform Admins (Access Group)
```

### Entity Creation Example

```javascript
// 1. Create the platform root
const platform = await createEntity({
  name: 'property_hub',
  display_name: 'Property Hub Platform',
  entity_type: 'platform',
  entity_class: 'structural',
  metadata: {
    platform_type: 'real_estate_marketplace',
    mls_integration: true,
    supported_regions: ['FL', 'TX', 'CA']
  }
});

// 2. Create a brokerage
const brokerage = await createEntity({
  name: 'sunshine_realty',
  display_name: 'Sunshine Realty Inc.',
  entity_type: 'brokerage',
  entity_class: 'structural',
  parent_entity_id: platform.id,
  metadata: {
    license_number: 'BRK-12345-FL',
    primary_contact: 'broker@sunshinerealty.com',
    commission_split_default: '80/20',
    mls_id: 'SUN123'
  }
});

// 3. Create an office
const office = await createEntity({
  name: 'miami_office',
  display_name: 'Miami Office',
  entity_type: 'office',
  entity_class: 'structural',
  parent_entity_id: brokerage.id,
  metadata: {
    address: '123 Ocean Drive, Miami, FL 33139',
    phone: '305-555-0100',
    office_manager: 'manager@sunshinerealty.com',
    active_listings_count: 0
  }
});

// 4. Create a team
const team = await createEntity({
  name: 'luxury_team',
  display_name: 'Luxury Properties Team',
  entity_type: 'team',
  entity_class: 'structural',
  parent_entity_id: office.id,
  metadata: {
    team_lead: 'lead@luxuryteam.com',
    specialization: 'luxury_residential',
    min_price_point: 1000000
  }
});

// 5. Create access groups
const listingCommittee = await createEntity({
  name: 'listing_committee',
  display_name: 'Listing Review Committee',
  entity_type: 'committee',
  entity_class: 'access_group',
  parent_entity_id: brokerage.id,
  metadata: {
    purpose: 'review_and_approve_listings',
    meeting_schedule: 'weekly'
  }
});
```

## Role Definitions

### Predefined Roles for Property Hubs

```javascript
// 1. Broker/Owner Role
const brokerRole = {
  name: 'broker_owner',
  display_name: 'Broker/Owner',
  description: 'Full access to all brokerage operations',
  permissions: [
    // Entity management
    'entity:create_tree',
    'entity:update_tree',
    'entity:delete_tree',
    
    // User management
    'user:create_all',
    'user:update_all',
    'user:delete_all',
    'user:view_all',
    
    // Listing management
    'listing:create_all',
    'listing:update_all',
    'listing:delete_all',
    'listing:approve_all',
    
    // Financial access
    'commission:view_all',
    'commission:update_all',
    'transaction:view_all',
    
    // Lead management
    'lead:view_all',
    'lead:assign_all',
    'lead:distribute_all'
  ],
  assignable_at_types: ['brokerage']
};

// 2. Office Manager Role
const officeManagerRole = {
  name: 'office_manager',
  display_name: 'Office Manager',
  description: 'Manages office operations and agents',
  permissions: [
    // Entity management (limited to office)
    'entity:create',
    'entity:update',
    'entity:update_tree',
    
    // User management in office
    'user:create',
    'user:update',
    'user:view_tree',
    
    // Listing management
    'listing:view_tree',
    'listing:approve',
    
    // Limited financial access
    'commission:view_tree',
    'transaction:view_tree',
    
    // Lead distribution
    'lead:view_tree',
    'lead:assign'
  ],
  assignable_at_types: ['office']
};

// 3. Team Lead Role
const teamLeadRole = {
  name: 'team_lead',
  display_name: 'Team Lead',
  description: 'Manages team members and their activities',
  permissions: [
    // Team management
    'user:view_tree',
    'user:update',
    
    // Listing supervision
    'listing:view_tree',
    'listing:approve',
    
    // Lead distribution within team
    'lead:view_tree',
    'lead:assign',
    
    // Team performance metrics
    'metrics:view_tree',
    'report:view_tree'
  ],
  assignable_at_types: ['team']
};

// 4. Agent Role
const agentRole = {
  name: 'agent',
  display_name: 'Real Estate Agent',
  description: 'Licensed agent with listing and client management',
  permissions: [
    // Own listings
    'listing:create',
    'listing:update_own',
    'listing:delete_own',
    'listing:view',
    
    // Lead management
    'lead:view_assigned',
    'lead:update_assigned',
    'lead:convert',
    
    // Client management
    'client:create',
    'client:update_own',
    'client:view_own',
    
    // Limited financial view
    'commission:view_own',
    'transaction:view_own'
  ],
  assignable_at_types: ['team', 'office', 'brokerage']
};

// 5. Administrative Staff Role
const adminStaffRole = {
  name: 'admin_staff',
  display_name: 'Administrative Staff',
  description: 'Support staff for office operations',
  permissions: [
    // Listing support
    'listing:view',
    'listing:update_details',
    
    // Document management
    'document:create',
    'document:update',
    'document:view',
    
    // Calendar management
    'calendar:view_all',
    'calendar:update_all',
    
    // Basic reporting
    'report:view',
    'metrics:view'
  ],
  assignable_at_types: ['office', 'brokerage']
};
```

## Permission Model

### Property Hub Specific Permissions

```javascript
const propertyHubPermissions = {
  // Listing Permissions
  'listing:create': 'Create new property listings',
  'listing:update': 'Update listing details',
  'listing:update_own': 'Update own listings only',
  'listing:delete': 'Delete listings',
  'listing:delete_own': 'Delete own listings only',
  'listing:approve': 'Approve listings for publication',
  'listing:view': 'View listings',
  'listing:export': 'Export listing data',
  
  // Lead Permissions
  'lead:view': 'View leads',
  'lead:view_assigned': 'View assigned leads only',
  'lead:assign': 'Assign leads to agents',
  'lead:distribute': 'Configure lead distribution rules',
  'lead:convert': 'Convert leads to clients',
  'lead:import': 'Import leads from external sources',
  
  // Client Permissions
  'client:create': 'Create client profiles',
  'client:view': 'View client information',
  'client:view_own': 'View own clients only',
  'client:update': 'Update client information',
  'client:delete': 'Delete client profiles',
  
  // Transaction Permissions
  'transaction:create': 'Create transactions',
  'transaction:view': 'View transaction details',
  'transaction:view_own': 'View own transactions only',
  'transaction:update': 'Update transaction status',
  'transaction:approve': 'Approve transactions',
  
  // Commission Permissions
  'commission:view': 'View commission details',
  'commission:view_own': 'View own commissions only',
  'commission:update': 'Update commission splits',
  'commission:approve': 'Approve commission disbursements',
  
  // MLS Permissions
  'mls:sync': 'Sync with MLS systems',
  'mls:export': 'Export to MLS',
  'mls:import': 'Import from MLS',
  
  // Analytics Permissions
  'analytics:view': 'View analytics dashboards',
  'analytics:view_own': 'View own performance only',
  'analytics:export': 'Export analytics data',
  'report:create': 'Create custom reports',
  'report:view': 'View reports'
};
```

### Permission Checking Example

```javascript
// Middleware for checking listing permissions
async function checkListingPermission(req, res, next) {
  const { listingId } = req.params;
  const userId = req.user.id;
  
  // Get listing details to check ownership
  const listing = await getListing(listingId);
  
  // Check if user can update any listing
  const canUpdateAny = await checkPermission(
    userId,
    'listing:update',
    listing.entity_id
  );
  
  if (canUpdateAny) {
    return next();
  }
  
  // Check if user can update own listings and owns this listing
  const canUpdateOwn = await checkPermission(
    userId,
    'listing:update_own',
    listing.entity_id
  );
  
  if (canUpdateOwn && listing.agent_id === userId) {
    return next();
  }
  
  return res.status(403).json({ 
    error: 'You do not have permission to update this listing' 
  });
}
```

## User Onboarding Flows

### 1. Brokerage Onboarding

```javascript
async function onboardBrokerage(brokerageData) {
  // Step 1: Create brokerage entity
  const brokerage = await createEntity({
    name: sanitizeName(brokerageData.name),
    display_name: brokerageData.name,
    entity_type: 'brokerage',
    entity_class: 'structural',
    parent_entity_id: platformId,
    metadata: {
      license_number: brokerageData.licenseNumber,
      state: brokerageData.state,
      mls_ids: brokerageData.mlsIds
    }
  });
  
  // Step 2: Create broker/owner user
  const broker = await createUser({
    email: brokerageData.brokerEmail,
    password: brokerageData.password,
    profile: {
      first_name: brokerageData.brokerFirstName,
      last_name: brokerageData.brokerLastName,
      license_number: brokerageData.brokerLicense
    }
  });
  
  // Step 3: Assign broker role
  await addUserToEntity({
    user_id: broker.id,
    entity_id: brokerage.id,
    role_ids: [brokerOwnerRoleId]
  });
  
  // Step 4: Create default office
  const mainOffice = await createEntity({
    name: 'main_office',
    display_name: 'Main Office',
    entity_type: 'office',
    entity_class: 'structural',
    parent_entity_id: brokerage.id
  });
  
  // Step 5: Set up default access groups
  await createDefaultAccessGroups(brokerage.id);
  
  // Step 6: Configure MLS integration
  if (brokerageData.mlsIds?.length > 0) {
    await configureMlsIntegration(brokerage.id, brokerageData.mlsIds);
  }
  
  return { brokerage, broker };
}
```

### 2. Agent Onboarding

```javascript
async function onboardAgent(agentData, inviteCode) {
  // Step 1: Validate invite code and get target entity
  const invite = await validateInviteCode(inviteCode);
  const targetEntity = await getEntity(invite.entity_id);
  
  // Step 2: Create agent user
  const agent = await createUser({
    email: agentData.email,
    password: agentData.password,
    profile: {
      first_name: agentData.firstName,
      last_name: agentData.lastName,
      license_number: agentData.licenseNumber,
      phone: agentData.phone,
      photo: agentData.photoUrl
    }
  });
  
  // Step 3: Add to entity with appropriate role
  await addUserToEntity({
    user_id: agent.id,
    entity_id: targetEntity.id,
    role_ids: [agentRoleId],
    metadata: {
      joined_date: new Date().toISOString(),
      commission_split: invite.commission_split || '80/20',
      mentor_id: invite.mentor_id
    }
  });
  
  // Step 4: Set up agent profile in property hub
  await createAgentProfile({
    user_id: agent.id,
    specializations: agentData.specializations,
    service_areas: agentData.serviceAreas,
    languages: agentData.languages,
    bio: agentData.bio
  });
  
  // Step 5: Assign to team if specified
  if (invite.team_id) {
    await addUserToEntity({
      user_id: agent.id,
      entity_id: invite.team_id,
      role_ids: [teamMemberRoleId]
    });
  }
  
  // Step 6: Send welcome email with resources
  await sendAgentWelcomeEmail(agent, targetEntity);
  
  return agent;
}
```

## Property Management Integration

### Creating and Managing Listings

```javascript
class ListingManager {
  async createListing(listingData, agentId) {
    // 1. Validate agent permissions
    const agent = await getUser(agentId);
    const canCreate = await checkPermission(
      agentId,
      'listing:create',
      listingData.entity_id
    );
    
    if (!canCreate) {
      throw new ForbiddenError('You cannot create listings in this entity');
    }
    
    // 2. Create listing with proper ownership
    const listing = await this.db.createListing({
      ...listingData,
      agent_id: agentId,
      entity_id: listingData.entity_id,
      status: 'draft',
      created_at: new Date(),
      outlabs_metadata: {
        created_by: agentId,
        entity_path: await this.getEntityPath(listingData.entity_id)
      }
    });
    
    // 3. Check if auto-approval is needed
    const needsApproval = await this.checkApprovalRequired(
      listing,
      listingData.entity_id
    );
    
    if (needsApproval) {
      await this.submitForApproval(listing.id, listingData.entity_id);
    } else {
      listing.status = 'active';
      await listing.save();
    }
    
    // 4. Sync with MLS if configured
    if (listingData.sync_to_mls) {
      await this.syncToMls(listing);
    }
    
    return listing;
  }
  
  async updateListing(listingId, updates, userId) {
    const listing = await this.getListing(listingId);
    
    // Check update permissions
    const canUpdateAny = await checkPermission(
      userId,
      'listing:update',
      listing.entity_id
    );
    
    const canUpdateOwn = await checkPermission(
      userId,
      'listing:update_own',
      listing.entity_id
    );
    
    if (!canUpdateAny && !(canUpdateOwn && listing.agent_id === userId)) {
      throw new ForbiddenError('You cannot update this listing');
    }
    
    // Apply updates with audit trail
    const updatedListing = await this.db.updateListing(listingId, {
      ...updates,
      outlabs_metadata: {
        ...listing.outlabs_metadata,
        last_updated_by: userId,
        last_updated_at: new Date()
      }
    });
    
    return updatedListing;
  }
}
```

### Listing Approval Workflow

```javascript
async function setupListingApprovalWorkflow(brokerageId) {
  // Create approval workflow for high-value listings
  const workflow = await createWorkflow({
    name: 'high_value_listing_approval',
    entity_id: brokerageId,
    trigger: {
      type: 'listing_created',
      conditions: [
        { field: 'price', operator: '>', value: 1000000 }
      ]
    },
    steps: [
      {
        name: 'manager_review',
        assignee: { role: 'office_manager' },
        required_permission: 'listing:approve',
        timeout_hours: 24
      },
      {
        name: 'broker_review',
        assignee: { role: 'broker_owner' },
        required_permission: 'listing:approve',
        timeout_hours: 48,
        conditions: [
          { field: 'price', operator: '>', value: 5000000 }
        ]
      }
    ],
    on_approval: {
      action: 'update_listing_status',
      status: 'active'
    },
    on_rejection: {
      action: 'update_listing_status',
      status: 'rejected',
      notify_agent: true
    }
  });
  
  return workflow;
}
```

## Lead Distribution System

### Configuring Lead Distribution Rules

```javascript
class LeadDistributionSystem {
  async configureDistributionRules(entityId, rules) {
    // Validate permissions
    const canConfigure = await checkPermission(
      currentUser.id,
      'lead:distribute',
      entityId
    );
    
    if (!canConfigure) {
      throw new ForbiddenError('You cannot configure lead distribution');
    }
    
    // Set up distribution rules
    const distributionConfig = {
      entity_id: entityId,
      rules: [
        {
          name: 'round_robin_by_specialization',
          priority: 1,
          conditions: [
            { field: 'property_type', operator: 'equals', value: 'residential' }
          ],
          distribution_method: 'round_robin',
          recipient_filter: {
            specializations: ['residential'],
            min_performance_score: 80,
            max_active_leads: 20
          }
        },
        {
          name: 'direct_to_luxury_team',
          priority: 2,
          conditions: [
            { field: 'budget', operator: '>', value: 1000000 }
          ],
          distribution_method: 'team_assignment',
          target_entity_id: luxuryTeamId
        },
        {
          name: 'geographic_assignment',
          priority: 3,
          distribution_method: 'geographic',
          geo_mapping: {
            'miami_beach': ['agent_123', 'agent_456'],
            'coral_gables': ['agent_789']
          }
        }
      ],
      fallback: {
        method: 'assign_to_manager',
        notification: true
      }
    };
    
    await this.saveDistributionConfig(distributionConfig);
    return distributionConfig;
  }
  
  async distributeLead(lead) {
    // Get applicable distribution rules
    const entity = await this.determineLeadEntity(lead);
    const rules = await this.getDistributionRules(entity.id);
    
    // Find matching rule
    for (const rule of rules.sortBy('priority')) {
      if (this.evaluateConditions(lead, rule.conditions)) {
        const assignee = await this.selectAssignee(rule, entity.id);
        
        if (assignee) {
          await this.assignLead(lead, assignee, rule);
          return assignee;
        }
      }
    }
    
    // Use fallback if no rule matches
    return this.handleFallback(lead, entity);
  }
}
```

## Multi-Brokerage Support

### Platform-Level Features

```javascript
class MultiBrokerageManager {
  async setupBrokerageIsolation(brokerageId) {
    // 1. Create brokerage-specific permission overrides
    await this.createPermissionOverrides(brokerageId, {
      // Prevent cross-brokerage data access
      'listing:view': {
        scope: 'entity_tree_only',
        conditions: {
          entity_root: brokerageId
        }
      },
      'client:view': {
        scope: 'entity_tree_only',
        conditions: {
          entity_root: brokerageId
        }
      }
    });
    
    // 2. Set up brokerage-specific branding
    await this.configureBranding(brokerageId, {
      logo_url: brokerageData.logo,
      primary_color: brokerageData.brandColor,
      email_domain: brokerageData.emailDomain
    });
    
    // 3. Configure brokerage-specific features
    await this.enableFeatures(brokerageId, {
      lead_distribution: true,
      commission_tracking: true,
      mls_sync: brokerageData.mlsEnabled,
      client_portal: true,
      custom_reports: brokerageData.plan === 'enterprise'
    });
  }
  
  async handleCrossBrokerageTransfer(agentId, fromBrokerageId, toBrokerageId) {
    // 1. Verify transfer is allowed
    const canTransfer = await this.validateTransfer(
      agentId,
      fromBrokerageId,
      toBrokerageId
    );
    
    if (!canTransfer) {
      throw new Error('Transfer not permitted');
    }
    
    // 2. Handle active listings
    const activeListings = await this.getAgentListings(agentId, {
      status: 'active',
      entity_id: fromBrokerageId
    });
    
    for (const listing of activeListings) {
      await this.transferListing(listing, toBrokerageId, {
        maintain_history: true,
        notify_clients: true
      });
    }
    
    // 3. Update agent membership
    await this.removeUserFromEntity(agentId, fromBrokerageId);
    await this.addUserToEntity(agentId, toBrokerageId, {
      role_ids: [agentRoleId],
      transferred_from: fromBrokerageId,
      transfer_date: new Date()
    });
    
    // 4. Handle commission splits
    await this.transferCommissionRecords(agentId, fromBrokerageId, toBrokerageId);
  }
}
```

## Implementation Examples

### Complete Integration Example

```javascript
// 1. Initialize OutlabsAuth client
class PropertyHubAuth {
  constructor(config) {
    this.apiUrl = config.outlabsAuthUrl;
    this.apiKey = config.apiKey;
    this.platformId = config.platformId;
  }
  
  // 2. User authentication
  async authenticateUser(email, password) {
    const response = await fetch(`${this.apiUrl}/v1/auth/login/json`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      throw new AuthError('Invalid credentials');
    }
    
    const { access_token, refresh_token } = await response.json();
    
    // Get user's property hub context
    const userContext = await this.getUserContext(access_token);
    
    return {
      tokens: { access_token, refresh_token },
      user: userContext.user,
      brokerage: userContext.brokerage,
      permissions: userContext.permissions
    };
  }
  
  // 3. Get user's property hub context
  async getUserContext(token) {
    // Get user info
    const userResponse = await fetch(`${this.apiUrl}/v1/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const user = await userResponse.json();
    
    // Find user's brokerage membership
    const brokerageMembership = user.entities.find(
      e => e.entity_type === 'brokerage'
    );
    
    if (!brokerageMembership) {
      throw new Error('User not associated with a brokerage');
    }
    
    // Get permissions in brokerage context
    const permsResponse = await fetch(
      `${this.apiUrl}/v1/users/${user.id}/permissions?entity_id=${brokerageMembership.id}`,
      { headers: { 'Authorization': `Bearer ${token}` } }
    );
    const permissions = await permsResponse.json();
    
    return {
      user,
      brokerage: brokerageMembership,
      permissions: permissions.permissions
    };
  }
  
  // 4. Check listing permissions
  async canManageListing(userId, listingId, action) {
    const listing = await this.getListing(listingId);
    const permission = `listing:${action}`;
    
    // Check general permission
    const hasPermission = await this.checkPermission(
      userId,
      permission,
      listing.entity_id
    );
    
    if (hasPermission) return true;
    
    // Check own listing permission
    if (listing.agent_id === userId) {
      return this.checkPermission(
        userId,
        `${permission}_own`,
        listing.entity_id
      );
    }
    
    return false;
  }
}

// 5. Property Hub API with auth integration
class PropertyHubAPI {
  constructor(authClient) {
    this.auth = authClient;
  }
  
  async createListing(listingData, token) {
    // Verify permissions before creating
    const context = await this.auth.getUserContext(token);
    const canCreate = context.permissions.includes('listing:create');
    
    if (!canCreate) {
      throw new ForbiddenError('You cannot create listings');
    }
    
    // Create listing with proper entity assignment
    const listing = await this.db.listings.create({
      ...listingData,
      agent_id: context.user.id,
      brokerage_id: context.brokerage.id,
      entity_id: context.brokerage.id,
      created_by: context.user.id,
      created_at: new Date()
    });
    
    // Audit log
    await this.audit.log({
      action: 'listing.created',
      user_id: context.user.id,
      entity_id: context.brokerage.id,
      resource_id: listing.id,
      details: { price: listing.price, address: listing.address }
    });
    
    return listing;
  }
}
```

## Best Practices

### 1. Entity Structure
- Keep brokerage hierarchies shallow (3-4 levels max)
- Use access groups for cross-functional teams
- Maintain consistent entity types across the platform
- Include relevant metadata for reporting

### 2. Permission Design
- Use `_own` permissions for agent-specific resources
- Implement `_tree` permissions for managers
- Reserve `_all` permissions for platform admins
- Create resource-specific permissions (listing, lead, commission)

### 3. Performance Optimization
- Cache user permissions for 5-10 minutes
- Batch permission checks when loading dashboards
- Use entity context headers to avoid repeated lookups
- Implement pagination for large agent/listing lists

### 4. Security Considerations
- Never expose commission/financial data without explicit permission
- Implement row-level security for sensitive data
- Audit all permission changes and entity modifications
- Use separate permissions for PII access

### 5. Integration Guidelines
- Map existing roles to OutlabsAuth roles during migration
- Maintain bi-directional sync for critical data
- Implement webhook handlers for real-time updates
- Plan for gradual rollout with fallback mechanisms

## Common Scenarios

### Scenario 1: Agent Switching Brokerages
```javascript
await handleAgentBrokerageChange(agentId, newBrokerageId, {
  transferListings: true,
  maintainClientRelationships: true,
  notifyPreviousBrokerage: true
});
```

### Scenario 2: Team Formation
```javascript
await createTeamWithMembers({
  name: 'Downtown Specialists',
  leadAgent: 'agent_123',
  members: ['agent_456', 'agent_789'],
  specialization: 'urban_residential',
  leadDistributionShare: 0.4
});
```

### Scenario 3: Temporary Access
```javascript
await grantTemporaryAccess({
  user_id: 'contractor_123',
  entity_id: officeId,
  permissions: ['listing:view', 'document:upload'],
  expires_at: '2024-12-31T23:59:59Z'
});
```

## Troubleshooting

### Common Issues

1. **Agent can't see listings**
   - Check entity membership
   - Verify `listing:view` permission
   - Ensure listing belongs to accessible entity

2. **Permission denied on update**
   - Verify ownership for `_own` permissions
   - Check entity context for `_tree` permissions
   - Confirm role assignment is active

3. **Lead distribution not working**
   - Verify `lead:distribute` permission
   - Check distribution rules configuration
   - Ensure agents meet recipient criteria

## Next Steps

1. Review [External API Integration Guide](./EXTERNAL_API_INTEGRATION_GUIDE.md) for general patterns
2. See [API Quick Start Guide](./API_QUICK_START_GUIDE.md) for code examples
3. Explore [Platform Setup Guide](./PLATFORM_SETUP_GUIDE.md) for initial configuration
4. Check [ADMIN_ACCESS_LEVELS.md](./ADMIN_ACCESS_LEVELS.md) for admin UI integration