"""
Channel-agnostic challenge delivery for the EnterpriseRBAC example.

Host-owned WhatsApp + SMS paths for auth challenges:
- Console spike when Twilio is not configured (local demos / E2E)
- Twilio WhatsApp Content API when TWILIO_WHATSAPP_* env vars are set
- Twilio SMS Messages API when TWILIO_SMS_FROM is set

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


def _normalize_sms_address(phone: str) -> str:
    return phone.removeprefix("whatsapp:").strip()


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


def _build_sms_body(intent: AuthChallengeDeliveryIntent) -> str:
    expires_minutes = _expires_minutes(intent.expires_at)
    expiry = (
        f" It expires in {expires_minutes} minutes."
        if expires_minutes is not None
        else ""
    )
    if intent.challenge_type == "phone_verify":
        return f"Your Outlabs Auth phone verification code is {intent.secret}.{expiry}"
    return f"Your Outlabs Auth sign-in code is {intent.secret}.{expiry}"


def _guard_access_code_whatsapp(
    intent: AuthChallengeDeliveryIntent,
    *,
    provider_name: str,
    require_phone_verified: bool,
) -> tuple[Optional[str], Optional[MessageDeliveryResult]]:
    delivery_channel = getattr(intent, "delivery_channel", None) or "whatsapp"
    if delivery_channel == "sms":
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "SMS challenges are handled by the SMS host path",
            details={
                "challenge_type": intent.challenge_type,
                "delivery_channel": delivery_channel,
            },
        )
    if delivery_channel not in {"whatsapp", "email"}:
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            f"unsupported delivery channel: {delivery_channel}",
            details={"challenge_type": intent.challenge_type},
        )

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

    if intent.challenge_type not in {
        "access_code",
        "whatsapp_otp",
        "phone_verify",
    }:
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "WhatsApp host path only implements whatsapp_otp, phone_verify, "
            "and legacy access_code templates",
            details={"challenge_type": intent.challenge_type},
        )

    if intent.challenge_type == "access_code" and delivery_channel == "email":
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "email access codes are not delivered over WhatsApp",
            details={"challenge_type": intent.challenge_type},
        )

    return phone, None


def _guard_access_code_sms(
    intent: AuthChallengeDeliveryIntent,
    *,
    provider_name: str,
    require_phone_verified: bool,
) -> tuple[Optional[str], Optional[MessageDeliveryResult]]:
    delivery_channel = getattr(intent, "delivery_channel", None) or "whatsapp"
    if delivery_channel != "sms":
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "WhatsApp/email challenges are not delivered over SMS",
            details={
                "challenge_type": intent.challenge_type,
                "delivery_channel": delivery_channel,
            },
        )

    phone = _normalize_sms_address(intent.recipient.phone or "")
    if not phone:
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "recipient has no phone",
            details={"challenge_type": intent.challenge_type, "email": intent.recipient.email},
        )

    if require_phone_verified and not intent.recipient.phone_verified:
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "phone is not verified",
            details={"challenge_type": intent.challenge_type, "phone": phone},
        )

    if intent.challenge_type not in {"sms_otp", "phone_verify"}:
        return None, MessageDeliveryResult.skipped_result(
            provider_name,
            "SMS host path only implements sms_otp and phone_verify",
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


class ConsoleSmsChallengeMessagingService:
    """Dev-friendly provider that prints a Twilio SMS-shaped payload."""

    provider_name = "console-sms"

    def __init__(
        self,
        *,
        output: Callable[[str], None] = print,
        require_phone_verified: bool = False,
    ) -> None:
        self.output = output
        self.require_phone_verified = require_phone_verified

    async def send_auth_challenge(
        self,
        intent: AuthChallengeDeliveryIntent,
    ) -> MessageDeliveryResult:
        phone, skipped = _guard_access_code_sms(
            intent,
            provider_name=self.provider_name,
            require_phone_verified=self.require_phone_verified,
        )
        if skipped is not None:
            return skipped
        assert phone is not None

        body = _build_sms_body(intent)
        lines = [
            "",
            "=" * 80,
            "SMS CHALLENGE (Console Spike)",
            "=" * 80,
            f"Challenge: {intent.challenge_type}",
            f"To: {phone}",
            f"Body: {body}",
            f"User ID: {intent.recipient.user_id}",
            f"Phone verified: {intent.recipient.phone_verified}",
            "=" * 80,
            "",
        ]
        self.output("\n".join(lines))
        return MessageDeliveryResult.queued(
            self.provider_name,
            details={"to": phone, "body": body},
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


class TwilioSmsChallengeMessagingService:
    """Host Twilio SMS Messages API delivery for sms_otp / phone_verify intents."""

    provider_name = "twilio-sms"

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        require_phone_verified: bool = False,
        fallback: Optional[ChallengeMessagingService] = None,
    ) -> None:
        try:
            from twilio.rest import Client as TwilioClient
        except ImportError as exc:  # pragma: no cover - optional extra
            raise ImportError(
                "twilio is required for Twilio SMS challenge delivery. "
                "Install with: pip install outlabs-auth[notifications]"
            ) from exc

        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = _normalize_sms_address(from_number)
        self.require_phone_verified = require_phone_verified
        self.fallback = fallback
        self.client = TwilioClient(account_sid, auth_token)

    async def send_auth_challenge(
        self,
        intent: AuthChallengeDeliveryIntent,
    ) -> MessageDeliveryResult:
        phone, skipped = _guard_access_code_sms(
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

        body = _build_sms_body(intent)
        try:
            message = await asyncio.to_thread(
                self.client.messages.create,
                from_=self.from_number,
                to=phone,
                body=body,
            )
        except Exception as exc:
            return MessageDeliveryResult.failed(
                self.provider_name,
                str(exc),
                details={"to": phone},
            )

        return MessageDeliveryResult.queued(
            self.provider_name,
            provider_message_id=getattr(message, "sid", None),
            details={"to": phone, "body": body},
        )


class MultiplexChallengeMessagingService:
    """Route intents to WhatsApp or SMS host providers by delivery_channel."""

    provider_name = "multiplex"

    def __init__(
        self,
        *,
        whatsapp: ChallengeMessagingService,
        sms: ChallengeMessagingService,
    ) -> None:
        self.whatsapp = whatsapp
        self.sms = sms

    async def send_auth_challenge(
        self,
        intent: AuthChallengeDeliveryIntent,
    ) -> MessageDeliveryResult:
        delivery_channel = getattr(intent, "delivery_channel", None) or "whatsapp"
        if delivery_channel == "sms":
            return await self.sms.send_auth_challenge(intent)
        if delivery_channel == "email":
            return MessageDeliveryResult.skipped_result(
                self.provider_name,
                "email challenges are delivered via transactional mail",
                details={"challenge_type": intent.challenge_type},
            )
        return await self.whatsapp.send_auth_challenge(intent)


def build_enterprise_example_challenge_messaging_service(
    *,
    access_code_content_sid: Optional[str] = None,
    twilio_account_sid: Optional[str] = None,
    twilio_auth_token: Optional[str] = None,
    twilio_whatsapp_from: Optional[str] = None,
    twilio_sms_from: Optional[str] = None,
    require_phone_verified: Optional[bool] = None,
) -> ChallengeMessagingService:
    """
    Factory used by the enterprise example app.

    WhatsApp: Twilio Content API when account SID, auth token, from number, and a
    real Content SID are configured; otherwise console spike.
    SMS: Twilio Messages API when TWILIO_SMS_FROM is set with shared account
    credentials; otherwise console spike.
    """
    content_sid = (
        access_code_content_sid
        or os.getenv("TWILIO_WHATSAPP_ACCESS_CODE_CONTENT_SID")
        or DEFAULT_ACCESS_CODE_CONTENT_SID
    )
    account_sid = twilio_account_sid or os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = twilio_auth_token or os.getenv("TWILIO_AUTH_TOKEN")
    whatsapp_from = twilio_whatsapp_from or os.getenv("TWILIO_WHATSAPP_FROM")
    sms_from = twilio_sms_from or os.getenv("TWILIO_SMS_FROM")
    if require_phone_verified is None:
        require_phone_verified = _env_flag("TWILIO_WHATSAPP_REQUIRE_VERIFIED", default=False)

    console_whatsapp = ConsoleWhatsAppChallengeMessagingService(
        access_code_content_sid=content_sid,
        require_phone_verified=require_phone_verified,
    )
    console_sms = ConsoleSmsChallengeMessagingService(
        require_phone_verified=require_phone_verified,
    )

    if (
        account_sid
        and auth_token
        and whatsapp_from
        and content_sid != DEFAULT_ACCESS_CODE_CONTENT_SID
    ):
        whatsapp: ChallengeMessagingService = TwilioWhatsAppChallengeMessagingService(
            account_sid=account_sid,
            auth_token=auth_token,
            from_number=whatsapp_from,
            access_code_content_sid=content_sid,
            require_phone_verified=require_phone_verified,
            fallback=console_whatsapp,
        )
    else:
        whatsapp = console_whatsapp

    if account_sid and auth_token and sms_from:
        sms: ChallengeMessagingService = TwilioSmsChallengeMessagingService(
            account_sid=account_sid,
            auth_token=auth_token,
            from_number=sms_from,
            require_phone_verified=require_phone_verified,
            fallback=console_sms,
        )
    else:
        sms = console_sms

    return MultiplexChallengeMessagingService(whatsapp=whatsapp, sms=sms)


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
