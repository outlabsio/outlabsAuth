import uuid
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import DefinitionStatus
from outlabs_auth.models.sql.role import Role
from outlabs_auth.routers import get_roles_router
from outlabs_auth.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
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
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
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
async def admin_user(auth_instance: SimpleRBAC) -> dict:
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"role-history-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Role",
            last_name="History",
            is_superuser=True,
        )
        await session.commit()

    return {
        "id": str(admin.id),
        "token": create_access_token(
            {"sub": str(admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        ),
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_definition_history_records_crud_and_permission_changes(
    auth_instance: SimpleRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    permission_a = f"history:{unique}_a"
    permission_b = f"history:{unique}_b"
    permission_c = f"history:{unique}_c"
    role_name = f"history-role-{unique}"

    async with auth_instance.get_session() as session:
        await auth_instance.permission_service.create_permission(
            session,
            permission_a,
            "History Permission A",
        )
        await auth_instance.permission_service.create_permission(
            session,
            permission_b,
            "History Permission B",
        )
        await auth_instance.permission_service.create_permission(
            session,
            permission_c,
            "History Permission C",
        )
        await session.commit()

    headers = {"Authorization": f"Bearer {admin_user['token']}"}

    create_resp = await client.post(
        "/v1/roles/",
        headers=headers,
        json={
            "name": role_name,
            "display_name": "History Role",
            "permissions": [permission_a],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    role_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/v1/roles/{role_id}",
        headers=headers,
        json={"display_name": "History Role Updated"},
    )
    assert update_resp.status_code == 200, update_resp.text

    replace_resp = await client.patch(
        f"/v1/roles/{role_id}",
        headers=headers,
        json={"permissions": [permission_a, permission_b]},
    )
    assert replace_resp.status_code == 200, replace_resp.text

    add_resp = await client.post(
        f"/v1/roles/{role_id}/permissions",
        headers=headers,
        json=[permission_c],
    )
    assert add_resp.status_code == 200, add_resp.text

    remove_resp = await client.request(
        "DELETE",
        f"/v1/roles/{role_id}/permissions",
        headers=headers,
        json=[permission_a],
    )
    assert remove_resp.status_code == 200, remove_resp.text

    delete_resp = await client.delete(
        f"/v1/roles/{role_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204, delete_resp.text

    async with auth_instance.get_session() as session:
        deleted_role = await session.get(Role, UUID(role_id))
        assert deleted_role is not None
        assert deleted_role.status == DefinitionStatus.ARCHIVED

        events, total = await auth_instance.role_history_service.list_role_events(
            session,
            UUID(role_id),
            limit=20,
        )
        first_page_events, first_page_total = await auth_instance.role_history_service.list_role_events(
            session,
            UUID(role_id),
            page=1,
            limit=2,
        )
        second_page_events, second_page_total = await auth_instance.role_history_service.list_role_events(
            session,
            UUID(role_id),
            page=2,
            limit=2,
        )
        filtered_events, filtered_total = await auth_instance.role_history_service.list_role_events(
            session,
            UUID(role_id),
            limit=10,
            event_type="permissions_added",
        )
        assert total == 6
        assert [event.event_type for event in events] == [
            "deleted",
            "permissions_removed",
            "permissions_added",
            "permissions_replaced",
            "updated",
            "created",
        ]
        assert first_page_total == 6
        assert [event.event_type for event in first_page_events] == [
            "deleted",
            "permissions_removed",
        ]
        assert second_page_total == 6
        assert [event.event_type for event in second_page_events] == [
            "permissions_added",
            "permissions_replaced",
        ]
        assert filtered_total == 1
        assert [event.event_type for event in filtered_events] == ["permissions_added"]

        deleted_event = events[0]
        assert deleted_event.role_id == UUID(role_id)
        assert deleted_event.actor_user_id == UUID(admin_user["id"])
        assert deleted_event.role_name_snapshot == role_name
        assert deleted_event.role_display_name_snapshot == "History Role Updated"
        assert deleted_event.status_snapshot == DefinitionStatus.ARCHIVED
        assert deleted_event.permission_names_snapshot == [permission_b, permission_c]
        assert deleted_event.after["status"] == "archived"

        removed_event = events[1]
        assert removed_event.event_source == "role_service.remove_permissions_by_name"
        assert removed_event.event_metadata["removed_permission_names"] == [permission_a]
        assert removed_event.before["permission_names"] == [permission_a, permission_b, permission_c]
        assert removed_event.after["permission_names"] == [permission_b, permission_c]

        added_event = events[2]
        assert added_event.event_source == "role_service.add_permissions_by_name"
        assert added_event.event_metadata["added_permission_names"] == [permission_c]
        assert added_event.before["permission_names"] == [permission_a, permission_b]
        assert added_event.after["permission_names"] == [permission_a, permission_b, permission_c]

        replaced_event = events[3]
        assert replaced_event.event_source == "role_service.update_role"
        assert replaced_event.event_metadata["added_permission_names"] == [permission_b]
        assert replaced_event.event_metadata["removed_permission_names"] == []
        assert replaced_event.before["permission_names"] == [permission_a]
        assert replaced_event.after["permission_names"] == [permission_a, permission_b]

        updated_event = events[4]
        assert updated_event.event_source == "role_service.update_role"
        assert updated_event.status_snapshot == DefinitionStatus.ACTIVE
        assert updated_event.event_metadata["changed_fields"] == ["role_display_name"]
        assert updated_event.before["role_display_name"] == "History Role"
        assert updated_event.after["role_display_name"] == "History Role Updated"

        created_event = events[5]
        assert created_event.event_source == "role_service.create_role"
        assert created_event.actor_user_id == UUID(admin_user["id"])
        assert created_event.role_name_snapshot == role_name
        assert created_event.status_snapshot == DefinitionStatus.ACTIVE
        assert created_event.permission_names_snapshot == [permission_a]
        assert created_event.after["permission_names"] == [permission_a]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_definition_history_records_abac_condition_group_and_condition_changes(
    auth_instance: SimpleRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    role_name = f"abac-history-role-{unique}"
    headers = {"Authorization": f"Bearer {admin_user['token']}"}

    create_resp = await client.post(
        "/v1/roles/",
        headers=headers,
        json={
            "name": role_name,
            "display_name": "ABAC History Role",
            "permissions": [],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    role_id = create_resp.json()["id"]

    create_group_resp = await client.post(
        f"/v1/roles/{role_id}/condition-groups",
        headers=headers,
        json={"operator": "OR", "description": "fallback access"},
    )
    assert create_group_resp.status_code == 201, create_group_resp.text
    group_id = create_group_resp.json()["id"]

    create_condition_resp = await client.post(
        f"/v1/roles/{role_id}/conditions",
        headers=headers,
        json={
            "attribute": "env.method",
            "operator": "equals",
            "value": "POST",
            "value_type": "string",
            "description": "post only",
            "condition_group_id": group_id,
        },
    )
    assert create_condition_resp.status_code == 201, create_condition_resp.text
    condition_id = create_condition_resp.json()["id"]

    update_group_resp = await client.patch(
        f"/v1/roles/{role_id}/condition-groups/{group_id}",
        headers=headers,
        json={"description": None},
    )
    assert update_group_resp.status_code == 200, update_group_resp.text

    update_condition_resp = await client.patch(
        f"/v1/roles/{role_id}/conditions/{condition_id}",
        headers=headers,
        json={"condition_group_id": None, "description": None},
    )
    assert update_condition_resp.status_code == 200, update_condition_resp.text

    delete_condition_resp = await client.delete(
        f"/v1/roles/{role_id}/conditions/{condition_id}",
        headers=headers,
    )
    assert delete_condition_resp.status_code == 204, delete_condition_resp.text

    delete_group_resp = await client.delete(
        f"/v1/roles/{role_id}/condition-groups/{group_id}",
        headers=headers,
    )
    assert delete_group_resp.status_code == 204, delete_group_resp.text

    async with auth_instance.get_session() as session:
        events, total = await auth_instance.role_history_service.list_role_events(
            session,
            UUID(role_id),
            limit=20,
        )
        assert total == 7
        assert [event.event_type for event in events] == [
            "condition_group_deleted",
            "condition_deleted",
            "condition_updated",
            "condition_group_updated",
            "condition_created",
            "condition_group_created",
            "created",
        ]

        deleted_group_event = events[0]
        assert deleted_group_event.event_source == "role_service.delete_condition_group"
        assert deleted_group_event.event_metadata["deleted_group"]["id"] == group_id
        assert deleted_group_event.before["condition_groups"] == [
            {"id": group_id, "operator": "OR", "description": None}
        ]
        assert deleted_group_event.after["condition_groups"] == []

        deleted_condition_event = events[1]
        assert deleted_condition_event.event_source == "role_service.delete_condition"
        assert deleted_condition_event.event_metadata["deleted_condition"]["id"] == condition_id
        assert deleted_condition_event.before["conditions"] == [
            {
                "id": condition_id,
                "condition_group_id": None,
                "attribute": "env.method",
                "operator": "equals",
                "value": "POST",
                "value_type": "string",
                "description": None,
            }
        ]
        assert deleted_condition_event.after["conditions"] == []

        updated_condition_event = events[2]
        assert updated_condition_event.event_source == "role_service.update_condition"
        assert updated_condition_event.event_metadata["changed_fields"] == [
            "condition_group_id",
            "description",
        ]
        assert updated_condition_event.event_metadata["before_condition"]["condition_group_id"] == group_id
        assert updated_condition_event.event_metadata["after_condition"]["condition_group_id"] is None
        assert updated_condition_event.event_metadata["before_condition"]["description"] == "post only"
        assert updated_condition_event.event_metadata["after_condition"]["description"] is None

        updated_group_event = events[3]
        assert updated_group_event.event_source == "role_service.update_condition_group"
        assert updated_group_event.event_metadata["changed_fields"] == ["description"]
        assert updated_group_event.event_metadata["before_group"] == {
            "id": group_id,
            "operator": "OR",
            "description": "fallback access",
        }
        assert updated_group_event.event_metadata["after_group"] == {
            "id": group_id,
            "operator": "OR",
            "description": None,
        }

        created_condition_event = events[4]
        assert created_condition_event.event_source == "role_service.create_condition"
        assert created_condition_event.event_metadata["condition"] == {
            "id": condition_id,
            "condition_group_id": group_id,
            "attribute": "env.method",
            "operator": "equals",
            "value": "POST",
            "value_type": "string",
            "description": "post only",
        }

        created_group_event = events[5]
        assert created_group_event.event_source == "role_service.create_condition_group"
        assert created_group_event.event_metadata["condition_group"] == {
            "id": group_id,
            "operator": "OR",
            "description": "fallback access",
        }
        assert created_group_event.after["condition_groups"] == [
            {"id": group_id, "operator": "OR", "description": "fallback access"}
        ]

        created_role_event = events[6]
        assert created_role_event.event_source == "role_service.create_role"
        assert created_role_event.after["condition_groups"] == []
        assert created_role_event.after["conditions"] == []
