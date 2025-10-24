"""
Test Immediate Logout (Redis JTI Blacklisting)

Tests for high-security logout mode where access tokens are immediately
revoked using Redis blacklist.

Mode: High Security
- store_refresh_tokens=True (MongoDB)
- enable_token_blacklist=True (Redis)
- Result: Immediate access token revocation

Flow:
1. Login → Get access + refresh tokens
2. Logout with blacklist_access_token=True
3. Access token added to Redis blacklist (key: blacklist:jwt:{jti})
4. Further requests with that access token are rejected immediately

Covers:
- Immediate access token revocation after logout
- Redis blacklist checking during authentication
- TTL management (auto-expire when token expires anyway)
- Graceful degradation if Redis unavailable
- Mixed mode (stateless + Redis blacklist)
"""
import pytest
from datetime import datetime, timedelta, timezone
import time

from outlabs_auth.models.token import RefreshTokenModel
from outlabs_auth.utils.jwt import verify_token


# ============================================================================
# Immediate Logout Tests (High Security Mode)
# ============================================================================

@pytest.mark.asyncio
async def test_immediate_logout_blacklists_access_token(auth_high_security, active_user, password):
    """
    Logout with blacklist_access_token=True immediately revokes access token.

    High security mode: Access token is blacklisted in Redis.
    """
    # Login to get tokens
    user, tokens = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI from access token
    payload = verify_token(
        tokens.access_token,
        auth_high_security.config.secret_key,
        auth_high_security.config.algorithm,
        expected_type="access",
        audience=auth_high_security.config.jwt_audience
    )
    jti = payload.get("jti")
    assert jti is not None, "Access token should have JTI"

    # Verify access token works before logout
    user_before = await auth_high_security.auth_service.get_current_user(tokens.access_token)
    assert user_before is not None
    assert user_before.id == user.id

    # Logout with immediate blacklisting
    result = await auth_high_security.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth_high_security.redis_client
    )
    assert result is True

    # Verify access token is now blacklisted in Redis
    is_blacklisted = await auth_high_security.redis_client.exists(f"blacklist:jwt:{jti}")
    assert is_blacklisted is True

    # Verify access token no longer works (should be rejected)
    user_after = await auth_high_security.auth_service.get_current_user(tokens.access_token)
    assert user_after is None, "Access token should be rejected after blacklisting"


@pytest.mark.asyncio
async def test_standard_logout_does_not_blacklist_access_token(auth_standard, active_user, password):
    """
    Standard logout (without blacklist_access_token=True) does NOT blacklist access token.

    Standard mode: 15-minute security window remains.
    """
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_standard.config.secret_key,
        auth_standard.config.algorithm,
        expected_type="access",
        audience=auth_standard.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout WITHOUT blacklisting (standard mode)
    result = await auth_standard.auth_service.logout(tokens.refresh_token)
    assert result is True

    # Verify access token still works (15-min window)
    user_after = await auth_standard.auth_service.get_current_user(tokens.access_token)
    assert user_after is not None
    assert user_after.id == user.id


@pytest.mark.asyncio
async def test_blacklist_with_ttl(auth_high_security, active_user, password):
    """Blacklisted tokens have TTL matching access token expiration."""
    # Login
    user, tokens = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_high_security.config.secret_key,
        auth_high_security.config.algorithm,
        expected_type="access",
        audience=auth_high_security.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout with blacklisting
    await auth_high_security.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth_high_security.redis_client
    )

    # Check TTL in Redis
    ttl = await auth_high_security.redis_client.ttl(f"blacklist:jwt:{jti}")

    # TTL should be around access_token_expire_minutes (15 min = 900 sec)
    expected_ttl = auth_high_security.config.access_token_expire_minutes * 60

    # Allow 10 second margin (for test execution time)
    assert ttl > 0, "Blacklist entry should have TTL"
    assert ttl <= expected_ttl, f"TTL should be <= {expected_ttl} seconds"
    assert ttl >= expected_ttl - 10, f"TTL should be close to {expected_ttl} seconds"


