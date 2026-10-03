"""
0.1.0a35 contract additions for admin consoles (WP-24).

Additive fields and endpoints only: capability discovery (password policy,
access-code length, registration mode), current-session marking, paginated
member details, names on /memberships/me, definition history, has_password,
and system-integration grantable scopes.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC, SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import (
    get_auth_router,
    get_integration_principals_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.routers.oauth import oauth_callback
from outlabs_auth.utils.jwt import create_access_token

SECRET = "test-secret-key-do-not-use-in-production-12345678"
PASSWORD = "TestPass123!"


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _headers(auth, user_id: Any) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user_id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )
    return {"Authorization": f"Bearer {token}"}


def _app(auth) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    app.include_router(get_integration_principals_router(auth, prefix="/v1/admin"))
    if auth.config.enable_entity_hierarchy:
        app.include_router(get_memberships_router(auth, prefix="/v1/memberships"))
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=20.0)


async def _enterprise(test_engine, **overrides) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key=SECRET,
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        **overrides,
    )
    await auth.initialize()
    return auth


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = await _enterprise(test_engine)
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def client(auth_instance) -> httpx.AsyncClient:
    async with _client(_app(auth_instance)) as http_client:
        yield http_client


async def _superuser(auth) -> Any:
    async with auth.get_session() as session:
        user = await auth.user_service.create_user(
            session=session,
            email=f"super-{_suffix()}@example.com",
            password=PASSWORD,
            is_superuser=True,
        )
        await session.commit()
    return user


# ---------------------------------------------------------------------------
# /auth/config: password policy, access-code length, registration mode
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_config_publishes_account_policies(client, auth_instance):
    response = await client.get("/v1/auth/config")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["registration_mode"] == "open"
    assert body["features"]["registration"] is True
    assert body["features"]["self_service_email_change"] is False
    assert body["self_service_email_change"] is False
    assert body["access_code_length"] == 6
    policy = body["password_policy"]
    assert policy == {
        "min_length": 8,
        "max_length": 128,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_digit": True,
        "require_special_char": True,
        "special_characters": '!@#$%^&*(),.?":{}|<>\\',
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_closed_registration_is_advertised_and_enforced(test_engine):
    auth = await _enterprise(
        test_engine,
        enable_registration=False,
        access_code_length=8,
        password_min_length=12,
    )
    try:
        async with _client(_app(auth)) as http_client:
            config = (await http_client.get("/v1/auth/config")).json()
            assert config["registration_mode"] == "invite_only"
            assert config["access_code_length"] == 8
            assert config["password_policy"]["min_length"] == 12

            register = await http_client.post(
                "/v1/auth/register",
                json={"email": f"nope-{_suffix()}@example.com", "password": "LongEnough123!"},
            )
            assert register.status_code == 403, register.text
            assert register.json()["details"]["code"] == "registration_disabled"

        async with auth.get_session() as session:
            with pytest.raises(Exception, match="No account found"):
                await oauth_callback(
                    auth=auth,
                    session=session,
                    provider="github",
                    access_token="provider-token",
                    refresh_token=None,
                    expires_at=None,
                    account_id=f"gh-{_suffix()}",
                    account_email=f"oauth-new-{_suffix()}@example.com",
                    account_email_verified=True,
                    associate_by_email=False,
                    is_verified_by_default=True,
                    require_existing_user=False,
                )
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registration_mode_closed_when_invitations_disabled(test_engine):
    auth = await _enterprise(test_engine, enable_registration=False, enable_invitations=False)
    try:
        async with _client(_app(auth)) as http_client:
            assert (await http_client.get("/v1/auth/config")).json()["registration_mode"] == "closed"
    finally:
        await auth.shutdown()


# ---------------------------------------------------------------------------
# Sessions: is_current + keep_current (F-157 / F-030)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sessions_mark_current_and_can_keep_it(client, auth_instance):
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session, email=f"sessions-{_suffix()}@example.com", password=PASSWORD
        )
        await session.commit()

    first = (await client.post("/v1/auth/login", json={"email": user.email, "password": PASSWORD})).json()
    second = (await client.post("/v1/auth/login", json={"email": user.email, "password": PASSWORD})).json()
    headers = {"Authorization": f"Bearer {second['access_token']}"}

    sessions = await client.get("/v1/users/me/sessions", headers=headers)
    assert sessions.status_code == 200, sessions.text
    rows = sessions.json()
    assert len(rows) == 2
    assert sorted(row["is_current"] for row in rows) == [False, True]

    # Rotation keeps the session identity.
    refreshed = (await client.post("/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})).json()
    headers = {"Authorization": f"Bearer {refreshed['access_token']}"}
    rows = (await client.get("/v1/users/me/sessions", headers=headers)).json()
    assert sum(1 for row in rows if row["is_current"]) == 1

    # Sign out other devices: only the calling session survives.
    keep = await client.delete("/v1/users/me/sessions", headers=headers, params={"keep_current": "true"})
    assert keep.status_code == 204, keep.text
    rows = (await client.get("/v1/users/me/sessions", headers=headers)).json()
    assert len(rows) == 1 and rows[0]["is_current"] is True
    stale = await client.post("/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert stale.status_code == 401

    # Tokens without a sid cannot ask to keep "the current" session.
    legacy = _headers(auth_instance, user.id)
    refused = await client.delete("/v1/users/me/sessions", headers=legacy, params={"keep_current": "true"})
    assert refused.status_code == 400
    assert all(row["is_current"] is False for row in (await client.get("/v1/users/me/sessions", headers=legacy)).json())


# ---------------------------------------------------------------------------
# Memberships: paginated details with totals + names on /me (F-024 / F-103)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_member_details_page_has_totals_search_and_names(client, auth_instance):
    admin = await _superuser(auth_instance)
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"org-{_suffix()}",
            display_name="Org",
            slug=f"org-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"member-{_suffix()}",
            display_name="Member",
            root_entity_id=root.id,
            is_global=False,
        )
        members = []
        for index in range(5):
            member = await auth_instance.user_service.create_user(
                session=session,
                email=f"member{index}-{_suffix()}@example.com",
                password=PASSWORD,
                first_name="Findme" if index == 3 else "Other",
            )
            await auth_instance.membership_service.add_member(
                session, entity_id=root.id, user_id=member.id, role_ids=[role.id]
            )
            members.append(member)
        await session.commit()

    headers = _headers(auth_instance, admin.id)
    page = await client.get(f"/v1/memberships/entity/{root.id}/members", headers=headers, params={"limit": 2})
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] == 5 and body["pages"] == 3 and len(body["items"]) == 2
    second = await client.get(
        f"/v1/memberships/entity/{root.id}/members", headers=headers, params={"limit": 2, "page": 2}
    )
    assert not {row["id"] for row in body["items"]} & {row["id"] for row in second.json()["items"]}

    found = await client.get(f"/v1/memberships/entity/{root.id}/members", headers=headers, params={"search": "findme"})
    assert found.json()["total"] == 1
    assert found.json()["items"][0]["user_id"] == str(members[3].id)
    assert found.json()["items"][0]["updated_at"] is not None

    mine = await client.get("/v1/memberships/me", headers=_headers(auth_instance, members[0].id))
    assert mine.status_code == 200, mine.text
    row = mine.json()[0]
    assert row["entity_display_name"] == "Org"
    assert row["entity_type"] == "organization"
    assert row["role_names"] == [role.name]


# ---------------------------------------------------------------------------
# Definition history endpoints + has_password (F-092 / F-098)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_and_permission_history_and_has_password(client, auth_instance):
    admin = await _superuser(auth_instance)
    headers = _headers(auth_instance, admin.id)

    permission = await client.post(
        "/v1/permissions/", headers=headers, json={"name": f"doc:{_suffix()}", "display_name": "Doc"}
    )
    assert permission.status_code == 201, permission.text
    permission_id = permission.json()["id"]
    assert (
        await client.patch(f"/v1/permissions/{permission_id}", headers=headers, json={"display_name": "Doc 2"})
    ).status_code == 200

    history = await client.get(f"/v1/permissions/{permission_id}/history", headers=headers)
    assert history.status_code == 200, history.text
    assert history.json()["total"] >= 2
    newest = history.json()["items"][0]
    assert newest["definition_kind"] == "permission"
    assert newest["display_name"] == "Doc 2"
    assert newest["actor_user_id"] == str(admin.id)
    assert (await client.get(f"/v1/permissions/{uuid.uuid4()}/history", headers=headers)).status_code == 404

    role = await client.post(
        "/v1/roles/",
        headers=headers,
        json={"name": f"history-{_suffix()}", "display_name": "History", "is_global": True},
    )
    assert role.status_code == 201, role.text
    role_id = role.json()["id"]
    await client.patch(f"/v1/roles/{role_id}", headers=headers, json={"description": "changed"})
    role_history = await client.get(f"/v1/roles/{role_id}/history", headers=headers)
    assert role_history.status_code == 200, role_history.text
    assert role_history.json()["items"][0]["definition_kind"] == "role"
    assert role_history.json()["total"] >= 2

    me = await client.get("/v1/users/me", headers=headers)
    assert me.json()["has_password"] is True
    async with auth_instance.get_session() as session:
        invited, _ = await auth_instance.user_service.invite_user(session, f"invited-{_suffix()}@example.com")
        await session.commit()
    invited_view = await client.get(f"/v1/users/{invited.id}", headers=headers)
    assert invited_view.json()["has_password"] is False


# ---------------------------------------------------------------------------
# System-integration grantable scopes (F-079)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_integration_grantable_scopes_endpoints(client, auth_instance):
    admin = await _superuser(auth_instance)
    headers = _headers(auth_instance, admin.id)
    async with auth_instance.get_session() as session:
        for name in ("lead:read", "lead:create", "lead:operate", "api_key:create", "api_key:create_tree"):
            await auth_instance.permission_service.create_permission(session, name=name, display_name=name)
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"org-{_suffix()}",
            display_name="Org",
            slug=f"org-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        await session.commit()

    platform = await client.get("/v1/admin/system/integration-principals/grantable-scopes", headers=headers)
    assert platform.status_code == 200, platform.text
    body = platform.json()
    assert body["scope_kind"] == "platform_global"
    assert {"lead:read", "lead:create", "lead:operate"} <= set(body["grantable_scopes"])
    assert "create" in body["system_allowed_action_prefixes"]

    entity = await client.get(f"/v1/admin/entities/{root.id}/integration-principals/grantable-scopes", headers=headers)
    assert entity.status_code == 200, entity.text
    assert entity.json()["anchor_entity_id"] == str(root.id)
    assert "lead:create" in entity.json()["grantable_scopes"]

    # A non-superuser cannot query the platform-global envelope.
    async with auth_instance.get_session() as session:
        scoped = await auth_instance.user_service.create_user(
            session=session, email=f"scoped-{_suffix()}@example.com", password=PASSWORD, root_entity_id=root.id
        )
        await session.commit()
    denied = await client.get(
        "/v1/admin/system/integration-principals/grantable-scopes", headers=_headers(auth_instance, scoped.id)
    )
    assert denied.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_rbac_platform_grantable_scopes(test_engine):
    auth = SimpleRBAC(engine=test_engine, secret_key=SECRET, enable_token_cleanup=False)
    await auth.initialize()
    try:
        admin = await _superuser(auth)
        async with auth.get_session() as session:
            await auth.permission_service.create_permission(session, name="post:create", display_name="post")
            await auth.permission_service.create_permission(session, name="api_key:create", display_name="ak")
            await session.commit()
        async with _client(_app(auth)) as http_client:
            response = await http_client.get(
                "/v1/admin/system/integration-principals/grantable-scopes", headers=_headers(auth, admin.id)
            )
            assert response.status_code == 200, response.text
            assert "post:create" in response.json()["grantable_scopes"]
    finally:
        await auth.shutdown()
