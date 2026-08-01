"""
Notification channels package.

Provides various channels for sending auth notifications:
- RabbitMQ: Publish events to message queue
- SMTP: Send email notifications (direct SMTP)
- SendGrid: Send email notifications (via SendGrid API)
- Webhook: POST events to HTTP endpoints
- Twilio: Send SMS notifications
- Telegram: Send messages via Telegram Bot API
- WhatsApp: Send WhatsApp messages (via Twilio)
"""
from typing import Any

from outlabs_auth.services.channels.base import NotificationChannel

RabbitMQChannel: Any
SMTPChannel: Any
WebhookChannel: Any
TwilioChannel: Any
SendGridChannel: Any
TelegramChannel: Any
WhatsAppChannel: Any

# RabbitMQ channel
try:
    from outlabs_auth.services.channels.rabbitmq import RabbitMQChannel
    RABBITMQ_AVAILABLE = True
except ImportError:
    RabbitMQChannel = None
    RABBITMQ_AVAILABLE = False

# SMTP/Email channel
try:
    from outlabs_auth.services.channels.smtp import SMTPChannel
    SMTP_AVAILABLE = True
except ImportError:
    SMTPChannel = None
    SMTP_AVAILABLE = False

# Webhook channel
try:
    from outlabs_auth.services.channels.webhook import WebhookChannel
    WEBHOOK_AVAILABLE = True
except ImportError:
    WebhookChannel = None
    WEBHOOK_AVAILABLE = False

# Twilio SMS channel
try:
    from outlabs_auth.services.channels.twilio import TwilioChannel
    TWILIO_AVAILABLE = True
except ImportError:
    TwilioChannel = None
    TWILIO_AVAILABLE = False

# SendGrid email channel
try:
    from outlabs_auth.services.channels.sendgrid import SendGridChannel
    SENDGRID_AVAILABLE = True
except ImportError:
    SendGridChannel = None
    SENDGRID_AVAILABLE = False

# Telegram channel
try:
    from outlabs_auth.services.channels.telegram import TelegramChannel
    TELEGRAM_AVAILABLE = True
except ImportError:
    TelegramChannel = None
    TELEGRAM_AVAILABLE = False

# WhatsApp channel (via Twilio)
try:
    from outlabs_auth.services.channels.whatsapp import WhatsAppChannel
    WHATSAPP_AVAILABLE = True
except ImportError:
    WhatsAppChannel = None
    WHATSAPP_AVAILABLE = False

__all__ = [
    "NotificationChannel",
    "RabbitMQChannel",
    "SMTPChannel",
    "SendGridChannel",
    "WebhookChannel",
    "TwilioChannel",
    "TelegramChannel",
    "WhatsAppChannel",
]
