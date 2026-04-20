from __future__ import annotations

import asyncio

import pytest

from outlabs_auth.services.cache import CacheService


class _FakePubSub:
    def __init__(self, messages: list[dict] | None = None) -> None:
        self.closed = False
        self.messages = list(messages or [])

    async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        await asyncio.sleep(0)
        if self.messages:
            return self.messages.pop(0)
        return None

    async def close(self) -> None:
        self.closed = True


class _FakeRedis:
    def __init__(self, *, messages: list[dict] | None = None) -> None:
        self.is_available = True
        self.deleted_patterns: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.subscribed_channels: list[str] = []
        self.get_values: dict[str, object] = {}
        self.counters: dict[str, int] = {}
        self.set_calls: list[tuple[str, object, int | None]] = []
        self.pubsub = _FakePubSub(messages=messages)

    def make_key(self, *parts: str) -> str:
        return ":".join(parts)

    async def get(self, key: str):
        return self.get_values.get(key)

    async def set(self, key: str, value, ttl: int | None = None):
        self.set_calls.append((key, value, ttl))
        return True

    async def get_counter(self, key: str) -> int:
        return self.counters.get(key, 0)

    async def increment(self, key: str, amount: int = 1):
        self.counters[key] = self.counters.get(key, 0) + amount
        return self.counters[key]

    async def delete_pattern(self, pattern: str) -> int:
        self.deleted_patterns.append(pattern)
        return 1

    async def publish(self, channel: str, message: str) -> bool:
        self.published.append((channel, message))
        return True

    async def subscribe(self, channel: str):
        self.subscribed_channels.append(channel)
        return self.pubsub


