#!/usr/bin/env python3
"""Benchmark hot auth paths against OutlabsAuth's own SimpleRBAC/EnterpriseRBAC fixtures."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from starlette.requests import Request

from outlabs_auth import EnterpriseRBAC, SimpleRBAC
from tests.integration.query_budget_support import (
    attach_query_counter,
    seed_enterprise_admin_api_key_query_context,
    seed_enterprise_query_budget_context,
)


DEFAULT_DATABASE_URL = os.getenv(
    "AUTH_BENCH_DATABASE_URL",
    os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test",
    ),
)
DEFAULT_REDIS_URL = os.getenv("AUTH_BENCH_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
SECRET_KEY = "benchmark-secret-key-do-not-use-in-production-12345678"


@dataclass(frozen=True, slots=True)
class RedisMode:
    name: str
    redis_url: str | None
    enable_caching: bool


@dataclass(frozen=True, slots=True)
class SimpleBenchContext:
    user_api_key: str
    permission_name: str
    service_token: str


@dataclass(frozen=True, slots=True)
class Scenario:
    preset: str
    name: str
    auth_kind: str
    operation: Callable[[], Awaitable[bool]]
    notes: str = ""


@dataclass(slots=True)
class BenchmarkResult:
    preset: str
    redis_mode: str
    scenario: str
    auth_kind: str
    redis_requested: bool
    redis_available: bool
    enable_caching: bool
    commit_usage: bool
    iterations: int
    concurrency: int
    failures: int
    queries_total: int
    queries_per_request: float
    db_ms_total: float
    db_ms_per_request: float
    median_ms: float
    p95_ms: float
    total_ms: float
    notes: str


@dataclass(slots=True)
class BenchmarkDatabase:
    schema_name: str
    admin_engine: AsyncEngine
    engine: AsyncEngine

    async def drop(self) -> None:
        await self.engine.dispose()
        async with self.admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{self.schema_name}" CASCADE'))
        await self.admin_engine.dispose()


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def local_url_host(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.hostname


def assert_local_url(url: str, *, kind: str, allow_nonlocal: bool) -> None:
    if allow_nonlocal:
        return
    host = local_url_host(url)
    if host in {None, "", "localhost", "127.0.0.1", "::1"}:
        return
    if host.endswith(".localhost"):
        return
    raise SystemExit(
        f"Refusing to benchmark against non-local {kind} host {host!r}. "
        f"Pass --allow-nonlocal-{kind} only when you are intentionally targeting a disposable environment."
    )


async def create_benchmark_database(args: argparse.Namespace) -> BenchmarkDatabase:
    schema_name = f"bench_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(
        args.database_url,
        echo=args.echo_sql,
        pool_pre_ping=True,
    )
    engine = create_async_engine(
        args.database_url,
        echo=args.echo_sql,
        pool_pre_ping=True,
        pool_size=args.db_pool_size,
        max_overflow=args.db_max_overflow,
        connect_args={"server_settings": {"search_path": f"{schema_name},public"}},
    )

    async with admin_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    return BenchmarkDatabase(schema_name=schema_name, admin_engine=admin_engine, engine=engine)


def redis_modes(args: argparse.Namespace) -> list[RedisMode]:
    modes = []
    for mode_name in parse_csv(args.redis_modes):
        if mode_name == "off":
            modes.append(RedisMode(name="off", redis_url=None, enable_caching=False))
        elif mode_name == "counters":
            modes.append(RedisMode(name="counters", redis_url=args.redis_url, enable_caching=False))
        elif mode_name == "cache":
            modes.append(RedisMode(name="cache", redis_url=args.redis_url, enable_caching=True))
        else:
            raise SystemExit(f"Unknown Redis mode {mode_name!r}. Use off,counters,cache.")
    return modes


async def build_auth(
    preset: str,
    engine: AsyncEngine,
    redis_mode: RedisMode,
) -> SimpleRBAC | EnterpriseRBAC:
    kwargs: dict[str, Any] = {
        "engine": engine,
        "secret_key": SECRET_KEY,
        "access_token_expire_minutes": 60,
        "enable_token_cleanup": False,
        "redis_url": redis_mode.redis_url,
        "enable_caching": redis_mode.enable_caching,
    }
    if preset == "simple":
        auth: SimpleRBAC | EnterpriseRBAC = SimpleRBAC(**kwargs)
    elif preset == "enterprise":
        auth = EnterpriseRBAC(
            **kwargs,
            enable_context_aware_roles=True,
            enable_abac=False,
        )
    else:
        raise SystemExit(f"Unknown preset {preset!r}. Use simple,enterprise.")
    await auth.initialize()
    return auth


def redis_available(auth: SimpleRBAC | EnterpriseRBAC) -> bool:
    redis_client = getattr(auth, "redis_client", None)
    return bool(redis_client is not None and redis_client.is_available)


async def seed_simple_context(
    auth: SimpleRBAC,
    *,
    extra_roles: int,
    extra_users: int,
) -> SimpleBenchContext:
    unique = uuid.uuid4().hex[:8]
    permission_name = f"bench{unique}:read"

    async with auth.get_session() as session:
        user = await auth.user_service.create_user(
            session=session,
            email=f"bench-simple-{unique}@example.com",
            password="TestPass123!",
            first_name="Bench",
            last_name="Simple",
        )
        await auth.permission_service.create_permission(
            session=session,
            name=permission_name,
            display_name=permission_name,
            is_system=True,
        )
        role = await auth.role_service.create_role(
            session=session,
            name=f"bench-simple-read-{unique}",
            display_name="Bench Simple Read",
            permission_names=[permission_name],
            is_global=True,
        )
        await auth.role_service.assign_role_to_user(
            session=session,
            user_id=user.id,
            role_id=role.id,
            assigned_by_id=user.id,
        )

        for index in range(extra_roles):
            extra_permission_name = f"bench{unique}:noise{index}"
            await auth.permission_service.create_permission(
                session=session,
                name=extra_permission_name,
                display_name=extra_permission_name,
                is_system=True,
            )
            extra_role = await auth.role_service.create_role(
                session=session,
                name=f"bench-simple-noise-{index}-{unique}",
                display_name=f"Bench Simple Noise {index}",
                permission_names=[extra_permission_name],
                is_global=True,
            )
            await auth.role_service.assign_role_to_user(
                session=session,
                user_id=user.id,
                role_id=extra_role.id,
                assigned_by_id=user.id,
            )

        for index in range(extra_users):
            await auth.user_service.create_user(
                session=session,
                email=f"bench-simple-extra-{index}-{unique}@example.com",
                password="TestPass123!",
                first_name=f"Extra{index}",
                last_name="Simple",
            )

        user_api_key, _ = await auth.api_key_service.create_api_key(
            session=session,
            owner_id=user.id,
            name="Bench Simple User Key",
            scopes=[permission_name],
            actor_user_id=user.id,
            rate_limit_per_minute=0,
        )
        await session.commit()

    service_token = auth.service_token_service.create_service_token(
        service_id=f"bench-simple-service-{unique}",
        service_name="Bench Simple Service",
        permissions=[permission_name],
        expires_days=1,
    )
    return SimpleBenchContext(
        user_api_key=user_api_key,
        permission_name=permission_name,
        service_token=service_token,
    )


def api_key_operation(
    auth: SimpleRBAC | EnterpriseRBAC,
    *,
    api_key: str,
    required_scope: str,
    entity_id: uuid.UUID | None = None,
    commit_usage: bool,
) -> Callable[[], Awaitable[bool]]:
    async def run() -> bool:
        async with auth.get_session() as session:
            result = await auth.authorize_api_key(
                session,
                api_key,
                required_scope=required_scope,
                entity_id=entity_id,
            )
            if commit_usage:
                await session.commit()
            return result is not None

    return run


def make_benchmark_request(*, api_key: str, path: str = "/bench/auth") -> Request:
    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "path_params": {},
            "query_string": b"",
            "headers": [(b"x-api-key", api_key.encode("utf-8"))],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        },
        receive,
    )


def api_key_dependency_operation(
    auth: SimpleRBAC | EnterpriseRBAC,
    *,
    api_key: str,
    required_scope: str,
    commit_usage: bool,
) -> Callable[[], Awaitable[bool]]:
    dependency = auth.deps.require_permission(required_scope)

    async def run() -> bool:
        async with auth.get_session() as session:
            result = await dependency(
                request=make_benchmark_request(api_key=api_key),
                session=session,
            )
            if commit_usage:
                await session.commit()
            return result is not None

    return run


def service_token_operation(
    auth: SimpleRBAC | EnterpriseRBAC,
    *,
    service_token: str,
    required_scope: str,
) -> Callable[[], Awaitable[bool]]:
    async def run() -> bool:
        payload = auth.service_token_service.validate_service_token(service_token)
        return bool(auth.service_token_service.check_service_permission(payload, required_scope))

    return run


async def build_scenarios(
    auth: SimpleRBAC | EnterpriseRBAC,
    preset: str,
    args: argparse.Namespace,
) -> list[Scenario]:
    scenarios: list[Scenario] = []
    service_token = auth.service_token_service.create_service_token(
        service_id=f"bench-{preset}-service-{uuid.uuid4().hex[:8]}",
        service_name=f"Bench {preset.title()} Service",
        permissions=["bench:read"],
        expires_days=1,
    )

    scenarios.append(
        Scenario(
            preset=preset,
            name=f"{preset}_service_token_permission",
            auth_kind="service_token",
            operation=service_token_operation(
                auth,
                service_token=service_token,
                required_scope="bench:read",
            ),
            notes="stateless service-token validation",
        )
    )

    if preset == "simple":
        simple_auth = auth
        simple_context = await seed_simple_context(
            simple_auth,
            extra_roles=args.extra_simple_roles,
            extra_users=args.extra_simple_users,
        )
        scenarios.append(
            Scenario(
                preset="simple",
                name="simple_user_api_key_global",
                auth_kind="user_api_key",
                operation=api_key_operation(
                    simple_auth,
                    api_key=simple_context.user_api_key,
                    required_scope=simple_context.permission_name,
                    commit_usage=args.commit_usage,
                ),
                notes=f"extra_roles={args.extra_simple_roles}, extra_users={args.extra_simple_users}",
            )
        )
        scenarios.append(
            Scenario(
                preset="simple",
                name="simple_user_api_key_dependency_global",
                auth_kind="user_api_key_dependency",
                operation=api_key_dependency_operation(
                    simple_auth,
                    api_key=simple_context.user_api_key,
                    required_scope=simple_context.permission_name,
                    commit_usage=args.commit_usage,
                ),
                notes="FastAPI require_permission path used by worker routes",
            )
        )
        scenarios.append(
            Scenario(
                preset="simple",
                name="simple_seeded_service_token_permission",
                auth_kind="service_token",
                operation=service_token_operation(
                    simple_auth,
                    service_token=simple_context.service_token,
                    required_scope=simple_context.permission_name,
                ),
                notes="service token using simple seed permission",
            )
        )
        return scenarios

    enterprise_auth = auth
    user_context = await seed_enterprise_query_budget_context(enterprise_auth)
    admin_context = await seed_enterprise_admin_api_key_query_context(enterprise_auth)
    scenarios.extend(
        [
            Scenario(
                preset="enterprise",
                name="enterprise_personal_api_key_unanchored",
                auth_kind="user_api_key",
                operation=api_key_operation(
                    enterprise_auth,
                    api_key=user_context.unanchored_api_key,
                    required_scope=user_context.api_key_global_scope,
                    commit_usage=args.commit_usage,
                ),
                notes="enterprise query-budget seed, global personal key",
            ),
            Scenario(
                preset="enterprise",
                name="enterprise_personal_api_key_dependency_unanchored",
                auth_kind="user_api_key_dependency",
                operation=api_key_dependency_operation(
                    enterprise_auth,
                    api_key=user_context.unanchored_api_key,
                    required_scope=user_context.api_key_global_scope,
                    commit_usage=args.commit_usage,
                ),
                notes="FastAPI require_permission path, global personal key",
            ),
            Scenario(
                preset="enterprise",
                name="enterprise_personal_api_key_anchored_tree",
                auth_kind="user_api_key",
                operation=api_key_operation(
                    enterprise_auth,
                    api_key=user_context.anchored_api_key,
                    required_scope=user_context.api_key_entity_scope,
                    entity_id=user_context.team_id,
                    commit_usage=args.commit_usage,
                ),
                notes="enterprise query-budget seed, descendant entity access",
            ),
            Scenario(
                preset="enterprise",
                name="enterprise_system_api_key_global",
                auth_kind="system_api_key",
                operation=api_key_operation(
                    enterprise_auth,
                    api_key=admin_context.system_global_api_key,
                    required_scope=admin_context.system_global_scope,
                    commit_usage=args.commit_usage,
                ),
                notes="platform-global integration principal",
            ),
            Scenario(
                preset="enterprise",
                name="enterprise_system_api_key_entity_tree",
                auth_kind="system_api_key",
                operation=api_key_operation(
                    enterprise_auth,
                    api_key=admin_context.entity_system_api_key,
                    required_scope=admin_context.entity_system_scope_check_name,
                    entity_id=admin_context.team_id,
                    commit_usage=args.commit_usage,
                ),
                notes="entity-scoped integration principal, descendant entity access",
            ),
        ]
    )
    return scenarios


async def run_timed(operation: Callable[[], Awaitable[bool]]) -> tuple[bool, float]:
    start = time.perf_counter()
    try:
        ok = await operation()
    except Exception:
        ok = False
    return ok, (time.perf_counter() - start) * 1000


async def run_operation_many(
    operation: Callable[[], Awaitable[bool]],
    *,
    iterations: int,
    concurrency: int,
) -> tuple[list[float], int]:
    semaphore = asyncio.Semaphore(concurrency)
    timings: list[float] = []
    failures = 0

    async def run_one() -> None:
        nonlocal failures
        async with semaphore:
            ok, elapsed_ms = await run_timed(operation)
            timings.append(elapsed_ms)
            if not ok:
                failures += 1

    await asyncio.gather(*(run_one() for _ in range(iterations)))
    return timings, failures


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) * pct) + 0.999999) - 1))
    return ordered[index]


async def benchmark_scenario(
    scenario: Scenario,
    *,
    auth: SimpleRBAC | EnterpriseRBAC,
    redis_mode: RedisMode,
    args: argparse.Namespace,
) -> BenchmarkResult:
    for _ in range(args.warmup):
        await scenario.operation()

    counter, cleanup = attach_query_counter(auth.engine)
    try:
        counter.reset()
        counter.enabled = True
        start = time.perf_counter()
        timings, failures = await run_operation_many(
            scenario.operation,
            iterations=args.iterations,
            concurrency=args.concurrency,
        )
        total_ms = (time.perf_counter() - start) * 1000
        counter.enabled = False
    finally:
        counter.enabled = False
        cleanup()

    return BenchmarkResult(
        preset=scenario.preset,
        redis_mode=redis_mode.name,
        scenario=scenario.name,
        auth_kind=scenario.auth_kind,
        redis_requested=redis_mode.redis_url is not None,
        redis_available=redis_available(auth),
        enable_caching=redis_mode.enable_caching,
        commit_usage=args.commit_usage,
        iterations=args.iterations,
        concurrency=args.concurrency,
        failures=failures,
        queries_total=counter.count,
        queries_per_request=counter.count / args.iterations if args.iterations else 0.0,
        db_ms_total=counter.db_ms,
        db_ms_per_request=counter.db_ms / args.iterations if args.iterations else 0.0,
        median_ms=percentile(timings, 0.50),
        p95_ms=percentile(timings, 0.95),
        total_ms=total_ms,
        notes=scenario.notes,
    )


async def run_suite(args: argparse.Namespace) -> list[BenchmarkResult]:
    assert_local_url(args.database_url, kind="db", allow_nonlocal=args.allow_nonlocal_db)
    if args.redis_url:
        assert_local_url(args.redis_url, kind="redis", allow_nonlocal=args.allow_nonlocal_redis)

    results: list[BenchmarkResult] = []
    for redis_mode in redis_modes(args):
        for preset in parse_csv(args.presets):
            bench_db = await create_benchmark_database(args)
            auth: SimpleRBAC | EnterpriseRBAC | None = None
            try:
                auth = await build_auth(preset, bench_db.engine, redis_mode)
                scenarios = await build_scenarios(auth, preset, args)
                for scenario in scenarios:
                    if not args.include_service_tokens and scenario.auth_kind == "service_token":
                        continue
                    results.append(
                        await benchmark_scenario(
                            scenario,
                            auth=auth,
                            redis_mode=redis_mode,
                            args=args,
                        )
                    )
            finally:
                if auth is not None:
                    await auth.shutdown()
                await bench_db.drop()
    return results


def print_markdown(results: list[BenchmarkResult]) -> None:
    print(
        "| preset | redis | scenario | auth | ok | q/req | db ms/req | median ms | p95 ms | redis ok | cache | notes |"
    )
    print("|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|")
    for result in results:
        ok_count = result.iterations - result.failures
        print(
            "| "
            f"{result.preset} | "
            f"{result.redis_mode} | "
            f"{result.scenario} | "
            f"{result.auth_kind} | "
            f"{ok_count}/{result.iterations} | "
            f"{result.queries_per_request:.2f} | "
            f"{result.db_ms_per_request:.2f} | "
            f"{result.median_ms:.2f} | "
            f"{result.p95_ms:.2f} | "
            f"{'yes' if result.redis_available else 'no'} | "
            f"{'yes' if result.enable_caching else 'no'} | "
            f"{result.notes} |"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run local OutlabsAuth auth-path benchmarks using isolated schemas and SimpleRBAC/EnterpriseRBAC seeds."
        )
    )
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--redis-url", default=DEFAULT_REDIS_URL)
    parser.add_argument("--redis-modes", default="off,counters,cache", help="Comma list: off,counters,cache")
    parser.add_argument("--presets", default="simple,enterprise", help="Comma list: simple,enterprise")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--db-pool-size", type=int, default=10)
    parser.add_argument("--db-max-overflow", type=int, default=10)
    parser.add_argument("--extra-simple-roles", type=int, default=0)
    parser.add_argument("--extra-simple-users", type=int, default=0)
    parser.add_argument("--commit-usage", action="store_true")
    parser.add_argument("--include-service-tokens", action="store_true", default=True)
    parser.add_argument("--no-service-tokens", dest="include_service_tokens", action="store_false")
    parser.add_argument("--allow-nonlocal-db", action="store_true")
    parser.add_argument("--allow-nonlocal-redis", action="store_true")
    parser.add_argument("--echo-sql", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a markdown table")
    return parser


async def async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.iterations < 1:
        raise SystemExit("--iterations must be >= 1")
    if args.warmup < 0:
        raise SystemExit("--warmup must be >= 0")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")

    results = await run_suite(args)
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        print_markdown(results)
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
