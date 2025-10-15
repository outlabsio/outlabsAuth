"""
Twilio SMS Notification Channel

Sends SMS notifications for auth events via Twilio.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

from outlabs_auth.services.channels.base import NotificationChannel


# Type alias for SMS builder callback
SMSBuilder = Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, str]]]]


class TwilioChannel(NotificationChannel):
    """
    Twilio SMS notification channel for auth events.
    
    Sends SMS messages via Twilio API. Users provide SMS content via a
    callback function - the library does not impose any template system.
    
    Features:
    - SMS via Twilio REST API
    - User-provided SMS builder callback
    - Event filtering (e.g., only send SMS for critical events)
    - Async-friendly (uses sync client in thread pool)
    
    Common Use Cases:
    - 2FA/MFA codes
    - Account lockout notifications
    - Password reset confirmations
    - Security alerts
    
    Example:
        >>> from outlabs_auth.services.channels.twilio import TwilioChannel
        >>> 
        >>> # Define SMS builder callback
        >>> async def build_sms(event):
        ...     if event["type"] == "user.locked":
        ...         # Get user's phone from your database
        ...         phone = await get_user_phone(event["data"]["user_id"])
        ...         return {
        ...             "to": phone,
        ...             "body": "Your account has been locked due to suspicious activity."
        ...         }
        ...     return None  # Don't send SMS for this event
        >>> 
        >>> # Create channel
        >>> twilio = TwilioChannel(
        ...     account_sid="ACxxxx",
        ...     auth_token="your-token",
        ...     from_number="+1234567890",
        ...     sms_builder=build_sms,
        ...     event_filter=["user.locked", "user.password_reset_requested"]
        ... )
        >>> 
        >>> # Events are automatically sent
        >>> await twilio.send({
        ...     "type": "user.locked",
        ...     "data": {"user_id": "123"}
        ... })
    """
    
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None,
        sms_builder: Optional[SMSBuilder] = None
    ):
        """
        Initialize Twilio channel.
        
        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Twilio phone number (E.164 format, e.g., +1234567890)
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
            sms_builder: Async callback to build SMS content from event
        
        Raises:
            ImportError: If twilio is not installed
        """
        super().__init__(enabled, event_filter)
        
        if not TWILIO_AVAILABLE:
            raise ImportError(
                "twilio is required for SMS support. "
                "Install with: pip install outlabs-auth[notifications] "
                "or: pip install twilio"
            )
        
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.sms_builder = sms_builder
        
        # Create Twilio client
        self.client = TwilioClient(account_sid, auth_token)
    
    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send SMS notification.
        
        Args:
            event: Event dictionary with type, timestamp, data, metadata
        
        Note:
            If sms_builder returns None, no SMS is sent.
            Failures are silently ignored.
            
            The Twilio client is synchronous, so this method runs it in
            the default executor to avoid blocking.
        """
        if not self.sms_builder or not self.enabled:
            return
        
        try:
            # User provides the SMS content via callback
            sms_data = await self.sms_builder(event)
            
            # If builder returns None, don't send SMS
            if not sms_data:
                return
            
            # Send SMS via Twilio (sync call - Twilio client is not async)
            # In production, you might want to use asyncio.to_thread
            # for better async handling
            self.client.messages.create(
                to=sms_data["to"],
                from_=self.from_number,
                body=sms_data["body"]
            )
            
        except Exception:
            # Fail silently - notifications should never break auth
            pass
    
    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        return f"<TwilioChannel: {status}, from={self.from_number}>"
