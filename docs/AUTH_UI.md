# OutlabsAuth Admin UI

**Path**: `auth-ui/`  
**Framework**: Nuxt 4 (SPA mode)  
**UI Library**: Nuxt UI v4.0.1  
**State Management**: Pinia  
**Status**: In Development (Testing & Hardening Phase)

---

## Overview

The OutlabsAuth Admin UI is a **pluggable, pre-built administration interface** that can be integrated into any application using the OutlabsAuth library (SimpleRBAC or EnterpriseRBAC).

### Key Characteristics

- ✅ **Pluggable**: Deploy standalone or embed in existing apps
- ✅ **Preset-Aware**: Automatically detects SimpleRBAC vs EnterpriseRBAC mode
- ✅ **Full CRUD**: Manage users, roles, permissions, entities, API keys
- ✅ **Context Switching**: Switch between entity contexts (EnterpriseRBAC)
- ✅ **Real-time**: Live updates with optimistic UI patterns
- ✅ **Type-Safe**: Full TypeScript support
- ✅ **Accessible**: Built on Nuxt UI v4 (Radix UI primitives)

### What It Does

The admin UI provides a complete management interface for:

1. **Users**: Create, update, deactivate users, manage roles/memberships
2. **Roles**: Define roles with granular permissions
3. **Permissions**: View and manage permission definitions
4. **Entities**: Manage organizational hierarchy (EnterpriseRBAC only)
5. **API Keys**: Generate and revoke API keys for programmatic access
6. **Activity**: View user activity and DAU/MAU metrics

---

## Architecture

### Directory Structure

```
auth-ui/
├── app/
│   ├── components/          # UI components
│   │   ├── RoleCreateModal.vue
│   │   ├── UserCreateModal.vue
│   │   ├── EntitySwitcher.vue
│   │   └── ...
│   ├── composables/         # Shared composables
│   │   └── useDashboard.ts  # Keyboard shortcuts, UI state
│   ├── layouts/             # Layout templates
│   │   └── default.vue      # Main dashboard layout
│   ├── pages/               # Routes
│   │   ├── index.vue        # Dashboard
│   │   ├── users.vue        # Users management
│   │   ├── roles.vue        # Roles management
│   │   ├── permissions.vue  # Permissions management
│   │   ├── entities.vue     # Entities (EnterpriseRBAC only)
│   │   └── api-keys.vue     # API keys management
│   ├── stores/              # Pinia stores
│   │   ├── auth.store.ts    # Authentication + config detection
│   │   ├── users.store.ts   # User management
│   │   ├── roles.store.ts   # Role management
│   │   ├── permissions.store.ts
│   │   ├── entities.store.ts
│   │   ├── context.store.ts # Entity context switching
│   │   └── ...
│   ├── types/               # TypeScript types
│   │   ├── auth.ts
│   │   ├── user.ts
│   │   ├── role.ts
│   │   └── ...
│   └── utils/               # Utilities
│       ├── mock.ts          # Mock data toggle
│       └── mockData.ts      # Development mock data
├── nuxt.config.ts           # Nuxt configuration
├── package.json
├── .env                     # Environment variables
└── README.md
```

---

## Configuration

### Environment Variables

```bash
# .env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8003   # OutlabsAuth API
NUXT_PUBLIC_SITE_URL=http://localhost:3000       # Admin UI URL
NUXT_PUBLIC_USE_REAL_API=true                    # true = real API, false = mock data
```

### Nuxt Configuration

```typescript
// nuxt.config.ts
export default defineNuxtConfig({
  ssr: false,  // SPA mode for admin UIs
  modules: [
    '@nuxt/ui',      // UI components
    '@pinia/nuxt',   // State management
    '@vueuse/nuxt'   // Composables
  ],
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || 'http://localhost:3000',
      useRealApi: process.env.NUXT_PUBLIC_USE_REAL_API === 'true'
    }
  }
})
```

---

## Preset Detection (SimpleRBAC vs EnterpriseRBAC)

### How It Works

The admin UI **automatically detects** which preset the backend is using via the `/v1/auth/config` endpoint.

