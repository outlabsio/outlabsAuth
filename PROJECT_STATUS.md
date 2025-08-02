# outlabsAuth Project Status

**Last Updated**: 2025-08-02

This file tracks the current implementation status of the outlabsAuth unified entity model system.

## Critical Updates (2025-08-01)

### 🚨 API-to-API Authentication Gaps - NEEDS IMPLEMENTATION

We've identified critical gaps in server-to-server authentication that need to be addressed before production deployment:

**Missing Components**:
1. **API Key Authentication**: 
   - Utility functions exist (`create_api_key`, `hash_api_key`) but no complete implementation
   - No middleware to validate API keys in request headers
   - No API key storage/management system
   - No rate limiting per API key

2. **Service Accounts/Platform Users**:
   - `is_system_user` flag exists but not utilized
   - No platform-level service accounts for API authentication
   - No way to create/manage service accounts
   - No platform-scoped permissions for service accounts

3. **OAuth/SSO Integration**:
   - No support for external auth providers (Google, GitHub, Microsoft)
   - No OAuth flow implementation
   - No user provisioning from OAuth identities
   - No mapping of external identities to OutlabsAuth users

4. **Proxy Authentication Pattern**:
   - No documented pattern for frontend → platform API → OutlabsAuth
   - No support for dual authentication (API key + user context)
   - No examples of passing user context in API-to-API calls

**Architectural Decisions Made**:
1. **Proxy Pattern as Primary Integration**: Frontends should authenticate through their platform's API, not directly with OutlabsAuth
2. **Platform-Managed OAuth**: Each platform (e.g., Property Hub) handles its own OAuth providers and provisions users via API
3. **Hybrid Authentication**: API calls use platform API key + optional user JWT for context

**Impact**:
- External platforms cannot securely integrate without API key authentication
- No way for platforms to perform administrative operations via API
- OAuth integration requires each platform to implement their own solution

**Next Steps**:
- Implement API key authentication middleware
- Create service account management system
- Document proxy authentication patterns
- Create OAuth integration guidelines for platforms

## Recent Updates (2025-08-02)

### ✅ User Status System Implementation - COMPLETED

We've implemented a comprehensive user status system replacing the simple boolean `is_active` field:

**What Changed**:
- ✅ Added `UserStatus` enum with values: ACTIVE, INACTIVE, SUSPENDED, BANNED, TERMINATED
- ✅ Updated `UserModel` to use `status: UserStatus` field instead of `is_active: bool`
- ✅ Updated authentication logic - only ACTIVE and SUSPENDED users can authenticate
- ✅ Updated all API endpoints, schemas, and services to use the new status system
- ✅ Updated frontend to display status badges and provide status management UI
- ✅ Maintained backward compatibility for EntityMembership which still uses `is_active: bool`

**Key Features**:
- Users can have granular statuses with specific behaviors
- SUSPENDED users can still authenticate (for time-restricted access scenarios)
- TERMINATED users cannot have their status changed (permanent state)
- Frontend displays color-coded status badges (green=active, yellow=suspended, red=banned/terminated)
- Bulk status updates supported via API

### ✅ Context-Aware Role System - FULLY IMPLEMENTED (2025-08-02)

We've fully implemented a powerful context-aware role system that allows roles to have different permissions based on WHERE they are assigned in the entity hierarchy:

**Backend Implementation**:
- ✅ Added `entity_type_permissions: Optional[Dict[str, List[str]]]` field to RoleModel
- ✅ Updated RoleCreate, RoleUpdate, and RoleResponse schemas with validation
- ✅ Modified RoleService to handle entity_type_permissions in create and update operations
- ✅ All role endpoints properly pass and return entity_type_permissions
- ✅ Permission resolution automatically checks entity type and applies context-specific permissions
- ✅ Updated seed script to use RoleService for context-aware roles (Regional Manager, Tech Lead)

**Frontend Implementation**:
- ✅ Updated Role TypeScript interface with `entity_type_permissions?: Record<string, string[]>`
- ✅ Role store's createRole and updateRole methods handle entity_type_permissions
- ✅ Role form component includes comprehensive context-aware permission editor:
  - **Tabbed interface** for organizing role settings (Basic Info, Scope, Permissions, Context Settings)
  - **Accordion-style entity sections** - only one entity type expanded at a time
  - **Streamlined permission selector** with single filter box and "show selected only" toggle
  - **Compact, clean design** using Nuxt UI v3 semantic color tokens
  - **Visual indicators** showing permission customization per entity type
  - **Real-time permission filtering** for better UX

