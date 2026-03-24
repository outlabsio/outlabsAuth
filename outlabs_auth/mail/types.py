"""Typed intent and message models for transactional auth mail."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional


@dataclass(slots=True, frozen=True)
class MailRecipient:
    """Normalized recipient data used by auth mail intents."""

    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @property
    def display_name(self) -> str:
        parts = [part.strip() for part in [self.first_name or "", self.last_name or ""] if part and part.strip()]
        return " ".join(parts) or self.email


@dataclass(slots=True, frozen=True)
class AuthMailMessage:
    """Provider-agnostic transactional mail message."""

    to_email: str
    subject: str
    text_body: str
    html_body: Optional[str] = None
    to_name: Optional[str] = None
    reply_to: Optional[str] = None
    provider_template_id: Optional[str] = None
    template_data: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class MailDeliveryResult:
    """Canonical result returned by transactional mail providers."""

    accepted: bool
    provider: str
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
    skipped: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def queued(
        cls,
        provider: str,
        *,
        provider_message_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> "MailDeliveryResult":
        return cls(
            accepted=True,
            provider=provider,
            provider_message_id=provider_message_id,
            details=details or {},
        )

    @classmethod
    def failed(
        cls,
        provider: str,
        error: str,
        *,
        details: Optional[dict[str, Any]] = None,
    ) -> "MailDeliveryResult":
        return cls(
            accepted=False,
            provider=provider,
            error=error,
            details=details or {},
        )

    @classmethod
    def skipped_result(
        cls,
        provider: str,
        reason: str,
        *,
        details: Optional[dict[str, Any]] = None,
    ) -> "MailDeliveryResult":
        return cls(
            accepted=False,
            provider=provider,
            error=reason,
            skipped=True,
            details=details or {},
        )


@dataclass(slots=True, frozen=True)
class InviteMailIntent:
    """Intent payload for invitation delivery."""

    recipient: MailRecipient
    token: str
    expires_at: Optional[datetime]
    request_base_url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ForgotPasswordMailIntent:
    """Intent payload for password reset delivery."""

    recipient: MailRecipient
    token: str
    expires_at: Optional[datetime]
    request_base_url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class PasswordResetConfirmationMailIntent:
    """Intent payload for password reset completion notices."""

    recipient: MailRecipient
    changed_at: Optional[datetime]
    request_base_url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class AccessGrantedMailIntent:
    """Intent payload for access-granted notifications."""

    recipient: MailRecipient
    request_base_url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


def coerce_metadata(value: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """Copy metadata mappings into a mutable plain dict."""
    return dict(value or {})
