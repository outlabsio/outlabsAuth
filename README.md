# OutLabs Auth - Enterprise RBAC Authentication API

**A production-ready FastAPI authentication and authorization service** with enterprise-grade Role-Based Access Control (RBAC), built on MongoDB with Beanie ODM. Designed to be integrated into your applications as a centralized auth service.

## 🎯 What is OutLabs Auth?

OutLabs Auth is a **standalone authentication API** that provides:
- JWT-based authentication with refresh tokens
- Hierarchical RBAC with permission inheritance
- Multi-tenant platform isolation
- Flexible entity system for any organizational structure
- RESTful API endpoints for all auth operations

**Includes an admin UI** built with Nuxt 3 for managing users, roles, and permissions - but the core value is the authentication API itself.

## 🚀 Core Features

### Authentication API
- **JWT Authentication**: Access tokens (15min) and refresh tokens (30 days)
- **Multi-device Sessions**: Support for multiple concurrent sessions
- **Rate Limiting**: Built-in brute force protection
- **Password Policies**: Configurable password requirements
- **Account Security**: Email verification, password reset, account locking

### Authorization System  
- **Explicit Permission Scoping**: Three levels of access control
  - **Entity-specific**: `entity:read` - Access only the specific entity
  - **Hierarchical**: `entity:read_tree` - Access entity and all descendants
  - **Platform-wide**: `entity:read_all` - Access all entities in platform
- **Action-based Permissions**: Separate permissions for each action (read, create, update, delete)
- **Custom Permissions**: Create domain-specific permissions for your application
- **Role Templates**: Pre-configured roles for common use cases

### Multi-Tenant Support
- **Platform Isolation**: Complete data separation between platforms
- **Flexible Entity Model**: Adapt to any organizational structure
- **Cross-Platform Users**: Users can belong to multiple platforms

## 📋 Prerequisites

- Python 3.11+
- MongoDB 4.4+
- Node.js 18+ (for frontend development)
- UV package manager for Python
- Bun package manager for frontend

## 🚦 Quick Start

### Running the Auth API

1. Clone the repository:
```bash
git clone https://github.com/outlabsai/outlabsAuth.git
cd outlabsAuth
```

