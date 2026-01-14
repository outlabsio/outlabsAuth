# OutlabsAuth Examples

Complete example applications demonstrating OutlabsAuth usage patterns.

## Available Examples

### 1. [SimpleRBAC - Blog API](./simple_rbac/)

**Best for**: Simple applications with flat role structure

A blog API demonstrating:
- ✅ User registration and JWT authentication
- ✅ Flat role hierarchy (Reader, Writer, Editor, Admin)
- ✅ Permission-based access control
- ✅ Owner-based permissions
- ✅ Public and authenticated endpoints

**Complexity**: ⭐️ Beginner
**Lines of Code**: ~500
**Running**: `cd simple_rbac && python main.py`

[View Documentation →](./simple_rbac/README.md)

---

### 2. [EnterpriseRBAC - Project Management](./enterprise_rbac/)

**Best for**: Organizations with departments, teams, or complex hierarchy

A project management system demonstrating:
- ✅ Entity hierarchy (Company → Department → Team)
- ✅ Multiple roles per user in different entities
- ✅ Tree permissions (manage descendants)
- ✅ Closure table for O(1) queries
- ✅ Entity-scoped permission checking

**Complexity**: ⭐️⭐️⭐️ Intermediate
**Lines of Code**: ~700
**Running**: `cd enterprise_rbac && python main.py`

[View Documentation →](./enterprise_rbac/README.md)

---

### 3. [ABAC Cookbook](./abac_cookbook/)

**Best for**: Understanding ABAC conditions + condition groups

Demonstrates:
- ✅ ABAC role conditions + condition groups (AND/OR)
- ✅ Server-derived `resource.*` context for permission checks (no client trust)
- ✅ Public API configuration of ABAC via `/roles/{id}/conditions` endpoints

**Complexity**: ⭐️⭐️⭐️ Intermediate
**Running**: `cd abac_cookbook && uv run uvicorn main:app --port 8005`

---

## Quick Start

### Prerequisites

```bash
# PostgreSQL (required for all examples)
docker run -d -p 5432:5432 --name postgres -e POSTGRES_PASSWORD=postgres postgres:16

# Redis (required for full-featured example)
docker run -d -p 6379:6379 --name redis redis:latest
```

### Installation

```bash
# Clone the repository
git clone https://github.com/outlabs/outlabs-auth.git
cd outlabs-auth

# Install OutlabsAuth in development mode
pip install -e .

# Navigate to an example
cd examples/simple_rbac

# Install example-specific dependencies
pip install -r requirements.txt

# Run the example
python main.py
```

## Choosing an Example

### Use SimpleRBAC Example if:
- ✅ You have a simple application structure
- ✅ Users have ONE role globally
- ✅ No organizational hierarchy needed
- ✅ Permissions don't vary by context
- ✅ Quick to implement and understand

**Examples**: Personal blogs, SaaS products, simple APIs

---

### Use EnterpriseRBAC Example if:
- ✅ You have departments, teams, or divisions
- ✅ Users need different roles in different parts of the org
- ✅ Managers need to control descendant entities
- ✅ You need entity-scoped permissions
- ✅ Complex organizational structures

**Examples**: Corporate systems, multi-tenant apps, project management

---

### Use Full-Featured Example if:
- ✅ You need attribute-based conditions (budget limits, etc.)
- ✅ Permissions should adapt based on context
- ✅ High-performance requirements (Redis caching)
- ✅ Complex permission evaluation logic
- ✅ Advanced use cases

**Examples**: Financial systems, healthcare, government

---

## Learning Path

### 1. Start with SimpleRBAC (30 minutes)
- Understand basic authentication flow
- Learn JWT token handling
- Practice permission checks
- Implement owner-based access

### 2. Progress to EnterpriseRBAC (1-2 hours)
- Create entity hierarchies
- Assign multiple roles
- Use tree permissions
- Implement entity-scoped checks

### 3. Master Full-Featured (2-3 hours)
- Add ABAC conditions
- Implement context-aware roles
- Enable Redis caching
- Optimize performance

---

## Example Comparison

| Feature | SimpleRBAC | EnterpriseRBAC | Full-Featured |
|---------|-----------|----------------|---------------|
| **Authentication** | ✅ JWT | ✅ JWT | ✅ JWT + API Keys |
| **Roles per User** | 1 | Multiple | Multiple |
| **Entity Hierarchy** | ❌ | ✅ | ✅ |
| **Tree Permissions** | ❌ | ✅ | ✅ |
| **ABAC Conditions** | ❌ | ❌ | ✅ |
| **Context-Aware Roles** | ❌ | ❌ | ✅ |
| **Redis Caching** | ❌ | ❌ | ✅ |
| **Complexity** | Low | Medium | High |
| **Setup Time** | 15 min | 30 min | 45 min |
| **Best For** | Simple apps | Enterprises | Complex systems |

