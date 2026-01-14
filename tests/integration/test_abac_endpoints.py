import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import OutlabsAuth
from outlabs_auth.models.sql.role import RoleCondition
from outlabs_auth.routers import get_permissions_router
from outlabs_auth.services.role import RoleService
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def auth(test_engine) -> OutlabsAuth:
    auth = OutlabsAuth(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_abac=True,
    )
    await auth.initialize()
    return auth


@pytest_asyncio.fixture
async def app(auth: OutlabsAuth) -> FastAPI:
    app = FastAPI()
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
async def user_token(auth: OutlabsAuth) -> str:
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

        user = await auth.user_service.create_user(
            session=session,
            email=f"abac-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="ABAC",
            last_name="User",
        )

        # Assign role (SimpleRBAC membership table)
        await auth.role_service.assign_role_to_user(
            session=session,
            user_id=user.id,
            role_id=role.id,
        )

        await session.commit()

    return create_access_token(
        {"sub": str(user.id)},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abac_role_condition_denies_when_env_mismatch(
    auth: OutlabsAuth, client: httpx.AsyncClient, user_token: str
):
    # Attach ABAC condition to the user's role: env.method must be GET (but endpoint is POST).
    async with auth.get_session() as session:
        role = await auth.role_service.get_role_by_name(session, "abac_tester")
        assert role is not None
        session.add(
            RoleCondition(
                role_id=role.id,
                attribute="env.method",
                operator="equals",
                value="GET",
                value_type="string",
            )
        )
        await session.commit()

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
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 403, r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abac_role_condition_allows_when_env_matches(
    auth: OutlabsAuth, client: httpx.AsyncClient, user_token: str
):
    # Clear existing conditions and set env.method must be POST.
    async with auth.get_session() as session:
        role = await auth.role_service.get_role_by_name(session, "abac_tester")
        assert role is not None
        await session.execute(
            RoleCondition.__table__.delete().where(RoleCondition.role_id == role.id)
        )
        session.add(
            RoleCondition(
                role_id=role.id,
                attribute="env.method",
                operator="equals",
                value="POST",
                value_type="string",
            )
        )
        await session.commit()

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
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 201, r.text
