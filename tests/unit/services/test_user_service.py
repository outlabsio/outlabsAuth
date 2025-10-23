"""Tests for UserService lifecycle hooks (DD-040)."""

import pytest
from outlabs_auth.services.user_service import UserService


class TestUserServiceHooks:
    """Test UserService lifecycle hooks."""

    def test_user_service_has_hooks(self):
        """Test that UserService has all expected lifecycle hooks."""
        service = UserService(database=None)

        # Verify all hooks exist and are callable
        assert hasattr(service, "on_after_register")
        assert callable(service.on_after_register)

        assert hasattr(service, "on_after_login")
        assert callable(service.on_after_login)

        assert hasattr(service, "on_after_update")
        assert callable(service.on_after_update)

        assert hasattr(service, "on_before_delete")
        assert callable(service.on_before_delete)

        assert hasattr(service, "on_after_delete")
        assert callable(service.on_after_delete)

        assert hasattr(service, "on_after_request_verify")
        assert callable(service.on_after_request_verify)

        assert hasattr(service, "on_after_verify")
        assert callable(service.on_after_verify)

        assert hasattr(service, "on_after_forgot_password")
        assert callable(service.on_after_forgot_password)

        assert hasattr(service, "on_after_reset_password")
        assert callable(service.on_after_reset_password)

        assert hasattr(service, "on_failed_login")
        assert callable(service.on_failed_login)

    @pytest.mark.asyncio
    async def test_custom_hook_override(self):
        """Test that hooks can be overridden in subclasses."""
        called = []

        class CustomUserService(UserService):
            async def on_after_register(self, user, request=None):
                called.append("on_after_register")

            async def on_after_login(self, user, request=None):
                called.append("on_after_login")

        service = CustomUserService(database=None)

        # Call hooks
        await service.on_after_register(user=None)
        await service.on_after_login(user=None)

        assert "on_after_register" in called
        assert "on_after_login" in called
