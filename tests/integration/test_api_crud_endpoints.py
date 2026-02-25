import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_entities_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def enterprise_auth(test_engine) -> EnterpriseRBAC:
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
async def app(enterprise_auth: EnterpriseRBAC) -> FastAPI:
    app = FastAPI()
    app.include_router(get_auth_router(enterprise_auth, prefix="/v1/auth"))
    app.include_router(get_users_router(enterprise_auth, prefix="/v1/users"))
    app.include_router(get_roles_router(enterprise_auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(enterprise_auth, prefix="/v1/permissions"))
    app.include_router(get_api_keys_router(enterprise_auth, prefix="/v1/api-keys"))
    app.include_router(get_entities_router(enterprise_auth, prefix="/v1/entities"))
    app.include_router(get_memberships_router(enterprise_auth, prefix="/v1/memberships"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_token(enterprise_auth: EnterpriseRBAC) -> str:
    async with enterprise_auth.get_session() as session:
        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email="admin@example.com",
            password="TestPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

    return create_access_token(
        {"sub": str(admin.id)},
        secret_key=enterprise_auth.config.secret_key,
        algorithm=enterprise_auth.config.algorithm,
        audience=enterprise_auth.config.jwt_audience,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_register_login_refresh(client: httpx.AsyncClient):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"

    r_register = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert r_register.status_code == 201, r_register.text

    r_login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r_login.status_code == 200, r_login.text
    tokens = r_login.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    r_refresh = await client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r_refresh.status_code == 200, r_refresh.text
    refreshed = r_refresh.json()
    assert "access_token" in refreshed and refreshed["access_token"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_crud(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    r_me = await client.get("/v1/users/me")
    assert r_me.status_code == 200, r_me.text

    email = f"created-{uuid.uuid4().hex[:8]}@example.com"
    r_create = await client.post(
        "/v1/users/",
        json={
            "email": email,
            "password": "TestPass123!",
            "first_name": "Created",
            "last_name": "User",
            "is_superuser": False,
        },
    )
    assert r_create.status_code == 201, r_create.text
    created = r_create.json()
    user_id = created["id"]

    r_list = await client.get("/v1/users/", params={"page": 1, "limit": 20})
    assert r_list.status_code == 200, r_list.text
    assert any(item["id"] == user_id for item in r_list.json()["items"])

    r_get = await client.get(f"/v1/users/{user_id}")
    assert r_get.status_code == 200, r_get.text

    r_update = await client.patch(f"/v1/users/{user_id}", json={"first_name": "Updated"})
    assert r_update.status_code == 200, r_update.text
    assert r_update.json()["first_name"] == "Updated"

    r_delete = await client.delete(f"/v1/users/{user_id}")
    assert r_delete.status_code == 204, r_delete.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_and_roles_crud(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    perm_name = f"demo:{uuid.uuid4().hex[:6]}"
    r_perm_create = await client.post(
        "/v1/permissions/",
        json={
            "name": perm_name,
            "display_name": "Demo Permission",
            "description": "integration test",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
    )
    assert r_perm_create.status_code == 201, r_perm_create.text
    perm = r_perm_create.json()
    perm_id = perm["id"]

    r_perm_get = await client.get(f"/v1/permissions/{perm_id}")
    assert r_perm_get.status_code == 200, r_perm_get.text

    r_perm_update = await client.patch(
        f"/v1/permissions/{perm_id}",
        json={"display_name": "Demo Permission Updated", "is_active": True},
    )
    assert r_perm_update.status_code == 200, r_perm_update.text

    role_name = f"demo_role_{uuid.uuid4().hex[:6]}"
    r_role_create = await client.post(
        "/v1/roles/",
        json={
            "name": role_name,
            "display_name": "Demo Role",
            "description": "integration test",
            "permissions": [perm_name],
            "is_global": False,
        },
    )
    assert r_role_create.status_code == 201, r_role_create.text
    role = r_role_create.json()
    role_id = role["id"]

    r_role_get = await client.get(f"/v1/roles/{role_id}")
    assert r_role_get.status_code == 200, r_role_get.text

    r_role_update = await client.patch(
        f"/v1/roles/{role_id}",
        json={"display_name": "Demo Role Updated", "is_global": True},
    )
    assert r_role_update.status_code == 200, r_role_update.text

    r_role_delete = await client.delete(f"/v1/roles/{role_id}")
    assert r_role_delete.status_code == 204, r_role_delete.text

    r_perm_delete = await client.delete(f"/v1/permissions/{perm_id}")
    assert r_perm_delete.status_code == 204, r_perm_delete.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_keys_crud(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    r_create = await client.post(
        "/v1/api-keys/",
        json={"name": "test key", "scopes": ["*:*"], "prefix_type": "sk"},
    )
    assert r_create.status_code == 201, r_create.text
    created = r_create.json()
    key_id = created["id"]
    assert created.get("api_key")  # full key shown only once

    r_list = await client.get("/v1/api-keys/")
    assert r_list.status_code == 200, r_list.text
    assert any(k["id"] == key_id for k in r_list.json())

    r_get = await client.get(f"/v1/api-keys/{key_id}")
    assert r_get.status_code == 200, r_get.text

    r_update = await client.patch(f"/v1/api-keys/{key_id}", json={"name": "renamed"})
    assert r_update.status_code == 200, r_update.text

    r_delete = await client.delete(f"/v1/api-keys/{key_id}")
    assert r_delete.status_code == 204, r_delete.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entities_and_memberships_smoke(
    client: httpx.AsyncClient, enterprise_auth: EnterpriseRBAC, admin_token: str
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    r_org = await client.post(
        "/v1/entities/",
        json={
            "name": "org",
            "display_name": "Org",
            "slug": f"org-{uuid.uuid4().hex[:6]}",
            "description": None,
            "entity_class": "structural",
            "entity_type": "organization",
            "parent_entity_id": None,
            "status": "active",
        },
    )
    assert r_org.status_code == 201, r_org.text
    org = r_org.json()

    r_team = await client.post(
        "/v1/entities/",
        json={
            "name": "team",
            "display_name": "Team",
            "slug": f"team-{uuid.uuid4().hex[:6]}",
            "description": None,
            "entity_class": "structural",
            "entity_type": "team",
            "parent_entity_id": org["id"],
            "status": "active",
        },
    )
    assert r_team.status_code == 201, r_team.text
    team = r_team.json()

    # Create a regular user directly and add them to the team via endpoint.
    async with enterprise_auth.get_session() as session:
        user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"member-{uuid.uuid4().hex[:6]}@example.com",
            password="TestPass123!",
            first_name="Member",
            last_name="User",
        )
        await session.commit()
        user_id = str(user.id)

    r_add = await client.post(
        "/v1/memberships/",
        json={"entity_id": team["id"], "user_id": user_id, "role_ids": []},
    )
    assert r_add.status_code == 201, r_add.text

    r_desc = await client.get(f"/v1/entities/{org['id']}/descendants")
    assert r_desc.status_code == 200, r_desc.text

    r_members = await client.get(f"/v1/entities/{org['id']}/members", params={"page": 1, "limit": 50})
    assert r_members.status_code == 200, r_members.text

    # Move team to root and then delete.
    r_move = await client.post(
        f"/v1/entities/{team['id']}/move",
        json={"new_parent_id": None},
    )
    assert r_move.status_code == 200, r_move.text

    r_delete = await client.delete(f"/v1/entities/{team['id']}")
    assert r_delete.status_code == 204, r_delete.text
