"""Transactional auth mail building blocks."""

from outlabs_auth.mail.composer import AuthMailComposer, DefaultAuthMailComposer
from outlabs_auth.mail.providers import (
    MailgunMailProvider,
    SMTPMailProvider,
    SendGridMailProvider,
    TransactionalMailProvider,
    WebhookMailProvider,
)
from outlabs_auth.mail.service import ComposedAuthMailService
from outlabs_auth.mail.types import (
    AccessGrantedMailIntent,
    AuthMailMessage,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    MailDeliveryResult,
    MailRecipient,
    PasswordResetConfirmationMailIntent,
)

__all__ = [
    "AccessGrantedMailIntent",
    "AuthMailComposer",
    "AuthMailMessage",
    "ComposedAuthMailService",
    "DefaultAuthMailComposer",
    "ForgotPasswordMailIntent",
    "InviteMailIntent",
    "MailDeliveryResult",
    "MailRecipient",
    "MailgunMailProvider",
    "PasswordResetConfirmationMailIntent",
    "SMTPMailProvider",
    "SendGridMailProvider",
    "TransactionalMailProvider",
    "WebhookMailProvider",
]
