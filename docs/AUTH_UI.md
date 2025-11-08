# OutlabsAuth Admin UI

**Path**: `auth-ui/`
**Framework**: Nuxt 4 (SPA mode)
**UI Library**: Nuxt UI v4.0.1
**State Management**: Pinia + Pinia Colada (Data Fetching)
**Status**: In Development (Testing & Hardening Phase)

**Recent Updates**:
- ✅ Migrated to Pinia Colada for data fetching (Jan 2025)
- ✅ Removed mock data system
- ✅ Implemented optimistic UI updates

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
│   ├── api/                 # 🆕 API abstraction layer (Pinia Colada)
│   │   ├── client.ts        # Base API client with auth
│   │   ├── users.ts         # User API functions
│   │   ├── roles.ts         # Role API functions
│   │   ├── permissions.ts   # Permission API functions
│   │   └── entities.ts      # Entity API functions
│   ├── queries/             # 🆕 Pinia Colada query definitions
│   │   ├── users.ts         # User queries + mutations (236 LOC)
│   │   ├── roles.ts         # Role queries + mutations (247 LOC)
│   │   ├── permissions.ts   # Permission queries (52 LOC)
│   │   └── entities.ts      # Entity queries + mutations (266 LOC)
│   ├── components/          # UI components
│   │   ├── RoleCreateModal.vue
│   │   ├── UserCreateModal.vue
│   │   ├── EntitySwitcher.vue
│   │   └── ...
│   ├── composables/         # Shared composables
│   │   ├── useDashboard.ts         # Keyboard shortcuts, UI state
│   │   ├── useContextAwareQuery.ts # 🆕 Context switching pattern
│   │   └── useUserHelpers.ts       # 🆕 User enrichment
│   ├── layouts/             # Layout templates
│   │   └── default.vue      # Main dashboard layout
│   ├── pages/               # Routes
│   │   ├── index.vue        # Dashboard
│   │   ├── users/index.vue  # Users management (uses useQuery)
│   │   ├── roles/index.vue  # Roles management (uses useQuery)
│   │   ├── permissions/index.vue # Permissions (uses useQuery)
│   │   ├── entities/index.vue    # Entities (uses useQuery)
│   │   └── api-keys.vue     # API keys management
│   ├── stores/              # Pinia stores (UI state only now)
│   │   ├── auth.store.ts    # Authentication + config detection
│   │   ├── context.store.ts # Entity context switching
│   │   └── ...              # Other stores for local UI state
│   ├── types/               # TypeScript types
│   │   ├── auth.ts
│   │   ├── user.ts
│   │   ├── role.ts
│   │   └── ...
│   └── utils/               # Utilities (mock data removed)
├── colada.options.ts        # 🆕 Pinia Colada global config
├── nuxt.config.ts           # Nuxt configuration (@pinia/colada-nuxt added)
├── package.json             # Added @pinia/colada dependencies
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

## Pinia Colada Data Fetching

**Status**: ✅ Fully Migrated (Phase 1 & 2 Complete - Jan 2025)

The admin UI uses **Pinia Colada** for all data fetching operations, replacing manual state management with automatic loading states, intelligent caching, and optimistic updates.

### Why Pinia Colada?

Pinia Colada provides:

- **Automatic loading/error states** - No manual `isLoading` flags needed
- **Request deduplication** - Multiple components requesting same data = 1 API call
- **Smart caching** - Stale-while-revalidate for instant UX
- **Optimistic updates** - Instant UI feedback before server confirms
- **Automatic refetching** - On window focus, reconnect, mount
- **Type-safe cache operations** - Query keys carry type information
- **Zero race conditions** - Query key changes cancel stale requests
- **Built for Vue** - Lighter than TanStack Query, official Pinia integration

### Configuration

```typescript
// colada.options.ts
export default {
  query: {
    staleTime: 5000,              // 5 seconds default
    refetchOnWindowFocus: true,   // Refetch when window regains focus
    refetchOnReconnect: true,     // Refetch when reconnecting
    retry: 1,                     // Retry failed requests once
  }
}
```

