import uuid
from datetime import timedelta, timezone
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC, SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_auth_router, get_memberships_router, get_users_router
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def enterprise_auth_instance(test_engine) -> EnterpriseRBAC:
    """Create EnterpriseRBAC instance for auth and user edge-case coverage."""
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
async def enterprise_app(enterprise_auth_instance: EnterpriseRBAC) -> FastAPI:
    """Create FastAPI app with auth, users, and memberships routes."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(enterprise_auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(enterprise_auth_instance, prefix="/v1/users"))
    app.include_router(get_memberships_router(enterprise_auth_instance, prefix="/v1/memberships"))
    return app


@pytest_asyncio.fixture
async def enterprise_client(enterprise_app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client."""
    transport = httpx.ASGITransport(app=enterprise_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def enterprise_admin(enterprise_auth_instance: EnterpriseRBAC) -> dict:
    """Create a superuser admin and return tokenized credentials."""
    async with enterprise_auth_instance.get_session() as session:
        admin = await enterprise_auth_instance.user_service.create_user(
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
            secret_key=enterprise_auth_instance.config.secret_key,
            algorithm=enterprise_auth_instance.config.algorithm,
            audience=enterprise_auth_instance.config.jwt_audience,
        )

        return {
            "id": str(admin.id),
            "email": admin.email,
            "password": "AdminPass123!",
            "token": token,
        }


async def _create_user(auth_instance: EnterpriseRBAC, *, prefix: str = "user", password: str = "TestPass123!") -> dict:
    """Create a standard active user for tests."""
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
            password=password,
            first_name="Test",
            last_name="User",
            is_superuser=False,
        )
        await session.commit()
        return {"id": str(user.id), "email": user.email, "password": password}


