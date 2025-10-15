"""
Quick test to verify the notification example can initialize properly.
"""
import asyncio
import os
import sys

# Set minimal environment variables for testing
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ["MONGO_DB"] = "outlabs_auth_notifications_test"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

# Import the notification service creation function
sys.path.insert(0, os.path.dirname(__file__))
from main import create_notification_service


async def test_notification_service():
    """Test that notification service can be created."""
    print("Testing notification service creation...")
    
    try:
        # Create notification service (should work even without any channels configured)
        notification_service = create_notification_service()
        
        print(f"✅ NotificationService created successfully")
        print(f"   Enabled: {notification_service.enabled}")
        print(f"   Total channels: {len(notification_service.channels)}")
        print(f"   Active channels: {notification_service.active_channels}")
        
        # Test emitting an event (should not fail)
        print("\nTesting event emission...")
        await notification_service.emit(
            "test.event",
            data={"message": "Hello from test"},
            metadata={"test": True}
        )
        print("✅ Event emission successful (fire-and-forget)")
        
        # Give time for async tasks
        await asyncio.sleep(0.2)
        
        print("\n✅ All tests passed! Notification system works.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_channel_imports():
    """Test that all channel modules can be imported."""
    print("\nTesting channel imports...")
    
    try:
        from outlabs_auth.services.notification import NotificationService
        print("✅ NotificationService imported")
        
        from outlabs_auth.services.channels.base import NotificationChannel
        print("✅ NotificationChannel base imported")
        
        from outlabs_auth.services.channels.webhook import WebhookChannel
        print("✅ WebhookChannel imported")
        
        # Try importing optional channels (may fail if dependencies not installed)
        try:
            from outlabs_auth.services.channels.smtp import SMTPChannel
            print("✅ SMTPChannel imported")
        except ImportError as e:
            print(f"⚠️  SMTPChannel not available: {e}")
        
        try:
            from outlabs_auth.services.channels.telegram import TelegramChannel
            print("✅ TelegramChannel imported")
        except ImportError as e:
            print(f"⚠️  TelegramChannel not available: {e}")
        
        try:
            from outlabs_auth.services.channels.rabbitmq import RabbitMQChannel
            print("✅ RabbitMQChannel imported")
        except ImportError as e:
            print(f"⚠️  RabbitMQChannel not available: {e}")
        
        try:
            from outlabs_auth.services.channels.sendgrid import SendGridChannel
            print("✅ SendGridChannel imported")
        except ImportError as e:
            print("⚠️  SendGridChannel not available: {e}")
        
        try:
            from outlabs_auth.services.channels.twilio import TwilioChannel
            print("✅ TwilioChannel imported")
        except ImportError as e:
            print(f"⚠️  TwilioChannel not available: {e}")
        
        try:
            from outlabs_auth.services.channels.whatsapp import WhatsAppChannel
            print("✅ WhatsAppChannel imported")
        except ImportError as e:
            print(f"⚠️  WhatsAppChannel not available: {e}")
        
        print("\n✅ All available channels imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Notification System Test")
    print("=" * 60)
    
    # Test imports
    imports_ok = await test_channel_imports()
    
    # Test notification service
    service_ok = await test_notification_service()
    
    print("\n" + "=" * 60)
    if imports_ok and service_ok:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
