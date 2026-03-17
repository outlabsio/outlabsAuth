"""
Authentication Service

Handles user authentication operations with PostgreSQL/SQLAlchemy:
- Login (email/password)
- Logout (revoke refresh tokens)
- Token refresh
- Current user retrieval
- Password reset
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    InvalidCredentialsError,
    RefreshTokenInvalidError,
    TokenExpiredError,
    TokenInvalidError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.token import RefreshToken
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.utils.jwt import create_token_pair, verify_token
from outlabs_auth.utils.password import generate_password_hash, verify_and_upgrade_password, verify_password
from outlabs_auth.utils.validation import validate_email


class TokenPair:
    """Container for access and refresh tokens."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        token_type: str = "bearer",
        expires_in: int = 900,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
        self.expires_in = expires_in

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
        }


class AuthService:
    """
    Authentication service for user login, logout, and token management.

    Handles:
    - Email/password authentication
    - JWT token creation and verification
    - Refresh token management
    - Account lockout after failed login attempts
    - Multi-device session support
    """

    def __init__(
        self,
        config: AuthConfig,
        notification_service: Optional[Any] = None,
        activity_tracker: Optional[Any] = None,
        observability: Optional[Any] = None,
    ):
        """
        Initialize AuthService.

        Args:
            config: Authentication configuration
            notification_service: Optional notification service for events
            activity_tracker: Optional activity tracker for DAU/MAU tracking
            observability: Optional observability service for logging/metrics
        """
        self.config = config
        self.notifications = notification_service
        self.activity_tracker = activity_tracker
        self.observability = observability

    async def login(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        device_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, TokenPair]:
        """
        Authenticate user with email and password.

        Args:
            session: Database session
            email: User email address
            password: Plain text password
            device_name: Optional device identifier
            ip_address: Optional IP address for tracking
            user_agent: Optional user agent string

        Returns:
            Tuple of (authenticated user, token pair)

        Raises:
            InvalidCredentialsError: If email or password is incorrect
            AccountLockedError: If account is locked
            AccountInactiveError: If account is not active
        """
        start_time = datetime.now(timezone.utc)

        # Validate and normalize email
        email = validate_email(email)

        # Find user by email
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            self._log_login_failed(email, "user_not_found", 0, ip_address, start_time)
            raise InvalidCredentialsError(
                message="Invalid email or password",
                details={"email": email},
            )

        # Check if account is locked
        if user.is_locked:
            self._log_login_failed(email, "account_locked", user.failed_login_attempts, ip_address, start_time)
            raise AccountLockedError(
                message=f"Account is locked until {user.locked_until.isoformat() if user.locked_until else 'unknown'}",
                details={
                    "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                    "reason": "Too many failed login attempts",
                },
            )

        # Check if account is active
        self._check_user_status(user)

        # Verify password (and opportunistically upgrade legacy hashes).
        is_valid_password = False
        upgraded_hash: Optional[str] = None
        if user.hashed_password:
            is_valid_password, upgraded_hash = verify_and_upgrade_password(password, user.hashed_password)

        if not is_valid_password:
            # Increment failed login attempts
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

            # Check if account should be locked
            was_locked = False
            if user.failed_login_attempts >= self.config.max_login_attempts:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=self.config.lockout_duration_minutes)
                was_locked = True

            await session.flush()
            await session.commit()

            self._log_login_failed(email, "invalid_password", user.failed_login_attempts, ip_address, start_time)

            if was_locked:
                self._log_account_locked(str(user.id), email, ip_address)

            # Emit notification for failed login
            if self.notifications:
                await self.notifications.emit(
                    "user.login_failed",
                    data={
                        "user_id": str(user.id),
                        "email": user.email,
                        "failed_attempts": user.failed_login_attempts,
                        "max_attempts": self.config.max_login_attempts,
                    },
                    metadata={"ip": ip_address, "user_agent": user_agent},
                )

            raise InvalidCredentialsError(
                message="Invalid email or password",
                details={
                    "failed_attempts": user.failed_login_attempts,
                    "max_attempts": self.config.max_login_attempts,
                },
            )

        if upgraded_hash and upgraded_hash != user.hashed_password:
            user.hashed_password = upgraded_hash

        # Successful login - reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        await session.flush()

        # Log successful login
        self._log_login_success(str(user.id), email, ip_address, start_time)

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.login",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "timestamp": user.last_login.isoformat(),
                },
                metadata={
                    "ip": ip_address,
                    "device": device_name,
                    "user_agent": user_agent,
                },
            )

        # Track activity
        if self.activity_tracker:
            import asyncio

            asyncio.create_task(self.activity_tracker.track_activity(str(user.id)))

        # Create JWT token pair
        access_token, refresh_token_value = create_token_pair(
            user_id=str(user.id),
            secret_key=self.config.secret_key,
            algorithm=self.config.algorithm,
            access_token_expire_minutes=self.config.access_token_expire_minutes,
            refresh_token_expire_days=self.config.refresh_token_expire_days,
            audience=self.config.jwt_audience,
        )

        # Store refresh token in database (if enabled)
        if self.config.store_refresh_tokens:
            refresh_token_hash = self._hash_token(refresh_token_value)
            refresh_token_model = RefreshToken(
                user_id=user.id,
                token_hash=refresh_token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=self.config.refresh_token_expire_days),
                device_name=device_name,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(refresh_token_model)
            await session.flush()

        # Return user and tokens
        token_pair = TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_value,
            expires_in=self.config.access_token_expire_minutes * 60,
        )

        return user, token_pair

    async def create_tokens_for_user(
        self,
        session: AsyncSession,
        user: User,
        *,
        device_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenPair:
        """
        Create a token pair for an already-authenticated user.

        This is intended for non-password authentication flows
        (for example, OAuth callbacks).
        """
        self._check_user_status(user)

        access_token, refresh_token_value = create_token_pair(
            user_id=str(user.id),
            secret_key=self.config.secret_key,
            algorithm=self.config.algorithm,
            access_token_expire_minutes=self.config.access_token_expire_minutes,
            refresh_token_expire_days=self.config.refresh_token_expire_days,
            audience=self.config.jwt_audience,
        )

        if self.config.store_refresh_tokens:
            refresh_token_hash = self._hash_token(refresh_token_value)
            refresh_token_model = RefreshToken(
                user_id=user.id,
                token_hash=refresh_token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=self.config.refresh_token_expire_days),
                device_name=device_name,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(refresh_token_model)
            await session.flush()

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_value,
            expires_in=self.config.access_token_expire_minutes * 60,
        )

    async def logout(
        self,
        session: AsyncSession,
        refresh_token: str,
        blacklist_access_token: bool = False,
        access_token_jti: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ) -> bool:
        """
        Logout user by revoking refresh token.

        Args:
            session: Database session
            refresh_token: Refresh token to revoke
            blacklist_access_token: If True, blacklist access token (requires Redis)
            access_token_jti: JWT ID of access token to blacklist
            redis_client: Optional Redis client for blacklisting

        Returns:
            True if refresh token was revoked, False if not found
        """
        # Check if refresh token storage is enabled
        if not self.config.store_refresh_tokens:
            # Stateless JWT mode - only blacklist access token if requested
            blacklisted = False
            if blacklist_access_token and access_token_jti and self.config.enable_token_blacklist:
                if redis_client and hasattr(redis_client, "is_available") and redis_client.is_available:
                    remaining_ttl = self.config.access_token_expire_minutes * 60
                    blacklisted = await redis_client.set(
                        f"blacklist:jwt:{access_token_jti}",
                        "revoked",
                        ttl=remaining_ttl,
                    )
            return blacklisted

        # Find refresh token in database
        token_hash = self._hash_token(refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await session.execute(stmt)
        token_model = result.scalar_one_or_none()

        if not token_model:
            return False

        if token_model.is_revoked:
            return False

        # Mark as revoked
        token_model.revoke("User logout")

        # Calculate session duration for observability
        session_duration_seconds = (datetime.now(timezone.utc) - token_model.created_at).total_seconds()

        await session.flush()

        # Optional: Blacklist access token in Redis
        blacklisted = False
        if blacklist_access_token and access_token_jti and self.config.enable_token_blacklist:
            if redis_client and hasattr(redis_client, "is_available") and redis_client.is_available:
                remaining_ttl = self.config.access_token_expire_minutes * 60
                blacklisted = await redis_client.set(
                    f"blacklist:jwt:{access_token_jti}",
                    "revoked",
                    ttl=remaining_ttl,
                )

        # Log logout
        if self.observability:
            self.observability.log_logout(
                user_id=str(token_model.user_id),
                session_duration_seconds=session_duration_seconds,
                revoke_all_tokens=blacklist_access_token,
            )

        return True

    async def refresh_access_token(
        self,
        session: AsyncSession,
        refresh_token: str,
    ) -> TokenPair:
        """
        Get new access token using refresh token.

        Args:
            session: Database session
            refresh_token: Valid refresh token

        Returns:
            New token pair with same refresh token

        Raises:
            RefreshTokenInvalidError: If refresh token is invalid or revoked
            TokenExpiredError: If refresh token has expired
            UserNotFoundError: If user no longer exists
        """
        # Verify JWT structure
        try:
            payload = verify_token(
                refresh_token,
                self.config.secret_key,
                self.config.algorithm,
                expected_type="refresh",
                audience=self.config.jwt_audience,
            )
        except TokenExpiredError:
            if self.observability:
                self.observability.log_token_refreshed(
                    user_id="unknown",
                    status="failed",
                    reason="token_expired",
                )
            raise
        except TokenInvalidError:
            if self.observability:
                self.observability.log_token_refreshed(
                    user_id="unknown",
                    status="failed",
                    reason="invalid_token",
                )
            raise RefreshTokenInvalidError(
                message="Invalid refresh token",
                details={"reason": "Token verification failed"},
            )

        # Extract user ID
        user_id = payload.get("sub")
        if not user_id:
            raise RefreshTokenInvalidError(
                message="Invalid refresh token: missing user ID",
                details={"reason": "No user ID in token"},
            )

        token_model = None

        # If refresh token storage is enabled, check database
        if self.config.store_refresh_tokens:
            token_hash = self._hash_token(refresh_token)
            stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            result = await session.execute(stmt)
            token_model = result.scalar_one_or_none()

            if not token_model:
                raise RefreshTokenInvalidError(
                    message="Refresh token not found",
                    details={"reason": "Token not in database"},
                )

            if not token_model.is_valid():
                if token_model.is_revoked:
                    raise RefreshTokenInvalidError(
                        message="Refresh token has been revoked",
                        details={
                            "reason": "revoked",
                            "revoked_at": token_model.revoked_at.isoformat() if token_model.revoked_at else None,
                            "revoked_reason": token_model.revoked_reason,
                        },
                    )
                raise RefreshTokenInvalidError(
                    message="Refresh token has expired",
                    details={
                        "reason": "expired",
                        "expires_at": token_model.expires_at.isoformat() if token_model.expires_at else None,
                    },
                )

        # Get user from database
        stmt = select(User).where(User.id == UUID(user_id))
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id},
            )

        # Check user status
        self._check_user_status(user)

        if self._token_is_stale(payload, user.last_password_change):
            if token_model is not None:
                token_model.revoke("Password changed")
                await session.flush()
            raise RefreshTokenInvalidError(
                message="Refresh token is no longer valid",
                details={"reason": "password_changed"},
            )

        # Create new access token
        access_token, _ = create_token_pair(
            user_id=str(user.id),
            secret_key=self.config.secret_key,
            algorithm=self.config.algorithm,
            access_token_expire_minutes=self.config.access_token_expire_minutes,
            refresh_token_expire_days=self.config.refresh_token_expire_days,
            audience=self.config.jwt_audience,
        )

        # Update token usage stats
        if self.config.store_refresh_tokens and token_model:
            token_model.record_usage()
            await session.flush()

        # Log successful refresh
        if self.observability:
            self.observability.log_token_refreshed(
                user_id=str(user.id),
                status="success",
            )

        # Track activity
        if self.activity_tracker:
            import asyncio

            asyncio.create_task(self.activity_tracker.track_activity(str(user.id)))

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.config.access_token_expire_minutes * 60,
        )

    async def get_current_user(
        self,
        session: AsyncSession,
        access_token: str,
    ) -> User:
        """
        Get current user from access token.

        Args:
            session: Database session
            access_token: JWT access token

        Returns:
            Authenticated user

        Raises:
            TokenInvalidError: If token is invalid
            TokenExpiredError: If token has expired
            UserNotFoundError: If user doesn't exist
            AccountInactiveError: If account is not active
        """
        # Verify and decode token
        payload = verify_token(
            access_token,
            self.config.secret_key,
            self.config.algorithm,
            expected_type="access",
            audience=self.config.jwt_audience,
        )

        # Get user ID
        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError(
                message="Invalid token: missing user ID",
                details={"payload": payload},
            )

        # Get user from database
        stmt = select(User).where(User.id == UUID(user_id))
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id},
            )

        # Check user status
        self._check_user_status(user)

        if self._token_is_stale(payload, user.last_password_change):
            raise TokenInvalidError(
                message="Token is no longer valid",
                details={"reason": "password_changed"},
            )

        return user

    async def revoke_all_user_tokens(
        self,
        session: AsyncSession,
        user_id: UUID,
        reason: str = "Revoke all sessions",
    ) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            session: Database session
            user_id: User UUID
            reason: Revocation reason

        Returns:
            Number of tokens revoked
        """
        if not self.config.store_refresh_tokens:
            return 0

        # Find all active tokens for user
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,
        )
        result = await session.execute(stmt)
        tokens = result.scalars().all()

        # Revoke all
        revoked_count = 0
        now = datetime.now(timezone.utc)
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = now
            token.revoked_reason = reason
            revoked_count += 1

        await session.flush()
        return revoked_count

    async def generate_reset_token(
        self,
        session: AsyncSession,
        user: User,
    ) -> str:
        """
        Generate a password reset token for user.

        Args:
            session: Database session
            user: User requesting password reset

        Returns:
            Plain reset token (to be sent via email)
        """
        import secrets

        # Generate secure random token
        plain_token = secrets.token_urlsafe(32)

        # Hash token for storage
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()

        # Set expiration (1 hour)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store hashed token
        user.password_reset_token = hashed_token
        user.password_reset_expires = expires
        await session.flush()

        return plain_token

    async def reset_password(
        self,
        session: AsyncSession,
        token: str,
        new_password: str,
    ) -> User:
        """
        Reset user password using reset token.

        Args:
            session: Database session
            token: Plain reset token (from email)
            new_password: New password (will be hashed)

        Returns:
            User with updated password

        Raises:
            TokenInvalidError: If token is invalid or expired
        """
        # Hash token to find user
        hashed_token = hashlib.sha256(token.encode()).hexdigest()

        # Find user by hashed token
        stmt = select(User).where(User.password_reset_token == hashed_token)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise TokenInvalidError(
                message="Invalid or expired reset token",
                details={"reason": "token_not_found"},
            )

        # Check expiration
        if not user.password_reset_expires or user.password_reset_expires < datetime.now(timezone.utc):
            # Clear expired token
            user.password_reset_token = None
            user.password_reset_expires = None
            await session.flush()
            await session.commit()

            raise TokenExpiredError(
                message="Reset token has expired",
                details={"expired_at": user.password_reset_expires},
            )

        # Change password
        hashed_password = generate_password_hash(new_password, self.config)
        user.hashed_password = hashed_password
        user.last_password_change = datetime.now(timezone.utc)

        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None

        # Clear reset token
        user.password_reset_token = None
        user.password_reset_expires = None

        await self.revoke_all_user_tokens(
            session,
            user.id,
            reason="Password reset",
        )
        await session.flush()

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.password_reset",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "reset_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return user

    async def verify_password(self, user: User, password: str) -> bool:
        """
        Verify a password against user's hashed password.

        Args:
            user: User to verify password for
            password: Plain text password to verify

        Returns:
            True if password is correct
        """
        if not user.hashed_password:
            return False
        return verify_password(password, user.hashed_password)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _hash_token(self, token: str) -> str:
        """Hash token for storage using SHA256."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _normalize_token_timestamp(value: Any) -> Optional[datetime]:
        if isinstance(value, Mapping):
            precise_issued_at = value.get("iat_ms")
            if precise_issued_at is not None:
                try:
                    return datetime.fromtimestamp(
                        float(precise_issued_at) / 1000,
                        tz=timezone.utc,
                    )
                except (TypeError, ValueError, OSError):
                    return None
            value = value.get("iat")
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    @classmethod
    def _token_is_stale(
        cls,
        issued_at: Any,
        last_password_change: Optional[datetime],
    ) -> bool:
        if last_password_change is None:
            return False

        issued_at_dt = cls._normalize_token_timestamp(issued_at)
        if issued_at_dt is None:
            return True

        password_change_dt = (
            last_password_change
            if last_password_change.tzinfo is not None
            else last_password_change.replace(tzinfo=timezone.utc)
        )
        return issued_at_dt < password_change_dt

    async def accept_invite(
        self,
        session: AsyncSession,
        token: str,
        new_password: str,
    ) -> User:
        """
        Accept an invitation by setting a password and activating the account.

        Args:
            session: Database session
            token: Plain invite token
            new_password: Password chosen by the invited user

        Returns:
            Activated user

        Raises:
            TokenInvalidError: If token is invalid
            TokenExpiredError: If token has expired
            AccountInactiveError: If user is not in INVITED status
        """
        # Hash token to find user (same pattern as reset_password)
        hashed_token = hashlib.sha256(token.encode()).hexdigest()

        stmt = select(User).where(User.invite_token == hashed_token)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise TokenInvalidError(
                message="Invalid or expired invite token",
                details={"reason": "token_not_found"},
            )

        # Check expiration
        if not user.invite_token_expires or user.invite_token_expires < datetime.now(timezone.utc):
            user.invite_token = None
            user.invite_token_expires = None
            await session.flush()

            raise TokenExpiredError(
                message="Invite token has expired",
                details={"expired_at": user.invite_token_expires.isoformat() if user.invite_token_expires else None},
            )

        # Verify user is in INVITED status
        if user.status != UserStatus.INVITED:
            raise AccountInactiveError(
                message="This invitation has already been accepted",
                details={"status": user.status.value},
            )

        # Set password and activate
        hashed_password = generate_password_hash(new_password, self.config)
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        user.email_verified = True
        user.last_password_change = datetime.now(timezone.utc)

        # Clear invite token fields
        user.invite_token = None
        user.invite_token_expires = None

        await session.flush()

        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.invite_accepted",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "accepted_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return user

    def _check_user_status(self, user: User) -> None:
        """Check if user account is active, raise appropriate error if not."""
        if user.status == UserStatus.ACTIVE:
            return

        if user.status == UserStatus.INVITED:
            raise AccountInactiveError(
                message="Account has not been activated yet. Please check your email for the invitation link.",
                details={"status": "invited"},
            )
        elif user.status == UserStatus.SUSPENDED:
            suspended_msg = f" until {user.suspended_until.isoformat()}" if user.suspended_until else ""
            raise AccountInactiveError(
                message=f"Account is suspended{suspended_msg}",
                details={
                    "status": "suspended",
                    "suspended_until": user.suspended_until.isoformat() if user.suspended_until else None,
                },
            )
        elif user.status == UserStatus.BANNED:
            raise AccountInactiveError(
                message="Account is permanently banned",
                details={"status": "banned"},
            )
        elif user.status == UserStatus.DELETED:
            raise AccountInactiveError(
                message="Account has been deleted",
                details={
                    "status": "deleted",
                    "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
                },
            )
        else:
            raise AccountInactiveError(
                message=f"Account is {user.status.value}",
                details={"status": user.status.value},
            )

    def _log_login_failed(
        self,
        email: str,
        reason: str,
        failed_attempts: int,
        ip_address: Optional[str],
        start_time: datetime,
    ) -> None:
        """Log failed login attempt for observability."""
        if self.observability:
            self.observability.log_login_failed(
                email=email,
                reason=reason,
                method="password",
                failed_attempts=failed_attempts,
                ip_address=ip_address,
            )

    def _log_login_success(
        self,
        user_id: str,
        email: str,
        ip_address: Optional[str],
        start_time: datetime,
    ) -> None:
        """Log successful login for observability."""
        if self.observability:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.observability.log_login_success(
                user_id=user_id,
                email=email,
                method="password",
                duration_ms=duration_ms,
                ip_address=ip_address,
            )

    def _log_account_locked(
        self,
        user_id: str,
        email: str,
        ip_address: Optional[str],
    ) -> None:
        """Log account lockout for observability."""
        if self.observability:
            self.observability.log_account_locked(
                user_id=user_id,
                email=email,
                reason="Too many failed login attempts",
                ip_address=ip_address,
            )
