"""
JWT-based OAuth state token management (DD-042).

Instead of storing OAuth state in the database, we use signed JWT tokens
for CSRF protection. This eliminates database writes and makes OAuth flows
completely stateless.

Key advantages:
- No database writes (faster, simpler)
- Stateless (works across load balancers without sticky sessions)
- Self-expiring (JWT exp claim)
- Tamper-proof (JWT signature)
"""

from typing import Dict, Any, Optional, Union
import jwt
from datetime import datetime, timedelta

STATE_TOKEN_AUDIENCE = "outlabs-auth:oauth-state"


def generate_state_token(
    data: Optional[Dict[str, Any]] = None,
    secret: Union[str, bytes] = None,
    lifetime_seconds: int = 600,  # 10 minutes
    algorithm: str = "HS256"
) -> str:
    """
    Generate a signed JWT token for OAuth state (CSRF protection).

    This token is used instead of database records for OAuth flow state.
    The state parameter is included in the authorization URL and validated
    in the callback to prevent CSRF attacks.

    Args:
        data: Optional data to embed in the token (e.g., {"user_id": "123"} for account linking)
        secret: JWT signing secret
        lifetime_seconds: Token lifetime in seconds (default: 10 minutes)
        algorithm: JWT signing algorithm (default: HS256)

    Returns:
        Signed JWT token string

    Example:
        ```python
        # New user registration (no user_id)
        state = generate_state_token({}, secret)

        # Account linking (include user_id)
        state = generate_state_token({"user_id": str(user.id)}, secret)

        # Custom redirect
        state = generate_state_token({"redirect_uri": "/dashboard"}, secret)
        ```

    Related:
        - DD-042: JWT State Tokens for OAuth Flow
        - Uses same JWT library as auth tokens (python-jose)
    """
    if secret is None:
        raise ValueError("secret is required for OAuth state tokens")

    payload = data.copy() if data else {}

    # Add standard JWT claims
    now = datetime.utcnow()
    payload.update({
        "aud": STATE_TOKEN_AUDIENCE,  # Audience claim (prevents token reuse)
        "iat": now,  # Issued at
        "exp": now + timedelta(seconds=lifetime_seconds),  # Expiration
    })

    # Sign the token
    token = jwt.encode(payload, secret, algorithm=algorithm)

    return token


def decode_state_token(
    token: str,
    secret: Union[str, bytes] = None,
    algorithms: list[str] = None
) -> Dict[str, Any]:
    """
    Decode and validate an OAuth state JWT token.

    Validates:
    - Signature (prevents tampering)
    - Expiration (prevents replay attacks)
    - Audience (prevents token reuse from other contexts)

    Args:
        token: The JWT state token from the callback
        secret: JWT signing secret (must match the one used to generate)
        algorithms: Allowed algorithms (default: ["HS256"])

    Returns:
        Decoded token payload (dict)

    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidSignatureError: Token signature is invalid (tampering detected)
        jwt.InvalidAudienceError: Token audience doesn't match
        jwt.InvalidTokenError: Other token validation errors

    Example:
        ```python
        try:
            state_data = decode_state_token(state, secret)
            user_id = state_data.get("user_id")  # For account linking
            redirect_uri = state_data.get("redirect_uri")  # Custom redirect
        except jwt.ExpiredSignatureError:
            raise HTTPException(400, "OAuth state expired, please try again")
        except jwt.InvalidTokenError:
            raise HTTPException(400, "Invalid OAuth state token")
        ```

    Security:
        - Always validate the user_id matches the authenticated user (for account linking)
        - Never trust client-provided data - validate against database
        - Short expiration (10 min) prevents long-term replay attacks

    Related:
        - DD-042: JWT State Tokens for OAuth Flow
        - Replaces database-based OAuthState model
    """
    if secret is None:
        raise ValueError("secret is required for OAuth state token validation")

    if algorithms is None:
        algorithms = ["HS256"]

    # Decode and validate the token
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=algorithms,
            audience=STATE_TOKEN_AUDIENCE,  # Validate audience
            options={
                "require_exp": True,  # Require expiration
                "require_iat": True,  # Require issued at
                "verify_exp": True,  # Verify not expired
                "verify_aud": True,  # Verify audience
            }
        )
        return payload
    except jwt.ExpiredSignatureError:
        # Token expired - user took too long to complete OAuth flow
        raise
    except jwt.InvalidAudienceError:
        # Wrong audience - possible token reuse attack
        raise
    except jwt.InvalidSignatureError:
        # Signature invalid - possible tampering
        raise
    except jwt.InvalidTokenError:
        # Other validation errors
        raise
