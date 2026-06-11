"""
Request-scoped memoization budgets (perf audit Phase 3).

Multi-permission routes (``require_permission("a", "b", ...)``, dependency
stacks) re-enter the permission service once per name within one request.
Phase 3 memoizes the membership graph per request, so every check after the
first must be SQL-free — previously each one re-paid the full eager-load
chain (~10 queries per extra permission on an entity route).

No Redis here: this isolates the request-level memo from the Redis caches.
"""

import pytest
import pytest_asyncio

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.services import request_cache
from tests.integration.query_budget_support import (
    EnterpriseQueryBudgetContext,
    QueryCounter,
    attach_query_counter,
    seed_enterprise_query_budget_context,
)


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def query_counter(auth_instance: EnterpriseRBAC):
    counter, cleanup = attach_query_counter(auth_instance.engine)
    yield counter
    cleanup()


@pytest_asyncio.fixture
async def seeded(auth_instance: EnterpriseRBAC) -> EnterpriseQueryBudgetContext:
    return await seed_enterprise_query_budget_context(auth_instance)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_additional_permission_checks_in_same_request_are_sql_free(
    auth_instance: EnterpriseRBAC,
    query_counter: QueryCounter,
    seeded: EnterpriseQueryBudgetContext,
) -> None:
    service = auth_instance.permission_service
    request_cache.reset()  # fresh "request"

    async with auth_instance.get_session() as session:
        # The first check of each aggregation shape pays its own load: the
        # global shape (entity_id=None) and the entity-context shape use
        # different eager-load options, so they memoize under different keys.
        query_counter.reset()
        query_counter.enabled = True
        first_global = await service.check_permission(
            session,
            user_id=seeded.benchmark_user_id,
            permission=seeded.permission_global_name,
        )
        query_counter.enabled = False
        assert first_global is True
        assert query_counter.count > 0

        query_counter.reset()
        query_counter.enabled = True
        first_entity = await service.check_permission(
            session,
            user_id=seeded.benchmark_user_id,
            permission=seeded.permission_entity_name,
            entity_id=seeded.team_id,
        )
        query_counter.enabled = False
        assert first_entity is True
        assert query_counter.count > 0

        # Every further check in the same request — different permission,
        # granted or denied, either shape — reuses the memoized graph.
        followups = [
            (seeded.permission_global_name, seeded.team_id, True),
            (seeded.permission_tree_check_name, seeded.team_id, True),
            ("definitely:not_granted", seeded.team_id, False),
            (seeded.permission_global_name, None, True),
            ("definitely:not_granted", None, False),
        ]
        for permission, entity_id, expected in followups:
            query_counter.reset()
            query_counter.enabled = True
            result = await service.check_permission(
                session,
                user_id=seeded.benchmark_user_id,
                permission=permission,
                entity_id=entity_id,
            )
            query_counter.enabled = False
            assert result is expected, permission
            assert query_counter.count == 0, (
                f"follow-up check '{permission}' (entity={entity_id}) should be "
                f"SQL-free via the request memo, saw {query_counter.count} queries"
            )

    request_cache.reset()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_boundary_resets_the_memo(
    auth_instance: EnterpriseRBAC,
    query_counter: QueryCounter,
    seeded: EnterpriseQueryBudgetContext,
) -> None:
    """A new request (cache reset) must re-read from the database."""
    service = auth_instance.permission_service

    async def one_request_check() -> int:
        request_cache.reset()
        async with auth_instance.get_session() as session:
            query_counter.reset()
            query_counter.enabled = True
            result = await service.check_permission(
                session,
                user_id=seeded.benchmark_user_id,
                permission=seeded.permission_entity_name,
                entity_id=seeded.team_id,
            )
            query_counter.enabled = False
            assert result is True
            return query_counter.count

    first = await one_request_check()
    second = await one_request_check()
    assert first > 0
    assert second > 0, "memo must not leak across simulated request boundaries"
    request_cache.reset()