**UI/UX Improvements** (2025-08-02):
- ✅ Reorganized role form into tabs for better information architecture
- ✅ Removed complexity: no quick templates or smart suggestions
- ✅ Improved permission selector with:
  - Single filter input instead of multiple dropdowns
  - Toggle to show only selected permissions
  - Compact list design with proper semantic colors
  - Groups start collapsed for cleaner initial view
- ✅ Fixed all hardcoded colors to use Nuxt UI v3's semantic design tokens
- ✅ Proper dark mode support throughout the interface

**Testing & Verification**:
- ✅ Successfully created context-aware role via API with different permissions per entity type
- ✅ Effective permissions endpoint correctly shows permission sources and context application
- ✅ System maintains backward compatibility - existing roles work unchanged
- ⚠️ Frontend UI implemented but not yet tested with actual role creation/updates

**Documentation**:
- ✅ Full design documentation in [Entity Type Role System Design](docs/ENTITY_TYPE_ROLE_SYSTEM_DESIGN.md)
- ✅ Migration guide in [Context-Aware Roles Migration](docs/MIGRATION_GUIDE_CONTEXT_AWARE_ROLES.md)

**How It Works**:
```python
# One role adapts based on assignment context
branch_manager_role = RoleModel(
    name="branch_manager",
    permissions=["entity:read", "user:read"],  # Default/fallback
    entity_type_permissions={
        "organization": ["entity:manage_tree", "user:manage_tree", "budget:approve"],
        "branch": ["entity:manage", "user:manage", "lead:distribute"],
        "team": ["entity:read", "user:read", "report:view"]
    }
)
```

**Benefits**:
- Eliminates role explosion (no more branch_manager_full, branch_manager_limited, etc.)
- Matches real organizational behavior (authority changes with context)
- Backward compatible - existing roles work unchanged
- Supports gradual migration - add context awareness as needed

**Real-World Use Cases**:
- **Diverse Platform**: Branch Manager has full control at branch level, advisory role at team level
- **qdarte Platform**: Campaign Manager has different permissions for clients vs influencers
- **Referral Brokerage**: Agent role evolves from solo permissions to team management when they create a team

**API Example - Creating a Context-Aware Role**:
```bash
curl -X POST http://localhost:8030/v1/roles/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_context_aware_role",
    "display_name": "Test Context Aware Role",
    "description": "A test role with context-aware permissions",
    "permissions": ["entity:read", "user:read"],
    "entity_type_permissions": {
      "organization": [
        "entity:create", "entity:read", "entity:update", "entity:delete",
        "user:create", "user:read", "user:update", "user:delete",
        "role:create", "role:read", "role:update", "role:delete"
      ],
      "branch": ["entity:read", "entity:update", "user:read", "user:update"],
      "team": ["entity:read", "user:read"]
    },
    "assignable_at_types": ["organization", "branch", "team"],
    "is_global": false
  }'
```

### ✅ Effective Permissions Endpoint - IMPLEMENTED (2025-08-02)

We've implemented a comprehensive effective permissions endpoint that shows exactly what permissions a user has on an entity and WHY they have them:

**Endpoint**: `GET /v1/permissions/users/{user_id}/effective-permissions?entity_id={entity_id}`

**Features**:
- Shows all permissions a user has at an entity
- Traces the source of each permission (role, entity, inheritance)
- Identifies context-aware permission application
- Shows inheritance from parent entities with tree permissions
- Includes detailed metadata about permission sources

**Response Example**:
```json
{
  "user_id": "user-123",
  "user_email": "john.doe@example.com",
  "entity_id": "miami-office",
  "entity_name": "Miami Branch",
  "entity_type": "branch",
  "effective_permissions": ["entity:read", "entity:update", "user:read"],
  "permission_sources": [
    {
      "permission": "entity:read",
      "source": "role:branch_manager",
      "context": "direct_assignment",
      "entity": "Miami Branch",
      "entity_id": "miami-office",
      "role_name": "Branch Manager",
      "is_context_aware": true,
      "applied_from_type": "branch"
    },
    {
      "permission": "user:read",
      "source": "inherited:role",
      "context": "inherited_from_parent",
      "entity": "Florida Division",
      "entity_id": "florida-div",
      "parent_permission": "user:read_tree",
      "inheritance_depth": 1
    }
  ]
}
```

