"""
SimpleRBAC permission query-count budgets.

Mirrors tests/integration/test_enterprise_permission_query_counts.py for the
flat SimpleRBAC path (no entity hierarchy). Keeps regression pressure on the
hot permission check path specifically for the simple preset, since the
Enterprise test exercises additional codepaths that may hide simple-case wins
(or regressions).
"""

import pytest
import pytest_asyncio

from outlabs_auth import SimpleRBAC
from tests.integration.query_budget_support import (
    QueryCounter,
    SimpleQueryBudgetContext,
    attach_query_counter,
    seed_simple_query_budget_context,
)


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def query_counter(auth_instance: SimpleRBAC):
    counter, cleanup = attach_query_counter(auth_instance.engine)
    yield counter
    cleanup()


@pytest_asyncio.fixture
async def seeded_simple_context(auth_instance: SimpleRBAC) -> SimpleQueryBudgetContext:
    return await seed_simple_query_budget_context(auth_instance)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_permission_checks_stay_within_query_budgets(
    auth_instance: SimpleRBAC,
    query_counter: QueryCounter,
    seeded_simple_context: SimpleQueryBudgetContext,
) -> None:
    cases = [
        (
            "check_permission_granted",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_simple_context.benchmark_user_id,
                permission=seeded_simple_context.permission_granted_name,
            ),
            True,
            5,
        ),
        (
            "check_permission_denied",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_simple_context.benchmark_user_id,
                permission=seeded_simple_context.permission_missing_name,
            ),
            False,
            5,
        ),
        (
            "check_permission_superuser",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_simple_context.admin_user_id,
                permission=seeded_simple_context.permission_missing_name,
            ),
            True,
            1,
        ),
        (
            "get_user_permissions",
            lambda session: auth_instance.permission_service.get_user_permissions(
                session,
                user_id=seeded_simple_context.benchmark_user_id,
            ),
            None,  # truthy check — non-empty list
            5,
        ),
    ]

    failures: list[str] = []
    for name, operation, expected, max_queries in cases:
        query_counter.reset()
        async with auth_instance.get_session() as session:
            query_counter.enabled = True
            result = await operation(session)
            query_counter.enabled = False

        if expected is True:
            assert result is True, f"{name} expected True, got {result!r}"
        elif expected is False:
            assert result is False, f"{name} expected False, got {result!r}"
        else:
            assert result, f"{name} returned unexpected falsy result"

        if query_counter.count > max_queries:
            failures.append(
                f"{name}: {query_counter.count} > {max_queries} (db_ms={query_counter.db_ms:.1f})"
            )

    assert not failures, "Query budgets exceeded:\n" + "\n".join(failures)
