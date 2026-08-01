import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_api_keys_router
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
    register_exception_handlers(app, debug=True)
    app.include_router(get_api_keys_router(enterprise_auth, prefix="/v1/api-keys"))
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_self_service_grantable_scopes_support_optional_entity_context_and_unanchored_create(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    global_permission_name = f"dashboard{unique}:read"
    entity_permission_name = f"pipeline{unique}:read_tree"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"self_service_root_{unique}",
            display_name="Self Service Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"self_service_department_{unique}",
            display_name="Self Service Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )

        user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"self-service-{unique}@example.com",
            password="TestPass123!",
            first_name="Self",
            last_name="Service",
            root_entity_id=root.id,
        )

        global_permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=global_permission_name,
            display_name=global_permission_name,
            description="global self-service permission",
        )
        entity_permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=entity_permission_name,
            display_name=entity_permission_name,
            description="entity self-service permission",
        )

        global_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"self_service_global_role_{unique}",
            display_name="Self Service Global Role",
            is_global=True,
        )
        entity_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"self_service_entity_role_{unique}",
            display_name="Self Service Entity Role",
            is_global=False,
            root_entity_id=root.id,
        )
        await enterprise_auth.role_service.add_permissions(session, global_role.id, [global_permission.id])
        await enterprise_auth.role_service.add_permissions(session, entity_role.id, [entity_permission.id])
        await enterprise_auth.role_service.assign_role_to_user(
            session=session,
            user_id=user.id,
            role_id=global_role.id,
            assigned_by_id=user.id,
        )
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=user.id,
            role_ids=[entity_role.id],
            joined_by_id=user.id,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=enterprise_auth.config.secret_key,
            algorithm=enterprise_auth.config.algorithm,
            audience=enterprise_auth.config.jwt_audience,
        )
        department_id = str(department.id)

    client.headers.update({"Authorization": f"Bearer {token}"})

    unanchored_scopes = await client.get("/v1/api-keys/grantable-scopes")
    assert unanchored_scopes.status_code == 200, unanchored_scopes.text
    unanchored_payload = unanchored_scopes.json()
    assert unanchored_payload["entity_id"] is None
    assert unanchored_payload["allowed_key_kinds"] == ["personal"]
    assert global_permission_name in unanchored_payload["grantable_scopes"]

    anchored_scopes = await client.get(
        f"/v1/api-keys/grantable-scopes?entity_id={department_id}&inherit_from_tree=true"
    )
    assert anchored_scopes.status_code == 200, anchored_scopes.text
    anchored_payload = anchored_scopes.json()
    assert anchored_payload["entity_id"] == department_id
    assert anchored_payload["inherit_from_tree"] is True
    assert global_permission_name in anchored_payload["grantable_scopes"]
    assert entity_permission_name in anchored_payload["grantable_scopes"]

    created_key = await client.post(
        "/v1/api-keys/",
        json={
            "name": "Unanchored Personal Key",
            "scopes": [global_permission_name],
        },
    )
    assert created_key.status_code == 201, created_key.text
    created_payload = created_key.json()
    assert created_payload["entity_ids"] is None
    assert created_payload["key_kind"] == "personal"
    assert created_payload["owner_type"] == "user"
    assert created_payload["api_key"].startswith("sk_live_")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_self_service_grantable_scopes_reject_tree_scope_without_anchor(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
):
    async with enterprise_auth.get_session() as session:
        user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"self-service-invalid-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Invalid",
            last_name="Tree",
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=enterprise_auth.config.secret_key,
            algorithm=enterprise_auth.config.algorithm,
            audience=enterprise_auth.config.jwt_audience,
        )

    response = await client.get(
        "/v1/api-keys/grantable-scopes?inherit_from_tree=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400, response.text
    assert "entity anchor" in response.text