## 🚀 Upcoming Enhancements - IN PLANNING

Based on architectural review and feedback, we're planning the following enhancements to make the system more robust and easier to debug:

### 2. **Optional Platform Schema** (MEDIUM PRIORITY)

**What**: Optional validation rules that platforms can define for their entity structures.

**Why We Need It**:
- Prevents configuration errors (e.g., creating a team as child of another team)
- Self-documenting - new admins can see valid entity types
- Maintains flexibility - schema is optional, not required
- Soft validation with warnings by default

**Planned Implementation**:
```python
class PlatformSchema(BaseModel):
    entity_types: Optional[List[str]] = None  # Valid types
    valid_parentage: Optional[Dict[str, List[str]]] = None  # Nesting rules
    enforcement_mode: str = "warn"  # "warn" or "strict"
    
# Example for Diverse platform
{
    "entity_types": ["organization", "branch", "team", "agent_team"],
    "valid_parentage": {
        "organization": ["platform"],
        "branch": ["organization"],
        "team": ["branch", "organization"],
        "agent_team": ["platform", "organization", "branch"]
    }
}
```

### 3. **Granular Permission Inheritance Control** (MEDIUM PRIORITY)

**What**: Add control over which permissions flow down the entity hierarchy.

**Why We Need It**:
- Some permissions should not inherit (e.g., budget approval)
- Provides more precise control over permission flow
- Reduces unintended permission grants
- Makes permission model more predictable

**Planned Implementation**:
```python
class RoleModel:
    # Existing fields...
    
    # New field - if None, all permissions inherit (current behavior)
    inheritable_permissions: Optional[List[str]] = None
    
# Example: Only some permissions inherit to children
role = RoleModel(
    name="division_head",
    permissions=["budget:approve", "entity:manage", "user:read"],
    inheritable_permissions=["entity:manage", "user:read"]  # budget:approve doesn't inherit
)
```

### 4. **Enhanced Documentation** (LOW PRIORITY)

**What**: Improve clarity around STRUCTURAL vs ACCESS_GROUP entities.

**Why We Need It**:
- The distinction exists but isn't well documented
- New developers need clearer guidance
- Reduce configuration errors

**Planned Updates**:
- Visual diagrams showing inheritance paths
- Decision tree for choosing entity class
- More real-world examples

## 📋 Development TODO List

### High Priority Tasks

1. **Implement Effective Permissions Endpoint** ✅ COMPLETED
   - [x] Create new route handler in permission_routes.py
   - [x] Add permission source tracking to permission_service.py
   - [x] Implement response schema with derivation details
   - [x] Add caching for performance (uses existing cache)
   - [x] Add API documentation
   - [ ] Write comprehensive tests

2. **Fix API-to-API Authentication** (from earlier section)
   - [ ] Implement API key middleware
   - [ ] Create service account management
   - [ ] Document proxy patterns

### Medium Priority Tasks

3. **Implement Optional Platform Schema**
   - [ ] Create PlatformSchema model
   - [ ] Add schema field to platform entities
   - [ ] Implement validation service with warn/strict modes
   - [ ] Add schema management endpoints
   - [ ] Create migration for existing platforms
   - [ ] Write tests for validation logic

4. **Add Permission Inheritance Control**
   - [ ] Add inheritable_permissions field to RoleModel
   - [ ] Update permission resolution logic
   - [ ] Maintain backward compatibility
   - [ ] Add tests for inheritance scenarios
   - [ ] Update seed data with examples

5. **Frontend Updates for Context-Aware Roles** ✅ COMPLETED
   - [x] Update role creation form to support entity_type_permissions
   - [x] Add UI for defining context-specific permissions
   - [x] Visual indicator showing how role behaves at different entity types
   - [x] Update role list to show context awareness
   - [x] Implement tabbed interface for better organization
   - [x] Add accordion behavior for entity sections
   - [x] Streamline permission selector with single filter
   - [x] Add "show selected only" toggle for filtering
   - [x] Remove complexity (templates, suggestions)
   - [x] Update all components to use Nuxt UI v3 semantic colors
   - [ ] Test actual role creation/update with new UI

### Low Priority Tasks

6. **Documentation Improvements**
   - [ ] Create visual diagrams for entity classes
   - [ ] Add decision tree for STRUCTURAL vs ACCESS_GROUP
   - [ ] More platform scenario examples
   - [ ] Video tutorials for complex features

