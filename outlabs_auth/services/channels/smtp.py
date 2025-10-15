"""
SMTP/Email Notification Channel

Sends email notifications for auth events.
Users provide email content via callback - no built-in templates.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable
from email.message import EmailMessage

try:
    import aiosmtplib
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False

from outlabs_auth.services.channels.base import NotificationChannel


# Type alias for email builder callback
EmailBuilder = Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, str]]]]


class SMTPChannel(NotificationChannel):
    """
    SMTP email notification channel for auth events.
    
    Handles email sending via SMTP. Users provide their own email content
    via a callback function - the library does not impose any template system.
    
    Features:
    - Async SMTP via aiosmtplib
    - TLS/SSL support
    - User-provided email builder callback
    - Plain text + HTML email support
    - Event filtering (e.g., only send emails for specific events)
    
    Example:
        >>> from outlabs_auth.services.channels.smtp import SMTPChannel
        >>> 
        >>> # Define email builder callback
        >>> async def build_email(event):
        ...     if event["type"] == "user.created":
        ...         return {
        ...             "to": event["data"]["email"],
        ...             "subject": "Welcome!",
        ...             "body": f"Welcome {event['data']['email']}!",
        ...             "html": "<h1>Welcome!</h1>"
        ...         }
        ...     return None  # Don't send email for this event
        >>> 
        >>> # Create channel
        >>> smtp = SMTPChannel(
        ...     host="smtp.gmail.com",
        ...     port=587,
        ...     user="noreply@example.com",
        ...     password="app-password",
        ...     from_email="noreply@example.com",
        ...     email_builder=build_email,
        ...     event_filter=["user.created", "user.password_reset_requested"]
        ... )
        >>> 
        >>> # Events are automatically sent
        >>> await smtp.send({
        ...     "type": "user.created",
        ...     "data": {"email": "user@example.com"}
        ... })
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_email: str,
        from_name: Optional[str] = None,
        use_tls: bool = True,
        timeout: int = 10,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None,
        email_builder: Optional[EmailBuilder] = None
    ):
        """
        Initialize SMTP channel.
        
        Args:
            host: SMTP server hostname (e.g., smtp.gmail.com)
            port: SMTP server port (587 for TLS, 465 for SSL, 25 for plain)
            user: SMTP username
            password: SMTP password (use app-specific password for Gmail)
            from_email: From email address
            from_name: Optional from name (e.g., "MyApp Notifications")
            use_tls: Use STARTTLS (recommended for port 587)
            timeout: SMTP connection timeout in seconds
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
            email_builder: Async callback to build email content from event
        
        Raises:
            ImportError: If aiosmtplib is not installed
        """
        super().__init__(enabled, event_filter)
        
        if not SMTP_AVAILABLE:
            raise ImportError(
                "aiosmtplib is required for SMTP support. "
                "Install with: pip install outlabs-auth[notifications] "
                "or: pip install aiosmtplib"
            )
        
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.use_tls = use_tls
        self.timeout = timeout
        self.email_builder = email_builder
    
    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send email notification.
        
        Args:
            event: Event dictionary with type, timestamp, data, metadata
        
        Note:
            If email_builder returns None, no email is sent.
            Failures are silently ignored.
        """
        if not self.email_builder or not self.enabled:
            return
        
        try:
            # User provides the email content via callback
            email_data = await self.email_builder(event)
            
            # If builder returns None, don't send email
            if not email_data:
                return
            
            # Create email message
            message = EmailMessage()
            message["From"] = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
            message["To"] = email_data["to"]
            message["Subject"] = email_data["subject"]
            
            # Set plain text body
            message.set_content(email_data["body"])
            
            # Add HTML alternative if provided
            if "html" in email_data:
                message.add_alternative(email_data["html"], subtype="html")
            
            # Send via SMTP
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                use_tls=self.use_tls,
                timeout=self.timeout
            )
            
        except Exception:
            # Fail silently - notifications should never break auth
            pass
    
    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        return f"<SMTPChannel: {status}, host={self.host}, from={self.from_email}>"
