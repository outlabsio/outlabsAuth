"""
Unit tests for email notification channels (SMTP and SendGrid)

Tests email content building, filtering, and error handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from outlabs_auth.services.channels.smtp import SMTPChannel
from outlabs_auth.services.channels.sendgrid import SendGridChannel


class TestSMTPChannel:
    """Test suite for SMTPChannel."""
    
    @pytest.fixture
    def mock_smtp(self):
        """Create mock SMTP connection."""
        smtp = MagicMock()
        return smtp
    
    @pytest.fixture
    def email_builder(self):
        """Create simple email content builder."""
        async def builder(event):
            return {
                "subject": f"Event: {event['type']}",
                "plain_text": f"Event data: {event['data']}",
                "html": f"<p>Event data: {event['data']}</p>"
            }
        return builder
    
    async def test_channel_initialization(self, email_builder):
        """Test channel can be initialized."""
        channel = SMTPChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="password",
            from_email="noreply@example.com",
            to_emails=["admin@example.com"],
            email_content_builder=email_builder,
            enabled=True
        )
        assert channel.enabled is True
        assert channel.from_email == "noreply@example.com"
        assert channel.to_emails == ["admin@example.com"]
    
    async def test_channel_disabled(self, email_builder):
        """Test disabled channel doesn't send emails."""
        channel = SMTPChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="password",
            from_email="noreply@example.com",
            to_emails=["admin@example.com"],
            email_content_builder=email_builder,
            enabled=False
        )
        
        # Should not raise exception
        await channel.send({"type": "test.event", "data": {}})
    
    async def test_send_email(self, email_builder, mock_smtp):
        """Test sending an email through SMTP."""
        with patch('aiosmtplib.SMTP', return_value=mock_smtp):
            channel = SMTPChannel(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user@example.com",
                smtp_password="password",
                from_email="noreply@example.com",
                to_emails=["admin@example.com"],
                email_content_builder=email_builder,
                enabled=True
            )
            
            event = {
                "type": "user.login",
                "data": {"user_id": "123", "email": "user@example.com"},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            }
            
            await channel.send(event)
            
            # Verify SMTP send was called
            mock_smtp.send_message.assert_called_once()
    
    async def test_email_content_builder_called(self, mock_smtp):
        """Test email content builder is called with event."""
        builder_called = False
        received_event = None
        
        async def builder(event):
            nonlocal builder_called, received_event
            builder_called = True
            received_event = event
            return {
                "subject": "Test",
                "plain_text": "Test body",
                "html": "<p>Test body</p>"
            }
        
        with patch('aiosmtplib.SMTP', return_value=mock_smtp):
            channel = SMTPChannel(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user@example.com",
                smtp_password="password",
                from_email="noreply@example.com",
                to_emails=["admin@example.com"],
                email_content_builder=builder,
                enabled=True
            )
            
            event = {"type": "user.login", "data": {}, "timestamp": "2025-01-01T00:00:00Z", "metadata": {}}
            await channel.send(event)
            
            assert builder_called is True
            assert received_event == event
    
    async def test_event_filtering(self, email_builder, mock_smtp):
        """Test channel respects event filter."""
        with patch('aiosmtplib.SMTP', return_value=mock_smtp):
            channel = SMTPChannel(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user@example.com",
                smtp_password="password",
                from_email="noreply@example.com",
                to_emails=["admin@example.com"],
                email_content_builder=email_builder,
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
            
            assert mock_smtp.send_message.call_count == 1
            
            # This should be filtered out
            await channel.send({
                "type": "user.created",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Call count should still be 1
            assert mock_smtp.send_message.call_count == 1
    
    async def test_multiple_recipients(self, email_builder, mock_smtp):
        """Test sending to multiple recipients."""
        with patch('aiosmtplib.SMTP', return_value=mock_smtp):
            channel = SMTPChannel(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user@example.com",
                smtp_password="password",
                from_email="noreply@example.com",
                to_emails=["admin1@example.com", "admin2@example.com", "admin3@example.com"],
                email_content_builder=email_builder,
                enabled=True
            )
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Message should be sent once with all recipients
            mock_smtp.send_message.assert_called_once()


class TestSendGridChannel:
    """Test suite for SendGridChannel."""
    
    @pytest.fixture
    def email_builder(self):
        """Create simple email content builder."""
        async def builder(event):
            return {
                "subject": f"Event: {event['type']}",
                "plain_text": f"Event data: {event['data']}",
                "html": f"<p>Event data: {event['data']}</p>"
            }
        return builder
    
    async def test_channel_initialization(self, email_builder):
        """Test channel can be initialized."""
        channel = SendGridChannel(
            sendgrid_api_key="SG.test_api_key",
            from_email="noreply@example.com",
            to_emails=["admin@example.com"],
            email_content_builder=email_builder,
            enabled=True
        )
        assert channel.enabled is True
        assert channel.from_email == "noreply@example.com"
        assert channel.to_emails == ["admin@example.com"]
    
    async def test_channel_disabled(self, email_builder):
        """Test disabled channel doesn't send emails."""
        channel = SendGridChannel(
            sendgrid_api_key="SG.test_api_key",
            from_email="noreply@example.com",
            to_emails=["admin@example.com"],
            email_content_builder=email_builder,
            enabled=False
        )
        
        # Should not raise exception
        await channel.send({"type": "test.event", "data": {}})
    
    async def test_send_email(self, email_builder):
        """Test sending an email through SendGrid."""
        with patch('sendgrid.SendGridAPIClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            channel = SendGridChannel(
                sendgrid_api_key="SG.test_api_key",
                from_email="noreply@example.com",
                to_emails=["admin@example.com"],
                email_content_builder=email_builder,
                enabled=True
            )
            
            event = {
                "type": "user.login",
                "data": {"user_id": "123"},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            }
            
            await channel.send(event)
            
            # Verify SendGrid send was called
            mock_instance.send.assert_called_once()
    
    async def test_email_content_builder_called(self):
        """Test email content builder is called with event."""
        builder_called = False
        received_event = None
        
        async def builder(event):
            nonlocal builder_called, received_event
            builder_called = True
            received_event = event
            return {
                "subject": "Test",
                "plain_text": "Test body",
                "html": "<p>Test body</p>"
            }
        
        with patch('sendgrid.SendGridAPIClient'):
            channel = SendGridChannel(
                sendgrid_api_key="SG.test_api_key",
                from_email="noreply@example.com",
                to_emails=["admin@example.com"],
                email_content_builder=builder,
                enabled=True
            )
            
            event = {"type": "user.login", "data": {}, "timestamp": "2025-01-01T00:00:00Z", "metadata": {}}
            await channel.send(event)
            
            assert builder_called is True
            assert received_event == event
    
    async def test_event_filtering(self, email_builder):
        """Test channel respects event filter."""
        with patch('sendgrid.SendGridAPIClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            channel = SendGridChannel(
                sendgrid_api_key="SG.test_api_key",
                from_email="noreply@example.com",
                to_emails=["admin@example.com"],
                email_content_builder=email_builder,
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
            
            assert mock_instance.send.call_count == 1
            
            # This should be filtered out
            await channel.send({
                "type": "user.created",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Call count should still be 1
            assert mock_instance.send.call_count == 1
    
    async def test_from_name_and_reply_to(self, email_builder):
        """Test custom from name and reply-to email."""
        with patch('sendgrid.SendGridAPIClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            channel = SendGridChannel(
                sendgrid_api_key="SG.test_api_key",
                from_email="noreply@example.com",
                from_name="Auth System",
                reply_to_email="support@example.com",
                to_emails=["admin@example.com"],
                email_content_builder=email_builder,
                enabled=True
            )
            
            await channel.send({
                "type": "user.login",
                "data": {},
                "timestamp": "2025-01-01T00:00:00Z",
                "metadata": {}
            })
            
            # Verify send was called
            mock_instance.send.assert_called_once()
