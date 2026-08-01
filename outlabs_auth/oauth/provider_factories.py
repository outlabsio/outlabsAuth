"""
OAuth provider factory (DD-045).

Pre-configured OAuth clients for popular providers using httpx-oauth library.

Supports:
- Google
- Facebook
- Apple
- GitHub
- Microsoft
- Discord
- And more via httpx-oauth

Based on httpx-oauth library (https://frankie567.github.io/httpx-oauth/)
"""

from typing import Optional

# Import from httpx-oauth (optional dependency)
try:
    from httpx_oauth.clients.google import GoogleOAuth2
    from httpx_oauth.clients.facebook import FacebookOAuth2
    from httpx_oauth.clients.github import GitHubOAuth2
    from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
    from httpx_oauth.clients.discord import DiscordOAuth2
    from httpx_oauth.oauth2 import BaseOAuth2

    HTTPX_OAUTH_AVAILABLE = True
except ImportError:
    HTTPX_OAUTH_AVAILABLE = False
    BaseOAuth2 = None  # type: ignore


def get_google_client(
    client_id: str,
    client_secret: str,
    scopes: Optional[list[str]] = None,
) -> "GoogleOAuth2":
    """
    Get Google OAuth2 client.

    Args:
        client_id: Google OAuth2 client ID (from Google Cloud Console)
        client_secret: Google OAuth2 client secret
        scopes: Optional custom scopes (default: ["openid", "email", "profile"])

    Returns:
        GoogleOAuth2 client instance

    Setup:
        1. Go to https://console.cloud.google.com/
        2. Create project
        3. Enable Google+ API
        4. Create OAuth 2.0 credentials
        5. Add authorized redirect URI: http://localhost:8000/auth/google/callback

    Example:
        ```python
        from outlabs_auth.oauth.providers import get_google_client
        from outlabs_auth.routers import get_oauth_router

        google = get_google_client(
            client_id="123.apps.googleusercontent.com",
            client_secret="secret"
        )

        app.include_router(
            get_oauth_router(google, auth, state_secret),
            prefix="/auth/google",
            tags=["auth"]
        )
        ```

    Security Notes:
        - Google verifies emails → Safe to use associate_by_email=True
        - Google returns email_verified claim → Safe for is_verified_by_default=True
        - Always use HTTPS in production redirect URIs
    """
    if not HTTPX_OAUTH_AVAILABLE:
        raise ImportError(
            "httpx-oauth is required for OAuth support. "
            "Install with: pip install outlabs-auth[oauth]"
        )

    return GoogleOAuth2(
        client_id,
        client_secret,
        scopes=scopes or ["openid", "email", "profile"],
    )


def get_facebook_client(
    client_id: str,
    client_secret: str,
    scopes: Optional[list[str]] = None,
) -> "FacebookOAuth2":
    """
    Get Facebook OAuth2 client.

    Args:
        client_id: Facebook App ID
        client_secret: Facebook App Secret
        scopes: Optional custom scopes (default: ["email", "public_profile"])

    Returns:
        FacebookOAuth2 client instance

    Setup:
        1. Go to https://developers.facebook.com/
        2. Create app
        3. Add Facebook Login product
        4. Add redirect URI: http://localhost:8000/auth/facebook/callback

    Security Notes:
        - Facebook verifies emails → Safe to use associate_by_email=True
        - Always use HTTPS in production
    """
    if not HTTPX_OAUTH_AVAILABLE:
        raise ImportError(
            "httpx-oauth is required for OAuth support. "
            "Install with: pip install outlabs-auth[oauth]"
        )

    return FacebookOAuth2(
        client_id,
        client_secret,
        scopes=scopes or ["email", "public_profile"],
    )


def get_github_client(
    client_id: str,
    client_secret: str,
    scopes: Optional[list[str]] = None,
) -> "GitHubOAuth2":
    """
    Get GitHub OAuth2 client.

    Args:
        client_id: GitHub OAuth App Client ID
        client_secret: GitHub OAuth App Client Secret
        scopes: Optional custom scopes (default: ["user:email"])

    Returns:
        GitHubOAuth2 client instance

    Setup:
        1. Go to https://github.com/settings/developers
        2. Create OAuth App
        3. Add redirect URI: http://localhost:8000/auth/github/callback

    Security Notes:
        - GitHub verifies primary email → Safe to use associate_by_email=True
        - Request "user:email" scope to get verified email
    """
    if not HTTPX_OAUTH_AVAILABLE:
        raise ImportError(
            "httpx-oauth is required for OAuth support. "
            "Install with: pip install outlabs-auth[oauth]"
        )

    return GitHubOAuth2(
        client_id,
        client_secret,
        scopes=scopes or ["user:email"],
    )


def get_microsoft_client(
    client_id: str,
    client_secret: str,
    tenant: str = "common",
    scopes: Optional[list[str]] = None,
) -> "MicrosoftGraphOAuth2":
    """
    Get Microsoft (Azure AD / Microsoft 365) OAuth2 client.

    Args:
        client_id: Microsoft Application (client) ID
        client_secret: Microsoft Client Secret
        tenant: Azure AD tenant ID or "common" (default: "common")
        scopes: Optional custom scopes (default: ["User.Read"])

    Returns:
        MicrosoftGraphOAuth2 client instance

    Setup:
        1. Go to https://portal.azure.com/
        2. Azure Active Directory → App registrations → New registration
        3. Add redirect URI: http://localhost:8000/auth/microsoft/callback
        4. Certificates & secrets → New client secret

    Security Notes:
        - Microsoft verifies emails → Safe to use associate_by_email=True
        - Use specific tenant ID for better security (not "common")
    """
    if not HTTPX_OAUTH_AVAILABLE:
        raise ImportError(
            "httpx-oauth is required for OAuth support. "
            "Install with: pip install outlabs-auth[oauth]"
        )

    return MicrosoftGraphOAuth2(
        client_id,
        client_secret,
        tenant=tenant,
        scopes=scopes or ["User.Read"],
    )


def get_discord_client(
    client_id: str,
    client_secret: str,
    scopes: Optional[list[str]] = None,
) -> "DiscordOAuth2":
    """
    Get Discord OAuth2 client.

    Args:
        client_id: Discord Application Client ID
        client_secret: Discord Application Client Secret
        scopes: Optional custom scopes (default: ["identify", "email"])

    Returns:
        DiscordOAuth2 client instance

    Setup:
        1. Go to https://discord.com/developers/applications
        2. Create application
        3. OAuth2 → Add redirect: http://localhost:8000/auth/discord/callback

    Security Notes:
        - Discord verifies emails → Safe to use associate_by_email=True
        - Require "email" scope to get email address
    """
    if not HTTPX_OAUTH_AVAILABLE:
        raise ImportError(
            "httpx-oauth is required for OAuth support. "
            "Install with: pip install outlabs-auth[oauth]"
        )

    return DiscordOAuth2(
        client_id,
        client_secret,
        scopes=scopes or ["identify", "email"],
    )
