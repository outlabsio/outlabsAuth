"""Transactional mail orchestration for auth lifecycle events."""

from __future__ import annotations

from outlabs_auth.mail.composer import AuthMailComposer
from outlabs_auth.mail.providers import TransactionalMailProvider
from outlabs_auth.mail.types import (
    AccessGrantedMailIntent,
    AuthMailMessage,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    MailDeliveryResult,
    PasswordResetConfirmationMailIntent,
)


class ComposedAuthMailService:
    """Compose auth mail messages and dispatch them through a provider."""

    def __init__(
        self,
        *,
        provider: TransactionalMailProvider,
        composer: AuthMailComposer,
    ) -> None:
        self.provider = provider
        self.composer = composer

    async def send_invite(self, intent: InviteMailIntent) -> MailDeliveryResult:
        return await self._compose_and_send(await self.composer.compose_invite(intent))

    async def send_forgot_password(self, intent: ForgotPasswordMailIntent) -> MailDeliveryResult:
        return await self._compose_and_send(await self.composer.compose_forgot_password(intent))

    async def send_password_reset_confirmation(
        self,
        intent: PasswordResetConfirmationMailIntent,
    ) -> MailDeliveryResult:
        return await self._compose_and_send(await self.composer.compose_password_reset_confirmation(intent))

    async def send_access_granted(self, intent: AccessGrantedMailIntent) -> MailDeliveryResult:
        return await self._compose_and_send(await self.composer.compose_access_granted(intent))

    async def _compose_and_send(self, message: AuthMailMessage | None) -> MailDeliveryResult:
        if message is None:
            return MailDeliveryResult.skipped_result(
                getattr(self.provider, "provider_name", self.provider.__class__.__name__.lower()),
                "composer returned no message",
            )
        return await self.provider.send(message)
