from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError, PermissionDeniedError
from outlabs_auth.models.sql.enums import DefinitionStatus
from outlabs_auth.services.permission import PermissionService


class FakePermissionCache:
    def __init__(self) -> None:
        self.cached_value = None
        self.get_calls: list[tuple[str, str, str | None, str | None]] = []
        self.set_calls: list[tuple[str, str, bool, str | None, str | None]] = []

    async def get_permission_check(
        self,
        user_id: str,
        permission: str,
        entity_id: str | None,
        context_hash: str | None = None,
    ):
        self.get_calls.append((user_id, permission, entity_id, context_hash))
        return self.cached_value

    async def set_permission_check(
        self,
        user_id: str,
        permission: str,
        result: bool,
        entity_id: str | None,
        context_hash: str | None = None,
    ):
        self.set_calls.append((user_id, permission, result, entity_id, context_hash))
        return True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permission_service_status_cache_and_require_helpers(
    test_session,
    auth_config: AuthConfig,
):
    service = PermissionService(config=auth_config)

    with pytest.raises(InvalidInputError, match="status and is_active cannot conflict"):
        service._resolve_permission_status(
            status=DefinitionStatus.ACTIVE,
            is_active=False,
        )

    with pytest.raises(InvalidInputError, match="Use delete to archive permissions"):
        service._resolve_permission_status(status=DefinitionStatus.ARCHIVED)

    assert (
        service._resolve_permission_status(is_active=False)
        == DefinitionStatus.INACTIVE
    )

    cache = FakePermissionCache()
    cache.cached_value = True
    service.cache_service = cache

    user_id = uuid4()
    entity_id = uuid4()
    cached = await service._get_cached_permission_result(
        user_id=user_id,
        permission="user:read",
        entity_id=entity_id,
    )
    assert cached is True

    await service._cache_permission_result(
        use_cache=True,
        user_id=user_id,
        permission="user:read",
        entity_id=entity_id,
        result=False,
    )
    await service._cache_permission_result(
        use_cache=False,
        user_id=user_id,
        permission="user:update",
        entity_id=None,
        result=True,
    )

    assert cache.get_calls == [(str(user_id), "user:read", str(entity_id), None)]
    assert cache.set_calls == [(str(user_id), "user:read", False, str(entity_id), None)]

    service.check_permission = AsyncMock(side_effect=[False, False, True, True, False])  # type: ignore[method-assign]

    with pytest.raises(PermissionDeniedError, match="Permission denied: user:delete"):
        await service.require_permission(test_session, user_id, "user:delete")

    await service.require_any_permission(
        test_session,
        user_id,
        ["user:create", "user:update"],
    )

    with pytest.raises(PermissionDeniedError, match="missing 1 required permission"):
        await service.require_all_permissions(
            test_session,
            user_id,
            ["user:read", "user:delete"],
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permission_service_crud_tag_and_archive_guards(
    test_session,
    auth_config: AuthConfig,
):
    service = PermissionService(config=auth_config)

    regular = await service.create_permission(
        test_session,
        name="invoice:approve",
        display_name="Invoice Approve",
        description="Approve invoices",
        is_active=False,
        tags=["finance", "finance", " approvals "],
    )
    system_permission = await service.create_permission(
        test_session,
        name="system:manage",
        display_name="System Manage",
        is_system=True,
    )

    assert regular.status == DefinitionStatus.INACTIVE
    assert [tag.name for tag in regular.tags] == ["finance", "approvals"]

    with pytest.raises(InvalidInputError, match="already exists"):
        await service.create_permission(
            test_session,
            name="invoice:approve",
            display_name="Duplicate",
        )

    with pytest.raises(InvalidInputError, match="Cannot modify system permission"):
        await service.update_permission(
            test_session,
            system_permission.id,
            display_name="Renamed",
        )

    with pytest.raises(InvalidInputError, match="Cannot modify system permission"):
        await service.set_permission_tags(
            test_session,
            system_permission.id,
            ["security"],
        )

    with pytest.raises(InvalidInputError, match="Cannot delete system permission"):
        await service.delete_permission(test_session, system_permission.id)

    updated = await service.update_permission(
        test_session,
        regular.id,
        display_name="Invoice Approver",
        description="Updated description",
        status=DefinitionStatus.ACTIVE,
        tags=[],
    )
    assert updated.display_name == "Invoice Approver"
    assert updated.description == "Updated description"
    assert updated.status == DefinitionStatus.ACTIVE
    assert updated.tags == []

    assert await service.delete_permission(test_session, regular.id) is True
    assert await service.delete_permission(test_session, regular.id) is False

    assert await service.get_permission_by_id(
        test_session,
        regular.id,
        include_archived=False,
    ) is None
    archived = await service.get_permission_by_id(
        test_session,
        regular.id,
        include_archived=True,
    )
    assert archived is not None
    assert archived.status == DefinitionStatus.ARCHIVED
    assert (
        await service.get_permission_by_name(
            test_session,
            regular.name,
            include_archived=False,
        )
        is None
    )
