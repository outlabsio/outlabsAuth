from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.services.user import UserService
from outlabs_auth.utils.validation import validate_phone


@pytest.mark.unit
def test_validate_phone_accepts_e164():
    assert validate_phone(" +1 5551234567 ") == "+15551234567"


@pytest.mark.unit
def test_validate_phone_rejects_local_format():
    with pytest.raises(InvalidInputError):
        validate_phone("555-123-4567")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_fields_sets_phone_and_clears_verification():
    config = AuthConfig(secret_key="x" * 32)
    service = UserService(config)
    user_id = uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="agent@example.com",
        first_name="Jane",
        last_name="Agent",
        phone=None,
        phone_verified=True,
        email_verified=True,
        root_entity_id=None,
    )

    service.get_by_id = AsyncMock(return_value=user)
    service.update = AsyncMock(side_effect=lambda _session, updated: updated)
    service.user_audit_service = None

    updated = await service.update_user_fields(
        MagicMock(),
        user_id,
        phone="+15559876543",
        phone_provided=True,
    )

    assert updated.phone == "+15559876543"
    assert updated.phone_verified is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_fields_clears_phone_when_null_provided():
    config = AuthConfig(secret_key="x" * 32)
    service = UserService(config)
    user_id = uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="agent@example.com",
        first_name="Jane",
        last_name="Agent",
        phone="+15551234567",
        phone_verified=True,
        email_verified=True,
        root_entity_id=None,
    )

    service.get_by_id = AsyncMock(return_value=user)
    service.update = AsyncMock(side_effect=lambda _session, updated: updated)
    service.user_audit_service = None

    updated = await service.update_user_fields(
        MagicMock(),
        user_id,
        phone=None,
        phone_provided=True,
    )

    assert updated.phone is None
    assert updated.phone_verified is False
