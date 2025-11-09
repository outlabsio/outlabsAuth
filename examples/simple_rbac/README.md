# Blog API - SimpleRBAC Example

A complete blog application demonstrating **OutlabsAuth's SimpleRBAC** preset for flat role-based access control.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Ports available: 8003, 27017, 6379, 9090, 3000

### Start the API (Recommended - Unified Stack)

**Use the unified Docker Compose stack** from the project root - it includes MongoDB, Redis, Prometheus, and Grafana:

```bash
# From the project root
docker-compose up -d mongodb redis simple-rbac

# Or start everything (including observability)
docker-compose up -d
```

The API will be available at:
- **API**: http://localhost:8003
- **OpenAPI Docs**: http://localhost:8003/docs
- **Health Check**: http://localhost:8003/health
- **Metrics**: http://localhost:8003/metrics
- **Grafana Dashboard**: http://localhost:3000 (admin/admin)

See **[DOCKER.md](../../DOCKER.md)** for complete documentation on the unified stack.

### Alternative: Local Development

If you have MongoDB and Redis running locally, you can use the example's local docker-compose:

```bash
cd examples/simple_rbac
docker compose up --build
```

### Stop the API

```bash
# If using unified stack (from project root)
docker-compose down

# If using local docker-compose
cd examples/simple_rbac
docker compose down
```

## Development & Testing

### Quick Test Environment Reset

When testing auth features, you'll often need a clean database with known test users. Use the **reset script** to instantly reset to a good state:

```bash
cd examples/simple_rbac
python reset_test_env.py
```

This script:
- ✅ Clears all test data (users, roles, permissions, memberships)
- ✅ Creates default roles (reader, writer, editor, admin)
- ✅ Creates 3 test users with different permission levels
- ✅ Takes ~2 seconds

**Test Users Created:**

| Email | Password | Role | Use For |
|-------|----------|------|---------|
| `admin@test.com` | `Test123!!` | Admin | Full access testing |
| `editor@test.com` | `Test123!!` | Editor | Content management testing |
| `writer@test.com` | `Test123!!` | Writer | Basic content creation testing |

**When to use this:**
- 🔄 After breaking auth/permissions during development
- 🧪 Before running integration tests
- 🚀 Setting up a demo environment
- 🐛 Debugging auth issues

## What This Example Demonstrates

### SimpleRBAC Features
- ✅ **Flat RBAC**: No entity hierarchy, just users → roles → permissions
- ✅ **Direct role assignment**: Users get roles directly
- ✅ **Simple permissions**: Clear permission model
- ✅ **Minimal code**: Most routes provided by OutlabsAuth

### Domain: Blog Application
- **Posts**: Create, read, update, delete blog posts
- **Comments**: Add and manage comments
- **Roles**: Reader, Writer, Editor, Admin
- **Permissions**: Granular control over who can do what

## Default Roles

Created automatically on startup:

| Role | Permissions | Can Do |
|------|-------------|--------|
| **Reader** | None | View published posts |
| **Writer** | `post:create`, `comment:create` | Create posts and comments |
| **Editor** | `post:create`, `post:update_own`, `post:delete_own`, `comment:create` | Manage own content |
| **Admin** | `post:*`, `comment:*`, `user:*` | Full control |

## API Routes

### Provided by OutlabsAuth

OutlabsAuth routers give you **20+ routes** for free:

**Auth** (`/auth/*`):
```bash
POST   /auth/register      # Register new user
POST   /auth/login         # Login and get JWT
POST   /auth/logout        # Logout
POST   /auth/refresh       # Refresh access token
```

**Users** (`/users/*`):
```bash
GET    /users/me           # Get current user
GET    /users              # List all users (admin)
GET    /users/{id}         # Get user by ID
PUT    /users/{id}         # Update user
DELETE /users/{id}         # Delete user
POST   /users/{id}/roles   # Assign role to user
```

**Roles** (`/roles/*`):
```bash
GET    /roles              # List all roles
POST   /roles              # Create new role (admin)
GET    /roles/{id}         # Get role details
PUT    /roles/{id}         # Update role
DELETE /roles/{id}         # Delete role
```

**Permissions** (`/permissions/*`):
```bash
GET    /permissions/check  # Check user permissions
```

**API Keys** (`/api-keys/*`):
```bash
POST   /api-keys           # Create API key
GET    /api-keys           # List API keys
DELETE /api-keys/{id}      # Revoke API key
```

### Custom Blog Routes

Only **8 routes** we needed to implement:

**Posts**:
```bash
POST   /posts              # Create post (writer+)
GET    /posts              # List posts (public)
GET    /posts/{id}         # View post (public)
PUT    /posts/{id}         # Update post (editor: own, admin: any)
DELETE /posts/{id}         # Delete post (admin)
```

**Comments**:
```bash
POST   /posts/{id}/comments   # Add comment (writer+)
GET    /posts/{id}/comments   # List comments (public)
DELETE /comments/{id}          # Delete comment (owner or admin)
```

**Health**:
```bash
GET    /health             # Health check
```

## Example API Calls

### 1. Register a New User

