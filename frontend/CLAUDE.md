# CLAUDE.md - OutlabsAuth Frontend

This file provides guidance to Claude Code (claude.ai/code) when working with the OutlabsAuth Nuxt 3 frontend.

## Project Overview
OutlabsAuth Frontend is a modern admin dashboard for managing the OutlabsAuth RBAC system. It's built as a Nuxt 3 SPA using Nuxt UI Pro v3 components.

## Tech Stack
- **Framework**: Nuxt 3.16.2 (Vue 3)
- **UI Components**: Nuxt UI Pro 3.0.2 (Premium component library)
- **Forms**: Nuxt UI Form components + Zod validation
- **State Management**: Pinia (handles all API calls and caching)
- **Styling**: UnoCSS/Tailwind (via Nuxt UI)
- **Package Manager**: Bun
- **TypeScript**: Full type safety

## Key Features
- **Entity Management**: Hierarchical organization structures (STRUCTURAL & ACCESS_GROUP)
- **User Management**: Create, edit, assign roles to users
- **Role Management**: Define roles with permissions at any entity level
- **Permission System**: Hierarchical permission inheritance
- **Platform Management**: Multi-tenant platform support
- **Real-time Updates**: Using Pinia stores for state management and updates

## API Integration
- Backend runs on http://localhost:8030
- Token-based authentication (JWT)
- All API calls go through Pinia stores for state management

## Development Commands
```bash
bun install      # Install dependencies
bun dev          # Start dev server on http://localhost:3000
bun build        # Build for production
bun lint         # Run linting
bun typecheck    # TypeScript checking
```

## Project Structure
```
/frontend/
├── app/
│   ├── components/      # Reusable components
│   │   ├── entities/    # Entity-related components
│   │   ├── users/       # User management components
│   │   ├── roles/       # Role management components
│   │   └── shared/      # Shared UI components
│   ├── pages/          # File-based routing
│   ├── stores/         # Pinia stores
│   ├── composables/    # Vue composables
│   ├── types/          # TypeScript types
│   └── utils/          # Utility functions
├── nuxt.config.ts      # Nuxt configuration
└── package.json        # Dependencies

```

## Authentication Flow
1. Login via `/login` page
2. JWT tokens stored in auth store
3. Access token (15 min) and refresh token (30 days)
4. Auto-refresh handled by auth store
5. Global middleware checks auth status

## Key Patterns

### Nuxt UI Forms with Zod
```vue
<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const schema = z.object({
  name: z.string().min(2),
  email: z.string().email()
})

const state = reactive({
  name: '',
  email: ''
})

const onSubmit = async (event: FormSubmitEvent<z.infer<typeof schema>>) => {
  // Handle submission with validated data
  console.log(event.data)
}
</script>

<template>
  <UForm :schema="schema" :state="state" @submit="onSubmit">
    <UFormField name="name" label="Name">
      <UInput v-model="state.name" />
    </UFormField>
    
    <UFormField name="email" label="Email">
      <UInput v-model="state.email" type="email" />
    </UFormField>
    
    <UButton type="submit">Submit</UButton>
  </UForm>
</template>
```

### Pinia Store Pattern
```typescript
// stores/entities.store.ts
export const useEntitiesStore = defineStore('entities', () => {
  const state = reactive({
    entities: [],
    isLoading: false,
    error: null
  })
  
  const fetchEntities = async () => {
    state.isLoading = true
    try {
      const response = await authStore.apiCall('/v1/entities')
      state.entities = response.items
    } catch (error) {
      state.error = error.message
    } finally {
      state.isLoading = false
    }
  }
  
  return {
    entities: computed(() => state.entities),
    isLoading: computed(() => state.isLoading),
    fetchEntities
  }
})
```

## Component Conventions
1. Use `<script setup lang="ts">` for all components
2. Prefer composables for shared logic
3. Use Nuxt UI Pro components for consistency
4. Use Nuxt UI Form components with Zod validation
5. Type all props and emits

## State Management
- **Auth Store**: JWT tokens, user info, permissions
- **Context Store**: Current organization context
- **UI Store**: Sidebar state, theme, notifications

## Error Handling
- Use Nuxt error boundaries
- Show toast notifications for user feedback
- Log errors to console in development
- Graceful degradation for failed API calls

## Key Frontend Features
- Vue 3 Composition API with `<script setup>`
- File-based routing with automatic route generation
- Nuxt UI Pro components for premium UI elements
- Pinia for centralized state management
- Auto-imports for components, composables, and utilities

## Environment Variables
```env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8030
NUXT_PUBLIC_SITE_URL=http://localhost:3000
```