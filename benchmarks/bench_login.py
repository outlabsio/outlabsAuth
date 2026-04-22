"""
Login performance benchmark.

Runs the full auth_service.login() flow against a real PostgreSQL database
and reports latency percentiles. Also times raw password verification in
isolation so we can attribute where the cost goes.

Usage:
    uv run python benchmarks/bench_login.py
    uv run python benchmarks/bench_login.py --iterations 50 --concurrency 10
"""

import argparse
import asyncio
import os
import statistics
import time
from typing import Callable, List

from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from outlabs_auth import SimpleRBAC
from outlabs_auth.observability import ObservabilityConfig
from outlabs_auth.utils.password import (
    hash_password,
    verify_and_upgrade_password,
    verify_password,
)


DEFAULT_DATABASE_URL = os.getenv(
    "BENCH_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/bench_login",
)
TEST_EMAIL = "bench@test.com"
TEST_PASSWORD = "BenchPass123!"


async def _ensure_database(database_url: str) -> None:
    url = make_url(database_url)
    db_name = url.database
    if not all(c.isalnum() or c == "_" for c in db_name):
        raise RuntimeError(f"Unsafe bench db name: {db_name!r}")

    admin_url = url.set(database="postgres")
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if exists.scalar_one_or_none() is not None:
                await conn.execute(text(f'DROP DATABASE "{db_name}"'))
            await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await admin_engine.dispose()


async def _drop_database(database_url: str) -> None:
    url = make_url(database_url)
    db_name = url.database
    admin_url = url.set(database="postgres")
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    finally:
        await admin_engine.dispose()


def _percentiles(samples_ms: List[float]) -> dict:
    sorted_samples = sorted(samples_ms)
    n = len(sorted_samples)

    def pct(p: float) -> float:
        if n == 0:
            return 0.0
        idx = min(int(round(p * (n - 1))), n - 1)
        return sorted_samples[idx]

    return {
        "count": n,
        "mean": statistics.mean(sorted_samples),
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "min": sorted_samples[0],
        "max": sorted_samples[-1],
    }


def _print_stats(name: str, samples_ms: List[float]) -> None:
    s = _percentiles(samples_ms)
    print(
        f"  {name:<30} "
        f"n={s['count']:<4} "
        f"mean={s['mean']:7.1f}ms  "
        f"p50={s['p50']:7.1f}ms  "
        f"p95={s['p95']:7.1f}ms  "
        f"p99={s['p99']:7.1f}ms  "
        f"min={s['min']:7.1f}ms  "
        f"max={s['max']:7.1f}ms"
    )


async def _time_serial(
    fn: Callable, iterations: int, warmup: int = 2
) -> List[float]:
    for _ in range(warmup):
        await fn()

    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


async def _time_concurrent(
    fn: Callable, concurrency: int, iterations: int
) -> List[float]:
    samples: List[float] = []

    async def one_call():
        t0 = time.perf_counter()
        await fn()
        samples.append((time.perf_counter() - t0) * 1000.0)

    remaining = iterations
    while remaining > 0:
        batch = min(concurrency, remaining)
        await asyncio.gather(*[one_call() for _ in range(batch)])
        remaining -= batch
    return samples


def _time_sync(fn: Callable, iterations: int, warmup: int = 2) -> List[float]:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


async def run_benchmarks(
    database_url: str, iterations: int, concurrency: int
) -> None:
    print(f"\n{'='*90}")
    print(f"  Login benchmark")
    print(f"  DB: {database_url}")
    print(f"  iterations={iterations} concurrency={concurrency}")
    print(f"{'='*90}\n")

    print("Setup: creating bench database...")
    await _ensure_database(database_url)

    obs = ObservabilityConfig(enabled=False, log_format="text", log_level="ERROR")
    auth = SimpleRBAC(
        database_url=database_url,
        secret_key="bench-secret-key-do-not-use-in-production-123456",
        enable_token_cleanup=False,
        observability_config=obs,
    )
    await auth.initialize()

    try:
        async with auth.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        async with auth.get_session() as session:
            user = await auth.user_service.create_user(
                session,
                email=TEST_EMAIL,
                password=TEST_PASSWORD,
                first_name="Bench",
                last_name="User",
            )
            await session.commit()
            stored_hash = user.hashed_password

        print("Setup: done.\n")

        # --- Microbench: just password hashing (isolated CPU work) ---
        print("[1/4] Pure password verify (no DB, no event loop)")
        verify_samples = _time_sync(
            lambda: verify_password(TEST_PASSWORD, stored_hash),
            iterations=iterations,
            warmup=2,
        )
        _print_stats("verify_password", verify_samples)

        print("\n[2/4] Pure password hash (registration cost)")
        hash_samples = _time_sync(
            lambda: hash_password(TEST_PASSWORD),
            iterations=min(iterations, 20),
            warmup=2,
        )
        _print_stats("hash_password", hash_samples)

        # --- Full login() serial ---
        print("\n[3/4] Full login() — serial (one at a time)")

        async def one_login():
            async with auth.get_session() as session:
                await auth.auth_service.login(
                    session,
                    email=TEST_EMAIL,
                    password=TEST_PASSWORD,
                    ip_address="127.0.0.1",
                    user_agent="bench/1.0",
                )
                await session.commit()

        login_serial = await _time_serial(one_login, iterations=iterations, warmup=2)
        _print_stats("login (serial)", login_serial)

        # --- Full login() concurrent ---
        print(
            f"\n[4/4] Full login() — concurrent (burst of {concurrency})"
        )
        login_concurrent = await _time_concurrent(
            one_login, concurrency=concurrency, iterations=iterations
        )
        _print_stats("login (concurrent)", login_concurrent)

        # --- Summary ---
        verify_median = _percentiles(verify_samples)["p50"]
        login_median = _percentiles(login_serial)["p50"]
        db_overhead = login_median - verify_median
        print(f"\n{'-'*90}")
        print(f"  Attribution (serial medians):")
        print(f"    password verify :  {verify_median:7.1f} ms")
        print(f"    rest of login   :  {db_overhead:7.1f} ms  (DB + token + audit)")
        print(f"    total login     :  {login_median:7.1f} ms")
        print(f"{'-'*90}\n")

    finally:
        await auth.shutdown()
        print("Cleanup: dropping bench database...")
        await _drop_database(database_url)
        print("Done.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    args = parser.parse_args()

    asyncio.run(
        run_benchmarks(
            database_url=args.database_url,
            iterations=args.iterations,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
