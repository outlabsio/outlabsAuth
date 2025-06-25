import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
import subprocess
import sys

# Set environment variables for testing BEFORE any imports
# This must happen before importing api modules that load settings
os.environ["TESTING"] = "1"
os.environ["MONGO_DATABASE"] = "outlabsAuth_test"

# Force reload of settings to pick up test environment variables
if 'api.config' in sys.modules:
    del sys.modules['api.config']

from api.main import app

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
TEST_DB_NAME = "outlabsAuth_test"

# Test data constants
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "admin123"
}

@pytest.fixture(scope="session")
def event_loop():
    """
    Creates an instance of the default event loop for the session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

def run_seed_script():
    """
    Executes the seeding script for both comprehensive and hierarchical scenarios
    to create a complete dataset for all tests.
    """
    script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'seed_test_environment.py')
    db_name = os.getenv("MONGO_DATABASE", "outlabsAuth_test")
    
    # First, run the comprehensive scenario, which will wipe the database
    print("\n--- Running seed script for 'comprehensive' scenario (with wipe) ---")
    try:
        result = subprocess.run(
            [sys.executable, script_path, "--scenario", "comprehensive", "--db", db_name],
            capture_output=True, text=True, check=True, timeout=90
        )
        print("--- 'comprehensive' scenario completed successfully ---")
        # Print output for debugging
        if result.stdout:
            print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print("--- !!! SEED SCRIPT FAILED for 'comprehensive' scenario !!! ---")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        pytest.fail(f"Seeding script failed, cannot proceed. Error: {e}", pytrace=False)

    # Second, run the hierarchical scenario without wiping the database
    print("\n--- Running seed script for 'hierarchical' scenario (no wipe) ---")
    try:
        subprocess.run(
            [sys.executable, script_path, "--scenario", "hierarchical", "--db", db_name, "--no-wipe"],
            capture_output=True, text=True, check=True, timeout=90
        )
        print("--- 'hierarchical' scenario completed successfully ---")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print("--- !!! SEED SCRIPT FAILED for 'hierarchical' scenario !!! ---")
        print(e.stdout)
        print(e.stderr)
        pytest.fail(f"Seeding script failed, cannot proceed. Error: {e}", pytrace=False)
    
    # Third, run the PropertyHub scenario without wiping the database
    print("\n--- Running seed script for 'propertyhub' scenario (no wipe) ---")
    try:
        subprocess.run(
            [sys.executable, script_path, "--scenario", "propertyhub", "--db", db_name, "--no-wipe"],
            capture_output=True, text=True, check=True, timeout=90
        )
        print("--- 'propertyhub' scenario completed successfully ---")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print("--- !!! SEED SCRIPT FAILED for 'propertyhub' scenario !!! ---")
        print(e.stdout)
        print(e.stderr)
        pytest.fail(f"Seeding script failed, cannot proceed. Error: {e}", pytrace=False)


@pytest_asyncio.fixture(scope="session")
async def test_db():
    """
    Provides a clean test database for the session.
    Always seeds the database to ensure consistent test state.
    """
    test_db_client = AsyncIOMotorClient(TEST_DATABASE_URL)
    test_db_instance = test_db_client[TEST_DB_NAME]
    
    print(f"Preparing test database {TEST_DB_NAME}...")
    
    # Always drop and recreate the database for consistent test state
    await test_db_client.drop_database(TEST_DB_NAME)
    print(f"Dropped existing database {TEST_DB_NAME}")
    
    # Run the seed script
    print("Running seed script...")
    run_seed_script()
    
    # Verify seeding worked
    collections_after = await test_db_instance.list_collection_names()
    if "users" not in collections_after:
        raise Exception("Seeding failed - no users collection found after seeding")
    
    user_count = await test_db_instance.users.count_documents({})
    print(f"Seeding complete - {user_count} users created")
    
    # Small delay to ensure database operations are fully committed
    import time
    time.sleep(0.5)
    
    yield test_db_instance
    
    # Keep the database for debugging - don't drop it
    print(f"Test session complete - keeping {TEST_DB_NAME} database for debugging")
    test_db_client.close()

@pytest_asyncio.fixture
async def client(test_db):
    """
    Async client for testing with Beanie-initialized database.
    """
    # Use the standard app lifespan which will initialize the database properly
    # The environment variables ensure it connects to our test database
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

@pytest_asyncio.fixture
async def admin_headers(client):
    """
    Provides admin authentication headers for tests.
    Logs in as the main super_admin from the comprehensive dataset.
    """
    login_data = {
        "username": "admin@test.com",
        "password": "admin123"
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    assert login_response.status_code == 200, f"Failed to log in admin user. Response: {login_response.text}"
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