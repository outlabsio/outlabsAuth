"""
Activity Tracker Service for DAU/MAU/WAU/QAU metrics

Uses Redis Sets for O(1) tracking with 99%+ write reduction.
Background worker syncs to MongoDB for historical analytics.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, date, timezone, timedelta
from redis.asyncio import Redis

from outlabs_auth.models.activity_metric import ActivityMetric
from outlabs_auth.models.user import UserModel

logger = logging.getLogger(__name__)


class ActivityTracker:
    """
    Track user activity for DAU/MAU/WAU/QAU metrics.

    Uses Redis Sets for O(1) tracking with 99%+ write reduction.
    Background worker syncs to MongoDB for historical analytics.

    Redis Keys:
    - active_users:daily:2025-01-24 (TTL: 48h)
    - active_users:monthly:2025-01 (TTL: 90d)
    - active_users:quarterly:2025-Q1 (TTL: 1y)
    - last_activity:{user_id} (TTL: 7d)
    """

    def __init__(
        self,
        redis_client: Redis,
        enabled: bool = True,
        update_user_model: bool = True,
        store_user_ids: bool = False,
    ):
        """
        Initialize ActivityTracker.

        Args:
            redis_client: Redis client instance
            enabled: Enable activity tracking (default: True)
            update_user_model: Update UserModel.last_activity (default: True)
            store_user_ids: Store user IDs in ActivityMetric for cohort analysis (default: False)
        """
        self.redis = redis_client
        self.enabled = enabled
        self.update_user_model = update_user_model
        self.store_user_ids = store_user_ids

    async def track_activity(self, user_id: str) -> None:
        """
        Track user activity (fire-and-forget, non-blocking).

        Adds user to Redis Sets for:
        - Daily: active_users:daily:2025-01-24
        - Monthly: active_users:monthly:2025-01
        - Quarterly: active_users:quarterly:2025-Q1
        - Last activity timestamp: last_activity:{user_id}

        Args:
            user_id: User ID to track

        Note: This method should NEVER raise exceptions to avoid blocking
              authenticated requests. All errors are logged and swallowed.
        """
        if not self.enabled:
            return

        try:
            now = datetime.now(timezone.utc)

            # Add to daily set
            daily_key = self._make_daily_key(now.date())
            await self.redis.sadd(daily_key, user_id)
            await self.redis.expire(daily_key, 48 * 3600)  # 48 hours

            # Add to monthly set
            monthly_key = self._make_monthly_key(now.year, now.month)
            await self.redis.sadd(monthly_key, user_id)
            await self.redis.expire(monthly_key, 90 * 86400)  # 90 days

            # Add to quarterly set
            quarter = (now.month - 1) // 3 + 1
            quarterly_key = self._make_quarterly_key(now.year, quarter)
            await self.redis.sadd(quarterly_key, user_id)
            await self.redis.expire(quarterly_key, 365 * 86400)  # 1 year

            # Update last_activity timestamp in Redis
            last_activity_key = f"last_activity:{user_id}"
            await self.redis.set(
                last_activity_key,
                now.isoformat(),
                ex=7 * 86400  # 7 days TTL
            )

            logger.debug(f"Tracked activity for user {user_id}")

        except Exception as e:
            # NEVER raise - log error and continue
            logger.error(f"Failed to track activity for user {user_id}: {e}", exc_info=True)

    async def get_daily_active_users(self, day: Optional[date] = None) -> int:
        """
        Get DAU count for a specific day (default: today).

        Args:
            day: Date to query (default: today)

        Returns:
            Count of unique active users for the day
        """
        if day is None:
            day = date.today()

        key = self._make_daily_key(day)
        count = await self.redis.scard(key)
        return count

    async def get_monthly_active_users(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> int:
        """
        Get MAU count for a specific month (default: current month).

        Args:
            year: Year to query (default: current year)
            month: Month to query (default: current month)

        Returns:
            Count of unique active users for the month
        """
        if year is None or month is None:
            now = datetime.now(timezone.utc)
            year, month = now.year, now.month

        key = self._make_monthly_key(year, month)
        count = await self.redis.scard(key)
        return count

    async def get_quarterly_active_users(
        self,
        year: Optional[int] = None,
        quarter: Optional[int] = None
    ) -> int:
        """
        Get QAU count for a specific quarter (default: current quarter).

        Args:
            year: Year to query (default: current year)
            quarter: Quarter to query (1-4, default: current quarter)

        Returns:
            Count of unique active users for the quarter
        """
        if year is None or quarter is None:
            now = datetime.now(timezone.utc)
            year = now.year
            quarter = (now.month - 1) // 3 + 1

        key = self._make_quarterly_key(year, quarter)
        count = await self.redis.scard(key)
        return count

    async def sync_to_mongodb(self) -> Dict[str, Any]:
        """
        Sync Redis activity data to MongoDB (run periodically by background worker).

        Creates ActivityMetric snapshots for historical analysis.
        Optionally updates UserModel.last_activity (batched).

        Returns:
            Statistics about the sync operation:
            {
                "daily": 1247,      # Users synced for daily metric
                "monthly": 45892,   # Users synced for monthly metric
                "quarterly": 128453,# Users synced for quarterly metric
                "users_updated": 1247,  # UserModel records updated
                "errors": 0         # Number of errors encountered
            }
        """
        stats = {
            "daily": 0,
            "monthly": 0,
            "quarterly": 0,
            "users_updated": 0,
            "errors": 0
        }

        try:
            now = datetime.now(timezone.utc)
            today = now.date()

            # 1. Sync daily metrics
            await self._sync_period(
                period_type="daily",
                period=today.isoformat(),
                key=self._make_daily_key(today),
                stats=stats,
                stats_key="daily"
            )

            # 2. Sync monthly metrics
            await self._sync_period(
                period_type="monthly",
                period=f"{now.year:04d}-{now.month:02d}",
                key=self._make_monthly_key(now.year, now.month),
                stats=stats,
                stats_key="monthly"
            )

            # 3. Sync quarterly metrics
            quarter = (now.month - 1) // 3 + 1
            await self._sync_period(
                period_type="quarterly",
                period=f"{now.year:04d}-Q{quarter}",
                key=self._make_quarterly_key(now.year, quarter),
                stats=stats,
                stats_key="quarterly"
            )

            # 4. Update UserModel.last_activity (batched)
            if self.update_user_model and stats["daily"] > 0:
                users_updated = await self._batch_update_last_activity()
                stats["users_updated"] = users_updated

            # 5. Cleanup old ActivityMetric records
            await self._cleanup_old_metrics()

            logger.info(
                f"Activity sync completed: "
                f"DAU={stats['daily']}, MAU={stats['monthly']}, QAU={stats['quarterly']}, "
                f"users_updated={stats['users_updated']}, errors={stats['errors']}"
            )

        except Exception as e:
            logger.error(f"Error syncing activity metrics: {e}", exc_info=True)
            stats["errors"] += 1

        return stats

    async def _sync_period(
        self,
        period_type: str,
        period: str,
        key: str,
        stats: Dict[str, Any],
        stats_key: str
    ) -> None:
        """
        Sync a single period (daily/monthly/quarterly) to MongoDB.

        Args:
            period_type: "daily", "monthly", or "quarterly"
            period: Period identifier (e.g., "2025-01-24", "2025-01", "2025-Q1")
            key: Redis key to read from
            stats: Statistics dict to update
            stats_key: Key in stats dict to update
        """
        try:
            # Get user IDs from Redis Set
            user_ids = await self.redis.smembers(key)

            if not user_ids:
                logger.debug(f"No activity for {period_type} period {period}")
                return

            # Convert bytes to strings (Redis returns bytes)
            user_ids = [uid.decode('utf-8') if isinstance(uid, bytes) else uid for uid in user_ids]
            count = len(user_ids)

            # Check if metric already exists
            existing_metric = await ActivityMetric.find_one(
                ActivityMetric.period_type == period_type,
                ActivityMetric.period == period
            )

            if existing_metric:
                # Update existing metric
                existing_metric.active_users = count
                if self.store_user_ids:
                    existing_metric.unique_user_ids = user_ids
                existing_metric.updated_at = datetime.now(timezone.utc)
                await existing_metric.save()
            else:
                # Create new metric
                metric = ActivityMetric(
                    period_type=period_type,
                    period=period,
                    active_users=count,
                    unique_user_ids=user_ids if self.store_user_ids else None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                await metric.save()

            stats[stats_key] = count
            logger.debug(f"Synced {period_type} metric for {period}: {count} users")

        except Exception as e:
            logger.error(f"Error syncing {period_type} period {period}: {e}", exc_info=True)
            stats["errors"] += 1

    async def _batch_update_last_activity(self) -> int:
        """
        Batch update UserModel.last_activity from Redis timestamps.

        Returns:
            Number of users updated
        """
        try:
            # Get all last_activity keys from Redis
            pattern = "last_activity:*"
            cursor = 0
            users_updated = 0
            batch_size = 100
            batch = []

            # Scan Redis for all last_activity keys
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

                for key in keys:
                    # Extract user_id from key
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    user_id = key_str.replace("last_activity:", "")

                    # Get timestamp from Redis
                    timestamp_str = await self.redis.get(key)
                    if timestamp_str:
                        timestamp_str = timestamp_str.decode('utf-8') if isinstance(timestamp_str, bytes) else timestamp_str
                        timestamp = datetime.fromisoformat(timestamp_str)

                        batch.append((user_id, timestamp))

                        # Process batch when it reaches batch_size
                        if len(batch) >= batch_size:
                            updated = await self._update_user_batch(batch)
                            users_updated += updated
                            batch = []

                if cursor == 0:
                    break

            # Process remaining batch
            if batch:
                updated = await self._update_user_batch(batch)
                users_updated += updated

            logger.debug(f"Updated last_activity for {users_updated} users")
            return users_updated

        except Exception as e:
            logger.error(f"Error batch updating last_activity: {e}", exc_info=True)
            return 0

    async def _update_user_batch(self, batch: list) -> int:
        """
        Update a batch of users' last_activity timestamps.

        Args:
            batch: List of (user_id, timestamp) tuples

        Returns:
            Number of users successfully updated
        """
        updated = 0
        for user_id, timestamp in batch:
            try:
                # Find and update user
                user = await UserModel.find_one(UserModel.id == user_id)
                if user:
                    user.last_activity = timestamp
                    await user.save()
                    updated += 1
            except Exception as e:
                logger.error(f"Error updating last_activity for user {user_id}: {e}")

        return updated

    async def _cleanup_old_metrics(self) -> None:
        """
        Cleanup old ActivityMetric records.

        Deletes metrics older than activity_ttl_days (default: 90 days).
        """
        try:
            # This would use config.activity_ttl_days, but we don't have access to config here
            # For now, hardcode to 90 days
            ttl_days = 90
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=ttl_days)

            result = await ActivityMetric.find(
                ActivityMetric.created_at < cutoff_date
            ).delete()

            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} old ActivityMetric records")

        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}", exc_info=True)

    # Helper methods for Redis key generation

    def _make_daily_key(self, day: date) -> str:
        """Generate Redis key for daily active users."""
        return f"active_users:daily:{day.isoformat()}"

    def _make_monthly_key(self, year: int, month: int) -> str:
        """Generate Redis key for monthly active users."""
        return f"active_users:monthly:{year:04d}-{month:02d}"

    def _make_quarterly_key(self, year: int, quarter: int) -> str:
        """Generate Redis key for quarterly active users."""
        return f"active_users:quarterly:{year:04d}-Q{quarter}"
