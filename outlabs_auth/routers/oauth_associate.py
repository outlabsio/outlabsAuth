"""
OAuth account association router for authenticated users (DD-044).

Allows authenticated users to link additional OAuth providers to their account.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Union, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.oauth.state import decode_state_token, generate_state_token
from outlabs_auth.routers.oauth_state_store import consume_oauth_state, issue_oauth_state
from outlabs_auth.routers.oauth_utils import encrypt_provider_token, get_oauth_user_info
from outlabs_auth.schemas.oauth import OAuthAuthorizeResponse, SocialAccountResponse


def _normalize_expires_at(expires_at: Optional[Any]) -> Optional[datetime]:
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
    provider_method = provider.upper()
    methods = list(user.auth_methods or [])
    if provider_method not in methods:
        methods.append(provider_method)
        user.auth_methods = methods


def _to_social_account_response(account: SocialAccount) -> SocialAccountResponse:
    return SocialAccountResponse(
        id=account.id,
        provider=account.provider,
        provider_user_id=account.provider_user_id,
        email=account.provider_email or "",
        email_verified=account.provider_email_verified,
        display_name=account.display_name,
        avatar_url=account.avatar_url,
        linked_at=account.created_at.isoformat(),
        last_used_at=account.last_login_at.isoformat() if account.last_login_at else None,
    )


def _build_success_redirect(base_url: str, *, provider: str) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'linked': provider})}"


def get_oauth_associate_router(
    oauth_client: Any,
    auth: Any,
    state_secret: str,
    prefix: str = "",
    tags: Optional[list[str | Enum]] = None,
    redirect_url: Optional[str] = None,
    success_redirect_url: Optional[str] = None,
    requires_verification: bool = False,
    cookie_secure: bool = True,
) -> APIRouter:
    """
    Generate OAuth account association router for authenticated users.

    ``/authorize`` requires a Bearer session. ``/callback`` authenticates via
    the signed one-time state + browser binding cookie (Google/GitHub will not
    send the SPA Bearer token on redirect). When ``success_redirect_url`` is
    set, successful callbacks redirect to the SPA instead of returning JSON.
    """
    from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback

    router = APIRouter(prefix=prefix, tags=tags or ["oauth"])

    get_current_user = auth.deps.require_auth(
        active=True,
        verified=requires_verification,
    )

    callback_route_name = f"oauth-associate:{oauth_client.name}.callback"

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
        response: Response,
        session: AsyncSession = Depends(auth.uow),
        auth_context=Depends(get_current_user),
        scopes: list[str] = Query(None, description="OAuth scopes to request"),
    ) -> OAuthAuthorizeResponse:
        user_id = auth_context.get("user_id")

        if redirect_url is not None:
            authorize_redirect_url = redirect_url
        else:
            authorize_redirect_url = str(request.url_for(callback_route_name))

        state_data = {"sub": user_id}
        state = generate_state_token(state_data, state_secret, lifetime_seconds=600)
        try:
            user_uuid = UUID(str(user_id))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid authenticated user ID",
            )
        await issue_oauth_state(
            session=session,
            response=response,
            state=state,
            provider=oauth_client.name,
            flow="associate",
            user_id=user_uuid,
            cookie_secure=cookie_secure,
        )

        authorization_url = await oauth_client.get_authorization_url(
            authorize_redirect_url,
            state,
            scopes,
        )

        return OAuthAuthorizeResponse(authorization_url=authorization_url)

    @router.get(
        "/callback",
        response_model=None,
        name=callback_route_name,
        summary=f"{oauth_client.name.title()} association callback",
        description=(
            "Handles OAuth provider callback and links account. Authenticated via "
            "signed state + binding cookie (no Bearer token required)."
        ),
        responses={
            status.HTTP_302_FOUND: {
                "description": "SPA redirect when success_redirect_url is configured",
            },
            status.HTTP_200_OK: {
                "description": "Linked account JSON when success_redirect_url is unset",
                "model": SocialAccountResponse,
            },
            status.HTTP_400_BAD_REQUEST: {
                "description": "Invalid state token or linking conflict",
            },
        },
    )
    async def callback(
        request: Request,
        response: Response,
        session: AsyncSession = Depends(auth.uow),
        access_token_state: tuple[dict[str, Any], str] = Depends(
            oauth2_authorize_callback
        ),
    ) -> Union[SocialAccountResponse, RedirectResponse]:
        token, state = access_token_state

        try:
            state_data = decode_state_token(state, state_secret)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth state token",
            )

        user_id = state_data.get("sub")
        try:
            user_uuid = UUID(str(user_id))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid authenticated user ID",
            )

        await consume_oauth_state(
            session=session,
            request=request,
            response=response,
            state=state,
            provider=oauth_client.name,
            flow="associate",
            expected_user_id=user_uuid,
        )

        user_info = await get_oauth_user_info(oauth_client, token)

        user = await auth.user_service.get_user_by_id(session, user_uuid)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        now = datetime.now(timezone.utc)
        token_expires_at = _normalize_expires_at(token.get("expires_at"))
        store_provider_tokens = bool(getattr(auth.config, "store_oauth_provider_tokens", False))
        provider_access_token = (
            encrypt_provider_token(auth, token["access_token"]) if store_provider_tokens else None
        )
        provider_refresh_token = (
            encrypt_provider_token(auth, token.get("refresh_token")) if store_provider_tokens else None
        )

        # Ensure this provider-user account is not linked to another user.
        provider_col = cast(Any, SocialAccount.provider)
        provider_user_id_col = cast(Any, SocialAccount.provider_user_id)
        linked_stmt = select(SocialAccount).where(
            provider_col == oauth_client.name,
            provider_user_id_col == user_info.provider_user_id,
        )
        linked_result = await session.execute(linked_stmt)
        linked_account = linked_result.scalar_one_or_none()
        if linked_account and linked_account.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This OAuth account is already linked to another user",
            )

        if linked_account and linked_account.user_id == user.id:
            linked_account.provider_email = user_info.email
            linked_account.provider_email_verified = user_info.email_verified
            linked_account.update_tokens(
                access_token=provider_access_token,
                refresh_token=provider_refresh_token,
                expires_at=token_expires_at,
            )
            linked_account.last_login_at = now
            _append_auth_method(user, oauth_client.name)
            await session.flush()
            await session.commit()
            if success_redirect_url:
                return RedirectResponse(
                    url=_build_success_redirect(
                        success_redirect_url, provider=oauth_client.name
                    ),
                    status_code=status.HTTP_302_FOUND,
                )
            return _to_social_account_response(linked_account)

        existing_provider_stmt = select(SocialAccount).where(
            SocialAccount.user_id == user.id,
            SocialAccount.provider == oauth_client.name,
        )
        existing_provider_result = await session.execute(existing_provider_stmt)
        existing_provider_account = existing_provider_result.scalar_one_or_none()

        if (
            existing_provider_account
            and existing_provider_account.provider_user_id != user_info.provider_user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A different account for this provider is already linked",
            )

        if existing_provider_account:
            existing_provider_account.provider_email = user_info.email
            existing_provider_account.provider_email_verified = user_info.email_verified
            existing_provider_account.update_tokens(
                access_token=provider_access_token,
                refresh_token=provider_refresh_token,
                expires_at=token_expires_at,
            )
            existing_provider_account.last_login_at = now
            social_account = existing_provider_account
        else:
            social_account = SocialAccount(
                user_id=user.id,
                provider=oauth_client.name,
                provider_user_id=user_info.provider_user_id,
                provider_email=user_info.email,
                provider_email_verified=user_info.email_verified,
                access_token=provider_access_token,
                refresh_token=provider_refresh_token,
                token_expires_at=token_expires_at,
                token_refreshed_at=now,
                last_login_at=now,
            )
            session.add(social_account)

        _append_auth_method(user, oauth_client.name)
        await session.flush()

        await auth.user_service.on_after_oauth_associate(user, oauth_client.name, request)

        # OAuth callback is GET; commit explicitly before read-method rollback.
        await session.commit()

        if success_redirect_url:
            return RedirectResponse(
                url=_build_success_redirect(
                    success_redirect_url, provider=oauth_client.name
                ),
                status_code=status.HTTP_302_FOUND,
            )
        return _to_social_account_response(social_account)

    return router
