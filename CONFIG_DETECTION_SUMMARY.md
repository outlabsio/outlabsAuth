# Config Detection Implementation Summary

**Date**: 2025-11-08  
**Status**: ✅ Complete (Ready for Testing)

## Problem Statement

The admin UI (`auth-ui/`) was showing ALL features (Entities, Context Settings) regardless of whether the backend was running SimpleRBAC or EnterpriseRBAC. This created confusion and a poor user experience.

**Key Issues**:
1. No way for UI to detect which preset the API is using
2. Permissions were hardcoded in components
3. EnterpriseRBAC-only features always visible

## Solution Overview

Implemented a **config detection system** that allows the admin UI to automatically adapt to the backend's capabilities.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Backend (SimpleRBAC or EnterpriseRBAC)                │
│  ┌───────────────────────────────────────────────────┐ │
│  │  GET /v1/auth/config                              │ │
│  │  {                                                │ │
│  │    "preset": "SimpleRBAC",                        │ │
│  │    "features": { ... },                           │ │
│  │    "available_permissions": [ ... ]               │ │
│  │  }                                                │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Frontend (Admin UI)                                    │
│  ┌───────────────────────────────────────────────────┐ │
│  │  auth.store.ts                                    │ │
│  │  - fetchConfig() on login/init                    │ │
│  │  - Computed: isSimpleRBAC, isEnterpriseRBAC       │ │
│  │  - Computed: availablePermissions                 │ │
│  └───────────────────────────────────────────────────┘ │
│                        ▼                                │
│  ┌───────────────────────────────────────────────────┐ │
│  │  Components (RoleCreateModal, etc.)               │ │
│  │  - v-if="authStore.isEnterpriseRBAC"              │ │
│  │  - Use authStore.availablePermissions             │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. Backend - Config Endpoint

**File**: `examples/simple_rbac/main.py`

Added `/v1/auth/config` endpoint that returns:

```python
{
    "preset": "SimpleRBAC",
    "features": {
        "entity_hierarchy": False,
        "context_aware_roles": False,
        "abac": False,
        "tree_permissions": False,
        "api_keys": True,
        "user_status": True,
        "activity_tracking": True,
    },
    "available_permissions": [
        {
            "value": "user:read",
            "label": "User Read",
            "category": "Users",
            "description": "View user information and profiles",
        },
        # ... all available permissions for this preset
    ],
}
```

**Key Points**:
- Returns preset type (SimpleRBAC or EnterpriseRBAC)
- Feature flags for conditional UI rendering
- Full list of available permissions (no hardcoding on frontend)
- Includes blog-specific permissions (post:read, post:create, etc.)

### 2. Frontend - Type Definitions

**File**: `auth-ui/app/types/auth.ts`

Added TypeScript types:

```typescript
export interface Permission {
  value: string
  label: string
  category: string
  description?: string
}

export interface AuthConfig {
  preset: 'SimpleRBAC' | 'EnterpriseRBAC'
  features: {
    entity_hierarchy: boolean
    context_aware_roles: boolean
    abac: boolean
    tree_permissions: boolean
    api_keys: boolean
    user_status: boolean
    activity_tracking: boolean
  }
  available_permissions: Permission[]
}

export interface AuthState {
  // ... existing fields ...
  config: AuthConfig | null
  isConfigLoaded: boolean
}
```

### 3. Frontend - Auth Store

**File**: `auth-ui/app/stores/auth.store.ts`

**Added State**:
```typescript
const state = reactive<AuthState>({
  // ... existing state ...
  config: null,
  isConfigLoaded: false,
})
```

**Added Computed Properties**:
```typescript
const isSimpleRBAC = computed(() => state.config?.preset === 'SimpleRBAC')
const isEnterpriseRBAC = computed(() => state.config?.preset === 'EnterpriseRBAC')
const features = computed(() => state.config?.features || {})
const availablePermissions = computed(() => state.config?.available_permissions || [])
```

**Added fetchConfig() Method**:
```typescript
const fetchConfig = async (): Promise<void> => {
  try {
    const config = await apiCall<AuthConfig>('/v1/auth/config')
    state.config = config
    state.isConfigLoaded = true
    
    console.log(`✅ Auth config loaded: ${config.preset}`, {
      features: config.features,
      permissions: config.available_permissions.length
    })
  } catch (error) {
    console.error('Failed to fetch auth config:', error)
    // Fallback to SimpleRBAC defaults
    state.config = { preset: 'SimpleRBAC', ... }
    state.isConfigLoaded = true
  }
}
```

**Updated initialize() and login()**:
```typescript
// Called after successful authentication
if (state.isAuthenticated) {
  await fetchConfig()
}
```

### 4. Frontend - Component Updates

**File**: `auth-ui/app/components/RoleCreateModal.vue`

**Before** (Hardcoded):
```vue
<script setup>
const availablePermissions = [
  { value: 'user:read', label: 'User Read', category: 'Users' },
  { value: 'entity:read', label: 'Entity Read', category: 'Entities' }, // ❌ Shows in SimpleRBAC
  // ... 20+ hardcoded permissions
]
</script>
```

