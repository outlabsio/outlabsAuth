# OutlabsAuth Admin UI

Modern admin dashboard for the OutlabsAuth library, built with Nuxt 4, Nuxt UI v4, and Pinia.

Current tracked UI version: `0.1.0-alpha.2`

## Tech Stack

- **Nuxt 4.1.3** - Vue 3 meta-framework
- **Nuxt UI v4.0.1** - Premium UI component library
- **Pinia** - State management
- **Vue 3.5.22** - Composition API
- **Bun 1.2.10** - Package manager
- **Zod** - Schema validation
- **TanStack Table** - Data tables

## Quick Start

### Prerequisites

- Bun 1.2.10 or later
- Node.js 18+ (for compatibility)

### Installation

```bash
# Install dependencies
bun install

# Start development server
bun dev
```

The app will be available at `http://localhost:3000`

## Development Modes

### Mock Mode (Default)

The UI runs in **mock mode** by default, using mock data instead of connecting to a real backend. This is perfect for UI development and testing without needing a running backend.

**Configuration**: Set in `.env`

```bash
# Use mock data (default)
NUXT_PUBLIC_USE_REAL_API=false
```

#### Mock Test Credentials

Use these credentials to log in during development:

| Role | Email | Password | Permissions |
|------|-------|----------|-------------|
| **Admin** (Superuser) | `admin@outlabs.com` | `password123` | Full system access, can see system context |
| **Manager** | `manager@outlabs.com` | `password123` | Engineering manager permissions |
| **Developer** | `developer@outlabs.com` | `password123` | Senior developer permissions |
| **Designer** | `designer@outlabs.com` | `password123` | Product designer permissions |
| **Viewer** | `viewer@outlabs.com` | `password123` | Read-only access |

**All mock passwords are `password123` for convenience.**

### Real API Mode

To connect to a real OutlabsAuth backend:

```bash
# .env
NUXT_PUBLIC_USE_REAL_API=true
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000
NUXT_PUBLIC_AUTH_API_PREFIX=/v1
```

Set `NUXT_PUBLIC_AUTH_API_PREFIX` to the mounted auth path for your backend.
Examples:

- Outlabs examples: `/v1`
- Diverse mounted runtime: `/iam`

## Project Structure

```
auth-ui/
├── app/
│   ├── assets/
│   │   └── css/
│   │       └── main.css          # Tailwind + Nuxt UI imports
│   ├── components/               # Vue components
│   │   ├── EntityContextMenu.vue # Entity context switcher
│   │   └── UserMenu.vue          # User dropdown menu
│   ├── composables/              # Vue composables
│   │   └── useDashboard.ts       # Dashboard state
│   ├── layouts/                  # Layout templates
│   │   └── default.vue           # Main dashboard layout
│   ├── pages/                    # Route pages
│   │   ├── dashboard.vue         # Dashboard home
│   │   ├── login.vue             # Login page
│   │   └── users/
│   │       └── index.vue         # Users list
│   ├── stores/                   # Pinia stores
│   │   ├── auth.store.ts         # Authentication
│   │   ├── context.store.ts      # Entity context
│   │   ├── users.store.ts        # User management
│   │   ├── roles.store.ts        # Role management
│   │   ├── entities.store.ts     # Entity hierarchy
│   │   └── permissions.store.ts  # Permission checking
│   ├── types/                    # TypeScript types
│   │   ├── auth.ts               # Auth types
│   │   ├── user.ts               # User types
│   │   ├── role.ts               # Role types
│   │   ├── entity.ts             # Entity types
│   │   └── api.ts                # API types
│   └── utils/                    # Utilities
│       ├── mock.ts               # Mock mode utilities
│       └── mockData.ts           # Mock data
├── .env                          # Environment config
├── nuxt.config.ts                # Nuxt configuration
├── app.config.ts                 # App configuration
└── package.json                  # Dependencies

```

## Key Features

### Authentication

- JWT-based authentication with refresh tokens
- Mock mode for development
- SSR-safe localStorage handling
- Automatic token refresh
- Context initialization after login

### Entity Context

- Multi-entity support
- Context switching in sidebar
- Entity hierarchy (STRUCTURAL + ACCESS_GROUP)
- System context for superusers

### User Management

- User CRUD operations
- Search and filtering
- Pagination
- Active/inactive status
- Avatar support

### State Management

- Pinia stores for all features
- SSR-compatible
- Mock mode toggle via environment variable
- Centralized error handling

## Available Scripts

```bash
# Development
bun dev                  # Start dev server

# Production
bun run build            # Build for production
bun run preview          # Preview production build

# Maintenance
bun install              # Install dependencies
rm -rf .nuxt             # Clear Nuxt cache
```

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# API Mode
NUXT_PUBLIC_USE_REAL_API=false
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000
NUXT_PUBLIC_SITE_URL=http://localhost:3000
```

### Theme Configuration

Edit `app/app.config.ts`:

```typescript
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'blue',    // Primary color
      neutral: 'zinc'      // Neutral/gray color
    }
  }
})
```

## Development Guidelines

### Adding New Pages

1. Create page in `app/pages/`
2. Add route to sidebar in `app/layouts/default.vue`
3. Create corresponding store if needed
4. Add mock data to `app/utils/mockData.ts`

### Creating New Stores

1. Create store in `app/stores/`
2. Add mock mode support with `USE_MOCK_DATA` check
3. Export typed getters and actions
4. Include SSR guards for localStorage

### UI Components

- Use Nuxt UI components (UButton, UCard, UTable, etc.)
- Follow patterns from `dashboardUi4` reference
- No drawers - use dedicated pages for editing
- Modals only for alerts and small forms

## Troubleshooting

### No CSS Styling

If the UI appears unstyled:

1. Check that `app/assets/css/main.css` exists
2. Verify `css: ['~/assets/css/main.css']` is in `nuxt.config.ts`
3. Clear cache: `rm -rf .nuxt && bun dev`

### Dev Server Crashes

1. Check `compatibilityDate` in `nuxt.config.ts` (should be `'2024-07-11'`)
2. Clear everything: `rm -rf node_modules .nuxt bun.lockb && bun install`
3. Restart: `bun dev`

### localStorage Errors (SSR)

Stores use SSR-safe localStorage helpers. If you see localStorage errors:

1. Check for `import.meta.client` guards
2. Use `safeLocalStorage` helper in stores
3. Add `if (import.meta.server) return` early returns

## Documentation

- `LAYOUT_IMPLEMENTATION.md` - Initial layout implementation
- `MOCK_PHASE_SUMMARY.md` - Mock infrastructure details
- `PHASE1_SUMMARY.md` - Phase 1 implementation summary

## Related Projects

- **OutlabsAuth Library** - Python FastAPI authentication library (parent project)
- **dashboardUi4** - Reference Nuxt UI v4 dashboard template

## License

Private - Outlabs
