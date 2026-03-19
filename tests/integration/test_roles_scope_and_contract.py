import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import EntityClass, RoleScope
from outlabs_auth.routers import (
    get_auth_router,
    get_entities_router,
    get_memberships_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
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
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    app.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth_instance, prefix="/v1/permissions"))
    app.include_router(get_entities_router(auth_instance, prefix="/v1/entities"))
    app.include_router(get_memberships_router(auth_instance, prefix="/v1/memberships"))
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
async def admin_user(auth_instance: EnterpriseRBAC) -> dict[str, str]:
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
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
    return {"id": str(admin.id), "token": token}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_contract_round_trips_assignable_at_types(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict[str, str],
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name=f"root-{uuid.uuid4().hex[:8]}",
            display_name="Contract Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"role-contract:{uuid.uuid4().hex[:6]}",
            display_name="Role Contract Permission",
            description="contract test permission",
        )
        await session.commit()

    create_response = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"contract-role-{uuid.uuid4().hex[:8]}",
            "display_name": "Contract Role",
            "description": "round-trip contract",
            "permissions": [permission.name],
            "is_global": False,
            "root_entity_id": str(root.id),
            "assignable_at_types": ["department", "department"],
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["assignable_at_types"] == ["department"]
    assert "entity_type_permissions" not in created
    role_id = created["id"]

    get_response = await client.get(
        f"/v1/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["assignable_at_types"] == ["department"]
    assert "entity_type_permissions" not in fetched

    list_response = await client.get(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        params={"root_entity_id": str(root.id)},
    )
    assert list_response.status_code == 200, list_response.text
    listed = next(item for item in list_response.json()["items"] if item["id"] == role_id)
    assert listed["assignable_at_types"] == ["department"]
    assert "entity_type_permissions" not in listed

    update_response = await client.patch(
        f"/v1/roles/{role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"display_name": "Contract Role Updated", "assignable_at_types": ["team"]},
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["display_name"] == "Contract Role Updated"
    assert updated["assignable_at_types"] == ["team"]
    assert "entity_type_permissions" not in updated


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_entity_catalog_and_membership_updates_respect_assignable_at_types(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict[str, str],
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name=f"root-{uuid.uuid4().hex[:8]}",
            display_name="Assignable Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session,
            name=f"department-{uuid.uuid4().hex[:8]}",
            display_name="Assignable Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session,
            name=f"team-{uuid.uuid4().hex[:8]}",
            display_name="Assignable Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )

        base_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"base-role-{uuid.uuid4().hex[:8]}",
            display_name="Base Role",
            root_entity_id=root.id,
            is_global=False,
        )
        department_only_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"department-only-{uuid.uuid4().hex[:8]}",
            display_name="Department Only",
            root_entity_id=root.id,
            is_global=False,
            assignable_at_types=["department"],
        )
        team_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"team-role-{uuid.uuid4().hex[:8]}",
            display_name="Team Role",
            scope_entity_id=department.id,
            scope=RoleScope.HIERARCHY,
            is_global=False,
            assignable_at_types=["team"],
        )

        member = await auth_instance.user_service.create_user(
            session=session,
            email=f"member-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Team",
            last_name="Member",
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=member.id,
            role_ids=[base_role.id],
        )
        await session.commit()

    department_roles_response = await client.get(
        f"/v1/roles/entity/{department.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert department_roles_response.status_code == 200, department_roles_response.text
    department_role_ids = {item["id"] for item in department_roles_response.json()["items"]}
    assert str(department_only_role.id) in department_role_ids
    assert str(team_role.id) not in department_role_ids

    team_roles_response = await client.get(
        f"/v1/roles/entity/{team.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert team_roles_response.status_code == 200, team_roles_response.text
    team_role_ids = {item["id"] for item in team_roles_response.json()["items"]}
    assert str(department_only_role.id) not in team_role_ids
    assert str(team_role.id) in team_role_ids

    reject_update_response = await client.patch(
        f"/v1/memberships/{team.id}/{member.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_ids": [str(department_only_role.id)]},
    )
    assert reject_update_response.status_code == 422, reject_update_response.text

    allow_update_response = await client.patch(
        f"/v1/memberships/{team.id}/{member.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"role_ids": [str(team_role.id)]},
    )
    assert allow_update_response.status_code == 200, allow_update_response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inactive_roles_are_hidden_from_entity_catalog_and_membership_assignment(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict[str, str],
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name=f"root-{uuid.uuid4().hex[:8]}",
            display_name="Lifecycle Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await auth_instance.entity_service.create_entity(
            session,
            name=f"team-{uuid.uuid4().hex[:8]}",
            display_name="Lifecycle Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        member = await auth_instance.user_service.create_user(
            session=session,
            email=f"lifecycle-member-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Lifecycle",
            last_name="Member",
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"lifecycle-role-{uuid.uuid4().hex[:8]}",
            display_name="Lifecycle Role",
            root_entity_id=root.id,
            is_global=False,
        )
        await session.commit()

    deactivate_response = await client.patch(
        f"/v1/roles/{role.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "inactive"},
    )
    assert deactivate_response.status_code == 200, deactivate_response.text
    assert deactivate_response.json()["status"] == "inactive"

    entity_roles_response = await client.get(
        f"/v1/roles/entity/{team.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert entity_roles_response.status_code == 200, entity_roles_response.text
    entity_role_ids = {item["id"] for item in entity_roles_response.json()["items"]}
    assert str(role.id) not in entity_role_ids

    create_membership_response = await client.post(
        "/v1/memberships/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "entity_id": str(team.id),
            "user_id": str(member.id),
            "role_ids": [str(role.id)],
        },
    )
    assert create_membership_response.status_code == 422, create_membership_response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scoped_admin_role_management_is_limited_to_access_scope(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
):
    async with auth_instance.get_session() as session:
        root_a = await auth_instance.entity_service.create_entity(
            session,
            name=f"root-a-{uuid.uuid4().hex[:8]}",
            display_name="Root A",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department_a = await auth_instance.entity_service.create_entity(
            session,
            name=f"department-a-{uuid.uuid4().hex[:8]}",
            display_name="Department A",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root_a.id,
        )
        root_b = await auth_instance.entity_service.create_entity(
            session,
            name=f"root-b-{uuid.uuid4().hex[:8]}",
            display_name="Root B",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

        permissions = []
        for permission_name in ("role:read", "role:create", "role:update", "role:delete"):
            permissions.append(
                await auth_instance.permission_service.create_permission(
                    session,
                    name=permission_name,
                    display_name=permission_name,
                    description="role management permission",
                )
            )

        management_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"root-a-manager-{uuid.uuid4().hex[:8]}",
            display_name="Root A Role Manager",
            root_entity_id=root_a.id,
            is_global=False,
        )
        await auth_instance.role_service.add_permissions(
            session,
            management_role.id,
            [permission.id for permission in permissions],
        )

        visible_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"visible-role-{uuid.uuid4().hex[:8]}",
            display_name="Visible Role",
            root_entity_id=root_a.id,
            is_global=False,
        )
        hidden_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"hidden-role-{uuid.uuid4().hex[:8]}",
            display_name="Hidden Role",
            root_entity_id=root_b.id,
            is_global=False,
        )
        global_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"global-role-{uuid.uuid4().hex[:8]}",
            display_name="Global Role",
            is_global=True,
        )

        scoped_admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"scoped-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Scoped",
            last_name="Admin",
            root_entity_id=root_a.id,
        )
        await auth_instance.role_service.assign_role_to_user(
            session=session,
            user_id=scoped_admin.id,
            role_id=management_role.id,
        )
        await session.commit()

    scoped_admin_token = create_access_token(
        {"sub": str(scoped_admin.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
    )
    headers = {"Authorization": f"Bearer {scoped_admin_token}"}

    list_response = await client.get("/v1/roles/", headers=headers)
    assert list_response.status_code == 200, list_response.text
    listed_ids = {item["id"] for item in list_response.json()["items"]}
    assert str(visible_role.id) in listed_ids
    assert str(hidden_role.id) not in listed_ids
    assert str(global_role.id) not in listed_ids

    visible_get_response = await client.get(f"/v1/roles/{visible_role.id}", headers=headers)
    assert visible_get_response.status_code == 200, visible_get_response.text

    hidden_get_response = await client.get(f"/v1/roles/{hidden_role.id}", headers=headers)
    assert hidden_get_response.status_code == 403, hidden_get_response.text

    global_get_response = await client.get(f"/v1/roles/{global_role.id}", headers=headers)
    assert global_get_response.status_code == 403, global_get_response.text

    allowed_create_response = await client.post(
        "/v1/roles/",
        headers=headers,
        json={
            "name": f"allowed-root-role-{uuid.uuid4().hex[:8]}",
            "display_name": "Allowed Root Role",
            "is_global": False,
            "root_entity_id": str(root_a.id),
        },
    )
    assert allowed_create_response.status_code == 201, allowed_create_response.text

    allowed_entity_create_response = await client.post(
        "/v1/roles/",
        headers=headers,
        json={
            "name": f"allowed-entity-role-{uuid.uuid4().hex[:8]}",
            "display_name": "Allowed Entity Role",
            "is_global": False,
            "scope_entity_id": str(department_a.id),
        },
    )
    assert allowed_entity_create_response.status_code == 201, allowed_entity_create_response.text

    other_root_create_response = await client.post(
        "/v1/roles/",
        headers=headers,
        json={
            "name": f"other-root-role-{uuid.uuid4().hex[:8]}",
            "display_name": "Other Root Role",
            "is_global": False,
            "root_entity_id": str(root_b.id),
        },
    )
    assert other_root_create_response.status_code == 403, other_root_create_response.text

    global_create_response = await client.post(
        "/v1/roles/",
        headers=headers,
        json={
            "name": f"forbidden-global-role-{uuid.uuid4().hex[:8]}",
            "display_name": "Forbidden Global Role",
            "is_global": True,
        },
    )
    assert global_create_response.status_code == 403, global_create_response.text

    hidden_update_response = await client.patch(
        f"/v1/roles/{hidden_role.id}",
        headers=headers,
        json={"display_name": "Should Fail"},
    )
    assert hidden_update_response.status_code == 403, hidden_update_response.text

    hidden_delete_response = await client.delete(
        f"/v1/roles/{hidden_role.id}",
        headers=headers,
    )
    assert hidden_delete_response.status_code == 403, hidden_delete_response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_assigned_roles_apply_retroactively_on_create_and_toggle(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict[str, str],
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name=f"root-{uuid.uuid4().hex[:8]}",
            display_name="Auto Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session,
            name=f"department-{uuid.uuid4().hex[:8]}",
            display_name="Auto Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session,
            name=f"team-{uuid.uuid4().hex[:8]}",
            display_name="Auto Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )
        member = await auth_instance.user_service.create_user(
            session=session,
            email=f"auto-member-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Auto",
            last_name="Member",
        )
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=member.id,
            role_ids=[],
        )
        await session.commit()

    create_response = await client.post(
        "/v1/roles/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"auto-create-role-{uuid.uuid4().hex[:8]}",
            "display_name": "Auto Create Role",
            "is_global": False,
            "scope_entity_id": str(department.id),
            "scope": "hierarchy",
            "is_auto_assigned": True,
        },
    )
    assert create_response.status_code == 201, create_response.text
    created_role_id = create_response.json()["id"]

    async with auth_instance.get_session() as session:
        membership = await auth_instance.membership_service.get_member(
            session,
            entity_id=team.id,
            user_id=member.id,
        )
        assert membership is not None
        assert created_role_id in {str(role.id) for role in membership.roles}

        toggled_role = await auth_instance.role_service.create_role(
            session=session,
            name=f"auto-toggle-role-{uuid.uuid4().hex[:8]}",
            display_name="Auto Toggle Role",
            scope_entity_id=department.id,
            scope=RoleScope.HIERARCHY,
            is_global=False,
            is_auto_assigned=False,
        )
        await session.commit()
        toggled_role_id = str(toggled_role.id)

    toggle_on_response = await client.patch(
        f"/v1/roles/{toggled_role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"is_auto_assigned": True},
    )
    assert toggle_on_response.status_code == 200, toggle_on_response.text

    async with auth_instance.get_session() as session:
        membership = await auth_instance.membership_service.get_member(
            session,
            entity_id=team.id,
            user_id=member.id,
        )
        assert membership is not None
        role_ids = {str(role.id) for role in membership.roles}
        assert toggled_role_id in role_ids

    toggle_off_response = await client.patch(
        f"/v1/roles/{toggled_role_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"is_auto_assigned": False},
    )
    assert toggle_off_response.status_code == 200, toggle_off_response.text

    async with auth_instance.get_session() as session:
        membership = await auth_instance.membership_service.get_member(
            session,
            entity_id=team.id,
            user_id=member.id,
        )
        assert membership is not None
        assert toggled_role_id in {str(role.id) for role in membership.roles}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inactive_auto_assigned_roles_do_not_apply_to_new_members(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict[str, str],
):
    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session,
            name=f"root-{uuid.uuid4().hex[:8]}",
            display_name="Inactive Auto Root",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        department = await auth_instance.entity_service.create_entity(
            session,
            name=f"department-{uuid.uuid4().hex[:8]}",
            display_name="Inactive Auto Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        team = await auth_instance.entity_service.create_entity(
            session,
            name=f"team-{uuid.uuid4().hex[:8]}",
            display_name="Inactive Auto Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=department.id,
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"inactive-auto-role-{uuid.uuid4().hex[:8]}",
            display_name="Inactive Auto Role",
            scope_entity_id=department.id,
            scope=RoleScope.HIERARCHY,
            is_global=False,
            is_auto_assigned=True,
        )
        member = await auth_instance.user_service.create_user(
            session=session,
            email=f"inactive-auto-member-{uuid.uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            first_name="Inactive",
            last_name="Auto",
        )
        await session.commit()

    deactivate_response = await client.patch(
        f"/v1/roles/{role.id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"status": "inactive"},
    )
    assert deactivate_response.status_code == 200, deactivate_response.text

    async with auth_instance.get_session() as session:
        await auth_instance.membership_service.add_member(
            session=session,
            entity_id=team.id,
            user_id=member.id,
            role_ids=[],
        )
        await session.commit()

        membership = await auth_instance.membership_service.get_member(
            session,
            entity_id=team.id,
            user_id=member.id,
        )
        assert membership is not None
        assert str(role.id) not in {str(assigned_role.id) for assigned_role in membership.roles}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_roles_reject_role_abac_mutations(
    client: httpx.AsyncClient,
    auth_instance: EnterpriseRBAC,
    admin_user: dict[str, str],
):
    async with auth_instance.get_session() as session:
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"system-role-{uuid.uuid4().hex[:8]}",
            display_name="System Role",
            is_global=True,
            is_system_role=True,
        )
        await session.commit()

    create_group_response = await client.post(
        f"/v1/roles/{role.id}/condition-groups",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"operator": "AND", "description": "should fail"},
    )
    assert create_group_response.status_code == 400, create_group_response.text

    create_condition_response = await client.post(
        f"/v1/roles/{role.id}/conditions",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "attribute": "env.method",
            "operator": "equals",
            "value": "POST",
            "value_type": "string",
        },
    )
    assert create_condition_response.status_code == 400, create_condition_response.text
