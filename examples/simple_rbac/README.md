# SimpleRBAC Example - Blog API

This example demonstrates a simple blog API using OutlabsAuth's **SimpleRBAC** preset.

## Features

- ✅ User registration and login
- ✅ JWT authentication
- ✅ Four role levels: Reader, Writer, Editor, Admin
- ✅ Blog post CRUD operations
- ✅ Permission-based access control
- ✅ Owner-based permissions (users can edit their own posts)

## Roles & Permissions

### Reader (Default)
- `post:read` - Read published blog posts

### Writer
- `post:read` - Read published blog posts
- `post:create` - Create new posts
- `post:update_own` - Update own posts
- `post:delete_own` - Delete own posts

### Editor
- `post:*` - Full post management (all users' posts)
- `user:read` - View user information

### Admin
- `*:*` - Full system access

## Installation

```bash
# Install OutlabsAuth (when published)
pip install outlabs-auth

# Or install from local development
cd ../..
pip install -e .

# Install additional dependencies
pip install fastapi uvicorn motor beanie
```

## Quick Start

### 1. Start MongoDB

```bash
# Using Docker (recommended)
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Or install MongoDB locally
# https://www.mongodb.com/docs/manual/installation/
```

### 2. Seed Demo Data

```bash
# Create demo users, roles, and blog posts
python seed_data.py
```

This creates:
- **4 roles**: reader, writer, editor, admin
- **5 demo users** with different roles
- **15 sample blog posts** (some published, some drafts)
- **Sample comments** on posts

**Demo Credentials:**
```
Admin:     admin@blog.com     / password123
Editor:    editor@blog.com    / password123
Writer 1:  writer1@blog.com   / password123
Writer 2:  writer2@blog.com   / password123
Reader:    reader@blog.com    / password123
```

### 3. Run the Application

```bash
# Using uvicorn (recommended)
uvicorn main:app --reload --port 8000

# Or run directly
python main.py
```

The API will be available at `http://localhost:8000`

### 4. Test the API

Visit the interactive docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Test Scenarios

Try these scenarios with the seeded demo data:

1. **Login as Reader** (`reader@blog.com`)
   - ✅ Can view published posts
   - ❌ Cannot create new posts (403 Forbidden)
   - ❌ Cannot edit any posts

2. **Login as Writer** (`writer1@blog.com`)
   - ✅ Can create new posts
   - ✅ Can edit their own posts
   - ❌ Cannot edit Writer 2's posts (403 Forbidden)
   - ❌ Cannot delete other writers' posts

3. **Login as Editor** (`editor@blog.com`)
   - ✅ Can edit ANY post (even others' posts)
   - ✅ Can delete any post
   - ✅ Can publish/unpublish posts
   - ✅ Can view all users

4. **Login as Admin** (`admin@blog.com`)
   - ✅ Full system access
   - ✅ Can manage users
   - ✅ Can assign roles
   - ✅ Can delete posts, users, etc.

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Example Usage

### 1. Register a New User

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "username": "john",
    "password": "SecurePass123!",
    "full_name": "John Doe"
  }'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### 2. Login

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123!"
  }'
```

### 3. Get Current User Info

```bash
curl -X GET http://localhost:8000/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "id": "507f1f77bcf86cd799439011",
  "email": "john@example.com",
  "username": "john",
  "full_name": "John Doe",
  "permissions": ["post:read"]
}
```

### 4. Create a Blog Post (Writer+ Role Required)

First, assign the writer role:
```bash
# As admin, assign writer role
curl -X POST "http://localhost:8000/admin/users/{user_id}/role?role_name=writer" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

Then create a post:
```bash
curl -X POST http://localhost:8000/posts \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Blog Post",
    "content": "This is the content of my first blog post.",
    "tags": ["introduction", "first-post"],
    "published": true
  }'
```

### 5. List Blog Posts (Public)

```bash
# Public endpoint - no auth required for published posts
curl -X GET http://localhost:8000/posts
```

### 6. Update a Post (Author or Editor)

```bash
curl -X PUT http://localhost:8000/posts/{post_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Title",
    "content": "Updated content",
    "published": true
  }'
```

### 7. Delete a Post (Author or Editor)

```bash
curl -X DELETE http://localhost:8000/posts/{post_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Permission Logic

### Reading Posts
- **Unauthenticated users**: Can only read published posts
- **Authenticated users (reader)**: Can read published posts
- **Authenticated users (editor+)**: Can read all posts (including unpublished)

### Creating Posts
- Requires `post:create` permission (Writer+ role)

### Updating Posts
- **Own posts**: Requires `post:update_own` permission
- **Any post**: Requires `post:manage` permission (Editor+ role)

### Deleting Posts
- **Own posts**: Requires `post:delete_own` permission
- **Any post**: Requires `post:manage` permission (Editor+ role)

## Key Concepts Demonstrated

1. **SimpleRBAC Initialization**
   ```python
   auth = SimpleRBAC(config=auth_config)
   await auth.initialize()
   ```

2. **Dependency Injection**
   ```python
   @app.get("/posts")
   async def list_posts(ctx = Depends(deps.require_auth())):
       user = ctx.metadata.get("user")
       permissions = ctx.metadata.get("permissions")
   ```

3. **Permission Checks**
   ```python
   has_perm = await auth.permission_service.has_permission(
       user_id=ctx.user_id,
       permission="post:create",
   )
   ```

4. **Optional Authentication**
   ```python
   @app.get("/posts")
   async def list_posts(ctx = Depends(deps.optional_auth())):
       # ctx is None if not authenticated
       # ctx contains user data if authenticated
   ```

5. **Wildcard Permissions**
   ```python
   # Editor role has post:* which matches:
   # post:read, post:create, post:update, post:delete, post:manage, etc.
   ```

## Environment Variables

```bash
# MongoDB connection
MONGODB_URL=mongodb://localhost:27017

# Database name
DATABASE_NAME=blog_simple_rbac

# JWT secret key (change in production!)
SECRET_KEY=your-secret-key-change-in-production
```

## Testing

```bash
# Run with pytest (create test_main.py first)
pytest test_main.py -v
```

## Production Considerations

1. **Change the SECRET_KEY**: Use a strong, random secret key
2. **Enable HTTPS**: Use HTTPS in production
3. **Rate Limiting**: Add rate limiting to prevent abuse
4. **Database Backups**: Regular MongoDB backups
5. **Token Refresh**: Implement refresh token rotation
6. **Logging**: Add comprehensive logging
7. **Monitoring**: Monitor authentication failures

## Connect Admin UI

You can use the universal admin UI to manage this blog instance:

```bash
# In a new terminal, navigate to auth-ui
cd ../../auth-ui

# Set environment variable to point to blog API
export NUXT_PUBLIC_API_BASE_URL=http://localhost:8000/api

# Start Nuxt dev server
npm run dev
```

Then visit `http://localhost:3000` and login with any demo credentials.

The admin UI will automatically detect that this is a SimpleRBAC instance (no entity hierarchy) and hide entity-related features.

## Next Steps

- Check out the **EnterpriseRBAC example** (`../enterprise_rbac/`) for hierarchical permissions
- Check out the **Full-Featured example** (`../full_featured/`) for ABAC conditions
- Read the [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) for the complete vision

## License

MIT License - see LICENSE file for details
