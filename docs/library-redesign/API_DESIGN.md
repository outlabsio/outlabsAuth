# OutlabsAuth Library - API Design & Developer Experience

**Version**: 1.1
**Date**: 2025-01-14
**Status**: Design Phase

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [SimpleRBAC Examples](#simplerbac-examples)
4. [EnterpriseRBAC Examples](#enterpriserbac-examples)
   - [Basic Hierarchy](#basic-hierarchy-examples)
   - [Optional Features](#optional-features-examples)
5. [FastAPI Integration Patterns](#fastapi-integration-patterns)
6. [Configuration](#configuration)
7. [Testing Your App](#testing-your-app)

---

## Installation

```bash
# Install from PyPI (when published)
pip install outlabs-auth

# Install with optional dependencies
pip install outlabs-auth[redis]  # For caching support
pip install outlabs-auth[full]   # All optional dependencies

# Install from source (development)
git clone https://github.com/outlabs/outlabs-auth.git
cd outlabs-auth
pip install -e .
```

---

## Quick Start

### 5-Minute Quick Start (SimpleRBAC)

```python
# app.py
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from motor.motor_asyncio import AsyncIOMotorClient

# Initialize FastAPI
app = FastAPI()

# Initialize database
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
database = mongo_client["myapp"]

# Initialize auth
auth = SimpleRBAC(database=database)

# Initialize database collections
@app.on_event("startup")
async def startup():
    await auth.initialize()

# Public endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to my app"}

# Protected endpoint - requires authentication
@app.get("/users/me")
async def get_current_user(user=Depends(auth.get_current_user)):
    return {
        "email": user.email,
        "status": user.status,
        "profile": user.profile
    }

# Protected endpoint - requires permission
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user=Depends(auth.require_permission("user:delete"))
):
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}

# Authentication endpoints
from outlabs_auth.schemas import LoginRequest, RegisterRequest

@app.post("/auth/register")
async def register(data: RegisterRequest):
    user = await auth.user_service.create_user(
        email=data.email,
        password=data.password
    )
    return {"message": "User created", "user_id": str(user.id)}

@app.post("/auth/login")
async def login(data: LoginRequest):
    tokens = await auth.auth_service.login(
        email=data.email,
        password=data.password
    )
    return tokens

# Run with: uvicorn app:app --reload
```

That's it! You now have:
- User registration
- Login with JWT tokens
- Protected routes
- Permission checks

---

## SimpleRBAC Examples

### Example 1: Basic User Management

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db)

# Create a user
user = await auth.user_service.create_user(
    email="john@example.com",
    password="SecurePass123!",
    first_name="John",
    last_name="Doe"
)

# Create roles
admin_role = await auth.role_service.create_role(
    name="admin",
    display_name="Administrator",
    permissions=[
        "user:read", "user:create", "user:update", "user:delete",
        "role:read", "role:create", "role:update", "role:delete"
    ]
)

viewer_role = await auth.role_service.create_role(
    name="viewer",
    display_name="Viewer",
    permissions=["user:read", "role:read"]
)

# Assign role to user
await auth.user_service.assign_role(user.id, admin_role.id)

# Check permission
has_permission = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="user:delete"
)
# Returns: True (user has admin role)
```

### Example 2: Custom Permissions

```python
# Define custom permissions for your domain
CUSTOM_PERMISSIONS = [
    "invoice:create",
    "invoice:approve",
    "invoice:pay",
    "report:view",
    "report:export",
]

# Create role with custom permissions
accountant_role = await auth.role_service.create_role(
    name="accountant",
    display_name="Accountant",
    permissions=[
        "invoice:create",
        "invoice:approve",
        "report:view",
        "report:export"
    ]
)

# Use in routes
@app.post("/invoices")
async def create_invoice(
    data: InvoiceCreate,
    user=Depends(auth.require_permission("invoice:create"))
):
    # Only users with invoice:create permission can access
    invoice = await invoice_service.create(data)
    return invoice

@app.post("/invoices/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: str,
    user=Depends(auth.require_permission("invoice:approve"))
):
    # Separate permission for approval
    invoice = await invoice_service.approve(invoice_id, user.id)
    return invoice
```

### Example 3: Multiple Permission Checks

```python
from outlabs_auth.dependencies import require_any_permission, require_all_permissions

# Require ANY of the permissions
@app.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    user=Depends(require_any_permission(auth, ["report:view", "report:export"]))
):
    # User needs report:view OR report:export
    return await report_service.get(report_id)

# Require ALL permissions
@app.delete("/users/{user_id}/complete")
async def complete_delete_user(
    user_id: str,
    user=Depends(require_all_permissions(auth, ["user:delete", "user:purge"]))
):
    # User needs BOTH user:delete AND user:purge
    await user_service.complete_deletion(user_id)
    return {"message": "User completely removed"}
```

---

## EnterpriseRBAC Examples

### Basic Hierarchy Examples

These examples show EnterpriseRBAC's core features (entity hierarchy and tree permissions), which are always included.

#### Example 1: Creating Entity Hierarchy

```python
from outlabs_auth import EnterpriseRBAC

# Basic setup - entity hierarchy is always included
auth = EnterpriseRBAC(database=db)

# Create organization
company = await auth.entity_service.create_entity(
    name="acme_corp",
    display_name="ACME Corporation",
    entity_class="structural",
    entity_type="company"
)

# Create departments
engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class="structural",
    entity_type="department",
    parent_id=company.id
)

sales = await auth.entity_service.create_entity(
    name="sales",
    display_name="Sales Department",
    entity_class="structural",
    entity_type="department",
    parent_id=company.id
)

# Create teams within department
backend_team = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class="structural",
    entity_type="team",
    parent_id=engineering.id
)

# Create access groups (cross-cutting)
admins_group = await auth.entity_service.create_entity(
    name="company_admins",
    display_name="Company Administrators",
    entity_class="access_group",
    entity_type="admin_group",
    parent_id=company.id
)
```

### Example 2: Entity Memberships with Roles

```python
# Create role that can be assigned at department level
dept_manager_role = await auth.role_service.create_role(
    name="department_manager",
    display_name="Department Manager",
    permissions=[
        "entity:read",
        "entity:update",
        "entity:read_tree",      # Can read all sub-entities
        "entity:create_tree",    # Can create sub-entities
        "user:read",
        "user:read_tree",        # Can see all users in sub-entities
        "user:manage_tree"       # Can manage users in sub-entities
    ],
    assignable_at_types=["department"]
)

# Assign user to department with role
await auth.membership_service.add_member(
    entity_id=engineering.id,
    user_id=user.id,
    role_ids=[dept_manager_role.id]
)

# User can now:
# - Read/update engineering department
# - Read all teams under engineering
# - Create new teams under engineering
# - Manage all users in engineering and its teams
```

### Example 3: Tree Permissions in Routes

```python
# Permission required in specific entity
@app.get("/entities/{entity_id}/details")
async def get_entity_details(
    entity_id: str,
    user=Depends(auth.require_entity_permission("entity:read", "entity_id"))
):
    # User must have entity:read in THIS specific entity
    entity = await auth.entity_service.get(entity_id)
    return entity

# Tree permission - can access descendants
@app.post("/entities/{parent_id}/sub-entities")
async def create_sub_entity(
    parent_id: str,
    data: EntityCreate,
    user=Depends(auth.require_tree_permission("entity:create", "parent_id"))
):
    # User must have entity:create_tree in parent_id (or any ancestor)
    entity = await auth.entity_service.create_entity(
        parent_id=parent_id,
        **data.dict()
    )
    return entity

# Member management with tree permission
@app.post("/entities/{entity_id}/members")
async def add_member(
    entity_id: str,
    data: MemberAdd,
    user=Depends(auth.require_tree_permission("user:manage", "entity_id"))
):
    # User must have user:manage_tree in entity_id or any ancestor
    await auth.membership_service.add_member(
        entity_id=entity_id,
        user_id=data.user_id,
        role_ids=data.role_ids
    )
    return {"message": "Member added"}
```

### Example 4: Get User's Accessible Entities

```python
@app.get("/my-entities")
async def get_my_entities(user=Depends(auth.get_current_user)):
    # Get all entities where user has membership
    entities = await auth.membership_service.get_user_entities(user.id)
    return entities

@app.get("/my-entities/{entity_type}")
async def get_my_entities_by_type(
    entity_type: str,
    user=Depends(auth.get_current_user)
):
    # Get entities of specific type (e.g., "department", "team")
    entities = await auth.membership_service.get_user_entities(
        user.id,
        entity_type=entity_type
    )
    return entities

@app.get("/entities-with-permission/{permission}")
async def get_entities_with_permission(
    permission: str,
    user=Depends(auth.get_current_user)
):
    # Get all entities where user has specific permission
    entity_ids = await auth.permission_service.get_user_entities_with_permission(
        user_id=user.id,
        permission=permission
    )
    return {"entity_ids": entity_ids}
```

---

### Optional Features Examples

These examples show EnterpriseRBAC's optional features (context-aware roles, ABAC, caching, multi-tenant, audit logging), which can be enabled via feature flags.

#### Example 1: Context-Aware Roles

```python
from outlabs_auth import EnterpriseRBAC

# Enable context-aware roles feature
auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True  # Opt-in feature
)

# Create context-aware role
regional_manager = await auth.role_service.create_role(
    name="regional_manager",
    display_name="Regional Manager",

    # Default permissions (fallback)
    permissions=["entity:read", "user:read"],

    # Context-specific permissions by entity type
    entity_type_permissions={
        "region": [
            # Full management at region level
            "entity:manage",
            "entity:manage_tree",
            "user:manage_tree",
            "budget:approve",
            "report:view_all"
        ],
        "office": [
            # Read-only at office level
            "entity:read",
            "entity:read_tree",
            "user:read",
            "report:view"
        ],
        "team": [
            # Advisory role at team level
            "entity:read",
            "user:read",
            "report:view"
        ]
    },

    assignable_at_types=["region", "office", "team"]
)

# Assign role at region level
await auth.membership_service.add_member(
    entity_id=west_region.id,
    user_id=user.id,
    role_ids=[regional_manager.id]
)

# Same user, different permissions based on context
# At region level: full management
# At office level: read-only
# At team level: view only
```

#### Example 2: ABAC Conditions

```python
from outlabs_auth import EnterpriseRBAC

# Enable ABAC feature
auth = EnterpriseRBAC(
    database=db,
    enable_abac=True  # Opt-in feature
)

# Create permission with conditions
invoice_approval = await auth.permission_service.create_permission(
    name="invoice:approve",
    display_name="Approve Invoices",
    description="Allows approving invoices",

    # ABAC conditions
    conditions=[
        {
            "attribute": "resource.amount",
            "operator": "LESS_THAN_OR_EQUAL",
            "value": 50000  # Can only approve invoices <= $50k
        },
        {
            "attribute": "resource.status",
            "operator": "EQUALS",
            "value": "pending_approval"
        },
        {
            "attribute": "resource.department",
            "operator": "EQUALS",
            "value": {"ref": "user.department"}  # Same department
        }
    ]
)

# Create role with conditional permission
manager_role = await auth.role_service.create_role(
    name="manager",
    display_name="Manager",
    permissions=["invoice:approve"]  # Has permission, but conditions apply
)

# Check permission with context
result = await auth.permission_service.check_permission_with_context(
    user_id=user.id,
    permission="invoice:approve",
    entity_id=entity.id,
    resource_attributes={
        "amount": 35000,           # ✓ Under limit
        "status": "pending_approval",  # ✓ Correct status
        "department": user.profile.department  # ✓ Same department
    }
)

if result.allowed:
    # User can approve this specific invoice
    await approve_invoice()
else:
    # Permission denied, result.reason explains why
    raise HTTPException(403, result.reason)
```

#### Example 3: Advanced Permission Checking with ABAC

```python
from outlabs_auth.schemas import PolicyResult

# Same ABAC-enabled setup from Example 2
# auth = EnterpriseRBAC(database=db, enable_abac=True)

@app.post("/invoices/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: str,
    user=Depends(auth.get_current_user)
):
    # Get invoice details
    invoice = await invoice_service.get(invoice_id)

    # Check permission with full context
    result: PolicyResult = await auth.permission_service.check_permission_with_context(
        user_id=user.id,
        permission="invoice:approve",
        entity_id=invoice.entity_id,
        resource_attributes={
            "amount": invoice.amount,
            "status": invoice.status,
            "department": invoice.department,
            "created_by": invoice.created_by
        }
    )

    if not result.allowed:
        # Return detailed reason
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Permission denied",
                "reason": result.reason,
                "evaluation": result.details
            }
        )

    # Approve invoice
    approved = await invoice_service.approve(invoice_id, user.id)
    return approved
