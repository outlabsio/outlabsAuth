import uuid
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.enums import DefinitionStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.routers import get_permissions_router
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
    app.include_router(get_permissions_router(auth_instance, prefix="/v1/permissions"))
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
            email=f"permission-history-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Permission",
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
async def test_permission_definition_history_records_crud_changes_and_survives_delete(
    auth_instance: SimpleRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    permission_name = f"history:{unique}"
    headers = {"Authorization": f"Bearer {admin_user['token']}"}

    create_resp = await client.post(
        "/v1/permissions/",
        headers=headers,
        json={
            "name": permission_name,
            "display_name": "History Permission",
            "description": "original description",
            "is_system": False,
            "is_active": True,
            "tags": ["alpha"],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    permission_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/v1/permissions/{permission_id}",
        headers=headers,
        json={
            "display_name": "History Permission Updated",
            "description": "updated description",
            "is_active": False,
            "tags": ["beta", "gamma"],
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    delete_resp = await client.delete(
        f"/v1/permissions/{permission_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204, delete_resp.text

    async with auth_instance.get_session() as session:
        deleted_permission = await session.get(Permission, UUID(permission_id))
        assert deleted_permission is not None
        assert deleted_permission.status == DefinitionStatus.ARCHIVED
        assert deleted_permission.is_active is False

        events, total = await auth_instance.permission_history_service.list_permission_events(
            session,
            UUID(permission_id),
            limit=20,
        )
        first_page_events, first_page_total = (
            await auth_instance.permission_history_service.list_permission_events(
                session,
                UUID(permission_id),
                page=1,
                limit=2,
            )
        )
        second_page_events, second_page_total = (
            await auth_instance.permission_history_service.list_permission_events(
                session,
                UUID(permission_id),
                page=2,
                limit=2,
            )
        )
        filtered_events, filtered_total = (
            await auth_instance.permission_history_service.list_permission_events(
                session,
                UUID(permission_id),
                limit=10,
                event_type="updated",
            )
        )
        assert total == 3
        assert [event.event_type for event in events] == [
            "deleted",
            "updated",
            "created",
        ]
        assert first_page_total == 3
        assert [event.event_type for event in first_page_events] == [
            "deleted",
            "updated",
        ]
        assert second_page_total == 3
        assert [event.event_type for event in second_page_events] == ["created"]
        assert filtered_total == 1
        assert [event.event_type for event in filtered_events] == ["updated"]

        deleted_event = events[0]
        assert deleted_event.permission_id == UUID(permission_id)
        assert deleted_event.actor_user_id == UUID(admin_user["id"])
        assert deleted_event.permission_name_snapshot == permission_name
        assert deleted_event.permission_display_name_snapshot == "History Permission Updated"
        assert deleted_event.permission_description_snapshot == "updated description"
        assert deleted_event.status_snapshot == DefinitionStatus.ARCHIVED
        assert deleted_event.is_active_snapshot is False
        assert deleted_event.tag_names_snapshot == ["beta", "gamma"]
        assert deleted_event.after["status"] == "archived"
        assert deleted_event.after["is_active"] is False

        updated_event = events[1]
        assert updated_event.event_source == "permission_service.update_permission"
        assert updated_event.status_snapshot == DefinitionStatus.INACTIVE
        assert updated_event.event_metadata["changed_fields"] == [
            "permission_display_name",
            "permission_description",
            "status",
            "is_active",
            "tag_names",
        ]
        assert updated_event.before["permission_display_name"] == "History Permission"
        assert updated_event.after["permission_display_name"] == "History Permission Updated"
        assert updated_event.before["permission_description"] == "original description"
        assert updated_event.after["permission_description"] == "updated description"
        assert updated_event.before["status"] == "active"
        assert updated_event.after["status"] == "inactive"
        assert updated_event.before["is_active"] is True
        assert updated_event.after["is_active"] is False
        assert updated_event.before["tag_names"] == ["alpha"]
        assert updated_event.after["tag_names"] == ["beta", "gamma"]

        created_event = events[2]
        assert created_event.event_source == "permission_service.create_permission"
        assert created_event.actor_user_id == UUID(admin_user["id"])
        assert created_event.permission_name_snapshot == permission_name
        assert created_event.permission_display_name_snapshot == "History Permission"
        assert created_event.permission_description_snapshot == "original description"
        assert created_event.status_snapshot == DefinitionStatus.ACTIVE
        assert created_event.is_active_snapshot is True
        assert created_event.tag_names_snapshot == ["alpha"]
        assert created_event.after["tag_names"] == ["alpha"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permission_definition_history_records_abac_condition_group_and_condition_changes(
    auth_instance: SimpleRBAC,
    client: httpx.AsyncClient,
    admin_user: dict,
):
    unique = uuid.uuid4().hex[:8]
    permission_name = f"abac-history:{unique}"
    headers = {"Authorization": f"Bearer {admin_user['token']}"}

    create_resp = await client.post(
        "/v1/permissions/",
        headers=headers,
        json={
            "name": permission_name,
            "display_name": "ABAC History Permission",
            "description": "permission with conditions",
            "is_system": False,
            "is_active": True,
            "tags": [],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    permission_id = create_resp.json()["id"]

    create_group_resp = await client.post(
        f"/v1/permissions/{permission_id}/condition-groups",
        headers=headers,
        json={"operator": "OR", "description": "fallback access"},
    )
    assert create_group_resp.status_code == 201, create_group_resp.text
    group_id = create_group_resp.json()["id"]

    create_condition_resp = await client.post(
        f"/v1/permissions/{permission_id}/conditions",
        headers=headers,
        json={
            "attribute": "context.department",
            "operator": "equals",
            "value": "finance",
            "value_type": "string",
            "description": "department gate",
            "condition_group_id": group_id,
        },
    )
    assert create_condition_resp.status_code == 201, create_condition_resp.text
    condition_id = create_condition_resp.json()["id"]

    update_group_resp = await client.patch(
        f"/v1/permissions/{permission_id}/condition-groups/{group_id}",
        headers=headers,
        json={"description": None},
    )
    assert update_group_resp.status_code == 200, update_group_resp.text

    update_condition_resp = await client.patch(
        f"/v1/permissions/{permission_id}/conditions/{condition_id}",
        headers=headers,
        json={"condition_group_id": None, "description": None},
    )
    assert update_condition_resp.status_code == 200, update_condition_resp.text

    delete_condition_resp = await client.delete(
        f"/v1/permissions/{permission_id}/conditions/{condition_id}",
        headers=headers,
    )
    assert delete_condition_resp.status_code == 204, delete_condition_resp.text

    delete_group_resp = await client.delete(
        f"/v1/permissions/{permission_id}/condition-groups/{group_id}",
        headers=headers,
    )
    assert delete_group_resp.status_code == 204, delete_group_resp.text

    async with auth_instance.get_session() as session:
        events, total = await auth_instance.permission_history_service.list_permission_events(
            session,
            UUID(permission_id),
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
        assert deleted_group_event.event_source == "permission_service.delete_condition_group"
        assert deleted_group_event.event_metadata["deleted_group"]["id"] == group_id
        assert deleted_group_event.before["condition_groups"] == [
            {"id": group_id, "operator": "OR", "description": None}
        ]
        assert deleted_group_event.after["condition_groups"] == []

        deleted_condition_event = events[1]
        assert deleted_condition_event.event_source == "permission_service.delete_condition"
        assert deleted_condition_event.event_metadata["deleted_condition"]["id"] == condition_id
        assert deleted_condition_event.before["conditions"] == [
            {
                "id": condition_id,
                "condition_group_id": None,
                "attribute": "context.department",
                "operator": "equals",
                "value": "finance",
                "value_type": "string",
                "description": None,
            }
        ]
        assert deleted_condition_event.after["conditions"] == []

        updated_condition_event = events[2]
        assert updated_condition_event.event_source == "permission_service.update_condition"
        assert updated_condition_event.event_metadata["changed_fields"] == [
            "condition_group_id",
            "description",
        ]
        assert updated_condition_event.event_metadata["before_condition"]["condition_group_id"] == group_id
        assert updated_condition_event.event_metadata["after_condition"]["condition_group_id"] is None
        assert updated_condition_event.event_metadata["before_condition"]["description"] == "department gate"
        assert updated_condition_event.event_metadata["after_condition"]["description"] is None

        updated_group_event = events[3]
        assert updated_group_event.event_source == "permission_service.update_condition_group"
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
        assert created_condition_event.event_source == "permission_service.create_condition"
        assert created_condition_event.event_metadata["condition"] == {
            "id": condition_id,
            "condition_group_id": group_id,
            "attribute": "context.department",
            "operator": "equals",
            "value": "finance",
            "value_type": "string",
            "description": "department gate",
        }

        created_group_event = events[5]
        assert created_group_event.event_source == "permission_service.create_condition_group"
        assert created_group_event.event_metadata["condition_group"] == {
            "id": group_id,
            "operator": "OR",
            "description": "fallback access",
        }
        assert created_group_event.after["condition_groups"] == [
            {"id": group_id, "operator": "OR", "description": "fallback access"}
        ]

        created_permission_event = events[6]
        assert created_permission_event.event_source == "permission_service.create_permission"
        assert created_permission_event.after["condition_groups"] == []
        assert created_permission_event.after["conditions"] == []
