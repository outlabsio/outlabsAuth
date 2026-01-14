"""
User Service

Handles user management operations with PostgreSQL/SQLAlchemy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.base import BaseService
from outlabs_auth.utils.password import generate_password_hash, verify_password
from outlabs_auth.utils.validation import validate_email, validate_name


class UserService(BaseService[User]):
    """
    User management service.

    Handles:
    - User creation with password validation
    - User profile updates
    - User status management
    - User listing and search
    - User deletion
    """

    def __init__(
        self,
        config: AuthConfig,
        notification_service: Optional[Any] = None,
    ):
        """
        Initialize UserService.

        Args:
            config: Authentication configuration
            notification_service: Optional notification service for events
        """
        super().__init__(User)
        self.config = config
        self.notifications = notification_service

    # =========================================================================
    # Lifecycle hooks (override in subclasses)
    # =========================================================================

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ) -> None:
        pass

    async def on_after_update(
        self, user: User, update_dict: Dict[str, Any], request: Optional[Request] = None
    ) -> None:
        pass

    async def on_before_delete(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_delete(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_verify(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_reset_password(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_failed_login(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        pass

    async def on_after_oauth_register(
        self, user: User, provider: str, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_oauth_login(
        self, user: User, provider: str, request: Optional[Request] = None
    ) -> None:
        pass

    async def on_after_oauth_associate(
        self, user: User, provider: str, request: Optional[Request] = None
    ) -> None:
        pass

    async def create_user(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_superuser: bool = False,
        tenant_id: Optional[str] = None,
    ) -> User:
        """
        Create a new user.

        Args:
            session: Database session
            email: User email (will be normalized to lowercase)
            password: Plain text password (will be hashed)
            first_name: Optional first name
            last_name: Optional last name
            is_superuser: Whether user has superuser privileges
            tenant_id: Optional tenant ID for multi-tenant mode

        Returns:
            User: Created user

        Raises:
            UserAlreadyExistsError: If email already exists
        """
        # Validate and normalize email
        email = validate_email(email)

        # Check if user already exists
        existing = await self.get_one(session, User.email == email)
        if existing:
            raise UserAlreadyExistsError(
                message=f"User with email {email} already exists",
                details={"email": email},
            )

        # Validate names if provided
        if first_name:
            first_name = validate_name(first_name, "first_name")
        if last_name:
            last_name = validate_name(last_name, "last_name")

        # Hash password (with validation)
        hashed_password = generate_password_hash(password, self.config)

        # Create user
        user = User(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            status=UserStatus.ACTIVE,
            is_superuser=is_superuser,
            tenant_id=tenant_id,
        )

        await self.create(session, user)

        # Emit notification (fire-and-forget)
        if self.notifications:
            await self.notifications.emit(
                "user.created",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "created_at": user.created_at.isoformat(),
                },
            )

        return user

    async def get_user_by_id(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> Optional[User]:
        """
        Get user by ID.

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            User if found, None otherwise
        """
        return await self.get_by_id(session, user_id)

    async def get_user_by_email(
        self,
        session: AsyncSession,
        email: str,
    ) -> Optional[User]:
        """
        Get user by email.

        Args:
            session: Database session
            email: User email

        Returns:
            User if found, None otherwise
        """
        email = validate_email(email)
        return await self.get_one(session, User.email == email)

    async def update_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """
        Update user profile.

        Args:
            session: Database session
            user_id: User UUID
            first_name: Updated first name
            last_name: Updated last name

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        if first_name is not None:
            user.first_name = validate_name(first_name, "first_name")

        if last_name is not None:
            user.last_name = validate_name(last_name, "last_name")

        await self.update(session, user)
        return user

    async def update_user_fields(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """
        Update user fields (email and/or profile).

        This is a convenience wrapper used by the HTTP routers.
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        if email is not None:
            normalized_email = validate_email(email)
            if normalized_email != user.email:
                existing = await self.get_one(
                    session,
                    User.email == normalized_email,
                    User.tenant_id == user.tenant_id,
                )
                if existing:
                    raise UserAlreadyExistsError(
                        message=f"User with email {normalized_email} already exists",
                        details={"email": normalized_email},
                    )
                user.email = normalized_email

        if first_name is not None:
            user.first_name = validate_name(first_name, "first_name")

        if last_name is not None:
            user.last_name = validate_name(last_name, "last_name")

        await self.update(session, user)
        return user

    async def change_password_with_current(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        current_password: str,
        new_password: str,
    ) -> User:
        """
        Change password, verifying the current password first.
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        if not user.hashed_password or not verify_password(
            current_password, user.hashed_password
        ):
            raise InvalidCredentialsError(message="Current password is incorrect")

        return await self.change_password(
            session, user_id=user_id, new_password=new_password
        )

    async def change_password(
        self,
        session: AsyncSession,
        user_id: UUID,
        new_password: str,
    ) -> User:
        """
        Change user password.

        Args:
            session: Database session
            user_id: User UUID
            new_password: New plain text password (will be hashed)

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        # Hash new password (with validation)
        hashed_password = generate_password_hash(new_password, self.config)
        user.hashed_password = hashed_password
        user.last_password_change = datetime.now(timezone.utc)

        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None

        await self.update(session, user)

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.password_changed",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "changed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return user

    async def update_user_status(
        self,
        session: AsyncSession,
        user_id: UUID,
        status: UserStatus,
    ) -> User:
        """
        Update user status.

        Args:
            session: Database session
            user_id: User UUID
            status: New user status

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        old_status = user.status
        user.status = status

        await self.update(session, user)

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.status_changed",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "old_status": old_status.value
                    if hasattr(old_status, "value")
                    else old_status,
                    "new_status": status.value if hasattr(status, "value") else status,
                    "changed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return user

    async def delete_user(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> bool:
        """
        Delete user.

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            return False

        # Store user data before deletion for notification
        user_email = user.email
        user_id_str = str(user.id)

        await self.delete(session, user)

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.deleted",
                data={
                    "user_id": user_id_str,
                    "email": user_email,
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return True

    async def list_users(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 20,
        status: Optional[UserStatus] = None,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[User], int]:
        """
        List users with pagination.

        Args:
            session: Database session
            page: Page number (1-indexed)
            limit: Results per page
            status: Filter by status
            tenant_id: Filter by tenant (multi-tenant mode)

        Returns:
            Tuple of (users, total_count)
        """
        # Build filters
        filters = []
        if status:
            filters.append(User.status == status)
        if tenant_id:
            filters.append(User.tenant_id == tenant_id)

        # Get total count
        total_count = await self.count(session, *filters)

        # Get paginated results
        skip = (page - 1) * limit
        users = await self.get_many(
            session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=User.created_at.desc(),
        )

        return users, total_count

    async def search_users(
        self,
        session: AsyncSession,
        search_term: str,
        limit: int = 20,
    ) -> List[User]:
        """
        Search users by email or name.

        Args:
            session: Database session
            search_term: Search term (searches email, first name, last name)
            limit: Maximum results to return

        Returns:
            List of matching users
        """
        # Case-insensitive search using ILIKE
        pattern = f"%{search_term}%"
        users = await self.get_many(
            session,
            or_(
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            ),
            limit=limit,
        )
        return users

    async def verify_email(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> User:
        """
        Mark user email as verified.

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        user.email_verified = True
        await self.update(session, user)
        return user

    async def record_login(
        self,
        session: AsyncSession,
        user: User,
        success: bool = True,
    ) -> None:
        """
        Record a login attempt.

        Args:
            session: Database session
            user: User attempting login
            success: Whether login was successful
        """
        if success:
            user.last_login_at = datetime.now(timezone.utc)
            user.failed_login_attempts = 0
            user.locked_until = None
        else:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        await self.update(session, user)

    # ========================================================================
    # Event Hooks (FastAPI-Users pattern)
    # ========================================================================

    async def on_after_register(
        self,
        user: User,
        request: Optional[Request] = None,
    ) -> None:
        """Hook called after successful user registration."""
        pass

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ) -> None:
        """Hook called after successful user login."""
        pass

    async def on_after_update(
        self,
        user: User,
        update_dict: Dict[str, Any],
        request: Optional[Request] = None,
    ) -> None:
        """Hook called after successful user update."""
        pass

    async def on_after_forgot_password(
        self,
        user: User,
        token: str,
        request: Optional[Request] = None,
    ) -> None:
        """Hook called after forgot password request."""
        pass

    async def on_after_reset_password(
        self,
        user: User,
        request: Optional[Request] = None,
    ) -> None:
        """Hook called after successful password reset."""
        pass

    async def on_after_verify(
        self,
        user: User,
        request: Optional[Request] = None,
    ) -> None:
        """Hook called after successful email verification."""
        pass
