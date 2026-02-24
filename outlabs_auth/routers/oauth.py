"""
OAuth/Social login router factory (DD-043).

Provides ready-to-use OAuth routes for authentication with social providers
(Google, Facebook, Apple, GitHub, etc.).
"""

import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback
from httpx_oauth.oauth2 import BaseOAuth2, OAuth2Token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.oauth.state import decode_state_token, generate_state_token
from outlabs_auth.schemas.oauth import OAuthAuthorizeResponse


def _normalize_expires_at(expires_at: Optional[Any]) -> Optional[datetime]:
    """Normalize OAuth expires_at values into timezone-aware UTC datetimes."""
    if expires_at is None:
        return None

    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            return expires_at.replace(tzinfo=timezone.utc)
        return expires_at.astimezone(timezone.utc)

    try:
        return datetime.fromtimestamp(int(expires_at), tz=timezone.utc)
    except Exception:
        return None


def _append_auth_method(user: Any, provider: str) -> None:
    """Ensure the provider auth method is present on user.auth_methods."""
    provider_method = provider.upper()
    methods = list(user.auth_methods or [])
    if provider_method not in methods:
        methods.append(provider_method)
        user.auth_methods = methods


def get_oauth_router(
    oauth_client: BaseOAuth2,
    auth: Any,
    state_secret: str,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    redirect_url: Optional[str] = None,
    associate_by_email: bool = False,
    is_verified_by_default: bool = False,
) -> APIRouter:
    """Generate OAuth authentication router for a provider."""
    router = APIRouter(prefix=prefix, tags=tags or ["oauth"])

    callback_route_name = f"oauth:{oauth_client.name}.callback"

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
        if redirect_url is not None:
            authorize_redirect_url = redirect_url
        else:
            authorize_redirect_url = str(request.url_for(callback_route_name))

        state_data: dict[str, str] = {}
        state = generate_state_token(state_data, state_secret, lifetime_seconds=600)

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
        session: AsyncSession = Depends(auth.uow),
        access_token_state: tuple[OAuth2Token, str] = Depends(oauth2_authorize_callback),
    ):
        token, state = access_token_state

        account_id, account_email = await oauth_client.get_id_email(token["access_token"])
        if account_email is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not available from OAuth provider",
            )

        try:
            decode_state_token(state, state_secret)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth state token",
            )

        user = await oauth_callback(
            auth=auth,
            session=session,
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

        tokens = await auth.auth_service.create_tokens_for_user(
            session,
            user,
            device_name=f"oauth:{oauth_client.name}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        await auth.user_service.on_after_login(user, request)
        await auth.user_service.on_after_oauth_login(user, oauth_client.name, request)

        # OAuth callback is a GET endpoint; commit explicitly before the UoW
        # middleware's read-method rollback step runs.
        await session.commit()

        return tokens.to_dict()

    return router


async def oauth_callback(
    auth: Any,
    session: AsyncSession,
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
    """Resolve/create a user and social-account link for an OAuth callback."""
    token_expires_at = _normalize_expires_at(expires_at)
    now = datetime.now(timezone.utc)
    store_provider_tokens = bool(getattr(auth.config, "store_oauth_provider_tokens", False))
    provider_access_token = access_token if store_provider_tokens else None
    provider_refresh_token = refresh_token if store_provider_tokens else None

    # 1) Existing provider account mapping.
    stmt = select(SocialAccount).where(
        SocialAccount.provider == provider,
        SocialAccount.provider_user_id == account_id,
    )
    result = await session.execute(stmt)
    social_account = result.scalar_one_or_none()
    if social_account:
        user = await auth.user_service.get_user_by_id(session, social_account.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth account is linked to an invalid user",
            )

        social_account.provider_email = account_email
        social_account.update_tokens(
            access_token=provider_access_token,
            refresh_token=provider_refresh_token,
            expires_at=token_expires_at,
        )
        social_account.last_login_at = now
        _append_auth_method(user, provider)
        await session.flush()
        return user

    # 2) Existing local user by email.
    user = await auth.user_service.get_user_by_email(session, account_email)
    created_user = False

    if user is None:
        random_password = secrets.token_urlsafe(32)
        user = await auth.user_service.create_user(
            session=session,
            email=account_email,
            password=random_password,
        )
        user.email_verified = is_verified_by_default
        created_user = True
    elif not associate_by_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # 3) Link provider to user (or refresh existing same-provider mapping).
    existing_provider_stmt = select(SocialAccount).where(
        SocialAccount.user_id == user.id,
        SocialAccount.provider == provider,
    )
    existing_provider_result = await session.execute(existing_provider_stmt)
    existing_provider_link = existing_provider_result.scalar_one_or_none()

    if existing_provider_link:
        if existing_provider_link.provider_user_id != account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This provider is already linked to a different account",
            )
        existing_provider_link.provider_email = account_email
        existing_provider_link.update_tokens(
            access_token=provider_access_token,
            refresh_token=provider_refresh_token,
            expires_at=token_expires_at,
        )
        existing_provider_link.last_login_at = now
    else:
        session.add(
            SocialAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=account_id,
                provider_email=account_email,
                access_token=provider_access_token,
                refresh_token=provider_refresh_token,
                token_expires_at=token_expires_at,
                token_refreshed_at=now,
                last_login_at=now,
            )
        )

    _append_auth_method(user, provider)
    await session.flush()

    if created_user:
        await auth.user_service.on_after_register(user, request)
        await auth.user_service.on_after_oauth_register(user, provider, request)

    return user
