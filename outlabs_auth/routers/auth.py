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
            # Authenticate user
            user = await auth.auth_service.authenticate(
                email=data.email,
                password=data.password
            )

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )

            # Check verification requirement
            if requires_verification:
                if not hasattr(user, "is_verified") or not user.is_verified:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Email verification required"
                    )

            # Generate tokens
            tokens = await auth.auth_service.create_tokens(user)

            # Trigger hook
            await auth.user_service.on_after_login(user)

            return LoginResponse(**tokens)

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
            tokens = await auth.auth_service.refresh_token(data.refresh_token)
            return RefreshResponse(**tokens)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    @router.post(
        "/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="User logout",
        description="Logout and invalidate tokens"
    )
    async def logout(auth_result = Depends(auth.deps.require_auth())):
        """
        Logout user (invalidate tokens if using Redis strategy).

        Requires authentication.
        """
        # If using Redis strategy, invalidate tokens
        try:
            if hasattr(auth.auth_service, "invalidate_tokens"):
                await auth.auth_service.invalidate_tokens(auth_result["user_id"])
        except Exception:
            pass  # Graceful degradation

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
