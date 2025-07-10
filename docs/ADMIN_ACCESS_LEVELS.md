# Admin Access Levels

This document outlines how different administrative levels access the OutlabsAuth Admin UI with properly scoped permissions. The system supports multi-level administration where platform users can log into the same admin interface with appropriately restricted views and capabilities.

## Table of Contents
1. [Overview](#overview)
2. [Access Level Hierarchy](#access-level-hierarchy)
3. [System Administrator](#system-administrator)
4. [Platform Administrator](#platform-administrator)
5. [Organization Administrator](#organization-administrator)
6. [Branch Administrator](#branch-administrator)
7. [Team Lead](#team-lead)
8. [Access Groups Administrator](#access-groups-administrator)
9. [UI Adaptation](#ui-adaptation)
10. [Permission Scoping](#permission-scoping)
11. [Implementation Guide](#implementation-guide)

## Overview

The OutlabsAuth Admin UI is designed to serve multiple administrative levels simultaneously. Rather than creating separate admin interfaces for each platform, the same UI adapts based on the logged-in user's permissions and entity context.

### Key Principles
1. **Single Interface, Multiple Views** - One admin UI that adapts to user permissions
2. **Context-Aware Navigation** - Only show accessible entities and features
3. **Permission-Based Rendering** - UI elements appear/disappear based on permissions
4. **Hierarchical Access** - Higher levels can manage lower levels
5. **Data Isolation** - Admins only see data within their scope

## Access Level Hierarchy

```
┌─────────────────────────────────────────────────────┐
│                System Administrator                  │
│        (Full access to all platforms/data)          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│              Platform Administrator                  │
│      (Manage entire platform and its entities)      │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│            Organization Administrator                │
│      (Manage organization and child entities)       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│              Branch Administrator                    │
│        (Manage branch and child entities)           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│                  Team Lead                          │
│          (Manage team members and settings)         │
└─────────────────────────────────────────────────────┘
```

## System Administrator

### Access Scope
- All platforms in the system
- All entities across all platforms
- All users across all platforms
- System-wide configurations

### UI Features Available
```yaml
Dashboard:
  - System-wide metrics
  - Platform health status
  - User growth charts
  - Permission usage analytics

Platforms:
  - Create new platforms
  - Edit platform configurations
  - View all platform hierarchies
  - Manage platform admins

Users:
  - View/edit all users
  - Create users in any platform
  - Assign platform-level roles
  - Reset passwords system-wide

Roles & Permissions:
  - Create system-wide roles
  - Define new permissions
  - View permission inheritance
  - Audit permission usage

Settings:
  - System configuration
  - Email templates
  - Security policies
  - API rate limits
```

### Required Permissions
```
platform:manage_all
user:manage_all
role:manage_all
permission:manage_all
settings:manage_all
audit:view_all
```

## Platform Administrator

### Access Scope
- Their assigned platform only
- All entities within their platform
- All users within their platform
- Platform-specific configurations

### UI Features Available
```yaml
Dashboard:
  - Platform metrics only
  - Entity hierarchy visualization
  - User activity within platform
  - Platform-specific analytics

Organizations:
  - Create organizations
  - Edit organization details
  - View organization hierarchies
  - Assign organization admins

Users:
  - View/edit platform users
  - Create users for platform
  - Assign roles within platform
  - Manage user memberships

Roles & Permissions:
  - Create platform-specific roles
  - Assign existing permissions
  - Cannot create new permissions
  - View role assignments

Settings:
  - Platform configuration
  - Branding/customization
  - Platform-specific rules
  - Integration settings
```

### Required Permissions
```
entity:manage_platform
user:manage_platform
role:manage_platform
membership:manage_platform
settings:manage_platform
audit:view_platform
```

### Example: Diverse Platform Admin
```javascript
// When Diverse admin logs in
const diverseAdmin = {
  platform_id: "diverse_platform_id",
  permissions: [
    "entity:manage_platform",
    "user:manage_platform",
    "role:manage_platform"
  ]
};

// UI shows only:
// - Diverse platform data
// - Organizations under Diverse
// - Users in Diverse platform
// - Roles scoped to Diverse
```

## Organization Administrator

### Access Scope
- Their organization and all child entities
- Users within their organization
- Organization-specific settings

### UI Features Available
```yaml
Dashboard:
  - Organization metrics
  - Branch performance
  - Team statistics
  - User activity

Branches:
  - Create branches
  - Edit branch details
  - Assign branch managers
  - View branch hierarchies

Teams:
  - View all teams
  - Approve team creation
  - Monitor team performance
  - Reassign team members

Users:
  - View/edit org users
  - Create users for org
  - Assign roles within org
  - Transfer between branches

Access Groups:
  - Create org-wide groups
  - Manage group memberships
  - Define access policies
  - Monitor group usage
```

### Required Permissions
```
entity:manage_organization
user:manage_organization
role:assign_organization
membership:manage_organization
report:view_organization
```

### Example: National Realty Corp Admin
```javascript
// When NRC admin logs in
const nrcAdmin = {
  organization_id: "national_realty_corp_id",
  permissions: [
    "entity:manage_organization",
    "user:manage_organization",
    "report:view_organization"
  ]
};

// UI shows only:
// - NRC organization structure
// - Branches under NRC
// - Users in NRC
// - NRC-specific reports
```

## Branch Administrator

### Access Scope
- Their branch and child teams
- Users within their branch
- Branch-specific settings

### UI Features Available
```yaml
Dashboard:
  - Branch metrics
  - Team performance
  - User statistics
  - Activity logs

Teams:
  - Create teams
  - Edit team details
  - Assign team leads
  - Monitor team metrics

Users:
  - View/edit branch users
  - Create users for branch
  - Assign to teams
  - Manage permissions

Reports:
  - Branch performance
  - User activity
  - Team comparisons
  - Export capabilities
```

### Required Permissions
```
entity:manage_branch
user:manage_branch
team:manage_branch
membership:manage_branch
report:view_branch
```

## Team Lead

### Access Scope
- Their team only
- Team members
- Team-specific settings

### UI Features Available
```yaml
Dashboard:
  - Team metrics
  - Member performance
  - Task statistics
  - Activity summary

Members:
  - View team members
  - Request new members
  - Update member roles
  - Remove members

Settings:
  - Team configuration
  - Notification preferences
  - Team workflows
  - Integration settings

Reports:
  - Team performance
  - Member activity
  - Productivity metrics
  - Basic exports
```

### Required Permissions
```
team:manage
member:manage_team
report:view_team
settings:update_team
```

## Access Groups Administrator

### Special Case: Cross-Cutting Permissions
Access groups can have administrators who manage membership across entity boundaries within their allowed scope.

### UI Features Available
```yaml
Access Groups:
  - View assigned groups
  - Add/remove members
  - Update group settings
  - Monitor group activity

Members:
  - Search eligible users
  - Bulk membership updates
  - Set membership duration
  - Export member lists

Permissions:
  - View group permissions
  - Cannot modify permissions
  - See permission inheritance
  - Audit permission usage
```

### Required Permissions
```
access_group:manage_assigned
member:manage_group
audit:view_group
```

## UI Adaptation

### Dynamic Navigation
```typescript
// Navigation adapts based on permissions
function getAdminNavigation(user: User): NavItem[] {
  const nav: NavItem[] = [];
  
  // System admin sees everything
  if (hasPermission(user, 'platform:manage_all')) {
    nav.push({
      label: 'Platforms',
      path: '/admin/platforms',
      icon: 'Globe'
    });
  }
  
  // Platform admin sees organizations
  if (hasPermission(user, 'entity:manage_platform')) {
    nav.push({
      label: 'Organizations',
      path: '/admin/organizations',
      icon: 'Building'
    });
  }
  
  // Organization admin sees branches
  if (hasPermission(user, 'entity:manage_organization')) {
    nav.push({
      label: 'Branches',
      path: '/admin/branches',
      icon: 'GitBranch'
    });
  }
  
  // All admins see users (filtered by scope)
  if (hasAnyPermission(user, [
    'user:manage_all',
    'user:manage_platform',
    'user:manage_organization',
    'user:manage_branch'
  ])) {
    nav.push({
      label: 'Users',
      path: '/admin/users',
      icon: 'Users'
    });
  }
  
  return nav;
}
```

### Context-Aware Data Loading
```typescript
// Data queries adapt to user's scope
async function loadUsers(adminUser: User): Promise<User[]> {
  const filters: UserFilters = {};
  
  if (hasPermission(adminUser, 'user:manage_all')) {
    // No filters - see all users
  } else if (hasPermission(adminUser, 'user:manage_platform')) {
    filters.platform_id = adminUser.platform_id;
  } else if (hasPermission(adminUser, 'user:manage_organization')) {
    filters.organization_id = adminUser.organization_id;
  } else if (hasPermission(adminUser, 'user:manage_branch')) {
    filters.branch_id = adminUser.branch_id;
  } else if (hasPermission(adminUser, 'user:manage_team')) {
    filters.team_id = adminUser.team_id;
  }
  
  return api.getUsers(filters);
}
```

### Permission-Based UI Components
```typescript
// Components render based on permissions
function EntityActions({ entity, user }: Props) {
  return (
    <div className="actions">
      {canEdit(user, entity) && (
        <Button onClick={() => editEntity(entity)}>
          Edit
        </Button>
      )}
      
      {canDelete(user, entity) && (
        <Button onClick={() => deleteEntity(entity)} variant="danger">
          Delete
        </Button>
      )}
      
      {canManageMembers(user, entity) && (
        <Button onClick={() => manageMembers(entity)}>
          Manage Members
        </Button>
      )}
      
      {canViewReports(user, entity) && (
        <Button onClick={() => viewReports(entity)}>
          View Reports
        </Button>
      )}
    </div>
  );
}
```

## Permission Scoping

### Hierarchical Permission Checking
```python
async def check_admin_access(user_id: str, resource_type: str, resource_id: str):
    """
    Check if user has admin access to a resource
    """
    user = await get_user_with_memberships(user_id)
    
    # System admin can access everything
    if has_permission(user, f"{resource_type}:manage_all"):
        return True
    
    # Platform admin can access within platform
    if has_permission(user, f"{resource_type}:manage_platform"):
        resource = await get_resource(resource_type, resource_id)
        return resource.platform_id == user.platform_id
    
    # Organization admin can access within org
    if has_permission(user, f"{resource_type}:manage_organization"):
        resource = await get_resource(resource_type, resource_id)
        return await is_in_organization_hierarchy(resource, user.organization_id)
    
    # Continue checking down the hierarchy...
    return False
```

### Scoped Data Queries
```python
async def get_visible_entities(user_id: str) -> List[Entity]:
    """
    Get all entities visible to an admin user
    """
    user = await get_user_with_permissions(user_id)
    
    if has_permission(user, "entity:view_all"):
        # System admin sees all
        return await Entity.find_all().to_list()
    
    elif has_permission(user, "entity:view_platform"):
        # Platform admin sees platform entities
        return await Entity.find(
            Entity.platform_id == user.platform_id
        ).to_list()
    
    elif has_permission(user, "entity:view_organization"):
        # Org admin sees org and children
        org_ids = await get_organization_hierarchy(user.organization_id)
        return await Entity.find(
            Entity.id.in_(org_ids)
        ).to_list()
    
    # Default: only entities user is member of
    return await get_user_entities(user_id)
```

## Implementation Guide

### Step 1: Define Admin Roles
```python
# In initialization or seed script
admin_roles = [
    {
        "name": "system_admin",
        "display_name": "System Administrator",
        "permissions": [
            "platform:manage_all",
            "user:manage_all",
            "role:manage_all",
            "permission:manage_all",
            "settings:manage_all",
            "audit:view_all"
        ]
    },
    {
        "name": "platform_admin",
        "display_name": "Platform Administrator",
        "permissions": [
            "entity:manage_platform",
            "user:manage_platform",
            "role:manage_platform",
            "membership:manage_platform",
            "settings:manage_platform",
            "audit:view_platform"
        ]
    },
    {
        "name": "organization_admin",
        "display_name": "Organization Administrator",
        "permissions": [
            "entity:manage_organization",
            "user:manage_organization",
            "role:assign_organization",
            "membership:manage_organization",
            "report:view_organization"
        ]
    }
    # ... more roles
]
```

### Step 2: Admin Assignment
```python
async def assign_admin_role(
    user_id: str,
    admin_level: str,
    entity_id: str,
    assigned_by: str
):
    """
    Assign appropriate admin role to user
    """
    # Get the appropriate role
    role = await Role.find_one(Role.name == f"{admin_level}_admin")
    
    # Create membership with admin role
    membership = await EntityMembership.create({
        "user_id": user_id,
        "entity_id": entity_id,
        "role_ids": [role.id],
        "metadata": {
            "admin_level": admin_level,
            "assigned_by": assigned_by,
            "assigned_at": datetime.utcnow()
        }
    })
    
    # Log admin assignment
    await create_audit_log(
        action="admin_assigned",
        user_id=assigned_by,
        target_user=user_id,
        details={"level": admin_level, "entity": entity_id}
    )
    
    return membership
```

### Step 3: UI Route Protection
```typescript
// Protect admin routes based on permissions
const adminRoutes = [
  {
    path: '/admin/platforms',
    component: PlatformsAdmin,
    requiredPermission: 'platform:manage_all'
  },
  {
    path: '/admin/organizations',
    component: OrganizationsAdmin,
    requiredPermission: 'entity:manage_platform'
  },
  {
    path: '/admin/users',
    component: UsersAdmin,
    requiredPermissions: [
      'user:manage_all',
      'user:manage_platform',
      'user:manage_organization'
    ],
    requireAny: true
  }
];

// Route guard component
function AdminRoute({ children, requiredPermissions }) {
  const { user } = useAuth();
  
  if (!hasRequiredPermissions(user, requiredPermissions)) {
    return <AccessDenied />;
  }
  
  return children;
}
```

### Step 4: API Filtering
```python
@router.get("/admin/entities")
async def get_admin_entities(
    current_user: User = Depends(get_current_user),
    filters: EntityFilters = Depends()
):
    """
    Get entities based on admin's access level
    """
    # Apply automatic scoping based on permissions
    query = Entity.find()
    
    if not has_permission(current_user, "entity:view_all"):
        if has_permission(current_user, "entity:view_platform"):
            query = query.find(Entity.platform_id == current_user.platform_id)
        elif has_permission(current_user, "entity:view_organization"):
            org_ids = await get_user_organization_hierarchy(current_user.id)
            query = query.find(Entity.id.in_(org_ids))
        else:
            # Only show entities user is member of
            entity_ids = await get_user_entity_ids(current_user.id)
            query = query.find(Entity.id.in_(entity_ids))
    
    # Apply additional filters
    if filters.entity_type:
        query = query.find(Entity.entity_type == filters.entity_type)
    
    return await query.to_list()
```

## Best Practices

### 1. Permission Naming
- Use consistent hierarchical naming: `resource:action_scope`
- Examples: `user:manage_all`, `user:manage_platform`, `user:manage_organization`

### 2. UI Adaptation
- Always check permissions before rendering UI elements
- Provide clear feedback when access is denied
- Show why certain features are unavailable

### 3. Data Security
- Apply permission checks at API level, not just UI
- Use database-level filtering for performance
- Log all admin actions for audit trail

### 4. Performance
- Cache permission checks for admin users
- Use indexed queries for entity hierarchy lookups
- Batch permission checks when possible

### 5. User Experience
- Provide role-appropriate dashboards
- Customize navigation based on access level
- Show contextual help based on permissions

## Common Scenarios

### Scenario 1: Platform Admin Managing Their Platform
```
1. Diverse admin logs into OutlabsAuth Admin UI
2. UI recognizes platform admin permissions
3. Navigation shows only platform-relevant sections
4. All queries automatically filtered to Diverse platform
5. Can create orgs, assign roles, manage users within Diverse
6. Cannot see or affect other platforms
```

### Scenario 2: Organization Admin Self-Service
```
1. National Realty Corp admin logs in
2. Sees organization-focused dashboard
3. Can manage branches and teams under NRC
4. Can view all NRC users and their roles
5. Can run reports for NRC entities only
6. Cannot modify platform-level settings
```

### Scenario 3: Team Lead Administration
```
1. Team lead logs into admin UI
2. Sees simplified team management interface
3. Can add/remove team members
4. Can view team performance metrics
5. Can update team settings
6. Cannot create new teams or modify roles
```

## Security Considerations

### 1. Permission Escalation Prevention
- Users cannot grant permissions they don't have
- Role assignments validated against assigner's permissions
- Audit trail for all permission changes

### 2. Cross-Platform Isolation
- Strict platform_id filtering at database level
- API-level validation of platform context
- No shared resources between platforms

### 3. Admin Action Auditing
```python
@audit_action("admin_action")
async def perform_admin_action(
    action: str,
    target: str,
    admin_user: User
):
    # All admin actions are logged
    return await audit_log.create({
        "action": action,
        "admin_user_id": admin_user.id,
        "admin_level": get_admin_level(admin_user),
        "target": target,
        "timestamp": datetime.utcnow(),
        "ip_address": get_client_ip(),
        "user_agent": get_user_agent()
    })
```

## Summary

The multi-level admin access system allows OutlabsAuth to serve as a unified administrative interface for all stakeholders while maintaining proper security boundaries. By using permission-based UI adaptation and context-aware data filtering, the same codebase can provide appropriate administrative capabilities to system admins, platform admins, organization admins, and team leads.

This approach provides:
- **Flexibility**: One system serves all admin needs
- **Security**: Strict permission enforcement at all levels
- **Scalability**: Efficient permission checking and data filtering
- **Usability**: Context-appropriate UI for each admin level
- **Maintainability**: Single codebase to maintain and deploy