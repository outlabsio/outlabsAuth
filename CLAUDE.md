# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: Always check PROJECT_STATUS.md first to understand the current implementation state and next steps.

**LATEST UPDATE (2025-07-10)**: Entity types are now flexible strings instead of fixed enums. Platforms can use any organizational terminology (e.g., "division", "region", "bureau"). The frontend provides autocomplete suggestions to maintain consistency. See docs/ENTITY_TYPE_FLEXIBILITY_CHANGES.md for details.

## Project Overview

outlabsAuth is an enterprise-grade Role-Based Access Control (RBAC) authentication platform built with FastAPI, MongoDB, and Beanie ODM. It provides centralized authentication and authorization for multiple platforms through a flexible unified entity system that supports diverse organizational structures from flat role-based access to complex multi-level hierarchies.

### Frontend Tech Stack
- **React 19** with TypeScript
- **Vite** for build tooling
- **TanStack Router** for type-safe routing
- **TanStack Query** for server state management
- **TanStack Form** for form handling
- **Zustand** for client state management (auth, UI state)
- **ShadCN UI** components with Radix UI primitives
- **Tailwind CSS v4** for styling
- **Sonner** for toast notifications
- **Bun** as package manager

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
cd admin-ui

# Install dependencies (use bun, NOT npm)
bun install

# Development server
bun dev                              # Start Vite dev server on port 5173

# Build for production
bun run build

# Add ShadCN components
bunx --bun shadcn@latest add <component-name>

# Type checking
bun run type-check
```

### Docker
```bash
docker compose up -d --build         # Build and start all services
docker compose logs -f api           # View API logs
docker compose down -v               # Stop and remove volumes
```

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
Permissions automatically inherit based on scope and action:

1. **Action Inheritance**: `manage` includes all lesser actions
   - `entity:manage` → `entity:update` → `entity:read`
   
2. **Scope Inheritance**: Higher scopes include lower scopes
   - `user:manage_all` → `user:manage_platform` → `user:manage_organization` → `user:manage`
   
3. **Entity Context**: Permissions can be scoped to specific entities
   - A user with `user:manage` in Team A can only manage Team A users
   - A user with `user:manage_organization` can manage all users in their organization

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
Always use the hierarchical permission checker:
```python
from api.dependencies import check_hierarchical_permissions

# In routes
@router.post("/", dependencies=[Depends(check_hierarchical_permissions("user:manage"))])
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

### State Management with Zustand
The frontend uses Zustand for client-side state management:

```typescript
// Auth store example (stores/auth-store.ts)
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tokens: null,
      isAuthenticated: false,
      
      login: async (tokens, user) => { /* ... */ },
      logout: () => { /* ... */ },
      refreshTokens: async () => { /* ... */ }
    }),
    { name: 'auth-storage' }
  )
);
```

### Authentication Flow
1. **Login**: Tokens stored in Zustand with localStorage persistence
2. **API Calls**: Use `authenticatedFetch` wrapper that handles:
   - Automatic token injection
   - 401 error handling with token refresh
   - Automatic logout on refresh failure
3. **Protected Routes**: Check auth state in route `beforeLoad`

### UI Patterns
- **Forms**: TanStack Form with validation
- **Notifications**: Sonner toasts for user feedback
- **Components**: ShadCN UI components, add with `bunx --bun shadcn@latest add`
- **Styling**: Tailwind CSS v4 with CSS variables for theming

### API Integration
```typescript
// Use authenticatedFetch for all API calls
import { authenticatedFetch } from '@/lib/auth';

const response = await authenticatedFetch('/v1/endpoint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
});
```

## Common Development Tasks

### Adding a New Endpoint
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

## Important Frontend Notes

- **Package Manager**: ALWAYS use `bun`, never `npm` or `yarn`
- **State Management**: Use Zustand for client state, TanStack Query for server state
- **Auth**: All API calls should use `authenticatedFetch` for automatic token handling
- **Components**: Prefer ShadCN UI components, install with `bunx --bun shadcn@latest add`
- **Notifications**: Use Sonner toasts instead of static alerts
- **Forms**: Use TanStack Form for form handling with built-in validation
- **Entity UI**: EntityDrawer for creation/editing, EntityTreeSidebar for navigation

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

## Common Pitfalls to Avoid

1. **Link Objects**: Always fetch before accessing properties
2. **Entity Creation**: 
   - Top-level entities have no parent (any entity_type is allowed)
   - Entity types are strings now, not enums
   - Use lowercase with underscores for consistency
3. **Entity Hierarchy**: Access groups cannot have structural children
4. **Permissions**: System permissions cannot be modified
5. **Testing**: Maintain 98%+ test pass rate
6. **Frontend**: Use bun, not npm; use authenticatedFetch for APIs

Always refer to PROJECT_STATUS.md when resuming work to understand the current state.