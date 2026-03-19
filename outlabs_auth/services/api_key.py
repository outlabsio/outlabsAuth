"""
API Key Service

Handles API key management and validation with Redis counter pattern for usage tracking.
Uses SQLAlchemy for PostgreSQL backend.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidInputError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.api_key import APIKey, APIKeyIPWhitelist, APIKeyScope
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.enums import APIKeyStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.base import BaseService

if TYPE_CHECKING:
    from outlabs_auth.services.redis_client import RedisClient

logger = logging.getLogger(__name__)


class APIKeyService(BaseService[APIKey]):
    """
    API key management service with Redis counter pattern.

    Features:
    - API key CRUD operations
    - Fast validation with Redis counters
    - Rate limiting
    - Usage tracking (99% fewer DB writes via Redis)
    - Background sync to database
    """

    def __init__(
        self,
        config: AuthConfig,
        redis_client: Optional["RedisClient"] = None,
    ):
        """
        Initialize APIKeyService.

        Args:
            config: Authentication configuration
            redis_client: Optional Redis client for counters
        """
        super().__init__(APIKey)
        self.config = config
        self.redis_client = redis_client

    async def create_api_key(
        self,
        session: AsyncSession,
        owner_id: UUID,
        name: str,
        scopes: Optional[List[str]] = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_hour: Optional[int] = None,
        rate_limit_per_day: Optional[int] = None,
        entity_id: Optional[UUID] = None,
        inherit_from_tree: bool = False,
        ip_whitelist: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        description: Optional[str] = None,
        prefix_type: str = "sk_live",
    ) -> tuple[str, APIKey]:
        """
        Create a new API key.

        Args:
            session: Database session
            owner_id: User ID who owns the key
            name: Human-readable key name
            scopes: Allowed permissions (None = all)
            rate_limit_per_minute: Max requests per minute
            rate_limit_per_hour: Max requests per hour
            rate_limit_per_day: Max requests per day
            entity_id: Scope to specific entity (EnterpriseRBAC)
            inherit_from_tree: Allow access to descendant entities (EnterpriseRBAC)
            ip_whitelist: Allowed IP addresses
            expires_in_days: Days until expiration
            description: Optional description
            prefix_type: Key prefix (sk_live, sk_test)

        Returns:
            tuple[str, APIKey]: (full_api_key, api_key_model)
                WARNING: full_api_key is only returned once!

        Raises:
            UserNotFoundError: If owner doesn't exist
        """
        # Validate owner exists
        owner = await session.get(User, owner_id)
        if not owner:
            raise UserNotFoundError(message="User not found", details={"user_id": str(owner_id)})

        # Generate API key
        full_key, prefix = APIKey.generate_key(prefix_type)
        key_hash = APIKey.hash_key(full_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Create API key model
        api_key = APIKey(
            name=name,
            prefix=prefix,
            key_hash=key_hash,
            owner_id=owner_id,
            status=APIKeyStatus.ACTIVE,
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour,
            rate_limit_per_day=rate_limit_per_day,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
            description=description,
        )

        session.add(api_key)
        await session.flush()

        # Add scopes via junction table
        if scopes:
            for scope in scopes:
                scope_entry = APIKeyScope(
                    api_key_id=api_key.id,
                    scope=scope,
                )
                session.add(scope_entry)

        # Add IP whitelist
        if ip_whitelist:
            for ip in ip_whitelist:
                ip_entry = APIKeyIPWhitelist(
                    api_key_id=api_key.id,
                    ip_address=ip,
                )
                session.add(ip_entry)

        await session.flush()
        await session.refresh(api_key)

        logger.info(f"Created API key '{name}' for user {owner_id} with prefix {prefix}")

        # Return full key (only time it's ever shown!)
        return full_key, api_key

    async def verify_api_key(
        self,
        session: AsyncSession,
        api_key_string: str,
        required_scope: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[Optional[APIKey], int]:
        """
        Verify API key and track usage with Redis counter.

        This is the core method for API key authentication.
        Uses Redis INCR for fast, low-latency usage tracking.

        Args:
            session: Database session
            api_key_string: Full API key string
            required_scope: Optional required permission
            entity_id: Optional entity ID for access check
            ip_address: Optional client IP for whitelist check

        Returns:
            tuple[Optional[APIKey], int]: (api_key, current_usage)
                - api_key: Valid API key model or None if invalid
                - current_usage: Current usage count (from Redis)
        """
        # Extract prefix from key string
        if not api_key_string or len(api_key_string) < 16:
            logger.warning("Invalid API key format")
            return None, 0

        prefix = api_key_string[:16]
        key_hash = APIKey.hash_key(api_key_string)

        # Find API key by prefix and verify hash
        api_key = await self.get_one(
            session,
            APIKey.prefix == prefix,
            APIKey.key_hash == key_hash,
        )

        if not api_key:
            logger.warning(f"Invalid API key: {api_key_string[:15]}...")
            return None, 0

        # Check if key is active
        if not api_key.is_active():
            logger.warning(f"Inactive API key: {api_key.prefix} (status: {api_key.status})")
            return None, 0

        # Check scope if required
        if required_scope:
            has_scope = await self._check_scope(session, api_key.id, required_scope)
            if not has_scope:
                logger.warning(f"API key {api_key.prefix} lacks required scope: {required_scope}")
                return None, 0

        # Check entity access if required (supports tree permissions)
        if entity_id:
            has_access = await self.check_entity_access_with_tree(session, api_key, entity_id)
            if not has_access:
                logger.warning(f"API key {api_key.prefix} lacks access to entity: {entity_id}")
                return None, 0

        # Check IP whitelist if required
        if ip_address:
            is_allowed = await self._check_ip(session, api_key.id, ip_address)
            if not is_allowed:
                logger.warning(f"API key {api_key.prefix} rejected IP: {ip_address}")
                return None, 0

        # Increment usage counter in Redis (FAST - ~0.1ms)
        usage_count = 0
        if self.redis_client and self.redis_client.is_available:
            counter_key = self._make_usage_counter_key(str(api_key.id))
            usage_count = await self.redis_client.increment(counter_key, amount=1) or 0

            # Also track last_used timestamp in Redis
            last_used_key = self._make_last_used_key(str(api_key.id))
            await self.redis_client.set(
                last_used_key,
                datetime.now(timezone.utc).isoformat(),
                ttl=self.config.cache_ttl_seconds,
            )
        else:
            # Fallback: Direct database write
            api_key.usage_count += 1
            api_key.last_used_at = datetime.now(timezone.utc)
            await session.flush()
            usage_count = api_key.usage_count

        # Check rate limits (using Redis counter)
        if self.redis_client and self.redis_client.is_available:
            await self._check_rate_limits(api_key)

        return api_key, usage_count

    @staticmethod
    def scopes_allow_permission(scopes: Optional[List[str]], required_scope: str) -> bool:
        """Check whether API key scopes allow a permission."""
        normalized = {
            ("*:*" if scope == "*" else scope)
            for scope in (scopes or [])
            if scope
        }
        if not normalized:
            return True

        from outlabs_auth.services.permission import PermissionService

        return PermissionService._permission_set_allows(required_scope, normalized)

    async def _check_scope(self, session: AsyncSession, api_key_id: UUID, required_scope: str) -> bool:
        """Check if API key has required scope."""
        # Check for exact match or wildcard
        stmt = select(APIKeyScope).where(
            APIKeyScope.api_key_id == api_key_id,
        )
        result = await session.execute(stmt)
        scopes = [row.scope for row in result.scalars().all()]

        # No scopes = full access
        if not scopes:
            return True

        # Check for exact match
        if required_scope in scopes:
            return True

        # Check for wildcard (e.g., "user:*" matches "user:read")
        scope_parts = required_scope.split(":")
        if len(scope_parts) == 2:
            wildcard = f"{scope_parts[0]}:*"
            if wildcard in scopes:
                return True

        # Check for global wildcard
        if "*" in scopes:
            return True

        return False

    async def _check_ip(self, session: AsyncSession, api_key_id: UUID, ip_address: str) -> bool:
        stmt = select(func.count()).select_from(APIKeyIPWhitelist).where(APIKeyIPWhitelist.api_key_id == api_key_id)
        result = await session.execute(stmt)
        count = result.scalar() or 0

        # No whitelist = allow all
        if count == 0:
            return True

        # Check if IP is in whitelist
        stmt = select(APIKeyIPWhitelist).where(
            APIKeyIPWhitelist.api_key_id == api_key_id,
            APIKeyIPWhitelist.ip_address == ip_address,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _check_rate_limits(self, api_key: APIKey) -> None:
        """
        Check rate limits using Redis counters with TTL.

        Args:
            api_key: API key to check

        Raises:
            InvalidInputError: If rate limit exceeded
        """
        if not self.redis_client or not self.redis_client.is_available:
            return

        key_id = str(api_key.id)

        # Check per-minute limit
        if api_key.rate_limit_per_minute:
            minute_key = self._make_rate_limit_key(key_id, "minute")
            count = await self.redis_client.increment_with_ttl(minute_key, amount=1, ttl=60) or 0

            if count > api_key.rate_limit_per_minute:
                raise InvalidInputError(
                    message=f"Rate limit exceeded: {api_key.rate_limit_per_minute} requests per minute",
                    details={
                        "limit": api_key.rate_limit_per_minute,
                        "current": count,
                        "window": "minute",
                    },
                )

        # Check per-hour limit
        if api_key.rate_limit_per_hour:
            hour_key = self._make_rate_limit_key(key_id, "hour")
            count = await self.redis_client.increment_with_ttl(hour_key, amount=1, ttl=3600) or 0

            if count > api_key.rate_limit_per_hour:
                raise InvalidInputError(
                    message=f"Rate limit exceeded: {api_key.rate_limit_per_hour} requests per hour",
                    details={
                        "limit": api_key.rate_limit_per_hour,
                        "current": count,
                        "window": "hour",
                    },
                )

        # Check per-day limit
        if api_key.rate_limit_per_day:
            day_key = self._make_rate_limit_key(key_id, "day")
            count = await self.redis_client.increment_with_ttl(day_key, amount=1, ttl=86400) or 0

            if count > api_key.rate_limit_per_day:
                raise InvalidInputError(
                    message=f"Rate limit exceeded: {api_key.rate_limit_per_day} requests per day",
                    details={
                        "limit": api_key.rate_limit_per_day,
                        "current": count,
                        "window": "day",
                    },
                )

    async def sync_usage_counters_to_db(self, session: AsyncSession) -> Dict[str, int]:
        """
        Sync API key usage counters from Redis to database.

        This is called by background worker (every 5 minutes).
        Implements the Redis counter pattern for 99% DB write reduction.

        Returns:
            Dict[str, int]: Stats about sync operation
        """
        if not self.redis_client or not self.redis_client.is_available:
            logger.debug("Redis not available - skipping counter sync")
            return {"synced_keys": 0, "total_usage": 0, "errors": 0}

        logger.info("Starting API key usage counter sync...")

        stats = {
            "synced_keys": 0,
            "total_usage": 0,
            "errors": 0,
        }

        try:
            # Get all usage counters from Redis
            pattern = self._make_usage_counter_key("*")
            counters = await self.redis_client.get_all_counters(pattern)

            logger.debug(f"Found {len(counters)} usage counters to sync")

            # Sync each counter to database
            for counter_key, usage_count in counters.items():
                if usage_count <= 0:
                    continue

                try:
                    # Extract key_id from "apikey:{key_id}:usage"
                    key_id = counter_key.split(":")[1]

                    # Get API key
                    api_key = await self.get_by_id(session, UUID(key_id))
                    if not api_key:
                        logger.warning(f"API key not found for counter: {key_id}")
                        await self.redis_client.delete(counter_key)
                        continue

                    # Update usage count in database
                    api_key.usage_count += usage_count

                    # Update last_used_at if we have it in Redis
                    last_used_key = self._make_last_used_key(key_id)
                    last_used_str = await self.redis_client.get(last_used_key)
                    if last_used_str:
                        api_key.last_used_at = datetime.fromisoformat(last_used_str)
                    else:
                        api_key.last_used_at = datetime.now(timezone.utc)

                    await session.flush()

                    # Reset Redis counter
                    await self.redis_client.delete(counter_key)

                    stats["synced_keys"] += 1
                    stats["total_usage"] += usage_count

                    logger.debug(f"Synced {usage_count} uses for API key {api_key.prefix}")

                except Exception as e:
                    logger.error(f"Error syncing counter {counter_key}: {e}")
                    stats["errors"] += 1

            logger.info(
                f"Counter sync complete: {stats['synced_keys']} keys, "
                f"{stats['total_usage']} total uses, {stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Error during counter sync: {e}")
            stats["errors"] += 1

        return stats

    # Helper methods for Redis keys

    def _make_usage_counter_key(self, key_id: str) -> str:
        """Make Redis key for usage counter."""
        return f"apikey:{key_id}:usage"

    def _make_last_used_key(self, key_id: str) -> str:
        """Make Redis key for last_used timestamp."""
        return f"apikey:{key_id}:last_used"

    def _make_rate_limit_key(self, key_id: str, window: str) -> str:
        """Make Redis key for rate limit window."""
        return f"apikey:{key_id}:ratelimit:{window}"

    # API Key Management Methods

    async def get_api_key(self, session: AsyncSession, key_id: UUID) -> Optional[APIKey]:
        """Get API key by ID with owner loaded."""
        return await self.get_by_id(session, key_id, options=[selectinload(APIKey.owner)])

    async def get_api_key_scopes(self, session: AsyncSession, key_id: UUID) -> List[str]:
        """Get scopes for an API key."""
        stmt = select(APIKeyScope.scope).where(APIKeyScope.api_key_id == key_id)
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_api_key_ip_whitelist(self, session: AsyncSession, key_id: UUID) -> List[str]:
        """Get IP whitelist entries for an API key."""
        stmt = select(APIKeyIPWhitelist.ip_address).where(APIKeyIPWhitelist.api_key_id == key_id)
        stmt = select(APIKeyIPWhitelist.ip_address).where(APIKeyIPWhitelist.api_key_id == key_id)
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_user_api_keys(
        self,
        session: AsyncSession,
        user_id: UUID,
        status: Optional[APIKeyStatus] = None,
    ) -> List[APIKey]:
        """
        List all API keys for a user.

        Args:
            session: Database session
            user_id: User ID
            status: Optional filter by status

        Returns:
            List[APIKey]: User's API keys
        """
        filters = [APIKey.owner_id == user_id]
        if status:
            filters.append(APIKey.status == status)

        return await self.get_many(session, *filters, limit=1000)

    async def revoke_api_key(self, session: AsyncSession, key_id: UUID) -> bool:
        """
        Revoke an API key.

        Args:
            session: Database session
            key_id: API key ID

        Returns:
            bool: True if revoked
        """
        api_key = await self.get_by_id(session, key_id)
        if not api_key:
            return False

        api_key.status = APIKeyStatus.REVOKED
        await session.flush()

        logger.info(f"Revoked API key: {api_key.prefix}")
        return True

    async def revoke_user_api_keys(self, session: AsyncSession, user_id: UUID) -> int:
        """Revoke all non-revoked API keys owned by a user."""
        stmt = select(APIKey).where(
            APIKey.owner_id == user_id,
            APIKey.status != APIKeyStatus.REVOKED,
        )
        result = await session.execute(stmt)
        api_keys = list(result.scalars().all())
        if not api_keys:
            return 0

        for api_key in api_keys:
            api_key.status = APIKeyStatus.REVOKED

        await session.flush()
        return len(api_keys)

    async def update_api_key(self, session: AsyncSession, key_id: UUID, **updates) -> Optional[APIKey]:
        """
        Update API key fields.

        Args:
            session: Database session
            key_id: API key ID
            **updates: Fields to update

        Returns:
            Optional[APIKey]: Updated key or None
        """
        api_key = await self.get_by_id(session, key_id)
        if not api_key:
            return None

        # Update allowed fields
        allowed_fields = {
            "name",
            "description",
            "rate_limit_per_minute",
            "rate_limit_per_hour",
            "rate_limit_per_day",
            "status",
            "expires_at",
            "entity_id",
            "inherit_from_tree",
        }

        for field, value in updates.items():
            if field in allowed_fields and hasattr(api_key, field):
                setattr(api_key, field, value)

        # Handle scopes separately
        if "scopes" in updates:
            # Clear existing scopes
            stmt = sql_delete(APIKeyScope).where(APIKeyScope.api_key_id == key_id)
            await session.execute(stmt)

            # Add new scopes
            for scope in updates["scopes"]:
                scope_entry = APIKeyScope(api_key_id=key_id, scope=scope)
                session.add(scope_entry)

        # Handle IP whitelist separately
        if "ip_whitelist" in updates:
            # Clear existing IPs
            stmt = sql_delete(APIKeyIPWhitelist).where(APIKeyIPWhitelist.api_key_id == key_id)
            await session.execute(stmt)

            # Add new IPs
            for ip in updates["ip_whitelist"]:
                ip_entry = APIKeyIPWhitelist(api_key_id=key_id, ip_address=ip)
                session.add(ip_entry)

        await session.flush()
        await session.refresh(api_key)
        return api_key

    async def check_entity_access_with_tree(
        self, session: AsyncSession, api_key: APIKey, target_entity_id: UUID
    ) -> bool:
        """
        Check if API key has access to target entity, including tree permissions.

        This method checks:
        1. Direct access: If entity_id matches target_entity_id
        2. Tree access: If inherit_from_tree=True and target is a descendant

        Args:
            session: Database session
            api_key: API key to check
            target_entity_id: Target entity ID to access

        Returns:
            bool: True if API key has access
        """
        # No entity_id = global access
        if not api_key.entity_id:
            return True

        # Direct match
        if api_key.entity_id == target_entity_id:
            return True

        # Check tree access if enabled
        if api_key.inherit_from_tree:
            # Check if target is a descendant of api_key's entity
            stmt = select(EntityClosure).where(
                EntityClosure.ancestor_id == api_key.entity_id,
                EntityClosure.descendant_id == target_entity_id,
                EntityClosure.depth > 0,  # Exclude self
            )
            result = await session.execute(stmt)
            closure = result.scalar_one_or_none()

            if closure:
                return True

        return False

    async def delete_api_key(self, session: AsyncSession, key_id: UUID) -> bool:
        """
        Hard delete an API key (use revoke for soft delete).

        Args:
            session: Database session
            key_id: API key ID

        Returns:
            bool: True if deleted
        """
        api_key = await self.get_by_id(session, key_id)
        if not api_key:
            return False

        # Scopes and IP whitelist are deleted via cascade
        await session.delete(api_key)
        await session.flush()

        logger.info(f"Deleted API key: {api_key.prefix}")
        return True
