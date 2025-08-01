# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: Always check PROJECT_STATUS.md first to understand the current implementation state and next steps.

**LATEST UPDATE (2025-07-10)**: Entity types are now flexible strings instead of fixed enums. Platforms can use any organizational terminology (e.g., "division", "region", "bureau"). The frontend provides autocomplete suggestions to maintain consistency.

## Project Overview

**OutlabsAuth is a FastAPI-based authentication and authorization API service** designed to be integrated into applications as a centralized auth solution. The core product is the REST API that provides:

- JWT-based authentication with refresh tokens
- Hierarchical RBAC with permission inheritance  
- Multi-tenant platform isolation
- Flexible entity system for any organizational structure
- Complete REST API for all auth operations

**The frontend admin UI is a supplementary tool** built with Nuxt 3 for managing the auth system, but the primary deliverable is the authentication API itself.

### Frontend Tech Stack
- **Nuxt 3** (v3.16.2) with TypeScript
- **Vue 3** as the underlying framework
- **Nuxt UI Pro v3** for premium UI components
- **Tailwind CSS v4** (via Nuxt UI)
- **Pinia** for state management and API calls
- **Zod** for form validation
- **VueUse** for composition utilities
- **Bun** as package manager
- **Auto-imports** for components and composables

### IMPORTANT: Nuxt UI Documentation Access
**ALWAYS use the Nuxt MCP server to check Nuxt UI documentation before implementing UI components:**
- The built-in Nuxt MCP server provides access to all Nuxt UI components (including Pro components)
- Access component lists, details, props, slots, and examples through the MCP resource
- This ensures you're using the latest Nuxt UI v3 patterns and best practices
- Never guess component APIs - always verify through the documentation

### Nuxt 3 Auto-imports (CRITICAL)

**NEVER manually import the following - they are auto-imported by Nuxt:**

#### Vue & Nuxt Composables
```typescript
// ❌ NEVER DO THIS
import { ref, computed, watch, reactive } from 'vue'
import { useRoute, useRouter, useState, useFetch } from '#app'

// ✅ Just use them directly
const count = ref(0)
const route = useRoute()
const { data } = await useFetch('/api/users')
```

#### Components
```typescript
// ❌ NEVER DO THIS
import UButton from '@nuxt/ui/components/UButton.vue'
import MyComponent from '~/components/MyComponent.vue'

// ✅ Just use them in templates
<UButton>Click me</UButton>
<MyComponent />
```

#### Utilities & Composables
```typescript
// ❌ NEVER DO THIS
import { useAuth } from '~/composables/useAuth'
import { formatDate } from '~/utils/formatDate'

// ✅ Just use them directly
const { user, login } = useAuth()
const formatted = formatDate(new Date())
```

#### What IS manually imported:
- External packages (zod, date-fns, etc.)
- Types/interfaces from type files
- Store imports from Pinia
- Assets (images, styles)

### Nuxt UI Component Usage

**ALWAYS consult Nuxt UI documentation via MCP before using components:**

```vue
<!-- Example: Check documentation first, then use -->
<UForm :schema="schema" :state="state" @submit="onSubmit">
  <UFormField name="email" label="Email" required>
    <UInput v-model="state.email" placeholder="Enter email" />
  </UFormField>
  
  <UButton type="submit" :loading="isLoading">
    Submit
  </UButton>
</UForm>
```

Common Nuxt UI v3 components:
- **Forms**: UForm, UFormField, UInput, USelect, UCheckbox, URadio, USwitch
- **Feedback**: UToast, UNotification, UAlert, USkeleton
- **Overlays**: UModal, UDrawer, USlideover, UPopover, UTooltip
- **Navigation**: UTabs, UBreadcrumb, UPagination, UCommandPalette
- **Data**: UTable, UCard, UBadge, UAvatar, UChip
- **Layout**: UContainer, UDivider, USeparator, UPage

## Essential Commands

