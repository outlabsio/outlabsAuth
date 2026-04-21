import uuid
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_integration_principals_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def simple_auth_instance(test_engine) -> SimpleRBAC:
    """Create a SimpleRBAC instance with the same shared routers as the example app."""
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
async def simple_app(simple_auth_instance: SimpleRBAC) -> FastAPI:
    """Create FastAPI app with the simple example's mounted auth surface."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(simple_auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(simple_auth_instance, prefix="/v1/users"))
    app.include_router(get_roles_router(simple_auth_instance, prefix="/v1/roles"))
    app.include_router(get_permissions_router(simple_auth_instance, prefix="/v1/permissions"))
    app.include_router(get_api_keys_router(simple_auth_instance, prefix="/v1/api-keys"))
    app.include_router(
        get_integration_principals_router(simple_auth_instance, prefix="/v1/admin")
    )
    return app


@pytest_asyncio.fixture
async def simple_client(simple_app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client for the simple example contract tests."""
    transport = httpx.ASGITransport(app=simple_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def simple_admin(simple_auth_instance: SimpleRBAC) -> dict[str, str]:
    """Create a superuser admin and return bearer-token credentials."""
    async with simple_auth_instance.get_session() as session:
        admin = await simple_auth_instance.user_service.create_user(
            session=session,
            email=f"simple-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Simple",
            last_name="Admin",
            is_superuser=True,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin.id)},
            secret_key=simple_auth_instance.config.secret_key,
            algorithm=simple_auth_instance.config.algorithm,
            audience=simple_auth_instance.config.jwt_audience,
        )

        return {
            "id": str(admin.id),
            "token": token,
        }


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_auth_config_returns_expected_features_and_permissions(
    simple_client: httpx.AsyncClient,
    simple_auth_instance: SimpleRBAC,
):
    """SimpleRBAC should expose the shared auth-config contract consumed by the UI."""
    permission_name = f"simpleconfig{uuid.uuid4().hex[:6]}:read"
    async with simple_auth_instance.get_session() as session:
        await simple_auth_instance.permission_service.create_permission(
            session,
            name=permission_name,
            display_name="Simple Config Read",
        )
        await session.commit()

    response = await simple_client.get("/v1/auth/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["preset"] == "SimpleRBAC"
    assert payload["features"]["entity_hierarchy"] is False
    assert payload["features"]["context_aware_roles"] is False
    assert payload["features"]["abac"] is False
    assert payload["features"]["tree_permissions"] is False
    assert payload["features"]["api_keys"] is True
    assert payload["features"]["system_api_keys"] is True
    assert payload["features"]["user_status"] is True
    assert payload["features"]["activity_tracking"] is True
    assert payload["features"]["invitations"] is True
    assert permission_name in payload["available_permissions"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_invite_assigns_selected_role_ids_as_direct_memberships(
    simple_client: httpx.AsyncClient,
    simple_auth_instance: SimpleRBAC,
    simple_admin: dict[str, str],
):
    """SimpleRBAC invite accepts role_ids and persists them as direct role memberships."""
    permission_name = f"simpleinvite{uuid.uuid4().hex[:6]}:read"
    role_name = f"simple-invite-role-{uuid.uuid4().hex[:8]}"
    invited_email = f"simple-invited-{uuid.uuid4().hex[:8]}@example.com"

    async with simple_auth_instance.get_session() as session:
        permission = await simple_auth_instance.permission_service.create_permission(
            session,
            name=permission_name,
            display_name="Simple Invite Read",
        )
        role = await simple_auth_instance.role_service.create_role(
            session,
            name=role_name,
            display_name="Simple Invite Role",
            permission_names=[permission.name],
            created_by_id=UUID(simple_admin["id"]),
        )
        await session.commit()
        role_id = str(role.id)

    headers = _auth_headers(simple_admin["token"])
    invite_response = await simple_client.post(
        "/v1/auth/invite",
        headers=headers,
        json={
            "email": invited_email,
            "first_name": "Simple",
            "last_name": "Invited",
            "role_ids": [role_id],
        },
    )

    assert invite_response.status_code == 201, invite_response.text
    invited_payload = invite_response.json()
    assert invited_payload["email"] == invited_email
    assert invited_payload["status"] == "invited"
    assert invited_payload["root_entity_id"] is None
    assert "role_ids" not in invited_payload

    memberships_response = await simple_client.get(
        f"/v1/users/{invited_payload['id']}/role-memberships?include_inactive=true",
        headers=headers,
    )
    assert memberships_response.status_code == 200, memberships_response.text
    memberships_payload = memberships_response.json()
    assert len(memberships_payload) == 1
    assert memberships_payload[0]["role_id"] == role_id
    assert memberships_payload[0]["status"] == "active"
    assert memberships_payload[0]["can_grant_permissions"] is True
    assert memberships_payload[0]["role"]["name"] == role_name

    permissions_response = await simple_client.get(
        f"/v1/users/{invited_payload['id']}/permissions",
        headers=headers,
    )
    assert permissions_response.status_code == 200, permissions_response.text
    permissions_payload = permissions_response.json()
    assert any(
        item["permission"]["name"] == permission_name for item in permissions_payload
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_permissioned_admin_can_list_global_roles(
    simple_client: httpx.AsyncClient,
    simple_auth_instance: SimpleRBAC,
    simple_admin: dict[str, str],
):
    """SimpleRBAC role catalogs are global for permissioned non-superuser admins."""
    visible_permission_name = f"simplerolecatalog{uuid.uuid4().hex[:6]}:read"
    visible_role_name = f"simple-visible-role-{uuid.uuid4().hex[:8]}"
    catalog_admin_role_name = f"simple-role-catalog-admin-{uuid.uuid4().hex[:8]}"

    async with simple_auth_instance.get_session() as session:
        if await simple_auth_instance.permission_service.get_permission_by_name(
            session,
            "role:read",
            include_archived=False,
        ) is None:
            await simple_auth_instance.permission_service.create_permission(
                session,
                name="role:read",
                display_name="Role Read",
            )
        visible_permission = await simple_auth_instance.permission_service.create_permission(
            session,
            name=visible_permission_name,
            display_name="Simple Visible Read",
        )
        visible_role = await simple_auth_instance.role_service.create_role(
            session,
            name=visible_role_name,
            display_name="Simple Visible Role",
            permission_names=[visible_permission.name],
            created_by_id=UUID(simple_admin["id"]),
        )
        catalog_admin_role = await simple_auth_instance.role_service.create_role(
            session,
            name=catalog_admin_role_name,
            display_name="Simple Role Catalog Admin",
            permission_names=["role:read"],
            created_by_id=UUID(simple_admin["id"]),
        )
        catalog_admin = await simple_auth_instance.user_service.create_user(
            session=session,
            email=f"simple-role-catalog-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Role",
            last_name="Admin",
            is_superuser=False,
        )
        await simple_auth_instance.role_service.assign_role_to_user(
            session,
            user_id=catalog_admin.id,
            role_id=catalog_admin_role.id,
            assigned_by_id=UUID(simple_admin["id"]),
        )
        await session.commit()
        catalog_admin_token = create_access_token(
            {"sub": str(catalog_admin.id)},
            secret_key=simple_auth_instance.config.secret_key,
            algorithm=simple_auth_instance.config.algorithm,
            audience=simple_auth_instance.config.jwt_audience,
        )

    roles_response = await simple_client.get(
        "/v1/roles/?page=1&limit=20&is_global=true",
        headers=_auth_headers(catalog_admin_token),
    )
    assert roles_response.status_code == 200, roles_response.text
    roles_payload = roles_response.json()
    assert any(item["id"] == str(visible_role.id) for item in roles_payload["items"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_admin_ui_contract_exposes_shared_routes_and_omits_enterprise_only_routes(
    simple_client: httpx.AsyncClient,
    simple_auth_instance: SimpleRBAC,
    simple_admin: dict[str, str],
):
    """Simple example should keep shared admin routes working and leave enterprise-only routes unmounted."""
    permission_name = f"article{uuid.uuid4().hex[:6]}:read"
    role_name = f"article-reader-{uuid.uuid4().hex[:8]}"

    async with simple_auth_instance.get_session() as session:
        permission = await simple_auth_instance.permission_service.create_permission(
            session,
            name=permission_name,
            display_name="Article Read",
        )
        role = await simple_auth_instance.role_service.create_role(
            session,
            name=role_name,
            display_name="Article Reader",
            permission_names=[permission.name],
            created_by_id=UUID(simple_admin["id"]),
        )
        user = await simple_auth_instance.user_service.create_user(
            session=session,
            email=f"simple-user-{uuid.uuid4().hex[:8]}@example.com",
            password="UserPass123!",
            first_name="Simple",
            last_name="User",
        )
        await simple_auth_instance.role_service.assign_role_to_user(
            session,
            user_id=user.id,
            role_id=role.id,
            assigned_by_id=UUID(simple_admin["id"]),
        )
        await session.commit()

        target_user_id = str(user.id)
        target_role_id = str(role.id)

    headers = _auth_headers(simple_admin["token"])

    me_response = await simple_client.get("/v1/users/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["id"] == simple_admin["id"]

    roles_response = await simple_client.get("/v1/roles/?page=1&limit=20", headers=headers)
    assert roles_response.status_code == 200
    roles_payload = roles_response.json()
    assert any(item["id"] == target_role_id for item in roles_payload["items"])

    permissions_response = await simple_client.get(
        "/v1/permissions/?page=1&limit=20",
        headers=headers,
    )
    assert permissions_response.status_code == 200
    permissions_payload = permissions_response.json()
    assert any(item["name"] == permission_name for item in permissions_payload["items"])

    api_keys_response = await simple_client.get("/v1/api-keys", headers=headers)
    assert api_keys_response.status_code == 200
    assert isinstance(api_keys_response.json(), list)

    integration_principals_response = await simple_client.get(
        "/v1/admin/system/integration-principals?page=1&limit=20",
        headers=headers,
    )
    assert integration_principals_response.status_code == 200
    integration_principals_payload = integration_principals_response.json()
    assert integration_principals_payload["items"] == []
    assert integration_principals_payload["total"] == 0

    user_roles_response = await simple_client.get(
        f"/v1/users/{target_user_id}/roles",
        headers=headers,
    )
    assert user_roles_response.status_code == 200
    assert any(item["id"] == target_role_id for item in user_roles_response.json())

    role_memberships_response = await simple_client.get(
        f"/v1/users/{target_user_id}/role-memberships?include_inactive=true",
        headers=headers,
    )
    assert role_memberships_response.status_code == 200
    role_memberships_payload = role_memberships_response.json()
    assert any(item["role"]["id"] == target_role_id for item in role_memberships_payload)

    user_permissions_response = await simple_client.get(
        f"/v1/users/{target_user_id}/permissions",
        headers=headers,
    )
    assert user_permissions_response.status_code == 200
    user_permissions_payload = user_permissions_response.json()
    assert any(
        item["permission"]["name"] == permission_name for item in user_permissions_payload
    )

    membership_history_response = await simple_client.get(
        f"/v1/users/{target_user_id}/membership-history?page=1&limit=6",
        headers=headers,
    )
    assert membership_history_response.status_code == 200
    membership_history_payload = membership_history_response.json()
    assert membership_history_payload["items"] == []
    assert membership_history_payload["total"] == 0

    audit_events_response = await simple_client.get(
        f"/v1/users/{target_user_id}/audit-events?page=1&limit=6",
        headers=headers,
    )
    assert audit_events_response.status_code == 200
    audit_events_payload = audit_events_response.json()
    assert "items" in audit_events_payload
    assert "total" in audit_events_payload

    absent_enterprise_routes = [
        "/v1/entities",
        f"/v1/memberships/user/{target_user_id}?include_inactive=true",
        "/v1/config/entity-types",
    ]

    for path in absent_enterprise_routes:
        response = await simple_client.get(path, headers=headers)
        assert response.status_code == 404, path
