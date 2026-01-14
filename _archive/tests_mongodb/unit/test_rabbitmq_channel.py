"""
Unit tests for RabbitMQ notification channel

Tests event publishing, filtering, and error handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from outlabs_auth.services.channels.rabbitmq import RabbitMQChannel


class TestRabbitMQChannel:
    """Test suite for RabbitMQChannel."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock RabbitMQ connection."""
        connection = AsyncMock()
        channel = AsyncMock()
        connection.channel.return_value = channel
        return connection, channel
    
    @pytest.fixture
    async def rabbitmq_channel(self, mock_connection):
        """Create RabbitMQ channel with mocked connection."""
        conn, ch = mock_connection
        
        with patch('aio_pika.connect_robust', return_value=conn):
            channel = RabbitMQChannel(
                rabbitmq_url="amqp://guest:guest@localhost:5672/",
                exchange_name="auth_events",
                enabled=True
            )
            await channel.connect()
            return channel, ch
    
    async def test_channel_initialization(self):
        """Test channel can be initialized without connection."""
        channel = RabbitMQChannel(
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            exchange_name="auth_events",
            enabled=True
        )
        assert channel.enabled is True
        assert channel.exchange_name == "auth_events"
    
    async def test_channel_disabled(self):
        """Test disabled channel doesn't send events."""
        channel = RabbitMQChannel(
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            exchange_name="auth_events",
            enabled=False
        )
        
        # Should not raise exception
        await channel.send({"type": "test.event", "data": {}})
    
    async def test_send_event(self, rabbitmq_channel):
        """Test sending an event through RabbitMQ."""
        channel, mock_ch = rabbitmq_channel
        mock_exchange = AsyncMock()
        mock_ch.get_exchange.return_value = mock_exchange
        
        event = {
            "type": "user.login",
            "data": {"user_id": "123"},
            "timestamp": "2025-01-01T00:00:00Z",
            "metadata": {}
        }
        
        await channel.send(event)
        
        # Verify exchange publish was called
        mock_exchange.publish.assert_called_once()
    
    async def test_event_filtering(self, rabbitmq_channel):
        """Test channel respects event filter."""
        channel, mock_ch = rabbitmq_channel
        channel.event_filter = ["user.login", "user.logout"]
        
        mock_exchange = AsyncMock()
        mock_ch.get_exchange.return_value = mock_exchange
        
        # This should be sent
        await channel.send({
            "type": "user.login",
            "data": {},
            "timestamp": "2025-01-01T00:00:00Z",
            "metadata": {}
        })
        
        assert mock_exchange.publish.call_count == 1
        
        # This should be filtered out
        await channel.send({
            "type": "user.created",
            "data": {},
            "timestamp": "2025-01-01T00:00:00Z",
            "metadata": {}
        })
        
        # Call count should still be 1
        assert mock_exchange.publish.call_count == 1
    
    async def test_connect_creates_exchange(self, mock_connection):
        """Test connect creates the exchange."""
        conn, mock_ch = mock_connection
        
        with patch('aio_pika.connect_robust', return_value=conn):
            channel = RabbitMQChannel(
                rabbitmq_url="amqp://guest:guest@localhost:5672/",
                exchange_name="auth_events",
                enabled=True
            )
            await channel.connect()
            
            # Verify channel and exchange declaration
            conn.channel.assert_called_once()
            mock_ch.declare_exchange.assert_called_once()
    
    async def test_disconnect(self, rabbitmq_channel):
        """Test disconnect closes connection."""
        channel, _ = rabbitmq_channel
        
        await channel.disconnect()
        
        # Verify connection was closed
        assert channel.connection is None
        assert channel.channel is None
    
    async def test_send_without_connection_fails_silently(self):
        """Test send without connection doesn't raise exception."""
        channel = RabbitMQChannel(
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            exchange_name="auth_events",
            enabled=True
        )
        
        # Should not raise exception (fire-and-forget)
        await channel.send({
            "type": "test.event",
            "data": {},
            "timestamp": "2025-01-01T00:00:00Z",
            "metadata": {}
        })
    
    async def test_routing_key_from_event_type(self, rabbitmq_channel):
        """Test routing key is derived from event type."""
        channel, mock_ch = rabbitmq_channel
        mock_exchange = AsyncMock()
        mock_ch.get_exchange.return_value = mock_exchange
        
        await channel.send({
            "type": "user.login",
            "data": {},
            "timestamp": "2025-01-01T00:00:00Z",
            "metadata": {}
        })
        
        # Check routing key matches event type
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]
        routing_key = call_args[1]['routing_key']
        
        assert routing_key == "user.login"
    
    async def test_custom_routing_key(self, mock_connection):
        """Test custom routing key configuration."""
        conn, mock_ch = mock_connection
        
        with patch('aio_pika.connect_robust', return_value=conn):
            channel = RabbitMQChannel(
                rabbitmq_url="amqp://guest:guest@localhost:5672/",
                exchange_name="auth_events",
                routing_key="custom.key",
                enabled=True
            )
            await channel.connect()
            
            mock_exchange = AsyncMock()
            mock_ch.get_exchange.return_value = mock_exchange
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Check routing key is custom
            call_args = mock_exchange.publish.call_args
            routing_key = call_args[1]['routing_key']
            assert routing_key == "custom.key"
