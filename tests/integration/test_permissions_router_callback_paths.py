import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException

from outlabs_auth import SimpleRBAC
from outlabs_auth.core.exceptions import InvalidInputError, PermissionNotFoundError
from outlabs_auth.routers import get_permissions_router
from outlabs_auth.schemas.abac import (
    AbacConditionCreateRequest,
    AbacConditionUpdateRequest,
    ConditionGroupCreateRequest,
    ConditionGroupUpdateRequest,
)
from outlabs_auth.schemas.permission import (
    PermissionCheckRequest,
    PermissionCreateRequest,
    PermissionUpdateRequest,
)


class DummyObs:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str, dict]] = []

    def log_500_error(self, exception: Exception, **extra) -> None:
        self.errors.append((type(exception).__name__, str(exception), extra))


class DummyObservability:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []
        self.logger = SimpleNamespace(
            debug=self._record,
            info=self._record,
            error=self._record,
        )

    def _record(self, event: str, **fields) -> None:
        self.records.append((event, fields))

    async def shutdown(self) -> None:
        return None


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _runtime_raiser(message: str):
    async def _raiser(*args, **kwargs):
        raise RuntimeError(message)

    return _raiser


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    auth.observability = DummyObservability()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def permissions_router(auth_instance: SimpleRBAC):
    return get_permissions_router(auth_instance, prefix="/v1/permissions")


