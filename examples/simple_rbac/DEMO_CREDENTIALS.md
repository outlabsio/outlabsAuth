# SimpleRBAC Demo Credentials

This file contains credentials for the seeded demo data in the SimpleRBAC example.

## How to Seed the Database

### For Docker Compose Setup (Recommended)

```bash
# Make sure Docker stack is running
docker compose up -d

# Run seed script pointing to Docker MongoDB (port 27018)
cd examples/simple_rbac
MONGODB_URL="mongodb://localhost:27018" \
DATABASE_NAME="blog_simple_rbac" \
uv run python reset_test_env.py
```

### For Local MongoDB

```bash
cd examples/simple_rbac
uv run python reset_test_env.py
```

## Demo Users

All users share the same password: **`Asd123$$$`**

| Email | Role | Permissions | Notes |
|-------|------|-------------|-------|
| `system@outlabs.io` | **Admin** | Full access (all permissions) | System administrator |
| `writer@example.com` | **Writer** | Create posts, create comments | Content creator |
| `editor@example.com` | **Editor** | Create/edit/delete own posts + comments | Content editor |
| `reader@example.com` | **None** | View public content only | No assigned role |
| `contractor@example.com` | **Writer (Temporary)** | Same as Writer, expires in 90 days | Temporary access example |

## What Gets Created

### Users
- 5 demo users with different roles
- All active status
- Full profile information (first name, last name, email)

### Roles
- **Admin**: 7 permissions (full access)
- **Editor**: 5 permissions (manage own content)
- **Writer**: 2 permissions (create content)
- **Reader**: 0 permissions (view only)

### Blog Posts
1. "Welcome to Our Blog!" (by admin, published)
2. "My First Blog Post" (by writer, published)
3. "Understanding RBAC..." (by editor, draft)

### Comments
- 2 sample comments on the published posts

### Role Memberships
- Full audit trail with `UserRoleMembership` records
- Demonstrates both permanent and temporary role assignments
- Shows "assigned by" tracking

## Testing Scenarios

### Scenario 1: Admin Full Access
**Login as**: `system@outlabs.io` / `Asd123$$$`

- Can create, edit, delete ANY post
- Can manage all users and roles
- Can create API keys
- Can view all memberships

### Scenario 2: Writer Creating Content
**Login as**: `writer@example.com` / `Asd123$$$`

- Can create new blog posts
- Can add comments
- Cannot edit other users' posts
- Cannot manage users or roles

### Scenario 3: Editor Managing Own Content
**Login as**: `editor@example.com` / `Asd123$$$`

- Can create, edit, delete own posts
- Can add comments
- Cannot edit other users' posts
- Cannot delete admin posts

### Scenario 4: Reader (No Role)
**Login as**: `reader@example.com` / `Asd123$$$`

- Can view published posts
- Can view comments
- Cannot create or edit anything
- Useful for testing permission denials

### Scenario 5: Temporary Access
**Login as**: `contractor@example.com` / `Asd123$$$`

- Has Writer permissions for 90 days
- Membership expires automatically
- Good for testing temporary role assignments

## API Endpoints to Test

### Authentication
```bash
# Login
curl -X POST http://localhost:8003/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "system@outlabs.io", "password": "Asd123$$$"}'

# Get current user
curl http://localhost:8003/v1/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Blog Posts
```bash
# List posts (public)
curl http://localhost:8003/posts

# Create post (requires writer+ role)
curl -X POST http://localhost:8003/posts \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My New Post",
    "content": "Content here",
    "status": "published",
    "tags": ["test"]
  }'
```

### Roles & Permissions
```bash
# List roles
curl http://localhost:8003/v1/roles

# View my memberships
curl http://localhost:8003/memberships/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Resetting the Database

To start fresh:

```bash
# Stop Docker stack
docker compose down

# Remove MongoDB volume
docker volume rm outlabs-mongodb-data

# Restart and reseed
docker compose up -d
cd examples/simple_rbac
MONGODB_URL="mongodb://localhost:27018" \
DATABASE_NAME="blog_simple_rbac" \
uv run python reset_test_env.py
```

## Observability

After logging in and creating content, check:
- **Grafana**: http://localhost:3011 (admin/admin)
  - View login metrics
  - See permission check rates
  - Monitor active sessions
- **Prometheus**: http://localhost:9090
  - Query raw metrics
  - Check scraping status
