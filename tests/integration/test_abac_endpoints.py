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


def _abac_app(auth: OutlabsAuth, *, exception_handler_mode: str = "auth_only") -> FastAPI:
    app = FastAPI()
    app.add_middleware(ResourceContextMiddleware, trust_client_header=True)
    # The documented host setup: library errors render as {error, message, details}.
    auth.instrument_fastapi(app, exception_handler_mode=exception_handler_mode)
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))
    return app


@pytest_asyncio.fixture
async def app(auth: OutlabsAuth) -> FastAPI:
    return _abac_app(auth)


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
            "attribute": "resource.region",
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
            "attribute": "resource.department",
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_permissions_reject_permission_abac_mutations(
    auth: OutlabsAuth, client: httpx.AsyncClient, abac_setup: dict
):
    admin_token = abac_setup["admin_token"]

    async with auth.get_session() as session:
        permission = await auth.permission_service.create_permission(
            session=session,
            name=f"system:{uuid.uuid4().hex[:6]}",
            display_name="System Permission",
            description="System permission for ABAC protection tests",
            is_system=True,
        )
        await session.commit()

    create_group_response = await client.post(
        f"/v1/permissions/{permission.id}/condition-groups",
        json={"operator": "AND", "description": "should fail"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_group_response.status_code == 400, create_group_response.text
    system_permission_refusal = {
        "error": "INVALID_INPUT",
        "message": "Cannot modify system permission",
        "details": {"permission_id": str(permission.id), "permission_name": permission.name},
    }
    assert create_group_response.json() == system_permission_refusal

    create_condition_response = await client.post(
        f"/v1/permissions/{permission.id}/conditions",
        json={
            "attribute": "env.method",
            "operator": "equals",
            "value": "POST",
            "value_type": "string",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_condition_response.status_code == 400, create_condition_response.text
    assert create_condition_response.json() == system_permission_refusal


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("exception_handler_mode", ["auth_only", "global"])
async def test_invalid_abac_condition_writes_keep_reason_and_field(
    auth: OutlabsAuth, abac_setup: dict, exception_handler_mode: str
):
    """A refused condition write answers 400 with the library envelope (0.1.0a35 contract).

    The routers used to re-raise the service error as ``HTTPException(400,
    detail=message)``, so a superuser writing ``operator: "eq"`` got
    ``HTTP_ERROR`` (or a bare ``detail``) without ``details.reason`` or
    ``details.field``.
    """
    headers = {"Authorization": f"Bearer {abac_setup['admin_token']}"}
    app = _abac_app(auth, exception_handler_mode=exception_handler_mode)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=20.0) as client:
        permission_response = await client.post(
            "/v1/permissions/",
            json={
                "name": f"abac:{uuid.uuid4().hex[:6]}",
                "display_name": "ABAC Permission",
                "description": "ABAC refusal contract",
                "is_system": False,
                "is_active": True,
                "tags": [],
            },
            headers=headers,
        )
        assert permission_response.status_code == 201, permission_response.text
        permission_id = permission_response.json()["id"]

        valid_condition = {
            "attribute": "user.department",
            "operator": "equals",
            "value": "sales",
            "value_type": "string",
        }
        for base in (f"/v1/permissions/{permission_id}", f"/v1/roles/{abac_setup['role_id']}"):
            refused = await client.post(
                f"{base}/conditions",
                json={**valid_condition, "operator": "eq"},
                headers=headers,
            )
            assert refused.status_code == 400, refused.text
            body = refused.json()
            assert body["error"] == "INVALID_INPUT", body
            assert body["message"] == "Unknown ABAC operator 'eq'", body
            assert body["details"]["reason"] == "invalid_abac_condition", body
            assert body["details"]["field"] == "operator", body
            assert "equals" in body["details"]["allowed"], body

            created = await client.post(f"{base}/conditions", json=valid_condition, headers=headers)
            assert created.status_code == 201, created.text
            condition_id = created.json()["id"]

            refused_update = await client.patch(
                f"{base}/conditions/{condition_id}",
                json={"attribute": "subject.team"},
                headers=headers,
            )
            assert refused_update.status_code == 400, refused_update.text
            assert refused_update.json() == {
                "error": "INVALID_INPUT",
                "message": "ABAC attribute context must be one of user, resource, env, time",
                "details": {
                    "reason": "invalid_abac_condition",
                    "field": "attribute",
                    "attribute": "subject.team",
                    "allowed_contexts": ["user", "resource", "env", "time"],
                },
            }

            # Neither refusal wrote anything.
            listed = await client.get(f"{base}/conditions", headers=headers)
            assert listed.status_code == 200, listed.text
            assert [(c["attribute"], c["operator"]) for c in listed.json()] == [("user.department", "equals")]
