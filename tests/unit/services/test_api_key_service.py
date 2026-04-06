from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import (
    APIKeyKind,
    APIKeyStatus,
    EntityClass,
    IntegrationPrincipalScopeKind,
    IntegrationPrincipalStatus,
    UserStatus,
)
from outlabs_auth.models.sql.integration_principal import IntegrationPrincipal
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.api_key_policy import APIKeyPolicyService
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.integration_principal import IntegrationPrincipalService
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.role import RoleService
from outlabs_auth.services.user import UserService


class FakeRedis:
    def __init__(self) -> None:
        self.is_available = True
        self.rate_limit_counts: dict[str, int] = {}
        self.counters: dict[str, int] = {}
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []

    async def increment_with_ttl(self, key: str, amount: int = 1, ttl: int | None = None):
        return self.rate_limit_counts.get(key, 0)

    async def get_all_counters(self, pattern: str):
        return dict(self.counters)

    async def get(self, key: str):
        return self.values.get(key)

    async def delete(self, key: str):
        self.deleted.append(key)
        self.counters.pop(key, None)
        self.values.pop(key, None)
        return True


def _entity(*, name: str, slug: str, parent_id=None, depth: int = 0, path: str | None = None) -> Entity:
    return Entity(
        name=name,
        display_name=name.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization" if parent_id is None else "team",
        parent_id=parent_id,
        depth=depth,
        path=path or f"/{slug}/",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_service_scope_ip_update_and_delete_helpers(
    test_session,
    auth_config: AuthConfig,
):
    user_service = UserService(config=auth_config)
    service = APIKeyService(config=auth_config)

    owner = await user_service.create_user(
        test_session,
        email="api-key-owner@example.com",
        password="TestPass123!",
        first_name="API",
        last_name="Owner",
    )

    _, key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Managed Key",
        scopes=["user:*"],
        ip_whitelist=["10.0.0.1"],
    )
    _, unrestricted = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Unrestricted Key",
    )

    assert APIKeyService.scopes_allow_permission(["user:*"], "user:read") is True
    assert APIKeyService.scopes_allow_permission(["*"], "role:update") is True
    assert APIKeyService.scopes_allow_permission(["user:read_tree"], "user:read") is True
    assert APIKeyService.scopes_allow_permission(None, "role:update") is True
    assert APIKeyService.scopes_allow_permission(["user:read"], "role:update") is False

    assert await service._check_scope(test_session, key.id, "user:read") is True
    assert await service._check_scope(test_session, key.id, "role:read") is False
    assert await service._check_scope(test_session, unrestricted.id, "role:read") is True

    assert await service._check_ip(test_session, key.id, "10.0.0.1") is True
    assert await service._check_ip(test_session, key.id, "10.0.0.2") is False
    assert await service._check_ip(test_session, unrestricted.id, "10.0.0.2") is True

    updated = await service.update_api_key(
        test_session,
        key.id,
        name="Updated Key",
        description="updated description",
        status=APIKeyStatus.REVOKED,
        scopes=["role:read"],
        ip_whitelist=["192.168.0.10"],
        entity_id=None,
    )
    assert updated is not None
    assert updated.name == "Updated Key"
    assert updated.description == "updated description"
    assert updated.status == APIKeyStatus.REVOKED
    assert await service.get_api_key_scopes(test_session, key.id) == ["role:read"]
    assert await service.get_api_key_ip_whitelist(test_session, key.id) == ["192.168.0.10"]

    assert await service.delete_api_key(test_session, key.id) is True
    assert await service.delete_api_key(test_session, key.id) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_service_tree_access_rate_limits_and_counter_sync(
    test_session,
    auth_config: AuthConfig,
):
    user_service = UserService(config=auth_config)
    fake_redis = FakeRedis()
    service = APIKeyService(config=auth_config, redis_client=fake_redis)

    owner = await user_service.create_user(
        test_session,
        email="api-tree-owner@example.com",
        password="TestPass123!",
        first_name="Tree",
        last_name="Owner",
    )

    root = _entity(name="root", slug="root")
    team = _entity(name="team", slug="team", parent_id=root.id, depth=1, path="/root/team/")
    other = _entity(name="other", slug="other")
    test_session.add(root)
    test_session.add(team)
    test_session.add(other)
    await test_session.flush()

    test_session.add_all(
        [
            EntityClosure(ancestor_id=root.id, descendant_id=root.id, depth=0),
            EntityClosure(ancestor_id=team.id, descendant_id=team.id, depth=0),
            EntityClosure(ancestor_id=other.id, descendant_id=other.id, depth=0),
            EntityClosure(ancestor_id=root.id, descendant_id=team.id, depth=1),
        ]
    )
    await test_session.flush()

    _, tree_key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Tree Key",
        entity_id=root.id,
        inherit_from_tree=True,
    )
    _, global_key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Global Key",
    )

    assert await service.check_entity_access_with_tree(test_session, global_key, team.id) is True
    assert await service.check_entity_access_with_tree(test_session, tree_key, root.id) is True
    assert await service.check_entity_access_with_tree(test_session, tree_key, team.id) is True
    assert await service.check_entity_access_with_tree(test_session, tree_key, other.id) is False

    minute_limited = SimpleNamespace(
        id=tree_key.id,
        rate_limit_per_minute=1,
        rate_limit_per_hour=None,
        rate_limit_per_day=None,
    )
    hour_limited = SimpleNamespace(
        id=tree_key.id,
        rate_limit_per_minute=None,
        rate_limit_per_hour=2,
        rate_limit_per_day=None,
    )
    day_limited = SimpleNamespace(
        id=tree_key.id,
        rate_limit_per_minute=None,
        rate_limit_per_hour=None,
        rate_limit_per_day=3,
    )

    minute_key = service._make_rate_limit_key(str(tree_key.id), "minute")
    hour_key = service._make_rate_limit_key(str(tree_key.id), "hour")
    day_key = service._make_rate_limit_key(str(tree_key.id), "day")

    fake_redis.rate_limit_counts = {minute_key: 2}
    with pytest.raises(InvalidInputError, match="per minute"):
        await service._check_rate_limits(minute_limited)

    fake_redis.rate_limit_counts = {hour_key: 3}
    with pytest.raises(InvalidInputError, match="per hour"):
        await service._check_rate_limits(hour_limited)

    fake_redis.rate_limit_counts = {day_key: 4}
    with pytest.raises(InvalidInputError, match="per day"):
        await service._check_rate_limits(day_limited)

    good_counter = service._make_usage_counter_key(str(global_key.id))
    bad_counter = service._make_usage_counter_key("not-a-uuid")
    last_used_key = service._make_last_used_key(str(global_key.id))
    fake_redis.counters = {
        good_counter: 3,
        bad_counter: 5,
    }
    fake_redis.values = {
        last_used_key: datetime.now(timezone.utc).isoformat(),
    }

    stats = await service.sync_usage_counters_to_db(test_session)
    assert stats == {"synced_keys": 1, "total_usage": 3, "errors": 1}

    refreshed = await service.get_api_key(test_session, global_key.id)
    assert refreshed is not None
    assert refreshed.usage_count == 3
    assert refreshed.last_used_at is not None
    assert good_counter in fake_redis.deleted


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_policy_enforces_enterprise_personal_key_rules_and_runtime_state(
    test_session,
):
    enterprise_config = AuthConfig(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
    )
    user_service = UserService(config=enterprise_config)
    policy_service = APIKeyPolicyService(config=enterprise_config)
    service = APIKeyService(config=enterprise_config, policy_service=policy_service)

    owner = await user_service.create_user(
        test_session,
        email="enterprise-api-owner@example.com",
        password="TestPass123!",
        first_name="Enterprise",
        last_name="Owner",
    )
    root = _entity(name="enterprise-root", slug="enterprise-root")
    test_session.add(root)
    await test_session.flush()
    owner.root_entity_id = root.id
    await test_session.flush()

    with pytest.raises(InvalidInputError, match="inherit_from_tree requires an entity anchor"):
        await service.create_api_key(
            test_session,
            owner_id=owner.id,
            name="Tree Without Anchor",
            scopes=["user:read"],
            inherit_from_tree=True,
        )

    with pytest.raises(InvalidInputError, match="explicit scope"):
        await service.create_api_key(
            test_session,
            owner_id=owner.id,
            name="Missing Scope",
            entity_id=root.id,
        )

    full_key, key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Personal Enterprise Key",
        scopes=["user:read"],
    )
    assert key.key_kind == APIKeyKind.PERSONAL
    assert key.entity_id is None

    owner.status = UserStatus.SUSPENDED
    await test_session.flush()
    suspended_key, _ = await service.verify_api_key(test_session, full_key)
    assert suspended_key is None

    owner.status = UserStatus.ACTIVE
    anchored_full_key, _ = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Anchored Enterprise Key",
        scopes=["user:read"],
        entity_id=root.id,
    )
    root.status = "archived"
    await test_session.flush()

    still_valid_key, _ = await service.verify_api_key(test_session, full_key)
    assert still_valid_key is not None

    archived_anchor_key, _ = await service.verify_api_key(test_session, anchored_full_key)
    assert archived_anchor_key is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_service_can_revoke_keys_for_an_archived_entity(
    test_session,
    auth_config: AuthConfig,
):
    user_service = UserService(config=auth_config)
    service = APIKeyService(config=auth_config)

    owner = await user_service.create_user(
        test_session,
        email="entity-revoke-owner@example.com",
        password="TestPass123!",
        first_name="Entity",
        last_name="Owner",
    )

    root = _entity(name="entity-revoke-root", slug="entity-revoke-root")
    other = _entity(name="entity-revoke-other", slug="entity-revoke-other")
    test_session.add(root)
    test_session.add(other)
    await test_session.flush()

    _, anchored_key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Anchored Key",
        scopes=["user:read"],
        entity_id=root.id,
    )
    _, other_key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Other Anchored Key",
        scopes=["user:read"],
        entity_id=other.id,
    )
    _, global_key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Global Key",
        scopes=["user:read"],
    )

    revoked = await service.revoke_entity_api_keys(
        test_session,
        root.id,
        reason="Entity archived",
    )

    assert revoked == 1
    assert anchored_key.status == APIKeyStatus.REVOKED
    assert other_key.status == APIKeyStatus.ACTIVE
    assert global_key.status == APIKeyStatus.ACTIVE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_service_emits_observability_for_lifecycle_and_runtime_denials(
    test_session,
    auth_config: AuthConfig,
):
    observability = SimpleNamespace(
        log_api_key_lifecycle=Mock(),
        log_api_key_validated=Mock(),
        log_api_key_policy_decision=Mock(),
        log_api_key_rate_limited=Mock(),
    )
    user_service = UserService(config=auth_config)
    service = APIKeyService(config=auth_config, observability=observability)

    owner = await user_service.create_user(
        test_session,
        email="observability-owner@example.com",
        password="TestPass123!",
        first_name="Observability",
        last_name="Owner",
    )

    full_key, key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Observable Key",
        scopes=["user:read"],
    )
    assert observability.log_api_key_lifecycle.call_args_list[0].kwargs["operation"] == "created"
    assert observability.log_api_key_lifecycle.call_args_list[0].kwargs["prefix"] == key.prefix

    invalid_key, _ = await service.verify_api_key(test_session, "bad-key")
    assert invalid_key is None
    assert observability.log_api_key_validated.call_args_list[-1].kwargs["reason"] == "invalid_format"

    await service.revoke_api_key(test_session, key.id, reason="test revoke")
    assert any(call.kwargs["operation"] == "revoked" for call in observability.log_api_key_lifecycle.call_args_list)

    valid_key, _ = await service.verify_api_key(test_session, full_key)
    assert valid_key is None
    assert observability.log_api_key_validated.call_args_list[-1].kwargs["reason"] == "status_revoked"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_policy_evaluates_current_effectiveness_after_owner_permission_loss(
    test_session,
):
    enterprise_config = AuthConfig(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
    )
    user_service = UserService(config=enterprise_config)
    permission_service = PermissionService(config=enterprise_config)
    role_service = RoleService(config=enterprise_config)
    membership_service = MembershipService(config=enterprise_config)
    policy_service = APIKeyPolicyService(
        config=enterprise_config,
        permission_service=permission_service,
    )
    service = APIKeyService(config=enterprise_config, policy_service=policy_service)

    owner = await user_service.create_user(
        test_session,
        email="effectiveness-owner@example.com",
        password="TestPass123!",
        first_name="Effectiveness",
        last_name="Owner",
    )
    root = _entity(name="effectiveness-root", slug="effectiveness-root")
    test_session.add(root)
    await test_session.flush()
    owner.root_entity_id = root.id
    test_session.add(EntityClosure(ancestor_id=root.id, descendant_id=root.id, depth=0))
    await test_session.flush()

    permission = await permission_service.create_permission(
        test_session,
        name="contacts:read",
        display_name="contacts:read",
        description="Effectiveness test permission",
    )
    role = await role_service.create_role(
        session=test_session,
        name="effectiveness-role",
        display_name="Effectiveness Role",
        is_global=False,
        root_entity_id=root.id,
    )
    await role_service.add_permissions(test_session, role.id, [permission.id], changed_by_id=owner.id)
    await membership_service.add_member(
        session=test_session,
        entity_id=root.id,
        user_id=owner.id,
        role_ids=[role.id],
        joined_by_id=owner.id,
    )

    _, api_key = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Effective Key",
        scopes=["contacts:read"],
        entity_id=root.id,
    )

    effective = await policy_service.evaluate_effectiveness(
        test_session,
        api_key=api_key,
        scopes=["contacts:read"],
    )
    assert effective.is_currently_effective is True
    assert effective.ineffective_reasons == []

    await role_service.remove_permissions(test_session, role.id, [permission.id], changed_by_id=owner.id)

    ineffective = await policy_service.evaluate_effectiveness(
        test_session,
        api_key=api_key,
        scopes=["contacts:read"],
    )
    assert ineffective.is_currently_effective is False
    assert ineffective.ineffective_reasons == ["no_effective_scopes"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_policy_and_service_emit_observability_for_enterprise_denials(
    test_session,
):
    observability = SimpleNamespace(
        log_api_key_lifecycle=Mock(),
        log_api_key_validated=Mock(),
        log_api_key_policy_decision=Mock(),
        log_api_key_rate_limited=Mock(),
    )
    enterprise_config = AuthConfig(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
    )
    user_service = UserService(config=enterprise_config)
    policy_service = APIKeyPolicyService(config=enterprise_config, observability=observability)
    service = APIKeyService(
        config=enterprise_config,
        policy_service=policy_service,
        observability=observability,
    )

    owner = await user_service.create_user(
        test_session,
        email="enterprise-observability-owner@example.com",
        password="TestPass123!",
        first_name="Enterprise",
        last_name="Observability",
    )
    root = _entity(name="enterprise-observability-root", slug="enterprise-observability-root")
    test_session.add(root)
    await test_session.flush()
    owner.root_entity_id = root.id
    await test_session.flush()

    with pytest.raises(InvalidInputError, match="inherit_from_tree requires an entity anchor"):
        await service.create_api_key(
            test_session,
            owner_id=owner.id,
            name="Tree Without Anchor",
            scopes=["user:read"],
            inherit_from_tree=True,
        )

    assert observability.log_api_key_policy_decision.call_args_list[-1].kwargs["surface"] == "grant_create"
    assert observability.log_api_key_policy_decision.call_args_list[-1].kwargs["reason"] == "inherit_from_tree_requires_anchor"

    full_key, _ = await service.create_api_key(
        test_session,
        owner_id=owner.id,
        name="Valid Enterprise Key",
        scopes=["user:read"],
    )
    owner.status = UserStatus.SUSPENDED
    await test_session.flush()

    denied, _ = await service.verify_api_key(test_session, full_key)
    assert denied is None
    assert observability.log_api_key_policy_decision.call_args_list[-1].kwargs["surface"] == "runtime_use"
    assert observability.log_api_key_policy_decision.call_args_list[-1].kwargs["reason"] == "owner_inactive"
    assert observability.log_api_key_validated.call_args_list[-1].kwargs["reason"] == "runtime_use_denied"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_system_integration_keys_follow_principal_scope_and_entity_archive(
    test_session,
):
    enterprise_config = AuthConfig(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
    )
    permission_service = PermissionService(config=enterprise_config)
    policy_service = APIKeyPolicyService(config=enterprise_config)
    api_key_service = APIKeyService(config=enterprise_config, policy_service=policy_service)
    principal_service = IntegrationPrincipalService(config=enterprise_config, policy_service=policy_service)
    entity_service = EntityService(config=enterprise_config)
    principal_service.api_key_service = api_key_service
    entity_service.api_key_service = api_key_service
    entity_service.integration_principal_service = principal_service
    user_service = UserService(config=enterprise_config)

    actor = await user_service.create_user(
        test_session,
        email="system-integration-actor@example.com",
        password="TestPass123!",
        first_name="System",
        last_name="Actor",
    )
    root = await entity_service.create_entity(
        session=test_session,
        name="system_integration_root",
        display_name="System Integration Root",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    child = await entity_service.create_entity(
        session=test_session,
        name="system_integration_child",
        display_name="System Integration Child",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=root.id,
    )
    actor.root_entity_id = root.id
    await test_session.flush()

    await permission_service.create_permission(
        test_session,
        name="workers:run",
        display_name="workers:run",
        description="system integration test permission",
    )
    await permission_service.create_permission(
        test_session,
        name="reports:update",
        display_name="reports:update",
        description="system integration test permission",
    )

    principal = await principal_service.create_principal(
        test_session,
        name="Worker Principal",
        description="owns worker automation keys",
        scope_kind=IntegrationPrincipalScopeKind.ENTITY,
        anchor_entity_id=root.id,
        inherit_from_tree=True,
        allowed_scopes=["workers:run"],
        created_by_user_id=actor.id,
    )
    assert principal.status == IntegrationPrincipalStatus.ACTIVE

    full_key, api_key = await api_key_service.create_api_key(
        test_session,
        integration_principal_id=principal.id,
        name="Worker Key",
        scopes=["workers:run"],
        key_kind=APIKeyKind.SYSTEM_INTEGRATION,
        actor_user_id=actor.id,
    )
    assert api_key.owner_id is None
    assert api_key.integration_principal_id == principal.id
    assert api_key.entity_id == root.id
    assert api_key.inherit_from_tree is True

    verified, _ = await api_key_service.verify_api_key(
        test_session,
        full_key,
        required_scope="workers:run",
        entity_id=child.id,
    )
    assert verified is not None

    updated_principal = await principal_service.update_principal(
        test_session,
        principal.id,
        actor_user_id=actor.id,
        allowed_scopes=["reports:update"],
    )
    assert updated_principal is not None
    denied, _ = await api_key_service.verify_api_key(
        test_session,
        full_key,
        required_scope="workers:run",
        entity_id=child.id,
    )
    assert denied is None

    await entity_service.delete_entity(
        test_session,
        root.id,
        cascade=True,
        deleted_by_id=actor.id,
    )
    refreshed_principal = await principal_service.get_principal(test_session, principal.id)
    refreshed_key = await api_key_service.get_api_key(test_session, api_key.id)
    assert refreshed_principal is not None
    assert refreshed_principal.status == IntegrationPrincipalStatus.ARCHIVED
    assert refreshed_key is not None
    assert refreshed_key.status == APIKeyStatus.REVOKED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_integration_principal_service_denies_cross_root_creation(
    test_session,
):
    enterprise_config = AuthConfig(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
    )
    entity_service = EntityService(config=enterprise_config)
    policy_service = APIKeyPolicyService(config=enterprise_config)
    principal_service = IntegrationPrincipalService(config=enterprise_config, policy_service=policy_service)
    permission_service = PermissionService(config=enterprise_config)
    user_service = UserService(config=enterprise_config)

    root_a = await entity_service.create_entity(
        session=test_session,
        name="cross_root_a",
        display_name="Cross Root A",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    root_b = await entity_service.create_entity(
        session=test_session,
        name="cross_root_b",
        display_name="Cross Root B",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization",
    )
    actor = await user_service.create_user(
        test_session,
        email="cross-root-actor@example.com",
        password="TestPass123!",
        first_name="Cross",
        last_name="Root",
        root_entity_id=root_b.id,
    )
    await permission_service.create_permission(
        test_session,
        name="workers:run",
        display_name="workers:run",
        description="cross root validation permission",
    )

    with pytest.raises(InvalidInputError, match="root entity"):
        await principal_service.create_principal(
            test_session,
            name="Denied Principal",
            description="should not be created cross-root",
            scope_kind=IntegrationPrincipalScopeKind.ENTITY,
            anchor_entity_id=root_a.id,
            inherit_from_tree=False,
            allowed_scopes=["workers:run"],
            created_by_user_id=actor.id,
        )


@pytest.mark.unit
def test_integration_principal_model_normalizes_string_backed_enum_fields():
    principal = IntegrationPrincipal(
        name="String Backed Principal",
        description="simulates ORM-loaded raw string enum fields",
        scope_kind=IntegrationPrincipalScopeKind.ENTITY,
        allowed_scopes=["entity:read_tree"],
    )
    principal.status = "active"
    principal.scope_kind = "platform_global"

    assert principal.status_enum == IntegrationPrincipalStatus.ACTIVE
    assert principal.scope_kind_enum == IntegrationPrincipalScopeKind.PLATFORM_GLOBAL
    assert principal.is_active() is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_integration_principal_service_logs_platform_global_creation_with_observability(
    test_session,
):
    enterprise_config = AuthConfig(
        database_url="postgresql+asyncpg://example:example@localhost:5432/test",
        secret_key="test-secret",
        enable_entity_hierarchy=True,
    )
    observability = Mock(log_api_key_lifecycle=Mock())
    permission_service = PermissionService(config=enterprise_config)
    policy_service = APIKeyPolicyService(config=enterprise_config)
    principal_service = IntegrationPrincipalService(
        config=enterprise_config,
        policy_service=policy_service,
        observability=observability,
    )
    user_service = UserService(config=enterprise_config)

    actor = await user_service.create_user(
        test_session,
        email="platform-global-actor@example.com",
        password="TestPass123!",
        first_name="Platform",
        last_name="Global",
        is_superuser=True,
    )
    await permission_service.create_permission(
        test_session,
        name="entity:read_tree",
        display_name="Entity Read Tree",
        description="platform global integration scope",
    )

    principal = await principal_service.create_principal(
        test_session,
        name="Global Export Worker",
        description="owns global export credentials",
        scope_kind=IntegrationPrincipalScopeKind.PLATFORM_GLOBAL,
        anchor_entity_id=None,
        inherit_from_tree=False,
        allowed_scopes=["entity:read_tree"],
        created_by_user_id=actor.id,
    )

    assert principal.scope_kind_enum == IntegrationPrincipalScopeKind.PLATFORM_GLOBAL
    assert principal.status_enum == IntegrationPrincipalStatus.ACTIVE
    observability.log_api_key_lifecycle.assert_called_once()
    assert observability.log_api_key_lifecycle.call_args.kwargs["status"] == "active"
    assert observability.log_api_key_lifecycle.call_args.kwargs["scope_kind"] == "platform_global"
