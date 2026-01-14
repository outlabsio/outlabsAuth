"""
Fixtures for activity tracking integration tests
"""
import pytest
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis
from beanie import init_beanie

from outlabs_auth import OutlabsAuth
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.activity_metric import ActivityMetric


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mongodb_client():
    """MongoDB client for testing."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    yield client
    client.close()


@pytest.fixture
async def test_database(mongodb_client):
    """Test database (cleaned up after each test)."""
    db_name = "test_activity_tracking"
    database = mongodb_client[db_name]

    # Initialize Beanie
    await init_beanie(
        database=database,
        document_models=[UserModel, ActivityMetric]
    )

    yield database

    # Cleanup: drop test database
    await mongodb_client.drop_database(db_name)


@pytest.fixture
async def redis_client():
    """Redis client for testing."""
    try:
        redis = Redis.from_url("redis://localhost:6379", decode_responses=True)
        await redis.ping()
        yield redis

        # Cleanup: delete test keys
        async for key in redis.scan_iter("active_users:*"):
            await redis.delete(key)
        async for key in redis.scan_iter("last_activity:*"):
            await redis.delete(key)

        await redis.close()
    except Exception:
        pytest.skip("Redis not available")


@pytest.fixture
async def auth_with_activity_tracking(test_database, redis_client):
    """OutlabsAuth instance with activity tracking enabled."""
    auth = OutlabsAuth(
        database=test_database,
        secret_key="test-secret-key-for-activity-tracking",
        redis_url="redis://localhost:6379",
        enable_activity_tracking=True,
        activity_sync_interval=10,  # Short interval for testing
        activity_update_user_model=True,
        activity_store_user_ids=True,  # Store for cohort tests
    )

    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest.fixture
async def auth_without_activity_tracking(test_database):
    """OutlabsAuth instance with activity tracking disabled."""
    auth = OutlabsAuth(
        database=test_database,
        secret_key="test-secret-key-no-activity",
        enable_activity_tracking=False,
    )

    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest.fixture
async def active_user(test_database):
    """Create an active test user."""
    user = UserModel(
        email="testuser@example.com",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5P5MyAB/MgzYW",  # "password123"
        profile={
            "first_name": "Test",
            "last_name": "User"
        }
    )
    await user.save()
    yield user
    await user.delete()


@pytest.fixture
def password():
    """Test user password."""
    return "password123"