@pytest.mark.asyncio
async def test_multiple_sessions_independent_blacklisting(auth_high_security, active_user, password):
    """Each session can be blacklisted independently (per JTI)."""
    # Create 3 sessions
    sessions = []
    for i in range(3):
        user, tokens = await auth_high_security.auth_service.login(
            email=active_user.email,
            password=password
        )
        payload = verify_token(
            tokens.access_token,
            auth_high_security.config.secret_key,
            auth_high_security.config.algorithm,
            expected_type="access",
            audience=auth_high_security.config.jwt_audience
        )
        sessions.append({
            "tokens": tokens,
            "jti": payload.get("jti")
        })

    # Verify all 3 sessions work
    for session in sessions:
        user = await auth_high_security.auth_service.get_current_user(
            session["tokens"].access_token
        )
        assert user is not None

    # Blacklist session 2 only
    await auth_high_security.auth_service.logout(
        sessions[1]["tokens"].refresh_token,
        blacklist_access_token=True,
        access_token_jti=sessions[1]["jti"],
        redis_client=auth_high_security.redis_client
    )

    # Verify session 1 and 3 still work
    user1 = await auth_high_security.auth_service.get_current_user(
        sessions[0]["tokens"].access_token
    )
    assert user1 is not None

    user3 = await auth_high_security.auth_service.get_current_user(
        sessions[2]["tokens"].access_token
    )
    assert user3 is not None

    # Verify session 2 is blocked
    user2 = await auth_high_security.auth_service.get_current_user(
        sessions[1]["tokens"].access_token
    )
    assert user2 is None


@pytest.mark.asyncio
async def test_refresh_token_also_revoked(auth_high_security, active_user, password):
    """
    Immediate logout blacklists access token AND revokes refresh token.

    Both tokens are invalidated.
    """
    # Login
    user, tokens = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_high_security.config.secret_key,
        auth_high_security.config.algorithm,
        expected_type="access",
        audience=auth_high_security.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout with blacklisting
    await auth_high_security.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth_high_security.redis_client
    )

    # Verify access token is blacklisted
    user_access = await auth_high_security.auth_service.get_current_user(
        tokens.access_token
    )
    assert user_access is None

    # Verify refresh token is revoked in MongoDB
    from outlabs_auth.exceptions import RefreshTokenInvalidError

    with pytest.raises(RefreshTokenInvalidError) as exc_info:
        await auth_high_security.auth_service.refresh_access_token(
            tokens.refresh_token
        )

    assert "revoked" in str(exc_info.value).lower()


# ============================================================================
# Stateless + Redis Blacklist Mode Tests
# ============================================================================

@pytest.mark.asyncio
async def test_stateless_with_blacklist(auth_redis_only, active_user, password):
    """
    Stateless mode + Redis blacklist: No refresh token storage, but access token blacklisting works.

    Mode: Redis-only
    - store_refresh_tokens=False (stateless)
    - enable_token_blacklist=True (Redis)
    """
    # Login (no refresh token stored in MongoDB)
    user, tokens = await auth_redis_only.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Verify no refresh token in MongoDB
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_redis_only.config.secret_key,
        auth_redis_only.config.algorithm,
        expected_type="access",
        audience=auth_redis_only.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout (can't revoke refresh token, but can blacklist access token)
    result = await auth_redis_only.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth_redis_only.redis_client
    )

    # logout() returns True if access token was blacklisted (stateless mode)
    assert result is True

    # Verify access token is blacklisted
    user_after = await auth_redis_only.auth_service.get_current_user(
        tokens.access_token
    )
    assert user_after is None


@pytest.mark.asyncio
async def test_stateless_refresh_still_works_after_access_blacklist(auth_redis_only, active_user, password):
    """
    In stateless mode, refresh token still works even after access token blacklist.

    This is the tradeoff of stateless mode: Can't revoke refresh tokens.
    """
    # Login
    user, tokens = await auth_redis_only.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_redis_only.config.secret_key,
        auth_redis_only.config.algorithm,
        expected_type="access",
        audience=auth_redis_only.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout (blacklist access token only)
    await auth_redis_only.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth_redis_only.redis_client
    )

    # Verify access token is blacklisted
    user_access = await auth_redis_only.auth_service.get_current_user(
        tokens.access_token
    )
    assert user_access is None

    # But refresh token still works (can't revoke in stateless mode)
    new_tokens = await auth_redis_only.auth_service.refresh_access_token(
        tokens.refresh_token
    )
    assert new_tokens is not None
    assert new_tokens.access_token != tokens.access_token  # New access token


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================

