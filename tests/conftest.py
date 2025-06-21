import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os

# Set environment variables for testing
os.environ["TESTING"] = "1"
os.environ["MONGO_DATABASE"] = "outlabs_auth_test"

from api.main import app
from scripts.seed import seed_database

# Import all document models for Beanie initialization
from api.models.user_model import UserModel
from api.models.role_model import RoleModel
from api.models.permission_model import PermissionModel
from api.models.client_account_model import ClientAccountModel
from api.models.refresh_token_model import RefreshTokenModel
from api.models.password_reset_token_model import PasswordResetTokenModel
from api.models.group_model import GroupModel

# Use a separate database for testing
TEST_DATABASE_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
TEST_DB_NAME = "outlabs_auth_test"

# Test data constants
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "a_very_secure_password"
}

@pytest.fixture(scope="session")
def event_loop():
    """
    Creates an instance of the default event loop for the session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def test_db():
    """
    Provides a clean test database for the session.
    Connects before tests and drops the database after tests.
    """
    test_db_client = AsyncIOMotorClient(TEST_DATABASE_URL)
    test_db_instance = test_db_client[TEST_DB_NAME]
    
    # Initialize Beanie for the test database
    await init_beanie(
        database=test_db_instance,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            ClientAccountModel,
            RefreshTokenModel,
            PasswordResetTokenModel,
            GroupModel,
        ]
    )
    
    # Rebuild models to resolve circular references with proper namespace
    namespace = {
        'UserModel': UserModel,
        'ClientAccountModel': ClientAccountModel,
        'RefreshTokenModel': RefreshTokenModel,
        'PasswordResetTokenModel': PasswordResetTokenModel,
        'GroupModel': GroupModel,
    }
    
    UserModel.model_rebuild(_types_namespace=namespace)
    ClientAccountModel.model_rebuild(_types_namespace=namespace)
    RefreshTokenModel.model_rebuild(_types_namespace=namespace)
    PasswordResetTokenModel.model_rebuild(_types_namespace=namespace)
    GroupModel.model_rebuild(_types_namespace=namespace)
    
    # Seed the test database
    await seed_database(test_db_instance)
    
    yield test_db_instance
    
    # Clean up - drop database first, then close client
    await test_db_client.drop_database(TEST_DB_NAME)
    test_db_client.close()

@pytest_asyncio.fixture
async def client(test_db):
    """
    Async client for testing with Beanie-initialized database.
    """
    # The test_db fixture ensures Beanie is initialized and data is seeded
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

@pytest_asyncio.fixture
async def admin_headers(client):
    """
    Provides admin authentication headers for tests.
    """
    login_data = {
        "username": "admin@test.com",
        "password": "a_very_secure_password"
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200
    admin_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {admin_token}"}

@pytest_asyncio.fixture
async def reset_admin_password(test_db):
    """
    Ensures the admin user has the correct password before each test.
    This prevents test isolation issues where password change tests 
    affect subsequent tests.
    """
    from api.services.security_service import security_service
    
    # Find the admin user
    admin_user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
    if admin_user:
        # Reset password to the original test password
        admin_user.password_hash = security_service.get_password_hash(ADMIN_USER_DATA["password"])
        await admin_user.save()
    
    yield
    
    # Optionally reset again after the test (for extra safety)
    admin_user = await UserModel.find_one(UserModel.email == ADMIN_USER_DATA["email"])
    if admin_user:
        admin_user.password_hash = security_service.get_password_hash(ADMIN_USER_DATA["password"])
        await admin_user.save() 