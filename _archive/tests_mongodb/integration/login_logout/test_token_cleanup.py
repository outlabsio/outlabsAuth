"""
Test Token Cleanup Worker

Tests for the background cleanup worker that removes:
1. Expired refresh tokens
2. Old revoked tokens (>7 days)
3. Expired OAuth states

Covers:
- cleanup_expired_refresh_tokens() function
- cleanup_expired_oauth_states() function
- cleanup_all() function
- Retention period handling
- Edge cases and error scenarios
"""
import pytest
from datetime import datetime, timedelta, timezone
import hashlib

from outlabs_auth.models.token import RefreshTokenModel
from outlabs_auth.workers.token_cleanup import (
    cleanup_expired_refresh_tokens,
    cleanup_expired_oauth_states,
    cleanup_all
)


# ============================================================================
# Expired Token Cleanup Tests
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_deletes_expired_tokens(auth_standard, active_user, expired_refresh_token):
    """Cleanup deletes tokens past their expires_at date."""
    # Verify expired token exists
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1
    assert all_tokens[0].id == expired_refresh_token.id

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify expired token was deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    # Check stats
    assert stats["expired"] == 1
    assert stats["revoked"] == 0
    assert stats["total"] == 1


@pytest.mark.asyncio
async def test_cleanup_keeps_valid_tokens(auth_standard, active_user):
    """Cleanup does NOT delete valid (not expired) tokens."""
    # Login to create valid token
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password="Password123!"
    )

    # Verify token exists
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify token still exists
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1

    # Check stats
    assert stats["expired"] == 0
    assert stats["revoked"] == 0
    assert stats["total"] == 0


@pytest.mark.asyncio
async def test_cleanup_deletes_multiple_expired_tokens(auth_standard, active_user):
    """Cleanup deletes multiple expired tokens in one pass."""
    # Create 3 expired tokens
    for i in range(3):
        token_value = f"fake_expired_token_{i}"
        token_hash = hashlib.sha256(token_value.encode()).hexdigest()

        expired_token = RefreshTokenModel(
            user=active_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=i+1),
            device_name=f"Device {i}"
        )
        await expired_token.save()

    # Verify 3 tokens exist
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 3

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify all expired tokens deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    # Check stats
    assert stats["expired"] == 3
    assert stats["total"] == 3


@pytest.mark.asyncio
async def test_cleanup_handles_edge_case_just_expired(auth_standard, active_user):
    """Cleanup deletes token that expired exactly now."""
    # Create token that expires right now (within 1 second)
    token_value = "fake_just_expired_token"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    just_expired = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),  # 1 second ago
        device_name="Test Device"
    )
    await just_expired.save()

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify token was deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    assert stats["expired"] == 1


# ============================================================================
# Revoked Token Cleanup Tests
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_deletes_old_revoked_tokens(auth_standard, active_user, old_revoked_token):
    """Cleanup deletes revoked tokens older than retention period (7 days)."""
    # Verify old revoked token exists
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1
    assert all_tokens[0].is_revoked is True

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify old revoked token was deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    # Check stats
    assert stats["expired"] == 0
    assert stats["revoked"] == 1
    assert stats["total"] == 1


@pytest.mark.asyncio
async def test_cleanup_keeps_recent_revoked_tokens(auth_standard, active_user, recent_revoked_token):
    """Cleanup does NOT delete recently revoked tokens (<7 days)."""
    # Verify recent revoked token exists
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1
    assert all_tokens[0].is_revoked is True

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify token still exists (too recent to delete)
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1

    # Check stats
    assert stats["expired"] == 0
    assert stats["revoked"] == 0
    assert stats["total"] == 0


