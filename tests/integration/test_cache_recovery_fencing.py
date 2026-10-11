"""Recovery must not resurrect authority whose publication was missed offline."""

import pytest

from outlabs_auth.models.sql.user import User
from outlabs_auth.services import request_cache
from outlabs_auth.services import cache_validity
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.redis_client import RedisClient
from tests.integration.query_budget_support import seed_simple_query_budget_context
from tests.integration.test_transactional_cache_freshness import auth_context


@pytest.mark.asyncio
async def test_reconnect_fences_permission_revoked_while_cache_was_offline(auth_with_cache):
    auth = auth_with_cache
    seeded = await seed_simple_query_budget_context(auth)
    async with auth.get_session() as session:
        user = await session.get(User, seeded.benchmark_user_id)
        role = await auth.role_service.create_role(
            session=session,
            name="recovery-reader",
            display_name="Recovery reader",
            permission_names=[seeded.permission_missing_name],
            is_global=True,
        )
        await auth.role_service.assign_role_to_user(session=session, user_id=user.id, role_id=role.id)
        await session.commit()

    async def check():
        request_cache.reset()
        async with auth.get_session() as session:
            return await auth.permission_service.check_permission(
                session, user_id=user.id, permission=seeded.permission_missing_name, user=user
            )

    assert await check() is True
    assert await check() is True
    # Keep the Redis data, as happens in a transient network outage. The
    # committed revocation deliberately cannot publish its invalidation.
    auth.redis_client._available = False
    async with auth.get_session() as session:
        await auth.role_service.revoke_role_from_user(session=session, user_id=user.id, role_id=role.id)
        await session.commit()
    assert await check() is False  # authoritative fallback while unavailable
    assert await auth.redis_client.connect()
    assert await check() is False  # stale pre-outage ALLOW must not return


@pytest.mark.asyncio
@pytest.mark.parametrize("local_ttl", [0, 120])
async def test_reconnect_discards_shared_and_local_key_snapshots(redis_client, auth_config, local_ttl):
    config = auth_config.model_copy(update={"enable_caching": True, "api_key_local_snapshot_cache_ttl": local_ttl})
    service = APIKeyService(config, redis_client=redis_client)
    service.cache_service = CacheService(redis_client, config)
    raw_key, key, result = auth_context()
    cache_validity.record(result["user_id"], None)
    result["_outlabs_snapshot_versions"] = await service.cache_service.get_api_key_auth_snapshot_versions(
        user_id=result["user_id"], credential_hash=key.key_hash
    )
    assert await service.set_api_key_auth_snapshot(raw_key, auth_result=result, effective_permissions=["report:read"])
    assert await service.get_api_key_auth_snapshot(raw_key) is not None
    # Missed offline credential revocation; the Redis snapshot remains intact.
    redis_client._available = False
    assert await service.get_api_key_auth_snapshot(raw_key) is None
    assert await redis_client.connect()
    assert await service.get_api_key_auth_snapshot(raw_key) is None


@pytest.mark.asyncio
async def test_recovery_fence_is_visible_to_another_worker(redis_client, auth_config):
    cache = CacheService(redis_client, auth_config)
    before = await cache.get_api_key_auth_snapshot_versions()
    other = RedisClient(redis_client.config)
    try:
        assert await other.connect()
        after = await cache.get_api_key_auth_snapshot_versions()
        assert after["global"] == before["global"] + 1
    finally:
        await other.disconnect()
