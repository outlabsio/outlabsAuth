import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_api_key_admin_router
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
async def test_admin_api_key_router_returns_grantable_scopes_and_manages_entity_keys(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_admin_root_{unique}",
            display_name="API Key Admin Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_admin_department_{unique}",
            display_name="API Key Admin Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_admin_team_{unique}",
            display_name="API Key Admin Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-admin-user-{unique}@example.com",
            password="TestPass123!",
            first_name="Admin",
            last_name="User",
            root_entity_id=root.id,
        )

        permission_names = [
            "api_key:create_tree",
            "api_key:read_tree",
            "api_key:update_tree",
            "api_key:delete_tree",
            f"contacts{unique}:read_tree",
            f"reports{unique}:update",
            f"contacts{unique}:create",
            f"contacts{unique}:delete",
        ]
        permission_ids = []
        for permission_name in permission_names:
            permission = await enterprise_auth.permission_service.create_permission(
                session,
                name=permission_name,
                display_name=permission_name,
                description="admin api key endpoint test",
            )
            permission_ids.append(permission.id)

        role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_admin_role_{unique}",
            display_name="API Key Admin Role",
            is_global=False,
            root_entity_id=root.id,
        )
        await enterprise_auth.role_service.add_permissions(session, role.id, permission_ids)
        await enterprise_auth.membership_service.add_member(
            session=session,
            entity_id=department.id,
            user_id=user.id,
            role_ids=[role.id],
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
        department_uuid = department.id
        team_id = team.id
        user_id = str(user.id)
        read_scope = f"contacts{unique}:read_tree"
        update_scope = f"reports{unique}:update"

    client.headers.update({"Authorization": f"Bearer {token}"})

    grantable = await client.get(
        f"/v1/admin/entities/{department_id}/grantable-scopes",
        params={"owner_id": user_id, "inherit_from_tree": "true"},
    )
    assert grantable.status_code == 200, grantable.text
    grantable_data = grantable.json()
    assert grantable_data["allowed_key_kinds"] == ["personal"]
    assert grantable_data["personal_allowed_action_prefixes"] == ["read", "list", "search", "view", "get", "update"]
    assert read_scope in grantable_data["grantable_scopes"]
    assert update_scope in grantable_data["grantable_scopes"]
    assert f"contacts{unique}:create" not in grantable_data["grantable_scopes"]
    assert f"contacts{unique}:delete" not in grantable_data["grantable_scopes"]
    assert "api_key:read_tree" not in grantable_data["grantable_scopes"]

    created = await client.post(
        f"/v1/admin/entities/{department_id}/api-keys",
        json={
            "owner_id": user_id,
            "name": "Entity Admin Key",
            "scopes": [read_scope],
            "inherit_from_tree": True,
        },
    )
    assert created.status_code == 201, created.text
    created_data = created.json()
    key_id = created_data["id"]
    full_api_key = created_data["api_key"]
    assert created_data["key_kind"] == "personal"
    assert created_data["entity_ids"] == [department_id]
    assert created_data["owner_id"] == user_id
    assert created_data["is_currently_effective"] is True
    assert created_data["ineffective_reasons"] == []

    second_created = await client.post(
        f"/v1/admin/entities/{department_id}/api-keys",
        json={
            "owner_id": user_id,
            "name": "Viewer Search Key",
            "scopes": [update_scope],
        },
    )
    assert second_created.status_code == 201, second_created.text
    second_key_id = second_created.json()["id"]

    listed = await client.get(f"/v1/admin/entities/{department_id}/api-keys")
    assert listed.status_code == 200, listed.text
    listed_data = listed.json()
    assert listed_data["total"] == 2
    assert listed_data["page"] == 1
    assert listed_data["limit"] == 20
    assert listed_data["pages"] == 1
    assert {item["id"] for item in listed_data["items"]} == {key_id, second_key_id}

    paginated = await client.get(
        f"/v1/admin/entities/{department_id}/api-keys",
        params={
            "page": 1,
            "limit": 1,
            "owner_id": user_id,
            "key_kind": "personal",
            "status": "active",
        },
    )
    assert paginated.status_code == 200, paginated.text
    paginated_data = paginated.json()
    assert paginated_data["total"] == 2
    assert paginated_data["page"] == 1
    assert paginated_data["limit"] == 1
    assert paginated_data["pages"] == 2
    assert len(paginated_data["items"]) == 1

    searched = await client.get(
        f"/v1/admin/entities/{department_id}/api-keys",
        params={"search": "Viewer"},
    )
    assert searched.status_code == 200, searched.text
    searched_data = searched.json()
    assert searched_data["total"] == 1
    assert searched_data["items"][0]["id"] == second_key_id

    fetched = await client.get(f"/v1/admin/entities/{department_id}/api-keys/{key_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == key_id
    assert fetched.json()["is_currently_effective"] is True
    assert fetched.json()["ineffective_reasons"] == []

    async with enterprise_auth.get_session() as session:
        verified = await enterprise_auth.authorize_api_key(
            session,
            full_api_key,
            required_scope=read_scope.replace("_tree", ""),
            entity_id=team_id,
        )
        assert verified is not None
        assert verified["metadata"]["key_id"] == key_id
        assert verified["metadata"]["key_kind"] == "personal"
        assert verified["metadata"]["is_currently_effective"] is True
        assert verified["metadata"]["ineffective_reasons"] == []

    updated = await client.patch(
        f"/v1/admin/entities/{department_id}/api-keys/{key_id}",
        json={
            "name": "Updated Entity Admin Key",
            "scopes": [update_scope],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated Entity Admin Key"
    assert updated.json()["scopes"] == [update_scope]

    async with enterprise_auth.get_session() as session:
        denied = await enterprise_auth.authorize_api_key(
            session,
            full_api_key,
            required_scope=read_scope.replace("_tree", ""),
            entity_id=team_id,
        )
        assert denied is None
        updated_verified = await enterprise_auth.authorize_api_key(
            session,
            full_api_key,
            required_scope=update_scope,
            entity_id=department_uuid,
        )
        assert updated_verified is not None
        assert updated_verified["metadata"]["scopes"] == [update_scope]

    rotated = await client.post(f"/v1/admin/entities/{department_id}/api-keys/{key_id}/rotate")
    assert rotated.status_code == 200, rotated.text
    rotated_data = rotated.json()
    rotated_key_id = rotated_data["id"]
    rotated_full_key = rotated_data["api_key"]
    assert rotated_key_id != key_id
    assert rotated_data["is_currently_effective"] is True

    async with enterprise_auth.get_session() as session:
        revoked = await enterprise_auth.authorize_api_key(
            session,
            full_api_key,
            required_scope=update_scope,
            entity_id=department_uuid,
        )
        assert revoked is None
        rotated_verified = await enterprise_auth.authorize_api_key(
            session,
            rotated_full_key,
            required_scope=update_scope,
            entity_id=department_uuid,
        )
        assert rotated_verified is not None

    revoked_list = await client.get(
        f"/v1/admin/entities/{department_id}/api-keys",
        params={"status": "revoked"},
    )
    assert revoked_list.status_code == 200, revoked_list.text
    revoked_data = revoked_list.json()
    assert revoked_data["total"] == 1
    assert revoked_data["items"][0]["id"] == key_id
    assert revoked_data["items"][0]["is_currently_effective"] is False
    assert "key_revoked" in revoked_data["items"][0]["ineffective_reasons"]

    rotated_search = await client.get(
        f"/v1/admin/entities/{department_id}/api-keys",
        params={"search": "rotated"},
    )
    assert rotated_search.status_code == 200, rotated_search.text
    rotated_search_data = rotated_search.json()
    assert rotated_search_data["total"] == 1
    assert rotated_search_data["items"][0]["id"] == rotated_key_id

    deleted = await client.delete(f"/v1/admin/entities/{department_id}/api-keys/{rotated_key_id}")
    assert deleted.status_code == 204, deleted.text

    async with enterprise_auth.get_session() as session:
        revoked = await enterprise_auth.authorize_api_key(
            session,
            rotated_full_key,
            required_scope=update_scope,
            entity_id=department_uuid,
        )
        assert revoked is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_api_key_router_rejects_cross_owner_personal_key_creation(
    client: httpx.AsyncClient,
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_admin_cross_owner_root_{unique}",
            display_name="API Key Admin Cross Owner Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-admin-cross-owner-admin-{unique}@example.com",
            password="AdminPass123!",
            first_name="Cross",
            last_name="Owner",
            is_superuser=True,
            root_entity_id=root.id,
        )
        owner = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-admin-cross-owner-target-{unique}@example.com",
            password="OwnerPass123!",
            first_name="Target",
            last_name="Owner",
            root_entity_id=root.id,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin.id)},
            secret_key=enterprise_auth.config.secret_key,
            algorithm=enterprise_auth.config.algorithm,
            audience=enterprise_auth.config.jwt_audience,
        )
        root_id = str(root.id)
        owner_id = str(owner.id)

    client.headers.update({"Authorization": f"Bearer {token}"})
    response = await client.post(
        f"/v1/admin/entities/{root_id}/api-keys",
        json={
            "owner_id": owner_id,
            "name": "Cross Owner Personal Key",
            "scopes": ["contacts:read"],
        },
    )
    assert response.status_code == 400, response.text
    assert "managed by their owner" in response.json()["message"].lower()
