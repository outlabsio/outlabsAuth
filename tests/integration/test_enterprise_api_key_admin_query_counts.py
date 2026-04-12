import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import (
    get_api_key_admin_router,
    get_integration_principals_router,
)
from tests.integration.query_budget_support import (
    EnterpriseAdminApiKeyQueryContext,
    QueryCounter,
    attach_query_counter,
    seed_enterprise_admin_api_key_query_context,
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
    register_exception_handlers(application, debug=True)
    application.include_router(get_api_key_admin_router(auth_instance, prefix="/v1/admin/entities"))
    application.include_router(get_integration_principals_router(auth_instance, prefix="/v1/admin"))
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
async def admin_context(auth_instance: EnterpriseRBAC) -> EnterpriseAdminApiKeyQueryContext:
    return await seed_enterprise_admin_api_key_query_context(auth_instance)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_integration_api_key_authorization_stays_within_query_budgets(
    auth_instance: EnterpriseRBAC,
    query_counter: QueryCounter,
    admin_context: EnterpriseAdminApiKeyQueryContext,
) -> None:
    cases = [
        (
            "entity_system_key_descendant_access",
            lambda session: auth_instance.authorize_api_key(
                session,
                admin_context.entity_system_api_key,
                required_scope=admin_context.entity_system_scope_check_name,
                entity_id=admin_context.team_id,
            ),
            True,
            20,
        ),
        (
            "entity_system_key_denied_anchor_escape",
            lambda session: auth_instance.authorize_api_key(
                session,
                admin_context.entity_system_api_key,
                required_scope=admin_context.entity_system_scope_check_name,
                entity_id=admin_context.root_id,
            ),
            False,
            10,
        ),
        (
            "platform_global_system_key",
            lambda session: auth_instance.authorize_api_key(
                session,
                admin_context.system_global_api_key,
                required_scope=admin_context.system_global_scope,
            ),
            True,
            15,
        ),
    ]

    for name, operation, should_succeed, max_queries in cases:
        query_counter.reset()
        async with auth_instance.get_session() as session:
            query_counter.enabled = True
            result = await operation(session)
            query_counter.enabled = False

        if should_succeed:
            assert result is not None, f"{name} returned no auth result"
        else:
            assert result is None, f"{name} unexpectedly authorized"
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_admin_inventory_routes_stay_within_query_budgets(
    client: httpx.AsyncClient,
    query_counter: QueryCounter,
    admin_context: EnterpriseAdminApiKeyQueryContext,
) -> None:
    cases = [
        (
            "entity_api_key_inventory",
            f"/v1/admin/entities/{admin_context.department_id}/api-keys",
            {"key_kind": "system_integration"},
            admin_context.entity_admin_headers,
            16,
        ),
        (
            "entity_principal_api_keys",
            f"/v1/admin/entities/{admin_context.department_id}/integration-principals/{admin_context.entity_principal_id}/api-keys",
            None,
            admin_context.entity_admin_headers,
            18,
        ),
        (
            "system_principal_api_keys",
            f"/v1/admin/system/integration-principals/{admin_context.system_principal_id}/api-keys",
            None,
            admin_context.superuser_headers,
            18,
        ),
    ]

    for name, path, params, headers, max_queries in cases:
        query_counter.reset()
        query_counter.enabled = True
        response = await client.get(path, params=params, headers=headers)
        query_counter.enabled = False

        assert response.status_code == 200, f"{name} failed: {response.text}"
        assert response.json()["total"] == 1
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )
