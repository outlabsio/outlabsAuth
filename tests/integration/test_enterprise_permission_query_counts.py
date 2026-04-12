import pytest
import pytest_asyncio

from outlabs_auth import EnterpriseRBAC
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
async def seeded_permission_context(auth_instance: EnterpriseRBAC) -> EnterpriseQueryBudgetContext:
    return await seed_enterprise_query_budget_context(auth_instance)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_permission_checks_stay_within_query_budgets(
    auth_instance: EnterpriseRBAC,
    query_counter: QueryCounter,
    seeded_permission_context: EnterpriseQueryBudgetContext,
) -> None:
    cases = [
        (
            "global_no_entity",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_permission_context.benchmark_user_id,
                permission=seeded_permission_context.permission_global_name,
            ),
            8,
        ),
        (
            "entity_direct",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_permission_context.benchmark_user_id,
                permission=seeded_permission_context.permission_entity_name,
                entity_id=seeded_permission_context.team_id,
            ),
            8,
        ),
        (
            "entity_from_ancestor_tree",
            lambda session: auth_instance.permission_service.check_permission(
                session,
                user_id=seeded_permission_context.benchmark_user_id,
                permission=seeded_permission_context.permission_tree_check_name,
                entity_id=seeded_permission_context.team_id,
            ),
            8,
        ),
        (
            "get_user_permissions",
            lambda session: auth_instance.permission_service.get_user_permissions(
                session,
                user_id=seeded_permission_context.benchmark_user_id,
            ),
            7,
        ),
    ]

    for name, operation, max_queries in cases:
        query_counter.reset()
        async with auth_instance.get_session() as session:
            query_counter.enabled = True
            result = await operation(session)
            query_counter.enabled = False

        assert result, f"{name} returned an unexpected falsy result"
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )
