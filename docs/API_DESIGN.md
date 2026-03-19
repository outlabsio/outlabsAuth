# OutlabsAuth Library - API Design & Developer Experience

**Version**: 1.4
**Date**: 2025-01-14
**Status**: Design Phase

**Architecture Changes (v1.4)**:
- **Unified AuthDeps**: Single dependency class replaces SimpleDeps, MultiSourceDeps, etc. (DD-035)
- **JWT Service Tokens**: Zero-DB authentication for internal microservices (DD-034)
- **Redis Counters**: API key usage tracking with 99%+ reduction in DB writes (DD-033)
- **Temporary Locks**: API keys locked for 30 min after 10 failures (no permanent revocation) (DD-028)
- **12-Char Prefixes**: API key prefixes (12 characters for identification) (DD-028)
- **SHA-256 Hashing**: Fast hashing appropriate for high-entropy secrets (DD-028 corrected)

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [SimpleRBAC Examples](#simplerbac-examples)
4. [EnterpriseRBAC Examples](#enterpriserbac-examples)
   - [Basic Hierarchy](#basic-hierarchy-examples)
   - [Optional Features](#optional-features-examples)
5. **[API Key Authentication](#api-key-authentication)** - Core v1.0 feature
6. **[JWT Service Tokens](#jwt-service-tokens)** ← NEW (v1.4 - DD-034)
7. **[Multi-Source Authentication](#multi-source-authentication)** - Updated for AuthDeps
8. [FastAPI Integration Patterns](#fastapi-integration-patterns)
9. [Configuration](#configuration)
10. [Testing Your App](#testing-your-app)

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

These examples show EnterpriseRBAC's optional features (context-aware roles, ABAC, caching, audit logging), which can be enabled via feature flags.

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

## API Key Authentication

API keys enable service-to-service authentication for automated systems, CI/CD pipelines, and backend services. They are **core v1.0 features** (not optional extensions).

### Example 1: Creating API Keys

```python
from outlabs_auth import SimpleRBAC
from datetime import datetime, timedelta

auth = SimpleRBAC(database=db)

# Create user who will own the API key
service_user = await auth.user_service.create_user(
    email="service@example.com",
    password="service-password",
    name="Service Account"
)

# Create API key for production service
raw_key, api_key_model = await auth.api_key_service.create_api_key(
    name="Production Service",
    owner_id=service_user.id,
    scopes=["user:read", "entity:read"],
    ip_whitelist=["10.0.1.0/24", "192.168.1.100"],  # Optional IP whitelist
    rate_limit_per_minute=60,
    expires_in_days=90,  # 90-day expiry
    prefix_type="sk_live"  # sk_live_ prefix
)

# CRITICAL: raw_key is only shown ONCE - store securely!
print(f"API Key: {raw_key}")  # sk_live_abc123...
print(f"Store this key securely - it won't be shown again!")

# Key is now hashed with SHA-256 in database (fast for high-entropy secrets)
# Only the prefix (first 12 chars) is stored in plaintext for identification
```

### Example 2: API Keys for Different Environments

```python
# Production key (most restrictive)
prod_key, prod_model = await auth.api_key_service.create_api_key(
    name="Production API",
    owner_id=user.id,
    scopes=["user:read", "entity:read"],
    ip_whitelist=["10.0.1.0/24"],
    rate_limit_per_minute=60,
    prefix_type="sk_live"
)

# Test key (more permissive)
test_key, test_model = await auth.api_key_service.create_api_key(
    name="Test API",
    owner_id=user.id,
    scopes=["user:read", "user:create", "entity:read"],
    ip_whitelist=None,  # No IP restrictions for testing
    rate_limit_per_minute=120,
    prefix_type="sk_test"
)

# Note: Use different prefixes to distinguish environments
# Common prefixes: sk_live (production), sk_test (testing)
```

### Example 3: Using API Keys in Routes

```python
from fastapi import FastAPI, Header, HTTPException
from typing import Optional

app = FastAPI()

@app.get("/api/users")
async def list_users(x_api_key: Optional[str] = Header(None)):
    """Public API endpoint authenticated with API key"""
    if not x_api_key:
        raise HTTPException(401, "API key required")

    # Authenticate API key
    try:
        api_key_model = await auth.api_key_service.authenticate_api_key(x_api_key)
    except Exception:
        raise HTTPException(401, "Invalid API key")

    # Check permission
    if "user:read" not in api_key_model.permissions:
        raise HTTPException(403, "API key lacks user:read permission")

    # Check IP whitelist (if configured)
    client_ip = request.client.host
    if not await auth.api_key_service.check_ip_whitelist(api_key_model, client_ip):
        raise HTTPException(403, "IP not whitelisted")

    # Check rate limit
    try:
        await auth.api_key_service.check_rate_limit(api_key_model)
    except RateLimitExceededException:
        raise HTTPException(429, "Rate limit exceeded")

    # API key is valid - return users
    users = await auth.user_service.list_users()
    return users
```

### Example 4: API Key Management Endpoints

```python
from outlabs_auth.schemas import CreateAPIKeyRequest, RotateAPIKeyRequest

# Create API key endpoint
@app.post("/api-keys")
async def create_api_key(
    data: CreateAPIKeyRequest,
    user=Depends(auth.require_permission("api_key:create"))
):
    """Create new API key (returns raw key once)"""
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name=data.name,
        permissions=data.permissions,
        environment=data.environment,
        allowed_ips=data.allowed_ips,
        rate_limit_per_minute=data.rate_limit_per_minute,
        expires_at=data.expires_at,
        created_by=user.id
    )

    return {
        "raw_key": raw_key,  # ONLY returned once!
        "key_prefix": api_key_model.key_prefix,
        "message": "Store this key securely - it won't be shown again"
    }

# List API keys endpoint
@app.get("/api-keys")
async def list_api_keys(user=Depends(auth.require_permission("api_key:read"))):
    """List all API keys (without raw keys)"""
    keys = await auth.api_key_service.list_api_keys()
    return {
        "keys": [
            {
                "id": str(key.id),
                "name": key.name,
                "key_prefix": key.key_prefix,  # First 8 chars only
                "environment": key.environment,
                "is_active": key.is_active,
                "usage_count": key.usage_count,
                "created_at": key.created_at,
                "expires_at": key.expires_at
            }
            for key in keys
        ]
    }

# Rotate API key endpoint
@app.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(
    key_id: str,
    user=Depends(auth.require_permission("api_key:rotate"))
):
    """Rotate API key (creates new, schedules old for revocation)"""
    new_raw_key, new_api_key = await auth.api_key_service.rotate_api_key(key_id)

    return {
        "raw_key": new_raw_key,  # ONLY returned once!
        "key_prefix": new_api_key.key_prefix,
        "message": "Old key will be revoked in 24 hours. Update your services with the new key.",
        "grace_period_hours": 24
    }

# Revoke API key endpoint
@app.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    user=Depends(auth.require_permission("api_key:revoke"))
):
    """Immediately revoke API key"""
    await auth.api_key_service.revoke_api_key(
        key_id=key_id,
        reason="Revoked by administrator"
    )
    return {"message": "API key revoked"}
```

### Example 5: Entity-Scoped API Keys (EnterpriseRBAC)

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(database=db)

# Create hierarchy
org = await auth.entity_service.create_entity(
    name="acme_corp",
    entity_type="organization",
    entity_class="STRUCTURAL"
)

dept = await auth.entity_service.create_entity(
    name="engineering",
    entity_type="department",
    entity_class="STRUCTURAL",
    parent_entity_id=org.id
)

# Create API key scoped to department
raw_key, api_key = await auth.api_key_service.create_api_key(
    name="Engineering Service",
    permissions=["entity:read", "entity:update", "user:read"],
    environment="production",
    entity_id=dept.id,  # Scoped to engineering department
    inherit_from_tree=True,  # Can access child entities
    created_by=user.id
)

# This API key can only access:
# - The engineering department (entity:read, entity:update)
# - Any teams under engineering (via tree permissions)
# - Users in engineering and its sub-entities

# Use in routes
@app.get("/entities/{entity_id}/data")
async def get_entity_data(
    entity_id: str,
    x_api_key: str = Header(...)
):
    # Authenticate API key
    api_key_model = await auth.api_key_service.authenticate_api_key(x_api_key)

    # Check if API key has access to this entity
    if api_key_model.entity_id:
        # Entity-scoped key - verify access
        has_access = await auth.permission_service.check_entity_access(
            api_key=api_key_model,
            target_entity_id=entity_id,
            permission="entity:read"
        )
        if not has_access:
            raise HTTPException(403, "API key does not have access to this entity")

    # Return data
    return await entity_service.get_data(entity_id)
```

### Example 6: Client-Side API Key Usage

```python
# Python client
import requests

API_KEY = "sk_prod_AbCdEfGh..."
BASE_URL = "https://api.example.com"

# Use API key in header
response = requests.get(
    f"{BASE_URL}/api/users",
    headers={"X-API-Key": API_KEY}
)

if response.status_code == 200:
    users = response.json()
else:
    print(f"Error: {response.status_code}")
```

```javascript
// JavaScript client
const API_KEY = 'sk_prod_AbCdEfGh...';
const BASE_URL = 'https://api.example.com';

// Use API key in header
fetch(`${BASE_URL}/api/users`, {
  headers: {
    'X-API-Key': API_KEY
  }
})
  .then(response => response.json())
  .then(users => console.log(users))
  .catch(error => console.error('Error:', error));
```

```bash
# cURL
curl -X GET https://api.example.com/api/users \
  -H "X-API-Key: sk_prod_AbCdEfGh..."
```

---

## JWT Service Tokens

**NEW in v1.4 (DD-034)**: JWT service tokens provide zero-database authentication for internal microservices with sub-millisecond validation times.

### Why JWT Service Tokens?

- **Performance**: ~0.5ms validation vs ~0.5-1ms for API keys (similar but no DB lookup)
- **Stateless**: Pure JWT validation, no database queries
- **Perfect for**: High-frequency internal service-to-service communication
- **Complements API Keys**: Use API keys for external partners, JWT tokens for internal services

### Example 1: Creating JWT Service Tokens

```python
from outlabs_auth import SimpleRBAC
from datetime import timedelta

auth = SimpleRBAC(database=db)

# Create JWT service token (short-lived, self-contained)
service_token = await auth.service_token_service.create_token(
    service_name="payment_processor",
    permissions=["invoice:read", "invoice:update", "payment:create"],
    expires_in=timedelta(hours=24)  # Short-lived: 1-24 hours recommended
)

print(f"Service Token: {service_token}")
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzZXJ2aWNlX25hbWUiOiJwYXltZW50X...

# Token is a JWT containing:
# - service_name: "payment_processor"
# - permissions: ["invoice:read", "invoice:update", "payment:create"]
# - iat (issued at), exp (expiration)
# - Cryptographically signed (cannot be forged)
```

### Example 2: Service-to-Service Communication with JWT

```python
# Service A (caller) - using JWT service token
import requests

SERVICE_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

response = requests.post(
    "https://service-b.example.com/api/process-payment",
    headers={"X-Service-Token": SERVICE_TOKEN},
    json={"invoice_id": "inv_123", "amount": 1000}
)

# Service B (receiver) - validates JWT (no DB lookup!)
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth=auth)

@app.post("/api/process-payment")
async def process_payment(
    data: dict,
    ctx: AuthContext = deps.require_source(AuthSource.SERVICE)
):
    """
    Fast internal endpoint using JWT service tokens.

    Validation: ~0.5ms (pure JWT validation, no DB)
    vs API keys: ~0.5-1ms (DB lookup + SHA-256 verification)
    """

    # Service name from JWT payload
    service_name = ctx.metadata["service"]
    print(f"Request from service: {service_name}")

    # Permissions from JWT payload (no DB lookup!)
    if not ctx.has_permission("payment:create"):
        raise HTTPException(403, "Service lacks payment:create permission")

    # Process payment
    result = await payment_service.process(data)
    return {"result": result}
```

### Example 3: API Keys vs JWT Service Tokens

```python
# Comparison of authentication methods

# API Keys (external partners, persistent)
# - Use: External integrations, third-party services
# - Storage: MongoDB (hashed with SHA-256)
# - Validation: ~0.5-1ms (DB lookup + hash verification)
# - Lifespan: Long-lived (90-365 days)
# - Rotation: Manual via API
# - Rate Limiting: Per-key limits in Redis
# - Security: SHA-256 hashing (fast for high-entropy), temp locks after 10 failures

api_key = await auth.api_key_service.create_api_key(
    name="Partner API",
    permissions=["invoice:read"],
    environment="production",
    expires_in_days=90
)
# Returns: sk_prod_abc1def2_x3y4z5...


# JWT Service Tokens (internal services, faster, ephemeral)
# - Use: Internal microservices, high-frequency requests
# - Storage: None (stateless JWT)
# - Validation: ~0.5ms (pure cryptographic verification)
# - Lifespan: Short-lived (1-24 hours)
# - Rotation: Automatic (create new token when needed)
# - Rate Limiting: Higher limits (trusted internal services)
# - Security: Cryptographic signatures, short expiration

service_token = await auth.service_token_service.create_token(
    service_name="internal_processor",
    permissions=["invoice:read", "invoice:update"],
    expires_in=timedelta(hours=12)
)
# Returns: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Example 4: Automatic Token Rotation

```python
# Internal service with automatic token rotation

import asyncio
from datetime import timedelta

class ServiceClient:
    """Client for internal service communication with auto-rotation"""

    def __init__(self, auth, service_name: str):
        self.auth = auth
        self.service_name = service_name
        self.token = None
        self.token_expires_at = None

    async def get_token(self) -> str:
        """Get valid token, rotating if needed"""
        if self.token and self.token_expires_at > datetime.utcnow():
            return self.token

        # Token expired or doesn't exist - create new one
        self.token = await self.auth.service_token_service.create_token(
            service_name=self.service_name,
            permissions=["invoice:read", "invoice:update", "payment:create"],
            expires_in=timedelta(hours=12)
        )
        self.token_expires_at = datetime.utcnow() + timedelta(hours=12)

        return self.token

    async def make_request(self, url: str, data: dict):
        """Make authenticated request with auto-rotating token"""
        token = await self.get_token()

        response = await httpx.post(
            url,
            headers={"X-Service-Token": token},
            json=data
        )
        return response

# Usage
client = ServiceClient(auth=auth, service_name="payment_processor")

# Token automatically rotates every 12 hours
await client.make_request("/api/process", {"invoice_id": "inv_123"})
await client.make_request("/api/process", {"invoice_id": "inv_456"})
# ... token seamlessly rotates in background
```

### Example 5: Multi-Environment Service Tokens

```python
# Different tokens for different environments

# Production service token (strict permissions)
prod_token = await auth.service_token_service.create_token(
    service_name="prod_payment_service",
    permissions=["invoice:read", "payment:create"],  # Read-only + create
    environment="production",
    expires_in=timedelta(hours=24)
)

# Staging service token (more permissive)
staging_token = await auth.service_token_service.create_token(
    service_name="staging_payment_service",
    permissions=["invoice:read", "invoice:update", "payment:create", "payment:refund"],
    environment="staging",
    expires_in=timedelta(hours=48)
)

# Development service token (most permissive)
dev_token = await auth.service_token_service.create_token(
    service_name="dev_payment_service",
    permissions=["invoice:*", "payment:*"],  # All permissions
    environment="development",
    expires_in=timedelta(days=7)
)
```

### Example 6: Service Token Health Checks

```python
# Fast health check endpoint using service tokens

@app.get("/health")
async def health_check(
    ctx: AuthContext = deps.require_source(AuthSource.SERVICE)
):
    """
    Health check endpoint for internal monitoring.

    Uses JWT service token validation (~0.5ms).
    Perfect for high-frequency health checks.
    """

    service_name = ctx.metadata["service"]

    return {
        "status": "healthy",
        "service": service_name,
        "timestamp": datetime.utcnow().isoformat(),
        "auth_source": "jwt_service_token"
    }

# Called by monitoring service every 5 seconds
# Validation: ~0.5ms per request (no DB load!)
```

### Best Practices

1. **Short Lifespan**: Keep tokens short-lived (1-24 hours max)
2. **Internal Only**: Never expose service tokens to external clients
3. **Rotate Frequently**: Create new tokens automatically before expiration
4. **Minimal Permissions**: Grant only required permissions per service
5. **Use API Keys for External**: Reserve JWT tokens for internal services only

---

## Multi-Source Authentication

Multi-source authentication allows your API to accept authentication from multiple sources with a priority chain: **Superuser > JWT Service Token > API Key > User > Anonymous**.

**Updated in v1.4**: Now uses unified `AuthDeps` class instead of separate `MultiSourceDeps` class.

### Example 1: Basic Multi-Source Setup

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import MultiSourceDeps
from outlabs_auth.models import AuthContext, AuthSource

auth = SimpleRBAC(database=db)

# Create multi-source dependency factory
deps = MultiSourceDeps(auth=auth)

@app.get("/api/users")
async def list_users(context: AuthContext = Depends(deps.get_context)):
    """
    Accepts authentication from:
    - User JWT (Authorization: Bearer <token>)
    - API Key (X-API-Key: sk_prod_...)
    - Service Token (X-Service-Token: <token>)
    - Superuser Token (X-Superuser-Token: <token>)
    - Anonymous (no auth - if allowed)
    """

    # Check which auth source was used
    if context.source == AuthSource.USER:
        print(f"Authenticated as user: {context.identity}")
    elif context.source == AuthSource.API_KEY:
        print(f"Authenticated with API key: {context.identity}")
    elif context.source == AuthSource.SERVICE:
        print(f"Authenticated as service: {context.identity}")
    elif context.source == AuthSource.SUPERUSER:
        print(f"Authenticated as superuser: {context.identity}")
    elif context.source == AuthSource.ANONYMOUS:
        print("Anonymous access")

    # Check permissions (works across all auth sources)
    if not context.has_permission("user:read"):
        raise HTTPException(403, "Permission denied")

    # Return users
    users = await auth.user_service.list_users()
    return users
```

### Example 2: Auth Source Priority Chain

```python
from outlabs_auth.dependencies import MultiSourceDeps

deps = MultiSourceDeps(auth=auth)

@app.get("/api/data")
async def get_data(context: AuthContext = Depends(deps.get_context)):
    """
    Priority chain (highest to lowest):
    1. Superuser Token (X-Superuser-Token) - Admin operations
    2. Service Token (X-Service-Token) - Internal services
    3. API Key (X-API-Key) - External services
    4. User JWT (Authorization: Bearer) - End users
    5. Anonymous (no auth) - Public access
    """

    # If multiple auth methods are provided, highest priority wins
    # Example: If both API key and user JWT are provided, API key is used

    if context.is_superuser:
        # Superuser has all permissions
        return await get_all_data()

    elif context.source == AuthSource.SERVICE:
        # Internal service - trusted
        return await get_service_data()

    elif context.source == AuthSource.API_KEY:
        # External service - check permissions
        if context.has_permission("data:read"):
            return await get_api_data()
        raise HTTPException(403)

    elif context.source == AuthSource.USER:
        # End user - check user-specific permissions
        if context.has_permission("data:read"):
            return await get_user_data(context.identity)
        raise HTTPException(403)

    else:
        # Anonymous - very limited access
        return await get_public_data()
```

### Example 3: Simple vs Multi-Source Dependencies

```python
from outlabs_auth.dependencies import SimpleDeps, MultiSourceDeps

# SimpleDeps - Basic authentication (JWT only)
simple_deps = SimpleDeps(auth=auth)

@app.get("/simple")
async def simple_route(user=Depends(simple_deps.authenticated())):
    """Only accepts JWT tokens (Authorization: Bearer)"""
    return {"user": user.email}

# MultiSourceDeps - Flexible authentication
multi_deps = MultiSourceDeps(auth=auth)

@app.get("/multi")
async def multi_route(context: AuthContext = Depends(multi_deps.get_context)):
    """Accepts JWT, API keys, service tokens, superuser tokens"""
    return {
        "source": context.source.value,
        "identity": context.identity,
        "permissions": context.permissions
    }
```

### Example 4: Permission Checking with Multi-Source

```python
from outlabs_auth.dependencies import MultiSourceDeps

deps = MultiSourceDeps(auth=auth)

# Require specific permission (any auth source)
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    context: AuthContext = Depends(deps.requires("user:delete"))
):
    """Requires user:delete permission from any auth source"""
    await auth.user_service.delete_user(user_id)
    return {"message": "User deleted"}

# Require multiple permissions
@app.post("/admin/reset-database")
async def reset_database(
    context: AuthContext = Depends(deps.requires("admin:reset", "admin:confirm"))
):
    """Requires BOTH admin:reset AND admin:confirm permissions"""
    await database.reset()
    return {"message": "Database reset"}

# Require ANY of multiple permissions
@app.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    context: AuthContext = Depends(deps.requires_any("report:view", "report:export"))
):
    """Requires report:view OR report:export permission"""
    return await report_service.get(report_id)
```

### Example 5: API Key + User JWT Combined

```python
@app.post("/api/user-actions")
async def user_action(
    action: str,
    context: AuthContext = Depends(deps.get_context)
):
    """
    Can be called by:
    1. User with JWT token (personal action)
    2. Service with API key on behalf of user (automated action)
    """

    if context.source == AuthSource.USER:
        # Direct user action
        user_id = context.identity  # User email
        print(f"User {user_id} performed action: {action}")

    elif context.source == AuthSource.API_KEY:
        # Service action on behalf of user
        # Service must pass user ID in request body
        user_id = request.body.get("user_id")
        print(f"Service performed action {action} for user {user_id}")

        # Verify API key has permission to act on behalf of users
        if not context.has_permission("user:impersonate"):
            raise HTTPException(403, "API key cannot act on behalf of users")

    else:
        raise HTTPException(401, "Authentication required")

    # Perform action
    await perform_action(user_id, action)
    return {"message": "Action completed"}
```

### Example 6: Rate Limiting Per Auth Source

```python
from outlabs_auth.dependencies import MultiSourceDeps
from slowapi import Limiter

limiter = Limiter(key_func=lambda: "global")
deps = MultiSourceDeps(auth=auth)

@app.get("/api/data")
async def get_data(context: AuthContext = Depends(deps.get_context)):
    """Different rate limits per auth source"""

    # Get rate limit from context metadata
    rate_limit = context.rate_limit_remaining

    if context.source == AuthSource.API_KEY:
        # API key has its own rate limit (configured in key)
        if rate_limit is not None and rate_limit <= 0:
            raise HTTPException(429, f"API key rate limit exceeded")

    elif context.source == AuthSource.USER:
        # User JWT - apply per-user rate limit
        # Rate limit is enforced by slowapi middleware
        pass

    elif context.source == AuthSource.ANONYMOUS:
        # Anonymous - strict rate limit
        # Enforced by IP address
        pass

    return {"data": "..."}
```

### Example 7: Service-to-Service Communication

```python
# Service A (caller)
import requests

SERVICE_API_KEY = "sk_prod_ServiceA..."

response = requests.post(
    "https://service-b.example.com/api/process",
    headers={"X-API-Key": SERVICE_API_KEY},
    json={"data": "..."}
)

# Service B (receiver)
@app.post("/api/process")
async def process_data(
    data: dict,
    context: AuthContext = Depends(deps.get_context)
):
    """Internal service endpoint"""

    # Verify caller is a trusted service
    if context.source != AuthSource.API_KEY:
        raise HTTPException(401, "API key required for service access")

    # Verify specific service permissions
    if not context.has_permission("service:process"):
        raise HTTPException(403, "API key lacks service:process permission")

    # Process data
    result = await process(data)
    return {"result": result}
```

### Example 8: AuthContext in Business Logic

```python
from outlabs_auth.models import AuthContext

async def approve_invoice(invoice_id: str, context: AuthContext):
    """Business logic that works with any auth source"""

    # Get invoice
    invoice = await invoice_service.get(invoice_id)

    # Check approval permission
    if not context.has_permission("invoice:approve"):
        raise PermissionError("Cannot approve invoice")

    # Additional ABAC checks (if enabled)
    if invoice.amount > 50000 and not context.has_permission("invoice:approve_high_value"):
        raise PermissionError("Invoice amount exceeds approval limit")

    # Audit log - record who approved
    await audit_log.record(
        action="invoice_approved",
        invoice_id=invoice_id,
        auth_source=context.source.value,
        identity=context.identity,
        metadata=context.metadata
    )

    # Approve invoice
    await invoice_service.approve(invoice_id, context.identity)
    return invoice

# Use from route
@app.post("/invoices/{invoice_id}/approve")
async def approve_invoice_endpoint(
    invoice_id: str,
    context: AuthContext = Depends(deps.get_context)
):
    invoice = await approve_invoice(invoice_id, context)
    return invoice
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

**Last Updated**: 2025-01-14 (v1.4: JWT service tokens, unified AuthDeps, Redis counters, temp locks, 12-char prefixes)
**Next Review**: After Phase 1 implementation
**Related Documents**:
- [DEPENDENCY_PATTERNS.md](DEPENDENCY_PATTERNS.md) - Unified AuthDeps implementation
- [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) - DD-028, DD-033, DD-034, DD-035