```

#### Example 4: Caching Performance

```python
from outlabs_auth import EnterpriseRBAC
import time

# Enable caching feature (requires Redis)
auth = EnterpriseRBAC(
    database=db,
    redis_url="redis://localhost:6379",
    enable_caching=True  # Opt-in feature, requires Redis
)

# First call - miss cache, hits database
start = time.time()
has_perm = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="invoice:create",
    entity_id=entity.id
)
first_call = time.time() - start
print(f"First call: {first_call * 1000:.2f}ms")  # ~45ms

# Second call - hits cache
start = time.time()
has_perm = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="invoice:create",
    entity_id=entity.id,
    use_cache=True
)
second_call = time.time() - start
print(f"Second call: {second_call * 1000:.2f}ms")  # ~2ms

# Cache invalidation
await auth.permission_service.invalidate_user_cache(user.id)

# Manual cache control
result = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="invoice:create",
    entity_id=entity.id,
    use_cache=False  # Force database check
)
```

---

## FastAPI Integration Patterns

### Pattern 1: Global Auth Instance

```python
# app/core/auth.py
from outlabs_auth import EnterpriseRBAC
from app.core.database import get_database

auth = EnterpriseRBAC(database=get_database())

# app/api/routes/users.py
from app.core.auth import auth

@router.get("/users/me")
async def get_me(user=Depends(auth.get_current_user)):
    return user
