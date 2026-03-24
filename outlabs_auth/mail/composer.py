"""Composer interfaces and default implementations for transactional auth mail."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from html import escape
from typing import Callable, Optional

from outlabs_auth.mail.types import (
    AccessGrantedMailIntent,
    AuthMailMessage,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    PasswordResetConfirmationMailIntent,
)

TokenUrlBuilder = Callable[[str], str]
SimpleUrlBuilder = Callable[[], str]


class AuthMailComposer(ABC):
    """Build branded mail messages from auth intents."""

    @abstractmethod
    async def compose_invite(self, intent: InviteMailIntent) -> Optional[AuthMailMessage]:
        """Build an invitation email."""

    @abstractmethod
    async def compose_forgot_password(self, intent: ForgotPasswordMailIntent) -> Optional[AuthMailMessage]:
        """Build a password-reset email."""

    @abstractmethod
    async def compose_password_reset_confirmation(
        self,
        intent: PasswordResetConfirmationMailIntent,
    ) -> Optional[AuthMailMessage]:
        """Build a password-reset confirmation email."""

    @abstractmethod
    async def compose_access_granted(self, intent: AccessGrantedMailIntent) -> Optional[AuthMailMessage]:
        """Build an access-granted email."""


class DefaultAuthMailComposer(AuthMailComposer):
    """Simple built-in composer for hosts that do not need custom branding yet."""

    def __init__(
        self,
        *,
        app_name: str,
        invite_url_builder: TokenUrlBuilder,
        password_reset_url_builder: TokenUrlBuilder,
        login_url_builder: Optional[SimpleUrlBuilder] = None,
        support_email: Optional[str] = None,
    ) -> None:
        self.app_name = app_name
        self.invite_url_builder = invite_url_builder
        self.password_reset_url_builder = password_reset_url_builder
        self.login_url_builder = login_url_builder
        self.support_email = support_email

    async def compose_invite(self, intent: InviteMailIntent) -> Optional[AuthMailMessage]:
        invite_url = self.invite_url_builder(intent.token)
        recipient_name = escape(intent.recipient.display_name)
        target_entity_name = escape(str(intent.metadata.get("target_entity_name") or "your organization"))
        inviter_name = escape(str(intent.metadata.get("inviter_email") or f"The {self.app_name} Team"))
        role_names = [str(role) for role in intent.metadata.get("role_names", []) or []]
        role_line = ""
        role_html = ""
        if role_names:
            role_list = ", ".join(sorted(set(role_names)))
            role_line = f"\nRoles: {role_list}"
            role_html = f"<p><strong>Roles:</strong> {escape(role_list)}</p>"

        expiry_line = self._format_expiry(intent.expires_at)
        resend_flag = bool(intent.metadata.get("is_resend"))
        subject_prefix = "Your invitation to" if resend_flag else "You're invited to"
        subject = f"{subject_prefix} {self.app_name}"

        text_body = (
            f"Hello {intent.recipient.display_name},\n\n"
            f"You have been invited to join {target_entity_name} on {self.app_name}.{role_line}\n\n"
            f"Accept your invitation and set your password:\n{invite_url}\n"
            f"{expiry_line}\n\n"
            f"Best,\n{inviter_name}"
        )
        html_body = (
            f"<p>Hello {recipient_name},</p>"
            f"<p>You have been invited to join <strong>{target_entity_name}</strong> on "
            f"<strong>{escape(self.app_name)}</strong>.</p>"
            f"{role_html}"
            f'<p><a href="{escape(invite_url)}">Accept your invitation</a> and set your password.</p>'
            f"<p>{escape(expiry_line)}</p>"
            f"<p>Best,<br>{inviter_name}</p>"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            reply_to=self.support_email,
            tags=("invite", "auth"),
        )

    async def compose_forgot_password(self, intent: ForgotPasswordMailIntent) -> Optional[AuthMailMessage]:
        reset_url = self.password_reset_url_builder(intent.token)
        expiry_line = self._format_expiry(intent.expires_at)
        text_body = (
            f"Hello {intent.recipient.display_name},\n\n"
            f"We received a request to reset your {self.app_name} password.\n\n"
            f"Reset your password here:\n{reset_url}\n"
            f"{expiry_line}\n\n"
            "If you did not request this change, you can ignore this email."
        )
        html_body = (
            f"<p>Hello {escape(intent.recipient.display_name)},</p>"
            f"<p>We received a request to reset your <strong>{escape(self.app_name)}</strong> password.</p>"
            f'<p><a href="{escape(reset_url)}">Reset your password</a></p>'
            f"<p>{escape(expiry_line)}</p>"
            "<p>If you did not request this change, you can ignore this email.</p>"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject=f"Reset your {self.app_name} password",
            text_body=text_body,
            html_body=html_body,
            reply_to=self.support_email,
            tags=("password-reset", "auth"),
        )

    async def compose_password_reset_confirmation(
        self,
        intent: PasswordResetConfirmationMailIntent,
    ) -> Optional[AuthMailMessage]:
        text_body = (
            f"Hello {intent.recipient.display_name},\n\n"
            f"Your {self.app_name} password has been changed successfully.\n\n"
            "If you did not make this change, contact support immediately."
        )
        html_body = (
            f"<p>Hello {escape(intent.recipient.display_name)},</p>"
            f"<p>Your <strong>{escape(self.app_name)}</strong> password has been changed successfully.</p>"
            "<p>If you did not make this change, contact support immediately.</p>"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject=f"Your {self.app_name} password was changed",
            text_body=text_body,
            html_body=html_body,
            reply_to=self.support_email,
            tags=("password-reset-confirmation", "auth"),
        )

    async def compose_access_granted(self, intent: AccessGrantedMailIntent) -> Optional[AuthMailMessage]:
        login_url = self.login_url_builder() if self.login_url_builder else None
        target_entity_name = escape(str(intent.metadata.get("target_entity_name") or "your organization"))
        inviter_name = escape(str(intent.metadata.get("inviter_email") or f"The {self.app_name} Team"))
        role_names = [str(role) for role in intent.metadata.get("role_names", []) or []]
        role_line = ""
        role_html = ""
        if role_names:
            role_list = ", ".join(sorted(set(role_names)))
            role_line = f"\nRoles: {role_list}"
            role_html = f"<p><strong>Roles:</strong> {escape(role_list)}</p>"
        login_line = f"\nLog in: {login_url}" if login_url else ""
        login_html = f'<p><a href="{escape(login_url)}">Log in to {escape(self.app_name)}</a></p>' if login_url else ""

        text_body = (
            f"Hello {intent.recipient.display_name},\n\n"
            f"You now have access to {target_entity_name} on {self.app_name}.{role_line}{login_line}\n\n"
            f"Best,\n{inviter_name}"
        )
        html_body = (
            f"<p>Hello {escape(intent.recipient.display_name)},</p>"
            f"<p>You now have access to <strong>{target_entity_name}</strong> on "
            f"<strong>{escape(self.app_name)}</strong>.</p>"
            f"{role_html}"
            f"{login_html}"
            f"<p>Best,<br>{inviter_name}</p>"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject=f"You have access to a new {self.app_name} team",
            text_body=text_body,
            html_body=html_body,
            reply_to=self.support_email,
            tags=("access-granted", "auth"),
        )

    @staticmethod
    def _format_expiry(expires_at: Optional[datetime]) -> str:
        if expires_at is None:
            return "This link expires soon."
        utc_value = expires_at.astimezone(timezone.utc)
        return f"This link expires on {utc_value.strftime('%Y-%m-%d %H:%M UTC')}."
