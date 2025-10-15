# OutlabsAuth Notifications Example

This example demonstrates how to integrate the OutlabsAuth notification system with multiple channels in a real FastAPI application.

## Features

- **Multiple notification channels**: Webhook, SMTP Email, Telegram, RabbitMQ
- **Event-based notifications**: Automatic notifications on auth events (login, password change, etc.)
- **Custom message builders**: Full control over notification content
- **Event filtering**: Configure which events each channel should handle
- **Production-ready patterns**: Fire-and-forget, error handling, async support

## Notification Channels

### 1. Webhook Channel
Send all auth events to an external webhook endpoint (e.g., for logging, monitoring, analytics).

**Use cases:**
- Log aggregation (Datadog, Splunk)
- Security monitoring (SIEM systems)
- Analytics platforms

**Example payload:**
```json
{
  "type": "user.login",
  "timestamp": "2025-10-15T10:30:00Z",
  "data": {
    "user_id": "507f1f77bcf86cd799439011",
    "email": "user@example.com"
  },
  "metadata": {
    "ip": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  }
}
```

### 2. SMTP Email Channel
Send email notifications to users on important account events.

**Use cases:**
- Login notifications
- Password change confirmations
- Account lockout alerts
- 2FA codes (if implemented)

**Features:**
- HTML and plain text email
- Custom templates per event type
- Multiple recipients

### 3. Telegram Channel
Send instant alerts to admin Telegram chat for critical events.

**Use cases:**
- Real-time security alerts
- Failed login attempts monitoring
- New user registrations
- System health notifications

**Features:**
- Markdown formatting
- Instant delivery
- Mobile notifications

### 4. RabbitMQ Channel
Publish events to message queue for microservices integration.

**Use cases:**
- Microservices event sourcing
- Async processing workflows
- Decoupled system integration
- Event replay and auditing

**Features:**
- Topic-based routing
- Persistent messages
- High throughput

## Installation

### 1. Install Dependencies

```bash
cd examples/notifications
pip install -r requirements.txt

# Or with uv (recommended)
uv sync
```

### 2. Setup MongoDB

Make sure MongoDB is running:
```bash
# Using Docker
docker run -d -p 27017:27017 --name mongo mongo:latest

# Or use your existing MongoDB instance
```

### 3. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Required
MONGO_URL=mongodb://localhost:27017
SECRET_KEY=your-super-secret-key-change-this

# Webhook (Optional)
WEBHOOK_URL=https://webhook.site/your-unique-url
WEBHOOK_TOKEN=your-webhook-auth-token

# SMTP Email (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
FROM_EMAIL=noreply@yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com

# Telegram (Optional)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=your-chat-id

# RabbitMQ (Optional)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

### 4. Start the Server

```bash
python main.py

# Or with uvicorn
uvicorn main:app --reload
```

The server will start on `http://localhost:8000`

## Usage

### Check Notification Status

```bash
curl http://localhost:8000/notifications/status
```

Response:
```json
{
  "enabled": true,
  "active_channels": ["WebhookChannel", "SMTPChannel", "TelegramChannel"],
  "total_channels": 3
}
```

### Register a User (Triggers `user.created`)

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "role": "user"
  }'
```

This will trigger:
- ✅ Telegram alert with new user info
- ✅ Webhook POST with full event data
- ✅ RabbitMQ message published

### Login (Triggers `user.login`)

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type": application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

This will trigger:
- ✅ Email notification to user
- ✅ Webhook POST
- ✅ RabbitMQ message

### Change Password (Triggers `user.password_changed`)

```bash
curl -X POST "http://localhost:8000/auth/change-password" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "SecurePass123!",
    "new_password": "NewSecurePass456!"
  }'
```

This will trigger:
- ✅ Email confirmation to user
- ✅ Webhook POST
- ✅ RabbitMQ message

### Failed Login (Triggers `user.login_failed` and `user.locked`)

Try logging in with wrong password 5 times:

```bash
for i in {1..5}; do
  curl -X POST "http://localhost:8000/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "user@example.com", "password": "WrongPassword"}'
done
```

This will trigger:
- ⚠️ Telegram alerts for each failed attempt
- 🔒 Email alert when account is locked
- ✅ Webhook POSTs for all events

## Customizing Notifications

### Add a New Channel

```python
from outlabs_auth.services.channels.sendgrid import SendGridChannel

