"""Built-in transactional auth mail providers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Any, Optional

import httpx

try:
    import aiosmtplib

    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False

from outlabs_auth.mail.types import AuthMailMessage, MailDeliveryResult


class TransactionalMailProvider(ABC):
    """Abstract delivery transport for transactional mail."""

    provider_name: str = "unknown"

    @abstractmethod
    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        """Send a composed mail message."""


class SMTPMailProvider(TransactionalMailProvider):
    """Deliver transactional mail through SMTP."""

    provider_name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        from_email: str,
        from_name: Optional[str] = None,
        use_starttls: bool = True,
        use_ssl_tls: bool = False,
        timeout: int = 10,
    ) -> None:
        if not SMTP_AVAILABLE:
            raise ImportError(
                "aiosmtplib is required for SMTPMailProvider. " "Install with: pip install outlabs-auth[notifications]"
            )

        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.use_starttls = use_starttls
        self.use_ssl_tls = use_ssl_tls
        self.timeout = timeout

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        email_message = EmailMessage()
        email_message["Subject"] = message.subject
        email_message["To"] = f"{message.to_name} <{message.to_email}>" if message.to_name else message.to_email
        email_message["From"] = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
        if message.reply_to:
            email_message["Reply-To"] = message.reply_to
        for key, value in message.headers.items():
            email_message[key] = value
        email_message.set_content(message.text_body)
        if message.html_body:
            email_message.add_alternative(message.html_body, subtype="html")

        try:
            await aiosmtplib.send(
                email_message,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                start_tls=self.use_starttls,
                use_tls=self.use_ssl_tls,
                timeout=self.timeout,
            )
            return MailDeliveryResult.queued(self.provider_name)
        except Exception as exc:
            return MailDeliveryResult.failed(self.provider_name, str(exc))


class SendGridMailProvider(TransactionalMailProvider):
    """Deliver transactional mail through the SendGrid REST API."""

    provider_name = "sendgrid"

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        from_name: Optional[str] = None,
        base_url: str = "https://api.sendgrid.com/v3",
        timeout: int = 10,
    ) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        personalization: dict[str, Any] = {
            "to": [
                {
                    "email": message.to_email,
                    **({"name": message.to_name} if message.to_name else {}),
                }
            ]
        }
        if message.headers:
            personalization["headers"] = dict(message.headers)
        if message.metadata:
            personalization["custom_args"] = {key: json.dumps(value) for key, value in message.metadata.items()}
        if message.provider_template_id:
            personalization["dynamic_template_data"] = dict(message.template_data)

        payload: dict[str, Any] = {
            "personalizations": [personalization],
            "from": {
                "email": self.from_email,
                **({"name": self.from_name} if self.from_name else {}),
            },
        }
        if message.tags:
            payload["categories"] = list(message.tags)
        if message.reply_to:
            payload["reply_to"] = {"email": message.reply_to}

        if message.provider_template_id:
            payload["template_id"] = message.provider_template_id
            if message.subject:
                payload["subject"] = message.subject
        else:
            content: list[dict[str, str]] = [{"type": "text/plain", "value": message.text_body}]
            if message.html_body:
                content.append({"type": "text/html", "value": message.html_body})
            payload["subject"] = message.subject
            payload["content"] = content

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            response.raise_for_status()
            headers = dict(response.headers)
            message_id = headers.get("X-Message-Id") or headers.get("X-Message-ID")
            return MailDeliveryResult.queued(
                self.provider_name,
                provider_message_id=message_id,
                details={"status_code": response.status_code},
            )
        except Exception as exc:
            return MailDeliveryResult.failed(self.provider_name, str(exc))


class MailgunMailProvider(TransactionalMailProvider):
    """Deliver transactional mail through the Mailgun HTTP API."""

    provider_name = "mailgun"

    def __init__(
        self,
        *,
        api_key: str,
        domain: str,
        from_email: str,
        from_name: Optional[str] = None,
        base_url: str = "https://api.mailgun.net",
        timeout: int = 10,
    ) -> None:
        self.api_key = api_key
        self.domain = domain
        self.from_email = from_email
        self.from_name = from_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        payload: dict[str, Any] = {
            "from": f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email,
            "to": message.to_email,
        }
        if message.provider_template_id:
            payload["template"] = message.provider_template_id
            payload["t:variables"] = json.dumps(message.template_data)
            if message.subject:
                payload["subject"] = message.subject
        else:
            payload["subject"] = message.subject
            payload["text"] = message.text_body
            if message.html_body:
                payload["html"] = message.html_body
        if message.reply_to:
            payload["h:Reply-To"] = message.reply_to
        for key, value in message.headers.items():
            payload[f"h:{key}"] = value
        if message.tags:
            payload["o:tag"] = list(message.tags)
        for key, value in message.metadata.items():
            payload[f"v:{key}"] = json.dumps(value) if not isinstance(value, str) else value

        url = f"{self.base_url}/v3/{self.domain}/messages"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, auth=("api", self.api_key), data=payload)
            response.raise_for_status()
            response_data = response.json()
            return MailDeliveryResult.queued(
                self.provider_name,
                provider_message_id=str(response_data.get("id") or ""),
                details={"message": response_data.get("message")},
            )
        except Exception as exc:
            return MailDeliveryResult.failed(self.provider_name, str(exc))


class WebhookMailProvider(TransactionalMailProvider):
    """Forward transactional mail payloads to an external delivery service."""

    provider_name = "webhook"

    def __init__(
        self,
        *,
        url: str,
        secret: Optional[str] = None,
        timeout: int = 10,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.url = url
        self.secret = secret
        self.timeout = timeout
        self.headers = headers or {}

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        payload = {
            "to_email": message.to_email,
            "to_name": message.to_name,
            "subject": message.subject,
            "text_body": message.text_body,
            "html_body": message.html_body,
            "provider_template_id": message.provider_template_id,
            "template_data": message.template_data,
            "reply_to": message.reply_to,
            "headers": message.headers,
            "metadata": message.metadata,
            "tags": list(message.tags),
        }
        headers = {"Content-Type": "application/json", **self.headers}
        if self.secret:
            headers["X-OutlabsAuth-Mail-Secret"] = self.secret

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            response_data: dict[str, Any]
            try:
                response_data = response.json()
            except Exception:
                response_data = {}
            provider_message_id = response_data.get("message_id")
            return MailDeliveryResult.queued(
                self.provider_name,
                provider_message_id=str(provider_message_id) if provider_message_id else None,
                details={"status_code": response.status_code},
            )
        except Exception as exc:
            return MailDeliveryResult.failed(self.provider_name, str(exc))