@pytest_asyncio.fixture
async def verification_auth_instance(test_engine) -> SimpleRBAC:
    """Create SimpleRBAC instance for verified-login coverage."""
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def verification_app(verification_auth_instance: SimpleRBAC) -> FastAPI:
    """Create FastAPI app with login verification enforced."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(
        get_auth_router(
            verification_auth_instance,
            prefix="/v1/auth",
            requires_verification=True,
        )
    )
    return app


@pytest_asyncio.fixture
async def verification_client(verification_app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client for verification tests."""
    transport = httpx.ASGITransport(app=verification_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_config_returns_expected_features_and_permissions(
    enterprise_client: httpx.AsyncClient,
    enterprise_auth_instance: EnterpriseRBAC,
):
    """Cover the auth runtime config contract consumed by admin UIs."""
    permission_name = f"config{uuid.uuid4().hex[:6]}:read"
    async with enterprise_auth_instance.get_session() as session:
        await enterprise_auth_instance.permission_service.create_permission(
            session,
            name=permission_name,
            display_name="Config Read",
        )
        await session.commit()

    response = await enterprise_client.get("/v1/auth/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["preset"] == "EnterpriseRBAC"
    assert payload["features"]["entity_hierarchy"] is True
    assert payload["features"]["tree_permissions"] is True
    assert payload["features"]["invitations"] is True
    assert payload["features"]["magic_links"] is False
    assert payload["features"]["access_codes"] is False
    assert payload["auth_methods"] == {"password": True, "magic_link": False, "access_code": False}
    assert permission_name in payload["available_permissions"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invite_with_entity_membership_can_be_accepted_and_activated(
    enterprise_client: httpx.AsyncClient,
    enterprise_auth_instance: EnterpriseRBAC,
    enterprise_admin: dict,
):
    """Cover invite-with-membership and accept-invite auto-login end to end."""
    captured: dict[str, str] = {}

    async def capture_invite(user, token, request=None):
        captured["token"] = token

    enterprise_auth_instance.user_service.on_after_invite = capture_invite

    async with enterprise_auth_instance.get_session() as session:
        root = await enterprise_auth_instance.entity_service.create_entity(
            session=session,
            name=f"root-{uuid.uuid4().hex[:8]}",
            display_name="Invite Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await enterprise_auth_instance.entity_service.create_entity(
            session=session,
            name=f"team-{uuid.uuid4().hex[:8]}",
            display_name="Invite Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role = await enterprise_auth_instance.role_service.create_role(
            session=session,
            name=f"invite-role-{uuid.uuid4().hex[:8]}",
            display_name="Invite Role",
            root_entity_id=root.id,
            is_global=False,
        )
        await session.commit()

    invite_email = f"invited-{uuid.uuid4().hex[:8]}@example.com"
    invite_response = await enterprise_client.post(
        "/v1/auth/invite",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
        json={
            "email": invite_email,
            "first_name": "Invited",
            "last_name": "Member",
            "entity_id": str(team.id),
            "role_ids": [str(role.id)],
        },
    )
    assert invite_response.status_code == 201, invite_response.text
    invited = invite_response.json()
    assert invited["status"] == "invited"
    assert captured["token"]

    membership_response = await enterprise_client.get(
        f"/v1/memberships/user/{invited['id']}?include_inactive=true",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
    )
    assert membership_response.status_code == 200, membership_response.text
    memberships = membership_response.json()
    assert len(memberships) == 1
    assert memberships[0]["entity_id"] == str(team.id)
    assert memberships[0]["role_ids"] == [str(role.id)]

    accept_response = await enterprise_client.post(
        "/v1/auth/accept-invite",
        json={"token": captured["token"], "new_password": "AcceptedPass123!"},
    )
    assert accept_response.status_code == 200, accept_response.text
    accepted = accept_response.json()
    assert accepted["access_token"]
    assert accepted["refresh_token"]

    async with enterprise_auth_instance.get_session() as session:
        user = await enterprise_auth_instance.user_service.get_user_by_email(session, invite_email)
        assert user is not None
        assert getattr(user.status, "value", user.status) == "active"
        assert user.email_verified is True
        assert user.invite_token is None
        assert user.invite_token_expires is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow_uses_captured_reset_token(
    enterprise_client: httpx.AsyncClient,
    enterprise_auth_instance: EnterpriseRBAC,
):
    """Cover forgot-password and reset-password with the real token lifecycle."""
    user = await _create_user(enterprise_auth_instance, prefix="forgot")
    captured: dict[str, str] = {}

    async def capture_reset(user_obj, token, request=None):
        captured["token"] = token

    enterprise_auth_instance.user_service.on_after_forgot_password = capture_reset

    forgot_response = await enterprise_client.post(
        "/v1/auth/forgot-password",
        json={"email": user["email"]},
    )
    assert forgot_response.status_code == 204
    assert captured["token"]

    async with enterprise_auth_instance.get_session() as session:
        stored_user = await enterprise_auth_instance.user_service.get_user_by_email(session, user["email"])
        assert stored_user is not None
        assert stored_user.password_reset_token is not None
        assert stored_user.password_reset_expires is not None

    reset_response = await enterprise_client.post(
        "/v1/auth/reset-password",
        json={"token": captured["token"], "new_password": "ResetFlow123!"},
    )
    assert reset_response.status_code == 204, reset_response.text

    login_response = await enterprise_client.post(
        "/v1/auth/login",
        json={"email": user["email"], "password": "ResetFlow123!"},
    )
    assert login_response.status_code == 200, login_response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verified_login_uses_email_verified_field(
    verification_client: httpx.AsyncClient,
    verification_auth_instance: SimpleRBAC,
):
    """Cover the verified-login branch against the actual email_verified field."""
    async with verification_auth_instance.get_session() as session:
        user = await verification_auth_instance.user_service.create_user(
            session=session,
            email=f"verify-{uuid.uuid4().hex[:8]}@example.com",
            password="VerifyPass123!",
            first_name="Verify",
            last_name="Me",
        )
        await session.commit()
        email = user.email
        user_id = user.id

    rejected_response = await verification_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "VerifyPass123!"},
    )
    assert rejected_response.status_code == 403, rejected_response.text
    assert "Email verification required" in rejected_response.text

    async with verification_auth_instance.get_session() as session:
        user = await verification_auth_instance.user_service.get_user_by_id(session, user_id)
        user.email_verified = True
        await session.commit()

    accepted_response = await verification_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "VerifyPass123!"},
    )
    assert accepted_response.status_code == 200, accepted_response.text
    payload = accepted_response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_search_update_me_and_permission_sources_contract(
    enterprise_client: httpx.AsyncClient,
    enterprise_auth_instance: EnterpriseRBAC,
    enterprise_admin: dict,
):
    """Cover user search, self-update, invalid status filtering, and permission source readback."""
    target_user = await _create_user(enterprise_auth_instance, prefix="searchable")

    async with enterprise_auth_instance.get_session() as session:
        permission = await enterprise_auth_instance.permission_service.create_permission(
            session,
            name=f"reports{uuid.uuid4().hex[:6]}:view",
            display_name="Reports View",
        )
        role = await enterprise_auth_instance.role_service.create_role(
            session=session,
            name=f"perm-role-{uuid.uuid4().hex[:8]}",
            display_name="Permission Role",
        )
        await enterprise_auth_instance.role_service.add_permissions(session, role.id, [permission.id])
        await enterprise_auth_instance.role_service.assign_role_to_user(
            session,
            UUID(target_user["id"]),
            role.id,
            assigned_by_id=UUID(enterprise_admin["id"]),
            valid_from=None,
            valid_until=None,
        )
        await session.commit()

    search_response = await enterprise_client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
        params={"search": "searchable", "page": 1, "limit": 5},
    )
    assert search_response.status_code == 200, search_response.text
    search_payload = search_response.json()
    assert search_payload["total"] >= 1
    assert any(item["id"] == target_user["id"] for item in search_payload["items"])

    invalid_status_response = await enterprise_client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
        params={"status": "not-a-real-status"},
    )
    assert invalid_status_response.status_code == 400
    assert "Invalid status" in invalid_status_response.text

    update_me_response = await enterprise_client.patch(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
        json={"first_name": "Self", "last_name": "Updated"},
    )
    assert update_me_response.status_code == 200, update_me_response.text
    me_payload = update_me_response.json()
    assert me_payload["first_name"] == "Self"
    assert me_payload["last_name"] == "Updated"

    permissions_response = await enterprise_client.get(
        f"/v1/users/{target_user['id']}/permissions",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
    )
    assert permissions_response.status_code == 200, permissions_response.text
    permission_sources = permissions_response.json()
    assert len(permission_sources) == 1
    assert permission_sources[0]["source"] == "role"
    assert permission_sources[0]["source_name"] == role.name
    assert permission_sources[0]["permission"]["name"] == permission.name


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_role_and_status_validation_error_paths(
    enterprise_client: httpx.AsyncClient,
    enterprise_auth_instance: EnterpriseRBAC,
    enterprise_admin: dict,
):
    """Cover remaining high-value 404 and validation branches in the user router."""
    target_user = await _create_user(enterprise_auth_instance, prefix="edge")
    missing_role_id = str(uuid.uuid4())

    assign_missing_role_response = await enterprise_client.post(
        f"/v1/users/{target_user['id']}/roles",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
        json={"role_id": missing_role_id},
    )
    assert assign_missing_role_response.status_code == 404
    assert "Role not found" in assign_missing_role_response.text

    revoke_missing_role_response = await enterprise_client.delete(
        f"/v1/users/{target_user['id']}/roles/{missing_role_id}",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
    )
    assert revoke_missing_role_response.status_code == 404
    assert "User does not have this role assigned" in revoke_missing_role_response.text

    invalid_suspension_response = await enterprise_client.patch(
        f"/v1/users/{target_user['id']}/status",
        headers={"Authorization": f"Bearer {enterprise_admin['token']}"},
        json={"status": "suspended", "suspended_until": "not-an-iso-datetime"},
    )
    assert invalid_suspension_response.status_code == 400
    assert "Invalid suspended_until format" in invalid_suspension_response.text