def _cache_config(auth_config):
    return auth_config.model_copy(
        update={
            "enable_caching": True,
            "redis_url": "redis://cache.test:6379/0",
            "redis_enabled": True,
        }
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_permission_key_get_and_set_helpers(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    global_key = cache_service.make_permission_check_key("user-1", "user:read")
    entity_key = cache_service.make_permission_check_key(
        "user-1",
        "entity:update",
        "entity-123",
    )
    assert global_key == "auth:permission-check:user-1:global:user:read"
    assert entity_key == "auth:permission-check:user-1:entity-123:entity:update"

    redis.get_values[global_key] = True
    redis.get_values[entity_key] = "not-a-bool"

    assert await cache_service.get_permission_check("user-1", "user:read") is True
    assert (
        await cache_service.get_permission_check(
            "user-1",
            "entity:update",
            "entity-123",
        )
        is None
    )

    assert (
        await cache_service.set_permission_check(
            "user-1",
            "entity:update",
            True,
            "entity-123",
        )
        is True
    )
    assert redis.set_calls == [
        (
            "auth:permission-check:user-1:entity-123:entity:update",
            True,
            config.cache_permission_ttl,
        )
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_entity_relation_helpers(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    relation_key = cache_service.make_entity_relation_key(
        "ancestor-1",
        "descendant-1",
        version=7,
    )
    assert relation_key == "auth:entity-relation:7:ancestor-1:descendant-1"

    redis.get_values[relation_key] = True
    assert (
        await cache_service.get_entity_relation(
            "ancestor-1",
            "descendant-1",
            version=7,
        )
        is True
    )

    assert (
        await cache_service.set_entity_relation(
            "ancestor-1",
            "descendant-2",
            False,
            version=7,
        )
        is True
    )
    assert redis.set_calls == [
        (
            "auth:entity-relation:7:ancestor-1:descendant-2",
            False,
            config.cache_entity_ttl,
        )
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_targeted_invalidation_and_publish_helpers(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    assert await cache_service.invalidate_user_permissions("user-1") == 1
    assert await cache_service.invalidate_entity_permissions("entity-123") == 1
    assert await cache_service.invalidate_all_permissions() == 1

    assert await cache_service.publish_user_permissions_invalidation("user-1") is True
    assert await cache_service.publish_entity_permissions_invalidation("entity-123") is True
    assert await cache_service.publish_all_permissions_invalidation() is True
    assert await cache_service.publish_role_permissions_invalidation("role-999") is True

    assert redis.deleted_patterns == [
        "auth:permission-check:user-1:*",
        "auth:permission-check:*:entity-123:*",
        "auth:permission-check:*",
    ]
    assert redis.published == [
        (config.redis_invalidation_channel, "permissions:user:user-1"),
        (config.redis_invalidation_channel, "permissions:entity:entity-123"),
        (config.redis_invalidation_channel, "permissions:all"),
        (config.redis_invalidation_channel, "permissions:all"),
    ]
    assert redis.counters == {
        "auth:api-key-snapshot-version:user:user-1": 1,
        "auth:api-key-snapshot-version:entity:entity-123": 1,
        "auth:api-key-snapshot-version:global": 2,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_api_key_auth_snapshot_version_helpers(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    assert await cache_service.get_api_key_auth_snapshot_versions(
        user_id="user-1",
        integration_principal_id="principal-1",
        entity_id="entity-1",
    ) == {
        "global": 0,
        "user:user-1": 0,
        "integration_principal:principal-1": 0,
        "entity:entity-1": 0,
    }

    assert await cache_service.bump_global_api_key_auth_snapshot_version() == 1
    assert await cache_service.bump_user_api_key_auth_snapshot_version("user-1") == 1
    assert await cache_service.bump_integration_principal_api_key_auth_snapshot_version("principal-1") == 1
    assert await cache_service.bump_entity_api_key_auth_snapshot_version("entity-1") == 1

    assert await cache_service.get_api_key_auth_snapshot_versions(
        user_id="user-1",
        integration_principal_id="principal-1",
        entity_id="entity-1",
    ) == {
        "global": 1,
        "user:user-1": 1,
        "integration_principal:principal-1": 1,
        "entity:entity-1": 1,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_handle_message_routes_targeted_invalidations(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)
    calls: list[tuple[str, str]] = []

    async def _capture_user(user_id: str) -> int:
        calls.append(("user", user_id))
        return 1

    async def _capture_entity(entity_id: str) -> int:
        calls.append(("entity", entity_id))
        return 1

    async def _capture_all() -> int:
        calls.append(("all", "*"))
        return 1

    cache_service.invalidate_user_permissions = _capture_user
    cache_service.invalidate_entity_permissions = _capture_entity
    cache_service.invalidate_all_permissions = _capture_all

    await cache_service._handle_message("permissions:user:user-1")
    await cache_service._handle_message("permissions:entity:entity-123")
    await cache_service._handle_message("permissions:all")
    await cache_service._handle_message("entity:root-1:hierarchy")
    await cache_service._handle_message("unknown:message")

    assert calls == [
        ("user", "user-1"),
        ("entity", "entity-123"),
        ("all", "*"),
        ("all", "*"),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_listener_decodes_bytes_messages_and_dispatches(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis(messages=[{"data": b"permissions:user:user-1"}])
    cache_service = CacheService(redis, config)
    cache_service._pubsub = redis.pubsub
    captured: list[str] = []

    async def _capture(payload: str) -> None:
        captured.append(payload)

    cache_service._handle_message = _capture

    listener = asyncio.create_task(cache_service._listen())
    await asyncio.sleep(0.01)
    listener.cancel()
    with pytest.raises(asyncio.CancelledError):
        await listener

    assert captured == ["permissions:user:user-1"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_noops_when_redis_is_unavailable(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    redis.is_available = False
    cache_service = CacheService(redis, config)

    assert await cache_service.get_permission_check("user-1", "user:read") is None
    assert await cache_service.set_permission_check("user-1", "user:read", True) is False
    assert await cache_service.invalidate_user_permissions("user-1") == 0
    assert await cache_service.invalidate_entity_permissions("entity-123") == 0
    assert await cache_service.invalidate_all_permissions() == 0
    assert await cache_service.publish_user_permissions_invalidation("user-1") is False
    assert await cache_service.publish_entity_permissions_invalidation("entity-123") is False
    assert await cache_service.publish_all_permissions_invalidation() is False
    assert await cache_service.publish_role_permissions_invalidation("role-999") is False
