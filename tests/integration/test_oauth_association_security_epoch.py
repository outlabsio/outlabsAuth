"""Real state consumption and retained-account transitions during enrollment."""

from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
import asyncio

from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.oauth.state import generate_state_token
from outlabs_auth.routers.oauth_associate import get_oauth_associate_router
from outlabs_auth.routers.oauth_state_store import issue_oauth_state, oauth_state_cookie_name
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.user import UserService


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["none", "revoke", "password", "reset", "suspend", "delete_restore"])
async def test_pending_association_rechecks_security_at_commit(test_session, auth_config, monkeypatch, change):
    user = User(email=f"enrollment-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    user_id = user.id
    users = UserService(auth_config)
    auth = AuthService(auth_config)
    secret = "synthetic-association-state-secret"
    state = generate_state_token({"sub": str(user.id), "security_epoch": 0}, secret, lifetime_seconds=600)
    response = Response()
    await issue_oauth_state(
        session=test_session,
        response=response,
        state=state,
        provider="github",
        flow="associate",
        user_id=user.id,
        cookie_secure=False,
    )
    cookie = SimpleCookie(response.headers["set-cookie"])
    request = SimpleNamespace(
        cookies={
            oauth_state_cookie_name("github", "associate"): cookie[oauth_state_cookie_name("github", "associate")].value
        }
    )
    if change == "revoke":
        await auth.revoke_all_user_tokens(test_session, user.id)
    elif change == "password":
        await users.change_password(test_session, user.id, "SyntheticPassword123!")
    elif change == "reset":
        user.password_reset_token = auth._hash_token("synthetic-reset")
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        await test_session.commit()
        await auth.reset_password(test_session, "synthetic-reset", "SyntheticPassword123!")
    elif change == "suspend":
        await users.update_user_status(test_session, user.id, UserStatus.SUSPENDED)
        await users.update_user_status(test_session, user.id, UserStatus.ACTIVE)
    elif change == "delete_restore":
        await users.delete_user(test_session, user.id)
        await users.restore_user(test_session, user.id)
    await test_session.commit()
    host = SimpleNamespace(
        config=auth_config,
        user_service=users,
        uow=None,
        deps=SimpleNamespace(require_auth=lambda **kwargs: lambda: None),
    )
    provider = SimpleNamespace(name="github")
    router = get_oauth_associate_router(
        provider, host, secret, prefix="/link", redirect_url="https://example.test/link/callback"
    )
    callback = next(route.endpoint for route in router.routes if route.path.endswith("/callback"))
    import outlabs_auth.routers.oauth_associate as module

    monkeypatch.setattr(
        module,
        "get_oauth_user_info",
        AsyncMock(
            return_value=SimpleNamespace(
                provider_user_id=uuid4().hex,
                email="provider@example.test",
                email_verified=True,
            )
        ),
    )
    monkeypatch.setattr(module, "validate_oidc_nonce", AsyncMock())
    kwargs = dict(
        request=request,
        response=Response(),
        session=test_session,
        code=None,
        state=state,
        error=None,
        access_token_state=({"access_token": "synthetic"}, state),
    )
    if change == "none":
        result = await callback(**kwargs)
        assert result.provider == "github"
    else:
        with pytest.raises(HTTPException) as exc:
            await callback(**kwargs)
        assert exc.value.status_code == 401
        await test_session.rollback()
    accounts = (
        (await test_session.execute(select(SocialAccount).where(SocialAccount.user_id == user_id))).scalars().all()
    )
    assert len(accounts) == int(change == "none")


@pytest.mark.asyncio
async def test_association_commit_serializes_with_security_revocation(
    test_engine, test_session, auth_config, monkeypatch
):
    user = User(email=f"serialized-{uuid4().hex}@example.test")
    test_session.add(user)
    await test_session.commit()
    user_id = user.id
    users = UserService(auth_config)
    auth = AuthService(auth_config)
    locked, release, writer_started = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def hook(*args):
        locked.set()
        await release.wait()

    users.on_after_oauth_associate = hook
    secret = "synthetic-association-state-secret"
    state = generate_state_token({"sub": str(user_id), "security_epoch": 0}, secret, lifetime_seconds=600)
    response = Response()
    await issue_oauth_state(
        session=test_session,
        response=response,
        state=state,
        provider="github",
        flow="associate",
        user_id=user_id,
        cookie_secure=False,
    )
    cookie_name = oauth_state_cookie_name("github", "associate")
    request = SimpleNamespace(cookies={cookie_name: SimpleCookie(response.headers["set-cookie"])[cookie_name].value})
    host = SimpleNamespace(
        config=auth_config,
        user_service=users,
        uow=None,
        deps=SimpleNamespace(require_auth=lambda **kwargs: lambda: None),
    )
    router = get_oauth_associate_router(
        SimpleNamespace(name="github"), host, secret, prefix="/link", redirect_url="https://example.test/link/callback"
    )
    callback = next(route.endpoint for route in router.routes if route.path.endswith("/callback"))
    import outlabs_auth.routers.oauth_associate as module

    monkeypatch.setattr(
        module,
        "get_oauth_user_info",
        AsyncMock(
            return_value=SimpleNamespace(
                provider_user_id=uuid4().hex, email="provider@example.test", email_verified=True
            )
        ),
    )
    monkeypatch.setattr(module, "validate_oidc_nonce", AsyncMock())
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    pid = []

    async def enroll():
        async with factory() as session:
            return await callback(
                request=request,
                response=Response(),
                session=session,
                code=None,
                state=state,
                error=None,
                access_token_state=({"access_token": "synthetic"}, state),
            )

    async def revoke():
        async with factory() as session:
            pid.append((await session.execute(text("SELECT pg_backend_pid()"))).scalar_one())
            writer_started.set()
            await auth.revoke_all_user_tokens(session, user_id)
            await session.commit()

    enrollment = asyncio.create_task(enroll())
    revocation = None
    try:
        await asyncio.wait_for(locked.wait(), 5)
        revocation = asyncio.create_task(revoke())
        await asyncio.wait_for(writer_started.wait(), 5)
        blocked = False
        for _ in range(100):
            async with test_engine.connect() as observer:
                blocked = (
                    await observer.execute(
                        text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid[0]}
                    )
                ).scalar_one()
            if blocked:
                break
            await asyncio.sleep(0.01)
        assert blocked, "security writer must wait for enrollment's user-row lock"
        assert not revocation.done()
    finally:
        release.set()
        assert (await asyncio.wait_for(enrollment, 5)).provider == "github"
        if revocation is not None:
            await asyncio.wait_for(revocation, 5)
    async with factory() as reader:
        assert (await reader.get(User, user_id)).session_security_epoch == 1