7. **Testing Improvements**
   - [ ] Add tests for context-aware role resolution
   - [ ] Performance tests for effective permissions endpoint
   - [ ] Integration tests for platform schema validation

## Recent Updates (2025-07-22)

### ✅ Standardized Permission System to CRUD - COMPLETED

We've successfully standardized all system permissions to use consistent CRUD operations:

**What Changed**:
- ✅ Replaced `member:add` → `member:create` and `member:remove` → `member:delete` for consistency
- ✅ Removed unused `role:assign` permission (role assignment happens through membership)
- ✅ Updated all API routes, services, and tests to use new permission names
- ✅ Maintained only one domain-specific permission: `user:invite` (compound operation)

**Benefits**:
- Consistent CRUD pattern across all resources (entity, user, role, member, permission)
- Reduced cognitive load - easier to remember permission names
- Cleaner, more predictable permission model
- Better alignment with REST API conventions

### 🔧 Testing Suite Improvements - IN PROGRESS

We've significantly improved the testing suite and identified remaining issues:

**Current Status**: 230/243 tests passing (94.7%)
- ✅ Core test suite: 126/126 tests passing (100%)
- ✅ Complex scenarios: 35/35 tests passing (100%)
- ✅ Permission enforcement: 25/29 tests passing (86.2%)
- ⚠️ Security tests: 36/45 tests passing (80%)

**Key Improvements**:
- ✅ Fixed all compound "manage" permission references
- ✅ Added permission enforcement tests to main suite
- ✅ Added complex scenario tests to main suite
- ✅ Fixed member permission naming inconsistencies
- ✅ Security test suite now included with proper error handling

**Remaining Issues**:
1. **Password Validation** (4 failures): Weak passwords like "password123" are being accepted
2. **Injection Protection** (5 failures): Entity names with SQL/NoSQL injection payloads not being sanitized
3. **Tree Permission Visibility** (4 failures): Entity lists not showing descendants with _tree permissions

## Recent Updates (2025-07-22)

### ✅ Removed All Compound "Manage" Permissions - COMPLETED

We've successfully removed all compound "manage" permissions from the system to provide more transparent and granular access control:

**What Changed**:
- ✅ Removed all compound permissions from SYSTEM_PERMISSIONS (e.g., `entity:manage`, `user:manage`, `role:manage`)
- ✅ Removed permission hierarchy expansion logic that automatically granted sub-permissions
- ✅ Updated all route dependencies to use specific permissions instead of compound ones
- ✅ Updated system initialization to use individual permissions in default roles
- ✅ Updated all documentation to reflect the new permission model

**Key Changes**:
1. **Permission Service**: Removed permission hierarchy that expanded `manage` to include other actions
2. **Dependencies**: Removed `require_user_manage`, `require_role_manage`, `require_member_manage`
3. **Routes**: All endpoints now check for specific permissions (e.g., `user:create` instead of `user:manage`)
4. **System Roles**: Updated to explicitly list all required permissions
5. **Documentation**: Updated to explain that permissions must be explicitly granted

**Benefits**:
- More transparent permission model - it's clear exactly what permissions are granted
- Better security - no hidden permission expansions
- Easier to audit - each permission stands alone
- More flexible - can grant update without delete, etc.

## Recent Updates (2025-07-22)

### ✅ Enterprise Testing Requirements - SECURITY UPDATES COMPLETED

Completed critical security improvements from enterprise testing requirements:

- ✅ **Password Policy Enforcement**: Implemented strong password requirements (uppercase, lowercase, digit, special character)
- ✅ **Input Validation**: Entity names now sanitized to prevent SQL/NoSQL injection attacks
- ✅ **Test Suite Health**: All 236 tests passing (100% pass rate)
- ✅ **Permission Model**: Standardized all system permissions to use CRUD operations
- ✅ **Entity Visibility**: Fixed entity list endpoints to properly show descendant entities for users with _tree permissions

### ✅ Tree Permissions for Entity Operations - FULLY IMPLEMENTED (2025-07-21)

We've successfully fixed and completed tree permission support for entity create/update operations:

**What's Working**:
- ✅ Entity creation with tree permissions - Users with `entity:create_tree` in a parent can create child entities
- ✅ Entity updates with tree permissions - Users with `entity:update_tree` in a parent can update child entities
- ✅ Platform admins can now correctly update child organizations with `entity:update_tree` permission
- ✅ Tree permission checking traverses full entity hierarchy (checks all ancestors)
- ✅ Member management with tree permissions fully functional
- ✅ Deep hierarchy support - permissions work through any depth
- ✅ All 126 core tests passing
- ✅ Complex scenario tests improved from 32/35 (91.4%) to 35/35 (100%) passing