**Backend Response**:
```json
{
  "preset": "SimpleRBAC",
  "features": {
    "entity_hierarchy": false,
    "context_aware_roles": false,
    "abac": false,
    "tree_permissions": false
  },
  "available_permissions": [
    {
      "value": "user:read",
      "label": "User Read",
      "category": "Users",
      "description": "View user information"
    },
    // ... only permissions available in this preset
  ]
}
```

### Frontend Detection (Auth Store)

```typescript
// auth-ui/app/stores/auth.store.ts

export const useAuthStore = defineStore('auth', () => {
  const state = reactive<AuthState>({
    // ... existing auth state ...
    
    // Config detection (NEW)
    config: null as AuthConfig | null,
    isConfigLoaded: false
  })

  const isSimpleRBAC = computed(() => state.config?.preset === 'SimpleRBAC')
  const isEnterpriseRBAC = computed(() => state.config?.preset === 'EnterpriseRBAC')
  const features = computed(() => state.config?.features || {})
  
  const fetchConfig = async (): Promise<void> => {
    const config = await apiCall<AuthConfig>('/v1/auth/config')
    state.config = config
    state.isConfigLoaded = true
  }

  // Initialize config after authentication
  const initialize = async (): Promise<boolean> => {
    // ... existing auth initialization ...
    
    if (state.isAuthenticated) {
      await fetchConfig()  // NEW: Load config
    }
    
    return state.isAuthenticated
  }

  return {
    // ... existing exports ...
    isSimpleRBAC,
    isEnterpriseRBAC,
    features,
    fetchConfig
  }
})
```

### Component Usage

```vue
<script setup>
const authStore = useAuthStore()

// Get available permissions from config
const availablePermissions = computed(() => 
  authStore.state.config?.available_permissions || []
)
</script>

<template>
  <!-- Only show entity features in EnterpriseRBAC -->
  <div v-if="authStore.isEnterpriseRBAC">
    <EntitySwitcher />
  </div>

  <!-- Conditionally show permissions based on preset -->
  <div v-for="perm in availablePermissions" :key="perm.value">
    <UCheckbox :label="perm.label" />
  </div>
</template>
```

---

## State Management (Pinia Stores)

### Auth Store (`auth.store.ts`)

**Purpose**: JWT authentication, token refresh, API calls, **config detection**

**Key Methods**:
- `initialize()` - Load tokens from localStorage, fetch config
- `login(credentials)` - Authenticate user
- `logout()` - Revoke tokens, clear state
- `apiCall(endpoint, options)` - Make authenticated API requests with auto-refresh
- `fetchConfig()` - **NEW**: Fetch auth configuration (preset, features, permissions)

**State**:
```typescript
{
  accessToken: string | null,
  refreshToken: string | null,
  user: User | null,
  isAuthenticated: boolean,
  config: AuthConfig | null,        // NEW
  isConfigLoaded: boolean           // NEW
}
```

**Computed**:
- `isAuthenticated` - Whether user is logged in
- `currentUser` - Current user object
- `isSimpleRBAC` - **NEW**: True if backend is SimpleRBAC
- `isEnterpriseRBAC` - **NEW**: True if backend is EnterpriseRBAC
- `features` - **NEW**: Feature flags from backend

### Context Store (`context.store.ts`)

**Purpose**: Entity context switching (EnterpriseRBAC only)

**Key Methods**:
- `initialize()` - Load entity memberships, restore context from localStorage
- `switchContext(entity)` - Switch to different entity
- `getContextHeaders()` - Get `X-Entity-Context` header for API calls

**Usage**:
```typescript
const contextStore = useContextStore()

// Switch context
contextStore.switchContext(entity)

// Current context automatically added to API calls
await authStore.apiCall('/users')  // Includes X-Entity-Context header
```

### Resource Stores

Each resource (users, roles, permissions, entities) has its own store:

**Pattern**:
```typescript
export const useRolesStore = defineStore('roles', () => {
  const authStore = useAuthStore()
  
  const state = reactive({
    roles: [] as Role[],
    isLoading: false
  })

  const fetchRoles = async () => {
    state.isLoading = true
    const data = await authStore.apiCall('/v1/roles')
    state.roles = data.items
    state.isLoading = false
  }

  const createRole = async (roleData: CreateRoleRequest) => {
    const role = await authStore.apiCall('/v1/roles', {
      method: 'POST',
      body: JSON.stringify(roleData)
    })
    state.roles.push(role)
    return true
  }

  return { state, fetchRoles, createRole }
})
```

