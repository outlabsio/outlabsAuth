"""
Warm-cache hot-path budgets (perf audit Phases 1-2).

With Redis caching enabled, the per-request permission paths must serve from
cache — ZERO SQL on a warm aggregated-permission read and on warm boolean
checks — and a permission-affecting mutation must take effect on the very next
read (versioned-key invalidation), not after a TTL.

These run against real Postgres + real Redis via the ``auth_with_cache``
fixture (skipped when Redis is unreachable). Latency summaries print with
``pytest -s`` so the file doubles as the hot-path benchmark:

    TEST_REDIS_URL=... uv run pytest tests/integration/test_cached_hotpath_budgets.py -s
"""

import pytest
import pytest_asyncio

from outlabs_auth.models.sql.user import User
from outlabs_auth.services import request_cache
from tests.integration.query_budget_support import (
    SimpleQueryBudgetContext,
    attach_query_counter,
    benchmark_operation,
    seed_simple_query_budget_context,
)


@pytest_asyncio.fixture
async def query_counter(auth_with_cache):
    counter, cleanup = attach_query_counter(auth_with_cache.engine)
    yield counter
    cleanup()


@pytest_asyncio.fixture
async def seeded(auth_with_cache) -> SimpleQueryBudgetContext:
    return await seed_simple_query_budget_context(auth_with_cache)


async def _detached_user(auth_instance, user_id) -> User:
    """Fetch the user once, as the auth dependency layer does before checks."""
    async with auth_instance.get_session() as session:
        user = await session.get(User, user_id)
    assert user is not None
    return user


@pytest.mark.integration
@pytest.mark.asyncio
async def test_warm_user_permission_aggregation_is_sql_free(auth_with_cache, query_counter, seeded) -> None:
    """The JWT fast path's aggregation must cost 0 SQL once the cache is warm."""
    service = auth_with_cache.permission_service
    user = await _detached_user(auth_with_cache, seeded.benchmark_user_id)

    async def aggregate():
        # Each iteration simulates a fresh request: without the reset the
        # request-scoped memo (Phase 3) would make this SQL-free on its own,
        # and the assertion would no longer prove the REDIS cache works.
        request_cache.reset()
        async with auth_with_cache.get_session() as session:
            return await service.get_user_permissions(
                session,
                seeded.benchmark_user_id,
                include_entity_local=False,
                user=user,
            )

    cold = await benchmark_operation(query_counter, aggregate, iterations=1, warmup=0)
    assert cold.query_count_max > 0, "cold pass should hit Postgres"

    warm = await benchmark_operation(query_counter, aggregate, iterations=20, warmup=1)
    assert warm.query_count_max == 0, (
        f"warm get_user_permissions must be SQL-free, saw {warm.query_count_max} queries " f"({warm.summary()})"
    )

    names = set(await aggregate())
    assert seeded.permission_granted_name in names
    assert seeded.permission_missing_name not in names

    print(f"\n[bench] get_user_permissions cold:  {cold.summary()}")
    print(f"[bench] get_user_permissions warm:  {warm.summary()}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_warm_boolean_permission_checks_are_sql_free(auth_with_cache, query_counter, seeded) -> None:
    service = auth_with_cache.permission_service
    user = await _detached_user(auth_with_cache, seeded.benchmark_user_id)

    def make_check(permission: str):
        async def check():
            request_cache.reset()  # simulate a fresh request per iteration
            async with auth_with_cache.get_session() as session:
                return await service.check_permission(
                    session,
                    user_id=seeded.benchmark_user_id,
                    permission=permission,
                    user=user,
                )

        return check

    check_granted = make_check(seeded.permission_granted_name)
    check_denied = make_check(seeded.permission_missing_name)

    assert await check_granted() is True  # cold — populates the verdict cache
    assert await check_denied() is False  # negative verdicts cache too

    warm_granted = await benchmark_operation(query_counter, check_granted, iterations=20, warmup=1)
    warm_denied = await benchmark_operation(query_counter, check_denied, iterations=20, warmup=1)
    assert warm_granted.query_count_max == 0, warm_granted.summary()
    assert warm_denied.query_count_max == 0, warm_denied.summary()
    assert await check_granted() is True
    assert await check_denied() is False

    print(f"\n[bench] check_permission warm granted: {warm_granted.summary()}")
    print(f"[bench] check_permission warm denied:  {warm_denied.summary()}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_mutations_invalidate_cached_permissions_immediately(auth_with_cache, seeded) -> None:
    """Versioned-key invalidation: grants and revocations apply on the next read.

    This is the safety contract that makes the warm-path caching above
    acceptable — a revoked permission must never be served from cache.
    """
    service = auth_with_cache.permission_service
    user = await _detached_user(auth_with_cache, seeded.benchmark_user_id)

    async def aggregated() -> set[str]:
        request_cache.reset()  # each read simulates a separate request
        async with auth_with_cache.get_session() as session:
            return set(
                await service.get_user_permissions(
                    session,
                    seeded.benchmark_user_id,
                    include_entity_local=False,
                    user=user,
                )
            )

    async def verdict() -> bool:
        request_cache.reset()  # each read simulates a separate request
        async with auth_with_cache.get_session() as session:
            return await service.check_permission(
                session,
                user_id=seeded.benchmark_user_id,
                permission=seeded.permission_missing_name,
                user=user,
            )

    # Warm both cache families with the pre-mutation state.
    assert seeded.permission_missing_name not in await aggregated()
    assert await verdict() is False

    # Grant: create a role carrying the previously-missing permission.
    async with auth_with_cache.get_session() as session:
        role = await auth_with_cache.role_service.create_role(
            session=session,
            name="cache-invalidation-role",
            display_name="Cache Invalidation Role",
            permission_names=[seeded.permission_missing_name],
            is_global=True,
        )
        await auth_with_cache.role_service.assign_role_to_user(
            session=session,
            user_id=seeded.benchmark_user_id,
            role_id=role.id,
        )
        await session.commit()

    assert seeded.permission_missing_name in await aggregated()
    assert await verdict() is True

    # Revoke: the cached ALLOW must die with the assignment.
    async with auth_with_cache.get_session() as session:
        await auth_with_cache.role_service.revoke_role_from_user(
            session=session,
            user_id=seeded.benchmark_user_id,
            role_id=role.id,
        )
        await session.commit()

    assert seeded.permission_missing_name not in await aggregated()
    assert await verdict() is False
