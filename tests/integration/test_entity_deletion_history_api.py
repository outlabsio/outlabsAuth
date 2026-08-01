import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import (
    get_auth_router,
    get_entities_router,
    get_memberships_router,
    get_roles_router,
    get_users_router,
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
    app.include_router(get_auth_router(enterprise_auth, prefix="/v1/auth"))
    app.include_router(get_users_router(enterprise_auth, prefix="/v1/users"))
    app.include_router(get_roles_router(enterprise_auth, prefix="/v1/roles"))
    app.include_router(get_entities_router(enterprise_auth, prefix="/v1/entities"))
    app.include_router(get_memberships_router(enterprise_auth, prefix="/v1/memberships"))
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


@pytest_asyncio.fixture
async def admin_user(enterprise_auth: EnterpriseRBAC) -> dict:
    async with enterprise_auth.get_session() as session:
        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

    return {
        "id": str(admin.id),
        "token": create_access_token(
            {"sub": str(admin.id)},
            secret_key=enterprise_auth.config.secret_key,
            algorithm=enterprise_auth.config.algorithm,
        ),
    }


def _token_for_user(auth: EnterpriseRBAC, user_id: str) -> str:
    return create_access_token(
        {"sub": user_id},
        secret_key=auth.config.secret_key,
        algorithm=auth.config.algorithm,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_leaf_delete_creates_history_marks_orphan_and_clears_orphan_after_reassignment(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    async with enterprise_auth.get_session() as session:
        await enterprise_auth.permission_service.create_permission(
            session,
            "membership:read_tree",
            "Membership Read Tree",
        )
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"root_{unique}",
            display_name="Acme Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        office_a = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"office_a_{unique}",
            display_name="Office Alpha",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        office_b = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"office_b_{unique}",
            display_name="Office Beta",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        office_a_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"office_alpha_reader_{unique}",
            display_name="Office Alpha Reader",
            permission_names=["membership:read_tree"],
            is_global=False,
            root_entity_id=root.id,
            scope_entity_id=office_a.id,
        )
        office_b_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"office_beta_reader_{unique}",
            display_name="Office Beta Reader",
            permission_names=["membership:read_tree"],
            is_global=False,
            root_entity_id=root.id,
            scope_entity_id=office_b.id,
        )
        user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"member-{unique}@example.com",
            password="MemberPass123!",
            first_name="Member",
            last_name="Target",
        )
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=office_a.id,
            user_id=user.id,
            role_ids=[office_a_role.id],
            joined_by_id=uuid.UUID(admin_user["id"]),
        )
        await session.commit()

        user_id = str(user.id)
        office_a_id = str(office_a.id)
        office_b_id = str(office_b.id)

    user_headers = {"Authorization": f"Bearer {_token_for_user(enterprise_auth, user_id)}"}
    admin_headers = {"Authorization": f"Bearer {admin_user['token']}"}

    before_delete = await client.get(f"/v1/memberships/entity/{office_a_id}", headers=user_headers)
    assert before_delete.status_code == 200, before_delete.text

    delete_resp = await client.delete(f"/v1/entities/{office_a_id}", headers=admin_headers)
    assert delete_resp.status_code == 204, delete_resp.text

    after_delete = await client.get(f"/v1/memberships/entity/{office_a_id}", headers=user_headers)
    assert after_delete.status_code == 403, after_delete.text

    orphaned_resp = await client.get("/v1/users/orphaned", headers=admin_headers)
    assert orphaned_resp.status_code == 200, orphaned_resp.text
    orphaned_items = orphaned_resp.json()["items"]
    orphaned_item = next(item for item in orphaned_items if item["user"]["id"] == user_id)
    assert orphaned_item["last_membership_event_type"] == "entity_archived"
    assert orphaned_item["last_entity_id"] == office_a_id
    assert orphaned_item["last_entity_name"] == "Office Alpha"

    history_resp = await client.get(
        f"/v1/users/{user_id}/membership-history",
        headers=admin_headers,
    )
    assert history_resp.status_code == 200, history_resp.text
    history_items = history_resp.json()["items"]
    assert [item["event_type"] for item in history_items][:2] == ["entity_archived", "created"]
    archive_event = history_items[0]
    assert archive_event["entity_path"] == ["Acme Root", "Office Alpha"]

    async with enterprise_auth.get_session() as session:
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=uuid.UUID(office_b_id),
            user_id=uuid.UUID(user_id),
            role_ids=[office_b_role.id],
            joined_by_id=uuid.UUID(admin_user["id"]),
        )
        await session.commit()

    orphaned_after_reassign = await client.get("/v1/users/orphaned", headers=admin_headers)
    assert orphaned_after_reassign.status_code == 200, orphaned_after_reassign.text
    assert all(item["user"]["id"] != user_id for item in orphaned_after_reassign.json()["items"])

    history_after_reassign = await client.get(
        f"/v1/users/{user_id}/membership-history",
        headers=admin_headers,
    )
    assert history_after_reassign.status_code == 200, history_after_reassign.text
    assert any(
        item["entity_id"] == office_b_id and item["event_type"] == "created"
        for item in history_after_reassign.json()["items"]
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cascade_delete_archives_descendants_and_revokes_root_scoped_direct_roles(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    async with enterprise_auth.get_session() as session:
        await enterprise_auth.permission_service.create_permission(
            session,
            "membership:read_tree",
            "Membership Read Tree",
        )
        await enterprise_auth.permission_service.create_permission(
            session,
            "role:read",
            "Role Read",
        )
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"cascade_root_{unique}",
            display_name="Cascade Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        region = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"cascade_region_{unique}",
            display_name="Cascade Region",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        office = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"cascade_office_{unique}",
            display_name="Cascade Office",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=region.id,
        )
        direct_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"root_reader_{unique}",
            display_name="Root Reader",
            permission_names=["role:read"],
            is_global=False,
            root_entity_id=root.id,
        )
        office_role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"office_membership_reader_{unique}",
            display_name="Office Membership Reader",
            permission_names=["membership:read_tree"],
            is_global=False,
            root_entity_id=root.id,
            scope_entity_id=office.id,
        )
        direct_user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"direct-{unique}@example.com",
            password="DirectPass123!",
            first_name="Direct",
            last_name="User",
            root_entity_id=root.id,
        )
        office_user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"office-{unique}@example.com",
            password="OfficePass123!",
            first_name="Office",
            last_name="User",
        )
        await enterprise_auth.role_service.assign_role_to_user(
            session=session,
            user_id=direct_user.id,
            role_id=direct_role.id,
            assigned_by_id=uuid.UUID(admin_user["id"]),
        )
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=office.id,
            user_id=office_user.id,
            role_ids=[office_role.id],
            joined_by_id=uuid.UUID(admin_user["id"]),
        )
        await session.commit()

        root_id = str(root.id)
        region_id = str(region.id)
        office_id = str(office.id)
        direct_user_id = str(direct_user.id)
        office_user_id = str(office_user.id)

    direct_headers = {"Authorization": f"Bearer {_token_for_user(enterprise_auth, direct_user_id)}"}
    admin_headers = {"Authorization": f"Bearer {admin_user['token']}"}

    before_delete = await client.get(
        "/v1/roles/",
        headers=direct_headers,
        params={"root_entity_id": root_id},
    )
    assert before_delete.status_code == 200, before_delete.text

    delete_resp = await client.delete(
        f"/v1/entities/{root_id}",
        headers=admin_headers,
        params={"cascade": "true"},
    )
    assert delete_resp.status_code == 204, delete_resp.text

    root_resp = await client.get(f"/v1/entities/{root_id}", headers=admin_headers)
    region_resp = await client.get(f"/v1/entities/{region_id}", headers=admin_headers)
    office_resp = await client.get(f"/v1/entities/{office_id}", headers=admin_headers)
    assert root_resp.status_code == 200, root_resp.text
    assert region_resp.status_code == 200, region_resp.text
    assert office_resp.status_code == 200, office_resp.text
    assert root_resp.json()["status"] == "archived"
    assert region_resp.json()["status"] == "archived"
    assert office_resp.json()["status"] == "archived"

    after_delete = await client.get(
        "/v1/roles/",
        headers=direct_headers,
        params={"root_entity_id": root_id},
    )
    assert after_delete.status_code == 403, after_delete.text

    orphaned_resp = await client.get("/v1/users/orphaned", headers=admin_headers)
    assert orphaned_resp.status_code == 200, orphaned_resp.text
    orphaned_ids = {item["user"]["id"] for item in orphaned_resp.json()["items"]}
    assert office_user_id in orphaned_ids
    assert direct_user_id not in orphaned_ids

    history_resp = await client.get(
        f"/v1/users/{office_user_id}/membership-history",
        headers=admin_headers,
        params={"entity_id": office_id},
    )
    assert history_resp.status_code == 200, history_resp.text
    history_items = history_resp.json()["items"]
    assert [item["event_type"] for item in history_items][:2] == ["entity_archived", "created"]
    assert history_items[0]["entity_path"] == ["Cascade Root", "Cascade Region", "Cascade Office"]
