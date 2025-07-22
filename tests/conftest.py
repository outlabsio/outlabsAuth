"""
Pytest configuration and fixtures
"""
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
import os
from datetime import datetime, timezone

from api.main import app
from api.config import settings
from api.models import (
    UserModel, EntityModel, RoleModel, EntityMembershipModel,
    PermissionModel, RefreshTokenModel
)
from api.services.auth_service import AuthService

auth_service = AuthService()
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_client():
    """Create database client for tests"""
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    yield client
    client.close()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_client):
    """Initialize database for each test"""
    # Use a test database
    test_db_name = f"test_outlabs_auth_{int(datetime.now().timestamp())}"
    db = db_client[test_db_name]
    
    # Initialize beanie with test database
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            EntityModel,
            RoleModel,
            EntityMembershipModel,
            PermissionModel,
            RefreshTokenModel
        ]
    )
    
    yield db
    
    # Cleanup - drop test database
    await db_client.drop_database(test_db_name)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user(db_session) -> UserModel:
    """Create a test user"""
    user = UserModel(
        email="testuser@example.com",
        is_active=True,
        is_verified=True,
        hashed_password=auth_service.hash_password("password")
    )
    await user.save()
    return user


@pytest_asyncio.fixture
async def test_platform(db_session) -> EntityModel:
    """Create a test platform"""
    platform = EntityModel(
        name="test_platform",
        display_name="Test Platform",
        entity_type="platform",
        entity_class="structural",
        slug="test-platform",
        platform_id="temp_id"
    )
    await platform.save()
    platform.platform_id = str(platform.id)
    await platform.save()
    return platform


@pytest_asyncio.fixture
async def test_organization(db_session, test_platform) -> EntityModel:
    """Create a test organization under the platform"""
    org = EntityModel(
        name="test_org",
        display_name="Test Organization",
        entity_type="organization",
        entity_class="structural",
        slug="test-org",
        parent_entity=test_platform,
        platform_id=str(test_platform.id)
    )
    await org.save()
    return org


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: UserModel) -> dict:
    """Get authentication headers for test user"""
    login_response = await client.post(
        "/v1/auth/login/json",
        json={"email": test_user.email, "password": "password"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def system_user(db_session) -> UserModel:
    """Create a system user"""
    user = UserModel(
        email="system@test.com",
        is_active=True,
        is_verified=True,
        is_system_user=True,
        hashed_password=auth_service.hash_password("password")
    )
    await user.save()
    return user


@pytest_asyncio.fixture
async def system_auth_headers(client: AsyncClient, system_user: UserModel) -> dict:
    """Get authentication headers for system user"""
    login_response = await client.post(
        "/v1/auth/login/json",
        json={"email": system_user.email, "password": "password"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}