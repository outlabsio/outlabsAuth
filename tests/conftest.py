"""
Pytest fixtures for OutlabsAuth testing

Provides shared fixtures for database connections, auth instances,
and test data used across all test files.
"""
import pytest
import asyncio
from typing import AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from outlabs_auth import SimpleRBAC
from outlabs_auth.models.user import UserModel, UserStatus
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.core.config import AuthConfig


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def mongo_client() -> AsyncGenerator[AsyncIOMotorClient, None]:
    """
    Create MongoDB client for testing.

    Scope: function (new client for each test to avoid event loop issues)

    Usage:
        async def test_something(mongo_client):
            db = mongo_client["test_db"]
    """
    client = AsyncIOMotorClient("mongodb://localhost:27017")

    # Test connection
    try:
        await client.admin.command("ping")
    except Exception as e:
        pytest.fail(f"Cannot connect to MongoDB: {e}\nMake sure MongoDB is running on localhost:27017")

    yield client

    # Cleanup
    client.close()


@pytest.fixture
async def test_db(mongo_client: AsyncIOMotorClient) -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    Provide a clean test database for each test.

    Scope: function (fresh database for each test)

    The database is automatically dropped after each test to ensure isolation.

    Usage:
        async def test_something(test_db):
            # test_db is empty and ready to use
            pass
    """
    db_name = "outlabs_auth_test"
    db = mongo_client[db_name]

    yield db

    # Cleanup: Drop the entire test database
    await mongo_client.drop_database(db_name)


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_secret_key() -> str:
    """Test JWT secret key."""
    return "test-secret-key-do-not-use-in-production-12345678"


@pytest.fixture
def auth_config(test_secret_key: str) -> AuthConfig:
    """
    Test authentication configuration.

    Usage:
        def test_something(auth_config):
            assert auth_config.secret_key == "test-secret-key..."
    """
    return AuthConfig(
        secret_key=test_secret_key,
        algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
        password_min_length=8,
        require_special_char=True,
        require_uppercase=True,
        require_digit=True,
        max_login_attempts=5,
        lockout_duration_minutes=30,
    )


# ============================================================================
# Auth Instance Fixtures
# ============================================================================

@pytest.fixture
async def auth(test_db: AsyncIOMotorDatabase, test_secret_key: str) -> AsyncGenerator[SimpleRBAC, None]:
    """
    Initialized SimpleRBAC instance for testing.

    Scope: function (fresh instance for each test)

    The auth instance is fully initialized with database collections.

    Usage:
        async def test_something(auth: SimpleRBAC):
            user = await auth.user_service.create_user(...)
    """
    auth_instance = SimpleRBAC(
        database=test_db,
        secret_key=test_secret_key,
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
    )

    # Initialize (creates collections and indexes)
    await auth_instance.initialize()

    yield auth_instance


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def test_password() -> str:
    """
    Standard test password that meets all requirements.

    Usage:
        async def test_login(auth, test_user, test_password):
            user, tokens = await auth.auth_service.login(
                email=test_user.email,
                password=test_password
            )
    """
    return "TestPass123!"


@pytest.fixture
async def test_user(auth: SimpleRBAC, test_password: str) -> UserModel:
    """
    Pre-created test user.

    Credentials:
    - Email: test@example.com
    - Password: TestPass123! (from test_password fixture)
    - Status: ACTIVE
    - Superuser: False

    Usage:
        async def test_something(test_user: UserModel):
            assert test_user.email == "test@example.com"
    """
    user = await auth.user_service.create_user(
        email="test@example.com",
        password=test_password,
        first_name="Test",
        last_name="User",
    )
    return user


@pytest.fixture
async def test_admin(auth: SimpleRBAC, test_password: str) -> UserModel:
    """
    Pre-created admin user (superuser).

    Credentials:
    - Email: admin@example.com
    - Password: TestPass123! (from test_password fixture)
    - Status: ACTIVE
    - Superuser: True

    Usage:
        async def test_admin_action(test_admin: UserModel):
            assert test_admin.is_superuser is True
    """
    admin = await auth.user_service.create_user(
        email="admin@example.com",
        password=test_password,
        first_name="Admin",
        last_name="User",
        is_superuser=True,
    )
    return admin


@pytest.fixture
async def test_role(auth: SimpleRBAC) -> RoleModel:
    """
    Pre-created test role with basic permissions.

    Role details:
    - Name: "test_role"
    - Display name: "Test Role"
    - Permissions: ["user:read", "user:create"]

    Usage:
        async def test_role_permissions(test_role: RoleModel):
            assert "user:read" in test_role.permissions
    """
    role = await auth.role_service.create_role(
        name="test_role",
        display_name="Test Role",
        description="A test role with basic permissions",
        permissions=["user:read", "user:create"],
        is_global=True,
    )
    return role


@pytest.fixture
async def test_permissions(auth: SimpleRBAC) -> list[PermissionModel]:
    """
    Pre-created test permissions.

    Creates the following permissions:
    - user:create - Create users
    - user:read - Read users
    - user:update - Update users
    - user:delete - Delete users

    Usage:
        async def test_with_permissions(test_permissions):
            assert len(test_permissions) == 4
    """
    permissions = []

    perm_definitions = [
        ("user:create", "Create Users", "Can create new users"),
        ("user:read", "Read Users", "Can view user information"),
        ("user:update", "Update Users", "Can modify user information"),
        ("user:delete", "Delete Users", "Can delete users"),
    ]

    for name, display_name, description in perm_definitions:
        perm = await auth.permission_service.create_permission(
            name=name,
            display_name=display_name,
            description=description,
            is_system=False,
        )
        permissions.append(perm)

    return permissions


@pytest.fixture
async def test_user_with_role(
    auth: SimpleRBAC,
    test_password: str,
    test_role: RoleModel
) -> UserModel:
    """
    Pre-created user with role assigned.

    The user has the test_role assigned via metadata.

    Usage:
        async def test_user_permissions(test_user_with_role: UserModel):
            # User has permissions from test_role
            pass
    """
    user = await auth.user_service.create_user(
        email="user_with_role@example.com",
        password=test_password,
        first_name="User",
        last_name="WithRole",
    )

    # Assign role via metadata (SimpleRBAC approach)
    user.metadata["role_ids"] = [str(test_role.id)]
    await user.save()

    return user


# ============================================================================
# FastAPI Fixtures (for dependency testing)
# ============================================================================

@pytest.fixture
def test_access_token(auth: SimpleRBAC, test_user: UserModel) -> str:
    """
    Generate a valid access token for test_user.

    Usage:
        def test_protected_route(test_access_token):
            headers = {"Authorization": f"Bearer {test_access_token}"}
            response = client.get("/protected", headers=headers)
    """
    from outlabs_auth.utils.jwt import create_access_token
    from datetime import timedelta

    token = create_access_token(
        data={"sub": str(test_user.id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        expires_delta=timedelta(minutes=15),
    )
    return token


@pytest.fixture
def test_expired_token(auth: SimpleRBAC, test_user: UserModel) -> str:
    """
    Generate an expired access token for testing.

    Usage:
        def test_expired_token_rejected(test_expired_token):
            headers = {"Authorization": f"Bearer {test_expired_token}"}
            response = client.get("/protected", headers=headers)
            assert response.status_code == 401
    """
    from outlabs_auth.utils.jwt import create_access_token
    from datetime import timedelta

    token = create_access_token(
        data={"sub": str(test_user.id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        expires_delta=timedelta(seconds=-1),  # Already expired
    )
    return token


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def sample_user_data(test_password: str) -> dict:
    """
    Sample user data for testing user creation.

    Usage:
        async def test_create_user(auth, sample_user_data):
            user = await auth.user_service.create_user(**sample_user_data)
    """
    return {
        "email": "newuser@example.com",
        "password": test_password,
        "first_name": "New",
        "last_name": "User",
    }


@pytest.fixture
def invalid_user_data() -> dict:
    """
    Invalid user data for testing validation.

    Password is too weak (no special characters).

    Usage:
        async def test_weak_password_rejected(auth, invalid_user_data):
            with pytest.raises(InvalidPasswordError):
                await auth.user_service.create_user(**invalid_user_data)
    """
    return {
        "email": "invalid@example.com",
        "password": "weak",  # Doesn't meet requirements
        "first_name": "Invalid",
        "last_name": "User",
    }
