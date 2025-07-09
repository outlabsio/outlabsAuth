"""
Authentication Service
Handles login, logout, token management, and password operations
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import secrets
import json
from passlib.context import CryptContext
from fastapi import HTTPException, status
from beanie import PydanticObjectId

from api.models import UserModel, RefreshTokenModel
from api.utils.jwt_utils import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
    create_password_reset_token,
    create_email_verification_token
)
from api.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storage"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[UserModel]:
        """
        Authenticate a user by email and password
        
        Args:
            email: User's email
            password: Plain text password
        
        Returns:
            User if authentication successful, None otherwise
        """
        user = await UserModel.find_one(UserModel.email == email)
        if not user:
            return None
        
        # Check if user can authenticate (not locked)
        if not user.can_authenticate():
            # Increment failed attempts even when locked
            user.failed_login_attempts += 1
            await user.save()
            return None
        
        # Verify password
        if not AuthService.verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            # Lock account if too many failed attempts
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
            
            await user.save()
            return None
        
        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.last_login = datetime.now(timezone.utc)
        await user.save()
        
        return user
    
    @staticmethod
    async def create_tokens(
        user: UserModel,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[str, str, RefreshTokenModel]:
        """
        Create access and refresh tokens for a user
        
        Args:
            user: User model
            device_info: Device information for tracking
            ip_address: IP address of the request
        
        Returns:
            Tuple of (access_token, refresh_token, refresh_token_model)
        """
        # Create token payload
        payload = TokenPayload(
            sub=str(user.id),
            email=user.email,
            device_id=device_info.get("device_id") if device_info else None
        )
        
        # Create access token
        access_token = create_access_token(payload)
        
        # Create refresh token with family ID
        refresh_token, family_id = create_refresh_token(payload)
        
        # Store refresh token in database
        refresh_model = RefreshTokenModel(
            token=refresh_token,
            user=user,
            family_id=family_id,
            device_info=json.dumps(device_info) if device_info else None,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        )
        await refresh_model.save()
        
        return access_token, refresh_token, refresh_model
    
    @staticmethod
    async def refresh_access_token(
        refresh_token: str,
        ip_address: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Refresh an access token using a refresh token
        Implements token rotation for security
        
        Args:
            refresh_token: Current refresh token
            ip_address: IP address of the request
        
        Returns:
            Tuple of (new_access_token, new_refresh_token)
        
        Raises:
            HTTPException: If token is invalid or revoked
        """
        # Decode the refresh token
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Find the refresh token in database
        token_model = await RefreshTokenModel.find_one(
            RefreshTokenModel.token == refresh_token
        )
        
        if not token_model:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found"
            )
        
        # Check if token is valid
        if not token_model.is_valid():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired"
            )
        
        # Check if token has already been used (potential token replay attack)
        if token_model.used_at:
            # Revoke entire token family
            await RefreshTokenModel.find(
                RefreshTokenModel.family_id == token_model.family_id
            ).update({"$set": {"revoked_at": datetime.now(timezone.utc)}})
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token replay detected - all tokens revoked"
            )
        
        # Mark current token as used
        token_model.used_at = datetime.now(timezone.utc)
        await token_model.save()
        
        # Get the user
        user = await UserModel.get(token_model.user.id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new token pair with same family ID
        payload = TokenPayload(
            sub=str(user.id),
            email=user.email,
            device_id=payload.get("device_id")
        )
        
        # Create new access token
        new_access_token = create_access_token(payload)
        
        # Create new refresh token with same family ID
        new_refresh_token, _ = create_refresh_token(payload, family_id=token_model.family_id)
        
        # Store new refresh token
        new_refresh_model = RefreshTokenModel(
            token=new_refresh_token,
            user=user,
            family_id=token_model.family_id,
            device_info=token_model.device_info,
            ip_address=ip_address or token_model.ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        )
        await new_refresh_model.save()
        
        return new_access_token, new_refresh_token
    
    @staticmethod
    async def logout(refresh_token: str) -> bool:
        """
        Logout a user by revoking their refresh token
        
        Args:
            refresh_token: Refresh token to revoke
        
        Returns:
            True if successful
        """
        token_model = await RefreshTokenModel.find_one(
            RefreshTokenModel.token == refresh_token
        )
        
        if token_model and token_model.is_valid():
            token_model.revoked_at = datetime.now(timezone.utc)
            await token_model.save()
            return True
        
        return False
    
    @staticmethod
    async def logout_all_devices(user_id: str) -> int:
        """
        Logout user from all devices by revoking all refresh tokens
        
        Args:
            user_id: User ID
        
        Returns:
            Number of tokens revoked
        """
        result = await RefreshTokenModel.find(
            RefreshTokenModel.user.id == PydanticObjectId(user_id),
            RefreshTokenModel.revoked_at == None
        ).update({"$set": {"revoked_at": datetime.now(timezone.utc)}})
        
        return result.modified_count if result else 0
    
    @staticmethod
    async def create_password_reset_request(email: str) -> Optional[str]:
        """
        Create a password reset token for a user
        
        Args:
            email: User's email
        
        Returns:
            Password reset token if user exists
        """
        user = await UserModel.find_one(UserModel.email == email)
        if not user:
            return None
        
        return create_password_reset_token(str(user.id))
    
    @staticmethod
    async def reset_password(token: str, new_password: str) -> bool:
        """
        Reset a user's password using a reset token
        
        Args:
            token: Password reset token
            new_password: New password
        
        Returns:
            True if successful
        
        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = decode_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token"
            )
        
        if payload.get("type") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )
        
        user = await UserModel.get(payload["sub"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password
        user.hashed_password = AuthService.hash_password(new_password)
        user.last_password_change = datetime.now(timezone.utc)
        
        # Reset security flags
        user.failed_login_attempts = 0
        user.locked_until = None
        
        await user.save()
        
        # Revoke all refresh tokens for security
        await AuthService.logout_all_devices(str(user.id))
        
        return True
    
    @staticmethod
    async def verify_email(token: str) -> bool:
        """
        Verify a user's email address
        
        Args:
            token: Email verification token
        
        Returns:
            True if successful
        
        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = decode_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email verification token"
            )
        
        if payload.get("type") != "email_verification":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )
        
        user = await UserModel.get(payload["sub"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify the email matches
        if user.email != payload.get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email mismatch"
            )
        
        user.email_verified = True
        await user.save()
        
        return True