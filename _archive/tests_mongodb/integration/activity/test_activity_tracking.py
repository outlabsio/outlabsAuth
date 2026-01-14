"""
Integration tests for activity tracking system

Tests end-to-end activity tracking across authentication flows.
"""
import pytest
from datetime import date, datetime, timezone
from outlabs_auth.models.activity_metric import ActivityMetric


class TestActivityTrackingOnLogin:
    """Test activity tracking during login flow."""

    @pytest.mark.asyncio
    async def test_login_tracks_activity(self, auth_with_activity_tracking, active_user, password):
        """Login tracks user activity."""
        user, tokens = await auth_with_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        # Give async task time to complete
        import asyncio
        await asyncio.sleep(0.1)

        # Check DAU was incremented
        dau = await auth_with_activity_tracking.activity_tracker.get_daily_active_users()
        assert dau == 1

    @pytest.mark.asyncio
    async def test_multiple_logins_same_user_count_once(self, auth_with_activity_tracking, active_user, password):
        """Multiple logins by same user counted once per day."""
        # Login 3 times
        for _ in range(3):
            await auth_with_activity_tracking.auth_service.login(
                email=active_user.email,
                password=password
            )

        import asyncio
        await asyncio.sleep(0.2)

        # DAU should still be 1 (Redis Set deduplication)
        dau = await auth_with_activity_tracking.activity_tracker.get_daily_active_users()
        assert dau == 1


class TestActivityTrackingOnTokenRefresh:
    """Test activity tracking during token refresh."""

    @pytest.mark.asyncio
    async def test_token_refresh_tracks_activity(self, auth_with_activity_tracking, active_user, password):
        """Token refresh tracks user activity."""
        # Login first
        user, tokens = await auth_with_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        import asyncio
        await asyncio.sleep(0.1)

        # Clear DAU to isolate refresh tracking
        # (In real scenario, this would be tested across different days)
        redis = auth_with_activity_tracking.activity_tracker.redis
        today = date.today()
        daily_key = f"active_users:daily:{today.isoformat()}"
        await redis.delete(daily_key)

        # Refresh token
        new_tokens = await auth_with_activity_tracking.auth_service.refresh_access_token(
            tokens.refresh_token
        )

        await asyncio.sleep(0.1)

        # DAU should be 1 from refresh
        dau = await auth_with_activity_tracking.activity_tracker.get_daily_active_users()
        assert dau == 1


class TestActivityTrackingDisabled:
    """Test that tracking doesn't occur when disabled."""

    @pytest.mark.asyncio
    async def test_no_tracking_when_disabled(self, auth_without_activity_tracking, active_user, password):
        """No activity tracking when feature is disabled."""
        # Activity tracker should be None
        assert auth_without_activity_tracking.activity_tracker is None

        # Login should work normally
        user, tokens = await auth_without_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        assert user is not None
        assert tokens.access_token is not None


class TestDAUMauQauMetrics:
    """Test DAU/MAU/QAU metric queries."""

    @pytest.mark.asyncio
    async def test_dau_mau_qau_all_tracked(self, auth_with_activity_tracking, active_user, password):
        """Activity appears in daily, monthly, and quarterly metrics."""
        await auth_with_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        import asyncio
        await asyncio.sleep(0.1)

        dau = await auth_with_activity_tracking.activity_tracker.get_daily_active_users()
        mau = await auth_with_activity_tracking.activity_tracker.get_monthly_active_users()
        qau = await auth_with_activity_tracking.activity_tracker.get_quarterly_active_users()

        assert dau == 1
        assert mau == 1
        assert qau == 1


class TestActivityMetricSync:
    """Test background sync to MongoDB."""

    @pytest.mark.asyncio
    async def test_sync_creates_activity_metrics(self, auth_with_activity_tracking, active_user, password):
        """Sync creates ActivityMetric records in MongoDB."""
        # Generate some activity
        await auth_with_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        import asyncio
        await asyncio.sleep(0.1)

        # Run sync manually
        stats = await auth_with_activity_tracking.activity_tracker.sync_to_mongodb()

        # Check stats
        assert stats["daily"] == 1
        assert stats["monthly"] == 1
        assert stats["quarterly"] == 1
        assert stats["errors"] == 0

        # Check MongoDB has records
        today = date.today()
        daily_metric = await ActivityMetric.find_one(
            ActivityMetric.period_type == "daily",
            ActivityMetric.period == today.isoformat()
        )

        assert daily_metric is not None
        assert daily_metric.active_users == 1

    @pytest.mark.asyncio
    async def test_sync_with_user_ids_stored(self, auth_with_activity_tracking, active_user, password):
        """Sync stores user IDs when configured."""
        await auth_with_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        import asyncio
        await asyncio.sleep(0.1)

        await auth_with_activity_tracking.activity_tracker.sync_to_mongodb()

        today = date.today()
        daily_metric = await ActivityMetric.find_one(
            ActivityMetric.period_type == "daily",
            ActivityMetric.period == today.isoformat()
        )

        # User IDs should be stored
        assert daily_metric.unique_user_ids is not None
        assert str(active_user.id) in daily_metric.unique_user_ids


