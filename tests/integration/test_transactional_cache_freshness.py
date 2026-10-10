"""Deterministic B1/B2 regressions with real transactions and cache backends."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus, IntegrationPrincipalScopeKind
from outlabs_auth.models.sql.integration_principal import IntegrationPrincipal
from outlabs_auth.authentication.strategy import ApiKeyStrategy
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.services import request_cache
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.api_key_policy import APIKeyPolicyService
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.cache_backend import MemoryCacheBackend
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.user import UserService
from outlabs_auth.services.entity import EntityService


@pytest.fixture(params=["memory", "redis"])
def cache_kind(request):
    return request.param


@pytest.fixture
def cache_backend(cache_kind, redis_client, auth_config):
    if cache_kind == "memory":
        config = auth_config.model_copy(update={"redis_key_prefix": f"race-{uuid4().hex}"})
        return MemoryCacheBackend(config)
    return redis_client


async def seed_member(session, *, active):
    entity = Entity(
        name="Customer",
        display_name="Customer",
        slug=f"customer-{uuid4().hex}",
        entity_type="organization",
        entity_class=EntityClass.STRUCTURAL,
        status="active",
        depth=0,
    )
    entity.update_path(None)
    session.add(entity)
    await session.flush()
    session.add(EntityClosure(ancestor_id=entity.id, descendant_id=entity.id, depth=0))
    user = User(email=f"member-{uuid4().hex}@example.test", root_entity_id=entity.id)
    permission = Permission(name="report:read", display_name="Read reports")
    role = Role(name=f"reader-{uuid4().hex}", display_name="Reader", permissions=[permission])
    session.add_all([user, role])
    await session.flush()
    member = EntityMembership(
        user_id=user.id,
        entity_id=entity.id,
        roles=[role],
        status=MembershipStatus.ACTIVE if active else MembershipStatus.SUSPENDED,
    )
    session.add(member)
    await session.commit()
    return user.id, entity.id


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("active", [True, False], ids=["revoke", "grant"])
@pytest.mark.parametrize("commit", [True, False], ids=["commit", "rollback"])
async def test_membership_authority_stays_private_until_commit(
    test_engine,
    test_session,
    auth_config,
    cache_backend,
    active,
    commit,
):
    user_id, entity_id = await seed_member(test_session, active=active)
    config = auth_config.model_copy(update={"enable_entity_hierarchy": True, "enable_caching": True})
    cache = CacheService(cache_backend, config)
    permissions = PermissionService(config)
    permissions.cache_service = cache
    memberships = MembershipService(config)
    memberships.cache_service = cache
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def read(session):
        request_cache.reset()
        return await permissions.check_permission(session, user_id, "report:read", entity_id=entity_id)

    try:
        async with factory() as reader:
            assert await read(reader) is active
        before = await cache.get_api_key_auth_snapshot_versions(user_id=str(user_id))
        async with factory() as writer:
            method = memberships.suspend_membership if active else memberships.reactivate_membership
            await method(writer, entity_id=entity_id, user_id=user_id)
            assert await cache.get_api_key_auth_snapshot_versions(user_id=str(user_id)) == before
            assert await read(writer) is not active  # Own writes must bypass shared caches.
            async with factory() as reader:
                assert await read(reader) is active  # Uncommitted authority cannot leak out.
            if commit:
                await writer.commit()
            else:
                await writer.rollback()
        after = await cache.get_api_key_auth_snapshot_versions(user_id=str(user_id))
        assert after[f"user:{user_id}"] == before[f"user:{user_id}"] + int(commit)
        async with factory() as reader:
            assert await read(reader) is (not active if commit else active)
    finally:
        request_cache.reset()


def auth_context():
    user_id = uuid4()
    raw_key = "oak_" + uuid4().hex + uuid4().hex
    key = SimpleNamespace(
        id=uuid4(),
        key_hash=APIKey.hash_key(raw_key),
        prefix=raw_key[:16],
        owner_type="user",
        resolved_owner_id=user_id,
        entity_id=None,
        expires_at=None,
        status="active",
        key_kind="personal",
        inherit_from_tree=False,
        rate_limit_per_minute=None,
        rate_limit_per_hour=None,
        rate_limit_per_day=None,
    )
    result = {
        "source": "api_key",
        "user_id": str(user_id),
        "api_key": key,
        "metadata": {"owner_type": "user", "owner_id": str(user_id), "scopes": ["report:read"]},
    }
    return raw_key, key, result


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_scope", ["user", "credential"])
async def test_stale_snapshot_cannot_be_relabelled_with_new_versions(
    auth_config,
    cache_backend,
    changed_scope,
):
    config = auth_config.model_copy(update={"enable_caching": True})
    cache = CacheService(cache_backend, config)
    service = APIKeyService(config, redis_client=cache_backend)
    service.cache_service = cache
    raw_key, key, result = auth_context()
    observed = await cache.get_api_key_auth_snapshot_versions(user_id=result["user_id"])
    observed[f"credential:{key.key_hash}"] = 0
    result["_outlabs_snapshot_versions"] = observed
    # A paused reader already computed the old authority; the writer revokes it.
    subject = result["user_id"] if changed_scope == "user" else key.key_hash
    await cache.bump_api_key_auth_snapshot_version(changed_scope, subject)
    await service.set_api_key_auth_snapshot(raw_key, auth_result=result, effective_permissions=["report:read"])
    assert await service.get_api_key_auth_snapshot(raw_key) is None


@pytest.mark.asyncio
async def test_snapshot_without_pre_authority_observation_is_not_cached(auth_config, cache_backend):
    service = APIKeyService(auth_config.model_copy(update={"enable_caching": True}), redis_client=cache_backend)
    service.cache_service = CacheService(cache_backend, service.config)
    raw_key, _key, result = auth_context()
    assert (
        await service.set_api_key_auth_snapshot(raw_key, auth_result=result, effective_permissions=["report:read"])
        is False
    )


@pytest.mark.asyncio
async def test_credential_revocation_during_first_db_read_fences_strategy_snapshot(
    test_engine,
    test_session,
    auth_config,
    cache_backend,
    redis_client,
    monkeypatch,
):
    """The real auth strategy must retain versions from before its DB reads."""
    config = auth_config.model_copy(update={"enable_caching": True})
    cache = CacheService(cache_backend, config)
    service = APIKeyService(config, redis_client=redis_client)
    service.cache_service = cache
    user = User(email=f"key-owner-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.flush()
    raw_key = "oak_" + uuid4().hex + uuid4().hex
    key = APIKey(
        name="Paused authentication",
        prefix=raw_key[:16],
        key_hash=APIKey.hash_key(raw_key),
        owner_id=user.id,
    )
    test_session.add(key)
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    get_one = service.get_one

    async def pause_after_key_read(session, *filters, **kwargs):
        old_key = await get_one(session, *filters, **kwargs)
        async with factory() as writer:
            assert await service.revoke_api_key(writer, key.id)
            await writer.commit()
        return old_key

    monkeypatch.setattr(service, "get_one", pause_after_key_read)
    async with factory() as reader:
        result = await ApiKeyStrategy().authenticate(
            raw_key,
            session=reader,
            api_key_service=service,
            user_service=UserService(config),
        )
        assert result is not None
        assert result["_outlabs_snapshot_versions"][f"credential:{key.key_hash}"] == 0
        await service.set_api_key_auth_snapshot(raw_key, auth_result=result, effective_permissions=[])
    assert await service.get_api_key_auth_snapshot(raw_key) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["revoke", "delete", "update"])
@pytest.mark.parametrize("commit", [True, False])
async def test_key_mutations_only_invalidate_committed_authority(
    test_engine,
    test_session,
    auth_config,
    cache_backend,
    operation,
    commit,
):
    config = auth_config.model_copy(update={"enable_caching": True})
    service = APIKeyService(config, redis_client=cache_backend)
    cache = CacheService(cache_backend, config)
    service.cache_service = cache
    user = User(email=f"key-mutation-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.flush()
    raw_key, _key, result = auth_context()
    key = APIKey(name="Lifecycle fixture", prefix=raw_key[:16], key_hash=APIKey.hash_key(raw_key), owner_id=user.id)
    test_session.add(key)
    await test_session.commit()
    result.update(user_id=str(user.id), api_key=key)
    result["metadata"]["owner_id"] = str(user.id)
    before = await cache.get_api_key_auth_snapshot_versions(user_id=str(user.id), credential_hash=key.key_hash)
    result["_outlabs_snapshot_versions"] = before
    assert await service.set_api_key_auth_snapshot(raw_key, auth_result=result, effective_permissions=["report:read"])
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as writer:
        if operation == "revoke":
            assert await service.revoke_api_key(writer, key.id)
        elif operation == "delete":
            assert await service.delete_api_key(writer, key.id)
        else:
            assert await service.update_api_key(writer, key.id, scopes=[])
        assert (
            await cache.get_api_key_auth_snapshot_versions(user_id=str(user.id), credential_hash=key.key_hash) == before
        )
        assert await service.get_api_key_auth_snapshot(raw_key) is not None
        await (writer.commit() if commit else writer.rollback())
    after = await cache.get_api_key_auth_snapshot_versions(user_id=str(user.id), credential_hash=key.key_hash)
    assert after[f"credential:{key.key_hash}"] == before[f"credential:{key.key_hash}"] + int(commit)
    assert (await service.get_api_key_auth_snapshot(raw_key) is None) is commit


async def seed_tree(session):
    entities = []
    for _ in range(2):
        entity = Entity(
            name="Tree",
            display_name="Tree",
            slug=f"tree-{uuid4().hex}",
            entity_type="organization",
            entity_class=EntityClass.STRUCTURAL,
            status="active",
            depth=0,
        )
        entity.update_path(None)
        entities.append(entity)
    session.add_all(entities)
    await session.flush()
    root, child = entities
    session.add(EntityClosure(ancestor_id=root.id, descendant_id=child.id, depth=1))
    await session.commit()
    return root.id, child.id


@pytest.mark.asyncio
async def test_paused_tree_query_cannot_publish_under_a_new_epoch(
    test_engine,
    test_session,
    auth_config,
    cache_backend,
    monkeypatch,
):
    root_id, child_id = await seed_tree(test_session)
    config = auth_config.model_copy(update={"enable_caching": True})
    cache = CacheService(cache_backend, config)
    service = APIKeyService(config, redis_client=cache_backend)
    service.cache_service = cache
    entities = EntityService(config)
    entities.cache_service = cache
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as reader:
        execute = reader.execute

        async def pause_after_query(*args, **kwargs):
            result = await execute(*args, **kwargs)
            async with factory() as writer:
                await writer.execute(delete(EntityClosure).where(EntityClosure.descendant_id == child_id))
                await entities._invalidate_permission_cache(writer, child_id, scope_global=True)
                await writer.commit()
            return result

        monkeypatch.setattr(reader, "execute", pause_after_query)
        key = SimpleNamespace(entity_id=root_id, inherit_from_tree=True)
        assert await service.check_entity_access_with_tree(reader, key, child_id) is True
    assert await service.get_cached_entity_relation(str(root_id), str(child_id)) is None


@pytest.mark.asyncio
async def test_uncommitted_tree_change_bypasses_shared_relation_cache(
    test_engine,
    test_session,
    auth_config,
    cache_backend,
):
    root_id, child_id = await seed_tree(test_session)
    config = auth_config.model_copy(update={"enable_caching": True})
    cache = CacheService(cache_backend, config)
    service = APIKeyService(config, redis_client=cache_backend)
    service.cache_service = cache
    entities = EntityService(config)
    entities.cache_service = cache
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    key = SimpleNamespace(entity_id=root_id, inherit_from_tree=True)
    async with factory() as reader:
        assert await service.check_entity_access_with_tree(reader, key, child_id) is True
    async with factory() as writer:
        await writer.execute(delete(EntityClosure).where(EntityClosure.descendant_id == child_id))
        await entities._invalidate_permission_cache(writer, child_id, scope_global=True)
        assert await service.check_entity_access_with_tree(writer, key, child_id) is False
        assert await service.get_cached_entity_relation(str(root_id), str(child_id)) is True
        await writer.rollback()
    assert await service.get_cached_entity_relation(str(root_id), str(child_id)) is True


@pytest.mark.asyncio
async def test_batched_principal_inventory_still_checks_other_and_missing_anchors(test_session, auth_config):
    root_id, other_id = await seed_tree(test_session)
    principal = IntegrationPrincipal(
        name="Inventory fixture",
        anchor_entity_id=root_id,
        scope_kind=IntegrationPrincipalScopeKind.ENTITY,
        allowed_scopes=["report:read"],
    )
    test_session.add(principal)
    other = await test_session.get(Entity, other_id)
    other.status = "archived"
    await test_session.commit()
    keys = []
    for anchor_id in [root_id, other_id, uuid4()]:
        keys.append(
            APIKey(
                name="Inventory",
                prefix=uuid4().hex[:16],
                key_hash=uuid4().hex,
                integration_principal_id=principal.id,
                entity_id=anchor_id,
            )
        )
    policy = APIKeyPolicyService(auth_config.model_copy(update={"enable_entity_hierarchy": True}))
    results = await policy.evaluate_effectiveness_map(
        test_session,
        api_keys=keys,
        scopes_by_key_id={key.id: ["report:read"] for key in keys},
    )
    assert results[keys[0].id].is_currently_effective is True
    assert results[keys[1].id].ineffective_reasons == ["anchor_inactive"]
    assert results[keys[2].id].ineffective_reasons == ["anchor_missing"]


@pytest.mark.asyncio
async def test_disabled_tree_cache_adds_no_version_reads(test_session, auth_config):
    root_id, child_id = await seed_tree(test_session)
    service = APIKeyService(
        auth_config.model_copy(update={"enable_caching": False}), redis_client=SimpleNamespace(is_available=True)
    )
    service._entity_relation_cache_version = AsyncMock(side_effect=AssertionError("disabled cache version read"))
    assert (
        await service.check_entity_access_with_tree(
            test_session,
            SimpleNamespace(entity_id=root_id, inherit_from_tree=True),
            child_id,
        )
        is True
    )
    service._entity_relation_cache_version.assert_not_awaited()
