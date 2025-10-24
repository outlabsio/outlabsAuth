"""
Fixtures for login/logout testing

Provides:
- Database fixtures (MongoDB)
- Redis fixtures (with graceful degradation)
- Auth instances with different configurations
- User fixtures with different statuses
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import OutlabsAuth
from outlabs_auth.models.user import UserModel, UserStatus
from outlabs_auth.models.token import RefreshTokenModel


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def mongo_db():
    """
    Test MongoDB database (function-scoped for isolation).

    Creates fresh database for each test, drops after test completes.
    """
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_outlabsauth_login_logout"]

    yield db

    # Cleanup: Drop database after test
    await client.drop_database("test_outlabsauth_login_logout")
    client.close()


# ============================================================================
# Redis Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def redis_available():
    """
    Check if Redis is available for testing.

    Returns True if Redis is running on localhost:6379, False otherwise.
    """
    try:
        from outlabs_auth.services.redis_client import RedisClient
        from outlabs_auth.core.config import AuthConfig

        config = AuthConfig(
            secret_key="test-secret",
            redis_url="redis://localhost:6379/1"  # Use DB 1 for tests
        )
        client = RedisClient(config)
        await client.connect()
        is_available = client.is_available
        await client.close()
        return is_available
    except Exception:
        return False


# ============================================================================
# Auth Instance Fixtures (Different Configurations)
# ============================================================================

@pytest.fixture
async def auth_standard(mongo_db):
    """
    Mode 1: Standard configuration (default security).

    - store_refresh_tokens=True (MongoDB storage)
    - enable_token_blacklist=False (no Redis blacklist)
    - Result: 15-min security window on logout
    """
    auth = OutlabsAuth(
        database=mongo_db,
        secret_key="test-secret-standard",
        store_refresh_tokens=True,
        enable_token_blacklist=False,
        enable_token_cleanup=False,  # Disable scheduler in tests
        access_token_expire_minutes=15,
        refresh_token_expire_days=30
    )
    await auth.initialize()

    yield auth

    # Cleanup
    await auth.shutdown()


@pytest.fixture
async def auth_high_security(mongo_db, redis_available):
    """
    Mode 2: High security configuration (immediate revocation).

    - store_refresh_tokens=True (MongoDB storage)
    - enable_token_blacklist=True (Redis blacklist)
    - Redis required
    - Result: Immediate token revocation

    Skips test if Redis not available.
    """
    if not redis_available:
        pytest.skip("Redis not available for high security testing")

    auth = OutlabsAuth(
        database=mongo_db,
        secret_key="test-secret-high-security",
        store_refresh_tokens=True,
        enable_token_blacklist=True,
        redis_url="redis://localhost:6379/1",  # Test DB
        enable_token_cleanup=False,
        access_token_expire_minutes=15,
        refresh_token_expire_days=30
    )
    await auth.initialize()

    yield auth

    # Cleanup
    await auth.shutdown()


@pytest.fixture
async def auth_stateless(mongo_db):
    """
    Mode 3: Stateless configuration (no token storage).

    - store_refresh_tokens=False (no MongoDB storage)
    - enable_token_blacklist=False (no Redis)
    - Result: Cannot revoke tokens (fully stateless)
    """
    auth = OutlabsAuth(
        database=mongo_db,
        secret_key="test-secret-stateless",
        store_refresh_tokens=False,
        enable_token_blacklist=False,
        enable_token_cleanup=False,
        access_token_expire_minutes=15,
        refresh_token_expire_days=30
    )
    await auth.initialize()

    yield auth

    # Cleanup
    await auth.shutdown()


@pytest.fixture
async def auth_redis_only(mongo_db, redis_available):
    """
    Mode 4: Redis-only configuration (stateless + blacklist).

    - store_refresh_tokens=False (no MongoDB storage)
    - enable_token_blacklist=True (Redis blacklist)
    - Result: Stateless JWT + access token blacklisting
    """
    if not redis_available:
        pytest.skip("Redis not available for Redis-only testing")

    auth = OutlabsAuth(
        database=mongo_db,
        secret_key="test-secret-redis-only",
        store_refresh_tokens=False,
        enable_token_blacklist=True,
        redis_url="redis://localhost:6379/1",
        enable_token_cleanup=False,
        access_token_expire_minutes=15,
        refresh_token_expire_days=30
    )
    await auth.initialize()

    yield auth

    # Cleanup
    await auth.shutdown()


@pytest.fixture
async def auth_with_cleanup(mongo_db):
    """
    Auth instance with token cleanup enabled (for scheduler testing).

    - enable_token_cleanup=True
    - token_cleanup_interval_hours=1 (short interval for testing)
    """
    auth = OutlabsAuth(
        database=mongo_db,
        secret_key="test-secret-cleanup",
        store_refresh_tokens=True,
        enable_token_blacklist=False,
        enable_token_cleanup=True,
        token_cleanup_interval_hours=1,  # 1 hour for testing
        access_token_expire_minutes=15,
        refresh_token_expire_days=30
    )
    await auth.initialize()

    yield auth

    # Cleanup
    await auth.shutdown()


# ============================================================================
# User Fixtures (Different Statuses)
# ============================================================================

@pytest.fixture
async def active_user(auth_standard):
    """
    Create ACTIVE user (default status).

    Can authenticate normally.
    """
    user = await auth_standard.user_service.create_user(
        email="active@test.com",
        password="Password123!",
        first_name="Active",
        last_name="User"
    )
    # User is ACTIVE by default
    return user


@pytest.fixture
async def suspended_user(auth_standard):
    """
    Create SUSPENDED user.

    Cannot authenticate.
    """
    user = await auth_standard.user_service.create_user(
        email="suspended@test.com",
        password="Password123!",
        first_name="Suspended",
        last_name="User"
    )
    user.status = UserStatus.SUSPENDED
    await user.save()
    return user


@pytest.fixture
async def suspended_user_with_expiry(auth_standard):
    """
    Create SUSPENDED user with expiry date (7 days from now).

    Cannot authenticate until expiry passes.
    """
    user = await auth_standard.user_service.create_user(
        email="suspended_expiry@test.com",
        password="Password123!",
        first_name="Suspended",
        last_name="WithExpiry"
    )
    user.status = UserStatus.SUSPENDED
    user.suspended_until = datetime.now(timezone.utc) + timedelta(days=7)
    await user.save()
    return user


@pytest.fixture
async def banned_user(auth_standard):
    """
    Create BANNED user.

    Cannot authenticate (permanent block).
    """
    user = await auth_standard.user_service.create_user(
        email="banned@test.com",
        password="Password123!",
        first_name="Banned",
        last_name="User"
    )
    user.status = UserStatus.BANNED
    await user.save()
    return user


@pytest.fixture
async def deleted_user(auth_standard):
    """
    Create DELETED user (soft delete).

    Cannot authenticate.
    """
    user = await auth_standard.user_service.create_user(
        email="deleted@test.com",
        password="Password123!",
        first_name="Deleted",
        last_name="User"
    )
    user.status = UserStatus.DELETED
    user.deleted_at = datetime.now(timezone.utc)
    await user.save()
    return user


@pytest.fixture
async def locked_user(auth_standard):
    """
    Create user that is temporarily locked (too many failed attempts).

    ACTIVE status but locked for 30 minutes.
    """
    user = await auth_standard.user_service.create_user(
        email="locked@test.com",
        password="Password123!",
        first_name="Locked",
        last_name="User"
    )
    # Simulate lockout
    user.failed_login_attempts = auth_standard.config.max_login_attempts
    user.locked_until = datetime.now(timezone.utc) + timedelta(
        minutes=auth_standard.config.lockout_duration_minutes
    )
    await user.save()
    return user


# ============================================================================
# Token Fixtures
# ============================================================================

@pytest.fixture
async def user_with_tokens(auth_standard, active_user):
    """
    Create ACTIVE user and authenticate to get tokens.

    Returns:
        dict: {
            "user": UserModel,
            "access_token": str,
            "refresh_token": str,
            "token_pair": TokenPair
        }
    """
    user, token_pair = await auth_standard.auth_service.login(
        email=active_user.email,
        password="Password123!"
    )

    return {
        "user": user,
        "access_token": token_pair.access_token,
        "refresh_token": token_pair.refresh_token,
        "token_pair": token_pair
    }


@pytest.fixture
async def expired_refresh_token(auth_standard, active_user):
    """
    Create an expired refresh token for testing cleanup.

    Returns:
        RefreshTokenModel: Expired token
    """
    import hashlib

    # Create token that expired 1 day ago
    token_value = "fake_expired_token_123"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    expired_token = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
        device_name="Test Device",
        ip_address="127.0.0.1"
    )
    await expired_token.save()

    return expired_token


@pytest.fixture
async def old_revoked_token(auth_standard, active_user):
    """
    Create a revoked token that's older than retention period (>7 days).

    Should be deleted by cleanup.
    """
    import hashlib

    token_value = "fake_old_revoked_token_456"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    old_revoked = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=23),  # Not expired
        is_revoked=True,
        revoked_at=datetime.now(timezone.utc) - timedelta(days=8),  # Revoked 8 days ago
        revoked_reason="Test",
        device_name="Test Device"
    )
    await old_revoked.save()

    return old_revoked


@pytest.fixture
async def recent_revoked_token(auth_standard, active_user):
    """
    Create a recently revoked token (<7 days).

    Should NOT be deleted by cleanup.
    """
    import hashlib

    token_value = "fake_recent_revoked_token_789"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    recent_revoked = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=29),
        is_revoked=True,
        revoked_at=datetime.now(timezone.utc) - timedelta(days=2),  # Revoked 2 days ago
        revoked_reason="Test",
        device_name="Test Device"
    )
    await recent_revoked.save()

    return recent_revoked


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def password():
    """Standard test password for all users."""
    return "Password123!"


@pytest.fixture
async def cleanup_tokens(mongo_db):
    """
    Cleanup all tokens after test.

    Useful when test creates many tokens.
    """
    yield

    # After test: delete all refresh tokens
    await RefreshTokenModel.delete_all()
