"""
Authentication router factory.

Provides ready-to-use authentication routes (DD-041).
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.observability import (
    ObservabilityContext,
    get_observability_dependency,
)
from outlabs_auth.schemas.auth import (
    AuthConfigResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from outlabs_auth.schemas.user import UserResponse
from outlabs_auth.utils.rate_limit import check_forgot_password_rate_limit


def get_auth_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False,
) -> APIRouter:
    """
    Generate authentication router with login/register/password routes.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["auth"])
        requires_verification: Require email verification for login (default: False)

    Returns:
        APIRouter with authentication endpoints

    Routes:
        POST /register - User registration
        POST /login - User login (JWT tokens)
        POST /refresh - Refresh access token
        POST /logout - Logout (invalidate tokens)
        POST /forgot-password - Request password reset
        POST /reset-password - Reset password with token

    Example:
        ```python
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_auth_router

        auth = SimpleRBAC(database=db)
        app.include_router(get_auth_router(auth, prefix="/auth"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["auth"])

    # Create observability dependency (no auth required for public endpoints)
    get_obs = get_observability_dependency(auth.observability)

    @router.get(
        "/config",
        response_model=AuthConfigResponse,
        summary="Get auth configuration",
        description="Returns preset type and enabled features (used by admin UIs)",
    )
    async def get_config():
        """
        Get OutlabsAuth configuration.

        Returns:
            - preset: SimpleRBAC or EnterpriseRBAC
            - features: Enabled features (entity_hierarchy, context_aware_roles, etc.)
            - available_permissions: All permission strings for this preset

        This endpoint is used by admin UIs to conditionally show/hide features
        based on the detected preset and enabled features.
        """
        # Determine preset name
        preset_name = auth.__class__.__name__

        # Get feature flags from config
        features = {
            "entity_hierarchy": auth.config.enable_entity_hierarchy,
            "context_aware_roles": auth.config.enable_context_aware_roles,
            "abac": auth.config.enable_abac,
            "tree_permissions": auth.config.enable_entity_hierarchy,  # Tree permissions require hierarchy
            "api_keys": True,  # Always available
            "user_status": True,  # Always available
            "activity_tracking": True,  # Always available
        }

        # Get available permissions from permission service
        # For now, return empty list - this will be populated when we have permission enumeration
        available_permissions = []

        return AuthConfigResponse(
            preset=preset_name,
            features=features,
            available_permissions=available_permissions,
        )

    @router.post(
        "/register",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Register new user",
        description="Create a new user account",
    )
    async def register(
        data: RegisterRequest,
        session: AsyncSession = Depends(auth.get_session),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Register a new user.

        Triggers on_after_register hook.
        """
        try:
            user = await auth.user_service.create_user(
                session,
                email=data.email,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name,
            )
            await session.commit()
            obs.log_event("user_registered", user_id=str(user.id), email=data.email)
            return user
        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            obs.log_500_error(e, email=data.email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register user",
            )

    @router.post(
        "/login",
        response_model=LoginResponse,
        summary="User login",
        description="Login with email and password to get JWT tokens",
    )
    async def login(
        data: LoginRequest,
        session: AsyncSession = Depends(auth.get_session),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Authenticate user and return JWT tokens.

        Triggers on_after_login hook.
        """
        try:
            # Authenticate user and get tokens
            user, tokens = await auth.auth_service.login(
                session, email=data.email, password=data.password
            )
            await session.commit()

            # Check verification requirement
            if requires_verification:
                if not hasattr(user, "is_verified") or not user.is_verified:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Email verification required",
                    )

            # Trigger hook
            await auth.user_service.on_after_login(user)

            return LoginResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
            )

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, email=data.email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed",
            )

    @router.post(
        "/refresh",
        response_model=RefreshResponse,
        summary="Refresh access token",
        description="Get new access token using refresh token",
    )
    async def refresh(
        data: RefreshRequest,
        session: AsyncSession = Depends(auth.get_session),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """Refresh access token using refresh token."""
        try:
            tokens = await auth.auth_service.refresh_access_token(session, data.refresh_token)
            await session.commit()
            return RefreshResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed",
            )

    @router.post(
        "/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="User logout",
        description="Logout and revoke tokens (supports optional immediate access token revocation)",
    )
    async def logout(
        data: Optional[LogoutRequest] = None,
        session: AsyncSession = Depends(auth.get_session),
        auth_result=Depends(auth.deps.require_auth()),
    ):
        """
        Logout user with flexible revocation options.

        Hybrid pattern:
        - Always revokes refresh token in database
        - Optionally blacklists access token in Redis (immediate=true)
        - Gracefully degrades if Redis unavailable

        Request body (optional):
        {
            "refresh_token": "eyJ...",  // Optional: specific session to revoke
            "immediate": false           // Optional: blacklist access token (requires Redis)
        }

        Behavior:
        - Without refresh_token: Revokes ALL user sessions (logout from all devices)
        - With refresh_token: Revokes specific session
        - immediate=false (default): Access token valid for 15 min
        - immediate=true: Access token blacklisted immediately (requires Redis)

        Security levels:
        - Low: No Redis → 15-min security window
        - Medium: Redis available, immediate=false → 15-min window (default)
        - High: Redis available, immediate=true → Immediate revocation
        """
        immediate = data.immediate if data else False
        jti = auth_result.get("jti") if immediate else None

        # Get Redis client if available
        redis_client = getattr(auth, "redis_client", None)

        if data and data.refresh_token:
            # Single device logout (revoke specific refresh token)
            await auth.auth_service.logout(
                session,
                data.refresh_token,
                blacklist_access_token=immediate,
                access_token_jti=jti,
                redis_client=redis_client,
            )
        else:
            # Logout from all devices (revoke all user's refresh tokens)
            await auth.auth_service.revoke_all_user_tokens(session, auth_result["user_id"])

            # If immediate revocation requested, still blacklist current access token
            if immediate and jti and redis_client:
                if hasattr(redis_client, "is_available") and redis_client.is_available:
                    remaining_ttl = auth.config.access_token_expire_minutes * 60
                    await redis_client.set(
                        f"blacklist:jwt:{jti}", "revoked", ttl=remaining_ttl
                    )

        await session.commit()
        return None

    @router.post(
        "/forgot-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Request password reset",
        description="Send password reset email (rate limited: 3 requests per 5 minutes)",
    )
    async def forgot_password(
        data: ForgotPasswordRequest,
        session: AsyncSession = Depends(auth.get_session),
    ):
        """
        Request password reset.

        Rate limited to 3 requests per 5 minutes per email address.

        Triggers on_after_forgot_password hook with reset token.
        """
        # Check rate limit
        is_limited, seconds_until_reset = await check_forgot_password_rate_limit(
            data.email
        )

        if is_limited:
            # Return 429 with retry-after information
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Too many password reset requests. Please try again later.",
                    "retry_after_seconds": seconds_until_reset,
                    "retry_after_minutes": round(seconds_until_reset / 60, 1),
                },
            )

        try:
            # Get user by email
            user = await auth.user_service.get_user_by_email(session, data.email)
            if not user:
                # Don't reveal if email exists (but still enforce rate limit)
                return None

            # Generate reset token
            token = await auth.auth_service.generate_reset_token(session, user)
            await session.commit()

            # Trigger hook (should send email)
            await auth.user_service.on_after_forgot_password(user, token)

        except Exception as e:
            # Log error but don't reveal to user
            if auth.observability:
                auth.observability.logger.error(
                    "forgot_password_error", email=data.email, error=str(e)
                )

        return None

    @router.post(
        "/reset-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Reset password",
        description="Reset password using reset token",
    )
    async def reset_password(
        data: ResetPasswordRequest,
        session: AsyncSession = Depends(auth.get_session),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Reset password using reset token.

        Triggers on_after_reset_password hook.
        """
        try:
            # Verify token and reset password
            user = await auth.auth_service.reset_password(
                session, token=data.token, new_password=data.new_password
            )
            await session.commit()

            # Trigger hook
            await auth.user_service.on_after_reset_password(user)
            obs.log_event("password_reset", user_id=str(user.id))

        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password reset failed",
            )

        return None

    return router
