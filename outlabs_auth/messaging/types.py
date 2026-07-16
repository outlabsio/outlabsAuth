"""Typed intents for channel-agnostic auth challenge delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Mapping, Optional

AuthChallengeTypeName = Literal["magic_link", "access_code", "phone_verify"]


@dataclass(slots=True, frozen=True)
class DeliveryRecipient:
    """Normalized recipient for challenge delivery (email identity + optional phone)."""

    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    phone_verified: bool = False

    @property
    def display_name(self) -> str:
        parts = [
            part.strip()
            for part in [self.first_name or "", self.last_name or ""]
            if part and part.strip()
        ]
        return " ".join(parts) or self.email


@dataclass(slots=True, frozen=True)
class AuthChallengeDeliveryIntent:
    """
    Intent payload for magic-link / access-code delivery.

    Hosts map this into email bodies and/or WhatsApp template variables.
    The library does not choose a provider or template.
    """

    challenge_type: AuthChallengeTypeName
    recipient: DeliveryRecipient
    secret: str
    expires_at: Optional[datetime]
    redirect_url: Optional[str] = None
    request_base_url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class MessageDeliveryResult:
    """Canonical result returned by transactional messaging services."""

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
    ) -> "MessageDeliveryResult":
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
    ) -> "MessageDeliveryResult":
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
    ) -> "MessageDeliveryResult":
        return cls(
            accepted=False,
            provider=provider,
            error=reason,
            skipped=True,
            details=details or {},
        )


def coerce_metadata(value: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """Copy metadata mappings into a mutable plain dict."""
    return dict(value or {})
