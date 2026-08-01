"""In-process cache backend for Redis-optional permission caching (DD-057)."""

from __future__ import annotations

import fnmatch
import json
import time
from collections import OrderedDict
from typing import Any, Optional

from outlabs_auth.core.config import AuthConfig


class MemoryCacheBackend:
    """Bounded in-process cache with the RedisClient surface CacheService uses.

    Single-instance deployments get instant invalidation via local version
    counters (pub/sub is a no-op). Multi-instance deployments see only
    TTL-bounded staleness — use Redis when workers must share a cache.
    """

    def __init__(
        self,
        config: AuthConfig,
        *,
        max_entries: int = 10_000,
    ) -> None:
        self.config = config
        self._max_entries = max(1, max_entries)
        # key -> (expires_at_monotonic | None, raw_string_value)
        self._store: OrderedDict[str, tuple[Optional[float], str]] = OrderedDict()

    @property
    def is_available(self) -> bool:
        return True

    @property
    def redis_key_prefix(self) -> str:
        prefix = self.config.redis_key_prefix
        if not prefix:
            raise RuntimeError("MemoryCacheBackend requires AuthConfig.redis_key_prefix")
        return prefix

    def _qualify_key(self, key: str) -> str:
        prefix = self.redis_key_prefix
        return key if key == prefix or key.startswith(f"{prefix}:") else f"{prefix}:{key}"

    def make_key(self, *parts: str) -> str:
        return self._qualify_key(":".join(str(p) for p in parts))

    def make_channel(self, channel: str) -> str:
        return self._qualify_key(f"channel:{channel}")

    def _purge_expired(self, key: str) -> None:
        item = self._store.get(key)
        if item is None:
            return
        expires_at, _value = item
        if expires_at is not None and expires_at <= time.monotonic():
            self._store.pop(key, None)

    def _evict_if_needed(self) -> None:
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def _set_raw_value(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        qualified = self._qualify_key(key)
        expires_at = time.monotonic() + ttl if ttl and ttl > 0 else None
        if qualified in self._store:
            self._store.move_to_end(qualified)
        self._store[qualified] = (expires_at, value)
        self._evict_if_needed()

    def _get_raw_value(self, key: str) -> Optional[str]:
        qualified = self._qualify_key(key)
        self._purge_expired(qualified)
        item = self._store.get(qualified)
        if item is None:
            return None
        self._store.move_to_end(qualified)
        return item[1]

    async def set_raw(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        self._set_raw_value(key, value, ttl)
        return True

    async def get_raw(self, key: str) -> Optional[str]:
        return self._get_raw_value(key)

    async def mget_raw(self, keys: list[str]) -> Optional[list[Optional[str]]]:
        return [self._get_raw_value(key) for key in keys]

    async def get(self, key: str) -> Optional[Any]:
        raw = self._get_raw_value(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            self._set_raw_value(key, json.dumps(value), ttl)
            return True
        except (TypeError, ValueError):
            return False

    async def delete(self, key: str) -> bool:
        qualified = self._qualify_key(key)
        return self._store.pop(qualified, None) is not None

    async def delete_pattern(self, pattern: str) -> int:
        qualified_pattern = self._qualify_key(pattern)
        matches = [key for key in list(self._store) if fnmatch.fnmatchcase(key, qualified_pattern)]
        for key in matches:
            self._store.pop(key, None)
        return len(matches)

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        current_raw = self._get_raw_value(key)
        try:
            current = int(current_raw) if current_raw is not None else 0
        except (TypeError, ValueError):
            current = 0
        new_value = current + amount
        # Preserve existing TTL when present.
        qualified = self._qualify_key(key)
        expires_at = None
        existing = self._store.get(qualified)
        if existing is not None:
            expires_at = existing[0]
        if qualified in self._store:
            self._store.move_to_end(qualified)
        self._store[qualified] = (expires_at, str(new_value))
        self._evict_if_needed()
        return new_value

    async def get_counter(self, key: str) -> int:
        raw = self._get_raw_value(key)
        try:
            return int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            return 0

    async def bump_versions_and_publish(
        self,
        *,
        version_keys: list[str],
        channel: str,
        messages: list[str],
    ) -> bool:
        for key in version_keys:
            await self.increment(key, amount=1)
        # Pub/sub is intentionally a no-op for in-process single-instance caches.
        _ = (channel, messages)
        return True

    async def publish(self, channel: str, message: str) -> bool:
        _ = (channel, message)
        return True

    async def subscribe(self, *channels: str):
        _ = channels
        return None
