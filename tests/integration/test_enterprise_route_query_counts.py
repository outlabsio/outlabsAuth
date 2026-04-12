import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.routers import (
    get_entities_router,
    get_memberships_router,
    get_roles_router,
    get_users_router,
)
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
async def app(auth_instance: EnterpriseRBAC) -> FastAPI:
    application = FastAPI()
    application.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    application.include_router(get_entities_router(auth_instance, prefix="/v1/entities"))
    application.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
    application.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
        timeout=20.0,
    ) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def query_counter(auth_instance: EnterpriseRBAC):
    counter, cleanup = attach_query_counter(auth_instance.engine)
    yield counter
    cleanup()


@pytest_asyncio.fixture
async def seeded_context(auth_instance: EnterpriseRBAC) -> EnterpriseQueryBudgetContext:
    return await seed_enterprise_query_budget_context(auth_instance)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_admin_routes_stay_within_query_budgets(
    client: httpx.AsyncClient,
    query_counter: QueryCounter,
    seeded_context: EnterpriseQueryBudgetContext,
) -> None:
    cases = [
        ("users_me", "/v1/users/me", None, 1),
        ("memberships_me", "/v1/memberships/me", {"include_inactive": "true"}, 3),
        ("entity_get", f"/v1/entities/{seeded_context.root_id}", None, 2),
        (
            "users_list",
            "/v1/users/",
            {"page": "1", "limit": "100", "root_entity_id": str(seeded_context.root_id)},
            4,
        ),
        (
            "users_permissions",
            f"/v1/users/{seeded_context.permissions_target_user_id}/permissions",
            None,
            8,
        ),
        (
            "entity_members",
            f"/v1/entities/{seeded_context.department_id}/members",
            {"page": "1", "limit": "100"},
            5,
        ),
        ("entity_descendants", f"/v1/entities/{seeded_context.root_id}/descendants", None, 3),
        ("entity_path", f"/v1/entities/{seeded_context.department_id}/path", None, 3),
        (
            "roles_for_entity",
            f"/v1/roles/entity/{seeded_context.root_id}",
            {"page": "1", "limit": "100"},
            5,
        ),
    ]

    for name, path, params, max_queries in cases:
        query_counter.reset()
        query_counter.enabled = True
        response = await client.get(path, params=params, headers=seeded_context.admin_headers)
        query_counter.enabled = False

        assert response.status_code == 200, f"{name} failed: {response.text}"
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )
