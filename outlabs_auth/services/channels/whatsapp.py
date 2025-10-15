"""
WhatsApp Notification Channel

Sends notifications for auth events via WhatsApp (using Twilio).
Popular globally, especially in international markets.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable

try:
    from twilio.rest import Client as TwilioClient
    WHATSAPP_AVAILABLE = True
except ImportError:
    WHATSAPP_AVAILABLE = False

from outlabs_auth.services.channels.base import NotificationChannel


# Type alias for message builder callback
MessageBuilder = Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, str]]]]


class WhatsAppChannel(NotificationChannel):
    """
    WhatsApp notification channel for auth events via Twilio.
    
    Sends WhatsApp messages using Twilio's WhatsApp API. Great for
    international users where WhatsApp is the primary messaging platform.
    
    Features:
    - WhatsApp Business API via Twilio
    - User-provided message builder callback
    - Template support (required by WhatsApp)
    - Event filtering
    - High open rates
    
    Setup:
    1. Set up Twilio WhatsApp Sandbox (for testing)
    2. Get approved WhatsApp Business account (for production)
    3. Create approved message templates
    4. Store user's WhatsApp number in database
    
    Note:
        WhatsApp requires pre-approved message templates for notifications.
        You cannot send arbitrary text. Templates must be approved by WhatsApp.
        
        For testing, use Twilio's WhatsApp Sandbox which is more flexible.
    
    Common Use Cases:
    - Security alerts
    - 2FA codes (with approved template)
    - Account activity notifications
    - Password reset confirmations
    
    Example:
        >>> from outlabs_auth.services.channels.whatsapp import WhatsAppChannel
        >>> 
        >>> # Define message builder callback
        >>> async def build_message(event):
        ...     if event["type"] == "user.locked":
        ...         # Get user's WhatsApp number from your database
        ...         phone = await get_user_whatsapp(event["data"]["user_id"])
        ...         if not phone:
        ...             return None
        ...         
        ...         return {
        ...             "to": phone,  # Must be in E.164 format: +1234567890
        ...             "body": "Your account has been locked due to suspicious activity. Please contact support."
        ...         }
        ...     return None
        >>> 
        >>> # Create channel
        >>> whatsapp = WhatsAppChannel(
        ...     account_sid="ACxxxx",
        ...     auth_token="your-token",
        ...     from_number="whatsapp:+14155238886",  # Twilio WhatsApp number
        ...     message_builder=build_message,
        ...     event_filter=["user.locked", "security.threat_detected"]
        ... )
        >>> 
        >>> # Events are automatically sent
        >>> await whatsapp.send({
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
        message_builder: Optional[MessageBuilder] = None
    ):
        """
        Initialize WhatsApp channel.
        
        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Twilio WhatsApp number (format: whatsapp:+1234567890)
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
            message_builder: Async callback to build message content from event
        
        Raises:
            ImportError: If twilio is not installed
        
        Note:
            The from_number must be in the format: whatsapp:+1234567890
            For sandbox: whatsapp:+14155238886
            For production: Your approved WhatsApp Business number
        """
        super().__init__(enabled, event_filter)
        
        if not WHATSAPP_AVAILABLE:
            raise ImportError(
                "twilio is required for WhatsApp support. "
                "Install with: pip install outlabs-auth[notifications] "
                "or: pip install twilio"
            )
        
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.message_builder = message_builder
        
        # Ensure from_number has whatsapp: prefix
        if not from_number.startswith("whatsapp:"):
            self.from_number = f"whatsapp:{from_number}"
        
        # Create Twilio client
        self.client = TwilioClient(account_sid, auth_token)
    
    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send WhatsApp notification.
        
        Args:
            event: Event dictionary with type, timestamp, data, metadata
        
        Note:
            If message_builder returns None, no message is sent.
            Failures are silently ignored.
            
            The message_builder should return:
            {
                "to": str (WhatsApp number in E.164 format: +1234567890),
                "body": str (message text - must comply with WhatsApp policies)
            }
            
            For production, you may need to use approved templates:
            {
                "to": str,
                "content_sid": str (template SID),
                "content_variables": dict (template variables)
            }
        """
        if not self.message_builder or not self.enabled:
            return
        
        try:
            # User provides the message content via callback
            message_data = await self.message_builder(event)
            
            # If builder returns None, don't send message
            if not message_data:
                return
            
            # Ensure 'to' number has whatsapp: prefix
            to_number = message_data["to"]
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"
            
            # Send via Twilio WhatsApp API
            # Note: Twilio client is synchronous
            if "content_sid" in message_data:
                # Using approved template (production)
                self.client.messages.create(
                    from_=self.from_number,
                    to=to_number,
                    content_sid=message_data["content_sid"],
                    content_variables=message_data.get("content_variables", {})
                )
            else:
                # Using freeform text (sandbox only)
                self.client.messages.create(
                    from_=self.from_number,
                    to=to_number,
                    body=message_data["body"]
                )
            
        except Exception:
            # Fail silently - notifications should never break auth
            pass
    
    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        return f"<WhatsAppChannel: {status}, from={self.from_number}>"
