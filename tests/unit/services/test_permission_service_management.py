import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.enums import DefinitionStatus
from outlabs_auth.models.sql.permission import PermissionTag
from outlabs_auth.services.permission import PermissionService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permission_service_management_helpers(
    test_session,
    auth_config: AuthConfig,
):
    service = PermissionService(config=auth_config)

    active = await service.create_permission(
        test_session,
        name="user:read",
        display_name="User Read",
        tags=["admin", "core"],
    )
    inactive = await service.create_permission(
        test_session,
        name="user:update",
        display_name="User Update",
        status=DefinitionStatus.INACTIVE,
    )
    archived = await service.create_permission(
        test_session,
        name="role:delete",
        display_name="Role Delete",
    )
    archived.status = DefinitionStatus.ARCHIVED
    await test_session.flush()

    listed_active, total_active = await service.list_permissions(
        test_session,
        page=1,
        limit=20,
        resource="user",
        is_active=True,
    )
    assert total_active == 1
    assert [permission.name for permission in listed_active] == ["user:read"]

    listed_inactive, total_inactive = await service.list_permissions(
        test_session,
        page=1,
        limit=20,
        resource="user",
        is_active=False,
    )
    assert total_inactive == 1
    assert [permission.name for permission in listed_inactive] == ["user:update"]

    searched = await service.search_permissions(test_session, "user")
    assert {permission.name for permission in searched} == {"user:read", "user:update"}

    extra_tag = PermissionTag(name="reporting")
    test_session.add(extra_tag)
    await test_session.flush()

    await service.add_tag_to_permission(test_session, active.id, extra_tag.id)
    await service.add_tag_to_permission(test_session, active.id, extra_tag.id)
    tagged = await service.get_permissions_by_tag(test_session, "reporting")
    assert [permission.name for permission in tagged] == ["user:read"]

    assert await service.remove_tag_from_permission(test_session, active.id, extra_tag.id) is True
    assert await service.remove_tag_from_permission(test_session, active.id, extra_tag.id) is False

    assert await service.check_permission_exists(test_session, "user:read") is True
    assert await service.check_permission_exists(test_session, "audit:read") is False

    created = await service.bulk_create_permissions(
        test_session,
        [
            {"name": "audit:read", "display_name": "Audit Read"},
            {"name": "user:read", "display_name": "Duplicate User Read"},
        ],
    )
    assert sorted(permission.name for permission in created) == ["audit:read", "user:read"]

    audit_permissions, total_permissions = await service.list_permissions(
        test_session,
        page=1,
        limit=20,
        resource=None,
    )
    assert total_permissions == 3
    assert "role:delete" not in {permission.name for permission in audit_permissions}