```typescript
// nuxt.config.ts
export default defineNuxtConfig({
  modules: [
    '@nuxt/ui',
    '@pinia/nuxt',
    '@pinia/colada-nuxt'  // 🆕 Pinia Colada module
  ]
})
```

### Architecture: Two-Layer Pattern

**Layer 1: API Functions** (`app/api/*.ts`)
- Pure API calls with auth handling
- Reusable across queries and non-query code
- Domain-specific (users, roles, permissions, entities)

**Layer 2: Query Definitions** (`app/queries/*.ts`)
- Query keys (hierarchical, type-safe)
- Query options (stale time, refetch behavior)
- Mutations with cache invalidation
- Optimistic update patterns

### Query Patterns

#### Pattern 1: Basic List Query

```typescript
// In component (e.g., pages/users/index.vue)
import { useQuery } from '@pinia/colada'
import { usersQueries } from '~/queries/users'

const { data: usersData, isLoading, error } = useQuery(
  () => usersQueries.list({}, { page: 1, limit: 20 })
)

// ✅ Automatic loading state
// ✅ Automatic error handling
// ✅ Cached for 5 seconds
// ✅ No race conditions
```

#### Pattern 2: Reactive Query with Filters

```typescript
const search = ref('')
const pagination = ref({ pageIndex: 0, pageSize: 20 })

const filters = computed(() => ({ search: search.value }))
const params = computed(() => ({
  page: pagination.value.pageIndex + 1,
  limit: pagination.value.pageSize
}))

const { data: usersData, isLoading } = useQuery(
  () => usersQueries.list(filters.value, params.value)
)

// When search/pagination changes → key changes → auto-refetch
// ✅ Debouncing handled by Pinia Colada
// ✅ Cancels stale requests automatically
// ✅ Zero race conditions
```

#### Pattern 3: Detail Query

```typescript
const userId = ref('690f878bf6935ab2a6f291f4')

const { data: user, isLoading } = useQuery(
  () => usersQueries.detail(userId.value)
)

// ✅ Cached for 10 seconds (longer than list)
// ✅ Navigate away and back = instant load
```

### Mutation Patterns

#### Pattern 1: Create Mutation

```typescript
// In component (e.g., components/UserCreateModal.vue)
import { useCreateUserMutation } from '~/queries/users'

const { mutate: createUser, isPending } = useCreateUserMutation()

async function handleSubmit(formData) {
  await createUser({
    email: formData.email,
    password: formData.password,
    first_name: formData.first_name,
    last_name: formData.last_name,
  })

  // ✅ Automatically invalidates user lists
  // ✅ All components show new user instantly
  // ✅ No manual refetch needed
}
```

#### Pattern 2: Update Mutation

```typescript
import { useUpdateUserMutation } from '~/queries/users'

const { mutate: updateUser } = useUpdateUserMutation()

async function handleUpdate(userId: string, changes: Partial<User>) {
  await updateUser({ userId, data: changes })

  // ✅ Invalidates specific user detail
  // ✅ Invalidates user lists
  // ✅ All components auto-update
}
```

#### Pattern 3: Delete with Optimistic Update

```typescript
import { useDeleteUserMutation } from '~/queries/users'

const { mutate: deleteUser } = useDeleteUserMutation()

async function handleDelete(userId: string) {
  await deleteUser(userId)

  // ✅ UI updates INSTANTLY (before server responds)
  // ✅ If server fails, automatically rolls back
  // ✅ If server succeeds, refetches for confirmation
}
```

**How Optimistic Updates Work:**

```typescript
// queries/users.ts
export function useDeleteUserMutation() {
  const queryClient = useQueryCache()

  return useMutation({
    mutation: (userId) => deleteUserAPI(userId),

    onMutate: async (userId) => {
      // 1. Cancel ongoing queries (prevent race conditions)
      await queryClient.cancelQueries({ queryKey: USER_KEYS.all })

      // 2. Snapshot current state (for rollback)
      const previousLists = queryClient.getQueriesData({
        queryKey: USER_KEYS.lists()
      })

      // 3. Optimistically update UI (instant feedback)
      queryClient.setQueriesData({ queryKey: USER_KEYS.lists() }, (old) => ({
        ...old,
        items: old.items.filter(u => u.id !== userId),
        total: old.total - 1
      }))

      return { previousLists, userId }
    },

    onError: (err, vars, context) => {
      // 4. Rollback on error
      context.previousLists.forEach(([key, data]) => {
        queryClient.setQueryData(key, data)
      })
    },

    onSuccess: (_, userId) => {
      // 5. Refetch to confirm (background)
      queryClient.invalidateQueries({ queryKey: USER_KEYS.lists() })
      queryClient.removeQueries({ queryKey: USER_KEYS.detail(userId) })
    }
  })
}
```

