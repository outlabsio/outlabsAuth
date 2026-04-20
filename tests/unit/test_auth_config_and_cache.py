from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from outlabs_auth import SimpleRBAC
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import ConfigurationError
from outlabs_auth.services.cache import CacheService


class _FakePubSub:
    def __init__(self) -> None:
        self.closed = False

    async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        await asyncio.sleep(0)
        return None

    async def close(self) -> None:
        self.closed = True


class _FakeRedis:
    def __init__(self) -> None:
        self.is_available = True
        self.deleted_patterns: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.subscribed_channels: list[str] = []
        self.pubsub = _FakePubSub()

    def make_key(self, *parts: str) -> str:
        return ":".join(parts)

    async def get(self, key: str):
        return None

    async def set(self, key: str, value, ttl: int | None = None):
        return True

    async def delete_pattern(self, pattern: str) -> int:
        self.deleted_patterns.append(pattern)
        return 1

    async def publish(self, channel: str, message: str) -> bool:
        self.published.append((channel, message))
        return True

    async def subscribe(self, channel: str):
        self.subscribed_channels.append(channel)
        return self.pubsub


@pytest.mark.unit
def test_removed_multi_tenant_argument_is_rejected():
    with pytest.raises(ConfigurationError, match="multi_tenant is no longer supported"):
        SimpleRBAC(
            database_url="postgresql+asyncpg://example:example@localhost:5432/test",
            secret_key="test-secret-key-do-not-use-in-production-12345678",
            multi_tenant=True,
        )


@pytest.mark.unit
def test_oauth_token_storage_requires_encryption_key():
    with pytest.raises(
        ConfigurationError,
        match="store_oauth_provider_tokens=True requires oauth_token_encryption_key",
    ):
        SimpleRBAC(
            database_url="postgresql+asyncpg://example:example@localhost:5432/test",
            secret_key="test-secret-key-do-not-use-in-production-12345678",
            store_oauth_provider_tokens=True,
        )


@pytest.mark.unit
def test_auth_config_enables_redis_and_caching_from_redis_url(test_secret_key: str):
    config = AuthConfig(
        secret_key=test_secret_key,
        redis_url="redis://localhost:6379/0",
    )

    assert config.redis_enabled is True
    assert config.enable_caching is True


@pytest.mark.unit
def test_auth_config_preserves_explicit_cache_opt_out(test_secret_key: str):
    config = AuthConfig(
        secret_key=test_secret_key,
        redis_url="redis://localhost:6379/0",
        enable_caching=False,
    )

    assert config.redis_enabled is True
    assert config.enable_caching is False


@pytest.mark.unit
def test_auth_config_preserves_explicit_redis_opt_out(test_secret_key: str):
    config = AuthConfig(
        secret_key=test_secret_key,
        redis_url="redis://localhost:6379/0",
        redis_enabled=False,
    )

    assert config.redis_enabled is False
    assert config.enable_caching is False


@pytest.mark.unit
def test_auth_config_rejects_cache_without_redis(test_secret_key: str):
    with pytest.raises(ValidationError, match="enable_caching=True requires Redis"):
        AuthConfig(
            secret_key=test_secret_key,
            enable_caching=True,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_invalidates_permission_cache_for_entity_messages(auth_config):
    config = auth_config.model_copy(
        update={
            "enable_caching": True,
            "redis_url": "redis://cache.test:6379/0",
            "redis_enabled": True,
        }
    )
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    await cache_service._handle_message("all:entities")
    await cache_service._handle_message("entity:1234:hierarchy")

    assert redis.deleted_patterns == [
        "auth:permission-check:*",
        "auth:permission-check:*",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_listener_lifecycle(auth_config):
    config = auth_config.model_copy(
        update={
            "enable_caching": True,
            "redis_url": "redis://cache.test:6379/0",
            "redis_enabled": True,
        }
    )
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    await cache_service.start()

    assert redis.subscribed_channels == [config.redis_invalidation_channel]
    assert cache_service._listener_task is not None

    await cache_service.shutdown()

    assert cache_service._listener_task is None
    assert redis.pubsub.closed is True
