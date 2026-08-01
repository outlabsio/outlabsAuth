import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_auth_router, get_memberships_router, get_users_router
from outlabs_auth.utils.jwt import create_access_token


def _iso_z(value: datetime) -> str:
    """Serialize UTC datetimes in a stable API-friendly format."""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_api_datetime(value: str | None) -> datetime | None:
    """Parse API datetime payloads that may use Z or +00:00."""
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    """Create EnterpriseRBAC instance for admin user-details contract tests."""
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
    """Create FastAPI app with the user-details routes used by the admin UI."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
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
    """Create superuser credentials for admin-only user-details routes."""
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(admin.id),
            "email": admin.email,
            "token": token,
            "password": "AdminPass123!",
        }


async def _create_active_user(auth_instance: EnterpriseRBAC, *, email_prefix: str = "user") -> dict:
    """Create an active user and return credentials."""
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
            password="StartPass123!",
            first_name="Target",
            last_name="User",
            is_superuser=False,
        )
        await session.commit()

        return {
            "id": str(user.id),
            "email": user.email,
            "password": "StartPass123!",
        }


async def _fetch_user(auth_instance: EnterpriseRBAC, user_id: str):
    """Reload a user model from the database."""
    async with auth_instance.get_session() as session:
        return await auth_instance.user_service.get_user_by_id(session, UUID(user_id))


async def _seed_membership_context(auth_instance: EnterpriseRBAC) -> dict:
    """Create a simple org/team hierarchy with assignable roles."""
    suffix = uuid.uuid4().hex[:8]
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"root-{suffix}",
            display_name="Contract Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        child = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"child-{suffix}",
            display_name="Contract Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role_a = await auth_instance.role_service.create_role(
            session=session,
            name=f"member-role-a-{suffix}",
            display_name="Member Role A",
            root_entity_id=root.id,
            is_global=False,
        )
        role_b = await auth_instance.role_service.create_role(
            session=session,
            name=f"member-role-b-{suffix}",
            display_name="Member Role B",
            root_entity_id=root.id,
            is_global=False,
        )
        await session.commit()

        return {
            "root_id": str(root.id),
            "child_id": str(child.id),
            "role_a_id": str(role_a.id),
            "role_b_id": str(role_b.id),
        }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_user_details_profile_status_and_password_contract(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict,
):
    """Cover the profile, status, and password flows used by the admin record page."""
    target_user = await _create_active_user(auth_instance)

    update_resp = await client.patch(
        f"/v1/users/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "email": f"updated-{uuid.uuid4().hex[:8]}@example.com",
            "first_name": "Updated",
            "last_name": "Record",
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["first_name"] == "Updated"
    assert updated["last_name"] == "Record"
    assert updated["email"].startswith("updated-")

    readback_resp = await client.get(
        f"/v1/users/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert readback_resp.status_code == 200
    assert readback_resp.json()["email"] == updated["email"]

    suspended_until = datetime.now(timezone.utc) + timedelta(days=2)
    suspend_resp = await client.patch(
        f"/v1/users/{target_user['id']}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "status": "suspended",
            "suspended_until": _iso_z(suspended_until),
            "reason": "Admin contract coverage",
        },
    )
    assert suspend_resp.status_code == 200
    suspended = suspend_resp.json()
    assert suspended["status"] == "suspended"
    assert _parse_api_datetime(suspended["suspended_until"]) == suspended_until.replace(microsecond=0)

    reactivate_resp = await client.patch(
        f"/v1/users/{target_user['id']}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "active"},
    )
    assert reactivate_resp.status_code == 200
    reactivated = reactivate_resp.json()
    assert reactivated["status"] == "active"
    assert reactivated["suspended_until"] is None

    reset_resp = await client.patch(
        f"/v1/users/{target_user['id']}/password",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"new_password": "ResetPass123!"},
    )
    assert reset_resp.status_code == 204

    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": updated["email"], "password": "ResetPass123!"},
    )
    assert login_resp.status_code == 200
    payload = login_resp.json()
    assert payload["access_token"]
    assert payload["refresh_token"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_user_details_invite_resend_and_delete_contract(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict,
):
    """Cover invited-user resend and delete flows used by the admin record page."""
    invite_email = f"invited-{uuid.uuid4().hex[:8]}@example.com"
    invite_resp = await client.post(
        "/v1/auth/invite",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "email": invite_email,
            "first_name": "Invited",
            "last_name": "User",
        },
    )
    assert invite_resp.status_code == 201
    invited = invite_resp.json()
    assert invited["status"] == "invited"
    assert invited["email"] == invite_email

    original_user = await _fetch_user(auth_instance, invited["id"])
    assert original_user is not None
    original_token = original_user.invite_token
    original_expiry = original_user.invite_token_expires

    resend_resp = await client.post(
        f"/v1/users/{invited['id']}/resend-invite",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resend_resp.status_code == 200
    resent = resend_resp.json()
    assert resent["id"] == invited["id"]
    assert resent["status"] == "invited"

    refreshed_user = await _fetch_user(auth_instance, invited["id"])
    assert refreshed_user is not None
    assert refreshed_user.invite_token != original_token
    assert refreshed_user.invite_token_expires > original_expiry

    delete_resp = await client.delete(
        f"/v1/users/{invited['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert delete_resp.status_code == 204

    readback_resp = await client.get(
        f"/v1/users/{invited['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert readback_resp.status_code == 200
    deleted_user = readback_resp.json()
    assert deleted_user["id"] == invited["id"]
    assert deleted_user["email"] == invite_email
    assert deleted_user["status"] == "deleted"
    assert deleted_user["deleted_at"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_user_details_direct_role_membership_contract(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict,
):
    """Cover direct role assign, read, and revoke behavior with lifecycle metadata."""
    target_user = await _create_active_user(auth_instance, email_prefix="direct-role")

    async with auth_instance.get_session() as session:
        direct_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"direct-role-{uuid.uuid4().hex[:8]}",
            display_name="Direct Role",
            is_global=True,
        )
        await session.commit()

    valid_from = datetime.now(timezone.utc) - timedelta(hours=1)
    valid_until = datetime.now(timezone.utc) + timedelta(days=5)

    assign_resp = await client.post(
        f"/v1/users/{target_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "role_id": str(direct_role.id),
            "valid_from": _iso_z(valid_from),
            "valid_until": _iso_z(valid_until),
        },
    )
    assert assign_resp.status_code == 201
    assigned = assign_resp.json()
    assert assigned["role_id"] == str(direct_role.id)
    assert assigned["status"] == "active"
    assert assigned["assigned_by_id"] == admin_user["id"]

    roles_resp = await client.get(
        f"/v1/users/{target_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert roles_resp.status_code == 200
    assert any(role["id"] == str(direct_role.id) for role in roles_resp.json())

    memberships_resp = await client.get(
        f"/v1/users/{target_user['id']}/role-memberships",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert memberships_resp.status_code == 200
    memberships = memberships_resp.json()
    assert len(memberships) == 1
    membership = memberships[0]
    assert membership["role_id"] == str(direct_role.id)
    assert membership["assigned_by_id"] == admin_user["id"]
    assert membership["role"]["display_name"] == "Direct Role"
    assert membership["is_currently_valid"] is True

    revoke_resp = await client.delete(
        f"/v1/users/{target_user['id']}/roles/{direct_role.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert revoke_resp.status_code == 204

    active_only_resp = await client.get(
        f"/v1/users/{target_user['id']}/role-memberships",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert active_only_resp.status_code == 200
    assert active_only_resp.json() == []

    include_inactive_resp = await client.get(
        f"/v1/users/{target_user['id']}/role-memberships?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert include_inactive_resp.status_code == 200
    revoked_memberships = include_inactive_resp.json()
    assert len(revoked_memberships) == 1
    revoked = revoked_memberships[0]
    assert revoked["status"] == "revoked"
    assert revoked["revoked_at"] is not None
    assert revoked["can_grant_permissions"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_user_details_entity_membership_contract(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict,
):
    """Cover entity membership create, update, revoke, and reactivate flows."""
    target_user = await _create_active_user(auth_instance, email_prefix="member")
    setup = await _seed_membership_context(auth_instance)

    valid_from = datetime.now(timezone.utc) - timedelta(hours=2)
    valid_until = datetime.now(timezone.utc) + timedelta(days=7)

    create_resp = await client.post(
        "/v1/memberships/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "entity_id": setup["child_id"],
            "user_id": target_user["id"],
            "role_ids": [setup["role_a_id"]],
            "status": "active",
            "valid_from": _iso_z(valid_from),
            "valid_until": _iso_z(valid_until),
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["entity_id"] == setup["child_id"]
    assert created["status"] == "active"
    assert created["effective_status"] == "active"
    assert created["role_ids"] == [setup["role_a_id"]]

    detail_resp = await client.get(
        f"/v1/users/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert detail_resp.status_code == 200
    detail_payload = detail_resp.json()
    assert detail_payload["root_entity_id"] == setup["root_id"]
    assert detail_payload["root_entity_name"] == "Contract Root"

    update_resp = await client.patch(
        f"/v1/memberships/{setup['child_id']}/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "role_ids": [setup["role_a_id"], setup["role_b_id"]],
            "status": "suspended",
            "reason": "Coverage pause",
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "suspended"
    assert updated["effective_status"] == "suspended"
    assert set(updated["role_ids"]) == {setup["role_a_id"], setup["role_b_id"]}
    assert updated["revocation_reason"] == "Coverage pause"

    active_only_resp = await client.get(
        f"/v1/memberships/user/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert active_only_resp.status_code == 200
    assert active_only_resp.json() == []

    include_inactive_resp = await client.get(
        f"/v1/memberships/user/{target_user['id']}?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert include_inactive_resp.status_code == 200
    suspended_memberships = include_inactive_resp.json()
    assert len(suspended_memberships) == 1
    assert suspended_memberships[0]["status"] == "suspended"

    revoke_resp = await client.delete(
        f"/v1/memberships/{setup['child_id']}/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert revoke_resp.status_code == 204

    revoked_resp = await client.get(
        f"/v1/memberships/user/{target_user['id']}?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert revoked_resp.status_code == 200
    revoked_memberships = revoked_resp.json()
    assert len(revoked_memberships) == 1
    revoked = revoked_memberships[0]
    assert revoked["status"] == "revoked"
    assert revoked["effective_status"] == "revoked"
    assert revoked["revoked_at"] is not None

    reactivate_resp = await client.patch(
        f"/v1/memberships/{setup['child_id']}/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "active", "reason": None},
    )
    assert reactivate_resp.status_code == 200
    reactivated = reactivate_resp.json()
    assert reactivated["status"] == "active"
    assert reactivated["effective_status"] == "active"
    assert reactivated["revoked_at"] is None
    assert reactivated["revocation_reason"] is None
    assert set(reactivated["role_ids"]) == {setup["role_a_id"], setup["role_b_id"]}

    final_active_resp = await client.get(
        f"/v1/memberships/user/{target_user['id']}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert final_active_resp.status_code == 200
    final_payload = final_active_resp.json()
    assert len(final_payload) == 1
    assert final_payload[0]["status"] == "active"
