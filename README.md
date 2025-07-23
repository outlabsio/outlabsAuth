# OutLabs Auth - Enterprise RBAC Authentication API

**A production-ready FastAPI authentication and authorization service** with enterprise-grade Role-Based Access Control (RBAC), built on MongoDB with Beanie ODM. Designed to be integrated into your applications as a centralized auth service.

## 🎯 Project Status

**Backend API**: ✅ Production Ready (100% core features, all tests passing)  
**Frontend Admin UI**: 🔄 85% Complete (optional management interface)  
**Documentation**: 📚 70% Complete  
**Test Coverage**: ✅ 236 tests, 100% pass rate

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for detailed status and roadmap.

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
- **Strong Password Policies**: Enforced uppercase, lowercase, digit, and special character requirements
- **Account Security**: Email verification, password reset, account locking
- **Input Validation**: SQL/NoSQL injection prevention with input sanitization

### Authorization System  
- **Explicit Permission Scoping**: Three levels of access control
  - **Entity-specific**: `entity:read` - Access only the specific entity
  - **Hierarchical**: `entity:read_tree` - Access all descendants (not the entity itself)
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

The platform uses a sophisticated permission system with explicit scoping for maximum flexibility and security.

> **Important**: Tree permissions grant access to descendants only, not the entity where assigned. See the [Tree Permissions Guide](docs/TREE_PERMISSIONS_GUIDE.md) for detailed information.

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
   - Scope: ALL descendants of the entity (NOT the entity where assigned)
   - Use Case: Organization admins who manage all teams within their org

3. **Platform-Wide Permissions** (Least Restrictive)
   - Format: `resource:action_all`
   - Example: `entity:read_all`, `user:manage_all`, `role:create_all`
   - Scope: All entities across the entire platform
   - Use Case: Platform administrators with global access

#### System Permissions (Built-in)

All system permissions follow a consistent CRUD pattern for predictability:

**Core Resources**:
- `entity:create`, `entity:read`, `entity:update`, `entity:delete` - Entity operations
- `user:create`, `user:read`, `user:update`, `user:delete` - User operations  
- `role:create`, `role:read`, `role:update`, `role:delete` - Role operations
- `member:create`, `member:read`, `member:update`, `member:delete` - Membership operations
- `permission:create`, `permission:read`, `permission:update`, `permission:delete` - Permission operations

**Special Permissions**:
- `user:invite` - Compound operation to create user + assign to entity
- `*` - Wildcard permission (grants all permissions - system admin only)
- `*:read_all` - Read-only wildcard (grants all read permissions)

Each permission also has `_tree` and `_all` variants for hierarchical and platform-wide access.

#### Permission Examples

```python
# Organization Admin Role
{
    "name": "org_admin",
    "permissions": [
        "entity:read",           # Read the org entity itself
        "entity:read_tree",      # Read all child entities below org
        "entity:update",         # Update only the org entity itself
        "entity:create",         # Create child entities
        "user:read_tree",        # Read users in org and children
        "user:create_tree",      # Create users in org and children
        "user:update_tree",      # Update users in org and children
        "user:delete_tree",      # Delete users in org and children
        "role:read",             # Read roles at org level
        "role:create",           # Create roles at org level
        "role:update",           # Update roles at org level
        "role:delete"            # Delete roles at org level
    ]
}

# Team Lead Role
{
    "name": "team_lead",
    "permissions": [
        "entity:read",           # Read only their team
        "entity:update",         # Update team settings
        "user:read",             # Read team members
        "user:create",           # Create team members
        "user:update",           # Update team members
        "user:delete",           # Delete team members
        "member:read",           # Read team memberships
        "member:create",         # Add team members
        "member:update",         # Update memberships
        "member:delete"          # Remove team members
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

### Entity System & Platform Flexibility

**Key Design Principle**: In OutlabsAuth, there's no separate "Platform" model. Any entity without a parent is automatically a platform. This provides incredible flexibility:

- **Top-level entities** (no parent) = Platforms
- Use **any entity_type** for your platform: "workspace", "company", "account", "tenant", etc.
- Complete **data isolation** between platforms
- Each platform can have its own **organizational structure**

Examples:
- SaaS app: Create a "workspace" entity (no parent) for each customer
- Enterprise: Create a "company" entity (no parent) as your platform
- Multi-brand: Create separate top-level entities for each brand

### Entity Hierarchy

Once you have your top-level entity (platform), build any structure:

```
Workspace (Top-level entity = Platform)
├── Organization
│   ├── Division
│   │   ├── Team
│   │   └── Access Group
│   └── Region
└── Department
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
   - System permissions only (hardcoded, immutable)
   - All resources use standard CRUD permissions
   - Entity, User, Role, Member, and Permission operations
   - Wildcard permissions for system administrators

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

### Comprehensive Test Suite

OutlabsAuth includes a comprehensive test suite with **230+ tests** covering all critical functionality:

**Test Coverage** (94.7% pass rate):
- ✅ **Authentication**: Login, logout, token refresh, password reset
- ✅ **User Management**: CRUD operations, profile updates, bulk operations  
- ✅ **Entity Hierarchy**: Tree validation, circular prevention, multi-level operations
- ✅ **Entity Access**: Search, filtering, visibility with tree permissions
- ✅ **Roles & Permissions**: Assignment, inheritance, tree permissions
- ✅ **Memberships**: User-entity relationships, multi-role support
- ✅ **Permission Enforcement**: Endpoint protection, hierarchical access
- ✅ **Complex Scenarios**: Real-world multi-entity workflows
- ✅ **Security**: Permission escalation prevention, data isolation

### Running Tests

```bash
# Run the comprehensive test suite
uv run python test/run_all_tests.py

# Run specific test suite
uv run python test/run_all_tests.py --test authentication
uv run python test/run_all_tests.py --test complex_scenarios

# List available test suites
uv run python test/run_all_tests.py --list

# Run with pytest directly (for debugging)
uv run pytest test/test_authentication.py -v

# Clear auth token cache before testing
uv run python test/run_all_tests.py --clear-cache
```

### Test Organization

Tests are organized into focused suites:
- `test_authentication.py` - Auth flows and token management
- `test_user_management.py` - User CRUD and profiles
- `test_entity_hierarchy.py` - Entity relationships and validation
- `test_entity_access.py` - Entity visibility and search
- `test_roles_permissions.py` - Role and permission management
- `test_memberships.py` - User-entity relationships
- `test_permission_enforcement.py` - Endpoint access control
- `test_complex_scenarios.py` - Real-world workflows
- `test_security.py` - Security vulnerability tests

### Code Quality Checks

```bash
# Format code
uv run black .
uv run isort .

# Lint
uv run flake8 .

# Type checking  
uv run mypy .

# Run all quality checks before committing
uv run black . && uv run isort . && uv run flake8 . && uv run mypy .
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