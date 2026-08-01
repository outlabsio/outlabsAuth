"""Unit tests for MemoryCacheBackend (DD-057)."""

from __future__ import annotations

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.cache_backend import MemoryCacheBackend


@pytest.fixture
def memory_config(test_secret_key: str) -> AuthConfig:
    return AuthConfig(
        secret_key=test_secret_key,
        cache_backend="memory",
        redis_key_prefix="outlabs-auth:test:memory",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_backend_set_get_and_ttl(memory_config: AuthConfig):
    backend = MemoryCacheBackend(memory_config, max_entries=100)
    key = backend.make_key("auth", "permission-check", "u1", "global", "post:read")

    assert await backend.set(key, {"allowed": True}, ttl=60) is True
    assert await backend.get(key) == {"allowed": True}
    assert await backend.mget_raw([key]) == ['{"allowed": true}']


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_backend_increment_and_bump_versions(memory_config: AuthConfig):
    backend = MemoryCacheBackend(memory_config, max_entries=100)
    version_key = backend.make_key("auth", "api-key-snapshot-version", "global")

    assert await backend.increment(version_key) == 1
    assert await backend.get_counter(version_key) == 1
    assert await backend.bump_versions_and_publish(
        version_keys=[version_key],
        channel="cache-invalidate",
        messages=["all"],
    )
    assert await backend.get_counter(version_key) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_backend_delete_pattern(memory_config: AuthConfig):
    backend = MemoryCacheBackend(memory_config, max_entries=100)
    k1 = backend.make_key("auth", "permission-check", "u1", "global", "a")
    k2 = backend.make_key("auth", "permission-check", "u1", "global", "b")
    k3 = backend.make_key("auth", "other", "x")
    await backend.set(k1, True)
    await backend.set(k2, True)
    await backend.set(k3, True)

    deleted = await backend.delete_pattern(
        backend.make_key("auth", "permission-check", "u1", "*")
    )
    assert deleted == 2
    assert await backend.get(k1) is None
    assert await backend.get(k3) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_works_with_memory_backend(memory_config: AuthConfig):
    backend = MemoryCacheBackend(memory_config, max_entries=100)
    cache = CacheService(backend, memory_config)

    key = cache.make_permission_check_key("user-1", "post:read")
    await backend.set(key, True, ttl=60)
    assert await backend.get(key) is True

    # Invalidation helpers should talk to the memory backend without error.
    assert await cache.invalidate_user_permissions("user-1") >= 0
