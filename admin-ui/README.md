# Admin UI - Enterprise RBAC Management Interface

A modern React-based administrative interface for the outlabsAuth enterprise RBAC authentication platform.

## 🚀 Quick Start

```bash
# Install dependencies
bun install

# Start development server
bun dev

# Build for production
bun run build

# Preview production build
bun run preview
```

**Development Server**: http://localhost:5173/

## 🔐 Initial Setup Procedure

When starting with a fresh database, the platform needs to be initialized with a Super Admin account:

1. **Automatic Detection**: When you first visit the application, it checks if the platform is initialized
2. **Login Redirect**: If no users exist, you'll be redirected to the login page by default
3. **Manual Setup Access**: Navigate to `/setup` manually to access the initialization form
4. **Create Super Admin**: Fill in the email and password to create the first Super Admin account
5. **Start Using**: After successful setup, you'll be redirected to login with your new credentials

> **Note**: The `/setup` route is only accessible when the database is empty (no users exist). Once the first user is created, this route becomes inaccessible for security reasons.

## 🎯 Features

### ✅ Implemented
- **First-Run Setup**: Automatic detection and guided superuser creation
- **Authentication**: JWT-based login/logout with token management
- **Dashboard**: Professional admin dashboard with statistics
- **Navigation**: Collapsible sidebar with ShadCN patterns
- **Context Switching**: Multi-tenant support with client account switching
- **Modern UI**: Clean, responsive interface built with shadcn/ui components

### 📋 Coming Soon
- **User Management**: Complete user lifecycle management with role assignments
- **Role & Permission Management**: Hierarchical RBAC administration
- **Client Account Management**: Multi-tenant organization control
- **Group Management**: Team organization and permission aggregation
- **Audit Logs**: Comprehensive activity tracking

## 🏗️ Tech Stack

### Core Framework

- **React 19** - Latest React with concurrent features
- **TypeScript** - Full type safety across the application
- **Vite 7** - Lightning-fast build tool and dev server
- **Bun** - Fast package manager and runtime

### Routing & State

- **TanStack Router** - Type-safe routing with automatic code splitting
- **TanStack Query** - Server state management and caching
- **TanStack Form** - Performant form handling with validation

### UI & Styling

- **Tailwind CSS v4** - Latest utility-first CSS framework
- **shadcn/ui** - High-quality, accessible React components
- **Radix UI** - Unstyled, accessible UI primitives
- **Lucide React** - Beautiful, customizable icons

### Development

- **ESLint** - Code linting and formatting
- **TypeScript** - Static type checking
- **Vite Dev Server** - Hot module replacement for fast development

## 📁 Project Structure

```
admin-ui/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── ui/             # shadcn/ui base components
│   │   ├── app-sidebar.tsx # Main navigation sidebar
│   │   ├── nav-main.tsx    # Navigation menu component
│   │   ├── nav-user.tsx    # User profile dropdown
│   │   ├── team-switcher.tsx # Context/client switcher
│   │   ├── login-form.tsx  # Authentication form
│   │   └── setup-form.tsx  # Initial setup form
│   ├── routes/             # Application routes
│   │   ├── __root.tsx      # Root layout
│   │   ├── index.tsx       # Entry point with auth check
│   │   ├── dashboard.tsx   # Main dashboard
│   │   ├── login.tsx       # Login page
│   │   ├── setup.tsx       # First-run setup
│   │   ├── settings.tsx    # System settings page
│   │   └── 404.tsx         # Not found page
│   ├── lib/                # Utility functions
│   │   └── utils.ts        # Common utilities
│   ├── hooks/              # Custom React hooks
│   │   └── use-mobile.ts   # Mobile detection hook
│   ├── App.tsx             # Main app component
│   ├── main.tsx            # Application entry point
│   └── index.css           # Global styles with Tailwind
├── public/                 # Static assets
├── components.json         # shadcn/ui configuration
├── tailwind.config.ts      # Tailwind CSS configuration
├── vite.config.ts          # Vite configuration with API proxy
└── package.json            # Dependencies and scripts
```

## 🔧 Development Workflow

### Adding New Components

```bash
# Add shadcn/ui components using Bun
bunx shadcn@latest add button
bunx shadcn@latest add form
bunx shadcn@latest add input

# Components are automatically added to src/components/ui/
```

### Creating New Routes

1. Create a new file in `src/routes/`
2. TanStack Router automatically generates route configuration
3. Import and use in your route tree

### API Integration

The frontend communicates with the FastAPI backend through Vite's proxy configuration:

- **Development**: Proxied from `/v1/*` to `http://localhost:8030`
- **Production**: Configured via Docker Compose

Key endpoints:

- `GET /v1/platform/status` - Check initialization status
- `POST /v1/platform/initialize` - Create first superuser
- `POST /v1/auth/login` - User authentication
- `POST /v1/auth/logout` - User logout
- `POST /v1/auth/refresh` - Refresh access token
- `GET /v1/auth/me` - Current user profile

## 🐳 Docker Deployment

### Multi-stage Dockerfile

```dockerfile
# Build stage with Bun
FROM oven/bun:latest as builder
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install
COPY . .
RUN bun run build

# Production stage with Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
```

### Docker Compose Integration

```yaml
services:
  admin-ui:
    build: ./admin-ui
    ports:
      - "8088:80"
    depends_on:
      - api
    environment:
      - API_BASE_URL=http://api:8030
```

## 🎨 UI Components

### Authentication Flow

- **Setup Form**: First-run superuser creation
- **Login Form**: Standard email/password authentication
- **Protected Routes**: Automatic redirect based on auth status

### Management Interfaces

- **User Management**: CRUD operations with role assignments
- **Role Management**: Permission hierarchy administration
- **Client Accounts**: Multi-tenant organization control
- **Groups**: Team-based permission aggregation

### Design System

- **Color Scheme**: Professional dark/light theme support
- **Typography**: Consistent font hierarchy
- **Spacing**: Tailwind's systematic spacing scale
- **Components**: Accessible, keyboard-navigable interfaces

## 🔒 Security Features

- **JWT Token Management**: Secure authentication flow
- **Route Protection**: Automatic auth state management
- **CSRF Protection**: Built-in security measures
- **Input Validation**: Client-side form validation

## 📈 Performance

- **Code Splitting**: Automatic route-based splitting
- **Tree Shaking**: Unused code elimination
- **Asset Optimization**: Vite's built-in optimizations
- **Caching**: TanStack Query for efficient data fetching

## 🧪 Testing

```bash
# Run linting
bun run lint

# Type checking
bun run build
```

## 🚀 Production Build

```bash
# Build optimized bundle
bun run build

# Preview production build locally
bun run preview
```

The build creates an optimized static site in the `dist/` directory, ready for deployment.

## 🔗 Related Projects

- **[outlabsAuth API](../README.md)** - FastAPI backend service
- **[Documentation](../docs/)** - Comprehensive API documentation

## 📄 License

Enterprise license - see main project for details.

---

**Built with ❤️ using the latest React ecosystem and Tailwind CSS v4**