---

## API Integration

### Authentication Flow

1. **Login**: User enters credentials
2. **Token Storage**: Access + refresh tokens stored in localStorage
3. **Config Fetch**: **NEW** - Fetch `/v1/auth/config` to detect preset
4. **Context Init**: If EnterpriseRBAC, load entity memberships
5. **Dashboard**: Show appropriate UI based on config

### API Call Pattern

All API calls go through `authStore.apiCall()`:

```typescript
// Automatic token refresh on 401
const users = await authStore.apiCall<PaginatedResponse<User>>('/v1/users')

// With options
const role = await authStore.apiCall('/v1/roles', {
  method: 'POST',
  body: JSON.stringify(roleData)
})

// Automatically includes:
// - Authorization: Bearer {token}
// - X-Entity-Context: {entity_id} (if applicable)
// - Auto-retry with refresh token on 401
```

### Expected Backend Endpoints

The admin UI expects these endpoints from any OutlabsAuth implementation:

**Auth**:
- `POST /auth/login` - Login with email/password
- `POST /auth/logout` - Revoke refresh token
- `POST /auth/refresh` - Refresh access token
- `GET /v1/auth/config` - **NEW**: Get preset and features

**Users**:
- `GET /v1/users` - List users (paginated)
- `GET /v1/users/me` - Current user
- `POST /v1/users` - Create user
- `PATCH /v1/users/{id}` - Update user
- `DELETE /v1/users/{id}` - Delete user
- `POST /v1/users/{id}/deactivate` - Deactivate user

**Roles**:
- `GET /v1/roles` - List roles
- `POST /v1/roles` - Create role
- `PATCH /v1/roles/{id}` - Update role
- `DELETE /v1/roles/{id}` - Delete role

**Permissions**:
- `GET /v1/permissions` - List permissions
- `POST /v1/permissions` - Create permission
- `PATCH /v1/permissions/{id}` - Update permission

**Entities** (EnterpriseRBAC only):
- `GET /v1/entities` - List entities
- `POST /v1/entities` - Create entity
- `PATCH /v1/entities/{id}` - Update entity
- `DELETE /v1/entities/{id}` - Delete entity

**API Keys**:
- `GET /v1/api-keys` - List API keys
- `POST /v1/api-keys` - Create API key
- `POST /v1/api-keys/{id}/revoke` - Revoke API key

**Memberships** (EnterpriseRBAC only):
- `GET /v1/memberships/me` - Current user's memberships (for context switching)

---

## Running the Admin UI

### Development

```bash
cd auth-ui
npm install
npm run dev
```

Runs on **http://localhost:3000**

### Production Build

```bash
npm run build
npm run preview
```

### Docker Deployment

The admin UI can be containerized and deployed alongside your OutlabsAuth-powered API:

```yaml
# docker-compose.yml
services:
  api:
    build: ./my-app
    ports:
      - "8000:8000"
  
  admin-ui:
    build: ./auth-ui
    ports:
      - "3000:3000"
    environment:
      - NUXT_PUBLIC_API_BASE_URL=http://api:8000
```

---

## Customization

### Theming

The UI uses Nuxt UI v4 which supports full theming:

```typescript
// app.config.ts
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'blue',
      neutral: 'slate'
    }
  }
})
```

### Adding Custom Pages

```vue
<!-- app/pages/custom-reports.vue -->
<script setup lang="ts">
const authStore = useAuthStore()

const reports = await authStore.apiCall('/v1/custom/reports')
</script>

<template>
  <div>
    <h1>Custom Reports</h1>
    <!-- Your custom UI -->
  </div>
</template>
```

### Extending Stores

```typescript
// app/stores/custom.store.ts
export const useCustomStore = defineStore('custom', () => {
  const authStore = useAuthStore()

  // Your custom logic
  const fetchCustomData = async () => {
    return await authStore.apiCall('/v1/custom/endpoint')
  }

  return { fetchCustomData }
})
```

---

## Keyboard Shortcuts

Global shortcuts (defined in `useDashboard.ts`):

