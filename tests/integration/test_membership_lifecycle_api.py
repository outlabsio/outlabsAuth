import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from uuid import UUID

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.routers import get_memberships_router
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    """Create EnterpriseRBAC instance for membership lifecycle testing."""
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
    """Create FastAPI app with the memberships router."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_user(auth_instance: EnterpriseRBAC) -> dict:
    """Create a superuser token for API calls."""
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email="membership-admin@example.com",
            password="TestPass123!",
            first_name="Membership",
            last_name="Admin",
            is_superuser=True,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {"id": str(admin.id), "token": token}


async def _seed_membership_setup(auth_instance: EnterpriseRBAC):
    """Create a root, child entity, target user, and assignable roles."""
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name="membership_root",
            display_name="Membership Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        child = await auth_instance.entity_service.create_entity(
            session=session,
            name="membership_child",
            display_name="Membership Child",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role_a = await auth_instance.role_service.create_role(
            session=session,
            name="membership_role_a",
            display_name="Membership Role A",
            root_entity_id=root.id,
            is_global=False,
        )
        role_b = await auth_instance.role_service.create_role(
            session=session,
            name="membership_role_b",
            display_name="Membership Role B",
            root_entity_id=root.id,
            is_global=False,
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email="membership-target@example.com",
            password="TestPass123!",
            first_name="Membership",
            last_name="Target",
            is_superuser=False,
        )
        await session.commit()

        return {
            "root_id": str(root.id),
            "child_id": str(child.id),
            "role_a_id": str(role_a.id),
            "role_b_id": str(role_b.id),
            "user_id": str(user.id),
        }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_create_accepts_lifecycle_fields(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    setup = await _seed_membership_setup(auth_instance)

    response = await client.post(
        "/v1/memberships/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "entity_id": setup["child_id"],
            "user_id": setup["user_id"],
            "role_ids": [setup["role_a_id"]],
            "status": "suspended",
            "valid_from": "2026-03-16T09:00:00Z",
            "valid_until": "2026-03-23T09:00:00Z",
            "reason": "Coverage pause",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "suspended"
    assert payload["effective_status"] == "suspended"
    assert payload["revocation_reason"] == "Coverage pause"
    assert payload["valid_from"].startswith("2026-03-16T09:00:00")
    assert payload["valid_until"].startswith("2026-03-23T09:00:00")
    assert payload["can_grant_permissions"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_update_persists_multiple_roles_and_lifecycle_fields(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    setup = await _seed_membership_setup(auth_instance)

    async with auth_instance.get_session() as session:
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=UUID(setup["child_id"]),
            user_id=UUID(setup["user_id"]),
            role_ids=[UUID(setup["role_a_id"])],
        )
        await session.commit()

    response = await client.patch(
        f"/v1/memberships/{setup['child_id']}/{setup['user_id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "role_ids": [setup["role_a_id"], setup["role_b_id"]],
            "status": "suspended",
            "valid_until": "2026-03-30T12:00:00Z",
            "reason": "Temporary leave",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["role_ids"]) == {setup["role_a_id"], setup["role_b_id"]}
    assert payload["status"] == "suspended"
    assert payload["revocation_reason"] == "Temporary leave"
    assert payload["valid_until"].startswith("2026-03-30T12:00:00")

    readback = await client.get(
        f"/v1/memberships/user/{setup['user_id']}?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )

    assert readback.status_code == 200
    readback_payload = readback.json()
    assert len(readback_payload) == 1
    assert set(readback_payload[0]["role_ids"]) == {
        setup["role_a_id"],
        setup["role_b_id"],
    }
    assert readback_payload[0]["status"] == "suspended"
    assert readback_payload[0]["effective_status"] == "suspended"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inactive_memberships_are_hidden_by_default_but_visible_when_requested(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    setup = await _seed_membership_setup(auth_instance)

    async with auth_instance.get_session() as session:
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=UUID(setup["child_id"]),
            user_id=UUID(setup["user_id"]),
            role_ids=[UUID(setup["role_a_id"])],
            status=MembershipStatus.SUSPENDED,
            reason="On leave",
        )
        await session.commit()

    active_only = await client.get(
        f"/v1/memberships/user/{setup['user_id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert active_only.status_code == 200
    assert active_only.json() == []

    include_inactive = await client.get(
        f"/v1/memberships/user/{setup['user_id']}?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert include_inactive.status_code == 200
    payload = include_inactive.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "suspended"
    assert payload[0]["effective_status"] == "suspended"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_delete_soft_revokes_and_can_be_reactivated(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    setup = await _seed_membership_setup(auth_instance)

    async with auth_instance.get_session() as session:
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=UUID(setup["child_id"]),
            user_id=UUID(setup["user_id"]),
            role_ids=[UUID(setup["role_a_id"])],
        )
        await session.commit()

    delete_response = await client.delete(
        f"/v1/memberships/{setup['child_id']}/{setup['user_id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert delete_response.status_code == 204

    readback = await client.get(
        f"/v1/memberships/user/{setup['user_id']}?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert readback.status_code == 200
    readback_payload = readback.json()
    assert len(readback_payload) == 1
    assert readback_payload[0]["status"] == "revoked"
    assert readback_payload[0]["effective_status"] == "revoked"
    assert readback_payload[0]["can_grant_permissions"] is False

    reactivate_response = await client.patch(
        f"/v1/memberships/{setup['child_id']}/{setup['user_id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "active", "reason": None},
    )

    assert reactivate_response.status_code == 200
    reactivated = reactivate_response.json()
    assert reactivated["status"] == "active"
    assert reactivated["effective_status"] == "active"
    assert reactivated["revoked_at"] is None
    assert reactivated["revocation_reason"] is None
