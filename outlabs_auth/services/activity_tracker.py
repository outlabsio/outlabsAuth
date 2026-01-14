"""
Activity Tracker Service for DAU/MAU/WAU/QAU metrics

Uses Redis Sets for O(1) tracking with 99%+ write reduction.
Background worker syncs to PostgreSQL for historical analytics.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, date, timezone, timedelta
from uuid import UUID

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.activity_metric import ActivityMetric
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.redis_client import RedisClient

logger = logging.getLogger(__name__)


class ActivityTracker:
    """
    Track user activity for DAU/MAU/WAU/QAU metrics.

    Uses Redis Sets for O(1) tracking with 99%+ write reduction.
    Background worker syncs to PostgreSQL for historical analytics.

    Redis Keys:
    - active_users:daily:2025-01-24 (TTL: 48h)
    - active_users:monthly:2025-01 (TTL: 90d)
    - active_users:quarterly:2025-Q1 (TTL: 1y)
    - last_activity:{user_id} (TTL: 7d)
    """

    def __init__(
        self,
        redis_client: RedisClient,
        enabled: bool = True,
        update_user_model: bool = True,
        store_user_ids: bool = False,
    ):
        """
        Initialize ActivityTracker.

        Args:
            redis_client: Redis client instance
            enabled: Enable activity tracking (default: True)
            update_user_model: Update User.last_activity (default: True)
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
            await self.redis.set_raw(last_activity_key, now.isoformat(), ttl=7 * 86400)

            logger.debug(f"Tracked activity for user {user_id}")

        except Exception as e:
            # NEVER raise - log error and continue
            logger.error(
                f"Failed to track activity for user {user_id}: {e}", exc_info=True
            )

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
        self, year: Optional[int] = None, month: Optional[int] = None
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
        self, year: Optional[int] = None, quarter: Optional[int] = None
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

    async def sync_to_database(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Sync Redis activity data to PostgreSQL (run periodically by background worker).

        Creates ActivityMetric snapshots for historical analysis.
        Optionally updates User.last_activity (batched).

        Returns:
            Statistics about the sync operation:
            {
                "daily": 1247,      # Users synced for daily metric
                "monthly": 45892,   # Users synced for monthly metric
                "quarterly": 128453,# Users synced for quarterly metric
                "users_updated": 1247,  # User records updated
                "errors": 0         # Number of errors encountered
            }
        """
        stats = {
            "daily": 0,
            "monthly": 0,
            "quarterly": 0,
            "users_updated": 0,
            "errors": 0,
        }

        try:
            now = datetime.now(timezone.utc)
            today = now.date()

            # 1. Sync daily metrics
            stats["daily"] = await self._upsert_metric(
                session,
                metric_type="dau",
                metric_date=today,
                redis_key=self._make_daily_key(today),
                snapshot_at=now,
            )

            # 2. Sync monthly metrics
            month_date = date(now.year, now.month, 1)
            stats["monthly"] = await self._upsert_metric(
                session,
                metric_type="mau",
                metric_date=month_date,
                redis_key=self._make_monthly_key(now.year, now.month),
                snapshot_at=now,
            )

            # 3. Sync quarterly metrics
            quarter = (now.month - 1) // 3 + 1
            quarter_start_month = 3 * (quarter - 1) + 1
            quarter_date = date(now.year, quarter_start_month, 1)
            stats["quarterly"] = await self._upsert_metric(
                session,
                metric_type="qau",
                metric_date=quarter_date,
                redis_key=self._make_quarterly_key(now.year, quarter),
                snapshot_at=now,
            )

            # 4. Update User.last_activity (batched)
            if self.update_user_model and stats["daily"] > 0:
                users_updated = await self._batch_update_last_activity(session)
                stats["users_updated"] = users_updated

            # 5. Cleanup old ActivityMetric records
            await self._cleanup_old_metrics(session)

            logger.info(
                f"Activity sync completed: "
                f"DAU={stats['daily']}, MAU={stats['monthly']}, QAU={stats['quarterly']}, "
                f"users_updated={stats['users_updated']}, errors={stats['errors']}"
            )

        except Exception as e:
            logger.error(f"Error syncing activity metrics: {e}", exc_info=True)
            stats["errors"] += 1

        return stats

    async def _upsert_metric(
        self,
        session: AsyncSession,
        *,
        metric_type: str,
        metric_date: date,
        redis_key: str,
        snapshot_at: datetime,
    ) -> int:
        """
        Upsert a single ActivityMetric row from a Redis set.
        """
        try:
            count = await self.redis.scard(redis_key)
            if count <= 0:
                return 0

            stmt = select(ActivityMetric).where(
                ActivityMetric.metric_type == metric_type,
                ActivityMetric.metric_date == metric_date,
                ActivityMetric.tenant_id.is_(None),
            )
            result = await session.execute(stmt)
            metric = result.scalar_one_or_none()

            if metric:
                metric.count = count
                metric.unique_users = count
                metric.snapshot_at = snapshot_at
                await session.flush()
            else:
                metric = ActivityMetric(
                    metric_type=metric_type,
                    metric_date=metric_date,
                    count=count,
                    unique_users=count,
                    snapshot_at=snapshot_at,
                )
                session.add(metric)
                await session.flush()

            return count
        except Exception as e:
            logger.error(
                f"Error syncing metric {metric_type} {metric_date}: {e}", exc_info=True
            )
            return 0

    async def _batch_update_last_activity(self, session: AsyncSession) -> int:
        """
        Batch update User.last_activity from Redis timestamps.

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
                    user_id = key.replace("last_activity:", "")

                    # Get timestamp from Redis
                    timestamp_str = await self.redis.get_raw(key)
                    if timestamp_str:
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
                updated = await self._update_user_batch(session, batch)
                users_updated += updated

            logger.debug(f"Updated last_activity for {users_updated} users")
            return users_updated

        except Exception as e:
            logger.error(f"Error batch updating last_activity: {e}", exc_info=True)
            return 0

    async def _update_user_batch(
        self, session: AsyncSession, batch: list[tuple[str, datetime]]
    ) -> int:
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
                user_uuid = UUID(user_id)
            except Exception:
                continue

            stmt = select(User).where(User.id == user_uuid)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                continue

            user.last_activity = timestamp
            updated += 1

        await session.flush()
        return updated

    async def _cleanup_old_metrics(self, session: AsyncSession) -> None:
        """
        Cleanup old ActivityMetric records.

        Deletes metrics older than activity_ttl_days (default: 90 days).
        """
        try:
            ttl_days = 90
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=ttl_days)
            stmt = sql_delete(ActivityMetric).where(
                ActivityMetric.created_at < cutoff_date
            )
            stmt = sql_delete(ActivityMetric).where(ActivityMetric.created_at < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount or 0
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old ActivityMetric records")

        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}", exc_info=True)

    # Backwards-compatible name
    async def sync_to_mongodb(self, session: AsyncSession) -> Dict[str, Any]:
        return await self.sync_to_database(session)

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
