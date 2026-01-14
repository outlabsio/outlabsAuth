"""
SQLModel Base Classes for OutlabsAuth

Provides base model with common fields (id, timestamps, tenant_id) for all tables.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, String, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class BaseModel(SQLModel):
    """
    Base model for all OutlabsAuth database tables.

    Provides:
    - UUID primary key (auto-generated)
    - created_at timestamp (auto-set on insert)
    - updated_at timestamp (auto-updated on modification)
    - tenant_id for multi-tenant support (optional)

    All OutlabsAuth models should inherit from this class:

        class User(BaseModel, table=True):
            __tablename__ = "users"
            email: str = Field(index=True)
            ...

    Note:
        This is NOT a table itself (table=False by default).
        Child classes must set table=True to create database tables.
    """

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        description="Unique identifier (UUID v4)",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        ),
        description="Timestamp when record was created (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        ),
        description="Timestamp when record was last updated (UTC)",
    )

    tenant_id: Optional[str] = Field(
        default=None,
        sa_column=Column(
            String(36),
            index=True,
            nullable=True,
        ),
        description="Tenant identifier for multi-tenant isolation",
    )

    class Config:
        """Pydantic/SQLModel configuration."""
        # Allow arbitrary types (needed for some PostgreSQL types)
        arbitrary_types_allowed = True
        # Use enum values instead of names
        use_enum_values = True


def update_timestamp_on_save(mapper, connection, target):
    """
    SQLAlchemy event listener to update `updated_at` on modifications.

    This is registered automatically when models are loaded.
    """
    target.updated_at = datetime.now(timezone.utc)


def register_timestamp_listener(model_class):
    """
    Register the timestamp update listener for a model class.

    Call this after defining models to ensure updated_at is always current.

    Example:
        class User(BaseModel, table=True):
            ...

        register_timestamp_listener(User)
    """
    event.listen(model_class, "before_update", update_timestamp_on_save)


# Note: The updated_at trigger is handled at the application level
# because PostgreSQL triggers are database-specific and we want
# the library to be portable across PostgreSQL instances.
