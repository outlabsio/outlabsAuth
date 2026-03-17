from __future__ import annotations

from uuid import uuid4

import pytest

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.role import RoleService


async def _create_entity(test_session, *, slug: str, entity_type: str) -> Entity:
    entity = Entity(
        name=slug,
        display_name=slug,
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type=entity_type,
        status="active",
        depth=0,
    )
    entity.update_path(None)
    test_session.add(entity)
    await test_session.flush()
    return entity


@pytest.mark.unit
@pytest.mark.asyncio
async def test_context_aware_role_override_replaces_base_permissions(
    test_session,
    auth_config,
):
    config = auth_config.model_copy(
        update={
            "enable_entity_hierarchy": True,
            "enable_context_aware_roles": True,
        }
    )
    role_service = RoleService(config)
    permission_service = PermissionService(config=config, observability=None)

    base_permission = await permission_service.create_permission(
        test_session,
        name=f"reports_{uuid4().hex[:6]}:view",
        display_name="Reports View",
    )
    override_permission = await permission_service.create_permission(
        test_session,
        name=f"reports_{uuid4().hex[:6]}:approve",
        display_name="Reports Approve",
    )

    role = await role_service.create_role(
        test_session,
        name=f"manager-{uuid4().hex[:6]}",
        display_name="Manager",
        permission_names=[base_permission.name],
        entity_type_permissions={"team": [override_permission.name]},
    )

    overrides = await role_service.get_role_entity_type_permission_names(
        test_session, role.id
    )
    assert overrides == {"team": [override_permission.name]}

    user = User(email=f"manager-{uuid4().hex[:6]}@example.com")
    test_session.add(user)
    await test_session.flush()

    test_session.add(
        UserRoleMembership(
            user_id=user.id,
            role_id=role.id,
            status=MembershipStatus.ACTIVE,
        )
    )
    await test_session.flush()

    org = await _create_entity(
        test_session,
        slug=f"org-{uuid4().hex[:6]}",
        entity_type="organization",
    )
    team = await _create_entity(
        test_session,
        slug=f"team-{uuid4().hex[:6]}",
        entity_type="team",
    )

    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission=base_permission.name,
            entity_id=org.id,
        )
        is True
    )
    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission=base_permission.name,
            entity_id=team.id,
        )
        is False
    )
    assert (
        await permission_service.check_permission(
            test_session,
            user_id=user.id,
            permission=override_permission.name,
            entity_id=team.id,
        )
        is True
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_role_rejects_unknown_context_override_permissions(
    test_session,
    auth_config,
):
    config = auth_config.model_copy(
        update={
            "enable_entity_hierarchy": True,
            "enable_context_aware_roles": True,
        }
    )
    role_service = RoleService(config)

    with pytest.raises(InvalidInputError) as exc_info:
        await role_service.create_role(
            test_session,
            name=f"manager-{uuid4().hex[:6]}",
            display_name="Manager",
            entity_type_permissions={"team": ["missing:permission"]},
        )

    assert exc_info.value.details == {
        "missing_permissions": ["missing:permission"]
    }
