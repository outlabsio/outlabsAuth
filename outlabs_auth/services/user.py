"""
User Service

Handles user management operations with PostgreSQL/SQLAlchemy.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, cast
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidCredentialsError,
    InvalidInputError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from outlabs_auth.mail.types import (
    AccessGrantedMailIntent,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    MailRecipient,
    PasswordResetConfirmationMailIntent,
    coerce_metadata,
)
from outlabs_auth.models.sql.entity import Entity
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
        auth_service: Optional[Any] = None,
        membership_service: Optional[Any] = None,
        role_service: Optional[Any] = None,
        api_key_service: Optional[Any] = None,
        user_audit_service: Optional[Any] = None,
        transactional_mail_service: Optional[Any] = None,
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
        self.auth_service = auth_service
        self.membership_service = membership_service
        self.role_service = role_service
        self.api_key_service = api_key_service
        self.user_audit_service = user_audit_service
        self.transactional_mail_service = transactional_mail_service

    # =========================================================================
    # Lifecycle hooks (override in subclasses)
    # =========================================================================

    async def on_after_register(self, user: User, request: Optional[Request] = None) -> None:
        pass

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
    ) -> None:
        pass

    async def on_after_update(self, user: User, update_dict: Dict[str, Any], request: Optional[Request] = None) -> None:
        pass

    async def on_before_delete(self, user: User, request: Optional[Request] = None) -> None:
        pass

    async def on_after_delete(self, user: User, request: Optional[Request] = None) -> None:
        pass

    async def on_after_request_verify(self, user: User, token: str, request: Optional[Request] = None) -> None:
        pass

    async def on_after_verify(self, user: User, request: Optional[Request] = None) -> None:
        pass

    async def on_after_forgot_password(self, user: User, token: str, request: Optional[Request] = None) -> None:
        await self.send_forgot_password_email(user, token, request=request)

    async def on_after_reset_password(self, user: User, request: Optional[Request] = None) -> None:
        await self.send_password_reset_confirmation_email(user, request=request)

    async def on_after_invite(self, user: User, token: str, request: Optional[Request] = None) -> None:
        """Hook called after user invitation. Override to send invite link via preferred channel."""
        await self.send_invitation_email(user, token, request=request)

    async def on_failed_login(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        pass

    async def on_after_oauth_register(self, user: User, provider: str, request: Optional[Request] = None) -> None:
        pass

    async def on_after_oauth_login(self, user: User, provider: str, request: Optional[Request] = None) -> None:
        pass

    async def on_after_oauth_associate(self, user: User, provider: str, request: Optional[Request] = None) -> None:
        pass

    async def send_invitation_email(
        self,
        user: User,
        token: str,
        *,
        request: Optional[Request] = None,
        metadata: Optional[dict[str, Any]] = None,
        **extra_metadata: Any,
    ) -> bool:
        """Send an invite email via the configured transactional mail service."""
        if self.transactional_mail_service is None:
            return False
        intent = InviteMailIntent(
            recipient=self._build_mail_recipient(user),
            token=token,
            expires_at=user.invite_token_expires,
            request_base_url=self._request_base_url(request),
            metadata=self._merge_mail_metadata(metadata, extra_metadata),
        )
        result = await self.transactional_mail_service.send_invite(intent)
        return bool(result.accepted)

    async def send_forgot_password_email(
        self,
        user: User,
        token: str,
        *,
        request: Optional[Request] = None,
        metadata: Optional[dict[str, Any]] = None,
        **extra_metadata: Any,
    ) -> bool:
        """Send a password-reset email via the configured transactional mail service."""
        if self.transactional_mail_service is None:
            return False
        intent = ForgotPasswordMailIntent(
            recipient=self._build_mail_recipient(user),
            token=token,
            expires_at=user.password_reset_expires,
            request_base_url=self._request_base_url(request),
            metadata=self._merge_mail_metadata(metadata, extra_metadata),
        )
        result = await self.transactional_mail_service.send_forgot_password(intent)
        return bool(result.accepted)

    async def send_password_reset_confirmation_email(
        self,
        user: User,
        *,
        request: Optional[Request] = None,
        metadata: Optional[dict[str, Any]] = None,
        **extra_metadata: Any,
    ) -> bool:
        """Send a password-reset confirmation email via the configured transactional mail service."""
        if self.transactional_mail_service is None:
            return False
        intent = PasswordResetConfirmationMailIntent(
            recipient=self._build_mail_recipient(user),
            changed_at=user.last_password_change,
            request_base_url=self._request_base_url(request),
            metadata=self._merge_mail_metadata(metadata, extra_metadata),
        )
        result = await self.transactional_mail_service.send_password_reset_confirmation(intent)
        return bool(result.accepted)

    async def send_entity_access_granted_email(
        self,
        user: User,
        *,
        request: Optional[Request] = None,
        metadata: Optional[dict[str, Any]] = None,
        **extra_metadata: Any,
    ) -> bool:
        """Send an access-granted email via the configured transactional mail service."""
        if self.transactional_mail_service is None:
            return False
        intent = AccessGrantedMailIntent(
            recipient=self._build_mail_recipient(user),
            request_base_url=self._request_base_url(request),
            metadata=self._merge_mail_metadata(metadata, extra_metadata),
        )
        result = await self.transactional_mail_service.send_access_granted(intent)
        return bool(result.accepted)

    async def create_user(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_superuser: bool = False,
        root_entity_id: Optional[UUID] = None,
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
            root_entity_id: Optional root entity ID to assign user to an organization.
                           Must be a root entity (parent_id is NULL).

        Returns:
            User: Created user

        Raises:
            UserAlreadyExistsError: If email already exists
            EntityNotFoundError: If root_entity_id doesn't exist
            InvalidInputError: If root_entity_id is not a root entity
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

        # Validate root_entity_id if provided
        if root_entity_id:
            entity = await session.get(Entity, root_entity_id)
            if not entity:
                raise EntityNotFoundError(
                    message="Root entity not found",
                    details={"root_entity_id": str(root_entity_id)},
                )
            if entity.parent_id is not None:
                raise InvalidInputError(
                    message="User can only be assigned to root entities (entities with no parent)",
                    details={
                        "root_entity_id": str(root_entity_id),
                        "entity_name": entity.name,
                        "parent_id": str(entity.parent_id),
                    },
                )

        # Create user
        user = User(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            status=UserStatus.ACTIVE,
            is_superuser=is_superuser,
            root_entity_id=root_entity_id,
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
        *,
        load_root_entity: bool = False,
    ) -> Optional[User]:
        """
        Get user by ID.

        Args:
            session: Database session
            user_id: User UUID
            load_root_entity: Whether to eager-load the assigned root entity

        Returns:
            User if found, None otherwise
        """
        options = [joinedload(cast(Any, User.root_entity))] if load_root_entity else None
        return await self.get_by_id(session, user_id, options=options)

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
        changed_by_id: Optional[UUID] = None,
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

        previous_email = user.email
        previous_email_verified = user.email_verified
        previous_first_name = user.first_name
        previous_last_name = user.last_name
        email_changed = False
        changed_profile_fields: List[str] = []

        if email is not None:
            normalized_email = validate_email(email)
            if normalized_email != user.email:
                existing = await self.get_one(
                    session,
                    User.email == normalized_email,
                )
                if existing:
                    raise UserAlreadyExistsError(
                        message=f"User with email {normalized_email} already exists",
                        details={"email": normalized_email},
                    )
                user.email = normalized_email
                user.email_verified = False
                email_changed = True

        if first_name is not None:
            validated_first_name = validate_name(first_name, "first_name")
            if validated_first_name != user.first_name:
                changed_profile_fields.append("first_name")
            user.first_name = validated_first_name

        if last_name is not None:
            validated_last_name = validate_name(last_name, "last_name")
            if validated_last_name != user.last_name:
                changed_profile_fields.append("last_name")
            user.last_name = validated_last_name

        await self.update(session, user)

        if self.user_audit_service and email_changed:
            await self.user_audit_service.record_event(
                session,
                event_category="profile",
                event_type="user.email_changed",
                event_source="user_service.update_user_fields",
                actor_user_id=changed_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                before={
                    "email": previous_email,
                    "email_verified": previous_email_verified,
                },
                after={
                    "email": user.email,
                    "email_verified": user.email_verified,
                },
                metadata={"changed_fields": ["email"]},
            )

        if self.user_audit_service and changed_profile_fields:
            await self.user_audit_service.record_event(
                session,
                event_category="profile",
                event_type="user.profile_updated",
                event_source="user_service.update_user_fields",
                actor_user_id=changed_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                before={
                    "first_name": previous_first_name,
                    "last_name": previous_last_name,
                },
                after={
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                metadata={"changed_fields": changed_profile_fields},
            )

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

        if not user.hashed_password or not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError(message="Current password is incorrect")

        return await self.change_password(
            session,
            user_id=user_id,
            new_password=new_password,
            changed_by_id=user_id,
        )

    async def change_password(
        self,
        session: AsyncSession,
        user_id: UUID,
        new_password: str,
        changed_by_id: Optional[UUID] = None,
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

        previous_last_password_change = user.last_password_change
        previous_failed_attempts = user.failed_login_attempts
        previous_locked_until = user.locked_until
        changed_at = datetime.now(timezone.utc)

        # Hash new password (with validation)
        hashed_password = generate_password_hash(new_password, self.config)
        user.hashed_password = hashed_password
        user.last_password_change = changed_at

        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None

        await self.update(session, user)

        revoked_token_count = 0
        if self.auth_service is not None:
            revoked_token_count = await self.auth_service.revoke_all_user_tokens(
                session,
                user.id,
                reason="Password changed",
            )

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.password_changed",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "changed_at": changed_at.isoformat(),
                },
            )

        if self.user_audit_service:
            await self.user_audit_service.record_event(
                session,
                event_category="credential",
                event_type="user.password_changed",
                event_source="user_service.change_password",
                actor_user_id=changed_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                before={
                    "last_password_change": previous_last_password_change,
                    "failed_login_attempts": previous_failed_attempts,
                    "locked_until": previous_locked_until,
                },
                after={
                    "last_password_change": user.last_password_change,
                    "failed_login_attempts": user.failed_login_attempts,
                    "locked_until": user.locked_until,
                },
                metadata={"revoked_refresh_token_count": revoked_token_count},
                occurred_at=changed_at,
            )

        return user

    async def update_user_status(
        self,
        session: AsyncSession,
        user_id: UUID,
        status: UserStatus,
        suspended_until: Optional[datetime] = None,
        changed_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> User:
        """
        Update user status.

        Args:
            session: Database session
            user_id: User UUID
            status: New user status
            suspended_until: Optional datetime for suspension auto-expiry

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
        if user.status == UserStatus.DELETED:
            raise InvalidInputError(
                message="Deleted users must be restored via the restore workflow",
                details={
                    "user_id": str(user_id),
                    "status": user.status.value if hasattr(user.status, "value") else user.status,
                },
            )

        old_status = user.status
        old_suspended_until = user.suspended_until
        user.status = status

        # Handle suspended_until field
        if status == UserStatus.SUSPENDED:
            user.suspended_until = suspended_until
        elif status == UserStatus.ACTIVE:
            # Clear suspension when activating
            user.suspended_until = None

        await self.update(session, user)

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.status_changed",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "old_status": old_status.value if hasattr(old_status, "value") else old_status,
                    "new_status": status.value if hasattr(status, "value") else status,
                    "changed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        if self.user_audit_service:
            await self.user_audit_service.record_event(
                session,
                event_category="status",
                event_type="user.status_changed",
                event_source="user_service.update_user_status",
                actor_user_id=changed_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                reason=reason,
                before={
                    "status": old_status,
                    "suspended_until": old_suspended_until,
                },
                after={
                    "status": user.status,
                    "suspended_until": user.suspended_until,
                },
            )

        return user

    async def restore_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        restored_by_id: Optional[UUID] = None,
    ) -> User:
        """
        Restore a deleted user identity only.

        This intentionally restores only the retained user row. Memberships,
        direct roles, refresh tokens, and API keys remain revoked and require
        explicit re-grant or re-issuance.
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        if user.status != UserStatus.DELETED:
            raise InvalidInputError(
                message="Only deleted users can be restored",
                details={
                    "user_id": str(user_id),
                    "status": user.status.value if hasattr(user.status, "value") else user.status,
                },
            )

        previous_deleted_at = user.deleted_at
        user.status = UserStatus.ACTIVE
        user.deleted_at = None
        user.suspended_until = None
        user.locked_until = None

        await self.update(session, user)

        if self.notifications:
            await self.notifications.emit(
                "user.restored",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "restored_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        if self.user_audit_service:
            await self.user_audit_service.record_event(
                session,
                event_category="status",
                event_type="user.restored",
                event_source="user_service.restore_user",
                actor_user_id=restored_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                before={
                    "status": UserStatus.DELETED,
                    "deleted_at": previous_deleted_at,
                },
                after={
                    "status": user.status,
                    "deleted_at": user.deleted_at,
                },
            )

        return user

    async def delete_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        deleted_by_id: Optional[UUID] = None,
    ) -> bool:
        """
        Retain-delete a user and revoke active access artifacts.

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            return False
        if user.status == UserStatus.DELETED:
            return False

        deleted_at = datetime.now(timezone.utc)

        revoked_membership_count = 0
        revoked_role_count = 0
        revoked_token_count = 0
        revoked_api_key_count = 0

        if self.membership_service is not None:
            revoked_memberships = await self.membership_service.revoke_memberships_for_user(
                session,
                user.id,
                revoked_by_id=deleted_by_id,
                reason="User deleted",
                event_source="user_service.delete_user",
            )
            revoked_membership_count = len(revoked_memberships)

        if self.role_service is not None:
            revoked_role_count = await self.role_service.revoke_all_roles_for_user(
                session,
                user.id,
                revoked_by_id=deleted_by_id,
                reason="User deleted",
            )

        if self.auth_service is not None:
            revoked_token_count = await self.auth_service.revoke_all_user_tokens(
                session,
                user.id,
                reason="User deleted",
            )

        if self.api_key_service is not None:
            revoked_api_key_count = await self.api_key_service.revoke_user_api_keys(
                session,
                user.id,
                revoked_by_id=deleted_by_id,
                reason="User deleted",
                event_source="user_service.delete_user",
            )

        previous_status = user.status
        user.status = UserStatus.DELETED
        user.deleted_at = deleted_at
        user.suspended_until = None
        user.locked_until = None

        await self.update(session, user)

        user_email = user.email
        user_id_str = str(user.id)

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.deleted",
                data={
                    "user_id": user_id_str,
                    "email": user_email,
                    "deleted_at": deleted_at.isoformat(),
                },
            )

        if self.user_audit_service:
            await self.user_audit_service.record_event(
                session,
                event_category="status",
                event_type="user.deleted",
                event_source="user_service.delete_user",
                actor_user_id=deleted_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                before={
                    "status": previous_status,
                    "deleted_at": None,
                },
                after={
                    "status": user.status,
                    "deleted_at": user.deleted_at,
                },
                metadata={
                    "revoked_membership_count": revoked_membership_count,
                    "revoked_direct_role_count": revoked_role_count,
                    "revoked_refresh_token_count": revoked_token_count,
                    "revoked_api_key_count": revoked_api_key_count,
                },
                occurred_at=deleted_at,
            )

        return True

    async def list_users(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 20,
        status: Optional[UserStatus] = None,
        is_superuser: Optional[bool] = None,
        root_entity_id: Optional[UUID] = None,
    ) -> Tuple[List[User], int]:
        """
        List users with pagination.

        Args:
            session: Database session
            page: Page number (1-indexed)
            limit: Results per page
            status: Filter by status
            is_superuser: Filter by superuser flag
            root_entity_id: Filter by assigned root entity
        Returns:
            Tuple of (users, total_count)
        """
        # Build filters
        status_col = cast(Any, User.status)
        is_superuser_col = cast(Any, User.is_superuser)
        root_entity_id_col = cast(Any, User.root_entity_id)
        created_at_col = cast(Any, User.created_at)
        filters: list[Any] = []
        if status:
            filters.append(status_col == status)
        if is_superuser is not None:
            filters.append(is_superuser_col == is_superuser)
        if root_entity_id is not None:
            filters.append(root_entity_id_col == root_entity_id)

        # Get total count
        total_count = await self.count(session, *filters)

        # Get paginated results
        skip = (page - 1) * limit
        users = await self.get_many(
            session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=created_at_col.desc(),
        )

        return users, total_count

    async def search_users(
        self,
        session: AsyncSession,
        search_term: str,
        limit: int = 20,
        status: Optional[UserStatus] = None,
        is_superuser: Optional[bool] = None,
        root_entity_id: Optional[UUID] = None,
    ) -> List[User]:
        """
        Search users by email or name.

        Args:
            session: Database session
            search_term: Search term (searches email, first name, last name)
            limit: Maximum results to return
            status: Filter by status
            is_superuser: Filter by superuser flag
            root_entity_id: Filter by assigned root entity

        Returns:
            List of matching users
        """
        # Case-insensitive search using ILIKE
        pattern = f"%{search_term}%"
        status_col = cast(Any, User.status)
        is_superuser_col = cast(Any, User.is_superuser)
        root_entity_id_col = cast(Any, User.root_entity_id)
        email_col = cast(Any, User.email)
        first_name_col = cast(Any, User.first_name)
        last_name_col = cast(Any, User.last_name)
        filters: list[Any] = []
        if status:
            filters.append(status_col == status)
        if is_superuser is not None:
            filters.append(is_superuser_col == is_superuser)
        if root_entity_id is not None:
            filters.append(root_entity_id_col == root_entity_id)

        users = await self.get_many(
            session,
            or_(
                email_col.ilike(pattern),
                first_name_col.ilike(pattern),
                last_name_col.ilike(pattern),
            ),
            *filters,
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
            user.last_login = datetime.now(timezone.utc)
            user.failed_login_attempts = 0
            user.locked_until = None
        else:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        await self.update(session, user)

    # =========================================================================
    # Invitation System
    # =========================================================================

    async def invite_user(
        self,
        session: AsyncSession,
        email: str,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        invited_by_id: Optional[UUID] = None,
        root_entity_id: Optional[UUID] = None,
    ) -> Tuple[User, str]:
        """
        Invite a user by email. Creates account with INVITED status and no password.

        Args:
            session: Database session
            email: Email to invite
            first_name: Optional first name
            last_name: Optional last name
            invited_by_id: UUID of inviting user
            root_entity_id: Optional root entity ID

        Returns:
            Tuple of (User, plain_token)
        """
        email = validate_email(email)

        # Check if user already exists
        existing = await self.get_one(session, User.email == email)
        if existing:
            raise UserAlreadyExistsError(
                message=f"User with email {email} already exists",
                details={"email": email},
            )

        if first_name:
            first_name = validate_name(first_name, "first_name")
        if last_name:
            last_name = validate_name(last_name, "last_name")

        # Validate root_entity_id if provided
        if root_entity_id:
            entity = await session.get(Entity, root_entity_id)
            if not entity:
                raise EntityNotFoundError(
                    message="Root entity not found",
                    details={"root_entity_id": str(root_entity_id)},
                )
            if entity.parent_id is not None:
                raise InvalidInputError(
                    message="User can only be assigned to root entities (entities with no parent)",
                    details={"root_entity_id": str(root_entity_id)},
                )

        # Generate invite token (same pattern as password reset)
        plain_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(days=self.config.invite_token_expire_days)

        user = User(
            email=email,
            hashed_password=None,
            first_name=first_name,
            last_name=last_name,
            status=UserStatus.INVITED,
            is_superuser=False,
            root_entity_id=root_entity_id,
            invite_token=hashed_token,
            invite_token_expires=expires,
            invited_by_id=invited_by_id,
        )

        await self.create(session, user)

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.invited",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "invited_by_id": str(invited_by_id) if invited_by_id else None,
                    "created_at": user.created_at.isoformat(),
                },
            )

        if self.user_audit_service:
            await self.user_audit_service.record_event(
                session,
                event_category="invitation",
                event_type="user.invited",
                event_source="user_service.invite_user",
                actor_user_id=invited_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                before=None,
                after={
                    "status": user.status,
                    "invite_token_expires": user.invite_token_expires,
                    "email_verified": user.email_verified,
                },
                metadata={
                    "invited_by_id": invited_by_id,
                    "root_entity_id": user.root_entity_id,
                },
                occurred_at=user.created_at,
            )

        return user, plain_token

    async def resend_invite(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        resent_by_id: Optional[UUID] = None,
    ) -> Tuple[User, str]:
        """
        Resend invitation by regenerating the invite token.

        Args:
            session: Database session
            user_id: ID of the invited user

        Returns:
            Tuple of (User, new_plain_token)
        """
        user = await self.get_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(user_id)},
            )

        if user.status != UserStatus.INVITED:
            raise InvalidInputError(
                message="Can only resend invitations for users with INVITED status",
                details={"user_id": str(user_id), "current_status": user.status.value},
            )

        # Regenerate token
        plain_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(days=self.config.invite_token_expire_days)
        previous_invite_token_expires = user.invite_token_expires

        user.invite_token = hashed_token
        user.invite_token_expires = expires

        await self.update(session, user)

        if self.user_audit_service:
            await self.user_audit_service.record_event(
                session,
                event_category="invitation",
                event_type="user.invite_resent",
                event_source="user_service.resend_invite",
                actor_user_id=resent_by_id,
                subject_user_id=user.id,
                subject_email_snapshot=user.email,
                root_entity_id=user.root_entity_id,
                before={
                    "status": user.status,
                    "invite_token_expires": previous_invite_token_expires,
                },
                after={
                    "status": user.status,
                    "invite_token_expires": user.invite_token_expires,
                },
            )

        return user, plain_token

    @staticmethod
    def _build_mail_recipient(user: User) -> MailRecipient:
        return MailRecipient(
            user_id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
        )

    @staticmethod
    def _request_base_url(request: Optional[Request]) -> Optional[str]:
        if request is None:
            return None
        return str(request.base_url).rstrip("/")

    @staticmethod
    def _merge_mail_metadata(
        metadata: Optional[dict[str, Any]],
        extra_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        merged = coerce_metadata(metadata)
        merged.update({key: value for key, value in extra_metadata.items() if value is not None})
        return merged