2. Install Python dependencies using UV:
```bash
uv sync
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Start MongoDB (if not already running):
```bash
# Using Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Or using local installation
mongod
```

5. Run the backend:
```bash
uv run uvicorn api.main:app --reload --port 8030
```

### API Documentation

Once running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8030/docs
- **ReDoc**: http://localhost:8030/redoc

### Optional: Admin UI Setup

The admin UI is included for managing users, roles, and permissions:

```bash
cd frontend
bun install
bun dev
```

Access at http://localhost:3000 (requires API to be running)

## 📡 API Endpoints

### Authentication Endpoints
```
POST   /v1/auth/register          # Register new user
POST   /v1/auth/login             # Login with email/password
POST   /v1/auth/refresh           # Refresh access token
POST   /v1/auth/logout            # Logout and revoke refresh token
POST   /v1/auth/forgot-password   # Request password reset
POST   /v1/auth/reset-password    # Reset password with token
GET    /v1/auth/me               # Get current user info
```

### User Management
```
GET    /v1/users                  # List users (with pagination/filters)
POST   /v1/users                  # Create new user
GET    /v1/users/{id}            # Get user details
PATCH  /v1/users/{id}            # Update user
DELETE /v1/users/{id}            # Delete user
POST   /v1/users/{id}/roles      # Assign roles to user
DELETE /v1/users/{id}/roles/{role_id}  # Remove role from user
```

### Role & Permission Management
```
GET    /v1/roles                  # List roles
POST   /v1/roles                  # Create role
PATCH  /v1/roles/{id}            # Update role
DELETE /v1/roles/{id}            # Delete role
GET    /v1/permissions           # List permissions
POST   /v1/permissions           # Create custom permission
```

See full [API Documentation](docs/API_ENDPOINTS.md) for complete endpoint reference.

## 🏗️ System Architecture

### Multi-Tenant Platform Support

OutLabs Auth is designed to support diverse business models through its flexible entity system:

1. **Complex Hierarchical Organizations** - Multi-level real estate brokerages with divisions, branches, and teams
2. **Simple Flat Platforms** - Role-based access without organizational hierarchy  
3. **Multi-Sided Marketplaces** - Separate portals for different user types (clients vs. service providers)
4. **Hybrid Models** - Start flat and optionally add team structures as you grow

See [Platform Scenarios](docs/PLATFORM_SCENARIOS.md) for detailed examples.

### Platform Integration

For comprehensive integration guidance:
- 📘 [Platform Setup Guide](docs/PLATFORM_SETUP_GUIDE.md) - Step-by-step guide for setting up a new platform
- 🔧 [API Integration Patterns](docs/API_INTEGRATION_PATTERNS.md) - Common patterns for platform integration
- 🏢 [Platform Integration: Diverse](docs/PLATFORM_INTEGRATION_DIVERSE.md) - Real-world example of complex platform integration
- 👥 [Admin Access Levels](docs/ADMIN_ACCESS_LEVELS.md) - Multi-level admin access and UI adaptation

### Permission System

The platform uses a sophisticated permission system with explicit scoping for maximum flexibility and security:

#### Permission Scoping Levels

Permissions follow a three-tier scoping model:

1. **Entity-Specific Permissions** (Most Restrictive)
   - Format: `resource:action`
   - Example: `entity:read`, `user:update`, `role:delete`
   - Scope: Only the specific entity where the permission is granted
   - Use Case: Team members who should only access their own team

2. **Hierarchical Permissions** (Tree Access)
   - Format: `resource:action_tree`
   - Example: `entity:read_tree`, `user:update_tree`, `role:delete_tree`
   - Scope: The entity and ALL its descendants in the hierarchy
   - Use Case: Organization admins who manage all teams within their org

3. **Platform-Wide Permissions** (Least Restrictive)
   - Format: `resource:action_all`
   - Example: `entity:read_all`, `user:manage_all`, `role:create_all`
   - Scope: All entities across the entire platform
   - Use Case: Platform administrators with global access

#### System Permissions (Built-in)
These permissions are hardcoded and always available:
- `system:manage_all`, `system:read_all` - Full system access
- `platform:manage_platform` - Platform administration
- `entity:create`, `entity:read`, `entity:update`, `entity:delete` - Entity operations
- `user:manage`, `user:read`, `user:create`, `user:update`, `user:delete` - User operations
- `role:manage`, `role:read`, `role:create`, `role:update`, `role:delete` - Role operations
- `member:manage`, `member:read`, `member:add`, `member:update`, `member:remove` - Membership operations

#### Custom Permissions
Created during system initialization for common use cases:
- **Organization**: `organization:manage_all`, `organization:create`, etc.
- **Team/Branch**: `team:create`, `team:manage`, `team:read`
- **Analytics**: `analytics:view`, `analytics:export`
- **Audit**: `audit:view`, `audit:export`
- **API**: `api:manage`, `api:create`
- **Settings**: `settings:manage`, `settings:view`

#### Permission Examples

```python
# Organization Admin Role
{
    "name": "org_admin",
    "permissions": [
        "entity:read_tree",      # Read org and all child entities
        "entity:update",         # Update only the org entity itself
        "entity:create",         # Create child entities
        "user:manage_tree",      # Manage users in org and children
        "role:manage"            # Manage roles at org level
    ]
}

# Team Lead Role
{
    "name": "team_lead",
    "permissions": [
        "entity:read",           # Read only their team
        "entity:update",         # Update team settings
        "user:manage",           # Manage team members
        "member:manage"          # Manage team memberships
    ]
}

