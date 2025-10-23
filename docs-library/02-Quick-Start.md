# Quick Start Guide

**Tags**: #getting-started #quick-start #tutorial

Get OutlabsAuth running in **5 minutes** with this quick start guide.

---

## Prerequisites

- Python 3.12+
- MongoDB (local or cloud)
- FastAPI project (or create new one)

---

## Installation

```bash
# Install OutlabsAuth
pip install outlabs-auth

# Optional: OAuth support
pip install outlabs-auth[oauth]

# Optional: Redis caching
pip install outlabs-auth[redis]

# Optional: All features
pip install outlabs-auth[all]
```

---

## Option 1: SimpleRBAC (Flat Permissions)

Perfect for most applications. No hierarchical structure, just users → roles → permissions.

### Step 1: Create FastAPI App

```python
# main.py
from fastapi import FastAPI, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC

# FastAPI app
app = FastAPI(title="My App with Auth")

# MongoDB connection
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["myapp"]

# Initialize SimpleRBAC
auth = SimpleRBAC(database=db)

# Initialize database (creates indexes, etc.)
@app.on_event("startup")
async def startup():
    await auth.initialize()
```

### Step 2: Add Authentication Routes

```python
from outlabs_auth.routers import get_auth_router, get_users_router

# Add pre-built authentication routes
app.include_router(
    get_auth_router(auth),
    prefix="/auth",
    tags=["auth"]
)

# Add user management routes
app.include_router(
    get_users_router(auth),
    prefix="/users",
    tags=["users"]
)
```

**That's it!** You now have:
- `POST /auth/register` - User registration
- `POST /auth/login` - Login (returns JWT tokens)
- `POST /auth/refresh` - Refresh access token
- `POST /auth/forgot-password` - Password reset request
- `POST /auth/reset-password` - Reset password
- `GET /users/me` - Get current user
- `PATCH /users/me` - Update profile
- `POST /users/me/change-password` - Change password

### Step 3: Protect Your Routes

```python
# Require authentication
@app.get("/protected")
async def protected_route(ctx = Depends(auth.deps.require_auth())):
    user_id = ctx["user_id"]
    return {"message": f"Hello user {user_id}!"}

# Require specific permission
@app.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    ctx = Depends(auth.deps.require_permission("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"status": "deleted"}

# Require specific role
@app.get("/admin/dashboard")
async def admin_dashboard(
    ctx = Depends(auth.deps.require_role("admin"))
):
    return {"message": "Welcome, admin!"}
```

### Step 4: Run Your App

```bash
uvicorn main:app --reload
```

Visit http://localhost:8000/docs to see your interactive API documentation!

---

## Option 2: EnterpriseRBAC (Hierarchical Permissions)

For applications with organizational hierarchy (company → departments → teams).

### Step 1: Create FastAPI App

```python
# main.py
from fastapi import FastAPI, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import EnterpriseRBAC

# FastAPI app
app = FastAPI(title="Enterprise App with Hierarchical Auth")

# MongoDB connection
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["enterprise_app"]

# Initialize EnterpriseRBAC
auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True,  # Optional: roles adapt by entity type
    enable_abac=True,  # Optional: attribute-based access control
    enable_caching=True,  # Optional: Redis caching
    redis_url="redis://localhost:6379"  # If caching enabled
)

# Initialize database
@app.on_event("startup")
async def startup():
    await auth.initialize()
```

### Step 2: Create Organizational Structure

```python
# Create root entity (company)
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_type="company",
    is_structural=True
)

# Create departments
engineering = await auth.entity_service.create_entity(
    name="Engineering",
    entity_type="department",
    parent_id=company.id,
    is_structural=True
)

sales = await auth.entity_service.create_entity(
    name="Sales",
    entity_type="department",
    parent_id=company.id,
    is_structural=True
)

# Create teams (access groups)
backend_team = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_type="team",
    parent_id=engineering.id,
    is_structural=False  # ACCESS_GROUP
)
```

### Step 3: Add Users and Assign Roles

```python
# Register user
user = await auth.user_service.create_user(
    email="john@acme.com",
    password="secure_password",
    is_verified=True
)

# Add user to backend team with "developer" role
await auth.entity_service.add_member(
    entity_id=backend_team.id,
    user_id=user.id,
    role_name="developer"
)

# Grant tree permission at Engineering level
# This gives access to ALL projects in Engineering and its children!
await auth.permission_service.grant_permission(
    user_id=user.id,
    entity_id=engineering.id,
    permission="project:read_tree"
)
```

