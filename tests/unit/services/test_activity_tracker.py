"""
Unit tests for ActivityTracker service

Tests Redis Set operations, DAU/MAU/QAU queries, and sync functionality.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from outlabs_auth.services.activity_tracker import ActivityTracker


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.sadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.set_raw = AsyncMock(return_value=True)
    redis.scard = AsyncMock(return_value=0)
    redis.scan = AsyncMock(return_value=(0, []))
    redis.get_raw = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def activity_tracker(mock_redis):
    """ActivityTracker instance with mock Redis."""
    return ActivityTracker(
        redis_client=mock_redis,
        enabled=True,
        update_user_model=True,
        store_user_ids=False,
    )


class TestActivityTracking:
    """Test activity tracking operations."""

    @pytest.mark.asyncio
    async def test_track_activity_adds_to_daily_set(self, activity_tracker, mock_redis):
        """Track activity adds user to daily Redis Set."""
        user_id = "user_123"
        await activity_tracker.track_activity(user_id)

        # Check daily set was called
        today = date.today()
        daily_key = f"active_users:daily:{today.isoformat()}"
        mock_redis.sadd.assert_any_call(daily_key, user_id)
        mock_redis.expire.assert_any_call(daily_key, 48 * 3600)

    @pytest.mark.asyncio
    async def test_track_activity_adds_to_monthly_set(
        self, activity_tracker, mock_redis
    ):
        """Track activity adds user to monthly Redis Set."""
        user_id = "user_123"
        await activity_tracker.track_activity(user_id)

        # Check monthly set was called
        now = datetime.now(timezone.utc)
        monthly_key = f"active_users:monthly:{now.year:04d}-{now.month:02d}"
        mock_redis.sadd.assert_any_call(monthly_key, user_id)
        mock_redis.expire.assert_any_call(monthly_key, 90 * 86400)

    @pytest.mark.asyncio
    async def test_track_activity_adds_to_quarterly_set(
        self, activity_tracker, mock_redis
    ):
        """Track activity adds user to quarterly Redis Set."""
        user_id = "user_123"
        await activity_tracker.track_activity(user_id)

        # Check quarterly set was called
        now = datetime.now(timezone.utc)
        quarter = (now.month - 1) // 3 + 1
        quarterly_key = f"active_users:quarterly:{now.year:04d}-Q{quarter}"
        mock_redis.sadd.assert_any_call(quarterly_key, user_id)
        mock_redis.expire.assert_any_call(quarterly_key, 365 * 86400)

    @pytest.mark.asyncio
    async def test_track_activity_updates_last_activity_timestamp(
        self, activity_tracker, mock_redis
    ):
        """Track activity stores last_activity timestamp in Redis."""
        user_id = "user_123"
        await activity_tracker.track_activity(user_id)

        # Check last_activity key was set
        last_activity_key = f"last_activity:{user_id}"
        mock_redis.set_raw.assert_called()
        assert any(
            last_activity_key in str(call) for call in mock_redis.set_raw.call_args_list
        )

    @pytest.mark.asyncio
    async def test_track_activity_when_disabled(self, mock_redis):
        """Track activity does nothing when disabled."""
        tracker = ActivityTracker(redis_client=mock_redis, enabled=False)

        await tracker.track_activity("user_123")

        # No Redis calls should be made
        mock_redis.sadd.assert_not_called()
        mock_redis.set_raw.assert_not_called()

    @pytest.mark.asyncio
    async def test_track_activity_never_raises_exception(self, mock_redis):
        """Track activity swallows all exceptions (non-blocking)."""
        # Make Redis raise an exception
        mock_redis.sadd.side_effect = Exception("Redis connection failed")

        tracker = ActivityTracker(redis_client=mock_redis, enabled=True)

        # Should not raise
        await tracker.track_activity("user_123")

    @pytest.mark.asyncio
    async def test_get_daily_active_users_default_today(
        self, activity_tracker, mock_redis
    ):
        """Get DAU with no args returns today's count."""
        mock_redis.scard.return_value = 42

        dau = await activity_tracker.get_daily_active_users()

        assert dau == 42
        today = date.today()
        daily_key = f"active_users:daily:{today.isoformat()}"
        mock_redis.scard.assert_called_with(daily_key)

    @pytest.mark.asyncio
    async def test_get_daily_active_users_specific_date(
        self, activity_tracker, mock_redis
    ):
        """Get DAU for specific date."""
        mock_redis.scard.return_value = 100
        specific_date = date(2025, 1, 15)

        dau = await activity_tracker.get_daily_active_users(specific_date)

        assert dau == 100
        daily_key = "active_users:daily:2025-01-15"
        mock_redis.scard.assert_called_with(daily_key)

    @pytest.mark.asyncio
    async def test_get_monthly_active_users_default_current(
        self, activity_tracker, mock_redis
    ):
        """Get MAU with no args returns current month's count."""
        mock_redis.scard.return_value = 1234

        mau = await activity_tracker.get_monthly_active_users()

        assert mau == 1234
        now = datetime.now(timezone.utc)
        monthly_key = f"active_users:monthly:{now.year:04d}-{now.month:02d}"
        mock_redis.scard.assert_called_with(monthly_key)

    @pytest.mark.asyncio
    async def test_get_monthly_active_users_specific_month(
        self, activity_tracker, mock_redis
    ):
        """Get MAU for specific month."""
        mock_redis.scard.return_value = 5000

        mau = await activity_tracker.get_monthly_active_users(2025, 1)

        assert mau == 5000
        monthly_key = "active_users:monthly:2025-01"
        mock_redis.scard.assert_called_with(monthly_key)

    @pytest.mark.asyncio
    async def test_get_quarterly_active_users_default_current(
        self, activity_tracker, mock_redis
    ):
        """Get QAU with no args returns current quarter's count."""
        mock_redis.scard.return_value = 10000

        qau = await activity_tracker.get_quarterly_active_users()

        assert qau == 10000
        now = datetime.now(timezone.utc)
        quarter = (now.month - 1) // 3 + 1
        quarterly_key = f"active_users:quarterly:{now.year:04d}-Q{quarter}"
        mock_redis.scard.assert_called_with(quarterly_key)

    @pytest.mark.asyncio
    async def test_get_quarterly_active_users_specific_quarter(
        self, activity_tracker, mock_redis
    ):
        """Get QAU for specific quarter."""
        mock_redis.scard.return_value = 15000

        qau = await activity_tracker.get_quarterly_active_users(2025, 1)

        assert qau == 15000
        quarterly_key = "active_users:quarterly:2025-Q1"
        mock_redis.scard.assert_called_with(quarterly_key)


