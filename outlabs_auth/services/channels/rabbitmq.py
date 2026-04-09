"""
RabbitMQ Notification Channel

Publishes auth events to existing RabbitMQ exchange/queue.
Does NOT declare queues - connects to existing infrastructure (N8n-style).
"""
import json
from typing import Any, Dict, List, Optional

try:
    import aio_pika
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False

from outlabs_auth.services.channels.base import NotificationChannel


class RabbitMQChannel(NotificationChannel):
    """
    RabbitMQ notification channel for auth events.
    
    Publishes events to existing RabbitMQ infrastructure. Does NOT manage
    queues - user must set up queues/exchanges/bindings separately.
    
    This is designed to work like N8n's RabbitMQ nodes: just connect and send.
    
    Features:
    - Connects to existing exchange
    - Publishes JSON-formatted events
    - Persistent delivery mode for reliability
    - Automatic reconnection via aio_pika.connect_robust
    - Graceful degradation (disables if connection fails)
    
    Example:
        >>> from outlabs_auth.services.channels.rabbitmq import RabbitMQChannel
        >>> 
        >>> # Create channel
        >>> rabbitmq = RabbitMQChannel(
        ...     url="amqp://user:pass@localhost:5672/vhost",
        ...     routing_key="auth.events"
        ... )
        >>> 
        >>> # Connect (call once during initialization)
        >>> await rabbitmq.connect()
        >>> 
        >>> # Events are automatically published
        >>> await rabbitmq.send({
        ...     "type": "user.login",
        ...     "timestamp": "2025-01-15T10:30:00Z",
        ...     "data": {"user_id": "123", "email": "user@example.com"},
        ...     "metadata": {"ip": "192.168.1.1"}
        ... })
    """
    
    def __init__(
        self,
        url: str,
        exchange: str = "",
        routing_key: str = "auth.events",
        enabled: bool = True,
        event_filter: Optional[List[str]] = None
    ):
        """
        Initialize RabbitMQ channel.
        
        Args:
            url: RabbitMQ connection URL (amqp://user:pass@host:port/vhost)
            exchange: Exchange name (empty string = default exchange)
            routing_key: Routing key for messages (default: "auth.events")
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
        
        Raises:
            ImportError: If aio-pika is not installed
        """
        super().__init__(enabled, event_filter)
        
        if not RABBITMQ_AVAILABLE:
            raise ImportError(
                "aio-pika is required for RabbitMQ support. "
                "Install with: pip install outlabs-auth[notifications] "
                "or: pip install aio-pika"
            )
        
        self.url = url
        self.exchange = exchange
        self.routing_key = routing_key
        self.connection = None
        self.channel = None
    
    async def connect(self) -> bool:
        """
        Connect to RabbitMQ.
        
        Call this once during application initialization.
        Uses connect_robust for automatic reconnection.
        
        Returns:
            bool: True if connected successfully, False otherwise
        
        Note:
            If connection fails, the channel is automatically disabled
            to prevent repeated connection attempts.
        """
        if not self.enabled:
            return False
        
        try:
            # connect_robust provides automatic reconnection
            connection = await aio_pika.connect_robust(self.url)
            self.connection = connection
            self.channel = await connection.channel()
            return True
        except Exception as e:
            # Connection failed - disable this channel
            # This prevents auth operations from being slowed down
            # by repeated connection attempts
            self.enabled = False
            return False
    
    async def send(self, event: Dict[str, Any]) -> None:
        """
        Publish event to RabbitMQ.
        
        Args:
            event: Event dictionary with type, timestamp, data, metadata
        
        Note:
            Failures are silently ignored to prevent notification errors
            from affecting auth operations.
        """
        if not self.channel or not self.enabled:
            return
        
        try:
            # Convert event to JSON
            body = json.dumps(event).encode('utf-8')
            
            # Create message with persistent delivery
            message = aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers={
                    "event_type": event.get("type"),
                    "timestamp": event.get("timestamp")
                }
            )
            
            # Get exchange (empty string = default exchange)
            if self.exchange:
                exchange = await self.channel.get_exchange(self.exchange)
            else:
                # Use default exchange
                exchange = self.channel.default_exchange
            
            # Publish to exchange with routing key
            await exchange.publish(
                message,
                routing_key=self.routing_key
            )
            
        except Exception:
            # Fail silently - notifications should never break auth
            # In production, you might want to log to error tracking
            pass
    
    async def close(self) -> None:
        """
        Close RabbitMQ connection.
        
        Call this during application shutdown.
        """
        if self.connection:
            try:
                await self.connection.close()
            except Exception:
                pass
    
    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        connected = "connected" if self.channel else "disconnected"
        return f"<RabbitMQChannel: {status}, {connected}, routing_key={self.routing_key}>"
