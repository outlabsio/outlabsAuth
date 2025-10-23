# OutlabsAuth Admin UI - Frontend Specification

**Version**: 1.0
**Date**: 2025-01-15
**Status**: Specification Phase
**Architecture**: Embeddable Component Library for Nuxt 4 + Nuxt UI v4

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Core Pinia Stores](#core-pinia-stores)
5. [Component Library](#component-library)
6. [Page Structure](#page-structure)
7. [Permission Waterfall Visualization](#permission-waterfall-visualization)
8. [Backend API Requirements](#backend-api-requirements)
9. [Implementation Phases](#implementation-phases)
10. [Migration from Old UI](#migration-from-old-ui)

---

## Overview

### What We're Building

An **embeddable component library** for managing OutlabsAuth users, roles, permissions, and entities. Unlike the old standalone admin UI, this is designed to be **dropped into any Nuxt 4 application** that uses OutlabsAuth.

### Core Principles

1. **Embeddable First** - Install via npm, import components where needed
2. **Pinia for Everything** - All state (including UI state) managed in stores
3. **Pages, Not Drawers** - Dedicated routes for editing (no slide-over drawers)
4. **Modals for Small Things** - Alerts, confirmations, quick forms only
5. **Nuxt UI v4 Native** - Matches your existing design system
6. **Reuse Proven Patterns** - Build on successful patterns from archived frontend

### Use Cases

**Use Case 1: Full Admin Interface**
```vue
<!-- pages/admin/auth.vue -->
<template>
  <OutlabsAuthAdmin />
</template>
```

**Use Case 2: Settings Page Integration**
```vue
<!-- pages/settings.vue -->
<template>
  <UContainer>
    <UTabs :items="tabs">
      <template #users>
        <OutlabsUserManager />
      </template>
      <template #roles>
        <OutlabsRoleManager />
      </template>
    </UTabs>
  </UContainer>
</template>
```

**Use Case 3: User Profile Enhancement**
```vue
<!-- pages/users/[id].vue -->
<template>
  <div>
    <UserProfile :user="user" />

    <!-- Show permission waterfall -->
    <OutlabsPermissionWaterfall
      :user-id="user.id"
      class="mt-6"
    />
  </div>
</template>
```

**Use Case 4: Custom UI with Stores**
```vue
<script setup lang="ts">
const authStore = useOutlabsAuthStore()
const userStore = useOutlabsUsersStore()

const { users, isLoading } = storeToRefs(userStore)

onMounted(async () => {
  await userStore.fetchUsers()
})
</script>

<template>
  <div>
    <h1>Custom User List</h1>
    <div v-for="user in users" :key="user.id">
      {{ user.email }}
    </div>
  </div>
</template>
```

---

## Architecture

### Package Structure

```
@outlabs/auth-ui/
├── package.json
├── nuxt.config.ts                  # Nuxt layer configuration
├── components/
│   ├── OutlabsAuthAdmin.vue        # Full admin interface
│   ├── OutlabsUserManager.vue      # User management
│   ├── OutlabsRoleManager.vue      # Role management
│   ├── OutlabsEntityTree.vue       # Entity hierarchy
│   ├── OutlabsPermissionWaterfall.vue  # ⭐ Killer feature
│   ├── OutlabsApiKeyManager.vue    # API key management
│   ├── OutlabsAuditLog.vue         # Audit logs
│   ├── users/
│   │   ├── UserList.vue
│   │   ├── UserCard.vue
│   │   └── UserForm.vue
│   ├── roles/
│   │   ├── RoleList.vue
│   │   ├── RoleCard.vue
│   │   └── RoleForm.vue
│   ├── entities/
│   │   ├── EntityTree.vue
│   │   ├── EntityNode.vue
│   │   └── EntityForm.vue
│   └── shared/
│       ├── PermissionBadge.vue
│       ├── EntityBreadcrumb.vue
│       └── LoadingState.vue
├── stores/
│   ├── auth.store.ts               # Auth, tokens, current user
│   ├── context.store.ts            # Entity context switching
│   ├── users.store.ts              # User CRUD
│   ├── roles.store.ts              # Role CRUD
│   ├── permissions.store.ts        # Permission checking
│   ├── entities.store.ts           # Entity hierarchy
│   ├── apiKeys.store.ts            # API key management
│   ├── audit.store.ts              # Audit logs
│   └── ui.store.ts                 # UI state (modals, loading, etc.)
├── composables/
│   ├── useOutlabsAuth.ts           # Auth helpers
│   ├── usePermissionCheck.ts       # Permission checking
│   └── useEntityContext.ts         # Entity context helpers
├── types/
│   ├── index.ts
│   ├── user.types.ts
│   ├── role.types.ts
│   ├── entity.types.ts
│   └── permission.types.ts
├── middleware/
│   └── outlabs-auth.global.ts      # Global auth middleware
└── pages/
    └── outlabs-admin/              # Pre-built pages (optional)
        ├── index.vue               # Dashboard
        ├── users/
        │   ├── index.vue           # User list
        │   ├── [id].vue            # User detail/edit
        │   └── create.vue          # Create user
        ├── roles/
        │   ├── index.vue
        │   ├── [id].vue
        │   └── create.vue
        ├── entities/
        │   ├── index.vue
        │   ├── [id].vue
        │   └── create.vue
        └── api-keys/
            ├── index.vue
            └── create.vue
```

### Installation

```bash
npm install @outlabs/auth-ui
# or
bun add @outlabs/auth-ui
```

### Nuxt Configuration

```typescript
// nuxt.config.ts
export default defineNuxtConfig({
  extends: ['@outlabs/auth-ui'],

  runtimeConfig: {
    public: {
      outlabsAuth: {
        apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
        preset: 'enterprise' // or 'simple'
      }
    }
  }
})
```

### Auto-Import

All components, composables, and stores are auto-imported via Nuxt's auto-import system:

```vue
<template>
  <!-- Components auto-imported -->
  <OutlabsUserManager />

  <script setup>
  // Stores auto-imported
  const userStore = useOutlabsUsersStore()

  // Composables auto-imported
  const { hasPermission } = useOutlabsAuth()
  </script>
</template>
```

---

## Technology Stack

### Core Technologies

- **Framework**: Nuxt 4
- **UI Library**: Nuxt UI v4
- **State Management**: Pinia
- **Forms**: Nuxt UI Form components + Zod validation
- **Icons**: Heroicons (via Nuxt UI)
- **Styling**: Tailwind CSS (via Nuxt UI)
- **Type Safety**: TypeScript
- **Package Manager**: Bun (or npm/pnpm)

### Key Dependencies

```json
{
  "dependencies": {
    "nuxt": "^4.0.0",
    "@nuxt/ui": "^4.0.0",
    "pinia": "^2.2.0",
    "zod": "^3.22.0",
    "@vueuse/core": "^11.0.0"
  },
  "devDependencies": {
    "@nuxtjs/tailwindcss": "^6.12.0",
    "typescript": "^5.3.0"
  }
}
```

---

## Core Pinia Stores

All state management follows proven patterns from the archived frontend, adapted for the new library architecture.

### 1. Auth Store (`stores/auth.store.ts`)

**Purpose**: Handle authentication, tokens, and API calls with automatic refresh.

**Based on**: `_archive/frontend-old/app/stores/auth.store.ts` (proven pattern)

```typescript
// stores/auth.store.ts
import type { User, AuthTokens, SystemStatus } from '../types'

export const useOutlabsAuthStore = defineStore('outlabs-auth', () => {
  const config = useRuntimeConfig()

  // State
  const state = reactive({
    accessToken: null as string | null,
    refreshToken: null as string | null,
    user: null as User | null,
    isAuthenticated: false,
    systemStatus: null as SystemStatus | null,
  })

  // API call helper with automatic token refresh
  const apiCall = async <T>(endpoint: string, options: any = {}): Promise<T> => {
    const contextStore = useOutlabsContextStore()

    const makeRequest = async (token: string | null) => {
      const headers = {
        ...contextStore.getContextHeaders, // Inject entity context
        ...options.headers,
        ...(token && { Authorization: `Bearer ${token}` }),
      }

      return await $fetch<T>(endpoint, {
        ...options,
        baseURL: config.public.outlabsAuth.apiBaseUrl,
        headers,
        credentials: 'include',
      })
    }

    try {
      return await makeRequest(state.accessToken)
    } catch (error: any) {
      // Auto-refresh on 401
      if (error.status === 401 && state.accessToken) {
        try {
          const newToken = await refreshAccessToken()
          return await makeRequest(newToken)
        } catch (refreshError) {
          clearAuth()
          throw refreshError
        }
      }
      throw error
    }
  }

  const refreshAccessToken = async () => {
    const response = await $fetch<AuthTokens>('/v1/auth/refresh', {
      baseURL: config.public.outlabsAuth.apiBaseUrl,
      method: 'POST',
      credentials: 'include',
    })

    if (response.access_token) {
      state.accessToken = response.access_token
      state.refreshToken = 'httponly-cookie'
      state.isAuthenticated = true
      return response.access_token
    }

    throw new Error('No access token in refresh response')
  }

  const initialize = async () => {
    try {
      // Try to refresh token from httpOnly cookie
      await refreshAccessToken()
      const userData = await apiCall<User>('/v1/auth/me')
      state.user = userData
      state.isAuthenticated = true
      return true
    } catch (error) {
      console.log('No valid session found')
      return false
    }
  }

  const login = async (email: string, password: string) => {
    const response = await $fetch<AuthTokens>('/v1/auth/login', {
      baseURL: config.public.outlabsAuth.apiBaseUrl,
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username: email.trim(),
        password: password,
      }),
      credentials: 'include',
    })

    state.accessToken = response.access_token
    state.refreshToken = 'httponly-cookie'
    state.isAuthenticated = true

    const userData = await apiCall<User>('/v1/auth/me')
    state.user = userData

    return true
  }

  const logout = async () => {
    try {
      await apiCall('/v1/auth/logout', { method: 'POST' })
    } catch (error) {
      console.warn('Logout endpoint error:', error)
    } finally {
      clearAuth()
    }
  }

  const clearAuth = () => {
    state.accessToken = null
    state.refreshToken = null
    state.user = null
    state.isAuthenticated = false
  }

  return {
    // State (as computed)
    isAuthenticated: computed(() => state.isAuthenticated),
    accessToken: computed(() => state.accessToken),
    user: computed(() => state.user),

    // Actions
    initialize,
    login,
    logout,
    refreshAccessToken,
    apiCall,
    clearAuth,
  }
})
```

### 2. Context Store (`stores/context.store.ts`)

**Purpose**: Handle entity/organization context switching for multi-entity environments.

**Based on**: `_archive/frontend-old/app/stores/context-store.ts` (proven pattern)

```typescript
// stores/context.store.ts
import type { EntityContext } from '../types'

const SYSTEM_CONTEXT: EntityContext = {
  id: 'system',
  name: 'System Administration',
  slug: 'system',
  entity_type: 'SYSTEM',
  entity_class: 'PLATFORM',
  is_system: true,
}

export const useOutlabsContextStore = defineStore('outlabs-context', {
  state: () => ({
    selectedEntity: null as EntityContext | null,
    availableEntities: [] as EntityContext[],
  }),

  actions: {
    setSelectedEntity(entity: EntityContext | null) {
      this.selectedEntity = entity

      // Persist to localStorage
      if (process.client) {
        if (entity) {
          localStorage.setItem('outlabs-selected-entity', JSON.stringify(entity))
        } else {
          localStorage.removeItem('outlabs-selected-entity')
        }
      }
    },

    loadPersistedEntity() {
      if (process.client) {
        try {
          const stored = localStorage.getItem('outlabs-selected-entity')
          if (stored) {
            this.selectedEntity = JSON.parse(stored)
          }
        } catch (error) {
          console.error('Failed to load persisted entity:', error)
          localStorage.removeItem('outlabs-selected-entity')
        }
      }
    },

    async fetchTopLevelEntities() {
      const authStore = useOutlabsAuthStore()
      const response = await authStore.apiCall<EntityContext[]>('/v1/entities/top-level')

      const withSystem = [SYSTEM_CONTEXT, ...response]
      this.availableEntities = withSystem

      if (!this.selectedEntity && withSystem.length > 0) {
        this.selectedEntity = withSystem[0]
      }

      return response
    },

    clearContext() {
      this.selectedEntity = null
      this.availableEntities = []
    },
  },

  getters: {
    isSystemContext(): boolean {
      return this.selectedEntity?.is_system === true
    },

    getContextHeaders(): Record<string, string> {
      if (!this.selectedEntity || this.selectedEntity.is_system) {
        return {}
      }
      return {
        'X-Entity-Context': this.selectedEntity.id,
      }
    },

    currentEntity(): EntityContext {
      return this.selectedEntity || SYSTEM_CONTEXT
    },
  },
})
```

### 3. Users Store (`stores/users.store.ts`)

```typescript
// stores/users.store.ts
import type { User, CreateUserInput, UpdateUserInput, PaginatedResponse } from '../types'

export const useOutlabsUsersStore = defineStore('outlabs-users', () => {
  const authStore = useOutlabsAuthStore()

  const state = reactive({
    users: [] as User[],
    selectedUser: null as User | null,
    isLoading: false,
    error: null as string | null,
    pagination: {
      page: 1,
      limit: 20,
      total: 0,
    },
  })

  const fetchUsers = async (page: number = 1, search?: string) => {
    state.isLoading = true
    state.error = null

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: state.pagination.limit.toString(),
        ...(search && { search }),
      })

      const response = await authStore.apiCall<PaginatedResponse<User>>(
        `/v1/users?${params}`
      )

      state.users = response.items
      state.pagination.total = response.total
      state.pagination.page = page
    } catch (error: any) {
      state.error = error.message
      throw error
    } finally {
      state.isLoading = false
    }
  }

  const fetchUser = async (userId: string) => {
    state.isLoading = true
    try {
      const user = await authStore.apiCall<User>(`/v1/users/${userId}`)
      state.selectedUser = user
      return user
    } catch (error: any) {
      state.error = error.message
      throw error
    } finally {
      state.isLoading = false
    }
  }

  const createUser = async (data: CreateUserInput) => {
    const user = await authStore.apiCall<User>('/v1/users', {
      method: 'POST',
      body: data,
    })

    state.users.unshift(user)
    return user
  }

  const updateUser = async (userId: string, data: UpdateUserInput) => {
    const user = await authStore.apiCall<User>(`/v1/users/${userId}`, {
      method: 'PUT',
      body: data,
    })

    const index = state.users.findIndex(u => u.id === userId)
    if (index !== -1) {
      state.users[index] = user
    }

    if (state.selectedUser?.id === userId) {
      state.selectedUser = user
    }

    return user
  }

  const deleteUser = async (userId: string) => {
    await authStore.apiCall(`/v1/users/${userId}`, {
      method: 'DELETE',
    })

    state.users = state.users.filter(u => u.id !== userId)

    if (state.selectedUser?.id === userId) {
      state.selectedUser = null
    }
  }

  return {
    // State
    users: computed(() => state.users),
    selectedUser: computed(() => state.selectedUser),
    isLoading: computed(() => state.isLoading),
    error: computed(() => state.error),
    pagination: computed(() => state.pagination),

    // Actions
    fetchUsers,
    fetchUser,
    createUser,
    updateUser,
    deleteUser,
  }
})
```

### 4. Roles Store (`stores/roles.store.ts`)

```typescript
// stores/roles.store.ts
import type { Role, CreateRoleInput, UpdateRoleInput } from '../types'

export const useOutlabsRolesStore = defineStore('outlabs-roles', () => {
  const authStore = useOutlabsAuthStore()

  const state = reactive({
    roles: [] as Role[],
    selectedRole: null as Role | null,
    isLoading: false,
    error: null as string | null,
  })

  const fetchRoles = async () => {
    state.isLoading = true
    try {
      const response = await authStore.apiCall<Role[]>('/v1/roles')
      state.roles = response
    } catch (error: any) {
      state.error = error.message
      throw error
    } finally {
      state.isLoading = false
    }
  }

  const fetchRole = async (roleId: string) => {
    state.isLoading = true
    try {
      const role = await authStore.apiCall<Role>(`/v1/roles/${roleId}`)
      state.selectedRole = role
      return role
    } finally {
      state.isLoading = false
    }
  }

  const createRole = async (data: CreateRoleInput) => {
    const role = await authStore.apiCall<Role>('/v1/roles', {
      method: 'POST',
      body: data,
    })

    state.roles.push(role)
    return role
  }

  const updateRole = async (roleId: string, data: UpdateRoleInput) => {
    const role = await authStore.apiCall<Role>(`/v1/roles/${roleId}`, {
      method: 'PUT',
      body: data,
    })

    const index = state.roles.findIndex(r => r.id === roleId)
    if (index !== -1) {
      state.roles[index] = role
    }

    return role
  }

  const deleteRole = async (roleId: string) => {
    await authStore.apiCall(`/v1/roles/${roleId}`, {
      method: 'DELETE',
    })

    state.roles = state.roles.filter(r => r.id !== roleId)
  }

  return {
    roles: computed(() => state.roles),
    selectedRole: computed(() => state.selectedRole),
    isLoading: computed(() => state.isLoading),
    fetchRoles,
    fetchRole,
    createRole,
    updateRole,
    deleteRole,
  }
})
```

### 5. Entities Store (`stores/entities.store.ts`)

```typescript
// stores/entities.store.ts
import type { Entity, CreateEntityInput, UpdateEntityInput, EntityTreeNode } from '../types'

export const useOutlabsEntitiesStore = defineStore('outlabs-entities', () => {
  const authStore = useOutlabsAuthStore()

  const state = reactive({
    entities: [] as Entity[],
    entityTree: null as EntityTreeNode | null,
    selectedEntity: null as Entity | null,
    isLoading: false,
    error: null as string | null,
  })

  const fetchEntities = async () => {
    state.isLoading = true
    try {
      const response = await authStore.apiCall<Entity[]>('/v1/entities')
      state.entities = response
    } catch (error: any) {
      state.error = error.message
      throw error
    } finally {
      state.isLoading = false
    }
  }

  const fetchEntityTree = async () => {
    state.isLoading = true
    try {
      const response = await authStore.apiCall<EntityTreeNode>('/v1/entities/tree')
      state.entityTree = response
    } finally {
      state.isLoading = false
    }
  }

  const fetchEntity = async (entityId: string) => {
    const entity = await authStore.apiCall<Entity>(`/v1/entities/${entityId}`)
    state.selectedEntity = entity
    return entity
  }

  const createEntity = async (data: CreateEntityInput) => {
    const entity = await authStore.apiCall<Entity>('/v1/entities', {
      method: 'POST',
      body: data,
    })

    state.entities.push(entity)
    return entity
  }

  const updateEntity = async (entityId: string, data: UpdateEntityInput) => {
    const entity = await authStore.apiCall<Entity>(`/v1/entities/${entityId}`, {
      method: 'PUT',
      body: data,
    })

    const index = state.entities.findIndex(e => e.id === entityId)
    if (index !== -1) {
      state.entities[index] = entity
    }

    return entity
  }

  const deleteEntity = async (entityId: string) => {
    await authStore.apiCall(`/v1/entities/${entityId}`, {
      method: 'DELETE',
    })

    state.entities = state.entities.filter(e => e.id !== entityId)
  }

  return {
    entities: computed(() => state.entities),
    entityTree: computed(() => state.entityTree),
    selectedEntity: computed(() => state.selectedEntity),
    isLoading: computed(() => state.isLoading),
    fetchEntities,
    fetchEntityTree,
    fetchEntity,
    createEntity,
    updateEntity,
    deleteEntity,
  }
})
```

### 6. Permissions Store (`stores/permissions.store.ts`)

```typescript
// stores/permissions.store.ts
import type { PermissionWaterfall, PermissionCheck } from '../types'

export const useOutlabsPermissionsStore = defineStore('outlabs-permissions', () => {
  const authStore = useOutlabsAuthStore()

  const state = reactive({
    waterfallCache: new Map<string, PermissionWaterfall>(),
    isLoading: false,
  })

  // Get permission waterfall for a user (THE KILLER FEATURE)
  const getPermissionWaterfall = async (userId: string, entityId?: string) => {
    const cacheKey = `${userId}:${entityId || 'global'}`

    if (state.waterfallCache.has(cacheKey)) {
      return state.waterfallCache.get(cacheKey)!
    }

    state.isLoading = true
    try {
      const params = new URLSearchParams({ user_id: userId })
      if (entityId) {
        params.append('entity_id', entityId)
      }

      const waterfall = await authStore.apiCall<PermissionWaterfall>(
        `/v1/permissions/waterfall?${params}`
      )

      state.waterfallCache.set(cacheKey, waterfall)
      return waterfall
    } finally {
      state.isLoading = false
    }
  }

  // Check if user has permission
  const checkPermission = async (
    userId: string,
    permission: string,
    entityId?: string
  ): Promise<PermissionCheck> => {
    const params = new URLSearchParams({
      user_id: userId,
      permission,
    })

    if (entityId) {
      params.append('entity_id', entityId)
    }

    return await authStore.apiCall<PermissionCheck>(
      `/v1/permissions/check?${params}`
    )
  }

  // Clear cache (when permissions change)
  const clearCache = () => {
    state.waterfallCache.clear()
  }

  return {
    isLoading: computed(() => state.isLoading),
    getPermissionWaterfall,
    checkPermission,
    clearCache,
  }
})
```

### 7. API Keys Store (`stores/apiKeys.store.ts`)

```typescript
// stores/apiKeys.store.ts
import type { ApiKey, CreateApiKeyInput, ApiKeyWithSecret } from '../types'

export const useOutlabsApiKeysStore = defineStore('outlabs-api-keys', () => {
  const authStore = useOutlabsAuthStore()

  const state = reactive({
    apiKeys: [] as ApiKey[],
    selectedKey: null as ApiKey | null,
    isLoading: false,
  })

  const fetchApiKeys = async () => {
    state.isLoading = true
    try {
      const response = await authStore.apiCall<ApiKey[]>('/v1/api-keys')
      state.apiKeys = response
    } finally {
      state.isLoading = false
    }
  }

  const createApiKey = async (data: CreateApiKeyInput) => {
    const response = await authStore.apiCall<ApiKeyWithSecret>('/v1/api-keys', {
      method: 'POST',
      body: data,
    })

    state.apiKeys.push(response.api_key)

    // Return full response with raw key (shown only once!)
    return response
  }

  const rotateApiKey = async (keyId: string) => {
    const response = await authStore.apiCall<ApiKeyWithSecret>(
      `/v1/api-keys/${keyId}/rotate`,
      { method: 'POST' }
    )

    // Update list
    const index = state.apiKeys.findIndex(k => k.id === keyId)
    if (index !== -1) {
      state.apiKeys[index] = response.api_key
    }

    return response
  }

  const revokeApiKey = async (keyId: string) => {
    await authStore.apiCall(`/v1/api-keys/${keyId}`, {
      method: 'DELETE',
    })

    state.apiKeys = state.apiKeys.filter(k => k.id !== keyId)
  }

  return {
    apiKeys: computed(() => state.apiKeys),
    selectedKey: computed(() => state.selectedKey),
    isLoading: computed(() => state.isLoading),
    fetchApiKeys,
    createApiKey,
    rotateApiKey,
    revokeApiKey,
  }
})
```

### 8. UI Store (`stores/ui.store.ts`)

**Purpose**: Manage UI state (modals, toasts, loading overlays, etc.)

```typescript
// stores/ui.store.ts
export const useOutlabsUIStore = defineStore('outlabs-ui', {
  state: () => ({
    // Modal state
    modals: {
      deleteUser: { open: false, userId: null as string | null },
      deleteRole: { open: false, roleId: null as string | null },
      deleteEntity: { open: false, entityId: null as string | null },
      showApiKey: { open: false, apiKey: null as string | null },
      confirmAction: { open: false, message: '', onConfirm: null as (() => void) | null },
    },

    // Loading overlays
    loadingOverlay: false,
    loadingMessage: '',

    // Toasts (managed by Nuxt UI toast system)
  }),

  actions: {
    openModal(modalName: keyof typeof this.modals, data?: any) {
      this.modals[modalName].open = true
      if (data) {
        Object.assign(this.modals[modalName], data)
      }
    },

    closeModal(modalName: keyof typeof this.modals) {
      this.modals[modalName].open = false
    },

    showLoadingOverlay(message: string = 'Loading...') {
      this.loadingOverlay = true
      this.loadingMessage = message
    },

    hideLoadingOverlay() {
      this.loadingOverlay = false
      this.loadingMessage = ''
    },
  },
})
```

---

## Component Library

### Top-Level Components

#### 1. `<OutlabsAuthAdmin>` - Full Admin Interface

**Purpose**: Drop-in complete admin UI with routing.

**Props:**
```typescript
interface OutlabsAuthAdminProps {
  apiBaseUrl?: string         // Override API URL
  preset?: 'simple' | 'enterprise'  // Preset mode
  hideNavigation?: boolean    // Hide sidebar navigation
}
```

**Usage:**
```vue
<template>
  <OutlabsAuthAdmin />
</template>
```

**Features:**
- Full navigation sidebar
- All management pages (users, roles, entities, API keys)
- Dashboard with stats
- Context switcher (for enterprise mode)

#### 2. `<OutlabsUserManager>` - User Management

**Purpose**: Complete user management interface.

**Props:**
```typescript
interface OutlabsUserManagerProps {
  entityId?: string          // Filter by entity
  hideCreate?: boolean       // Hide create button
  hideActions?: boolean      // Hide edit/delete actions
}

interface OutlabsUserManagerEmits {
  (e: 'user-created', user: User): void
  (e: 'user-updated', user: User): void
  (e: 'user-deleted', userId: string): void
}
```

**Usage:**
```vue
<OutlabsUserManager
  :entity-id="currentEntity.id"
  @user-created="handleUserCreated"
/>
```

#### 3. `<OutlabsRoleManager>` - Role Management

Similar to user manager but for roles.

#### 4. `<OutlabsEntityTree>` - Entity Hierarchy Visualization

**Purpose**: Interactive tree view of entity hierarchy.

**Props:**
```typescript
interface OutlabsEntityTreeProps {
  rootEntityId?: string      // Start from specific entity
  expandAll?: boolean        // Expand all nodes by default
  selectable?: boolean       // Allow selection
  draggable?: boolean        // Allow drag-and-drop reorganization
}

interface OutlabsEntityTreeEmits {
  (e: 'node-selected', entity: Entity): void
  (e: 'node-moved', data: { entityId: string, newParentId: string }): void
}
```

**Features:**
- Expandable/collapsible tree
- Drag-and-drop to reorganize (if `draggable`)
- Click to select/view details
- Visual indicators for entity class (STRUCTURAL vs ACCESS_GROUP)

#### 5. `<OutlabsPermissionWaterfall>` - ⭐ Permission Waterfall (Killer Feature)

**Purpose**: Visual cascade showing exactly how a user gets their permissions.

**Props:**
```typescript
interface OutlabsPermissionWaterfallProps {
  userId: string             // User to analyze
  entityId?: string          // Scope to specific entity
  showInherited?: boolean    // Show inherited permissions
  expandAll?: boolean        // Expand all sections by default
}
```

**Usage:**
```vue
<OutlabsPermissionWaterfall
  :user-id="userId"
  :entity-id="currentEntity.id"
  expand-all
/>
```

**See detailed spec in [Permission Waterfall Visualization](#permission-waterfall-visualization) section below.**

#### 6. `<OutlabsApiKeyManager>` - API Key Management

**Purpose**: Create, rotate, and revoke API keys.

**Features:**
- List all API keys (with prefix, not full key)
- Create new keys (shows full key ONCE)
- Rotate keys (with grace period)
- Revoke keys
- Key usage statistics
- Copy to clipboard

#### 7. `<OutlabsAuditLog>` - Audit Log Viewer

**Purpose**: View security and activity logs.

**Props:**
```typescript
interface OutlabsAuditLogProps {
  userId?: string            // Filter by user
  entityId?: string          // Filter by entity
  action?: string            // Filter by action type
  limit?: number             // Items per page
}
```

---

### Supporting Components

#### User Components

**`<UserList>`** - Table/grid of users
**`<UserCard>`** - User profile card
**`<UserForm>`** - Create/edit user form with Zod validation

#### Role Components

**`<RoleList>`** - Table of roles
**`<RoleCard>`** - Role detail card
**`<RoleForm>`** - Create/edit role form
**`<PermissionSelector>`** - Multi-select for permissions

#### Entity Components

**`<EntityNode>`** - Single tree node with actions
**`<EntityBreadcrumb>`** - Entity path breadcrumb
**`<EntityForm>`** - Create/edit entity form

#### Shared Components

**`<PermissionBadge>`** - Visual badge for permission
**`<LoadingState>`** - Loading skeleton
**`<EmptyState>`** - Empty state placeholder
**`<ConfirmModal>`** - Reusable confirmation modal

---

## Page Structure

### Philosophy: Dedicated Pages, Not Drawers

**Old Pattern (Archived UI):**
- List page + drawer for editing
- Drawer slides in from right
- Content below drawer is dimmed

**New Pattern:**
- List page → separate detail/edit page
- Clean URLs (`/users/123/edit`)
- Proper browser history
- Better for bookmarking and sharing

### Page Routes

```
/outlabs-admin/
├── index.vue                   # Dashboard
├── users/
│   ├── index.vue               # User list
│   ├── [id].vue                # User detail (view mode)
│   ├── [id]/edit.vue           # User edit
│   └── create.vue              # Create user
├── roles/
│   ├── index.vue
│   ├── [id].vue
│   ├── [id]/edit.vue
│   └── create.vue
├── entities/
│   ├── index.vue               # Entity tree view
│   ├── [id].vue                # Entity detail
│   ├── [id]/edit.vue
│   └── create.vue
├── api-keys/
│   ├── index.vue               # API key list
│   └── create.vue              # Create API key
└── audit-log/
    └── index.vue               # Audit log viewer
```

### Example: User List Page

```vue
<!-- pages/outlabs-admin/users/index.vue -->
<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Users</h1>
      <UButton
        icon="i-heroicons-plus"
        to="/outlabs-admin/users/create"
      >
        Create User
      </UButton>
    </div>

    <!-- Search and filters -->
    <div class="mb-6">
      <UInput
        v-model="search"
        icon="i-heroicons-magnifying-glass"
        placeholder="Search users..."
        @input="debouncedSearch"
      />
    </div>

    <!-- User table -->
    <UTable
      :rows="users"
      :columns="columns"
      :loading="isLoading"
      @select="handleRowClick"
    >
      <template #actions="{ row }">
        <UDropdown :items="getActions(row)">
          <UButton
            icon="i-heroicons-ellipsis-vertical"
            variant="ghost"
          />
        </UDropdown>
      </template>
    </UTable>

    <!-- Pagination -->
    <UPagination
      v-model="page"
      :total="pagination.total"
      :per-page="pagination.limit"
      @update:model-value="fetchUsers"
    />
  </div>
</template>

<script setup lang="ts">
const userStore = useOutlabsUsersStore()
const router = useRouter()

const { users, isLoading, pagination } = storeToRefs(userStore)
const search = ref('')
const page = ref(1)

const columns = [
  { key: 'email', label: 'Email' },
  { key: 'name', label: 'Name' },
  { key: 'status', label: 'Status' },
  { key: 'created_at', label: 'Created' },
  { key: 'actions', label: '' },
]

const getActions = (user: User) => [[
  {
    label: 'View',
    icon: 'i-heroicons-eye',
    click: () => router.push(`/outlabs-admin/users/${user.id}`)
  },
  {
    label: 'Edit',
    icon: 'i-heroicons-pencil',
    click: () => router.push(`/outlabs-admin/users/${user.id}/edit`)
  },
  {
    label: 'Delete',
    icon: 'i-heroicons-trash',
    click: () => handleDelete(user.id)
  }
]]

const handleRowClick = (row: User) => {
  router.push(`/outlabs-admin/users/${row.id}`)
}

const debouncedSearch = useDebounceFn(() => {
  fetchUsers()
}, 300)

const fetchUsers = async () => {
  await userStore.fetchUsers(page.value, search.value || undefined)
}

onMounted(() => {
  fetchUsers()
})
</script>
```

### Example: User Edit Page

```vue
<!-- pages/outlabs-admin/users/[id]/edit.vue -->
<template>
  <div>
    <div class="mb-6">
      <UButton
        icon="i-heroicons-arrow-left"
        variant="ghost"
        @click="$router.back()"
      >
        Back
      </UButton>
    </div>

    <h1 class="text-2xl font-bold mb-6">Edit User</h1>

    <UCard>
      <UForm
        :schema="schema"
        :state="state"
        @submit="onSubmit"
      >
        <UFormField name="email" label="Email">
          <UInput v-model="state.email" type="email" />
        </UFormField>

        <UFormField name="first_name" label="First Name">
          <UInput v-model="state.first_name" />
        </UFormField>

        <UFormField name="last_name" label="Last Name">
          <UInput v-model="state.last_name" />
        </UFormField>

        <UFormField name="status" label="Status">
          <USelect
            v-model="state.status"
            :options="statusOptions"
          />
        </UFormField>

        <div class="flex gap-2 mt-6">
          <UButton type="submit" :loading="isLoading">
            Save Changes
          </UButton>
          <UButton
            variant="outline"
            @click="$router.back()"
          >
            Cancel
          </UButton>
        </div>
      </UForm>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const route = useRoute()
const router = useRouter()
const userStore = useOutlabsUsersStore()
const toast = useToast()

const userId = route.params.id as string

const schema = z.object({
  email: z.string().email('Invalid email'),
  first_name: z.string().min(2, 'First name too short'),
  last_name: z.string().min(2, 'Last name too short'),
  status: z.enum(['active', 'inactive', 'suspended']),
})

const state = reactive({
  email: '',
  first_name: '',
  last_name: '',
  status: 'active' as 'active' | 'inactive' | 'suspended',
})

const { isLoading } = storeToRefs(userStore)

const statusOptions = [
  { label: 'Active', value: 'active' },
  { label: 'Inactive', value: 'inactive' },
  { label: 'Suspended', value: 'suspended' },
]

const onSubmit = async (event: FormSubmitEvent<z.infer<typeof schema>>) => {
  try {
    await userStore.updateUser(userId, event.data)
    toast.add({
      title: 'Success',
      description: 'User updated successfully',
      color: 'green',
    })
    router.push(`/outlabs-admin/users/${userId}`)
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message,
      color: 'red',
    })
  }
}

// Load user data
onMounted(async () => {
  const user = await userStore.fetchUser(userId)
  Object.assign(state, {
    email: user.email,
    first_name: user.profile.first_name,
    last_name: user.profile.last_name,
    status: user.status,
  })
})
</script>
```

### Modal Usage

Modals are ONLY for:
- Confirmation dialogs (delete, revoke, etc.)
- Quick forms (add permission to role, etc.)
- One-time displays (show API key secret)

**Example: Delete Confirmation Modal**

```vue
<!-- In list page -->
<template>
  <div>
    <!-- User list -->

    <!-- Delete confirmation modal -->
    <UModal v-model="deleteModal.open">
      <UCard>
        <template #header>
          <h3 class="text-lg font-semibold">Delete User</h3>
        </template>

        <p>Are you sure you want to delete this user? This action cannot be undone.</p>

        <template #footer>
          <div class="flex gap-2 justify-end">
            <UButton
              variant="outline"
              @click="deleteModal.open = false"
            >
              Cancel
            </UButton>
            <UButton
              color="red"
              :loading="isDeleting"
              @click="confirmDelete"
            >
              Delete
            </UButton>
          </div>
        </template>
      </UCard>
    </UModal>
  </div>
</template>

<script setup lang="ts">
const deleteModal = reactive({
  open: false,
  userId: null as string | null,
})

const handleDelete = (userId: string) => {
  deleteModal.userId = userId
  deleteModal.open = true
}

const confirmDelete = async () => {
  if (!deleteModal.userId) return

  try {
    await userStore.deleteUser(deleteModal.userId)
    toast.add({ title: 'User deleted', color: 'green' })
    deleteModal.open = false
  } catch (error: any) {
    toast.add({ title: 'Error', description: error.message, color: 'red' })
  }
}
</script>
```

---

## Permission Waterfall Visualization

### The Killer Feature

This is the **most important** and **most valuable** component in the entire UI. It answers the question:

> **"Why does this user have (or not have) this permission?"**

### What It Shows

The waterfall displays **all sources** of permissions for a user in a visual cascade:

1. **Direct Role Assignments** (SimpleRBAC)
   - User → Role → Permissions

2. **Entity Memberships** (EnterpriseRBAC)
   - User → Entity → Role → Permissions

3. **Tree Permissions** (EnterpriseRBAC)
   - Parent Entity → Role → Tree Permissions → Inherited by children

4. **Context-Aware Roles** (EnterpriseRBAC optional)
   - Same role, different permissions based on entity type

5. **ABAC Conditions** (EnterpriseRBAC optional)
   - Permission with conditions (shows evaluation result)

### Visual Design

```
┌─────────────────────────────────────────────────────────────┐
│  Permission Waterfall: john@example.com                     │
│  Context: Engineering Department                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ 📊 Summary                              │                │
│  │ ─────────────────────────────────────  │                │
│  │ Total Permissions: 47                   │                │
│  │ Direct: 12                              │                │
│  │ Inherited: 35                           │                │
│  │ Conditional: 8                          │                │
│  └────────────────────────────────────────┘                │
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ 👤 Direct Role Assignment               │                │
│  │ ─────────────────────────────────────  │                │
│  │ Role: Developer                         │                │
│  │ Assigned: System-wide                   │                │
│  │                                         │                │
│  │ Permissions (12):                       │                │
│  │ ✓ code:read         ✓ code:write       │                │
│  │ ✓ code:review       ✓ docs:read        │                │
│  │ ✓ docs:write        ✓ issue:create     │                │
│  │ ... (show all 12)                       │                │
│  └────────────────────────────────────────┘                │
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ 🏢 Entity Membership                    │                │
│  │ ─────────────────────────────────────  │                │
│  │ Entity: Engineering > Backend Team      │                │
│  │ Role: Team Lead                         │                │
│  │                                         │                │
│  │ Direct Permissions (8):                 │                │
│  │ ✓ team:read         ✓ team:update      │                │
│  │ ✓ member:add        ✓ member:remove    │                │
│  │ ... (show all 8)                        │                │
│  └────────────────────────────────────────┘                │
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ 🌲 Tree Permissions (Inherited)         │                │
│  │ ─────────────────────────────────────  │                │
│  │ From: Engineering (parent)              │                │
│  │ Role: Department Manager                │                │
│  │                                         │                │
│  │ Tree Permissions (18):                  │                │
│  │ ✓ entity:read_tree   → Inherited ✓     │                │
│  │ ✓ entity:update_tree → Inherited ✓     │                │
│  │ ✓ user:read_tree     → Inherited ✓     │                │
│  │ ✓ user:manage_tree   → Inherited ✓     │                │
│  │ ... (show all 18)                       │                │
│  │                                         │                │
│  │ 📍 Inheritance Path:                    │                │
│  │ Company > Engineering > Backend Team    │                │
│  │    └─ Manager role at Engineering       │                │
│  └────────────────────────────────────────┘                │
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ 🎭 Context-Aware Permissions            │                │
│  │ ─────────────────────────────────────  │                │
│  │ Role: Regional Manager                  │                │
│  │ Context: Team (current entity type)     │                │
│  │                                         │                │
│  │ At Department Level:                    │                │
│  │ ✓ budget:approve_tree                  │                │
│  │ ✓ user:manage_tree                     │                │
│  │                                         │                │
│  │ At Team Level: (7 permissions)          │                │
│  │ ✓ entity:read       ✓ user:read        │                │
│  │ ✓ report:view       ... (show all 7)   │                │
│  └────────────────────────────────────────┘                │
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ 🔒 ABAC Conditional Permissions         │                │
│  │ ─────────────────────────────────────  │                │
│  │ Permission: invoice:approve             │                │
│  │ Conditions:                             │                │
│  │   ✓ amount ≤ $50,000         ✅ PASS   │                │
│  │   ✓ status = pending         ✅ PASS   │                │
│  │   ✓ department = same        ✅ PASS   │                │
│  │                                         │                │
│  │ Result: ✅ Permission GRANTED           │                │
│  └────────────────────────────────────────┘                │
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ 🔍 Permission Test                      │                │
│  │ ─────────────────────────────────────  │                │
│  │ Test permission: [invoice:approve   ▼] │                │
│  │ In entity: [Engineering        ▼]      │                │
│  │                            [Test]       │                │
│  │                                         │                │
│  │ Result: ✅ ALLOWED                      │                │
│  │ Source: ABAC (invoice:approve)          │                │
│  │ Reason: All conditions met              │                │
│  └────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### Component Implementation

```vue
<!-- components/OutlabsPermissionWaterfall.vue -->
<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold">Permission Waterfall</h2>
        <p class="text-sm text-gray-500">
          {{ user?.email }} {{ entityId ? `in ${currentEntity?.name}` : '(Global)' }}
        </p>
      </div>

      <UButton
        icon="i-heroicons-arrow-path"
        variant="ghost"
        @click="refresh"
      >
        Refresh
      </UButton>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <UIcon name="i-heroicons-arrow-path" class="animate-spin w-8 h-8" />
    </div>

    <!-- Waterfall sections -->
    <div v-else-if="waterfall" class="space-y-4">
      <!-- Summary Card -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-chart-bar" />
            <h3 class="font-semibold">Summary</h3>
          </div>
        </template>

        <div class="grid grid-cols-4 gap-4">
          <div>
            <div class="text-2xl font-bold">{{ waterfall.total }}</div>
            <div class="text-sm text-gray-500">Total Permissions</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-blue-600">{{ waterfall.direct }}</div>
            <div class="text-sm text-gray-500">Direct</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-green-600">{{ waterfall.inherited }}</div>
            <div class="text-sm text-gray-500">Inherited</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-purple-600">{{ waterfall.conditional }}</div>
            <div class="text-sm text-gray-500">Conditional</div>
          </div>
        </div>
      </UCard>

      <!-- Direct Role Assignment -->
      <UCard v-if="waterfall.directRole">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-user" />
            <h3 class="font-semibold">Direct Role Assignment</h3>
          </div>
        </template>

        <div class="space-y-3">
          <div>
            <span class="text-sm text-gray-500">Role:</span>
            <span class="ml-2 font-medium">{{ waterfall.directRole.name }}</span>
          </div>

          <div>
            <span class="text-sm text-gray-500">Permissions ({{ waterfall.directRole.permissions.length }}):</span>
            <div class="flex flex-wrap gap-2 mt-2">
              <UBadge
                v-for="perm in waterfall.directRole.permissions"
                :key="perm"
                color="blue"
              >
                {{ perm }}
              </UBadge>
            </div>
          </div>
        </div>
      </UCard>

      <!-- Entity Memberships -->
      <UCard v-for="membership in waterfall.memberships" :key="membership.entity.id">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-building-office" />
            <h3 class="font-semibold">Entity Membership</h3>
          </div>
        </template>

        <div class="space-y-3">
          <div>
            <span class="text-sm text-gray-500">Entity:</span>
            <EntityBreadcrumb :entity-id="membership.entity.id" class="ml-2" />
          </div>

          <div>
            <span class="text-sm text-gray-500">Role:</span>
            <span class="ml-2 font-medium">{{ membership.role.name }}</span>
          </div>

          <div>
            <span class="text-sm text-gray-500">Permissions ({{ membership.permissions.length }}):</span>
            <div class="flex flex-wrap gap-2 mt-2">
              <UBadge
                v-for="perm in membership.permissions"
                :key="perm"
                color="green"
              >
                {{ perm }}
              </UBadge>
            </div>
          </div>
        </div>
      </UCard>

      <!-- Tree Permissions -->
      <UCard v-for="tree in waterfall.treePermissions" :key="tree.parentEntity.id">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-chart-bar-square" />
            <h3 class="font-semibold">Tree Permissions (Inherited)</h3>
          </div>
        </template>

        <div class="space-y-3">
          <div>
            <span class="text-sm text-gray-500">From:</span>
            <EntityBreadcrumb :entity-id="tree.parentEntity.id" class="ml-2" />
          </div>

          <div>
            <span class="text-sm text-gray-500">Role:</span>
            <span class="ml-2 font-medium">{{ tree.role.name }}</span>
          </div>

          <div>
            <span class="text-sm text-gray-500">Tree Permissions ({{ tree.permissions.length }}):</span>
            <div class="flex flex-wrap gap-2 mt-2">
              <UBadge
                v-for="perm in tree.permissions"
                :key="perm"
                color="amber"
              >
                {{ perm }} → Inherited ✓
              </UBadge>
            </div>
          </div>

          <div>
            <span class="text-sm text-gray-500">Inheritance Path:</span>
            <EntityBreadcrumb :entity-id="currentEntity.id" class="ml-2" />
          </div>
        </div>
      </UCard>

      <!-- Context-Aware Permissions -->
      <UCard v-if="waterfall.contextAware.length > 0">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-adjustments-horizontal" />
            <h3 class="font-semibold">Context-Aware Permissions</h3>
          </div>
        </template>

        <div class="space-y-4">
          <div v-for="ctx in waterfall.contextAware" :key="ctx.role.id">
            <div class="font-medium">{{ ctx.role.name }}</div>
            <div class="text-sm text-gray-500">Context: {{ ctx.entityType }}</div>

            <div class="flex flex-wrap gap-2 mt-2">
              <UBadge
                v-for="perm in ctx.permissions"
                :key="perm"
                color="purple"
              >
                {{ perm }}
              </UBadge>
            </div>
          </div>
        </div>
      </UCard>

      <!-- ABAC Conditional Permissions -->
      <UCard v-if="waterfall.abac.length > 0">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-shield-check" />
            <h3 class="font-semibold">ABAC Conditional Permissions</h3>
          </div>
        </template>

        <div class="space-y-4">
          <div
            v-for="abac in waterfall.abac"
            :key="abac.permission"
            class="border rounded-lg p-4"
          >
            <div class="font-medium mb-2">{{ abac.permission }}</div>

            <div class="text-sm space-y-1 mb-3">
              <div
                v-for="(condition, idx) in abac.conditions"
                :key="idx"
                class="flex items-center gap-2"
              >
                <UIcon
                  :name="condition.passed ? 'i-heroicons-check-circle' : 'i-heroicons-x-circle'"
                  :class="condition.passed ? 'text-green-500' : 'text-red-500'"
                />
                <span>{{ condition.description }}</span>
                <UBadge :color="condition.passed ? 'green' : 'red'">
                  {{ condition.passed ? 'PASS' : 'FAIL' }}
                </UBadge>
              </div>
            </div>

            <UBadge
              :color="abac.result === 'granted' ? 'green' : 'red'"
              size="lg"
            >
              {{ abac.result === 'granted' ? '✅ Permission GRANTED' : '❌ Permission DENIED' }}
            </UBadge>
          </div>
        </div>
      </UCard>

      <!-- Permission Test Tool -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-heroicons-beaker" />
            <h3 class="font-semibold">Permission Test</h3>
          </div>
        </template>

        <div class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <UFormField label="Test Permission">
              <UInput
                v-model="testPermission"
                placeholder="e.g., invoice:approve"
              />
            </UFormField>

            <UFormField label="In Entity (optional)">
              <USelect
                v-model="testEntityId"
                :options="entityOptions"
                placeholder="Select entity"
              />
            </UFormField>
          </div>

          <UButton @click="runPermissionTest">
            Test Permission
          </UButton>

          <div v-if="testResult" class="border rounded-lg p-4">
            <div class="flex items-center gap-2 mb-2">
              <UIcon
                :name="testResult.allowed ? 'i-heroicons-check-circle' : 'i-heroicons-x-circle'"
                :class="testResult.allowed ? 'text-green-500' : 'text-red-500'"
                class="w-6 h-6"
              />
              <span class="font-bold text-lg">
                {{ testResult.allowed ? 'ALLOWED' : 'DENIED' }}
              </span>
            </div>

            <div class="text-sm space-y-1">
              <div>
                <span class="text-gray-500">Source:</span>
                <span class="ml-2">{{ testResult.source }}</span>
              </div>
              <div>
                <span class="text-gray-500">Reason:</span>
                <span class="ml-2">{{ testResult.reason }}</span>
              </div>
            </div>
          </div>
        </div>
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PermissionWaterfall, PermissionCheck } from '../types'

interface Props {
  userId: string
  entityId?: string
  showInherited?: boolean
  expandAll?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showInherited: true,
  expandAll: false,
})

const permissionsStore = useOutlabsPermissionsStore()
const entitiesStore = useOutlabsEntitiesStore()
const userStore = useOutlabsUsersStore()

const { isLoading } = storeToRefs(permissionsStore)

const waterfall = ref<PermissionWaterfall | null>(null)
const user = ref(null)
const currentEntity = ref(null)

// Permission test
const testPermission = ref('')
const testEntityId = ref('')
const testResult = ref<PermissionCheck | null>(null)

const entityOptions = computed(() => {
  return entitiesStore.entities.map(e => ({
    label: e.name,
    value: e.id,
  }))
})

const refresh = async () => {
  waterfall.value = await permissionsStore.getPermissionWaterfall(
    props.userId,
    props.entityId
  )
}

const runPermissionTest = async () => {
  if (!testPermission.value) return

  testResult.value = await permissionsStore.checkPermission(
    props.userId,
    testPermission.value,
    testEntityId.value || undefined
  )
}

onMounted(async () => {
  await refresh()
  user.value = await userStore.fetchUser(props.userId)

  if (props.entityId) {
    currentEntity.value = await entitiesStore.fetchEntity(props.entityId)
  }
})
</script>
```

### Backend API Requirement

```typescript
// GET /v1/permissions/waterfall?user_id={userId}&entity_id={entityId}
interface PermissionWaterfall {
  user: {
    id: string
    email: string
  }
  entity?: {
    id: string
    name: string
  }
  total: number
  direct: number
  inherited: number
  conditional: number
  directRole?: {
    id: string
    name: string
    permissions: string[]
  }
  memberships: Array<{
    entity: { id: string, name: string, path: string[] }
    role: { id: string, name: string }
    permissions: string[]
  }>
  treePermissions: Array<{
    parentEntity: { id: string, name: string }
    role: { id: string, name: string }
    permissions: string[]
    inheritancePath: string[]
  }>
  contextAware: Array<{
    role: { id: string, name: string }
    entityType: string
    permissions: string[]
  }>
  abac: Array<{
    permission: string
    conditions: Array<{
      description: string
      passed: boolean
    }>
    result: 'granted' | 'denied'
  }>
}
```

---

## Backend API Requirements

### Admin API Service

The frontend requires a **FastAPI service** that uses the OutlabsAuth library and exposes admin endpoints.

**Architecture:**
```
Frontend (Nuxt 4)
      ↓ HTTP/REST
Admin API Service (FastAPI)
      ↓ Uses OutlabsAuth library
auth = EnterpriseRBAC(database=mongo)
      ↓
MongoDB
```

### Required Endpoints

#### Authentication
- `POST /v1/auth/login` - Login with username/password
- `POST /v1/auth/refresh` - Refresh access token
- `POST /v1/auth/logout` - Logout
- `GET /v1/auth/me` - Get current user

#### Users
- `GET /v1/users` - List users (paginated, searchable)
- `GET /v1/users/{id}` - Get user details
- `POST /v1/users` - Create user
- `PUT /v1/users/{id}` - Update user
- `DELETE /v1/users/{id}` - Delete user

#### Roles
- `GET /v1/roles` - List all roles
- `GET /v1/roles/{id}` - Get role details
- `POST /v1/roles` - Create role
- `PUT /v1/roles/{id}` - Update role
- `DELETE /v1/roles/{id}` - Delete role

#### Entities (EnterpriseRBAC only)
- `GET /v1/entities` - List all entities
- `GET /v1/entities/tree` - Get entity hierarchy tree
- `GET /v1/entities/top-level` - Get top-level entities
- `GET /v1/entities/{id}` - Get entity details
- `POST /v1/entities` - Create entity
- `PUT /v1/entities/{id}` - Update entity
- `DELETE /v1/entities/{id}` - Delete entity

#### Permissions
- `GET /v1/permissions/waterfall` - Get permission waterfall for user ⭐
- `GET /v1/permissions/check` - Check if user has permission

#### API Keys
- `GET /v1/api-keys` - List API keys
- `POST /v1/api-keys` - Create API key (returns raw key once!)
- `POST /v1/api-keys/{id}/rotate` - Rotate API key
- `DELETE /v1/api-keys/{id}` - Revoke API key

#### Audit Log
- `GET /v1/audit-log` - Get audit log entries

### Example Admin API Service

```python
# admin_api/main.py
from fastapi import FastAPI, Depends
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.dependencies import AuthDeps
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

# Initialize auth
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
database = mongo_client["outlabs_auth"]

auth = EnterpriseRBAC(
    database=database,
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

deps = AuthDeps(auth)

@app.on_event("startup")
async def startup():
    await auth.initialize()

# Users endpoints
@app.get("/v1/users")
async def list_users(
    page: int = 1,
    limit: int = 20,
    search: str = None,
    ctx = Depends(deps.require_permission("user:read"))
):
    return await auth.user_service.list_users(page, limit, search)

@app.post("/v1/users")
async def create_user(
    data: dict,
    ctx = Depends(deps.require_permission("user:create"))
):
    return await auth.user_service.create_user(**data)

# Permission waterfall endpoint ⭐
@app.get("/v1/permissions/waterfall")
async def get_permission_waterfall(
    user_id: str,
    entity_id: str = None,
    ctx = Depends(deps.require_permission("permission:view"))
):
    return await auth.permission_service.get_waterfall(user_id, entity_id)

# ... more endpoints
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal**: Core infrastructure and auth flow.

**Tasks:**
- [ ] Set up package structure (`@outlabs/auth-ui`)
- [ ] Implement auth store (token management, auto-refresh)
- [ ] Implement context store (entity switching)
- [ ] Create global middleware
- [ ] Build login/logout pages
- [ ] Test auth flow end-to-end

**Deliverable**: Working authentication with token refresh.

### Phase 2: User Management (Week 2)

**Goal**: Complete user CRUD with pages.

**Tasks:**
- [ ] Users store
- [ ] User list page
- [ ] User detail page
- [ ] User edit page (dedicated, not drawer)
- [ ] User create page
- [ ] Delete confirmation modal
- [ ] Search and pagination

**Deliverable**: Full user management interface.

### Phase 3: Role Management (Week 3)

**Goal**: Role and permission management.

**Tasks:**
- [ ] Roles store
- [ ] Permissions store
- [ ] Role list page
- [ ] Role detail page
- [ ] Role edit page
- [ ] Permission selector component
- [ ] Create/delete modals

**Deliverable**: Complete role management.

### Phase 4: Entity Management (Week 4) - EnterpriseRBAC

**Goal**: Entity hierarchy visualization and management.

**Tasks:**
- [ ] Entities store
- [ ] Entity tree component (with expand/collapse)
- [ ] Entity list/tree page
- [ ] Entity detail page
- [ ] Entity edit page
- [ ] Entity create modal
- [ ] Drag-and-drop reorganization (optional)

**Deliverable**: Entity hierarchy management.

### Phase 5: Permission Waterfall (Week 5) ⭐

**Goal**: The killer feature - permission debugging.

**Tasks:**
- [ ] Permission waterfall backend endpoint
- [ ] Waterfall component with all sections:
  - Summary card
  - Direct roles
  - Entity memberships
  - Tree permissions
  - Context-aware permissions
  - ABAC conditions
- [ ] Permission test tool
- [ ] Entity breadcrumb navigation
- [ ] Permission badge components

**Deliverable**: Complete permission waterfall visualization.

### Phase 6: API Keys & Polish (Week 6)

**Goal**: API key management and final touches.

**Tasks:**
- [ ] API keys store
- [ ] API key list page
- [ ] API key create page
- [ ] Show key secret modal (once only!)
- [ ] Rotate key functionality
- [ ] Revoke key confirmation
- [ ] Audit log viewer
- [ ] Dashboard with stats
- [ ] Overall polish and refinement

**Deliverable**: Production-ready component library.

---

## Migration from Old UI

### What to Keep

**1. Store Patterns** ✅
- `apiCall` helper with auto-refresh
- Context headers injection
- localStorage persistence

**2. Middleware Pattern** ✅
- Public vs protected routes
- System initialization check
- Auto-redirect logic

**3. Modal Patterns** ✅
- Confirmation dialogs
- Alert modals
- Small form modals

### What to Change

**1. NO Drawers** ❌
- Old: List + drawer for editing
- New: List + dedicated edit page

**2. Dedicated Pages** ✅
- `/users/123/edit` instead of drawer
- Better URLs and browser history

**3. Component Library** ✅
- Old: Standalone app
- New: Embeddable components

### Migration Checklist

- [ ] Extract auth store pattern
- [ ] Extract context store pattern
- [ ] Extract middleware logic
- [ ] Redesign routes (pages instead of drawers)
- [ ] Convert to component library structure
- [ ] Add Nuxt layer configuration
- [ ] Test in multiple host apps

---

## Summary

This specification provides a **complete blueprint** for building the OutlabsAuth admin UI as an **embeddable component library**.

**Key Decisions:**
1. **Embeddable** - Install in any Nuxt 4 app
2. **Pinia for State** - All state management in stores
3. **Pages, Not Drawers** - Dedicated routes for editing
4. **Modals for Small Things** - Confirmations and quick forms
5. **Reuse Proven Patterns** - Build on successful patterns from archived frontend

**Killer Feature:**
The **Permission Waterfall** visualization is the most valuable component - it clearly shows how users get permissions through roles, entities, tree permissions, and ABAC conditions.

**Timeline:**
6 weeks to production-ready library with all core features.

**Next Steps:**
1. Review and approve this spec
2. Set up package structure
3. Start Phase 1 (Foundation)

---

**Last Updated**: 2025-01-15
**Status**: Awaiting Approval
**Estimated Effort**: 6 weeks for complete implementation
