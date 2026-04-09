"""
Configuration Service

Manages system-level configuration stored in the database.
Only superusers should be able to modify these settings.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.system_config import (
    DEFAULT_ENTITY_TYPE_CONFIG,
    ConfigKeys,
    SystemConfig,
)
from outlabs_auth.schemas.config import EntityTypeConfig


class ConfigService:
    """
    System configuration service.

    Handles:
    - Reading and writing system configuration values
    - Entity type configuration (allowed root types, default child types)
    - Seeding default configuration values
    """

    async def get_config(
        self,
        session: AsyncSession,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a configuration value by key.

        Args:
            session: Database session
            key: Configuration key

        Returns:
            Parsed JSON value or None if not found
        """
        stmt = select(SystemConfig).where(cast(Any, SystemConfig.key) == key)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config is None:
            return None

        return cast(Optional[Dict[str, Any]], json.loads(config.value))

    async def set_config(
        self,
        session: AsyncSession,
        key: str,
        value: Dict[str, Any],
        description: Optional[str] = None,
        updated_by_id: Optional[UUID] = None,
    ) -> SystemConfig:
        """
        Set a configuration value.

        Creates the key if it doesn't exist, updates if it does.

        Args:
            session: Database session
            key: Configuration key
            value: Value to store (will be JSON-encoded)
            description: Optional description
            updated_by_id: ID of user making the change

        Returns:
            Updated SystemConfig record
        """
        stmt = select(SystemConfig).where(cast(Any, SystemConfig.key) == key)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config is None:
            # Create new config
            config = SystemConfig(
                key=key,
                value=json.dumps(value),
                description=description,
                updated_at=datetime.now(timezone.utc),
                updated_by_id=updated_by_id,
            )
            session.add(config)
        else:
            # Update existing
            config.value = json.dumps(value)
            config.updated_at = datetime.now(timezone.utc)
            config.updated_by_id = updated_by_id
            if description is not None:
                config.description = description

        await session.flush()
        await session.refresh(config)
        return config

    async def delete_config(
        self,
        session: AsyncSession,
        key: str,
    ) -> bool:
        """
        Delete a configuration key.

        Args:
            session: Database session
            key: Configuration key to delete

        Returns:
            True if deleted, False if not found
        """
        stmt = select(SystemConfig).where(cast(Any, SystemConfig.key) == key)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config is None:
            return False

        await session.delete(config)
        await session.flush()
        return True

    # === Entity Type Configuration ===

    async def get_entity_type_config(
        self,
        session: AsyncSession,
    ) -> EntityTypeConfig:
        """
        Get the entity type configuration.

        Returns default values if not configured.

        Args:
            session: Database session

        Returns:
            EntityTypeConfig with allowed root types and default child types
        """
        value = await self.get_config(session, ConfigKeys.ENTITY_TYPES)

        if value is None:
            # Return defaults
            return EntityTypeConfig.model_validate(DEFAULT_ENTITY_TYPE_CONFIG)

        return EntityTypeConfig.model_validate(value)

    async def set_entity_type_config(
        self,
        session: AsyncSession,
        config: EntityTypeConfig,
        updated_by_id: Optional[UUID] = None,
    ) -> EntityTypeConfig:
        """
        Update the entity type configuration.

        Args:
            session: Database session
            config: New entity type configuration
            updated_by_id: ID of user making the change

        Returns:
            Updated EntityTypeConfig
        """
        await self.set_config(
            session,
            ConfigKeys.ENTITY_TYPES,
            config.model_dump(),
            description="Configures allowed entity types for root entities and default child types",
            updated_by_id=updated_by_id,
        )
        return config

    async def seed_defaults(
        self,
        session: AsyncSession,
        updated_by_id: Optional[UUID] = None,
    ) -> None:
        """
        Seed default configuration values if they don't exist.

        Call this during application startup.

        Args:
            session: Database session
            updated_by_id: Optional user ID for audit trail
        """
        # Check if entity type config exists
        existing = await self.get_config(session, ConfigKeys.ENTITY_TYPES)
        if existing is None:
            await self.set_config(
                session,
                ConfigKeys.ENTITY_TYPES,
                DEFAULT_ENTITY_TYPE_CONFIG,
                description="Configures allowed entity types for root entities and default child types",
                updated_by_id=updated_by_id,
            )
