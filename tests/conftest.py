"""
Pytest fixtures for OutlabsAuth testing

Provides shared fixtures for database connections, auth instances,
and test data used across all test files.

Updated for PostgreSQL/SQLAlchemy.
"""

import asyncio
import os
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from outlabs_auth import SimpleRBAC
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User

# ============================================================================
# Pytest Configuration
# ============================================================================

# Test database URL - uses a separate test database
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test",
)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# ============================================================================
# Event Loop Fixture
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """
    Create async engine for testing.

    Creates all tables before tests and drops them after.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for each test.

    Each test gets a fresh session that's rolled back after the test.
    """
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


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


@pytest_asyncio.fixture
async def auth(test_secret_key: str) -> AsyncGenerator[SimpleRBAC, None]:
    """
    Initialized SimpleRBAC instance for testing.

    Creates a fresh database for each test.
    """
    from outlabs_auth.observability import ObservabilityConfig

    # Disable observability for tests
    obs_config = ObservabilityConfig(
        enabled=False,
        log_format="text",
        log_level="ERROR",
    )

    auth_instance = SimpleRBAC(
        database_url=TEST_DATABASE_URL,
        secret_key=test_secret_key,
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
        enable_token_cleanup=False,
        observability_config=obs_config,
    )

    # Initialize (creates tables)
    await auth_instance.initialize()

    # Create tables
    async with auth_instance.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield auth_instance

    # Cleanup: drop all tables
    async with auth_instance.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await auth_instance.shutdown()


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_password() -> str:
    """
    Standard test password that meets all requirements.
    """
    return "TestPass123!"


@pytest_asyncio.fixture
async def test_user(auth: SimpleRBAC, test_password: str) -> User:
    """
    Pre-created test user.

    Credentials:
    - Email: test@example.com
    - Password: TestPass123!
    - Status: ACTIVE
    - Superuser: False
    """
    async with auth.get_session() as session:
        user = await auth.user_service.create_user(
            session,
            email="test@example.com",
            password=test_password,
            first_name="Test",
            last_name="User",
        )
        await session.commit()
        return user


@pytest_asyncio.fixture
async def test_admin(auth: SimpleRBAC, test_password: str) -> User:
    """
    Pre-created admin user (superuser).

    Credentials:
    - Email: admin@example.com
    - Password: TestPass123!
    - Status: ACTIVE
    - Superuser: True
    """
    async with auth.get_session() as session:
        admin = await auth.user_service.create_user(
            session,
            email="admin@example.com",
            password=test_password,
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()
        return admin


@pytest_asyncio.fixture
async def test_role(auth: SimpleRBAC) -> Role:
    """
    Pre-created test role with basic permissions.

    Role details:
    - Name: "test_role"
    - Display name: "Test Role"
    """
    async with auth.get_session() as session:
        role = await auth.role_service.create_role(
            session,
            name="test_role",
            display_name="Test Role",
            description="A test role with basic permissions",
            is_system_role=False,
        )
        await session.commit()
        return role


@pytest_asyncio.fixture
async def test_permissions(auth: SimpleRBAC) -> list[Permission]:
    """
    Pre-created test permissions.

    Creates: user:create, user:read, user:update, user:delete
    """
    permissions = []

    perm_definitions = [
        ("user:create", "Create Users", "Can create new users"),
        ("user:read", "Read Users", "Can view user information"),
        ("user:update", "Update Users", "Can modify user information"),
        ("user:delete", "Delete Users", "Can delete users"),
    ]

    async with auth.get_session() as session:
        for name, display_name, description in perm_definitions:
            perm = await auth.permission_service.create_permission(
                session,
                name=name,
                display_name=display_name,
                description=description,
                is_system=False,
            )
            permissions.append(perm)
        await session.commit()

    return permissions


# ============================================================================
# Token Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_access_token(auth: SimpleRBAC, test_user: User) -> str:
    """
    Generate a valid access token for test_user.
    """
    from datetime import timedelta

    from outlabs_auth.utils.jwt import create_access_token

    token = create_access_token(
        data={"sub": str(test_user.id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        expires_delta=timedelta(minutes=15),
    )
    return token


@pytest_asyncio.fixture
async def test_expired_token(auth: SimpleRBAC, test_user: User) -> str:
    """
    Generate an expired access token for testing.
    """
    from datetime import timedelta

    from outlabs_auth.utils.jwt import create_access_token

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
    Password is too weak.
    """
    return {
        "email": "invalid@example.com",
        "password": "weak",  # Doesn't meet requirements
        "first_name": "Invalid",
        "last_name": "User",
    }
