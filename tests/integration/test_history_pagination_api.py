import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_memberships_router, get_users_router
from outlabs_auth.utils.jwt import create_access_token


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
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    app.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_user(auth_instance: EnterpriseRBAC) -> dict:
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"history-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="History",
            last_name="Admin",
            is_superuser=True,
        )
        await session.commit()
        admin_id = str(admin.id)

    token = create_access_token(
        {"sub": admin_id},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
    )
    return {"id": admin_id, "token": token}


async def _seed_history_context(auth_instance: EnterpriseRBAC) -> dict:
    unique = uuid.uuid4().hex[:8]
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"history-root-{unique}",
            display_name="History Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team_a = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"history-team-a-{unique}",
            display_name="History Team A",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        team_b = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"history-team-b-{unique}",
            display_name="History Team B",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role_a = await auth_instance.role_service.create_role(
            session=session,
            name=f"history-role-a-{unique}",
            display_name="History Role A",
            is_global=False,
            root_entity_id=root.id,
        )
        role_b = await auth_instance.role_service.create_role(
            session=session,
            name=f"history-role-b-{unique}",
            display_name="History Role B",
            is_global=False,
            root_entity_id=root.id,
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"history-target-{unique}@example.com",
            password="TestPass123!",
            first_name="History",
            last_name="Target",
            root_entity_id=root.id,
        )
        await session.commit()

    return {
        "user_id": str(user.id),
        "team_a_id": str(team_a.id),
        "team_b_id": str(team_b.id),
        "role_a_id": str(role_a.id),
        "role_b_id": str(role_b.id),
    }


