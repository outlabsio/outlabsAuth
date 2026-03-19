from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError, PermissionNotFoundError, UserNotFoundError
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import DefinitionStatus, EntityClass, MembershipStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine
from outlabs_auth.services.role import RoleService


async def _create_entity_tree(test_session, auth_config: AuthConfig):
    entity_service = EntityService(config=auth_config, redis_client=None)
    root = await entity_service.create_entity(
        session=test_session,
        name=f"perm-root-{uuid4().hex[:6]}",
        display_name="Permission Root",
        slug=f"perm-root-{uuid4().hex[:6]}",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    team = await entity_service.create_entity(
        session=test_session,
        name=f"perm-team-{uuid4().hex[:6]}",
        display_name="Permission Team",
        slug=f"perm-team-{uuid4().hex[:6]}",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=root.id,
    )
    return root, team


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permission_service_abac_definition_crud_and_mutable_guards(
    test_session,
    auth_config: AuthConfig,
):
    service = PermissionService(config=auth_config)

    permission = await service.create_permission(
        test_session,
        name=f"reports:{uuid4().hex[:6]}",
        display_name="Reports Permission",
    )
    system_permission = await service.create_permission(
        test_session,
        name=f"system:{uuid4().hex[:6]}",
        display_name="System Permission",
        is_system=True,
    )

    with pytest.raises(PermissionNotFoundError, match="Permission not found"):
        await service._get_mutable_permission_for_definition_edit(test_session, uuid4())

    with pytest.raises(InvalidInputError, match="Cannot modify system permission"):
        await service._get_mutable_permission_for_definition_edit(test_session, system_permission.id)

    group = await service.create_permission_condition_group(
        test_session,
        permission.id,
        operator="OR",
        description="group created",
    )
    assert group.permission_id == permission.id
    assert group.operator == "OR"

    updated_group = await service.update_permission_condition_group(
        test_session,
        permission.id,
        group.id,
        fields_set={"description"},
        description="group updated",
    )
    assert updated_group is not None
    assert updated_group.description == "group updated"

    assert (
        await service.update_permission_condition_group(
            test_session,
            permission.id,
            uuid4(),
            fields_set={"description"},
            description="missing",
        )
        is None
    )

    with pytest.raises(InvalidInputError, match="Invalid condition_group_id"):
        await service.create_permission_condition(
            test_session,
            permission.id,
            condition_group_id=uuid4(),
            attribute="user.department",
            operator="eq",
            value="finance",
            value_type="string",
        )

    condition = await service.create_permission_condition(
        test_session,
        permission.id,
        condition_group_id=group.id,
        attribute="user.department",
        operator="eq",
        value="finance",
        value_type="string",
        description="finance only",
    )
    assert condition.condition_group_id == group.id

    with pytest.raises(InvalidInputError, match="Invalid condition_group_id"):
        await service.update_permission_condition(
            test_session,
            permission.id,
            condition.id,
            fields_set={"condition_group_id"},
            condition_group_id=uuid4(),
        )

    updated_condition = await service.update_permission_condition(
        test_session,
        permission.id,
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
        description="region only",
    )
    assert updated_condition is not None
    assert updated_condition.attribute == "resource.region"
    assert updated_condition.value == "latam"

    assert (
        await service.update_permission_condition(
            test_session,
            permission.id,
            uuid4(),
            fields_set={"description"},
            description="missing",
        )
        is None
    )
    assert await service.delete_permission_condition(test_session, permission.id, uuid4()) is False
    assert await service.delete_permission_condition(test_session, permission.id, condition.id) is True

    recreated_condition = await service.create_permission_condition(
        test_session,
        permission.id,
        condition_group_id=group.id,
        attribute="user.department",
        operator="eq",
        value="finance",
        value_type="string",
    )
    assert recreated_condition.id is not None

    assert await service.delete_permission_condition_group(test_session, permission.id, uuid4()) is False
    assert await service.delete_permission_condition_group(test_session, permission.id, group.id) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permission_service_abac_permission_resolution_and_user_permission_helpers(
    test_session,
    auth_config: AuthConfig,
):
    config = auth_config.model_copy(
        update={
            "enable_entity_hierarchy": True,
            "enable_context_aware_roles": True,
        }
    )
    observability = MagicMock()
    permission_service = PermissionService(config=config, observability=observability)
    role_service = RoleService(config=config)
    root, team = await _create_entity_tree(test_session, config)

    permission = await permission_service.create_permission(
        test_session,
        name=f"reports_{uuid4().hex[:6]}:view",
        display_name="Reports View",
    )
    entity_local_permission = await permission_service.create_permission(
        test_session,
        name=f"team_{uuid4().hex[:6]}:edit",
        display_name="Team Edit",
    )
    inactive_permission = await permission_service.create_permission(
        test_session,
        name=f"inactive_{uuid4().hex[:6]}:read",
        display_name="Inactive Permission",
        status=DefinitionStatus.INACTIVE,
    )

    user = User(email=f"perm-user-{uuid4().hex[:6]}@example.com")
    superuser = User(
        email=f"perm-superuser-{uuid4().hex[:6]}@example.com",
        is_superuser=True,
    )
    test_session.add(user)
    test_session.add(superuser)
    await test_session.flush()

    with pytest.raises(UserNotFoundError, match="User not found"):
        await permission_service.get_user_permissions(test_session, uuid4())

    assert await permission_service.get_user_permissions(test_session, superuser.id) == ["*:*"]

    global_role = await role_service.create_role(
        test_session,
        name=f"perm-global-{uuid4().hex[:6]}",
        display_name="Permission Global",
        is_global=True,
        permission_names=[permission.name],
    )
    entity_role = await role_service.create_role(
        test_session,
        name=f"perm-entity-{uuid4().hex[:6]}",
        display_name="Permission Entity",
        is_global=False,
        scope_entity_id=team.id,
        permission_names=[entity_local_permission.name],
    )
    inactive_role = await role_service.create_role(
        test_session,
        name=f"perm-inactive-{uuid4().hex[:6]}",
        display_name="Permission Inactive",
        is_global=True,
        status=DefinitionStatus.INACTIVE,
        permission_names=[permission.name],
    )

    active_membership = UserRoleMembership(
        user_id=user.id,
        role_id=global_role.id,
        status=MembershipStatus.ACTIVE,
    )
    expired_membership = UserRoleMembership(
        user_id=user.id,
        role_id=inactive_role.id,
        status=MembershipStatus.ACTIVE,
        valid_until=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    entity_local_membership = UserRoleMembership(
        user_id=user.id,
        role_id=entity_role.id,
        status=MembershipStatus.ACTIVE,
    )
    test_session.add(active_membership)
    test_session.add(expired_membership)
    test_session.add(entity_local_membership)

    expired_entity_membership = EntityMembership(
        user_id=user.id,
        entity_id=root.id,
        status=MembershipStatus.ACTIVE,
        valid_until=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    valid_entity_membership = EntityMembership(
        user_id=user.id,
        entity_id=team.id,
        status=MembershipStatus.ACTIVE,
    )
    expired_entity_membership.roles = [global_role]
    valid_entity_membership.roles = [entity_role, inactive_role]
    test_session.add(expired_entity_membership)
    test_session.add(valid_entity_membership)
    await test_session.flush()

    group = await permission_service.create_permission_condition_group(
        test_session,
        permission.id,
        operator="AND",
        description="permission guard",
    )
    await permission_service.create_permission_condition(
        test_session,
        permission.id,
        condition_group_id=group.id,
        attribute="user.department",
        operator="equals",
        value="finance",
        value_type="string",
    )

    role_loaded = await role_service.get_role_by_id(
        test_session,
        global_role.id,
        load_permissions=True,
    )
    assert role_loaded is not None
    engine = PolicyEvaluationEngine()

    assert await permission_service._abac_allows_role_and_permission(
        session=test_session,
        role=role_loaded,
        required_permission=permission.name,
        entity_type=None,
        context={"user": {"department": "finance"}},
        engine=engine,
    )
    assert not await permission_service._abac_allows_role_and_permission(
        session=test_session,
        role=role_loaded,
        required_permission="missing:permission",
        entity_type=None,
        context={"user": {"department": "finance"}},
        engine=engine,
    )
    assert not await permission_service._abac_allows_role_and_permission(
        session=test_session,
        role=role_loaded,
        required_permission=permission.name,
        entity_type=None,
        context={"user": {"department": "sales"}},
        engine=engine,
    )

    assert not await permission_service._check_permission_via_user_roles_with_abac(
        session=test_session,
        user_id=user.id,
        permission=entity_local_permission.name,
        context={},
        engine=engine,
        include_entity_local=False,
    )
    assert await permission_service._check_permission_via_user_roles_with_abac(
        session=test_session,
        user_id=user.id,
        permission=entity_local_permission.name,
        context={},
        engine=engine,
        include_entity_local=True,
    )

    assert await permission_service._get_user_role_permissions(
        session=test_session,
        user_id=user.id,
        include_entity_local=False,
    ) == {permission.name}
    assert await permission_service._get_user_role_permissions(
        session=test_session,
        user_id=user.id,
        include_entity_local=True,
    ) == {permission.name, entity_local_permission.name}

    assert set(
        await permission_service.get_user_permissions(
            test_session,
            user.id,
            include_entity_local=False,
        )
    ) == {permission.name}
    assert set(await permission_service._get_global_role_permissions(test_session, user.id)) == {
        permission.name
    }

    permission_service._log_permission_check(
        user.id,
        permission.name,
        "granted",
        datetime.now(timezone.utc) - timedelta(milliseconds=5),
        "test",
    )
    observability.log_permission_check.assert_called_once()