### Backend Development
```bash
# Setup and dependencies
uv sync                              # Install all dependencies
uv sync --extra stress               # Include stress testing dependencies

# Run the application
uv run uvicorn api.main:app --reload # Start FastAPI dev server on port 8030

# Testing - ALWAYS run tests before committing
uv run pytest                        # Run all tests (should have 98%+ pass rate)
uv run pytest tests/test_auth_routes.py::test_login # Run specific test
uv run pytest -k "test_user"         # Run tests matching pattern
uv run pytest -v                     # Verbose output

# Code quality checks - MUST pass before changes are complete
uv run black .                       # Format code
uv run isort .                       # Sort imports
uv run flake8 .                      # Linting
uv run mypy .                        # Type checking

# Database seeding
uv run python scripts/seed_test_environment.py # Seed test data
```

### Frontend Development
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (use bun, NOT npm)
bun install

# Development server
bun dev                              # Start Nuxt dev server on port 3000

# Build for production
bun run build

# Preview production build
bun run preview

# Type checking
bun run typecheck

# Linting
bun run lint
```

### Docker

**IMPORTANT**: The FastAPI server is always running in Docker and automatically reloads when you make changes. You never need to manually start the server - it's continuously running on port 8030.

```bash
docker compose up -d --build         # Build and start all services (already running in dev)
docker compose logs -f api           # View API logs
docker compose down -v               # Stop and remove volumes
```

## Primary Focus: Authentication API

**When working on this project, remember:**
1. The FastAPI authentication service is the main product
2. API endpoints should be well-documented and follow REST conventions
3. The admin UI is a management tool, not the core deliverable
4. Focus on API performance, security, and reliability
5. Ensure the API can be easily integrated into any application

### Key API Design Principles
- **Stateless**: All requests should be self-contained
- **RESTful**: Follow REST conventions for resource naming and HTTP methods
- **Secure**: JWT tokens, rate limiting, permission checks on all endpoints
- **Documented**: All endpoints documented in OpenAPI/Swagger format
- **Versioned**: API versioned at `/v1/` to allow future updates

## Architecture & Key Concepts

### Unified Entity System
The system uses a flexible entity hierarchy that can adapt to any organizational structure:

#### Entity Classes (Fixed)
1. **STRUCTURAL**: Forms the organizational hierarchy
   - Can contain other structural entities or access groups
   - Examples: platform, organization, division, department, office, team

2. **ACCESS_GROUP**: Cross-cutting permission groups
   - Can only contain other access groups
   - Examples: admin_group, viewer_group, project_team, committee

#### Entity Types (Flexible)
Entity types are now flexible strings, allowing platforms to use their own terminology:
- **Traditional**: organization → division → department → team
- **Real Estate**: organization → region → office → team
- **Government**: organization → bureau → section → unit
- **Custom**: Any naming that fits your business model

#### Entity Type Consistency
- Use the `/v1/entities/entity-types` endpoint to see existing types
- Frontend provides autocomplete suggestions to maintain consistency
- Types are automatically lowercased and stored with underscores
- Use `display_name` for user-friendly labels

#### Entity Rules
- Top-level entities (no parent) can use any entity_type ("platform" is suggested but not required)
- Structural entities can contain other structural entities or access groups
- Access groups can only contain other access groups (not structural entities)
- Users are members of entities through EntityMembership

### Hierarchical Permission System

**⚠️ CRITICAL: See [Tree Permissions Guide](docs/TREE_PERMISSIONS_GUIDE.md) for detailed explanation of how tree permissions work.**

Permissions use a three-tier scoping model with automatic inheritance:

1. **Permission Scoping Levels**:
   - **Entity-Specific** (`resource:action`) - Access only in the specific entity
   - **Tree/Hierarchical** (`resource:action_tree`) - Access to all descendants (not the entity where assigned)
   - **Platform-Wide** (`resource:action_all`) - Access across entire platform

2. **Tree Permission Behavior**:
   - Tree permissions apply to descendants only - to access the entity where assigned, you need the non-tree permission
   - Users with `entity:create_tree` in a parent can create entities anywhere in the subtree
   - Users with `entity:update_tree` in a parent can update entities anywhere in the subtree
   - Tree permissions are checked up the entire ancestor chain, not just immediate parent
   - Example: Platform admin with tree permissions at platform level can perform actions on all entities below the platform
   - Example: To both update an entity AND its descendants, assign both `entity:update` and `entity:update_tree`

3. **No Compound Permissions**: Each action must be explicitly granted
   - No automatic expansion of permissions
   - Grant each permission individually: `entity:create`, `entity:update`, `entity:delete`, `entity:read`

4. **Tree Permission Implementation** (Fixed 2025-07-21):
   - ✅ Entity creation with tree permissions works correctly
   - ✅ Entity updates with tree permissions work correctly (fixed array slicing bug)
   - ✅ Member management with tree permissions works correctly
   - ✅ Platform admins can update child organizations with `entity:update_tree`
   - ✅ Tree permissions work at any depth in the hierarchy

### Multi-Platform Architecture
- **Platform Isolation**: Each platform is completely isolated
- **Shared Admin UI**: Platform admins can use OutlabsAuth Admin UI with scoped access
- **Flexible Structure**: Platforms can have different organizational models
- **Cross-Platform Users**: Users can belong to multiple platforms

### Service Layer Pattern
```
routes/ → services/ → models/
```
- **Routes**: Handle HTTP requests, validation, and responses
- **Services**: Business logic, permission checks, database operations
- **Models**: Beanie ODM documents with type safety

### Email Service
- **Non-blocking**: Uses asyncio.Queue for background processing
- **Templates**: Jinja2 templates in `api/email_templates/`
- **Graceful degradation**: Logs emails when SMTP not configured
- **System emails**: Welcome, invitations, password reset, etc.
- **Background worker**: Processes emails without blocking main thread

### Authentication Flow
1. Login creates JWT access token (15 min) and refresh token (30 days)
2. Refresh tokens support multi-device sessions
3. Logout revokes specific refresh tokens
4. Rate limiting prevents brute force attacks

## Critical Implementation Notes

### Permission Checks
Always use the permission checker:
```python
from api.dependencies import require_permission

