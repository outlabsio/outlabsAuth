"""Retained identities cannot regain old platform authority or old proofs."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from outlabs_auth.authentication.strategy import JWTStrategy
from outlabs_auth.core.exceptions import TokenInvalidError
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.enums import UserStatus, MembershipStatus
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.routers._scope import user_is_global_account
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.user import UserService
from outlabs_auth.utils.jwt import create_access_token
from outlabs_auth.core.session_security import advance_epoch, epoch
from sqlalchemy.ext.asyncio import async_sessionmaker
import asyncio


@pytest.mark.asyncio
@pytest.mark.parametrize("superuser", [False, True])
async def test_delete_restore_never_revives_access_or_privilege(test_session, auth_config, superuser):
    user = User(email=f"retained-{uuid4().hex}@example.test", is_superuser=superuser)
    test_session.add(user)
    await test_session.commit()
    users = UserService(auth_config)
    auth = AuthService(auth_config)
    token = create_access_token({"sub": str(user.id)}, auth_config.secret_key, audience=auth_config.jwt_audience)
    assert await auth.get_current_user(test_session, token) is user
    assert await users.delete_user(test_session, user.id)
    await test_session.commit()
    restored = await users.restore_user(test_session, user.id)
    await test_session.commit()
    assert not restored.is_superuser
    scope_host = SimpleNamespace(config=SimpleNamespace(enable_entity_hierarchy=False))
    assert await user_is_global_account(scope_host, test_session, restored) is superuser
    with pytest.raises(TokenInvalidError):
        await auth.get_current_user(test_session, token)
    strategy = JWTStrategy(secret=auth_config.secret_key, audience=auth_config.jwt_audience)
    assert await strategy.authenticate(token, user_service=users, session=test_session) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["revoke", "suspend", "password"])
async def test_security_changes_cancel_both_bearer_paths_without_stored_refresh(
    test_session,
    auth_config,
    change,
):
    config = auth_config.model_copy(update={"store_refresh_tokens": False})
    user = User(email=f"epoch-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    users = UserService(config)
    auth = AuthService(config)
    token = create_access_token({"sub": str(user.id)}, config.secret_key, audience=config.jwt_audience)
    if change == "revoke":
        assert await auth.revoke_all_user_tokens(test_session, user.id) == 0
    elif change == "suspend":
        await users.update_user_status(test_session, user.id, UserStatus.SUSPENDED)
        await users.update_user_status(test_session, user.id, UserStatus.ACTIVE)
    else:
        await users.change_password(test_session, user.id, "SyntheticPassword123!")
    await test_session.commit()
    with pytest.raises(TokenInvalidError):
        await auth.get_current_user(test_session, token)
    strategy = JWTStrategy(secret=config.secret_key, audience=config.jwt_audience)
    assert await strategy.authenticate(token, user_service=users, session=test_session) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(MembershipStatus))
async def test_retained_system_role_history_survives_definition_changes(test_session, auth_config, status):
    user = User(email=f"operator-{uuid4().hex}@example.test")
    role = Role(name=uuid4().hex, display_name="Operator", is_global=True)
    test_session.add_all([user, role])
    await test_session.flush()
    original_revoked_at = datetime.now(timezone.utc) - timedelta(days=30)
    grant = UserRoleMembership(
        user_id=user.id,
        role_id=role.id,
        status=status,
        valid_from=datetime.now(timezone.utc) + timedelta(days=1),
        revoked_at=original_revoked_at if status == MembershipStatus.REVOKED else None,
        revocation_reason="Original removal" if status == MembershipStatus.REVOKED else None,
    )
    test_session.add(grant)
    await test_session.commit()
    users = UserService(auth_config.model_copy(update={"enable_entity_hierarchy": True}))
    await users.delete_user(test_session, user.id)
    await test_session.commit()
    role.is_global = False
    await test_session.commit()
    restored = await users.restore_user(test_session, user.id)
    await test_session.commit()
    assert grant.status == MembershipStatus.REVOKED
    if status == MembershipStatus.REVOKED:
        assert grant.revoked_at == original_revoked_at
        assert grant.revocation_reason == "Original removal"
    host = SimpleNamespace(config=SimpleNamespace(enable_entity_hierarchy=False))
    assert await user_is_global_account(host, test_session, restored)


@pytest.mark.asyncio
@pytest.mark.parametrize("claimed", [None, False, "1", -1, 0, 2, 1])
async def test_epoch_claim_is_exact_on_both_bearer_paths(test_session, auth_config, claimed):
    user = User(email=f"proof-{uuid4().hex}@example.test", session_security_epoch=1)
    test_session.add(user)
    await test_session.commit()
    token = create_access_token(
        {"sub": str(user.id), "security_epoch": claimed}, auth_config.secret_key, audience=auth_config.jwt_audience
    )
    users = UserService(auth_config)
    auth = AuthService(auth_config)
    strategy = JWTStrategy(secret=auth_config.secret_key, audience=auth_config.jwt_audience)
    if type(claimed) is int and claimed == 1:
        assert await auth.get_current_user(test_session, token) is user
        assert await strategy.authenticate(token, user_service=users, session=test_session)
    else:
        with pytest.raises(TokenInvalidError):
            await auth.get_current_user(test_session, token)
        assert await strategy.authenticate(token, user_service=users, session=test_session) is None


@pytest.mark.asyncio
async def test_concurrent_revocations_are_monotonic_and_rollback_is_private(test_session, test_engine):
    user = User(email=f"concurrent-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as first:
        assert await advance_epoch(first, user.id) == 1
        async with factory() as reader:
            assert epoch(await reader.get(User, user.id)) == 0

        async def second():
            async with factory() as writer:
                value = await advance_epoch(writer, user.id)
                await writer.commit()
                return value

        task = asyncio.create_task(second())
        await first.commit()
        assert await asyncio.wait_for(task, timeout=5) == 2
    async with factory() as writer:
        assert await advance_epoch(writer, user.id) == 3
        await writer.rollback()
    async with factory() as reader:
        assert epoch(await reader.get(User, user.id)) == 2


@pytest.mark.asyncio
async def test_new_token_pair_after_revocation_includes_current_epoch(test_session, auth_config):
    from outlabs_auth.utils.jwt import verify_token

    config = auth_config.model_copy(update={"store_refresh_tokens": False})
    user = User(email=f"new-session-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    auth = AuthService(config)
    await auth.revoke_all_user_tokens(test_session, user.id)
    pair = await auth.create_tokens_for_user(test_session, user)
    await test_session.commit()
    for token, kind in ((pair.access_token, "access"), (pair.refresh_token, "refresh")):
        assert (
            verify_token(token, config.secret_key, expected_type=kind, audience=config.jwt_audience)["security_epoch"]
            == 1
        )
    assert await auth.get_current_user(test_session, pair.access_token) is user
    replacement = await auth.refresh_access_token(test_session, pair.refresh_token)
    assert await auth.get_current_user(test_session, replacement.access_token) is user


@pytest.mark.asyncio
async def test_same_clock_tick_security_change_and_new_proof(test_session, auth_config, monkeypatch):
    import outlabs_auth.services.user as user_module
    import outlabs_auth.utils.jwt as jwt_module

    fixed = datetime.now(timezone.utc).replace(microsecond=123456)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(user_module, "datetime", Clock)
    monkeypatch.setattr(jwt_module, "datetime", Clock)
    user = User(email=f"precision-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    config = auth_config.model_copy(update={"store_refresh_tokens": False})
    auth = AuthService(config)
    users = UserService(config)
    old = await auth.create_tokens_for_user(test_session, user)
    await users.change_password(test_session, user.id, "SyntheticPassword123!")
    fresh = await auth.create_tokens_for_user(test_session, user)
    await test_session.commit()
    with pytest.raises(TokenInvalidError):
        await auth.get_current_user(test_session, old.access_token)
    assert await auth.get_current_user(test_session, fresh.access_token) is user
    strategy = JWTStrategy(secret=config.secret_key, audience=config.jwt_audience)
    assert await strategy.authenticate(old.access_token, user_service=users, session=test_session) is None
    assert await strategy.authenticate(fresh.access_token, user_service=users, session=test_session)


@pytest.mark.asyncio
async def test_status_edit_cannot_bypass_retained_delete_workflow(test_session, auth_config):
    user = User(email=f"status-{uuid4().hex}@example.test", is_superuser=True)
    test_session.add(user)
    await test_session.commit()
    with pytest.raises(InvalidInputError, match="delete workflow"):
        await UserService(auth_config).update_user_status(test_session, user.id, UserStatus.DELETED)
    assert user.status == UserStatus.ACTIVE
    assert user.is_superuser


@pytest.mark.asyncio
async def test_limited_admin_cannot_reset_retained_operator_with_scope_disabled(test_engine):
    import httpx
    from fastapi import FastAPI
    from outlabs_auth import SimpleRBAC
    from outlabs_auth.models.sql.permission import Permission
    from outlabs_auth.routers.users import get_users_router
    from outlabs_auth.fastapi import register_exception_handlers

    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="synthetic-security-test-secret-32bytes",
        enable_token_cleanup=False,
        enforce_user_scope=False,
    )
    await auth.initialize()
    try:
        async with auth.get_session() as session:
            limited = await auth.user_service.create_user(
                session, email=f"limited-{uuid4().hex}@example.test", password="SyntheticPassword123!"
            )
            operator = await auth.user_service.create_user(
                session,
                email=f"operator-{uuid4().hex}@example.test",
                password="SyntheticPassword123!",
                is_superuser=True,
            )
            role = Role(
                name=uuid4().hex,
                display_name="User admin",
                permissions=[Permission(name="user:update", display_name="Update users")],
            )
            session.add(role)
            await session.flush()
            await auth.role_service.assign_role_to_user(session, user_id=limited.id, role_id=role.id)
            await auth.user_service.delete_user(session, operator.id)
            await auth.user_service.restore_user(session, operator.id)
            await session.commit()
            operator_id = operator.id
            token = create_access_token(
                {"sub": str(limited.id)}, auth.config.secret_key, audience=auth.config.jwt_audience
            )
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(get_users_router(auth, prefix="/users"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.patch(
                f"/users/{operator_id}",
                json={"first_name": "Unauthorized"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 403
        async with auth.get_session() as session:
            operator = await session.get(User, operator_id)
            assert operator.first_name is None
            assert operator.platform_protected is True
            assert not operator.is_superuser
    finally:
        await auth.shutdown()


@pytest.mark.asyncio
async def test_restore_retires_legacy_artifacts_and_keeps_platform_classification(test_session, auth_config):
    from outlabs_auth.models.sql.api_key import APIKey
    from outlabs_auth.models.sql.token import RefreshToken
    from outlabs_auth.models.sql.enums import APIKeyStatus
    from outlabs_auth.services.permission import PermissionService

    user = User(email=f"legacy-artifacts-{uuid4().hex}@example.test", status=UserStatus.DELETED)
    role = Role(name=uuid4().hex, display_name="Legacy operator", is_global=True)
    test_session.add_all([user, role])
    await test_session.flush()
    grant = UserRoleMembership(user_id=user.id, role_id=role.id, status=MembershipStatus.ACTIVE)
    key = APIKey(name="Legacy retained", owner_id=user.id, prefix=uuid4().hex[:16], key_hash=uuid4().hex)
    refresh = RefreshToken(
        user_id=user.id, token_hash=uuid4().hex, expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    test_session.add_all([grant, key, refresh])
    await test_session.commit()
    config = auth_config.model_copy(update={"enable_entity_hierarchy": True})
    await UserService(config).restore_user(test_session, user.id)
    await test_session.commit()
    assert user.status == UserStatus.ACTIVE
    assert user.platform_protected is True
    assert not user.is_superuser
    assert grant.status == MembershipStatus.REVOKED
    assert key.status == APIKeyStatus.REVOKED
    assert refresh.is_revoked
    assert await PermissionService(config).get_user_permissions(test_session, user.id) == []
