from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from outlabs_auth.models.sql.enums import DefinitionStatus, RoleScope
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role, RoleEntityTypePermission
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.role import RoleService


def _permission(
    name: str,
    *,
    status: DefinitionStatus = DefinitionStatus.ACTIVE,
) -> Permission:
    return Permission(
        name=name,
        display_name=name,
        status=status,
        is_active=status == DefinitionStatus.ACTIVE,
    )


def _role(
    name: str = "manager",
    *,
    status: DefinitionStatus = DefinitionStatus.ACTIVE,
    scope: RoleScope = RoleScope.HIERARCHY,
    scope_entity_id=None,
    assignable_at_types=None,
) -> Role:
    return Role(
        name=name,
        display_name=name.title(),
        is_global=scope_entity_id is None,
        status=status,
        scope=scope,
        scope_entity_id=scope_entity_id,
        assignable_at_types=assignable_at_types or [],
    )


@pytest.mark.unit
def test_permission_service_name_and_allowance_helpers():
    service = PermissionService(SimpleNamespace(enable_context_aware_roles=False))

    assert service._parse_permission_name("user:read") == ("user", "read", None)
    assert service._parse_permission_name("user:read_tree") == ("user", "read", "tree")
    assert service._parse_permission_name("user:read_custom") == (
        "user",
        "read_custom",
        None,
    )
    assert service._parse_permission_name("invalid") == ("invalid", "*", None)

    granted = {"user:*", "role:update_all"}
    assert service._permission_set_allows("user:create", granted) is True
    assert service._permission_set_allows("role:update", granted) is True
    assert service._permission_set_allows("role:update_tree", granted) is True
    assert service._permission_set_allows("role:delete", granted) is False

    ancestor_granted = {"membership:read_tree", "role:update_all"}
    assert (
        service._permission_set_allows_from_ancestor(
            "membership:read",
            ancestor_granted,
        )
        is True
    )
    assert (
        service._permission_set_allows_from_ancestor(
            "membership:read_tree",
            ancestor_granted,
        )
        is True
    )
    assert (
        service._permission_set_allows_from_ancestor(
            "role:update_all",
            ancestor_granted,
        )
        is True
    )
    assert (
        service._permission_set_allows_from_ancestor(
            "role:delete",
            ancestor_granted,
        )
        is False
    )


@pytest.mark.unit
def test_permission_service_role_context_and_cache_helpers():
    config = SimpleNamespace(enable_context_aware_roles=True, enable_caching=True)
    service = PermissionService(config)
    service.cache_service = object()

    active_permission = _permission("task:read")
    override_permission = _permission("task:approve")
    inactive_override = _permission("task:archive", status=DefinitionStatus.INACTIVE)

    role = _role(assignable_at_types=["team"])
    role.permissions = [active_permission]
    role.entity_type_permissions = [
        RoleEntityTypePermission(
            role_id=role.id,
            entity_type="team",
            permission_id=override_permission.id,
            permission=override_permission,
        )
    ]

    role_with_inactive_override = _role(name="reviewer")
    role_with_inactive_override.permissions = [active_permission]
    role_with_inactive_override.entity_type_permissions = [
        RoleEntityTypePermission(
            role_id=role_with_inactive_override.id,
            entity_type="team",
            permission_id=inactive_override.id,
            permission=inactive_override,
        )
    ]

    archived_role = _role(name="archived", status=DefinitionStatus.ARCHIVED)
    archived_role.permissions = [active_permission]
    archived_role.entity_type_permissions = []

    assert PermissionService._role_can_grant_at_entity(
        role,
        uuid4(),
        uuid4(),
        False,
    ) is True

    scope_entity_id = uuid4()
    entity_only_role = _role(
        name="entity-only",
        scope=RoleScope.ENTITY_ONLY,
        scope_entity_id=scope_entity_id,
    )
    assert PermissionService._role_can_grant_at_entity(
        entity_only_role,
        scope_entity_id,
        scope_entity_id,
        True,
    ) is True
    assert PermissionService._role_can_grant_at_entity(
        entity_only_role,
        scope_entity_id,
        uuid4(),
        False,
    ) is False

    assert service._get_role_permissions_for_context(role, "team") == [override_permission]
    assert service._get_role_permissions_for_context(role, "org") == [active_permission]
    assert service._get_role_permissions_for_context(archived_role, "team") == []
    assert service._get_role_permissions_for_context(
        role_with_inactive_override,
        "team",
    ) == []
    assert service._get_role_permission_names_for_context(role, "team") == {"task:approve"}

    assert (
        service._can_use_permission_cache(
            resource_context=None,
            env_context=None,
            time_attrs=None,
            abac_enabled=False,
        )
        is True
    )
    assert (
        service._can_use_permission_cache(
            resource_context={"resource": "doc"},
            env_context=None,
            time_attrs=None,
            abac_enabled=False,
        )
        is False
    )
    assert (
        service._can_use_permission_cache(
            resource_context=None,
            env_context=None,
            time_attrs=None,
            abac_enabled=True,
        )
        is False
    )
    assert service._role_definition_is_live(role) is True
    assert service._role_definition_is_live(archived_role) is False
    assert service._permission_definition_is_live(active_permission) is True
    assert service._permission_definition_is_live(inactive_override) is False


@pytest.mark.unit
def test_role_service_definition_and_delta_helpers():
    service = RoleService(SimpleNamespace())

    active_permission = _permission("task:read")
    archived_permission = _permission(
        "task:archive",
        status=DefinitionStatus.ARCHIVED,
    )
    active_role = _role(assignable_at_types=["team", "team", " org ", ""])
    archived_role = _role(name="archived", status=DefinitionStatus.ARCHIVED)

    assert service._coerce_definition_status("inactive") == DefinitionStatus.INACTIVE
    assert service._role_definition_is_active(active_role) is True
    assert service._role_definition_is_active(archived_role) is False
    assert service._role_definition_is_visible(active_role) is True
    assert service._role_definition_is_visible(archived_role) is False
    assert service._permission_definition_is_assignable(active_permission) is True
    assert service._permission_definition_is_assignable(archived_permission) is False

    assert service._normalize_assignable_at_types(["Team", "team", " org ", ""]) == [
        "team",
        "org",
    ]
    assert service._allows_entity_type(active_role, "TEAM") is True
    assert service._allows_entity_type(active_role, "folder") is False
    assert service._allows_entity_type(_role(name="global"), None) is True

    previous_snapshot = {
        "role_name": "manager",
        "role_display_name": "Manager",
        "role_description": "Before",
        "status": "active",
        "assignable_at_types": ["team"],
        "permission_names": ["task:read"],
    }
    current_snapshot = {
        "role_name": "manager",
        "role_display_name": "Lead",
        "role_description": "After",
        "status": "inactive",
        "assignable_at_types": ["team", "org"],
        "permission_names": ["task:read", "task:update"],
    }

    assert service._changed_role_definition_fields(
        previous_snapshot,
        current_snapshot,
    ) == [
        "role_display_name",
        "role_description",
        "status",
        "assignable_at_types",
    ]
    assert service._permission_name_delta(previous_snapshot, current_snapshot) == (
        ["task:update"],
        [],
    )
    assert service._changed_snapshot_fields(
        previous_snapshot,
        current_snapshot,
        ["role_description", "status", "permission_names"],
    ) == ["role_description", "status", "permission_names"]
