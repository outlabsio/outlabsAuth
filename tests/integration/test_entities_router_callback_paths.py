import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import HTTPException

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_entities_router
from outlabs_auth.schemas.entity import EntityCreateRequest, EntityMoveRequest, EntityUpdateRequest


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
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
async def entities_router(auth_instance: EnterpriseRBAC):
    return get_entities_router(auth_instance, prefix="/v1/entities")


async def _create_user(auth: EnterpriseRBAC, session, *, email_prefix: str):
    return await auth.user_service.create_user(
        session=session,
        email=f"{email_prefix}-{_suffix()}@example.com",
        password="TestPass123!",
        first_name="Entity",
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
async def test_entities_router_callback_list_and_crud_paths(
    auth_instance: EnterpriseRBAC,
    entities_router,
    monkeypatch: pytest.MonkeyPatch,
):
    list_entities = _endpoint(entities_router, "/v1/entities/", "GET")
    create_entity = _endpoint(entities_router, "/v1/entities/", "POST")
    get_entity_type_suggestions = _endpoint(
        entities_router,
        "/v1/entities/type-suggestions",
        "GET",
    )
    get_entity = _endpoint(entities_router, "/v1/entities/{entity_id}", "GET")
    update_entity = _endpoint(entities_router, "/v1/entities/{entity_id}", "PATCH")
    delete_entity = _endpoint(entities_router, "/v1/entities/{entity_id}", "DELETE")
    get_children = _endpoint(entities_router, "/v1/entities/{entity_id}/children", "GET")
    get_path = _endpoint(entities_router, "/v1/entities/{entity_id}/path", "GET")

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="entity-router")
        root = await _create_root(auth_instance, session, label="root")
        dept = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"dept-{_suffix()}",
            display_name="Department Alpha",
            slug=f"dept-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        await auth_instance.entity_service.create_entity(
            session=session,
            name=f"team-{_suffix()}",
            display_name="Team Beta",
            slug=f"team-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
            status="archived",
        )

        created = await create_entity(
            data=EntityCreateRequest(
                name=f"project-{_suffix()}",
                display_name="Project Gamma",
                slug=f"project-{_suffix()}",
                description="created via callback",
                entity_class="structural",
                entity_type="project",
                parent_entity_id=str(dept.id),
            ),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert created.parent_entity_id == str(dept.id)
        assert created.entity_class == "structural"

        listed = await list_entities(
            search="Department",
            entity_class="structural",
            entity_type="department",
            parent_id=root.id,
            root_only=False,
            page=1,
            limit=10,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert listed.total == 1
        assert [item.id for item in listed.items] == [str(dept.id)]

        roots = await list_entities(
            search=None,
            entity_class=None,
            entity_type=None,
            parent_id=None,
            root_only=True,
            page=1,
            limit=10,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert roots.total == 1
        assert [item.id for item in roots.items] == [str(root.id)]

        invalid_class = await list_entities(
            search=None,
            entity_class="legacy-scope",
            entity_type=None,
            parent_id=None,
            root_only=False,
            page=1,
            limit=10,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert invalid_class.total == 0
        assert invalid_class.pages == 0

        suggestions = await get_entity_type_suggestions(
            parent_id=root.id,
            entity_class="structural",
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert suggestions.total_children == 1
        assert suggestions.parent_entity.id == str(root.id)
        assert suggestions.suggestions[0].entity_type == "department"

        fetched = await get_entity(
            entity_id=dept.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert fetched.id == str(dept.id)

        updated = await update_entity(
            entity_id=dept.id,
            data=EntityUpdateRequest(display_name="Department Renamed", description="updated"),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert updated.display_name == "Department Renamed"
        assert updated.description == "updated"

        children = await get_children(
            entity_id=root.id,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert {child.id for child in children} == {str(dept.id)}

        path = await get_path(
            entity_id=uuid.UUID(created.id),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert [entity.id for entity in path] == [str(root.id), str(dept.id), created.id]

        async def _missing_entity(*args, **kwargs):
            return None

        monkeypatch.setattr(auth_instance.entity_service, "get_entity", _missing_entity)
        with pytest.raises(HTTPException) as exc:
            await get_entity(
                entity_id=uuid.uuid4(),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 404

        delete_spy = AsyncMock(return_value=True)
        monkeypatch.setattr(auth_instance.entity_service, "delete_entity", delete_spy)
        response = await delete_entity(
            entity_id=dept.id,
            cascade=True,
            session=session,
            auth_result={},
        )
        assert response is None
        assert delete_spy.await_args.kwargs["deleted_by_id"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_entities_router_callback_move_descendants_and_members_paths(
    auth_instance: EnterpriseRBAC,
    entities_router,
    monkeypatch: pytest.MonkeyPatch,
):
    move_entity = _endpoint(entities_router, "/v1/entities/{entity_id}/move", "POST")
    get_descendants = _endpoint(entities_router, "/v1/entities/{entity_id}/descendants", "GET")
    get_entity_members = _endpoint(entities_router, "/v1/entities/{entity_id}/members", "GET")

    async with auth_instance.get_session() as session:
        actor = await _create_user(auth_instance, session, email_prefix="entity-move")
        root = await _create_root(auth_instance, session, label="move-root")
        current_parent = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"current-{_suffix()}",
            display_name="Current Parent",
            slug=f"current-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        new_parent = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"new-{_suffix()}",
            display_name="New Parent",
            slug=f"new-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=root.id,
        )
        node = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"node-{_suffix()}",
            display_name="Movable Node",
            slug=f"node-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=current_parent.id,
        )

        moved_to_root = await move_entity(
            entity_id=node.id,
            data=EntityMoveRequest(new_parent_id=None),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert moved_to_root.parent_entity_id is None

        async def _deny_create_under_parent(*args, **kwargs):
            return False

        monkeypatch.setattr(
            auth_instance.permission_service,
            "check_permission",
            _deny_create_under_parent,
        )
        with pytest.raises(HTTPException) as exc:
            await move_entity(
                entity_id=node.id,
                data=EntityMoveRequest(new_parent_id=str(new_parent.id)),
                session=session,
                auth_result={"user_id": str(actor.id)},
            )
        assert exc.value.status_code == 403

        async def _allow_create_under_parent(*args, **kwargs):
            return True

        monkeypatch.setattr(
            auth_instance.permission_service,
            "check_permission",
            _allow_create_under_parent,
        )
        moved_to_parent = await move_entity(
            entity_id=node.id,
            data=EntityMoveRequest(new_parent_id=str(new_parent.id)),
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert moved_to_parent.parent_entity_id == str(new_parent.id)

        descendants = await get_descendants(
            entity_id=root.id,
            entity_type="team",
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert [entity.id for entity in descendants] == [str(node.id)]

        member_user = SimpleNamespace(
            id=uuid.uuid4(),
            email="member@example.com",
            first_name="Member",
            last_name="User",
        )
        role = SimpleNamespace(id=uuid.uuid4(), name="entity_reader")
        memberships = [
            SimpleNamespace(user_id=member_user.id, roles=[role]),
            SimpleNamespace(user_id=uuid.uuid4(), roles=[]),
        ]
        monkeypatch.setattr(
            auth_instance.membership_service,
            "get_entity_members",
            AsyncMock(return_value=(memberships, 2)),
        )
        monkeypatch.setattr(session, "get", AsyncMock(side_effect=[member_user, None]))

        paginated_members = await get_entity_members(
            entity_id=root.id,
            page=1,
            limit=2,
            session=session,
            auth_result={"user_id": str(actor.id)},
        )
        assert paginated_members.total == 2
        assert paginated_members.pages == 1
        assert len(paginated_members.items) == 1
        assert paginated_members.items[0].email == "member@example.com"
        assert paginated_members.items[0].role_names == ["entity_reader"]
