"""
Base notification channel interface.

All notification channels (RabbitMQ, SMTP, Webhook, SMS) inherit from this.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class NotificationChannel(ABC):
    """
    Abstract base class for notification channels.
    
    Each channel (RabbitMQ, Email, SMS, Webhook) implements this interface
    to handle notifications in their specific way.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None
    ):
        """
        Initialize notification channel.
        
        Args:
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
                         (None = handle all events)
        """
        self.enabled = enabled
        self.event_filter = event_filter
    
    def should_handle(self, event_type: str) -> bool:
        """
        Check if this channel should handle a specific event type.
        
        Args:
            event_type: Event type to check (e.g., "user.login")
            
        Returns:
            bool: True if channel should handle this event
        """
        if not self.enabled:
            return False
        
        if self.event_filter is None:
            # No filter = handle all events
            return True
        
        # Check if event type is in filter
        return event_type in self.event_filter
    
    @abstractmethod
    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send notification via this channel.
        
        Args:
            event: Event dictionary containing:
                - type: str (event type, e.g., "user.login")
                - timestamp: str (ISO format)
                - data: dict (event-specific data)
                - metadata: dict (additional context)
        
        Note:
            This method should never raise exceptions - failures should be
            handled gracefully to prevent notification errors from affecting
            auth operations.
        """
        pass
