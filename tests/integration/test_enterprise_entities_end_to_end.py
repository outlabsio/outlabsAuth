import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers.entities import get_entities_router
from outlabs_auth.routers.memberships import get_memberships_router
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
    app.include_router(get_memberships_router(enterprise_auth, prefix="/memberships"))
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_move_entity_requires_update_on_entity_and_create_tree_on_new_parent(
    enterprise_app: FastAPI, enterprise_auth: EnterpriseRBAC
):
    async with enterprise_auth.get_session() as session:
        # Seed permissions
        for name in (
            "entity:create",
            "entity:create_tree",
            "entity:update",
            "entity:update_tree",
        ):
            await enterprise_auth.permission_service.create_permission(
                session=session,
                name=name,
                display_name=name,
                description=name,
                is_system=True,
            )

        # Roles:
        # - mover: can update entities (tree required by deps when entity_id context exists)
        # - parent_creator: can create under a parent (tree)
        mover_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="mover",
            display_name="mover",
            permission_names=["entity:update_tree"],
            is_global=False,
        )
        parent_creator_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="parent_creator",
            display_name="parent_creator",
            permission_names=["entity:create_tree"],
            is_global=False,
        )

        user = await enterprise_auth.user_service.create_user(
            session=session,
            email="mover@example.com",
            password="TestPass123!",
            first_name="Mover",
            last_name="User",
        )

        # Seed entity hierarchy:
        # old_root -> node -> leaf
        # new_root
        old_root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="old_root",
            display_name="Old Root",
            slug="old-root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="root",
        )
        node = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="node",
            display_name="Node",
            slug="node",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="node",
            parent_id=old_root.id,
        )
        leaf = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="leaf",
            display_name="Leaf",
            slug="leaf",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="leaf",
            parent_id=node.id,
        )
        new_root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="new_root",
            display_name="New Root",
            slug="new-root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="root",
        )

        membership_service = MembershipService(enterprise_auth.config)
        # Must be able to update the moved entity (node context)
        await membership_service.add_member(
            session=session,
            entity_id=node.id,
            user_id=user.id,
            role_ids=[mover_role.id],
        )
        # Must be able to create under the target parent (new_root context)
        await membership_service.add_member(
            session=session,
            entity_id=new_root.id,
            user_id=user.id,
            role_ids=[parent_creator_role.id],
        )

        await session.commit()

        token = await _bearer_token(enterprise_auth, str(user.id))

    transport = httpx.ASGITransport(app=enterprise_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Move node under new_root
        r = await client.post(
            f"/entities/{node.id}/move",
            json={"new_parent_id": str(new_root.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        moved = r.json()
        assert moved["parent_entity_id"] == str(new_root.id)

    # Verify closure/path/depth after move using the service directly.
    async with enterprise_auth.get_session() as session:
        node_fresh = await enterprise_auth.entity_service.get_entity(session, node.id)
        leaf_fresh = await enterprise_auth.entity_service.get_entity(session, leaf.id)
        old_root_fresh = await enterprise_auth.entity_service.get_entity(
            session, old_root.id
        )
        new_root_fresh = await enterprise_auth.entity_service.get_entity(
            session, new_root.id
        )

        assert node_fresh.parent_id == new_root_fresh.id
        assert node_fresh.depth == new_root_fresh.depth + 1
        assert leaf_fresh.depth == node_fresh.depth + 1

        assert node_fresh.path == f"{new_root_fresh.path}{node_fresh.slug}/"
        assert leaf_fresh.path == f"{node_fresh.path}{leaf_fresh.slug}/"

        assert await enterprise_auth.entity_service.is_ancestor_of(
            session, new_root_fresh.id, node_fresh.id
        )
        assert await enterprise_auth.entity_service.is_ancestor_of(
            session, new_root_fresh.id, leaf_fresh.id
        )
        assert not await enterprise_auth.entity_service.is_ancestor_of(
            session, old_root_fresh.id, node_fresh.id
        )
        assert not await enterprise_auth.entity_service.is_ancestor_of(
            session, old_root_fresh.id, leaf_fresh.id
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_member_requires_membership_create_tree_in_target_context(
    enterprise_app: FastAPI, enterprise_auth: EnterpriseRBAC
):
    async with enterprise_auth.get_session() as session:
        # Seed permissions
        for name in ("membership:create", "membership:create_tree"):
            await enterprise_auth.permission_service.create_permission(
                session=session,
                name=name,
                display_name=name,
                description=name,
                is_system=True,
            )

        # Create roles
        membership_tree_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="membership_tree",
            display_name="membership_tree",
            permission_names=["membership:create_tree"],
            is_global=False,
        )
        membership_base_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="membership_base",
            display_name="membership_base",
            permission_names=["membership:create"],
            is_global=False,
        )

        # Create users
        admin_tree = await enterprise_auth.user_service.create_user(
            session=session,
            email="member-tree@example.com",
            password="TestPass123!",
            first_name="Member",
            last_name="Tree",
        )
        admin_base = await enterprise_auth.user_service.create_user(
            session=session,
            email="member-base@example.com",
            password="TestPass123!",
            first_name="Member",
            last_name="Base",
        )
        target_user = await enterprise_auth.user_service.create_user(
            session=session,
            email="target@example.com",
            password="TestPass123!",
            first_name="Target",
            last_name="User",
        )

        # Entity hierarchy: org -> team
        org = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="org_membership",
            display_name="Org",
            slug="org-membership",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="team_membership",
            display_name="Team",
            slug="team-membership",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=org.id,
        )

        membership_service = MembershipService(enterprise_auth.config)
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=admin_tree.id,
            role_ids=[membership_tree_role.id],
        )
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=admin_base.id,
            role_ids=[membership_base_role.id],
        )

        await session.commit()

        token_tree = await _bearer_token(enterprise_auth, str(admin_tree.id))
        token_base = await _bearer_token(enterprise_auth, str(admin_base.id))

    transport = httpx.ASGITransport(app=enterprise_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "entity_id": str(team.id),
            "user_id": str(target_user.id),
            "role_ids": [],
        }

        r_ok = await client.post(
            "/memberships/",
            json=payload,
            headers={"Authorization": f"Bearer {token_tree}"},
        )
        assert r_ok.status_code == 201, r_ok.text

        # Base permission should not cascade to descendants.
        payload["user_id"] = payload["user_id"]  # explicit, same payload structure
        r_forbidden = await client.post(
            "/memberships/",
            json=payload,
            headers={"Authorization": f"Bearer {token_base}"},
        )
        assert r_forbidden.status_code == 403, r_forbidden.text
