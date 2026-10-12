"""Security boundaries reproduced during the independent a37 review."""

from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from outlabs_auth import SimpleRBAC
from outlabs_auth.authentication.strategy import JWTStrategy
from outlabs_auth.core.exceptions import (
    AccountInactiveError,
    InvalidInputError,
    TokenInvalidError,
    RefreshTokenInvalidError,
)
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.auth_challenge import AuthChallenge
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.routers import get_auth_router, get_users_router
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.user import UserService
from outlabs_auth.utils.jwt import create_access_token


@pytest.mark.asyncio
async def test_stale_user_cannot_free_deleted_identifier(test_session, test_engine, auth_config):
    users = UserService(auth_config)
    user = User(email=f"reserved-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    user_id, original_email = user.id, user.email
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as stale:
        held = await users.get_user_by_id(stale, user_id)
        await stale.commit()
        async with factory() as writer:
            await users.delete_user(writer, user_id)
            await writer.commit()
        with pytest.raises(InvalidInputError, match="retained-deleted"):
            await users.update_user_fields(stale, user_id, email=f"changed-{uuid4().hex}@example.test")
        assert held.status == UserStatus.DELETED
        await stale.rollback()
    async with factory() as reader:
        assert (await reader.get(User, user_id)).email == original_email


@pytest.mark.asyncio
async def test_both_bearer_validators_refresh_stale_epoch(test_session, test_engine, auth_config):
    config = auth_config.model_copy(update={"store_refresh_tokens": False})
    users, auth = UserService(config), AuthService(config)
    user = User(email=f"epoch-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    token = create_access_token({"sub": str(user.id)}, config.secret_key, audience=config.jwt_audience)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as stale:
        held = await users.get_user_by_id(stale, user.id)
        await stale.commit()
        async with factory() as writer:
            await auth.revoke_all_user_tokens(writer, user.id)
            await writer.commit()
        with pytest.raises(TokenInvalidError):
            await auth.get_current_user(stale, token)
        assert held.session_security_epoch == 1
    async with factory() as stale:
        # Hold the current row, then invalidate again for an independent strategy check.
        held = await users.get_user_by_id(stale, user.id)
        await stale.commit()
        current = create_access_token(
            {"sub": str(user.id), "security_epoch": 1}, config.secret_key, audience=config.jwt_audience
        )
        async with factory() as writer:
            await auth.revoke_all_user_tokens(writer, user.id)
            await writer.commit()
        strategy = JWTStrategy(secret=config.secret_key, audience=config.jwt_audience)
        assert await strategy.authenticate(current, user_service=users, session=stale) is None
        assert held.session_security_epoch == 2


async def issue_challenge(auth, session, user, kind):
    if kind == "magic":
        return await auth.generate_magic_link_token(session, user)
    if kind == "reset":
        return await auth.generate_reset_token(session, user)
    if kind == "phone_verify":
        return await auth.generate_phone_verify_code(session, user)
    return await auth.generate_access_code(
        session,
        user,
        recipient=user.phone if kind in {"whatsapp", "sms"} else None,
        channel=kind if kind in {"whatsapp", "sms"} else None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["magic", "email", "whatsapp", "sms", "reset", "phone_verify"])
async def test_pre_delete_challenges_stay_retired_after_restore(test_session, auth_config, kind):
    auth, users = AuthService(auth_config), UserService(auth_config)
    user = User(email=f"challenge-{uuid4().hex}@example.test", phone="+15555550123", phone_verified=True)
    test_session.add(user)
    await test_session.commit()
    proof = await issue_challenge(auth, test_session, user, kind)
    await test_session.commit()
    await users.delete_user(test_session, user.id)
    await test_session.commit()
    await users.restore_user(test_session, user.id)
    await test_session.commit()
    with pytest.raises(TokenInvalidError):
        if kind == "magic":
            await auth.verify_magic_link(test_session, proof)
        elif kind == "reset":
            await auth.reset_password(test_session, proof, "SyntheticPassword123!")
        elif kind == "phone_verify":
            await auth.verify_phone_verify_code(test_session, user, code=proof)
        else:
            await auth.verify_access_code(
                test_session,
                code=proof,
                email=user.email if kind == "email" else None,
                phone=user.phone if kind != "email" else None,
                channel=kind if kind != "email" else None,
            )
    assert not list(
        (await test_session.execute(select(AuthChallenge).where(AuthChallenge.used_at.is_(None)))).scalars()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["magic", "email", "whatsapp", "sms", "reset", "phone_verify"])
async def test_stale_challenge_issuer_cannot_follow_deletion(test_session, test_engine, auth_config, kind):
    auth, users = AuthService(auth_config), UserService(auth_config)
    user = User(email=f"issuer-{uuid4().hex}@example.test", phone="+15555550123", phone_verified=True)
    test_session.add(user)
    await test_session.commit()
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as stale:
        held = await stale.get(User, user.id)
        await stale.commit()
        async with factory() as writer:
            await users.delete_user(writer, user.id)
            await writer.commit()
        with pytest.raises(AccountInactiveError):
            await issue_challenge(auth, stale, held, kind)


@pytest.mark.asyncio
@pytest.mark.parametrize("host_factory", [False, True])
async def test_refresh_reuse_commits_only_containment(test_session, test_engine, auth_config, host_factory):
    auth = AuthService(auth_config)
    entered = []
    if host_factory:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def security_transaction(failed_session):
            assert failed_session is test_session
            # The failed caller transaction has already rolled back.
            assert not failed_session.in_transaction()
            entered.append(True)
            async with async_sessionmaker(test_engine, expire_on_commit=False)() as containment:
                yield containment

        auth.security_transaction_factory = security_transaction
    user = User(email=f"reuse-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    user_id = user.id
    original = await auth.create_tokens_for_user(test_session, user)
    await test_session.commit()
    rotated = await auth.refresh_access_token(test_session, original.refresh_token)
    await test_session.commit()
    unrelated_name = f"uncommitted:{uuid4().hex}"
    test_session.add(Permission(name=unrelated_name, display_name="Must roll back"))
    await test_session.flush()
    with pytest.raises(RefreshTokenInvalidError, match="reuse detected"):
        await auth.refresh_access_token(test_session, original.refresh_token)
    assert len(entered) == int(host_factory)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as reader:
        assert (await reader.get(User, user_id)).session_security_epoch == 1
        assert (
            await reader.execute(select(Permission).where(Permission.name == unrelated_name))
        ).scalar_one_or_none() is None
        with pytest.raises(RefreshTokenInvalidError):
            await auth.refresh_access_token(reader, rotated.refresh_token)
        with pytest.raises(TokenInvalidError):
            await auth.get_current_user(reader, rotated.access_token)


@pytest.mark.asyncio
async def test_http_refresh_reuse_withdraws_replacement_proofs(test_engine):
    auth = SimpleRBAC(
        engine=test_engine, secret_key="synthetic-review-secret-longer-than-32bytes", enable_token_cleanup=False
    )
    await auth.initialize()
    try:
        async with auth.get_session() as session:
            user = await auth.user_service.create_user(
                session, email=f"http-{uuid4().hex}@example.test", password="SyntheticPassword123!"
            )
            original = await auth.auth_service.create_tokens_for_user(session, user)
            await session.commit()
        app = FastAPI()
        auth.instrument_fastapi(app)
        register_exception_handlers(app)
        app.include_router(get_auth_router(auth, prefix="/auth"))
        app.include_router(get_users_router(auth, prefix="/users"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            rotated = await client.post("/auth/refresh", json={"refresh_token": original.refresh_token})
            assert rotated.status_code == 200
            replay = await client.post("/auth/refresh", json={"refresh_token": original.refresh_token})
            assert replay.status_code == 401
            assert (
                await client.post("/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]})
            ).status_code == 401
            assert (
                await client.get("/users/me", headers={"Authorization": f"Bearer {rotated.json()['access_token']}"})
            ).status_code == 401
    finally:
        await auth.shutdown()


@pytest.mark.asyncio
async def test_null_classified_legacy_superuser_is_protected_with_scope_disabled(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="synthetic-review-secret-longer-than-32bytes",
        enable_token_cleanup=False,
        enforce_user_scope=False,
    )
    await auth.initialize()
    try:
        async with auth.get_session() as session:
            limited = User(email=f"limited-{uuid4().hex}@example.test")
            legacy = User(email=f"legacy-{uuid4().hex}@example.test", is_superuser=True, platform_protected=None)
            role = Role(
                name=uuid4().hex,
                display_name="Limited admin",
                permissions=[Permission(name="user:update", display_name="Update")],
            )
            session.add_all([limited, legacy, role])
            await session.flush()
            await auth.role_service.assign_role_to_user(session, user_id=limited.id, role_id=role.id)
            await session.commit()
            target_id = legacy.id
            token = create_access_token(
                {"sub": str(limited.id)}, auth.config.secret_key, audience=auth.config.jwt_audience
            )
        app = FastAPI()
        auth.instrument_fastapi(app)
        register_exception_handlers(app)
        app.include_router(get_users_router(auth, prefix="/users"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            result = await client.patch(
                f"/users/{target_id}", json={"first_name": "Unauthorized"}, headers={"Authorization": f"Bearer {token}"}
            )
            assert result.status_code == 403
        async with auth.get_session() as session:
            assert (await session.get(User, target_id)).first_name is None
    finally:
        await auth.shutdown()
