"""
SendGrid Email Notification Channel

Sends email notifications for auth events via SendGrid API.
Often preferred over SMTP for production due to better deliverability.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, From, To, Subject, PlainTextContent, HtmlContent
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

from outlabs_auth.services.channels.base import NotificationChannel


# Type alias for email builder callback
EmailBuilder = Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, str]]]]


class SendGridChannel(NotificationChannel):
    """
    SendGrid email notification channel for auth events.
    
    Sends transactional emails via SendGrid API. Often preferred over SMTP
    for production use due to better deliverability, analytics, and reliability.
    
    Features:
    - SendGrid API v3
    - User-provided email builder callback
    - Plain text + HTML email support
    - Event filtering
    - Better deliverability than SMTP
    
    Example:
        >>> from outlabs_auth.services.channels.sendgrid import SendGridChannel
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
        >>> sendgrid = SendGridChannel(
        ...     api_key="SG.xxxxx",
        ...     from_email="noreply@example.com",
        ...     from_name="MyApp",
        ...     email_builder=build_email,
        ...     event_filter=["user.created", "user.password_reset_requested"]
        ... )
        >>> 
        >>> # Events are automatically sent
        >>> await sendgrid.send({
        ...     "type": "user.created",
        ...     "data": {"email": "user@example.com"}
        ... })
    """
    
    def __init__(
        self,
        api_key: str,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None,
        email_builder: Optional[EmailBuilder] = None
    ):
        """
        Initialize SendGrid channel.
        
        Args:
            api_key: SendGrid API key (starts with "SG.")
            from_email: From email address (must be verified in SendGrid)
            from_name: Optional from name (e.g., "MyApp Notifications")
            reply_to: Optional reply-to email address
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
            email_builder: Async callback to build email content from event
        
        Raises:
            ImportError: If sendgrid is not installed
        """
        super().__init__(enabled, event_filter)
        
        if not SENDGRID_AVAILABLE:
            raise ImportError(
                "sendgrid is required for SendGrid support. "
                "Install with: pip install outlabs-auth[notifications] "
                "or: pip install sendgrid"
            )
        
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.reply_to = reply_to
        self.email_builder = email_builder
        
        # Create SendGrid client
        self.client = SendGridAPIClient(api_key)
    
    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send email notification via SendGrid.
        
        Args:
            event: Event dictionary with type, timestamp, data, metadata
        
        Note:
            If email_builder returns None, no email is sent.
            Failures are silently ignored.
            
            The SendGrid client is synchronous, so this method runs it
            without blocking (fire-and-forget).
        """
        if not self.email_builder or not self.enabled:
            return
        
        try:
            # User provides the email content via callback
            email_data = await self.email_builder(event)
            
            # If builder returns None, don't send email
            if not email_data:
                return
            
            # Build from address
            from_addr = From(
                email=self.from_email,
                name=self.from_name
            ) if self.from_name else From(self.from_email)
            
            # Build to address
            to_addr = To(email_data["to"])
            
            # Build subject
            subject = Subject(email_data["subject"])
            
            # Build content
            plain_content = PlainTextContent(email_data["body"])
            
            # Create mail object
            mail = Mail(
                from_email=from_addr,
                to_emails=to_addr,
                subject=subject,
                plain_text_content=plain_content
            )
            
            # Add HTML content if provided
            if "html" in email_data:
                mail.add_content(HtmlContent(email_data["html"]))
            
            # Add reply-to if configured
            if self.reply_to:
                mail.reply_to = self.reply_to
            
            # Send via SendGrid
            # Note: SendGrid client is synchronous
            response = self.client.send(mail)
            
            # SendGrid returns 202 Accepted for successful queuing
            # We don't need to check the response - just fire and forget
            
        except Exception:
            # Fail silently - notifications should never break auth
            pass
    
    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        return f"<SendGridChannel: {status}, from={self.from_email}>"