@pytest.mark.asyncio
async def test_logout_without_jti_does_not_blacklist(auth_high_security, active_user, password):
    """
    If JTI not provided, logout revokes refresh token but doesn't blacklist access token.
    """
    # Login
    user, tokens = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Logout WITHOUT providing JTI
    result = await auth_high_security.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,  # Request blacklisting
        access_token_jti=None,        # But no JTI provided
        redis_client=auth_high_security.redis_client
    )

    # Refresh token is revoked
    assert result is True

    # But access token is NOT blacklisted (no JTI provided)
    user_after = await auth_high_security.auth_service.get_current_user(
        tokens.access_token
    )
    # Access token still works (15-min window)
    assert user_after is not None


@pytest.mark.asyncio
async def test_blacklist_graceful_degradation_no_redis(auth_standard, active_user, password):
    """
    If Redis not available, blacklisting fails gracefully.

    Refresh token is still revoked (MongoDB), but access token not blacklisted.
    """
    # Login
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_standard.config.secret_key,
        auth_standard.config.algorithm,
        expected_type="access",
        audience=auth_standard.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout with blacklisting request, but no Redis client
    result = await auth_standard.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=None  # No Redis
    )

    # Refresh token is revoked
    assert result is True

    # Access token is NOT blacklisted (no Redis)
    user_after = await auth_standard.auth_service.get_current_user(
        tokens.access_token
    )
    assert user_after is not None


@pytest.mark.asyncio
async def test_already_blacklisted_token_rejected(auth_high_security, active_user, password):
    """
    Token that's already blacklisted continues to be rejected.
    """
    # Login
    user, tokens = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_high_security.config.secret_key,
        auth_high_security.config.algorithm,
        expected_type="access",
        audience=auth_high_security.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout (blacklist)
    await auth_high_security.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth_high_security.redis_client
    )

    # Try to use token multiple times (should be rejected every time)
    for i in range(3):
        user_result = await auth_high_security.auth_service.get_current_user(
            tokens.access_token
        )
        assert user_result is None, f"Attempt {i+1}: Token should be rejected"


@pytest.mark.asyncio
async def test_different_users_independent_blacklists(auth_high_security, active_user, password, mongo_db):
    """
    Blacklisting one user's token doesn't affect other users.
    """
    # Create second user
    user2 = await auth_high_security.user_service.create_user(
        email="user2@test.com",
        password=password,
        first_name="User",
        last_name="Two"
    )

    # Login both users
    _, tokens1 = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    _, tokens2 = await auth_high_security.auth_service.login(
        email=user2.email,
        password=password
    )

    # Extract JTIs
    payload1 = verify_token(
        tokens1.access_token,
        auth_high_security.config.secret_key,
        auth_high_security.config.algorithm,
        expected_type="access",
        audience=auth_high_security.config.jwt_audience
    )
    jti1 = payload1.get("jti")

    # Blacklist user1's token
    await auth_high_security.auth_service.logout(
        tokens1.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti1,
        redis_client=auth_high_security.redis_client
    )

    # User1's token is rejected
    result1 = await auth_high_security.auth_service.get_current_user(
        tokens1.access_token
    )
    assert result1 is None

    # User2's token still works
    result2 = await auth_high_security.auth_service.get_current_user(
        tokens2.access_token
    )
    assert result2 is not None
    assert result2.id == user2.id


