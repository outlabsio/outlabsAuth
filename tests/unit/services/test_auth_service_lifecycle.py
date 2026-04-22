import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    InvalidCredentialsError,
    RefreshTokenInvalidError,
    TokenExpiredError,
    TokenInvalidError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.token import RefreshToken
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.auth import AuthService, TokenPair
from outlabs_auth.services.user import UserService
from outlabs_auth.utils.jwt import verify_token as jwt_verify_token


async def _create_user(
    test_session,
    auth_config: AuthConfig,
    *,
    email: str,
    password: str = "TestPass123!",
) -> User:
    user_service = UserService(config=auth_config)
    return await user_service.create_user(
        test_session,
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_login_failure_paths_cover_not_found_lockout_and_locked_user(
    test_session,
    auth_config: AuthConfig,
):
    config = auth_config.model_copy(update={"max_login_attempts": 2, "lockout_duration_minutes": 10})
    notifications = SimpleNamespace(emit=AsyncMock())
    observability = MagicMock()
    audit = SimpleNamespace(record_event=AsyncMock())
    service = AuthService(
        config=config,
        notification_service=notifications,
        observability=observability,
        user_audit_service=audit,
    )

    with pytest.raises(InvalidCredentialsError):
        await service.login(
            test_session,
            email="missing@example.com",
            password="WrongPass123!",
            ip_address="127.0.0.1",
        )
    observability.log_login_failed.assert_called_with(
        email="missing@example.com",
        reason="user_not_found",
        method="password",
        failed_attempts=0,
        ip_address="127.0.0.1",
    )

    user = await _create_user(test_session, auth_config, email="lockout@example.com")

    with pytest.raises(InvalidCredentialsError):
        await service.login(
            test_session,
            email=user.email,
            password="WrongPass123!",
            ip_address="10.0.0.1",
            user_agent="bad-agent",
        )
    assert user.failed_login_attempts == 1
    notifications.emit.assert_awaited_once()
    assert notifications.emit.await_args_list[0].args[0] == "user.login_failed"

    with pytest.raises(InvalidCredentialsError):
        await service.login(
            test_session,
            email=user.email,
            password="WrongPass123!",
            ip_address="10.0.0.1",
            user_agent="bad-agent",
        )
    assert user.failed_login_attempts == 2
    assert user.locked_until is not None
    observability.log_account_locked.assert_called_once()
    assert audit.record_event.await_count == 2

    with pytest.raises(AccountLockedError):
        await service.login(
            test_session,
            email=user.email,
            password="TestPass123!",
            ip_address="10.0.0.2",
        )
    assert observability.log_login_failed.call_args_list[-1].kwargs["reason"] == "account_locked"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_login_success_emits_notification_tracks_activity_and_stores_refresh_token(
    test_session,
    auth_config: AuthConfig,
    monkeypatch,
):
    notifications = SimpleNamespace(emit=AsyncMock())
    activity_tracker = SimpleNamespace(track_activity=AsyncMock())
    observability = MagicMock()
    audit = SimpleNamespace(record_event=AsyncMock())
    service = AuthService(
        config=auth_config,
        notification_service=notifications,
        activity_tracker=activity_tracker,
        observability=observability,
        user_audit_service=audit,
    )
    user = await _create_user(test_session, auth_config, email="success@example.com")

    created_coroutines = []

    def fake_create_task(coro):
        created_coroutines.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    async def _fake_verify(plain, hashed):
        return (True, "upgraded-password-hash")

    monkeypatch.setattr(
        "outlabs_auth.services.auth.verify_and_upgrade_password_async",
        _fake_verify,
    )

    _, token_pair = await service.login(
        test_session,
        email=user.email,
        password="TestPass123!",
        device_name="MacBook",
        ip_address="10.0.0.3",
        user_agent="browser",
    )

    assert token_pair.access_token
    assert token_pair.refresh_token
    notifications.emit.assert_awaited_once()
    assert notifications.emit.await_args_list[0].args[0] == "user.login"
    assert len(created_coroutines) == 1
    assert user.hashed_password == "upgraded-password-hash"
    observability.log_login_success.assert_called_once()
    audit.record_event.assert_awaited_once()

    stored_tokens = (
        await test_session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert len(stored_tokens) == 1
    assert stored_tokens[0].device_name == "MacBook"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_logout_covers_stateless_blacklist_and_stateful_revocation(
    test_session,
    auth_config: AuthConfig,
):
    stateless_config = auth_config.model_copy(
        update={"store_refresh_tokens": False, "enable_token_blacklist": True}
    )
    stateless_service = AuthService(config=stateless_config)
    redis_client = SimpleNamespace(is_available=True, set=AsyncMock(return_value=True))

    blacklisted = await stateless_service.logout(
        test_session,
        refresh_token="unused",
        blacklist_access_token=True,
        access_token_jti="access-jti",
        redis_client=redis_client,
    )
    assert blacklisted is True
    redis_client.set.assert_awaited_once_with(
        "blacklist:jwt:access-jti",
        "revoked",
        ttl=stateless_config.access_token_expire_minutes * 60,
    )

    observability = MagicMock()
    stateful_service = AuthService(
        config=auth_config.model_copy(update={"enable_token_blacklist": True}),
        observability=observability,
    )
    user = await _create_user(test_session, auth_config, email="logout@example.com")
    token_pair = await stateful_service.create_tokens_for_user(test_session, user)
    stateful_redis = SimpleNamespace(is_available=True, set=AsyncMock(return_value=True))

    assert await stateful_service.logout(test_session, "missing-refresh-token") is False
    assert (
        await stateful_service.logout(
            test_session,
            token_pair.refresh_token,
            blacklist_access_token=True,
            access_token_jti="stateful-jti",
            redis_client=stateful_redis,
        )
        is True
    )
    observability.log_logout.assert_called_once()
    stateful_redis.set.assert_awaited_once()
    assert await stateful_service.logout(test_session, token_pair.refresh_token) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_refresh_access_token_covers_invalid_and_missing_payload_branches(
    test_session,
    auth_config: AuthConfig,
    monkeypatch,
):
    observability = MagicMock()
    service = AuthService(config=auth_config, observability=observability)

    monkeypatch.setattr(
        "outlabs_auth.services.auth.verify_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(TokenExpiredError(message="expired")),
    )
    with pytest.raises(TokenExpiredError):
        await service.refresh_access_token(test_session, "expired")
    observability.log_token_refreshed.assert_called_with(
        user_id="unknown",
        status="failed",
        reason="token_expired",
    )

    monkeypatch.setattr(
        "outlabs_auth.services.auth.verify_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(TokenInvalidError(message="invalid")),
    )
    with pytest.raises(RefreshTokenInvalidError, match="Invalid refresh token"):
        await service.refresh_access_token(test_session, "invalid")
    observability.log_token_refreshed.assert_called_with(
        user_id="unknown",
        status="failed",
        reason="invalid_token",
    )

    monkeypatch.setattr("outlabs_auth.services.auth.verify_token", lambda *args, **kwargs: {})
    with pytest.raises(RefreshTokenInvalidError, match="missing user ID"):
        await service.refresh_access_token(test_session, "missing-sub")

    token_value = "missing-db-token"
    monkeypatch.setattr(
        "outlabs_auth.services.auth.verify_token",
        lambda *args, **kwargs: {"sub": str(uuid4())},
    )
    with pytest.raises(RefreshTokenInvalidError, match="not found"):
        await service.refresh_access_token(test_session, token_value)

    token_user = await _create_user(test_session, auth_config, email="expired-refresh@example.com")
    token_hash = service._hash_token(token_value)
    expired_token = RefreshToken(
        user_id=token_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    test_session.add(expired_token)
    await test_session.flush()

    monkeypatch.setattr(
        "outlabs_auth.services.auth.verify_token",
        lambda *args, **kwargs: {"sub": str(token_user.id)},
    )
    with pytest.raises(RefreshTokenInvalidError, match="expired"):
        await service.refresh_access_token(test_session, token_value)

    expired_token.is_revoked = True
    expired_token.revoked_at = datetime.now(timezone.utc)
    expired_token.revoked_reason = "manual"
    await test_session.flush()
    with pytest.raises(RefreshTokenInvalidError, match="revoked"):
        await service.refresh_access_token(test_session, token_value)

    mock_session = AsyncMock()
    valid_token_model = SimpleNamespace(
        is_valid=lambda: True,
        is_revoked=False,
        revoked_at=None,
        revoked_reason=None,
    )
    mock_session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=valid_token_model)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
    )

    with pytest.raises(UserNotFoundError):
        await service.refresh_access_token(mock_session, token_value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_refresh_access_token_revokes_stale_token_and_tracks_success(
    test_session,
    auth_config: AuthConfig,
    monkeypatch,
):
    observability = MagicMock()
    activity_tracker = SimpleNamespace(track_activity=AsyncMock())
    service = AuthService(
        config=auth_config,
        observability=observability,
        activity_tracker=activity_tracker,
    )
    user = await _create_user(test_session, auth_config, email="refresh@example.com")
    token_pair = await service.create_tokens_for_user(test_session, user)

    created_coroutines = []

    def fake_create_task(coro):
        created_coroutines.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    refreshed = await service.refresh_access_token(test_session, token_pair.refresh_token)
    assert refreshed.refresh_token == token_pair.refresh_token
    observability.log_token_refreshed.assert_called_with(user_id=str(user.id), status="success")
    assert len(created_coroutines) == 1

    user.last_password_change = datetime.now(timezone.utc) + timedelta(seconds=1)
    await test_session.flush()

    with pytest.raises(RefreshTokenInvalidError, match="no longer valid"):
        await service.refresh_access_token(test_session, token_pair.refresh_token)

    token_hash = service._hash_token(token_pair.refresh_token)
    stored_token = (
        await test_session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one()
    assert stored_token.is_revoked is True
    assert stored_token.revoked_reason == "Password changed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_get_current_user_covers_missing_missing_user_and_stale_token(
    test_session,
    auth_config: AuthConfig,
    monkeypatch,
):
    service = AuthService(config=auth_config)

    monkeypatch.setattr("outlabs_auth.services.auth.verify_token", lambda *args, **kwargs: {})
    with pytest.raises(TokenInvalidError, match="missing user ID"):
        await service.get_current_user(test_session, "missing-sub")

    monkeypatch.setattr(
        "outlabs_auth.services.auth.verify_token",
        lambda *args, **kwargs: {"sub": str(uuid4())},
    )
    with pytest.raises(UserNotFoundError):
        await service.get_current_user(test_session, "missing-user")

    user = await _create_user(test_session, auth_config, email="current-user@example.com")
    token_pair = await AuthService(config=auth_config).create_tokens_for_user(test_session, user)
    monkeypatch.setattr("outlabs_auth.services.auth.verify_token", jwt_verify_token)
    assert (await service.get_current_user(test_session, token_pair.access_token)).id == user.id
    user.last_password_change = datetime.now(timezone.utc) + timedelta(seconds=1)
    await test_session.flush()

    with pytest.raises(TokenInvalidError, match="no longer valid"):
        await service.get_current_user(test_session, token_pair.access_token)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_revoke_all_tokens_reset_password_and_accept_invite_cover_notifications(
    test_session,
    auth_config: AuthConfig,
):
    notifications = SimpleNamespace(emit=AsyncMock())
    audit = SimpleNamespace(record_event=AsyncMock())
    service = AuthService(
        config=auth_config,
        notification_service=notifications,
        user_audit_service=audit,
    )

    disabled_service = AuthService(
        config=auth_config.model_copy(update={"store_refresh_tokens": False})
    )
    user = await _create_user(test_session, auth_config, email="reset@example.com")
    assert await disabled_service.revoke_all_user_tokens(test_session, user.id) == 0

    first_tokens = await service.create_tokens_for_user(test_session, user, device_name="reset-1")
    await service.create_tokens_for_user(test_session, user, device_name="reset-2")

    plain_reset_token = await service.generate_reset_token(test_session, user)
    reset_user = await service.reset_password(
        test_session,
        plain_reset_token,
        new_password="NewPass123!",
    )
    assert reset_user.password_reset_token is None
    assert reset_user.password_reset_expires is None
    notifications.emit.assert_any_await(
        "user.password_reset",
        data={
            "user_id": str(user.id),
            "email": user.email,
            "reset_at": reset_user.last_password_change.isoformat(),
        },
    )
    token_hash = service._hash_token(first_tokens.refresh_token)
    revoked_tokens = (
        await test_session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert revoked_tokens
    assert all(token.is_revoked for token in revoked_tokens)
    assert any(token.token_hash == token_hash for token in revoked_tokens)

    plain_invite_token = "invite-token"
    invited_user = User(
        email="invited-audit@example.com",
        status=UserStatus.INVITED,
        invite_token=hashlib.sha256(plain_invite_token.encode()).hexdigest(),
        invite_token_expires=datetime.now(timezone.utc) + timedelta(days=1),
    )
    test_session.add(invited_user)
    await test_session.flush()

    accepted = await service.accept_invite(
        test_session,
        token=plain_invite_token,
        new_password="InvitePass123!",
    )
    assert accepted.status == UserStatus.ACTIVE
    notifications.emit.assert_any_await(
        "user.invite_accepted",
        data={
            "user_id": str(invited_user.id),
            "email": invited_user.email,
            "accepted_at": accepted.last_password_change.isoformat(),
        },
    )
    assert audit.record_event.await_count >= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_reset_password_expired_token_clears_token_and_commits():
    config = AuthConfig(secret_key="test-secret-key")
    service = AuthService(config=config)
    session = AsyncMock()

    user = User(
        id=uuid4(),
        email="expired-reset@example.com",
        password_reset_token=hashlib.sha256(b"expired-token").hexdigest(),
        password_reset_expires=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=user)
    )
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    with pytest.raises(TokenExpiredError):
        await service.reset_password(session, "expired-token", "NewPass123!")

    assert user.password_reset_token is None
    assert user.password_reset_expires is None
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_create_tokens_for_locked_user_and_invalid_reset_token_branches(
    auth_config: AuthConfig,
):
    service = AuthService(config=auth_config, user_audit_service=SimpleNamespace(record_event=AsyncMock()))

    locked_user = User(
        id=uuid4(),
        email="locked-create@example.com",
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    with pytest.raises(AccountLockedError):
        await service.create_tokens_for_user(AsyncMock(), locked_user)

    missing_reset_session = AsyncMock()
    missing_reset_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    )
    with pytest.raises(TokenInvalidError, match="Invalid or expired reset token"):
        await service.reset_password(missing_reset_session, "missing-token", "NewPass123!")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_service_verify_password_and_helper_methods_cover_remaining_branches(
    auth_config: AuthConfig,
):
    service = AuthService(config=auth_config)

    assert await service.verify_password(User(email="no-password@example.com"), "irrelevant") is False
    assert TokenPair("access", "refresh", expires_in=123).to_dict() == {
        "access_token": "access",
        "refresh_token": "refresh",
        "token_type": "bearer",
        "expires_in": 123,
    }
    hashed_user = User(email="with-password@example.com", hashed_password="stored-password-hash")
    assert await service.verify_password(hashed_user, "secret") is False

    now = datetime.now(timezone.utc)
    assert service._normalize_token_timestamp({"iat_ms": now.timestamp() * 1000}) is not None
    assert service._normalize_token_timestamp({"iat_ms": "invalid"}) is None
    assert service._normalize_token_timestamp({"iat": now.timestamp()}) is not None
    assert service._normalize_token_timestamp(now.replace(tzinfo=None)).tzinfo == timezone.utc
    assert service._normalize_token_timestamp(None) is None
    assert service._normalize_token_timestamp("not-a-timestamp") is None

    assert service._token_is_stale({"iat": now.timestamp()}, None) is False
    assert service._token_is_stale({"iat": "bad"}, now) is True
    assert service._token_is_stale({"iat": now.timestamp() - 60}, now) is True
    assert service._token_is_stale({"iat": now.timestamp() + 60}, now) is False

    with pytest.raises(AccountInactiveError, match="Account is pending_review"):
        service._check_user_status(SimpleNamespace(status=SimpleNamespace(value="pending_review")))
    with pytest.raises(AccountInactiveError, match="Account has been deleted"):
        service._check_user_status(
            User(
                email="deleted@example.com",
                status=UserStatus.DELETED,
                deleted_at=now,
            )
        )
