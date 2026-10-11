"""Time transitions must invalidate authority with unchanged mutation versions."""

import importlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services import request_cache
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.cache_backend import MemoryCacheBackend
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.api_key_policy import APIKeyPolicyService
from outlabs_auth.services import cache_validity


@pytest.fixture
def clock(monkeypatch):
    state = [datetime.now(timezone.utc)]

    class ClockMeta(type):
        def __instancecheck__(cls, value):
            return isinstance(value, datetime)

    class Clock(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None):
            return state[0] if tz else state[0].replace(tzinfo=None)

    for name in (
        "services.permission",
        "services.api_key",
        "services.cache",
        "services.cache_validity",
        "models.sql.entity_membership",
        "models.sql.user_role_membership",
        "models.sql.entity",
    ):
        try:
            module = importlib.import_module(f"outlabs_auth.{name}")
        except ModuleNotFoundError:
            continue
        monkeypatch.setattr(module, "datetime", Clock, raising=False)
    return state


@pytest.fixture(params=["memory", "redis"])
def backend(request, redis_client, auth_config):
    if request.param == "redis":
        return redis_client
    return MemoryCacheBackend(auth_config.model_copy(update={"redis_key_prefix": uuid4().hex}))


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("binding", ["direct_role", "entity", "ancestor"])
@pytest.mark.parametrize("activation", [False, True], ids=["expiry", "activation"])
async def test_permission_and_aggregate_cross_windows(
    test_engine,
    test_session,
    auth_config,
    backend,
    clock,
    binding,
    activation,
):
    entity = Entity(
        name="Root",
        display_name="Root",
        slug=uuid4().hex,
        entity_type="organization",
        entity_class=EntityClass.STRUCTURAL,
    )
    entity.update_path(None)
    test_session.add(entity)
    await test_session.flush()
    target = entity
    if binding == "ancestor":
        target = Entity(
            name="Branch",
            display_name="Branch",
            slug=uuid4().hex,
            parent_id=entity.id,
            depth=1,
            entity_type="organization",
            entity_class=EntityClass.STRUCTURAL,
        )
        target.update_path(entity.path)
        test_session.add(target)
        await test_session.flush()
        test_session.add_all(
            [
                EntityClosure(ancestor_id=entity.id, descendant_id=target.id, depth=1),
                EntityClosure(ancestor_id=target.id, descendant_id=target.id, depth=0),
            ]
        )
    test_session.add(EntityClosure(ancestor_id=entity.id, descendant_id=entity.id, depth=0))
    user = User(email=f"window-{uuid4().hex}@example.test", root_entity_id=entity.id)
    permission = Permission(name="report:read_tree", display_name="Read")
    role = Role(name=uuid4().hex, display_name="Reader", permissions=[permission])
    test_session.add_all([user, role])
    await test_session.flush()
    transition = clock[0] + timedelta(seconds=30)
    window = {"valid_from": transition} if activation else {"valid_until": transition}
    if binding == "direct_role":
        member = UserRoleMembership(user_id=user.id, role_id=role.id, status=MembershipStatus.ACTIVE, **window)
    else:
        member = EntityMembership(
            user_id=user.id, entity_id=entity.id, roles=[role], status=MembershipStatus.ACTIVE, **window
        )
    test_session.add(member)
    await test_session.commit()
    config = auth_config.model_copy(update={"enable_caching": True, "enable_entity_hierarchy": True})
    cache = CacheService(backend, config)
    service = PermissionService(config)
    service.cache_service = cache
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def read():
        request_cache.reset()
        async with factory() as session:
            verdict = await service.check_permission(session, user.id, "report:read", entity_id=target.id)
            names = await service.get_user_permissions(session, user.id)
            return verdict, "report:read_tree" in names

    try:
        assert await read() == (not activation, not activation)
        assert await read() == (not activation, not activation)
        versions = await cache.get_api_key_auth_snapshot_versions(user_id=str(user.id))
        clock[0] = transition + timedelta(microseconds=1)
        assert await cache.get_api_key_auth_snapshot_versions(user_id=str(user.id)) == versions
        assert await read() == (activation, activation)
    finally:
        request_cache.reset()


