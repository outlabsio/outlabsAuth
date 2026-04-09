"""
JWT token creation and verification utilities

Uses python-jose for JWT operations with configurable algorithm and expiration.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast

from jose import JWTError, jwt

from outlabs_auth.core.exceptions import TokenInvalidError, TokenExpiredError


def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: Optional[timedelta] = None,
    audience: str = "outlabs-auth",
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        secret_key: Secret key for signing
        algorithm: JWT algorithm (default: HS256)
        expires_delta: Token expiration time (default: 15 minutes)
        audience: JWT audience claim for cross-application security (default: "outlabs-auth")

    Returns:
        str: Encoded JWT token

    Example:
        >>> token = create_access_token(
        ...     data={"sub": "user_id_123"},
        ...     secret_key="my-secret-key",
        ...     audience="my-app"
        ... )
        >>> # Token is valid for 15 minutes by default
    """
    to_encode = data.copy()

    issued_at = datetime.now(timezone.utc)

    # Set expiration time
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(minutes=15)

    # Generate unique JWT ID for blacklist support
    jti = secrets.token_urlsafe(16)

    to_encode.update({
        "exp": expire,
        "iat": issued_at,  # Issued at
        "iat_ms": int(issued_at.timestamp() * 1000),
        "type": "access",
        "aud": audience,  # Audience claim for cross-application security
        "jti": jti  # JWT ID for token revocation/blacklisting
    })

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return cast(str, encoded_jwt)


def create_refresh_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: Optional[timedelta] = None,
    audience: str = "outlabs-auth",
) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Payload data to encode in the token
        secret_key: Secret key for signing
        algorithm: JWT algorithm (default: HS256)
        expires_delta: Token expiration time (default: 30 days)
        audience: JWT audience claim for cross-application security (default: "outlabs-auth")

    Returns:
        str: Encoded JWT refresh token

    Example:
        >>> token = create_refresh_token(
        ...     data={"sub": "user_id_123"},
        ...     secret_key="my-secret-key",
        ...     audience="my-app"
        ... )
        >>> # Token is valid for 30 days by default
    """
    to_encode = data.copy()

    issued_at = datetime.now(timezone.utc)

    # Set expiration time
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(days=30)

    # Generate unique JWT ID for each refresh token (prevents token collisions)
    jti = secrets.token_urlsafe(16)

    to_encode.update({
        "exp": expire,
        "iat": issued_at,
        "iat_ms": int(issued_at.timestamp() * 1000),
        "type": "refresh",
        "aud": audience,  # Audience claim for cross-application security
        "jti": jti  # JWT ID ensures each token is unique
    })

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return cast(str, encoded_jwt)


def verify_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
    expected_type: Optional[str] = None,
    audience: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token to verify
        secret_key: Secret key for verification
        algorithm: JWT algorithm (default: HS256)
        expected_type: Expected token type ("access" or "refresh")
        audience: Expected JWT audience (if None, audience is not validated)

    Returns:
        Dict[str, Any]: Decoded token payload

    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid or malformed

    Example:
        >>> token = create_access_token({"sub": "user_123"}, "secret", audience="my-app")
        >>> payload = verify_token(token, "secret", expected_type="access", audience="my-app")
        >>> payload["sub"]
        'user_123'
    """
    try:
        # Decode with or without audience validation
        decode_options: dict[str, Any] = {"algorithms": [algorithm]}
        if audience:
            decode_options["audience"] = audience
            payload = jwt.decode(token, secret_key, **decode_options)
        else:
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Check token type if specified
        if expected_type:
            token_type = payload.get("type")
            if token_type != expected_type:
                raise TokenInvalidError(
                    message=f"Invalid token type: expected {expected_type}, got {token_type}",
                    details={"expected_type": expected_type, "actual_type": token_type}
                )

        return cast(Dict[str, Any], payload)

    except jwt.ExpiredSignatureError:
        raise TokenExpiredError(
            message="Token has expired",
            details={"token_expired": True}
        )
    except JWTError as e:
        raise TokenInvalidError(
            message=f"Invalid token: {str(e)}",
            details={"jwt_error": str(e)}
        )


def decode_token_without_verification(token: str) -> Dict[str, Any]:
    """
    Decode token without verifying signature (for inspection only).

    WARNING: This does not validate the token! Only use for debugging or
    extracting claims when you don't care about verification.

    Args:
        token: JWT token to decode

    Returns:
        Dict[str, Any]: Decoded token payload (unverified)

    Example:
        >>> token = create_access_token({"sub": "user_123"}, "secret")
        >>> payload = decode_token_without_verification(token)
        >>> payload["sub"]  # Returns data without verifying signature
        'user_123'
    """
    try:
        return cast(Dict[str, Any], jwt.get_unverified_claims(token))
    except JWTError as e:
        raise TokenInvalidError(
            message=f"Cannot decode token: {str(e)}",
            details={"jwt_error": str(e)}
        )


def get_token_expiration(token: str) -> Optional[datetime]:
    """
    Get expiration time from token without verification.

    Args:
        token: JWT token

    Returns:
        Optional[datetime]: Expiration datetime in UTC, or None if not set

    Example:
        >>> token = create_access_token({"sub": "user_123"}, "secret")
        >>> exp = get_token_expiration(token)
        >>> isinstance(exp, datetime)
        True
    """
    try:
        payload = decode_token_without_verification(token)
        exp_timestamp = payload.get("exp")

        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        return None
    except TokenInvalidError:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired without full verification.

    Args:
        token: JWT token

    Returns:
        bool: True if token is expired, False otherwise

    Example:
        >>> token = create_access_token({"sub": "user_123"}, "secret")
        >>> is_token_expired(token)
        False
    """
    exp = get_token_expiration(token)
    if not exp:
        return False

    return datetime.now(timezone.utc) > exp


def create_token_pair(
    user_id: str,
    secret_key: str,
    algorithm: str = "HS256",
    access_token_expire_minutes: int = 15,
    refresh_token_expire_days: int = 30,
    additional_claims: Optional[Dict[str, Any]] = None,
    audience: str = "outlabs-auth",
) -> tuple[str, str]:
    """
    Create both access and refresh tokens for a user.

    Args:
        user_id: User ID to encode in tokens
        secret_key: Secret key for signing
        algorithm: JWT algorithm
        access_token_expire_minutes: Access token TTL in minutes
        refresh_token_expire_days: Refresh token TTL in days
        additional_claims: Additional data to include in tokens
        audience: JWT audience claim for cross-application security (default: "outlabs-auth")

    Returns:
        tuple[str, str]: (access_token, refresh_token)

    Example:
        >>> access, refresh = create_token_pair(
        ...     user_id="user_123",
        ...     secret_key="my-secret",
        ...     audience="my-app"
        ... )
        >>> # access token valid for 15 min, refresh for 30 days
    """
    # Base payload
    base_data = {"sub": user_id}
    if additional_claims:
        base_data.update(additional_claims)

    # Create access token
    access_token = create_access_token(
        data=base_data,
        secret_key=secret_key,
        algorithm=algorithm,
        expires_delta=timedelta(minutes=access_token_expire_minutes),
        audience=audience,
    )

    # Create refresh token
    refresh_token = create_refresh_token(
        data={"sub": user_id},  # Refresh token only needs user ID
        secret_key=secret_key,
        algorithm=algorithm,
        expires_delta=timedelta(days=refresh_token_expire_days),
        audience=audience,
    )

    return access_token, refresh_token
