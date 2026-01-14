"""
Unit tests for webhook and messaging channels

Tests Webhook, Telegram, Twilio SMS, and WhatsApp channels.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from outlabs_auth.services.channels.webhook import WebhookChannel
from outlabs_auth.services.channels.telegram import TelegramChannel
from outlabs_auth.services.channels.twilio import TwilioChannel
from outlabs_auth.services.channels.whatsapp import WhatsAppChannel


class TestWebhookChannel:
    """Test suite for WebhookChannel."""
    
    async def test_channel_initialization(self):
        """Test channel can be initialized."""
        channel = WebhookChannel(
            webhook_url="https://example.com/webhook",
            enabled=True
        )
        assert channel.enabled is True
        assert channel.webhook_url == "https://example.com/webhook"
    
    async def test_channel_disabled(self):
        """Test disabled channel doesn't send webhooks."""
        channel = WebhookChannel(
            webhook_url="https://example.com/webhook",
            enabled=False
        )
        
        # Should not raise exception
        await channel.send({"type": "test.event", "data": {}})
    
    async def test_send_webhook(self):
        """Test sending a webhook."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            channel = WebhookChannel(
                webhook_url="https://example.com/webhook",
                enabled=True
            )
            
            event = {
                "type": "user.login",
                "data": {"user_id": "123"},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            }
            
            await channel.send(event)
            
            # Verify POST was called
            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert call_args[0][0] == "https://example.com/webhook"
    
    async def test_custom_headers(self):
        """Test webhook with custom headers."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            channel = WebhookChannel(
                webhook_url="https://example.com/webhook",
                headers={"Authorization": "Bearer token123", "X-Custom": "value"},
                enabled=True
            )
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Verify headers were passed
            call_args = mock_instance.post.call_args
            headers = call_args[1]['headers']
            assert headers["Authorization"] == "Bearer token123"
            assert headers["X-Custom"] == "value"
    
    async def test_event_filtering(self):
        """Test channel respects event filter."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            channel = WebhookChannel(
                webhook_url="https://example.com/webhook",
                event_filter=["user.login"],
                enabled=True
            )
            
            # This should be sent
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            assert mock_instance.post.call_count == 1
            
            # This should be filtered out
            await channel.send({
                "type": "user.created",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Call count should still be 1
            assert mock_instance.post.call_count == 1


class TestTelegramChannel:
    """Test suite for TelegramChannel."""
    
    @pytest.fixture
    def message_builder(self):
        """Create simple message builder."""
        async def builder(event):
            return f"Event: {event['type']}"
        return builder
    
    async def test_channel_initialization(self, message_builder):
        """Test channel can be initialized."""
        channel = TelegramChannel(
            bot_token="123456:ABC-DEF",
            chat_ids=["123456789"],
            message_builder=message_builder,
            enabled=True
        )
        assert channel.enabled is True
        assert channel.bot_token == "123456:ABC-DEF"
        assert channel.chat_ids == ["123456789"]
    
    async def test_channel_disabled(self, message_builder):
        """Test disabled channel doesn't send messages."""
        channel = TelegramChannel(
            bot_token="123456:ABC-DEF",
            chat_ids=["123456789"],
            message_builder=message_builder,
            enabled=False
        )
        
        # Should not raise exception
        await channel.send({"type": "test.event", "data": {}})
    
    async def test_send_message(self, message_builder):
        """Test sending a Telegram message."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            channel = TelegramChannel(
                bot_token="123456:ABC-DEF",
                chat_ids=["123456789"],
                message_builder=message_builder,
                enabled=True
            )
            
            event = {
                "type": "user.login",
                "data": {"user_id": "123"},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            }
            
            await channel.send(event)
            
            # Verify POST was called
            mock_instance.post.assert_called_once()
    
    async def test_message_builder_called(self):
        """Test message builder is called with event."""
        builder_called = False
        received_event = None
        
        async def builder(event):
            nonlocal builder_called, received_event
            builder_called = True
            received_event = event
            return "Test message"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            channel = TelegramChannel(
                bot_token="123456:ABC-DEF",
                chat_ids=["123456789"],
                message_builder=builder,
                enabled=True
            )
            
            event = {"type": "user.login", "data": {}, "timestamp": "2025-01-01T00:00:00Z", "metadata": {}}
            await channel.send(event)
            
            assert builder_called is True
            assert received_event == event
    
    async def test_multiple_chat_ids(self, message_builder):
        """Test sending to multiple chat IDs."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            channel = TelegramChannel(
                bot_token="123456:ABC-DEF",
                chat_ids=["123456789", "987654321", "111222333"],
                message_builder=message_builder,
                enabled=True
            )
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Should be called 3 times (once per chat)
            assert mock_instance.post.call_count == 3


