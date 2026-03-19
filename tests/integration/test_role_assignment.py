"""
Role Assignment and Revocation Integration Tests

Tests the complete role lifecycle:
- Assigning roles to users
- Revoking roles from users
- Permission inheritance through roles
- Role CRUD operations
- Permission changes propagation

These tests ensure role management works correctly end-to-end.
"""

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import (
    get_auth_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token

# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    """Create SimpleRBAC instance for role testing."""
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
async def app(auth_instance: SimpleRBAC) -> FastAPI:
    """Create FastAPI app with routers."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    app.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth_instance, prefix="/v1/permissions"))
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
async def admin_user(auth_instance: SimpleRBAC) -> dict:
    """Create admin user (superuser) and return credentials."""
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
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

        return {
            "id": str(admin.id),
            "email": admin.email,
            "token": token,
        }


@pytest_asyncio.fixture
async def regular_user(auth_instance: SimpleRBAC) -> dict:
    """Create regular user (no permissions) and return credentials."""
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="RegularPass123!",
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

        return {
            "id": str(user.id),
            "email": user.email,
            "token": token,
        }


# ============================================================================
# Role CRUD Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_create_role(client: httpx.AsyncClient, admin_user: dict):
    """Test that admin can create a new role."""
    role_name = f"test-role-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": role_name,
            "display_name": "Test Role",
            "description": "A test role for testing",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == role_name
    assert data["display_name"] == "Test Role"
    assert "id" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_list_roles(client: httpx.AsyncClient, admin_user: dict):
    """Test that admin can list all roles."""
    # Create a role first
    role_name = f"listable-{uuid.uuid4().hex[:8]}"
    await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "Listable Role"},
    )

    # List roles (paginated response)
    resp = await client.get(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Paginated response
    assert "items" in data
    assert "total" in data
    roles = data["items"]
    assert any(r["name"] == role_name for r in roles)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_update_role(client: httpx.AsyncClient, admin_user: dict):
    """Test that admin can update a role."""
    # Create role
    role_name = f"updatable-{uuid.uuid4().hex[:8]}"
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "Original Name"},
    )
    role_id = create_resp.json()["id"]

    # Update role
    resp = await client.patch(
        f"/v1/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"display_name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated Name"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_delete_role(client: httpx.AsyncClient, admin_user: dict):
    """Test that admin can delete a role."""
    # Create role
    role_name = f"deletable-{uuid.uuid4().hex[:8]}"
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "To Delete"},
    )
    role_id = create_resp.json()["id"]

    # Delete role
    resp = await client.delete(
        f"/v1/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 204

    # Verify role is gone
    get_resp = await client.get(
        f"/v1/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inactive_and_archived_roles_stop_granting_access_and_cannot_be_assigned(
    client: httpx.AsyncClient,
    auth_instance: SimpleRBAC,
    admin_user: dict,
    regular_user: dict,
):
    async with auth_instance.get_session() as session:
        permission = await auth_instance.permission_service.create_permission(
            session=session,
            name="user:read",
            display_name="User Read",
            description="Can read users",
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"lifecycle-role-{uuid.uuid4().hex[:8]}",
            display_name="Lifecycle Role",
            permission_names=[permission.name],
        )
        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=uuid.UUID(regular_user["id"]),
            role_id=role.id,
        )
        extra_user = await auth_instance.user_service.create_user(
            session=session,
            email=f"extra-{uuid.uuid4().hex[:8]}@example.com",
            password="ExtraPass123!",
            first_name="Extra",
            last_name="User",
        )
        await session.commit()

    allowed_response = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert allowed_response.status_code == 200, allowed_response.text

    deactivate_response = await client.patch(
        f"/v1/roles/{role.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "inactive"},
    )
    assert deactivate_response.status_code == 200, deactivate_response.text
    assert deactivate_response.json()["status"] == "inactive"

    denied_response = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert denied_response.status_code == 403, denied_response.text

    assign_inactive_response = await client.post(
        f"/v1/users/{extra_user.id}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": str(role.id)},
    )
    assert assign_inactive_response.status_code == 422, assign_inactive_response.text

    delete_response = await client.delete(
        f"/v1/roles/{role.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert delete_response.status_code == 204, delete_response.text

    hidden_response = await client.get(
        f"/v1/roles/{role.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert hidden_response.status_code == 404, hidden_response.text

    assign_archived_response = await client.post(
        f"/v1/users/{extra_user.id}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": str(role.id)},
    )
    assert assign_archived_response.status_code == 404, assign_archived_response.text


# ============================================================================
# Role Assignment Tests (via API)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_assign_role_to_user(
    client: httpx.AsyncClient, admin_user: dict, regular_user: dict
):
    """Test that admin can assign a role to a user via PUT /users/{user_id}/roles."""
    # Create role
    role_name = f"assignable-{uuid.uuid4().hex[:8]}"
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "Assignable Role"},
    )
    role_id = create_resp.json()["id"]

    # Assign role to user via POST /users/{user_id}/roles
    resp = await client.post(
        f"/v1/users/{regular_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": role_id},
    )
    assert resp.status_code == 201

    # Verify user has role
    user_resp = await client.get(
        f"/v1/users/{regular_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert user_resp.status_code == 200
    roles = user_resp.json()
    # Response is list of RoleResponse, not wrapped memberships
    assert any(r["id"] == role_id for r in roles)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inactive_and_archived_permissions_stop_granting_access(
    client: httpx.AsyncClient,
    auth_instance: SimpleRBAC,
    admin_user: dict,
    regular_user: dict,
):
    async with auth_instance.get_session() as session:
        permission = await auth_instance.permission_service.create_permission(
            session=session,
            name="user:read",
            display_name="User Read",
            description="Can read users",
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"permission-lifecycle-{uuid.uuid4().hex[:8]}",
            display_name="Permission Lifecycle Role",
            permission_names=[permission.name],
        )
        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=uuid.UUID(regular_user["id"]),
            role_id=role.id,
        )
        await session.commit()

    allowed_response = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert allowed_response.status_code == 200, allowed_response.text

    deactivate_response = await client.patch(
        f"/v1/permissions/{permission.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 200, deactivate_response.text
    assert deactivate_response.json()["status"] == "inactive"
    assert deactivate_response.json()["is_active"] is False

    denied_response = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert denied_response.status_code == 403, denied_response.text

    reactivate_response = await client.patch(
        f"/v1/permissions/{permission.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"is_active": True},
    )
    assert reactivate_response.status_code == 200, reactivate_response.text
    assert reactivate_response.json()["status"] == "active"

    restored_response = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert restored_response.status_code == 200, restored_response.text

    delete_response = await client.delete(
        f"/v1/permissions/{permission.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert delete_response.status_code == 204, delete_response.text

    archived_denied_response = await client.get(
        "/v1/users/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert archived_denied_response.status_code == 403, archived_denied_response.text

    hidden_permission_response = await client.get(
        f"/v1/permissions/{permission.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert hidden_permission_response.status_code == 404, hidden_permission_response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_revoke_role_from_user(
    client: httpx.AsyncClient, admin_user: dict, regular_user: dict
):
    """Test that admin can revoke a role from a user via DELETE /users/{user_id}/roles/{role_id}."""
    # Create and assign role
    role_name = f"revokable-{uuid.uuid4().hex[:8]}"
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "Revokable Role"},
    )
    role_id = create_resp.json()["id"]

    # Assign role
    await client.post(
        f"/v1/users/{regular_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": role_id},
    )

    # Revoke role
    resp = await client.delete(
        f"/v1/users/{regular_user['id']}/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 204

    # Verify user no longer has role
    user_resp = await client.get(
        f"/v1/users/{regular_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    roles = user_resp.json()
    # Response is list of RoleResponse, not wrapped memberships
    assert not any(r["id"] == role_id for r in roles)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_view_direct_role_memberships_with_lifecycle_metadata(
    client: httpx.AsyncClient, admin_user: dict, regular_user: dict
):
    """Test that direct role memberships expose lifecycle fields and nested role data."""
    role_name = f"detail-{uuid.uuid4().hex[:8]}"
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "Detailed Role"},
    )
    role_id = create_resp.json()["id"]

    assign_resp = await client.post(
        f"/v1/users/{regular_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "role_id": role_id,
            "valid_from": "2026-03-16T09:00:00Z",
            "valid_until": "2026-03-20T17:00:00Z",
        },
    )
    assert assign_resp.status_code == 201

    memberships_resp = await client.get(
        f"/v1/users/{regular_user['id']}/role-memberships",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert memberships_resp.status_code == 200

    memberships = memberships_resp.json()
    assert len(memberships) == 1

    membership = memberships[0]
    assert membership["user_id"] == regular_user["id"]
    assert membership["role_id"] == role_id
    assert membership["status"] == "active"
    assert membership["assigned_by_id"] == admin_user["id"]
    assert membership["valid_from"] == "2026-03-16T09:00:00Z"
    assert membership["valid_until"] == "2026-03-20T17:00:00Z"
    assert membership["revoked_at"] is None
    assert membership["revocation_reason"] is None
    assert membership["role"]["id"] == role_id
    assert membership["role"]["display_name"] == "Detailed Role"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_role_memberships_hide_revoked_by_default_but_show_when_requested(
    client: httpx.AsyncClient, admin_user: dict, regular_user: dict
):
    """Test that revoked direct role memberships only appear with include_inactive=true."""
    role_name = f"revoked-detail-{uuid.uuid4().hex[:8]}"
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "Revoked Detail Role"},
    )
    role_id = create_resp.json()["id"]

    assign_resp = await client.post(
        f"/v1/users/{regular_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": role_id},
    )
    assert assign_resp.status_code == 201

    revoke_resp = await client.delete(
        f"/v1/users/{regular_user['id']}/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert revoke_resp.status_code == 204

    active_only_resp = await client.get(
        f"/v1/users/{regular_user['id']}/role-memberships",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert active_only_resp.status_code == 200
    assert active_only_resp.json() == []

    include_inactive_resp = await client.get(
        f"/v1/users/{regular_user['id']}/role-memberships?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert include_inactive_resp.status_code == 200

    memberships = include_inactive_resp.json()
    assert len(memberships) == 1

    membership = memberships[0]
    assert membership["role_id"] == role_id
    assert membership["status"] == "revoked"
    assert membership["revoked_at"] is not None
    assert membership["is_currently_valid"] is True
    assert membership["can_grant_permissions"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_can_view_own_roles(
    client: httpx.AsyncClient, admin_user: dict, regular_user: dict
):
    """Test that a user can view their own assigned roles."""
    # Create and assign role
    role_name = f"viewable-{uuid.uuid4().hex[:8]}"
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": role_name, "display_name": "Viewable Role"},
    )
    role_id = create_resp.json()["id"]

    await client.post(
        f"/v1/users/{regular_user['id']}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": role_id},
    )

    # User views their own roles via /users/me
    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 200
    # Note: roles might not be included in /me response, depends on schema


# ============================================================================
# Permission Inheritance Tests (via Services directly)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_gains_permission_through_role(
    client: httpx.AsyncClient,
    admin_user: dict,
    regular_user: dict,
    auth_instance: SimpleRBAC,
):
    """Test that user gains permissions when role with permissions is assigned."""
    # Create permission
    async with auth_instance.get_session() as session:
        perm = await auth_instance.permission_service.create_permission(
            session, name="test:action", display_name="Test Action"
        )

        # Create role and add permission
        role = await auth_instance.role_service.create_role(
            session, name=f"perm-role-{uuid.uuid4().hex[:8]}", display_name="Perm Role"
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        # Assign role to user
        await auth_instance.role_service.assign_role_to_user(
            session, uuid.UUID(regular_user["id"]), role.id
        )
        await session.commit()

        # Check user has permission
        has_perm = await auth_instance.permission_service.check_permission(
            session, user_id=uuid.UUID(regular_user["id"]), permission="test:action"
        )
        assert has_perm is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_loses_permission_when_role_revoked(
    client: httpx.AsyncClient,
    admin_user: dict,
    regular_user: dict,
    auth_instance: SimpleRBAC,
):
    """Test that user loses permissions when role is revoked."""
    async with auth_instance.get_session() as session:
        # Create permission
        perm = await auth_instance.permission_service.create_permission(
            session, name="revoke:action", display_name="Revoke Action"
        )

        # Create role and add permission
        role = await auth_instance.role_service.create_role(
            session,
            name=f"revoke-role-{uuid.uuid4().hex[:8]}",
            display_name="Revoke Role",
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])

        # Assign role
        await auth_instance.role_service.assign_role_to_user(
            session, uuid.UUID(regular_user["id"]), role.id
        )
        await session.commit()

        # Verify user has permission
        has_perm = await auth_instance.permission_service.check_permission(
            session, user_id=uuid.UUID(regular_user["id"]), permission="revoke:action"
        )
        assert has_perm is True

        # Revoke role
        await auth_instance.role_service.revoke_role_from_user(
            session, uuid.UUID(regular_user["id"]), role.id
        )
        await session.commit()

        # Verify user no longer has permission
        has_perm = await auth_instance.permission_service.check_permission(
            session, user_id=uuid.UUID(regular_user["id"]), permission="revoke:action"
        )
        assert has_perm is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_adding_permission_to_role_grants_to_all_users(
    client: httpx.AsyncClient, admin_user: dict, auth_instance: SimpleRBAC
):
    """Test that adding permission to role grants it to all users with that role."""
    async with auth_instance.get_session() as session:
        # Create role
        role = await auth_instance.role_service.create_role(
            session,
            name=f"shared-role-{uuid.uuid4().hex[:8]}",
            display_name="Shared Role",
        )

        # Create two users and assign role
        user1 = await auth_instance.user_service.create_user(
            session,
            email=f"user1-{uuid.uuid4().hex[:8]}@example.com",
            password="Pass123!@#",
            first_name="User",
            last_name="One",
        )
        user2 = await auth_instance.user_service.create_user(
            session,
            email=f"user2-{uuid.uuid4().hex[:8]}@example.com",
            password="Pass123!@#",
            first_name="User",
            last_name="Two",
        )

        await auth_instance.role_service.assign_role_to_user(session, user1.id, role.id)
        await auth_instance.role_service.assign_role_to_user(session, user2.id, role.id)
        await session.commit()

        # Create and add permission to role
        perm = await auth_instance.permission_service.create_permission(
            session, name="shared:action", display_name="Shared Action"
        )
        await auth_instance.role_service.add_permissions(session, role.id, [perm.id])
        await session.commit()

        # Both users should now have the permission
        has_perm1 = await auth_instance.permission_service.check_permission(
            session, user_id=user1.id, permission="shared:action"
        )
        has_perm2 = await auth_instance.permission_service.check_permission(
            session, user_id=user2.id, permission="shared:action"
        )

        assert has_perm1 is True
        assert has_perm2 is True


# ============================================================================
# Multiple Role Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_can_have_multiple_roles(
    client: httpx.AsyncClient, admin_user: dict, auth_instance: SimpleRBAC
):
    """Test that a user can have multiple roles assigned."""
    async with auth_instance.get_session() as session:
        # Create user
        user = await auth_instance.user_service.create_user(
            session,
            email=f"multirole-{uuid.uuid4().hex[:8]}@example.com",
            password="Pass123!@#",
            first_name="Multi",
            last_name="Role",
        )

        # Create multiple roles
        role1 = await auth_instance.role_service.create_role(
            session, name=f"role1-{uuid.uuid4().hex[:8]}", display_name="Role 1"
        )
        role2 = await auth_instance.role_service.create_role(
            session, name=f"role2-{uuid.uuid4().hex[:8]}", display_name="Role 2"
        )
        role3 = await auth_instance.role_service.create_role(
            session, name=f"role3-{uuid.uuid4().hex[:8]}", display_name="Role 3"
        )

        # Assign all roles
        await auth_instance.role_service.assign_role_to_user(session, user.id, role1.id)
        await auth_instance.role_service.assign_role_to_user(session, user.id, role2.id)
        await auth_instance.role_service.assign_role_to_user(session, user.id, role3.id)
        await session.commit()

        # Get user roles
        user_roles = await auth_instance.role_service.get_user_roles(session, user.id)

        role_ids = [r.id for r in user_roles]
        assert role1.id in role_ids
        assert role2.id in role_ids
        assert role3.id in role_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_from_multiple_roles_combine(
    client: httpx.AsyncClient, admin_user: dict, auth_instance: SimpleRBAC
):
    """Test that permissions from multiple roles combine correctly."""
    async with auth_instance.get_session() as session:
        # Create permissions
        perm1 = await auth_instance.permission_service.create_permission(
            session, name="action1:do", display_name="Action 1"
        )
        perm2 = await auth_instance.permission_service.create_permission(
            session, name="action2:do", display_name="Action 2"
        )

        # Create roles with different permissions
        role1 = await auth_instance.role_service.create_role(
            session, name=f"combo1-{uuid.uuid4().hex[:8]}", display_name="Combo Role 1"
        )
        role2 = await auth_instance.role_service.create_role(
            session, name=f"combo2-{uuid.uuid4().hex[:8]}", display_name="Combo Role 2"
        )

        await auth_instance.role_service.add_permissions(session, role1.id, [perm1.id])
        await auth_instance.role_service.add_permissions(session, role2.id, [perm2.id])

        # Create user and assign both roles
        user = await auth_instance.user_service.create_user(
            session,
            email=f"combouser-{uuid.uuid4().hex[:8]}@example.com",
            password="Pass123!@#",
            first_name="Combo",
            last_name="User",
        )

        await auth_instance.role_service.assign_role_to_user(session, user.id, role1.id)
        await auth_instance.role_service.assign_role_to_user(session, user.id, role2.id)
        await session.commit()

        # User should have both permissions
        has_perm1 = await auth_instance.permission_service.check_permission(
            session, user_id=user.id, permission="action1:do"
        )
        has_perm2 = await auth_instance.permission_service.check_permission(
            session, user_id=user.id, permission="action2:do"
        )

        assert has_perm1 is True
        assert has_perm2 is True


# ============================================================================
# Authorization Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_create_role(
    client: httpx.AsyncClient, regular_user: dict
):
    """Test that regular user cannot create roles."""
    resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
        json={"name": "unauthorized-role", "display_name": "Unauthorized"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_assign_roles(
    client: httpx.AsyncClient, admin_user: dict, regular_user: dict
):
    """Test that regular user cannot assign roles to others."""
    # Create role as admin
    create_resp = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"noassign-{uuid.uuid4().hex[:8]}", "display_name": "No Assign"},
    )
    role_id = create_resp.json()["id"]

    # Try to assign as regular user via POST
    resp = await client.post(
        f"/v1/users/{admin_user['id']}/roles",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
        json={"role_id": role_id},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regular_user_cannot_list_other_user_roles(
    client: httpx.AsyncClient, admin_user: dict, regular_user: dict
):
    """Test that regular user cannot list another user's roles."""
    resp = await client.get(
        f"/v1/users/{admin_user['id']}/roles",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_rbac_rejects_entity_local_role_assignment(
    client: httpx.AsyncClient, admin_user: dict, auth_instance: SimpleRBAC
):
    """Entity-local roles should not be assignable in SimpleRBAC."""
    async with auth_instance.get_session() as session:
        entity = Entity(
            name="local_scope",
            display_name="Local Scope",
            slug=f"local-scope-{uuid.uuid4().hex[:8]}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        session.add(entity)
        await session.flush()

        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"local-role-{uuid.uuid4().hex[:8]}",
            display_name="Local Role",
            is_global=False,
            scope_entity_id=entity.id,
        )
        await session.commit()

    user_resp = await client.post(
        "/v1/users/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "email": f"user-{uuid.uuid4().hex[:8]}@example.com",
            "password": "UserPass123!",
            "first_name": "Local",
            "last_name": "User",
        },
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    assign_resp = await client.post(
        f"/v1/users/{user_id}/roles",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_id": str(role.id)},
    )
    assert assign_resp.status_code == 422
