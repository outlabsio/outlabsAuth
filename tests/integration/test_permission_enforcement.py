"""
Permission Enforcement Integration Tests

Tests that API endpoints correctly enforce authorization:
- Protected endpoints require authentication
- Users can only access resources they have permission for
- Superusers bypass permission checks
- Tree permissions work correctly in entity hierarchy
- ABAC conditions are evaluated during permission checks

These tests verify the security boundary at the HTTP layer.
"""

import uuid
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus, RoleScope
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

# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    """Create EnterpriseRBAC instance for permission testing."""
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_abac=True,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def app(auth_instance: EnterpriseRBAC) -> FastAPI:
    """Create FastAPI app with all routers."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    app.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth_instance, prefix="/v1/permissions"))
    app.include_router(get_api_keys_router(auth_instance, prefix="/v1/api-keys"))
    app.include_router(get_entities_router(auth_instance, prefix="/v1/entities"))
    app.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_user(auth_instance: EnterpriseRBAC) -> dict:
    """Create admin user (superuser) and return credentials."""
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email="admin@example.com",
            password="TestPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {"id": str(admin.id), "email": admin.email, "token": token}


@pytest_asyncio.fixture
async def regular_user(auth_instance: EnterpriseRBAC) -> dict:
    """Create regular user (no permissions) and return credentials."""
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email="regular@example.com",
            password="TestPass123!",
            first_name="Regular",
            last_name="User",
            is_superuser=False,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {"id": str(user.id), "email": user.email, "token": token}


@pytest_asyncio.fixture
async def user_with_read_permission(auth_instance: EnterpriseRBAC) -> dict:
    """Create user with only user:read permission."""
    async with auth_instance.get_session() as session:
        # Create permission
        perm = await auth_instance.permission_service.create_permission(
            session,
            name="user:read",
            display_name="User Read",
            description="Can read users",
        )

        # Create role
        role = await auth_instance.role_service.create_role(
            session,
            name="reader",
            display_name="Reader",
            description="Read-only access",
        )

        # Assign permission to role
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        # Create user
        user = await auth_instance.user_service.create_user(
            session=session,
            email="reader@example.com",
            password="TestPass123!",
            first_name="Reader",
            last_name="User",
            is_superuser=False,
        )

        # Assign role to user
        await auth_instance.role_service.assign_role_to_user(session, user.id, role.id)

        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "token": token,
            "role_id": str(role.id),
        }


@pytest_asyncio.fixture
async def user_with_create_permission(auth_instance: EnterpriseRBAC) -> dict:
    """Create user with user:create permission."""
    async with auth_instance.get_session() as session:
        perm = await auth_instance.permission_service.create_permission(
            session,
            name="user:create",
            display_name="User Create",
            description="Can create users",
        )

        role = await auth_instance.role_service.create_role(
            session,
            name="user_creator",
            display_name="User Creator",
            description="Can create users",
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        user = await auth_instance.user_service.create_user(
            session=session,
            email="creator@example.com",
            password="TestPass123!",
            first_name="User",
            last_name="Creator",
            is_superuser=False,
        )
        await auth_instance.role_service.assign_role_to_user(session, user.id, role.id)
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "token": token,
            "role_id": str(role.id),
        }


@pytest_asyncio.fixture
async def user_with_create_superuser_permission(auth_instance: EnterpriseRBAC) -> dict:
    """Create user with both user:create and user:create_superuser permissions."""
    async with auth_instance.get_session() as session:
        create_perm = await auth_instance.permission_service.create_permission(
            session,
            name="user:create",
            display_name="User Create",
            description="Can create users",
        )
        superuser_create_perm = await auth_instance.permission_service.create_permission(
            session,
            name="user:create_superuser",
            display_name="User Create Superuser",
            description="Can create superusers",
        )

        role = await auth_instance.role_service.create_role(
            session,
            name="superuser_creator",
            display_name="Superuser Creator",
            description="Can create superusers",
        )
        await auth_instance.role_service.add_permissions(session, role.id, [create_perm.id, superuser_create_perm.id])

        user = await auth_instance.user_service.create_user(
            session=session,
            email="superuser-creator@example.com",
            password="TestPass123!",
            first_name="Superuser",
            last_name="Creator",
            is_superuser=False,
        )
        await auth_instance.role_service.assign_role_to_user(session, user.id, role.id)
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "token": token,
            "role_id": str(role.id),
        }


@pytest_asyncio.fixture
async def user_with_role_read_tree_permission(auth_instance: EnterpriseRBAC) -> dict:
    """Create user with role:read_tree permission."""
    async with auth_instance.get_session() as session:
        perm = await auth_instance.permission_service.create_permission(
            session,
            name="role:read_tree",
            display_name="Role Read Tree",
            description="Can read roles in entity context",
        )

        role = await auth_instance.role_service.create_role(
            session,
            name="role_tree_reader",
            display_name="Role Tree Reader",
            description="Can read roles in entity context",
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        user = await auth_instance.user_service.create_user(
            session=session,
            email="role-tree-reader@example.com",
            password="TestPass123!",
            first_name="Role",
            last_name="Reader",
            is_superuser=False,
        )
        await auth_instance.role_service.assign_role_to_user(session, user.id, role.id)

        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "token": token,
            "role_id": str(role.id),
        }


# ============================================================================
# Authentication Required Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_users_list_requires_authentication(client: httpx.AsyncClient):
    """Test that /users/ endpoint requires authentication."""
    resp = await client.get("/v1/users/")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_list_requires_authentication(client: httpx.AsyncClient):
    """Test that /roles/ endpoint requires authentication."""
    resp = await client.get("/v1/roles/")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_list_requires_authentication(client: httpx.AsyncClient):
    """Test that /permissions/ endpoint requires authentication."""
    resp = await client.get("/v1/permissions/")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entities_list_requires_authentication(client: httpx.AsyncClient):
    """Test that /entities/ endpoint requires authentication."""
    resp = await client.get("/v1/entities/")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_keys_list_requires_authentication(client: httpx.AsyncClient):
    """Test that /api-keys/ endpoint requires authentication."""
    resp = await client.get("/v1/api-keys/")
    assert resp.status_code == 401


# ============================================================================
# Superuser Bypass Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_list_users(client: httpx.AsyncClient, admin_user: dict):
    """Test that superuser can access any endpoint."""
    resp = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_create_user(client: httpx.AsyncClient, admin_user: dict):
    """Test that superuser can create users."""
    resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "email": f"new-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPass123!",
            "first_name": "New",
            "last_name": "User",
        },
    )
    assert resp.status_code == 201


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_list_roles(client: httpx.AsyncClient, admin_user: dict):
    """Test that superuser can list roles."""
    resp = await client.get(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_create_role(client: httpx.AsyncClient, admin_user: dict):
    """Test that superuser can create roles."""
    resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"test-role-{uuid.uuid4().hex[:8]}",
            "display_name": "Test Role",
            "description": "A test role",
        },
    )
    assert resp.status_code == 201


# ============================================================================
# Permission Denied Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_list_users(client: httpx.AsyncClient, regular_user: dict):
    """Test that user without permissions cannot list users."""
    resp = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_create_user(client: httpx.AsyncClient, regular_user: dict):
    """Test that user without permissions cannot create users."""
    resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
        json={
            "email": "attempt@example.com",
            "password": "TestPass123!",
            "first_name": "Attempt",
            "last_name": "User",
        },
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_list_roles(client: httpx.AsyncClient, regular_user: dict):
    """Test that user without permissions cannot list roles."""
    resp = await client.get(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_create_role(client: httpx.AsyncClient, regular_user: dict):
    """Test that user without permissions cannot create roles."""
    resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
        json={
            "name": "unauthorized-role",
            "display_name": "Unauthorized Role",
        },
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_update_role_permissions(
    client: httpx.AsyncClient, regular_user: dict, admin_user: dict
):
    """Test that regular user cannot update role permissions."""
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"perm-update-{uuid.uuid4().hex[:8]}",
            "display_name": "Perm Update Role",
        },
    )
    role_id = create_resp.json()["id"]

    resp = await client.post(
        f"/v1/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
        json=["user:read"],
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_with_role_update_can_update_role_permissions(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    """Test that user with role:update can assign permissions to roles."""
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"role-update-root-{uuid.uuid4().hex[:8]}",
            display_name="Role Update Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        perm = await auth_instance.permission_service.create_permission(
            session,
            name="role:update",
            display_name="Role Update",
            description="Can update roles",
        )
        role = await auth_instance.role_service.create_role(
            session,
            name="role_updater",
            display_name="Role Updater",
            is_global=False,
            root_entity_id=root.id,
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        user = await auth_instance.user_service.create_user(
            session=session,
            email="role-updater@example.com",
            password="TestPass123!",
            first_name="Role",
            last_name="Updater",
            is_superuser=False,
            root_entity_id=root.id,
        )
        await auth_instance.role_service.assign_role_to_user(session, user.id, role.id)
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"perm-target-{uuid.uuid4().hex[:8]}",
            "display_name": "Perm Target Role",
            "is_global": False,
            "root_entity_id": str(root.id),
        },
    )
    target_role_id = create_resp.json()["id"]

    perm_create_resp = await client.post(
        "/v1/permissions/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"custom:read_{uuid.uuid4().hex[:8]}",
            "display_name": "Custom Read",
            "description": "Custom read permission",
        },
    )
    perm_name = perm_create_resp.json()["name"]

    resp = await client.post(
        f"/v1/roles/{target_role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json=[perm_name],
    )
    assert resp.status_code == 200


# ============================================================================
# Specific Permission Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_with_read_permission_can_list_users(client: httpx.AsyncClient, user_with_read_permission: dict):
    """Test that user with user:read can list users."""
    resp = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {user_with_read_permission['token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_with_read_permission_cannot_create_user(client: httpx.AsyncClient, user_with_read_permission: dict):
    """Test that user with only user:read cannot create users."""
    resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {user_with_read_permission['token']}"},
        json={
            "email": "attempt@example.com",
            "password": "TestPass123!",
            "first_name": "Attempt",
            "last_name": "User",
        },
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_with_read_permission_cannot_delete_user(
    client: httpx.AsyncClient,
    user_with_read_permission: dict,
    admin_user: dict,
):
    """Test that user with only user:read cannot delete users."""
    # Create a user to attempt to delete
    create_resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "email": f"to-delete-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPass123!",
            "first_name": "ToDelete",
            "last_name": "User",
        },
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Try to delete with read-only user
    delete_resp = await client.delete(
        f"/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {user_with_read_permission['token']}"},
    )
    assert delete_resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_with_create_permission_can_create_non_superuser(
    client: httpx.AsyncClient, user_with_create_permission: dict
):
    """Test that user:create can create standard users."""
    resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {user_with_create_permission['token']}"},
        json={
            "email": f"created-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPass123!",
            "first_name": "Created",
            "last_name": "User",
            "is_superuser": False,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_superuser"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_with_create_permission_cannot_create_superuser(
    client: httpx.AsyncClient, user_with_create_permission: dict
):
    """Test that user:create alone cannot escalate to is_superuser=True."""
    resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {user_with_create_permission['token']}"},
        json={
            "email": f"escalation-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPass123!",
            "first_name": "Escalation",
            "last_name": "Attempt",
            "is_superuser": True,
        },
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_with_create_superuser_permission_can_create_superuser(
    client: httpx.AsyncClient, user_with_create_superuser_permission: dict
):
    """Test delegated superuser creation when explicit permission is granted."""
    resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {user_with_create_superuser_permission['token']}"},
        json={
            "email": f"new-super-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPass123!",
            "first_name": "New",
            "last_name": "Superuser",
            "is_superuser": True,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_superuser"] is True


# ============================================================================
# Self-Access Tests (users/me)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_any_authenticated_user_can_access_me(client: httpx.AsyncClient, regular_user: dict):
    """Test that any authenticated user can access /users/me."""
    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == regular_user["email"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_can_update_own_profile(client: httpx.AsyncClient, regular_user: dict):
    """Test that user can update their own profile via /users/me."""
    resp = await client.patch(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
        json={"first_name": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Updated"


# ============================================================================
# Wildcard Permission Tests
# ============================================================================


@pytest_asyncio.fixture
async def user_with_wildcard_permission(auth_instance: EnterpriseRBAC) -> dict:
    """Create user with user:* wildcard permission."""
    async with auth_instance.get_session() as session:
        # Create wildcard permission
        perm = await auth_instance.permission_service.create_permission(
            session,
            name="user:*",
            display_name="User All",
            description="All user operations",
        )

        # Create role
        role = await auth_instance.role_service.create_role(
            session,
            name="user_admin",
            display_name="User Admin",
            description="Full user access",
        )

        # Assign permission to role
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        # Create user
        user = await auth_instance.user_service.create_user(
            session=session,
            email="useradmin@example.com",
            password="TestPass123!",
            first_name="User",
            last_name="Admin",
            is_superuser=False,
        )

        # Assign role to user
        await auth_instance.role_service.assign_role_to_user(session, user.id, role.id)

        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {"id": str(user.id), "email": user.email, "token": token}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wildcard_permission_grants_all_actions(client: httpx.AsyncClient, user_with_wildcard_permission: dict):
    """Test that user:* grants all user operations."""
    headers = {"Authorization": f"Bearer {user_with_wildcard_permission['token']}"}

    # Can list
    list_resp = await client.get("/v1/users/", headers=headers)
    assert list_resp.status_code == 200

    # Can create
    create_resp = await client.post(
        "/v1/users/",
        headers=headers,
        json={
            "email": f"created-{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPass123!",
            "first_name": "Created",
            "last_name": "User",
        },
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Can update
    update_resp = await client.patch(
        f"/v1/users/{user_id}",
        headers=headers,
        json={"first_name": "Updated"},
    )
    assert update_resp.status_code == 200

    # Can delete
    delete_resp = await client.delete(f"/v1/users/{user_id}", headers=headers)
    assert delete_resp.status_code == 204


# ============================================================================
# Cross-Resource Permission Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_permission_does_not_grant_role_access(client: httpx.AsyncClient, user_with_read_permission: dict):
    """Test that user:read does not grant role:read."""
    resp = await client.get(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {user_with_read_permission['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_permission_does_not_grant_permission_access(
    client: httpx.AsyncClient, user_with_read_permission: dict
):
    """Test that user:read does not grant permission:read."""
    resp = await client.get(
        "/v1/permissions/",
        headers={"Authorization": f"Bearer {user_with_read_permission['token']}"},
    )
    assert resp.status_code == 403


# ============================================================================
# Entity Permission Tests (EnterpriseRBAC)
# ============================================================================


@pytest_asyncio.fixture
async def entity_setup(auth_instance: EnterpriseRBAC, admin_user: dict) -> dict:
    """Create entity hierarchy for testing tree permissions."""
    async with auth_instance.get_session() as session:
        # Create parent entity
        parent = await auth_instance.entity_service.create_entity(
            session,
            name="parent_org",
            display_name="Parent Organization",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

        # Create child entity
        child = await auth_instance.entity_service.create_entity(
            session,
            name="child_dept",
            display_name="Child Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=parent.id,
        )

        await session.commit()

        return {
            "parent_id": str(parent.id),
            "child_id": str(child.id),
        }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_list_returns_empty_for_regular_user(client: httpx.AsyncClient, regular_user: dict):
    """Test that entity list returns empty for user without entity access.

    Note: The entity list endpoint requires entity:read permission. A user
    without that permission should get a 403.
    """
    resp = await client.get(
        "/v1/entities/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_list_entities(client: httpx.AsyncClient, admin_user: dict):
    """Test that superuser can list entities."""
    resp = await client.get(
        "/v1/entities/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_for_entity_requires_tree_permission(
    client: httpx.AsyncClient, user_with_read_permission: dict, entity_setup: dict
):
    """Test that /roles/entity/{entity_id} requires role:read_tree permission."""
    resp = await client.get(
        f"/v1/roles/entity/{entity_setup['parent_id']}",
        headers={"Authorization": f"Bearer {user_with_read_permission['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_for_entity_allows_tree_permission(
    client: httpx.AsyncClient,
    user_with_role_read_tree_permission: dict,
    entity_setup: dict,
):
    """Test that role:read_tree allows listing roles for entity."""
    resp = await client.get(
        f"/v1/roles/entity/{entity_setup['parent_id']}",
        headers={"Authorization": f"Bearer {user_with_role_read_tree_permission['token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entity_local_role_does_not_grant_global_role_list_with_header(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, entity_setup: dict
):
    """Entity-local roles should not grant access to /roles/ even with header."""
    async with auth_instance.get_session() as session:
        perm = await auth_instance.permission_service.create_permission(
            session,
            name="role:read",
            display_name="Role Read",
            description="Can read roles",
        )

        role = await auth_instance.role_service.create_role(
            session,
            name="local_role_reader",
            display_name="Local Role Reader",
            is_global=False,
            scope_entity_id=uuid.UUID(entity_setup["parent_id"]),
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        user = await auth_instance.user_service.create_user(
            session=session,
            email="local-role-reader@example.com",
            password="TestPass123!",
            first_name="Local",
            last_name="Reader",
            is_superuser=False,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=uuid.UUID(entity_setup["parent_id"]),
            user_id=user.id,
            role_ids=[role.id],
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

    resp = await client.get(
        "/v1/roles/",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Entity-Context": entity_setup["parent_id"],
        },
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_update_rejects_cross_root_role(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    """Roles from other root entities should be rejected in membership updates."""
    async with auth_instance.get_session() as session:
        root_a = await auth_instance.entity_service.create_entity(
            session,
            name="root_a",
            display_name="Root A",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        child_a = await auth_instance.entity_service.create_entity(
            session,
            name="child_a",
            display_name="Child A",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root_a.id,
        )
        root_b = await auth_instance.entity_service.create_entity(
            session,
            name="root_b",
            display_name="Root B",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

        role_a = await auth_instance.role_service.create_role(
            session=session,
            name="role_a",
            display_name="Role A",
            root_entity_id=root_a.id,
            is_global=False,
        )
        role_b = await auth_instance.role_service.create_role(
            session=session,
            name="role_b",
            display_name="Role B",
            root_entity_id=root_b.id,
            is_global=False,
        )

        user = await auth_instance.user_service.create_user(
            session=session,
            email="cross-root@example.com",
            password="TestPass123!",
            first_name="Cross",
            last_name="Root",
            is_superuser=False,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=child_a.id,
            user_id=user.id,
            role_ids=[role_a.id],
        )
        await session.commit()

    resp = await client.patch(
        f"/v1/memberships/{child_a.id}/{user.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_ids": [str(role_b.id)]},
    )
    assert resp.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_update_rejects_entity_only_role_from_ancestor(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    """Entity-only roles should not be assignable to descendant memberships."""
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name="root_entity_only",
            display_name="Root Entity Only",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        parent = await auth_instance.entity_service.create_entity(
            session,
            name="parent_entity_only",
            display_name="Parent Entity Only",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        child = await auth_instance.entity_service.create_entity(
            session,
            name="child_entity_only",
            display_name="Child Entity Only",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=parent.id,
        )

        base_role = await auth_instance.role_service.create_role(
            session=session,
            name="base_role",
            display_name="Base Role",
            root_entity_id=root.id,
            is_global=False,
        )
        entity_only_role = await auth_instance.role_service.create_role(
            session=session,
            name="parent_entity_only_role",
            display_name="Parent Entity Only Role",
            is_global=False,
            scope_entity_id=parent.id,
            scope=RoleScope.ENTITY_ONLY,
        )

        user = await auth_instance.user_service.create_user(
            session=session,
            email="entity-only@example.com",
            password="TestPass123!",
            first_name="Entity",
            last_name="Only",
            is_superuser=False,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=child.id,
            user_id=user.id,
            role_ids=[base_role.id],
        )
        await session.commit()

    resp = await client.patch(
        f"/v1/memberships/{child.id}/{user.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_ids": [str(entity_only_role.id)]},
    )
    assert resp.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tree_permission_required_for_descendant_membership_create(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC
):
    """Non-tree permission should not allow creating memberships in descendants."""
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name="root_tree_perm",
            display_name="Root Tree Perm",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        child = await auth_instance.entity_service.create_entity(
            session,
            name="child_tree_perm",
            display_name="Child Tree Perm",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )

        perm = await auth_instance.permission_service.create_permission(
            session,
            name="membership:create",
            display_name="Membership Create",
            description="Create membership at entity only",
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name="membership_creator",
            display_name="Membership Creator",
            root_entity_id=root.id,
            is_global=False,
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        actor = await auth_instance.user_service.create_user(
            session=session,
            email="actor@example.com",
            password="TestPass123!",
            first_name="Actor",
            last_name="User",
            is_superuser=False,
        )
        target = await auth_instance.user_service.create_user(
            session=session,
            email="target@example.com",
            password="TestPass123!",
            first_name="Target",
            last_name="User",
            is_superuser=False,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=root.id,
            user_id=actor.id,
            role_ids=[role.id],
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(actor.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

    resp = await client.post(
        "/v1/memberships/",
        headers={"Authorization": f"Bearer {token}"},
        json={"entity_id": str(child.id), "user_id": str(target.id), "role_ids": []},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tree_permission_allows_descendant_membership_create(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC
):
    """Tree permission should allow creating memberships in descendants."""
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name="root_tree_allow",
            display_name="Root Tree Allow",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        child = await auth_instance.entity_service.create_entity(
            session,
            name="child_tree_allow",
            display_name="Child Tree Allow",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )

        perm = await auth_instance.permission_service.create_permission(
            session,
            name="membership:create_tree",
            display_name="Membership Create Tree",
            description="Create membership in descendant entities",
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name="membership_creator_tree",
            display_name="Membership Creator Tree",
            root_entity_id=root.id,
            is_global=False,
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        actor = await auth_instance.user_service.create_user(
            session=session,
            email="actor-tree@example.com",
            password="TestPass123!",
            first_name="Actor",
            last_name="Tree",
            is_superuser=False,
        )
        target = await auth_instance.user_service.create_user(
            session=session,
            email="target-tree@example.com",
            password="TestPass123!",
            first_name="Target",
            last_name="Tree",
            is_superuser=False,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=root.id,
            user_id=actor.id,
            role_ids=[role.id],
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(actor.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

    resp = await client.post(
        "/v1/memberships/",
        headers={"Authorization": f"Bearer {token}"},
        json={"entity_id": str(child.id), "user_id": str(target.id), "role_ids": []},
    )
    assert resp.status_code == 201


@pytest.mark.integration
@pytest.mark.asyncio
async def test_membership_update_allows_hierarchy_role_from_ancestor(
    client: httpx.AsyncClient, auth_instance: EnterpriseRBAC, admin_user: dict
):
    """Hierarchy-scoped roles from ancestors should be assignable to descendants."""
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name="root_hierarchy_role",
            display_name="Root Hierarchy Role",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        parent = await auth_instance.entity_service.create_entity(
            session,
            name="parent_hierarchy_role",
            display_name="Parent Hierarchy Role",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        child = await auth_instance.entity_service.create_entity(
            session,
            name="child_hierarchy_role",
            display_name="Child Hierarchy Role",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=parent.id,
        )

        base_role = await auth_instance.role_service.create_role(
            session=session,
            name="base_role_hierarchy",
            display_name="Base Role Hierarchy",
            root_entity_id=root.id,
            is_global=False,
        )
        hierarchy_role = await auth_instance.role_service.create_role(
            session=session,
            name="parent_hierarchy_role_local",
            display_name="Parent Hierarchy Role Local",
            is_global=False,
            scope_entity_id=parent.id,
            scope=RoleScope.HIERARCHY,
        )

        user = await auth_instance.user_service.create_user(
            session=session,
            email="hierarchy-role-user@example.com",
            password="TestPass123!",
            first_name="Hierarchy",
            last_name="Role",
            is_superuser=False,
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=child.id,
            user_id=user.id,
            role_ids=[base_role.id],
        )
        await session.commit()

    resp = await client.patch(
        f"/v1/memberships/{child.id}/{user.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_ids": [str(hierarchy_role.id)]},
    )
    assert resp.status_code == 200


# ============================================================================
# API Key Permission Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_list_returns_empty_for_regular_user(client: httpx.AsyncClient, regular_user: dict):
    """Test that API key list returns empty for user without any keys.

    Note: The API key list endpoint returns the user's own API keys.
    It doesn't require apikey:read permission - users can always
    see their own keys. A user without any keys sees an empty list.
    """
    resp = await client.get(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    # Endpoint returns 200 with user's own keys (empty for new user)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_list_api_keys(client: httpx.AsyncClient, admin_user: dict):
    """Test that superuser can list API keys."""
    resp = await client.get(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_create_api_key(client: httpx.AsyncClient, admin_user: dict):
    """Test that superuser can create API keys."""
    entity_resp = await client.post(
        "/v1/entities/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"api-key-entity-{uuid.uuid4().hex[:8]}",
            "display_name": "API Key Entity",
            "slug": f"api-key-entity-{uuid.uuid4().hex[:8]}",
            "entity_class": EntityClass.STRUCTURAL.value,
            "entity_type": "organization",
        },
    )
    assert entity_resp.status_code == 201, entity_resp.text
    entity_id = entity_resp.json()["id"]

    resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"test-key-{uuid.uuid4().hex[:8]}",
            "description": "Test API key",
            "scopes": ["user:read"],
            "entity_ids": [entity_id],
        },
    )
    assert resp.status_code == 201
    # Verify key is returned
    data = resp.json()
    assert "api_key" in data  # Full key returned on creation (field is api_key)
    assert "prefix" in data


# ============================================================================
# Error Response Format Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_401_response_format(client: httpx.AsyncClient):
    """Test that 401 responses have consistent format."""
    resp = await client.get("/v1/users/")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data or "detail" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_403_response_format(client: httpx.AsyncClient, regular_user: dict):
    """Test that 403 responses have consistent format."""
    resp = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 403
    data = resp.json()
    assert "error" in data or "detail" in data
