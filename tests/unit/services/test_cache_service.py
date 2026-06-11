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
        self.raw_values: dict[str, str] = {}
        self.raw_set_calls: list[tuple[str, str, int | None]] = []
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

    async def set_raw(self, key: str, value: str, ttl: int | None = None) -> bool:
        self.raw_values[key] = value
        self.raw_set_calls.append((key, value, ttl))
        return True

    async def mget_raw(self, keys: list[str]) -> list[str | None]:
        out: list[str | None] = []
        for key in keys:
            if key in self.raw_values:
                out.append(self.raw_values[key])
            elif key in self.counters:
                out.append(str(self.counters[key]))
            else:
                out.append(None)
        return out

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
async def test_cache_service_permission_check_versioned_roundtrip(auth_config):
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
    ctx_hash = "abc1234567890def"
    abac_key = cache_service.make_permission_check_key("user-1", "user:read", None, ctx_hash)
    assert abac_key == f"auth:permission-check:user-1:global:user:read:{ctx_hash}"

    # Cold read: miss + current versions token for the follow-up write.
    result, versions = await cache_service.get_permission_check("user-1", "user:read")
    assert result is None
    assert versions == {"global": 0, "user:user-1": 0}

    # Positive and negative verdicts both round-trip.
    assert await cache_service.set_permission_check("user-1", "user:read", True, versions=versions) is True
    assert await cache_service.set_permission_check("user-1", "admin:write", False, versions=versions) is True
    result, _ = await cache_service.get_permission_check("user-1", "user:read")
    assert result is True
    result, _ = await cache_service.get_permission_check("user-1", "admin:write")
    assert result is False

    # Entity-scoped entries also validate the entity version.
    result, entity_versions = await cache_service.get_permission_check(
        "user-1", "entity:update", "entity-123"
    )
    assert result is None
    assert entity_versions == {"global": 0, "user:user-1": 0, "entity:entity-123": 0}
    await cache_service.set_permission_check(
        "user-1", "entity:update", True, "entity-123", versions=entity_versions
    )
    result, _ = await cache_service.get_permission_check("user-1", "entity:update", "entity-123")
    assert result is True
    await cache_service.publish_entity_permissions_invalidation("entity-123")
    result, _ = await cache_service.get_permission_check("user-1", "entity:update", "entity-123")
    assert result is None

    # A user bump invalidates the global-scope entry immediately.
    await cache_service.publish_user_permissions_invalidation("user-1")
    result, versions = await cache_service.get_permission_check("user-1", "user:read")
    assert result is None
    assert versions == {"global": 0, "user:user-1": 1}

    # Legacy plain-boolean entries (pre-versioning format) read as a miss.
    redis.raw_values[cache_service.make_permission_check_key("user-1", "legacy:perm")] = "true"
    result, _ = await cache_service.get_permission_check("user-1", "legacy:perm")
    assert result is None

    # Writes without a versions token are refused.
    assert await cache_service.set_permission_check("user-1", "user:read", True) is False

    # TTLs are jittered within ±10% of the configured base.
    base = config.cache_permission_ttl
    spread = base // 10
    for _key, _payload, ttl in redis.raw_set_calls:
        assert base - spread <= ttl <= base + spread


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
async def test_cache_service_user_permission_names_roundtrip_and_version_invalidation(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    # Cold read: miss, but current versions come back for the follow-up write.
    names, versions = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    )
    assert names is None
    assert versions == {"global": 0, "user:user-1": 0}

    assert (
        await cache_service.set_user_permission_names(
            "user-1",
            include_entity_local=False,
            names=["post:read", "comment:create"],
            versions=versions,
        )
        is True
    )
    key, _payload, ttl = redis.raw_set_calls[-1]
    assert key == "auth:user-permissions:user-1:global"
    spread = config.cache_permission_ttl // 10
    assert config.cache_permission_ttl - spread <= ttl <= config.cache_permission_ttl + spread

    # Warm read: hit (names stored sorted).
    names, _ = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    )
    assert names == ["comment:create", "post:read"]

    # The include_entity_local variant is a distinct key — still cold.
    other_names, _ = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=True
    )
    assert other_names is None

    # A user-scoped invalidation (role assignment, membership change, ...)
    # bumps the user version and makes the entry unreadable immediately.
    await cache_service.publish_user_permissions_invalidation("user-1")
    names, versions = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    )
    assert names is None
    assert versions == {"global": 0, "user:user-1": 1}

    # Re-write at the new versions, then verify a global bump (role/permission
    # definition CRUD) invalidates as well.
    await cache_service.set_user_permission_names(
        "user-1", include_entity_local=False, names=["post:read"], versions=versions
    )
    names, _ = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    )
    assert names == ["post:read"]

    await cache_service.publish_all_permissions_invalidation()
    names, _ = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    )
    assert names is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_user_permission_names_racing_write_is_stored_stale(auth_config):
    """A write that lost a race with a concurrent version bump must never be served."""
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    cache_service = CacheService(redis, config)

    _, versions = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    )
    # A mutation bumps the user version between our read and our write.
    await cache_service.publish_user_permissions_invalidation("user-1")
    await cache_service.set_user_permission_names(
        "user-1", include_entity_local=False, names=["post:read"], versions=versions
    )

    names, _ = await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    )
    assert names is None

    # versions=None (Redis was unavailable at read time) makes the write a no-op.
    assert (
        await cache_service.set_user_permission_names(
            "user-1", include_entity_local=False, names=["x:y"], versions=None
        )
        is False
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_batch_user_invalidation_uses_pipeline_helper(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()
    captured: dict = {}

    async def bump_versions_and_publish(*, version_keys, channel, messages):
        captured["version_keys"] = version_keys
        captured["channel"] = channel
        captured["messages"] = messages
        return True

    redis.bump_versions_and_publish = bump_versions_and_publish  # type: ignore[attr-defined]
    cache_service = CacheService(redis, config)

    assert await cache_service.publish_user_permissions_invalidation_batch(["u1", "u2"]) is True
    assert captured["version_keys"] == [
        "auth:api-key-snapshot-version:user:u1",
        "auth:api-key-snapshot-version:user:u2",
    ]
    assert captured["messages"] == ["permissions:user:u1", "permissions:user:u2"]
    assert captured["channel"] == config.redis_invalidation_channel

    # Empty input is a successful no-op.
    captured.clear()
    assert await cache_service.publish_user_permissions_invalidation_batch([]) is True
    assert captured == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_batch_user_invalidation_falls_back_per_user(auth_config):
    config = _cache_config(auth_config)
    redis = _FakeRedis()  # no bump_versions_and_publish helper
    cache_service = CacheService(redis, config)

    assert await cache_service.publish_user_permissions_invalidation_batch(["u1", "u2"]) is True
    assert redis.counters == {
        "auth:api-key-snapshot-version:user:u1": 1,
        "auth:api-key-snapshot-version:user:u2": 1,
    }
    assert redis.published == [
        (config.redis_invalidation_channel, "permissions:user:u1"),
        (config.redis_invalidation_channel, "permissions:user:u2"),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_service_handle_message_no_longer_scan_deletes(auth_config):
    """Versioned entries make pub/sub deletion redundant.

    Every instance used to react to each invalidation message with a
    full-keyspace SCAN+DEL; entries now embed the bumped version counters, so
    the handler is informational and must not run any deletion.
    """
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

    assert calls == []
    assert redis.deleted_patterns == []


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

    assert await cache_service.get_permission_check("user-1", "user:read") == (None, None)
    assert (
        await cache_service.set_permission_check(
            "user-1", "user:read", True, versions={"global": 0, "user:user-1": 0}
        )
        is False
    )
    assert await cache_service.invalidate_user_permissions("user-1") == 0
    assert await cache_service.invalidate_entity_permissions("entity-123") == 0
    assert await cache_service.invalidate_all_permissions() == 0
    assert await cache_service.publish_user_permissions_invalidation("user-1") is False
    assert await cache_service.publish_entity_permissions_invalidation("entity-123") is False
    assert await cache_service.publish_all_permissions_invalidation() is False
    assert await cache_service.publish_role_permissions_invalidation("role-999") is False
    assert await cache_service.get_user_permission_names(
        "user-1", include_entity_local=False
    ) == (None, None)
    assert (
        await cache_service.set_user_permission_names(
            "user-1", include_entity_local=False, names=[], versions={"global": 0}
        )
        is False
    )
