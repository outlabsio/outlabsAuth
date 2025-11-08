# UI Testing Issues - Roles Create Modal

**Testing Date**: 2025-11-08  
**Component**: `auth-ui/app/components/RoleCreateModal.vue`  
**API Backend**: SimpleRBAC (port 8003)  
**UI Framework**: Nuxt UI v4.0.1

---

## Critical Issues Found

### Issue #1: No SimpleRBAC/EnterpriseRBAC Detection ❌

**Problem**: The admin UI does NOT detect which auth mode the API is running in. It shows ALL permissions and features regardless of whether the backend is SimpleRBAC or EnterpriseRBAC.

**Evidence**:
- UI shows "Entities" permission section (Entity Read, Entity Create, Entity Update, Entity Delete)
- UI shows "Context-aware role" checkbox
- UI shows "Entity Type" dropdown

**Expected Behavior**: 
- In **SimpleRBAC** mode: Hide Entities section, hide Context Settings
- In **EnterpriseRBAC** mode: Show all sections

**Current Implementation**:
```typescript
// RoleCreateModal.vue - Lines 12-18
// Available permissions (HARDCODED - doesn't adapt to auth mode)
const availablePermissions = [
  // User permissions
  { value: 'user:read', label: 'User Read', category: 'Users' },
  // ...
  // Entity permissions - SHOULD NOT SHOW IN SIMPLERB AC
  { value: 'entity:read', label: 'Entity Read', category: 'Entities' },
  { value: 'entity:create', label: 'Entity Create', category: 'Entities' },
  // ...
]
```

**Root Cause**:
1. No API endpoint to query auth mode/capabilities
2. No store to cache auth configuration
3. Permissions are hardcoded in the component

---

### Issue #2: Confusing Layout ❌

**Problem**: The current layout is hard for users to understand.

**Layout Issues**:
- Left/right split feels arbitrary (why is Basic Info on left but Permissions on right?)
- Permission categories scattered in 2-column grid
- "All" buttons for each category but unclear visual hierarchy
- Context Settings appear before seeing permission count
- Footer text conflicts with visual importance

**User Feedback**: "the layout is confusing and not going to be easy for users"

**Current Layout**:
```
┌─────────────────────────────────────────────────────┐
│ Create Role                                    [X] │
├──────────────────┬──────────────────────────────────┤
│ Basic Info       │  Permissions                     │
│ - Display Name   │  ┌───────┐ ┌───────┐            │
│ - Name           │  │ Users │ │ Roles │            │
│ - Description    │  └───────┘ └───────┘            │
│                  │  ┌──────────┐ ┌──────────┐      │
│ Context Settings │  │ Entities │ │ Perms    │      │
│ - Context-aware  │  └──────────┘ └──────────┘      │
│ - Entity Type    │  ┌──────────┐                   │
│                  │  │ API Keys │                   │
│ Perms Count: 0   │  └──────────┘                   │
└──────────────────┴──────────────────────────────────┘
```

---

## Proposed Solution

### Part 1: Add Auth Mode Detection (Backend)

**Add API Endpoint**:
```python
# examples/simple_rbac/main.py
@app.get("/v1/auth/config")
async def get_auth_config():
    """Get authentication system configuration"""
    return {
        "preset": "SimpleRBAC",  # or "EnterpriseRBAC"
        "features": {
            "entity_hierarchy": False,
            "context_aware_roles": False,
            "abac": False,
            "tree_permissions": False
        },
        "available_permissions": [
            {"value": "user:read", "label": "User Read", "category": "Users"},
            {"value": "user:create", "label": "User Create", "category": "Users"},
            # ... (only SimpleRBAC permissions)
        ]
    }
```

### Part 2: Create Auth Config Store (Frontend)

**Create New Store**:
```typescript
// auth-ui/app/stores/config.store.ts
export const useConfigStore = defineStore('config', () => {
  const state = reactive({
    preset: null as 'SimpleRBAC' | 'EnterpriseRBAC' | null,
    features: {
      entity_hierarchy: false,
      context_aware_roles: false,
      abac: false,
      tree_permissions: false
    },
    availablePermissions: [] as Permission[],
    isLoaded: false
  })

  const isSimpleRBAC = computed(() => state.preset === 'SimpleRBAC')
  const isEnterpriseRBAC = computed(() => state.preset === 'EnterpriseRBAC')

  async function fetchConfig() {
    const config = await authStore.apiCall('/v1/auth/config')
    state.preset = config.preset
    state.features = config.features
    state.availablePermissions = config.available_permissions
    state.isLoaded = true
  }

  return { state, isSimpleRBAC, isEnterpriseRBAC, fetchConfig }
})
```

