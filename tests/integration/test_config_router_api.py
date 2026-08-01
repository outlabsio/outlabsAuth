from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.system_config import DEFAULT_ENTITY_TYPE_CONFIG
from outlabs_auth.routers import get_config_router
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
    app.include_router(get_config_router(auth_instance, prefix="/v1/config"))
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


async def _create_user(auth_instance: EnterpriseRBAC, *, is_superuser: bool) -> dict:
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"config-{uuid.uuid4().hex[:8]}@example.com",
            password="ConfigPass123!",
            first_name="Config",
            last_name="User",
            is_superuser=is_superuser,
        )
        await session.commit()

    token = create_access_token(
        {"sub": str(user.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
    )
    return {"id": str(user.id), "token": token}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_config_router_public_get_returns_seeded_entity_type_config(
    client: httpx.AsyncClient,
):
    response = await client.get("/v1/config/entity-types")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["allowed_root_types"] == DEFAULT_ENTITY_TYPE_CONFIG["allowed_root_types"]
    assert payload["default_child_types"] == DEFAULT_ENTITY_TYPE_CONFIG["default_child_types"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_config_router_put_requires_superuser(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
):
    regular_user = await _create_user(auth_instance, is_superuser=False)

    response = await client.put(
        "/v1/config/entity-types",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
        json={
            "allowed_root_types": {
                "structural": ["organization", "workspace"],
                "access_group": ["permission_group"],
            },
        },
    )

    assert response.status_code == 403, response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_config_router_superuser_update_merges_and_persists_configuration(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
):
    admin_user = await _create_user(auth_instance, is_superuser=True)

    update_response = await client.put(
        "/v1/config/entity-types",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "default_child_types": {
                "structural": ["department", "team", "division"],
                "access_group": ["admin_group"],
            }
        },
    )

    assert update_response.status_code == 200, update_response.text
    payload = update_response.json()
    assert payload["allowed_root_types"] == DEFAULT_ENTITY_TYPE_CONFIG["allowed_root_types"]
    assert payload["default_child_types"] == {
        "structural": ["department", "team", "division"],
        "access_group": ["admin_group"],
    }

    readback_response = await client.get("/v1/config/entity-types")
    assert readback_response.status_code == 200, readback_response.text
    assert readback_response.json()["default_child_types"] == payload["default_child_types"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_config_router_rejects_empty_allowed_root_types_payload(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
):
    admin_user = await _create_user(auth_instance, is_superuser=True)

    response = await client.put(
        "/v1/config/entity-types",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"allowed_root_types": {"structural": [], "access_group": []}},
    )

    assert response.status_code == 400, response.text
