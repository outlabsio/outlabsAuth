# CLAUDE.md - OutlabsAuth Frontend

This file provides guidance to Claude Code (claude.ai/code) when working with the OutlabsAuth Nuxt 3 frontend.

## Project Overview
OutlabsAuth Frontend is a modern admin dashboard for managing the OutlabsAuth RBAC system. It's built as a Nuxt 3 SPA using Nuxt UI Pro v3 components with TanStack Form integration.

## Tech Stack
- **Framework**: Nuxt 3.16.2 (Vue 3)
- **UI Components**: Nuxt UI Pro 3.0.2 (Premium component library)
- **Forms**: TanStack Form + Zod validation
- **API Client**: TanStack Query for caching and state management
- **State Management**: Pinia
- **Styling**: UnoCSS/Tailwind (via Nuxt UI)
- **Package Manager**: Bun
- **TypeScript**: Full type safety

## Key Features
- **Entity Management**: Hierarchical organization structures (STRUCTURAL & ACCESS_GROUP)
- **User Management**: Create, edit, assign roles to users
- **Role Management**: Define roles with permissions at any entity level
- **Permission System**: Hierarchical permission inheritance
- **Platform Management**: Multi-tenant platform support
- **Real-time Updates**: Using TanStack Query for optimistic updates

## API Integration
- Backend runs on http://localhost:8030
- Token-based authentication (JWT)
- All API calls go through TanStack Query for caching

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
4. Auto-refresh handled by TanStack Query
5. Global middleware checks auth status

## Key Patterns

### TanStack Form with Nuxt UI
```vue
<script setup lang="ts">
import { useForm } from '@tanstack/vue-form'
import { zodValidator } from '@tanstack/zod-form-adapter'
import { z } from 'zod'

const form = useForm({
  defaultValues: {
    name: '',
    email: ''
  },
  onSubmit: async ({ value }) => {
    // Handle submission
  },
  validatorAdapter: zodValidator()
})
</script>

<template>
  <form @submit="form.handleSubmit">
    <form.Field name="name">
      <template v-slot="{ field }">
        <UFormField :error="field.state.meta.errors[0]">
          <UInput 
            v-model="field.state.value" 
            @blur="field.handleBlur"
            placeholder="Name"
          />
        </UFormField>
      </template>
    </form.Field>
  </form>
</template>
```

### TanStack Query Pattern
```typescript
// composables/useEntities.ts
export const useEntities = () => {
  return useQuery({
    queryKey: ['entities'],
    queryFn: () => $fetch('/api/v1/entities'),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
```

## Component Conventions
1. Use `<script setup lang="ts">` for all components
2. Prefer composables for shared logic
3. Use Nuxt UI Pro components for consistency
4. Integrate TanStack Form for complex forms
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

## Key Differences from React Version
- Vue 3 Composition API instead of React hooks
- File-based routing instead of TanStack Router
- Nuxt UI Pro instead of ShadCN
- Pinia instead of Zustand
- Auto-imports for components and composables

## Environment Variables
```env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8030
NUXT_PUBLIC_SITE_URL=http://localhost:3000
```