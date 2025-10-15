# Notification System Design (v1.1)

**Version**: 1.1  
**Status**: Planning  
**Scope**: Auth-related communications only

---

## Overview

The notification system provides an event-driven architecture for sending auth-related notifications through multiple channels (RabbitMQ, Email, SMS, Webhooks). It's designed to be:

- **Optional**: Can be disabled entirely without affecting core auth functionality
- **Non-blocking**: Fire-and-forget pattern - auth operations never wait for notifications
- **Easy to extend**: Simple API for emitting notifications from any service
- **Channel-agnostic**: Same event can be sent to multiple channels
- **Auth-scoped**: Only handles authentication and authorization events

---

## Architecture

### High-Level Design

```
┌─────────────┐
│   Service   │  (e.g., AuthService, UserService)
│  emits()    │
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ NotificationService  │  Central coordinator
│  - Route events      │
│  - Fire-and-forget   │
└──────────────────────┘
       │
       ├─────────┬─────────┬─────────┐
       ▼         ▼         ▼         ▼
  ┌────────┐ ┌──────┐ ┌──────┐ ┌─────────┐
  │RabbitMQ│ │ SMTP │ │ SMS  │ │Webhooks │
  │Channel │ │Channel│ │Channel│ │Channel  │
  └────────┘ └──────┘ └──────┘ └─────────┘
```

### Event Flow

1. **Service emits event**: `await self.notify("user.login", user_id=user.id, ip=request.ip)`
2. **NotificationService receives**: Validates event, enriches with context
3. **Channels process**: Each enabled channel handles the event asynchronously
4. **Fire-and-forget**: Original service continues immediately

---

## Event Catalog

### User Authentication Events

| Event | Trigger | Data | Use Cases |
|-------|---------|------|-----------|
| `user.login` | Successful login | user_id, ip, device | Security alerts, analytics |
| `user.login_failed` | Failed login attempt | email, ip, reason | Brute force detection |
| `user.locked` | Account locked | user_id, reason, attempts | Security notification |
| `user.unlocked` | Account unlocked | user_id, unlocked_by | Confirmation email |
| `user.logout` | User logs out | user_id, session_id | Session tracking |

### User Lifecycle Events

| Event | Trigger | Data | Use Cases |
|-------|---------|------|-----------|
| `user.created` | New user registered | user_id, email | Welcome email, onboarding |
| `user.email_verified` | Email verified | user_id, email | Confirmation notification |
| `user.status_changed` | Status updated | user_id, old_status, new_status | Admin notification |
| `user.deleted` | User deleted | user_id, email, deleted_by | Audit log |

### Password Events

| Event | Trigger | Data | Use Cases |
|-------|---------|------|-----------|
| `user.password_changed` | Password updated | user_id, changed_by | Security notification |
| `user.password_reset_requested` | Reset initiated | user_id, email, token | Reset email |
| `user.password_reset_completed` | Reset finished | user_id, email | Confirmation |

### Authorization Events

| Event | Trigger | Data | Use Cases |
|-------|---------|------|-----------|
| `role.assigned` | Role added | user_id, role_id, entity_id | Permission change notification |
| `role.revoked` | Role removed | user_id, role_id, entity_id | Permission change notification |
| `permission.denied` | Access denied | user_id, permission, resource | Security monitoring |

### System/Admin Events

| Event | Trigger | Data | Use Cases |
|-------|---------|------|-----------|
| `auth.error` | Auth system error | error_type, message, trace | Admin alert |
| `security.threat_detected` | Suspicious activity | user_id, threat_type, details | Security team alert |
| `api_key.created` | API key created | key_id, created_by | Security audit |
| `api_key.revoked` | API key revoked | key_id, revoked_by | Security audit |

---

## Implementation Design

### 1. NotificationService (Core)

```python
# outlabs_auth/services/notification.py

from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime

class NotificationService:
    """
    Central notification coordinator.
    
    Responsibilities:
    - Route events to appropriate channels
    - Fire-and-forget execution (non-blocking)
    - Event validation and enrichment
    """
    
    def __init__(
        self,
        enabled: bool = False,
        channels: Optional[List['NotificationChannel']] = None
    ):
        self.enabled = enabled
        self.channels = channels or []
    
    async def emit(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Emit a notification event (fire-and-forget).
        
        Args:
            event_type: Event name (e.g., "user.login")
            data: Event data (user_id, email, etc.)
            metadata: Additional context (ip, user_agent, etc.)
        
        Usage:
            await notification_service.emit(
                "user.login",
                data={"user_id": str(user.id), "email": user.email},
                metadata={"ip": request.ip, "device": "mobile"}
            )
        """
        if not self.enabled:
            return
        
        # Fire and forget - don't block the caller
        asyncio.create_task(self._process_event(event_type, data, metadata))
    
    async def _process_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Internal: Process event across all channels."""
        try:
            # Enrich event with timestamp and context
            event = {
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data or {},
                "metadata": metadata or {}
            }
            
            # Send to all enabled channels
            tasks = [
                channel.send(event)
                for channel in self.channels
                if channel.should_handle(event_type)
            ]
            
            if tasks:
                # Fire all channels concurrently, ignore failures
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            # Never let notification errors crash the app
            # Could log to error tracking service here
            pass
```

