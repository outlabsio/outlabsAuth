from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus, EntityClass, UserStatus
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.api_key_policy import APIKeyPolicyService
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

    with pytest.raises(InvalidInputError, match="entity anchor"):
        await service.create_api_key(
            test_session,
            owner_id=owner.id,
            name="Missing Anchor",
            scopes=["user:read"],
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
        entity_id=root.id,
    )
    assert key.key_kind == APIKeyKind.PERSONAL

    owner.status = UserStatus.SUSPENDED
    await test_session.flush()
    suspended_key, _ = await service.verify_api_key(test_session, full_key)
    assert suspended_key is None

    owner.status = UserStatus.ACTIVE
    root.status = "archived"
    await test_session.flush()
    archived_anchor_key, _ = await service.verify_api_key(test_session, full_key)
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
