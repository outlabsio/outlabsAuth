from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.messaging import (
    AuthChallengeDeliveryIntent,
    DeliveryRecipient,
    MessageDeliveryResult,
)
from outlabs_auth.services.user import UserService


class RecordingMessagingService:
    provider_name = "recording"

    def __init__(self) -> None:
        self.intents: list[AuthChallengeDeliveryIntent] = []

    async def send_auth_challenge(self, intent: AuthChallengeDeliveryIntent):
        self.intents.append(intent)
        return MessageDeliveryResult.queued(self.provider_name, provider_message_id="msg-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_service_sends_access_code_delivery_intent():
    messaging = RecordingMessagingService()
    config = AuthConfig(
        secret_key="x" * 32,
        access_code_expire_minutes=10,
        magic_link_expire_minutes=15,
    )
    service = UserService(config, transactional_messaging_service=messaging)
    user = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        email="agent@example.com",
        first_name="Jane",
        last_name="Agent",
        phone="+15551234567",
        phone_verified=True,
    )

    sent = await service.send_access_code_delivery(user, "123456", redirect_url="/app")

    assert sent is True
    assert len(messaging.intents) == 1
    intent = messaging.intents[0]
    assert intent.challenge_type == "access_code"
    assert intent.secret == "123456"
    assert intent.redirect_url == "/app"
    assert intent.recipient.phone == "+15551234567"
    assert intent.recipient.phone_verified is True
    assert intent.expires_at is not None
    assert intent.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=10, seconds=5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_access_code_hook_uses_messaging_service():
    messaging = RecordingMessagingService()
    config = AuthConfig(secret_key="x" * 32)
    service = UserService(config, transactional_messaging_service=messaging)
    user = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        email="agent@example.com",
        first_name=None,
        last_name=None,
        phone=None,
        phone_verified=False,
    )

    await service.on_after_access_code_requested(user, "654321")

    assert messaging.intents[0].challenge_type == "access_code"
    assert messaging.intents[0].secret == "654321"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_hooks_noop_without_messaging_service():
    config = AuthConfig(secret_key="x" * 32)
    service = UserService(config)
    user = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        email="agent@example.com",
        first_name=None,
        last_name=None,
        phone="+15551234567",
        phone_verified=False,
    )

    assert await service.send_magic_link_delivery(user, "token") is False
    assert await service.send_access_code_delivery(user, "123456") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_console_whatsapp_spike_queues_when_phone_present():
    from examples.enterprise_rbac.challenge_messaging import (
        ConsoleWhatsAppChallengeMessagingService,
    )

    lines: list[str] = []
    service = ConsoleWhatsAppChallengeMessagingService(output=lines.append)
    intent = AuthChallengeDeliveryIntent(
        challenge_type="access_code",
        recipient=DeliveryRecipient(
            user_id="user-1",
            email="agent@example.com",
            phone="+15551234567",
            phone_verified=True,
        ),
        secret="123456",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    result = await service.send_auth_challenge(intent)

    assert result.accepted is True
    assert result.skipped is False
    assert "whatsapp:+15551234567" in lines[0]
    assert "123456" in lines[0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_console_whatsapp_spike_skips_without_phone():
    from examples.enterprise_rbac.challenge_messaging import (
        ConsoleWhatsAppChallengeMessagingService,
    )

    service = ConsoleWhatsAppChallengeMessagingService(output=lambda _line: None)
    intent = AuthChallengeDeliveryIntent(
        challenge_type="access_code",
        recipient=DeliveryRecipient(
            user_id="user-1",
            email="agent@example.com",
        ),
        secret="123456",
        expires_at=None,
    )

    result = await service.send_auth_challenge(intent)

    assert result.accepted is False
    assert result.skipped is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mail_recipient_includes_optional_phone():
    from outlabs_auth.mail import MailRecipient

    recipient = MailRecipient(
        user_id="user-1",
        email="agent@example.com",
        phone="+15551234567",
        phone_verified=True,
    )
    assert recipient.phone == "+15551234567"
    assert recipient.phone_verified is True


@pytest.mark.unit
def test_enterprise_factory_uses_console_without_twilio_env(monkeypatch):
    from examples.enterprise_rbac.challenge_messaging import (
        ConsoleWhatsAppChallengeMessagingService,
        build_enterprise_example_challenge_messaging_service,
    )

    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_ACCESS_CODE_CONTENT_SID", raising=False)

    service = build_enterprise_example_challenge_messaging_service()
    assert isinstance(service, ConsoleWhatsAppChallengeMessagingService)
