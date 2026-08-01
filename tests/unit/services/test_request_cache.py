from __future__ import annotations

import asyncio

import pytest

from outlabs_auth.services import request_cache


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_returns_none_before_any_write_and_absent_keys():
    request_cache.reset()

    assert request_cache.get(("user", "u1")) is None
    assert request_cache.contains(("user", "u1")) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_value_and_get_round_trip_survives_across_awaits():
    request_cache.reset()

    request_cache.set_value(("user", "u1"), {"name": "Alice"})
    await asyncio.sleep(0)
    assert request_cache.get(("user", "u1")) == {"name": "Alice"}
    assert request_cache.contains(("user", "u1")) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reset_drops_all_entries():
    request_cache.reset()
    request_cache.set_value(("user", "u1"), "v1")
    request_cache.set_value(("entity", "e1"), "v2")

    request_cache.reset()

    assert request_cache.get(("user", "u1")) is None
    assert request_cache.get(("entity", "e1")) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_or_load_calls_loader_only_on_miss():
    request_cache.reset()
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return {"v": 1}

    first = await request_cache.get_or_load(("user", "u1"), loader)
    second = await request_cache.get_or_load(("user", "u1"), loader)

    assert first is second
    assert calls == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_or_load_caches_none_results():
    request_cache.reset()
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return None

    assert await request_cache.get_or_load(("missing",), loader) is None
    assert await request_cache.get_or_load(("missing",), loader) is None
    assert calls == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_isolated_between_independent_contexts():
    """Two independent contexts (simulating separate requests) do not share state."""
    import contextvars

    ctx_a = contextvars.copy_context()
    ctx_b = contextvars.copy_context()

    def _seed_a():
        request_cache.reset()
        request_cache.set_value(("user", "u1"), "A")

    def _read_b():
        request_cache.reset()
        return request_cache.get(("user", "u1"))

    ctx_a.run(_seed_a)
    observed_in_b = ctx_b.run(_read_b)

    assert observed_in_b is None
    assert ctx_a.run(request_cache.get, ("user", "u1")) == "A"
