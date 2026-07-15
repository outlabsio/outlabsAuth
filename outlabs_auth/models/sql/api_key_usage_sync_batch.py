"""Durable idempotency receipts for Redis-backed API-key usage synchronization."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer
from sqlmodel import Field, SQLModel

from outlabs_auth.database.base import BaseModel


class APIKeyUsageSyncBatch(BaseModel, table=True):
    """A Redis counter batch that has been durably applied to PostgreSQL exactly once.

    Redis staged keys intentionally survive a worker crash until they are acknowledged.
    This receipt lets a retry safely acknowledge a batch that committed just before a
    previous worker died, without incrementing ``api_keys.usage_count`` a second time.
    """

    __tablename__ = "api_key_usage_sync_batches"
    __table_args__ = (Index("ix_api_key_usage_sync_batches_applied_at", "applied_at"),)

    applied_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When this batch was atomically applied to API-key usage totals",
    )
    key_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Number of API-key counter entries represented by the batch",
    )
    total_usage: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0),
        description="Total usage delta represented by the batch",
    )