@pytest.mark.asyncio
async def test_cleanup_custom_retention_period(auth_standard, active_user):
    """Cleanup respects custom retention period for revoked tokens."""
    # Create revoked token that's 3 days old
    token_value = "fake_revoked_3days"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    revoked_token = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=27),
        is_revoked=True,
        revoked_at=datetime.now(timezone.utc) - timedelta(days=3),
        revoked_reason="Test"
    )
    await revoked_token.save()

    # Run cleanup with 2-day retention (should delete 3-day-old token)
    stats = await cleanup_expired_refresh_tokens(revoked_retention_days=2)

    # Verify token was deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    assert stats["revoked"] == 1

    # Create another 3-day-old revoked token
    revoked_token2 = RefreshTokenModel(
        user=active_user,
        token_hash=hashlib.sha256(b"another_token").hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=27),
        is_revoked=True,
        revoked_at=datetime.now(timezone.utc) - timedelta(days=3),
        revoked_reason="Test"
    )
    await revoked_token2.save()

    # Run cleanup with 5-day retention (should NOT delete 3-day-old token)
    stats = await cleanup_expired_refresh_tokens(revoked_retention_days=5)

    # Verify token still exists
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1

    assert stats["revoked"] == 0


@pytest.mark.asyncio
async def test_cleanup_handles_revoked_token_at_exact_cutoff(auth_standard, active_user):
    """Cleanup handles revoked token at exact retention boundary (7 days)."""
    # Create token revoked exactly 7 days ago
    token_value = "fake_revoked_exactly_7days"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    exactly_7days = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=23),
        is_revoked=True,
        revoked_at=datetime.now(timezone.utc) - timedelta(days=7),
        revoked_reason="Test"
    )
    await exactly_7days.save()

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Token revoked exactly 7 days ago should be deleted (< means older than cutoff)
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    assert stats["revoked"] == 1


# ============================================================================
# Mixed Scenario Tests
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_deletes_both_expired_and_revoked(
    auth_standard,
    active_user,
    expired_refresh_token,
    old_revoked_token
):
    """Cleanup deletes both expired AND old revoked tokens in one pass."""
    # Verify both tokens exist
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 2

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify both tokens deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    # Check stats
    assert stats["expired"] == 1
    assert stats["revoked"] == 1
    assert stats["total"] == 2


@pytest.mark.asyncio
async def test_cleanup_mixed_tokens_keeps_valid_ones(
    auth_standard,
    active_user,
    expired_refresh_token,
    old_revoked_token,
    recent_revoked_token
):
    """Cleanup deletes expired/old revoked but keeps valid/recent revoked."""
    # Create one valid active token
    user, tokens = await auth_standard.auth_service.login(
        email=active_user.email,
        password="Password123!"
    )

    # Verify 4 tokens exist (1 expired, 1 old revoked, 1 recent revoked, 1 valid)
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 4

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify 2 tokens remain (valid + recent revoked)
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 2

    # Check which tokens remain
    remaining_tokens = {t.id for t in all_tokens}
    assert recent_revoked_token.id in remaining_tokens  # Recent revoked kept

    # One of the remaining should be the valid token
    valid_tokens = [t for t in all_tokens if not t.is_revoked]
    assert len(valid_tokens) == 1

    # Check stats
    assert stats["expired"] == 1
    assert stats["revoked"] == 1
    assert stats["total"] == 2


@pytest.mark.asyncio
async def test_cleanup_handles_large_batch(auth_standard, active_user):
    """Cleanup efficiently handles large number of expired tokens."""
    # Create 100 expired tokens
    for i in range(100):
        token_value = f"fake_expired_token_{i}"
        token_hash = hashlib.sha256(token_value.encode()).hexdigest()

        expired_token = RefreshTokenModel(
            user=active_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            device_name=f"Device {i}"
        )
        await expired_token.save()

    # Verify 100 tokens exist
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 100

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify all deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    # Check stats
    assert stats["expired"] == 100
    assert stats["total"] == 100


# ============================================================================
# OAuth State Cleanup Tests
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_oauth_states_deletes_expired(auth_standard, mongo_db):
    """Cleanup deletes expired OAuth state records."""
    try:
        from outlabs_auth.models.oauth_state import OAuthState
        import beanie

        # Initialize OAuthState collection for this test
        await beanie.init_beanie(
            database=mongo_db,
            document_models=[OAuthState]
        )

        # Create expired OAuth state (2 hours old)
        old_state = OAuthState(
            state="expired_state_123",
            provider="google",
            redirect_uri="http://localhost/callback",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=110)
        )
        await old_state.insert()

        # Run cleanup (retention=1 hour, so 2-hour-old state should be deleted)
        stats = await cleanup_expired_oauth_states(retention_hours=1)

        # Verify state was deleted
        all_states = await OAuthState.find_all().to_list()
        assert len(all_states) == 0

        assert stats["deleted"] == 1

    except ImportError:
        pytest.skip("OAuth module not available")


