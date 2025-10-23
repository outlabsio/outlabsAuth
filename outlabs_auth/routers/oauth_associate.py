"""
OAuth account association router for authenticated users (DD-044).

Allows authenticated users to link additional OAuth providers to their account.
This enables users to login with multiple methods (password + Google + GitHub, etc.).

Security: State token includes user_id to prevent account hijacking.
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from httpx_oauth.oauth2 import BaseOAuth2, OAuth2Token
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback

from outlabs_auth.schemas.oauth import OAuthAuthorizeResponse, SocialAccountResponse
from outlabs_auth.oauth.state import generate_state_token, decode_state_token


def get_oauth_associate_router(
    oauth_client: BaseOAuth2,
    auth: Any,  # OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
    state_secret: str,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    redirect_url: Optional[str] = None,
    requires_verification: bool = False,
) -> APIRouter:
    """
    Generate OAuth account association router for authenticated users.

    Creates `/authorize` and `/callback` endpoints for linking OAuth accounts
    to existing user accounts.

    Args:
        oauth_client: httpx-oauth client instance (GoogleOAuth2, FacebookOAuth2, etc.)
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        state_secret: Secret for signing OAuth state JWT tokens (CSRF protection)
        prefix: Router prefix (default: "", usually set when including router)
        tags: OpenAPI tags (default: ["oauth"])
        redirect_url: Optional fixed redirect URL (if not using FastAPI route names)
        requires_verification: Require verified email to link accounts (default: False)

    Returns:
        APIRouter with `/authorize` and `/callback` endpoints

    Security Notes:
        - State token MUST include user_id to prevent account hijacking
        - Validates that callback state matches authenticated user
        - Requires active user (enforced by auth.deps.require_auth())
        - Optional email verification requirement

    Example:
        ```python
        from httpx_oauth.clients.google import GoogleOAuth2
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_oauth_associate_router

        google_client = GoogleOAuth2(
            client_id="your-client-id.apps.googleusercontent.com",
            client_secret="your-client-secret"
        )

        auth = SimpleRBAC(database=db)

        # Authenticated users can link Google account
        app.include_router(
            get_oauth_associate_router(
                google_client,
                auth,
                state_secret="different-secret-for-oauth-state",
                requires_verification=True,  # Only verified users can link
            ),
            prefix="/auth/associate/google",
            tags=["auth"]
        )
        ```

    Flow:
        1. Authenticated user visits GET /auth/associate/google/authorize
        2. Returns authorization_url with state containing user_id
        3. User authenticates with Google
        4. Google redirects to GET /auth/associate/google/callback
        5. Backend validates state user_id matches authenticated user
        6. Links OAuth account to user
        7. Returns updated user with new oauth_accounts

    Use Cases:
        - User registered with email/password, wants to add Google login
        - User has Google login, wants to add GitHub login
        - User wants backup authentication methods
        - User wants to unify accounts across providers

    Related:
        - DD-042: JWT State Tokens
        - DD-044: OAuth Associate Router
        - Prevents account hijacking by validating user_id in state
    """
    router = APIRouter(prefix=prefix, tags=tags or ["oauth"])

    # Get dependency for authenticated user
    get_current_user = auth.deps.require_auth(
        active=True,
        verified=requires_verification
    )

    # Route name for callback
    callback_route_name = f"oauth-associate:{oauth_client.name}.callback"

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
        summary=f"Link {oauth_client.name.title()} account",
        description=f"Start OAuth flow to link {oauth_client.name.title()} to your account",
    )
    async def authorize(
        request: Request,
        auth_context = Depends(get_current_user),
        scopes: list[str] = Query(None, description="OAuth scopes to request"),
    ) -> OAuthAuthorizeResponse:
        """
        Start OAuth association flow for authenticated user.

        Returns the authorization URL where the user should be redirected
        to authenticate with the OAuth provider and link their account.

        The state parameter includes the user_id to prevent account hijacking.

        Security:
            - Requires authenticated user (JWT token)
            - State token includes user_id for validation in callback
            - User_id is verified in callback to prevent hijacking
        """
        user_id = auth_context.get("user_id")

        # Determine callback URL
        if redirect_url is not None:
            authorize_redirect_url = redirect_url
        else:
            authorize_redirect_url = str(request.url_for(callback_route_name))

        # Generate JWT state token WITH user_id (security!)
        state_data = {"sub": user_id}  # Include user_id for validation
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
        response_model=SocialAccountResponse,
        name=callback_route_name,
        summary=f"{oauth_client.name.title()} association callback",
        description="Handles OAuth provider callback and links account",
        responses={
            status.HTTP_400_BAD_REQUEST: {
                "description": "Invalid state token or user mismatch",
                "content": {
                    "application/json": {
                        "examples": {
                            "invalid_state": {
                                "summary": "Invalid or expired state token",
                                "value": {"detail": "Invalid OAuth state token"},
                            },
                            "user_mismatch": {
                                "summary": "State user_id doesn't match authenticated user",
                                "value": {"detail": "OAuth state user mismatch (security)"},
                            },
                            "no_email": {
                                "summary": "Provider didn't return email",
                                "value": {"detail": "Email not available from OAuth provider"},
                            },
                            "already_linked": {
                                "summary": "This OAuth account is already linked",
                                "value": {"detail": "This OAuth account is already linked to a user"},
                            },
                        }
                    }
                },
            },
        },
    )
    async def callback(
        request: Request,
        auth_context = Depends(get_current_user),
        access_token_state: tuple[OAuth2Token, str] = Depends(oauth2_authorize_callback),
    ):
        """
        Handle OAuth provider callback for account association.

        Validates:
        1. State token signature and expiration
        2. State user_id matches authenticated user (prevents hijacking!)
        3. OAuth account not already linked to another user
        4. User is active

        Creates social account link and triggers on_after_oauth_associate hook.

        Security:
            - CRITICAL: Validates state["sub"] == authenticated user_id
            - This prevents attacker from hijacking victim's account by:
              1. Starting OAuth flow for their own account
              2. Tricking victim into completing the callback
              3. Without validation, victim's OAuth would link to attacker's account!
        """
        token, state = access_token_state
        user_id = auth_context.get("user_id")

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

        # SECURITY: Validate state user_id matches authenticated user
        if state_data.get("sub") != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth state user mismatch (security)",
            )

        # Check if this OAuth account is already linked to ANY user
        try:
            existing_user = await auth.user_service.get_by_oauth_account(
                oauth_client.name,
                account_id
            )
            if str(existing_user.id) != user_id:
                # OAuth account linked to different user
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This OAuth account is already linked to another user",
                )
            else:
                # Already linked to this user (maybe they clicked twice)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This OAuth account is already linked to your account",
                )
        except Exception:
            # OAuth account not found - good, we can link it
            pass

        # Get current user
        user = await auth.user_service.get_user(user_id)

        # Link OAuth account to user
        social_account = await auth.social_account_service.create(
            user_id=user.id,
            provider=oauth_client.name,
            provider_user_id=account_id,
            email=account_email,
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            expires_at=token.get("expires_at"),
        )

        # Trigger hook
        await auth.user_service.on_after_oauth_associate(
            user,
            oauth_client.name,
            request
        )

        # Return the newly created social account
        return SocialAccountResponse(
            provider=social_account.provider,
            provider_user_id=social_account.provider_user_id,
            email=social_account.email,
            email_verified=social_account.email_verified,
            display_name=social_account.display_name,
            avatar_url=social_account.avatar_url,
            linked_at=social_account.linked_at.isoformat(),
            last_used_at=social_account.last_used_at.isoformat() if social_account.last_used_at else None,
        )

    return router
