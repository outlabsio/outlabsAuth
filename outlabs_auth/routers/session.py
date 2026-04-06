"""Minimal session auth router factory for embedded hosts."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import OutlabsAuthException
from outlabs_auth.observability import (
    ObservabilityContext,
    get_observability_dependency,
)
from outlabs_auth.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
)


def get_session_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False,
) -> APIRouter:
    """
    Generate a minimal auth session router for embedded applications.

    Routes:
        POST /login
        POST /refresh
        POST /logout
    """
    router = APIRouter(prefix=prefix, tags=tags or ["auth-session"])
    get_obs = get_observability_dependency(auth.observability)

    @router.post(
        "/login",
        response_model=LoginResponse,
        summary="User login",
        description="Login with email and password to get JWT tokens",
    )
    async def login(
        data: LoginRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        try:
            user, tokens = await auth.auth_service.login(session, email=data.email, password=data.password)

            if requires_verification and not getattr(user, "email_verified", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email verification required",
                )

            await auth.user_service.on_after_login(user)

            return LoginResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
            )
        except HTTPException:
            raise
        except OutlabsAuthException:
            raise
        except Exception as exc:
            obs.log_500_error(exc, email=data.email)
            raise

    @router.post(
        "/refresh",
        response_model=RefreshResponse,
        summary="Refresh access token",
        description="Get new access token using refresh token",
    )
    async def refresh(
        data: RefreshRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        try:
            tokens = await auth.auth_service.refresh_access_token(session, data.refresh_token)
            return RefreshResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
            )
        except HTTPException:
            raise
        except OutlabsAuthException:
            raise
        except Exception as exc:
            obs.log_500_error(exc)
            raise

    @router.post(
        "/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="User logout",
        description="Logout and revoke tokens (supports optional immediate access token revocation)",
    )
    async def logout(
        data: LogoutRequest | None = None,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        immediate = data.immediate if data else False
        jti = auth_result.get("jti") if immediate else None
        redis_client = getattr(auth, "redis_client", None)

        if data and data.refresh_token:
            await auth.auth_service.logout(
                session,
                data.refresh_token,
                blacklist_access_token=immediate,
                access_token_jti=jti,
                redis_client=redis_client,
            )
            return None

        await auth.auth_service.revoke_all_user_tokens(session, auth_result["user_id"])

        if immediate and jti and redis_client and getattr(redis_client, "is_available", False):
            remaining_ttl = auth.config.access_token_expire_minutes * 60
            await redis_client.set(f"blacklist:jwt:{jti}", "revoked", ttl=remaining_ttl)

        return None

    return router
