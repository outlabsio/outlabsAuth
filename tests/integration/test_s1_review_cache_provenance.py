"""Independent-review reproductions: old request authority cannot acquire new cache counters."""

import asyncio
from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.api_key import APIKey
from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.models.sql.integration_principal import IntegrationPrincipal
from outlabs_auth.models.sql.enums import (
    UserStatus,
    IntegrationPrincipalStatus,
    IntegrationPrincipalScopeKind,
    APIKeyKind,
)
from outlabs_auth.services.api_key_policy import APIKeyPolicyService
from outlabs_auth.services.user import UserService
from outlabs_auth.services.integration_principal import IntegrationPrincipalService
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.role import Role, RoleEntityTypePermission
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.services import request_cache
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.cache_backend import MemoryCacheBackend
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.role import RoleService


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_context_race(test_session, test_engine, auth_config, monkeypatch, redis_client, backend):
    config = auth_config.model_copy(
        update={
            "enable_caching": True,
            "enable_entity_hierarchy": False,
            "enable_context_aware_roles": True,
            "redis_key_prefix": uuid4().hex,
        }
    )
    cache = CacheService(redis_client if backend == "redis" else MemoryCacheBackend(config), config)
    service = PermissionService(config)
    service.cache_service = cache
    entities = EntityService(config)
    entities.cache_service = cache
    entity = Entity(
        name="Root", display_name="Root", slug=uuid4().hex, entity_type="old_type", entity_class=EntityClass.STRUCTURAL
    )
    entity.update_path(None)
    user = User(email=f"{uuid4().hex}@example.test")
    permission = Permission(name="report:read", display_name="Read")
    role = Role(name=uuid4().hex, display_name="Reader")
    test_session.add_all([entity, user, permission, role])
    await test_session.flush()
    test_session.add_all(
        [
            EntityClosure(ancestor_id=entity.id, descendant_id=entity.id, depth=0),
            RoleEntityTypePermission(role_id=role.id, entity_type="old_type", permission_id=permission.id),
            UserRoleMembership(user_id=user.id, role_id=role.id),
        ]
    )
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    original = service._get_cached_permission_result
    changed = False

    async def invalidate_before_versions(**kwargs):
        nonlocal changed
        if not changed:
            changed = True

            async def writer():
                async with factory() as session:
                    await entities.update_entity(session, entity.id, entity_type="new_type")
                    await session.commit()

            await asyncio.create_task(writer())
        return await original(**kwargs)

    monkeypatch.setattr(service, "_get_cached_permission_result", invalidate_before_versions)
    request_cache.reset()
    async with factory() as reader:
        first = await service.check_permission(reader, user.id, "report:read", entity_id=entity.id)
    request_cache.reset()
    async with factory() as reader:
        second = await service.check_permission(reader, user.id, "report:read", entity_id=entity.id)
    service.cache_service = None
    request_cache.reset()
    async with factory() as reader:
        uncached = await service.check_permission(reader, user.id, "report:read", entity_id=entity.id)
    print(f"first={first} cached_after_mutation={second} authoritative={uncached}")
    assert second == uncached


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_request_memo_race(test_session, test_engine, auth_config, redis_client, backend):
    config = auth_config.model_copy(
        update={"enable_caching": True, "enable_entity_hierarchy": False, "redis_key_prefix": uuid4().hex}
    )
    cache = CacheService(redis_client if backend == "redis" else MemoryCacheBackend(config), config)
    service = PermissionService(config)
    service.cache_service = cache
    roles = RoleService(config)
    roles.cache_service = cache
    user = User(email=f"{uuid4().hex}@example.test")
    role = Role(
        name=uuid4().hex,
        display_name="Reader",
        permissions=[
            Permission(name="report:read", display_name="Read"),
            Permission(name="report:write", display_name="Write"),
        ],
    )
    test_session.add_all([user, role])
    await test_session.flush()
    test_session.add(UserRoleMembership(user_id=user.id, role_id=role.id))
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    request_cache.reset()
    async with factory() as reader:
        first = await service.check_permission(reader, user.id, "report:read")

        async def writer():
            async with factory() as session:
                await roles.revoke_role_from_user(session, user_id=user.id, role_id=role.id)
                await session.commit()

        await asyncio.create_task(writer())
        second = await service.check_permission(reader, user.id, "report:write")
    request_cache.reset()
    async with factory() as reader:
        later = await service.check_permission(reader, user.id, "report:write")
    service.cache_service = None
    request_cache.reset()
    async with factory() as reader:
        uncached = await service.check_permission(reader, user.id, "report:write")
    print(f"first={first} same_request_after_revoke={second} cached_next_request={later} authoritative={uncached}")
    assert later == uncached


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_late_target_provenance(test_session, test_engine, auth_config, monkeypatch, redis_client, backend):
    config = auth_config.model_copy(
        update={
            "enable_caching": True,
            "enable_entity_hierarchy": False,
            "enable_context_aware_roles": True,
            "redis_key_prefix": uuid4().hex,
        }
    )
    cache = CacheService(redis_client if backend == "redis" else MemoryCacheBackend(config), config)
    service = PermissionService(config)
    service.cache_service = cache
    entities = EntityService(config)
    entities.cache_service = cache
    entity = Entity(
        name="Root", display_name="Root", slug=uuid4().hex, entity_type="old_type", entity_class=EntityClass.STRUCTURAL
    )
    entity.update_path(None)
    user = User(email=f"{uuid4().hex}@example.test")
    permission = Permission(name="report:read", display_name="Read")
    role = Role(name=uuid4().hex, display_name="Reader")
    test_session.add_all([entity, user, permission, role])
    await test_session.flush()
    test_session.add_all(
        [
            EntityClosure(ancestor_id=entity.id, descendant_id=entity.id, depth=0),
            RoleEntityTypePermission(role_id=role.id, entity_type="old_type", permission_id=permission.id),
            UserRoleMembership(user_id=user.id, role_id=role.id),
        ]
    )
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    request_cache.reset()
    async with factory() as reader:
        await service.check_permission(reader, user.id, "report:read")
        assert await service._resolve_context_entity_type(reader, entity.id) == "old_type"

        async def writer():
            async with factory() as session:
                await entities.update_entity(session, entity.id, entity_type="new_type")
                await session.commit()

        await asyncio.create_task(writer())
        first = await service.check_permission(reader, user.id, "report:read", entity_id=entity.id)
    request_cache.reset()
    async with factory() as reader:
        second = await service.check_permission(reader, user.id, "report:read", entity_id=entity.id)
    service.cache_service = None
    request_cache.reset()
    async with factory() as reader:
        uncached = await service.check_permission(reader, user.id, "report:read", entity_id=entity.id)
    print(f"first={first} cached_after_mutation={second} authoritative={uncached}")
    assert second == uncached


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_orm_graph_reset_race(test_session, test_engine, auth_config, redis_client, backend):
    config = auth_config.model_copy(
        update={"enable_caching": True, "enable_entity_hierarchy": False, "redis_key_prefix": uuid4().hex}
    )
    cache = CacheService(redis_client if backend == "redis" else MemoryCacheBackend(config), config)
    service = PermissionService(config)
    service.cache_service = cache
    roles = RoleService(config)
    roles.cache_service = cache
    user = User(email=f"{uuid4().hex}@example.test")
    role = Role(
        name=uuid4().hex,
        display_name="Reader",
        permissions=[
            Permission(name="report:read", display_name="Read"),
            Permission(name="report:write", display_name="Write"),
        ],
    )
    test_session.add_all([user, role])
    await test_session.flush()
    test_session.add(UserRoleMembership(user_id=user.id, role_id=role.id))
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    request_cache.reset()
    async with factory() as reader:
        first = await service.check_permission(reader, user.id, "report:read")
        held = await service._load_user_role_memberships(reader, user.id, None)
        assert held[0].role.permissions

        async def writer():
            async with factory() as session:
                await roles.set_permissions_by_name(session, role.id, ["report:read"])
                await session.commit()

        await asyncio.create_task(writer())
        request_cache.reset()
        second = await service.check_permission(reader, user.id, "report:write")
    request_cache.reset()
    async with factory() as reader:
        later = await service.check_permission(reader, user.id, "report:write")
    service.cache_service = None
    request_cache.reset()
    async with factory() as reader:
        uncached = await service.check_permission(reader, user.id, "report:write")
    print(f"first={first} same_request_after_revoke={second} cached_next_request={later} authoritative={uncached}")
    assert first
    assert not second
    assert later == uncached