async def _create_user(auth: SimpleRBAC, session, *, email_prefix: str):
    return await auth.user_service.create_user(
        session=session,
        email=f"{email_prefix}-{_suffix()}@example.com",
        password="TestPass123!",
        first_name="Perm",
        last_name="Actor",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_router_callback_crud_and_user_paths(
    auth_instance: SimpleRBAC,
    permissions_router,
    monkeypatch: pytest.MonkeyPatch,
):
    create_permission = _endpoint(permissions_router, "/v1/permissions/", "POST")
    get_permission = _endpoint(permissions_router, "/v1/permissions/{permission_id}", "GET")
    update_permission = _endpoint(permissions_router, "/v1/permissions/{permission_id}", "PATCH")
    delete_permission = _endpoint(permissions_router, "/v1/permissions/{permission_id}", "DELETE")
    get_my_permissions = _endpoint(permissions_router, "/v1/permissions/me", "GET")
    check_permissions = _endpoint(permissions_router, "/v1/permissions/check", "POST")
    get_user_permissions = _endpoint(permissions_router, "/v1/permissions/user/{user_id}", "GET")

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="perm-actor")
        existing = await auth_instance.permission_service.create_permission(
            session,
            name=f"user:{_suffix()}",
            display_name="Existing Permission",
        )

        created = await create_permission(
            data=PermissionCreateRequest(
                name=f"role:{_suffix()}",
                display_name="Created Permission",
                description="created via callback",
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert created.name.startswith("role:")

        with pytest.raises(HTTPException) as exc:
            await create_permission(
                data=PermissionCreateRequest(
                    name=existing.name,
                    display_name="Duplicate Permission",
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 409

        with pytest.raises(HTTPException) as exc:
            await get_permission(
                permission_id=uuid.uuid4(),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _noop_update(*args, **kwargs):
            return None

        async def _missing_permission(*args, **kwargs):
            return None

        monkeypatch.setattr(auth_instance.permission_service, "update_permission", _noop_update)
        monkeypatch.setattr(auth_instance.permission_service, "get_permission_by_id", _missing_permission)
        with pytest.raises(HTTPException) as exc:
            await update_permission(
                permission_id=existing.id,
                data=PermissionUpdateRequest(display_name="Renamed"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(auth_instance.permission_service, "delete_permission", _missing_permission)
        with pytest.raises(HTTPException) as exc:
            await delete_permission(
                permission_id=existing.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _return_permissions(*args, **kwargs):
            return ["user:read", "user:update"]

        monkeypatch.setattr(auth_instance.permission_service, "get_user_permissions", _return_permissions)
        mine = await get_my_permissions(
            entity_id=None,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert mine == ["user:read", "user:update"]

        with pytest.raises(HTTPException) as exc:
            await check_permissions(
                data=PermissionCheckRequest(
                    user_id=str(uuid.uuid4()),
                    permissions=["user:read", "role:update"],
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _check_permission(*args, **kwargs):
            return kwargs["permission"] == "user:read"

        monkeypatch.setattr(auth_instance.permission_service, "check_permission", _check_permission)
        checked = await check_permissions(
            data=PermissionCheckRequest(
                user_id=str(actor.id),
                permissions=["user:read", "role:update"],
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert checked.has_all_permissions is False
        assert checked.results == {"user:read": True, "role:update": False}

        with pytest.raises(HTTPException) as exc:
            await get_user_permissions(
                user_id=uuid.uuid4(),
                entity_id=None,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_router_callback_list_and_abac_paths(
    auth_instance: SimpleRBAC,
    permissions_router,
    monkeypatch: pytest.MonkeyPatch,
):
    list_permissions = _endpoint(permissions_router, "/v1/permissions/", "GET")
    create_group = _endpoint(permissions_router, "/v1/permissions/{permission_id}/condition-groups", "POST")
    update_group = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/condition-groups/{group_id}",
        "PATCH",
    )
    delete_group = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/condition-groups/{group_id}",
        "DELETE",
    )
    create_condition = _endpoint(permissions_router, "/v1/permissions/{permission_id}/conditions", "POST")
    update_condition = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/conditions/{condition_id}",
        "PATCH",
    )
    delete_condition = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/conditions/{condition_id}",
        "DELETE",
    )

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="perm-abac")
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"audit:{_suffix()}",
            display_name="ABAC Permission",
        )

        obs = DummyObs()
        monkeypatch.setattr(
            auth_instance.permission_service,
            "list_permissions",
            _runtime_raiser("permission list exploded"),
        )
        with pytest.raises(RuntimeError, match="permission list exploded"):
            await list_permissions(
                page=1,
                limit=25,
                resource=None,
                session=session,
                obs=obs,
            )
        assert obs.errors == [("RuntimeError", "permission list exploded", {"page": 1, "limit": 25, "resource": None})]

        async def _permission_missing(*args, **kwargs):
            raise PermissionNotFoundError(message="Permission missing")

        async def _invalid_input(*args, **kwargs):
            raise InvalidInputError(message="Bad ABAC request")

        monkeypatch.setattr(auth_instance.permission_service, "create_permission_condition_group", _permission_missing)
        with pytest.raises(HTTPException) as exc:
            await create_group(
                permission_id=permission.id,
                data=ConditionGroupCreateRequest(operator="AND", description="group"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(auth_instance.permission_service, "create_permission_condition_group", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await create_group(
                permission_id=permission.id,
                data=ConditionGroupCreateRequest(operator="AND", description="group"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        async def _return_none_group(*args, **kwargs):
            return None

        monkeypatch.setattr(auth_instance.permission_service, "update_permission_condition_group", _return_none_group)
        with pytest.raises(HTTPException) as exc:
            await update_group(
                permission_id=permission.id,
                group_id=uuid.uuid4(),
                data=ConditionGroupUpdateRequest(description="updated"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _return_false(*args, **kwargs):
            return False

        monkeypatch.setattr(auth_instance.permission_service, "delete_permission_condition_group", _return_false)
        with pytest.raises(HTTPException) as exc:
            await delete_group(
                permission_id=permission.id,
                group_id=uuid.uuid4(),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(auth_instance.permission_service, "create_permission_condition", _permission_missing)
        with pytest.raises(HTTPException) as exc:
            await create_condition(
                permission_id=permission.id,
                data=AbacConditionCreateRequest(
                    attribute="user.department",
                    operator="eq",
                    value="finance",
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(auth_instance.permission_service, "update_permission_condition", _return_none_group)
        with pytest.raises(HTTPException) as exc:
            await update_condition(
                permission_id=permission.id,
                condition_id=uuid.uuid4(),
                data=AbacConditionUpdateRequest(description="updated"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(auth_instance.permission_service, "delete_permission_condition", _return_false)
        with pytest.raises(HTTPException) as exc:
            await delete_condition(
                permission_id=permission.id,
                condition_id=uuid.uuid4(),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _create_group_success(*args, **kwargs):
            return SimpleNamespace(
                id=uuid.uuid4(),
                operator="OR",
                description="group created",
            )

        async def _create_condition_success(*args, **kwargs):
            return SimpleNamespace(
                id=uuid.uuid4(),
                attribute="user.department",
                operator="eq",
                value="finance",
                value_type="string",
                description="condition created",
                condition_group_id=None,
            )

        monkeypatch.setattr(auth_instance.permission_service, "create_permission_condition_group", _create_group_success)
        group = await create_group(
            permission_id=permission.id,
            data=ConditionGroupCreateRequest(operator="OR", description="group created"),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert group.permission_id == str(permission.id)
        assert group.operator == "OR"

        monkeypatch.setattr(auth_instance.permission_service, "create_permission_condition", _create_condition_success)
        condition = await create_condition(
            permission_id=permission.id,
            data=AbacConditionCreateRequest(
                attribute="user.department",
                operator="eq",
                value="finance",
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert condition.attribute == "user.department"
        assert condition.value == "finance"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permissions_router_callback_success_paths_cover_read_update_delete_and_abac_lists(
    auth_instance: SimpleRBAC,
    permissions_router,
    monkeypatch: pytest.MonkeyPatch,
):
    list_permissions = _endpoint(permissions_router, "/v1/permissions/", "GET")
    get_permission = _endpoint(permissions_router, "/v1/permissions/{permission_id}", "GET")
    update_permission = _endpoint(permissions_router, "/v1/permissions/{permission_id}", "PATCH")
    delete_permission = _endpoint(permissions_router, "/v1/permissions/{permission_id}", "DELETE")
    get_user_permissions = _endpoint(permissions_router, "/v1/permissions/user/{user_id}", "GET")
    list_groups = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/condition-groups",
        "GET",
    )
    update_group = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/condition-groups/{group_id}",
        "PATCH",
    )
    delete_group = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/condition-groups/{group_id}",
        "DELETE",
    )
    list_conditions = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/conditions",
        "GET",
    )
    create_condition = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/conditions",
        "POST",
    )
    update_condition = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/conditions/{condition_id}",
        "PATCH",
    )
    delete_condition = _endpoint(
        permissions_router,
        "/v1/permissions/{permission_id}/conditions/{condition_id}",
        "DELETE",
    )

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="perm-success")
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"success:{_suffix()}",
            display_name="Success Permission",
            tags=["ops"],
        )
        delete_target = await auth_instance.permission_service.create_permission(
            session,
            name=f"delete:{_suffix()}",
            display_name="Delete Permission",
        )

        listed = await list_permissions(
            page=1,
            limit=20,
            resource=None,
            session=session,
            obs=DummyObs(),
        )
        assert any(item.id == str(permission.id) for item in listed.items)

        fetched = await get_permission(
            permission_id=permission.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert fetched.id == str(permission.id)
        assert fetched.tags == ["ops"]

        updated = await update_permission(
            permission_id=permission.id,
            data=PermissionUpdateRequest(
                display_name="Updated Permission",
                description="updated via callback",
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert updated.display_name == "Updated Permission"
        assert any(
            event == "permission_updated" and fields["permission_id"] == str(permission.id)
            for event, fields in auth_instance.observability.records
        )

        deleted = await delete_permission(
            permission_id=delete_target.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert deleted is None
        assert any(
            event == "permission_deleted" and fields["permission_id"] == str(delete_target.id)
            for event, fields in auth_instance.observability.records
        )

        user_permissions = await get_user_permissions(
            user_id=actor.id,
            entity_id=None,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert isinstance(user_permissions, list)

        group = await auth_instance.permission_service.create_permission_condition_group(
            session,
            permission.id,
            operator="AND",
            description="group listed",
        )
        condition = await auth_instance.permission_service.create_permission_condition(
            session,
            permission.id,
            condition_group_id=group.id,
            attribute="user.department",
            operator="eq",
            value="finance",
            value_type="string",
            description="condition listed",
        )

        groups = await list_groups(
            permission_id=permission.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert groups[0].id == str(group.id)

        conditions = await list_conditions(
            permission_id=permission.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert conditions[0].id == str(condition.id)

        async def _invalid_input(*args, **kwargs):
            raise InvalidInputError(message="Bad request")

        monkeypatch.setattr(auth_instance.permission_service, "update_permission_condition_group", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await update_group(
                permission_id=permission.id,
                group_id=group.id,
                data=ConditionGroupUpdateRequest(description="nope"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        async def _group_success(*args, **kwargs):
            return SimpleNamespace(
                id=group.id,
                operator="OR",
                description="group updated",
                role_id=None,
                permission_id=permission.id,
            )

        monkeypatch.setattr(auth_instance.permission_service, "update_permission_condition_group", _group_success)
        updated_group = await update_group(
            permission_id=permission.id,
            group_id=group.id,
            data=ConditionGroupUpdateRequest(operator="OR", description="group updated"),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert updated_group.operator == "OR"

        async def _permission_missing(*args, **kwargs):
            raise PermissionNotFoundError(message="Permission missing")

        monkeypatch.setattr(auth_instance.permission_service, "delete_permission_condition_group", _permission_missing)
        with pytest.raises(HTTPException) as exc:
            await delete_group(
                permission_id=permission.id,
                group_id=group.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _delete_true(*args, **kwargs):
            return True

        monkeypatch.setattr(auth_instance.permission_service, "delete_permission_condition_group", _delete_true)
        assert (
            await delete_group(
                permission_id=permission.id,
                group_id=group.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
            is None
        )

        monkeypatch.setattr(auth_instance.permission_service, "create_permission_condition", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await create_condition(
                permission_id=permission.id,
                data=AbacConditionCreateRequest(
                    attribute="user.department",
                    operator="eq",
                    value="finance",
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        monkeypatch.setattr(auth_instance.permission_service, "update_permission_condition", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await update_condition(
                permission_id=permission.id,
                condition_id=condition.id,
                data=AbacConditionUpdateRequest(description="bad update"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        async def _condition_success(*args, **kwargs):
            return SimpleNamespace(
                id=condition.id,
                attribute="resource.region",
                operator="eq",
                value="latam",
                value_type="string",
                description="condition updated",
                condition_group_id=group.id,
            )

        monkeypatch.setattr(auth_instance.permission_service, "update_permission_condition", _condition_success)
        updated_condition = await update_condition(
            permission_id=permission.id,
            condition_id=condition.id,
            data=AbacConditionUpdateRequest(
                attribute="resource.region",
                operator="eq",
                value="latam",
                description="condition updated",
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert updated_condition.attribute == "resource.region"

        monkeypatch.setattr(auth_instance.permission_service, "delete_permission_condition", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await delete_condition(
                permission_id=permission.id,
                condition_id=condition.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        monkeypatch.setattr(auth_instance.permission_service, "delete_permission_condition", _delete_true)
        assert (
            await delete_condition(
                permission_id=permission.id,
                condition_id=condition.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
            is None
        )