---

## API Endpoints Comparison

### SimpleRBAC Endpoints
```
POST   /register              # Register new user
POST   /login                 # Login
GET    /me                    # Current user
GET    /posts                 # List posts (public)
POST   /posts                 # Create post
GET    /posts/{id}            # Get post
PUT    /posts/{id}            # Update post
DELETE /posts/{id}            # Delete post
POST   /admin/users/{id}/role # Assign role
```

### EnterpriseRBAC Endpoints
```
POST   /register                     # Register new user
POST   /login                        # Login
GET    /me                           # Current user + entities
GET    /entities                     # List entities
POST   /entities                     # Create entity
GET    /entities/{id}                # Get entity
GET    /entities/{id}/hierarchy      # Get hierarchy
POST   /entities/{id}/members        # Add member
GET    /entities/{id}/members        # List members
POST   /entities/{id}/projects       # Create project
GET    /entities/{id}/projects       # List projects
```

---

## Common Patterns

### Pattern 1: Protect an Endpoint

```python
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

# Require authentication
@app.get("/protected")
async def protected_route(ctx = Depends(deps.require_auth())):
    user = ctx.metadata.get("user")
    return {"message": f"Hello, {user.username}!"}
```

### Pattern 2: Check Permission

```python
# Require specific permission
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx = Depends(deps.require_permission("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"success": True}
```

### Pattern 3: Optional Authentication

```python
# Public endpoint with optional auth
@app.get("/posts")
async def list_posts(ctx = Depends(deps.optional_auth())):
    if ctx:
        # Authenticated - show all posts
        return await get_all_posts()
    else:
        # Public - show only published
        return await get_published_posts()
```

### Pattern 4: Entity-Scoped Permission (EnterpriseRBAC)

```python
# Check permission in specific entity
@app.put("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    ctx = Depends(deps.require_auth())
):
    # Check if user can update this entity
    has_perm = await auth.permission_service.check_permission(
        user_id=ctx.user_id,
        permission="entity:update",
        entity_id=entity_id,
    )
    if not has_perm[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    # Update entity...
```

---

## Development Tips

### Tip 1: Use API Documentation

All examples include OpenAPI/Swagger documentation:
- **SimpleRBAC**: http://localhost:8000/docs
- **EnterpriseRBAC**: http://localhost:8001/docs

### Tip 2: Check Logs

Enable debug logging to see permission checks:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Tip 3: Test Permissions

Use curl or httpie to test different user roles:

```bash
# Login as different users
TOKEN_ADMIN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"pass"}' \
  | jq -r '.access_token')

TOKEN_USER=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass"}' \
  | jq -r '.access_token')

# Test with different tokens
curl -H "Authorization: Bearer $TOKEN_ADMIN" http://localhost:8000/admin/users
curl -H "Authorization: Bearer $TOKEN_USER" http://localhost:8000/admin/users  # Should fail
```

### Tip 4: Use Docker Compose

Create a `docker-compose.yml` for your example:

```yaml
version: '3.8'
services:
  mongodb:
    image: mongo:latest
    ports:
      - "27017:27017"

  redis:
    image: redis:latest
    ports:
      - "6379:6379"

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URL=mongodb://mongodb:27017
      - SECRET_KEY=your-secret-key
    depends_on:
      - mongodb
```

---

## Troubleshooting

### MongoDB Connection Failed

```bash
# Check if MongoDB is running
docker ps | grep mongo

# Start MongoDB
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### Permission Denied Errors

```bash
# Check user's roles
curl -X GET http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN"

# Check role permissions
curl -X GET http://localhost:8000/admin/roles \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Token Expired

```bash
# Tokens expire after 60 minutes by default
# Login again to get a new token
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'
```

---

## Next Steps

1. **Run the examples**: Start with SimpleRBAC
2. **Read the documentation**: Check each example's README
3. **Modify the examples**: Add your own endpoints
4. **Build your app**: Use examples as starting point
5. **Read the guides**: Check [docs/](../docs/)

---

## Contributing

Found a bug in an example? Have a suggestion?

- **Issues**: [GitHub Issues](https://github.com/outlabs/outlabs-auth/issues)
- **Discussions**: [GitHub Discussions](https://github.com/outlabs/outlabs-auth/discussions)
- **Pull Requests**: Welcome!

---

## License

MIT License - see [LICENSE](../LICENSE) file for details

---

**Built with ❤️ by Outlabs**
