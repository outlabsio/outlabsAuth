"""
Authentication Service

Handles user authentication operations:
- Login (email/password)
- Logout (revoke refresh tokens)
- Token refresh
- Current user retrieval
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
import hashlib

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


class TokenPair:
    """Container for access and refresh tokens"""
    def __init__(self, access_token: str, refresh_token: str, token_type: str = "bearer"):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
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
    ):
        """
        Initialize AuthService.

        Args:
            database: MongoDB database instance
            config: Authentication configuration
        """
        self.database = database
        self.config = config

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
        # Validate and normalize email
        email = validate_email(email)

        # Find user by email
        user = await UserModel.find_one(UserModel.email == email)
        if not user:
            raise InvalidCredentialsError(
                message="Invalid email or password",
                details={"email": email}
            )

        # Check if account is locked
        if user.is_locked:
            raise AccountLockedError(
                message=f"Account is locked until {user.locked_until.isoformat() if user.locked_until else 'unknown'}",
                details={
                    "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                    "reason": "Too many failed login attempts"
                }
            )

        # Check if account is active
        if user.status != UserStatus.ACTIVE:
            raise AccountInactiveError(
                message=f"Account is {user.status.value}",
                details={"status": user.status.value}
            )

        # Verify password
        if not user.hashed_password or not verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts += 1

            # Lock account if max attempts exceeded
            if user.failed_login_attempts >= self.config.max_login_attempts:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.config.lockout_duration_minutes
                )

            await user.save()

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

        # Create JWT token pair
        access_token, refresh_token_value = create_token_pair(
            user_id=str(user.id),
            secret_key=self.config.secret_key,
            algorithm=self.config.algorithm,
            access_token_expire_minutes=self.config.access_token_expire_minutes,
            refresh_token_expire_days=self.config.refresh_token_expire_days,
        )

        # Store refresh token in database (for revocation support)
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
        )

        return user, token_pair

    async def logout(self, refresh_token: str) -> bool:
        """
        Logout user by revoking refresh token.

        Args:
            refresh_token: Refresh token to revoke

        Returns:
            bool: True if token was revoked, False if not found

        Example:
            >>> await auth_service.logout(refresh_token)
            True
        """
        token_hash = self._hash_token(refresh_token)

        # Find and revoke the refresh token
        token_model = await RefreshTokenModel.find_one(
            RefreshTokenModel.token_hash == token_hash
        )

        if not token_model:
            return False

        # Mark as revoked
        token_model.is_revoked = True
        token_model.revoked_at = datetime.now(timezone.utc)
        token_model.revoked_reason = "User logout"
        await token_model.save()

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
                expected_type="refresh"
            )
        except TokenExpiredError:
            raise
        except TokenInvalidError:
            raise RefreshTokenInvalidError(
                message="Invalid refresh token",
                details={"reason": "Token verification failed"}
            )

        # Check if refresh token exists in database and is valid
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
            raise RefreshTokenInvalidError(
                message="Refresh token is invalid or expired",
                details={
                    "is_revoked": token_model.is_revoked,
                    "expires_at": token_model.expires_at.isoformat() if token_model.expires_at else None,
                }
            )

        # Get user
        user = await token_model.user.fetch()
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": str(token_model.user.ref.id)}
            )

        # Check user status
        if user.status != UserStatus.ACTIVE:
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
        )

        # Update token usage stats
        token_model.last_used_at = datetime.now(timezone.utc)
        token_model.usage_count += 1
        await token_model.save()

        # Return new access token with same refresh token
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,  # Same refresh token
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
            expected_type="access"
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

        # Check user status
        if user.status != UserStatus.ACTIVE:
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
