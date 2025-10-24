"""
Activity Metric model for tracking DAU/MAU/WAU/QAU

Historical snapshots created by background sync worker from Redis Sets.
Used for analytics, dashboards, and growth tracking.
"""
from datetime import datetime, timezone
from typing import Optional, List
from beanie import Document
from pydantic import Field


class ActivityMetric(Document):
    """
    Historical snapshot of user activity metrics.

    Created by background sync worker from Redis Sets.
    Provides historical data for analytics and growth tracking.

    Example periods:
    - Daily: "2025-01-24"
    - Monthly: "2025-01"
    - Quarterly: "2025-Q1"
    """

    period_type: str = Field(
        description="Type of period: 'daily', 'monthly', 'quarterly'"
    )
    period: str = Field(
        description="Period identifier: '2025-01-24', '2025-01', '2025-Q1'"
    )
    active_users: int = Field(
        description="Count of unique active users in this period"
    )
    unique_user_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of user IDs (for cohort analysis, increases storage)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this metric was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this metric was last updated"
    )

    class Settings:
        """Beanie configuration"""
        name = "activity_metrics"
        indexes = [
            [("period_type", 1), ("period", -1)],  # Query by type, sorted by time
            [("created_at", 1)],                   # Cleanup old records
            [("period_type", 1), ("period", 1)],   # Unique constraint per period
        ]
