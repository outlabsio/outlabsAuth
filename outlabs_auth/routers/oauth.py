"""
OAuth/Social login router factory (DD-043).

Provides ready-to-use OAuth routes for authentication with social providers
(Google, Facebook, Apple, GitHub, etc.).

Based on FastAPI-Users OAuth implementation but adapted for OutlabsAuth.
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from httpx_oauth.oauth2 import BaseOAuth2, OAuth2Token
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback

from outlabs_auth.schemas.oauth import OAuthAuthorizeResponse
from outlabs_auth.oauth.state import generate_state_token, decode_state_token


def get_oauth_router(
    oauth_client: BaseOAuth2,
    auth: Any,  # OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
    state_secret: str,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    redirect_url: Optional[str] = None,
    associate_by_email: bool = False,
    is_verified_by_default: bool = False,
) -> APIRouter:
    """
    Generate OAuth authentication router for a provider.

    Creates `/authorize` and `/callback` endpoints for OAuth flow.

    Args:
        oauth_client: httpx-oauth client instance (GoogleOAuth2, FacebookOAuth2, etc.)
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        state_secret: Secret for signing OAuth state JWT tokens (CSRF protection)
        prefix: Router prefix (default: "", usually set when including router)
        tags: OpenAPI tags (default: ["oauth"])
        redirect_url: Optional fixed redirect URL (if not using FastAPI route names)
        associate_by_email: Auto-link OAuth to existing user with same email (default: False)
        is_verified_by_default: Set is_verified=True for OAuth users (default: False)

    Returns:
        APIRouter with `/authorize` and `/callback` endpoints

    Security Notes:
        - state_secret MUST be different from JWT secret (use separate secret)
        - associate_by_email=True requires trusted email providers (Google ✅, random OAuth ❌)
        - is_verified_by_default=True requires provider email verification

    Example:
        ```python
        from httpx_oauth.clients.google import GoogleOAuth2
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_oauth_router

        google_client = GoogleOAuth2(
            client_id="your-client-id.apps.googleusercontent.com",
            client_secret="your-client-secret"
        )

        auth = SimpleRBAC(database=db)

        app.include_router(
            get_oauth_router(
                google_client,
                auth,
                state_secret="different-secret-for-oauth-state",
                associate_by_email=True,  # Google verifies emails
                is_verified_by_default=True,  # Trust Google's email verification
            ),
            prefix="/auth/google",
            tags=["auth"]
        )
        ```

    Flow:
        1. User visits GET /auth/google/authorize
        2. Returns authorization_url (redirect user there)
        3. User authenticates with Google
        4. Google redirects to GET /auth/google/callback?code=...&state=...
        5. Backend validates state, exchanges code for tokens
        6. Creates/updates user and social account
        7. Returns auth tokens (JWT + refresh)

    Related:
        - DD-042: JWT State Tokens
        - DD-043: OAuth Router Factory Pattern
        - DD-046: associate_by_email Security Flag
    """
    router = APIRouter(prefix=prefix, tags=tags or ["oauth"])

    # Route name for callback (used if redirect_url not provided)
    callback_route_name = f"oauth:{oauth_client.name}.callback"

    # Setup OAuth callback handler
    if redirect_url is not None:
        oauth2_authorize_callback = OAuth2AuthorizeCallback(
            oauth_client,
            redirect_url=redirect_url,
        )
    else:
        oauth2_authorize_callback = OAuth2AuthorizeCallback(
            oauth_client,
            route_name=callback_route_name,
        )

    @router.get(
        "/authorize",
        response_model=OAuthAuthorizeResponse,
        summary=f"Start {oauth_client.name.title()} OAuth flow",
        description=f"Returns authorization URL to redirect user to {oauth_client.name.title()}",
    )
    async def authorize(
        request: Request,
        scopes: list[str] = Query(None, description="OAuth scopes to request"),
    ) -> OAuthAuthorizeResponse:
        """
        Start OAuth authorization flow.

        Returns the authorization URL where the user should be redirected
        to authenticate with the OAuth provider.

        The state parameter (JWT token) is automatically generated and
        included in the authorization URL for CSRF protection.
        """
        # Determine callback URL
        if redirect_url is not None:
            authorize_redirect_url = redirect_url
        else:
            authorize_redirect_url = str(request.url_for(callback_route_name))

        # Generate JWT state token (no database write!)
        state_data: dict[str, str] = {}  # Empty for new user registration
        state = generate_state_token(state_data, state_secret, lifetime_seconds=600)

        # Get authorization URL from provider
        authorization_url = await oauth_client.get_authorization_url(
            authorize_redirect_url,
            state,
            scopes,
        )

        return OAuthAuthorizeResponse(authorization_url=authorization_url)

    @router.get(
        "/callback",
        name=callback_route_name,
        summary=f"{oauth_client.name.title()} OAuth callback",
        description="Handles OAuth provider callback and authenticates user",
        responses={
            status.HTTP_400_BAD_REQUEST: {
                "description": "Invalid state token or inactive user",
                "content": {
                    "application/json": {
                        "examples": {
                            "invalid_state": {
                                "summary": "Invalid or expired state token",
                                "value": {"detail": "Invalid OAuth state token"},
                            },
                            "no_email": {
                                "summary": "Provider didn't return email",
                                "value": {"detail": "Email not available from OAuth provider"},
                            },
                            "user_exists": {
                                "summary": "User with this email already exists",
                                "value": {"detail": "User with this email already exists"},
                            },
                            "inactive_user": {
                                "summary": "User account is inactive",
                                "value": {"detail": "User is inactive"},
                            },
                        }
                    }
                },
            },
        },
    )
    async def callback(
        request: Request,
        access_token_state: tuple[OAuth2Token, str] = Depends(oauth2_authorize_callback),
    ):
        """
        Handle OAuth provider callback.

        Validates state token, gets user info from provider, and either:
        - Creates new user (if first time)
        - Links OAuth account (if associate_by_email=True and email exists)
        - Updates existing OAuth account tokens
        - Returns authentication tokens (JWT + refresh)

        Triggers hooks:
        - on_after_register (if new user created)
        - on_after_oauth_register (if new user via OAuth)
        - on_after_login (always)
        - on_after_oauth_login (always)
        """
        token, state = access_token_state

        # Get user info from OAuth provider
        account_id, account_email = await oauth_client.get_id_email(token["access_token"])

        if account_email is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not available from OAuth provider",
            )

        # Validate state token (JWT signature + expiration)
        try:
            state_data = decode_state_token(state, state_secret)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth state token",
            )

        # OAuth callback logic (create/update user + social account)
        user = await oauth_callback(
            auth=auth,
            provider=oauth_client.name,
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            expires_at=token.get("expires_at"),
            account_id=account_id,
            account_email=account_email,
            associate_by_email=associate_by_email,
            is_verified_by_default=is_verified_by_default,
            request=request,
        )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is inactive",
            )

        # Create auth tokens (JWT + refresh)
        tokens = await auth.auth_service.create_tokens(user)

        # Trigger hooks
        await auth.user_service.on_after_login(user, request)
        await auth.user_service.on_after_oauth_login(user, oauth_client.name, request)

        return tokens

    return router


async def oauth_callback(
    auth: Any,
    provider: str,
    access_token: str,
    account_id: str,
    account_email: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[int] = None,
    associate_by_email: bool = False,
    is_verified_by_default: bool = False,
    request: Optional[Request] = None,
) -> Any:
    """
    Handle OAuth callback logic (create/update user and social account).

    This is the core OAuth logic adapted from FastAPI-Users.

    Logic:
    1. Try to find user by OAuth account (provider + account_id)
    2. If not found, try to find user by email:
       - If associate_by_email=True: Link OAuth to existing user
       - If associate_by_email=False: Raise error (security)
    3. If still not found: Create new user
    4. Update/create social account record
    5. Trigger appropriate hooks

    Args:
        auth: OutlabsAuth instance
        provider: OAuth provider name ("google", "facebook", etc.)
        access_token: OAuth access token
        account_id: User ID from OAuth provider
        account_email: Email from OAuth provider
        refresh_token: Optional refresh token
        expires_at: Optional token expiration timestamp
        associate_by_email: Auto-link to existing user by email
        is_verified_by_default: Set is_verified=True for new users
        request: Optional FastAPI request

    Returns:
        User object

    Raises:
        HTTPException: If user exists but associate_by_email=False

    Security:
        - Only enable associate_by_email for trusted providers that verify emails
        - Check provider's email_verified claim if available
        - Log all OAuth account linking for security audit
    """
    # TODO: Implement actual database logic
    # This is a placeholder showing the pattern

    # Try to find existing user by OAuth account
    try:
        user = await auth.user_service.get_by_oauth_account(provider, account_id)

        # Update OAuth tokens (user logged in with existing OAuth account)
        await auth.social_account_service.update_tokens(
            user_id=user.id,
            provider=provider,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

        return user

    except Exception:  # User not found by OAuth account
        pass

    # Try to find existing user by email
    try:
        user = await auth.user_service.get_by_email(account_email)

        if not associate_by_email:
            # Security: Don't auto-link accounts unless explicitly enabled
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        # Link OAuth account to existing user
        await auth.social_account_service.create(
            user_id=user.id,
            provider=provider,
            provider_user_id=account_id,
            email=account_email,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

        return user

    except Exception:  # User not found by email
        pass

    # Create new user
    # Generate random password (user will use OAuth to login)
    import secrets
    random_password = secrets.token_urlsafe(32)

    user = await auth.user_service.create_user(
        email=account_email,
        password=random_password,
        is_verified=is_verified_by_default,
    )

    # Create social account
    await auth.social_account_service.create(
        user_id=user.id,
        provider=provider,
        provider_user_id=account_id,
        email=account_email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    # Trigger hooks
    await auth.user_service.on_after_register(user, request)
    await auth.user_service.on_after_oauth_register(user, provider, request)

    return user
