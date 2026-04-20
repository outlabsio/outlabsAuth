import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_auth_router, get_memberships_router, get_roles_router, get_users_router
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
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    app.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
    app.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_user(auth_instance: EnterpriseRBAC) -> dict:
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-audit-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Admin",
            last_name="Audit",
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_status_delete_and_restore(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"audit-root-{uuid.uuid4().hex[:8]}",
            display_name="Audit Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"audit-target-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Audit",
            last_name="Target",
            root_entity_id=root.id,
        )
        await session.commit()
        user_id = str(user.id)

    suspend_resp = await client.patch(
        f"/v1/users/{user_id}/status",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "status": "suspended",
            "reason": "policy review",
            "suspended_until": "2026-03-25T12:00:00Z",
        },
    )
    assert suspend_resp.status_code == 200, suspend_resp.text

    delete_resp = await client.delete(
        f"/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert delete_resp.status_code == 204, delete_resp.text

    restore_resp = await client.post(
        f"/v1/users/{user_id}/restore",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert restore_resp.status_code == 200, restore_resp.text

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]

    assert [item["event_type"] for item in items][:3] == [
        "user.restored",
        "user.deleted",
        "user.status_changed",
    ]

    restored_event = items[0]
    assert restored_event["event_category"] == "status"
    assert restored_event["actor_user_id"] == admin_user["id"]
    assert restored_event["before"]["status"] == "deleted"
    assert restored_event["after"]["status"] == "active"
    assert restored_event["after"]["deleted_at"] is None

    deleted_event = items[1]
    assert deleted_event["actor_user_id"] == admin_user["id"]
    assert deleted_event["before"]["status"] == "suspended"
    assert deleted_event["after"]["status"] == "deleted"
    assert deleted_event["after"]["deleted_at"] is not None
    assert deleted_event["metadata"]["revoked_refresh_token_count"] == 0

    status_event = items[2]
    assert status_event["reason"] == "policy review"
    assert status_event["before"]["status"] == "active"
    assert status_event["after"]["status"] == "suspended"
    assert status_event["after"]["suspended_until"] == "2026-03-25T12:00:00+00:00"

    filtered_resp = await client.get(
        f"/v1/users/{user_id}/audit-events?event_type=user.deleted",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert filtered_resp.status_code == 200, filtered_resp.text
    filtered_items = filtered_resp.json()["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["event_type"] == "user.deleted"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_superuser_privilege_changes(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"superuser-audit-{uuid.uuid4().hex[:8]}@example.com",
            password="StartPass123!",
            first_name="Privilege",
            last_name="Audit",
        )
        await session.commit()
        user_id = str(user.id)

    grant_resp = await client.patch(
        f"/v1/users/{user_id}/superuser",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"is_superuser": True, "reason": "backup platform owner"},
    )
    assert grant_resp.status_code == 200, grant_resp.text
    assert grant_resp.json()["is_superuser"] is True

    revoke_resp = await client.patch(
        f"/v1/users/{user_id}/superuser",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"is_superuser": False, "reason": "rotation complete"},
    )
    assert revoke_resp.status_code == 200, revoke_resp.text
    assert revoke_resp.json()["is_superuser"] is False

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events?category=privilege",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]

    assert [item["event_type"] for item in items] == [
        "user.superuser_revoked",
        "user.superuser_granted",
    ]

    revoked_event = items[0]
    assert revoked_event["event_category"] == "privilege"
    assert revoked_event["actor_user_id"] == admin_user["id"]
    assert revoked_event["reason"] == "rotation complete"
    assert revoked_event["before"]["is_superuser"] is True
    assert revoked_event["after"]["is_superuser"] is False
    assert revoked_event["metadata"]["changed_fields"] == ["is_superuser"]

    granted_event = items[1]
    assert granted_event["event_category"] == "privilege"
    assert granted_event["actor_user_id"] == admin_user["id"]
    assert granted_event["reason"] == "backup platform owner"
    assert granted_event["before"]["is_superuser"] is False
    assert granted_event["after"]["is_superuser"] is True
    assert granted_event["metadata"]["changed_fields"] == ["is_superuser"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_profile_email_and_password_changes(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"profile-audit-{uuid.uuid4().hex[:8]}@example.com",
            password="StartPass123!",
            first_name="Before",
            last_name="Person",
        )
        await session.commit()
        user_id = str(user.id)

    update_resp = await client.patch(
        f"/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "email": f"profile-updated-{uuid.uuid4().hex[:8]}@example.com",
            "first_name": "After",
            "last_name": "Updated",
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    reset_resp = await client.patch(
        f"/v1/users/{user_id}/password",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"new_password": "ChangedPass123!"},
    )
    assert reset_resp.status_code == 204, reset_resp.text

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]
    events_by_type = {item["event_type"]: item for item in items}

    assert "user.email_changed" in events_by_type
    assert "user.profile_updated" in events_by_type
    assert "user.password_changed" in events_by_type

    email_event = events_by_type["user.email_changed"]
    assert email_event["event_category"] == "profile"
    assert email_event["actor_user_id"] == admin_user["id"]
    assert email_event["before"]["email"] == user.email
    assert email_event["after"]["email"] == update_resp.json()["email"]
    assert email_event["after"]["email_verified"] is False

    profile_event = events_by_type["user.profile_updated"]
    assert profile_event["actor_user_id"] == admin_user["id"]
    assert profile_event["before"]["first_name"] == "Before"
    assert profile_event["after"]["first_name"] == "After"
    assert profile_event["metadata"]["changed_fields"] == ["first_name", "last_name"]

    password_event = events_by_type["user.password_changed"]
    assert password_event["event_category"] == "credential"
    assert password_event["actor_user_id"] == admin_user["id"]
    assert password_event["metadata"]["revoked_refresh_token_count"] == 0
    assert password_event["before"]["failed_login_attempts"] == 0
    assert password_event["after"]["locked_until"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_login_and_password_reset_lifecycle(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"auth-audit-{uuid.uuid4().hex[:8]}@example.com",
            password="AuthPass123!",
            first_name="Auth",
            last_name="Audit",
        )
        await session.commit()
        user_id = str(user.id)
        user_email = user.email

    captured: dict[str, str] = {}

    async def capture_reset(user_obj, token, request=None):
        captured["token"] = token

    auth_instance.user_service.on_after_forgot_password = capture_reset

    failed_login = await client.post(
        "/v1/auth/login",
        json={"email": user_email, "password": "WrongPass123!"},
    )
    assert failed_login.status_code == 401, failed_login.text

    successful_login = await client.post(
        "/v1/auth/login",
        json={"email": user_email, "password": "AuthPass123!"},
    )
    assert successful_login.status_code == 200, successful_login.text

    forgot_resp = await client.post(
        "/v1/auth/forgot-password",
        json={"email": user_email},
    )
    assert forgot_resp.status_code == 204, forgot_resp.text
    assert captured["token"]

    reset_resp = await client.post(
        "/v1/auth/reset-password",
        json={"token": captured["token"], "new_password": "ResetPass123!"},
    )
    assert reset_resp.status_code == 204, reset_resp.text

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]
    events_by_type = {item["event_type"]: item for item in items}

    assert "user.login_failed" in events_by_type
    assert "user.login" in events_by_type
    assert "user.password_reset_requested" in events_by_type
    assert "user.password_reset_completed" in events_by_type

    login_failed_event = events_by_type["user.login_failed"]
    assert login_failed_event["event_category"] == "authentication"
    assert login_failed_event["before"]["failed_login_attempts"] == 0
    assert login_failed_event["after"]["failed_login_attempts"] == 1
    assert login_failed_event["metadata"]["failure_reason"] == "invalid_password"

    login_event = events_by_type["user.login"]
    assert login_event["event_category"] == "authentication"
    assert login_event["metadata"]["auth_method"] == "password"
    assert login_event["after"]["last_login"] is not None

    reset_requested_event = events_by_type["user.password_reset_requested"]
    assert reset_requested_event["event_category"] == "credential"
    assert reset_requested_event["after"]["password_reset_requested"] is True

    reset_completed_event = events_by_type["user.password_reset_completed"]
    assert reset_completed_event["event_category"] == "credential"
    assert reset_completed_event["metadata"]["revoked_refresh_token_count"] == 1
    assert reset_completed_event["after"]["password_reset_expires"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_invite_resend_and_accept_lifecycle(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    invite_tokens: list[str] = []

    async def capture_invite(user_obj, token, request=None):
        invite_tokens.append(token)

    auth_instance.user_service.on_after_invite = capture_invite

    invite_email = f"invite-audit-{uuid.uuid4().hex[:8]}@example.com"
    invite_resp = await client.post(
        "/v1/auth/invite",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "email": invite_email,
            "first_name": "Invited",
            "last_name": "Audit",
        },
    )
    assert invite_resp.status_code == 201, invite_resp.text
    invited_user = invite_resp.json()
    user_id = invited_user["id"]
    assert invite_tokens

    resend_resp = await client.post(
        f"/v1/users/{user_id}/resend-invite",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resend_resp.status_code == 200, resend_resp.text
    assert len(invite_tokens) == 2

    accept_resp = await client.post(
        "/v1/auth/accept-invite",
        json={
            "token": invite_tokens[-1],
            "new_password": "InviteAccept123!",
        },
    )
    assert accept_resp.status_code == 200, accept_resp.text

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]
    events_by_type = {item["event_type"]: item for item in items}

    assert "user.invited" in events_by_type
    assert "user.invite_resent" in events_by_type
    assert "user.invite_accepted" in events_by_type
    assert "user.login" in events_by_type

    invited_event = events_by_type["user.invited"]
    assert invited_event["event_category"] == "invitation"
    assert invited_event["actor_user_id"] == admin_user["id"]
    assert invited_event["after"]["status"] == "invited"

    resent_event = events_by_type["user.invite_resent"]
    assert resent_event["event_category"] == "invitation"
    assert resent_event["actor_user_id"] == admin_user["id"]
    assert resent_event["after"]["invite_token_expires"] is not None

    accepted_event = events_by_type["user.invite_accepted"]
    assert accepted_event["event_category"] == "invitation"
    assert accepted_event["before"]["status"] == "invited"
    assert accepted_event["after"]["status"] == "active"
    assert accepted_event["after"]["email_verified"] is True

    login_event = events_by_type["user.login"]
    assert login_event["event_category"] == "authentication"
    assert login_event["metadata"]["auth_method"] == "invite_accept"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_direct_role_assign_and_revoke(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"role-audit-root-{uuid.uuid4().hex[:8]}",
            display_name="Role Audit Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"role-audit-target-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Role",
            last_name="Audit",
            root_entity_id=root.id,
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"role-audit-{uuid.uuid4().hex[:8]}",
            display_name="Role Audit Assignment",
            is_global=False,
            root_entity_id=root.id,
        )
        await session.commit()
        user_id = str(user.id)
        role_id = str(role.id)
        root_id = str(root.id)

    assign_resp = await client.post(
        f"/v1/users/{user_id}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": role_id},
    )
    assert assign_resp.status_code == 201, assign_resp.text

    revoke_resp = await client.delete(
        f"/v1/users/{user_id}/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert revoke_resp.status_code == 204, revoke_resp.text

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events?category=role",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]

    assert [item["event_type"] for item in items] == [
        "user.role_revoked",
        "user.role_assigned",
    ]

    revoked_event = items[0]
    assert revoked_event["role_id"] == role_id
    assert revoked_event["root_entity_id"] == root_id
    assert revoked_event["before"]["status"] == "active"
    assert revoked_event["after"]["status"] == "revoked"
    assert revoked_event["metadata"]["role_display_name"] == "Role Audit Assignment"
    assert revoked_event["metadata"]["role_root_entity_id"] == root_id

    assigned_event = items[1]
    assert assigned_event["role_id"] == role_id
    assert assigned_event["after"]["status"] == "active"
    assert assigned_event["metadata"]["reactivated_existing_membership"] is False
    assert assigned_event["metadata"]["role_name"].startswith("role-audit-")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_delete_records_direct_role_revocation_audit_event(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"role-delete-root-{uuid.uuid4().hex[:8]}",
            display_name="Role Delete Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"role-delete-target-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Delete",
            last_name="Role",
            root_entity_id=root.id,
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"role-delete-audit-{uuid.uuid4().hex[:8]}",
            display_name="Role Delete Audit",
            is_global=False,
            root_entity_id=root.id,
        )
        await session.commit()
        user_id = str(user.id)
        role_id = str(role.id)

    assign_resp = await client.post(
        f"/v1/users/{user_id}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": role_id},
    )
    assert assign_resp.status_code == 201, assign_resp.text

    delete_resp = await client.delete(
        f"/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert delete_resp.status_code == 204, delete_resp.text

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events?category=role",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]

    assert [item["event_type"] for item in items] == [
        "user.role_revoked",
        "user.role_assigned",
    ]
    assert items[0]["event_source"] == "role_service.revoke_all_roles_for_user"
    assert items[0]["reason"] == "User deleted"
    assert items[0]["after"]["status"] == "revoked"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_membership_lifecycle_changes(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"membership-audit-root-{unique}",
            display_name="Membership Audit Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"membership-audit-team-{unique}",
            display_name="Membership Audit Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role_a = await auth_instance.role_service.create_role(
            session=session,
            name=f"membership-audit-role-a-{unique}",
            display_name="Membership Audit Role A",
            is_global=False,
            root_entity_id=root.id,
        )
        role_b = await auth_instance.role_service.create_role(
            session=session,
            name=f"membership-audit-role-b-{unique}",
            display_name="Membership Audit Role B",
            is_global=False,
            root_entity_id=root.id,
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"membership-audit-{unique}@example.com",
            password="TestPass123!",
            first_name="Membership",
            last_name="Audit",
            root_entity_id=root.id,
        )
        await session.commit()
        user_id = str(user.id)
        team_id = str(team.id)
        role_a_id = str(role_a.id)
        role_b_id = str(role_b.id)

    create_resp = await client.post(
        "/v1/memberships/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "entity_id": team_id,
            "user_id": user_id,
            "role_ids": [role_a_id],
        },
    )
    assert create_resp.status_code == 201, create_resp.text

    update_resp = await client.patch(
        f"/v1/memberships/{team_id}/{user_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "role_ids": [role_a_id, role_b_id],
            "valid_until": "2026-04-01T12:00:00Z",
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    suspend_resp = await client.patch(
        f"/v1/memberships/{team_id}/{user_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "status": "suspended",
            "reason": "Temporary leave",
        },
    )
    assert suspend_resp.status_code == 200, suspend_resp.text

    reactivate_resp = await client.patch(
        f"/v1/memberships/{team_id}/{user_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "status": "active",
            "reason": None,
        },
    )
    assert reactivate_resp.status_code == 200, reactivate_resp.text

    revoke_resp = await client.delete(
        f"/v1/memberships/{team_id}/{user_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert revoke_resp.status_code == 204, revoke_resp.text

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events?category=membership",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]

    assert [item["event_type"] for item in items][:5] == [
        "user.membership_revoked",
        "user.membership_reactivated",
        "user.membership_suspended",
        "user.membership_updated",
        "user.membership_created",
    ]

    revoked_event = items[0]
    assert revoked_event["actor_user_id"] == admin_user["id"]
    assert revoked_event["event_source"] == "membership_service.remove_member"
    assert revoked_event["entity_id"] == team_id
    assert revoked_event["before"]["status"] == "active"
    assert revoked_event["after"]["status"] == "revoked"
    assert revoked_event["metadata"]["entity_display_name"] == "Membership Audit Team"
    assert revoked_event["metadata"]["entity_path"] == ["Membership Audit Root", "Membership Audit Team"]

    reactivated_event = items[1]
    assert reactivated_event["actor_user_id"] == admin_user["id"]
    assert reactivated_event["before"]["status"] == "suspended"
    assert reactivated_event["after"]["status"] == "active"

    suspended_event = items[2]
    assert suspended_event["actor_user_id"] == admin_user["id"]
    assert suspended_event["reason"] == "Temporary leave"
    assert suspended_event["before"]["status"] == "active"
    assert suspended_event["after"]["status"] == "suspended"

    updated_event = items[3]
    assert updated_event["actor_user_id"] == admin_user["id"]
    assert updated_event["before"]["role_names"] == ["Membership Audit Role A"]
    assert set(updated_event["after"]["role_names"]) == {
        "Membership Audit Role A",
        "Membership Audit Role B",
    }
    assert updated_event["after"]["valid_until"] == "2026-04-01T12:00:00+00:00"

    created_event = items[4]
    assert created_event["actor_user_id"] == admin_user["id"]
    assert created_event["after"]["status"] == "active"
    assert created_event["metadata"]["history_event_type"] == "created"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_audit_events_capture_membership_entity_archived(
    auth_instance: EnterpriseRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"membership-archive-root-{unique}",
            display_name="Membership Archive Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"membership-archive-team-{unique}",
            display_name="Membership Archive Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"membership-archive-role-{unique}",
            display_name="Membership Archive Role",
            is_global=False,
            root_entity_id=root.id,
        )
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"membership-archive-{unique}@example.com",
            password="TestPass123!",
            first_name="Membership",
            last_name="Archive",
            root_entity_id=root.id,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=user.id,
            role_ids=[role.id],
            joined_by_id=uuid.UUID(admin_user["id"]),
        )
        await session.commit()
        user_id = str(user.id)
        team_id = str(team.id)

    async with auth_instance.get_session() as session:
        await auth_instance.entity_service.delete_entity(
            session=session,
            entity_id=uuid.UUID(team_id),
            deleted_by_id=uuid.UUID(admin_user["id"]),
        )
        await session.commit()

    audit_resp = await client.get(
        f"/v1/users/{user_id}/audit-events?category=membership&event_type=user.membership_entity_archived",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    items = audit_resp.json()["items"]
    assert len(items) == 1

    archived_event = items[0]
    assert archived_event["actor_user_id"] == admin_user["id"]
    assert archived_event["event_source"] == "entity_service.delete_entity"
    assert archived_event["reason"] == "Entity 'Membership Archive Team' archived"
    assert archived_event["before"]["status"] == "active"
    assert archived_event["after"]["status"] == "revoked"
    assert archived_event["metadata"]["entity_display_name"] == "Membership Archive Team"
    assert archived_event["metadata"]["entity_path"] == [
        "Membership Archive Root",
        "Membership Archive Team",
    ]
    assert archived_event["metadata"]["history_event_type"] == "entity_archived"