# In routes
@router.post("/", dependencies=[Depends(require_permission("user:create"))])
```
```python
# To update an entity and its descendants, assign BOTH permissions:
role.permissions = [
    "entity:update",      # Update the entity itself
    "entity:update_tree"  # Update all descendants
]

# Tree permissions alone DO NOT grant access to the assigned entity:
role.permissions = [
    "entity:update_tree"  # ❌ Cannot update the entity where this is assigned
                         # ✅ Can manage all child entities below
]
```

### Database Operations
- Use Beanie's async methods: `await EntityModel.find_all()`, `await entity.save()`
- Always handle Link objects properly: fetch before accessing properties
- Filter by platform_id for platform isolation
- Use transactions for multi-document operations

### Working with Link Objects
```python
# WRONG - Will cause AttributeError
entity_name = role.entity.name

# CORRECT - Fetch the linked document first
if role.entity:
    entity = await role.entity.fetch() if hasattr(role.entity, 'fetch') else role.entity
    entity_name = entity.name if entity else None
```

### Testing Requirements
- Maintain 98%+ test success rate
- Use fixtures from conftest.py for consistent test data
- Test both success and error cases
- Verify permission boundaries in all tests

### Testing Tree Permissions
When testing tree permissions, ensure:
- Test entity creation with `entity:create_tree` in parent entities
- Test entity updates with `entity:update_tree` in parent entities
- Test that tree permissions work through multiple hierarchy levels
- Test that users without tree permissions cannot access descendant entities
- Use `test/test_complex_scenarios.py` for comprehensive tree permission testing
- Complex scenario tests should have 100% pass rate (35/35 tests passing)
- When testing tree permissions, remember they apply to descendants only

### Error Handling
- Use FastAPI's HTTPException with appropriate status codes
- Include descriptive error messages
- Log security-related errors (failed logins, permission denials)

## File Structure

```
api/
├── models/          # Beanie ODM models
│   ├── entity_model.py      # Unified entity system (structural & access groups)
│   ├── user_model.py        # User accounts and profiles
│   ├── role_model.py        # Roles with entity scope
│   └── permission_model.py  # System and custom permissions
├── routes/          # FastAPI endpoints (use dependency injection)
├── services/        # Business logic (handle permissions here)
│   ├── entity_service.py    # Entity hierarchy management
│   ├── membership_service.py # User-entity relationships
│   └── permission_service.py # Permission checking logic
├── schemas/         # Pydantic models for request/response
├── middleware/      # Rate limiting, CORS, etc.
└── dependencies.py  # Auth helpers, permission checkers

