import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.routers.entities import get_entities_router
from outlabs_auth.routers.memberships import get_memberships_router
from outlabs_auth.utils.jwt import create_access_token


async def _bearer_token(auth: EnterpriseRBAC, user_id: str) -> str:
    return create_access_token(
        {"sub": user_id},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
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
    application.include_router(get_entities_router(auth_instance, prefix="/v1/entities"))
    application.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def admin_headers(auth_instance: EnterpriseRBAC) -> dict[str, str]:
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"read-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Read",
            last_name="Admin",
            is_superuser=True,
        )
        await session.commit()

    token = await _bearer_token(auth_instance, str(admin.id))
    return {"Authorization": f"Bearer {token}"}


async def _seed_read_route_context(auth_instance: EnterpriseRBAC) -> dict:
    suffix = uuid.uuid4().hex[:8]

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"root-{suffix}",
            display_name="Read Root",
            slug=f"read-root-{suffix}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        dept_a = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"dept-a-{suffix}",
            display_name="Department A",
            slug=f"dept-a-{suffix}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        dept_b = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"dept-b-{suffix}",
            display_name="Department B",
            slug=f"dept-b-{suffix}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"team-{suffix}",
            display_name="Read Team",
            slug=f"read-team-{suffix}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=dept_a.id,
        )
        project = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"project-{suffix}",
            display_name="Read Project",
            slug=f"read-project-{suffix}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="project",
            parent_id=team.id,
        )

        role_alpha = await auth_instance.role_service.create_role(
            session=session,
            name=f"read-alpha-{suffix}",
            display_name="Read Alpha",
            root_entity_id=root.id,
            is_global=False,
        )
        role_beta = await auth_instance.role_service.create_role(
            session=session,
            name=f"read-beta-{suffix}",
            display_name="Read Beta",
            root_entity_id=root.id,
            is_global=False,
        )

        team_user_a = await auth_instance.user_service.create_user(
            session=session,
            email=f"team-a-{suffix}@example.com",
            password="TestPass123!",
            first_name="Team",
            last_name="Alpha",
        )
        team_user_b = await auth_instance.user_service.create_user(
            session=session,
            email=f"team-b-{suffix}@example.com",
            password="TestPass123!",
            first_name="Team",
            last_name="Beta",
        )
        team_user_c = await auth_instance.user_service.create_user(
            session=session,
            email=f"team-c-{suffix}@example.com",
            password="TestPass123!",
            first_name="Team",
            last_name="Gamma",
        )
        suspended_team_user = await auth_instance.user_service.create_user(
            session=session,
            email=f"team-suspended-{suffix}@example.com",
            password="TestPass123!",
            first_name="Team",
            last_name="Suspended",
        )
        journey_user = await auth_instance.user_service.create_user(
            session=session,
            email=f"journey-{suffix}@example.com",
            password="TestPass123!",
            first_name="Journey",
            last_name="User",
        )

        team_membership_a = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=team_user_a.id,
            role_ids=[role_alpha.id],
        )
        team_membership_b = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=team_user_b.id,
            role_ids=[role_beta.id],
        )
        team_membership_c = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=team_user_c.id,
            role_ids=[],
        )
        team_membership_journey = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=journey_user.id,
            role_ids=[role_beta.id],
        )
        suspended_team_membership = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=suspended_team_user.id,
            role_ids=[role_alpha.id],
            status=MembershipStatus.SUSPENDED,
            reason="Suspended for read-route coverage",
        )

        journey_root_membership = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=root.id,
            user_id=journey_user.id,
            role_ids=[role_alpha.id],
        )
        journey_department_membership = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=dept_a.id,
            user_id=journey_user.id,
            role_ids=[],
        )
        journey_project_membership = await auth_instance.membership_service.add_member(
            session=session,
            entity_id=project.id,
            user_id=journey_user.id,
            role_ids=[],
            status=MembershipStatus.SUSPENDED,
            reason="Project access paused",
        )

        await session.commit()

    return {
        "root_id": str(root.id),
        "dept_a_id": str(dept_a.id),
        "dept_b_id": str(dept_b.id),
        "team_id": str(team.id),
        "project_id": str(project.id),
        "role_alpha_id": str(role_alpha.id),
        "role_beta_id": str(role_beta.id),
        "suspended_team_user_id": str(suspended_team_user.id),
        "suspended_team_user_email": suspended_team_user.email,
        "active_team_member_user_ids": {
            str(team_user_a.id),
            str(team_user_b.id),
            str(team_user_c.id),
            str(journey_user.id),
        },
        "active_team_membership_ids": {
            str(team_membership_a.id),
            str(team_membership_b.id),
            str(team_membership_c.id),
            str(team_membership_journey.id),
        },
        "suspended_team_membership_id": str(suspended_team_membership.id),
        "journey_user_id": str(journey_user.id),
        "journey_active_membership_ids": {
            str(journey_root_membership.id),
            str(journey_department_membership.id),
            str(team_membership_journey.id),
        },
        "journey_suspended_membership_id": str(journey_project_membership.id),
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_children_and_path_routes_return_expected_contract(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_headers: dict[str, str],
):
    context = await _seed_read_route_context(auth_instance)

    children_response = await client.get(
        f"/v1/entities/{context['root_id']}/children",
        headers=admin_headers,
    )
    assert children_response.status_code == 200, children_response.text
    children = children_response.json()
    assert {item["id"] for item in children} == {context["dept_a_id"], context["dept_b_id"]}
    assert all(item["parent_entity_id"] == context["root_id"] for item in children)
    assert all(item["entity_class"] == "structural" for item in children)
    assert all(item["status"] == "active" for item in children)

    path_response = await client.get(
        f"/v1/entities/{context['project_id']}/path",
        headers=admin_headers,
    )
    assert path_response.status_code == 200, path_response.text
    path_items = path_response.json()
    assert [item["id"] for item in path_items] == [
        context["root_id"],
        context["dept_a_id"],
        context["team_id"],
        context["project_id"],
    ]
    assert [item["entity_type"] for item in path_items] == [
        "organization",
        "department",
        "team",
        "project",
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_members_route_returns_paginated_member_response(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_headers: dict[str, str],
):
    context = await _seed_read_route_context(auth_instance)

    page_one = await client.get(
        f"/v1/entities/{context['team_id']}/members",
        params={"page": 1, "limit": 2},
        headers=admin_headers,
    )
    page_two = await client.get(
        f"/v1/entities/{context['team_id']}/members",
        params={"page": 2, "limit": 2},
        headers=admin_headers,
    )

    assert page_one.status_code == 200, page_one.text
    assert page_two.status_code == 200, page_two.text

    page_one_payload = page_one.json()
    page_two_payload = page_two.json()
    assert page_one_payload["total"] == 4
    assert page_one_payload["page"] == 1
    assert page_one_payload["limit"] == 2
    assert page_one_payload["pages"] == 2
    assert page_two_payload["total"] == 4
    assert page_two_payload["page"] == 2
    assert page_two_payload["pages"] == 2

    page_one_user_ids = {item["user_id"] for item in page_one_payload["items"]}
    page_two_user_ids = {item["user_id"] for item in page_two_payload["items"]}
    assert len(page_one_payload["items"]) == 2
    assert len(page_two_payload["items"]) == 2
    assert page_one_user_ids.isdisjoint(page_two_user_ids)
    assert page_one_user_ids | page_two_user_ids == context["active_team_member_user_ids"]

    sample_member = page_one_payload["items"][0]
    assert sample_member["email"].endswith("@example.com")
    assert isinstance(sample_member["role_ids"], list)
    assert isinstance(sample_member["role_names"], list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_entity_read_routes_cover_pagination_details_and_inactive_members(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_headers: dict[str, str],
):
    context = await _seed_read_route_context(auth_instance)

    page_one = await client.get(
        f"/v1/memberships/entity/{context['team_id']}",
        params={"page": 1, "limit": 2},
        headers=admin_headers,
    )
    page_two = await client.get(
        f"/v1/memberships/entity/{context['team_id']}",
        params={"page": 2, "limit": 2},
        headers=admin_headers,
    )

    assert page_one.status_code == 200, page_one.text
    assert page_two.status_code == 200, page_two.text

    page_one_memberships = page_one.json()
    page_two_memberships = page_two.json()
    assert len(page_one_memberships) == 2
    assert len(page_two_memberships) == 2

    page_one_ids = {item["id"] for item in page_one_memberships}
    page_two_ids = {item["id"] for item in page_two_memberships}
    assert page_one_ids.isdisjoint(page_two_ids)
    assert page_one_ids | page_two_ids == context["active_team_membership_ids"]
    assert context["suspended_team_membership_id"] not in (page_one_ids | page_two_ids)
    assert all(item["status"] == "active" for item in page_one_memberships + page_two_memberships)
    assert all(item["effective_status"] == "active" for item in page_one_memberships + page_two_memberships)

    details_response = await client.get(
        f"/v1/memberships/entity/{context['team_id']}/details",
        params={"page": 1, "limit": 10, "include_inactive": True},
        headers=admin_headers,
    )
    assert details_response.status_code == 200, details_response.text
    detailed_members = details_response.json()
    assert len(detailed_members) == 5

    suspended_member = next(
        item for item in detailed_members if item["user_id"] == context["suspended_team_user_id"]
    )
    assert suspended_member["user_email"] == context["suspended_team_user_email"]
    assert suspended_member["user_status"] == "active"
    assert suspended_member["status"] == "suspended"
    assert suspended_member["effective_status"] == "suspended"
    assert suspended_member["roles"] == [
        {
            "id": context["role_alpha_id"],
            "name": next(role["name"] for role in suspended_member["roles"]),
            "display_name": "Read Alpha",
        }
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_user_read_route_supports_pagination_and_include_inactive(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_headers: dict[str, str],
):
    context = await _seed_read_route_context(auth_instance)

    page_one = await client.get(
        f"/v1/memberships/user/{context['journey_user_id']}",
        params={"page": 1, "limit": 2},
        headers=admin_headers,
    )
    page_two = await client.get(
        f"/v1/memberships/user/{context['journey_user_id']}",
        params={"page": 2, "limit": 2},
        headers=admin_headers,
    )

    assert page_one.status_code == 200, page_one.text
    assert page_two.status_code == 200, page_two.text

    page_one_memberships = page_one.json()
    page_two_memberships = page_two.json()
    assert len(page_one_memberships) == 2
    assert len(page_two_memberships) == 1

    page_one_ids = {item["id"] for item in page_one_memberships}
    page_two_ids = {item["id"] for item in page_two_memberships}
    assert page_one_ids.isdisjoint(page_two_ids)
    assert page_one_ids | page_two_ids == context["journey_active_membership_ids"]
    assert all(item["status"] == "active" for item in page_one_memberships + page_two_memberships)

    include_inactive = await client.get(
        f"/v1/memberships/user/{context['journey_user_id']}",
        params={"page": 1, "limit": 10, "include_inactive": True},
        headers=admin_headers,
    )
    assert include_inactive.status_code == 200, include_inactive.text
    all_memberships = include_inactive.json()
    assert len(all_memberships) == 4

    suspended_membership = next(
        item for item in all_memberships if item["id"] == context["journey_suspended_membership_id"]
    )
    assert suspended_membership["status"] == "suspended"
    assert suspended_membership["effective_status"] == "suspended"
    assert suspended_membership["can_grant_permissions"] is False
    assert suspended_membership["revocation_reason"] == "Project access paused"
