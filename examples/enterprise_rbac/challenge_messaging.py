"""
Channel-agnostic challenge delivery for the EnterpriseRBAC example.

Demonstrates Phase A/B WhatsApp wiring without real Twilio credentials:
when an access-code intent includes a phone number, print a WhatsApp
Content API-shaped payload to stdout. Magic links without a phone are
skipped here (hosts can also compose email in the same service).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

from outlabs_auth.messaging import (
    AuthChallengeDeliveryIntent,
    MessageDeliveryResult,
)

# Example Content SID placeholder — replace with a host-approved Twilio template.
DEFAULT_ACCESS_CODE_CONTENT_SID = "HX_ACCESS_CODE_TEMPLATE_PLACEHOLDER"


class ConsoleWhatsAppChallengeMessagingService:
    """
    Host-owned challenge messaging spike.

    Real mounts would call Twilio/Meta here. This console provider shows the
    exact template variables OutlabsAuth supplies so hosts can map them.
    """

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
        phone = (intent.recipient.phone or "").strip()
        if not phone:
            return MessageDeliveryResult.skipped_result(
                self.provider_name,
                "recipient has no phone; host may deliver via email instead",
                details={"challenge_type": intent.challenge_type, "email": intent.recipient.email},
            )

        if self.require_phone_verified and not intent.recipient.phone_verified:
            return MessageDeliveryResult.skipped_result(
                self.provider_name,
                "phone is not verified",
                details={"challenge_type": intent.challenge_type, "phone": phone},
            )

        if intent.challenge_type != "access_code":
            return MessageDeliveryResult.skipped_result(
                self.provider_name,
                "console WhatsApp spike only implements access_code templates",
                details={"challenge_type": intent.challenge_type},
            )

        expires_minutes = _expires_minutes(intent.expires_at)
        to_address = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        content_variables = {
            "1": intent.secret,
            "2": str(expires_minutes) if expires_minutes is not None else "",
            "email": intent.recipient.email,
            "display_name": intent.recipient.display_name,
        }
        if intent.redirect_url:
            content_variables["redirect_url"] = intent.redirect_url

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


def build_enterprise_example_challenge_messaging_service(
    *,
    access_code_content_sid: Optional[str] = None,
) -> ConsoleWhatsAppChallengeMessagingService:
    """Factory used by the enterprise example app."""
    return ConsoleWhatsAppChallengeMessagingService(
        access_code_content_sid=access_code_content_sid or DEFAULT_ACCESS_CODE_CONTENT_SID,
    )


def _expires_minutes(expires_at: Optional[datetime]) -> Optional[int]:
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - datetime.now(timezone.utc)
    return max(int(delta.total_seconds() // 60), 0)
