# 61-EnterpriseRBAC-API.md - EnterpriseRBAC API Reference

Complete API reference for the **EnterpriseRBAC** preset.

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Initialization](#initialization)
4. [Configuration Options](#configuration-options)
5. [Available Services](#available-services)
6. [Core Methods](#core-methods)
7. [Entity Services](#entity-services)
8. [Membership Services](#membership-services)
9. [Complete Application Example](#complete-application-example)
10. [Differences from SimpleRBAC](#differences-from-simplerbac)
11. [Optional Features](#optional-features)
12. [Migration from SimpleRBAC](#migration-from-simplerbac)

---

## Overview

**EnterpriseRBAC** is a preset for **hierarchical organizational structures** with departments, teams, and nested entities.

### When to Use EnterpriseRBAC

✅ **Use EnterpriseRBAC when:**
- You have departments, teams, or organizational units
- You need hierarchical permission inheritance
- You want tree permissions (`resource:action_tree`)
- Users need different roles in different entities
- You need entity-scoped permissions

❌ **Don't use EnterpriseRBAC if:**
- You have a flat organizational structure → Use `SimpleRBAC`
- You don't need entity hierarchy → Use `SimpleRBAC`

### What EnterpriseRBAC Includes

**Always Enabled:**
- ✅ Entity hierarchy with closure table
- ✅ Tree permissions (`_tree` suffix)
- ✅ Entity memberships (users belong to entities)
- ✅ Multi-role assignments per entity
- ✅ Hierarchical permission resolution

**Optional Features:**
- 🔧 Context-aware roles (permissions adapt by entity type)
- 🔧 ABAC policies (attribute-based conditions)
- 🔧 Redis caching
- 🔧 API keys
- 🔧 Service tokens
- 🔧 OAuth/social login
- 🔧 Notifications

---

## Installation

```bash
pip install outlabs-auth
```

Or with optional dependencies:

```bash
# With Redis caching
pip install outlabs-auth[redis]

# With OAuth support
pip install outlabs-auth[oauth]

# With all features
pip install outlabs-auth[all]
```

---

## Initialization

### Basic Setup

```python
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import EnterpriseRBAC

# MongoDB connection
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["my_database"]

# Initialize EnterpriseRBAC
auth = EnterpriseRBAC(
    database=db,
    secret_key="your-secret-key-here-min-32-chars",
)

# Initialize database (create indexes, etc.)
await auth.initialize()
```

### With Optional Features

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key="your-secret-key-here-min-32-chars",

    # Optional features
    enable_context_aware_roles=True,  # Roles adapt by entity type
    enable_abac=True,                 # ABAC policy evaluation

    # Caching
    enable_caching=True,
    redis_url="redis://localhost:6379",
    cache_ttl=300,  # 5 minutes

    # JWT settings
    access_token_expire_minutes=15,
    refresh_token_expire_days=30,

    # API keys
    enable_api_keys=True,
    api_key_default_expiry_days=90,

    # Service tokens
    enable_service_tokens=True,

    # OAuth
    enable_oauth=True,
    google_client_id="your-google-client-id",
    google_client_secret="your-google-client-secret",
    github_client_id="your-github-client-id",
    github_client_secret="your-github-client-secret",

    # Notifications
    enable_notifications=True,
)
```

---

## Configuration Options

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `database` | `AsyncIOMotorDatabase` | MongoDB database instance |
| `secret_key` | `str` | JWT signing key (min 32 chars) |

### Optional Features

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_context_aware_roles` | `bool` | `False` | Enable context-aware roles |
| `enable_abac` | `bool` | `False` | Enable ABAC policies |
| `enable_caching` | `bool` | `False` | Enable Redis caching |
| `redis_url` | `str` | `None` | Redis connection URL |
| `cache_ttl` | `int` | `300` | Cache TTL in seconds |

### Authentication Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token_expire_minutes` | `int` | `15` | Access token expiry |
| `refresh_token_expire_days` | `int` | `30` | Refresh token expiry |
| `enable_api_keys` | `bool` | `False` | Enable API key authentication |
| `api_key_default_expiry_days` | `int` | `90` | Default API key expiry |
| `enable_service_tokens` | `bool` | `False` | Enable service tokens |

### OAuth Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_oauth` | `bool` | `False` | Enable OAuth login |
| `google_client_id` | `str` | `None` | Google OAuth client ID |
| `google_client_secret` | `str` | `None` | Google OAuth secret |
| `github_client_id` | `str` | `None` | GitHub OAuth client ID |
| `github_client_secret` | `str` | `None` | GitHub OAuth secret |

### Notification Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_notifications` | `bool` | `False` | Enable notification system |

---

## Available Services

EnterpriseRBAC provides **all services from SimpleRBAC** plus additional services for entity management:

### Core Services (from SimpleRBAC)

| Service | Attribute | Description |
|---------|-----------|-------------|
| **AuthService** | `auth.auth_service` | JWT authentication, login, logout |
| **UserService** | `auth.user_service` | User CRUD, profile management |
| **RoleService** | `auth.role_service` | Role management, assignments |
| **PermissionService** | `auth.permission_service` | Permission checks, grants |

### Additional Services (EnterpriseRBAC)

| Service | Attribute | Description |
|---------|-----------|-------------|
| **EntityService** | `auth.entity_service` | Entity hierarchy management |
| **MembershipService** | `auth.membership_service` | Entity memberships, role assignments |

### Optional Services

| Service | Attribute | Requires | Description |
|---------|-----------|----------|-------------|
| **ApiKeyService** | `auth.api_key_service` | `enable_api_keys=True` | API key management |
| **ServiceTokenService** | `auth.service_token_service` | `enable_service_tokens=True` | Service token management |
| **OAuthService** | `auth.oauth_service` | `enable_oauth=True` | OAuth authentication |
| **NotificationService** | `auth.notification_service` | `enable_notifications=True` | Notification delivery |

---

## Core Methods

### initialize()

Initialize database indexes and setup.

```python
await auth.initialize()
```

**Must be called once at startup** before using the library.

### get_current_user()

Get current user from JWT token.

```python
from fastapi import Depends
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

@app.get("/me")
async def get_me(user = Depends(deps.authenticated())):
    return user
```

**Returns:** `UserModel` or raises `HTTPException(401)`

### verify_password()

Verify a plaintext password against a hashed password.

```python
is_valid = auth.verify_password("plain_password", user.hashed_password)
```

**Parameters:**
- `plain_password` (str): Plaintext password
- `hashed_password` (str): argon2id hashed password

**Returns:** `bool`

### hash_password()

Hash a plaintext password.

```python
hashed = auth.hash_password("my_password")
```

**Parameters:**
- `password` (str): Plaintext password

**Returns:** `str` (argon2id hash)

---

## Entity Services

### EntityService

Manage entity hierarchy, types, and organizational structure.

#### create_entity()

Create a new entity.

```python
from outlabs_auth.models.entity import EntityClass

entity = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=None,  # Root entity
    metadata={"location": "Building A"}
)
```

**Parameters:**
- `name` (str): Unique identifier (snake_case)
- `display_name` (str): Human-readable name
- `entity_class` (EntityClass): `STRUCTURAL` or `ACCESS_GROUP`
- `entity_type` (str): Custom type (e.g., "department", "team")
- `parent_id` (str | None): Parent entity ID for hierarchy
- `metadata` (dict): Additional key-value data

**Returns:** `EntityModel`

#### get_entity()

Get entity by ID.

```python
entity = await auth.entity_service.get_entity(entity_id)
```

**Parameters:**
- `entity_id` (str): Entity ID

**Returns:** `EntityModel` or `None`

#### get_entity_by_name()

Get entity by unique name.

```python
entity = await auth.entity_service.get_entity_by_name("engineering")
```

**Parameters:**
- `name` (str): Entity name

**Returns:** `EntityModel` or `None`

#### update_entity()

Update entity fields.

```python
updated = await auth.entity_service.update_entity(
    entity_id,
    display_name="Engineering Division",
    metadata={"location": "Building B"}
)
```

**Parameters:**
- `entity_id` (str): Entity ID
- `**updates`: Fields to update

**Returns:** `EntityModel`

#### delete_entity()

Delete entity and all descendants.

```python
await auth.entity_service.delete_entity(entity_id)
```

**Parameters:**
- `entity_id` (str): Entity ID

**Returns:** `bool`

**Warning:** Deletes all child entities, memberships, and roles. Use with caution.

#### get_ancestors()

Get all ancestor entities (parents, grandparents, etc.) using closure table.

```python
ancestors = await auth.entity_service.get_ancestors(entity_id)
```

**Parameters:**
- `entity_id` (str): Entity ID

**Returns:** `list[EntityModel]` (ordered from immediate parent to root)

**Performance:** O(1) query using closure table.

#### get_descendants()

Get all descendant entities (children, grandchildren, etc.).

```python
descendants = await auth.entity_service.get_descendants(entity_id)
```

**Parameters:**
- `entity_id` (str): Entity ID

**Returns:** `list[EntityModel]` (all descendants)

**Performance:** O(1) query using closure table.

#### get_children()

Get immediate children only.

```python
children = await auth.entity_service.get_children(entity_id)
```

**Parameters:**
- `entity_id` (str): Entity ID

**Returns:** `list[EntityModel]`

#### is_ancestor()

Check if entity A is an ancestor of entity B.

```python
is_parent = await auth.entity_service.is_ancestor(
    ancestor_id=dept_id,
    descendant_id=team_id
)
```

**Parameters:**
- `ancestor_id` (str): Potential ancestor entity ID
- `descendant_id` (str): Potential descendant entity ID

**Returns:** `bool`

**Performance:** O(1) query using closure table.

#### get_entity_path()

Get full path from root to entity.

```python
path = await auth.entity_service.get_entity_path(entity_id)
# Example: ["acme_corp", "engineering", "backend_team"]
```

**Parameters:**
- `entity_id` (str): Entity ID

**Returns:** `list[str]` (entity names from root to target)

---

## Membership Services

### MembershipService

Manage user memberships in entities and role assignments.

#### add_member()

Add user to entity with roles.

```python
membership = await auth.membership_service.add_member(
    entity_id=str(engineering.id),
    user_id=str(user.id),
    role_ids=[str(developer_role.id), str(reviewer_role.id)],
    granted_by=str(admin.id)
)
```

**Parameters:**
- `entity_id` (str): Entity ID
- `user_id` (str): User ID
- `role_ids` (list[str]): Role IDs to assign
- `granted_by` (str): Admin user ID who granted membership

**Returns:** `EntityMembershipModel`

#### remove_member()

Remove user from entity.

```python
success = await auth.membership_service.remove_member(
    entity_id=str(engineering.id),
    user_id=str(user.id)
)
```

**Parameters:**
- `entity_id` (str): Entity ID
- `user_id` (str): User ID

**Returns:** `bool`

#### get_membership()

Get membership for user in entity.

```python
membership = await auth.membership_service.get_membership(
    entity_id=str(engineering.id),
    user_id=str(user.id)
)
```

**Parameters:**
- `entity_id` (str): Entity ID
- `user_id` (str): User ID

**Returns:** `EntityMembershipModel` or `None`

#### get_user_memberships()

Get all memberships for a user.

```python
memberships = await auth.membership_service.get_user_memberships(
    user_id=str(user.id)
)
```

**Parameters:**
- `user_id` (str): User ID

**Returns:** `list[EntityMembershipModel]`

#### get_entity_members()

Get all members of an entity.

```python
members = await auth.membership_service.get_entity_members(
    entity_id=str(engineering.id)
)
```

**Parameters:**
- `entity_id` (str): Entity ID

**Returns:** `list[EntityMembershipModel]`

#### add_roles_to_member()

Add additional roles to existing member.

```python
updated = await auth.membership_service.add_roles_to_member(
    entity_id=str(engineering.id),
    user_id=str(user.id),
    role_ids=[str(new_role.id)]
)
```

**Parameters:**
- `entity_id` (str): Entity ID
- `user_id` (str): User ID
- `role_ids` (list[str]): Additional role IDs

**Returns:** `EntityMembershipModel`

#### remove_roles_from_member()

Remove roles from member.

```python
updated = await auth.membership_service.remove_roles_from_member(
    entity_id=str(engineering.id),
    user_id=str(user.id),
    role_ids=[str(old_role.id)]
)
```

**Parameters:**
- `entity_id` (str): Entity ID
- `user_id` (str): User ID
- `role_ids` (list[str]): Role IDs to remove

**Returns:** `EntityMembershipModel`

#### get_user_roles_in_entity()

Get all roles for user in specific entity.

```python
roles = await auth.membership_service.get_user_roles_in_entity(
    entity_id=str(engineering.id),
    user_id=str(user.id)
)
```

**Parameters:**
- `entity_id` (str): Entity ID
- `user_id` (str): User ID

**Returns:** `list[RoleModel]`

---

## Complete Application Example

### Setup: Hierarchical Organization

```python
from fastapi import FastAPI, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.models.entity import EntityClass

app = FastAPI()

# MongoDB connection
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["company_db"]

# Initialize EnterpriseRBAC
auth = EnterpriseRBAC(
    database=db,
    secret_key="your-secret-key-min-32-chars-long",
    enable_context_aware_roles=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Dependency injection
deps = AuthDeps(auth)

@app.on_event("startup")
async def startup():
    await auth.initialize()
    await setup_organization()

async def setup_organization():
    """Create organizational hierarchy."""

    # 1. Create root organization
    org = await auth.entity_service.create_entity(
        name="acme_corp",
        display_name="ACME Corporation",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization"
    )

    # 2. Create departments
    engineering = await auth.entity_service.create_entity(
        name="engineering",
        display_name="Engineering Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(org.id)
    )

    sales = await auth.entity_service.create_entity(
        name="sales",
        display_name="Sales Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(org.id)
    )

    # 3. Create teams under Engineering
    backend_team = await auth.entity_service.create_entity(
        name="backend_team",
        display_name="Backend Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(engineering.id)
    )

    frontend_team = await auth.entity_service.create_entity(
        name="frontend_team",
        display_name="Frontend Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(engineering.id)
    )

    # 4. Create roles
    developer_role = await auth.role_service.create_role(
        name="developer",
        permissions=[
            "code:read",
            "code:write",
            "repo:push"
        ]
    )

    manager_role = await auth.role_service.create_role(
        name="manager",
        permissions=[
            "code:read",
            "code:approve_tree",      # Tree permission
            "budget:view_tree",       # Tree permission
            "team:manage"
        ]
    )

    cto_role = await auth.role_service.create_role(
        name="cto",
        permissions=[
            "code:read",
            "code:approve_tree",
            "budget:approve_tree",
            "org:manage_tree"
        ]
    )

    # 5. Assign users to entities
    # Create users
    alice = await auth.user_service.create_user(
        email="alice@acme.com",
        password="SecurePass123!",
        first_name="Alice",
        last_name="Developer"
    )

    bob = await auth.user_service.create_user(
        email="bob@acme.com",
        password="SecurePass123!",
        first_name="Bob",
        last_name="Manager"
    )

    charlie = await auth.user_service.create_user(
        email="charlie@acme.com",
        password="SecurePass123!",
        first_name="Charlie",
        last_name="CTO"
    )

    # Add Alice as developer in backend team
    await auth.membership_service.add_member(
        entity_id=str(backend_team.id),
        user_id=str(alice.id),
        role_ids=[str(developer_role.id)],
        granted_by=str(charlie.id)
    )

    # Add Bob as manager in Engineering (affects all descendants)
    await auth.membership_service.add_member(
        entity_id=str(engineering.id),
        user_id=str(bob.id),
        role_ids=[str(manager_role.id)],
        granted_by=str(charlie.id)
    )

    # Add Charlie as CTO at org level
    await auth.membership_service.add_member(
        entity_id=str(org.id),
        user_id=str(charlie.id),
        role_ids=[str(cto_role.id)],
        granted_by=str(charlie.id)  # Self-granted (bootstrapping)
    )
```

### Protected Routes with Entity Context

```python
# ============================================
# Public Routes
# ============================================

@app.post("/auth/login")
async def login(email: str, password: str):
    """Login with email and password."""
    tokens = await auth.auth_service.login(email, password)
    return tokens

# ============================================
# Authenticated Routes
# ============================================

@app.get("/users/me")
async def get_me(user = Depends(deps.authenticated())):
    """Get current user profile."""
    return user

@app.get("/users/me/entities")
async def get_my_entities(user = Depends(deps.authenticated())):
    """Get all entities user belongs to."""
    memberships = await auth.membership_service.get_user_memberships(str(user.id))

    entities = []
    for membership in memberships:
        entity = await auth.entity_service.get_entity(membership.entity_id)
        roles = await auth.membership_service.get_user_roles_in_entity(
            entity_id=membership.entity_id,
            user_id=str(user.id)
        )
        entities.append({
            "entity": entity,
            "roles": roles
        })

    return entities

# ============================================
# Permission-Based Routes
# ============================================

@app.get("/code/repo/{repo_id}")
async def get_repo(
    repo_id: str,
    user = Depends(deps.requires("code:read"))
):
    """Read code repository."""
    return {"repo_id": repo_id, "content": "..."}

@app.post("/code/repo/{repo_id}/push")
async def push_code(
    repo_id: str,
    user = Depends(deps.requires("code:write"))
):
    """Push code to repository."""
    return {"message": "Code pushed successfully"}

# ============================================
# Entity-Scoped Routes
# ============================================

@app.get("/entities/{entity_id}/budget")
async def get_budget(
    entity_id: str,
    user = Depends(deps.authenticated())
):
    """Get budget for entity (requires budget:view or budget:view_tree)."""

    # Check permission in entity context
    has_perm, source = await auth.permission_service.check_permission(
        user_id=str(user.id),
        permission="budget:view",
        entity_id=entity_id
    )

    if not has_perm:
        raise HTTPException(status_code=403, detail="Permission denied")

    # If permission came from tree, user is viewing from ancestor entity
    if source == "tree":
        return {
            "entity_id": entity_id,
            "budget": 50000,
            "access_type": "inherited"
        }
    else:
        return {
            "entity_id": entity_id,
            "budget": 50000,
            "access_type": "direct"
        }

@app.put("/entities/{entity_id}/budget")
async def update_budget(
    entity_id: str,
    amount: float,
    user = Depends(deps.authenticated())
):
    """Update budget for entity (requires budget:approve or budget:approve_tree)."""

    has_perm, source = await auth.permission_service.check_permission(
        user_id=str(user.id),
        permission="budget:approve",
        entity_id=entity_id
    )

    if not has_perm:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Update budget logic here
    return {
        "entity_id": entity_id,
        "budget": amount,
        "updated_by": user.email
    }

# ============================================
# Admin Routes (Tree Permissions)
# ============================================

@app.get("/entities/{entity_id}/tree")
async def get_entity_tree(
    entity_id: str,
    user = Depends(deps.requires("org:manage_tree"))
):
    """Get entity and all descendants."""

    entity = await auth.entity_service.get_entity(entity_id)
    descendants = await auth.entity_service.get_descendants(entity_id)

    return {
        "entity": entity,
        "descendants": descendants
    }

@app.post("/entities/{parent_id}/subentities")
async def create_subentity(
    parent_id: str,
    name: str,
    display_name: str,
    entity_type: str,
    user = Depends(deps.requires("org:manage_tree"))
):
    """Create sub-entity (requires org:manage_tree in parent)."""

    # Verify permission in parent entity
    has_perm, _ = await auth.permission_service.check_permission(
        user_id=str(user.id),
        permission="org:manage",
        entity_id=parent_id
    )

    if not has_perm:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Create sub-entity
    entity = await auth.entity_service.create_entity(
        name=name,
        display_name=display_name,
        entity_class=EntityClass.STRUCTURAL,
        entity_type=entity_type,
        parent_id=parent_id
    )

    return entity

# ============================================
# Membership Management
# ============================================

@app.post("/entities/{entity_id}/members")
async def add_member_to_entity(
    entity_id: str,
    user_id: str,
    role_ids: list[str],
    admin = Depends(deps.requires("team:manage"))
):
    """Add member to entity."""

    membership = await auth.membership_service.add_member(
        entity_id=entity_id,
        user_id=user_id,
        role_ids=role_ids,
        granted_by=str(admin.id)
    )

    return membership

@app.delete("/entities/{entity_id}/members/{user_id}")
async def remove_member_from_entity(
    entity_id: str,
    user_id: str,
    admin = Depends(deps.requires("team:manage"))
):
    """Remove member from entity."""

    success = await auth.membership_service.remove_member(
        entity_id=entity_id,
        user_id=user_id
    )

    return {"success": success}

@app.get("/entities/{entity_id}/members")
async def list_entity_members(
    entity_id: str,
    user = Depends(deps.requires("team:view"))
):
    """List all members of entity."""

    members = await auth.membership_service.get_entity_members(entity_id)

    # Enrich with user details
    result = []
    for membership in members:
        user = await auth.user_service.get_user(membership.user_id)
        roles = await auth.membership_service.get_user_roles_in_entity(
            entity_id=entity_id,
            user_id=membership.user_id
        )
        result.append({
            "user": user,
            "roles": roles,
            "joined_at": membership.created_at
        })

    return result
```

---

## Differences from SimpleRBAC

| Feature | SimpleRBAC | EnterpriseRBAC |
|---------|------------|----------------|
| **Entity Hierarchy** | ❌ Not available | ✅ Always enabled |
| **Tree Permissions** | ❌ Not available | ✅ Available (`_tree` suffix) |
| **Entity Memberships** | ❌ Not available | ✅ Users belong to entities |
| **Multi-Role per Context** | ✅ Global roles | ✅ Different roles per entity |
| **Organizational Structure** | Flat | Hierarchical (departments, teams) |
| **Permission Scope** | Global only | Entity-scoped + global |
| **EntityService** | ❌ Not available | ✅ Available |
| **MembershipService** | ❌ Not available | ✅ Available |
| **Use Case** | Small apps, flat structure | Enterprise, departments, teams |

---

## Optional Features

### Context-Aware Roles

Enable roles that adapt permissions based on entity type.

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key="...",
    enable_context_aware_roles=True
)
```

**Example:**

```python
# Create context-aware role
manager_role = await auth.role_service.create_role(
    name="manager",
    permissions=["project:read", "project:write"],
    context_aware=True,
    entity_type_permissions={
        "department": ["budget:approve", "team:manage"],
        "team": ["task:assign", "member:add"]
    }
)

# When user has this role in "department" entity:
# - Gets: project:read, project:write, budget:approve, team:manage
# When user has this role in "team" entity:
# - Gets: project:read, project:write, task:assign, member:add
```

See **41-RBAC-Patterns.md** for complete guide.

### ABAC Policies

Enable attribute-based access control with conditions.

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key="...",
    enable_abac=True
)
```

**Example:**

```python
# Create permission with ABAC condition
permission = await auth.permission_service.create_permission(
    name="document:edit",
    conditions={
        "user.department": {"$eq": "legal"},
        "resource.status": {"$in": ["draft", "review"]},
        "user.clearance_level": {"$gte": 3}
    }
)
```

See **46-ABAC-Policies.md** for complete guide with 20+ operators.

### Redis Caching

Enable Redis caching for permission checks.

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key="...",
    enable_caching=True,
    redis_url="redis://localhost:6379",
    cache_ttl=300  # 5 minutes
)
```

**Cached Operations:**
- Permission checks
- Role lookups
- Entity hierarchy queries
- User memberships

**Cache Invalidation:**
- Automatic on role/permission changes
- Redis Pub/Sub for multi-instance sync
- Manual: `await auth.permission_service.invalidate_cache(user_id)`

### API Keys

Enable API key authentication.

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key="...",
    enable_api_keys=True,
    api_key_default_expiry_days=90
)
```

**Usage:**

```python
# Create API key
api_key = await auth.api_key_service.create_api_key(
    user_id=str(user.id),
    name="Production API Key",
    expires_in_days=90
)

# Returns: "oal_abc123xyz..." (prefix + key)
# Store this securely - it's only shown once

# Authenticate with API key
@app.get("/api/data")
async def get_data(user = Depends(deps.authenticated())):
    # Accepts both JWT and API key
    return {"data": "..."}
```

See **60-SimpleRBAC-API.md** for complete API key reference.

### Service Tokens

Enable service-to-service authentication.

```python
auth = EnterpriseRBAC(
    database=db,
    secret_key="...",
    enable_service_tokens=True
)
```

**Usage:**

```python
# Create service token
service_token = await auth.service_token_service.create_service_token(
    service_name="billing_service",
    permissions=["invoice:create", "payment:process"]
)

# Use in microservice
headers = {"Authorization": f"Bearer {service_token}"}
response = requests.post(
    "https://api.example.com/invoices",
    headers=headers,
    json={"amount": 100}
)
```

---

## Migration from SimpleRBAC

### Step 1: Update Initialization

**Before (SimpleRBAC):**

```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=db, secret_key="...")
```

**After (EnterpriseRBAC):**

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(database=db, secret_key="...")
```

### Step 2: Create Entity Hierarchy

```python
# Create root organization
org = await auth.entity_service.create_entity(
    name="my_organization",
    display_name="My Organization",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="organization"
)

# Create departments, teams, etc.
```

### Step 3: Migrate User Roles

**Before:** Users had global roles

```python
# Old: Global role assignment
await auth.role_service.assign_role(user_id, role_id)
```

**After:** Users have roles within entities

```python
# New: Entity-scoped role assignment
await auth.membership_service.add_member(
    entity_id=str(org.id),
    user_id=str(user.id),
    role_ids=[str(role.id)],
    granted_by=str(admin.id)
)
```

### Step 4: Update Permission Checks

**Before:** Global permission checks

```python
has_perm = await auth.permission_service.check_permission(
    user_id, "document:edit"
)
```

**After:** Entity-scoped permission checks

```python
has_perm, source = await auth.permission_service.check_permission(
    user_id, "document:edit", entity_id=entity_id
)
```

### Step 5: Add Tree Permissions (Optional)

If you want hierarchical permission inheritance:

```python
# Update roles to use tree permissions
await auth.role_service.update_role(
    role_id,
    permissions=[
        "document:read",
        "document:approve_tree",  # Applies to all descendant entities
    ]
)
```

### Step 6: Test Permission Resolution

```python
# Test in different entity contexts
has_perm_in_dept, source = await auth.permission_service.check_permission(
    user_id, "budget:approve", entity_id=department_id
)

has_perm_in_team, source = await auth.permission_service.check_permission(
    user_id, "budget:approve", entity_id=team_id
)

# If user has budget:approve_tree in department:
# - has_perm_in_dept = True, source = "direct"
# - has_perm_in_team = True, source = "tree" (inherited)
```

---

## Summary

**EnterpriseRBAC** provides:

✅ **Entity Hierarchy** - Departments, teams, nested structures
✅ **Tree Permissions** - Hierarchical permission inheritance
✅ **Entity Memberships** - Users with different roles per entity
✅ **Multi-Role Support** - Multiple roles in each entity
✅ **Closure Table** - O(1) ancestor/descendant queries
✅ **All SimpleRBAC Features** - Authentication, JWT, API keys, etc.

**Optional:**
- 🔧 Context-aware roles
- 🔧 ABAC policies
- 🔧 Redis caching
- 🔧 OAuth/social login
- 🔧 Service tokens
- 🔧 Notifications

---

## Related Documentation

- **42-Entity-Hierarchy.md** - Complete entity hierarchy guide
- **43-Tree-Permissions.md** - Tree permission inheritance patterns
- **41-RBAC-Patterns.md** - RBAC design patterns
- **60-SimpleRBAC-API.md** - SimpleRBAC API reference
- **70-User-Service.md** - UserService API reference
- **71-Role-Service.md** - RoleService API reference
- **72-Permission-Service.md** - PermissionService API reference

---

**Last Updated:** 2025-01-14
