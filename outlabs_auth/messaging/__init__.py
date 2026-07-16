"""Channel-agnostic transactional messaging for auth challenges."""

from outlabs_auth.messaging.types import (
    AuthChallengeDeliveryIntent,
    AuthChallengeTypeName,
    DeliveryRecipient,
    MessageDeliveryResult,
    coerce_metadata,
)

__all__ = [
    "AuthChallengeDeliveryIntent",
    "AuthChallengeTypeName",
    "DeliveryRecipient",
    "MessageDeliveryResult",
    "coerce_metadata",
]