@pytest.mark.asyncio
async def test_retained_key_refuses_after_revoke(test_session, test_engine, auth_config, redis_client):
    config = auth_config.model_copy(update={"enable_caching": True, "enable_entity_hierarchy": False})
    cache = CacheService(redis_client, config)
    keys = APIKeyService(config, redis_client=redis_client)
    keys.cache_service = cache
    raw = "oak_" + uuid4().hex + uuid4().hex
    user = User(email=f"{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.flush()
    key = APIKey(name="Held key", owner_id=user.id, prefix=raw[:16], key_hash=APIKey.hash_key(raw))
    test_session.add(key)
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    request_cache.reset()
    async with factory() as reader:
        held, _ = await keys.verify_api_key(reader, raw)
        assert held is not None

        async def writer():
            async with factory() as session:
                assert await keys.revoke_api_key(session, key.id)
                await session.commit()

        await asyncio.create_task(writer())
        request_cache.reset()
        again, _ = await keys.verify_api_key(reader, raw)
        print(f"held_status={held.status} accepted_after_committed_revoke={again is not None}")
        assert again is None


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["owner", "principal", "anchor"])
async def test_retained_owner_lifecycle_refresh(test_session, test_engine, auth_config, boundary):
    policy = APIKeyPolicyService(auth_config)
    entity = Entity(
        name="Root",
        display_name="Root",
        slug=uuid4().hex,
        entity_type="organization",
        entity_class=EntityClass.STRUCTURAL,
    )
    entity.update_path(None)
    user = User(email=f"{uuid4().hex}@example.test")
    principal = IntegrationPrincipal(
        name="Held principal", scope_kind=IntegrationPrincipalScopeKind.PLATFORM_GLOBAL, allowed_scopes=["report:read"]
    )
    test_session.add_all([user, entity, principal])
    await test_session.flush()
    key = APIKey(
        name="Held owner",
        prefix=uuid4().hex[:16],
        key_hash=uuid4().hex,
        owner_id=None if boundary == "principal" else user.id,
        integration_principal_id=principal.id if boundary == "principal" else None,
        key_kind=APIKeyKind.SYSTEM_INTEGRATION if boundary == "principal" else APIKeyKind.PERSONAL,
        entity_id=entity.id if boundary == "anchor" else None,
    )
    test_session.add(key)
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as reader:
        held_user = await reader.get(User, user.id)
        held_principal = await reader.get(IntegrationPrincipal, principal.id)
        held_entity = await reader.get(Entity, entity.id)
        current = await reader.get(APIKey, key.id)
        assert await policy.validate_runtime_use(reader, api_key=current)

        async def writer():
            async with factory() as session:
                if boundary == "owner":
                    await UserService(auth_config).update_user_status(session, user.id, UserStatus.BANNED)
                elif boundary == "principal":
                    await IntegrationPrincipalService(auth_config).update_principal(
                        session, principal.id, status=IntegrationPrincipalStatus.INACTIVE
                    )
                else:
                    await EntityService(auth_config).update_entity(session, entity.id, status="inactive")
                await session.commit()

        await asyncio.create_task(writer())
        request_cache.reset()
        accepted = await policy.validate_runtime_use(reader, api_key=current)
        print(
            f"boundary={boundary} accepted_after_mutation={accepted}; user={held_user.status}, principal={held_principal.status}, entity={held_entity.status}"
        )
        assert not accepted