class TestKeyGeneration:
    """Test Redis key generation helpers."""

    def test_make_daily_key(self, activity_tracker):
        """Daily key format is correct."""
        test_date = date(2025, 1, 24)
        key = activity_tracker._make_daily_key(test_date)
        assert key == "active_users:daily:2025-01-24"

    def test_make_monthly_key(self, activity_tracker):
        """Monthly key format is correct."""
        key = activity_tracker._make_monthly_key(2025, 1)
        assert key == "active_users:monthly:2025-01"

        key = activity_tracker._make_monthly_key(2025, 12)
        assert key == "active_users:monthly:2025-12"

    def test_make_quarterly_key(self, activity_tracker):
        """Quarterly key format is correct."""
        key = activity_tracker._make_quarterly_key(2025, 1)
        assert key == "active_users:quarterly:2025-Q1"

        key = activity_tracker._make_quarterly_key(2025, 4)
        assert key == "active_users:quarterly:2025-Q4"


class TestSyncToDatabase:
    """Test database sync operations (unit-level)."""

    @pytest.mark.asyncio
    async def test_sync_aggregates_counts(self, activity_tracker):
        session = AsyncMock()

        with (
            patch.object(
                activity_tracker,
                "_upsert_metric",
                new=AsyncMock(side_effect=[3, 10, 25]),
            ),
            patch.object(
                activity_tracker,
                "_batch_update_last_activity",
                new=AsyncMock(return_value=3),
            ),
            patch.object(
                activity_tracker,
                "_cleanup_old_metrics",
                new=AsyncMock(return_value=None),
            ),
        ):
            stats = await activity_tracker.sync_to_database(session)

        assert stats["daily"] == 3
        assert stats["monthly"] == 10
        assert stats["quarterly"] == 25
        assert stats["users_updated"] == 3