### Step 4: Check Permissions in Routes

```python
# Check permission in specific entity context
@app.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:read",
        entity_id_param="project_id"  # Check in project's entity context
    ))
):
    project = await get_project_from_db(project_id)
    return project

# Tree permission: Check access to entire subtree
@app.get("/departments/{dept_id}/all-projects")
async def get_all_dept_projects(
    dept_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:read_tree",
        entity_id=dept_id
    ))
):
    # User can see ALL projects under this department!
    projects = await get_department_projects(dept_id)
    return projects
```

---

## Test Your Setup

### 1. Register a User

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### 3. Access Protected Route

```bash
curl -X GET "http://localhost:8000/protected" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Add OAuth Login (Optional)

Add Google login in 2 lines:

```python
from outlabs_auth.oauth.providers import get_google_client
from outlabs_auth.routers import get_oauth_router

# Configure Google OAuth
google = get_google_client(
    client_id="your-id.apps.googleusercontent.com",
    client_secret="your-secret"
)

# Add OAuth routes
app.include_router(
    get_oauth_router(
        google,
        auth,
        state_secret="different-secret-from-jwt",
        associate_by_email=True,  # Link to existing users by email
        is_verified_by_default=True  # Trust Google's email verification
    ),
    prefix="/auth/google",
    tags=["auth"]
)
```

**Usage**:
1. Frontend redirects to `GET /auth/google/authorize`
2. User authenticates with Google
3. Google redirects to `GET /auth/google/callback`
4. Backend returns JWT tokens

See [[31-OAuth-Setup|OAuth Setup Guide]] for detailed configuration.

---

## Add API Keys (Optional)

Let users create API keys for programmatic access:

```python
from outlabs_auth.routers import get_api_keys_router

app.include_router(
    get_api_keys_router(auth),
    prefix="/api-keys",
    tags=["api-keys"]
)
```

**Routes**:
- `POST /api-keys` - Create API key (returns full key ONCE!)
- `GET /api-keys` - List user's API keys
- `DELETE /api-keys/{key_id}` - Revoke API key
- `POST /api-keys/{key_id}/rotate` - Rotate API key

**Usage**:
```bash
# Create API key
curl -X POST "http://localhost:8000/api-keys" \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production API Key"}'

# Use API key
curl -X GET "http://localhost:8000/protected" \
  -H "X-API-Key: ola_1234567890abcdef..."
```

---

## Next Steps

You now have a working authentication system! Here's what to explore next:

### For SimpleRBAC Users
1. [[41-SimpleRBAC|SimpleRBAC Full Guide]] - Deep dive into features
2. [[43-Permissions-System|Permissions System]] - How permissions work
3. [[130-Hooks-Overview|Lifecycle Hooks]] - Add custom business logic
4. [[150-Tutorial-Simple-App|Full Tutorial]] - Build complete app

### For EnterpriseRBAC Users
1. [[42-EnterpriseRBAC|EnterpriseRBAC Full Guide]] - Deep dive into features
2. [[50-Entity-System|Entity System]] - Organizational hierarchy
3. [[44-Tree-Permissions|Tree Permissions]] - Hierarchical access control
4. [[151-Tutorial-Enterprise-App|Full Tutorial]] - Build enterprise app

### For OAuth Integration
1. [[30-OAuth-Overview|OAuth Overview]] - Understanding OAuth
2. [[31-OAuth-Setup|OAuth Setup]] - Configure providers
3. [[152-Tutorial-OAuth-Integration|OAuth Tutorial]] - Full integration guide

### Best Practices
1. [[110-Security-Best-Practices|Security Best Practices]] - Secure your app
2. [[111-Performance-Optimization|Performance Tips]] - Optimize for production
3. [[114-Deployment-Guide|Deployment Guide]] - Deploy to production

---

## Common Issues

### MongoDB Connection Error
```
pymongo.errors.ServerSelectionTimeoutError
```
**Solution**: Make sure MongoDB is running:
```bash
# Start MongoDB with Docker
docker run -d -p 27017:27017 mongo:latest
```

### Import Error
```
ModuleNotFoundError: No module named 'outlabs_auth'
```
**Solution**: Install the package:
```bash
pip install outlabs-auth
```

### OAuth "Client Not Found"
**Solution**: Make sure to install OAuth dependencies:
```bash
pip install outlabs-auth[oauth]
```

See [[262-Troubleshooting|Troubleshooting Guide]] for more help.

---

**Previous**: [[01-Introduction|← Introduction]]
**Next**: [[03-Installation|Installation Guide →]]
