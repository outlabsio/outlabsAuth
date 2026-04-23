from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from outlabs_auth.models.sql.enums import DefinitionStatus, RoleScope
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role, RoleEntityTypePermission
from outlabs_auth.services.permission import PermissionMatcher, PermissionService
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
def test_permission_matcher_matches_all_grammar_variants():
    matcher = PermissionMatcher(
        {
            "user:*",
            "role:update_all",
            "post:publish_tree",
            "comment:read",
        }
    )

    assert matcher.allows("user:create") is True
    assert matcher.allows("user:delete_all") is True
    assert matcher.allows("role:update") is True
    assert matcher.allows("role:update_tree") is True
    assert matcher.allows("role:update_all") is True
    assert matcher.allows("post:publish") is True
    assert matcher.allows("post:publish_tree") is True
    assert matcher.allows("post:publish_all") is False
    assert matcher.allows("comment:read") is True
    assert matcher.allows("comment:write") is False
    assert matcher.allows("team:edit") is False


@pytest.mark.unit
def test_permission_matcher_super_grant_short_circuits():
    matcher = PermissionMatcher({"*:*"})

    assert matcher.allows("anything:goes") is True
    assert matcher.allows_from_ancestor("deep:tree") is True


@pytest.mark.unit
def test_permission_matcher_empty_set_denies_everything():
    matcher = PermissionMatcher(set())

    assert matcher.allows("user:read") is False
    assert matcher.allows_from_ancestor("user:read") is False


@pytest.mark.unit
def test_permission_matcher_ancestor_only_propagates_tree_and_all():
    matcher = PermissionMatcher({"membership:read_tree", "role:update_all"})

    # tree or all upstream satisfies both non-scoped and _tree requireds
    assert matcher.allows_from_ancestor("membership:read") is True
    assert matcher.allows_from_ancestor("membership:read_tree") is True
    assert matcher.allows_from_ancestor("role:update") is True
    assert matcher.allows_from_ancestor("role:update_tree") is True
    # _all requireds only match an upstream _all grant
    assert matcher.allows_from_ancestor("role:update_all") is True
    assert matcher.allows_from_ancestor("membership:read_all") is False
    # Non-tree/non-all grants never propagate
    assert matcher.allows_from_ancestor("other:thing") is False


@pytest.mark.unit
def test_permission_matcher_ignores_non_permission_strings():
    # Entries without ':' or with empty values should not crash or match stray requireds.
    matcher = PermissionMatcher({"", "not_a_permission", "user:read"})

    assert matcher.allows("user:read") is True
    assert matcher.allows("not_a_permission") is True  # exact-match passthrough
    assert matcher.allows("something:else") is False


@pytest.mark.unit
def test_permission_matcher_agrees_with_permission_service_helpers():
    granted = {"user:*", "role:update_all", "post:publish_tree", "comment:read"}
    ancestor_granted = {"membership:read_tree", "role:update_all"}

    requireds = [
        "user:create",
        "role:update",
        "role:update_tree",
        "role:update_all",
        "post:publish",
        "post:publish_all",
        "comment:read",
        "comment:write",
        "team:edit",
    ]

    matcher = PermissionMatcher(granted)
    ancestor_matcher = PermissionMatcher(ancestor_granted)
    for required in requireds:
        assert matcher.allows(required) == PermissionService._permission_set_allows(
            required, granted
        )
        assert ancestor_matcher.allows_from_ancestor(
            required
        ) == PermissionService._permission_set_allows_from_ancestor(
            required, ancestor_granted
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

    assert service._can_use_permission_cache() is True

    # Non-ABAC calls never add a context hash — resource/env/time context
    # does not affect the non-ABAC evaluation path.
    assert (
        service._permission_cache_context_hash(
            abac_enabled=False,
            resource_context={"resource": "doc"},
            env_context=None,
            time_attrs=None,
        )
        is None
    )

    # ABAC calls produce a stable short hash derived from all three contexts.
    abac_hash = service._permission_cache_context_hash(
        abac_enabled=True,
        resource_context={"resource": "doc"},
        env_context={"method": "GET"},
        time_attrs=None,
    )
    assert isinstance(abac_hash, str) and len(abac_hash) == 16
    # Same inputs → same hash (deterministic).
    assert abac_hash == service._permission_cache_context_hash(
        abac_enabled=True,
        resource_context={"resource": "doc"},
        env_context={"method": "GET"},
        time_attrs=None,
    )
    # Different inputs → different hash.
    assert abac_hash != service._permission_cache_context_hash(
        abac_enabled=True,
        resource_context={"resource": "doc"},
        env_context={"method": "POST"},
        time_attrs=None,
    )
    assert service._role_definition_is_live(role) is True
    assert service._role_definition_is_live(archived_role) is False
    assert service._permission_definition_is_live(active_permission) is True
    assert service._permission_definition_is_live(inactive_override) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permission_service_resolve_context_entity_type_dedupes_within_request():
    from outlabs_auth.services import request_cache

    service = PermissionService(SimpleNamespace(enable_context_aware_roles=True))
    entity_id = uuid4()
    entity = SimpleNamespace(entity_type="team")

    class FakeSession:
        def __init__(self):
            self.calls = 0

        async def get(self, model, key):
            self.calls += 1
            return entity if key == entity_id else None

    session = FakeSession()
    request_cache.reset()

    # First call loads from the session and populates the cache.
    first = await service._resolve_context_entity_type(session, entity_id)
    # Second call must reuse the cached Entity — the session is not touched again.
    second = await service._resolve_context_entity_type(session, entity_id)

    assert first == second == "team"
    assert session.calls == 1
    assert request_cache.get(("entity", entity_id)) is entity

    # Short-circuits: no entity, or context-aware roles disabled.
    assert await service._resolve_context_entity_type(session, None) is None
    disabled = PermissionService(SimpleNamespace(enable_context_aware_roles=False))
    assert await disabled._resolve_context_entity_type(session, entity_id) is None
    assert session.calls == 1  # still one — neither short-circuit touched the session

    request_cache.reset()


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
