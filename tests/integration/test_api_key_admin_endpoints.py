import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import APIKeyStatus, EntityClass, IntegrationPrincipalStatus
from outlabs_auth.routers import (
    get_api_key_admin_router,
    get_integration_principals_router,
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
    register_exception_handlers(app, debug=True)
    app.include_router(get_api_key_admin_router(enterprise_auth, prefix="/v1/admin/entities"))
    app.include_router(get_integration_principals_router(enterprise_auth, prefix="/v1/admin"))
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
async def test_entity_integration_principal_routes_manage_system_keys_and_inventory(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    contacts_read_tree = f"contacts{unique}:read_tree"
    reports_update = f"reports{unique}:update"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"entity_principal_root_{unique}",
            display_name="Entity Principal Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"entity_principal_department_{unique}",
            display_name="Entity Principal Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"entity_principal_team_{unique}",
            display_name="Entity Principal Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        admin_user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"entity-principal-admin-{unique}@example.com",
            password="TestPass123!",
            first_name="Entity",
            last_name="Admin",
            root_entity_id=root.id,
        )

        permission_names = [
            "api_key:create_tree",
            "api_key:read_tree",
            "api_key:update_tree",
            "api_key:delete_tree",
            contacts_read_tree,
            reports_update,
        ]
        permission_ids = []
        for permission_name in permission_names:
            permission = await enterprise_auth.permission_service.create_permission(
                session,
                name=permission_name,
                display_name=permission_name,
                description="integration principal admin route test",
            )
            permission_ids.append(permission.id)

        role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"entity_principal_role_{unique}",
            display_name="Entity Principal Admin Role",
            is_global=False,
            root_entity_id=root.id,
        )
        await enterprise_auth.role_service.add_permissions(session, role.id, permission_ids)
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=admin_user.id,
            role_ids=[role.id],
            joined_by_id=admin_user.id,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin_user.id)},
            secret_key=enterprise_auth.config.secret_key,
            algorithm=enterprise_auth.config.algorithm,
            audience=enterprise_auth.config.jwt_audience,
        )
        department_id = str(department.id)
        team_id = team.id

    client.headers.update({"Authorization": f"Bearer {token}"})

    created_principal = await client.post(
        f"/v1/admin/entities/{department_id}/integration-principals",
        json={
            "name": "Worker Principal",
            "description": "Entity-scoped worker automation",
            "allowed_scopes": [contacts_read_tree, reports_update],
            "inherit_from_tree": True,
        },
    )
    assert created_principal.status_code == 201, created_principal.text
    principal_data = created_principal.json()
    principal_id = principal_data["id"]
    assert principal_data["scope_kind"] == "entity"
    assert principal_data["anchor_entity_id"] == department_id
    assert principal_data["allowed_scopes"] == [contacts_read_tree, reports_update]

    created_key = await client.post(
        f"/v1/admin/entities/{department_id}/integration-principals/{principal_id}/api-keys",
        json={
            "name": "Worker Runtime Key",
            "scopes": [contacts_read_tree],
        },
    )
    assert created_key.status_code == 201, created_key.text
    key_data = created_key.json()
    key_id = key_data["id"]
    original_secret = key_data["api_key"]
    assert key_data["key_kind"] == "system_integration"
    assert key_data["owner_type"] == "integration_principal"
    assert key_data["owner_id"] == principal_id
    assert key_data["entity_ids"] == [department_id]
    assert key_data["is_currently_effective"] is True

    principal_list = await client.get(f"/v1/admin/entities/{department_id}/integration-principals")
    assert principal_list.status_code == 200, principal_list.text
    assert principal_list.json()["total"] == 1

    nested_keys = await client.get(
        f"/v1/admin/entities/{department_id}/integration-principals/{principal_id}/api-keys"
    )
    assert nested_keys.status_code == 200, nested_keys.text
    assert nested_keys.json()["total"] == 1
    assert nested_keys.json()["items"][0]["id"] == key_id

    async with enterprise_auth.get_session() as session:
        authorized = await enterprise_auth.authorize_api_key(
            session,
            original_secret,
            required_scope=contacts_read_tree.replace("_tree", ""),
            entity_id=team_id,
        )
        assert authorized is not None
        assert authorized["user"] is None
        assert authorized["integration_principal_id"] == principal_id
        assert authorized["metadata"]["owner_type"] == "integration_principal"

    rotated = await client.post(
        f"/v1/admin/entities/{department_id}/integration-principals/{principal_id}/api-keys/{key_id}/rotate"
    )
    assert rotated.status_code == 200, rotated.text
    rotated_data = rotated.json()
    rotated_secret = rotated_data["api_key"]
    rotated_key_id = rotated_data["id"]
    assert rotated_key_id != key_id

    async with enterprise_auth.get_session() as session:
        revoked = await enterprise_auth.authorize_api_key(
            session,
            original_secret,
            required_scope=contacts_read_tree.replace("_tree", ""),
            entity_id=team_id,
        )
        assert revoked is None
        rotated_auth = await enterprise_auth.authorize_api_key(
            session,
            rotated_secret,
            required_scope=contacts_read_tree.replace("_tree", ""),
            entity_id=team_id,
        )
        assert rotated_auth is not None

    updated_principal = await client.patch(
        f"/v1/admin/entities/{department_id}/integration-principals/{principal_id}",
        json={"allowed_scopes": [reports_update]},
    )
    assert updated_principal.status_code == 200, updated_principal.text
    assert updated_principal.json()["allowed_scopes"] == [reports_update]

    async with enterprise_auth.get_session() as session:
        denied = await enterprise_auth.authorize_api_key(
            session,
            rotated_secret,
            required_scope=contacts_read_tree.replace("_tree", ""),
            entity_id=team_id,
        )
        assert denied is None

    inventory = await client.get(f"/v1/admin/entities/{department_id}/api-keys")
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()["total"] == 2
    assert any(item["owner_type"] == "integration_principal" for item in inventory.json()["items"])

    revoked_key = await client.delete(
        f"/v1/admin/entities/{department_id}/integration-principals/{principal_id}/api-keys/{rotated_key_id}"
    )
    assert revoked_key.status_code == 204, revoked_key.text

    fetched_inventory_key = await client.get(
        f"/v1/admin/entities/{department_id}/api-keys/{rotated_key_id}"
    )
    assert fetched_inventory_key.status_code == 200, fetched_inventory_key.text
    assert fetched_inventory_key.json()["status"] == APIKeyStatus.REVOKED.value

    archived_principal = await client.delete(
        f"/v1/admin/entities/{department_id}/integration-principals/{principal_id}"
    )
    assert archived_principal.status_code == 204, archived_principal.text

    fetched_principal = await client.get(
        f"/v1/admin/entities/{department_id}/integration-principals/{principal_id}"
    )
    assert fetched_principal.status_code == 200, fetched_principal.text
    assert fetched_principal.json()["status"] == IntegrationPrincipalStatus.ARCHIVED.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_integration_principal_routes_require_superuser_and_issue_global_keys(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    reports_update = f"reports{unique}:update"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"system_principal_root_{unique}",
            display_name="System Principal Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        admin_user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"system-principal-admin-{unique}@example.com",
            password="TestPass123!",
            first_name="System",
            last_name="Admin",
            root_entity_id=root.id,
        )
        superuser = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"system-principal-superuser-{unique}@example.com",
            password="TestPass123!",
            first_name="Super",
            last_name="User",
            is_superuser=True,
        )
        await enterprise_auth.permission_service.create_permission(
            session,
            name=reports_update,
            display_name=reports_update,
            description="platform global system integration test permission",
        )
        await session.commit()

        admin_token = create_access_token(
            {"sub": str(admin_user.id)},
            secret_key=enterprise_auth.config.secret_key,
            algorithm=enterprise_auth.config.algorithm,
            audience=enterprise_auth.config.jwt_audience,
        )
        superuser_token = create_access_token(
            {"sub": str(superuser.id)},
            secret_key=enterprise_auth.config.secret_key,
            algorithm=enterprise_auth.config.algorithm,
            audience=enterprise_auth.config.jwt_audience,
        )

    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    forbidden = await client.post(
        "/v1/admin/system/integration-principals",
        json={
            "name": "Forbidden Principal",
            "allowed_scopes": [reports_update],
        },
    )
    assert forbidden.status_code == 403, forbidden.text

    client.headers.update({"Authorization": f"Bearer {superuser_token}"})
    created_principal = await client.post(
        "/v1/admin/system/integration-principals",
        json={
            "name": "Global Reporting Principal",
            "description": "Platform-global reporting integration",
            "allowed_scopes": [reports_update],
        },
    )
    assert created_principal.status_code == 201, created_principal.text
    principal_data = created_principal.json()
    principal_id = principal_data["id"]
    assert principal_data["scope_kind"] == "platform_global"
    assert principal_data["anchor_entity_id"] is None

    created_key = await client.post(
        f"/v1/admin/system/integration-principals/{principal_id}/api-keys",
        json={
            "name": "Reporting Global Key",
            "scopes": [reports_update],
        },
    )
    assert created_key.status_code == 201, created_key.text
    key_data = created_key.json()
    key_id = key_data["id"]
    full_key = key_data["api_key"]
    assert key_data["owner_type"] == "integration_principal"
    assert key_data["entity_ids"] is None

    async with enterprise_auth.get_session() as session:
        authorized = await enterprise_auth.authorize_api_key(
            session,
            full_key,
            required_scope=reports_update,
        )
        assert authorized is not None
        assert authorized["user"] is None
        assert authorized["integration_principal_id"] == principal_id
        assert authorized["metadata"]["key_kind"] == "system_integration"

    updated_key = await client.patch(
        f"/v1/admin/system/integration-principals/{principal_id}/api-keys/{key_id}",
        json={"description": "Updated global key description"},
    )
    assert updated_key.status_code == 200, updated_key.text
    assert updated_key.json()["description"] == "Updated global key description"

    listed_keys = await client.get(f"/v1/admin/system/integration-principals/{principal_id}/api-keys")
    assert listed_keys.status_code == 200, listed_keys.text
    assert listed_keys.json()["total"] == 1

    revoked_key = await client.delete(
        f"/v1/admin/system/integration-principals/{principal_id}/api-keys/{key_id}"
    )
    assert revoked_key.status_code == 204, revoked_key.text

    archived_principal = await client.delete(f"/v1/admin/system/integration-principals/{principal_id}")
    assert archived_principal.status_code == 204, archived_principal.text
