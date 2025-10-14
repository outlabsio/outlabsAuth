# Migration Guide: Centralized API → Library

**Version**: 1.0
**Date**: 2025-01-14
**Audience**: Developers migrating from the centralized OutlabsAuth API

---

## Overview

This guide helps you migrate from the centralized OutlabsAuth API service to the library-based approach. The migration preserves all your data and functionality while eliminating the centralized service dependency.

---

## Migration Path Options

### Option 1: Fresh Start (Recommended for New Features)
- Use library for new projects
- Keep existing projects on centralized API
- No migration needed

### Option 2: Gradual Migration (Recommended for Existing Projects)
- Run centralized API and library side-by-side
- Migrate one feature at a time
- Test thoroughly before switching

### Option 3: Complete Migration
- Migrate entire project from API → library
- Database migration required
- Comprehensive testing needed

---

## Pre-Migration Checklist

- [ ] Review current auth implementation
- [ ] Document all custom permissions
- [ ] Export user data and roles
- [ ] Identify which preset to use (Simple, Hierarchical, Full)
- [ ] Set up test environment
- [ ] Create rollback plan

---

## Database Migration

### Schema Changes

#### Removed Fields
```python
# OLD (Centralized API)
class EntityModel:
    platform_id: str  # ❌ Removed

# NEW (Library)
class EntityModel:
    tenant_id: Optional[str] = None  # ✅ Optional tenant isolation
```

#### Migration Script

```python
# migrate_database.py
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth.models import EntityModel, UserModel
import asyncio

async def migrate_database():
    """Migrate from centralized API schema to library schema"""

    # Connect to database
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["your_database"]

    print("Starting migration...")

    # 1. Remove platform_id from entities
    result = await db.entities.update_many(
        {},
        {"$unset": {"platform_id": ""}}
    )
    print(f"Updated {result.modified_count} entities")

    # 2. Add tenant_id if needed (for multi-tenant apps)
    # Skip this if you're not using multi-tenancy
    # result = await db.entities.update_many(
    #     {},
    #     {"$set": {"tenant_id": "default"}}
    # )

    # 3. Update indexes
    await db.entities.drop_index("platform_id_1")
    print("Dropped platform_id index")

    # 4. Recreate indexes for library
    await db.entities.create_index("slug", unique=True)
    await db.entities.create_index("parent_entity")
    print("Created new indexes")

    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_database())
```

Run migration:
```bash
python migrate_database.py
```

---

## Code Migration

### Step 1: Install Library

```bash
pip install outlabs-auth

# Or from source
git clone https://github.com/outlabs/outlabs-auth.git
cd outlabs-auth
pip install -e .
```

### Step 2: Replace API Client with Library

#### BEFORE: Centralized API

```python
# app/core/auth_client.py
import httpx

class AuthClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    async def validate_token(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/v1/auth/validate",
                headers={"Authorization": f"Bearer {token}"}
            )
            return response.json()

    async def check_permission(self, user_id: str, permission: str, entity_id: str = None):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/v1/permissions/check",
                headers={"X-API-Key": self.api_key},
                json={
                    "user_id": user_id,
                    "permission": permission,
                    "entity_id": entity_id
                }
            )
            return response.json()["has_permission"]

# app/main.py
from app.core.auth_client import AuthClient

auth_client = AuthClient(
    api_url="https://auth.outlabs.io",
    api_key=os.getenv("AUTH_API_KEY")
)

@app.get("/users/me")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    user_data = await auth_client.validate_token(token)
    return user_data

@app.delete("/users/{user_id}")
async def delete_user(user_id: str, token: str = Depends(oauth2_scheme)):
    user = await auth_client.validate_token(token)
    has_permission = await auth_client.check_permission(
        user["id"], "user:delete"
    )
    if not has_permission:
        raise HTTPException(403, "Permission denied")

    # Delete user logic
    ...
```

#### AFTER: Library

```python
# app/core/auth.py
from outlabs_auth import HierarchicalRBAC
from app.core.database import get_database

# Initialize once
auth = HierarchicalRBAC(database=get_database())

# app/main.py
from fastapi import FastAPI, Depends
from app.core.auth import auth

app = FastAPI()

@app.on_event("startup")
async def startup():
    await auth.initialize()

@app.get("/users/me")
async def get_current_user(user=Depends(auth.get_current_user)):
    # user is already a UserModel object
    return user

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user=Depends(auth.require_permission("user:delete"))
):
    # Permission already checked, user object provided
    # Delete user logic
    ...
```

### Step 3: Update Authentication Flow

#### BEFORE: API Calls

```python
@app.post("/auth/login")
async def login(credentials: LoginRequest):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{auth_client.api_url}/v1/auth/login",
            json=credentials.dict()
        )
        if response.status_code == 200:
            return response.json()
        raise HTTPException(response.status_code, response.text)
```

#### AFTER: Direct Library Calls

```python
@app.post("/auth/login")
async def login(credentials: LoginRequest):
    tokens = await auth.auth_service.login(
        email=credentials.email,
        password=credentials.password
    )
    return tokens
```

### Step 4: Update Permission Checks

#### BEFORE: API Calls with Entity Context

```python
async def check_entity_access(user_id: str, entity_id: str, permission: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{auth_client.api_url}/v1/permissions/check",
            headers={
                "X-API-Key": auth_client.api_key,
                "X-Entity-Context": entity_id
            },
            json={
                "user_id": user_id,
                "permission": permission,
                "entity_id": entity_id
            }
        )
        return response.json()["has_permission"]
```

#### AFTER: Library Calls

```python
# Option 1: Manual check
async def check_entity_access(user_id: str, entity_id: str, permission: str):
    has_permission, source = await auth.permission_service.check_permission(
        user_id=user_id,
        permission=permission,
        entity_id=entity_id
    )
    return has_permission

# Option 2: Use dependency (recommended)
@app.get("/entities/{entity_id}/members")
async def get_entity_members(
    entity_id: str,
    user=Depends(auth.require_entity_permission("member:read", "entity_id"))
):
    # Permission already checked
    members = await auth.membership_service.get_entity_members(entity_id)
    return members
```

---

## Feature Mapping

### Authentication Features

| Centralized API | Library Equivalent |
|----------------|-------------------|
| `POST /v1/auth/login` | `auth.auth_service.login()` |
| `POST /v1/auth/logout` | `auth.auth_service.logout()` |
| `POST /v1/auth/refresh` | `auth.auth_service.refresh_access_token()` |
| `POST /v1/auth/validate` | `auth.get_current_user` (dependency) |

### User Management

| Centralized API | Library Equivalent |
|----------------|-------------------|
| `GET /v1/users` | `auth.user_service.list_users()` |
| `POST /v1/users` | `auth.user_service.create_user()` |
| `GET /v1/users/{id}` | `auth.user_service.get_user()` |
| `PUT /v1/users/{id}` | `auth.user_service.update_user()` |
| `DELETE /v1/users/{id}` | `auth.user_service.delete_user()` |

### Entity Management (Hierarchical+)

| Centralized API | Library Equivalent |
|----------------|-------------------|
| `GET /v1/entities` | `auth.entity_service.list_entities()` |
| `POST /v1/entities` | `auth.entity_service.create_entity()` |
| `GET /v1/entities/{id}` | `auth.entity_service.get_entity()` |
| `PUT /v1/entities/{id}` | `auth.entity_service.update_entity()` |
| `DELETE /v1/entities/{id}` | `auth.entity_service.delete_entity()` |

### Permission Checks

| Centralized API | Library Equivalent |
|----------------|-------------------|
| `POST /v1/permissions/check` | `auth.permission_service.check_permission()` |
| `GET /v1/users/{id}/permissions` | `auth.permission_service.resolve_user_permissions()` |
| `GET /v1/permissions/effective` | `auth.permission_service.get_user_permissions()` |

---

## Configuration Migration

### BEFORE: Environment Variables for API

```bash
# .env
AUTH_API_URL=https://auth.outlabs.io
AUTH_API_KEY=your-api-key
AUTH_PLATFORM_ID=your-platform-id
```

### AFTER: Library Configuration

```bash
# .env
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=your_app
SECRET_KEY=your-secret-key-change-in-production
REDIS_URL=redis://localhost:6379  # Optional, for caching

# Optional: Multi-tenant
TENANT_ID=your-tenant  # Only if using multi-tenancy
```

```python
# app/core/config.py
from outlabs_auth import HierarchicalConfig
import os

config = HierarchicalConfig(
    secret_key=os.getenv("SECRET_KEY"),
    max_entity_depth=5,
    enable_tree_permissions=True,
    enable_caching=bool(os.getenv("REDIS_URL")),
    redis_url=os.getenv("REDIS_URL"),
)
```

---

## Testing Strategy

### Phase 1: Setup Test Environment

```bash
# 1. Clone database
mongodump --uri="mongodb://prod/your_db" --out=backup
mongorestore --uri="mongodb://test/your_db_test" backup/your_db

# 2. Run migration script on test database
python migrate_database.py --database="your_db_test"

# 3. Install library
pip install outlabs-auth
```

### Phase 2: Parallel Testing

```python
# test_migration.py
import pytest
from outlabs_auth import HierarchicalRBAC

@pytest.mark.asyncio
async def test_user_can_still_login(test_db):
    """Verify users can login after migration"""
    auth = HierarchicalRBAC(database=test_db)

    # Test with existing user credentials
    tokens = await auth.auth_service.login(
        email="existing@user.com",
        password="their-password"
    )

    assert tokens.access_token
    assert tokens.refresh_token

@pytest.mark.asyncio
async def test_permissions_preserved(test_db, existing_user_id):
    """Verify permissions still work"""
    auth = HierarchicalRBAC(database=test_db)

    # Check permission that user had before
    has_perm, _ = await auth.permission_service.check_permission(
        user_id=existing_user_id,
        permission="invoice:approve"
    )

    assert has_perm is True  # Should still have permission

@pytest.mark.asyncio
async def test_entity_hierarchy_intact(test_db):
    """Verify entity hierarchy preserved"""
    auth = HierarchicalRBAC(database=test_db)

    # Get entity that had children
    entity = await auth.entity_service.get("parent-entity-id")
    children = await auth.entity_service.get_descendants(entity.id)

    assert len(children) > 0  # Children still exist
```

### Phase 3: Integration Testing

```python
# test_api_migration.py
from fastapi.testclient import TestClient

def test_existing_users_can_login(client: TestClient):
    """End-to-end test of login flow"""
    response = client.post("/auth/login", json={
        "email": "existing@user.com",
        "password": "their-password"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()

def test_protected_routes_still_work(client: TestClient, auth_token):
    """Test protected routes with migrated data"""
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "existing@user.com"
```

---

## Rollback Plan

If migration fails, rollback steps:

### 1. Restore Database

```bash
# Restore from backup
mongorestore --uri="mongodb://localhost/your_db" backup/your_db --drop
```

### 2. Revert Code Changes

```bash
# Revert to previous version
git revert HEAD
git push
```

### 3. Restart Centralized API

```bash
# Bring centralized API back online
docker compose up -d auth-api
```

---

## Post-Migration Checklist

- [ ] All users can login
- [ ] All permissions work correctly
- [ ] Entity hierarchy intact
- [ ] Tree permissions functional
- [ ] Performance acceptable
- [ ] No data loss
- [ ] Backups verified
- [ ] Documentation updated
- [ ] Team trained on new approach

---

## Performance Comparison

### Centralized API Approach

```
Request → API Gateway → Auth Service → Database
  ↓
1-2ms   + 10-20ms     + 30-50ms      = 41-72ms per request
```

### Library Approach

```
Request → Auth Library → Database
  ↓
<1ms    + 10-30ms    = 10-30ms per request
```

**Expected improvement**: 2-3x faster permission checks

---

## Common Migration Issues

### Issue 1: platform_id References

**Problem**: Code still references `platform_id`

**Solution**:
```bash
# Find all references
grep -r "platform_id" .

# Replace with tenant_id (if needed) or remove
```

### Issue 2: API-Specific Headers

**Problem**: Code sends `X-Platform-Id` header

**Solution**: Remove platform headers, use tenant_id in config if needed

### Issue 3: Cross-Platform Queries

**Problem**: Queries filtered by `platform_id`

**Solution**: Remove platform filters or replace with `tenant_id`

```python
# BEFORE
entities = await EntityModel.find(
    EntityModel.platform_id == platform_id
).to_list()

# AFTER (single tenant)
entities = await EntityModel.find().to_list()

# AFTER (multi-tenant)
entities = await EntityModel.find(
    EntityModel.tenant_id == tenant_id
).to_list()
```

### Issue 4: External API Calls

**Problem**: Other services call centralized auth API

**Solution**: Update those services to use library OR provide REST API wrapper

---

## Gradual Migration Strategy

### Week 1: Preparation
- Set up library in test environment
- Run migration script on test data
- Verify data integrity
- Update tests

### Week 2: New Features
- Use library for new features only
- Keep existing features on API
- Monitor for issues

### Week 3: Core Features
- Migrate authentication
- Migrate user management
- Keep entity management on API

### Week 4: Complete Migration
- Migrate entity management
- Migrate all permission checks
- Remove API client code

### Week 5: Cleanup
- Decommission centralized API
- Remove old code
- Update documentation

---

## Getting Help

If you encounter issues:

1. Check [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for architectural context
2. Review [API_DESIGN.md](API_DESIGN.md) for code examples
3. Check example apps in `examples/` directory
4. File an issue with:
   - What you're migrating from
   - What's not working
   - Error messages
   - Minimal reproduction code

---

**Last Updated**: 2025-01-14
**Next Review**: After first successful migration
