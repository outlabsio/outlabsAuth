"""
Notification Service

Central coordinator for auth-related notifications.
Emits events to configured channels (RabbitMQ, Email, SMS, Webhooks).
"""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from outlabs_auth.observability import ObservabilityService

from outlabs_auth.services.channels.base import NotificationChannel


class NotificationService:
    """
    Central notification coordinator for auth events.

    Responsibilities:
    - Route events to appropriate channels
    - Fire-and-forget execution (non-blocking)
    - Event validation and enrichment

    This service handles all auth-related notifications:
    - User authentication events (login, logout, login_failed)
    - User lifecycle events (created, deleted, status_changed)
    - Password events (changed, reset_requested, reset_completed)
    - Authorization events (role.assigned, role.revoked, permission.denied)
    - System/admin events (auth.error, security.threat_detected)

    Example:
        >>> from outlabs_auth.services.notification import NotificationService
        >>> from outlabs_auth.services.channels import RabbitMQChannel
        >>>
        >>> rabbitmq = RabbitMQChannel(url="amqp://localhost")
        >>> await rabbitmq.connect()
        >>>
        >>> notification_service = NotificationService(
        ...     enabled=True,
        ...     channels=[rabbitmq]
        ... )
        >>>
        >>> # Emit event (fire-and-forget)
        >>> await notification_service.emit(
        ...     "user.login",
        ...     data={"user_id": "123", "email": "user@example.com"},
        ...     metadata={"ip": "192.168.1.1"}
        ... )
    """

    def __init__(
        self,
        enabled: bool = False,
        channels: Optional[List[NotificationChannel]] = None,
        observability: Optional["ObservabilityService"] = None,
    ):
        """
        Initialize NotificationService.

        Args:
            enabled: Whether notifications are enabled globally
            channels: List of notification channels to use
            observability: Optional observability service for metrics/logging
        """
        self.enabled = enabled
        self.channels = channels or []
        self.observability = observability

    async def emit(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a notification event (fire-and-forget).

        This method returns immediately without waiting for notifications
        to be sent. Notification failures never affect auth operations.

        Args:
            event_type: Event name (e.g., "user.login", "user.locked")
            data: Event-specific data (user_id, email, etc.)
            metadata: Additional context (ip, user_agent, device, etc.)

        Event Types:
            Authentication:
                - user.login: Successful login
                - user.login_failed: Failed login attempt
                - user.locked: Account locked
                - user.unlocked: Account unlocked
                - user.logout: User logged out

            User Lifecycle:
                - user.created: New user registered
                - user.email_verified: Email verified
                - user.status_changed: Status updated
                - user.deleted: User deleted

            Password:
                - user.password_changed: Password updated
                - user.password_reset_requested: Reset initiated
                - user.password_reset_completed: Reset finished

            Authorization:
                - role.assigned: Role added to user
                - role.revoked: Role removed from user
                - permission.denied: Access denied

            System/Admin:
                - auth.error: Auth system error
                - security.threat_detected: Suspicious activity
                - api_key.created: API key created
                - api_key.revoked: API key revoked

        Example:
            >>> # In UserService.create_user():
            >>> await self.notifications.emit(
            ...     "user.created",
            ...     data={
            ...         "user_id": str(user.id),
            ...         "email": user.email,
            ...         "created_at": user.created_at.isoformat()
            ...     }
            ... )
            >>>
            >>> # In AuthService.login():
            >>> await self.notifications.emit(
            ...     "user.login",
            ...     data={"user_id": str(user.id), "email": user.email"},
            ...     metadata={"ip": ip_address, "device": device_name}
            ... )
        """
        if not self.enabled:
            return

        # Log observability
        if self.observability:
            user_id = data.get("user_id") if data else None
            self.observability.log_notification_event(
                event_type=event_type,
                channels_count=len(self.channels),
                user_id=user_id,
            )

        # Fire and forget - don't block the caller
        asyncio.create_task(self._process_event(event_type, data, metadata))

    async def _process_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """
        Internal: Process event across all channels.

        This runs in a background task and never raises exceptions
        to the caller.
        """
        try:
            # Enrich event with timestamp and context
            event = {
                "type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data or {},
                "metadata": metadata or {},
            }

            # Send to all enabled channels that want this event
            handled_channels = [
                channel for channel in self.channels if channel.should_handle(event_type)
            ]
            tasks = [channel.send(event) for channel in handled_channels]

            if tasks:
                # Fire all channels concurrently, capture exceptions
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Log any delivery failures
                if self.observability:
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            channel_name = handled_channels[i].__class__.__name__
                            self.observability.log_notification_delivery_failure(
                                event_type=event_type,
                                channel=channel_name,
                                error=str(result),
                            )

        except Exception as e:
            # Never let notification errors crash the app
            if self.observability:
                self.observability.log_notification_delivery_failure(
                    event_type=event_type,
                    channel="unknown",
                    error=str(e),
                )

    def add_channel(self, channel: NotificationChannel) -> None:
        """
        Add a notification channel at runtime.

        Args:
            channel: NotificationChannel instance to add
        """
        self.channels.append(channel)

    def remove_channel(self, channel: NotificationChannel) -> None:
        """
        Remove a notification channel.

        Args:
            channel: NotificationChannel instance to remove
        """
        if channel in self.channels:
            self.channels.remove(channel)

    @property
    def active_channels(self) -> List[str]:
        """Get list of active channel names."""
        return [
            channel.__class__.__name__ for channel in self.channels if channel.enabled
        ]
