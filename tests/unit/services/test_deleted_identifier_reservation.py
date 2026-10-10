"""TI-04: ordinary profile editing cannot release a retained identifier."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidInputError, UserAlreadyExistsError
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.user import UserService


@pytest.mark.asyncio
async def test_deleted_identifier_change_is_rejected_before_profile_side_effects():
    service = UserService(AuthConfig(secret_key="deleted-identifier-regression-secret-0123456789"))
    user = User(id=uuid4(), email="reserved@example.test", status=UserStatus.DELETED, first_name="Reserved")
    service.get_by_id = AsyncMock(return_value=user)
    service.get_one = AsyncMock(return_value=None)
    service.update = AsyncMock()
    with pytest.raises(InvalidInputError):
        await service.update_user_fields(AsyncMock(), user.id, email="replacement@example.test", first_name="Changed")
    assert user.email == "reserved@example.test"
    assert user.first_name == "Reserved"
    service.get_one.assert_not_awaited()
    service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_deleted_identifier_reservation_remains_unique_in_real_database(test_session, auth_config):
    service = UserService(auth_config)
    user = await service.create_user(
        test_session, email=f"reserved-{uuid4().hex}@example.test", password="TestPass123!"
    )
    reserved = user.email
    await service.delete_user(test_session, user.id)
    with pytest.raises(InvalidInputError):
        await service.update_user_fields(test_session, user.id, email="replacement@example.test")
    await test_session.refresh(user)
    assert user.email == reserved
    assert user.status == UserStatus.DELETED
    with pytest.raises(UserAlreadyExistsError):
        await service.create_user(test_session, email=reserved, password="TestPass123!")


@pytest.mark.asyncio
async def test_deleted_account_allows_profile_maintenance_without_releasing_identifier(test_session, auth_config):
    service = UserService(auth_config)
    user = await service.create_user(
        test_session, email=f"reserved-{uuid4().hex}@example.test", password="TestPass123!"
    )
    reserved = user.email
    await service.delete_user(test_session, user.id)
    updated = await service.update_user_fields(test_session, user.id, email=reserved.upper(), first_name="Corrected")
    assert updated.email == reserved
    assert updated.status == UserStatus.DELETED
    assert updated.first_name == "Corrected"
