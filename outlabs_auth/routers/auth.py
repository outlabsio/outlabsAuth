"""
Authentication router factory.

Provides ready-to-use authentication routes (DD-041).
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from outlabs_auth.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RefreshRequest,
    RefreshResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LogoutRequest,
)
from outlabs_auth.schemas.user import UserResponse


def get_auth_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str]] = None,
    requires_verification: bool = False
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

    @router.post(
        "/register",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Register new user",
        description="Create a new user account"
    )
    async def register(data: RegisterRequest):
        """
        Register a new user.

        Triggers on_after_register hook.
        """
        try:
            user = await auth.user_service.create_user(
                email=data.email,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name
            )
            return user
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    @router.post(
        "/login",
        response_model=LoginResponse,
        summary="User login",
        description="Login with email and password to get JWT tokens"
    )
    async def login(data: LoginRequest):
        """
        Authenticate user and return JWT tokens.

        Triggers on_after_login hook.
        """
        try:
            # Authenticate user and get tokens
            user, tokens = await auth.auth_service.login(
                email=data.email,
                password=data.password
            )

            # Check verification requirement
            if requires_verification:
                if not hasattr(user, "is_verified") or not user.is_verified:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Email verification required"
                    )

            # Trigger hook
            await auth.user_service.on_after_login(user)

            return LoginResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @router.post(
        "/refresh",
        response_model=RefreshResponse,
        summary="Refresh access token",
        description="Get new access token using refresh token"
    )
    async def refresh(data: RefreshRequest):
        """Refresh access token using refresh token."""
        try:
            tokens = await auth.auth_service.refresh_access_token(data.refresh_token)
            return RefreshResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    @router.post(
        "/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="User logout",
        description="Logout and revoke tokens (supports optional immediate access token revocation)"
    )
    async def logout(
        data: Optional[LogoutRequest] = None,
        auth_result = Depends(auth.deps.require_auth())
    ):
        """
        Logout user with flexible revocation options.

        Hybrid pattern:
        - Always revokes refresh token in MongoDB
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
        redis_client = getattr(auth, 'redis_client', None)

        if data and data.refresh_token:
            # Single device logout (revoke specific refresh token)
            await auth.auth_service.logout(
                data.refresh_token,
                blacklist_access_token=immediate,
                access_token_jti=jti,
                redis_client=redis_client
            )
        else:
            # Logout from all devices (revoke all user's refresh tokens)
            await auth.auth_service.revoke_all_user_tokens(auth_result["user_id"])

            # If immediate revocation requested, still blacklist current access token
            if immediate and jti and redis_client:
                if hasattr(redis_client, 'is_available') and redis_client.is_available:
                    remaining_ttl = auth.config.access_token_expire_minutes * 60
                    await redis_client.set(
                        f"blacklist:jwt:{jti}",
                        "revoked",
                        ttl=remaining_ttl
                    )

        return None

    @router.post(
        "/forgot-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Request password reset",
        description="Send password reset email"
    )
    async def forgot_password(data: ForgotPasswordRequest):
        """
        Request password reset.

        Triggers on_after_forgot_password hook with reset token.
        """
        try:
            # Get user by email
            user = await auth.user_service.get_user_by_email(data.email)
            if not user:
                # Don't reveal if email exists
                return None

            # Generate reset token
            token = await auth.auth_service.generate_reset_token(user)

            # Trigger hook (should send email)
            await auth.user_service.on_after_forgot_password(user, token)

        except Exception:
            pass  # Don't reveal errors

        return None

    @router.post(
        "/reset-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Reset password",
        description="Reset password using reset token"
    )
    async def reset_password(data: ResetPasswordRequest):
        """
        Reset password using reset token.

        Triggers on_after_reset_password hook.
        """
        try:
            # Verify token and reset password
            user = await auth.auth_service.reset_password(
                token=data.token,
                new_password=data.new_password
            )

            # Trigger hook
            await auth.user_service.on_after_reset_password(user)

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )

        return None

    return router