- `g-d` - Go to Dashboard
- `g-u` - Go to Users
- `g-r` - Go to Roles
- `g-e` - Go to Entities
- `g-p` - Go to Permissions
- `g-k` - Go to API Keys
- `g-s` - Go to Settings
- `n` - Toggle notifications

---

## Testing the Admin UI

### With SimpleRBAC Example

```bash
# Terminal 1: Run SimpleRBAC API
cd examples/simple_rbac
docker compose up -d  # MongoDB, Redis
uv run uvicorn main:app --port 8003 --reload

# Terminal 2: Run Admin UI
cd auth-ui
npm run dev

# Visit http://localhost:3000
# Login with system@outlabs.io / Asd123$$
```

**Expected Behavior**:
- ✅ "Entities" section hidden (SimpleRBAC mode)
- ✅ No context switcher in header
- ✅ Permissions limited to user, role, permission, api_key

### With EnterpriseRBAC Example (Future)

```bash
# Terminal 1: Run EnterpriseRBAC API
cd examples/enterprise_rbac
docker compose up -d
uv run uvicorn main:app --port 8004 --reload

# Terminal 2: Run Admin UI (point to 8004)
cd auth-ui
NUXT_PUBLIC_API_BASE_URL=http://localhost:8004 npm run dev
```

**Expected Behavior**:
- ✅ "Entities" section visible
- ✅ Context switcher in header
- ✅ Tree permissions available
- ✅ Context-aware role option shown

---

## Mock Data Mode

For UI development without a running backend:

```bash
# .env
NUXT_PUBLIC_USE_REAL_API=false
```

Mock data defined in `app/utils/mockData.ts`:
- Users, roles, permissions, entities
- Simulated API delays
- Full CRUD operations (in-memory)

---

## Current Status (2025-11-08)

**Phase**: Testing & Hardening  
**Branch**: `library-redesign`

**Completed**:
- ✅ JWT authentication flow
- ✅ Token refresh mechanism
- ✅ All stores implemented (auth, users, roles, permissions, entities, context)
- ✅ All CRUD modals (users, roles, API keys)
- ✅ Context switching (EnterpriseRBAC)
- ✅ Keyboard shortcuts
- ✅ Mock data mode

**In Progress**:
- 🔄 Config detection (SimpleRBAC vs EnterpriseRBAC)
- 🔄 UI layout improvements (Roles modal)
- 🔄 Testing all CRUD operations

**Not Yet Started**:
- ⏸️ Activity tracking dashboard
- ⏸️ Metrics visualization
- ⏸️ User permissions matrix view
- ⏸️ Bulk operations

---

## Issues & Troubleshooting

### Issue: UI shows Entities section in SimpleRBAC mode

**Cause**: Config detection not yet implemented  
**Status**: In progress (see `UI_TESTING_ISSUES.md`)  
**Fix**: Adding `/v1/auth/config` endpoint and auth store config detection

### Issue: Cannot log in

**Checklist**:
1. Is the API running? (`http://localhost:8003`)
2. Is the database seeded? (Run `seed_data.py`)
3. Correct credentials? (See `examples/simple_rbac/DEMO_CREDENTIALS.md`)
4. CORS enabled on API?

### Issue: 401 Unauthorized after login

**Cause**: Token expired or invalid  
**Fix**: Logout and login again (refresh token may be expired)

---

## Future Enhancements (Post-v1.0)

- **Dashboard Analytics**: DAU/MAU charts, login heatmaps
- **Permission Matrix**: Visual grid of users × roles × permissions
- **Audit Log**: View all permission checks and API calls
- **Bulk Operations**: Assign roles to multiple users at once
- **Entity Tree View**: Visual hierarchy of entities (EnterpriseRBAC)
- **Advanced Search**: Filter users by role, entity, status
- **Export/Import**: Backup and restore roles/permissions

---

## Related Documentation

- **Implementation Plan**: `docs/IMPLEMENTATION_ROADMAP.md`
- **Testing Issues**: `UI_TESTING_ISSUES.md`
- **API Design**: `docs/API_DESIGN.md`
- **Library Architecture**: `docs/LIBRARY_ARCHITECTURE.md`

---

**Last Updated**: 2025-11-08  
**Maintainer**: OutlabsAuth Team  
**Questions**: See `docs/REDESIGN_VISION.md`
