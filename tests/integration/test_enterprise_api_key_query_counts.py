import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import get_api_keys_router
from tests.integration.query_budget_support import (
    ApiKeyMutationQueryContext,
    EnterpriseQueryBudgetContext,
    PersonalApiKeySelfServiceQueryContext,
    QueryCounter,
    attach_query_counter,
    seed_api_key_mutation_query_context,
    seed_enterprise_query_budget_context,
    seed_personal_api_key_self_service_query_context,
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
    application.include_router(get_api_keys_router(auth_instance, prefix="/v1/api-keys"))
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


@pytest_asyncio.fixture
async def self_service_context(
    auth_instance: EnterpriseRBAC,
) -> PersonalApiKeySelfServiceQueryContext:
    return await seed_personal_api_key_self_service_query_context(auth_instance)


@pytest_asyncio.fixture
async def mutation_context(auth_instance: EnterpriseRBAC) -> ApiKeyMutationQueryContext:
    return await seed_api_key_mutation_query_context(auth_instance)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_api_key_authorization_stays_within_query_budgets(
    auth_instance: EnterpriseRBAC,
    query_counter: QueryCounter,
    seeded_context: EnterpriseQueryBudgetContext,
) -> None:
    cases = [
        (
            "unanchored_global",
            lambda session: auth_instance.authorize_api_key(
                session,
                seeded_context.unanchored_api_key,
                required_scope=seeded_context.api_key_global_scope,
            ),
            True,
            24,
        ),
        (
            "anchored_tree",
            lambda session: auth_instance.authorize_api_key(
                session,
                seeded_context.anchored_api_key,
                required_scope=seeded_context.api_key_entity_scope,
                entity_id=seeded_context.team_id,
            ),
            True,
            30,
        ),
        (
            "denied_scope",
            lambda session: auth_instance.authorize_api_key(
                session,
                seeded_context.anchored_api_key,
                required_scope=seeded_context.api_key_denied_scope,
                entity_id=seeded_context.team_id,
            ),
            False,
            12,
        ),
        (
            "denied_entity_access",
            lambda session: auth_instance.authorize_api_key(
                session,
                seeded_context.anchored_api_key,
                required_scope=seeded_context.api_key_entity_scope,
                entity_id=seeded_context.root_id,
            ),
            False,
            10,
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
async def test_enterprise_api_key_routes_stay_within_query_budgets(
    client: httpx.AsyncClient,
    query_counter: QueryCounter,
    self_service_context: PersonalApiKeySelfServiceQueryContext,
) -> None:
    cases = [
        (
            "list_api_keys",
            "/v1/api-keys/",
            None,
            self_service_context.headers,
            24,
        ),
        (
            "grantable_scopes_unanchored",
            "/v1/api-keys/grantable-scopes",
            None,
            self_service_context.headers,
            10,
        ),
        (
            "grantable_scopes_anchored",
            "/v1/api-keys/grantable-scopes",
            {
                "entity_id": str(self_service_context.department_id),
                "inherit_from_tree": "true",
            },
            self_service_context.headers,
            13,
        ),
    ]

    for name, path, params, headers, max_queries in cases:
        query_counter.reset()
        query_counter.enabled = True
        response = await client.get(path, params=params, headers=headers)
        query_counter.enabled = False

        assert response.status_code == 200, f"{name} failed: {response.text}"
        if name == "list_api_keys":
            assert len(response.json()) == self_service_context.key_count
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_api_key_mutation_denials_stay_within_query_budgets(
    auth_instance: EnterpriseRBAC,
    query_counter: QueryCounter,
    mutation_context: ApiKeyMutationQueryContext,
) -> None:
    async with auth_instance.get_session() as session:
        await auth_instance.role_service.remove_permissions_by_name(
            session,
            mutation_context.permission_removed_role_id,
            [f"{mutation_context.permission_removed_scope_check_name}_tree"],
            changed_by_id=mutation_context.admin_user_id,
        )
        await auth_instance.membership_service.update_membership(
            session=session,
            entity_id=mutation_context.department_id,
            user_id=mutation_context.membership_owner_id,
            role_ids=[],
            update_roles=True,
            changed_by_id=mutation_context.admin_user_id,
        )
        await auth_instance.role_service.revoke_role_from_user(
            session,
            user_id=mutation_context.direct_role_owner_id,
            role_id=mutation_context.direct_user_role_id,
            revoked_by_id=mutation_context.admin_user_id,
            reason="query budget test revoke",
        )
        await session.commit()

    cases = [
        (
            "permission_removed_from_role",
            mutation_context.permission_removed_key,
            mutation_context.permission_removed_scope_check_name,
            mutation_context.team_id,
            12,
        ),
        (
            "membership_roles_removed",
            mutation_context.membership_key,
            mutation_context.membership_scope_check_name,
            mutation_context.team_id,
            12,
        ),
        (
            "direct_user_role_revoked",
            mutation_context.direct_role_key,
            mutation_context.direct_role_scope_name,
            mutation_context.team_id,
            12,
        ),
    ]

    for name, api_key, required_scope, entity_id, max_queries in cases:
        query_counter.reset()
        async with auth_instance.get_session() as session:
            query_counter.enabled = True
            result = await auth_instance.authorize_api_key(
                session,
                api_key,
                required_scope=required_scope,
                entity_id=entity_id,
            )
            query_counter.enabled = False

        assert result is None, f"{name} unexpectedly authorized after mutation"
        assert query_counter.count <= max_queries, (
            f"{name} exceeded query budget: {query_counter.count} > {max_queries} " f"(db_ms={query_counter.db_ms:.1f})"
        )
