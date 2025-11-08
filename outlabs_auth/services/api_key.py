"""
API Key Service

Handles API key management and validation with Redis counter pattern for usage tracking.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidInputError,
    UserNotFoundError,
)
from outlabs_auth.models.api_key import APIKeyModel, APIKeyStatus
from outlabs_auth.models.user import UserModel

logger = logging.getLogger(__name__)


class APIKeyService:
    """
    API key management service with Redis counter pattern.

    Features:
    - API key CRUD operations
    - Fast validation with Redis counters
    - Rate limiting
    - Usage tracking (99% fewer DB writes via Redis)
    - Background sync to MongoDB

    Example:
        >>> api_key_service = APIKeyService(database, config, redis_client)
        >>>
        >>> # Create key
        >>> key, model = await api_key_service.create_api_key(
        ...     owner_id=user_id,
        ...     name="Production Key",
        ...     scopes=["user:read", "entity:read"],
        ...     rate_limit_per_minute=60
        ... )
        >>> print(key)  # Only shown once: sk_live_abc123...
        >>>
        >>> # Verify key (fast - uses Redis counter)
        >>> api_key, usage = await api_key_service.verify_api_key(key)
        >>> if not api_key:
        ...     raise InvalidAPIKeyError()
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: AuthConfig,
        redis_client: Optional["RedisClient"] = None,
    ):
        """
        Initialize APIKeyService.

        Args:
            database: MongoDB database instance
            config: Authentication configuration
            redis_client: Optional Redis client for counters
        """
        self.database = database
        self.config = config
        self.redis_client = redis_client

    async def create_api_key(
        self,
        owner_id: str,
        name: str,
        scopes: Optional[List[str]] = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_hour: Optional[int] = None,
        rate_limit_per_day: Optional[int] = None,
        entity_ids: Optional[List[str]] = None,
        ip_whitelist: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        prefix_type: str = "sk_live",
    ) -> tuple[str, APIKeyModel]:
        """
        Create a new API key.

        Args:
            owner_id: User ID who owns the key
            name: Human-readable key name
            scopes: Allowed permissions (None = all)
            rate_limit_per_minute: Max requests per minute
            rate_limit_per_hour: Max requests per hour
            rate_limit_per_day: Max requests per day
            entity_ids: Restrict to specific entities
            ip_whitelist: Allowed IP addresses
            expires_in_days: Days until expiration
            description: Optional description
            metadata: Additional metadata
            prefix_type: Key prefix (sk_live, sk_test)

        Returns:
            tuple[str, APIKeyModel]: (full_api_key, api_key_model)
                WARNING: full_api_key is only returned once!

        Raises:
            UserNotFoundError: If owner doesn't exist

        Example:
            >>> key, model = await api_key_service.create_api_key(
            ...     owner_id=user_id,
            ...     name="Production API",
            ...     scopes=["user:read"],
            ...     rate_limit_per_minute=100
            ... )
            >>> # Store 'key' securely - it's never shown again!
        """
        # Validate owner exists
        owner = await UserModel.get(owner_id)
        if not owner:
            raise UserNotFoundError(
                message="User not found", details={"user_id": owner_id}
            )

        # Generate API key
        full_key, prefix = APIKeyModel.generate_key(prefix_type)
        key_hash = APIKeyModel.hash_key(full_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Create API key model
        api_key = APIKeyModel(
            name=name,
            prefix=prefix,
            key_hash=key_hash,
            owner=owner,
            status=APIKeyStatus.ACTIVE,
            expires_at=expires_at,
            scopes=scopes or [],
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour,
            rate_limit_per_day=rate_limit_per_day,
            entity_ids=entity_ids,
            ip_whitelist=ip_whitelist,
            description=description,
            metadata=metadata or {},
        )

        await api_key.save()

        logger.info(
            f"Created API key '{name}' for user {owner_id} with prefix {prefix}"
        )

        # Return full key (only time it's ever shown!)
        return full_key, api_key

    async def verify_api_key(
        self,
        api_key_string: str,
        required_scope: Optional[str] = None,
        entity_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[Optional[APIKeyModel], int]:
        """
        Verify API key and track usage with Redis counter.

        This is the core method for API key authentication.
        Uses Redis INCR for fast, low-latency usage tracking.

        Args:
            api_key_string: Full API key string
            required_scope: Optional required permission
            entity_id: Optional entity ID for access check
            ip_address: Optional client IP for whitelist check

        Returns:
            tuple[Optional[APIKeyModel], int]: (api_key, current_usage)
                - api_key: Valid API key model or None if invalid
                - current_usage: Current usage count (from Redis)

        Example:
            >>> api_key, usage = await api_key_service.verify_api_key(
            ...     request.headers.get("X-API-Key"),
            ...     required_scope="user:read",
            ...     ip_address=request.client.host
            ... )
            >>> if not api_key:
            ...     raise InvalidAPIKeyError()
        """
        # Verify key exists and hash matches
        api_key = await APIKeyModel.verify_key(api_key_string)
        if not api_key:
            logger.warning(f"Invalid API key: {api_key_string[:15]}...")
            return None, 0

        # Check if key is active
        if not api_key.is_active():
            logger.warning(
                f"Inactive API key: {api_key.prefix} (status: {api_key.status})"
            )
            return None, 0

        # Check scope if required
        if required_scope and not api_key.has_scope(required_scope):
            logger.warning(
                f"API key {api_key.prefix} lacks required scope: {required_scope}"
            )
            return None, 0

        # Check entity access if required
        if entity_id and not api_key.has_entity_access(entity_id):
            logger.warning(
                f"API key {api_key.prefix} lacks access to entity: {entity_id}"
            )
            return None, 0

        # Check IP whitelist if required
        if ip_address and not api_key.check_ip(ip_address):
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
            # Fallback: Direct MongoDB write (slow - ~15ms)
            api_key.usage_count += 1
            api_key.last_used_at = datetime.now(timezone.utc)
            await api_key.save()
            usage_count = api_key.usage_count

        # Check rate limits (using Redis counter)
        if self.redis_client and self.redis_client.is_available:
            await self._check_rate_limits(api_key)

        return api_key, usage_count

    async def _check_rate_limits(self, api_key: APIKeyModel) -> None:
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
            count = (
                await self.redis_client.increment_with_ttl(minute_key, amount=1, ttl=60)
                or 0
            )

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
            count = (
                await self.redis_client.increment_with_ttl(hour_key, amount=1, ttl=3600)
                or 0
            )

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
            count = (
                await self.redis_client.increment_with_ttl(day_key, amount=1, ttl=86400)
                or 0
            )

            if count > api_key.rate_limit_per_day:
                raise InvalidInputError(
                    message=f"Rate limit exceeded: {api_key.rate_limit_per_day} requests per day",
                    details={
                        "limit": api_key.rate_limit_per_day,
                        "current": count,
                        "window": "day",
                    },
                )

    async def sync_usage_counters_to_db(self) -> Dict[str, int]:
        """
        Sync API key usage counters from Redis to MongoDB.

        This is called by background worker (every 5 minutes).
        Implements the Redis counter pattern for 99% DB write reduction.

        Returns:
            Dict[str, int]: Stats about sync operation
                - synced_keys: Number of keys synced
                - total_usage: Total usage count synced
                - errors: Number of errors

        Example:
            >>> stats = await api_key_service.sync_usage_counters_to_db()
            >>> print(f"Synced {stats['synced_keys']} API keys")
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
                    api_key = await APIKeyModel.get(key_id)
                    if not api_key:
                        logger.warning(f"API key not found for counter: {key_id}")
                        await self.redis_client.delete(counter_key)
                        continue

                    # Update usage count in MongoDB
                    api_key.usage_count += usage_count

                    # Update last_used_at if we have it in Redis
                    last_used_key = self._make_last_used_key(key_id)
                    last_used_str = await self.redis_client.get(last_used_key)
                    if last_used_str:
                        api_key.last_used_at = datetime.fromisoformat(last_used_str)
                    else:
                        api_key.last_used_at = datetime.now(timezone.utc)

                    await api_key.save()

                    # Reset Redis counter
                    await self.redis_client.delete(counter_key)

                    stats["synced_keys"] += 1
                    stats["total_usage"] += usage_count

                    logger.debug(
                        f"Synced {usage_count} uses for API key {api_key.prefix}"
                    )

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

    async def get_api_key(self, key_id: str) -> Optional[APIKeyModel]:
        """Get API key by ID."""
        return await APIKeyModel.get(key_id)

    async def list_user_api_keys(
        self, user_id: str, status: Optional[APIKeyStatus] = None
    ) -> List[APIKeyModel]:
        """
        List all API keys for a user.

        Args:
            user_id: User ID
            status: Optional filter by status

        Returns:
            List[APIKeyModel]: User's API keys
        """
        user = await UserModel.get(user_id)
        if not user:
            return []

        query_conditions = [APIKeyModel.owner.id == user.id]
        if status:
            query_conditions.append(APIKeyModel.status == status)

        return await APIKeyModel.find(*query_conditions).to_list()

    async def revoke_api_key(self, key_id: str) -> bool:
        """
        Revoke an API key.

        Args:
            key_id: API key ID

        Returns:
            bool: True if revoked
        """
        api_key = await APIKeyModel.get(key_id)
        if not api_key:
            return False

        api_key.status = APIKeyStatus.REVOKED
        await api_key.save()

        logger.info(f"Revoked API key: {api_key.prefix}")
        return True

    async def update_api_key(self, key_id: str, **updates) -> Optional[APIKeyModel]:
        """
        Update API key fields.

        Args:
            key_id: API key ID
            **updates: Fields to update

        Returns:
            Optional[APIKeyModel]: Updated key or None
        """
        api_key = await APIKeyModel.get(key_id)
        if not api_key:
            return None

        # Update allowed fields
        allowed_fields = {
            "name",
            "description",
            "scopes",
            "rate_limit_per_minute",
            "rate_limit_per_hour",
            "rate_limit_per_day",
            "entity_ids",
            "ip_whitelist",
            "status",
            "expires_at",
            "metadata",
        }

        for field, value in updates.items():
            if field in allowed_fields and hasattr(api_key, field):
                setattr(api_key, field, value)

        await api_key.save()
        return api_key
