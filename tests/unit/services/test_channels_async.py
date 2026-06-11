"""
Notification channels must not block the event loop (perf audit Phase 3).

The Twilio (SMS/WhatsApp) and SendGrid SDKs are synchronous; calling them
directly inside ``async def send`` stalled every in-flight request for the
duration of the outbound HTTPS call. These tests pin that the blocking call is
routed through ``asyncio.to_thread``, and that the HTTP-based channels reuse a
pooled client instead of paying a TCP+TLS handshake per event.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from outlabs_auth.services.channels.webhook import WebhookChannel


@pytest.mark.unit
@pytest.mark.asyncio
async def test_twilio_send_runs_client_in_worker_thread():
    pytest.importorskip("twilio")
    from outlabs_auth.services.channels.twilio import TwilioChannel

    calling_thread: dict = {}

    async def sms_builder(event):
        return {"to": "+15550001111", "body": "hello"}

    channel = TwilioChannel(
        account_sid="ACtest",
        auth_token="token",
        from_number="+15550002222",
        sms_builder=sms_builder,
    )
    client = MagicMock()
    client.messages.create.side_effect = lambda **kwargs: calling_thread.update(thread=threading.current_thread())
    channel.client = client

    await channel.send({"type": "user.login", "timestamp": "now", "data": {}})

    client.messages.create.assert_called_once()
    assert (
        calling_thread["thread"] is not threading.main_thread()
    ), "Twilio's sync client must run via asyncio.to_thread, not on the event loop"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whatsapp_send_runs_client_in_worker_thread():
    pytest.importorskip("twilio")
    from outlabs_auth.services.channels.whatsapp import WhatsAppChannel

    calling_thread: dict = {}

    async def message_builder(event):
        return {"to": "+15550001111", "body": "hello"}

    channel = WhatsAppChannel(
        account_sid="ACtest",
        auth_token="token",
        from_number="+15550002222",
        message_builder=message_builder,
    )
    client = MagicMock()
    client.messages.create.side_effect = lambda **kwargs: calling_thread.update(thread=threading.current_thread())
    channel.client = client

    await channel.send({"type": "user.login", "timestamp": "now", "data": {}})

    client.messages.create.assert_called_once()
    assert calling_thread["thread"] is not threading.main_thread()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sendgrid_send_runs_client_in_worker_thread():
    pytest.importorskip("sendgrid")
    from outlabs_auth.services.channels.sendgrid import SendGridChannel

    calling_thread: dict = {}

    async def email_builder(event):
        return {"to": "user@example.com", "subject": "hi", "body": "hello"}

    channel = SendGridChannel(
        api_key="SG.test",
        from_email="auth@example.com",
        email_builder=email_builder,
    )
    client = MagicMock()
    client.send.side_effect = lambda mail: calling_thread.update(thread=threading.current_thread())
    channel.client = client

    await channel.send({"type": "user.login", "timestamp": "now", "data": {}})

    client.send.assert_called_once()
    assert calling_thread["thread"] is not threading.main_thread()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_webhook_channel_reuses_pooled_http_client():
    channel = WebhookChannel(url="https://example.test/hook")

    first = channel._get_http_client()
    second = channel._get_http_client()
    assert first is second

    await channel.close()
    assert first.is_closed

    # A closed pool is transparently replaced on the next send.
    replacement = channel._get_http_client()
    assert replacement is not first
    await channel.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mail_providers_reuse_pooled_http_client_and_aclose():
    from outlabs_auth.mail.providers import SendGridMailProvider
    from outlabs_auth.mail.service import ComposedAuthMailService

    provider = SendGridMailProvider(api_key="SG.test", from_email="auth@example.com")
    first = provider._get_http_client()
    assert provider._get_http_client() is first

    # The mail service exposes aclose() for OutlabsAuth.shutdown().
    service = ComposedAuthMailService(provider=provider, composer=MagicMock())
    await service.aclose()
    assert first.is_closed
