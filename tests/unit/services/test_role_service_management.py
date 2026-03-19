import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import DefinitionStatus, EntityClass, RoleScope
from outlabs_auth.services.role import RoleService


def _entity(*, name: str, slug: str, parent_id=None, depth: int = 0, entity_type: str = "organization", path: str | None = None) -> Entity:
    return Entity(
        name=name,
        display_name=name.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type=entity_type,
        parent_id=parent_id,
        depth=depth,
        path=path or f"/{slug}/",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_service_scope_listing_and_entity_availability(
    test_session,
    auth_config: AuthConfig,
):
    service = RoleService(config=auth_config)

    root = _entity(name="root", slug="root")
    team = _entity(
        name="team",
        slug="team",
        parent_id=root.id,
        depth=1,
        entity_type="team",
        path="/root/team/",
    )
    other_root = _entity(name="other", slug="other")
    test_session.add_all([root, team, other_root])
    await test_session.flush()
    test_session.add_all(
        [
            EntityClosure(ancestor_id=root.id, descendant_id=root.id, depth=0),
            EntityClosure(ancestor_id=team.id, descendant_id=team.id, depth=0),
            EntityClosure(ancestor_id=other_root.id, descendant_id=other_root.id, depth=0),
            EntityClosure(ancestor_id=root.id, descendant_id=team.id, depth=1),
        ]
    )
    await test_session.flush()

    system_role = await service.create_role(
        test_session,
        name="system_admin",
        display_name="System Admin",
        is_global=True,
    )
    org_role = await service.create_role(
        test_session,
        name="org_admin",
        display_name="Org Admin",
        is_global=False,
        root_entity_id=root.id,
    )
    hierarchy_role = await service.create_role(
        test_session,
        name="team_manager",
        display_name="Team Manager",
        is_global=False,
        root_entity_id=root.id,
        scope_entity_id=root.id,
        scope=RoleScope.HIERARCHY,
        assignable_at_types=["team"],
    )
    entity_only_role = await service.create_role(
        test_session,
        name="team_local",
        display_name="Team Local",
        is_global=False,
        root_entity_id=root.id,
        scope_entity_id=team.id,
        scope=RoleScope.ENTITY_ONLY,
        is_auto_assigned=True,
        assignable_at_types=["team"],
    )
    archived_role = await service.create_role(
        test_session,
        name="archived_role",
        display_name="Archived Role",
        is_global=False,
        root_entity_id=root.id,
        status=DefinitionStatus.INACTIVE,
    )
    await service.delete_role(test_session, archived_role.id)

    scoped_roles, scoped_total = await service.list_roles(
        test_session,
        page=1,
        limit=20,
        manageable_root_entity_ids=[root.id],
        manageable_entity_ids=[root.id, team.id],
        include_system_global=False,
    )
    assert scoped_total == 3
    assert {role.name for role in scoped_roles} == {"org_admin", "team_local", "team_manager"}

    global_roles, global_total = await service.list_roles(
        test_session,
        page=1,
        limit=20,
        manageable_root_entity_ids=None,
        manageable_entity_ids=None,
        include_system_global=True,
    )
    assert global_total == 4
    assert {role.name for role in global_roles} == {
        "org_admin",
        "system_admin",
        "team_local",
        "team_manager",
    }

    available, total_available = await service.get_roles_for_entity(
        test_session,
        entity_id=team.id,
        page=1,
        limit=20,
    )
    assert total_available == 4
    assert {role.name for role in available} == {
        "org_admin",
        "system_admin",
        "team_local",
        "team_manager",
    }

    auto_roles = await service.get_auto_assigned_roles_for_entity(test_session, team.id)
    assert [role.name for role in auto_roles] == ["team_local"]

    assert await service.is_role_available_for_entity(test_session, system_role, team.id) is True
    assert await service.is_role_available_for_entity(test_session, org_role, team.id) is True
    assert await service.is_role_available_for_entity(test_session, hierarchy_role, team.id) is True
    assert await service.is_role_available_for_entity(test_session, entity_only_role, team.id) is True
    assert await service.is_role_available_for_entity(test_session, entity_only_role, root.id) is False
    assert await service.is_role_available_for_entity(test_session, archived_role, team.id) is False