### Query Keys Pattern

**Hierarchical Keys** for precise cache invalidation:

```typescript
// queries/users.ts
export const USER_KEYS = {
  all: ['users'] as const,                    // Invalidate everything
  lists: () => [...USER_KEYS.all, 'list'] as const,  // All lists
  list: (filters, params) => [...USER_KEYS.lists(), { filters, params }] as const,
  details: () => [...USER_KEYS.all, 'detail'] as const,
  detail: (id) => [...USER_KEYS.details(), id] as const,
}

// Usage:
// Invalidate all users → USER_KEYS.all
// Invalidate all lists → USER_KEYS.lists()
// Invalidate specific list → USER_KEYS.list(filters, params)
// Invalidate specific user → USER_KEYS.detail(userId)
```

### Context-Aware Queries (EnterpriseRBAC)

```typescript
// composables/useContextAwareQuery.ts
export function useContextAwareQuery(resourceType: string) {
  const contextStore = useContextStore()

  const { data, isLoading } = useQuery({
    key: computed(() => [
      resourceType,
      contextStore.selectedEntity?.id  // 🔑 Include context in key
    ]),
    query: () => fetchData()
  })

  // When context switches → key changes → auto-refetch
  // ✅ Zero manual coordination needed

  return { data, isLoading }
}
```

### Benefits Achieved

**Before Migration (Manual State Management):**
- 50+ fetch methods across 6 stores
- ~1,200 lines of boilerplate (loading flags, error handling, try/catch)
- Race conditions between search/pagination/filters
- No caching (loading spinner every time)
- Manual refetch after mutations
- No optimistic updates

**After Migration (Pinia Colada):**
- ~800 lines of query definitions
- Zero manual loading states
- Zero race conditions (query keys prevent them)
- Instant page loads (stale-while-revalidate)
- Automatic cache invalidation
- Instant UI feedback (optimistic updates)

**Code Reduction:**
- ✅ ~1,200 lines removed (boilerplate)
- ✅ ~800 lines added (query definitions)
- ✅ **Net: -400 lines** with better UX!

### API Abstraction Layer

```typescript
// app/api/client.ts - Base client
export function createAPIClient() {
  const authStore = useAuthStore()

  return {
    call: <T>(endpoint: string, options?: RequestInit) =>
      authStore.apiCall<T>(endpoint, options),
    buildQueryString: (params: Record<string, any>) => { /* ... */ }
  }
}

// app/api/users.ts - Domain-specific API
export function createUsersAPI() {
  const client = createAPIClient()

  return {
    fetchUsers: async (filters, params) => {
      const query = client.buildQueryString({ ...filters, ...params })
      return client.call<PaginatedResponse<User>>(`/v1/users?${query}`)
    },

    fetchUser: async (userId: string) => {
      return client.call<User>(`/v1/users/${userId}`)
    },

    createUser: async (data: CreateUserRequest) => {
      return client.call<User>('/v1/users', {
        method: 'POST',
        body: JSON.stringify(data)
      })
    },

    // ... more methods
  }
}
```

### Global Loading State

```typescript
import { useIsFetching } from '@pinia/colada'

const isFetching = useIsFetching()
const isAnyLoading = computed(() => isFetching.value > 0)

// ✅ Single source of truth for global loading
// ✅ Show global spinner when any request is in flight
```

### Stale Time Configuration

Different resources have different stale times based on change frequency:

```typescript
// Users - change frequently
usersQueries.list() → staleTime: 5000  // 5 seconds

// Roles - change less frequently
rolesQueries.list() → staleTime: 5000  // 5 seconds

// Permissions - rarely change
permissionsQueries.list() → staleTime: 60000  // 60 seconds

// Entities - moderate change frequency
entitiesQueries.list() → staleTime: 10000  // 10 seconds
```

