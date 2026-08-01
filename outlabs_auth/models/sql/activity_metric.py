"""
ActivityMetric Model

DAU/MAU tracking and activity snapshots.
"""

from datetime import datetime, timezone, date
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Index, UniqueConstraint, ForeignKey, String, Integer, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel


class ActivityMetric(BaseModel, table=True):
    """
    Daily activity metrics snapshot.

    Stores aggregated activity counts per day for DAU/MAU tracking.
    These are rolled up from Redis counters periodically.

    Table: activity_metrics
    """
    __tablename__ = "activity_metrics"
    __table_args__ = (
        UniqueConstraint("metric_date", "metric_type", name="uq_activity_metric_date_type"),
        Index("ix_activity_metrics_date", "metric_date"),
        Index("ix_activity_metrics_type", "metric_type"),
    )

    # === Metric Identity ===
    metric_date: date = Field(
        sa_column=Column(Date, nullable=False),
        description="Date for this metric",
    )
    metric_type: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="Type: dau, mau, logins, registrations, api_calls",
    )

    # === Counts ===
    count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Count for this metric",
    )
    unique_users: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Unique user count (for DAU/MAU)",
    )

    # === Snapshot Metadata ===
    snapshot_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When this snapshot was taken",
    )


class UserActivity(BaseModel, table=True):
    """
    Individual user activity tracking.

    Records user activity for accurate DAU/MAU calculation.
    Stores one record per user per day.

    Table: user_activities
    """
    __tablename__ = "user_activities"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_user_activity_date"),
        Index("ix_user_activities_user_id", "user_id"),
        Index("ix_user_activities_date", "activity_date"),
    )

    # === User ===
    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # === Activity Date ===
    activity_date: date = Field(
        sa_column=Column(Date, nullable=False),
        description="Date of activity",
    )

    # === Activity Counts ===
    login_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
    )
    api_call_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
    )
    action_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Other tracked actions",
    )

    # === Timestamps ===
    first_activity_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_activity_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # === Methods ===
    def record_activity(self, activity_type: str = "action") -> None:
        """Record an activity for this user on this date."""
        self.last_activity_at = datetime.now(timezone.utc)
        if activity_type == "login":
            self.login_count += 1
        elif activity_type == "api_call":
            self.api_call_count += 1
        else:
            self.action_count += 1


class LoginHistory(BaseModel, table=True):
    """
    User login history for security and analytics.

    Table: login_history
    """
    __tablename__ = "login_history"
    __table_args__ = (
        Index("ix_login_history_user_id", "user_id"),
        Index("ix_login_history_timestamp", "login_at"),
        Index("ix_login_history_success", "success"),
    )

    # === User ===
    user_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # === Login Details ===
    login_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    success: bool = Field(
        sa_column=Column(String(10), nullable=False),  # 'success' or 'failed'
        description="Whether login was successful",
    )
    auth_method: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="Authentication method used (password, oauth, api_key, etc.)",
    )

    # === Client Information ===
    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(String(45), nullable=True),  # IPv6 max
    )
    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )
    device_fingerprint: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )

    # === Location (if available) ===
    country_code: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2), nullable=True),
    )
    city: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
    )

    # === Failure Information ===
    failure_reason: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Reason for login failure",
    )
