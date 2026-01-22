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
async def test_create_entity_requires_tree_permission_in_parent(
    enterprise_app: FastAPI, enterprise_auth: EnterpriseRBAC
):
    async with enterprise_auth.get_session() as session:
        # Seed permissions
        await _seed_permissions(
            session,
            enterprise_auth,
            ["entity:create", "entity:create_tree", "entity:read"],
        )

        # Seed roles (global so they can be used across any entity)
        creator_tree_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="creator_tree",
            display_name="creator_tree",
            permission_names=["entity:create_tree"],
            is_global=True,
        )
        creator_base_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="creator_base",
            display_name="creator_base",
            permission_names=["entity:create"],
            is_global=True,
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
        await _seed_permissions(
            session,
            enterprise_auth,
            [
                "entity:create",
                "entity:create_tree",
                "entity:update",
                "entity:update_tree",
            ],
        )

        # Roles (global so they can be used across any entity):
        # - mover: can update entities (tree required by deps when entity_id context exists)
        # - parent_creator: can create under a parent (tree)
        mover_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="mover",
            display_name="mover",
            permission_names=["entity:update_tree"],
            is_global=True,
        )
        parent_creator_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="parent_creator",
            display_name="parent_creator",
            permission_names=["entity:create_tree"],
            is_global=True,
        )

        user = await enterprise_auth.user_service.create_user(
            session=session,
            email="mover@example.com",
            password="TestPass123!",
            first_name="Mover",
            last_name="User",
        )

        # Seed entity hierarchy (all under one root organization):
        # root -> old_branch -> node -> leaf
        #      -> new_branch (target for move)
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="root",
            display_name="Root",
            slug="root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        old_branch = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="old_branch",
            display_name="Old Branch",
            slug="old-branch",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        node = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="node",
            display_name="Node",
            slug="node",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=old_branch.id,
        )
        leaf = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="leaf",
            display_name="Leaf",
            slug="leaf",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="project",
            parent_id=node.id,
        )
        new_branch = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="new_branch",
            display_name="New Branch",
            slug="new-branch",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )

        membership_service = MembershipService(enterprise_auth.config)
        # Must be able to update the moved entity (node context)
        await membership_service.add_member(
            session=session,
            entity_id=node.id,
            user_id=user.id,
            role_ids=[mover_role.id],
        )
        # Must be able to create under the target parent (new_branch context)
        await membership_service.add_member(
            session=session,
            entity_id=new_branch.id,
            user_id=user.id,
            role_ids=[parent_creator_role.id],
        )

        await session.commit()

        token = await _bearer_token(enterprise_auth, str(user.id))

    transport = httpx.ASGITransport(app=enterprise_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Move node under new_branch
        r = await client.post(
            f"/entities/{node.id}/move",
            json={"new_parent_id": str(new_branch.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        moved = r.json()
        assert moved["parent_entity_id"] == str(new_branch.id)

    # Verify closure/path/depth after move using the service directly.
    async with enterprise_auth.get_session() as session:
        node_fresh = await enterprise_auth.entity_service.get_entity(session, node.id)
        leaf_fresh = await enterprise_auth.entity_service.get_entity(session, leaf.id)
        old_branch_fresh = await enterprise_auth.entity_service.get_entity(
            session, old_branch.id
        )
        new_branch_fresh = await enterprise_auth.entity_service.get_entity(
            session, new_branch.id
        )

        assert node_fresh.parent_id == new_branch_fresh.id
        assert node_fresh.depth == new_branch_fresh.depth + 1
        assert leaf_fresh.depth == node_fresh.depth + 1

        assert node_fresh.path == f"{new_branch_fresh.path}{node_fresh.slug}/"
        assert leaf_fresh.path == f"{node_fresh.path}{leaf_fresh.slug}/"

        assert await enterprise_auth.entity_service.is_ancestor_of(
            session, new_branch_fresh.id, node_fresh.id
        )
        assert await enterprise_auth.entity_service.is_ancestor_of(
            session, new_branch_fresh.id, leaf_fresh.id
        )
        assert not await enterprise_auth.entity_service.is_ancestor_of(
            session, old_branch_fresh.id, node_fresh.id
        )
        assert not await enterprise_auth.entity_service.is_ancestor_of(
            session, old_branch_fresh.id, leaf_fresh.id
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_member_requires_membership_create_tree_in_target_context(
    enterprise_app: FastAPI, enterprise_auth: EnterpriseRBAC
):
    async with enterprise_auth.get_session() as session:
        # Seed permissions
        await _seed_permissions(
            session,
            enterprise_auth,
            ["membership:create", "membership:create_tree"],
        )

        # Create roles (global so they can be used across any entity)
        membership_tree_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="membership_tree",
            display_name="membership_tree",
            permission_names=["membership:create_tree"],
            is_global=True,
        )
        membership_base_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="membership_base",
            display_name="membership_base",
            permission_names=["membership:create"],
            is_global=True,
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_descendants_requires_entity_read_tree(
    enterprise_app: FastAPI, enterprise_auth: EnterpriseRBAC
):
    async with enterprise_auth.get_session() as session:
        await _seed_permissions(
            session,
            enterprise_auth,
            ["entity:read", "entity:read_tree"],
        )

        read_tree_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="entity_read_tree",
            display_name="entity_read_tree",
            permission_names=["entity:read_tree"],
            is_global=True,
        )
        read_base_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="entity_read_base",
            display_name="entity_read_base",
            permission_names=["entity:read"],
            is_global=True,
        )

        user_tree = await enterprise_auth.user_service.create_user(
            session=session,
            email="entity-read-tree@example.com",
            password="TestPass123!",
            first_name="Entity",
            last_name="Tree",
        )
        user_base = await enterprise_auth.user_service.create_user(
            session=session,
            email="entity-read-base@example.com",
            password="TestPass123!",
            first_name="Entity",
            last_name="Base",
        )

        org = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="org_desc",
            display_name="Org",
            slug="org-desc",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="team_desc",
            display_name="Team",
            slug="team-desc",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=org.id,
        )

        membership_service = MembershipService(enterprise_auth.config)
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=user_tree.id,
            role_ids=[read_tree_role.id],
        )
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=user_base.id,
            role_ids=[read_base_role.id],
        )

        await session.commit()

        token_tree = await _bearer_token(enterprise_auth, str(user_tree.id))
        token_base = await _bearer_token(enterprise_auth, str(user_base.id))

    transport = httpx.ASGITransport(app=enterprise_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.get(
            f"/entities/{org.id}/descendants",
            headers={"Authorization": f"Bearer {token_tree}"},
        )
        assert ok.status_code == 200, ok.text
        ids = {item["id"] for item in ok.json()}
        assert str(team.id) in ids

        forbidden = await client.get(
            f"/entities/{org.id}/descendants",
            headers={"Authorization": f"Bearer {token_base}"},
        )
        assert forbidden.status_code == 403, forbidden.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_members_requires_membership_read_tree(
    enterprise_app: FastAPI, enterprise_auth: EnterpriseRBAC
):
    async with enterprise_auth.get_session() as session:
        await _seed_permissions(
            session,
            enterprise_auth,
            ["membership:read", "membership:read_tree"],
        )

        membership_read_tree_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="membership_read_tree",
            display_name="membership_read_tree",
            permission_names=["membership:read_tree"],
            is_global=True,
        )
        membership_read_base_role = await enterprise_auth.role_service.create_role(
            session=session,
            name="membership_read_base",
            display_name="membership_read_base",
            permission_names=["membership:read"],
            is_global=True,
        )

        admin_tree = await enterprise_auth.user_service.create_user(
            session=session,
            email="membership-read-tree@example.com",
            password="TestPass123!",
            first_name="Membership",
            last_name="Tree",
        )
        admin_base = await enterprise_auth.user_service.create_user(
            session=session,
            email="membership-read-base@example.com",
            password="TestPass123!",
            first_name="Membership",
            last_name="Base",
        )
        member = await enterprise_auth.user_service.create_user(
            session=session,
            email="member@example.com",
            password="TestPass123!",
            first_name="Member",
            last_name="User",
        )

        org = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="org_mem_read",
            display_name="Org",
            slug="org-mem-read",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name="team_mem_read",
            display_name="Team",
            slug="team-mem-read",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=org.id,
        )

        membership_service = MembershipService(enterprise_auth.config)
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=admin_tree.id,
            role_ids=[membership_read_tree_role.id],
        )
        await membership_service.add_member(
            session=session,
            entity_id=org.id,
            user_id=admin_base.id,
            role_ids=[membership_read_base_role.id],
        )
        await membership_service.add_member(
            session=session, entity_id=team.id, user_id=member.id, role_ids=[]
        )
        await session.commit()

        token_tree = await _bearer_token(enterprise_auth, str(admin_tree.id))
        token_base = await _bearer_token(enterprise_auth, str(admin_base.id))

    transport = httpx.ASGITransport(app=enterprise_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.get(
            f"/entities/{org.id}/members",
            params={"page": 1, "limit": 50},
            headers={"Authorization": f"Bearer {token_tree}"},
        )
        assert ok.status_code == 200, ok.text

        forbidden = await client.get(
            f"/entities/{org.id}/members",
            params={"page": 1, "limit": 50},
            headers={"Authorization": f"Bearer {token_base}"},
        )
        assert forbidden.status_code == 403, forbidden.text
