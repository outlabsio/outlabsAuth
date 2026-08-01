"""
OutlabsAuth Database Module

Provides PostgreSQL database connectivity using SQLModel/SQLAlchemy.
"""

from outlabs_auth.database.engine import (
    DatabaseConfig,
    DatabasePresets,
    create_engine,
    create_session_factory,
    get_session,
)
from outlabs_auth.database.base import BaseModel
from outlabs_auth.database.registry import ModelRegistry

__all__ = [
    "DatabaseConfig",
    "DatabasePresets",
    "create_engine",
    "create_session_factory",
    "get_session",
    "BaseModel",
    "ModelRegistry",
]
