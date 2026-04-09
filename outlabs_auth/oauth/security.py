"""Security utilities for OAuth flows (PKCE, state, nonce)."""

import base64
import hashlib
import secrets
from typing import Optional, Tuple


def generate_state() -> str:
    """
    Generate secure random state parameter for CSRF protection.
    
    Returns:
        Random URL-safe string (32 bytes = 43 chars base64)
    """
    return secrets.token_urlsafe(32)


def generate_nonce() -> str:
    """
    Generate secure random nonce for OpenID Connect.
    
    Used to prevent replay attacks in ID tokens.
    
    Returns:
        Random URL-safe string (32 bytes = 43 chars base64)
    """
    return secrets.token_urlsafe(32)


def generate_pkce_pair(method: str = "S256") -> Tuple[str, str]:
    """
    Generate PKCE code verifier and challenge.
    
    PKCE (Proof Key for Code Exchange) prevents authorization code
    interception attacks.
    
    Args:
        method: Challenge method - "S256" (SHA256) or "plain"
    
    Returns:
        Tuple of (code_verifier, code_challenge)
    
    Raises:
        ValueError: If method is not "S256" or "plain"
    """
    if method not in ("S256", "plain"):
        raise ValueError("PKCE method must be 'S256' or 'plain'")
    
    # Generate code verifier (43-128 chars, we use 43)
    code_verifier = secrets.token_urlsafe(32)  # 32 bytes = 43 chars
    
    # Generate code challenge
    if method == "S256":
        # SHA256 hash of verifier, base64-url-encoded
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = (
            base64.urlsafe_b64encode(digest)
            .decode()
            .rstrip("=")  # Remove padding
        )
    else:
        # Plain method: challenge = verifier
        code_challenge = code_verifier
    
    return code_verifier, code_challenge


def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """
    Verify PKCE code verifier matches challenge.
    
    Args:
        code_verifier: Code verifier from callback
        code_challenge: Stored code challenge
        method: Challenge method used
    
    Returns:
        True if verifier matches challenge
    """
    if method == "S256":
        # Recompute challenge from verifier
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed_challenge = (
            base64.urlsafe_b64encode(digest)
            .decode()
            .rstrip("=")
        )
        return secrets.compare_digest(computed_challenge, code_challenge)
    else:
        # Plain method: verifier should equal challenge
        return secrets.compare_digest(code_verifier, code_challenge)


def build_authorization_url(
    base_url: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    response_type: str = "code",
    code_challenge: Optional[str] = None,
    code_challenge_method: str = "S256",
    nonce: Optional[str] = None,
    **extra_params
) -> str:
    """
    Build OAuth authorization URL with all parameters.
    
    Args:
        base_url: Provider's authorization endpoint
        client_id: OAuth client ID
        redirect_uri: Where to redirect after authorization
        scope: Space-separated scopes
        state: State parameter for CSRF protection
        response_type: OAuth response type (default: "code")
        code_challenge: PKCE code challenge (optional)
        code_challenge_method: PKCE method (default: "S256")
        nonce: OpenID Connect nonce (optional)
        **extra_params: Additional provider-specific parameters
    
    Returns:
        Complete authorization URL
    """
    from urllib.parse import urlencode
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "scope": scope,
        "state": state,
    }
    
    # Add PKCE if provided
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = code_challenge_method
    
    # Add nonce for OpenID Connect
    if nonce:
        params["nonce"] = nonce
    
    # Add any extra parameters
    params.update(extra_params)
    
    # Build URL
    query_string = urlencode(params)
    return f"{base_url}?{query_string}"


def constant_time_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.
    
    Use this for comparing secrets (state, nonce, etc.).
    
    Args:
        a: First string
        b: Second string
    
    Returns:
        True if strings are equal
    """
    return secrets.compare_digest(a, b)