@pytest.mark.asyncio
async def test_cleanup_oauth_states_keeps_recent(auth_standard, mongo_db):
    """Cleanup does NOT delete recent OAuth states."""
    try:
        from outlabs_auth.models.oauth_state import OAuthState
        import beanie

        # Initialize OAuthState collection for this test
        await beanie.init_beanie(
            database=mongo_db,
            document_models=[OAuthState]
        )

        # Create recent OAuth state (30 minutes old)
        recent_state = OAuthState(
            state="recent_state_456",
            provider="google",
            redirect_uri="http://localhost/callback",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
        )
        await recent_state.insert()

        # Run cleanup (retention=1 hour, so 30-min-old state should be kept)
        stats = await cleanup_expired_oauth_states(retention_hours=1)

        # Verify state still exists
        all_states = await OAuthState.find_all().to_list()
        assert len(all_states) == 1

        assert stats["deleted"] == 0

    except ImportError:
        pytest.skip("OAuth module not available")


@pytest.mark.asyncio
async def test_cleanup_oauth_states_handles_no_oauth_module(auth_standard):
    """Cleanup gracefully handles missing OAuth module."""
    # This test ensures cleanup doesn't crash if OAuth is not installed
    stats = await cleanup_expired_oauth_states()

    # Should return 0 deleted (gracefully skip)
    assert "deleted" in stats
    assert stats["deleted"] == 0


# ============================================================================
# cleanup_all() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_all_runs_all_cleanup_tasks(
    auth_standard,
    mongo_db,
    active_user,
    expired_refresh_token,
    old_revoked_token
):
    """cleanup_all() runs both refresh token and OAuth state cleanup."""
    # Add OAuth state if available
    try:
        from outlabs_auth.models.oauth_state import OAuthState
        import beanie

        # Initialize OAuthState collection for this test
        await beanie.init_beanie(
            database=mongo_db,
            document_models=[OAuthState]
        )

        old_state = OAuthState(
            state="old_state_789",
            provider="google",
            redirect_uri="http://localhost/callback",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        await old_state.insert()
        has_oauth = True
    except ImportError:
        has_oauth = False

    # Run all cleanup tasks
    results = await cleanup_all()

    # Check results structure
    assert "refresh_tokens" in results
    assert "oauth_states" in results

    # Check refresh token cleanup
    assert results["refresh_tokens"]["expired"] == 1
    assert results["refresh_tokens"]["revoked"] == 1
    assert results["refresh_tokens"]["total"] == 2

    # Check OAuth state cleanup (if available)
    if has_oauth:
        assert results["oauth_states"]["deleted"] == 1

    # Verify tokens deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0


@pytest.mark.asyncio
async def test_cleanup_all_handles_empty_database(auth_standard):
    """cleanup_all() handles empty database gracefully."""
    # Run cleanup on empty database
    results = await cleanup_all()

    # Should return 0 for all counts
    assert results["refresh_tokens"]["expired"] == 0
    assert results["refresh_tokens"]["revoked"] == 0
    assert results["refresh_tokens"]["total"] == 0
    assert results["oauth_states"]["deleted"] == 0


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_empty_database_returns_zero(auth_standard):
    """Cleanup on empty database returns 0 for all counts."""
    stats = await cleanup_expired_refresh_tokens()

    assert stats["expired"] == 0
    assert stats["revoked"] == 0
    assert stats["total"] == 0


@pytest.mark.asyncio
async def test_cleanup_with_only_valid_tokens(auth_standard, active_user):
    """Cleanup with only valid tokens returns 0 deleted."""
    # Create 3 valid tokens
    for i in range(3):
        token_value = f"valid_token_{i}"
        token_hash = hashlib.sha256(token_value.encode()).hexdigest()

        valid_token = RefreshTokenModel(
            user=active_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            device_name=f"Device {i}"
        )
        await valid_token.save()

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify no tokens deleted
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 3

    assert stats["total"] == 0


@pytest.mark.asyncio
async def test_cleanup_idempotent(auth_standard, active_user, expired_refresh_token):
    """Running cleanup multiple times is safe (idempotent)."""
    # First cleanup
    stats1 = await cleanup_expired_refresh_tokens()
    assert stats1["expired"] == 1

    # Second cleanup (should find nothing)
    stats2 = await cleanup_expired_refresh_tokens()
    assert stats2["expired"] == 0
    assert stats2["total"] == 0

    # Third cleanup (still nothing)
    stats3 = await cleanup_expired_refresh_tokens()
    assert stats3["expired"] == 0
    assert stats3["total"] == 0


@pytest.mark.asyncio
async def test_cleanup_preserves_user_data(auth_standard, active_user, expired_refresh_token):
    """Cleanup deletes tokens but does NOT delete user data."""
    # Verify user exists
    user = await auth_standard.user_service.get_user_by_email(active_user.email)
    assert user is not None

    # Run cleanup
    await cleanup_expired_refresh_tokens()

    # Verify user still exists
    user_after = await auth_standard.user_service.get_user_by_email(active_user.email)
    assert user_after is not None
    assert user_after.id == user.id


@pytest.mark.asyncio
async def test_cleanup_with_timezone_naive_tokens(auth_standard, active_user):
    """Cleanup handles tokens with timezone-naive datetimes (edge case)."""
    # Note: Our models now ensure timezone-aware datetimes, but test edge case
    # where database might have old timezone-naive data

    # Create token with timezone-naive datetime (simulate old data)
    token_value = "timezone_naive_token"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    # Create with timezone-naive datetime (this shouldn't happen but test it)
    naive_expired = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.utcnow() - timedelta(days=1),  # Naive datetime
        device_name="Test Device"
    )
    await naive_expired.save()

    # Run cleanup (should handle timezone comparison gracefully)
    stats = await cleanup_expired_refresh_tokens()

    # Token should be deleted (comparison should work)
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 0

    assert stats["expired"] == 1


