from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import get_integration_principals_router
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def simple_auth_with_global_keys(test_engine) -> AsyncGenerator[SimpleRBAC, None]:
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
async def simple_global_keys_app(simple_auth_with_global_keys: SimpleRBAC) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(
        get_integration_principals_router(simple_auth_with_global_keys, prefix="/v1/admin")
    )
    return app


async def _bearer_token(auth: SimpleRBAC, user_id: str) -> str:
    return create_access_token(
        {"sub": user_id},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_rbac_system_key_routes_honor_api_key_permissions(
    simple_global_keys_app: FastAPI,
    simple_auth_with_global_keys: SimpleRBAC,
):
    assert simple_auth_with_global_keys.permission_service is not None
    assert simple_auth_with_global_keys.role_service is not None
    assert simple_auth_with_global_keys.user_service is not None
    assert simple_auth_with_global_keys.api_key_service is not None

    async with simple_auth_with_global_keys.get_session() as session:
        for name in ["api_key:read", "api_key:create", "api_key:revoke", "agent:read"]:
            await simple_auth_with_global_keys.permission_service.create_permission(
                session,
                name=name,
                display_name=name,
                description=f"{name} permission.",
            )

        scraper_role = await simple_auth_with_global_keys.role_service.create_role(
            session,
            name=f"permissioned-scraper-{uuid.uuid4().hex[:8]}",
            display_name="Permissioned Scraper",
            description="Global worker role for scraper traffic.",
            permission_names=["agent:read"],
        )
        api_key_admin_role = await simple_auth_with_global_keys.role_service.create_role(
            session,
            name=f"api-key-admin-{uuid.uuid4().hex[:8]}",
            display_name="API Key Admin",
            description="Can manage SimpleRBAC platform-global service accounts.",
            permission_names=["api_key:read", "api_key:create", "api_key:revoke", "agent:read"],
        )
        permissioned_user = await simple_auth_with_global_keys.user_service.create_user(
            session=session,
            email=f"simple-api-key-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="API",
            last_name="Admin",
            is_superuser=False,
        )
        await simple_auth_with_global_keys.role_service.assign_role_to_user(
            session,
            user_id=permissioned_user.id,
            role_id=api_key_admin_role.id,
            assigned_by_id=permissioned_user.id,
        )
        await session.commit()
        token = await _bearer_token(simple_auth_with_global_keys, str(permissioned_user.id))

    transport = httpx.ASGITransport(app=simple_global_keys_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        list_response = await client.get(
            "/v1/admin/system/integration-principals",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200, list_response.text

        principal_response = await client.post(
            "/v1/admin/system/integration-principals",
            json={
                "name": "Permissioned Scraping Workers",
                "description": "Global worker principal managed by an API-key admin role.",
                "role_ids": [str(scraper_role.id)],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert principal_response.status_code == 201, principal_response.text
        principal_id = principal_response.json()["id"]

        api_key_response = await client.post(
            f"/v1/admin/system/integration-principals/{principal_id}/api-keys",
            json={
                "name": "Permissioned Scraper Key",
                "description": "Scraper key created by a non-superuser API-key admin.",
                "scopes": ["agent:read"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert api_key_response.status_code == 201, api_key_response.text
        key_id = api_key_response.json()["id"]

        list_keys_response = await client.get(
            f"/v1/admin/system/integration-principals/{principal_id}/api-keys",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_keys_response.status_code == 200, list_keys_response.text
        assert [item["id"] for item in list_keys_response.json()["items"]] == [key_id]

        revoke_key_response = await client.delete(
            f"/v1/admin/system/integration-principals/{principal_id}/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert revoke_key_response.status_code == 204, revoke_key_response.text

        archive_principal_response = await client.delete(
            f"/v1/admin/system/integration-principals/{principal_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert archive_principal_response.status_code == 204, archive_principal_response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_rbac_supports_platform_global_system_keys(
    simple_global_keys_app: FastAPI,
    simple_auth_with_global_keys: SimpleRBAC,
):
    assert simple_auth_with_global_keys.permission_service is not None
    assert simple_auth_with_global_keys.role_service is not None
    assert simple_auth_with_global_keys.user_service is not None
    assert simple_auth_with_global_keys.api_key_service is not None

    async with simple_auth_with_global_keys.get_session() as session:
        await simple_auth_with_global_keys.permission_service.create_permission(
            session,
            name="agent:read",
            display_name="Agent Read",
            description="Read agents for worker automation.",
        )
        scraper_role = await simple_auth_with_global_keys.role_service.create_role(
            session,
            name=f"scraper-worker-{uuid.uuid4().hex[:8]}",
            display_name="Scraper Worker",
            description="Global worker role for scraper traffic.",
            permission_names=["agent:read"],
        )
        superuser = await simple_auth_with_global_keys.user_service.create_user(
            session=session,
            email=f"simple-global-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Simple",
            last_name="Global",
            is_superuser=True,
        )
        await session.commit()
        token = await _bearer_token(simple_auth_with_global_keys, str(superuser.id))

    transport = httpx.ASGITransport(app=simple_global_keys_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        principal_response = await client.post(
            "/v1/admin/system/integration-principals",
            json={
                "name": "Scraping Workers",
                "description": "Global worker principal for scraper traffic.",
                "role_ids": [str(scraper_role.id)],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert principal_response.status_code == 201, principal_response.text
        principal_payload = principal_response.json()
        principal_id = principal_payload["id"]
        assert principal_payload["scope_kind"] == "platform_global"
        assert principal_payload["anchor_entity_id"] is None
        assert principal_payload["allowed_scopes"] == []
        assert principal_payload["effective_allowed_scopes"] == ["agent:read"]
        assert principal_payload["role_ids"] == [str(scraper_role.id)]

        api_key_response = await client.post(
            f"/v1/admin/system/integration-principals/{principal_id}/api-keys",
            json={
                "name": "Scraper Key",
                "description": "Production scraper key.",
                "scopes": ["agent:read"],
                "prefix_type": "sk_live",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert api_key_response.status_code == 201, api_key_response.text
        key_payload = api_key_response.json()
        assert key_payload["key_kind"] == "system_integration"
        assert key_payload["owner_type"] == "integration_principal"
        assert key_payload["entity_ids"] is None
        assert key_payload["api_key"].startswith("sk_live_")

        list_response = await client.get(
            f"/v1/admin/system/integration-principals/{principal_id}/api-keys",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert list_response.status_code == 200, list_response.text
        listed_keys = list_response.json()["items"]
        assert len(listed_keys) == 1
        assert listed_keys[0]["id"] == key_payload["id"]

        async with simple_auth_with_global_keys.get_session() as session:
            verified_key, _ = await simple_auth_with_global_keys.api_key_service.verify_api_key(
                session,
                key_payload["api_key"],
                required_scope="agent:read",
            )

        assert verified_key is not None
        assert str(verified_key.integration_principal_id) == principal_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_rbac_system_key_can_access_permission_protected_route(
    simple_auth_with_global_keys: SimpleRBAC,
):
    assert simple_auth_with_global_keys.permission_service is not None
    assert simple_auth_with_global_keys.role_service is not None
    assert simple_auth_with_global_keys.user_service is not None
    assert simple_auth_with_global_keys.api_key_service is not None

    protected_app = FastAPI()
    register_exception_handlers(protected_app, debug=True)

    @protected_app.get("/protected")
    async def protected_route(
        _: dict = Depends(simple_auth_with_global_keys.deps.require_permission("agent:write")),
    ) -> dict[str, str]:
        return {"ok": "yes"}

    protected_app.include_router(
        get_integration_principals_router(simple_auth_with_global_keys, prefix="/v1/admin")
    )

    async with simple_auth_with_global_keys.get_session() as session:
        await simple_auth_with_global_keys.permission_service.create_permission(
            session,
            name="agent:write",
            display_name="Agent Write",
            description="Write agents for worker automation.",
        )
        scraper_role = await simple_auth_with_global_keys.role_service.create_role(
            session,
            name=f"scraper-worker-{uuid.uuid4().hex[:8]}",
            display_name="Scraper Worker",
            description="Global worker role for scraper traffic.",
            permission_names=["agent:write"],
        )
        superuser = await simple_auth_with_global_keys.user_service.create_user(
            session=session,
            email=f"simple-global-route-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Simple",
            last_name="Global",
            is_superuser=True,
        )
        await session.commit()
        token = await _bearer_token(simple_auth_with_global_keys, str(superuser.id))

    transport = httpx.ASGITransport(app=protected_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        principal_response = await client.post(
            "/v1/admin/system/integration-principals",
            json={
                "name": "Scraping Workers",
                "description": "Global worker principal for scraper traffic.",
                "role_ids": [str(scraper_role.id)],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert principal_response.status_code == 201, principal_response.text
        principal_id = principal_response.json()["id"]

        api_key_response = await client.post(
            f"/v1/admin/system/integration-principals/{principal_id}/api-keys",
            json={
                "name": "Scraper Key",
                "description": "Production scraper key.",
                "scopes": ["agent:write"],
                "prefix_type": "sk_live",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert api_key_response.status_code == 201, api_key_response.text
        api_key = api_key_response.json()["api_key"]

        protected_response = await client.get(
            "/protected",
            headers={"X-API-Key": api_key},
        )

        assert protected_response.status_code == 200, protected_response.text
        assert protected_response.json() == {"ok": "yes"}
