import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os

# Set environment variables for testing
os.environ["TESTING"] = "1"
os.environ["MONGO_DATABASE"] = "outlabs_auth_test"

from api.main import app
from api.database import get_database, db
from scripts.seed import seed_database

# Use a separate database for testing
TEST_DATABASE_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
TEST_DB_NAME = "outlabs_auth_test"

# Create a new Motor client for testing
# test_db_client = AsyncIOMotorClient(TEST_DATABASE_URL)
# test_db_instance = test_db_client[TEST_DB_NAME]

async def override_get_db() -> AsyncIOMotorDatabase:
    """
    Dependency override to use the test database.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

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
    
    # The global db object is updated here for services that might still import it directly.
    # However, the dependency override in the `client` fixture is the preferred approach.
    db.client = test_db_client
    db.db = test_db_instance
    
    await seed_database(test_db_instance)
    
    yield test_db_instance
    
    await test_db_client.drop_database(TEST_DB_NAME)
    await test_db_client.close()


@pytest_asyncio.fixture
async def client():
    """
    Simple async client for testing.
    """
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac 