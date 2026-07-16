"""
Channel-agnostic challenge delivery for the EnterpriseRBAC example.

Host-owned WhatsApp path for access codes:
- Console spike when Twilio is not configured (local demos / E2E)
- Twilio Content API when TWILIO_* env vars are set

Library supplies AuthChallengeDeliveryIntent; this module owns templates
and credentials (see docs/WHATSAPP_ACCOUNT_MESSAGING.md).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional, Protocol

from outlabs_auth.messaging import (
    AuthChallengeDeliveryIntent,
    MessageDeliveryResult,
)

# Example Content SID placeholder — replace with a host-approved Twilio template.
DEFAULT_ACCESS_CODE_CONTENT_SID = "HX_ACCESS_CODE_TEMPLATE_PLACEHOLDER"


class ChallengeMessagingService(Protocol):
    async def send_auth_challenge(
        self,
        intent: AuthChallengeDeliveryIntent,
    ) -> MessageDeliveryResult: ...


def _normalize_whatsapp_address(phone: str) -> str:
    return phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"


def _build_access_code_content_variables(
    intent: AuthChallengeDeliveryIntent,
) -> dict[str, str]:
    expires_minutes = _expires_minutes(intent.expires_at)
    content_variables = {
        "1": intent.secret,
        "2": str(expires_minutes) if expires_minutes is not None else "",
        "email": intent.recipient.email,
        "display_name": intent.recipient.display_name,
    }
    if intent.redirect_url:
        content_variables["redirect_url"] = intent.redirect_url
    return content_variables


def _guard_access_code_whatsapp(
    intent: AuthChallengeDeliveryIntent,
    *,
    provider_name: str,
    require_phone_verified: bool,
) -> tuple[Optional[str], Optional[MessageDeliveryResult]]:
    phone = (intent.recipient.phone or "").strip()
    if not phone:
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "recipient has no phone; host may deliver via email instead",
            details={"challenge_type": intent.challenge_type, "email": intent.recipient.email},
        )

    if require_phone_verified and not intent.recipient.phone_verified:
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "phone is not verified",
            details={"challenge_type": intent.challenge_type, "phone": phone},
        )

    if intent.challenge_type != "access_code":
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "WhatsApp host path only implements access_code templates",
            details={"challenge_type": intent.challenge_type},
        )

    return phone, None


class ConsoleWhatsAppChallengeMessagingService:
    """Dev-friendly provider that prints a Twilio Content API-shaped payload."""

    provider_name = "console-whatsapp"

    def __init__(
        self,
        *,
        access_code_content_sid: str = DEFAULT_ACCESS_CODE_CONTENT_SID,
        output: Callable[[str], None] = print,
        require_phone_verified: bool = False,
    ) -> None:
        self.access_code_content_sid = access_code_content_sid
        self.output = output
        self.require_phone_verified = require_phone_verified

    async def send_auth_challenge(
        self,
        intent: AuthChallengeDeliveryIntent,
    ) -> MessageDeliveryResult:
        phone, skipped = _guard_access_code_whatsapp(
            intent,
            provider_name=self.provider_name,
            require_phone_verified=self.require_phone_verified,
        )
        if skipped is not None:
            return skipped
        assert phone is not None

        to_address = _normalize_whatsapp_address(phone)
        content_variables = _build_access_code_content_variables(intent)
        lines = [
            "",
            "=" * 80,
            "WHATSAPP CHALLENGE (Console Spike)",
            "=" * 80,
            f"Challenge: {intent.challenge_type}",
            f"To: {to_address}",
            f"Content SID: {self.access_code_content_sid}",
            f"Content variables: {content_variables}",
            f"User ID: {intent.recipient.user_id}",
            f"Phone verified: {intent.recipient.phone_verified}",
            "=" * 80,
            "",
        ]
        self.output("\n".join(lines))
        return MessageDeliveryResult.queued(
            self.provider_name,
            details={
                "to": to_address,
                "content_sid": self.access_code_content_sid,
                "content_variables": content_variables,
            },
        )


class TwilioWhatsAppChallengeMessagingService:
    """Host Twilio WhatsApp Content API delivery for access-code intents."""

    provider_name = "twilio-whatsapp"

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        access_code_content_sid: str,
        require_phone_verified: bool = False,
        fallback: Optional[ChallengeMessagingService] = None,
    ) -> None:
        try:
            from twilio.rest import Client as TwilioClient
        except ImportError as exc:  # pragma: no cover - optional extra
            raise ImportError(
                "twilio is required for Twilio WhatsApp challenge delivery. "
                "Install with: pip install outlabs-auth[notifications]"
            ) from exc

        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = _normalize_whatsapp_address(from_number)
        self.access_code_content_sid = access_code_content_sid
        self.require_phone_verified = require_phone_verified
        self.fallback = fallback
        self.client = TwilioClient(account_sid, auth_token)

    async def send_auth_challenge(
        self,
        intent: AuthChallengeDeliveryIntent,
    ) -> MessageDeliveryResult:
        phone, skipped = _guard_access_code_whatsapp(
            intent,
            provider_name=self.provider_name,
            require_phone_verified=self.require_phone_verified,
        )
        if skipped is not None:
            if self.fallback is not None and skipped.skipped:
                return await self.fallback.send_auth_challenge(intent)
            return skipped
        assert phone is not None

        import asyncio

        to_address = _normalize_whatsapp_address(phone)
        content_variables = _build_access_code_content_variables(intent)

        try:
            message = await asyncio.to_thread(
                self.client.messages.create,
                from_=self.from_number,
                to=to_address,
                content_sid=self.access_code_content_sid,
                content_variables=json.dumps(content_variables),
            )
        except Exception as exc:
            return MessageDeliveryResult.failed(
                self.provider_name,
                str(exc),
                details={"to": to_address, "content_sid": self.access_code_content_sid},
            )

        return MessageDeliveryResult.queued(
            self.provider_name,
            provider_message_id=getattr(message, "sid", None),
            details={
                "to": to_address,
                "content_sid": self.access_code_content_sid,
                "content_variables": content_variables,
            },
        )


def build_enterprise_example_challenge_messaging_service(
    *,
    access_code_content_sid: Optional[str] = None,
    twilio_account_sid: Optional[str] = None,
    twilio_auth_token: Optional[str] = None,
    twilio_whatsapp_from: Optional[str] = None,
    require_phone_verified: Optional[bool] = None,
) -> ChallengeMessagingService:
    """
    Factory used by the enterprise example app.

    Uses Twilio when account SID, auth token, from number, and a real Content
    SID are configured; otherwise falls back to the console spike.
    """
    content_sid = (
        access_code_content_sid
        or os.getenv("TWILIO_WHATSAPP_ACCESS_CODE_CONTENT_SID")
        or DEFAULT_ACCESS_CODE_CONTENT_SID
    )
    account_sid = twilio_account_sid or os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = twilio_auth_token or os.getenv("TWILIO_AUTH_TOKEN")
    from_number = twilio_whatsapp_from or os.getenv("TWILIO_WHATSAPP_FROM")
    if require_phone_verified is None:
        require_phone_verified = _env_flag("TWILIO_WHATSAPP_REQUIRE_VERIFIED", default=False)

    console = ConsoleWhatsAppChallengeMessagingService(
        access_code_content_sid=content_sid,
        require_phone_verified=require_phone_verified,
    )

    if (
        account_sid
        and auth_token
        and from_number
        and content_sid != DEFAULT_ACCESS_CODE_CONTENT_SID
    ):
        return TwilioWhatsAppChallengeMessagingService(
            account_sid=account_sid,
            auth_token=auth_token,
            from_number=from_number,
            access_code_content_sid=content_sid,
            require_phone_verified=require_phone_verified,
            fallback=console,
        )

    return console


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _expires_minutes(expires_at: Optional[datetime]) -> Optional[int]:
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - datetime.now(timezone.utc)
    return max(int(delta.total_seconds() // 60), 0)
