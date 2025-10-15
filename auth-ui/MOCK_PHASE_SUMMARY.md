# Mock Phase Summary

**Date**: 2025-10-15
**Status**: ✅ Completed

## Overview

Implemented comprehensive mock data infrastructure to enable frontend development without requiring a running backend API. This allows rapid UI iteration and design refinement before integrating with the real OutlabsAuth library backend.

## Key Accomplishments

### 1. Mock Infrastructure (`app/utils/mock.ts`)

Created centralized mock mode control:

```typescript
// Toggle mock mode via environment variable
export const USE_MOCK_DATA = !useRuntimeConfig().public.useRealApi

// Simulate network delays (200-700ms)
export const mockDelay = (min = 200, max = 700): Promise<void>

// Development logging for mock API calls
export const logMockCall = (method: string, endpoint: string, data?: any)

// Generate mock IDs
export const mockId = (): string
```

**Benefits**:
- Single source of truth for mock mode toggle
- Realistic network delay simulation
- Clear console logging for debugging
- Easy to switch to real API via environment variable

### 2. Comprehensive Mock Data (`app/utils/mockData.ts`)

Created production-like test data:

**Users** (5 mock users):
- `admin@outlabs.io` - Superuser with system access
- `sarah.manager@outlabs.io` - Engineering manager
- `john.dev@outlabs.io` - Backend team developer
- `alice.dev@outlabs.io` - Frontend team developer
- `bob.sales@outlabs.io` - Sales team member

**Password**: Any password works with these emails (mock mode only)

**Roles** (4 roles):
- Admin - Full system access
- Manager - Department management
- Developer - Project access
- Viewer - Read-only access

**Entities** (6 hierarchical entities):
```
Outlabs (org)
├── Engineering (dept)
│   ├── Backend Team (team)
│   └── Frontend Team (team)
├── Sales (dept)
└── Project Alpha (project)
```

**Other Data**:
- 15 permissions (user:*, role:*, entity:*, permission:*)
- 3 API keys (prod, dev, test)
- Entity contexts for context switcher
- Helper functions for credential validation and hierarchy queries

### 3. Environment Configuration

**Updated Files**:
- `.env` - Added `NUXT_PUBLIC_USE_REAL_API=false`
- `.env.example` - Added mock mode documentation
- `nuxt.config.ts` - Added `useRealApi` to runtime config

**Toggle Mock Mode**:
```bash
# Use mock data (default)
NUXT_PUBLIC_USE_REAL_API=false

# Use real API
NUXT_PUBLIC_USE_REAL_API=true
```

### 4. Store Integration

#### Auth Store (`app/stores/auth.store.ts`)

**Modified Methods**:
- `login()` - Mock login with any password for valid emails
- `fetchCurrentUser()` - Return mock user from localStorage
- `checkSystemStatus()` - Return mock system status (always initialized)

**Pattern**:
```typescript
const login = async (credentials: LoginCredentials): Promise<void> => {
  try {
    // Mock mode
    if (USE_MOCK_DATA) {
      logMockCall('POST', '/v1/auth/login', credentials)
      await mockDelay()

      const mockUser = getMockUserByCredentials(credentials.email, credentials.password)
      if (!mockUser || !mockUser.is_active) {
        throw new Error('Invalid email or password')
      }

      // Generate mock tokens and persist
      // ...
      return
    }

    // Real API call
    // ...
  }
}
```

#### Context Store (`app/stores/context.store.ts`)

**Modified Methods**:
- `fetchAvailableEntities()` - Return mock entity contexts

**Pattern**:
```typescript
const fetchAvailableEntities = async (): Promise<void> => {
  try {
    state.isLoading = true

    // Mock mode
    if (USE_MOCK_DATA) {
      logMockCall('GET', '/v1/memberships/me')
      await mockDelay()

      const entities = [...mockEntityContexts]

      if (authStore.currentUser?.is_superuser) {
        entities.unshift(SYSTEM_CONTEXT)
      }

      state.availableEntities = entities
      return
    }

    // Real API call
    // ...
  }
}
```

