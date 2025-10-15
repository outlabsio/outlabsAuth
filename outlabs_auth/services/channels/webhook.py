"""
Webhook Notification Channel

POSTs auth events to HTTP endpoints with optional HMAC signature verification.
"""
import json
import hmac
import hashlib
from typing import Optional, List, Dict, Any

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from outlabs_auth.services.channels.base import NotificationChannel


class WebhookChannel(NotificationChannel):
    """
    Webhook notification channel for auth events.
    
    POSTs events to user-defined HTTP endpoints with optional HMAC signature
    for webhook verification (similar to GitHub, Stripe, etc.).
    
    Features:
    - POST events as JSON
    - HMAC-SHA256 signature in headers
    - Custom timeout configuration
    - Event type in headers for easy routing
    - Async HTTP via httpx
    
    Example:
        >>> from outlabs_auth.services.channels.webhook import WebhookChannel
        >>> 
        >>> # Create channel with signature
        >>> webhook = WebhookChannel(
        ...     url="https://api.example.com/auth-events",
        ...     secret="webhook-signing-secret",
        ...     timeout=5
        ... )
        >>> 
        >>> # Events are automatically POSTed
        >>> await webhook.send({
        ...     "type": "user.login",
        ...     "timestamp": "2025-01-15T10:30:00Z",
        ...     "data": {"user_id": "123", "email": "user@example.com"},
        ...     "metadata": {"ip": "192.168.1.1"}
        ... })
        >>> 
        >>> # Verify signature on receiving end:
        >>> import hmac
        >>> import hashlib
        >>> 
        >>> def verify_webhook(payload, signature, secret):
        ...     expected = hmac.new(
        ...         secret.encode(),
        ...         payload.encode(),
        ...         hashlib.sha256
        ...     ).hexdigest()
        ...     return hmac.compare_digest(f"sha256={expected}", signature)
    """
    
    def __init__(
        self,
        url: str,
        secret: Optional[str] = None,
        timeout: int = 5,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None,
        custom_headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize Webhook channel.
        
        Args:
            url: Webhook endpoint URL (must be HTTPS in production)
            secret: Optional secret for HMAC signature (highly recommended)
            timeout: HTTP request timeout in seconds
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
            custom_headers: Optional additional headers to send
        
        Raises:
            ImportError: If httpx is not installed
        """
        super().__init__(enabled, event_filter)
        
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx is required for Webhook support. "
                "Install with: pip install outlabs-auth[notifications] "
                "or: pip install httpx"
            )
        
        self.url = url
        self.secret = secret
        self.timeout = timeout
        self.custom_headers = custom_headers or {}
    
    def _sign_payload(self, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook verification.
        
        Args:
            payload: JSON payload string
        
        Returns:
            str: Hex digest of HMAC signature (prefixed with "sha256=")
        """
        if not self.secret:
            return ""
        
        signature = hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    async def send(self, event: Dict[str, Any]) -> None:
        """
        POST event to webhook URL.
        
        Args:
            event: Event dictionary with type, timestamp, data, metadata
        
        Headers sent:
            - Content-Type: application/json
            - X-OutlabsAuth-Event: {event_type}
            - X-OutlabsAuth-Signature: sha256={hmac} (if secret provided)
            - X-OutlabsAuth-Timestamp: {event_timestamp}
        
        Note:
            Failures are silently ignored. The webhook endpoint should
            return 2xx for success - other responses are considered failures.
        """
        if not self.enabled:
            return
        
        try:
            # Convert event to JSON
            payload = json.dumps(event)
            
            # Build headers
            headers = {
                "Content-Type": "application/json",
                "X-OutlabsAuth-Event": event.get("type", "unknown"),
                "X-OutlabsAuth-Timestamp": event.get("timestamp", ""),
                **self.custom_headers
            }
            
            # Add HMAC signature if secret provided
            if self.secret:
                headers["X-OutlabsAuth-Signature"] = self._sign_payload(payload)
            
            # POST to webhook URL
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    content=payload,
                    headers=headers
                )
                
                # We don't raise on bad status - just fail silently
                # Webhook endpoints should return 2xx for success
                
        except Exception:
            # Fail silently - notifications should never break auth
            pass
    
    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        signed = "signed" if self.secret else "unsigned"
        return f"<WebhookChannel: {status}, {signed}, url={self.url}>"
