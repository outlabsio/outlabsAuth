"""Production-hardening integration coverage for Redis-backed authentication paths."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.api_key_usage_sync_batch import APIKeyUsageSyncBatch
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.redis_client import RedisClient
from outlabs_auth.services.user import UserService
from scripts.benchmark_auth_paths import make_benchmark_request


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_sync_is_idempotent_when_commit_succeeds_before_redis_ack(
    test_engine,
    redis_client,
    auth_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Redis-ack failure after commit must not cause a duplicate usage update on retry."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    service = APIKeyService(config=auth_config, redis_client=redis_client)
    user_service = UserService(config=auth_config)

    async with session_factory() as session:
        user = await user_service.create_user(
            session,
            email=f"usage-sync-{uuid4().hex}@example.com",
            password="TestPass123!",
        )
        _, api_key = await service.create_api_key(
            session,
            owner_id=user.id,
            name="durable usage sync",
            rate_limit_per_minute=0,
        )
        key_id = api_key.id
        await session.commit()

    usage_key = service._make_usage_counter_key(str(key_id))
    assert await redis_client.increment(usage_key, amount=7) == 7

    original_delete_many = redis_client.delete_many

    async def fail_ack(_keys: list[str]) -> int:
        return 0

    monkeypatch.setattr(redis_client, "delete_many", fail_ack)
    async with session_factory() as session:
        first = await service.sync_usage_counters_to_db(session)
    assert first == {"synced_keys": 1, "total_usage": 7, "errors": 0}

    staged = await redis_client.get_all_counters(service._make_staged_usage_counter_pattern())
    assert len(staged) == 1, "committed batch must remain retryable until acknowledged"

    async with session_factory() as session:
        persisted = await session.get(APIKey, key_id)
        receipts = (await session.execute(select(APIKeyUsageSyncBatch))).scalars().all()
    assert persisted is not None and persisted.usage_count == 7
    assert len(receipts) == 1

    monkeypatch.setattr(redis_client, "delete_many", original_delete_many)
    async with session_factory() as session:
        retry = await service.sync_usage_counters_to_db(session)
    assert retry == {"synced_keys": 0, "total_usage": 0, "errors": 0}
    assert await redis_client.get_all_counters(service._make_staged_usage_counter_pattern()) == {}

    async with session_factory() as session:
        persisted = await session.get(APIKey, key_id)
    assert persisted is not None and persisted.usage_count == 7


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_namespaces_isolate_keys_scans_and_channels(redis_client, test_secret_key: str) -> None:
    """Two applications on one Redis DB cannot observe each other's auth state."""
    other = RedisClient(
        AuthConfig(
            secret_key=test_secret_key,
            redis_url=redis_client.config.redis_url,
            redis_enabled=True,
            redis_key_prefix="outlabs-auth:test:other-application",
        )
    )
    assert await other.connect()
    try:
        await redis_client.set_raw("apikey:shared-looking-id:usage", "9")

        assert await other.get_raw("apikey:shared-looking-id:usage") is None
        assert await other.get_all_counters("apikey:*:usage") == {}
        assert redis_client.make_channel("auth:cache:invalidate") != other.make_channel(
            "auth:cache:invalidate"
        )
    finally:
        await other.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cached_api_key_rate_limit_is_terminal_and_counted_once(auth_with_cache) -> None:
    """An over-limit key returns 429 directly instead of falling through to SQL auth."""
    unique = uuid4().hex[:10]
    permission = f"hardening{unique}:read"
    async with auth_with_cache.get_session() as session:
        user = await auth_with_cache.user_service.create_user(
            session,
            email=f"rate-limit-{unique}@example.com",
            password="TestPass123!",
        )
        await auth_with_cache.permission_service.create_permission(
            session,
            name=permission,
            display_name=permission,
            is_system=True,
        )
        role = await auth_with_cache.role_service.create_role(
            session,
            name=f"hardening-role-{unique}",
            display_name="Hardening role",
            permission_names=[permission],
            is_global=True,
        )
        await auth_with_cache.role_service.assign_role_to_user(
            session,
            user_id=user.id,
            role_id=role.id,
            assigned_by_id=user.id,
        )
        raw_key, api_key = await auth_with_cache.api_key_service.create_api_key(
            session,
            owner_id=user.id,
            name="terminal rate limit",
            scopes=[permission],
            rate_limit_per_minute=1,
        )
        await session.commit()

    dependency = auth_with_cache.deps.require_permission(permission)
    async with auth_with_cache.get_session() as session:
        assert await dependency(request=make_benchmark_request(api_key=raw_key), session=session)

    async with auth_with_cache.get_session() as session:
        with pytest.raises(HTTPException) as exc_info:
            await dependency(request=make_benchmark_request(api_key=raw_key), session=session)
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}

    rate_key = auth_with_cache.api_key_service._make_rate_limit_key(str(api_key.id), "minute")
    assert await auth_with_cache.redis_client.get_counter(rate_key) == 2
