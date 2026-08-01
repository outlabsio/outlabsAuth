from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.integrations import HostQueryService
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import EntityClass, RoleScope, UserStatus
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.role import RoleService
from outlabs_auth.services.user import UserService


def _entity(
    *,
    name: str,
    slug: str,
    parent_id=None,
    depth: int = 0,
    entity_type: str = "organization",
    path: str | None = None,
) -> Entity:
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
async def test_host_query_service_lists_current_entity_members(
    test_session,
    auth_config: AuthConfig,
):
    membership_service = MembershipService(config=auth_config)
    role_service = RoleService(config=auth_config)
    user_service = UserService(config=auth_config)
    host_queries = HostQueryService(
        membership_service=membership_service,
        role_service=role_service,
    )

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

    team_role = await role_service.create_role(
        test_session,
        name="team_member",
        display_name="Team Member",
        is_global=False,
        root_entity_id=root.id,
        scope_entity_id=team.id,
        scope=RoleScope.ENTITY_ONLY,
        assignable_at_types=["team"],
    )

    active_user = await user_service.create_user(
        test_session,
        email="active@host-query.test",
        password="TestPass123!",
        first_name="Active",
        last_name="User",
    )
    active_user.phone = "+1-555-0100"
    await test_session.flush()
    suspended_user = await user_service.create_user(
        test_session,
        email="suspended@host-query.test",
        password="TestPass123!",
        first_name="Suspended",
        last_name="User",
    )
    suspended_user.status = UserStatus.SUSPENDED

    expired_user = await user_service.create_user(
        test_session,
        email="expired@host-query.test",
        password="TestPass123!",
        first_name="Expired",
        last_name="User",
    )

    await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=active_user.id,
        role_ids=[team_role.id],
    )
    await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=suspended_user.id,
        role_ids=[],
    )
    expired_membership = await membership_service.add_member(
        test_session,
        entity_id=team.id,
        user_id=expired_user.id,
        role_ids=[],
    )
    expired_membership.valid_until = datetime.now(timezone.utc) - timedelta(days=1)
    await test_session.flush()

    current_members, current_total = await host_queries.list_entity_members(
        test_session,
        entity_id=team.id,
        active_only=True,
    )

    assert current_total == 1
    assert [member.user.email for member in current_members] == ["active@host-query.test"]
    assert current_members[0].entity.entity_type == "team"
    assert [role.name for role in current_members[0].roles] == ["team_member"]

    all_members, all_total = await host_queries.list_entity_members(
        test_session,
        entity_id=team.id,
        active_only=False,
    )
    assert all_total == 3
    assert {member.user.email for member in all_members} == {
        "active@host-query.test",
        "suspended@host-query.test",
        "expired@host-query.test",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_host_query_service_lists_roles_for_entity(
    test_session,
    auth_config: AuthConfig,
):
    role_service = RoleService(config=auth_config)
    host_queries = HostQueryService(
        membership_service=MembershipService(config=auth_config),
        role_service=role_service,
    )

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

    await role_service.create_role(
        test_session,
        name="global_viewer",
        display_name="Global Viewer",
        is_global=True,
        assignable_at_types=["team"],
    )
    await role_service.create_role(
        test_session,
        name="team_manager",
        display_name="Team Manager",
        is_global=False,
        root_entity_id=root.id,
        scope_entity_id=root.id,
        scope=RoleScope.HIERARCHY,
        assignable_at_types=["team"],
    )

    roles, total = await host_queries.list_roles_for_entity(
        test_session,
        entity_id=team.id,
        include_global=True,
    )

    assert total == 2
    assert {role.name for role in roles} == {"global_viewer", "team_manager"}
    assert next(role for role in roles if role.name == "team_manager").assignable_at_types == ("team",)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_host_query_service_lists_memberships_for_multiple_users(
    test_session,
    auth_config: AuthConfig,
):
    membership_service = MembershipService(config=auth_config)
    user_service = UserService(config=auth_config)
    host_queries = HostQueryService(
        membership_service=membership_service,
        role_service=RoleService(config=auth_config),
    )

    root = _entity(name="root", slug="root")
    office = _entity(
        name="office",
        slug="office",
        parent_id=root.id,
        depth=1,
        entity_type="office",
        path="/root/office/",
    )
    agent_practice = _entity(
        name="practice",
        slug="practice",
        parent_id=office.id,
        depth=2,
        entity_type="agent_practice",
        path="/root/office/practice/",
    )
    test_session.add_all([root, office, agent_practice])
    await test_session.flush()
    test_session.add_all(
        [
            EntityClosure(ancestor_id=root.id, descendant_id=root.id, depth=0),
            EntityClosure(ancestor_id=office.id, descendant_id=office.id, depth=0),
            EntityClosure(ancestor_id=agent_practice.id, descendant_id=agent_practice.id, depth=0),
            EntityClosure(ancestor_id=root.id, descendant_id=office.id, depth=1),
            EntityClosure(ancestor_id=root.id, descendant_id=agent_practice.id, depth=2),
            EntityClosure(ancestor_id=office.id, descendant_id=agent_practice.id, depth=1),
        ]
    )
    await test_session.flush()

    primary_user = await user_service.create_user(
        test_session,
        email="primary@host-query.test",
        password="TestPass123!",
        first_name="Primary",
        last_name="User",
    )
    secondary_user = await user_service.create_user(
        test_session,
        email="secondary@host-query.test",
        password="TestPass123!",
        first_name="Secondary",
        last_name="User",
    )

    await membership_service.add_member(
        test_session,
        entity_id=agent_practice.id,
        user_id=primary_user.id,
        role_ids=[],
    )
    await membership_service.add_member(
        test_session,
        entity_id=office.id,
        user_id=secondary_user.id,
        role_ids=[],
    )

    memberships = await host_queries.list_user_entity_memberships(
        test_session,
        user_ids=[primary_user.id, secondary_user.id],
        active_only=True,
    )

    assert {(membership.user.email, membership.entity.entity_type) for membership in memberships} == {
        ("primary@host-query.test", "agent_practice"),
        ("secondary@host-query.test", "office"),
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_host_query_service_lists_users_without_membership_dependency(
    test_session,
    auth_config: AuthConfig,
):
    user_service = UserService(config=auth_config)
    host_queries = HostQueryService(
        membership_service=MembershipService(config=auth_config),
        role_service=RoleService(config=auth_config),
    )

    active_user = await user_service.create_user(
        test_session,
        email="active-user@host-query.test",
        password="TestPass123!",
        first_name="Active",
        last_name="User",
    )
    active_user.phone = "+1-555-0142"
    suspended_user = await user_service.create_user(
        test_session,
        email="suspended-user@host-query.test",
        password="TestPass123!",
        first_name="Suspended",
        last_name="User",
    )
    suspended_user.status = UserStatus.SUSPENDED
    await test_session.flush()

    all_users = await host_queries.list_users_by_ids(
        test_session,
        user_ids=[active_user.id, suspended_user.id],
        active_only=False,
    )
    active_users = await host_queries.list_users_by_ids(
        test_session,
        user_ids=[active_user.id, suspended_user.id],
        active_only=True,
    )

    assert {(user.email, user.status) for user in all_users} == {
        ("active-user@host-query.test", "active"),
        ("suspended-user@host-query.test", "suspended"),
    }
    assert [user.email for user in active_users] == ["active-user@host-query.test"]
    active_projection = next(user for user in all_users if user.email == "active-user@host-query.test")
    assert active_projection.phone == "+1-555-0142"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_host_query_service_applies_configured_schema_to_session(
    monkeypatch: pytest.MonkeyPatch,
):
    class _FakeSession:
        def __init__(self):
            self.calls: list[str] = []

        async def execute(self, stmt):
            self.calls.append(str(stmt))
            return SimpleNamespace()

    host_queries = HostQueryService(
        membership_service=SimpleNamespace(config=SimpleNamespace(database_schema="outlabs_auth")),
        role_service=SimpleNamespace(),
    )

    async def _fake_count_memberships(_session, *filters):
        return 0

    async def _fake_load_memberships(_session, *, filters, page, limit):
        return []

    monkeypatch.setattr(host_queries, "_count_memberships", _fake_count_memberships)
    monkeypatch.setattr(host_queries, "_load_memberships", _fake_load_memberships)

    session = _FakeSession()
    members, total = await host_queries.list_entity_members(
        session,
        entity_id="00000000-0000-0000-0000-000000000001",
    )

    assert members == []
    assert total == 0
    assert any('SET LOCAL search_path TO "outlabs_auth", public' in call for call in session.calls)
    assert all("SHOW search_path" not in call for call in session.calls)
