"""The bool compatibility hook and receipt hook share invitation composition."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.mail.types import MailDeliveryResult
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.user import UserService

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def test_invitation_result_retains_receipt_and_existing_bool_contract():
    result = MailDeliveryResult.queued("recording", provider_message_id="synthetic-receipt")
    mail = SimpleNamespace(send_invite=AsyncMock(return_value=result))
    service = UserService(
        AuthConfig(secret_key="synthetic-receipt-compatibility-secret"), transactional_mail_service=mail
    )
    user = User(email="receipt@example.com", first_name="Receipt", last_name="Fixture")
    assert (
        await service.send_invitation_email_result(user, "synthetic-token", logical_delivery_id="logical-1") is result
    )
    assert await service.send_invitation_email(user, "synthetic-token", logical_delivery_id="logical-1") is True
    first, second = [call.args[0] for call in mail.send_invite.call_args_list]
    assert first == second and first.metadata["logical_delivery_id"] == "logical-1"


async def test_missing_mail_result_is_explicitly_skipped_and_bool_stays_false():
    service = UserService(AuthConfig(secret_key="synthetic-receipt-compatibility-secret"))
    user = User(email="receipt@example.com", first_name="Receipt", last_name="Fixture")
    result = await service.send_invitation_email_result(user, "synthetic-token")
    assert not result.accepted and result.skipped and result.provider == "unconfigured"
    assert await service.send_invitation_email(user, "synthetic-token") is False
