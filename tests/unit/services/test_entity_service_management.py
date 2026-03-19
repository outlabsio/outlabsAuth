from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import EntityNotFoundError, InvalidInputError
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.services.entity import EntityService


class FakeRedis:
    def __init__(self) -> None:
        self.is_available = True
        self.values: dict[str, object] = {}
        self.set_calls: list[tuple[str, object, int | None]] = []
        self.delete_calls: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.delete_pattern_calls: list[str] = []
        self.delete_pattern_result = 0
        self.delete_results: dict[str, bool] = {}

    def make_key(self, *parts: str) -> str:
        return ":".join(parts)

    def make_entity_path_key(self, entity_id: str) -> str:
        return f"entity:path:{entity_id}"

    def make_entity_descendants_key(self, entity_id: str) -> str:
        return f"entity:descendants:{entity_id}"

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value, ttl: int | None = None):
        self.values[key] = value
        self.set_calls.append((key, value, ttl))
        return True

    async def delete(self, key: str):
        self.delete_calls.append(key)
        return self.delete_results.get(key, True)

    async def publish(self, channel: str, message: str):
        self.published.append((channel, message))
        return True

    async def delete_pattern(self, pattern: str):
        self.delete_pattern_calls.append(pattern)
        return self.delete_pattern_result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_service_create_update_lookup_and_permission_invalidation(
    test_session,
    auth_config: AuthConfig,
):
    observability = SimpleNamespace(log_entity_operation=Mock())
    cache_service = SimpleNamespace(
        publish_entity_permissions_invalidation=AsyncMock(),
        publish_all_permissions_invalidation=AsyncMock(),
    )
    service = EntityService(config=auth_config, redis_client=None, observability=observability)
    service.cache_service = cache_service

    created = await service.create_entity(
        session=test_session,
        name="Root Branch!!",
        display_name="Root Branch",
        slug=None,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="Organization",
    )

    assert created.slug == "root-branch"
    assert created.name == "root branch!!".lower()
    assert created.entity_type == "organization"

    fetched = await service.get_entity_by_slug(test_session, "root-branch")
    assert fetched is not None
    assert fetched.id == created.id

    updated = await service.update_entity(
        test_session,
        created.id,
        display_name="Renamed Root",
        non_model_field="ignored",
    )
    assert updated.display_name == "Renamed Root"

    assert observability.log_entity_operation.call_count == 2
    assert [
        call.kwargs["operation"]
        for call in observability.log_entity_operation.call_args_list
    ] == ["create", "update"]

    assert cache_service.publish_entity_permissions_invalidation.await_count == 2
    assert cache_service.publish_all_permissions_invalidation.await_count == 2

    with pytest.raises(InvalidInputError, match="already exists"):
        await service.create_entity(
            session=test_session,
            name="Duplicate",
            display_name="Duplicate",
            slug="root-branch",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

    with pytest.raises(EntityNotFoundError, match="Parent entity not found"):
        await service.create_entity(
            session=test_session,
            name="Child",
            display_name="Child",
            slug="child",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=uuid4(),
        )

    with pytest.raises(EntityNotFoundError, match="Entity not found"):
        await service.get_entity(test_session, uuid4())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_service_move_and_delete_management_paths(
    test_session,
    auth_config: AuthConfig,
):
    observability = SimpleNamespace(log_entity_operation=Mock())
    cache_service = SimpleNamespace(
        publish_entity_permissions_invalidation=AsyncMock(),
        publish_all_permissions_invalidation=AsyncMock(),
    )
    membership_service = SimpleNamespace(archive_memberships_for_entity=AsyncMock())
    role_service = SimpleNamespace(revoke_memberships_for_archived_entities=AsyncMock())

    service = EntityService(config=auth_config, redis_client=None, observability=observability)
    service.cache_service = cache_service
    service.membership_service = membership_service
    service.role_service = role_service

    root = await service.create_entity(
        session=test_session,
        name="root",
        display_name="Root",
        slug="root",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    child = await service.create_entity(
        session=test_session,
        name="child",
        display_name="Child",
        slug="child",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=root.id,
    )
    grandchild = await service.create_entity(
        session=test_session,
        name="grandchild",
        display_name="Grandchild",
        slug="grandchild",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=child.id,
    )

    unchanged = await service.move_entity(test_session, entity_id=child.id, new_parent_id=root.id)
    assert unchanged.id == child.id

    with pytest.raises(InvalidInputError, match="own parent"):
        await service.move_entity(test_session, entity_id=child.id, new_parent_id=child.id)

    with pytest.raises(EntityNotFoundError, match="Parent entity not found"):
        await service.move_entity(test_session, entity_id=child.id, new_parent_id=uuid4())

    with pytest.raises(InvalidInputError, match="Cannot delete entity with children"):
        await service.delete_entity(test_session, root.id)

    deleted_by_id = uuid4()
    assert await service.delete_entity(
        test_session,
        root.id,
        cascade=True,
        deleted_by_id=deleted_by_id,
    )

    root_fresh = await service.get_entity(test_session, root.id)
    child_fresh = await service.get_entity(test_session, child.id)
    grandchild_fresh = await service.get_entity(test_session, grandchild.id)
    assert root_fresh.status == "archived"
    assert child_fresh.status == "archived"
    assert grandchild_fresh.status == "archived"

    assert membership_service.archive_memberships_for_entity.await_count == 3
    assert role_service.revoke_memberships_for_archived_entities.await_count == 3
    archived_entity_ids = {
        call.args[1] for call in membership_service.archive_memberships_for_entity.await_args_list
    }
    assert archived_entity_ids == {root.id, child.id, grandchild.id}
    assert observability.log_entity_operation.call_args_list[-1].kwargs["operation"] == "delete"
    assert cache_service.publish_entity_permissions_invalidation.await_count >= 4
    assert cache_service.publish_all_permissions_invalidation.await_count >= 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_service_path_descendants_suggestions_and_cache_invalidation(
    test_session,
    auth_config: AuthConfig,
):
    fake_redis = FakeRedis()
    service = EntityService(config=auth_config, redis_client=fake_redis)

    root = await service.create_entity(
        session=test_session,
        name="root",
        display_name="Root",
        slug="root",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    dept_a = await service.create_entity(
        session=test_session,
        name="dept-a",
        display_name="Department A",
        slug="dept-a",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=root.id,
    )
    dept_b = await service.create_entity(
        session=test_session,
        name="dept-b",
        display_name="Department B",
        slug="dept-b",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=root.id,
    )
    team = await service.create_entity(
        session=test_session,
        name="team",
        display_name="Team",
        slug="team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=dept_a.id,
    )
    project = await service.create_entity(
        session=test_session,
        name="project",
        display_name="Project",
        slug="project",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="project",
        parent_id=team.id,
    )

    path = await service.get_entity_path(test_session, project.id)
    assert [entity.id for entity in path] == [root.id, dept_a.id, team.id, project.id]

    cached_path = await service.get_entity_path(test_session, project.id)
    assert [entity.id for entity in cached_path] == [root.id, dept_a.id, team.id, project.id]

    descendants = await service.get_descendants(test_session, root.id)
    assert {entity.id for entity in descendants} == {dept_a.id, dept_b.id, team.id, project.id}

    cached_descendants = await service.get_descendants(test_session, root.id)
    assert {entity.id for entity in cached_descendants} == {dept_a.id, dept_b.id, team.id, project.id}

    team_only = await service.get_descendants(test_session, root.id, entity_type="team")
    assert [entity.id for entity in team_only] == [team.id]

    suggestions = await service.get_suggested_entity_types(
        test_session,
        parent_id=root.id,
        entity_class=EntityClass.STRUCTURAL,
    )
    assert suggestions["total_children"] == 2
    assert suggestions["parent_entity"]["id"] == str(root.id)
    assert suggestions["suggestions"][0]["entity_type"] == "department"
    assert suggestions["suggestions"][0]["count"] == 2
    assert suggestions["suggestions"][0]["examples"] == ["Department A", "Department B"]

    ancestors = await service.get_ancestors(test_session, project.id, include_self=True)
    assert [entity.id for entity in ancestors] == [project.id, team.id, dept_a.id, root.id]

    path_key = fake_redis.make_entity_path_key(str(project.id))
    descendants_key = fake_redis.make_entity_descendants_key(str(root.id))
    assert any(call[0] == path_key for call in fake_redis.set_calls)
    assert any(call[0] == descendants_key for call in fake_redis.set_calls)

    deleted = await service.invalidate_entity_cache(project.id)
    assert deleted == 2
    assert fake_redis.published[-1] == (
        auth_config.redis_invalidation_channel,
        f"entity:{project.id}:hierarchy",
    )

    tree_deleted = await service.invalidate_entity_tree_cache(test_session, dept_a.id)
    assert tree_deleted > 0

    fake_redis.delete_pattern_result = 4
    deleted_all = await service.invalidate_all_entity_cache()
    assert deleted_all == 4
    assert fake_redis.delete_pattern_calls == ["auth:entity:*"]
    assert fake_redis.published[-1] == (auth_config.redis_invalidation_channel, "all:entities")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_service_hierarchy_validation_helpers(
    test_session,
    auth_config: AuthConfig,
):
    service = EntityService(config=auth_config, redis_client=None)

    root = await service.create_entity(
        session=test_session,
        name="root",
        display_name="Root",
        slug="root-validation",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
        allowed_child_types=["department"],
    )
    dept = await service.create_entity(
        session=test_session,
        name="dept",
        display_name="Dept",
        slug="dept-validation",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=root.id,
    )
    access_group = await service.create_entity(
        session=test_session,
        name="access-group",
        display_name="Access Group",
        slug="access-group-validation",
        entity_class=EntityClass.ACCESS_GROUP,
        entity_type="group",
    )

    with pytest.raises(InvalidInputError, match="not allowed as child"):
        await service.create_entity(
            session=test_session,
            name="team",
            display_name="Team",
            slug="team-validation",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=dept.id,
        )

    with pytest.raises(InvalidInputError, match="Access groups cannot have structural entities"):
        await service.create_entity(
            session=test_session,
            name="member-team",
            display_name="Member Team",
            slug="member-team-validation",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=access_group.id,
        )

    limited_config = auth_config.model_copy(update={"max_entity_depth": 1})
    limited_service = EntityService(config=limited_config, redis_client=None)
    limited_root = await limited_service.create_entity(
        session=test_session,
        name="limited-root",
        display_name="Limited Root",
        slug="limited-root",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )

    with pytest.raises(InvalidInputError, match="Maximum hierarchy depth"):
        await limited_service.create_entity(
            session=test_session,
            name="too-deep",
            display_name="Too Deep",
            slug="too-deep",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=limited_root.id,
        )

    allowed_types = await service._get_allowed_child_types(test_session, dept, EntityClass.STRUCTURAL)
    assert allowed_types == ["department"]
    assert await service._get_root_entity(test_session, root) == root
