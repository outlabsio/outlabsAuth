"""
Unit tests for NotificationService

Tests fire-and-forget behavior, channel filtering, and event enrichment.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from outlabs_auth.services.notification import NotificationService
from outlabs_auth.services.channels.base import NotificationChannel


class MockChannel(NotificationChannel):
    """Mock notification channel for testing."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent_events = []
    
    async def send(self, event):
        """Record sent events."""
        self.sent_events.append(event)
    
    def reset(self):
        """Clear sent events."""
        self.sent_events = []


class TestNotificationService:
    """Test suite for NotificationService."""
    
    @pytest.fixture
    def mock_channel(self):
        """Create a mock channel."""
        return MockChannel(enabled=True)
    
    @pytest.fixture
    def notification_service(self, mock_channel):
        """Create notification service with mock channel."""
        return NotificationService(
            enabled=True,
            channels=[mock_channel]
        )
    
    async def test_service_initialization(self):
        """Test service can be initialized."""
        service = NotificationService(enabled=True)
        assert service.enabled is True
        assert service.channels == []
    
    async def test_service_disabled(self, mock_channel):
        """Test disabled service doesn't send events."""
        service = NotificationService(enabled=False, channels=[mock_channel])
        
        await service.emit("test.event", data={"key": "value"})
        
        # Give time for any async tasks (should be none)
        await asyncio.sleep(0.1)
        
        # No events should be sent
        assert len(mock_channel.sent_events) == 0
    
    async def test_emit_basic_event(self, notification_service, mock_channel):
        """Test basic event emission."""
        await notification_service.emit(
            "user.login",
            data={"user_id": "123", "email": "user@example.com"}
        )
        
        # Give time for async task to complete
        await asyncio.sleep(0.1)
        
        # Check event was sent
        assert len(mock_channel.sent_events) == 1
        event = mock_channel.sent_events[0]
        
        assert event["type"] == "user.login"
        assert event["data"]["user_id"] == "123"
        assert event["data"]["email"] == "user@example.com"
        assert "timestamp" in event
        assert "metadata" in event
    
    async def test_emit_with_metadata(self, notification_service, mock_channel):
        """Test event emission with metadata."""
        await notification_service.emit(
            "user.login",
            data={"user_id": "123"},
            metadata={"ip": "192.168.1.1", "device": "iPhone"}
        )
        
        await asyncio.sleep(0.1)
        
        event = mock_channel.sent_events[0]
        assert event["metadata"]["ip"] == "192.168.1.1"
        assert event["metadata"]["device"] == "iPhone"
    
    async def test_emit_adds_timestamp(self, notification_service, mock_channel):
        """Test that emit adds ISO timestamp."""
        await notification_service.emit("test.event", data={})
        await asyncio.sleep(0.1)
        
        event = mock_channel.sent_events[0]
        timestamp = event["timestamp"]
        
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(timestamp)
    
    async def test_fire_and_forget_behavior(self, notification_service, mock_channel):
        """Test that emit returns immediately without waiting."""
        # Create a slow channel
        slow_channel = MockChannel(enabled=True)
        original_send = slow_channel.send
        
        async def slow_send(event):
            await asyncio.sleep(1)  # Simulate slow operation
            await original_send(event)
        
        slow_channel.send = slow_send
        
        service = NotificationService(enabled=True, channels=[slow_channel])
        
        # This should return immediately, not wait 1 second
        start = asyncio.get_event_loop().time()
        await service.emit("test.event", data={})
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should return in less than 0.1 seconds (fire-and-forget)
        assert elapsed < 0.1
    
    async def test_multiple_channels(self):
        """Test event sent to multiple channels."""
        channel1 = MockChannel(enabled=True)
        channel2 = MockChannel(enabled=True)
        channel3 = MockChannel(enabled=True)
        
        service = NotificationService(
            enabled=True,
            channels=[channel1, channel2, channel3]
        )
        
        await service.emit("test.event", data={"value": 42})
        await asyncio.sleep(0.1)
        
        # All channels should receive the event
        assert len(channel1.sent_events) == 1
        assert len(channel2.sent_events) == 1
        assert len(channel3.sent_events) == 1
        
        # All should have same content
        assert channel1.sent_events[0]["data"]["value"] == 42
        assert channel2.sent_events[0]["data"]["value"] == 42
        assert channel3.sent_events[0]["data"]["value"] == 42
    
    async def test_channel_event_filtering(self):
        """Test channels can filter events."""
        # Channel that only handles user.login
        filtered_channel = MockChannel(
            enabled=True,
            event_filter=["user.login", "user.logout"]
        )
        
        # Channel that handles all events
        all_channel = MockChannel(enabled=True, event_filter=None)
        
        service = NotificationService(
            enabled=True,
            channels=[filtered_channel, all_channel]
        )
        
        # Send user.login (both should receive)
        await service.emit("user.login", data={})
        await asyncio.sleep(0.1)
        
        assert len(filtered_channel.sent_events) == 1
        assert len(all_channel.sent_events) == 1
        
        filtered_channel.reset()
        all_channel.reset()
        
        # Send user.created (only all_channel should receive)
        await service.emit("user.created", data={})
        await asyncio.sleep(0.1)
        
        assert len(filtered_channel.sent_events) == 0
        assert len(all_channel.sent_events) == 1
    
    async def test_disabled_channel_ignored(self):
        """Test disabled channels don't receive events."""
        enabled_channel = MockChannel(enabled=True)
        disabled_channel = MockChannel(enabled=False)
        
        service = NotificationService(
            enabled=True,
            channels=[enabled_channel, disabled_channel]
        )
        
        await service.emit("test.event", data={})
        await asyncio.sleep(0.1)
        
        assert len(enabled_channel.sent_events) == 1
        assert len(disabled_channel.sent_events) == 0
    
    async def test_channel_failure_doesnt_crash(self):
        """Test that channel failures don't crash the service."""
        # Create a channel that raises an exception
        failing_channel = MockChannel(enabled=True)
        
        async def failing_send(event):
            raise Exception("Channel failed!")
        
        failing_channel.send = failing_send
        
        good_channel = MockChannel(enabled=True)
        
        service = NotificationService(
            enabled=True,
            channels=[failing_channel, good_channel]
        )
        
        # This should not raise an exception
        await service.emit("test.event", data={})
        await asyncio.sleep(0.1)
        
        # Good channel should still receive the event
        assert len(good_channel.sent_events) == 1
    
    async def test_add_channel(self, notification_service, mock_channel):
        """Test adding channels at runtime."""
        new_channel = MockChannel(enabled=True)
        notification_service.add_channel(new_channel)
        
        await notification_service.emit("test.event", data={})
        await asyncio.sleep(0.1)
        
        # Both channels should receive event
        assert len(mock_channel.sent_events) == 1
        assert len(new_channel.sent_events) == 1
    
    async def test_remove_channel(self, notification_service, mock_channel):
        """Test removing channels."""
        notification_service.remove_channel(mock_channel)
        
        await notification_service.emit("test.event", data={})
        await asyncio.sleep(0.1)
        
        # Channel should not receive event
        assert len(mock_channel.sent_events) == 0
    
    async def test_active_channels_property(self):
        """Test active_channels property."""
        enabled1 = MockChannel(enabled=True)
        enabled2 = MockChannel(enabled=True)
        disabled = MockChannel(enabled=False)
        
        service = NotificationService(
            enabled=True,
            channels=[enabled1, enabled2, disabled]
        )
        
        active = service.active_channels
        assert len(active) == 2
        assert "MockChannel" in active[0]
        assert "MockChannel" in active[1]
    
    async def test_empty_data_and_metadata(self, notification_service, mock_channel):
        """Test emit works with None data and metadata."""
        await notification_service.emit("test.event")
        await asyncio.sleep(0.1)
        
        event = mock_channel.sent_events[0]
        assert event["data"] == {}
        assert event["metadata"] == {}
    
    async def test_concurrent_emissions(self, notification_service, mock_channel):
        """Test multiple concurrent emissions."""
        # Emit multiple events concurrently
        await asyncio.gather(
            notification_service.emit("event.1", data={"id": 1}),
            notification_service.emit("event.2", data={"id": 2}),
            notification_service.emit("event.3", data={"id": 3}),
        )
        
        await asyncio.sleep(0.1)
        
        # All events should be received
        assert len(mock_channel.sent_events) == 3
        
        # Check all events were sent
        event_types = [e["type"] for e in mock_channel.sent_events]
        assert "event.1" in event_types
        assert "event.2" in event_types
        assert "event.3" in event_types
