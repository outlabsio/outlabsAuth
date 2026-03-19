from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import APIKeyStatus, EntityClass
from outlabs_auth.services.api_key import APIKeyService
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
