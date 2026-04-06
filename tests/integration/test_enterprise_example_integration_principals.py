import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass
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
async def enterprise_example_admin_app(enterprise_auth: EnterpriseRBAC) -> FastAPI:
    app = FastAPI()
    app.include_router(get_api_key_admin_router(enterprise_auth, prefix="/v1/admin/entities"))
    app.include_router(get_integration_principals_router(enterprise_auth, prefix="/v1/admin"))
    return app


async def _bearer_token(auth: EnterpriseRBAC, user_id: str) -> str:
    return create_access_token(
        {"sub": user_id},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )


async def _seed_permissions(session, auth: EnterpriseRBAC, names: list[str]) -> None:
    for name in names:
        await auth.permission_service.create_permission(
            session=session,
            name=name,
            display_name=name,
            description=name,
            is_system=True,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_example_entity_integration_principal_lifecycle_and_inventory(
    enterprise_example_admin_app: FastAPI,
    enterprise_auth: EnterpriseRBAC,
):
    async with enterprise_auth.get_session() as session:
        await _seed_permissions(
            session,
            enterprise_auth,
            [
                "api_key:create",
                "api_key:read",
                "api_key:update",
                "api_key:delete",
                "lead:read",
                "lead:update",
            ],
        )

        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email="admin@enterprise-example.test",
            password="TestPass123!",
            first_name="Admin",
            last_name="Example",
            is_superuser=True,
        )

        org = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="enterprise_example_root",
            display_name="Enterprise Example Root",
            slug="enterprise-example-root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        office = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="enterprise_example_office",
            display_name="Enterprise Example Office",
            slug="enterprise-example-office",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="office",
            parent_id=org.id,
        )
        await session.commit()

        admin_token = await _bearer_token(enterprise_auth, str(admin.id))

    transport = httpx.ASGITransport(app=enterprise_example_admin_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_principal_response = await client.post(
            f"/v1/admin/entities/{office.id}/integration-principals",
            json={
                "name": "Office Sync Worker",
                "description": "Durable office-scoped worker principal for the enterprise example host.",
                "allowed_scopes": ["lead:update"],
                "inherit_from_tree": True,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert create_principal_response.status_code == 201, create_principal_response.text
        principal_payload = create_principal_response.json()
        principal_id = principal_payload["id"]

        assert principal_payload["scope_kind"] == "entity"
        assert principal_payload["anchor_entity_id"] == str(office.id)
        assert principal_payload["inherit_from_tree"] is True
        assert principal_payload["allowed_scopes"] == ["lead:update"]

        create_key_response = await client.post(
            f"/v1/admin/entities/{office.id}/integration-principals/{principal_id}/api-keys",
            json={
                "name": "Office Sync Key",
                "description": "System key for the office sync worker.",
                "scopes": ["lead:update"],
                "prefix_type": "sk_live",
                "rate_limit_per_minute": 45,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert create_key_response.status_code == 201, create_key_response.text
        created_key_payload = create_key_response.json()
        key_id = created_key_payload["id"]

        assert created_key_payload["key_kind"] == "system_integration"
        assert created_key_payload["owner_type"] == "integration_principal"
        assert created_key_payload["owner_id"] == principal_id
        assert created_key_payload["entity_ids"] == [str(office.id)]
        assert created_key_payload["inherit_from_tree"] is True
        assert created_key_payload["is_currently_effective"] is True
        assert created_key_payload["api_key"].startswith("sk_live_")

        inventory_response = await client.get(
            f"/v1/admin/entities/{office.id}/api-keys?key_kind=system_integration",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert inventory_response.status_code == 200, inventory_response.text
        inventory_items = inventory_response.json()["items"]
        assert len(inventory_items) == 1
        assert inventory_items[0]["id"] == key_id
        assert inventory_items[0]["owner_type"] == "integration_principal"
        assert inventory_items[0]["is_currently_effective"] is True

        rotate_response = await client.post(
            f"/v1/admin/entities/{office.id}/integration-principals/{principal_id}/api-keys/{key_id}/rotate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert rotate_response.status_code == 200, rotate_response.text
        rotated_payload = rotate_response.json()
        rotated_key_id = rotated_payload["id"]
        assert rotated_key_id != key_id
        assert rotated_payload["owner_type"] == "integration_principal"
        assert rotated_payload["api_key"].startswith("sk_live_")

        narrow_principal_response = await client.patch(
            f"/v1/admin/entities/{office.id}/integration-principals/{principal_id}",
            json={
                "allowed_scopes": ["lead:read"],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert narrow_principal_response.status_code == 200, narrow_principal_response.text
        assert narrow_principal_response.json()["allowed_scopes"] == ["lead:read"]

        ineffective_inventory_response = await client.get(
            f"/v1/admin/entities/{office.id}/api-keys?key_kind=system_integration",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert ineffective_inventory_response.status_code == 200, ineffective_inventory_response.text
        ineffective_item = ineffective_inventory_response.json()["items"][0]
        assert ineffective_item["id"] == rotated_key_id
        assert ineffective_item["is_currently_effective"] is False
        assert "no_effective_scopes" in ineffective_item["ineffective_reasons"]

        revoke_response = await client.delete(
            f"/v1/admin/entities/{office.id}/integration-principals/{principal_id}/api-keys/{rotated_key_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert revoke_response.status_code == 204, revoke_response.text

        revoked_inventory_response = await client.get(
            f"/v1/admin/entities/{office.id}/api-keys?key_kind=system_integration&status=revoked",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert revoked_inventory_response.status_code == 200, revoked_inventory_response.text
        revoked_item = revoked_inventory_response.json()["items"][0]
        assert revoked_item["id"] == rotated_key_id
        assert revoked_item["status"] == "revoked"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_example_platform_global_integration_principals_are_superuser_only(
    enterprise_example_admin_app: FastAPI,
    enterprise_auth: EnterpriseRBAC,
):
    async with enterprise_auth.get_session() as session:
        await _seed_permissions(
            session,
            enterprise_auth,
            [
                "api_key:create",
                "api_key:read",
                "entity:read",
            ],
        )

        superuser = await enterprise_auth.user_service.create_user(
            session=session,
            email="superuser@enterprise-example.test",
            password="TestPass123!",
            first_name="Super",
            last_name="User",
            is_superuser=True,
        )
        member_user = await enterprise_auth.user_service.create_user(
            session=session,
            email="member@enterprise-example.test",
            password="TestPass123!",
            first_name="Scoped",
            last_name="Member",
        )
        await session.commit()

        superuser_token = await _bearer_token(enterprise_auth, str(superuser.id))
        member_token = await _bearer_token(enterprise_auth, str(member_user.id))

    transport = httpx.ASGITransport(app=enterprise_example_admin_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        superuser_create_response = await client.post(
            "/v1/admin/system/integration-principals",
            json={
                "name": "Global Export Worker",
                "description": "Platform-global integration principal used by the enterprise example host.",
                "allowed_scopes": ["entity:read"],
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )

        assert superuser_create_response.status_code == 201, superuser_create_response.text
        principal_payload = superuser_create_response.json()
        principal_id = principal_payload["id"]
        assert principal_payload["scope_kind"] == "platform_global"
        assert principal_payload["anchor_entity_id"] is None

        create_key_response = await client.post(
            f"/v1/admin/system/integration-principals/{principal_id}/api-keys",
            json={
                "name": "Global Export Key",
                "description": "System integration key for the global export worker.",
                "scopes": ["entity:read"],
                "prefix_type": "sk_live",
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )

        assert create_key_response.status_code == 201, create_key_response.text
        key_payload = create_key_response.json()
        assert key_payload["owner_type"] == "integration_principal"
        assert key_payload["key_kind"] == "system_integration"
        assert key_payload["entity_ids"] is None
        assert key_payload["api_key"].startswith("sk_live_")

        forbidden_response = await client.post(
            "/v1/admin/system/integration-principals",
            json={
                "name": "Forbidden Principal",
                "allowed_scopes": ["entity:read"],
            },
            headers={"Authorization": f"Bearer {member_token}"},
        )

        assert forbidden_response.status_code == 403, forbidden_response.text