**After** (Dynamic):
```vue
<script setup>
const authStore = useAuthStore()

// Get from backend config
const availablePermissions = computed(() => authStore.availablePermissions)
</script>

<template>
  <!-- Only show Context Settings in EnterpriseRBAC -->
  <UDivider v-if="authStore.isEnterpriseRBAC" />
  
  <div v-if="authStore.isEnterpriseRBAC">
    <h3>Context Settings</h3>
    <UCheckbox v-model="state.is_context_aware" />
    <!-- ... -->
  </div>
</template>
```

## Behavior Changes

### SimpleRBAC Mode

**Before**:
- ❌ Shows "Entities" permission section
- ❌ Shows "Context Settings" section
- ❌ Shows entity type dropdown
- ❌ 20+ hardcoded permissions including EnterpriseRBAC ones

**After**:
- ✅ Hides "Entities" section (no entity permissions available)
- ✅ Hides "Context Settings" section entirely
- ✅ Only shows SimpleRBAC permissions (users, roles, permissions, api_keys, blog)
- ✅ Permissions loaded dynamically from backend

### EnterpriseRBAC Mode (Future)

When connected to EnterpriseRBAC backend:
- ✅ Shows "Entities" section
- ✅ Shows "Context Settings"
- ✅ Shows tree permissions
- ✅ Shows ABAC conditions (if enabled)

## Testing Instructions

### Prerequisites

1. **Start Docker Compose** (MongoDB + Redis):
   ```bash
   cd /Users/outlabs/Documents/GitHub/outlabsAuth
   docker compose up -d
   ```

2. **Start SimpleRBAC API**:
   ```bash
   cd examples/simple_rbac
   MONGODB_URL="mongodb://localhost:27018" uv run uvicorn main:app --port 8003 --reload
   ```

3. **Start Admin UI**:
   ```bash
   cd auth-ui
   bun run dev  # Runs on http://localhost:3000
   ```

### Test Cases

#### Test 1: Config Endpoint
```bash
curl http://localhost:8003/v1/auth/config | jq
```

**Expected**:
```json
{
  "preset": "SimpleRBAC",
  "features": {
    "entity_hierarchy": false,
    "context_aware_roles": false,
    ...
  },
  "available_permissions": [...]
}
```

#### Test 2: Login Flow
1. Open http://localhost:3000
2. Login with `system@outlabs.io` / `Asd123$$`
3. Check browser console for: `✅ Auth config loaded: SimpleRBAC`

#### Test 3: Create Role Modal
1. Navigate to `/roles`
2. Click "Create Role"
3. **Verify**:
   - ✅ NO "Entities" section visible
   - ✅ NO "Context Settings" section visible
   - ✅ Permissions grouped by: Users, Roles, Permissions, API Keys, Blog
   - ✅ Total permissions shown includes blog-specific ones

#### Test 4: Config in Browser DevTools
```javascript
// In browser console
const authStore = useAuthStore()
console.log(authStore.isSimpleRBAC)  // Should be true
console.log(authStore.isEnterpriseRBAC)  // Should be false
console.log(authStore.availablePermissions.length)  // Should be 18
```

## Files Changed

### Backend
- ✅ `examples/simple_rbac/main.py` - Added `/v1/auth/config` endpoint

### Frontend
- ✅ `auth-ui/app/types/auth.ts` - Added config types
- ✅ `auth-ui/app/stores/auth.store.ts` - Added config detection
- ✅ `auth-ui/app/components/RoleCreateModal.vue` - Made preset-aware

### Documentation
- ✅ `docs/AUTH_UI.md` - Complete admin UI documentation
- ✅ `CLAUDE.md` - Added admin UI section
- ✅ `UI_TESTING_ISSUES.md` - Documented original issues
- ✅ `CONFIG_DETECTION_SUMMARY.md` - This file

## Next Steps

1. **Test the implementation** (user needs to start Docker + API)
2. **Verify Entities section is hidden** in SimpleRBAC
3. **Test role creation** with new permission structure
4. **Continue UI testing** (Permissions, Users, API Keys)
5. **Future**: Add same config detection to EnterpriseRBAC example

## Benefits

✅ **Better UX**: UI adapts to backend capabilities  
✅ **No hardcoding**: Permissions come from backend  
✅ **Type-safe**: Full TypeScript coverage  
✅ **Flexible**: Works with any OutlabsAuth preset  
✅ **Maintainable**: Single source of truth (backend)  
✅ **Extensible**: Easy to add new features/flags  

## Known Limitations

1. **No caching**: Config is fetched on every login/init (could cache in localStorage)
2. **No hot-reload**: If backend preset changes, user must logout/login
3. **Fallback defaults**: If config fetch fails, assumes SimpleRBAC

## Future Enhancements

- [ ] Cache config in localStorage (with expiry)
- [ ] Add config refresh button in UI
- [ ] Show preset indicator in header ("SimpleRBAC Mode")
- [ ] Add config version for breaking changes
- [ ] Support for custom permission categories

---

**Status**: Ready for user testing  
**Blockers**: None (waiting for Docker + API to be started)  
**Next Action**: User to test with running stack