# Platform Viewer Role
{
    "name": "platform_viewer",
    "permissions": [
        "entity:read_all",       # Read all entities
        "user:read_all",         # Read all users
        "role:read_all"          # Read all roles
    ]
}
```

📚 **For detailed permission documentation, see [docs/PERMISSIONS.md](docs/PERMISSIONS.md)**

### Entity Hierarchy

```
Platform (Root)
├── Organization
│   ├── Branch
│   │   ├── Team
│   │   └── Access Group
│   └── Branch
└── Organization
```

Each entity can have:
- **Roles**: Define permission sets
- **Members**: Users assigned to the entity with specific roles
- **Custom Permissions**: Entity-specific permissions

## 🚦 Getting Started

### 1. System Initialization

When you first start the system, it needs to be initialized. Visit http://localhost:5173 and follow the initialization wizard.

#### What Happens During Initialization:

1. **Root Platform Entity Creation**
   - Creates the top-level platform entity
   - Sets up the entity hierarchy structure
   - Configures allowed child entity types

2. **System Role Creation**
   - System Administrator (full access)
   - Platform Administrator (platform management)
   - Organization Administrator (org-level control)
   - Team Lead (team management)
   - Member (basic access)
   - Viewer (read-only)

3. **Permission Initialization**
   - 41 system permissions (hardcoded, immutable)
   - 19 custom permissions for common use cases:
     - Organization management (5 permissions)
     - Team/Branch operations (3 permissions)
     - Project management (3 permissions)
     - Analytics & reporting (2 permissions)
     - Audit & compliance (2 permissions)
     - API management (2 permissions)
     - Settings management (2 permissions)

4. **Administrator Account**
   - Creates the first superuser account
   - Assigns System Administrator role
   - Auto-verifies the account
   - Adds to root platform entity

The initialization is idempotent - it can only run once when the database is empty.

### 2. Understanding Roles

Roles are collections of permissions that can be assigned to users. The system includes:

**Default System Roles:**
- **System Administrator**: Full system access (`*:manage_all`)
- **Platform Administrator**: Platform-wide management
- **Organization Administrator**: Organization-level control
- **Team Lead**: Team management capabilities
- **Member**: Basic read access
- **Viewer**: Read-only access

**Role Templates:**
When creating custom roles, you can use templates:
- **Viewer**: Read-only access to entities and users
- **Editor**: Create and edit capabilities
- **Administrator**: Full administrative access
- **Member Manager**: User and membership management
- **Project Lead**: Entity and member management
- **Developer**: Technical role with system read access
- **Auditor**: Compliance and audit access

### 3. Creating Custom Permissions

Custom permissions extend the system's capabilities for domain-specific needs:

```python
# Example: Creating a custom permission via API
POST /v1/permissions/
{
    "name": "invoice:approve",
    "display_name": "Approve Invoices",
    "description": "Allows approving invoices above threshold",
    "tags": ["finance", "approval"]
}
```

## 🧪 Testing

### Run Backend Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_auth_routes.py
```

### Code Quality Checks
```bash
# Format code
uv run black .
uv run isort .

# Lint
uv run flake8 .

# Type checking
uv run mypy .
```

## 📚 API Documentation

Once the backend is running, API documentation is available at:
- Swagger UI: http://localhost:8030/docs
- ReDoc: http://localhost:8030/redoc

## 🔧 Configuration

### Environment Variables

Key environment variables:

```env
# Database
DATABASE_URL=mongodb://localhost:27017
MONGO_DATABASE=outlabs_auth

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Permission Configuration

System permissions are defined in:
- `api/services/permission_management_service.py` - System permissions
- `api/services/system_service.py` - Custom permissions created during init

## 🚀 Deployment

### Using Docker

```bash
# Build and run with Docker Compose
docker compose up -d --build

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Production Considerations

1. **Database**: Use MongoDB replica sets for high availability
2. **Security**: 
   - Use strong SECRET_KEY
   - Enable HTTPS
   - Configure CORS properly
3. **Performance**:
   - Enable Redis for caching
   - Use connection pooling
   - Configure rate limiting
4. **Monitoring**: 
   - Set up logging aggregation
   - Monitor API metrics
   - Track permission usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use TypeScript for all frontend code
- Write tests for new features
- Update documentation as needed
- Use conventional commits

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Beanie](https://github.com/roman-right/beanie) - Async MongoDB ODM
- [Nuxt 3](https://nuxt.com/) - The intuitive Vue framework
- [Vue 3](https://vuejs.org/) - Progressive JavaScript framework
- [Nuxt UI Pro](https://ui.nuxt.com/pro) - Premium Vue components
- [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS framework
- [Pinia](https://pinia.vuejs.org/) - Vue store management

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the [API documentation](http://localhost:8030/docs)
- Review the [PROJECT_STATUS.md](PROJECT_STATUS.md) for current development status