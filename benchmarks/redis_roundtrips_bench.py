"""
Wall-clock micro-benchmarks for the Redis round-trip optimizations
(perf audit Phases 1-2).

Measures the old sequential-await shapes against the pipelined replacements on
a real Redis, so the speedups claimed in docs/PERFORMANCE_AUDIT_2026-06.md can
be re-verified on any box:

  - activity tracking: 7 sequential ops  vs  1 pipelined round trip
  - snapshot version validation: 3 sequential GETs  vs  1 MGET
  - rate-limit window: INCR + EXPIRE  vs  atomic SET NX EX + INCRBY pipeline
  - invalidation fan-out (50 users): 100 sequential ops  vs  1 pipeline

Usage:
    REDIS_URL=redis://localhost:6379/15 uv run python benchmarks/redis_roundtrips_bench.py
    # falls back to TEST_REDIS_URL, then redis://localhost:6379/15

The DB selected by the URL gets benchmark keys written and deleted; don't
point it at production.
"""

from __future__ import annotations

import asyncio
import os
import time

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.services.redis_client import RedisClient

ITERATIONS = 300
FANOUT_USERS = 50


async def _timed(label: str, fn, iterations: int = ITERATIONS) -> float:
    # Warmup
    for _ in range(10):
        await fn()
    start = time.perf_counter()
    for _ in range(iterations):
        await fn()
    per_op_us = (time.perf_counter() - start) / iterations * 1_000_000
    print(f"  {label:<58} {per_op_us:>10.1f} µs/op")
    return per_op_us


async def main() -> None:
    redis_url = os.getenv("REDIS_URL") or os.getenv("TEST_REDIS_URL") or "redis://localhost:6379/15"
    config = AuthConfig(
        secret_key="benchmark-secret-key-not-for-production-123456",
        redis_enabled=True,
        redis_url=redis_url,
    )
    client = RedisClient(config)
    if not await client.connect():
        raise SystemExit(f"Redis not reachable at {redis_url}")
    raw = client._client
    assert raw is not None
    print(f"Redis: {redis_url}, {ITERATIONS} iterations per case\n")

    # --- Activity tracking: 7 sequential ops vs 1 pipeline -------------------
    async def activity_sequential():
        await client.sadd("bench:act:d", "u1")
        await client.expire("bench:act:d", 3600)
        await client.sadd("bench:act:m", "u1")
        await client.expire("bench:act:m", 3600)
        await client.sadd("bench:act:q", "u1")
        await client.expire("bench:act:q", 3600)
        await client.set_raw("bench:act:last", "now", ttl=3600)

    async def activity_pipelined():
        await client.record_activity_pipeline(
            member="u1",
            set_ops=[("bench:act:d", 3600), ("bench:act:m", 3600), ("bench:act:q", 3600)],
            last_activity_key="bench:act:last",
            last_activity_value="now",
            last_activity_ttl=3600,
        )

    print("Activity tracking (per authenticated request):")
    old = await _timed("7 sequential awaits (old shape)", activity_sequential)
    new = await _timed("record_activity_pipeline (1 round trip)", activity_pipelined)
    print(f"  -> {old / new:.1f}x faster\n")

    # --- Snapshot/permission version validation: GETs vs MGET ----------------
    version_keys = [f"bench:ver:{scope}" for scope in ("global", "user", "entity")]
    for key in version_keys:
        await client.set_raw(key, "3")

    async def versions_sequential():
        for key in version_keys:
            await client.get_raw(key)

    async def versions_mget():
        await client.mget_raw(version_keys)

    print("Version validation (per API-key / permission cache read):")
    old = await _timed("3 sequential GETs (old shape)", versions_sequential)
    new = await _timed("1 MGET", versions_mget)
    print(f"  -> {old / new:.1f}x faster\n")

    # --- Rate-limit window: non-atomic INCR+EXPIRE vs atomic pipeline --------
    async def window_old_shape():
        value = await raw.incrby("bench:win:old", 1)
        if value == 1:
            await raw.expire("bench:win:old", 60)

    async def window_atomic():
        await client.increment_with_ttl("bench:win:new", amount=1, ttl=60)

    print("Rate-limit window increment:")
    old = await _timed("INCR then conditional EXPIRE (old, non-atomic)", window_old_shape)
    new = await _timed("SET NX EX + INCRBY pipeline (atomic)", window_atomic)
    print(f"  -> {old / new:.1f}x ({'faster' if old > new else 'slower'}; atomicity is the point)\n")

    # --- Invalidation fan-out: per-user INCR+PUBLISH vs one pipeline ----------
    user_ids = [f"user-{i}" for i in range(FANOUT_USERS)]
    fanout_keys = [f"bench:fan:{uid}" for uid in user_ids]
    messages = [f"permissions:user:{uid}" for uid in user_ids]

    async def fanout_sequential():
        for key, message in zip(fanout_keys, messages):
            await raw.incrby(key, 1)
            await raw.publish("bench:chan", message)

    async def fanout_pipelined():
        await client.bump_versions_and_publish(
            version_keys=fanout_keys,
            channel="bench:chan",
            messages=messages,
        )

    print(f"Invalidation fan-out ({FANOUT_USERS} users, e.g. role edit):")
    old = await _timed(f"{2 * FANOUT_USERS} sequential ops (old shape)", fanout_sequential, iterations=50)
    new = await _timed("bump_versions_and_publish (1 round trip)", fanout_pipelined, iterations=50)
    print(f"  -> {old / new:.1f}x faster\n")

    # Cleanup
    await raw.delete(
        "bench:act:d",
        "bench:act:m",
        "bench:act:q",
        "bench:act:last",
        "bench:win:old",
        "bench:win:new",
        *version_keys,
        *fanout_keys,
    )
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
