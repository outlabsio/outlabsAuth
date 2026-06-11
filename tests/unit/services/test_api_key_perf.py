"""
Performance regression tests for the API-key hot-path optimizations
(docs/PERFORMANCE_AUDIT_2026-06-10.md, Perf #1 + #2).

- Perf #2: the per-request usage + rate-limit writes are pipelined into a single
  Redis round trip, preserving true fixed-window rate-limit semantics (the window
  TTL is established once per window and not reset by later requests).
- Perf #1: an opt-in per-process snapshot cache serves hot keys without a Redis read.
"""
from unittest.mock import AsyncMock

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import APIKeyStatus
from outlabs_auth.services.api_key import APIKeyService

SECRET = "test-secret-key-do-not-use-in-production-12345678"


def _service(local_ttl: float = 0.0, redis_client=None) -> APIKeyService:
    config = AuthConfig(
        secret_key=SECRET,
        enable_caching=True,
        redis_enabled=True,  # satisfies the enable_caching validator; tests inject the client
        api_key_local_snapshot_cache_ttl=local_ttl,
    )
    return APIKeyService(config=config, redis_client=redis_client)


class _FakeRedis:
    """Minimal redis_client stub that counts snapshot reads."""

    is_available = True

    def __init__(self, snapshot: dict):
        self._snapshot = snapshot
        self.get_calls = 0

    def make_key(self, *parts):
        return ":".join(str(part) for part in parts)

    async def get(self, key):
        self.get_calls += 1
        return dict(self._snapshot)

    async def delete(self, key):
        return True


# --------------------------------------------------------------------------
# Perf #2 — pipelined usage + fixed-window rate limit (real Redis)
# --------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_usage_pipeline_counts_and_fixed_window(redis_client):
    usage_key = "perftest:usage"
    last_key = "perftest:last"
    rl_key = "perftest:rl:minute"

    counts = await redis_client.record_api_key_usage_pipeline(
        usage_key=usage_key,
        last_used_key=last_key,
        last_used_value="t1",
        last_used_ttl=300,
        rate_windows=[(rl_key, 60)],
    )
    assert counts is not None
    assert counts[usage_key] == 1
    assert counts[rl_key] == 1
    ttl_after_first = await redis_client._client.ttl(rl_key)
    assert 0 < ttl_after_first <= 60

    counts2 = await redis_client.record_api_key_usage_pipeline(
        usage_key=usage_key,
        last_used_key=last_key,
        last_used_value="t2",
        last_used_ttl=300,
        rate_windows=[(rl_key, 60)],
    )
    assert counts2[usage_key] == 2
    assert counts2[rl_key] == 2
    ttl_after_second = await redis_client._client.ttl(rl_key)
    # Fixed window: SET ... NX EX must NOT reset the TTL on later requests, so the
    # window expires relative to the FIRST request (TTL is non-increasing). A bare
    # EXPIRE-every-request would instead keep the counter alive forever under steady
    # traffic and eventually wedge the limit.
    assert 0 < ttl_after_second <= ttl_after_first


@pytest.mark.unit
@pytest.mark.asyncio
async def test_usage_pipeline_without_rate_windows(redis_client):
    counts = await redis_client.record_api_key_usage_pipeline(
        usage_key="perftest:u2",
        last_used_key="perftest:l2",
        last_used_value="x",
        last_used_ttl=None,
        rate_windows=None,
    )
    assert counts == {"perftest:u2": 1}


# --------------------------------------------------------------------------
# Perf #1 — opt-in per-process snapshot cache
# --------------------------------------------------------------------------

@pytest.mark.unit
def test_local_snapshot_cache_disabled_by_default():
    svc = _service(local_ttl=0.0)
    svc._local_snapshot_put("h1", {"key_id": "k1"})
    assert svc._local_snapshot_get("h1") is None


@pytest.mark.unit
def test_local_snapshot_cache_hit_and_evict():
    svc = _service(local_ttl=5.0)
    snap = {"key_id": "k1", "status": "active"}
    svc._local_snapshot_put("h1", snap)
    assert svc._local_snapshot_get("h1") is snap
    svc._local_snapshot_evict("h1")
    assert svc._local_snapshot_get("h1") is None


@pytest.mark.unit
def test_local_snapshot_cache_expires(monkeypatch):
    import outlabs_auth.services.api_key as mod

    svc = _service(local_ttl=2.0)
    clock = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "monotonic", lambda: clock["t"])

    svc._local_snapshot_put("h1", {"key_id": "k1"})
    assert svc._local_snapshot_get("h1") is not None
    clock["t"] = 1003.0  # 3s elapsed > 2s TTL
    assert svc._local_snapshot_get("h1") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_snapshot_serves_hot_key_from_local_cache(monkeypatch):
    snapshot = {"key_id": "k1", "status": APIKeyStatus.ACTIVE.value, "expires_at": None}
    fake = _FakeRedis(snapshot)
    svc = _service(local_ttl=5.0, redis_client=fake)
    # Version revalidation is covered elsewhere; force a match for this read path.
    monkeypatch.setattr(svc, "_auth_snapshot_versions_match", AsyncMock(return_value=True))

    api_key_string = "k" * 40
    first = await svc.get_api_key_auth_snapshot(api_key_string)
    second = await svc.get_api_key_auth_snapshot(api_key_string)

    assert first is not None and second is not None
    # First call reads Redis; the second is served from the per-process cache.
    assert fake.get_calls == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_snapshot_reads_redis_each_time_when_cache_disabled(monkeypatch):
    snapshot = {"key_id": "k1", "status": APIKeyStatus.ACTIVE.value, "expires_at": None}
    fake = _FakeRedis(snapshot)
    svc = _service(local_ttl=0.0, redis_client=fake)  # in-process cache disabled
    monkeypatch.setattr(svc, "_auth_snapshot_versions_match", AsyncMock(return_value=True))

    api_key_string = "k" * 40
    await svc.get_api_key_auth_snapshot(api_key_string)
    await svc.get_api_key_auth_snapshot(api_key_string)
    assert fake.get_calls == 2
