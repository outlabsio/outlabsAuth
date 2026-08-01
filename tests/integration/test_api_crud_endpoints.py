import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import APIKeyStatus, DefinitionStatus, EntityClass, UserStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user_audit_event import UserAuditEvent
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.routers import (
    get_api_keys_router,
    get_auth_router,
    get_entities_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token


async def _create_api_key_anchor_entity(client: httpx.AsyncClient, *, label: str) -> str:
    response = await client.post(
        "/v1/entities/",
        json={
            "name": f"{label}-{uuid.uuid4().hex[:8]}",
            "display_name": f"{label.title()} Entity",
            "slug": f"{label}-{uuid.uuid4().hex[:8]}",
            "entity_class": EntityClass.STRUCTURAL.value,
            "entity_type": "organization",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


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
    app.include_router(get_auth_router(enterprise_auth, prefix="/v1/auth"))
    app.include_router(get_users_router(enterprise_auth, prefix="/v1/users"))
    app.include_router(get_roles_router(enterprise_auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(enterprise_auth, prefix="/v1/permissions"))
    app.include_router(get_api_keys_router(enterprise_auth, prefix="/v1/api-keys"))
    app.include_router(get_entities_router(enterprise_auth, prefix="/v1/entities"))
    app.include_router(get_memberships_router(enterprise_auth, prefix="/v1/memberships"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_token(enterprise_auth: EnterpriseRBAC) -> str:
    async with enterprise_auth.get_session() as session:
        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email="admin@example.com",
            password="TestPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

    return create_access_token(
        {"sub": str(admin.id)},
        secret_key=enterprise_auth.config.secret_key,
        algorithm=enterprise_auth.config.algorithm,
        audience=enterprise_auth.config.jwt_audience,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_register_login_refresh(client: httpx.AsyncClient):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"

    r_register = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert r_register.status_code == 201, r_register.text

    r_login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r_login.status_code == 200, r_login.text
    tokens = r_login.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    r_refresh = await client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r_refresh.status_code == 200, r_refresh.text
    refreshed = r_refresh.json()
    assert "access_token" in refreshed and refreshed["access_token"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_crud(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    r_me = await client.get("/v1/users/me")
    assert r_me.status_code == 200, r_me.text

    email = f"created-{uuid.uuid4().hex[:8]}@example.com"
    r_create = await client.post(
        "/v1/users/",
        json={
            "email": email,
            "password": "TestPass123!",
            "first_name": "Created",
            "last_name": "User",
            "is_superuser": False,
        },
    )
    assert r_create.status_code == 201, r_create.text
    created = r_create.json()
    user_id = created["id"]

    r_list = await client.get("/v1/users/", params={"page": 1, "limit": 20})
    assert r_list.status_code == 200, r_list.text
    assert any(item["id"] == user_id for item in r_list.json()["items"])

    r_get = await client.get(f"/v1/users/{user_id}")
    assert r_get.status_code == 200, r_get.text

    r_update = await client.patch(f"/v1/users/{user_id}", json={"first_name": "Updated"})
    assert r_update.status_code == 200, r_update.text
    assert r_update.json()["first_name"] == "Updated"

    r_delete = await client.delete(f"/v1/users/{user_id}")
    assert r_delete.status_code == 204, r_delete.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_responses_and_filters_match_admin_ui_contract(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    root_name = f"org-{uuid.uuid4().hex[:8]}"
    root_resp = await client.post(
        "/v1/entities/",
        json={
            "name": root_name,
            "display_name": "Scoped Organization",
            "slug": root_name,
            "entity_class": EntityClass.STRUCTURAL.value,
            "entity_type": "organization",
        },
    )
    assert root_resp.status_code == 201, root_resp.text
    root_id = root_resp.json()["id"]

    scoped_email = f"scoped-{uuid.uuid4().hex[:8]}@example.com"
    scoped_resp = await client.post(
        "/v1/users/",
        json={
            "email": scoped_email,
            "password": "TestPass123!",
            "first_name": "Scoped",
            "last_name": "User",
            "root_entity_id": root_id,
        },
    )
    assert scoped_resp.status_code == 201, scoped_resp.text
    scoped_user = scoped_resp.json()

    assert scoped_user["root_entity_id"] == root_id
    assert "created_at" in scoped_user
    assert "updated_at" in scoped_user
    assert "last_login" in scoped_user
    assert "last_activity" in scoped_user
    assert "last_password_change" in scoped_user

    status_resp = await client.patch(
        f"/v1/users/{scoped_user['id']}/status",
        json={"status": "suspended"},
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["status"] == "suspended"

    filtered_by_status = await client.get(
        "/v1/users/",
        params={"status": "suspended"},
    )
    assert filtered_by_status.status_code == 200, filtered_by_status.text
    assert [item["id"] for item in filtered_by_status.json()["items"]] == [scoped_user["id"]]

    filtered_by_root = await client.get(
        "/v1/users/",
        params={"root_entity_id": root_id},
    )
    assert filtered_by_root.status_code == 200, filtered_by_root.text
    assert [item["id"] for item in filtered_by_root.json()["items"]] == [scoped_user["id"]]

    filtered_superusers = await client.get(
        "/v1/users/",
        params={"is_superuser": "true"},
    )
    assert filtered_superusers.status_code == 200, filtered_superusers.text
    assert all(item["is_superuser"] is True for item in filtered_superusers.json()["items"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_and_roles_crud(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    perm_name = f"demo:{uuid.uuid4().hex[:6]}"
    r_perm_create = await client.post(
        "/v1/permissions/",
        json={
            "name": perm_name,
            "display_name": "Demo Permission",
            "description": "integration test",
            "is_system": False,
            "is_active": True,
            "tags": ["frontend", "contract"],
        },
    )
    assert r_perm_create.status_code == 201, r_perm_create.text
    perm = r_perm_create.json()
    perm_id = perm["id"]
    assert perm["status"] == "active"
    assert perm["tags"] == ["frontend", "contract"]

    r_perm_get = await client.get(f"/v1/permissions/{perm_id}")
    assert r_perm_get.status_code == 200, r_perm_get.text
    assert r_perm_get.json()["tags"] == ["frontend", "contract"]

    r_perm_list = await client.get("/v1/permissions/", params={"page": 1, "limit": 1000})
    assert r_perm_list.status_code == 200, r_perm_list.text
    listed_perm = next(item for item in r_perm_list.json()["items"] if item["id"] == perm_id)
    assert listed_perm["tags"] == ["frontend", "contract"]

    r_perm_update = await client.patch(
        f"/v1/permissions/{perm_id}",
        json={"display_name": "Demo Permission Updated", "is_active": True},
    )
    assert r_perm_update.status_code == 200, r_perm_update.text
    assert r_perm_update.json()["display_name"] == "Demo Permission Updated"

    root_name = f"role-root-{uuid.uuid4().hex[:8]}"
    r_root_create = await client.post(
        "/v1/entities/",
        json={
            "name": root_name,
            "display_name": "Role Root",
            "slug": root_name,
            "entity_class": EntityClass.STRUCTURAL.value,
            "entity_type": "organization",
        },
    )
    assert r_root_create.status_code == 201, r_root_create.text
    root_id = r_root_create.json()["id"]

    role_name = f"demo_role_{uuid.uuid4().hex[:6]}"
    r_role_create = await client.post(
        "/v1/roles/",
        json={
            "name": role_name,
            "display_name": "Demo Role",
            "description": "integration test",
            "permissions": [perm_name],
            "is_global": False,
            "root_entity_id": root_id,
            "assignable_at_types": ["department"],
        },
    )
    assert r_role_create.status_code == 201, r_role_create.text
    role = r_role_create.json()
    role_id = role["id"]
    assert role["assignable_at_types"] == ["department"]
    assert role["status"] == "active"
    assert "entity_type_permissions" not in role

    r_role_get = await client.get(f"/v1/roles/{role_id}")
    assert r_role_get.status_code == 200, r_role_get.text
    assert r_role_get.json()["assignable_at_types"] == ["department"]
    assert "entity_type_permissions" not in r_role_get.json()

    r_role_update = await client.patch(
        f"/v1/roles/{role_id}",
        json={"display_name": "Demo Role Updated", "assignable_at_types": ["team"]},
    )
    assert r_role_update.status_code == 200, r_role_update.text
    assert r_role_update.json()["assignable_at_types"] == ["team"]
    assert "entity_type_permissions" not in r_role_update.json()

    r_role_delete = await client.delete(f"/v1/roles/{role_id}")
    assert r_role_delete.status_code == 204, r_role_delete.text

    r_perm_delete = await client.delete(f"/v1/permissions/{perm_id}")
    assert r_perm_delete.status_code == 204, r_perm_delete.text

    r_perm_missing = await client.get(f"/v1/permissions/{perm_id}")
    assert r_perm_missing.status_code == 404, r_perm_missing.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deleted_roles_and_permissions_are_retained_but_hidden(
    client: httpx.AsyncClient,
    admin_token: str,
    enterprise_auth: EnterpriseRBAC,
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    permission_name = f"retained:{uuid.uuid4().hex[:6]}"
    create_permission_response = await client.post(
        "/v1/permissions/",
        json={
            "name": permission_name,
            "display_name": "Retained Permission",
            "description": "retained delete contract",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
    )
    assert create_permission_response.status_code == 201, create_permission_response.text
    permission_id = create_permission_response.json()["id"]

    create_role_response = await client.post(
        "/v1/roles/",
        json={
            "name": f"retained-role-{uuid.uuid4().hex[:6]}",
            "display_name": "Retained Role",
            "permissions": [permission_name],
            "is_global": True,
        },
    )
    assert create_role_response.status_code == 201, create_role_response.text
    role_id = create_role_response.json()["id"]

    delete_role_response = await client.delete(f"/v1/roles/{role_id}")
    assert delete_role_response.status_code == 204, delete_role_response.text
    delete_permission_response = await client.delete(f"/v1/permissions/{permission_id}")
    assert delete_permission_response.status_code == 204, delete_permission_response.text

    hidden_role_response = await client.get(f"/v1/roles/{role_id}")
    assert hidden_role_response.status_code == 404, hidden_role_response.text
    hidden_permission_response = await client.get(f"/v1/permissions/{permission_id}")
    assert hidden_permission_response.status_code == 404, hidden_permission_response.text

    async with enterprise_auth.get_session() as session:
        archived_role = await session.get(Role, uuid.UUID(role_id))
        archived_permission = await session.get(Permission, uuid.UUID(permission_id))
        assert archived_role is not None
        assert archived_permission is not None
        assert archived_role.status == DefinitionStatus.ARCHIVED
        assert archived_permission.status == DefinitionStatus.ARCHIVED
        assert archived_permission.is_active is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_search_and_permission_array_payloads(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    first_perm_name = f"alpha:{uuid.uuid4().hex[:6]}"
    second_perm_name = f"beta:{uuid.uuid4().hex[:6]}"

    for permission_name in (first_perm_name, second_perm_name):
        resp = await client.post(
            "/v1/permissions/",
            json={
                "name": permission_name,
                "display_name": permission_name,
                "description": "integration test",
                "is_system": False,
                "is_active": True,
                "tags": [],
            },
        )
        assert resp.status_code == 201, resp.text

    role_name = f"searchable-role-{uuid.uuid4().hex[:6]}"
    role_resp = await client.post(
        "/v1/roles/",
        json={
            "name": role_name,
            "display_name": "Searchable Role",
            "description": "role search contract",
            "permissions": [first_perm_name],
            "is_global": True,
        },
    )
    assert role_resp.status_code == 201, role_resp.text
    role = role_resp.json()

    search_resp = await client.get("/v1/roles/", params={"search": "Searchable"})
    assert search_resp.status_code == 200, search_resp.text
    assert any(item["id"] == role["id"] for item in search_resp.json()["items"])

    add_perm_resp = await client.post(
        f"/v1/roles/{role['id']}/permissions",
        json=[second_perm_name],
    )
    assert add_perm_resp.status_code == 200, add_perm_resp.text
    assert sorted(add_perm_resp.json()["permissions"]) == sorted([first_perm_name, second_perm_name])

    remove_perm_resp = await client.request(
        "DELETE",
        f"/v1/roles/{role['id']}/permissions",
        json=[first_perm_name],
    )
    assert remove_perm_resp.status_code == 200, remove_perm_resp.text
    assert remove_perm_resp.json()["permissions"] == [second_perm_name]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entities_support_root_only_and_search_filters(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    root_name = f"root-{uuid.uuid4().hex[:8]}"
    root_resp = await client.post(
        "/v1/entities/",
        json={
            "name": root_name,
            "display_name": "Filter Root",
            "slug": root_name,
            "entity_class": EntityClass.STRUCTURAL.value,
            "entity_type": "organization",
        },
    )
    assert root_resp.status_code == 201, root_resp.text
    root_id = root_resp.json()["id"]

    child_name = f"child-{uuid.uuid4().hex[:8]}"
    child_resp = await client.post(
        "/v1/entities/",
        json={
            "name": child_name,
            "display_name": "Searchable Child",
            "slug": child_name,
            "entity_class": EntityClass.STRUCTURAL.value,
            "entity_type": "department",
            "parent_entity_id": root_id,
        },
    )
    assert child_resp.status_code == 201, child_resp.text
    child_id = child_resp.json()["id"]

    root_only_resp = await client.get("/v1/entities/", params={"root_only": "true"})
    assert root_only_resp.status_code == 200, root_only_resp.text
    root_only_ids = {item["id"] for item in root_only_resp.json()["items"]}
    assert root_id in root_only_ids
    assert child_id not in root_only_ids

    search_resp = await client.get("/v1/entities/", params={"search": "Searchable Child"})
    assert search_resp.status_code == 200, search_resp.text
    search_ids = {item["id"] for item in search_resp.json()["items"]}
    assert child_id in search_ids
    assert root_id not in search_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_keys_crud(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    entity_id = await _create_api_key_anchor_entity(client, label="api-key-anchor")

    r_create = await client.post(
        "/v1/api-keys/",
        json={
            "name": "test key",
            "scopes": ["user:read"],
            "prefix_type": "sk",
            "entity_ids": [entity_id],
        },
    )
    assert r_create.status_code == 201, r_create.text
    created = r_create.json()
    key_id = created["id"]
    assert created.get("api_key")  # full key shown only once
    assert created["key_kind"] == "personal"
    assert created["entity_ids"] == [entity_id]

    r_list = await client.get("/v1/api-keys/")
    assert r_list.status_code == 200, r_list.text
    assert any(k["id"] == key_id for k in r_list.json())

    r_get = await client.get(f"/v1/api-keys/{key_id}")
    assert r_get.status_code == 200, r_get.text

    r_update = await client.patch(f"/v1/api-keys/{key_id}", json={"name": "renamed"})
    assert r_update.status_code == 200, r_update.text

    r_delete = await client.delete(f"/v1/api-keys/{key_id}")
    assert r_delete.status_code == 204, r_delete.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_api_key_create_requires_entity_anchor_and_scopes(client: httpx.AsyncClient, admin_token: str):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    entity_id = await _create_api_key_anchor_entity(client, label="api-key-policy")

    missing_anchor = await client.post(
        "/v1/api-keys/",
        json={"name": "missing-anchor", "scopes": ["user:read"]},
    )
    assert missing_anchor.status_code == 400, missing_anchor.text
    assert "entity anchor" in missing_anchor.json()["detail"].lower()

    missing_scopes = await client.post(
        "/v1/api-keys/",
        json={"name": "missing-scopes", "entity_ids": [entity_id]},
    )
    assert missing_scopes.status_code == 400, missing_scopes.text
    assert "explicit scope" in missing_scopes.json()["detail"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_service_verify_api_key_rejects_suspended_owner_and_archived_anchor(
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    owner_email = f"api-key-runtime-{unique}@example.com"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_runtime_root_{unique}",
            display_name="API Key Runtime Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        owner = await enterprise_auth.user_service.create_user(
            session=session,
            email=owner_email,
            password="TestPass123!",
            first_name="Runtime",
            last_name="Owner",
            is_superuser=True,
            root_entity_id=root.id,
        )

        full_key, _ = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner.id,
            name="Runtime Policy Key",
            scopes=["user:read"],
            entity_id=root.id,
        )
        await session.commit()
        root_id = root.id

    async with enterprise_auth.get_session() as session:
        owner = await enterprise_auth.user_service.get_user_by_email(session, owner_email)
        assert owner is not None

        await enterprise_auth.user_service.update_user_status(
            session,
            owner.id,
            status=UserStatus.SUSPENDED,
        )
        denied, _ = await enterprise_auth.api_key_service.verify_api_key(session, full_key)
        assert denied is None

        await enterprise_auth.user_service.update_user_status(
            session,
            owner.id,
            status=UserStatus.ACTIVE,
        )
        await enterprise_auth.entity_service.delete_entity(session, root_id)
        denied_after_archive, _ = await enterprise_auth.api_key_service.verify_api_key(
            session,
            full_key,
        )
        assert denied_after_archive is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_api_key_grant_and_runtime_intersect_owner_permissions(
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    permission_name = f"leads{unique}:read"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_policy_root_{unique}",
            display_name="API Key Policy Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-policy-admin-{unique}@example.com",
            password="AdminPass123!",
            first_name="Policy",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        owner = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-policy-owner-{unique}@example.com",
            password="OwnerPass123!",
            first_name="Policy",
            last_name="Owner",
            root_entity_id=root.id,
        )
        permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=permission_name,
            display_name="Lead Read",
            description="Can read leads",
        )
        role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_policy_role_{unique}",
            display_name="API Key Policy Role",
            is_global=False,
            root_entity_id=root.id,
        )

        await enterprise_auth.role_service.add_permissions(session, role.id, [permission.id])

        with pytest.raises(InvalidInputError, match="owner's current permissions"):
            await enterprise_auth.api_key_service.create_api_key(
                session=session,
                owner_id=owner.id,
                name="Denied Personal Key",
                scopes=[permission_name],
                entity_id=root.id,
                actor_user_id=owner.id,
            )

        await enterprise_auth.role_service.assign_role_to_user(
            session=session,
            user_id=owner.id,
            role_id=role.id,
            assigned_by_id=admin.id,
        )
        full_key, _ = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner.id,
            name="Allowed Personal Key",
            scopes=[permission_name],
            entity_id=root.id,
            actor_user_id=owner.id,
        )

        allowed, _ = await enterprise_auth.api_key_service.verify_api_key(
            session,
            full_key,
            required_scope=permission_name,
            entity_id=root.id,
        )
        assert allowed is not None

        await enterprise_auth.role_service.revoke_role_from_user(
            session,
            user_id=owner.id,
            role_id=role.id,
            revoked_by_id=admin.id,
            reason="permission removed",
        )

        denied, _ = await enterprise_auth.api_key_service.verify_api_key(
            session,
            full_key,
            required_scope=permission_name,
            entity_id=root.id,
        )
        assert denied is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enterprise_api_key_lifecycle_records_user_audit_events(
    enterprise_auth: EnterpriseRBAC,
):
    unique = uuid.uuid4().hex[:8]
    permission_name = f"contacts{unique}:read"

    async with enterprise_auth.get_session() as session:
        root = await enterprise_auth.entity_service.create_entity(
            session=session,
            name=f"api_key_audit_root_{unique}",
            display_name="API Key Audit Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        admin = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-audit-admin-{unique}@example.com",
            password="AdminPass123!",
            first_name="Audit",
            last_name="Admin",
            is_superuser=True,
            root_entity_id=root.id,
        )
        owner = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"api-key-audit-owner-{unique}@example.com",
            password="OwnerPass123!",
            first_name="Audit",
            last_name="Owner",
            root_entity_id=root.id,
        )
        permission = await enterprise_auth.permission_service.create_permission(
            session,
            name=permission_name,
            display_name="Contact Read",
            description="Can read contacts",
        )
        role = await enterprise_auth.role_service.create_role(
            session=session,
            name=f"api_key_audit_role_{unique}",
            display_name="API Key Audit Role",
            is_global=False,
            root_entity_id=root.id,
        )
        await enterprise_auth.role_service.add_permissions(session, role.id, [permission.id])
        await enterprise_auth.role_service.assign_role_to_user(
            session=session,
            user_id=owner.id,
            role_id=role.id,
            assigned_by_id=admin.id,
        )

        _, key = await enterprise_auth.api_key_service.create_api_key(
            session=session,
            owner_id=owner.id,
            name="Audit Key",
            scopes=[permission_name],
            entity_id=root.id,
            actor_user_id=owner.id,
        )
        await enterprise_auth.api_key_service.update_api_key(
            session,
            key.id,
            actor_user_id=owner.id,
            description="updated description",
        )
        _, rotated = await enterprise_auth.api_key_service.rotate_api_key(
            session,
            key.id,
            actor_user_id=owner.id,
        )
        await enterprise_auth.api_key_service.revoke_api_key(
            session,
            rotated.id,
            actor_user_id=owner.id,
            reason="cleanup",
        )
        await session.commit()

    async with enterprise_auth.get_session() as session:
        events = (
            (
                await session.execute(
                    select(UserAuditEvent)
                    .where(UserAuditEvent.subject_user_id == owner.id)
                    .where(UserAuditEvent.event_type.like("user.api_key_%"))
                    .order_by(UserAuditEvent.occurred_at.asc(), UserAuditEvent.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

        event_types = [event.event_type for event in events]
        assert event_types == [
            "user.api_key_created",
            "user.api_key_updated",
            "user.api_key_rotated",
            "user.api_key_revoked",
        ]
        assert events[0].after["scopes"] == [permission_name]
        assert events[2].event_metadata["rotated_from_key_id"] == str(key.id)
        assert events[3].reason == "cleanup"
        assert events[3].after["status"] == APIKeyStatus.REVOKED.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entities_and_memberships_smoke(
    client: httpx.AsyncClient, enterprise_auth: EnterpriseRBAC, admin_token: str
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})

    r_org = await client.post(
        "/v1/entities/",
        json={
            "name": "org",
            "display_name": "Org",
            "slug": f"org-{uuid.uuid4().hex[:6]}",
            "description": None,
            "entity_class": "structural",
            "entity_type": "organization",
            "parent_entity_id": None,
            "status": "active",
        },
    )
    assert r_org.status_code == 201, r_org.text
    org = r_org.json()

    r_team = await client.post(
        "/v1/entities/",
        json={
            "name": "team",
            "display_name": "Team",
            "slug": f"team-{uuid.uuid4().hex[:6]}",
            "description": None,
            "entity_class": "structural",
            "entity_type": "team",
            "parent_entity_id": org["id"],
            "status": "active",
        },
    )
    assert r_team.status_code == 201, r_team.text
    team = r_team.json()

    # Create a regular user directly and add them to the team via endpoint.
    async with enterprise_auth.get_session() as session:
        user = await enterprise_auth.user_service.create_user(
            session=session,
            email=f"member-{uuid.uuid4().hex[:6]}@example.com",
            password="TestPass123!",
            first_name="Member",
            last_name="User",
        )
        await session.commit()
        user_id = str(user.id)

    r_add = await client.post(
        "/v1/memberships/",
        json={"entity_id": team["id"], "user_id": user_id, "role_ids": []},
    )
    assert r_add.status_code == 201, r_add.text

    r_desc = await client.get(f"/v1/entities/{org['id']}/descendants")
    assert r_desc.status_code == 200, r_desc.text

    r_members = await client.get(f"/v1/entities/{org['id']}/members", params={"page": 1, "limit": 50})
    assert r_members.status_code == 200, r_members.text

    # Move team to root and then delete.
    r_move = await client.post(
        f"/v1/entities/{team['id']}/move",
        json={"new_parent_id": None},
    )
    assert r_move.status_code == 200, r_move.text

    r_delete = await client.delete(f"/v1/entities/{team['id']}")
    assert r_delete.status_code == 204, r_delete.text
