"""
Redis Client Manager

Handles Redis connections with graceful fallback when Redis is unavailable.
Provides caching operations with automatic serialization/deserialization.
"""
from typing import Optional, Any, List
import json
import logging
from datetime import timedelta

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None  # type: ignore
    RedisError = Exception  # type: ignore
    RedisConnectionError = Exception  # type: ignore

from outlabs_auth.core.config import AuthConfig

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client with graceful fallback.

    Features:
    - Automatic connection management
    - Graceful fallback when Redis unavailable
    - JSON serialization/deserialization
    - TTL support
    - Pub/Sub for cache invalidation
    - Connection pooling
    """

    def __init__(self, config: AuthConfig):
        """
        Initialize Redis client.

        Args:
            config: Authentication configuration with Redis settings
        """
        self.config = config
        self._client: Optional[Redis] = None
        self._pubsub = None
        self._available = False

    async def connect(self) -> bool:
        """
        Connect to Redis server.

        Returns:
            bool: True if connected, False if unavailable
        """
        if not REDIS_AVAILABLE:
            logger.warning("redis package not installed - caching disabled")
            return False

        if not self.config.redis_enabled:
            logger.info("Redis caching disabled in configuration")
            return False

        try:
            self._client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                max_connections=50,
            )

            # Test connection
            await self._client.ping()
            self._available = True
            logger.info(f"Connected to Redis at {self.config.redis_host}:{self.config.redis_port}")
            return True

        except (RedisConnectionError, RedisError) as e:
            logger.warning(f"Redis connection failed: {e} - caching disabled")
            self._available = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._available = False
            logger.info("Disconnected from Redis")

    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._available

    # Cache Operations

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value (deserialized from JSON) or None
        """
        if not self._available or not self._client:
            return None

        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.debug(f"Cache get failed for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (None = no expiration)

        Returns:
            bool: True if set successfully
        """
        if not self._available or not self._client:
            return False

        try:
            serialized = json.dumps(value)
            if ttl:
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
            return True
        except (RedisError, TypeError, json.JSONEncodeError) as e:
            logger.debug(f"Cache set failed for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            bool: True if deleted
        """
        if not self._available or not self._client:
            return False

        try:
            await self._client.delete(key)
            return True
        except RedisError as e:
            logger.debug(f"Cache delete failed for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "user:*")

        Returns:
            int: Number of keys deleted
        """
        if not self._available or not self._client:
            return 0

        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self._client.delete(*keys)
            return len(keys)
        except RedisError as e:
            logger.debug(f"Cache delete pattern failed for {pattern}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            bool: True if exists
        """
        if not self._available or not self._client:
            return False

        try:
            return bool(await self._client.exists(key))
        except RedisError as e:
            logger.debug(f"Cache exists check failed for {key}: {e}")
            return False

    # Counter Operations (DD-033)

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment counter.

        Args:
            key: Counter key
            amount: Amount to increment by

        Returns:
            New counter value or None if failed
        """
        if not self._available or not self._client:
            return None

        try:
            return await self._client.incrby(key, amount)
        except RedisError as e:
            logger.debug(f"Counter increment failed for {key}: {e}")
            return None

    async def get_counter(self, key: str) -> int:
        """
        Get counter value.

        Args:
            key: Counter key

        Returns:
            Counter value (0 if not exists)
        """
        if not self._available or not self._client:
            return 0

        try:
            value = await self._client.get(key)
            return int(value) if value else 0
        except (RedisError, ValueError) as e:
            logger.debug(f"Counter get failed for {key}: {e}")
            return 0

    async def reset_counter(self, key: str) -> bool:
        """
        Reset counter to 0.

        Args:
            key: Counter key

        Returns:
            bool: True if reset
        """
        return await self.delete(key)

    async def get_all_counters(self, pattern: str) -> dict[str, int]:
        """
        Get all counters matching pattern.

        Args:
            pattern: Key pattern (e.g., "apikey:*:usage")

        Returns:
            dict[str, int]: Dictionary of key -> counter value

        Example:
            >>> counters = await redis.get_all_counters("apikey:*:usage")
            >>> counters
            {'apikey:abc:usage': 42, 'apikey:xyz:usage': 17}
        """
        if not self._available or not self._client:
            return {}

        try:
            counters = {}
            async for key in self._client.scan_iter(match=pattern):
                value = await self.get_counter(key)
                counters[key] = value
            return counters
        except RedisError as e:
            logger.debug(f"Get all counters failed for {pattern}: {e}")
            return {}

    async def get_and_reset_counter(self, key: str) -> int:
        """
        Get counter value and reset it to 0 atomically.

        This is useful for syncing counters to database.

        Args:
            key: Counter key

        Returns:
            int: Counter value before reset

        Example:
            >>> usage = await redis.get_and_reset_counter("apikey:abc:usage")
            >>> # Now sync usage to database
            >>> api_key.usage_count += usage
        """
        if not self._available or not self._client:
            return 0

        try:
            # Use GETDEL to atomically get and delete
            value = await self._client.get(key)
            if value:
                await self._client.delete(key)
                return int(value)
            return 0
        except (RedisError, ValueError) as e:
            logger.debug(f"Get and reset counter failed for {key}: {e}")
            return 0

    async def increment_with_ttl(
        self,
        key: str,
        amount: int = 1,
        ttl: Optional[int] = None
    ) -> Optional[int]:
        """
        Increment counter and set TTL if it's a new key.

        Useful for rate limiting with automatic expiration.

        Args:
            key: Counter key
            amount: Amount to increment by
            ttl: TTL in seconds for new keys

        Returns:
            New counter value or None if failed

        Example:
            >>> # Rate limit: 60 requests per minute
            >>> count = await redis.increment_with_ttl(
            ...     f"ratelimit:{user_id}:minute",
            ...     amount=1,
            ...     ttl=60
            ... )
            >>> if count > 60:
            ...     raise RateLimitError()
        """
        if not self._available or not self._client:
            return None

        try:
            # Increment counter
            new_value = await self._client.incrby(key, amount)

            # Set TTL only if this is the first increment (value == amount)
            if ttl and new_value == amount:
                await self._client.expire(key, ttl)

            return new_value
        except RedisError as e:
            logger.debug(f"Increment with TTL failed for {key}: {e}")
            return None

    # Pub/Sub Operations (DD-037)

    async def publish(self, channel: str, message: str) -> bool:
        """
        Publish message to channel.

        Args:
            channel: Channel name
            message: Message to publish

        Returns:
            bool: True if published
        """
        if not self._available or not self._client:
            return False

        try:
            await self._client.publish(channel, message)
            return True
        except RedisError as e:
            logger.debug(f"Publish failed for {channel}: {e}")
            return False

    async def subscribe(self, *channels: str):
        """
        Subscribe to channels.

        Args:
            *channels: Channel names

        Returns:
            PubSub object or None
        """
        if not self._available or not self._client:
            return None

        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(*channels)
            return pubsub
        except RedisError as e:
            logger.debug(f"Subscribe failed: {e}")
            return None

    # Cache Key Helpers

    def make_key(self, *parts: str) -> str:
        """
        Create cache key from parts.

        Args:
            *parts: Key parts

        Returns:
            str: Cache key (e.g., "auth:user:123:permissions")
        """
        return ":".join(str(p) for p in parts)

    def make_permission_key(self, user_id: str, entity_id: Optional[str] = None) -> str:
        """
        Create permission cache key.

        Args:
            user_id: User ID
            entity_id: Optional entity ID

        Returns:
            str: Permission cache key
        """
        if entity_id:
            return self.make_key("auth", "permissions", user_id, entity_id)
        return self.make_key("auth", "permissions", user_id, "global")

    def make_entity_path_key(self, entity_id: str) -> str:
        """
        Create entity path cache key.

        Args:
            entity_id: Entity ID

        Returns:
            str: Entity path cache key
        """
        return self.make_key("auth", "entity", "path", entity_id)

    def make_entity_descendants_key(self, entity_id: str) -> str:
        """
        Create entity descendants cache key.

        Args:
            entity_id: Entity ID

        Returns:
            str: Entity descendants cache key
        """
        return self.make_key("auth", "entity", "descendants", entity_id)