**Recently Fixed Issues**:
- ✅ Fixed array slicing bug in permission_service.py that was checking wrong entities in hierarchy
- ✅ Fixed role link dereferencing to properly handle Beanie Link objects
- ✅ Added circular hierarchy prevention to avoid infinite loops
- ✅ Updated test fixtures for pytest-based tests

**Additional Fixes**:
- ✅ Fixed test expectations to correctly understand tree permission behavior
- ✅ Clarified that tree permissions apply to descendants only, not the entity where assigned
- ✅ Added comprehensive documentation:
  - [Tree Permissions Guide](docs/TREE_PERMISSIONS_GUIDE.md) - Detailed explanation of tree permission behavior
  - [Permission Visual Examples](docs/PERMISSION_VISUAL_EXAMPLES.md) - Visual diagrams and real-world scenarios

**Security Improvements (2025-07-22)**:
- ✅ Added password validation to all password fields requiring uppercase, lowercase, digit, and special character
- ✅ Implemented entity name sanitization to prevent injection attacks
- ✅ Standardized all member permissions from add/remove to create/delete for consistency
- ✅ Removed obsolete role:assign permissions in favor of member:update

**Implementation Details**:
- Fixed `entity_path[:-1]` in permission_service.py to correctly check parent entities
- Added proper handling for both populated roles and Link objects in permission resolution
- Implemented `_check_circular_hierarchy` method in entity_service.py
- Tree permissions now work correctly at any depth in the hierarchy

### ✅ New Permission Scoping Model - FULLY IMPLEMENTED

We've successfully implemented a new hierarchical permission scoping model to replace the previous flat permission system:

**Three-Tier Permission Scoping**:
1. **Entity-Specific** (`resource:action`) - Access only the specific entity
2. **Hierarchical** (`resource:action_tree`) - Access entity and all descendants
3. **Platform-Wide** (`resource:action_all`) - Access all entities in platform

**Implementation Details**:
- ✅ System permissions updated to include _tree variants for all resources
- ✅ Permission checking logic handles hierarchical inheritance through entity tree
- ✅ System initialization roles use appropriate _tree permissions
- ✅ Entity visibility in search/list endpoints respects _tree permissions
- ✅ Removed composite `entity:manage` permission in favor of specific actions
- ✅ All permission enforcement tests passing (25/25 tests)

**Benefits**:
- Clear, explicit permission intent
- Flexible access control at any organizational level
- Backward compatible with existing entity-specific permissions
- Supports both strict and inherited access models
- Entity lists now properly show descendant entities for users with _tree permissions

## Project Overview

outlabsAuth is an enterprise-grade Role-Based Access Control (RBAC) authentication platform that has successfully implemented the **Unified Entity Model** architecture. The system provides centralized authentication and authorization for multiple platforms through a flexible entity system where everything is an entity, classified as either STRUCTURAL (organizational hierarchy) or ACCESS_GROUP (flexible collections).

## Current Architecture

### Backend
- **Framework**: FastAPI with async/await throughout
- **Database**: MongoDB with Beanie ODM
- **Cache**: Redis for permission caching (5-minute TTL)
- **Authentication**: JWT tokens (access: 15min, refresh: 30 days)
- **API**: RESTful API running on port 8030
- **Email**: Async email service with Jinja2 templates

### Frontend
- **Framework**: Nuxt 3.16.2 (Vue 3) - SPA mode
- **UI Library**: Nuxt UI Pro v3 with Tailwind CSS v4
- **State Management**: Pinia stores for all state and API calls
- **Forms**: Nuxt UI forms with Zod validation
- **Authentication**: Custom JWT implementation with automatic refresh
- **Build Tool**: Vite
- **Package Manager**: npm/yarn (Bun recommended)

## Implementation Status

### ✅ Unified Entity Model (COMPLETED)

The core innovation of the system - everything is an entity:

**Entity Classes**:
- `STRUCTURAL`: Forms organizational hierarchy (platform, organization, division, branch, team)
- `ACCESS_GROUP`: Flexible collections (functional_group, permission_group, project_group, role_group)

