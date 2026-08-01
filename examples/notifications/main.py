"""
OutlabsAuth Notifications Example

Demonstrates how to use the notification system with multiple channels:
- Webhook (for logging/monitoring)
- SMTP Email (for user notifications)
- Telegram (for admin alerts)
- RabbitMQ (for microservices integration)

Uses PostgreSQL for database storage.

This example shows:
1. Setting up multiple notification channels
2. Creating custom message builders
3. Filtering events per channel
4. Integration with FastAPI auth system
"""
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from sqlmodel import SQLModel

from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.notification import NotificationService
from outlabs_auth.services.channels.webhook import WebhookChannel
from outlabs_auth.services.channels.smtp import SMTPChannel
from outlabs_auth.services.channels.telegram import TelegramChannel
from outlabs_auth.services.channels.rabbitmq import RabbitMQChannel


# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_notifications"
)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================

async def build_email_notification(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Build email content for auth events.

    This is called for each event. Return None to skip sending.
    Returns dict with: to, subject, body, html (optional)
    """
    event_type = event["type"]
    data = event["data"]

    # Get recipient email (from event data or configured admin)
    to_email = data.get('email') or os.getenv("ADMIN_EMAIL", "admin@example.com")

    # Map events to email content
    if event_type == "user.login":
        return {
            "to": to_email,
            "subject": "New Login Detected",
            "body": f"A new login was detected for {data.get('email', 'your account')}.\n\n"
                   f"Time: {event['timestamp']}\n"
                   f"IP: {event['metadata'].get('ip', 'Unknown')}",
            "html": f"<h2>New Login Detected</h2>"
                   f"<p>A new login was detected for <strong>{data.get('email', 'your account')}</strong>.</p>"
                   f"<ul><li>Time: {event['timestamp']}</li>"
                   f"<li>IP: {event['metadata'].get('ip', 'Unknown')}</li></ul>"
        }
    elif event_type == "user.locked":
        return {
            "to": to_email,
            "subject": "Account Locked - Security Alert",
            "body": f"Your account ({data.get('email')}) has been locked due to multiple failed login attempts.\n\n"
                   f"If this wasn't you, please contact support immediately.\n"
                   f"Time: {event['timestamp']}",
            "html": f"<h2 style='color: red;'>Account Locked</h2>"
                   f"<p>Your account (<strong>{data.get('email')}</strong>) has been locked due to multiple failed login attempts.</p>"
                   f"<p>If this wasn't you, please <a href='mailto:support@example.com'>contact support</a> immediately.</p>"
                   f"<p><small>Time: {event['timestamp']}</small></p>"
        }
    elif event_type == "user.password_changed":
        return {
            "to": to_email,
            "subject": "Password Changed Successfully",
            "body": f"Your password has been changed successfully.\n\n"
                   f"Time: {event['timestamp']}\n\n"
                   f"If you didn't make this change, please contact support immediately.",
            "html": f"<h2>Password Changed</h2>"
                   f"<p>Your password has been changed successfully.</p>"
                   f"<p><small>Time: {event['timestamp']}</small></p>"
                   f"<p><em>If you didn't make this change, please contact support immediately.</em></p>"
        }

    return None


async def build_telegram_alert(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Build Telegram message for admin alerts.

    Short, formatted messages for critical events.
    Returns dict with: chat_id, text, parse_mode (optional)
    """
    event_type = event["type"]
    data = event["data"]

    # Get chat ID from environment
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        return None

    text = None
    if event_type == "user.locked":
        text = f"*Account Locked*\n" \
               f"User: {data.get('email')}\n" \
               f"Reason: Too many failed attempts"
    elif event_type == "user.login_failed":
        text = f"*Login Failed*\n" \
               f"Email: {data.get('email')}\n" \
               f"Attempts: {data.get('failed_attempts')}\n" \
               f"IP: {event['metadata'].get('ip', 'Unknown')}"
    elif event_type == "user.created":
        text = f"*New User*\n" \
               f"Email: {data.get('email')}\n" \
               f"Role: {data.get('role', 'user')}"

    if not text:
        return None

    return {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }


# ============================================================================
# NOTIFICATION SETUP
# ============================================================================

def create_notification_service() -> NotificationService:
    """
    Create and configure notification service with multiple channels.

    Environment variables:
    - WEBHOOK_URL: Your webhook endpoint
    - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS: Email config
    - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID: Telegram config
    - RABBITMQ_URL: RabbitMQ connection string
    """
    channels = []

    # 1. Webhook Channel - Log all events to external service
    if webhook_url := os.getenv("WEBHOOK_URL"):
        webhook = WebhookChannel(
            url=webhook_url,
            headers={
                "Authorization": f"Bearer {os.getenv('WEBHOOK_TOKEN', '')}",
                "Content-Type": "application/json"
            },
            enabled=True,
            event_filter=None  # All events
        )
        channels.append(webhook)
        print("Webhook channel enabled")

    # 2. SMTP Email Channel - User notifications
    if os.getenv("SMTP_HOST"):
        smtp = SMTPChannel(
            host=os.getenv("SMTP_HOST"),
            port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER"),
            password=os.getenv("SMTP_PASS"),
            use_tls=True,
            from_email=os.getenv("FROM_EMAIL", "noreply@example.com"),
            from_name="Auth System",
            email_builder=build_email_notification,
            enabled=True,
            event_filter=["user.login", "user.locked", "user.password_changed"]
        )
        channels.append(smtp)
        print("SMTP email channel enabled")

    # 3. Telegram Channel - Admin alerts
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        telegram = TelegramChannel(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            message_builder=build_telegram_alert,
            enabled=True,
            event_filter=["user.locked", "user.login_failed", "user.created"]
        )
        channels.append(telegram)
        print("Telegram channel enabled")

    # 4. RabbitMQ Channel - Microservices integration
    if os.getenv("RABBITMQ_URL"):
        rabbitmq = RabbitMQChannel(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="auth_events",
            routing_key="auth.events",
            enabled=True,
            event_filter=None  # All events for microservices
        )
        channels.append(rabbitmq)
        print("RabbitMQ channel enabled")

    if not channels:
        print("No notification channels configured. Set environment variables to enable.")

    return NotificationService(enabled=True, channels=channels)


# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

auth: Optional[SimpleRBAC] = None
notification_service: Optional[NotificationService] = None


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global auth, notification_service

    # Startup
    print("Starting OutlabsAuth Notifications Example...")

    # Create notification service
    notification_service = create_notification_service()

    # Initialize OutlabsAuth with notifications
    auth = SimpleRBAC(
        database_url=DATABASE_URL,
        secret_key=SECRET_KEY,
        notification_service=notification_service,
        enable_notifications=True
    )

    await auth.initialize()

    # Create tables
    print("Creating database tables...")
    async with auth.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("Database tables created")

    # Connect RabbitMQ channels if present
    for channel in notification_service.channels:
        if isinstance(channel, RabbitMQChannel):
            await channel.connect()

    print(f"\nServer started with {len(notification_service.active_channels)} notification channels")
    print(f"Active channels: {', '.join(notification_service.active_channels)}\n")

    yield

    # Shutdown
    print("Shutting down...")
    for channel in notification_service.channels:
        if isinstance(channel, RabbitMQChannel):
            await channel.close()
    await auth.shutdown()
    print("Shutdown complete")


app = FastAPI(
    title="OutlabsAuth Notifications Example",
    description="Demonstrates notification channels with PostgreSQL storage",
    version="1.0.0",
    lifespan=lifespan,
)


def get_auth() -> SimpleRBAC:
    """Get the global auth instance."""
    if auth is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return auth


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.post("/auth/register")
async def register(email: str, password: str, role: str = "user"):
    """
    Register new user.

    Triggers: user.created notification
    """
    try:
        user = await get_auth().user_service.create_user(
            email=email,
            password=password,
            role_names=[role]
        )
        return {
            "user_id": str(user.id),
            "email": user.email,
            "message": "User created. Check your email/Telegram for notification!"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login")
async def login(email: str, password: str):
    """
    Login user.

    Triggers: user.login or user.login_failed notification
    """
    try:
        result = await get_auth().auth_service.login(
            email=email,
            password=password,
            metadata={"ip": "127.0.0.1", "user_agent": "Example"}
        )
        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "message": "Login successful. Check your email for notification!"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@app.post("/auth/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    user: User = Depends(lambda: get_auth().deps.authenticated())
):
    """
    Change user password.

    Triggers: user.password_changed notification
    """
    try:
        await get_auth().user_service.change_password(
            user_id=str(user.id),
            old_password=old_password,
            new_password=new_password
        )
        return {"message": "Password changed. Check your email for confirmation!"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/me")
async def get_me(user: User = Depends(lambda: get_auth().deps.authenticated())):
    """Get current user info."""
    return {
        "id": str(user.id),
        "email": user.email,
        "status": user.status.value if hasattr(user.status, 'value') else user.status
    }


@app.get("/notifications/status")
async def notification_status():
    """Check notification system status."""
    if notification_service is None:
        raise HTTPException(status_code=500, detail="Notification service not initialized")
    return {
        "enabled": notification_service.enabled,
        "active_channels": notification_service.active_channels,
        "total_channels": len(notification_service.channels)
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "service": "OutlabsAuth Notifications Example",
        "status": "healthy",
        "version": "1.0.0",
        "preset": "SimpleRBAC",
    }


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("OutlabsAuth Notifications Example")
    print("=" * 60)
    print("\nThis example demonstrates notification channels:")
    print("  - Webhook - External logging")
    print("  - Email (SMTP) - User notifications")
    print("  - Telegram - Admin alerts")
    print("  - RabbitMQ - Microservices integration")
    print("\nConfigure via environment variables (see README.md)")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8005)
