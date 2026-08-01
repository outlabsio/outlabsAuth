import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import EntityClass, RoleScope
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.role import RoleService
from outlabs_auth.services.user import UserService


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
async def test_membership_service_queries_and_orphan_discovery(
    test_session,
    auth_config: AuthConfig,
):
    membership_service = MembershipService(config=auth_config)
    user_service = UserService(config=auth_config)

    root = _entity(name="root", slug="root")
    team = _entity(
        name="team",
        slug="team",
        parent_id=root.id,
        depth=1,
        entity_type="team",
        path="/root/team/",
    )
    test_session.add_all([root, team])
    await test_session.flush()
    test_session.add_all(
        [
            EntityClosure(ancestor_id=root.id, descendant_id=root.id, depth=0),
            EntityClosure(ancestor_id=team.id, descendant_id=team.id, depth=0),
            EntityClosure(ancestor_id=root.id, descendant_id=team.id, depth=1),
        ]
    )
    await test_session.flush()

    active_user = await user_service.create_user(
        test_session,
        email="active-membership@example.com",
        password="TestPass123!",
        first_name="Active",
        last_name="Member",
    )
    orphan_user = await user_service.create_user(
        test_session,
        email="orphan-member@example.com",
        password="TestPass123!",
        first_name="Orphan",
        last_name="Member",
    )

    await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=active_user.id,
        role_ids=[],
    )
    await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=orphan_user.id,
        role_ids=[],
    )
    await membership_service.remove_member(
        test_session,
        entity_id=team.id,
        user_id=orphan_user.id,
        reason="left team",
    )

    memberships, total = await membership_service.get_user_entities(
        test_session,
        user_id=active_user.id,
        page=1,
        limit=20,
        entity_type="team",
        active_only=True,
    )
    assert total == 1
    assert [membership.entity_id for membership in memberships] == [team.id]

    entity_members, entity_total = await membership_service.get_entity_members_with_users(
        test_session,
        entity_id=team.id,
        page=1,
        limit=20,
        active_only=False,
    )
    assert entity_total == 2
    assert {membership.user.email for membership in entity_members} == {
        "active-membership@example.com",
        "orphan-member@example.com",
    }

    orphaned, orphan_total = await membership_service.list_orphaned_users(
        test_session,
        page=1,
        limit=20,
        search="orphan",
        root_entity_id=root.id,
    )
    assert orphan_total == 1
    assert orphaned[0].user.email == "orphan-member@example.com"
    assert orphaned[0].active_membership_count == 0
    assert orphaned[0].total_membership_count == 1
    assert orphaned[0].last_event_type == "revoked"
    assert orphaned[0].last_entity_id == team.id
    assert orphaned[0].last_entity_name == team.display_name


@pytest.mark.unit
@pytest.mark.asyncio
async def test_membership_service_apply_auto_assigned_role(
    test_session,
    auth_config: AuthConfig,
):
    membership_service = MembershipService(config=auth_config)
    role_service = RoleService(config=auth_config)
    user_service = UserService(config=auth_config)

    root = _entity(name="root", slug="root")
    team = _entity(
        name="team",
        slug="team",
        parent_id=root.id,
        depth=1,
        entity_type="team",
        path="/root/team/",
    )
    test_session.add_all([root, team])
    await test_session.flush()
    test_session.add_all(
        [
            EntityClosure(ancestor_id=root.id, descendant_id=root.id, depth=0),
            EntityClosure(ancestor_id=team.id, descendant_id=team.id, depth=0),
            EntityClosure(ancestor_id=root.id, descendant_id=team.id, depth=1),
        ]
    )
    await test_session.flush()

    member = await user_service.create_user(
        test_session,
        email="auto-assign@example.com",
        password="TestPass123!",
        first_name="Auto",
        last_name="Assign",
    )
    membership = await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=member.id,
        role_ids=[],
    )

    auto_role = await role_service.create_role(
        test_session,
        name="team_auto",
        display_name="Team Auto",
        is_global=False,
        root_entity_id=root.id,
        scope_entity_id=root.id,
        scope=RoleScope.HIERARCHY,
        is_auto_assigned=True,
        assignable_at_types=["team"],
    )

    updated_count = await membership_service.apply_auto_assigned_role(test_session, auto_role.id)
    assert updated_count == 1

    await test_session.refresh(membership, ["roles"])
    assert {role.name for role in membership.roles} == {"team_auto"}

    updated_count_again = await membership_service.apply_auto_assigned_role(test_session, auto_role.id)
    assert updated_count_again == 0