**Key Features Implemented**:
- ✅ No separate groups table - everything is an entity
- ✅ Flexible entity types (strings, not enums) allowing custom terminology
- ✅ Hierarchical entity relationships with depth validation
- ✅ Time-based entity validity (valid_from/valid_until)
- ✅ Entity membership with role assignments
- ✅ Direct permissions on entities
- ✅ Metadata support for custom fields
- ✅ Capacity limits (max_members)

### ✅ Backend Implementation (COMPLETED)

#### Core Services
- ✅ **Authentication Service**: Complete JWT auth with refresh token rotation
- ✅ **Entity Service**: Full CRUD with hierarchy validation
- ✅ **Entity Membership Service**: Member management with role assignments
- ✅ **Permission Service**: Hierarchical permission resolution with caching
- ✅ **Role Service**: Role templates and custom roles per entity
- ✅ **User Service**: User management, invitations, bulk operations
- ✅ **Email Service**: Async email processing with templates

#### API Endpoints
All planned endpoints are implemented and working:
- `/v1/auth/*` - Authentication endpoints
- `/v1/entities/*` - Entity management 
- `/v1/roles/*` - Role management
- `/v1/permissions/*` - Permission management
- `/v1/users/*` - User management

#### Advanced Features
- ✅ Hybrid Authorization Model (RBAC + ReBAC + ABAC)
- ✅ Conditional permissions with attribute-based rules
- ✅ Redis caching for performance
- ✅ Background email processing
- ✅ Rate limiting on auth endpoints
- ✅ Comprehensive error handling

### ✅ Frontend Implementation (85% COMPLETED)

#### Implemented Pages & Features
- ✅ **Authentication**: Login, signup, password reset, email verification
- ✅ **Dashboard**: Main dashboard with navigation
- ✅ **Entity Management**: 
  - Full support for unified entity model
  - Create/edit both structural entities and access groups
  - Entity tree visualization
  - Flexible entity type system with autocomplete
  - Parent entity selection with validation
- ✅ **User Management**: List, create, edit, invite users
- ✅ **Role Management**: Create and assign roles at entity level
- ✅ **Permission Management**: View and manage permissions
- ✅ **Context System**: Switch between system and organization context

#### Frontend Architecture
- ✅ All API calls go through `authStore.apiCall()` for centralized auth
- ✅ Pinia stores handle all state and API communication
- ✅ Automatic token refresh on 401 errors
- ✅ Context-aware requests (system vs organization level)
- ✅ Full TypeScript support with proper types
- ✅ Responsive UI with Nuxt UI Pro components

#### Missing Frontend Features
- ❌ Platform management UI
- ❌ System settings/configuration pages
- ❌ Audit log viewer
- ❌ User profile/preferences page
- ❌ Conditional permissions UI builder
- ❌ Bulk operations UI
- ❌ Advanced analytics dashboard

### 📊 Overall Project Completion

- **Backend Core**: 100% ✅
- **Backend Advanced**: 90% ✅ (MFA and OAuth2 pending)
- **Frontend Core**: 85% ✅
- **Frontend Advanced**: 20% 🔄
- **Documentation**: 70% ⚠️ (needs updates for Nuxt frontend)
- **Testing**: 60% 🔄 (backend tests exist, frontend tests needed)

## Quick Start

```bash
# Backend (requires Docker)
docker compose up -d
# API available at http://localhost:8030
# API docs at http://localhost:8030/docs

# Frontend (requires Node.js)
cd frontend
npm install  # or yarn/pnpm/bun
npm run dev
# Frontend available at http://localhost:3000
```

## Test Users (Seeded)

```bash
# Seed the database
docker compose exec api python /app/scripts/seed_database.py --clear

# Test accounts
system@outlabs.com / outlabs123    # System admin
platform@outlabs.com / platform123  # Platform admin
org@outlabs.com / org123           # Organization admin
team@outlabs.com / team123         # Team lead
user@outlabs.com / user123         # Regular user
viewer@outlabs.com / viewer123     # Read-only
```

## Key Differences from Original Plan

### ✅ Improvements
1. **Flexible Entity Types**: Instead of fixed enums, entity types are strings allowing platforms to use their own terminology
2. **Advanced Authorization**: Hybrid RBAC + ReBAC + ABAC model with conditional permissions
3. **Performance**: Redis caching and optimized queries
4. **Better UX**: Entity type autocomplete, context switching, responsive design