### 2. Channel Interface

```python
# outlabs_auth/services/channels/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List

class NotificationChannel(ABC):
    """Base class for notification channels."""
    
    def __init__(self, enabled: bool = True, event_filter: Optional[List[str]] = None):
        self.enabled = enabled
        self.event_filter = event_filter  # None = all events
    
    def should_handle(self, event_type: str) -> bool:
        """Check if this channel should handle the event."""
        if not self.enabled:
            return False
        if self.event_filter is None:
            return True
        return event_type in self.event_filter
    
    @abstractmethod
    async def send(self, event: Dict[str, Any]) -> None:
        """Send notification via this channel."""
        pass
```

### 3. RabbitMQ Channel

```python
# outlabs_auth/services/channels/rabbitmq.py

import aio_pika
import json
from typing import Optional

class RabbitMQChannel(NotificationChannel):
    """
    RabbitMQ notification channel.
    
    Publishes events to existing RabbitMQ exchange/queue.
    Does NOT declare queues - connects to existing infrastructure.
    """
    
    def __init__(
        self,
        url: str,
        exchange: str = "",
        routing_key: str = "auth.events",
        enabled: bool = True,
        event_filter: Optional[List[str]] = None
    ):
        super().__init__(enabled, event_filter)
        self.url = url
        self.exchange = exchange
        self.routing_key = routing_key
        self.connection = None
        self.channel = None
    
    async def connect(self):
        """Connect to RabbitMQ (call once during initialization)."""
        try:
            self.connection = await aio_pika.connect_robust(self.url)
            self.channel = await self.connection.channel()
        except Exception as e:
            # Connection failed - disable this channel
            self.enabled = False
    
    async def send(self, event: Dict[str, Any]) -> None:
        """Publish event to RabbitMQ."""
        if not self.channel:
            return
        
        try:
            message = aio_pika.Message(
                body=json.dumps(event).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            exchange = await self.channel.get_exchange(self.exchange)
            await exchange.publish(
                message,
                routing_key=self.routing_key
            )
        except Exception:
            # Fail silently - notifications should never break auth
            pass
```

### 4. SMTP Channel

```python
# outlabs_auth/services/channels/smtp.py

import aiosmtplib
from email.message import EmailMessage
from typing import Optional, Dict, Any

class SMTPChannel(NotificationChannel):
    """
    Email notification channel.
    
    Users provide email content via callbacks or templates.
    This channel handles the SMTP sending.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_email: str,
        use_tls: bool = True,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None,
        email_builder: Optional[callable] = None
    ):
        super().__init__(enabled, event_filter)
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls
        self.email_builder = email_builder  # User-provided callback
    
    async def send(self, event: Dict[str, Any]) -> None:
        """Send email notification."""
        if not self.email_builder:
            return
        
        try:
            # User provides the email content via callback
            email_data = await self.email_builder(event)
            if not email_data:
                return
            
            message = EmailMessage()
            message["From"] = self.from_email
            message["To"] = email_data["to"]
            message["Subject"] = email_data["subject"]
            message.set_content(email_data["body"])
            
            if "html" in email_data:
                message.add_alternative(email_data["html"], subtype="html")
            
            # Send via SMTP
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                use_tls=self.use_tls
            )
        except Exception:
            pass
```

### 5. Webhook Channel

```python
# outlabs_auth/services/channels/webhook.py

import httpx
import hmac
import hashlib
import json
from typing import Optional

class WebhookChannel(NotificationChannel):
    """
    Webhook notification channel.
    
    POSTs events to user-defined URL with HMAC signature.
    """
    
    def __init__(
        self,
        url: str,
        secret: Optional[str] = None,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None,
        timeout: int = 5
    ):
        super().__init__(enabled, event_filter)
        self.url = url
        self.secret = secret
        self.timeout = timeout
    
    def _sign_payload(self, payload: str) -> str:
        """Generate HMAC signature for webhook verification."""
        if not self.secret:
            return ""
        return hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def send(self, event: Dict[str, Any]) -> None:
        """POST event to webhook URL."""
        try:
            payload = json.dumps(event)
            headers = {
                "Content-Type": "application/json",
                "X-OutlabsAuth-Event": event["type"]
            }
            
            if self.secret:
                headers["X-OutlabsAuth-Signature"] = f"sha256={self._sign_payload(payload)}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(self.url, content=payload, headers=headers)
        except Exception:
            pass
```

---

## Integration with Services

### Adding Notifications to Existing Services

**Example: UserService with notifications**