```

### Pattern 2: Dependency Injection with FastAPI Depends

```python
# app/core/auth.py
from fastapi import Depends
from outlabs_auth import SimpleRBAC

def get_auth() -> SimpleRBAC:
    """Dependency that provides auth instance"""
    return SimpleRBAC(database=get_database())

# app/api/routes/users.py
from app.core.auth import get_auth

@router.get("/users/me")
async def get_me(
    auth: SimpleRBAC = Depends(get_auth),
    user = Depends(lambda auth=Depends(get_auth): auth.get_current_user)
):
    return user
```

### Pattern 3: Custom Permission Decorator

```python
# app/core/permissions.py
from functools import wraps
from fastapi import HTTPException

def require_permissions(*permissions: str):
    """Decorator for requiring multiple permissions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user, **kwargs):
            for perm in permissions:
                has_perm = await auth.permission_service.check_permission(
                    user.id, perm
                )
                if not has_perm:
                    raise HTTPException(403, f"Missing permission: {perm}")
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

# Usage
@app.delete("/users/{user_id}")
@require_permissions("user:delete", "user:purge")
async def delete_user(user_id: str, user=Depends(auth.get_current_user)):
    await user_service.delete(user_id)
    return {"message": "User deleted"}
```

### Pattern 4: Entity Context Middleware

```python
# app/middleware/entity_context.py
from starlette.middleware.base import BaseHTTPMiddleware

class EntityContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Extract entity_id from path, query, or header
        entity_id = request.path_params.get("entity_id")
        if not entity_id:
            entity_id = request.query_params.get("entity_id")

        # Store in request state
        request.state.entity_id = entity_id

        response = await call_next(request)
        return response

# Add to app
app.add_middleware(EntityContextMiddleware)

# Use in routes
@app.get("/entities/{entity_id}/data")
async def get_entity_data(
    request: Request,
    user=Depends(auth.get_current_user)
):
    entity_id = request.state.entity_id
    # Check permission with entity context
    has_perm = await auth.permission_service.check_permission(
        user.id, "data:read", entity_id
    )
    if not has_perm:
        raise HTTPException(403)
    return {"data": "..."}
```

---

## Configuration

### SimpleRBAC Configuration

```python
from outlabs_auth import SimpleRBAC, SimpleConfig

config = SimpleConfig(
    # JWT settings
    secret_key="your-secret-key-change-in-production",
    algorithm="HS256",
    access_token_expire_minutes=15,
    refresh_token_expire_days=30,

    # Password requirements
    password_min_length=8,
    require_special_char=True,
    require_uppercase=True,
    require_digit=True,

    # Security
    max_login_attempts=5,
    lockout_duration_minutes=30,
)

auth = SimpleRBAC(database=db, config=config)
```

### EnterpriseRBAC Configuration

```python
from outlabs_auth import EnterpriseRBAC, EnterpriseConfig

# Basic configuration (entity hierarchy always enabled)
config = EnterpriseConfig(
    # Inherit all SimpleConfig options
    secret_key="your-secret-key",
    access_token_expire_minutes=15,
    refresh_token_expire_days=30,

    # Entity settings (always enabled)
    max_entity_depth=5,
    allowed_entity_types=["company", "department", "team", "project"],
    allow_access_groups=True,
)

auth = EnterpriseRBAC(database=db, config=config)
```

```python
# Full configuration with all optional features
config = EnterpriseConfig(
    # Inherit all SimpleConfig options
    secret_key="your-secret-key",
    max_entity_depth=5,

    # Optional features (opt-in via feature flags)
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    enable_audit_log=True,
    multi_tenant=True,

    # Caching settings (only used when enable_caching=True)
    redis_url="redis://localhost:6379",
    cache_ttl_seconds=300,  # 5 minutes
)

auth = EnterpriseRBAC(database=db, config=config)
```

### Environment-Based Configuration

```python
# config.py
import os
from outlabs_auth import SimpleConfig

class Settings:
    def __init__(self):
        self.auth_config = SimpleConfig(
            secret_key=os.getenv("SECRET_KEY"),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE", "15")),
            redis_url=os.getenv("REDIS_URL"),
        )

settings = Settings()

# app.py
from config import settings
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db, config=settings.auth_config)
```

---

## Testing Your App

### Test Fixtures

```python
# conftest.py
import pytest
from outlabs_auth import SimpleRBAC

@pytest.fixture
async def auth(mongo_db):
    """Auth instance for testing"""
    auth = SimpleRBAC(database=mongo_db)
    await auth.initialize()
    return auth

@pytest.fixture
async def test_user(auth):
    """Create test user"""
    return await auth.user_service.create_user(
        email="test@example.com",
        password="Test123!@#"
    )

@pytest.fixture
async def admin_user(auth):
    """Create admin user with full permissions"""
    user = await auth.user_service.create_user(
        email="admin@example.com",
        password="Admin123!@#"
    )

    admin_role = await auth.role_service.create_role(
        name="admin",
        permissions=["user:create", "user:delete", "role:manage"]
    )

    await auth.user_service.assign_role(user.id, admin_role.id)
    return user

@pytest.fixture
async def auth_headers(auth, test_user):
    """Get auth headers for test user"""
    tokens = await auth.auth_service.login(
        email="test@example.com",
        password="Test123!@#"
    )
    return {"Authorization": f"Bearer {tokens.access_token}"}
```

### Unit Tests

```python
# test_auth.py
import pytest

@pytest.mark.asyncio
async def test_user_can_login(auth, test_user):
    tokens = await auth.auth_service.login(
        email="test@example.com",
        password="Test123!@#"
    )
    assert tokens.access_token
    assert tokens.refresh_token

@pytest.mark.asyncio
async def test_user_with_permission_can_access(auth, admin_user):
    has_perm = await auth.permission_service.check_permission(
        user_id=admin_user.id,
        permission="user:delete"
    )
    assert has_perm is True

@pytest.mark.asyncio
async def test_user_without_permission_cannot_access(auth, test_user):
    has_perm = await auth.permission_service.check_permission(
        user_id=test_user.id,
        permission="user:delete"
    )
    assert has_perm is False
```

### Integration Tests

```python
# test_api.py
from fastapi.testclient import TestClient

def test_protected_route_requires_auth(client: TestClient):
    response = client.get("/users/me")
    assert response.status_code == 401

def test_protected_route_with_valid_token(client: TestClient, auth_headers):
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

def test_permission_required_route(client: TestClient, auth_headers):
    # Test user doesn't have permission
    response = client.delete("/users/other-user-id", headers=auth_headers)
    assert response.status_code == 403

def test_admin_can_delete_user(client: TestClient, admin_headers):
    response = client.delete("/users/user-id", headers=admin_headers)
    assert response.status_code == 200
```

---

## Best Practices

### 1. Always Use Environment Variables for Secrets

```python
# ❌ Bad
config = SimpleConfig(secret_key="hardcoded-secret")

# ✅ Good
config = SimpleConfig(secret_key=os.getenv("SECRET_KEY"))
```

### 2. Initialize Database on Startup

```python
@app.on_event("startup")
async def startup():
    await auth.initialize()
    # Creates indexes and initializes collections
```

### 3. Use Specific Permissions

```python
# ❌ Avoid overly broad permissions
permissions = ["admin:all"]

# ✅ Use specific permissions
permissions = [
    "user:read",
    "user:create",
    "user:update",
    "role:manage"
]
```

### 4. Implement Proper Error Handling

```python
from fastapi import HTTPException

@app.post("/users")
async def create_user(data: UserCreate):
    try:
        user = await auth.user_service.create_user(
            email=data.email,
            password=data.password
        )
        return user
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"User creation failed: {e}")
        raise HTTPException(500, "Internal server error")
```

### 5. Cache Permission Checks When Appropriate

```python
# For frequently checked permissions, use caching
result = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="resource:action",
    use_cache=True  # Default in FullFeatured
)

# For critical security checks, skip cache
result = await auth.permission_service.check_permission(
    user_id=user.id,
    permission="admin:delete_everything",
    use_cache=False  # Force fresh check
)
```

---

## Next Steps

- Review [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) for development phases
- Check [COMPARISON_MATRIX.md](COMPARISON_MATRIX.md) to choose the right preset
- See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if migrating from centralized API

---

**Last Updated**: 2025-01-14
**Next Review**: After Phase 1 implementation