## Testing Instructions

### 1. Start Dev Server
```bash
cd auth-ui
bun run dev
```

### 2. Test Login
- Navigate to http://localhost:3003/login
- Login with `admin@outlabs.io` + any password
- Should successfully authenticate and redirect to dashboard

### 3. Test Entity Context Switcher
- Click entity dropdown in top navigation
- Should see 6 mock entities + system context (for admin)
- Switch between contexts
- Selected context persists in localStorage

### 4. Test Mock Console Logging
Open browser console to see mock API calls:
```
[MOCK] POST /v1/auth/login
[MOCK] GET /v1/users/me
[MOCK] GET /v1/memberships/me
```

### 5. Test LocalStorage Persistence
- Login and switch entity context
- Refresh page
- User and context should be restored from localStorage

## Current State

**Functional Features**:
- ✅ Login with mock credentials
- ✅ Entity context switching
- ✅ User menu with logout
- ✅ Theme switcher (light/dark)
- ✅ Dashboard layout
- ✅ LocalStorage persistence
- ✅ Mock API call logging

**Pending Features** (Next Phase):
- ⏭️ User management (list, create, edit, delete)
- ⏭️ Role management (list, create, edit, delete)
- ⏭️ Entity management (list, create, edit, delete, hierarchy)
- ⏭️ Permission management (list, assign, revoke)
- ⏭️ API key management
- ⏭️ Permission Waterfall component

## Design Decisions

### Why Mock First?

**User quote**: "Let's go with the mock UI for now. So I can get that right. That's the most, well, arguably the most important part."

**Benefits**:
1. **Fast iteration** - No backend dependency
2. **Design focus** - Perfect the UI/UX first
3. **Offline development** - Work anywhere
4. **Easy testing** - Predictable data for QA
5. **Clean toggle** - Switch to real API when ready

### Mock Data Patterns

**Realistic Structure**:
- Hierarchical entity relationships
- Role-based permissions
- Multiple entity types (org, dept, team, project)
- Active/inactive users
- Realistic email addresses and names

**Edge Cases Covered**:
- Superuser with system context
- Users with no entity access
- Deactivated users
- Different entity types and classes

## Next Steps

### Phase 2: Additional Stores (In Progress)

Create mock-enabled stores for:
1. **users.store.ts** - User CRUD operations
2. **roles.store.ts** - Role CRUD operations
3. **entities.store.ts** - Entity hierarchy management
4. **permissions.store.ts** - Permission assignment and checking

### Phase 3: User Management Pages

Build pages for:
- `/users` - User list with search, filter, pagination
- `/users/[id]` - User detail/edit page
- User create form
- User role assignments
- User entity memberships

### Phase 4: Role Management Pages

Build pages for:
- `/roles` - Role list
- `/roles/[id]` - Role detail/edit page
- Role permission assignments
- Context-aware role configuration

### Phase 5: Entity Management Pages

Build pages for:
- `/entities` - Entity hierarchy tree view
- `/entities/[id]` - Entity detail/edit page
- Entity member management
- Permission Waterfall component (killer feature)

## Files Created/Modified

### New Files
- `app/utils/mock.ts` - Mock infrastructure
- `app/utils/mockData.ts` - Comprehensive test data
- `MOCK_PHASE_SUMMARY.md` - This document

### Modified Files
- `.env` - Added mock mode flag
- `.env.example` - Added mock mode documentation
- `nuxt.config.ts` - Added `useRealApi` to runtime config
- `app/stores/auth.store.ts` - Added mock mode support
- `app/stores/context.store.ts` - Added mock mode support

## Conclusion

Mock infrastructure is complete and functional. The frontend can now be developed independently with realistic test data. When ready to integrate with the real backend, simply set `NUXT_PUBLIC_USE_REAL_API=true` and all stores will switch to real API calls.

**Status**: ✅ Phase 1 Complete - Moving to Phase 2 (Additional Stores)

---

**Created**: 2025-10-15
**Author**: Claude Code
**Project**: OutlabsAuth Frontend (auth-ui)
