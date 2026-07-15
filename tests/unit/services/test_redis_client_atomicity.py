"""
Redis primitives against a real server: atomic window counters and the
pipelined invalidation helpers (perf audit Phase 2, findings 3.3 / 3.7).

Uses the ``redis_client`` fixture (TEST_REDIS_URL, DB flushed per test);
skips when Redis is unreachable.
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_increment_with_ttl_sets_window_ttl_atomically(redis_client):
    count = await redis_client.increment_with_ttl("bench:window", amount=1, ttl=60)
    assert count == 1
    ttl = await redis_client._client.ttl(redis_client.make_key("bench:window"))
    assert 0 < ttl <= 60

    # Subsequent increments keep counting inside the same window.
    count = await redis_client.increment_with_ttl("bench:window", amount=1, ttl=60)
    assert count == 2
    assert 0 < await redis_client._client.ttl(redis_client.make_key("bench:window")) <= 60


@pytest.mark.unit
@pytest.mark.asyncio
async def test_increment_with_ttl_heals_legacy_immortal_counter(redis_client):
    # A counter left behind by the old non-atomic INCR-then-EXPIRE shape:
    # value present, no TTL — previously rate-limited the key forever.
    await redis_client.set_raw("bench:immortal", "7")
    assert await redis_client._client.ttl(redis_client.make_key("bench:immortal")) == -1

    count = await redis_client.increment_with_ttl("bench:immortal", amount=1, ttl=60)
    assert count == 8
    assert 0 < await redis_client._client.ttl(redis_client.make_key("bench:immortal")) <= 60


@pytest.mark.unit
@pytest.mark.asyncio
async def test_increment_without_ttl_keeps_plain_incr_semantics(redis_client):
    assert await redis_client.increment_with_ttl("bench:plain", amount=5) == 5
    assert await redis_client.increment_with_ttl("bench:plain", amount=5) == 10
    assert await redis_client._client.ttl(redis_client.make_key("bench:plain")) == -1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_many_unlinks_in_one_round_trip(redis_client):
    await redis_client.set_raw("bench:k1", "a")
    await redis_client.set_raw("bench:k2", "b")

    assert await redis_client.delete_many(["bench:k1", "bench:k2", "bench:missing"]) == 2
    assert await redis_client.get_raw("bench:k1") is None
    assert await redis_client.delete_many([]) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bump_versions_and_publish_pipeline(redis_client):
    ok = await redis_client.bump_versions_and_publish(
        version_keys=["bench:v1", "bench:v2"],
        channel="bench:chan",
        messages=["m1", "m2"],
    )
    assert ok is True
    assert await redis_client.get_counter("bench:v1") == 1
    assert await redis_client.get_counter("bench:v2") == 1

    ok = await redis_client.bump_versions_and_publish(
        version_keys=["bench:v1"],
        channel="bench:chan",
        messages=[],
    )
    assert ok is True
    assert await redis_client.get_counter("bench:v1") == 2
