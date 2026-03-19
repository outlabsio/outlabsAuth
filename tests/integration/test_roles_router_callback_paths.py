import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import HTTPException

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.core.exceptions import InvalidInputError, RoleNotFoundError
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_roles_router
from outlabs_auth.schemas.abac import (
    AbacConditionCreateRequest,
    AbacConditionUpdateRequest,
    ConditionGroupCreateRequest,
    ConditionGroupUpdateRequest,
)
from outlabs_auth.schemas.role import RoleCreateRequest, RoleUpdateRequest


class DummyObs:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str, dict]] = []

    def log_500_error(self, exception: Exception, **extra) -> None:
        self.errors.append((type(exception).__name__, str(exception), extra))


class DummyObservability:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []
        self.logger = SimpleNamespace(info=self._record, error=self._record)

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
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
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
async def roles_router(auth_instance: EnterpriseRBAC):
    return get_roles_router(auth_instance, prefix="/v1/roles")


async def _create_user(auth: EnterpriseRBAC, session, *, email_prefix: str):
    return await auth.user_service.create_user(
        session=session,
        email=f"{email_prefix}-{_suffix()}@example.com",
        password="TestPass123!",
        first_name="Role",
        last_name="Actor",
    )


async def _create_root(auth: EnterpriseRBAC, session, *, label: str):
    suffix = _suffix()
    return await auth.entity_service.create_entity(
        session=session,
        name=f"{label}-{suffix}",
        display_name=label.title(),
        slug=f"{label}-{suffix}",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_router_callback_scope_and_crud_paths(
    auth_instance: EnterpriseRBAC,
    roles_router,
    monkeypatch: pytest.MonkeyPatch,
):
    list_roles = _endpoint(roles_router, "/v1/roles/", "GET")
    create_role = _endpoint(roles_router, "/v1/roles/", "POST")
    get_role = _endpoint(roles_router, "/v1/roles/{role_id}", "GET")
    delete_role = _endpoint(roles_router, "/v1/roles/{role_id}", "DELETE")

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="role-actor")
        root = await _create_root(auth_instance, session, label="root-scope")
        system_role = await auth_instance.role_service.create_role(
            session,
            name=f"system-role-{_suffix()}",
            display_name="System Role",
            is_global=True,
        )

        async def _scoped_scope(*args, **kwargs):
            return {
                "is_global": False,
                "entity_ids": [str(root.id)],
                "root_entity_ids": [str(root.id)],
            }

        monkeypatch.setattr(auth_instance.access_scope_service, "resolve_for_auth_result", _scoped_scope)

        with pytest.raises(HTTPException) as exc:
            await create_role(
                data=RoleCreateRequest(
                    name=f"scoped-create-{_suffix()}",
                    display_name="Scoped Create",
                    is_global=True,
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 403
        assert "Only superusers" in exc.value.detail

        created = await create_role(
            data=RoleCreateRequest(
                name=f"org-role-{_suffix()}",
                display_name="Org Role",
                is_global=False,
                root_entity_id=str(root.id),
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert created.root_entity_id == str(root.id)
        assert created.is_global is False

        with pytest.raises(HTTPException) as exc:
            await get_role(
                role_id=system_role.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 403
        assert exc.value.detail == "Only superusers can access system-wide roles"

        async def _return_false(*args, **kwargs):
            return False

        monkeypatch.setattr(auth_instance.role_service, "delete_role", _return_false)
        with pytest.raises(HTTPException) as exc:
            await delete_role(
                role_id=uuid.UUID(created.id),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _global_scope(*args, **kwargs):
            return {"is_global": True, "entity_ids": [], "root_entity_ids": []}

        monkeypatch.setattr(auth_instance.access_scope_service, "resolve_for_auth_result", _global_scope)
        monkeypatch.setattr(auth_instance.role_service, "list_roles", _runtime_raiser("role list exploded"))
        obs = DummyObs()
        with pytest.raises(RuntimeError, match="role list exploded"):
            await list_roles(
                page=1,
                limit=20,
                search=None,
                is_global=None,
                root_entity_id=None,
                session=session,
                auth_result={"user_id": str(actor.id)},
                obs=obs,
            )
        assert obs.errors == [
            ("RuntimeError", "role list exploded", {"page": 1, "limit": 20, "search": None, "is_global": None})
        ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_router_callback_permission_and_abac_paths(
    auth_instance: EnterpriseRBAC,
    roles_router,
    monkeypatch: pytest.MonkeyPatch,
):
    add_permissions = _endpoint(roles_router, "/v1/roles/{role_id}/permissions", "POST")
    remove_permissions = _endpoint(roles_router, "/v1/roles/{role_id}/permissions", "DELETE")
    create_group = _endpoint(roles_router, "/v1/roles/{role_id}/condition-groups", "POST")
    update_group = _endpoint(roles_router, "/v1/roles/{role_id}/condition-groups/{group_id}", "PATCH")
    delete_group = _endpoint(roles_router, "/v1/roles/{role_id}/condition-groups/{group_id}", "DELETE")
    create_condition = _endpoint(roles_router, "/v1/roles/{role_id}/conditions", "POST")
    update_condition = _endpoint(roles_router, "/v1/roles/{role_id}/conditions/{condition_id}", "PATCH")
    delete_condition = _endpoint(roles_router, "/v1/roles/{role_id}/conditions/{condition_id}", "DELETE")

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="role-abac")
        root = await _create_root(auth_instance, session, label="root-abac")
        role = await auth_instance.role_service.create_role(
            session,
            name=f"root-role-{_suffix()}",
            display_name="Root Role",
            is_global=False,
            root_entity_id=root.id,
        )
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"roleperm:{_suffix()}",
            display_name="Role Permission",
        )

        async def _scoped_scope(*args, **kwargs):
            return {
                "is_global": False,
                "entity_ids": [],
                "root_entity_ids": [str(root.id)],
            }

        monkeypatch.setattr(auth_instance.access_scope_service, "resolve_for_auth_result", _scoped_scope)

        added = await add_permissions(
            role_id=role.id,
            permissions=[permission.name],
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert permission.name in added.permissions

        removed = await remove_permissions(
            role_id=role.id,
            permissions=[permission.name],
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert permission.name not in removed.permissions

        async def _invalid_group(*args, **kwargs):
            raise InvalidInputError(message="Invalid role group")

        monkeypatch.setattr(auth_instance.role_service, "create_role_condition_group", _invalid_group)
        with pytest.raises(HTTPException) as exc:
            await create_group(
                role_id=role.id,
                data=ConditionGroupCreateRequest(operator="AND", description="group"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        async def _return_none(*args, **kwargs):
            return None

        monkeypatch.setattr(auth_instance.role_service, "update_role_condition_group", _return_none)
        with pytest.raises(HTTPException) as exc:
            await update_group(
                role_id=role.id,
                group_id=uuid.uuid4(),
                data=ConditionGroupUpdateRequest(description="updated"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _return_false(*args, **kwargs):
            return False

        monkeypatch.setattr(auth_instance.role_service, "delete_role_condition_group", _return_false)
        with pytest.raises(HTTPException) as exc:
            await delete_group(
                role_id=role.id,
                group_id=uuid.uuid4(),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        async def _missing_role(*args, **kwargs):
            raise RoleNotFoundError(message="Role missing")

        monkeypatch.setattr(auth_instance.role_service, "create_role_condition", _missing_role)
        with pytest.raises(HTTPException) as exc:
            await create_condition(
                role_id=role.id,
                data=AbacConditionCreateRequest(
                    attribute="resource.environment",
                    operator="eq",
                    value="prod",
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(auth_instance.role_service, "update_role_condition", _return_none)
        with pytest.raises(HTTPException) as exc:
            await update_condition(
                role_id=role.id,
                condition_id=uuid.uuid4(),
                data=AbacConditionUpdateRequest(description="updated"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        monkeypatch.setattr(auth_instance.role_service, "delete_role_condition", _return_false)
        with pytest.raises(HTTPException) as exc:
            await delete_condition(
                role_id=role.id,
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
                attribute="resource.environment",
                operator="eq",
                value="prod",
                value_type="string",
                description="condition created",
                condition_group_id=None,
            )

        monkeypatch.setattr(auth_instance.role_service, "create_role_condition_group", _create_group_success)
        group = await create_group(
            role_id=role.id,
            data=ConditionGroupCreateRequest(operator="OR", description="group created"),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert group.role_id == str(role.id)
        assert group.operator == "OR"

        monkeypatch.setattr(auth_instance.role_service, "create_role_condition", _create_condition_success)
        condition = await create_condition(
            role_id=role.id,
            data=AbacConditionCreateRequest(
                attribute="resource.environment",
                operator="eq",
                value="prod",
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert condition.attribute == "resource.environment"
        assert condition.value == "prod"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_roles_router_callback_success_paths_cover_list_read_update_delete_and_abac_lists(
    auth_instance: EnterpriseRBAC,
    roles_router,
    monkeypatch: pytest.MonkeyPatch,
):
    list_roles = _endpoint(roles_router, "/v1/roles/", "GET")
    list_roles_for_entity = _endpoint(roles_router, "/v1/roles/entity/{entity_id}", "GET")
    create_role = _endpoint(roles_router, "/v1/roles/", "POST")
    get_role = _endpoint(roles_router, "/v1/roles/{role_id}", "GET")
    update_role = _endpoint(roles_router, "/v1/roles/{role_id}", "PATCH")
    delete_role = _endpoint(roles_router, "/v1/roles/{role_id}", "DELETE")
    list_groups = _endpoint(roles_router, "/v1/roles/{role_id}/condition-groups", "GET")
    update_group = _endpoint(
        roles_router,
        "/v1/roles/{role_id}/condition-groups/{group_id}",
        "PATCH",
    )
    delete_group = _endpoint(
        roles_router,
        "/v1/roles/{role_id}/condition-groups/{group_id}",
        "DELETE",
    )
    list_conditions = _endpoint(roles_router, "/v1/roles/{role_id}/conditions", "GET")
    create_condition = _endpoint(roles_router, "/v1/roles/{role_id}/conditions", "POST")
    update_condition = _endpoint(
        roles_router,
        "/v1/roles/{role_id}/conditions/{condition_id}",
        "PATCH",
    )
    delete_condition = _endpoint(
        roles_router,
        "/v1/roles/{role_id}/conditions/{condition_id}",
        "DELETE",
    )

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="role-success")
        root = await _create_root(auth_instance, session, label="role-success-root")
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"team-success-{_suffix()}",
            display_name="Team Success",
            slug=f"team-success-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"successperm:{_suffix()}",
            display_name="Success Permission",
        )
        role = await auth_instance.role_service.create_role(
            session,
            name=f"success-role-{_suffix()}",
            display_name="Success Role",
            is_global=False,
            scope_entity_id=team.id,
            permission_names=[permission.name],
        )
        delete_target = await auth_instance.role_service.create_role(
            session,
            name=f"delete-role-{_suffix()}",
            display_name="Delete Role",
            is_global=False,
            root_entity_id=root.id,
        )

        async def _scoped_scope(*args, **kwargs):
            return {
                "is_global": False,
                "entity_ids": [str(team.id)],
                "root_entity_ids": [str(root.id)],
            }

        monkeypatch.setattr(auth_instance.access_scope_service, "resolve_for_auth_result", _scoped_scope)

        listed = await list_roles(
            page=1,
            limit=20,
            search=None,
            is_global=None,
            root_entity_id=None,
            session=session,
            auth_result={"user_id": str(actor.id)},
            obs=DummyObs(),
        )
        assert any(item.id == str(role.id) for item in listed.items)

        listed_for_entity = await list_roles_for_entity(
            entity_id=team.id,
            page=1,
            limit=20,
            session=session,
            auth_result={"user_id": str(actor.id)},
            obs=DummyObs(),
        )
        assert any(item.id == str(role.id) for item in listed_for_entity.items)

        monkeypatch.setattr(auth_instance.role_service, "get_roles_for_entity", _runtime_raiser("entity roles exploded"))
        obs = DummyObs()
        with pytest.raises(RuntimeError, match="entity roles exploded"):
            await list_roles_for_entity(
                entity_id=team.id,
                page=1,
                limit=20,
                session=session,
                auth_result={"user_id": str(actor.id)},
                obs=obs,
            )
        assert obs.errors == [
            ("RuntimeError", "entity roles exploded", {"entity_id": str(team.id), "page": 1, "limit": 20})
        ]

        monkeypatch.setattr(auth_instance.access_scope_service, "resolve_for_auth_result", _scoped_scope)
        fetched = await get_role(
            role_id=role.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert fetched.id == str(role.id)

        create_out_of_scope_root = await _create_root(auth_instance, session, label="role-out-of-scope")
        with pytest.raises(HTTPException) as exc:
            await create_role(
                data=RoleCreateRequest(
                    name=f"bad-root-{_suffix()}",
                    display_name="Bad Root",
                    is_global=False,
                    root_entity_id=str(create_out_of_scope_root.id),
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 403
        assert "organization scope" in exc.value.detail

        other_team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"other-team-{_suffix()}",
            display_name="Other Team",
            slug=f"other-team-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=create_out_of_scope_root.id,
        )
        with pytest.raises(HTTPException) as exc:
            await create_role(
                data=RoleCreateRequest(
                    name=f"bad-entity-{_suffix()}",
                    display_name="Bad Entity",
                    is_global=False,
                    scope_entity_id=str(other_team.id),
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 403
        assert "entity scope" in exc.value.detail

        apply_auto_assigned_role = AsyncMock()
        monkeypatch.setattr(auth_instance.membership_service, "apply_auto_assigned_role", apply_auto_assigned_role)
        updated = await update_role(
            role_id=role.id,
            data=RoleUpdateRequest(
                display_name="Updated Role",
                description="updated",
                is_auto_assigned=True,
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert updated.display_name == "Updated Role"
        apply_auto_assigned_role.assert_awaited_once_with(session, role.id)

        deleted = await delete_role(
            role_id=delete_target.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert deleted is None

        group = await auth_instance.role_service.create_role_condition_group(
            session,
            role.id,
            operator="AND",
            description="group listed",
        )
        condition = await auth_instance.role_service.create_role_condition(
            session,
            role.id,
            condition_group_id=group.id,
            attribute="resource.environment",
            operator="eq",
            value="prod",
            value_type="string",
            description="condition listed",
        )

        groups = await list_groups(
            role_id=role.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert groups[0].id == str(group.id)

        conditions = await list_conditions(
            role_id=role.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert conditions[0].id == str(condition.id)

        async def _invalid_input(*args, **kwargs):
            raise InvalidInputError(message="Bad role request")

        monkeypatch.setattr(auth_instance.role_service, "create_role_condition_group", _runtime_raiser("unused"))
        monkeypatch.setattr(auth_instance.role_service, "update_role_condition_group", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await update_group(
                role_id=role.id,
                group_id=group.id,
                data=ConditionGroupUpdateRequest(description="bad"),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        async def _group_success(*args, **kwargs):
            return SimpleNamespace(
                id=group.id,
                operator="OR",
                description="group updated",
                role_id=role.id,
                permission_id=None,
            )

        monkeypatch.setattr(auth_instance.role_service, "update_role_condition_group", _group_success)
        updated_group = await update_group(
            role_id=role.id,
            group_id=group.id,
            data=ConditionGroupUpdateRequest(operator="OR", description="group updated"),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert updated_group.operator == "OR"

        monkeypatch.setattr(auth_instance.role_service, "delete_role_condition_group", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await delete_group(
                role_id=role.id,
                group_id=group.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        async def _return_true(*args, **kwargs):
            return True

        monkeypatch.setattr(auth_instance.role_service, "delete_role_condition_group", _return_true)
        assert (
            await delete_group(
                role_id=role.id,
                group_id=group.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
            is None
        )

        monkeypatch.setattr(auth_instance.role_service, "create_role_condition", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await create_condition(
                role_id=role.id,
                data=AbacConditionCreateRequest(
                    attribute="resource.environment",
                    operator="eq",
                    value="prod",
                ),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        monkeypatch.setattr(auth_instance.role_service, "update_role_condition", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await update_condition(
                role_id=role.id,
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

        monkeypatch.setattr(auth_instance.role_service, "update_role_condition", _condition_success)
        updated_condition = await update_condition(
            role_id=role.id,
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

        monkeypatch.setattr(auth_instance.role_service, "delete_role_condition", _invalid_input)
        with pytest.raises(HTTPException) as exc:
            await delete_condition(
                role_id=role.id,
                condition_id=condition.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 400

        monkeypatch.setattr(auth_instance.role_service, "delete_role_condition", _return_true)
        assert (
            await delete_condition(
                role_id=role.id,
                condition_id=condition.id,
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
            is None
        )