class TestTwilioChannel:
    """Test suite for TwilioChannel."""
    
    @pytest.fixture
    def sms_builder(self):
        """Create simple SMS builder."""
        async def builder(event):
            return {
                "to": "+0987654321",
                "body": f"Event: {event['type']}"
            }
        return builder
    
    async def test_channel_initialization(self, sms_builder):
        """Test channel can be initialized."""
        channel = TwilioChannel(
            account_sid="ACxxxx",
            auth_token="token",
            from_number="+1234567890",
            sms_builder=sms_builder,
            enabled=True
        )
        assert channel.enabled is True
        assert channel.account_sid == "ACxxxx"
        assert channel.from_number == "+1234567890"
    
    async def test_channel_disabled(self, sms_builder):
        """Test disabled channel doesn't send SMS."""
        channel = TwilioChannel(
            account_sid="ACxxxx",
            auth_token="token",
            from_number="+1234567890",
            sms_builder=sms_builder,
            enabled=False
        )
        
        # Should not raise exception
        await channel.send({"type": "test.event", "data": {}})
    
    async def test_send_sms(self, sms_builder):
        """Test sending an SMS via Twilio."""
        with patch('twilio.rest.Client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            channel = TwilioChannel(
                account_sid="ACxxxx",
                auth_token="token",
                from_number="+1234567890",
                sms_builder=sms_builder,
                enabled=True
            )
            
            event = {
                "type": "user.login",
                "data": {"user_id": "123"},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            }
            
            await channel.send(event)
            
            # Verify SMS was sent
            mock_instance.messages.create.assert_called_once()
            call_args = mock_instance.messages.create.call_args
            assert call_args[1]['to'] == "+0987654321"
            assert call_args[1]['from_'] == "+1234567890"
    
    async def test_builder_returns_none(self):
        """Test that no SMS is sent when builder returns None."""
        async def builder(event):
            return None  # Don't send SMS
        
        with patch('twilio.rest.Client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            channel = TwilioChannel(
                account_sid="ACxxxx",
                auth_token="token",
                from_number="+1234567890",
                sms_builder=builder,
                enabled=True
            )
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Should not be called
            mock_instance.messages.create.assert_not_called()


class TestWhatsAppChannel:
    """Test suite for WhatsAppChannel."""
    
    @pytest.fixture
    def message_builder(self):
        """Create simple message builder."""
        async def builder(event):
            return {
                "to": "+0987654321",
                "body": f"Event: {event['type']}"
            }
        return builder
    
    async def test_channel_initialization(self, message_builder):
        """Test channel can be initialized."""
        channel = WhatsAppChannel(
            account_sid="ACxxxx",
            auth_token="token",
            from_number="whatsapp:+1234567890",
            message_builder=message_builder,
            enabled=True
        )
        assert channel.enabled is True
        assert channel.from_number == "whatsapp:+1234567890"
    
    async def test_channel_disabled(self, message_builder):
        """Test disabled channel doesn't send WhatsApp messages."""
        channel = WhatsAppChannel(
            account_sid="ACxxxx",
            auth_token="token",
            from_number="whatsapp:+1234567890",
            message_builder=message_builder,
            enabled=False
        )
        
        # Should not raise exception
        await channel.send({"type": "test.event", "data": {}})
    
    async def test_send_whatsapp(self, message_builder):
        """Test sending a WhatsApp message via Twilio."""
        with patch('twilio.rest.Client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            channel = WhatsAppChannel(
                account_sid="ACxxxx",
                auth_token="token",
                from_number="whatsapp:+1234567890",
                message_builder=message_builder,
                enabled=True
            )
            
            event = {
                "type": "user.login",
                "data": {"user_id": "123"},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            }
            
            await channel.send(event)
            
            # Verify WhatsApp message was sent
            mock_instance.messages.create.assert_called_once()
            
            # Verify it's using WhatsApp numbers
            call_args = mock_instance.messages.create.call_args
            assert call_args[1]['from_'] == "whatsapp:+1234567890"
            assert call_args[1]['to'] == "whatsapp:+0987654321"
    
    async def test_whatsapp_prefix_added_to_numbers(self):
        """Test that whatsapp: prefix is added to numbers without it."""
        async def builder(event):
            return {
                "to": "+0987654321",  # No whatsapp: prefix
                "body": "Test message"
            }
        
        with patch('twilio.rest.Client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            # Initialize with number without prefix
            channel = WhatsAppChannel(
                account_sid="ACxxxx",
                auth_token="token",
                from_number="+1234567890",  # No prefix
                message_builder=builder,
                enabled=True
            )
            
            # Should have added prefix
            assert channel.from_number == "whatsapp:+1234567890"
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Verify prefix was added to 'to' number as well
            call_args = mock_instance.messages.create.call_args
            assert call_args[1]['to'] == "whatsapp:+0987654321"
    
    async def test_builder_returns_none(self):
        """Test that no message is sent when builder returns None."""
        async def builder(event):
            return None  # Don't send message
        
        with patch('twilio.rest.Client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            channel = WhatsAppChannel(
                account_sid="ACxxxx",
                auth_token="token",
                from_number="whatsapp:+1234567890",
                message_builder=builder,
                enabled=True
            )
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Should not be called
            mock_instance.messages.create.assert_not_called()
