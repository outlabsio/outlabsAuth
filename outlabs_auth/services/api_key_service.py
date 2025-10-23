"""
API Key service with lifecycle hooks.

Implements lifecycle hooks pattern from FastAPI-Users (DD-040).
"""

from typing import Any, Optional
from fastapi import Request
from outlabs_auth.services.base import BaseService


class ApiKeyService(BaseService):
    """
    API key management service with lifecycle hooks.

    Available Hooks:
        - on_api_key_created: After API key creation
        - on_api_key_revoked: After API key revocation
        - on_api_key_locked: After API key temporary lock
        - on_api_key_unlocked: After API key unlock
        - on_api_key_rotated: After API key rotation
        - on_failed_verification: After failed API key verification
    """

    def __init__(self, database: Any):
        self.database = database

    # ===================================================================
    # LIFECYCLE HOOKS
    # ===================================================================

    async def on_api_key_created(
        self,
        api_key: Any,
        plain_key: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after API key creation.

        Override to:
        - Email the key to user (ONLY time to show full key!)
        - Log security event
        - Trigger webhook

        Args:
            api_key: The created API key document
            plain_key: The plain text key (will never be shown again!)
            request: Optional request object
        """
        pass

    async def on_api_key_revoked(
        self,
        api_key: Any,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after API key revocation.

        Override to:
        - Send security notification to user
        - Log audit event
        - Invalidate cache

        Args:
            api_key: The revoked API key
            request: Optional request object
        """
        pass

    async def on_api_key_locked(
        self,
        api_key: Any,
        reason: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after API key temporary lock (DD-028).

        Override to:
        - Alert user of suspicious activity
        - Log security event
        - Trigger fraud detection

        Args:
            api_key: The locked API key
            reason: Reason for lock (e.g., "10 failures in 10 minutes")
            request: Optional request object
        """
        pass

    async def on_api_key_unlocked(
        self,
        api_key: Any,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after API key unlock.

        Args:
            api_key: The unlocked API key
            request: Optional request object
        """
        pass

    async def on_api_key_rotated(
        self,
        old_api_key: Any,
        new_api_key: Any,
        new_plain_key: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after API key rotation.

        Override to:
        - Email new key to user
        - Log rotation event
        - Send migration instructions

        Args:
            old_api_key: The old (revoked) API key
            new_api_key: The new API key
            new_plain_key: The plain text new key
            request: Optional request object
        """
        pass

    async def on_failed_verification(
        self,
        key_prefix: str,
        reason: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after failed API key verification.

        Override to:
        - Track brute force attempts
        - Implement rate limiting
        - Alert on suspicious patterns

        Args:
            key_prefix: The key prefix that failed
            reason: Reason for failure (e.g., "invalid hash", "locked", "expired")
            request: Optional request object
        """
        pass