```python
# outlabs_auth/services/user.py

class UserService:
    def __init__(
        self,
        database,
        notification_service: Optional[NotificationService] = None
    ):
        self.db = database
        self.notifications = notification_service
    
    async def create_user(self, email: str, password: str, **kwargs) -> UserModel:
        """Create new user with notification."""
        user = UserModel(email=email, ...)
        await user.insert()
        
        # Emit notification (fire-and-forget)
        if self.notifications:
            await self.notifications.emit(
                "user.created",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "created_at": user.created_at.isoformat()
                }
            )
        
        return user
    
    async def lock_account(self, user_id: str, reason: str) -> None:
        """Lock user account with notification."""
        user = await self.get_user(user_id)
        user.status = UserStatus.LOCKED
        await user.save()
        
        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.locked",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "reason": reason,
                    "locked_at": datetime.utcnow().isoformat()
                }
            )
```

---

## Configuration

### Environment Variables

```bash
# Enable notifications
NOTIFICATIONS_ENABLED=true

# RabbitMQ (primary channel)
RABBITMQ_URL=amqp://user:pass@localhost:5672/vhost
RABBITMQ_EXCHANGE=notifications
RABBITMQ_ROUTING_KEY=auth.events

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=app-password
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=noreply@example.com

# SMS (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_FROM_NUMBER=+1234567890

# Webhooks
WEBHOOK_URL=https://api.example.com/auth-events
WEBHOOK_SECRET=signing-secret
```

### Initialization

```python
# User's application code

from outlabs_auth import SimpleRBAC
from outlabs_auth.services.notification import NotificationService
from outlabs_auth.services.channels import RabbitMQChannel, SMTPChannel

# Define custom email builder
async def build_email(event):
    """User-provided callback to build emails."""
    if event["type"] == "user.created":
        return {
            "to": event["data"]["email"],
            "subject": "Welcome to our app!",
            "body": f"Welcome {event['data']['email']}!",
            "html": "<h1>Welcome!</h1>"
        }
    return None

# Configure notification channels
rabbitmq = RabbitMQChannel(
    url=os.getenv("RABBITMQ_URL"),
    routing_key="auth.events"
)
await rabbitmq.connect()

smtp = SMTPChannel(
    host=os.getenv("SMTP_HOST"),
    port=int(os.getenv("SMTP_PORT")),
    user=os.getenv("SMTP_USER"),
    password=os.getenv("SMTP_PASSWORD"),
    from_email=os.getenv("SMTP_FROM_EMAIL"),
    email_builder=build_email,
    event_filter=["user.created", "user.password_reset_requested"]  # Only these events
)

# Create notification service
notification_service = NotificationService(
    enabled=os.getenv("NOTIFICATIONS_ENABLED") == "true",
    channels=[rabbitmq, smtp]
)

# Initialize auth with notifications
auth = SimpleRBAC(
    database=mongo_client,
    secret_key="...",
    notification_service=notification_service
)
```

---

## Key Design Principles

### 1. **Fire-and-Forget**
- Auth operations never wait for notifications
- Uses `asyncio.create_task()` for non-blocking execution
- Notification failures never crash auth operations

### 2. **Optional and Safe**
- Can be disabled entirely (`enabled=False`)
- Missing config = channel disabled automatically
- Exceptions are caught and ignored

### 3. **Channel Filtering**
- Channels can subscribe to specific events
- `event_filter=["user.login", "user.locked"]`
- Default: All events go to all channels

### 4. **User-Provided Content**
- Library doesn't dictate email templates
- Users provide `email_builder` callback
- Full control over notification content

### 5. **Simple Integration**
- One line to emit: `await self.notifications.emit("event", data)`
- Same pattern everywhere in codebase
- Easy to add to new services

---

## Testing Strategy

### Unit Tests
- Test each channel independently
- Mock external services (RabbitMQ, SMTP)
- Test event filtering logic

### Integration Tests
- Test NotificationService with real channels
- Verify fire-and-forget behavior
- Test failure scenarios (channel down, timeout)

### Test Fixtures
```python
@pytest.fixture
async def notification_service_with_mock():
    """NotificationService with mock channels."""
    mock_channel = MockNotificationChannel()
    service = NotificationService(enabled=True, channels=[mock_channel])
    return service, mock_channel
```

---

## Future Enhancements (Post v1.1)

- **Event History**: Optional DB storage of sent notifications
- **Retry Logic**: Configurable retry for failed deliveries
- **Rate Limiting**: Prevent notification spam
- **Additional Channels**: Slack, Discord, PagerDuty
- **Event Batching**: Batch multiple events for efficiency

---

## Migration Path

### Adding to Existing Services

1. Add `notification_service` parameter to service `__init__`
2. Call `await self.notifications.emit()` after key operations
3. No breaking changes - all optional

```python
# Before
class UserService:
    def __init__(self, database):
        self.db = database

# After (backward compatible)
class UserService:
    def __init__(self, database, notification_service=None):
        self.db = database
        self.notifications = notification_service
```

---

## Summary

This notification system:
- ✅ **Scoped to auth**: Only handles auth-related events
- ✅ **Non-blocking**: Fire-and-forget pattern
- ✅ **Easy to use**: One-line API for emitting events
- ✅ **Optional**: Can be disabled without breaking anything
- ✅ **Extensible**: Easy to add new channels and events
- ✅ **Safe**: Failures never affect auth operations
- ✅ **Flexible**: Users control notification content
