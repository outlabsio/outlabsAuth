"""Release-critical API-key rate-limit contracts against a real Redis server."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import RateLimitError
from outlabs_auth.services.api_key import APIKeyService


def _service(redis_client, secret_key: str) -> APIKeyService:
    return APIKeyService(
        config=AuthConfig(
            secret_key=secret_key,
            enable_caching=True,
            redis_enabled=True,
            redis_key_prefix="outlabs-auth:test:rate-limit-contract",
        ),
        redis_client=redis_client,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cached_authorization_heals_all_windows_before_rejecting_over_limit(
    redis_client,
    test_secret_key,
):
    """The real cached-key service path must heal TTLs even when it raises 429."""
    service = _service(redis_client, test_secret_key)
    key_id = str(uuid4())
    snapshot = {
        "key_id": key_id,
        "key_prefix": "sk_live_contract",
        "key_kind": "system_integration",
        "rate_limit_per_minute": 2,
        "rate_limit_per_hour": 100,
        "rate_limit_per_day": 1_000,
    }
    minute_key = service._make_rate_limit_key(key_id, "minute")
    hour_key = service._make_rate_limit_key(key_id, "hour")
    day_key = service._make_rate_limit_key(key_id, "day")

    # Production incident shape for minute/day; the hour window is healthy and
    # must keep its original fixed-window expiry rather than being extended.
    assert await redis_client.set_raw(minute_key, "4487")
    assert await redis_client.set_raw(hour_key, "8", ttl=45)
    assert await redis_client.set_raw(day_key, "21")
    hour_ttl_before = await redis_client._client.ttl(redis_client.make_key(hour_key))

    with pytest.raises(RateLimitError) as exc_info:
        await service.record_api_key_auth_snapshot_usage(snapshot)

    assert exc_info.value.details == {
        "limit": 2,
        "current": 4488,
        "window": "minute",
        "retry_after_seconds": 60,
    }
    assert 0 < await redis_client._client.ttl(redis_client.make_key(minute_key)) <= 60
    assert 0 < await redis_client._client.ttl(redis_client.make_key(hour_key)) <= hour_ttl_before
    assert 0 < await redis_client._client.ttl(redis_client.make_key(day_key)) <= 86_400
    assert await redis_client.get_counter(service._make_usage_counter_key(key_id)) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_pipeline_resets_after_the_fixed_window_expires(redis_client):
    rate_key = "contract:expires:minute"

    first = await redis_client.record_api_key_usage_pipeline(
        usage_key="contract:expires:usage",
        last_used_key="contract:expires:last",
        last_used_value="first",
        rate_windows=[(rate_key, 1)],
    )
    assert first is not None and first[rate_key] == 1

    await asyncio.sleep(1.1)

    second = await redis_client.record_api_key_usage_pipeline(
        usage_key="contract:expires:usage",
        last_used_key="contract:expires:last",
        last_used_value="second",
        rate_windows=[(rate_key, 1)],
    )
    assert second is not None and second[rate_key] == 1
    assert 0 < await redis_client._client.ttl(redis_client.make_key(rate_key)) <= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_usage_pipeline_keeps_one_expiring_window(redis_client):
    rate_key = "contract:concurrent:minute"
    request_count = 40  # Heavy burst within the client's 50-connection pool contract.

    async def record(number: int) -> dict[str, int] | None:
        return await redis_client.record_api_key_usage_pipeline(
            usage_key="contract:concurrent:usage",
            last_used_key="contract:concurrent:last",
            last_used_value=str(number),
            rate_windows=[(rate_key, 60)],
        )

    results = await asyncio.gather(*(record(number) for number in range(request_count)))

    assert all(result is not None for result in results)
    assert sorted(result[rate_key] for result in results if result is not None) == list(range(1, request_count + 1))
    assert await redis_client.get_counter("contract:concurrent:usage") == request_count
    assert 0 < await redis_client._client.ttl(redis_client.make_key(rate_key)) <= 60
