from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from jose import jwt

from outlabs_auth.core.exceptions import TokenInvalidError
from outlabs_auth.authentication.strategy import (
    AnonymousStrategy,
    ApiKeyStrategy,
    JWTStrategy,
    ServiceTokenStrategy,
    SuperuserStrategy,
)


def _make_access_token(secret: str, **claims: object) -> str:
    payload = {
        "sub": "user-123",
        "aud": "outlabs-auth",
        "exp": int(time.time()) + 300,
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_service_token(secret: str, **claims: object) -> str:
    payload = {
        "sub": "service-123",
        "service_name": "worker",
        "permissions": ["jobs:run"],
        "type": "service",
        "aud": "outlabs-auth:service",
        "exp": int(time.time()) + 300,
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_user(user_id: str = "user-123", can_authenticate: bool = True, **extra: object):
    user = SimpleNamespace(id=user_id, **extra)
    user.can_authenticate = lambda: can_authenticate
    return user


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_authenticates_active_user():
    user = _make_user(last_password_change=None)
    user_service = SimpleNamespace(get_user_by_id=AsyncMock(return_value=user))
    session = object()
    strategy = JWTStrategy(secret="test-secret")
    token = _make_access_token("test-secret", jti="jwt-123")

    result = await strategy.authenticate(token, user_service=user_service, session=session)

    assert result == {
        "user": user,
        "user_id": "user-123",
        "source": "jwt",
        "metadata": {
            "sub": "user-123",
            "aud": "outlabs-auth",
            "exp": pytest.approx(result["metadata"]["exp"]),
            "jti": "jwt-123",
        },
        "jti": "jwt-123",
    }
    user_service.get_user_by_id.assert_awaited_once_with(session, "user-123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_rejects_blacklisted_token_before_db_lookup():
    redis_client = SimpleNamespace(
        is_available=True,
        exists=AsyncMock(return_value=True),
    )
    user_service = SimpleNamespace(get_user_by_id=AsyncMock(side_effect=AssertionError("should not fetch user")))
    strategy = JWTStrategy(secret="test-secret", redis_client=redis_client)
    token = _make_access_token("test-secret", jti="jwt-blacklisted")

    result = await strategy.authenticate(token, user_service=user_service, session=object())

    assert result is None
    redis_client.exists.assert_awaited_once_with("blacklist:jwt:jwt-blacklisted")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_rejects_stale_token_after_password_change():
    last_password_change = datetime.now(timezone.utc)
    stale_iat = last_password_change - timedelta(minutes=5)
    user = _make_user(
        last_password_change=last_password_change,
    )
    user_service = SimpleNamespace(get_user_by_id=AsyncMock(return_value=user))
    strategy = JWTStrategy(secret="test-secret")
    token = _make_access_token(
        "test-secret",
        iat=int(stale_iat.timestamp()),
        iat_ms=int(stale_iat.timestamp() * 1000),
    )

    result = await strategy.authenticate(token, user_service=user_service, session=object())

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_returns_none_when_payload_missing_subject():
    strategy = JWTStrategy(secret="test-secret")
    token = jwt.encode(
        {"aud": "outlabs-auth", "exp": int(time.time()) + 300},
        "test-secret",
        algorithm="HS256",
    )

    result = await strategy.authenticate(token, user_service=SimpleNamespace(), session=object())

    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_returns_none_without_db_session():
    user_service = SimpleNamespace(get_user_by_id=AsyncMock())
    strategy = JWTStrategy(secret="test-secret")
    token = _make_access_token("test-secret")

    result = await strategy.authenticate(token, user_service=user_service, session=None)

    assert result is None
    user_service.get_user_by_id.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_returns_none_without_user_service_and_on_decode_failures():
    strategy = JWTStrategy(secret="test-secret")
    valid_token = _make_access_token("test-secret")
    expired_token = jwt.encode(
        {
            "sub": "user-123",
            "aud": "outlabs-auth",
            "exp": int(time.time()) - 5,
        },
        "test-secret",
        algorithm="HS256",
    )

    assert await strategy.authenticate(valid_token, session=object()) is None
    assert await strategy.authenticate(expired_token, user_service=SimpleNamespace(), session=object()) is None
    assert await strategy.authenticate("not-a-jwt", user_service=SimpleNamespace(), session=object()) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwt_strategy_returns_none_on_unexpected_user_lookup_error():
    user_service = SimpleNamespace(get_user_by_id=AsyncMock(side_effect=RuntimeError("db offline")))
    strategy = JWTStrategy(secret="test-secret")
    token = _make_access_token("test-secret")

    result = await strategy.authenticate(token, user_service=user_service, session=object())

    assert result is None


@pytest.mark.unit
def test_jwt_strategy_token_timestamp_prefers_iat_ms_and_staleness_defaults_closed():
    issued_at = datetime.now(timezone.utc)
    precise_payload = {
        "iat": int((issued_at - timedelta(minutes=1)).timestamp()),
        "iat_ms": int(issued_at.timestamp() * 1000),
    }

    normalized = JWTStrategy._normalize_token_timestamp(precise_payload)

    assert normalized == issued_at.replace(microsecond=0) or abs((normalized - issued_at).total_seconds()) < 0.001
    assert JWTStrategy._token_is_stale({"iat": "bad"}, issued_at) is True


@pytest.mark.unit
def test_jwt_strategy_normalize_timestamp_handles_invalid_and_naive_values():
    naive_dt = datetime(2026, 1, 1, 12, 0, 0)

    assert JWTStrategy._normalize_token_timestamp({"iat_ms": "bad-ms"}) is None
    assert JWTStrategy._normalize_token_timestamp(None) is None
    assert JWTStrategy._normalize_token_timestamp(naive_dt) == naive_dt.replace(tzinfo=timezone.utc)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_strategy_returns_key_metadata_for_owner_lookup():
    api_key = SimpleNamespace(id="key-123", owner_id="user-123", prefix="olk_live")
    user = _make_user()
    session = object()
    api_key_service = SimpleNamespace(
        verify_api_key=AsyncMock(return_value=(api_key, 7)),
        get_api_key_scopes=AsyncMock(return_value=["users:read", "users:write"]),
    )
    user_service = SimpleNamespace(get_user_by_id=AsyncMock(return_value=user))
    request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.10"))
    strategy = ApiKeyStrategy()

    result = await strategy.authenticate(
        "olk_live.secret",
        api_key_service=api_key_service,
        session=session,
        user_service=user_service,
        request=request,
    )

    assert result == {
        "user": user,
        "user_id": "user-123",
        "source": "api_key",
        "api_key": api_key,
        "metadata": {
            "key_id": "key-123",
            "key_prefix": "olk_live",
            "scopes": ["users:read", "users:write"],
            "usage_count": 7,
        },
    }
    api_key_service.verify_api_key.assert_awaited_once_with(
        session,
        "olk_live.secret",
        ip_address="203.0.113.10",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_strategy_returns_none_when_owner_not_found_via_session_fallback():
    api_key = SimpleNamespace(id="key-123", owner_id="user-missing", prefix="olk_live")
    session = SimpleNamespace(get=AsyncMock(return_value=None))
    api_key_service = SimpleNamespace(
        verify_api_key=AsyncMock(return_value=(api_key, 1)),
        get_api_key_scopes=AsyncMock(),
    )
    strategy = ApiKeyStrategy()

    result = await strategy.authenticate(
        "olk_live.secret",
        api_key_service=api_key_service,
        session=session,
        user_service=None,
    )

    assert result is None
    session.get.assert_awaited_once()
    api_key_service.get_api_key_scopes.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_strategy_handles_missing_services_empty_lookup_and_exceptions():
    strategy = ApiKeyStrategy()

    assert await strategy.authenticate("olk_live.secret", api_key_service=None, session=object()) is None
    assert await strategy.authenticate(
        "olk_live.secret",
        api_key_service=SimpleNamespace(),
        session=None,
    ) is None

    verify_returns_none = SimpleNamespace(
        verify_api_key=AsyncMock(return_value=(None, 0)),
        get_api_key_scopes=AsyncMock(),
    )
    assert (
        await strategy.authenticate(
            "olk_live.secret",
            api_key_service=verify_returns_none,
            session=object(),
        )
        is None
    )
    verify_returns_none.get_api_key_scopes.assert_not_awaited()

    failing_service = SimpleNamespace(
        verify_api_key=AsyncMock(side_effect=RuntimeError("redis unavailable")),
    )
    assert (
        await strategy.authenticate(
            "olk_live.secret",
            api_key_service=failing_service,
            session=object(),
        )
        is None
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_strategy_uses_session_lookup_when_user_service_is_missing():
    api_key = SimpleNamespace(id="key-123", owner_id="user-123", prefix="olk_live")
    user = _make_user()
    session = SimpleNamespace(get=AsyncMock(return_value=user))
    api_key_service = SimpleNamespace(
        verify_api_key=AsyncMock(return_value=(api_key, 2)),
        get_api_key_scopes=AsyncMock(return_value=["users:read"]),
    )
    request = SimpleNamespace(client=SimpleNamespace(host="198.51.100.24"))
    strategy = ApiKeyStrategy()

    result = await strategy.authenticate(
        "olk_live.secret",
        api_key_service=api_key_service,
        session=session,
        user_service=None,
        request=request,
    )

    assert result["user"] is user
    assert result["metadata"]["scopes"] == ["users:read"]
    session.get.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_strategy_returns_principal_backed_auth_result():
    principal = SimpleNamespace(id="principal-123", allowed_scopes=["jobs:run"])
    api_key = SimpleNamespace(
        id="key-123",
        owner_id=None,
        integration_principal_id="principal-123",
        prefix="olk_live",
        key_kind="system_integration",
        owner_type="integration_principal",
        resolved_owner_id="principal-123",
        entity_id=None,
    )
    resolved_owner = SimpleNamespace(
        user=None,
        integration_principal=principal,
        owner_id="principal-123",
    )
    session = object()
    api_key_service = SimpleNamespace(
        verify_api_key=AsyncMock(return_value=(api_key, 5)),
        get_api_key_scopes=AsyncMock(return_value=["jobs:run"]),
        resolve_api_key_owner=AsyncMock(return_value=resolved_owner),
    )
    strategy = ApiKeyStrategy()

    result = await strategy.authenticate(
        "olk_live.secret",
        api_key_service=api_key_service,
        session=session,
        request=SimpleNamespace(client=SimpleNamespace(host="203.0.113.20")),
    )

    assert result == {
        "user": None,
        "user_id": None,
        "integration_principal": principal,
        "integration_principal_id": "principal-123",
        "source": "api_key",
        "api_key": api_key,
        "metadata": {
            "key_id": "key-123",
            "key_prefix": "olk_live",
            "key_kind": "system_integration",
            "owner_type": "integration_principal",
            "owner_id": "principal-123",
            "scopes": ["jobs:run"],
            "principal_allowed_scopes": ["jobs:run"],
            "usage_count": 5,
        },
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_token_strategy_accepts_local_jwt_service_token():
    strategy = ServiceTokenStrategy(secret="service-secret")
    token = _make_service_token("service-secret")

    result = await strategy.authenticate(token)

    assert result == {
        "user": None,
        "user_id": None,
        "source": "service_token",
        "service_id": "service-123",
        "service_name": "worker",
        "metadata": {
            "sub": "service-123",
            "service_name": "worker",
            "permissions": ["jobs:run"],
            "type": "service",
            "aud": "outlabs-auth:service",
            "exp": pytest.approx(result["metadata"]["exp"]),
        },
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_token_strategy_accepts_external_validator_payload():
    validator = SimpleNamespace(
        validate_service_token=lambda _: {
            "sub": "service-abc",
            "service_name": "queue-consumer",
            "permissions": ["jobs:read"],
        }
    )
    strategy = ServiceTokenStrategy(secret="unused")

    result = await strategy.authenticate("opaque-token", service_token_service=validator)

    assert result["service_id"] == "service-abc"
    assert result["service_name"] == "queue-consumer"
    assert result["metadata"]["permissions"] == ["jobs:read"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_token_strategy_rejects_wrong_type_missing_fields_and_failure_paths():
    strategy = ServiceTokenStrategy(secret="service-secret")
    wrong_type_token = _make_service_token("service-secret", type="access")
    missing_permissions_token = jwt.encode(
        {
            "sub": "service-123",
            "service_name": "worker",
            "permissions": "jobs:run",
            "type": "service",
            "aud": "outlabs-auth:service",
            "exp": int(time.time()) + 300,
        },
        "service-secret",
        algorithm="HS256",
    )
    expired_token = jwt.encode(
        {
            "sub": "service-123",
            "service_name": "worker",
            "permissions": ["jobs:run"],
            "type": "service",
            "aud": "outlabs-auth:service",
            "exp": int(time.time()) - 5,
        },
        "service-secret",
        algorithm="HS256",
    )

    assert await strategy.authenticate(wrong_type_token) is None
    assert await strategy.authenticate(missing_permissions_token) is None
    assert await strategy.authenticate(expired_token) is None
    assert await strategy.authenticate("invalid.jwt.token") is None

    token_invalid_validator = SimpleNamespace(
        validate_service_token=lambda _: (_ for _ in ()).throw(TokenInvalidError("bad token"))
    )
    runtime_error_validator = SimpleNamespace(
        validate_service_token=lambda _: (_ for _ in ()).throw(RuntimeError("validator offline"))
    )

    assert await strategy.authenticate("opaque", service_token_service=token_invalid_validator) is None
    assert await strategy.authenticate("opaque", service_token_service=runtime_error_validator) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_superuser_strategy_fetches_superuser_context():
    superuser = SimpleNamespace(id="root-user")
    user_service = SimpleNamespace(get_first_superuser=AsyncMock(return_value=superuser))
    strategy = SuperuserStrategy("top-secret")

    result = await strategy.authenticate("top-secret", user_service=user_service)

    assert result == {
        "user": superuser,
        "user_id": "root-user",
        "source": "superuser",
        "metadata": {"superuser": True},
    }
    user_service.get_first_superuser.assert_awaited_once_with()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_superuser_strategy_handles_missing_user_record_and_wrong_credentials():
    failing_user_service = SimpleNamespace(get_first_superuser=AsyncMock(side_effect=RuntimeError("db offline")))
    strategy = SuperuserStrategy("top-secret")

    result = await strategy.authenticate("top-secret", user_service=failing_user_service)

    assert result == {
        "user": None,
        "user_id": None,
        "source": "superuser",
        "metadata": {"superuser": True},
    }
    assert await strategy.authenticate("wrong-secret", user_service=failing_user_service) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_anonymous_strategy_returns_anonymous_context():
    result = await AnonymousStrategy().authenticate("")

    assert result == {
        "user": None,
        "user_id": None,
        "source": "anonymous",
        "metadata": {"anonymous": True},
    }