```bash
curl -X POST http://localhost:8003/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePassword123!",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### 2. Login

```bash
curl -X POST http://localhost:8003/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePassword123!"
  }'
```

### 3. Get Current User

```bash
curl -X GET http://localhost:8003/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Create a Blog Post (requires writer role)

```bash
curl -X POST http://localhost:8003/posts \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "This is the content of my first blog post!",
    "status": "published",
    "tags": ["introduction", "first-post"]
  }'
```

### 5. List Published Posts (public)

```bash
curl -X GET http://localhost:8003/posts
```

### 6. Add Comment to Post (requires writer role)

```bash
curl -X POST http://localhost:8003/posts/POST_ID/comments \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Great post! Thanks for sharing."
  }'
```

### 7. Assign Role to User

```bash
# First, get the role ID
curl -X GET http://localhost:8003/roles

# Then assign it to the user
curl -X POST http://localhost:8003/users/USER_ID/roles \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "WRITER_ROLE_ID"
  }'
```

## Running Tests

```bash
# Make sure the API is running
docker compose up

# In another terminal, run tests
python test_api.py
```

## Development

### Hot Reload

The Docker setup supports hot reload for both:
- **Library code** (`outlabs_auth/`) - Changes reload automatically
- **Example code** (`examples/simple_rbac/`) - Changes reload automatically

Just edit files and save - the server restarts instantly!

### Project Structure

```
examples/simple_rbac/
├── main.py                # FastAPI app with SimpleRBAC
├── models.py              # BlogPost and Comment models
├── docker-compose.yml     # Docker setup
├── Dockerfile             # Container definition
├── test_api.py           # Integration tests
├── REQUIREMENTS.md        # Detailed use cases
└── README.md              # This file
```

### Key Files

**main.py**:
- Initializes SimpleRBAC
- Includes OutlabsAuth routers (auth, users, roles, etc.)
- Implements blog-specific routes (posts, comments)
- Creates default roles on startup

**models.py**:
- `BlogPost`: Title, content, author, status, tags
- `Comment`: Content, author, timestamps

## Configuration

Environment variables (set in `docker-compose.yml`):

```yaml
MONGODB_URL=mongodb://host.docker.internal:27017
DATABASE_NAME=blog_simple_rbac
SECRET_KEY=development-secret-key-change-in-production
REDIS_URL=redis://:guest@host.docker.internal:6379  # Optional
```

## Permission Model

### Post Permissions

| Permission | Who Has It | What It Allows |
|------------|------------|----------------|
| `post:create` | Writer, Editor, Admin | Create new posts |
| `post:update_own` | Editor, Admin | Update own posts |
| `post:update` | Admin | Update ANY post |
| `post:delete_own` | Editor, Admin | Delete own posts |
| `post:delete` | Admin | Delete ANY post |

### Comment Permissions

| Permission | Who Has It | What It Allows |
|------------|------------|----------------|
| `comment:create` | Writer, Editor, Admin | Add comments |
| `comment:delete` | Admin | Delete ANY comment |
| (ownership) | Comment author | Delete own comment |

## Database

**Collections created**:
- `users` - User accounts
- `roles` - Role definitions
- `permissions` - Permission registry
- `blog_posts` - Blog posts
- `comments` - Post comments

**Default database**: `blog_simple_rbac`

## Troubleshooting

### API won't start

**Check MongoDB**:
```bash
mongosh --host localhost:27017
```

**Check logs**:
```bash
docker compose logs -f
```

### Permission denied errors

Make sure the user has the correct role:
1. Login as admin
2. Assign role via `/users/{id}/roles`
3. User needs to re-login to get updated permissions

### Hot reload not working

Volume mounts should be writable (not read-only):
```yaml
volumes:
  - ../../outlabs_auth:/app/outlabs_auth        # ✅ Good
  - ../../outlabs_auth:/app/outlabs_auth:ro     # ❌ Won't reload
```

## Next Steps

1. **Read REQUIREMENTS.md** for detailed use cases
2. **Explore the OpenAPI docs** at http://localhost:8003/docs
3. **Run the tests** with `python test_api.py`
4. **Compare with EnterpriseRBAC** example to see the difference

## SimpleRBAC vs EnterpriseRBAC

**Use SimpleRBAC** (this example) when:
- ✅ Flat organization (no departments/teams)
- ✅ Direct role assignment
- ✅ Simple permission model
- ✅ Small to medium scale

**Use EnterpriseRBAC** when:
- ⚠️ Hierarchical organizations (company → dept → team)
- ⚠️ Entity-based permissions (access by department)
- ⚠️ Tree permissions (manager sees all team data)
- ⚠️ Large scale, complex structures

See `../enterprise_rbac/` for the EnterpriseRBAC example.

## Documentation

- **This README**: Quick start and API reference
- **REQUIREMENTS.md**: Detailed use cases and requirements
- **OpenAPI Docs**: http://localhost:8003/docs (interactive)
- **OutlabsAuth Docs**: `../../docs/` (library documentation)

## License

Same as OutlabsAuth library.

---

**Version**: 1.0.0
**Created**: 2025-01-25
**OutlabsAuth**: SimpleRBAC Preset