### Part 3: Update RoleCreateModal

**Use Dynamic Permissions**:
```vue
<script setup>
const configStore = useConfigStore()

// Use permissions from API config instead of hardcoded
const availablePermissions = computed(() => 
  configStore.state.availablePermissions
)

// Group by category, filtering out empty categories
const permissionsByCategory = computed(() => {
  const grouped = {}
  availablePermissions.value.forEach(perm => {
    if (!grouped[perm.category]) {
      grouped[perm.category] = []
    }
    grouped[perm.category].push(perm)
  })
  return grouped
})
</script>

<template>
  <!-- Only show Context Settings in EnterpriseRBAC -->
  <div v-if="configStore.isEnterpriseRBAC">
    <h3>Context Settings</h3>
    <UCheckbox v-model="state.is_context_aware" />
    <!-- ... -->
  </div>
</template>
```

### Part 4: Redesign Layout (Nuxt UI v4)

**Proposed Simpler Layout**:
```
┌──────────────────────────────────────────────────┐
│ Create Role                                 [X]  │
├──────────────────────────────────────────────────┤
│                                                  │
│ Basic Information                                │
│ ┌──────────────┐ ┌──────────────┐               │
│ │ Display Name │ │ Name         │               │
│ └──────────────┘ └──────────────┘               │
│ ┌─────────────────────────────────────────────┐ │
│ │ Description                                 │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ Permissions (0 selected)                         │
│ ┌──────────────────────────────────────────────┐│
│ │ Users            [All]                       ││
│ │ ☐ User Read     ☐ User Create               ││
│ │ ☐ User Update   ☐ User Delete               ││
│ ├──────────────────────────────────────────────┤│
│ │ Roles            [All]                       ││
│ │ ☐ Role Read     ☐ Role Create               ││
│ │ ☐ Role Update   ☐ Role Delete               ││
│ ├──────────────────────────────────────────────┤│
│ │ Permissions      [All]                       ││
│ │ ☐ Permission Read  ☐ Permission Create      ││
│ │ ☐ Permission Update                         ││
│ ├──────────────────────────────────────────────┤│
│ │ API Keys         [All]                       ││
│ │ ☐ API Key Read  ☐ API Key Create            ││
│ │ ☐ API Key Revoke                            ││
│ └──────────────────────────────────────────────┘│
│                                                  │
│ <!-- Only shown in EnterpriseRBAC -->           │
│ Context Settings (Optional)                      │
│ ☐ Context-aware role                            │
│                                                  │
├──────────────────────────────────────────────────┤
│                    [Cancel]  [Create Role]       │
└──────────────────────────────────────────────────┘
```

**Layout Improvements**:
1. **Single column** - simpler flow, top to bottom
2. **Grouped permissions** - all in one scrollable area with clear sections
3. **Context Settings at bottom** - only for EnterpriseRBAC
4. **Permission count in header** - visible while scrolling
5. **Accordion-style categories** - cleaner, more compact

---

## Action Items

### Backend (SimpleRBAC Example)
- [ ] Add `/v1/auth/config` endpoint
- [ ] Include preset type and feature flags
- [ ] Return only available permissions for current mode

### Frontend (Auth UI)
- [ ] Create `config.store.ts` for auth configuration
- [ ] Update `RoleCreateModal.vue` to use dynamic permissions
- [ ] Hide Entities section in SimpleRBAC mode
- [ ] Hide Context Settings in SimpleRBAC mode
- [ ] Redesign layout (single column, accordion categories)
- [ ] Update Nuxt UI v4 components (UAccordion, UCard improvements)

### Testing
- [ ] Verify Entities section hidden in SimpleRBAC
- [ ] Verify Entities section visible in EnterpriseRBAC
- [ ] Test role creation with new layout
- [ ] Validate permissions correctly assigned
- [ ] Test "All" category toggles

---

## Design Decisions Needed

1. **Should we also hide the Entities navigation item** in SimpleRBAC mode?
   - Currently: `/entities` route exists in nav
   - Proposal: Hide nav item if `!configStore.features.entity_hierarchy`

2. **Should permission categories be collapsible** (accordion) or always expanded?
   - Pros (accordion): Cleaner, less scrolling
   - Cons (accordion): Extra click to see all

3. **Should we show a banner** explaining which mode is active?
   - Example: "Running in SimpleRBAC mode - entity features disabled"

---

## Notes

- **Nuxt UI v4** confirmed - can use latest components
- **Current API URL**: `http://localhost:8003` (SimpleRBAC)
- **No config endpoint exists yet** - needs to be added
- **Mock data mode available** but currently disabled (`USE_REAL_API=true`)
