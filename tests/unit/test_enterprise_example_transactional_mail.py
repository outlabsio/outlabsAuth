from __future__ import annotations

import pytest

from examples.enterprise_rbac.transactional_mail import (
    ConsoleMailProvider,
    build_enterprise_example_transactional_mail_service,
)
from outlabs_auth.mail import AuthMailMessage, MailDeliveryResult, MailRecipient, TransactionalMailProvider
from outlabs_auth.mail.types import ForgotPasswordMailIntent, InviteMailIntent


class RecordingProvider(TransactionalMailProvider):
    provider_name = "recording"

    def __init__(self) -> None:
        self.messages: list[AuthMailMessage] = []

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        self.messages.append(message)
        return MailDeliveryResult.queued(self.provider_name, provider_message_id="msg-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enterprise_example_mail_service_uses_provider_override_and_accept_invite_link() -> None:
    provider = RecordingProvider()
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        provider_override=provider,
    )

    result = await service.send_invite(
        InviteMailIntent(
            recipient=MailRecipient(
                user_id="user-1",
                email="invitee@example.com",
                first_name="Invitee",
                last_name="User",
            ),
            token="plain-token",
            expires_at=None,
            metadata={"target_entity_name": "Enterprise Example Team", "role_names": ["team_agent"]},
        )
    )

    assert result.accepted is True
    assert len(provider.messages) == 1
    message = provider.messages[0]
    assert message.to_email == "invitee@example.com"
    assert "https://frontend.example.com/auth/accept-invite?token=plain-token" in message.text_body
    assert "Enterprise Example Team" in message.text_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enterprise_example_mail_service_applies_recipient_override() -> None:
    provider = RecordingProvider()
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        provider_override=provider,
        mailgun_recipient_override="sandbox@example.com",
    )

    await service.send_invite(
        InviteMailIntent(
            recipient=MailRecipient(user_id="user-1", email="real-user@example.com"),
            token="plain-token",
            expires_at=None,
        )
    )

    assert len(provider.messages) == 1
    message = provider.messages[0]
    assert message.to_email == "sandbox@example.com"
    assert "Intended recipient: real-user@example.com" in message.text_body
    assert message.metadata["intended_recipient"] == "real-user@example.com"
    assert message.metadata["sandbox_recipient"] == "sandbox@example.com"


@pytest.mark.unit
def test_enterprise_example_mail_service_falls_back_to_console_provider() -> None:
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        mail_provider="console",
    )

    assert isinstance(service.provider, ConsoleMailProvider)


@pytest.mark.unit
def test_resolve_mail_provider_name_auto_prefers_mailgun(monkeypatch: pytest.MonkeyPatch) -> None:
    from examples.enterprise_rbac.transactional_mail import resolve_mail_provider_name

    monkeypatch.delenv("OUTLABS_AUTH_MAIL_PROVIDER", raising=False)
    monkeypatch.setenv("MAILGUN_DOMAIN", "example.mailgun.org")
    monkeypatch.setenv("MAILGUN_API_KEY", "key")
    monkeypatch.setenv("MAILGUN_FROM_EMAIL", "postmaster@example.mailgun.org")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("POSTMARK_SERVER_TOKEN", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    assert resolve_mail_provider_name("auto") == "mailgun"


@pytest.mark.unit
def test_resolve_mail_provider_name_explicit_postmark() -> None:
    from examples.enterprise_rbac.transactional_mail import resolve_mail_provider_name

    assert resolve_mail_provider_name("postmark") == "postmark"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enterprise_example_routes_portal_send_via_requested_profile_key() -> None:
    provider = RecordingProvider()
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        portal_frontend_url="https://portal.example.com",
        provider_override=provider,
    )

    result = await service.send_forgot_password(
        ForgotPasswordMailIntent(
            recipient=MailRecipient(user_id="user-2", email="agent@example.com"),
            token="plain-token",
            expires_at=None,
            profile_id="portal",
        )
    )

    assert result.accepted is True
    assert len(provider.messages) == 1
    # Portal profile: path token placement on the portal origin.
    assert "https://portal.example.com/recovery/plain-token" in provider.messages[0].text_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enterprise_example_routes_by_root_entity_slug() -> None:
    provider = RecordingProvider()
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        portal_frontend_url="https://portal.example.com",
        provider_override=provider,
    )

    result = await service.send_forgot_password(
        ForgotPasswordMailIntent(
            recipient=MailRecipient(user_id="user-3", email="agent@example.com"),
            token="plain-token",
            expires_at=None,
            root_entity_slug="agent-practice",
        )
    )

    assert result.accepted is True
    assert "https://portal.example.com/recovery/plain-token" in provider.messages[0].text_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enterprise_example_unknown_requested_profile_fails_closed() -> None:
    provider = RecordingProvider()
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        provider_override=provider,
    )

    result = await service.send_forgot_password(
        ForgotPasswordMailIntent(
            recipient=MailRecipient(user_id="user-4", email="user@example.com"),
            token="plain-token",
            expires_at=None,
            profile_id="ghost",
        )
    )

    assert result.accepted is False
    assert result.error == "frontend_resolution_failed:frontend_profile_unknown"
    assert provider.messages == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enterprise_example_portal_invite_fails_closed_on_unsupported_flow() -> None:
    provider = RecordingProvider()
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        portal_frontend_url="https://portal.example.com",
        provider_override=provider,
    )

    result = await service.send_invite(
        InviteMailIntent(
            recipient=MailRecipient(user_id="user-5", email="invitee@example.com"),
            token="plain-token",
            expires_at=None,
            profile_id="portal",  # the portal declares accept_invite=None
        )
    )

    assert result.accepted is False
    assert result.error == "frontend_flow_unsupported"
    assert provider.messages == []


@pytest.mark.unit
def test_enterprise_example_exposes_frontend_resolver_for_auth_wiring() -> None:
    service = build_enterprise_example_transactional_mail_service(
        frontend_url="https://frontend.example.com",
        provider_override=RecordingProvider(),
    )

    # OutlabsAuth picks this up for challenge flows, OAuth, and the sign-in gate.
    assert service.frontend_resolver is not None
    assert service.frontend_resolver.registry.keys() == ("console", "portal")
    assert service.frontend_resolver.default_key == "console"