# ============================================================================
# Performance and Logging Tests
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_performance_large_dataset(auth_standard, active_user):
    """Cleanup performs well with large datasets (500 tokens)."""
    import time

    # Create 500 expired tokens
    for i in range(500):
        token_value = f"perf_test_token_{i}"
        token_hash = hashlib.sha256(token_value.encode()).hexdigest()

        expired_token = RefreshTokenModel(
            user=active_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            device_name=f"Device {i}"
        )
        await expired_token.save()

    # Time the cleanup
    start_time = time.time()
    stats = await cleanup_expired_refresh_tokens()
    elapsed_time = time.time() - start_time

    # Verify all deleted
    assert stats["expired"] == 500

    # Performance check: should complete in < 5 seconds for 500 tokens
    assert elapsed_time < 5.0, f"Cleanup took {elapsed_time:.2f}s (expected < 5s)"


@pytest.mark.asyncio
async def test_cleanup_returns_correct_statistics(
    auth_standard,
    active_user,
    expired_refresh_token,
    old_revoked_token,
    recent_revoked_token
):
    """Cleanup returns accurate statistics breakdown."""
    # Create one more expired token
    token_value = "another_expired"
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()

    another_expired = RefreshTokenModel(
        user=active_user,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(days=2),
        device_name="Test Device"
    )
    await another_expired.save()

    # Run cleanup
    stats = await cleanup_expired_refresh_tokens()

    # Verify stats breakdown
    assert stats["expired"] == 2  # 2 expired tokens
    assert stats["revoked"] == 1  # 1 old revoked token
    assert stats["total"] == 3    # Total: 3 deleted
    assert "error" not in stats   # No errors

    # Verify only recent revoked token remains
    all_tokens = await RefreshTokenModel.find_all().to_list()
    assert len(all_tokens) == 1
    assert all_tokens[0].id == recent_revoked_token.id