async def _create_membership_history_sequence(
    client: httpx.AsyncClient,
    admin_token: str,
    *,
    user_id: str,
    team_a_id: str,
    team_b_id: str,
    role_a_id: str,
    role_b_id: str,
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_a = await client.post(
        "/v1/memberships/",
        headers=headers,
        json={
            "entity_id": team_a_id,
            "user_id": user_id,
            "role_ids": [role_a_id],
        },
    )
    assert create_a.status_code == 201, create_a.text

    update_a = await client.patch(
        f"/v1/memberships/{team_a_id}/{user_id}",
        headers=headers,
        json={
            "role_ids": [role_a_id, role_b_id],
            "valid_until": "2026-04-15T12:00:00Z",
        },
    )
    assert update_a.status_code == 200, update_a.text

    suspend_a = await client.patch(
        f"/v1/memberships/{team_a_id}/{user_id}",
        headers=headers,
        json={
            "status": "suspended",
            "reason": "Coverage leave",
        },
    )
    assert suspend_a.status_code == 200, suspend_a.text

    reactivate_a = await client.patch(
        f"/v1/memberships/{team_a_id}/{user_id}",
        headers=headers,
        json={"status": "active"},
    )
    assert reactivate_a.status_code == 200, reactivate_a.text

    revoke_a = await client.delete(
        f"/v1/memberships/{team_a_id}/{user_id}",
        headers=headers,
    )
    assert revoke_a.status_code == 204, revoke_a.text

    create_b = await client.post(
        "/v1/memberships/",
        headers=headers,
        json={
            "entity_id": team_b_id,
            "user_id": user_id,
            "role_ids": [role_b_id],
        },
    )
    assert create_b.status_code == 201, create_b.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_support_pagination_and_combined_filters(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    context = await _seed_history_context(auth_instance)
    await _create_membership_history_sequence(
        client,
        admin_user["token"],
        user_id=context["user_id"],
        team_a_id=context["team_a_id"],
        team_b_id=context["team_b_id"],
        role_a_id=context["role_a_id"],
        role_b_id=context["role_b_id"],
    )

    headers = {"Authorization": f"Bearer {admin_user['token']}"}

    page_one_resp = await client.get(
        f"/v1/users/{context['user_id']}/audit-events",
        headers=headers,
        params={"category": "membership", "page": 1, "limit": 2},
    )
    page_two_resp = await client.get(
        f"/v1/users/{context['user_id']}/audit-events",
        headers=headers,
        params={"category": "membership", "page": 2, "limit": 2},
    )
    filtered_resp = await client.get(
        f"/v1/users/{context['user_id']}/audit-events",
        headers=headers,
        params={
            "category": "membership",
            "event_type": "user.membership_created",
            "entity_id": context["team_a_id"],
            "page": 1,
            "limit": 1,
        },
    )

    assert page_one_resp.status_code == 200, page_one_resp.text
    assert page_two_resp.status_code == 200, page_two_resp.text
    assert filtered_resp.status_code == 200, filtered_resp.text

    page_one = page_one_resp.json()
    page_two = page_two_resp.json()
    filtered = filtered_resp.json()

    assert page_one["total"] == 6
    assert page_one["page"] == 1
    assert page_one["limit"] == 2
    assert page_one["pages"] == 3
    assert [item["event_type"] for item in page_one["items"]] == [
        "user.membership_created",
        "user.membership_revoked",
    ]
    assert page_one["items"][0]["entity_id"] == context["team_b_id"]
    assert page_one["items"][1]["entity_id"] == context["team_a_id"]

    assert page_two["total"] == 6
    assert page_two["page"] == 2
    assert page_two["pages"] == 3
    assert [item["event_type"] for item in page_two["items"]] == [
        "user.membership_reactivated",
        "user.membership_suspended",
    ]

    assert filtered["total"] == 1
    assert filtered["page"] == 1
    assert filtered["pages"] == 1
    assert [item["event_type"] for item in filtered["items"]] == [
        "user.membership_created"
    ]
    assert filtered["items"][0]["entity_id"] == context["team_a_id"]
    assert filtered["items"][0]["metadata"]["history_event_type"] == "created"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_membership_history_supports_pagination_and_combined_filters(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    context = await _seed_history_context(auth_instance)
    await _create_membership_history_sequence(
        client,
        admin_user["token"],
        user_id=context["user_id"],
        team_a_id=context["team_a_id"],
        team_b_id=context["team_b_id"],
        role_a_id=context["role_a_id"],
        role_b_id=context["role_b_id"],
    )

    headers = {"Authorization": f"Bearer {admin_user['token']}"}

    page_one_resp = await client.get(
        f"/v1/users/{context['user_id']}/membership-history",
        headers=headers,
        params={"page": 1, "limit": 2},
    )
    page_two_resp = await client.get(
        f"/v1/users/{context['user_id']}/membership-history",
        headers=headers,
        params={"page": 2, "limit": 2},
    )
    filtered_resp = await client.get(
        f"/v1/users/{context['user_id']}/membership-history",
        headers=headers,
        params={
            "entity_id": context["team_a_id"],
            "event_type": "created",
            "page": 1,
            "limit": 1,
        },
    )

    assert page_one_resp.status_code == 200, page_one_resp.text
    assert page_two_resp.status_code == 200, page_two_resp.text
    assert filtered_resp.status_code == 200, filtered_resp.text

    page_one = page_one_resp.json()
    page_two = page_two_resp.json()
    filtered = filtered_resp.json()

    assert page_one["total"] == 6
    assert page_one["page"] == 1
    assert page_one["limit"] == 2
    assert page_one["pages"] == 3
    assert [item["event_type"] for item in page_one["items"]] == [
        "created",
        "revoked",
    ]
    assert page_one["items"][0]["entity_id"] == context["team_b_id"]
    assert page_one["items"][1]["entity_id"] == context["team_a_id"]

    assert page_two["total"] == 6
    assert page_two["page"] == 2
    assert page_two["pages"] == 3
    assert [item["event_type"] for item in page_two["items"]] == [
        "reactivated",
        "suspended",
    ]

    assert filtered["total"] == 1
    assert filtered["page"] == 1
    assert filtered["pages"] == 1
    assert [item["event_type"] for item in filtered["items"]] == ["created"]
    assert filtered["items"][0]["entity_id"] == context["team_a_id"]
