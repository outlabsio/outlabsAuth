"""
JWT Token Management Utilities
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import secrets
from jose import jwt, JWTError
from api.config import settings


class TokenPayload:
    """Structured token payload for type safety"""
    def __init__(
        self,
        sub: str,  # user_id
        email: str,
        platform_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        permissions: Optional[list[str]] = None,
        token_type: str = "access",
        family_id: Optional[str] = None,
        device_id: Optional[str] = None
    ):
        self.sub = sub
        self.email = email
        self.platform_id = platform_id
        self.entity_id = entity_id
        self.permissions = permissions or []
        self.token_type = token_type
        self.family_id = family_id
        self.device_id = device_id


def create_access_token(
    payload: TokenPayload,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token
    
    Args:
        payload: Token payload with user data
        expires_delta: Token expiration time
    
    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": payload.sub,
        "email": payload.email,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16)  # JWT ID for revocation
    }
    
    # Add optional fields
    if payload.platform_id:
        to_encode["platform_id"] = payload.platform_id
    if payload.entity_id:
        to_encode["entity_id"] = payload.entity_id
    if payload.permissions:
        to_encode["permissions"] = payload.permissions
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    payload: TokenPayload,
    family_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:
    """
    Create a JWT refresh token with family ID for rotation
    
    Args:
        payload: Token payload with user data
        family_id: Token family ID for rotation tracking
        expires_delta: Token expiration time
    
    Returns:
        Tuple of (token, family_id)
    """
    if not family_id:
        family_id = secrets.token_urlsafe(16)
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "sub": payload.sub,
        "email": payload.email,
        "type": "refresh",
        "family_id": family_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16)
    }
    
    # Add device ID if provided
    if payload.device_id:
        to_encode["device_id"] = payload.device_id
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt, family_id


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token
    
    Args:
        token: JWT token to decode
    
    Returns:
        Decoded token payload
    
    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise


def create_api_key() -> str:
    """
    Generate a secure API key for server-to-server authentication
    
    Returns:
        Secure random API key
    """
    return f"sk_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage
    
    Args:
        api_key: Plain text API key
    
    Returns:
        Hashed API key
    """
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_password_reset_token(user_id: str) -> str:
    """
    Create a short-lived token for password reset
    
    Args:
        user_id: User ID for the reset
    
    Returns:
        Encoded JWT token
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode = {
        "sub": user_id,
        "type": "password_reset",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16)
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_email_verification_token(user_id: str, email: str) -> str:
    """
    Create a token for email verification
    
    Args:
        user_id: User ID
        email: Email to verify
    
    Returns:
        Encoded JWT token
    """
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {
        "sub": user_id,
        "email": email,
        "type": "email_verification",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16)
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt