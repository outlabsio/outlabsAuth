# OutlabsAuth Testing Guide

**Version**: 1.4
**Date**: 2025-01-14
**Audience**: Developers testing OutlabsAuth integrations
**Status**: Production Reference

**Key Testing Updates (v1.4)**:
- **Unified AuthDeps**: Single dependency class instead of MultiSourceDeps (DD-035)
- **12-Char Prefixes**: API keys now have 12-character prefixes (DD-028)
- **Temporary Locks**: Test 30-min cooldowns instead of permanent revocation (DD-028)
- **Redis Counters**: Test Redis-based usage tracking (DD-033)
- **Closure Table**: Test O(1) tree permission queries (DD-036)
- **JWT Service Tokens**: Test stateless internal service authentication (DD-034)

**Recent Coverage Note (Mar 2026)**:
- membership lifecycle API coverage exists in `tests/integration/test_membership_lifecycle_api.py`
- direct role membership lifecycle read coverage exists in `tests/integration/test_role_assignment.py`
- a comprehensive admin user-details regression suite is still missing and should be added in a future pass

That future suite should cover the combined contract used by the admin frontend record page:

- profile update
- user status change
- resend invite
- admin password reset
- delete user
- direct role assignment, read, and revoke
- entity membership create, update, revoke, and reactivate

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure](#test-structure)
3. [Testing Utilities](#testing-utilities)
4. [Unit Testing](#unit-testing)
5. [Integration Testing](#integration-testing)
6. [Permission Testing](#permission-testing)
7. [Entity Hierarchy Testing](#entity-hierarchy-testing)
8. [Authentication Testing](#authentication-testing)
9. **[API Key Testing](#api-key-testing)** ← NEW
10. **[Multi-Source Authentication Testing](#multi-source-authentication-testing)** ← NEW
11. [Mocking & Fixtures](#mocking--fixtures)
12. [Performance Testing](#performance-testing)
13. [CI/CD Integration](#cicd-integration)
14. [Test Coverage](#test-coverage)
15. [Testing Patterns](#testing-patterns)

---

## Testing Philosophy

### Our Approach

OutlabsAuth provides comprehensive testing utilities to make testing your authentication and authorization logic straightforward:

1. **Test Fixtures**: Pre-built fixtures for users, roles, entities
2. **Helper Functions**: Utilities for common testing scenarios
3. **Mocking Support**: Easy mocking of auth components
4. **Async-First**: Full async/await support in tests
5. **Isolated Tests**: Each test runs with clean database state

### Testing Pyramid

```
       /\
      /  \     E2E Tests (Few)
     /____\    - Full application flow
    /      \   - Real database
   /________\  Integration Tests (Some)
  /          \ - Multiple components
 /____________\- Test database
/              \
________________ Unit Tests (Many)
                - Single components
                - Mocked dependencies
```

**Target Coverage**:
- Unit tests: 90%+ coverage
- Integration tests: 80%+ coverage
- E2E tests: Critical paths only

---

## Test Structure

### Project Layout

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_auth_service.py
│   ├── test_permission_service.py
│   ├── test_user_service.py
│   └── test_models.py
├── integration/             # Integration tests
│   ├── test_auth_flow.py
│   ├── test_permission_flow.py
│   └── test_entity_hierarchy.py
├── e2e/                     # End-to-end tests
│   ├── test_user_lifecycle.py
│   └── test_admin_operations.py
└── fixtures/                # Test data
    ├── users.json
    ├── roles.json
    └── entities.json
```

### Test File Naming

- **Unit tests**: `test_<module>_unit.py`
- **Integration tests**: `test_<feature>_integration.py`
- **E2E tests**: `test_<scenario>_e2e.py`
- **Test classes**: `Test<Feature>`
- **Test functions**: `test_<what_it_tests>`

---

## Testing Utilities

### AuthTestCase Base Class

```python
# tests/base.py
from outlabs_auth.testing import AuthTestCase
import pytest

class TestAuth(AuthTestCase):
    """Base class for auth tests"""

    async def asyncSetUp(self):
        """Called before each test"""
        await super().asyncSetUp()
        # Additional setup
        self.test_user = await self.create_test_user(
            email="test@example.com",
            password="Test123!@#"
        )

    async def asyncTearDown(self):
        """Called after each test"""
        # Cleanup
        await super().asyncTearDown()

    @pytest.mark.asyncio
    async def test_example(self):
        """Example test"""
        # Test logic here
        assert self.test_user.email == "test@example.com"
```

### Built-in Test Helpers

```python
from outlabs_auth.testing import (
    create_test_user,
    create_test_role,
    create_test_entity,
    create_test_permission,
    assign_role_to_user,
    add_user_to_entity,
    create_test_tokens
)

# Create test user
user = await create_test_user(
    email="user@example.com",
    password="password123",
    is_active=True
)

# Create test role with permissions
role = await create_test_role(
    name="test_role",
    permissions=["user:read", "user:create"],
    is_global=True
)

# Create test entity
entity = await create_test_entity(
    name="test_org",
    entity_type="organization",
    entity_class="STRUCTURAL"
)

# Assign role to user
await assign_role_to_user(user.id, role.id)

# Add user to entity
await add_user_to_entity(user.id, entity.id)

# Create test tokens
tokens = await create_test_tokens(user)
access_token = tokens.access_token
```

### Test Database Setup

```python
# conftest.py
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from beanie import init_beanie

@pytest_asyncio.fixture
async def test_db():
    """Create test database"""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["outlabs_auth_test"]

    # Initialize Beanie with models
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            EntityModel,
            PermissionModel,
            RefreshTokenModel
        ]
    )

    yield db

    # Cleanup
    await client.drop_database("outlabs_auth_test")
    client.close()

@pytest_asyncio.fixture
async def auth(test_db):
    """Create auth instance"""
    auth = SimpleRBAC(database=test_db)
    await auth.initialize()
    return auth
```

---

## Unit Testing

### Testing Service Methods

```python
# tests/unit/test_user_service.py
import pytest
from outlabs_auth import SimpleRBAC
from outlabs_auth.exceptions import UserAlreadyExistsException

@pytest.mark.asyncio
async def test_create_user(auth):
    """Test creating a new user"""
    user = await auth.user_service.create_user(
        email="newuser@example.com",
        password="SecurePassword123!",
        name="New User"
    )

    assert user.email == "newuser@example.com"
    assert user.name == "New User"
    assert user.hashed_password is not None
    assert user.is_active is True

@pytest.mark.asyncio
async def test_create_duplicate_user_fails(auth):
    """Test that creating duplicate user raises exception"""
    # Create first user
    await auth.user_service.create_user(
        email="user@example.com",
        password="password123",
        name="User"
    )

    # Attempt to create duplicate
    with pytest.raises(UserAlreadyExistsException):
        await auth.user_service.create_user(
            email="user@example.com",
            password="different_password",
            name="Different Name"
        )

@pytest.mark.asyncio
async def test_get_user_by_email(auth):
    """Test retrieving user by email"""
    # Create user
    created_user = await auth.user_service.create_user(
        email="findme@example.com",
        password="password123",
        name="Find Me"
    )

    # Retrieve user
    found_user = await auth.user_service.get_user_by_email("findme@example.com")

    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == "findme@example.com"

@pytest.mark.asyncio
async def test_update_user(auth):
    """Test updating user information"""
    user = await auth.user_service.create_user(
        email="update@example.com",
        password="password123",
        name="Old Name"
    )

    # Update user
    updated_user = await auth.user_service.update_user(
        user_id=user.id,
        name="New Name"
    )

    assert updated_user.name == "New Name"
    assert updated_user.email == "update@example.com"

@pytest.mark.asyncio
async def test_delete_user(auth):
    """Test deleting a user"""
    user = await auth.user_service.create_user(
        email="deleteme@example.com",
        password="password123",
        name="Delete Me"
    )

    # Delete user
    await auth.user_service.delete_user(user.id)

    # Verify user is deleted
    deleted_user = await auth.user_service.get_user(user.id)
    assert deleted_user is None
```

### Testing Models

```python
# tests/unit/test_models.py
import pytest
from outlabs_auth.models import UserModel, RoleModel
from pydantic import ValidationError

@pytest.mark.asyncio
async def test_user_model_validation():
    """Test UserModel validation"""
    # Valid user
    user = UserModel(
        email="valid@example.com",
        hashed_password="hashed_password_here",
        name="Valid User"
    )
    assert user.email == "valid@example.com"

    # Invalid email
    with pytest.raises(ValidationError):
        UserModel(
            email="invalid-email",  # Not a valid email
            hashed_password="password",
            name="Invalid User"
        )

@pytest.mark.asyncio
async def test_role_model_defaults():
    """Test RoleModel default values"""
    role = RoleModel(
        name="test_role",
        display_name="Test Role",
        permissions=["user:read"]
    )

    assert role.is_global is False  # Default
    assert role.is_active is True   # Default
    assert role.entity_type_permissions == {}  # Default
```

---

## Integration Testing

### Testing Complete Flows

```python
# tests/integration/test_auth_flow.py
import pytest
from outlabs_auth import SimpleRBAC
from outlabs_auth.exceptions import InvalidCredentialsException

@pytest.mark.asyncio
async def test_complete_auth_flow(auth):
    """Test complete authentication flow"""
    # 1. Create user
    user = await auth.user_service.create_user(
        email="authtest@example.com",
        password="SecurePassword123!",
        name="Auth Test"
    )

    # 2. Login
    tokens = await auth.auth_service.login(
        email="authtest@example.com",
        password="SecurePassword123!"
    )

    assert tokens.access_token is not None
    assert tokens.refresh_token is not None
    assert tokens.token_type == "bearer"

    # 3. Validate access token
    validated_user = await auth.auth_service.get_user_from_token(
        tokens.access_token
    )

    assert validated_user.id == user.id
    assert validated_user.email == "authtest@example.com"

    # 4. Refresh token
    new_tokens = await auth.auth_service.refresh_access_token(
        tokens.refresh_token
    )

    assert new_tokens.access_token != tokens.access_token  # New token
    assert new_tokens.refresh_token is not None

    # 5. Logout
    await auth.auth_service.logout(tokens.refresh_token)

    # 6. Verify token is revoked
    with pytest.raises(InvalidCredentialsException):
        await auth.auth_service.refresh_access_token(tokens.refresh_token)

@pytest.mark.asyncio
async def test_role_assignment_flow(auth):
    """Test role assignment and permission checking"""
    # 1. Create user
    user = await auth.user_service.create_user(
        email="roletest@example.com",
        password="password123",
        name="Role Test"
    )

    # 2. Create role
    role = await auth.role_service.create_role(
        name="test_role",
        display_name="Test Role",
        permissions=["user:read", "user:create"],
        is_global=True
    )

    # 3. Assign role to user
    await auth.role_service.assign_role(
        user_id=user.id,
        role_id=role.id
    )

    # 4. Check permissions
    has_read, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:read"
    )
    assert has_read is True

    has_delete, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:delete"
    )
    assert has_delete is False

    # 5. Remove role
    await auth.role_service.remove_role(
        user_id=user.id,
        role_id=role.id
    )

    # 6. Verify permissions removed
    has_read_after, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:read"
    )
    assert has_read_after is False
```

---

## Permission Testing

### Testing Permission Logic

```python
# tests/integration/test_permissions.py
import pytest
from outlabs_auth import SimpleRBAC

@pytest.mark.asyncio
async def test_basic_permission_check(auth):
    """Test basic permission checking"""
    # Create user with role
    user = await auth.user_service.create_user(
        email="perm@example.com",
        password="password123",
        name="Permission Test"
    )

    role = await auth.role_service.create_role(
        name="editor",
        permissions=["user:read", "user:update"],
        is_global=True
    )

    await auth.role_service.assign_role(user.id, role.id)

    # Check permissions
    has_read, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:read"
    )
    assert has_read is True

    has_update, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:update"
    )
    assert has_update is True

    has_delete, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:delete"
    )
    assert has_delete is False

@pytest.mark.asyncio
async def test_multiple_roles_permissions(auth):
    """Test permissions from multiple roles"""
    user = await auth.user_service.create_user(
        email="multi@example.com",
        password="password123",
        name="Multi Role"
    )

    # Create multiple roles
    role1 = await auth.role_service.create_role(
        name="role1",
        permissions=["user:read"],
        is_global=True
    )

    role2 = await auth.role_service.create_role(
        name="role2",
        permissions=["user:update"],
        is_global=True
    )

    # Assign both roles
    await auth.role_service.assign_role(user.id, role1.id)
    await auth.role_service.assign_role(user.id, role2.id)

    # User should have permissions from both roles
    has_read, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:read"
    )
    assert has_read is True

    has_update, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="user:update"
    )
    assert has_update is True
```

---

## Entity Hierarchy Testing

### Testing Tree Permissions (EnterpriseRBAC)

```python
# tests/integration/test_entity_hierarchy.py
import pytest
from outlabs_auth import EnterpriseRBAC

@pytest.mark.asyncio
async def test_tree_permission_inheritance(test_db):
    """Test tree permissions across hierarchy"""
    auth = EnterpriseRBAC(database=test_db)
    await auth.initialize()

    # Create hierarchy: platform > organization > department
    platform = await auth.entity_service.create_entity(
        name="platform",
        entity_type="platform",
        entity_class="STRUCTURAL"
    )

    org = await auth.entity_service.create_entity(
        name="organization",
        entity_type="organization",
        entity_class="STRUCTURAL",
        parent_entity_id=platform.id
    )

    dept = await auth.entity_service.create_entity(
        name="department",
        entity_type="department",
        entity_class="STRUCTURAL",
        parent_entity_id=org.id
    )

    # Create user with tree permission at organization level
    user = await auth.user_service.create_user(
        email="tree@example.com",
        password="password123",
        name="Tree User"
    )

    role = await auth.role_service.create_role(
        name="org_admin",
        permissions=["entity:update_tree"],
        entity_id=org.id
    )

    await auth.membership_service.add_member(
        entity_id=org.id,
        user_id=user.id,
        role_id=role.id
    )

    # User should be able to update department (child)
    has_perm, source = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="entity:update",
        entity_id=dept.id
    )

    assert has_perm is True
    assert "tree" in source.lower()

    # User should NOT be able to update platform (parent)
    has_perm_platform, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="entity:update",
        entity_id=platform.id
    )

    assert has_perm_platform is False

@pytest.mark.asyncio
async def test_entity_specific_permissions(test_db):
    """Test entity-specific permissions (non-tree)"""
    auth = EnterpriseRBAC(database=test_db)
    await auth.initialize()

    # Create entities
    parent = await auth.entity_service.create_entity(
        name="parent",
        entity_type="organization",
        entity_class="STRUCTURAL"
    )

    child = await auth.entity_service.create_entity(
        name="child",
        entity_type="department",
        entity_class="STRUCTURAL",
        parent_entity_id=parent.id
    )

    # Create user with non-tree permission at parent
    user = await auth.user_service.create_user(
        email="entity@example.com",
        password="password123",
        name="Entity User"
    )

    role = await auth.role_service.create_role(
        name="parent_editor",
        permissions=["entity:update"],  # Non-tree permission
        entity_id=parent.id
    )

    await auth.membership_service.add_member(
        entity_id=parent.id,
        user_id=user.id,
        role_id=role.id
    )

    # User can update parent
    has_perm_parent, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="entity:update",
        entity_id=parent.id
    )
    assert has_perm_parent is True

    # User CANNOT update child (no tree permission)
    has_perm_child, _ = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="entity:update",
        entity_id=child.id
    )
    assert has_perm_child is False
```

### Testing Closure Table Tree Permissions (v1.4 - DD-036)

```python
@pytest.mark.asyncio
async def test_closure_table_o1_query_performance(test_db):
    """Test closure table provides O(1) tree permission queries (20x faster)"""
    import time
    auth = EnterpriseRBAC(database=test_db)
    await auth.initialize()

    # Create deep hierarchy (10 levels)
    entities = []
    parent_id = None

    for i in range(10):
        entity = await auth.entity_service.create_entity(
            name=f"level_{i}",
            entity_type="department",
            entity_class="STRUCTURAL",
            parent_entity_id=parent_id
        )
        entities.append(entity)
        parent_id = entity.id

    # Create user with tree permission at root
    user = await auth.user_service.create_user(
        email="closure@example.com",
        password="password123",
        name="Closure Test"
    )

    role = await auth.role_service.create_role(
        name="root_admin",
        permissions=["entity:read_tree"],
        entity_id=entities[0].id  # Root level
    )

    await auth.membership_service.add_member(
        entity_id=entities[0].id,
        user_id=user.id,
        role_id=role.id
    )

    # Benchmark tree permission check at deepest level
    deepest_entity = entities[-1]

    start = time.perf_counter()

    has_perm, source = await auth.permission_service.check_permission(
        user_id=user.id,
        permission="entity:read",
        entity_id=deepest_entity.id
    )

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should complete in ~5ms (O(1) with closure table)
    assert elapsed_ms < 10  # Less than 10ms
    assert has_perm is True
    assert "tree" in source.lower()

    print(f"Tree permission check completed in {elapsed_ms:.2f}ms")

@pytest.mark.asyncio
async def test_closure_table_ancestry_query(test_db):
    """Test closure table efficiently finds all ancestors"""
    auth = EnterpriseRBAC(database=test_db)
    await auth.initialize()

    # Create hierarchy: root > org > dept > team
    root = await auth.entity_service.create_entity(
        name="root",
        entity_type="platform",
        entity_class="STRUCTURAL"
    )

    org = await auth.entity_service.create_entity(
        name="org",
        entity_type="organization",
        entity_class="STRUCTURAL",
        parent_entity_id=root.id
    )

    dept = await auth.entity_service.create_entity(
        name="dept",
        entity_type="department",
        entity_class="STRUCTURAL",
        parent_entity_id=org.id
    )

    team = await auth.entity_service.create_entity(
        name="team",
        entity_type="team",
        entity_class="STRUCTURAL",
        parent_entity_id=dept.id
    )

    # Query closure table for all ancestors of team
    from outlabs_auth.models import EntityClosureModel

    closures = await EntityClosureModel.find(
        EntityClosureModel.descendant_id == team.id,
        EntityClosureModel.depth > 0
    ).to_list()

    # Should find all 3 ancestors in single query
    assert len(closures) == 3

    ancestor_ids = [c.ancestor_id for c in closures]
    assert dept.id in ancestor_ids
    assert org.id in ancestor_ids
    assert root.id in ancestor_ids

    # Verify depths
    depth_map = {c.ancestor_id: c.depth for c in closures}
    assert depth_map[dept.id] == 1  # Immediate parent
    assert depth_map[org.id] == 2
    assert depth_map[root.id] == 3

@pytest.mark.asyncio
async def test_closure_table_descendant_query(test_db):
    """Test closure table efficiently finds all descendants"""
    auth = EnterpriseRBAC(database=test_db)
    await auth.initialize()

    # Create hierarchy
    root = await auth.entity_service.create_entity(
        name="root",
        entity_type="platform",
        entity_class="STRUCTURAL"
    )

    # Create multiple branches
    children = []
    for i in range(3):
        child = await auth.entity_service.create_entity(
            name=f"child_{i}",
            entity_type="department",
            entity_class="STRUCTURAL",
            parent_entity_id=root.id
        )
        children.append(child)

        # Each child has 2 grandchildren
        for j in range(2):
            await auth.entity_service.create_entity(
                name=f"grandchild_{i}_{j}",
                entity_type="team",
                entity_class="STRUCTURAL",
                parent_entity_id=child.id
            )

    # Query all descendants of root (should be 9 total: 3 children + 6 grandchildren)
    from outlabs_auth.models import EntityClosureModel

    closures = await EntityClosureModel.find(
        EntityClosureModel.ancestor_id == root.id,
        EntityClosureModel.depth > 0
    ).to_list()

    # Should find all 9 descendants in single query
    assert len(closures) == 9

    # Count by depth
    depth_1 = [c for c in closures if c.depth == 1]  # Direct children
    depth_2 = [c for c in closures if c.depth == 2]  # Grandchildren

    assert len(depth_1) == 3
    assert len(depth_2) == 6
```

---

## Authentication Testing

### Testing Login/Logout

```python
# tests/integration/test_authentication.py
import pytest
from outlabs_auth import SimpleRBAC
from outlabs_auth.exceptions import (
    InvalidCredentialsException,
    UserInactiveException
)

@pytest.mark.asyncio
async def test_successful_login(auth):
    """Test successful login"""
    user = await auth.user_service.create_user(
        email="login@example.com",
        password="SecurePassword123!",
        name="Login User"
    )

    tokens = await auth.auth_service.login(
        email="login@example.com",
        password="SecurePassword123!"
    )

    assert tokens.access_token is not None
    assert tokens.refresh_token is not None

@pytest.mark.asyncio
async def test_login_with_wrong_password(auth):
    """Test login fails with wrong password"""
    await auth.user_service.create_user(
        email="wrong@example.com",
        password="CorrectPassword123!",
        name="Wrong Password"
    )

    with pytest.raises(InvalidCredentialsException):
        await auth.auth_service.login(
            email="wrong@example.com",
            password="WrongPassword123!"
        )

@pytest.mark.asyncio
async def test_login_with_nonexistent_user(auth):
    """Test login fails with non-existent user"""
    with pytest.raises(InvalidCredentialsException):
        await auth.auth_service.login(
            email="nonexistent@example.com",
            password="password123"
        )

@pytest.mark.asyncio
async def test_login_with_inactive_user(auth):
    """Test login fails for inactive user"""
    user = await auth.user_service.create_user(
        email="inactive@example.com",
        password="password123",
        name="Inactive User"
    )

    # Deactivate user
    await auth.user_service.update_user(
        user_id=user.id,
        is_active=False
    )

    with pytest.raises(UserInactiveException):
        await auth.auth_service.login(
            email="inactive@example.com",
            password="password123"
        )

@pytest.mark.asyncio
async def test_token_refresh(auth):
    """Test refreshing access token"""
    user = await auth.user_service.create_user(
        email="refresh@example.com",
        password="password123",
        name="Refresh User"
    )

    # Initial login
    tokens = await auth.auth_service.login(
        email="refresh@example.com",
        password="password123"
    )

    # Refresh token
    new_tokens = await auth.auth_service.refresh_access_token(
        tokens.refresh_token
    )

    assert new_tokens.access_token != tokens.access_token
    assert new_tokens.refresh_token is not None

@pytest.mark.asyncio
async def test_logout(auth):
    """Test logout revokes tokens"""
    user = await auth.user_service.create_user(
        email="logout@example.com",
        password="password123",
        name="Logout User"
    )

    tokens = await auth.auth_service.login(
        email="logout@example.com",
        password="password123"
    )

    # Logout
    await auth.auth_service.logout(tokens.refresh_token)

    # Refresh should fail
    with pytest.raises(InvalidCredentialsException):
        await auth.auth_service.refresh_access_token(tokens.refresh_token)
```

---

## API Key Testing

### Testing API Key Creation

```python
# tests/integration/test_api_keys.py
import pytest
from outlabs_auth import SimpleRBAC
from outlabs_auth.services import APIKeyService
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_create_api_key(auth):
    """Test creating an API key"""
    user = await auth.user_service.create_user(
        email="apitest@example.com",
        password="password123",
        name="API Test"
    )

    # Create API key
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Test Service",
        permissions=["user:read", "entity:read"],
        environment="production",
        allowed_ips=["192.168.1.100"],
        rate_limit_per_minute=60,
        expires_at=datetime.now() + timedelta(days=90),
        created_by=user.id
    )

    # Verify raw key format
    assert raw_key.startswith("sk_prod_")
    assert len(raw_key) > 20  # At least prefix + some random data

    # Verify model (DD-028: 12-char prefixes)
    assert api_key_model.name == "Test Service"
    assert api_key_model.key_prefix == raw_key[:12]  # 12-char prefix (v1.4)
    assert len(api_key_model.key_prefix) == 12
    assert api_key_model.key_hash is not None  # Hash stored, not raw key
    assert "user:read" in api_key_model.permissions
    assert api_key_model.is_active is True
    assert api_key_model.environment == "production"

@pytest.mark.asyncio
async def test_api_key_environments(auth):
    """Test API key prefixes for different environments"""
    user = await auth.user_service.create_user(
        email="env@example.com",
        password="password123",
        name="Env Test"
    )

    # Production key
    prod_key, prod_model = await auth.api_key_service.create_api_key(
        name="Prod Key",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )
    assert prod_key.startswith("sk_prod_")

    # Staging key
    stag_key, stag_model = await auth.api_key_service.create_api_key(
        name="Staging Key",
        permissions=["user:read"],
        environment="staging",
        created_by=user.id
    )
    assert stag_key.startswith("sk_stag_")

    # Development key
    dev_key, dev_model = await auth.api_key_service.create_api_key(
        name="Dev Key",
        permissions=["user:read"],
        environment="development",
        created_by=user.id
    )
    assert dev_key.startswith("sk_dev_")

    # Test key
    test_key, test_model = await auth.api_key_service.create_api_key(
        name="Test Key",
        permissions=["user:read"],
        environment="test",
        created_by=user.id
    )
    assert test_key.startswith("sk_test_")
```

### Testing API Key Authentication

```python
@pytest.mark.asyncio
async def test_api_key_authentication(auth):
    """Test authenticating with API key"""
    user = await auth.user_service.create_user(
        email="authkey@example.com",
        password="password123",
        name="Auth Key"
    )

    # Create API key
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Auth Test",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    # Authenticate with API key
    validated_key = await auth.api_key_service.authenticate_api_key(raw_key)

    assert validated_key.id == api_key_model.id
    assert validated_key.name == "Auth Test"
    assert validated_key.is_active is True

@pytest.mark.asyncio
async def test_api_key_invalid_authentication(auth):
    """Test authentication fails with invalid API key"""
    from outlabs_auth.exceptions import InvalidAPIKeyException

    # Attempt to authenticate with invalid key
    with pytest.raises(InvalidAPIKeyException):
        await auth.api_key_service.authenticate_api_key("sk_prod_invalid_key")

@pytest.mark.asyncio
async def test_api_key_expired(auth):
    """Test expired API key fails authentication"""
    from outlabs_auth.exceptions import ExpiredAPIKeyException

    user = await auth.user_service.create_user(
        email="expired@example.com",
        password="password123",
        name="Expired Test"
    )

    # Create already-expired API key
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Expired Key",
        permissions=["user:read"],
        environment="production",
        expires_at=datetime.now() - timedelta(days=1),  # Expired yesterday
        created_by=user.id
    )

    # Authentication should fail
    with pytest.raises(ExpiredAPIKeyException):
        await auth.api_key_service.authenticate_api_key(raw_key)
```

### Testing API Key Hashing (argon2id)

```python
@pytest.mark.asyncio
async def test_api_key_hash_security(auth):
    """Test API key is hashed with argon2id, not stored as plaintext"""
    user = await auth.user_service.create_user(
        email="hash@example.com",
        password="password123",
        name="Hash Test"
    )

    # Create API key
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Hash Test",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    # Verify hash is NOT the raw key
    assert api_key_model.key_hash != raw_key

    # Verify hash starts with argon2id identifier
    assert api_key_model.key_hash.startswith("$argon2id$")

    # Verify raw key can be verified against hash
    from passlib.hash import argon2
    assert argon2.verify(raw_key, api_key_model.key_hash)

@pytest.mark.asyncio
async def test_api_key_hash_collision(auth):
    """Test different keys produce different hashes"""
    user = await auth.user_service.create_user(
        email="collision@example.com",
        password="password123",
        name="Collision Test"
    )

    # Create two API keys
    raw_key1, api_key1 = await auth.api_key_service.create_api_key(
        name="Key 1",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    raw_key2, api_key2 = await auth.api_key_service.create_api_key(
        name="Key 2",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    # Different raw keys
    assert raw_key1 != raw_key2

    # Different hashes (due to salt)
    assert api_key1.key_hash != api_key2.key_hash
```

### Testing API Key IP Whitelisting

```python
@pytest.mark.asyncio
async def test_api_key_ip_whitelist(auth):
    """Test API key IP whitelisting"""
    user = await auth.user_service.create_user(
        email="iptest@example.com",
        password="password123",
        name="IP Test"
    )

    # Create API key with IP whitelist
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="IP Restricted",
        permissions=["user:read"],
        environment="production",
        allowed_ips=["192.168.1.100", "10.0.1.0/24"],
        created_by=user.id
    )

    # Test IP validation
    assert await auth.api_key_service.check_ip_whitelist(
        api_key_model, "192.168.1.100"
    ) is True  # Exact match

    assert await auth.api_key_service.check_ip_whitelist(
        api_key_model, "10.0.1.50"
    ) is True  # CIDR range match

    assert await auth.api_key_service.check_ip_whitelist(
        api_key_model, "192.168.2.100"
    ) is False  # Not in whitelist

@pytest.mark.asyncio
async def test_api_key_no_ip_restriction(auth):
    """Test API key with no IP restrictions"""
    user = await auth.user_service.create_user(
        email="noip@example.com",
        password="password123",
        name="No IP Test"
    )

    # Create API key without IP restrictions
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="No IP Restriction",
        permissions=["user:read"],
        environment="production",
        allowed_ips=[],  # No restrictions
        created_by=user.id
    )

    # Any IP should be allowed
    assert await auth.api_key_service.check_ip_whitelist(
        api_key_model, "1.2.3.4"
    ) is True
```

### Testing API Key Rate Limiting

```python
@pytest.mark.asyncio
async def test_api_key_rate_limiting(auth):
    """Test API key rate limiting"""
    from outlabs_auth.exceptions import RateLimitExceededException

    user = await auth.user_service.create_user(
        email="rate@example.com",
        password="password123",
        name="Rate Test"
    )

    # Create API key with low rate limit
    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Rate Limited",
        permissions=["user:read"],
        environment="production",
        rate_limit_per_minute=5,  # Only 5 requests per minute
        created_by=user.id
    )

    # Make 5 requests (should succeed)
    for i in range(5):
        await auth.api_key_service.check_rate_limit(api_key_model)

    # 6th request should fail
    with pytest.raises(RateLimitExceededException):
        await auth.api_key_service.check_rate_limit(api_key_model)
```

### Testing API Key Temporary Locks (v1.4 - DD-028)

```python
@pytest.mark.asyncio
async def test_api_key_temporary_lock_after_failures(auth, redis):
    """Test API key gets 30-min temporary lock after 10 failed attempts in 10 minutes"""
    from outlabs_auth.exceptions import InvalidAPIKeyException, APIKeyLockedException
    import time

    user = await auth.user_service.create_user(
        email="lock@example.com",
        password="password123",
        name="Lock Test"
    )

    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Temporary Lock Test",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    # Simulate 10 failed attempts within 10-minute window
    # (In production, this would be detected by Redis tracking)
    for i in range(10):
        # Record failed attempt in Redis
        await redis.incr(f"api_key_failures:{api_key_model.key_prefix}")
        await redis.expire(f"api_key_failures:{api_key_model.key_prefix}", 600)  # 10 min

    # After 10 failures, key should be temporarily locked
    await redis.setex(f"api_key_lock:{api_key_model.key_prefix}", 1800, "1")  # 30 min lock

    # Attempt to authenticate with locked key
    with pytest.raises(APIKeyLockedException) as exc_info:
        await auth.api_key_service.authenticate_api_key(raw_key)

    assert "temporarily locked" in str(exc_info.value).lower()
    assert "30 minutes" in str(exc_info.value)

    # Verify key is still active (not permanently revoked)
    api_key_model = await auth.api_key_service.get_api_key(api_key_model.id)
    assert api_key_model.is_active is True  # Still active, just locked

    # After lock expires (30 min), key should work again
    await redis.delete(f"api_key_lock:{api_key_model.key_prefix}")
    await redis.delete(f"api_key_failures:{api_key_model.key_prefix}")

    # Should authenticate successfully now
    validated_key = await auth.api_key_service.authenticate_api_key(raw_key)
    assert validated_key.id == api_key_model.id
```

### Testing Redis Counters for API Keys (v1.4 - DD-033)

```python
@pytest.mark.asyncio
async def test_api_key_redis_usage_counters(auth, redis):
    """Test API key usage tracking with Redis counters (99%+ DB write reduction)"""
    user = await auth.user_service.create_user(
        email="counter@example.com",
        password="password123",
        name="Counter Test"
    )

    raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Counter Test",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    # Make 100 API calls
    for i in range(100):
        await auth.api_key_service.authenticate_api_key(raw_key)

    # Redis counter should be updated (not DB yet)
    counter_key = f"api_key_usage:{api_key_model.id}"
    redis_count = await redis.get(counter_key)
    assert int(redis_count) == 100

    # Database should still show 0 or small number (not synced yet)
    api_key_model = await auth.api_key_service.get_api_key(api_key_model.id)
    assert api_key_model.usage_count < 100  # Not synced to DB yet

    # Trigger background sync (normally runs every 5 minutes)
    await auth.api_key_service.sync_usage_counters_from_redis()

    # Now DB should be updated
    api_key_model = await auth.api_key_service.get_api_key(api_key_model.id)
    assert api_key_model.usage_count == 100
    assert api_key_model.last_used_at is not None

@pytest.mark.asyncio
async def test_api_key_counter_background_sync(auth, redis):
    """Test automatic background sync of Redis counters to database"""
    import asyncio

    user = await auth.user_service.create_user(
        email="sync@example.com",
        password="password123",
        name="Sync Test"
    )

    # Create multiple API keys
    keys = []
    for i in range(5):
        raw_key, api_key = await auth.api_key_service.create_api_key(
            name=f"Key {i}",
            permissions=["user:read"],
            environment="production",
            created_by=user.id
        )
        keys.append((raw_key, api_key))

        # Simulate usage
        for _ in range(50):
            await redis.incr(f"api_key_usage:{api_key.id}")

    # Start background sync task
    sync_task = asyncio.create_task(
        auth.api_key_service.run_background_sync(interval=5)
    )

    # Wait for sync
    await asyncio.sleep(6)

    # Cancel background task
    sync_task.cancel()

    # Verify all counters synced to DB
    for raw_key, api_key in keys:
        refreshed = await auth.api_key_service.get_api_key(api_key.id)
        assert refreshed.usage_count == 50
```

### Testing API Key Rotation

```python
@pytest.mark.asyncio
async def test_api_key_rotation(auth):
    """Test rotating an API key"""
    user = await auth.user_service.create_user(
        email="rotate@example.com",
        password="password123",
        name="Rotate Test"
    )

    # Create original API key
    old_raw_key, old_api_key = await auth.api_key_service.create_api_key(
        name="Original Key",
        permissions=["user:read", "entity:read"],
        environment="production",
        allowed_ips=["192.168.1.100"],
        created_by=user.id
    )

    # Rotate the key
    new_raw_key, new_api_key = await auth.api_key_service.rotate_api_key(
        old_key_id=old_api_key.id
    )

    # New key should have same permissions and settings
    assert new_api_key.permissions == old_api_key.permissions
    assert new_api_key.allowed_ips == old_api_key.allowed_ips
    assert new_api_key.environment == old_api_key.environment

    # New key should be different
    assert new_raw_key != old_raw_key
    assert new_api_key.id != old_api_key.id

    # Old key should be marked for revocation (but may have grace period)
    # Check scheduled revocation
```

### Testing Entity-Scoped API Keys (EnterpriseRBAC)

```python
@pytest.mark.asyncio
async def test_entity_scoped_api_key(test_db):
    """Test API key scoped to specific entity"""
    from outlabs_auth import EnterpriseRBAC

    auth = EnterpriseRBAC(database=test_db)
    await auth.initialize()

    # Create hierarchy
    org = await auth.entity_service.create_entity(
        name="organization",
        entity_type="organization",
        entity_class="STRUCTURAL"
    )

    dept = await auth.entity_service.create_entity(
        name="department",
        entity_type="department",
        entity_class="STRUCTURAL",
        parent_entity_id=org.id
    )

    user = await auth.user_service.create_user(
        email="entity_api@example.com",
        password="password123",
        name="Entity API Test"
    )

    # Create entity-scoped API key
    raw_key, api_key = await auth.api_key_service.create_api_key(
        name="Department Key",
        permissions=["entity:read", "entity:update"],
        environment="production",
        entity_id=dept.id,  # Scoped to department
        created_by=user.id
    )

    # Verify entity scope
    assert api_key.entity_id == dept.id

    # Check permission in entity context
    context = await auth.multi_source_auth.authenticate_api_key_to_context(raw_key)

    has_perm = await auth.permission_service.check_permission(
        context=context,
        permission="entity:read",
        entity_id=dept.id
    )

    assert has_perm is True

@pytest.mark.asyncio
async def test_entity_scoped_api_key_tree_permissions(test_db):
    """Test entity-scoped API key with tree permissions"""
    from outlabs_auth import EnterpriseRBAC

    auth = EnterpriseRBAC(database=test_db)
    await auth.initialize()

    # Create hierarchy: org > dept > team
    org = await auth.entity_service.create_entity(
        name="organization",
        entity_type="organization",
        entity_class="STRUCTURAL"
    )

    dept = await auth.entity_service.create_entity(
        name="department",
        entity_type="department",
        entity_class="STRUCTURAL",
        parent_entity_id=org.id
    )

    team = await auth.entity_service.create_entity(
        name="team",
        entity_type="team",
        entity_class="STRUCTURAL",
        parent_entity_id=dept.id
    )

    user = await auth.user_service.create_user(
        email="tree_api@example.com",
        password="password123",
        name="Tree API Test"
    )

    # Create API key with tree permissions at department level
    raw_key, api_key = await auth.api_key_service.create_api_key(
        name="Dept Tree Key",
        permissions=["entity:read_tree"],  # Tree permission
        environment="production",
        entity_id=dept.id,
        inherit_from_tree=True,  # Enable tree permissions
        created_by=user.id
    )

    # API key should have access to team (descendant)
    context = await auth.multi_source_auth.authenticate_api_key_to_context(raw_key)

    has_perm = await auth.permission_service.check_permission(
        context=context,
        permission="entity:read",
        entity_id=team.id
    )

    assert has_perm is True  # Tree permission applies

    # Should NOT have access to org (parent)
    has_perm_parent = await auth.permission_service.check_permission(
        context=context,
        permission="entity:read",
        entity_id=org.id
    )

    assert has_perm_parent is False
```

---

## Multi-Source Authentication Testing

### Testing Auth Source Priority Chain

```python
# tests/integration/test_multi_source_auth.py
import pytest
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.models import AuthSource, AuthContext
from fastapi import Request

@pytest.mark.asyncio
async def test_auth_source_priority_chain(auth, redis):
    """Test priority: Superuser > Service > API Key > User > Anonymous"""
    deps = AuthDeps(auth=auth, redis=redis)

    # Create test user with token
    user = await auth.user_service.create_user(
        email="priority@example.com",
        password="password123",
        name="Priority Test"
    )
    user_tokens = await auth.auth_service.login(
        email="priority@example.com",
        password="password123"
    )

    # Create API key
    api_raw_key, api_key_model = await auth.api_key_service.create_api_key(
        name="Priority Test",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    # Mock request with all auth headers
    class MockRequest:
        def __init__(self):
            self.headers = {
                "x-superuser-token": "superuser_token",
                "x-service-token": "service_token",
                "x-api-key": api_raw_key,
                "authorization": f"Bearer {user_tokens.access_token}"
            }

    request = MockRequest()

    # Get context (should use superuser - highest priority)
    context = await deps.get_context(
        request=request,
        x_superuser_token="superuser_token",
        x_service_token="service_token",
        x_api_key=api_raw_key,
        authorization=f"Bearer {user_tokens.access_token}"
    )

    # Should use superuser (highest priority)
    assert context.source == AuthSource.SUPERUSER

@pytest.mark.asyncio
async def test_api_key_auth_source(auth, redis):
    """Test authentication with API key source"""
    user = await auth.user_service.create_user(
        email="apiauth@example.com",
        password="password123",
        name="API Auth"
    )

    raw_key, api_key = await auth.api_key_service.create_api_key(
        name="Source Test",
        permissions=["user:read", "user:create"],
        environment="production",
        created_by=user.id
    )

    # Authenticate with API key only
    deps = AuthDeps(auth=auth, redis=redis)

    class MockRequest:
        def __init__(self):
            self.headers = {"x-api-key": raw_key}

    context = await deps.get_context(
        request=MockRequest(),
        x_api_key=raw_key
    )

    # Verify context
    assert context.source == AuthSource.API_KEY
    assert context.identity == api_key.key_prefix
    assert "user:read" in context.permissions
    assert "user:create" in context.permissions

@pytest.mark.asyncio
async def test_user_jwt_auth_source(auth, redis):
    """Test authentication with JWT source"""
    user = await auth.user_service.create_user(
        email="jwtauth@example.com",
        password="password123",
        name="JWT Auth"
    )

    tokens = await auth.auth_service.login(
        email="jwtauth@example.com",
        password="password123"
    )

    # Authenticate with JWT only
    deps = AuthDeps(auth=auth, redis=redis)

    class MockRequest:
        def __init__(self):
            self.headers = {"authorization": f"Bearer {tokens.access_token}"}

    context = await deps.get_context(
        request=MockRequest(),
        authorization=f"Bearer {tokens.access_token}"
    )

    # Verify context
    assert context.source == AuthSource.USER
    assert context.identity == user.email

@pytest.mark.asyncio
async def test_anonymous_auth_source(auth, redis):
    """Test anonymous access"""
    deps = AuthDeps(auth=auth, redis=redis)

    class MockRequest:
        def __init__(self):
            self.headers = {}

    # No auth headers
    context = await deps.get_context(request=MockRequest())

    # Verify anonymous context
    assert context.source == AuthSource.ANONYMOUS
    assert context.identity == "anonymous"
    assert context.permissions == []
    assert context.is_superuser is False
```

### Testing AuthContext Permissions

```python
@pytest.mark.asyncio
async def test_auth_context_has_permission(auth):
    """Test AuthContext.has_permission() method"""
    # Create context with permissions
    context = AuthContext(
        source=AuthSource.API_KEY,
        identity="sk_prod_test",
        permissions=["user:read", "user:create"],
        is_superuser=False
    )

    # Check permissions
    assert context.has_permission("user:read") is True
    assert context.has_permission("user:create") is True
    assert context.has_permission("user:delete") is False

@pytest.mark.asyncio
async def test_auth_context_superuser_bypass(auth):
    """Test superuser bypasses permission checks"""
    # Superuser context
    context = AuthContext(
        source=AuthSource.SUPERUSER,
        identity="superuser",
        permissions=[],  # No explicit permissions
        is_superuser=True
    )

    # Superuser has all permissions
    assert context.has_permission("user:read") is True
    assert context.has_permission("user:delete") is True
    assert context.has_permission("entity:create_tree") is True
```

### Testing Multi-Source Auth in FastAPI

```python
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_multi_source_auth_in_route(auth, redis):
    """Test multi-source auth with FastAPI routes"""
    app = FastAPI()
    deps = AuthDeps(auth=auth, redis=redis)

    @app.get("/test")
    async def test_route(context: AuthContext = Depends(deps.get_context)):
        return {
            "source": context.source.value,
            "identity": context.identity,
            "permissions": context.permissions
        }

    client = TestClient(app)

    # Create API key
    user = await auth.user_service.create_user(
        email="route@example.com",
        password="password123",
        name="Route Test"
    )

    raw_key, api_key = await auth.api_key_service.create_api_key(
        name="Route Test",
        permissions=["user:read"],
        environment="production",
        created_by=user.id
    )

    # Make request with API key
    response = client.get("/test", headers={"X-API-Key": raw_key})

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "API_KEY"
    assert "user:read" in data["permissions"]
```

### Testing JWT Service Tokens (v1.4 - DD-034)

```python
@pytest.mark.asyncio
async def test_jwt_service_token_authentication(auth):
    """Test stateless JWT service token authentication (~0.5ms, zero DB hits)"""
    from outlabs_auth.services import JWTServiceTokenService

    # Create service token
    service_token = await auth.jwt_service_token_service.create_service_token(
        service_name="payment-processor",
        permissions=["payment:create", "payment:read", "invoice:generate"],
        expires_in_days=365
    )

    # Validate service token (no DB lookup, pure JWT validation)
    import time
    start = time.perf_counter()

    context = await auth.jwt_service_token_service.validate_service_token(service_token)

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should be extremely fast (~0.5ms)
    assert elapsed_ms < 1.0  # Less than 1ms

    # Verify context
    assert context.source == AuthSource.SERVICE_TOKEN
    assert context.identity == "service:payment-processor"
    assert "payment:create" in context.permissions
    assert "payment:read" in context.permissions
    assert "invoice:generate" in context.permissions

@pytest.mark.asyncio
async def test_jwt_service_token_in_fastapi(auth, redis):
    """Test JWT service token authentication in FastAPI routes"""
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient

    app = FastAPI()
    deps = AuthDeps(auth=auth, redis=redis)

    @app.post("/payments")
    async def create_payment(context: AuthContext = Depends(deps.require_permission("payment:create"))):
        return {
            "message": "Payment created",
            "service": context.identity
        }

    # Create service token
    service_token = await auth.jwt_service_token_service.create_service_token(
        service_name="payment-processor",
        permissions=["payment:create"],
        expires_in_days=365
    )

    client = TestClient(app)

    # Make request with service token
    response = client.post(
        "/payments",
        headers={"X-Service-Token": service_token}
    )

    assert response.status_code == 200
    data = response.json()
    assert "service:payment-processor" in data["service"]

@pytest.mark.asyncio
async def test_jwt_service_token_expiration(auth):
    """Test JWT service token expiration handling"""
    from datetime import datetime, timedelta
    import jwt

    # Create expired service token (manually for testing)
    payload = {
        "sub": "service:test-service",
        "permissions": ["test:read"],
        "exp": datetime.utcnow() - timedelta(days=1),  # Expired yesterday
        "iat": datetime.utcnow() - timedelta(days=2)
    }

    expired_token = jwt.encode(payload, auth.config.secret_key, algorithm="HS256")

    # Validation should fail
    from outlabs_auth.exceptions import ExpiredTokenException

    with pytest.raises(ExpiredTokenException):
        await auth.jwt_service_token_service.validate_service_token(expired_token)

@pytest.mark.asyncio
async def test_jwt_service_token_no_db_queries(auth, monkeypatch):
    """Test JWT service token validation performs zero database queries"""
    db_queries = []

    # Mock database to track queries
    original_find = auth.database.find

    async def tracked_find(*args, **kwargs):
        db_queries.append(("find", args, kwargs))
        return await original_find(*args, **kwargs)

    monkeypatch.setattr(auth.database, "find", tracked_find)

    # Create and validate service token
    service_token = await auth.jwt_service_token_service.create_service_token(
        service_name="test-service",
        permissions=["test:read"],
        expires_in_days=365
    )

    # Clear query log
    db_queries.clear()

    # Validate token
    context = await auth.jwt_service_token_service.validate_service_token(service_token)

    # Should have zero DB queries
    assert len(db_queries) == 0
    assert context.source == AuthSource.SERVICE_TOKEN
```

---

## Mocking & Fixtures

### Pytest Fixtures

```python
# conftest.py
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from outlabs_auth import SimpleRBAC, EnterpriseRBAC
from outlabs_auth.models import UserModel, RoleModel, EntityModel

@pytest_asyncio.fixture
async def test_user(auth) -> UserModel:
    """Create a test user"""
    user = await auth.user_service.create_user(
        email="testuser@example.com",
        password="TestPassword123!",
        name="Test User"
    )
    return user

@pytest_asyncio.fixture
async def test_role(auth) -> RoleModel:
    """Create a test role"""
    role = await auth.role_service.create_role(
        name="test_role",
        display_name="Test Role",
        permissions=["user:read", "user:create"],
        is_global=True
    )
    return role

@pytest_asyncio.fixture
async def test_entity(auth) -> EntityModel:
    """Create a test entity (EnterpriseRBAC only)"""
    if isinstance(auth, EnterpriseRBAC):
        entity = await auth.entity_service.create_entity(
            name="test_entity",
            entity_type="organization",
            entity_class="STRUCTURAL"
        )
        return entity
    return None

@pytest_asyncio.fixture
async def authenticated_user(auth, test_user):
    """Create authenticated user with tokens"""
    tokens = await auth.auth_service.login(
        email=test_user.email,
        password="TestPassword123!"
    )
    test_user.tokens = tokens
    return test_user

@pytest_asyncio.fixture
async def admin_user(auth):
    """Create admin user with admin role"""
    user = await auth.user_service.create_user(
        email="admin@example.com",
        password="AdminPassword123!",
        name="Admin User"
    )

    role = await auth.role_service.create_role(
        name="admin",
        display_name="Administrator",
        permissions=[
            "user:create", "user:read", "user:update", "user:delete",
            "role:create", "role:read", "role:update", "role:delete",
        ],
        is_global=True
    )

    await auth.role_service.assign_role(user.id, role.id)
    return user
```

### Mocking Dependencies

```python
# tests/unit/test_with_mocks.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from outlabs_auth.services import AuthService

@pytest.mark.asyncio
async def test_login_with_mocked_database():
    """Test login with mocked database"""
    # Mock database
    mock_db = AsyncMock()

    # Mock user lookup
    mock_user = MagicMock()
    mock_user.email = "mock@example.com"
    mock_user.hashed_password = "hashed_password"
    mock_user.is_active = True

    # Create service with mocked dependencies
    with patch('outlabs_auth.services.UserService.get_user_by_email', return_value=mock_user):
        with patch('outlabs_auth.security.verify_password', return_value=True):
            auth_service = AuthService(database=mock_db)

            tokens = await auth_service.login(
                email="mock@example.com",
                password="password123"
            )

            assert tokens.access_token is not None
```

---

## Performance Testing

### Load Testing

```python
# tests/performance/test_load.py
import pytest
import asyncio
import time
from outlabs_auth import SimpleRBAC

@pytest.mark.asyncio
async def test_concurrent_logins(auth):
    """Test performance under concurrent logins"""
    # Create test users
    users = []
    for i in range(100):
        user = await auth.user_service.create_user(
            email=f"loadtest{i}@example.com",
            password="password123",
            name=f"Load Test {i}"
        )
        users.append(user)

    # Concurrent login
    start_time = time.time()

    async def login_user(email):
        return await auth.auth_service.login(
            email=email,
            password="password123"
        )

    tasks = [login_user(user.email) for user in users]
    results = await asyncio.gather(*tasks)

    end_time = time.time()
    duration = end_time - start_time

    # Assertions
    assert len(results) == 100
    assert all(r.access_token for r in results)
    assert duration < 10  # Should complete within 10 seconds

    print(f"100 concurrent logins completed in {duration:.2f} seconds")
    print(f"Average: {duration/100*1000:.2f}ms per login")

@pytest.mark.asyncio
async def test_permission_check_performance(auth):
    """Test permission checking performance"""
    # Setup
    user = await auth.user_service.create_user(
        email="perftest@example.com",
        password="password123",
        name="Perf Test"
    )

    role = await auth.role_service.create_role(
        name="perf_role",
        permissions=["user:read", "user:create"],
        is_global=True
    )

    await auth.role_service.assign_role(user.id, role.id)

    # Benchmark
    iterations = 1000
    start_time = time.time()

    for _ in range(iterations):
        await auth.permission_service.check_permission(
            user_id=user.id,
            permission="user:read"
        )

    end_time = time.time()
    duration = end_time - start_time
    avg_ms = (duration / iterations) * 1000

    print(f"{iterations} permission checks in {duration:.2f}s")
    print(f"Average: {avg_ms:.2f}ms per check")

    # Should be fast
    assert avg_ms < 10  # Less than 10ms per check
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      mongodb:
        image: mongo:6.0
        ports:
          - 27017:27017
        options: >-
          --health-cmd "mongosh --eval 'db.adminCommand({ping: 1})'"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          pytest --cov=outlabs_auth --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true
```

### Pytest Configuration

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --verbose
    --strict-markers
    --cov=outlabs_auth
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90

markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow tests
    security: Security-related tests
```

---

## Test Coverage

### Measuring Coverage

```bash
# Run tests with coverage
pytest --cov=outlabs_auth --cov-report=html

# View coverage report
open htmlcov/index.html

# Coverage by file
pytest --cov=outlabs_auth --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=outlabs_auth --cov-fail-under=90
```

### Coverage Targets

| Component | Target Coverage |
|-----------|-----------------|
| Services | 95%+ |
| Models | 90%+ |
| Routes | 85%+ |
| Utilities | 90%+ |
| Overall | 90%+ |

### Excluding Files

```python
# .coveragerc
[run]
omit =
    */tests/*
    */migrations/*
    */conftest.py
    */__init__.py
```

---

## Testing Patterns

### Pattern: Arrange-Act-Assert

```python
@pytest.mark.asyncio
async def test_create_user(auth):
    # ARRANGE: Set up test data
    email = "test@example.com"
    password = "password123"
    name = "Test User"

    # ACT: Perform the action
    user = await auth.user_service.create_user(
        email=email,
        password=password,
        name=name
    )

    # ASSERT: Verify the results
    assert user.email == email
    assert user.name == name
    assert user.is_active is True
```

### Pattern: Given-When-Then

```python
@pytest.mark.asyncio
async def test_user_login_flow(auth):
    # GIVEN: A user exists
    user = await auth.user_service.create_user(
        email="user@example.com",
        password="password123",
        name="User"
    )

    # WHEN: User logs in
    tokens = await auth.auth_service.login(
        email="user@example.com",
        password="password123"
    )

    # THEN: Tokens are returned
    assert tokens.access_token is not None
    assert tokens.refresh_token is not None
```

### Pattern: Parameterized Tests

```python
@pytest.mark.parametrize("email,password,should_succeed", [
    ("valid@example.com", "SecurePassword123!", True),
    ("invalid@example.com", "weak", False),
    ("", "password123", False),
    ("user@example.com", "", False),
])
@pytest.mark.asyncio
async def test_user_creation_validation(auth, email, password, should_succeed):
    """Test user creation with various inputs"""
    if should_succeed:
        user = await auth.user_service.create_user(
            email=email,
            password=password,
            name="Test"
        )
        assert user.email == email
    else:
        with pytest.raises(Exception):
            await auth.user_service.create_user(
                email=email,
                password=password,
                name="Test"
            )
```

---

## Best Practices

### Do's ✅

- Use async fixtures and tests
- Clean up after each test
- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies
- Maintain high coverage (90%+)
- Use parameterized tests for multiple scenarios
- Test permission boundaries
- Test entity hierarchy thoroughly

### Don'ts ❌

- Don't share state between tests
- Don't use sleep() for timing
- Don't skip cleanup
- Don't test implementation details
- Don't rely on test execution order
- Don't commit sensitive test data
- Don't use production database

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.4 | 2025-01-14 | Updated all code examples for v1.4: replaced `MultiSourceDeps` with `AuthDeps` (DD-035); updated API key prefix tests to 12 characters (DD-028); replaced permanent revocation with temporary lock testing (DD-028); added Redis counter testing (DD-033); added JWT service token testing (DD-034); added closure table tree permission tests (DD-036) |
| 1.3 | 2025-01-14 | Added API key testing section with comprehensive examples |
| 1.2 | 2025-01-14 | Added multi-source authentication testing section |
| 1.1 | 2025-01-14 | Enhanced entity hierarchy testing examples |
| 1.0 | 2025-01-14 | Initial testing guide |

---

**Last Updated**: 2025-01-14 (v1.4 - Comprehensive updates for unified architecture, closure table, Redis patterns, JWT service tokens)
**Next Review**: Quarterly
**Owner**: Engineering Team
