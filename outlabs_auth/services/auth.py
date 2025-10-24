"""
Authentication Service

Handles user authentication operations:
- Login (email/password)
- Logout (revoke refresh tokens)
- Token refresh
- Current user retrieval
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import hashlib
from beanie import PydanticObjectId

from outlabs_auth.models.user import UserModel, UserStatus
from outlabs_auth.models.token import RefreshTokenModel
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    TokenInvalidError,
    TokenExpiredError,
    AccountLockedError,
    AccountInactiveError,
    UserNotFoundError,
    RefreshTokenInvalidError,
)
from outlabs_auth.utils.password import verify_password
from outlabs_auth.utils.jwt import (
    create_token_pair,
    verify_token,
)
from outlabs_auth.utils.validation import validate_email

# Import observability (v1.5)
from outlabs_auth.observability import ObservabilityService


class TokenPair:
    """Container for access and refresh tokens"""
    def __init__(self, access_token: str, refresh_token: str, token_type: str = "bearer", expires_in: int = 900):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
        self.expires_in = expires_in  # Access token expiration in seconds

    def to_dict(self):
        """Convert to dictionary for API responses"""
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
        database: AsyncIOMotorDatabase,
        config: AuthConfig,
        notification_service: Optional[Any] = None,
        activity_tracker: Optional[Any] = None,
        observability: Optional[ObservabilityService] = None,
    ):
        """
        Initialize AuthService.

        Args:
            database: MongoDB database instance
            config: Authentication configuration
            notification_service: Optional notification service for events
            activity_tracker: Optional activity tracker for DAU/MAU tracking
            observability: Optional observability service for logging/metrics
        """
        self.database = database
        self.config = config
        self.notifications = notification_service
        self.activity_tracker = activity_tracker
        self.observability = observability

    async def login(
        self,
        email: str,
        password: str,
        device_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[UserModel, TokenPair]:
        """
        Authenticate user with email and password.

        Args:
            email: User email address
            password: Plain text password
            device_name: Optional device identifier (for multi-device support)
            ip_address: Optional IP address for tracking
            user_agent: Optional user agent string

        Returns:
            Tuple[UserModel, TokenPair]: Authenticated user and token pair

        Raises:
            InvalidCredentialsError: If email or password is incorrect
            AccountLockedError: If account is locked due to failed login attempts
            AccountInactiveError: If account is not active

        Example:
            >>> user, tokens = await auth_service.login(
            ...     email="user@example.com",
            ...     password="MyPassword123!",
            ...     device_name="iPhone 12"
            ... )
            >>> tokens.access_token
            'eyJ...'
        """
        # Start timing for observability
        start_time = datetime.now(timezone.utc)

        # Validate and normalize email
        email = validate_email(email)

        # Find user by email
        user = await UserModel.find_one(UserModel.email == email)
        if not user:
            # Log failed login attempt (observability)
            if self.observability:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self.observability.log_login_failed(
                    email=email,
                    reason="user_not_found",
                    method="password",
                    failed_attempts=0,
                    ip_address=ip_address,
                )

            raise InvalidCredentialsError(
                message="Invalid email or password",
                details={"email": email}
            )

        # Check if account is locked
        if user.is_locked:
            # Log failed login attempt on locked account (observability)
            if self.observability:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self.observability.log_login_failed(
                    email=email,
                    reason="account_locked",
                    method="password",
                    failed_attempts=user.failed_login_attempts,
                    ip_address=ip_address,
                )

            raise AccountLockedError(
                message=f"Account is locked until {user.locked_until.isoformat() if user.locked_until else 'unknown'}",
                details={
                    "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                    "reason": "Too many failed login attempts"
                }
            )

        # Check if account is active (provide specific error messages per status)
        if user.status != UserStatus.ACTIVE:
            if user.status == UserStatus.SUSPENDED:
                # Suspended with optional expiry date
                suspended_msg = f" until {user.suspended_until.isoformat()}" if user.suspended_until else ""
                raise AccountInactiveError(
                    message=f"Account is suspended{suspended_msg}",
                    details={
                        "status": "suspended",
                        "suspended_until": user.suspended_until.isoformat() if user.suspended_until else None
                    }
                )
            elif user.status == UserStatus.BANNED:
                raise AccountInactiveError(
                    message="Account is permanently banned",
                    details={"status": "banned"}
                )
            elif user.status == UserStatus.DELETED:
                raise AccountInactiveError(
                    message="Account has been deleted",
                    details={
                        "status": "deleted",
                        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None
                    }
                )
            else:
                # Fallback for any unexpected status
                raise AccountInactiveError(
                    message=f"Account is {user.status.value}",
                    details={"status": user.status.value}
                )

        # Verify password
        if not user.hashed_password or not verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts += 1

            # Check if account will be locked
            was_locked = False
            if user.failed_login_attempts >= self.config.max_login_attempts:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.config.lockout_duration_minutes
                )
                was_locked = True

            await user.save()

            # Log failed login attempt (observability)
            if self.observability:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self.observability.log_login_failed(
                    email=user.email,
                    reason="invalid_password",
                    method="password",
                    failed_attempts=user.failed_login_attempts,
                    ip_address=ip_address,
                )

            # Log account lockout (observability)
            if was_locked and self.observability:
                self.observability.log_account_locked(
                    user_id=str(user.id),
                    email=user.email,
                    reason="Too many failed login attempts",
                    ip_address=ip_address,
                )

            # Emit notification for failed login
            if self.notifications:
                await self.notifications.emit(
                    "user.login_failed",
                    data={
                        "user_id": str(user.id),
                        "email": user.email,
                        "failed_attempts": user.failed_login_attempts,
                        "max_attempts": self.config.max_login_attempts
                    },
                    metadata={
                        "ip": ip_address,
                        "user_agent": user_agent
                    }
                )

            # Emit notification if account was locked
            if was_locked and self.notifications:
                await self.notifications.emit(
                    "user.locked",
                    data={
                        "user_id": str(user.id),
                        "email": user.email,
                        "reason": "Too many failed login attempts",
                        "locked_until": user.locked_until.isoformat() if user.locked_until else None
                    }
                )

            raise InvalidCredentialsError(
                message="Invalid email or password",
                details={
                    "failed_attempts": user.failed_login_attempts,
                    "max_attempts": self.config.max_login_attempts,
                }
            )

        # Successful login - reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        await user.save()

        # Log successful login (observability)
        if self.observability:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.observability.log_login_success(
                user_id=str(user.id),
                email=user.email,
                method="password",
                duration_ms=duration_ms,
                ip_address=ip_address,
            )

        # Emit notification (fire-and-forget)
        if self.notifications:
            await self.notifications.emit(
                "user.login",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "timestamp": user.last_login.isoformat()
                },
                metadata={
                    "ip": ip_address,
                    "device": device_name,
                    "user_agent": user_agent
                }
            )

        # Track activity (fire-and-forget)
        if self.activity_tracker:
            import asyncio
            asyncio.create_task(
                self.activity_tracker.track_activity(str(user.id))
            )

        # Create JWT token pair
        access_token, refresh_token_value = create_token_pair(
            user_id=str(user.id),
            secret_key=self.config.secret_key,
            algorithm=self.config.algorithm,
            access_token_expire_minutes=self.config.access_token_expire_minutes,
            refresh_token_expire_days=self.config.refresh_token_expire_days,
            audience=self.config.jwt_audience,
        )

        # Store refresh token in database (for revocation support) - only if enabled
        if self.config.store_refresh_tokens:
            refresh_token_hash = self._hash_token(refresh_token_value)
            refresh_token_model = RefreshTokenModel(
                user=user,
                token_hash=refresh_token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(
                    days=self.config.refresh_token_expire_days
                ),
                device_name=device_name,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await refresh_token_model.save()

        # Return user and tokens
        token_pair = TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_value,
            expires_in=self.config.access_token_expire_minutes * 60,  # Convert to seconds
        )

        return user, token_pair

    async def logout(
        self,
        refresh_token: str,
        blacklist_access_token: bool = False,
        access_token_jti: Optional[str] = None,
        redis_client: Optional[Any] = None
    ) -> bool:
        """
        Logout user by revoking refresh token with optional immediate access token blacklisting.

        Hybrid pattern:
        - Always revokes refresh token in MongoDB (required)
        - Optionally blacklists access token in Redis (for immediate revocation)
        - Gracefully degrades if Redis unavailable

        Args:
            refresh_token: Refresh token to revoke
            blacklist_access_token: If True, blacklist access token immediately (requires Redis)
            access_token_jti: JWT ID of access token to blacklist (required if blacklist_access_token=True)
            redis_client: Optional Redis client for blacklisting

        Returns:
            bool: True if refresh token was revoked, False if not found

        Example:
            >>> # Standard logout (15-min security window)
            >>> await auth_service.logout(refresh_token)
            True

            >>> # Immediate logout (requires Redis)
            >>> await auth_service.logout(
            ...     refresh_token,
            ...     blacklist_access_token=True,
            ...     access_token_jti="abc123...",
            ...     redis_client=redis
            ... )
            True
        """
        # Check if refresh token storage is enabled
        if not self.config.store_refresh_tokens:
            # Stateless JWT mode - can't revoke refresh tokens
            # Only blacklist access token if requested
            blacklisted = False
            if blacklist_access_token and access_token_jti and self.config.enable_token_blacklist:
                if redis_client and hasattr(redis_client, 'is_available') and redis_client.is_available:
                    remaining_ttl = self.config.access_token_expire_minutes * 60
                    blacklisted = await redis_client.set(
                        f"blacklist:jwt:{access_token_jti}",
                        "revoked",
                        ttl=remaining_ttl
                    )
            return blacklisted  # Return True if access token was blacklisted

        # Refresh token storage enabled - revoke in MongoDB
        token_hash = self._hash_token(refresh_token)

        # Find and revoke the refresh token
        token_model = await RefreshTokenModel.find_one(
            RefreshTokenModel.token_hash == token_hash
        )

        if not token_model:
            return False

        # Check if already revoked
        if token_model.is_revoked:
            return False

        # Mark as revoked
        token_model.is_revoked = True
        token_model.revoked_at = datetime.now(timezone.utc)
        token_model.revoked_reason = "User logout"

        # Calculate session duration for observability
        session_start = token_model.created_at
        session_duration_seconds = (datetime.now(timezone.utc) - session_start).total_seconds()

        await token_model.save()

        # Optional: Blacklist access token in Redis for immediate revocation
        blacklisted = False
        if blacklist_access_token and access_token_jti and self.config.enable_token_blacklist:
            if redis_client and hasattr(redis_client, 'is_available') and redis_client.is_available:
                # Calculate remaining TTL for access token
                remaining_ttl = self.config.access_token_expire_minutes * 60

                # Add to blacklist with TTL (auto-expires when token would anyway)
                blacklisted = await redis_client.set(
                    f"blacklist:jwt:{access_token_jti}",
                    "revoked",
                    ttl=remaining_ttl
                )

        # Fetch user for observability and notifications
        user = await token_model.fetch_link("user")

        # Log logout (observability)
        if self.observability and user:
            self.observability.log_logout(
                user_id=str(user.id),
                session_duration_seconds=session_duration_seconds,
                revoke_all_tokens=blacklist_access_token,
            )

        # Emit notification
        if self.notifications and user:
            await self.notifications.emit(
                "user.logout",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "session_id": str(token_model.id),
                    "immediate_revocation": blacklisted
                }
            )

        return True

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """
        Get new access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            TokenPair: New access token and same refresh token

        Raises:
            RefreshTokenInvalidError: If refresh token is invalid or revoked
            TokenExpiredError: If refresh token has expired
            UserNotFoundError: If user no longer exists

        Example:
            >>> tokens = await auth_service.refresh_access_token(refresh_token)
            >>> tokens.access_token  # New access token
            'eyJ...'
        """
        # Verify JWT structure (but don't validate user yet)
        try:
            payload = verify_token(
                refresh_token,
                self.config.secret_key,
                self.config.algorithm,
                expected_type="refresh",
                audience=self.config.jwt_audience
            )
        except TokenExpiredError:
            # Log failed token refresh (observability)
            if self.observability:
                self.observability.log_token_refreshed(
                    user_id="unknown",
                    status="failed",
                    reason="token_expired",
                )
            raise
        except TokenInvalidError:
            # Log failed token refresh (observability)
            if self.observability:
                self.observability.log_token_refreshed(
                    user_id="unknown",
                    status="failed",
                    reason="invalid_token",
                )
            raise RefreshTokenInvalidError(
                message="Invalid refresh token",
                details={"reason": "Token verification failed"}
            )

        # Extract user ID from payload
        user_id = payload.get("sub")
        if not user_id:
            raise RefreshTokenInvalidError(
                message="Invalid refresh token: missing user ID",
                details={"reason": "No user ID in token"}
            )

        # Initialize token_model (will be None in stateless mode)
        token_model = None

        # If refresh token storage is enabled, check database
        if self.config.store_refresh_tokens:
            token_hash = self._hash_token(refresh_token)
            token_model = await RefreshTokenModel.find_one(
                RefreshTokenModel.token_hash == token_hash
            )

            if not token_model:
                raise RefreshTokenInvalidError(
                    message="Refresh token not found",
                    details={"reason": "Token not in database"}
                )

            # Check if token is still valid
            if not token_model.is_valid():
                # Provide specific error message for revoked tokens
                if token_model.is_revoked:
                    raise RefreshTokenInvalidError(
                        message="Refresh token has been revoked",
                        details={
                            "reason": "revoked",
                            "revoked_at": token_model.revoked_at.isoformat() if token_model.revoked_at else None,
                            "revoked_reason": token_model.revoked_reason
                        }
                    )
                # Token is expired
                raise RefreshTokenInvalidError(
                    message="Refresh token has expired",
                    details={
                        "reason": "expired",
                        "expires_at": token_model.expires_at.isoformat() if token_model.expires_at else None,
                    }
                )

            # Get user from token model
            user = await token_model.user.fetch()
            if not user:
                raise UserNotFoundError(
                    message="User not found",
                    details={"user_id": str(token_model.user.ref.id)}
                )
        else:
            # Stateless mode - get user directly from database
            user = await UserModel.find_one(UserModel.id == PydanticObjectId(user_id))
            if not user:
                raise UserNotFoundError(
                    message="User not found",
                    details={"user_id": user_id}
                )

        # Check user status (provide specific error messages per status)
        if user.status != UserStatus.ACTIVE:
            if user.status == UserStatus.SUSPENDED:
                suspended_msg = f" until {user.suspended_until.isoformat()}" if user.suspended_until else ""
                raise AccountInactiveError(
                    message=f"Account is suspended{suspended_msg}",
                    details={
                        "status": "suspended",
                        "suspended_until": user.suspended_until.isoformat() if user.suspended_until else None
                    }
                )
            elif user.status == UserStatus.BANNED:
                raise AccountInactiveError(
                    message="Account is permanently banned",
                    details={"status": "banned"}
                )
            elif user.status == UserStatus.DELETED:
                raise AccountInactiveError(
                    message="Account has been deleted",
                    details={
                        "status": "deleted",
                        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None
                    }
                )
            else:
                raise AccountInactiveError(
                    message=f"Account is {user.status.value}",
                    details={"status": user.status.value}
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

        # Update token usage stats (only if token storage enabled)
        if self.config.store_refresh_tokens and token_model:
            token_model.last_used_at = datetime.now(timezone.utc)
            token_model.usage_count += 1
            await token_model.save()

        # Log successful token refresh (observability)
        if self.observability:
            self.observability.log_token_refreshed(
                user_id=str(user.id),
                status="success",
            )

        # Track activity (fire-and-forget)
        if self.activity_tracker:
            import asyncio
            asyncio.create_task(
                self.activity_tracker.track_activity(str(user.id))
            )

        # Return new access token with same refresh token
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,  # Same refresh token
            expires_in=self.config.access_token_expire_minutes * 60,  # Convert to seconds
        )

    async def get_current_user(self, access_token: str) -> UserModel:
        """
        Get current user from access token.

        Args:
            access_token: JWT access token

        Returns:
            UserModel: Authenticated user

        Raises:
            TokenInvalidError: If token is invalid
            TokenExpiredError: If token has expired
            UserNotFoundError: If user doesn't exist
            AccountInactiveError: If account is not active

        Example:
            >>> user = await auth_service.get_current_user(access_token)
            >>> user.email
            'user@example.com'
        """
        # Verify and decode token
        payload = verify_token(
            access_token,
            self.config.secret_key,
            self.config.algorithm,
            expected_type="access",
            audience=self.config.jwt_audience
        )

        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError(
                message="Invalid token: missing user ID",
                details={"payload": payload}
            )

        # Get user from database
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Check user status (provide specific error messages per status)
        if user.status != UserStatus.ACTIVE:
            if user.status == UserStatus.SUSPENDED:
                suspended_msg = f" until {user.suspended_until.isoformat()}" if user.suspended_until else ""
                raise AccountInactiveError(
                    message=f"Account is suspended{suspended_msg}",
                    details={
                        "status": "suspended",
                        "suspended_until": user.suspended_until.isoformat() if user.suspended_until else None
                    }
                )
            elif user.status == UserStatus.BANNED:
                raise AccountInactiveError(
                    message="Account is permanently banned",
                    details={"status": "banned"}
                )
            elif user.status == UserStatus.DELETED:
                raise AccountInactiveError(
                    message="Account has been deleted",
                    details={
                        "status": "deleted",
                        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None
                    }
                )
            else:
                raise AccountInactiveError(
                    message=f"Account is {user.status.value}",
                    details={"status": user.status.value}
                )

        return user

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all refresh tokens for a user.

        Useful for logout from all devices or security incidents.

        Args:
            user_id: User ID

        Returns:
            int: Number of tokens revoked

        Example:
            >>> count = await auth_service.revoke_all_user_tokens(user_id)
            >>> print(f"Revoked {count} tokens")
        """
        # Find all active refresh tokens for user
        tokens = await RefreshTokenModel.find(
            RefreshTokenModel.user.ref.id == user_id,
            RefreshTokenModel.is_revoked == False
        ).to_list()

        # Revoke all
        revoked_count = 0
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = datetime.now(timezone.utc)
            token.revoked_reason = "Revoke all sessions"
            await token.save()
            revoked_count += 1

        return revoked_count

    def _hash_token(self, token: str) -> str:
        """
        Hash refresh token for storage.

        Uses SHA256 for fast lookups (not for password hashing).

        Args:
            token: Token to hash

        Returns:
            str: Hashed token
        """
        return hashlib.sha256(token.encode()).hexdigest()
