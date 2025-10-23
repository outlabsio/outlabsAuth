"""
User service with lifecycle hooks.

Implements lifecycle hooks pattern from FastAPI-Users (DD-040).
"""

from typing import Any, Optional, Dict
from fastapi import Request
from outlabs_auth.services.base import BaseService


class UserService(BaseService):
    """
    User management service with lifecycle hooks.

    Override hook methods to add custom logic at key points in the user lifecycle.

    Available Hooks:
        - on_after_register: After successful user registration
        - on_after_login: After successful login
        - on_after_update: After user profile update
        - on_before_delete: Before user deletion (can prevent by raising exception)
        - on_after_delete: After user deletion
        - on_after_request_verify: After email verification request
        - on_after_verify: After successful email verification
        - on_after_forgot_password: After password reset request
        - on_after_reset_password: After successful password reset
        - on_failed_login: After failed login attempt

    Example:
        ```python
        class MyUserService(UserService):
            async def on_after_register(self, user, request=None):
                await email_service.send_welcome(user.email)
                logger.info(f"New user: {user.email}")

            async def on_after_login(self, user, request=None):
                await analytics.track("login", user.id)

            async def on_before_delete(self, user, request=None):
                if user.is_superuser:
                    raise ValueError("Cannot delete superuser")
        ```
    """

    def __init__(self, database: Any):
        """
        Initialize user service.

        Args:
            database: MongoDB database instance
        """
        self.database = database
        # User model will be initialized later

    # ===================================================================
    # LIFECYCLE HOOKS - Override these in your custom service
    # ===================================================================

    async def on_after_register(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after successful user registration.

        Override to:
        - Send welcome email
        - Create default profile
        - Trigger analytics event
        - Send to CRM
        - Create default entities (EnterpriseRBAC)

        Args:
            user: The newly registered user
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    async def on_after_login(
        self,
        user: Any,
        request: Optional[Request] = None,
        response: Any = None
    ) -> None:
        """
        Called after successful login.

        Override to:
        - Track last login time
        - Log security event
        - Send login notification email
        - Update analytics
        - Check for suspicious activity

        Args:
            user: The user who logged in
            request: Optional FastAPI request object
            response: Optional FastAPI response object
        """
        pass  # Default: do nothing

    async def on_after_update(
        self,
        user: Any,
        update_dict: Dict[str, Any],
        request: Optional[Request] = None
    ) -> None:
        """
        Called after user profile update.

        Override to:
        - Send profile change notification
        - Audit log changes
        - Invalidate caches
        - Sync to external systems

        Args:
            user: The updated user
            update_dict: Dictionary of fields that were updated
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    async def on_before_delete(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """
        Called before user deletion.

        Override to:
        - Prevent deletion of important users
        - Require additional confirmation
        - Check for dependencies

        Raise an exception to prevent deletion.

        Args:
            user: The user to be deleted
            request: Optional FastAPI request object

        Raises:
            Exception: To prevent deletion
        """
        pass  # Default: do nothing

    async def on_after_delete(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after user deletion.

        Override to:
        - Clean up user data
        - Send cancellation email
        - Remove from external systems
        - Log security event

        Args:
            user: The deleted user (before deletion)
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    async def on_after_request_verify(
        self,
        user: Any,
        token: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after email verification request.

        Override to:
        - Send verification email
        - Log event

        Args:
            user: The user requesting verification
            token: The verification token
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    async def on_after_verify(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after successful email verification.

        Override to:
        - Send welcome email
        - Grant verified-only permissions
        - Update status

        Args:
            user: The verified user
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    async def on_after_forgot_password(
        self,
        user: Any,
        token: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after password reset request.

        Override to:
        - Send password reset email
        - Log security event

        Args:
            user: The user requesting password reset
            token: The reset token
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    async def on_after_reset_password(
        self,
        user: Any,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after successful password reset.

        Override to:
        - Send password changed notification
        - Invalidate all sessions
        - Log security event

        Args:
            user: The user whose password was reset
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    async def on_failed_login(
        self,
        email: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after failed login attempt.

        Override to:
        - Track brute force attempts
        - Send security alert
        - Temporarily lock account
        - Log security event

        Args:
            email: The email that failed to login
            request: Optional FastAPI request object
        """
        pass  # Default: do nothing

    # ===================================================================
    # OAUTH/SOCIAL LOGIN HOOKS (v1.2, DD-043)
    # ===================================================================

    async def on_after_oauth_register(
        self,
        user: Any,
        provider: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after a new user registers via OAuth (v1.2).

        Override to:
        - Send OAuth-specific welcome email
        - Import profile data from provider
        - Create default settings
        - Track OAuth registration

        Note: This is called AFTER on_after_register, so you can
        differentiate between password-based and OAuth registration.

        Args:
            user: The newly registered user
            provider: OAuth provider name ("google", "facebook", etc.)
            request: Optional FastAPI request object

        Example:
            ```python
            async def on_after_oauth_register(self, user, provider, request=None):
                # Send OAuth-specific welcome
                await email_service.send_oauth_welcome(user.email, provider)

                # Import avatar if available
                social_account = [a for a in user.oauth_accounts if a.provider == provider][0]
                if social_account.avatar_url:
                    await profile_service.set_avatar(user.id, social_account.avatar_url)
            ```
        """
        pass  # Default: do nothing

    async def on_after_oauth_login(
        self,
        user: Any,
        provider: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after successful OAuth login (v1.2).

        Override to:
        - Track OAuth login
        - Update social account metadata
        - Sync profile changes from provider
        - Send login notification

        Note: This is called AFTER on_after_login, so you can
        differentiate between password-based and OAuth login.

        Args:
            user: The user who logged in
            provider: OAuth provider name ("google", "facebook", etc.)
            request: Optional FastAPI request object

        Example:
            ```python
            async def on_after_oauth_login(self, user, provider, request=None):
                # Update last_used_at for this social account
                await social_account_service.update_last_used(user.id, provider)

                # Track OAuth login separately from password login
                await analytics.track("oauth_login", user.id, {"provider": provider})
            ```
        """
        pass  # Default: do nothing

    async def on_after_oauth_associate(
        self,
        user: Any,
        provider: str,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after an existing user links a new OAuth account (v1.2).

        This happens when an authenticated user uses the associate flow
        to add Google/Facebook/etc login to their existing account.

        Override to:
        - Send account linking notification
        - Log security event (new auth method added)
        - Update user profile with provider data
        - Grant provider-specific features

        Args:
            user: The user who linked the OAuth account
            provider: OAuth provider name ("google", "facebook", etc.)
            request: Optional FastAPI request object

        Example:
            ```python
            async def on_after_oauth_associate(self, user, provider, request=None):
                # Send security notification
                await email_service.send_account_linked_notification(
                    user.email,
                    provider,
                    request.client.host if request else None
                )

                # Log for security audit
                await audit_log.log("oauth_account_linked", user.id, {
                    "provider": provider,
                    "ip": request.client.host if request else None
                })
            ```
        """
        pass  # Default: do nothing

    # ===================================================================
    # CORE SERVICE METHODS - Implement these based on your models
    # ===================================================================

    async def get_user(self, user_id: str) -> Optional[Any]:
        """Get user by ID."""
        raise NotImplementedError("Implement in concrete service")

    async def create_user(self, email: str, password: str, **kwargs) -> Any:
        """
        Create a new user.

        Calls on_after_register hook after creation.
        """
        raise NotImplementedError("Implement in concrete service")

    async def update_user(self, user_id: str, update_dict: Dict[str, Any]) -> Any:
        """
        Update user profile.

        Calls on_after_update hook after update.
        """
        raise NotImplementedError("Implement in concrete service")

    async def delete_user(self, user_id: str) -> None:
        """
        Delete user.

        Calls on_before_delete and on_after_delete hooks.
        """
        raise NotImplementedError("Implement in concrete service")
