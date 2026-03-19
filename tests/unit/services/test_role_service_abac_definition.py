from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError, RoleNotFoundError
from outlabs_auth.models.sql.enums import DefinitionStatus, EntityClass
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.role import RoleService


async def _create_entity_tree(test_session, auth_config: AuthConfig):
    entity_service = EntityService(config=auth_config, redis_client=None)
    root = await entity_service.create_entity(
        session=test_session,
        name=f"role-root-{uuid4().hex[:6]}",
        display_name="Role Root",
        slug=f"role-root-{uuid4().hex[:6]}",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    team = await entity_service.create_entity(
        session=test_session,
        name=f"role-team-{uuid4().hex[:6]}",
        display_name="Role Team",
        slug=f"role-team-{uuid4().hex[:6]}",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=root.id,
    )
    return root, team


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_service_abac_definition_crud_and_mutable_guards(
    test_session,
    auth_config: AuthConfig,
):
    config = auth_config.model_copy(update={"enable_entity_hierarchy": True})
    role_service = RoleService(config=config)
    permission_service = PermissionService(config=config)
    root, team = await _create_entity_tree(test_session, config)

    permission = await permission_service.create_permission(
        test_session,
        name=f"role_{uuid4().hex[:6]}:manage",
        display_name="Role Manage",
    )
    role = await role_service.create_role(
        test_session,
        name=f"abac-role-{uuid4().hex[:6]}",
        display_name="ABAC Role",
        is_global=False,
        scope_entity_id=team.id,
        permission_names=[permission.name],
    )
    system_role = await role_service.create_role(
        test_session,
        name=f"system-role-{uuid4().hex[:6]}",
        display_name="System Role",
        is_global=True,
        is_system_role=True,
    )

    with pytest.raises(RoleNotFoundError, match="Role not found"):
        await role_service._get_mutable_role_for_definition_edit(test_session, uuid4())

    with pytest.raises(InvalidInputError, match="Cannot modify system role"):
        await role_service._get_mutable_role_for_definition_edit(test_session, system_role.id)

    group = await role_service.create_role_condition_group(
        test_session,
        role.id,
        operator="OR",
        description="group created",
    )
    assert group.role_id == role.id
    assert group.operator == "OR"

    updated_group = await role_service.update_role_condition_group(
        test_session,
        role.id,
        group.id,
        fields_set={"description"},
        description="group updated",
    )
    assert updated_group is not None
    assert updated_group.description == "group updated"

    assert (
        await role_service.update_role_condition_group(
            test_session,
            role.id,
            uuid4(),
            fields_set={"description"},
            description="missing",
        )
        is None
    )

    with pytest.raises(InvalidInputError, match="Invalid condition_group_id"):
        await role_service.create_role_condition(
            test_session,
            role.id,
            condition_group_id=uuid4(),
            attribute="resource.environment",
            operator="eq",
            value="prod",
            value_type="string",
        )

    condition = await role_service.create_role_condition(
        test_session,
        role.id,
        condition_group_id=group.id,
        attribute="resource.environment",
        operator="eq",
        value="prod",
        value_type="string",
        description="prod only",
    )
    assert condition.condition_group_id == group.id

    with pytest.raises(InvalidInputError, match="Invalid condition_group_id"):
        await role_service.update_role_condition(
            test_session,
            role.id,
            condition.id,
            fields_set={"condition_group_id"},
            condition_group_id=uuid4(),
        )

    updated_condition = await role_service.update_role_condition(
        test_session,
        role.id,
        condition.id,
        fields_set={
            "condition_group_id",
            "attribute",
            "operator",
            "value",
            "value_type",
            "description",
        },
        condition_group_id=group.id,
        attribute="resource.region",
        operator="eq",
        value="latam",
        value_type="string",
        description="latam only",
    )
    assert updated_condition is not None
    assert updated_condition.attribute == "resource.region"
    assert updated_condition.value == "latam"

    assert (
        await role_service.update_role_condition(
            test_session,
            role.id,
            uuid4(),
            fields_set={"description"},
            description="missing",
        )
        is None
    )
    assert await role_service.delete_role_condition(test_session, role.id, uuid4()) is False
    assert await role_service.delete_role_condition(test_session, role.id, condition.id) is True

    recreated_condition = await role_service.create_role_condition(
        test_session,
        role.id,
        condition_group_id=group.id,
        attribute="resource.environment",
        operator="eq",
        value="prod",
        value_type="string",
    )
    assert recreated_condition.id is not None

    assert await role_service.delete_role_condition_group(test_session, role.id, uuid4()) is False
    assert await role_service.delete_role_condition_group(test_session, role.id, group.id) is True
    assert root.id is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_role_service_helper_paths_cover_permission_resolution_and_cache_invalidations(
    test_session,
    auth_config: AuthConfig,
):
    config = auth_config.model_copy(update={"enable_entity_hierarchy": True})
    role_service = RoleService(config=config)
    permission_service = PermissionService(config=config)
    _, team = await _create_entity_tree(test_session, config)

    active_permission = await permission_service.create_permission(
        test_session,
        name=f"active:{uuid4().hex[:6]}",
        display_name="Active Permission",
    )
    inactive_permission = await permission_service.create_permission(
        test_session,
        name=f"inactive:{uuid4().hex[:6]}",
        display_name="Inactive Permission",
        status=DefinitionStatus.INACTIVE,
    )

    assert await role_service._resolve_permission_names_by_ids(test_session, []) == []

    with pytest.raises(InvalidInputError, match="not active"):
        await role_service._resolve_permission_names_by_ids(test_session, [inactive_permission.id])

    with pytest.raises(InvalidInputError, match="do not exist"):
        await role_service._resolve_permission_names_by_ids(test_session, [uuid4()])

    assert await role_service._resolve_permission_names_by_ids(
        test_session,
        [active_permission.id],
    ) == [active_permission.name]

    role = await role_service.create_role(
        test_session,
        name=f"helper-role-{uuid4().hex[:6]}",
        display_name="Helper Role",
        is_global=False,
        scope_entity_id=team.id,
        permission_names=[active_permission.name],
    )

    user = User(email=f"role-user-{uuid4().hex[:6]}@example.com")
    test_session.add(user)
    await test_session.flush()

    membership = UserRoleMembership(
        user_id=user.id,
        role_id=role.id,
    )
    test_session.add(membership)
    await test_session.flush()

    role_service.cache_service = SimpleNamespace(
        publish_all_permissions_invalidation=AsyncMock(),
        publish_user_permissions_invalidation=AsyncMock(),
    )
    await role_service._invalidate_all_permissions_cache()
    await role_service._invalidate_user_permissions_cache(user.id)
    role_service.cache_service.publish_all_permissions_invalidation.assert_awaited_once()
    role_service.cache_service.publish_user_permissions_invalidation.assert_awaited_once_with(
        str(user.id)
    )

    snapshot = await role_service._build_user_role_audit_snapshot(test_session, membership)
    assert snapshot["role_name"] == role.name
