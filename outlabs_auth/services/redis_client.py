"""
Redis Client Manager

Handles Redis connections with graceful fallback when Redis is unavailable.
Provides caching operations with automatic serialization/deserialization.
"""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any, List, Optional, cast

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import RedisError
    from redis.exceptions import TimeoutError as RedisTimeoutError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None  # type: ignore
    RedisError = Exception  # type: ignore
    RedisConnectionError = Exception  # type: ignore
    RedisTimeoutError = Exception  # type: ignore

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
        self._reconnect_task: Optional["asyncio.Task[None]"] = None
        self._closed = False

    def _build_client(self) -> "Redis":
        client_kwargs = {
            "decode_responses": True,
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
            "retry_on_timeout": True,
            "max_connections": 50,
        }
        if self.config.redis_url:
            return redis.Redis.from_url(self.config.redis_url, **client_kwargs)
        return redis.Redis(
            host=self.config.redis_host,
            port=self.config.redis_port,
            db=self.config.redis_db,
            password=self.config.redis_password,
            **client_kwargs,
        )

    async def connect(self) -> bool:
        """
        Connect to Redis server.

        Returns:
            bool: True if connected, False if unavailable

        A failed connection no longer disables caching for the process
        lifetime: the background reconnect probe keeps pinging and re-enables
        Redis features when the server answers again.
        """
        if not REDIS_AVAILABLE:
            logger.warning("redis package not installed - caching disabled")
            return False

        if not self.config.redis_enabled:
            logger.info("Redis caching disabled in configuration")
            return False

        self._closed = False
        try:
            if self._client is None:
                self._client = self._build_client()

            # Test connection
            await self._client.ping()
            self._available = True
            location = self.config.redis_url or f"{self.config.redis_host}:{self.config.redis_port}"
            logger.info(f"Connected to Redis at {location}")
            return True

        except (RedisConnectionError, RedisTimeoutError, RedisError, OSError) as e:
            self._trip_breaker(e)
            logger.warning(f"Redis connection failed: {e} - caching disabled until reconnect")
            self._available = False
            self._schedule_reconnect()
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._closed = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
        if self._client:
            await self._client.close()
            self._available = False
            logger.info("Disconnected from Redis")

    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._available

    # Circuit breaker: a Redis outage must not add per-call socket timeouts to
    # every request, and an outage at startup must not disable caching for the
    # process lifetime. On a connection-class failure we flip _available off
    # (callers fall back instantly) and a single background probe re-pings with
    # exponential backoff until Redis answers again.

    _RECONNECT_BACKOFF_INITIAL = 1.0
    _RECONNECT_BACKOFF_MAX = 30.0

    def _trip_breaker(self, error: BaseException) -> None:
        """Open the breaker on connection-class errors (server unreachable).

        Data-shape errors (WRONGTYPE, decode failures, ...) don't mean the
        server is down and must not disable caching.
        """
        if not isinstance(error, (RedisConnectionError, RedisTimeoutError, OSError)):
            return
        if not self._available:
            return
        self._available = False
        logger.warning(f"Redis connection lost ({error}) - caching disabled until reconnect")
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._closed or not REDIS_AVAILABLE or not self.config.redis_enabled:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        try:
            self._reconnect_task = asyncio.create_task(self._reconnect_probe())
        except RuntimeError:
            # No running event loop (sync construction/teardown) — the next
            # connect() call retries instead.
            self._reconnect_task = None

    async def _reconnect_probe(self) -> None:
        backoff = self._RECONNECT_BACKOFF_INITIAL
        while not self._available and not self._closed:
            await asyncio.sleep(backoff)
            try:
                if self._client is None:
                    self._client = self._build_client()
                await self._client.ping()
            except (RedisConnectionError, RedisTimeoutError, RedisError, OSError):
                backoff = min(backoff * 2, self._RECONNECT_BACKOFF_MAX)
                continue
            self._available = True
            logger.info("Redis connection restored - caching re-enabled")
            return

    # Low-level Redis passthroughs (used by activity tracking, etc.)

    async def sadd(self, key: str, *members: str) -> int:
        if not self._available or not self._client:
            return 0
        try:
            return int(await cast(Any, self._client.sadd(key, *members)))
        except RedisError as e:
            self._trip_breaker(e)
            return 0

    async def scard(self, key: str) -> int:
        if not self._available or not self._client:
            return 0
        try:
            return int(await cast(Any, self._client.scard(key)))
        except RedisError as e:
            self._trip_breaker(e)
            return 0

    async def smembers(self, key: str) -> set[str]:
        if not self._available or not self._client:
            return set()
        try:
            members = await cast(Any, self._client.smembers(key))
            return set(members) if members else set()
        except RedisError as e:
            self._trip_breaker(e)
            return set()

    async def expire(self, key: str, seconds: int) -> bool:
        if not self._available or not self._client:
            return False
        try:
            return bool(await self._client.expire(key, seconds))
        except RedisError as e:
            self._trip_breaker(e)
            return False

    async def set_raw(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        if not self._available or not self._client:
            return False
        try:
            if ttl is not None:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except RedisError as e:
            self._trip_breaker(e)
            return False

    async def get_raw(self, key: str) -> Optional[str]:
        if not self._available or not self._client:
            return None
        try:
            return cast(Optional[str], await self._client.get(key))
        except RedisError as e:
            self._trip_breaker(e)
            return None

    async def mget_raw(self, keys: List[str]) -> Optional[List[Optional[str]]]:
        """Fetch several keys in one round trip; None (vs a list) means Redis failed."""
        if not self._available or not self._client:
            return None
        if not keys:
            return []
        try:
            values = await cast(Any, self._client.mget(keys))
            return [cast(Optional[str], value) for value in values]
        except RedisError as e:
            self._trip_breaker(e)
            return None

    async def scan(
        self, cursor: int = 0, match: Optional[str] = None, count: int = 100
    ) -> tuple[int, list[str]]:
        if not self._available or not self._client:
            return 0, []
        try:
            next_cursor, keys = await self._client.scan(
                cursor=cursor, match=match, count=count
            )
            return int(next_cursor), list(keys) if keys else []
        except RedisError as e:
            self._trip_breaker(e)
            return 0, []

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
            self._trip_breaker(e)
            logger.debug(f"Cache get failed for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
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
        except (RedisError, TypeError, ValueError) as e:
            self._trip_breaker(e)
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
            self._trip_breaker(e)
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
            self._trip_breaker(e)
            logger.debug(f"Cache delete pattern failed for {pattern}: {e}")
            return 0

    async def delete_many(self, keys: List[str]) -> int:
        """Delete several keys in one round trip (UNLINK, falling back to DEL)."""
        if not self._available or not self._client:
            return 0
        if not keys:
            return 0
        try:
            return int(await cast(Any, self._client.unlink(*keys)))
        except RedisError as e:
            self._trip_breaker(e)
            try:
                return int(await cast(Any, self._client.delete(*keys)))
            except RedisError as e:
                self._trip_breaker(e)
                logger.debug(f"Delete many failed: {e}")
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
            self._trip_breaker(e)
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
            return cast(Optional[int], await self._client.incrby(key, amount))
        except RedisError as e:
            self._trip_breaker(e)
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
            self._trip_breaker(e)
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
            self._trip_breaker(e)
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
            self._trip_breaker(e)
            logger.debug(f"Get and reset counter failed for {key}: {e}")
            return 0

    async def increment_with_ttl(
        self, key: str, amount: int = 1, ttl: Optional[int] = None
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
            if not ttl:
                return cast(int, await self._client.incrby(key, amount))

            # SET NX EX + INCRBY in one pipelined round trip: the window TTL is
            # established atomically with the first increment, so it can never
            # be lost between an INCR and a separate EXPIRE (the old shape left
            # an immortal counter — i.e. a permanently rate-limited key — when
            # the EXPIRE never landed).
            pipe = self._client.pipeline(transaction=False)
            pipe.set(key, 0, nx=True, ex=ttl)
            pipe.incrby(key, amount)
            pipe.ttl(key)
            results = await pipe.execute()
            new_value = int(results[1])
            if int(results[2]) < 0:
                # Pre-existing key without a TTL (written by the old non-atomic
                # shape) — heal it with the window TTL.
                await self._client.expire(key, ttl)
            return new_value
        except (RedisError, IndexError, TypeError, ValueError) as e:
            self._trip_breaker(e)
            logger.debug(f"Increment with TTL failed for {key}: {e}")
            return None

    async def record_api_key_usage_pipeline(
        self,
        *,
        usage_key: str,
        last_used_key: str,
        last_used_value: str,
        last_used_ttl: Optional[int] = None,
        rate_windows: Optional[list[tuple[str, int]]] = None,
    ) -> Optional[dict[str, int]]:
        """Record per-request API-key usage and rate-limit counters in ONE round trip.

        Pipelines (non-transactional) the writes that previously ran as 3-4 sequential
        awaits on the API-key hot path:
          - ``INCR usage_key``
          - ``SET last_used_key`` (with optional TTL)
          - for each ``(rate_limit_key, ttl)`` window: ``SET key 0 NX EX ttl`` then ``INCR``

        The ``SET ... NX EX`` establishes the window TTL exactly once (on the first request
        of the window) and is a no-op thereafter, preserving true fixed-window semantics
        without a read-back — issuing a bare ``EXPIRE`` every request would instead keep
        resetting the TTL and the counter would never roll over under steady traffic.

        Returns ``{usage_key: count, <rate_limit_key>: count, ...}``, or ``None`` if Redis
        is unavailable (callers fall back to their existing per-op path).
        """
        if not self._available or not self._client:
            return None

        windows = list(rate_windows or [])
        try:
            pipe = self._client.pipeline(transaction=False)
            pipe.incrby(usage_key, 1)
            if last_used_ttl:
                pipe.set(last_used_key, last_used_value, ex=last_used_ttl)
            else:
                pipe.set(last_used_key, last_used_value)
            for rate_key, ttl in windows:
                pipe.set(rate_key, 0, nx=True, ex=ttl)
                pipe.incrby(rate_key, 1)
            results = await pipe.execute()
        except RedisError as e:
            self._trip_breaker(e)
            logger.debug(f"API key usage pipeline failed: {e}")
            return None

        try:
            counts: dict[str, int] = {usage_key: int(results[0] or 0)}
            cursor = 2  # results[1] is the last_used SET
            for rate_key, _ttl in windows:
                # results[cursor] = SET NX result, results[cursor + 1] = INCR result
                counts[rate_key] = int(results[cursor + 1] or 0)
                cursor += 2
        except (IndexError, TypeError, ValueError) as e:
            logger.debug(f"API key usage pipeline result parse failed: {e}")
            return None
        return counts

    async def record_activity_pipeline(
        self,
        *,
        member: str,
        set_ops: list[tuple[str, int]],
        last_activity_key: str,
        last_activity_value: str,
        last_activity_ttl: int,
    ) -> bool:
        """Record activity-tracking bookkeeping in ONE round trip.

        Pipelines (non-transactional) the SADD + EXPIRE pair for each
        ``(set_key, ttl_seconds)`` in ``set_ops`` plus the last-activity SET —
        previously 7 sequential awaits per authenticated request.
        """
        if not self._available or not self._client:
            return False
        try:
            pipe = self._client.pipeline(transaction=False)
            for set_key, ttl_seconds in set_ops:
                pipe.sadd(set_key, member)
                pipe.expire(set_key, ttl_seconds)
            pipe.set(last_activity_key, last_activity_value, ex=last_activity_ttl)
            await pipe.execute()
            return True
        except RedisError as e:
            self._trip_breaker(e)
            logger.debug(f"Activity tracking pipeline failed: {e}")
            return False

    async def bump_versions_and_publish(
        self,
        *,
        version_keys: List[str],
        channel: str,
        messages: List[str],
    ) -> bool:
        """INCR every version key and publish every message in ONE round trip.

        Used by invalidation fan-outs (e.g. a role edit touching up to 200
        users) that previously issued two sequential round trips per user.
        """
        if not self._available or not self._client:
            return False
        try:
            pipe = self._client.pipeline(transaction=False)
            for key in version_keys:
                pipe.incrby(key, 1)
            for message in messages:
                pipe.publish(channel, message)
            await pipe.execute()
            return True
        except RedisError as e:
            self._trip_breaker(e)
            logger.debug(f"Version bump/publish pipeline failed: {e}")
            return False

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
            self._trip_breaker(e)
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
            self._trip_breaker(e)
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
