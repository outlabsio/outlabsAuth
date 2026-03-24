from datetime import datetime, timezone

import pytest

from outlabs_auth.mail import (
    AuthMailComposer,
    ComposedAuthMailService,
    DefaultAuthMailComposer,
    InviteMailIntent,
    MailDeliveryResult,
    MailRecipient,
    TransactionalMailProvider,
)


class RecordingProvider(TransactionalMailProvider):
    provider_name = "recording"

    def __init__(self) -> None:
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return MailDeliveryResult.queued(self.provider_name, provider_message_id="msg-1")


class SkippingComposer(AuthMailComposer):
    async def compose_invite(self, intent):
        return None

    async def compose_forgot_password(self, intent):
        return None

    async def compose_password_reset_confirmation(self, intent):
        return None

    async def compose_access_granted(self, intent):
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_auth_mail_composer_builds_invite_message():
    composer = DefaultAuthMailComposer(
        app_name="Outlabs Auth",
        invite_url_builder=lambda token: f"https://ui.example.com/accept-invite?token={token}",
        password_reset_url_builder=lambda token: f"https://ui.example.com/reset-password?token={token}",
        login_url_builder=lambda: "https://ui.example.com/login",
        support_email="support@example.com",
    )

    message = await composer.compose_invite(
        InviteMailIntent(
            recipient=MailRecipient(
                user_id="user-1",
                email="invitee@example.com",
                first_name="Jane",
                last_name="Admin",
            ),
            token="plain-token",
            expires_at=datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
            metadata={"target_entity_name": "Internal Admin", "role_names": ["internal_admin"]},
        )
    )

    assert message is not None
    assert message.to_email == "invitee@example.com"
    assert "You're invited" in message.subject
    assert "plain-token" in message.text_body
    assert "Internal Admin" in (message.html_body or "")
    assert message.reply_to == "support@example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_composed_auth_mail_service_skips_when_composer_returns_none():
    provider = RecordingProvider()
    service = ComposedAuthMailService(provider=provider, composer=SkippingComposer())

    result = await service.send_invite(
        InviteMailIntent(
            recipient=MailRecipient(user_id="user-1", email="invitee@example.com"),
            token="plain-token",
            expires_at=None,
        )
    )

    assert result.skipped is True
    assert result.accepted is False
    assert provider.messages == []