### 🔄 Technology Stack
1. **Frontend**: Nuxt 3 + Vue 3 with Composition API
2. **State Management**: Pinia stores for all state and API calls
3. **UI Library**: Nuxt UI Pro v3 premium components
4. **API Calls**: Centralized through auth store with automatic token refresh

## Known Issues

### High Priority Issues
1. ~~**Entity Update Tree Permissions**: The `require_entity_update_with_tree` dependency is not correctly checking parent entity permissions in all cases. Platform admins with `entity:update_tree` at platform level cannot update child organizations.~~ ✅ FIXED
2. ~~**Test Failures**: Complex scenario tests show 3 failures (out of 35) related to entity updates with tree permissions.~~ ✅ FIXED - All tests passing

### Medium Priority Issues
1. **Documentation Updates**: Some code examples need to be converted to Vue 3 syntax
2. **Uncommitted Changes**: Several form components have pending changes
3. **Package Manager**: Using npm but Bun is recommended
4. **Missing Tests**: Frontend lacks comprehensive test coverage
5. **Circular Hierarchy Prevention**: No validation to prevent circular entity relationships (noted as known limitation in tests)

## Next Steps

### High Priority
1. ~~**Fix Entity Update Tree Permissions**: Debug and fix the `require_entity_update_with_tree` function to properly check ancestor permissions~~ ✅ COMPLETED
2. **Update Documentation**: Fix all references to wrong tech stack
3. **Commit Pending Changes**: Clean up git status
4. **Platform Management UI**: Essential for multi-tenant operation
5. **System Settings**: Configuration UI for admins
6. **Continue Enterprise Testing**: Implement remaining security tests from enterprise requirements

### Medium Priority
1. **Frontend Tests**: Add Vitest/Vue Test Utils coverage
2. **Conditional Permissions UI**: Visual builder for ABAC rules
3. **Audit Log Viewer**: UI for viewing system audit trails
4. **User Profile Page**: Let users manage their own settings

### Low Priority
1. **MFA Implementation**: Multi-factor authentication
2. **OAuth2 Providers**: Social login support
3. **Advanced Analytics**: Usage dashboards and reports
4. **API Documentation**: Update Swagger/OpenAPI specs

## Migration Notes

For teams migrating from the old system:
1. The unified entity model is fully backward compatible
2. All entities support both structural hierarchy and flexible groups
3. Permissions are cached for 5 minutes - plan accordingly
4. Entity types are now flexible strings - use consistent naming

## Environment Variables

### Backend (.env)
```env
DATABASE_URL=mongodb://localhost:27017
MONGO_DATABASE=outlabsAuth_test
REDIS_URL=redis://localhost:6379
SECRET_KEY=change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Frontend (.env)
```env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8030
NUXT_PUBLIC_SITE_URL=http://localhost:3000
```

## Development Commands

```bash
# Backend
docker compose logs -f api          # View logs
docker compose restart api          # Restart after changes
uv run pytest                      # Run tests (outside Docker)

# Frontend
cd frontend
npm run dev                        # Development server
npm run build                      # Production build
npm run preview                    # Preview production build
npm run typecheck                  # Type checking
npm run lint                       # Linting

# Database
mongosh mongodb://localhost:27017/outlabsAuth_test  # MongoDB shell
redis-cli                          # Redis CLI
```

## Testing Context-Aware Roles

After seeding the database, you can test the context-aware role system:

1. **Regional Manager Role** - Has different permissions at organization, branch, and team levels
2. **Tech Lead Role** - Varies permissions between branch, team, and access group contexts

Check the effective permissions endpoint to see how permissions change:
```bash
# Get effective permissions for a user at a specific entity
curl -X GET "http://localhost:8030/v1/permissions/users/{user_id}/effective-permissions?entity_id={entity_id}" \
  -H "Authorization: Bearer $TOKEN"
```

## Success Metrics

The unified entity model has successfully:
- ✅ Eliminated the need for separate group management
- ✅ Provided infinite flexibility for organizational structures
- ✅ Simplified permission management to a single system
- ✅ Enabled cross-entity memberships and time-based access
- ✅ Maintained excellent performance with caching
- ✅ Achieved the vision from MAIN_REFACTOR_PLAN.md

## Conclusion

The outlabsAuth unified entity model is successfully implemented and operational. The system provides a powerful, flexible authentication and authorization platform that can adapt to any organizational structure. While some frontend features and documentation updates are needed, the core system is production-ready and delivers on the original architectural vision.