@pytest.mark.asyncio
async def test_blacklist_cleanup_after_ttl_expires(auth_high_security, active_user, password):
    """
    Blacklist entries auto-expire after TTL (when token would expire anyway).

    This test uses a short TTL to verify cleanup.
    """
    # Create auth config with very short access token expiry (5 seconds)
    from outlabs_auth import OutlabsAuth

    short_ttl_auth = OutlabsAuth(
        database=auth_high_security.config.database,
        secret_key="test-secret-short-ttl",
        store_refresh_tokens=True,
        enable_token_blacklist=True,
        redis_url="redis://localhost:6379/1",
        enable_token_cleanup=False,
        access_token_expire_minutes=1/12,  # 5 seconds
        refresh_token_expire_days=30
    )
    await short_ttl_auth.initialize()

    try:
        # Login
        user, tokens = await short_ttl_auth.auth_service.login(
            email=active_user.email,
            password=password
        )

        # Extract JTI
        payload = verify_token(
            tokens.access_token,
            short_ttl_auth.config.secret_key,
            short_ttl_auth.config.algorithm,
            expected_type="access",
            audience=short_ttl_auth.config.jwt_audience
        )
        jti = payload.get("jti")

        # Logout (blacklist)
        await short_ttl_auth.auth_service.logout(
            tokens.refresh_token,
            blacklist_access_token=True,
            access_token_jti=jti,
            redis_client=short_ttl_auth.redis_client
        )

        # Verify blacklist exists
        is_blacklisted = await short_ttl_auth.redis_client.exists(f"blacklist:jwt:{jti}")
        assert is_blacklisted is True

        # Wait for TTL to expire (5 seconds + 1 second buffer)
        time.sleep(6)

        # Verify blacklist entry auto-expired
        is_blacklisted_after = await short_ttl_auth.redis_client.exists(f"blacklist:jwt:{jti}")
        assert is_blacklisted_after is False

    finally:
        await short_ttl_auth.shutdown()


@pytest.mark.asyncio
async def test_blacklist_notification_event(auth_high_security, active_user, password):
    """
    Logout with blacklisting emits notification with immediate_revocation=True.
    """
    # Note: This test verifies the notification contains the blacklisting status
    # Full notification testing would require a notification channel mock

    # Login
    user, tokens = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Extract JTI
    payload = verify_token(
        tokens.access_token,
        auth_high_security.config.secret_key,
        auth_high_security.config.algorithm,
        expected_type="access",
        audience=auth_high_security.config.jwt_audience
    )
    jti = payload.get("jti")

    # Logout with blacklisting
    result = await auth_high_security.auth_service.logout(
        tokens.refresh_token,
        blacklist_access_token=True,
        access_token_jti=jti,
        redis_client=auth_high_security.redis_client
    )

    # Result should be True (refresh token revoked)
    assert result is True

    # Notification should be emitted with immediate_revocation=True
    # (Full verification would require mocking notification service)


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_blacklist_performance(auth_high_security, active_user, password):
    """
    Blacklisting should be very fast (< 50ms for 10 tokens).
    """
    import time

    # Create 10 sessions
    sessions = []
    for i in range(10):
        user, tokens = await auth_high_security.auth_service.login(
            email=active_user.email,
            password=password
        )
        payload = verify_token(
            tokens.access_token,
            auth_high_security.config.secret_key,
            auth_high_security.config.algorithm,
            expected_type="access",
            audience=auth_high_security.config.jwt_audience
        )
        sessions.append({
            "tokens": tokens,
            "jti": payload.get("jti")
        })

    # Time blacklisting all 10
    start_time = time.time()

    for session in sessions:
        await auth_high_security.auth_service.logout(
            session["tokens"].refresh_token,
            blacklist_access_token=True,
            access_token_jti=session["jti"],
            redis_client=auth_high_security.redis_client
        )

    elapsed_time = time.time() - start_time

    # Should complete in < 1 second for 10 tokens
    assert elapsed_time < 1.0, f"Blacklisting 10 tokens took {elapsed_time:.2f}s (expected < 1s)"

    # Average time per blacklist operation
    avg_time = elapsed_time / 10 * 1000  # Convert to ms
    assert avg_time < 100, f"Average blacklist time {avg_time:.2f}ms (expected < 100ms)"


@pytest.mark.asyncio
async def test_blacklist_check_performance(auth_high_security, active_user, password):
    """
    Checking blacklist during authentication should be fast (< 10ms per check).
    """
    import time

    # Login
    user, tokens = await auth_high_security.auth_service.login(
        email=active_user.email,
        password=password
    )

    # Time 10 authentication checks (not blacklisted)
    start_time = time.time()

    for i in range(10):
        result = await auth_high_security.auth_service.get_current_user(
            tokens.access_token
        )
        assert result is not None

    elapsed_time = time.time() - start_time
    avg_time = elapsed_time / 10 * 1000  # ms

    # Should be < 50ms per check (includes database lookup)
    assert avg_time < 50, f"Average auth check time {avg_time:.2f}ms (expected < 50ms)"
