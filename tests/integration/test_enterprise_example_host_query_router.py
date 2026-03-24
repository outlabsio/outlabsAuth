import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlmodel import SQLModel

from examples.enterprise_rbac.models import Lead
from examples.enterprise_rbac.team_directory import get_team_directory_router
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def enterprise_auth(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        enable_context_aware_roles=True,
    )
    await auth.initialize()
    async with test_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: SQLModel.metadata.create_all(
                sync_conn,
                tables=[Lead.__table__],
            )
        )
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def example_app(enterprise_auth: EnterpriseRBAC) -> FastAPI:
    app = FastAPI()
    app.include_router(get_team_directory_router(enterprise_auth, prefix="/v1"))
    return app


async def _bearer_token(auth: EnterpriseRBAC, user_id: str) -> str:
    return create_access_token(
        {"sub": user_id},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )


async def _seed_permissions(session, auth: EnterpriseRBAC, names: list[str]) -> None:
    for name in names:
        await auth.permission_service.create_permission(
            session=session,
            name=name,
            display_name=name,
            description=name,
            is_system=True,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_example_team_directory_route_uses_host_query_service(
    example_app: FastAPI,
    enterprise_auth: EnterpriseRBAC,
):
    async with enterprise_auth.get_session() as session:
        await _seed_permissions(session, enterprise_auth, ["membership:read", "membership:read_tree"])

        viewer_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="directory_viewer",
            display_name="Directory Viewer",
            permission_names=["membership:read_tree"],
            is_global=True,
            assignable_at_types=["organization", "team"],
        )
        team_member_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="team_agent",
            display_name="Team Agent",
            is_global=True,
            permission_names=[],
            assignable_at_types=["team"],
        )

        manager = await enterprise_auth.user_service.create_user(
            session=session,
            email="manager@enterprise-example.test",
            password="TestPass123!",
            first_name="Mara",
            last_name="Manager",
        )
        agent_one = await enterprise_auth.user_service.create_user(
            session=session,
            email="agent.one@enterprise-example.test",
            password="TestPass123!",
            first_name="Ava",
            last_name="Agent",
        )
        agent_two = await enterprise_auth.user_service.create_user(
            session=session,
            email="agent.two@enterprise-example.test",
            password="TestPass123!",
            first_name="Ben",
            last_name="Agent",
        )

        org = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="enterprise_example_org",
            display_name="Enterprise Example Org",
            slug="enterprise-example-org",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="enterprise_example_team",
            display_name="Enterprise Example Team",
            slug="enterprise-example-team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=org.id,
        )

        membership_service = MembershipService(enterprise_auth.config)
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=manager.id,
            role_ids=[viewer_role.id],
        )
        await membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=agent_one.id,
            role_ids=[team_member_role.id],
        )
        await membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=agent_two.id,
            role_ids=[team_member_role.id],
        )

        session.add_all(
            [
                Lead(
                    entity_id=team.id,
                    first_name="Lead",
                    last_name="One",
                    email="lead1@example.com",
                    phone="+1-555-0101",
                    lead_type="buyer",
                    status="new",
                    source="Website",
                    assigned_to=agent_one.id,
                    created_by=manager.id,
                ),
                Lead(
                    entity_id=team.id,
                    first_name="Lead",
                    last_name="Two",
                    email="lead2@example.com",
                    phone="+1-555-0102",
                    lead_type="seller",
                    status="contacted",
                    source="Referral",
                    assigned_to=agent_one.id,
                    created_by=manager.id,
                ),
                Lead(
                    entity_id=team.id,
                    first_name="Lead",
                    last_name="Three",
                    email="lead3@example.com",
                    phone="+1-555-0103",
                    lead_type="buyer",
                    status="qualified",
                    source="Zillow",
                    assigned_to=agent_two.id,
                    created_by=manager.id,
                ),
            ]
        )
        await session.commit()

        token = await _bearer_token(enterprise_auth, str(manager.id))

    transport = httpx.ASGITransport(app=example_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/entities/{team.id}/team-directory",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["entity_id"] == str(team.id)
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["limit"] == 50

    items_by_email = {item["email"]: item for item in payload["items"]}
    assert set(items_by_email) == {
        "agent.one@enterprise-example.test",
        "agent.two@enterprise-example.test",
    }
    assert items_by_email["agent.one@enterprise-example.test"]["assigned_lead_count"] == 2
    assert items_by_email["agent.two@enterprise-example.test"]["assigned_lead_count"] == 1
    assert items_by_email["agent.one@enterprise-example.test"]["roles"][0]["name"] == "team_agent"