@pytest.mark.asyncio
@pytest.mark.parametrize("local_ttl", [0, 120])
@pytest.mark.parametrize("activation", [False, True], ids=["expiry", "activation"])
async def test_compiled_snapshot_crosses_membership_transition(
    test_session,
    auth_config,
    backend,
    clock,
    local_ttl,
    activation,
):
    user = User(email=f"snapshot-{uuid4().hex}@example.test")
    role = Role(
        name=uuid4().hex,
        display_name="Reader",
        permissions=[
            Permission(name="report:read", display_name="Read"),
        ],
    )
    test_session.add_all([user, role])
    await test_session.flush()
    transition = clock[0] + timedelta(seconds=30)
    window = {"valid_from": transition} if activation else {"valid_until": transition}
    test_session.add(UserRoleMembership(user_id=user.id, role_id=role.id, status=MembershipStatus.ACTIVE, **window))
    await test_session.commit()
    config = auth_config.model_copy(
        update={"enable_caching": True, "enable_entity_hierarchy": False, "api_key_local_snapshot_cache_ttl": local_ttl}
    )
    cache = CacheService(backend, config)
    permissions = PermissionService(config)
    permissions.cache_service = cache
    keys = APIKeyService(config, redis_client=backend)
    keys.cache_service = cache
    raw = "oak_" + uuid4().hex + uuid4().hex
    key = APIKey(id=uuid4(), name="Window", owner_id=user.id, prefix=raw[:16], key_hash=APIKey.hash_key(raw))
    result = {
        "source": "api_key",
        "user_id": str(user.id),
        "api_key": key,
        "metadata": {"owner_type": "user", "owner_id": str(user.id), "scopes": ["report:read"]},
    }
    result["_outlabs_snapshot_versions"] = await cache.get_api_key_auth_snapshot_versions(
        user_id=str(user.id),
        credential_hash=key.key_hash,
    )
    try:
        request_cache.reset()
        names = await permissions.get_user_permissions(test_session, user.id)
        assert ("report:read" in names) is (not activation)
        assert await keys.set_api_key_auth_snapshot(raw, auth_result=result, effective_permissions=names)
        assert await keys.get_api_key_auth_snapshot(raw) is not None
        clock[0] = transition + timedelta(microseconds=1)
        assert await keys.get_api_key_auth_snapshot(raw) is None
        request_cache.reset()
        assert ("report:read" in await permissions.get_user_permissions(test_session, user.id)) is activation
    finally:
        request_cache.reset()


@pytest.mark.asyncio
async def test_elapsed_deadline_does_not_get_a_new_cache_lease(auth_config, backend, clock):
    cache = CacheService(backend, auth_config)
    user_id = str(uuid4())
    _, versions = await cache.get_permission_check(user_id, "report:read")
    deadline = clock[0].timestamp() + 0.5
    # No integer TTL is safe; zero must mean no write, never an immortal SET.
    assert not await cache.set_permission_check(user_id, "report:read", True, versions=versions, valid_until=deadline)
    clock[0] += timedelta(seconds=1)
    assert not await cache.set_user_permission_names(
        user_id, include_entity_local=False, names=["report:read"], versions=versions, valid_until=deadline
    )
    assert (await cache.get_permission_check(user_id, "report:read"))[0] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("local_ttl", [0, 120])
@pytest.mark.parametrize("source", ["key", "anchor"])
async def test_snapshot_cannot_outlive_key_or_anchor(
    test_session,
    auth_config,
    backend,
    clock,
    local_ttl,
    source,
):
    transition = clock[0] + timedelta(seconds=30)
    entity = Entity(
        name="Anchor",
        display_name="Anchor",
        slug=uuid4().hex,
        entity_type="organization",
        entity_class=EntityClass.STRUCTURAL,
        valid_until=transition if source == "anchor" else None,
    )
    user = User(email=f"anchor-{uuid4().hex}@example.test")
    test_session.add_all([entity, user])
    await test_session.commit()
    config = auth_config.model_copy(update={"enable_caching": True, "api_key_local_snapshot_cache_ttl": local_ttl})
    cache = CacheService(backend, config)
    keys = APIKeyService(config, redis_client=backend)
    keys.cache_service = cache
    raw = "oak_" + uuid4().hex + uuid4().hex
    key = APIKey(
        id=uuid4(),
        name="Anchor",
        owner_id=user.id,
        prefix=raw[:16],
        key_hash=APIKey.hash_key(raw),
        entity_id=entity.id,
        expires_at=transition if source == "key" else None,
    )
    result = {
        "source": "api_key",
        "user_id": str(user.id),
        "api_key": key,
        "metadata": {"owner_type": "user", "owner_id": str(user.id)},
    }
    result["_outlabs_snapshot_versions"] = await cache.get_api_key_auth_snapshot_versions(
        user_id=str(user.id),
        entity_id=str(entity.id),
        credential_hash=key.key_hash,
    )
    try:
        request_cache.reset()
        cache_validity.record(str(user.id), None)
        assert await APIKeyPolicyService(config).validate_runtime_use(test_session, api_key=key)
        assert await keys.set_api_key_auth_snapshot(raw, auth_result=result, effective_permissions=[])
        assert await keys.get_api_key_auth_snapshot(raw) is not None
        clock[0] = transition  # conservative miss at the boundary, including local cache
        assert await keys.get_api_key_auth_snapshot(raw) is None
    finally:
        request_cache.reset()


@pytest.mark.asyncio
async def test_legacy_cached_allow_without_time_proof_misses(auth_config, backend):
    cache = CacheService(backend, auth_config)
    user_id = str(uuid4())
    _, versions = await cache.get_permission_check(user_id, "report:read")
    await backend.set(
        cache.make_permission_check_key(user_id, "report:read"), {"result": True, "versions": versions}, ttl=60
    )
    assert (await cache.get_permission_check(user_id, "report:read"))[0] is None
