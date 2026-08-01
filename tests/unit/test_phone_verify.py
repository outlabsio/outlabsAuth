from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError, TokenInvalidError
from outlabs_auth.models.sql.enums import AuthChallengeType
from outlabs_auth.services.auth import AuthService
from outlabs_auth.services.user import UserService


@pytest.mark.unit
def test_phone_verify_hash_roundtrip():
    config = AuthConfig(secret_key="x" * 32)
    service = AuthService(config)
    phone = "+15551234567"
    code = "123456"
    stored = service._hash_phone_verify_code(code, phone)
    assert service._verify_phone_verify_code_hash(code, phone, stored) is True
    assert service._verify_phone_verify_code_hash("000000", phone, stored) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_phone_verify_code_sets_phone_verified():
    config = AuthConfig(secret_key="x" * 32)
    service = AuthService(config)
    user_id = uuid4()
    phone = "+15551234567"
    code = "654321"
    now = datetime.now(timezone.utc)
    challenge = SimpleNamespace(
        user_id=user_id,
        challenge_type=AuthChallengeType.PHONE_VERIFY,
        token_hash=service._hash_phone_verify_code(code, phone),
        recipient=phone,
        expires_at=now + timedelta(minutes=10),
        used_at=None,
        requested_ip_address=None,
    )
    user = SimpleNamespace(
        id=user_id,
        email="agent@example.com",
        phone=phone,
        phone_verified=False,
        root_entity_id=None,
    )

    class UserResult:
        def scalar_one_or_none(self):
            return user

    class ChallengeResult:
        def scalars(self):
            return self

        def all(self):
            return [challenge]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[UserResult(), ChallengeResult()])
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    service.user_audit_service = None
    service.notifications = None

    updated = await service.verify_phone_verify_code(session, user, code=code)

    assert updated.phone_verified is True
    assert challenge.used_at is not None
    session.refresh.assert_awaited_once_with(user)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_request_phone_verification_requires_phone():
    config = AuthConfig(secret_key="x" * 32)
    service = UserService(config, auth_service=AuthService(config))
    user = SimpleNamespace(
        id=uuid4(),
        email="agent@example.com",
        phone=None,
        phone_verified=False,
    )
    service.get_by_id = AsyncMock(return_value=user)

    with pytest.raises(InvalidInputError):
        await service.request_phone_verification(MagicMock(), user.id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confirm_phone_verification_rejects_bad_code():
    config = AuthConfig(secret_key="x" * 32)
    auth_service = AuthService(config)
    service = UserService(config, auth_service=auth_service)
    user_id = uuid4()
    phone = "+15551234567"
    user = SimpleNamespace(
        id=user_id,
        email="agent@example.com",
        phone=phone,
        phone_verified=False,
        root_entity_id=None,
    )
    challenge = SimpleNamespace(
        user_id=user_id,
        challenge_type=AuthChallengeType.PHONE_VERIFY,
        token_hash=auth_service._hash_phone_verify_code("111111", phone),
        recipient=phone,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        used_at=None,
        requested_ip_address=None,
    )

    class UserResult:
        def scalar_one_or_none(self):
            return user

    class ChallengeResult:
        def scalars(self):
            return self

        def all(self):
            return [challenge]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[UserResult(), ChallengeResult()])
    session.refresh = AsyncMock()
    service.get_by_id = AsyncMock(return_value=user)
    auth_service.user_audit_service = None

    with pytest.raises(TokenInvalidError):
        await service.confirm_phone_verification(session, user_id, code="000000")