# In create_notification_service()
sendgrid = SendGridChannel(
    api_key=os.getenv("SENDGRID_API_KEY"),
    from_email="noreply@yourdomain.com",
    to_emails=["user@example.com"],
    email_content_builder=build_email_notification,
    enabled=True
)
channels.append(sendgrid)
```

### Customize Email Templates

Edit the `build_email_notification()` function in `main.py`:

```python
async def build_email_notification(event: Dict[str, Any]) -> Dict[str, str]:
    if event["type"] == "user.login":
        return {
            "subject": "🔐 New Login Alert",
            "plain_text": "Custom plain text...",
            "html": "<h1>Custom HTML...</h1>"
        }
    # Add more event types...
```

### Filter Events Per Channel

```python
# Only send critical events to Telegram
telegram = TelegramChannel(
    bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    message_builder=build_telegram_alert,
    enabled=True,
    event_filter=["user.locked", "user.login_failed"]  # Only these events
)
```

### Create Custom Channel

```python
from outlabs_auth.services.channels.base import NotificationChannel

class SlackChannel(NotificationChannel):
    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url
    
    async def send(self, event: Dict[str, Any]) -> None:
        # Implement Slack-specific logic
        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json={
                "text": f"Event: {event['type']}",
                "attachments": [{"text": str(event['data'])}]
            })
```

## Event Types

The notification system emits these events:

### Auth Events
- `user.login` - Successful login
- `user.login_failed` - Failed login attempt
- `user.locked` - Account locked after too many failed attempts
- `user.logout` - User logged out

### User Events
- `user.created` - New user registered
- `user.password_changed` - Password updated
- `user.status_changed` - User status changed (active/inactive/suspended)
- `user.deleted` - User account deleted

## Testing Channels

### Webhook Testing

Use [webhook.site](https://webhook.site) for quick testing:
1. Go to webhook.site
2. Copy your unique URL
3. Set `WEBHOOK_URL=https://webhook.site/your-unique-url`
4. Trigger events and see real-time payloads

### SMTP Testing

Use Gmail with an App Password:
1. Enable 2FA on your Google account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the app password in `SMTP_PASS`

Or use a service like [Mailtrap](https://mailtrap.io) for testing.

### Telegram Testing

1. Create a bot with [@BotFather](https://t.me/BotFather)
2. Get your bot token
3. Send a message to your bot
4. Get your chat ID: `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`

### RabbitMQ Testing

Run RabbitMQ with Docker:
```bash
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

Access management UI: http://localhost:15672 (guest/guest)

## Production Considerations

### Security
- ✅ Use strong `SECRET_KEY`
- ✅ Store credentials in environment variables or secrets manager
- ✅ Use HTTPS for webhooks
- ✅ Validate webhook signatures (if applicable)
- ✅ Rate limit notification endpoints

### Reliability
- ✅ Fire-and-forget: Notifications never block auth operations
- ✅ Error handling: Failed notifications are logged but don't crash
- ✅ Async: All channels use async I/O
- ✅ Retries: Consider adding retry logic for critical notifications

### Scalability
- ✅ Use RabbitMQ for high-volume events
- ✅ Batch email notifications if sending many
- ✅ Consider using a dedicated notification service (AWS SNS, Twilio, etc.)
- ✅ Monitor notification queue sizes

### Monitoring
- ✅ Track notification delivery rates
- ✅ Log failed notifications
- ✅ Alert on channel failures
- ✅ Monitor queue depths (RabbitMQ)

## Troubleshooting

### No notifications being sent

Check:
1. Environment variables are set correctly
2. Notification service is enabled: `enable_notifications=True`
3. Channels are configured and enabled
4. Check server logs for errors

### Email not sending

- Verify SMTP credentials
- Check if Gmail/provider blocks "less secure apps"
- Use app-specific passwords for Gmail
- Check spam folder
- Verify firewall allows SMTP traffic

### Telegram not working

- Verify bot token is correct
- Ensure you've sent at least one message to the bot
- Check chat ID is correct (should be a number)
- Bot must be added to group (if using group chat)

### RabbitMQ connection fails

- Ensure RabbitMQ is running
- Check connection URL format
- Verify network access to RabbitMQ port (5672)
- Check RabbitMQ logs

## API Documentation

Once running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

## Learn More

- [OutlabsAuth Documentation](https://github.com/outlabs/outlabs-auth)
- [Notification System Architecture](../../docs/NOTIFICATIONS.md)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/tutorials)

## License

This example is part of the OutlabsAuth project and is provided as-is for educational purposes.