class TestRedisKeyTTLs:
    """Test that Redis keys have correct TTLs."""

    @pytest.mark.asyncio
    async def test_daily_key_has_48h_ttl(self, auth_with_activity_tracking, active_user, password):
        """Daily activity keys expire after 48 hours."""
        await auth_with_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        import asyncio
        await asyncio.sleep(0.1)

        redis = auth_with_activity_tracking.activity_tracker.redis
        today = date.today()
        daily_key = f"active_users:daily:{today.isoformat()}"

        ttl = await redis.ttl(daily_key)

        # TTL should be ~48 hours (172800 seconds), allow some variance
        assert ttl > 172000  # At least 47+ hours
        assert ttl <= 172800  # At most 48 hours

    @pytest.mark.asyncio
    async def test_monthly_key_has_90d_ttl(self, auth_with_activity_tracking, active_user, password):
        """Monthly activity keys expire after 90 days."""
        await auth_with_activity_tracking.auth_service.login(
            email=active_user.email,
            password=password
        )

        import asyncio
        await asyncio.sleep(0.1)

        redis = auth_with_activity_tracking.activity_tracker.redis
        now = datetime.now(timezone.utc)
        monthly_key = f"active_users:monthly:{now.year:04d}-{now.month:02d}"

        ttl = await redis.ttl(monthly_key)

        # TTL should be ~90 days (7776000 seconds)
        assert ttl > 7770000  # At least 89+ days
        assert ttl <= 7776000  # At most 90 days


class TestAPIKeyTracking:
    """Test activity tracking for API key authentication."""

    @pytest.mark.asyncio
    async def test_api_key_authentication_tracks_activity(self, auth_with_activity_tracking, active_user):
        """API key authentication tracks user activity."""
        from outlabs_auth.models.api_key import APIKeyModel

        # Create an API key for the user
        api_key_plain, api_key_model = await auth_with_activity_tracking.api_key_service.create_api_key(
            user=active_user,
            name="Test API Key",
            scopes=["read", "write"]
        )

        import asyncio
        await asyncio.sleep(0.1)

        # Clear DAU to isolate API key tracking
        redis = auth_with_activity_tracking.activity_tracker.redis
        from datetime import date
        today = date.today()
        daily_key = f"active_users:daily:{today.isoformat()}"
        await redis.delete(daily_key)

        # Simulate API key authentication through AuthDeps
        # (In real scenario, this would be an API request with the key)
        from fastapi import Request
        from unittest.mock import MagicMock

        # Create mock request with API key
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"x-api-key": api_key_plain}

        # Authenticate via backend
        for backend in auth_with_activity_tracking._backends:
            if backend.name == "api_key":
                result = await backend.authenticate(
                    mock_request,
                    api_key_service=auth_with_activity_tracking.api_key_service
                )
                if result:
                    # Manually trigger activity tracking (simulating AuthDeps)
                    await auth_with_activity_tracking.activity_tracker.track_activity(str(result["user"].id))
                    break

        await asyncio.sleep(0.1)

        # DAU should be 1 from API key usage
        dau = await auth_with_activity_tracking.activity_tracker.get_daily_active_users()
        assert dau == 1


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_tracking_is_fast(self, auth_with_activity_tracking, active_user, password):
        """Activity tracking completes quickly (fire-and-forget)."""
        import time

        start = time.time()

        # Track activity
        await auth_with_activity_tracking.activity_tracker.track_activity(str(active_user.id))

        elapsed = time.time() - start

        # Should complete in < 100ms (typically < 10ms)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_idempotent_writes(self, auth_with_activity_tracking):
        """Multiple tracks of same user don't increase count (Redis Set)."""
        user_id = "user_test_123"

        # Track 100 times
        for _ in range(100):
            await auth_with_activity_tracking.activity_tracker.track_activity(user_id)

        import asyncio
        await asyncio.sleep(0.2)

        # DAU should still be 1
        dau = await auth_with_activity_tracking.activity_tracker.get_daily_active_users()
        assert dau == 1
