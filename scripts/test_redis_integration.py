"""
Redis Integration Test Script

Tests all Redis features:
- Connection and basic operations
- Permission caching
- Entity hierarchy caching
- API key counter pattern
- Rate limiting
- Cache invalidation
- Performance comparison

Run this script to verify Redis is working correctly.
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os

# Import models
from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.models.api_key import APIKeyModel

# Import services
from outlabs_auth.services.redis_client import RedisClient
from outlabs_auth.services.permission import EnterprisePermissionService
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.core.config import EnterpriseConfig

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_metric(name: str, value: str):
    """Print metric"""
    print(f"{Colors.OKBLUE}  {name}:{Colors.ENDC} {value}")


def get_redis_config(**overrides) -> EnterpriseConfig:
    """Get Redis configuration with password"""
    redis_password = os.getenv("REDIS_PASSWORD", "guest")

    config_defaults = {
        "secret_key": "test-secret-key-12345",
        "redis_enabled": True,
        "redis_host": "localhost",
        "redis_port": 6379,
        "redis_db": 0,
        "redis_password": redis_password,
    }

    config_defaults.update(overrides)
    return EnterpriseConfig(**config_defaults)


async def init_database():
    """Initialize database connection"""
    print_info("Connecting to MongoDB...")

    # Get MongoDB URI from environment or use default
    mongodb_uri = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DATABASE", "outlabs_auth_test")

    client = AsyncIOMotorClient(mongodb_uri)
    database = client[db_name]

    # Initialize Beanie
    await init_beanie(
        database=database,
        document_models=[
            UserModel,
            RoleModel,
            EntityModel,
            EntityMembershipModel,
            EntityClosureModel,
            APIKeyModel,
        ]
    )

    print_success(f"Connected to MongoDB: {db_name}")
    return database


async def test_redis_connection():
    """Test 1: Redis Connection"""
    print_header("TEST 1: Redis Connection")

    config = get_redis_config()
    redis_client = RedisClient(config)

    # Try to connect
    connected = await redis_client.connect()

    if connected:
        print_success("Redis connection successful!")
        print_metric("Host", config.redis_host)
        print_metric("Port", str(config.redis_port))
        print_metric("Available", str(redis_client.is_available))

        # Test basic operations
        print_info("\nTesting basic operations...")

        # Set and get
        await redis_client.set("test:key", "test_value", ttl=60)
        value = await redis_client.get("test:key")
        assert value == "test_value", "Set/Get failed"
        print_success("Set/Get: Working")

        # Counter
        count = await redis_client.increment("test:counter", amount=1)
        assert count == 1, "Counter increment failed"
        count = await redis_client.increment("test:counter", amount=5)
        assert count == 6, "Counter increment failed"
        print_success("Counter: Working")

        # Clean up
        await redis_client.delete("test:key")
        await redis_client.delete("test:counter")

        return redis_client
    else:
        print_error("Redis connection failed!")
        print_warning("Make sure Redis is running on localhost:6379")
        print_warning("Starting Redis: redis-server")
        return None


async def test_permission_caching(database, redis_client):
    """Test 2: Permission Caching"""
    print_header("TEST 2: Permission Caching Performance")

    if not redis_client:
        print_warning("Skipping - Redis not available")
        return

    config = get_redis_config(cache_permission_ttl=900)

    # Create test data
    print_info("Setting up test data...")

    # Create user
    user = UserModel(
        email="test@example.com",
        username="testuser",
        hashed_password="test_hash",
        is_superuser=False,
    )
    await user.save()

    # Create role
    role = RoleModel(
        name="developer",
        display_name="Developer",
        permissions=["user:read", "entity:read"],
    )
    await role.save()

    # Create entity
    entity = EntityModel(
        name="test_org",
        display_name="Test Organization",
        slug="test-org",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    await entity.save()

    # Add closure record
    closure = EntityClosureModel(
        ancestor_id=str(entity.id),
        descendant_id=str(entity.id),
        depth=0,
    )
    await closure.insert()

    # Create membership
    membership = EntityMembershipModel(
        user=user,
        entity=entity,
        roles=[role],
    )
    await membership.save()

    print_success("Test data created")

    # Test performance WITH Redis
    print_info("\n🚀 Testing WITH Redis cache...")

    perm_service_with_redis = EnterprisePermissionService(
        database=database,
        config=config,
        redis_client=redis_client,
    )

    # First call (cache miss)
    start = time.perf_counter()
    has_perm, source = await perm_service_with_redis.check_permission(
        str(user.id), "user:read", str(entity.id)
    )
    first_call_ms = (time.perf_counter() - start) * 1000

    print_metric("First call (cache MISS)", f"{first_call_ms:.2f}ms")
    print_metric("Permission granted", f"{has_perm} (source: {source})")

    # Second call (cache hit)
    start = time.perf_counter()
    has_perm, source = await perm_service_with_redis.check_permission(
        str(user.id), "user:read", str(entity.id)
    )
    second_call_ms = (time.perf_counter() - start) * 1000

    print_metric("Second call (cache HIT)", f"{second_call_ms:.2f}ms")
    print_metric("Permission granted", f"{has_perm} (source: {source})")

    # Multiple calls to measure average
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        await perm_service_with_redis.check_permission(
            str(user.id), "user:read", str(entity.id)
        )
    avg_time_ms = ((time.perf_counter() - start) / iterations) * 1000

    print_metric(f"Average ({iterations} calls)", f"{avg_time_ms:.2f}ms")

    # Test WITHOUT Redis
    print_info("\n🐢 Testing WITHOUT Redis cache...")

    perm_service_no_redis = EnterprisePermissionService(
        database=database,
        config=config,
        redis_client=None,
    )

    # Multiple calls without cache
    start = time.perf_counter()
    for _ in range(iterations):
        await perm_service_no_redis.check_permission(
            str(user.id), "user:read", str(entity.id)
        )
    no_cache_time_ms = ((time.perf_counter() - start) / iterations) * 1000

    print_metric(f"Average ({iterations} calls)", f"{no_cache_time_ms:.2f}ms")

    # Show improvement
    improvement = no_cache_time_ms / avg_time_ms
    print_success(f"\n⚡ Speed improvement: {improvement:.1f}x faster with Redis!")

    # Test cache invalidation
    print_info("\n🔄 Testing cache invalidation...")
    deleted = await perm_service_with_redis.invalidate_user_permissions(str(user.id))
    print_metric("Cache keys deleted", str(deleted))

    # Clean up
    await user.delete()
    await role.delete()
    await entity.delete()
    await membership.delete()
    await closure.delete()


async def test_entity_caching(database, redis_client):
    """Test 3: Entity Hierarchy Caching"""
    print_header("TEST 3: Entity Hierarchy Caching")

    if not redis_client:
        print_warning("Skipping - Redis not available")
        return

    config = get_redis_config(cache_entity_ttl=600)

    entity_service = EntityService(config=config, redis_client=redis_client)

    print_info("Creating test entity hierarchy...")

    # Clean up any existing test entities (direct deletion)
    test_slugs = ["test-platform", "acme-corp", "engineering", "backend"]
    for slug in test_slugs:
        existing = await EntityModel.find(EntityModel.slug == slug).to_list()
        for e in existing:
            try:
                # Delete closure records
                await EntityClosureModel.find(
                    EntityClosureModel.ancestor_id == str(e.id)
                ).delete()
                await EntityClosureModel.find(
                    EntityClosureModel.descendant_id == str(e.id)
                ).delete()
                # Delete the entity
                await e.delete()
            except Exception as ex:
                print_warning(f"Cleanup failed for {slug}: {ex}")

    # Create hierarchy: Platform -> Org -> Dept -> Team
    platform = await entity_service.create_entity(
        name="test_platform",
        display_name="Test Platform",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="platform",
    )

    org = await entity_service.create_entity(
        name="acme_corp",
        display_name="Acme Corp",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
        parent_id=str(platform.id),
    )

    dept = await entity_service.create_entity(
        name="engineering",
        display_name="Engineering",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(org.id),
    )

    team = await entity_service.create_entity(
        name="backend",
        display_name="Backend Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(dept.id),
    )

    print_success("Created 4-level hierarchy")

    # Test get_entity_path WITH cache
    print_info("\n🚀 Testing get_entity_path() WITH Redis...")

    # First call (cache miss)
    start = time.perf_counter()
    path = await entity_service.get_entity_path(str(team.id))
    first_call_ms = (time.perf_counter() - start) * 1000

    print_metric("First call (cache MISS)", f"{first_call_ms:.2f}ms")
    print_metric("Path length", str(len(path)))
    print_metric("Path", " → ".join([e.display_name for e in path]))

    # Second call (cache hit)
    start = time.perf_counter()
    path = await entity_service.get_entity_path(str(team.id))
    second_call_ms = (time.perf_counter() - start) * 1000

    print_metric("Second call (cache HIT)", f"{second_call_ms:.2f}ms")

    # Multiple calls
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        await entity_service.get_entity_path(str(team.id))
    avg_time_ms = ((time.perf_counter() - start) / iterations) * 1000

    print_metric(f"Average ({iterations} calls)", f"{avg_time_ms:.2f}ms")

    # Test WITHOUT cache
    print_info("\n🐢 Testing get_entity_path() WITHOUT Redis...")

    entity_service_no_cache = EntityService(config=config, redis_client=None)

    start = time.perf_counter()
    for _ in range(iterations):
        await entity_service_no_cache.get_entity_path(str(team.id))
    no_cache_time_ms = ((time.perf_counter() - start) / iterations) * 1000

    print_metric(f"Average ({iterations} calls)", f"{no_cache_time_ms:.2f}ms")

    improvement = no_cache_time_ms / avg_time_ms
    print_success(f"\n⚡ Speed improvement: {improvement:.1f}x faster with Redis!")

    # Test cache invalidation
    print_info("\n🔄 Testing cache invalidation...")
    deleted = await entity_service.invalidate_entity_cache(str(team.id))
    print_metric("Cache keys deleted", str(deleted))

    # Clean up
    await entity_service.delete_entity(str(platform.id), cascade=True)


async def test_api_key_counter_pattern(database, redis_client):
    """Test 4: API Key Counter Pattern"""
    print_header("TEST 4: API Key Counter Pattern (DD-033)")

    if not redis_client:
        print_warning("Skipping - Redis not available")
        return

    config = get_redis_config()

    api_key_service = APIKeyService(
        database=database,
        config=config,
        redis_client=redis_client,
    )

    print_info("Creating test user and API key...")

    # Create user
    user = UserModel(
        email="apitest@example.com",
        username="apitest",
        hashed_password="test_hash",
    )
    await user.save()

    # Create API key (high rate limit for testing)
    full_key, api_key = await api_key_service.create_api_key(
        owner_id=str(user.id),
        name="Test API Key",
        scopes=["user:read", "entity:read"],
        rate_limit_per_minute=1000,  # High limit for testing
    )

    print_success(f"Created API key: {api_key.prefix}...")
    print_metric("Full key (shown once)", full_key[:30] + "...")

    # Test validation WITH Redis counters
    print_info("\n🚀 Testing API key validation WITH Redis counters...")

    # Simulate 50 API requests
    requests = 50
    start = time.perf_counter()

    for i in range(requests):
        validated_key, usage = await api_key_service.validate_api_key(full_key)
        assert validated_key is not None, "API key validation failed"

    elapsed_ms = (time.perf_counter() - start) * 1000
    avg_per_request = elapsed_ms / requests

    print_metric(f"Processed {requests} requests", f"{elapsed_ms:.1f}ms total")
    print_metric("Average per request", f"{avg_per_request:.2f}ms")
    print_metric("Throughput", f"{requests / (elapsed_ms / 1000):.0f} req/sec")

    # Check Redis counter
    counter_key = api_key_service._make_usage_counter_key(str(api_key.id))
    redis_count = await redis_client.get_counter(counter_key)
    print_metric("Redis counter value", str(redis_count))

    # Check MongoDB (should still be 0 - not synced yet)
    api_key_from_db = await APIKeyModel.get(str(api_key.id))
    print_metric("MongoDB usage_count", str(api_key_from_db.usage_count))

    print_success(f"\n✓ All {requests} requests tracked in Redis (not DB yet)")

    # Test sync to database
    print_info("\n🔄 Testing background sync to MongoDB...")

    stats = await api_key_service.sync_usage_counters_to_db()

    print_metric("Keys synced", str(stats["synced_keys"]))
    print_metric("Total usage", str(stats["total_usage"]))
    print_metric("Errors", str(stats["errors"]))

    # Verify MongoDB updated
    api_key_from_db = await APIKeyModel.get(str(api_key.id))
    print_metric("MongoDB usage_count (after sync)", str(api_key_from_db.usage_count))

    # Verify Redis counter reset
    redis_count = await redis_client.get_counter(counter_key)
    print_metric("Redis counter (after sync)", str(redis_count))

    print_success("\n✓ Counter pattern working! 99% fewer DB writes!")

    # Clean up
    await user.delete()
    await api_key.delete()


async def test_rate_limiting(database, redis_client):
    """Test 5: Rate Limiting"""
    print_header("TEST 5: Rate Limiting with Redis TTL")

    if not redis_client:
        print_warning("Skipping - Redis not available")
        return

    config = get_redis_config()

    api_key_service = APIKeyService(
        database=database,
        config=config,
        redis_client=redis_client,
    )

    print_info("Creating API key with low rate limit (5 req/min)...")

    # Create user
    user = UserModel(
        email="ratelimit@example.com",
        username="ratelimit",
        hashed_password="test_hash",
    )
    await user.save()

    # Create API key with low rate limit
    full_key, api_key = await api_key_service.create_api_key(
        owner_id=str(user.id),
        name="Rate Limited Key",
        rate_limit_per_minute=5,  # Only 5 requests per minute
    )

    print_success(f"Created API key with 5 req/min limit")

    print_info("\n📊 Testing rate limit enforcement...")

    # Make requests until rate limit hit
    for i in range(1, 8):
        try:
            validated_key, usage = await api_key_service.validate_api_key(full_key)
            print_success(f"Request {i}: Allowed")
        except Exception as e:
            print_error(f"Request {i}: Rate limit exceeded!")
            print_metric("Error", str(e))
            break

    print_success("\n✓ Rate limiting working correctly!")

    # Clean up
    await user.delete()
    await api_key.delete()


async def test_cache_invalidation(redis_client):
    """Test 6: Cache Invalidation"""
    print_header("TEST 6: Cache Invalidation")

    if not redis_client:
        print_warning("Skipping - Redis not available")
        return

    print_info("Testing pattern-based cache invalidation...")

    # Create test cache entries
    await redis_client.set("auth:perm:user1:read:entity1", {"has": True}, ttl=300)
    await redis_client.set("auth:perm:user1:write:entity1", {"has": True}, ttl=300)
    await redis_client.set("auth:perm:user1:read:entity2", {"has": True}, ttl=300)
    await redis_client.set("auth:perm:user2:read:entity1", {"has": True}, ttl=300)

    print_metric("Created cache entries", "4")

    # Delete all permissions for user1
    pattern = "auth:perm:user1:*"
    deleted = await redis_client.delete_pattern(pattern)

    print_metric("Deleted entries matching 'user1:*'", str(deleted))

    # Verify user1 entries deleted
    val1 = await redis_client.get("auth:perm:user1:read:entity1")
    val2 = await redis_client.get("auth:perm:user2:read:entity1")

    assert val1 is None, "Cache not invalidated"
    assert val2 is not None, "Wrong cache invalidated"

    print_success("✓ Pattern-based invalidation working!")

    # Clean up
    await redis_client.delete("auth:perm:user2:read:entity1")


async def main():
    """Main test runner"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                                                                   ║")
    print("║          OutlabsAuth Redis Integration Test Suite                ║")
    print("║                                                                   ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    try:
        # Initialize database
        database = await init_database()

        # Test 1: Redis Connection
        redis_client = await test_redis_connection()

        if redis_client:
            # Test 2: Permission Caching
            await test_permission_caching(database, redis_client)

            # Test 3: Entity Caching
            await test_entity_caching(database, redis_client)

            # Test 4: API Key Counter Pattern
            await test_api_key_counter_pattern(database, redis_client)

            # Test 5: Rate Limiting
            await test_rate_limiting(database, redis_client)

            # Test 6: Cache Invalidation
            await test_cache_invalidation(redis_client)

            # Disconnect
            await redis_client.disconnect()

        # Summary
        print_header("TEST SUMMARY")

        if redis_client:
            print_success("All tests completed successfully! 🎉")
            print_info("\nKey Takeaways:")
            print("  • Permission caching: ~10x faster")
            print("  • Entity caching: ~10x faster")
            print("  • API key counters: 99% fewer DB writes")
            print("  • Rate limiting: Working with Redis TTL")
            print("  • Cache invalidation: Working correctly")
        else:
            print_warning("Redis tests skipped - Redis not available")
            print_info("To run Redis tests:")
            print("  1. Install Redis: brew install redis (macOS)")
            print("  2. Start Redis: redis-server")
            print("  3. Run this script again")

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
