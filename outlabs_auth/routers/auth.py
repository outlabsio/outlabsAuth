"""
Authentication router factory.

Provides ready-to-use authentication routes (DD-041).
"""

from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import OutlabsAuthException
from outlabs_auth.observability import (
    ObservabilityContext,
    get_observability_dependency,
    get_observability_with_auth,
)
from outlabs_auth.response_builders import build_user_response_async
from outlabs_auth.schemas.auth import (
    AcceptInviteRequest,
    AuthConfigResponse,
    ForgotPasswordRequest,
    InviteUserRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from outlabs_auth.schemas.user import UserResponse
from outlabs_auth.utils.rate_limit import (
    check_forgot_password_rate_limit,
    check_magic_link_rate_limit,
)


def get_auth_router(
    auth: Any,
    prefix: str = "",
    tags: Optional[list[str | Enum]] = None,
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
    async def get_config(
        session: AsyncSession = Depends(auth.uow),
    ):
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
            "system_api_keys": True,  # Platform-global system keys are available in all presets
            "user_status": True,  # Always available
            "activity_tracking": True,  # Always available
            "invitations": auth.config.enable_invitations,
            "magic_links": auth.config.enable_magic_links,
        }
        auth_methods = {
            "password": True,
            "magic_link": auth.config.enable_magic_links,
        }

        # Get available permissions from database
        permissions, _ = await auth.permission_service.list_permissions(session, page=1, limit=1000, is_active=True)
        available_permissions = [p.name for p in permissions]

        return AuthConfigResponse(
            preset=preset_name,
            features=features,
            auth_methods=auth_methods,
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
        session: AsyncSession = Depends(auth.uow),
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
            obs.log_event("user_registered", user_id=str(user.id), email=data.email)
            return await build_user_response_async(session, user)
        except HTTPException:
            raise
        except OutlabsAuthException:
            # Let the exception handler convert this to proper HTTP response
            raise
        except Exception as e:
            obs.log_500_error(e, email=data.email)
            raise

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
        """
        Authenticate user and return JWT tokens.

        Triggers on_after_login hook.
        """
        try:
            # Authenticate user and get tokens
            user, tokens = await auth.auth_service.login(session, email=data.email, password=data.password)

            # Check verification requirement
            if requires_verification:
                if not getattr(user, "email_verified", False):
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
        except OutlabsAuthException:
            # Let the exception handler convert this to proper HTTP response
            raise
        except Exception as e:
            obs.log_500_error(e, email=data.email)
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
        """Refresh access token using refresh token."""
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
            # Let the exception handler convert this to proper HTTP response
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise

    @router.post(
        "/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="User logout",
        description="Logout and revoke tokens (supports optional immediate access token revocation)",
    )
    async def logout(
        data: Optional[LogoutRequest] = None,
        session: AsyncSession = Depends(auth.uow),
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
                    await redis_client.set(f"blacklist:jwt:{jti}", "revoked", ttl=remaining_ttl)

        return None

    @router.post(
        "/forgot-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Request password reset",
        description="Send password reset email (rate limited: 3 requests per 5 minutes)",
    )
    async def forgot_password(
        data: ForgotPasswordRequest,
        session: AsyncSession = Depends(auth.uow),
    ):
        """
        Request password reset.

        Rate limited to 3 requests per 5 minutes per email address.

        Triggers on_after_forgot_password hook with reset token.
        """
        # Check rate limit
        is_limited, seconds_until_reset = await check_forgot_password_rate_limit(
            data.email,
            redis_client=getattr(auth, "redis_client", None),
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
                headers={"Retry-After": str(max(seconds_until_reset, 1))},
            )

        try:
            # Get user by email
            user = await auth.user_service.get_user_by_email(session, data.email)
            if not user:
                # Don't reveal if email exists (but still enforce rate limit)
                return None

            # Generate reset token
            token = await auth.auth_service.generate_reset_token(session, user)

            # Trigger hook (should send email)
            await auth.user_service.on_after_forgot_password(user, token)

        except Exception as e:
            # Log error but don't reveal to user
            if auth.observability:
                auth.observability.logger.error("forgot_password_error", email=data.email, error=str(e))

        return None

    @router.post(
        "/reset-password",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Reset password",
        description="Reset password using reset token",
    )
    async def reset_password(
        data: ResetPasswordRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Reset password using reset token.

        Triggers on_after_reset_password hook.
        """
        try:
            # Verify token and reset password
            user = await auth.auth_service.reset_password(session, token=data.token, new_password=data.new_password)

            # Trigger hook
            await auth.user_service.on_after_reset_password(user)
            obs.log_event("password_reset", user_id=str(user.id))

        except HTTPException:
            raise
        except OutlabsAuthException:
            # Let the exception handler convert this to proper HTTP response
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise

        return None

    @router.post(
        "/magic-link/request",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Request magic link",
        description="Generate a one-time magic-link token and expose it to the host email hook.",
    )
    async def request_magic_link(
        data: MagicLinkRequest,
        request: Request,
        session: AsyncSession = Depends(auth.uow),
    ):
        """
        Request a magic-link token.

        This endpoint never reveals whether the email belongs to an account. If
        a usable account exists, it calls `on_after_magic_link_requested` with
        the plain token so the host application can send its own email.
        """
        if not auth.config.enable_magic_links:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Magic link authentication is not enabled",
            )

        is_limited, seconds_until_reset = await check_magic_link_rate_limit(
            data.email,
            redis_client=getattr(auth, "redis_client", None),
            max_requests=auth.config.magic_link_request_rate_limit_max,
            window_seconds=auth.config.magic_link_request_rate_limit_window_seconds,
        )
        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Too many magic link requests. Please try again later.",
                    "retry_after_seconds": seconds_until_reset,
                    "retry_after_minutes": round(seconds_until_reset / 60, 1),
                },
                headers={"Retry-After": str(max(seconds_until_reset, 1))},
            )

        try:
            user = await auth.user_service.get_user_by_email(session, data.email)
            if not user:
                return None

            if getattr(user.status, "value", user.status) != "active" or user.is_locked:
                return None

            token = await auth.auth_service.generate_magic_link_token(
                session,
                user,
                redirect_url=data.redirect_url,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            await auth.user_service.on_after_magic_link_requested(
                user,
                token,
                request,
                redirect_url=data.redirect_url,
            )
        except Exception as e:
            if auth.observability:
                auth.observability.logger.error("magic_link_request_error", email=data.email, error=str(e))

        return None

    @router.post(
        "/magic-link/verify",
        response_model=LoginResponse,
        summary="Verify magic link",
        description="Exchange a one-time magic-link token for JWT tokens.",
    )
    async def verify_magic_link(
        data: MagicLinkVerifyRequest,
        request: Request,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Verify a magic-link token and return JWT tokens.
        """
        if not auth.config.enable_magic_links:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Magic link authentication is not enabled",
            )

        try:
            user, tokens = await auth.auth_service.verify_magic_link(
                session,
                data.token,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            await auth.user_service.on_after_login(user, request)
            obs.log_event("magic_link_verified", user_id=str(user.id))

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
        except Exception as e:
            obs.log_500_error(e)
            raise

    @router.post(
        "/invite",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Invite user",
        description="Invite a user by email (requires user:create permission). Creates account with INVITED status.",
    )
    async def invite_user(
        data: InviteUserRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("user:create"),
            )
        ),
    ):
        """
        Invite a user by email.

        Creates an account with INVITED status and no password.
        Triggers on_after_invite hook with the plain token.
        If entity_id is provided, also adds entity membership.
        """
        from uuid import UUID

        try:
            actor_user_id = UUID(obs.user_id) if obs.user_id else None
            actor_user = (
                await auth.user_service.get_user_by_id(session, actor_user_id) if actor_user_id is not None else None
            )
            if data.is_superuser and not (actor_user and actor_user.is_superuser):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only superusers can invite superusers",
                )

            user, plain_token = await auth.user_service.invite_user(
                session,
                email=data.email,
                first_name=data.first_name,
                last_name=data.last_name,
                is_superuser=data.is_superuser,
                invited_by_id=actor_user_id,
                root_entity_id=None,
            )

            role_ids = [UUID(rid) for rid in data.role_ids] if data.role_ids else []

            # If entity_id is provided, roles are applied through the entity
            # membership. Without an entity, role_ids represent direct RBAC
            # assignments for SimpleRBAC/system-wide roles.
            if data.entity_id:
                if auth.membership_service:
                    await auth.membership_service.add_member(
                        session,
                        entity_id=UUID(data.entity_id),
                        user_id=user.id,
                        role_ids=role_ids,
                        joined_by_id=actor_user_id,
                    )
                    await session.refresh(user)
            elif role_ids:
                for role_id in role_ids:
                    await auth.role_service.assign_role_to_user(
                        session,
                        user_id=user.id,
                        role_id=role_id,
                        assigned_by_id=actor_user_id,
                    )
                await session.refresh(user)

            # Trigger hook
            await auth.user_service.on_after_invite(user, plain_token)

            obs.log_event("user_invited", invited_user_id=str(user.id), email=data.email)

            return await build_user_response_async(session, user)
        except HTTPException:
            raise
        except OutlabsAuthException:
            raise
        except Exception as e:
            obs.log_500_error(e, email=data.email)
            raise

    @router.post(
        "/accept-invite",
        response_model=LoginResponse,
        summary="Accept invitation",
        description="Accept an invitation by setting a password. Returns JWT tokens for auto-login.",
    )
    async def accept_invite(
        data: AcceptInviteRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Accept an invitation and set password.

        Activates the account and returns JWT tokens for immediate login.
        """
        try:
            user = await auth.auth_service.accept_invite(
                session,
                token=data.token,
                new_password=data.new_password,
            )

            # Auto-login: create tokens
            tokens = await auth.auth_service.create_tokens_for_user(
                session,
                user,
                auth_method="invite_accept",
            )

            obs.log_event("invite_accepted", user_id=str(user.id))

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
        except Exception as e:
            obs.log_500_error(e)
            raise

    return router
