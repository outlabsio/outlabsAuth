"""
OAuth/Social login router factory (DD-043).

Provides ready-to-use OAuth routes for authentication with social providers
(Google, Facebook, Apple, GitHub, etc.).
"""

import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.oauth.state import decode_state_token, generate_state_token
from outlabs_auth.routers.oauth_utils import encrypt_provider_token, get_oauth_user_info
from outlabs_auth.schemas.oauth import OAuthAuthorizeResponse
from outlabs_auth.utils.validation import validate_email


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


def _generate_oauth_placeholder_password(config: Any) -> str:
    """Generate a password that satisfies the configured password policy."""
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"

    required_parts = ["a"]
    if getattr(config, "require_uppercase", True):
        required_parts.append("A")
    if getattr(config, "require_digit", True):
        required_parts.append("1")
    if getattr(config, "require_special_char", True):
        required_parts.append("!")

    min_length = max(getattr(config, "password_min_length", 8), len(required_parts))
    pool = alphabet + alphabet.upper() + digits + special_chars
    password_chars = required_parts + [
        secrets.choice(pool) for _ in range(min_length - len(required_parts))
    ]
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


def _append_auth_method(user: Any, provider: str) -> None:
    """Ensure the provider auth method is present on user.auth_methods."""
    provider_method = provider.upper()
    methods = list(user.auth_methods or [])
    if provider_method not in methods:
        methods.append(provider_method)
        user.auth_methods = methods


def _normalize_oauth_email(email: Optional[str]) -> Optional[str]:
    """Return a normalized usable OAuth email or None when absent/invalid."""
    if email is None:
        return None
    try:
        return validate_email(email)
    except InvalidInputError:
        return None


def get_oauth_router(
    oauth_client: Any,
    auth: Any,
    state_secret: str,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    redirect_url: Optional[str] = None,
    associate_by_email: bool = False,
    is_verified_by_default: bool = False,
) -> APIRouter:
    """Generate OAuth authentication router for a provider."""
    from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback

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
        access_token_state: tuple[dict[str, Any], str] = Depends(
            oauth2_authorize_callback
        ),
    ):
        token, state = access_token_state

        user_info = await get_oauth_user_info(oauth_client, token)

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
            account_id=user_info.provider_user_id,
            account_email=user_info.email,
            account_email_verified=user_info.email_verified,
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
            auth_method=f"oauth:{oauth_client.name}",
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
    account_email: Optional[str],
    account_email_verified: bool,
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
    normalized_email = _normalize_oauth_email(account_email)

    if associate_by_email and not account_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="associate_by_email requires a provider-verified email",
        )
    if is_verified_by_default and not account_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="is_verified_by_default requires a provider-verified email",
        )

    provider_access_token = (
        encrypt_provider_token(auth, access_token) if store_provider_tokens else None
    )
    provider_refresh_token = (
        encrypt_provider_token(auth, refresh_token) if store_provider_tokens else None
    )

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

        if normalized_email is not None:
            social_account.provider_email = normalized_email
        social_account.provider_email_verified = account_email_verified
        social_account.update_tokens(
            access_token=provider_access_token,
            refresh_token=provider_refresh_token,
            expires_at=token_expires_at,
        )
        social_account.last_login_at = now
        _append_auth_method(user, provider)
        await session.flush()
        return user

    if normalized_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not available from OAuth provider",
        )

    # 2) Existing local user by email.
    user = await auth.user_service.get_user_by_email(session, normalized_email)
    created_user = False

    if user is None:
        random_password = _generate_oauth_placeholder_password(auth.config)
        user = await auth.user_service.create_user(
            session=session,
            email=normalized_email,
            password=random_password,
        )
        user.email_verified = account_email_verified if is_verified_by_default else False
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
        existing_provider_link.provider_email = normalized_email
        existing_provider_link.provider_email_verified = account_email_verified
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
                provider_email=normalized_email,
                provider_email_verified=account_email_verified,
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
