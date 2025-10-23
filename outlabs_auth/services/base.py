"""
Base service class with lifecycle hook support.

Lifecycle hooks pattern from FastAPI-Users (DD-040).
"""

from typing import Any, Optional
from fastapi import Request


class BaseService:
    """
    Base class for all services with lifecycle hook support.

    Services can override hook methods to add custom logic:
    - Send emails
    - Trigger webhooks
    - Log events
    - Update analytics
    - Enforce business rules

    Example:
        ```python
        class MyUserService(UserService):
            async def on_after_register(self, user, request=None):
                # Send welcome email
                await email_service.send_welcome(user.email)

                # Log event
                logger.info(f"New user: {user.email}")

                # Trigger webhook
                await webhook.trigger("user.registered", {...})
        ```
    """

    pass  # Base class for type hints and future shared functionality