frontend/
├── app/             # Main app directory
│   ├── assets/      # Stylesheets and static assets
│   ├── components/  # Vue components (auto-imported)
│   │   ├── entities/    # Entity management components
│   │   ├── users/       # User management components
│   │   ├── roles/       # Role management components
│   │   └── permissions/ # Permission components
│   ├── composables/ # Reusable composition functions (auto-imported)
│   ├── layouts/     # Page layouts
│   ├── middleware/  # Route middleware
│   ├── pages/       # File-based routing
│   ├── plugins/     # Nuxt plugins
│   ├── stores/      # Pinia stores
│   └── utils/       # Utility functions (auto-imported)
├── public/          # Static files
├── server/          # Nitro server directory
│   ├── api/         # Server API routes
│   └── utils/       # Server utilities
├── nuxt.config.ts   # Nuxt configuration
├── app.config.ts    # App configuration (theme, etc.)
└── tailwind.config.ts # Tailwind CSS configuration

tests/
├── conftest.py      # Shared fixtures (test users, roles, entities)
├── test_*_routes.py # API endpoint tests
└── test_*_service.py # Service layer tests

docs/
├── PLATFORM_SCENARIOS.md    # Real-world platform examples
├── PLATFORM_SETUP_GUIDE.md  # Step-by-step platform setup
├── API_INTEGRATION_PATTERNS.md # Common integration patterns
├── ADMIN_ACCESS_LEVELS.md   # Multi-level admin access
└── PLATFORM_INTEGRATION_*.md # Platform-specific guides
```

## Frontend Architecture & Patterns

### Nuxt-Specific Patterns

#### Auto-imports
Nuxt automatically imports components, composables, and utilities:
```typescript
// No need to import these - they're auto-imported
const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()
const { $fetch } = useNuxtApp()
```

#### File-based Routing
Pages are automatically generated from the `pages/` directory:
```
pages/
├── index.vue          → /
├── users/
│   ├── index.vue      → /users
│   └── [id].vue       → /users/:id
└── entities/
    └── [...slug].vue  → /entities/** (catch-all)
```

#### Server API Routes
Create API endpoints in `server/api/`:
```typescript
// server/api/auth/login.post.ts
export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  // Handle login
  return { token: '...' }
})
```

#### Composables Pattern
Create reusable logic in `composables/`:
```typescript
// composables/useAuth.ts
export const useAuth = () => {
  const user = useState<User | null>('auth.user', () => null)
  
  const login = async (credentials: LoginCredentials) => {
    // Login logic
  }
  
  return { user: readonly(user), login }
}
```

### State Management with Pinia
The frontend uses Pinia stores for all state management and API calls:

```typescript
// Standard store pattern
export const useFeatureStore = defineStore('feature', () => {
  // 1. Reactive state
  const state = reactive({
    items: [],
    selectedItem: null,
    isLoading: false,
    error: null,
    pagination: { page: 1, limit: 20, total: 0 },
    filters: {}
  })
  
  // 2. Dependencies
  const authStore = useAuthStore()
  const contextStore = useContextStore()
  const toast = useToast()
  
  // 3. Actions (all API calls go through authStore.apiCall)
  const fetchItems = async () => {
    state.isLoading = true
    try {
      const params = new URLSearchParams({
        page: state.pagination.page.toString(),
        limit: state.pagination.limit.toString(),
        ...state.filters
      })
      
      const response = await authStore.apiCall<ItemsResponse>(
        `/v1/items?${params}`,
        { headers: contextStore.getContextHeaders() }
      )
      
      state.items = response.items
      state.pagination.total = response.total
    } catch (error) {
      state.error = error.message
      toast.add({ title: 'Error', description: error.message, color: 'red' })
    } finally {
      state.isLoading = false
    }
  }
  
  // 4. Return computed refs and actions
  return {
    items: computed(() => state.items),
    isLoading: computed(() => state.isLoading),
    pagination: computed(() => state.pagination),
    fetchItems,
    // ... other actions
  }
})
```

### Authentication Flow
1. **Login**: JWT tokens managed by auth store
   - Access token (15 min) stored in Pinia state
   - Refresh token (30 days) stored as httpOnly cookie
2. **API Calls**: All API calls go through `authStore.apiCall()`:
   - Automatically includes Bearer token
   - Handles token refresh on 401 errors
   - Includes context headers from context store
   - Manages the entire auth flow transparently
3. **Protected Routes**: Route middleware checks auth state
4. **Token Management**: Automatic refresh on 401 responses

### UI Patterns
- **Forms**: Nuxt UI form components with Zod validation
- **Notifications**: Nuxt UI toast notifications via `useToast()`
- **Components**: Nuxt UI Pro v3 components with full customization
- **Icons**: Iconify with Lucide and Simple Icons collections
- **Styling**: Tailwind CSS v4 via Nuxt UI's design system
- **Dark Mode**: Built-in dark mode support with color mode module
- **Modals**: UModal component for overlays and dialogs
- **Tables**: UTable with sorting, filtering, and pagination
- **Data Fetching**: Pinia stores handle all API calls and state

### API Integration
```typescript
// All API calls go through authStore.apiCall() for automatic auth handling
const authStore = useAuthStore()

// In a Pinia store
export const useEntityStore = defineStore('entities', () => {
  const state = reactive({
    entities: [],
    isLoading: false,
    error: null
  })
  
  const fetchEntities = async () => {
    state.isLoading = true
    try {
      const response = await authStore.apiCall<EntitiesResponse>('/v1/entities')
      state.entities = response.items
    } catch (error) {
      state.error = error.message
      toast.add({ title: 'Error', description: error.message, color: 'red' })
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

## Common Development Tasks

### Frontend Development

#### IMPORTANT: Component Development Workflow
1. **ALWAYS check Nuxt UI documentation first** using the MCP resource
2. Verify component props, slots, and events before implementation
3. Use the exact API as documented - don't guess or assume
4. Reference examples from the documentation

#### Adding a New Page
1. Create a `.vue` file in `pages/` directory (auto-routed)
2. Use `definePageMeta()` for middleware and layout
3. Data fetching: use Pinia stores, NOT `useFetch` directly
4. Handle loading and error states via store state
5. Navigation: use `<NuxtLink>` for internal routes

#### Creating a Component
1. Add to `components/` directory (auto-imported - NO manual imports!)
2. Use `<script setup lang="ts">` always
3. Type props with TypeScript: `defineProps<{ ... }>()`
4. Check Nuxt UI docs for which components to use
5. Never import Vue reactivity functions - they're auto-imported

#### Working with Nuxt UI Forms and Zod Validation
```vue
<template>
  <UForm :schema="schema" :state="state" @submit="onSubmit">
    <UFormField name="email" label="Email">
      <UInput v-model="state.email" placeholder="Enter email" />
    </UFormField>
    
    <UFormField name="name" label="Name">
      <UInput v-model="state.name" placeholder="Enter name" />
    </UFormField>
    
    <UButton type="submit" :loading="isSubmitting">
      Submit
    </UButton>
  </UForm>
</template>

<script setup lang="ts">
import { z } from 'zod'

// Define Zod schema
const schema = z.object({
  email: z.string().email('Invalid email'),
  name: z.string().min(2, 'Name must be at least 2 characters')
})

// Form state
const state = reactive({
  email: '',
  name: ''
})

const isSubmitting = ref(false)

// Handle form submission
const onSubmit = async (event: FormSubmitEvent<z.infer<typeof schema>>) => {
  isSubmitting.value = true
  try {
    await authStore.apiCall('/v1/users', {
      method: 'POST',
      body: event.data
    })
    toast.add({ title: 'Success', description: 'User created' })
  } catch (error) {
    toast.add({ title: 'Error', description: error.message, color: 'red' })
  } finally {
    isSubmitting.value = false
  }
}
</script>
```

### Backend Development

#### Adding a New Endpoint
1. Define Pydantic schemas in `schemas/`
2. Implement service logic in `services/`
3. Create route in `routes/` with proper permission dependencies
4. Add comprehensive tests covering success/error cases
5. Update route documentation in `docs/routes/`

### Creating a New Platform
1. Create a top-level entity (no parent) - can use any entity_type
2. Define platform-specific permissions
3. Create role templates for the platform
4. Set up default organization for individual users
5. Configure platform admin access
6. See `docs/PLATFORM_SETUP_GUIDE.md` for detailed steps

### Understanding Role Assignment
Roles can be assigned in three ways:
1. **Global Roles** (`is_global=true`) - Assignable anywhere in the platform
2. **Entity-Specific Roles** - Only assignable in the entity that owns them
3. **Type-Specific Roles** (`assignable_at_types`) - Assignable at specified entity types

See `docs/ROLE_ASSIGNMENT_GUIDE.md` for comprehensive role assignment documentation.

### Working with Entities
1. Choose entity class based on purpose (STRUCTURAL vs ACCESS_GROUP)
2. Use flexible entity types that match your business (e.g., "region", "bureau", "cost_center")
3. Check existing types with `/v1/entities/entity-types` for consistency
4. Top-level entities have no parent (entity_type can be anything, "platform" is just a suggestion)
5. Use proper system names (lowercase, underscores) for `name` field
6. Include user-friendly `display_name` for UI presentation
7. Remember: Access groups cannot have structural children

### Modifying Permissions
1. System permissions are immutable (defined in code)
2. Custom permissions can be created per platform
3. Follow naming convention: `resource:action_scope`
4. Test permission inheritance thoroughly
5. Document new permissions in platform guides

### Database Schema Changes
1. Update Beanie model in `models/`
2. Handle Link object changes carefully
3. Consider impact on existing platforms
4. Update related services and routes
5. Add migration scripts if needed

## Environment Variables

Key variables for local development:
- `DATABASE_URL`: MongoDB connection string
- `MONGO_DATABASE`: Database name (default: outlabs_auth)
- `SECRET_KEY`: JWT signing key
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Default 15
- `REFRESH_TOKEN_EXPIRE_DAYS`: Default 30

## Development Credentials

For local development testing:
- **Username**: `system@outlabs.io`
- **Password**: `Asd123$$$`

## Testing API Routes with curl

To test protected API endpoints, you need to authenticate first and use the JWT token:

```bash
# 1. Login to get access token (use /login/json for JSON payload)
curl -X POST http://localhost:8030/v1/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{"email": "system@outlabs.io", "password": "Asd123$$$"}'

# Response will include access_token:
# {
#   "access_token": "eyJ...",
#   "refresh_token": "eyJ...",
#   "token_type": "bearer"
# }

# 2. Use the access token for authenticated requests
export TOKEN="<your-access-token-here>"

# Example: Get all roles
curl -X GET http://localhost:8030/v1/roles \
  -H "Authorization: Bearer $TOKEN"

# Example: Get roles with query parameters
curl -X GET "http://localhost:8030/v1/roles?page=1&limit=20" \
  -H "Authorization: Bearer $TOKEN"

# Example: Get a specific role
curl -X GET http://localhost:8030/v1/roles/<role-id> \
  -H "Authorization: Bearer $TOKEN"

# Example: Create a new role
curl -X POST http://localhost:8030/v1/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_role",
    "display_name": "Test Role",
    "description": "A test role",
    "permissions": ["user:read"],
    "is_global": false
  }'
```

### Common API Endpoints for Testing

- **Auth**: `/v1/auth/login`, `/v1/auth/logout`, `/v1/auth/refresh`
- **Users**: `/v1/users`, `/v1/users/{id}`
- **Roles**: `/v1/roles`, `/v1/roles/{id}`
- **Permissions**: `/v1/permissions`, `/v1/permissions/{id}`
- **Entities**: `/v1/entities`, `/v1/entities/{id}`, `/v1/entities/entity-types`

### Tips for API Testing

1. The access token expires in 15 minutes, so you may need to refresh it
2. Include `X-Entity-Context-Id` header when testing entity-scoped operations
3. Use `jq` to parse JSON responses: `curl ... | jq .`
4. Save tokens in environment variables to reuse across commands
5. Check response status codes: add `-w "\nHTTP Status: %{http_code}\n"` to curl commands

## Important Frontend Notes

- **Package Manager**: ALWAYS use `bun`, never `npm` or `yarn`
- **State Management**: Use Pinia stores for ALL state and API calls
- **API Pattern**: All API calls MUST go through `authStore.apiCall()` - never use $fetch directly
- **Auth**: Custom JWT implementation - tokens managed in auth store
- **Components**: Use Nuxt UI Pro v3 components - they're auto-imported
- **Notifications**: Use `const toast = useToast()` for notifications
- **Forms**: Use Nuxt UI form components with Zod validation schemas
- **Entity UI**: Use UModal for creation/editing, USlideover for entity details
- **Navigation**: Use NuxtLink for internal navigation, not <a> tags
- **Composables**: Leverage auto-imported composables from `composables/` directory
- **Context Headers**: Use `contextStore.getContextHeaders()` for multi-tenant requests

## Key Documentation

### For Understanding the System
- **PROJECT_STATUS.md**: Current implementation state and next steps
- **docs/PLATFORM_SCENARIOS.md**: Real-world examples of different platform types
- **docs/ARCHITECTURE.md**: Deep technical architecture dive

### For Platform Integration
- **docs/PLATFORM_SETUP_GUIDE.md**: Step-by-step guide for new platforms
- **docs/API_INTEGRATION_PATTERNS.md**: Common integration patterns
- **docs/ADMIN_ACCESS_LEVELS.md**: How platform admins use the admin UI

### For Specific Examples
- **docs/PLATFORM_INTEGRATION_DIVERSE.md**: Complex hierarchical platform example
- Check other PLATFORM_INTEGRATION_*.md files as they're added

## Common Nuxt UI 3 Patterns

### Modal with Form
```vue
<UModal v-model="isOpen">
  <UCard>
    <template #header>
      <h3 class="text-lg font-semibold">Create User</h3>
    </template>
    
    <UForm :schema="schema" :state="state" @submit="onSubmit">
      <UFormField name="email" label="Email">
        <UInput v-model="state.email" />
      </UFormField>
      
      <template #footer>
        <div class="flex gap-3">
          <UButton variant="outline" @click="isOpen = false">Cancel</UButton>
          <UButton type="submit">Create</UButton>
        </div>
      </template>
    </UForm>
  </UCard>
</UModal>
```

### Table with Actions
```vue
<UTable :columns="columns" :rows="users">
  <template #actions-data="{ row }">
    <UDropdown :items="getActions(row)">
      <UButton variant="ghost" icon="i-lucide-more-vertical" />
    </UDropdown>
  </template>
</UTable>
```

### Toast Notifications
```typescript
const toast = useToast()

// Success
toast.add({ 
  title: 'Success', 
  description: 'User created successfully',
  color: 'success' 
})

// Error
toast.add({ 
  title: 'Error', 
  description: 'Failed to create user',
  color: 'error' 
})
```

## Common Pitfalls to Avoid

1. **Auto-imports**: Never manually import Vue/Nuxt composables or components
2. **Nuxt UI Docs**: Always check component documentation via MCP before use
3. **Link Objects**: Always fetch before accessing properties
4. **Entity Creation**: 
   - Top-level entities have no parent (any entity_type is allowed)
   - Entity types are strings now, not enums
   - Use lowercase with underscores for consistency
5. **Entity Hierarchy**: Access groups cannot have structural children
6. **Permissions**: System permissions cannot be modified
7. **Testing**: Maintain 98%+ test pass rate
8. **Frontend**: 
   - Use bun, not npm
   - Use authStore.apiCall() for all API calls
   - Never use $fetch directly
   - Check Nuxt UI docs before implementing components

Always refer to PROJECT_STATUS.md when resuming work to understand the current state.