### Migration Summary

**Phase 1: UI Migration** ✅ Complete
- Created 4 query files (~800 lines): users, roles, permissions, entities
- Migrated 6 pages/components to useQuery()
- Implemented 15 mutations with optimistic updates
- Removed ~1,200 lines of boilerplate

**Phase 2: Backend API Fixes** ✅ Complete
- Added `/v1` URL prefix to all routes
- Created `PaginatedResponse<T>` schema
- Added list endpoints for users, roles, permissions, memberships
- Fixed permission resolution bug

**Phase 2.5: Integration Fixes** ✅ Complete
- Fixed auth endpoint URLs with `/v1` prefix
- Fixed permission dependency to fetch from database
- Aligned frontend types with backend data model
- Created user enrichment composable

**Phase 2.6: Permission Service Bug** ✅ Complete
- Added `.fetch_links()` to populate Beanie Link fields
- Removed silent fallback in permission dependency
- All permission-protected endpoints now work correctly

**Current Status**: Ready for production testing!

**For complete migration details, see**: `auth-ui/PINIA_COLADA_MIGRATION.md`

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

**Architecture**: After Pinia Colada migration, stores are used for **local UI state only**. All data fetching is handled by Pinia Colada queries and mutations.

### Auth Store (`auth.store.ts`)

**Purpose**: JWT authentication, token refresh, API calls, **config detection**

**Responsibilities**:
- ✅ Authentication state (tokens, user)
- ✅ Config detection (SimpleRBAC vs EnterpriseRBAC)
- ✅ Authenticated API client (`apiCall` method)
- ❌ **NOT** data fetching (handled by Pinia Colada)

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

**Responsibilities**:
- ✅ Current entity context
- ✅ Entity switching logic
- ✅ Context headers for API calls
- ❌ **NOT** entity data fetching (handled by Pinia Colada)

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

**Integration with Pinia Colada**:
```typescript
// Queries automatically react to context changes
const { data: users } = useQuery({
  key: computed(() => ['users', contextStore.selectedEntity?.id]),
  query: () => fetchUsers()
})

// When context switches → key changes → auto-refetch
```

### Resource Stores (Deprecated Pattern)

**⚠️ Legacy Pattern** - Pre-Pinia Colada migration:

```typescript
// ❌ OLD PATTERN (Don't use anymore)
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

  return { state, fetchRoles }
})
```

**✅ NEW PATTERN** - Use Pinia Colada instead:

```typescript
// In component
import { useQuery } from '@pinia/colada'
import { rolesQueries } from '~/queries/roles'

const { data: rolesData, isLoading, error } = useQuery(
  () => rolesQueries.list()
)

// ✅ No store needed for data fetching!
// ✅ Automatic loading states
// ✅ Automatic caching
// ✅ Automatic refetching
```

### When to Use Stores vs Pinia Colada

**Use Pinia Stores for:**
- ✅ Authentication state
- ✅ UI state (modals open/closed, selected items, etc.)
- ✅ App-level configuration
- ✅ Cross-cutting concerns (context, theme, etc.)

**Use Pinia Colada for:**
- ✅ Data fetching (users, roles, permissions, entities)
- ✅ Mutations (create, update, delete)
- ✅ Caching and invalidation
- ✅ Loading and error states

**Example: Local UI State**

```typescript
// Good use of a store - local UI state
export const useRolesUIStore = defineStore('rolesUI', () => {
  const state = reactive({
    isCreateModalOpen: false,
    isDeleteModalOpen: false,
    selectedRoleId: null as string | null,
    searchQuery: '',
  })

  const openCreateModal = () => {
    state.isCreateModalOpen = true
  }

  const closeCreateModal = () => {
    state.isCreateModalOpen = false
  }

  return { state, openCreateModal, closeCreateModal }
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
bun install
bun run dev
```

Runs on **http://localhost:3000**

### Production Build

```bash
bun run build
bun run preview
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
bun run dev

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
NUXT_PUBLIC_API_BASE_URL=http://localhost:8004 bun run dev
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
