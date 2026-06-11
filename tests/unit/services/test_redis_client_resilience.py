"""
RedisClient circuit-breaker behavior (perf audit Phase 2, finding 3.6).

Before the breaker, a Redis outage meant every wrapped call ate up to a 2s
socket timeout (multiplied by the 3-8 Redis calls per request), and an outage
at startup disabled caching for the process lifetime. These tests pin the new
contract: connection-class failures open the breaker instantly, a background
probe restores availability, and data-shape errors never trip it.
"""

from __future__ import annotations

import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.services.redis_client import RedisClient


class _FlakyClient:
    """Stands in for redis.asyncio.Redis: fails until ``healthy`` is flipped."""

    def __init__(self) -> None:
        self.healthy = False
        self.ping_calls = 0

    async def get(self, key):
        if not self.healthy:
            raise RedisConnectionError("connection refused")
        return None

    async def ping(self):
        self.ping_calls += 1
        if not self.healthy:
            raise RedisConnectionError("connection refused")
        return True

    async def close(self):
        return None


def _make_client() -> tuple[RedisClient, _FlakyClient]:
    config = AuthConfig(
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        redis_enabled=True,
        redis_url="redis://breaker.test:6379/0",
    )
    client = RedisClient(config)
    fake = _FlakyClient()
    client._client = fake  # type: ignore[assignment]
    client._available = True
    # Instance attributes shadow the class backoff constants for fast tests.
    client._RECONNECT_BACKOFF_INITIAL = 0.01  # type: ignore[misc]
    client._RECONNECT_BACKOFF_MAX = 0.02  # type: ignore[misc]
    return client, fake


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connection_error_trips_breaker_and_probe_restores():
    client, fake = _make_client()

    # The failing call is swallowed (graceful fallback) and opens the breaker.
    assert await client.get("some-key") is None
    assert client.is_available is False
    assert client._reconnect_task is not None

    # Subsequent calls short-circuit without touching the (dead) connection.
    assert await client.get("some-key") is None

    # Once Redis answers again, the probe restores availability.
    fake.healthy = True
    await asyncio.wait_for(client._reconnect_task, timeout=2.0)
    assert client.is_available is True
    assert fake.ping_calls >= 1

    await client.disconnect()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_data_shape_errors_do_not_trip_breaker():
    client, fake = _make_client()

    async def wrongtype(key):
        raise ResponseError("WRONGTYPE Operation against a key holding the wrong kind of value")

    fake.get = wrongtype  # type: ignore[assignment]

    assert await client.get("some-key") is None
    assert client.is_available is True
    assert client._reconnect_task is None

    await client.disconnect()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_disconnect_cancels_reconnect_probe():
    client, _fake = _make_client()
    client._RECONNECT_BACKOFF_INITIAL = 5.0  # type: ignore[misc] — cancel must interrupt the sleep

    await client.get("some-key")
    task = client._reconnect_task
    assert task is not None and not task.done()

    await client.disconnect()
    assert client._reconnect_task is None
    assert task.done()
    assert client.is_available is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_startup_connect_schedules_probe_and_recovers():
    """Redis down at startup must not disable caching for the process lifetime."""
    config = AuthConfig(
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        redis_enabled=True,
        redis_url="redis://breaker.test:6379/0",
    )
    client = RedisClient(config)
    client._RECONNECT_BACKOFF_INITIAL = 0.01  # type: ignore[misc]
    client._RECONNECT_BACKOFF_MAX = 0.02  # type: ignore[misc]
    fake = _FlakyClient()
    client._build_client = lambda: fake  # type: ignore[assignment]

    assert await client.connect() is False
    assert client.is_available is False
    assert client._reconnect_task is not None

    fake.healthy = True
    await asyncio.wait_for(client._reconnect_task, timeout=2.0)
    assert client.is_available is True

    await client.disconnect()
