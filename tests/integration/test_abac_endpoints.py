import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import OutlabsAuth
from outlabs_auth.middleware import ResourceContextMiddleware
from outlabs_auth.routers import get_permissions_router, get_roles_router
from outlabs_auth.services.role import RoleService
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def auth(test_engine) -> OutlabsAuth:
    auth = OutlabsAuth(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_abac=True,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def app(auth: OutlabsAuth) -> FastAPI:
    app = FastAPI()
    app.add_middleware(ResourceContextMiddleware, trust_client_header=True)
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def abac_setup(auth: OutlabsAuth) -> dict:
    async with auth.get_session() as session:
        # Minimal permissions needed to hit POST /permissions/
        await auth.permission_service.create_permission(
            session=session,
            name="permission:create",
            display_name="permission:create",
            description="",
            is_system=True,
        )

        role_service = RoleService(auth.config)
        role = await role_service.create_role(
            session=session,
            name="abac_tester",
            display_name="abac_tester",
            permission_names=["permission:create"],
            is_global=True,
        )

        actor = await auth.user_service.create_user(
            session=session,
            email=f"abac-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="ABAC",
            last_name="User",
        )

        # Assign role (SimpleRBAC membership table)
        await auth.role_service.assign_role_to_user(
            session=session,
            user_id=actor.id,
            role_id=role.id,
        )

        admin = await auth.user_service.create_user(
            session=session,
            email=f"abac-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="ABAC",
            last_name="Admin",
            is_superuser=True,
        )

        await session.commit()

    actor_token = create_access_token(
        {"sub": str(actor.id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )
    admin_token = create_access_token(
        {"sub": str(admin.id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )

    return {
        "actor_token": actor_token,
        "admin_token": admin_token,
        "role_id": str(role.id),
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abac_role_condition_denies_when_env_mismatch(
    auth: OutlabsAuth, client: httpx.AsyncClient, abac_setup: dict
):
    admin_token = abac_setup["admin_token"]
    actor_token = abac_setup["actor_token"]
    role_id = abac_setup["role_id"]

    r_create = await client.post(
        f"/v1/roles/{role_id}/conditions",
        json={
            "attribute": "env.method",
            "operator": "equals",
            "value": "GET",
            "value_type": "string",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_create.status_code == 201, r_create.text

    r = await client.post(
        "/v1/permissions/",
        json={
            "name": f"demo:{uuid.uuid4().hex[:6]}",
            "display_name": "Demo",
            "description": "demo",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
        headers={"Authorization": f"Bearer {actor_token}"},
    )
    assert r.status_code == 403, r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abac_role_condition_allows_when_env_matches(
    auth: OutlabsAuth, client: httpx.AsyncClient, abac_setup: dict
):
    admin_token = abac_setup["admin_token"]
    actor_token = abac_setup["actor_token"]
    role_id = abac_setup["role_id"]

    existing = await client.get(
        f"/v1/roles/{role_id}/conditions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert existing.status_code == 200, existing.text
    for cond in existing.json():
        d = await client.delete(
            f"/v1/roles/{role_id}/conditions/{cond['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert d.status_code == 204, d.text

    r_create = await client.post(
        f"/v1/roles/{role_id}/conditions",
        json={
            "attribute": "env.method",
            "operator": "equals",
            "value": "POST",
            "value_type": "string",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_create.status_code == 201, r_create.text

    r = await client.post(
        "/v1/permissions/",
        json={
            "name": f"demo:{uuid.uuid4().hex[:6]}",
            "display_name": "Demo",
            "description": "demo",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
        headers={"Authorization": f"Bearer {actor_token}"},
    )
    assert r.status_code == 201, r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abac_resource_context_from_header(auth: OutlabsAuth, client: httpx.AsyncClient, abac_setup: dict):
    admin_token = abac_setup["admin_token"]
    actor_token = abac_setup["actor_token"]
    role_id = abac_setup["role_id"]

    existing = await client.get(
        f"/v1/roles/{role_id}/conditions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert existing.status_code == 200, existing.text
    for cond in existing.json():
        d = await client.delete(
            f"/v1/roles/{role_id}/conditions/{cond['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert d.status_code == 204, d.text

    r_create = await client.post(
        f"/v1/roles/{role_id}/conditions",
        json={
            "attribute": "resource.status",
            "operator": "equals",
            "value": "draft",
            "value_type": "string",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_create.status_code == 201, r_create.text

    # Missing/incorrect resource context should deny.
    denied = await client.post(
        "/v1/permissions/",
        json={
            "name": f"demo:{uuid.uuid4().hex[:6]}",
            "display_name": "Demo",
            "description": "demo",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
        headers={
            "Authorization": f"Bearer {actor_token}",
            "X-Resource-Context": '{"status":"published"}',
        },
    )
    assert denied.status_code == 403, denied.text

    allowed = await client.post(
        "/v1/permissions/",
        json={
            "name": f"demo:{uuid.uuid4().hex[:6]}",
            "display_name": "Demo",
            "description": "demo",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
        headers={
            "Authorization": f"Bearer {actor_token}",
            "X-Resource-Context": '{"status":"draft"}',
        },
    )
    assert allowed.status_code == 201, allowed.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_abac_updates_allow_explicit_ungrouping_and_description_clear(
    client: httpx.AsyncClient, abac_setup: dict
):
    admin_token = abac_setup["admin_token"]
    role_id = abac_setup["role_id"]

    group_response = await client.post(
        f"/v1/roles/{role_id}/condition-groups",
        json={"operator": "AND", "description": "Regional approvals"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert group_response.status_code == 201, group_response.text
    group_id = group_response.json()["id"]

    condition_response = await client.post(
        f"/v1/roles/{role_id}/conditions",
        json={
            "attribute": "context.region",
            "operator": "equals",
            "value": "latam",
            "value_type": "string",
            "description": "Regional gate",
            "condition_group_id": group_id,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert condition_response.status_code == 201, condition_response.text
    condition_id = condition_response.json()["id"]

    updated_group = await client.patch(
        f"/v1/roles/{role_id}/condition-groups/{group_id}",
        json={"description": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated_group.status_code == 200, updated_group.text
    assert updated_group.json()["description"] is None

    updated_condition = await client.patch(
        f"/v1/roles/{role_id}/conditions/{condition_id}",
        json={"condition_group_id": None, "description": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated_condition.status_code == 200, updated_condition.text
    payload = updated_condition.json()
    assert payload["condition_group_id"] is None
    assert payload["description"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permission_abac_updates_allow_explicit_ungrouping_and_description_clear(
    client: httpx.AsyncClient, abac_setup: dict
):
    admin_token = abac_setup["admin_token"]

    permission_response = await client.post(
        "/v1/permissions/",
        json={
            "name": f"abac:{uuid.uuid4().hex[:6]}",
            "display_name": "ABAC Permission",
            "description": "ABAC test permission",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert permission_response.status_code == 201, permission_response.text
    permission_id = permission_response.json()["id"]

    group_response = await client.post(
        f"/v1/permissions/{permission_id}/condition-groups",
        json={"operator": "OR", "description": "Temporary exceptions"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert group_response.status_code == 201, group_response.text
    group_id = group_response.json()["id"]

    condition_response = await client.post(
        f"/v1/permissions/{permission_id}/conditions",
        json={
            "attribute": "context.department",
            "operator": "equals",
            "value": "finance",
            "value_type": "string",
            "description": "Department gate",
            "condition_group_id": group_id,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert condition_response.status_code == 201, condition_response.text
    condition_id = condition_response.json()["id"]

    updated_group = await client.patch(
        f"/v1/permissions/{permission_id}/condition-groups/{group_id}",
        json={"description": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated_group.status_code == 200, updated_group.text
    assert updated_group.json()["description"] is None

    updated_condition = await client.patch(
        f"/v1/permissions/{permission_id}/conditions/{condition_id}",
        json={"condition_group_id": None, "description": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated_condition.status_code == 200, updated_condition.text
    payload = updated_condition.json()
    assert payload["condition_group_id"] is None
    assert payload["description"] is None
