from sqlalchemy import func, select

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import EntityNotFoundError, InvalidInputError
from outlabs_auth.models.sql.enums import DefinitionStatus, EntityClass
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.role import RoleService
from outlabs_auth.services.user import UserService


async def _create_entity_tree(test_session, auth_config: AuthConfig):
    entity_service = EntityService(config=auth_config, redis_client=None)
    root = await entity_service.create_entity(
        session=test_session,
        name="root-role-scope",
        display_name="Root Scope",
        slug="root-role-scope",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    team = await entity_service.create_entity(
        session=test_session,
        name="team-role-scope",
        display_name="Team Scope",
        slug="team-role-scope",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=root.id,
    )
    return root, team


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_service_create_update_and_definition_guards(
    test_session,
    auth_config: AuthConfig,
):
    entity_service = EntityService(config=auth_config, redis_client=None)
    permission_service = PermissionService(config=auth_config)
    role_service = RoleService(config=auth_config)

    root = await entity_service.create_entity(
        session=test_session,
        name="root-a",
        display_name="Root A",
        slug="root-a-role",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    team = await entity_service.create_entity(
        session=test_session,
        name="team-a",
        display_name="Team A",
        slug="team-a-role",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=root.id,
    )

    active_permission = await permission_service.create_permission(
        test_session,
        name="role:manage",
        display_name="Role Manage",
    )
    await permission_service.create_permission(
        test_session,
        name="role:inactive",
        display_name="Role Inactive",
        status=DefinitionStatus.INACTIVE,
    )

    with pytest.raises(InvalidInputError, match="System-wide roles cannot set"):
        await role_service.create_role(
            test_session,
            name="invalid-global",
            display_name="Invalid Global",
            is_global=True,
            root_entity_id=root.id,
        )

    with pytest.raises(InvalidInputError, match="Scoped roles must define"):
        await role_service.create_role(
            test_session,
            name="missing-scope",
            display_name="Missing Scope",
            is_global=False,
        )

    with pytest.raises(InvalidInputError, match="Role can only be scoped to root entities"):
        await role_service.create_role(
            test_session,
            name="non-root-owner",
            display_name="Non Root Owner",
            is_global=False,
            root_entity_id=team.id,
        )

    with pytest.raises(EntityNotFoundError, match="Scope entity not found"):
        await role_service.create_role(
            test_session,
            name="missing-scope-entity",
            display_name="Missing Scope Entity",
            is_global=False,
            scope_entity_id=active_permission.id,
        )

    with pytest.raises(InvalidInputError, match="Only active roles can be auto-assigned"):
        await role_service.create_role(
            test_session,
            name="inactive-auto-role",
            display_name="Inactive Auto Role",
            is_global=False,
            scope_entity_id=team.id,
            status=DefinitionStatus.INACTIVE,
            is_auto_assigned=True,
        )

    with pytest.raises(InvalidInputError, match="not active"):
        await role_service.create_role(
            test_session,
            name="inactive-permission-role",
            display_name="Inactive Permission Role",
            is_global=False,
            root_entity_id=root.id,
            permission_names=["role:inactive"],
        )

    scoped_role = await role_service.create_role(
        test_session,
        name="team-manager",
        display_name="Team Manager",
        is_global=False,
        scope_entity_id=team.id,
        permission_names=[active_permission.name],
        assignable_at_types=["TEAM", "team", ""],
    )
    assert scoped_role.root_entity_id == root.id
    assert scoped_role.assignable_at_types == ["team"]

    org_role = await role_service.create_role(
        test_session,
        name="org-manager",
        display_name="Org Manager",
        is_global=False,
        root_entity_id=root.id,
    )
    global_role = await role_service.create_role(
        test_session,
        name="platform-role",
        display_name="Platform Role",
        is_global=True,
    )
    system_role = await role_service.create_role(
        test_session,
        name="system-role-guard",
        display_name="System Role Guard",
        is_global=True,
        is_system_role=True,
    )

    with pytest.raises(InvalidInputError, match="Cannot modify system role"):
        await role_service.update_role(
            test_session,
            system_role.id,
            display_name="Changed",
        )

    with pytest.raises(InvalidInputError, match="Scoped roles cannot be converted"):
        await role_service.update_role(
            test_session,
            org_role.id,
            is_global=True,
        )

    with pytest.raises(InvalidInputError, match="System-wide roles cannot be made non-global"):
        await role_service.update_role(
            test_session,
            global_role.id,
            is_global=False,
        )

    with pytest.raises(InvalidInputError, match="Auto-assigned roles must have a scope_entity_id"):
        await role_service.update_role(
            test_session,
            org_role.id,
            is_auto_assigned=True,
        )

    updated = await role_service.set_entity_type_permissions(
        test_session,
        scoped_role.id,
        {"team": [active_permission.name]},
    )
    assert updated.id == scoped_role.id
    assert await role_service.get_role_entity_type_permission_names(
        test_session,
        scoped_role.id,
    ) == {"team": [active_permission.name]}

    assert await role_service.delete_role(test_session, global_role.id) is True
    assert await role_service.delete_role(test_session, global_role.id) is False

    with pytest.raises(InvalidInputError, match="Cannot delete system role"):
        await role_service.delete_role(test_session, system_role.id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_service_permission_assignment_and_revocation_paths(
    test_session,
    auth_config: AuthConfig,
):
    permission_service = PermissionService(config=auth_config)
    role_service = RoleService(config=auth_config)
    user_service = UserService(config=auth_config)
    root, team = await _create_entity_tree(test_session, auth_config)

    read_permission = await permission_service.create_permission(
        test_session,
        name="user:read",
        display_name="User Read",
    )
    write_permission = await permission_service.create_permission(
        test_session,
        name="user:update",
        display_name="User Update",
    )

    active_role = await role_service.create_role(
        test_session,
        name="active-direct-role",
        display_name="Active Direct Role",
        is_global=True,
        permission_names=[read_permission.name],
    )
    inactive_role = await role_service.create_role(
        test_session,
        name="inactive-direct-role",
        display_name="Inactive Direct Role",
        is_global=True,
        status=DefinitionStatus.INACTIVE,
    )
    entity_local_role = await role_service.create_role(
        test_session,
        name="entity-local-role",
        display_name="Entity Local Role",
        is_global=False,
        scope_entity_id=team.id,
    )
    root_scoped_role = await role_service.create_role(
        test_session,
        name="root-scoped-role",
        display_name="Root Scoped Role",
        is_global=False,
        root_entity_id=root.id,
    )

    await role_service.add_permissions_by_name(
        test_session,
        active_role.id,
        [write_permission.name],
    )
    assert set(
        await role_service.get_role_permission_names(test_session, active_role.id)
    ) == {"user:read", "user:update"}

    await role_service.remove_permissions(
        test_session,
        active_role.id,
        [read_permission.id],
    )
    assert await role_service.get_role_permission_names(
        test_session,
        active_role.id,
    ) == ["user:update"]

    await role_service.set_permissions_by_name(
        test_session,
        active_role.id,
        [read_permission.name, write_permission.name],
    )
    assert set(
        await role_service.get_role_permission_names(test_session, active_role.id)
    ) == {"user:read", "user:update"}

    user = await user_service.create_user(
        test_session,
        email="direct-role-user@example.com",
        password="TestPass123!",
        first_name="Direct",
        last_name="Role",
    )

    with pytest.raises(InvalidInputError, match="Only active roles can be assigned"):
        await role_service.assign_role_to_user(
            test_session,
            user.id,
            inactive_role.id,
        )

    with pytest.raises(InvalidInputError, match="Entity-local roles cannot be assigned"):
        await role_service.assign_role_to_user(
            test_session,
            user.id,
            entity_local_role.id,
        )

    membership = await role_service.assign_role_to_user(
        test_session,
        user.id,
        active_role.id,
    )
    with pytest.raises(InvalidInputError, match="already has this role assigned"):
        await role_service.assign_role_to_user(
            test_session,
            user.id,
            active_role.id,
        )

    assert await role_service.revoke_role_from_user(
        test_session,
        user.id,
        root_scoped_role.id,
    ) is False
    assert await role_service.revoke_role_from_user(
        test_session,
        user.id,
        active_role.id,
        reason="cleanup",
    ) is True

    reactivated = await role_service.assign_role_to_user(
        test_session,
        user.id,
        active_role.id,
    )
    assert reactivated.id == membership.id

    membership_count = await test_session.scalar(
        select(func.count())
        .select_from(UserRoleMembership)
        .where(
            UserRoleMembership.user_id == user.id,
            UserRoleMembership.role_id == active_role.id,
        )
    )
    assert membership_count == 1

    active_roles = await role_service.get_user_roles(test_session, user.id)
    assert [role.id for role in active_roles] == [active_role.id]

    assert await role_service.revoke_all_roles_for_user(test_session, user.id) == 1
    assert await role_service.get_user_roles(test_session, user.id) == []

    archived_membership = await role_service.assign_role_to_user(
        test_session,
        user.id,
        root_scoped_role.id,
    )
    assert getattr(archived_membership.status, "value", archived_membership.status) == "active"
    assert (
        await role_service.revoke_memberships_for_archived_entities(
            test_session,
            [root.id],
            reason="entity archived",
        )
        == 1
    )

