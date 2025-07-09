# Frontend Migration Plan for outlabsAuth

## Overview

The admin-ui frontend was built for a previous version of the outlabsAuth system. This document outlines the plan to migrate and update the frontend to work with the new unified entity model and hybrid authorization system.

## Current State Assessment

### What We Have
- **Tech Stack**: React 19 RC, TypeScript, Vite, TanStack Router/Query/Form, Zustand, ShadCN UI
- **Completed Features**: 
  - Authentication flow (login/logout)
  - Dashboard with sidebar navigation
  - Basic routing structure
  - Email settings management
  - Platform management UI (needs migration to entities)
  - Role management UI (partially complete)
  - Permission management UI (partially complete)

### TypeScript Errors
1. Missing UI components (`alert-dialog`, `select`)
2. Type mismatches between old and new API models
3. Unused imports
4. Missing dependency (`react-hook-form`)

### API Endpoint Mismatches
| Old Endpoint | New Endpoint | Notes |
|--------------|--------------|-------|
| `/v1/platforms/` | `/v1/entities/` | Platforms are now entities with type "platform" |
| `/v1/client_accounts/` | `/v1/entities/` | Client accounts are entities with type "organization" |
| Platform-specific fields | Entity model fields | Need to map old platform fields to new entity structure |

## Migration Strategy

### Phase 1: Fix Build Issues (1-2 days)
- [ ] Install missing dependencies (`react-hook-form`)
- [ ] Add missing ShadCN components (`alert-dialog`, `select`)
- [ ] Fix TypeScript type definitions
- [ ] Remove unused imports
- [ ] Update type interfaces to match new API models

### Phase 2: Update API Integration (2-3 days)
- [ ] Create new API type definitions matching backend models
- [ ] Update all API endpoints to match new backend
- [ ] Implement entity-based management instead of platforms
- [ ] Update authentication to work with new permission system
- [ ] Add support for conditional permissions (ABAC)

### Phase 3: Entity Management (3-4 days)
- [ ] Convert platform management to entity management
- [ ] Implement entity hierarchy visualization
- [ ] Add entity type selection (platform, organization, branch, team)
- [ ] Implement parent-child relationship management
- [ ] Add entity membership management

### Phase 4: Permission Builder UI (3-4 days)
- [ ] Implement the Permission Builder UI as designed in documentation
- [ ] Add condition builder for ABAC rules
- [ ] Create attribute selector with namespaces (user.*, resource.*, etc.)
- [ ] Add operator selection based on attribute type
- [ ] Implement real-time permission testing

### Phase 5: Enhanced User Management (2-3 days)
- [ ] Update user list to show entity memberships
- [ ] Add entity context switcher
- [ ] Implement user invitation flow
- [ ] Add bulk operations
- [ ] Show user permissions in context

### Phase 6: Role Management Updates (2 days)
- [ ] Update role creation with new permission model
- [ ] Add conditional permission assignment
- [ ] Implement role templates
- [ ] Add role usage analytics

### Phase 7: Testing & Polish (2-3 days)
- [ ] Add error boundaries
- [ ] Implement proper loading states
- [ ] Add toast notifications for all operations
- [ ] Test all CRUD operations
- [ ] Verify permission checks work correctly

## Component Reusability Assessment

### Fully Reusable
- ✅ Authentication components (login form, auth store)
- ✅ Layout components (sidebar, breadcrumbs, navigation)
- ✅ UI components (all ShadCN components)
- ✅ Theme system
- ✅ Routing structure

### Needs Minor Updates
- ⚠️ User components (add entity context)
- ⚠️ Role components (add conditional permissions)
- ⚠️ Dashboard (update stats to reflect entities)

### Needs Major Rewrite
- ❌ Platform components → Entity components
- ❌ Permission components (add ABAC support)
- ❌ Client account components → Entity organization type

## New Components Needed

### 1. Entity Components
- `EntityList` - Display entities with hierarchy
- `EntityTree` - Visualize entity relationships
- `EntityForm` - Create/edit entities
- `EntityMembershipManager` - Manage entity members

### 2. Permission Components
- `PermissionBuilder` - Visual permission creator with conditions
- `ConditionBuilder` - ABAC condition editor
- `AttributeSelector` - Attribute path selector
- `PermissionTester` - Test permissions with context

### 3. Shared Components
- `EntitySelector` - Dropdown to select entity context
- `PermissionBadge` - Display permission with conditions
- `EntityBreadcrumb` - Show entity hierarchy path

## API Type Definitions Needed

```typescript
// Entity types
interface Entity {
  id: string;
  name: string;
  display_name: string;
  entity_type: 'platform' | 'organization' | 'branch' | 'team';
  parent_entity_id?: string;
  hierarchy_level: number;
  is_active: boolean;
  settings: Record<string, any>;
  member_count: number;
  created_at: string;
  updated_at: string;
}

// Permission types
interface Condition {
  attribute: string;
  operator: OperatorType;
  value: any;
}

interface Permission {
  id?: string;
  name: string;
  display_name: string;
  description?: string;
  resource: string;
  action: string;
  conditions: Condition[];
  is_system: boolean;
  is_active: boolean;
  tags: string[];
}

// User types with entity context
interface UserWithMembership {
  id: string;
  email: string;
  profile: UserProfile;
  memberships: EntityMembership[];
}
```

## Implementation Priority

1. **Critical Path** (Must have for basic functionality):
   - Fix build errors
   - Update authentication flow
   - Entity management (replacing platforms)
   - Basic user management

2. **High Priority** (Core features):
   - Permission Builder UI
   - Role management with conditions
   - Entity membership management

3. **Medium Priority** (Enhanced UX):
   - Entity hierarchy visualization
   - Permission testing interface
   - Bulk operations

4. **Nice to Have** (Future enhancements):
   - Analytics dashboards
   - Audit log viewer
   - Advanced search

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API contract changes | High | Create API adapter layer |
| Complex permission UI | Medium | Start with simple UI, progressively enhance |
| Entity hierarchy complexity | Medium | Limit depth, provide clear visualization |
| Performance with large datasets | Low | Implement pagination and virtual scrolling |

## Success Criteria

- [ ] All TypeScript errors resolved
- [ ] Frontend builds successfully
- [ ] Authentication flow works with new backend
- [ ] Entity CRUD operations functional
- [ ] Permission Builder creates conditional permissions
- [ ] User can test permissions with resource context
- [ ] All features from old system migrated or replaced

## Timeline Estimate

- **Total Duration**: 15-20 days
- **Phase 1-2**: 3-5 days (Foundation)
- **Phase 3-4**: 6-8 days (Core Features)
- **Phase 5-7**: 6-7 days (Enhancement & Polish)

## Next Steps

1. Install missing dependencies
2. Add missing ShadCN components
3. Create type definition files for new API
4. Start updating API endpoints in existing components
5. Build Entity management components

## Notes

- Keep backward compatibility where possible
- Use feature flags for gradual rollout
- Maintain consistent UX patterns
- Document all new components
- Add Storybook for component development (optional)