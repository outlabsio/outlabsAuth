"""
Telegram Notification Channel

Sends notifications for auth events via Telegram Bot API.
Popular for international users and developer communities.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

from outlabs_auth.services.channels.base import NotificationChannel


# Type alias for message builder callback
MessageBuilder = Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, str]]]]


class TelegramChannel(NotificationChannel):
    """
    Telegram notification channel for auth events.
    
    Sends messages via Telegram Bot API. Great for security notifications,
    2FA codes, and alerts for international users.
    
    Features:
    - Telegram Bot API
    - User-provided message builder callback
    - Markdown or HTML formatting support
    - Event filtering
    - Async-friendly
    
    Setup:
    1. Create bot via @BotFather on Telegram
    2. Get bot token
    3. Users must start conversation with bot first
    4. Store user's chat_id in your database
    
    Common Use Cases:
    - Security alerts
    - 2FA codes
    - Account activity notifications
    - Critical system alerts
    
    Example:
        >>> from outlabs_auth.services.channels.telegram import TelegramChannel
        >>> 
        >>> # Define message builder callback
        >>> async def build_message(event):
        ...     if event["type"] == "user.login":
        ...         # Get user's Telegram chat_id from your database
        ...         chat_id = await get_user_telegram_chat_id(event["data"]["user_id"])
        ...         if not chat_id:
        ...             return None
        ...         
        ...         return {
        ...             "chat_id": chat_id,
        ...             "text": f"🔐 New login detected from {event['metadata'].get('ip', 'unknown')}",
        ...             "parse_mode": "Markdown"  # or "HTML"
        ...         }
        ...     return None
        >>> 
        >>> # Create channel
        >>> telegram = TelegramChannel(
        ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        ...     message_builder=build_message,
        ...     event_filter=["user.login", "user.locked", "security.threat_detected"]
        ... )
        >>> 
        >>> # Events are automatically sent
        >>> await telegram.send({
        ...     "type": "user.login",
        ...     "data": {"user_id": "123"},
        ...     "metadata": {"ip": "192.168.1.1"}
        ... })
    """
    
    def __init__(
        self,
        bot_token: str,
        enabled: bool = True,
        event_filter: Optional[List[str]] = None,
        message_builder: Optional[MessageBuilder] = None
    ):
        """
        Initialize Telegram channel.
        
        Args:
            bot_token: Telegram bot token (from @BotFather)
            enabled: Whether this channel is enabled
            event_filter: Optional list of event types to handle
            message_builder: Async callback to build message content from event
        
        Raises:
            ImportError: If python-telegram-bot is not installed
        """
        super().__init__(enabled, event_filter)
        
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot is required for Telegram support. "
                "Install with: pip install outlabs-auth[notifications] "
                "or: pip install python-telegram-bot"
            )
        
        self.bot_token = bot_token
        self.message_builder = message_builder
        
        # Create Telegram bot
        self.bot = Bot(token=bot_token)
    
    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send Telegram notification.
        
        Args:
            event: Event dictionary with type, timestamp, data, metadata
        
        Note:
            If message_builder returns None, no message is sent.
            Failures are silently ignored.
            
            The message_builder should return:
            {
                "chat_id": str or int (Telegram chat ID),
                "text": str (message text),
                "parse_mode": Optional[str] ("Markdown" or "HTML")
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
            
            # Send message via Telegram
            await self.bot.send_message(
                chat_id=message_data["chat_id"],
                text=message_data["text"],
                parse_mode=message_data.get("parse_mode")
            )
            
        except TelegramError:
            # Telegram-specific errors (invalid chat_id, blocked bot, etc.)
            # Fail silently - notifications should never break auth
            pass
        except Exception:
            # Any other errors
            # Fail silently - notifications should never break auth
            pass
    
    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        return f"<TelegramChannel: {status}, bot_token=***{self.bot_token[-6:] if self.bot_token else 'None'}>"
