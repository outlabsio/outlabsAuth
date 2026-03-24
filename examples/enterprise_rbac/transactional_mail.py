"""Transactional mail wiring for the EnterpriseRBAC example app."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from html import escape
from typing import Optional
from urllib.parse import urlencode

from outlabs_auth.mail import (
    AccessGrantedMailIntent,
    AuthMailMessage,
    ComposedAuthMailService,
    DefaultAuthMailComposer,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    MailDeliveryResult,
    MailgunMailProvider,
    PasswordResetConfirmationMailIntent,
    TransactionalMailProvider,
)

APP_NAME = "Outlabs Auth"
ACCEPT_INVITE_PATH = "/auth/accept-invite"
PASSWORD_RESET_PATH = "/auth/reset-password"
LOGIN_PATH = "/auth/login"
DEFAULT_MAILGUN_API_BASE_URL = "https://api.mailgun.net"


def _trim_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def build_frontend_token_link(frontend_url: str, path: str, token: str) -> str:
    query = urlencode({"token": token})
    return f"{_trim_trailing_slash(frontend_url)}{path}?{query}"


def build_frontend_link(frontend_url: str, path: str) -> str:
    return f"{_trim_trailing_slash(frontend_url)}{path}"


class ConsoleMailProvider(TransactionalMailProvider):
    """Development-friendly provider that prints transactional mail to stdout."""

    provider_name = "console"

    def __init__(self, *, output: Callable[[str], None] = print) -> None:
        self.output = output

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        lines = [
            "",
            "=" * 80,
            "TRANSACTIONAL EMAIL (Console Fallback)",
            "=" * 80,
            f"To: {message.to_email}",
            f"Subject: {message.subject}",
        ]
        if message.reply_to:
            lines.append(f"Reply-To: {message.reply_to}")
        if message.tags:
            lines.append(f"Tags: {', '.join(message.tags)}")
        lines.extend(["", message.text_body, "=" * 80, ""])
        self.output("\n".join(lines))
        return MailDeliveryResult.queued(self.provider_name)


class RecipientOverrideMailProvider(TransactionalMailProvider):
    """Redirect delivery to a sandbox address while preserving intended-recipient context."""

    def __init__(
        self,
        *,
        provider: TransactionalMailProvider,
        override_email: str,
    ) -> None:
        self.provider = provider
        self.provider_name = provider.provider_name
        self.override_email = override_email

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        note = f"Intended recipient: {message.to_email}\n" f"Sandbox override recipient: {self.override_email}\n\n"
        overridden = replace(
            message,
            to_email=self.override_email,
            to_name=None,
            text_body=f"{note}{message.text_body}",
            metadata={
                **message.metadata,
                "intended_recipient": message.to_email,
                "sandbox_recipient": self.override_email,
            },
        )
        return await self.provider.send(overridden)


class EnterpriseExampleMailComposer(DefaultAuthMailComposer):
    """Example-app composer showing host-owned copy, URLs, and branding."""

    def __init__(
        self,
        *,
        frontend_url: str,
        support_email: Optional[str] = None,
    ) -> None:
        self.frontend_url = _trim_trailing_slash(frontend_url)
        super().__init__(
            app_name=APP_NAME,
            invite_url_builder=lambda token: build_frontend_token_link(self.frontend_url, ACCEPT_INVITE_PATH, token),
            password_reset_url_builder=lambda token: build_frontend_token_link(
                self.frontend_url, PASSWORD_RESET_PATH, token
            ),
            login_url_builder=lambda: build_frontend_link(self.frontend_url, LOGIN_PATH),
            support_email=support_email,
        )

    async def compose_invite(self, intent: InviteMailIntent) -> Optional[AuthMailMessage]:
        accept_link = self.invite_url_builder(intent.token)
        target_entity_name = str(intent.metadata.get("target_entity_name") or "your organization")
        recipient_name = intent.recipient.display_name
        role_names = sorted({str(role) for role in intent.metadata.get("role_names", []) or []})
        role_line = f"\nRoles: {', '.join(role_names)}" if role_names else ""
        text_body = (
            f"Hello {recipient_name},\n\n"
            f"You've been invited to join {target_entity_name} on {APP_NAME}.{role_line}\n\n"
            "Click the link below to accept your invitation and set your password:\n\n"
            f"{accept_link}\n\n"
            f"{self._format_expiry(intent.expires_at)}"
        )
        html_body = (
            f"<p>Hello {escape(recipient_name)},</p>"
            f"<p>You've been invited to join <strong>{escape(target_entity_name)}</strong> on "
            f"<strong>{escape(APP_NAME)}</strong>.</p>"
            f"{f'<p><strong>Roles:</strong> {escape(', '.join(role_names))}</p>' if role_names else ''}"
            f'<p><a href="{escape(accept_link)}">Accept your invitation</a> and set your password.</p>'
            f"<p>{escape(self._format_expiry(intent.expires_at))}</p>"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=recipient_name,
            subject=f"You're invited to {APP_NAME}",
            text_body=text_body,
            html_body=html_body,
            reply_to=self.support_email,
            tags=("invite", "enterprise-example"),
            metadata={"intent": "invite", **intent.metadata},
        )

    async def compose_forgot_password(self, intent: ForgotPasswordMailIntent) -> Optional[AuthMailMessage]:
        reset_link = self.password_reset_url_builder(intent.token)
        text_body = (
            "Click the link below to reset your password:\n\n"
            f"{reset_link}\n\n"
            f"{self._format_expiry(intent.expires_at)}"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject="Reset your password",
            text_body=text_body,
            reply_to=self.support_email,
            tags=("password-reset", "enterprise-example"),
            metadata={"intent": "forgot-password", **intent.metadata},
        )

    async def compose_password_reset_confirmation(
        self,
        intent: PasswordResetConfirmationMailIntent,
    ) -> Optional[AuthMailMessage]:
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject="Password reset successful",
            text_body=(
                "Your password has been successfully reset.\n\n"
                "If you didn't make this change, please contact support immediately."
            ),
            reply_to=self.support_email,
            tags=("password-reset-confirmation", "enterprise-example"),
            metadata={"intent": "password-reset-confirmation", **intent.metadata},
        )

    async def compose_access_granted(self, intent: AccessGrantedMailIntent) -> Optional[AuthMailMessage]:
        login_link = self.login_url_builder() if self.login_url_builder else ""
        target_entity_name = str(intent.metadata.get("target_entity_name") or "your organization")
        role_names = sorted({str(role) for role in intent.metadata.get("role_names", []) or []})
        role_line = f"\nRoles: {', '.join(role_names)}" if role_names else ""
        text_body = (
            f"You now have access to {target_entity_name} on {APP_NAME}.{role_line}\n\n" f"Log in here: {login_link}"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject=f"You have access to a new {APP_NAME} team",
            text_body=text_body,
            reply_to=self.support_email,
            tags=("access-granted", "enterprise-example"),
            metadata={"intent": "access-granted", **intent.metadata},
        )


def build_enterprise_example_transactional_mail_service(
    *,
    frontend_url: str,
    mailgun_api_base_url: str = DEFAULT_MAILGUN_API_BASE_URL,
    mailgun_domain: Optional[str] = None,
    mailgun_api_key: Optional[str] = None,
    mailgun_from_email: Optional[str] = None,
    mailgun_from_name: str = APP_NAME,
    mailgun_recipient_override: Optional[str] = None,
    provider_override: Optional[TransactionalMailProvider] = None,
    console_output: Callable[[str], None] = print,
) -> ComposedAuthMailService:
    provider = provider_override or _build_mail_provider(
        mailgun_api_base_url=mailgun_api_base_url,
        mailgun_domain=mailgun_domain,
        mailgun_api_key=mailgun_api_key,
        mailgun_from_email=mailgun_from_email,
        mailgun_from_name=mailgun_from_name,
        console_output=console_output,
    )
    if mailgun_recipient_override:
        provider = RecipientOverrideMailProvider(
            provider=provider,
            override_email=mailgun_recipient_override,
        )
    composer = EnterpriseExampleMailComposer(
        frontend_url=frontend_url,
        support_email=mailgun_from_email,
    )
    return ComposedAuthMailService(provider=provider, composer=composer)


def _build_mail_provider(
    *,
    mailgun_api_base_url: str,
    mailgun_domain: Optional[str],
    mailgun_api_key: Optional[str],
    mailgun_from_email: Optional[str],
    mailgun_from_name: str,
    console_output: Callable[[str], None],
) -> TransactionalMailProvider:
    if mailgun_domain and mailgun_api_key and mailgun_from_email:
        return MailgunMailProvider(
            api_key=mailgun_api_key,
            domain=mailgun_domain,
            from_email=mailgun_from_email,
            from_name=mailgun_from_name,
            base_url=_trim_trailing_slash(mailgun_api_base_url),
        )
    return ConsoleMailProvider(output=console_output)
