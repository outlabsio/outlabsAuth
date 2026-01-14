import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers.entities import get_entities_router
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def enterprise_auth(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
    )
    await auth.initialize()
    return auth


@pytest_asyncio.fixture
async def enterprise_app(enterprise_auth: EnterpriseRBAC) -> FastAPI:
    app = FastAPI()
    app.include_router(get_entities_router(enterprise_auth, prefix="/entities"))
    return app


async def _bearer_token(auth: EnterpriseRBAC, user_id: str) -> str:
    return create_access_token(
        {"sub": user_id},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
        audience=auth.config.jwt_audience,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_entity_requires_tree_permission_in_parent(
    enterprise_app: FastAPI, enterprise_auth: EnterpriseRBAC
):
    async with enterprise_auth.get_session() as session:
        # Seed permissions
        for name in ("entity:create", "entity:create_tree", "entity:read"):
            await enterprise_auth.permission_service.create_permission(
                session=session,
                name=name,
                display_name=name,
                description=name,
                is_system=True,
            )

        # Seed roles
        creator_tree_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="creator_tree",
            display_name="creator_tree",
            permission_names=["entity:create_tree"],
            is_global=False,
        )
        creator_base_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="creator_base",
            display_name="creator_base",
            permission_names=["entity:create"],
            is_global=False,
        )

        # Seed users
        user_tree = await enterprise_auth.user_service.create_user(
            session=session,
            email="tree@example.com",
            password="TestPass123!",
            first_name="Tree",
            last_name="User",
        )
        user_base = await enterprise_auth.user_service.create_user(
            session=session,
            email="base@example.com",
            password="TestPass123!",
            first_name="Base",
            last_name="User",
        )

        # Seed entity hierarchy
        org = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="org",
            display_name="Org",
            slug="org",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

        # Seed memberships (EnterpriseRBAC)
        membership_service = MembershipService(enterprise_auth.config)
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=user_tree.id,
            role_ids=[creator_tree_role.id],
        )
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=user_base.id,
            role_ids=[creator_base_role.id],
        )

        await session.commit()

        token_tree = await _bearer_token(enterprise_auth, str(user_tree.id))
        token_base = await _bearer_token(enterprise_auth, str(user_base.id))

    transport = httpx.ASGITransport(app=enterprise_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": "team",
            "display_name": "Team",
            "slug": "team",
            "description": None,
            "entity_class": "structural",
            "entity_type": "team",
            "parent_entity_id": str(org.id),
            "status": "active",
        }

        # User with create_tree can create child entities.
        r_ok = await client.post(
            "/entities/",
            json=payload,
            headers={"Authorization": f"Bearer {token_tree}"},
        )
        assert r_ok.status_code == 201, r_ok.text

        # User with only base create is denied when a parent context exists.
        payload["slug"] = "team2"
        payload["name"] = "team2"
        payload["display_name"] = "Team 2"
        r_forbidden = await client.post(
            "/entities/",
            json=payload,
            headers={"Authorization": f"Bearer {token_base}"},
        )
        assert r_forbidden.status_code == 403, r_forbidden.text
