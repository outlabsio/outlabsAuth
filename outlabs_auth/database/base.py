"""
SQLModel Base Classes for OutlabsAuth

Provides base model with common fields (id, timestamps) for all tables.
"""

from datetime import datetime, timezone
from typing import ClassVar, cast
from uuid import UUID, uuid4

from pydantic import ConfigDict
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel
from sqlmodel.main import SQLModelConfig


class BaseModel(SQLModel):
    """
    Base model for all OutlabsAuth database tables.

    Provides:
    - UUID primary key (auto-generated)
    - created_at timestamp (auto-set on insert)
    - updated_at timestamp (auto-updated on modification)
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
        primary_key=True,
        sa_type=PG_UUID(as_uuid=True),
        description="Unique identifier (UUID v4)",
    )  # type: ignore[call-overload]

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=TIMESTAMP(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now()},
        description="Timestamp when record was created (UTC)",
    )  # type: ignore[call-overload]

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=TIMESTAMP(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        description="Timestamp when record was last updated (UTC)",
    )  # type: ignore[call-overload]

    model_config: ClassVar[SQLModelConfig] = cast(
        SQLModelConfig,
        ConfigDict(
            arbitrary_types_allowed=True,
            use_enum_values=True,
        ),
    )
