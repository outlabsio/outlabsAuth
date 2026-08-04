"""
Authentication router factory.

Provides ready-to-use authentication routes (DD-041).
"""

from enum import Enum
import secrets
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import (
    OutlabsAuthException,
    PermissionDeniedError,
    RateLimitError,
)
from outlabs_auth.frontend.errors import WrongApplicationError
from outlabs_auth.frontend.flows import (
    consume_verified_challenge,
    prepare_challenge_dispatch,
    stash_send_next_url,
    stash_send_profile,
)
from outlabs_auth.frontend.types import FrontendFlow
from outlabs_auth.observability import (
    ObservabilityContext,
    get_observability_dependency,
    get_observability_with_auth,
)
from outlabs_auth.response_builders import build_user_response_async
from outlabs_auth.routers._authz_utils import require_can_delegate_roles
from outlabs_auth.routers.capabilities import build_auth_config_response, mark_auth_surface
from outlabs_auth.schemas.auth import (
    AcceptInviteRequest,
    AccessCodeRequest,
    AccessCodeVerifyRequest,
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
    check_access_code_request_rate_limit,
    check_access_code_verify_rate_limit,
    check_forgot_password_rate_limit,
    check_login_ip_rate_limit,
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
    login_rate_limit_namespace = (
        auth.config.redis_key_prefix if auth.config.redis_enabled else f"instance:{secrets.token_urlsafe(12)}"
    )

    # Create observability dependency (no auth required for public endpoints)
    get_obs = get_observability_dependency(auth.observability)

    @router.get(
        "/config",
        response_model=AuthConfigResponse,
        summary="Get auth configuration",
        description="Returns preset type and enabled features (used by admin UIs)",
    )
    async def get_config(request: Request):
        """
        Get OutlabsAuth configuration.

        Returns:
            - preset: SimpleRBAC or EnterpriseRBAC
            - features: Enabled features (entity_hierarchy, context_aware_roles, etc.)
        This public endpoint contains capability flags only. The permission
        catalog is available from the authenticated ``/config/permissions``
        endpoint.
        """
        return build_auth_config_response(auth, request)

    @router.get(
        "/config/permissions",
        response_model=List[str],
        summary="Get permission catalog",
        description="Returns active permission names (requires permission:read)",
    )
    async def get_permission_catalog(
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("permission:read")),
    ) -> List[str]:
        permissions, _ = await auth.permission_service.list_permissions(
            session,
            page=1,
            limit=1000,
            is_active=True,
        )
        return [permission.name for permission in permissions]

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
        request: Request,
        data: LoginRequest,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Authenticate user and return JWT tokens.

        Triggers on_after_login hook.
        """
        try:
            # Trust the ASGI server's resolved client address. Deployments behind
            # a proxy must configure that server's trusted-proxy handling; raw
            # X-Forwarded-For is intentionally not accepted here.
            ip_address = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "")[:512] or None
            limited, retry_after = await check_login_ip_rate_limit(
                ip_address,
                auth.redis_client,
                max_requests=auth.config.login_ip_rate_limit_max,
                window_seconds=auth.config.login_ip_rate_limit_window_seconds,
                redis_required=auth.config.redis_enabled,
                failure_mode=auth.config.login_ip_rate_limit_failure_mode,
                namespace=login_rate_limit_namespace,
            )
            if limited:
                raise RateLimitError(
                    message="Too many login attempts. Please try again later.",
                    details={"retry_after_seconds": retry_after},
                )

            # Authenticate user and get tokens
            user, tokens = await auth.auth_service.login(
                session,
                email=data.email,
                password=data.password,
                ip_address=ip_address,
                user_agent=user_agent,
                app=data.app,
            )

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
        except WrongApplicationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "wrong_application",
                    "message": "This account cannot sign in to the requested application.",
                },
            ) from exc
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
        except WrongApplicationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "wrong_application",
                    "message": "This session's application no longer accepts this account.",
                },
            ) from exc
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

            # DD-059: carry the requested frontend profile key to the mail
            # intent without changing the frozen hook signature. Unknown keys
            # fail closed at delivery; the outward 204 stays opaque.
            if data.app:
                stash_send_profile(data.app)

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

            # DD-059: resolve the frontend profile and canonical return target
            # once, at request time. Fail-closed outcomes skip generation and
            # delivery entirely while the outward 204 stays opaque.
            resolver = getattr(auth, "frontend_resolver", None)
            dispatch = await prepare_challenge_dispatch(
                resolver,
                session,
                user,
                flow=FrontendFlow.MAGIC_LINK,
                requested_app=data.app,
                redirect_url=data.redirect_url,
            )
            if not dispatch.deliver:
                return None

            token = await auth.auth_service.generate_magic_link_token(
                session,
                user,
                redirect_url=data.redirect_url,
                profile_id=dispatch.profile_id,
                next_url=dispatch.next_url,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            if dispatch.profile_id is not None:
                stash_send_profile(dispatch.profile_id)
                stash_send_next_url(dispatch.next_url)
            await auth.user_service.on_after_magic_link_requested(
                user,
                token,
                request,
                redirect_url=(dispatch.next_url if resolver is not None else data.redirect_url),
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

            verified = consume_verified_challenge()
            return LoginResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
                next_url=verified.get("next_url"),
            )
        except HTTPException:
            raise
        except WrongApplicationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "wrong_application",
                    "message": "This account cannot sign in to the requested application.",
                },
            ) from exc
        except OutlabsAuthException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise

    @router.post(
        "/access-code/request",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Request access code",
        description=(
            "Generate a one-time access code by email or verified WhatsApp phone "
            "and expose it to the host delivery hook."
        ),
    )
    async def request_access_code(
        data: AccessCodeRequest,
        request: Request,
        session: AsyncSession = Depends(auth.uow),
    ):
        """
        Request an access code by email or verified phone.

        This endpoint never reveals whether the identifier belongs to an account.
        Phone requests only match users with ``phone_verified``. If a usable
        account exists, it calls `on_after_access_code_requested` with the plain
        code so the host can deliver via email/WhatsApp.
        """
        if not auth.config.enable_access_codes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Access code authentication is not enabled",
            )

        rate_limit_identifier = data.email or data.phone
        assert rate_limit_identifier is not None
        delivery_channel = data.channel or ("email" if data.email else "whatsapp")

        is_limited, seconds_until_reset = await check_access_code_request_rate_limit(
            rate_limit_identifier,
            redis_client=getattr(auth, "redis_client", None),
            channel=delivery_channel,
            max_requests=auth.config.access_code_request_rate_limit_max,
            window_seconds=auth.config.access_code_request_rate_limit_window_seconds,
        )
        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Too many access code requests. Please try again later.",
                    "retry_after_seconds": seconds_until_reset,
                    "retry_after_minutes": round(seconds_until_reset / 60, 1),
                },
                headers={"Retry-After": str(max(seconds_until_reset, 1))},
            )

        try:
            if data.email:
                user = await auth.user_service.get_user_by_email(session, data.email)
                challenge_recipient = None
                challenge_type = "access_code"
            else:
                user = await auth.user_service.get_user_by_verified_phone(session, data.phone or "")
                challenge_recipient = data.phone
                challenge_type = "whatsapp_otp" if delivery_channel == "whatsapp" else "sms_otp"

            if not user:
                return None

            if getattr(user.status, "value", user.status) != "active" or user.is_locked:
                return None

            # DD-059: resolve the frontend profile and canonical return target
            # once, at request time; fail-closed outcomes skip generation and
            # delivery while the outward 204 stays opaque.
            resolver = getattr(auth, "frontend_resolver", None)
            dispatch = await prepare_challenge_dispatch(
                resolver,
                session,
                user,
                flow=FrontendFlow.ACCESS_CODE,
                requested_app=data.app,
                redirect_url=data.redirect_url,
            )
            if not dispatch.deliver:
                return None

            code = await auth.auth_service.generate_access_code(
                session,
                user,
                recipient=challenge_recipient,
                channel=delivery_channel,
                redirect_url=data.redirect_url,
                profile_id=dispatch.profile_id,
                next_url=dispatch.next_url,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            if dispatch.profile_id is not None:
                stash_send_profile(dispatch.profile_id)
                stash_send_next_url(dispatch.next_url)
            await auth.user_service.on_after_access_code_requested(
                user,
                code,
                request,
                redirect_url=(dispatch.next_url if resolver is not None else data.redirect_url),
                delivery_channel=delivery_channel,
                challenge_type=challenge_type,
            )
        except Exception as e:
            if auth.observability:
                auth.observability.logger.error(
                    "access_code_request_error",
                    email=data.email,
                    phone=data.phone,
                    error=str(e),
                )

        return None

    @router.post(
        "/access-code/verify",
        response_model=LoginResponse,
        summary="Verify access code",
        description="Exchange a one-time access code (email or WhatsApp phone) for JWT tokens.",
    )
    async def verify_access_code(
        data: AccessCodeVerifyRequest,
        request: Request,
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """
        Verify an access code and return JWT tokens.
        """
        if not auth.config.enable_access_codes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Access code authentication is not enabled",
            )

        rate_limit_identifier = data.email or data.phone
        assert rate_limit_identifier is not None
        delivery_channel = data.channel or ("email" if data.email else "whatsapp")

        is_limited, seconds_until_reset = await check_access_code_verify_rate_limit(
            rate_limit_identifier,
            redis_client=getattr(auth, "redis_client", None),
            channel=delivery_channel,
            max_requests=auth.config.access_code_verify_rate_limit_max,
            window_seconds=auth.config.access_code_verify_rate_limit_window_seconds,
        )
        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Too many access code verification attempts. Please try again later.",
                    "retry_after_seconds": seconds_until_reset,
                    "retry_after_minutes": round(seconds_until_reset / 60, 1),
                },
                headers={"Retry-After": str(max(seconds_until_reset, 1))},
            )

        try:
            user, tokens = await auth.auth_service.verify_access_code(
                session,
                email=data.email,
                phone=data.phone,
                code=data.code,
                channel=delivery_channel,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            await auth.user_service.on_after_login(user, request)
            obs.log_event("access_code_verified", user_id=str(user.id))

            verified = consume_verified_challenge()
            return LoginResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
                next_url=verified.get("next_url"),
            )
        except HTTPException:
            raise
        except WrongApplicationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "wrong_application",
                    "message": "This account cannot sign in to the requested application.",
                },
            ) from exc
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
            if not auth.config.enable_invitations:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invitation endpoints are disabled",
                )
            actor_user_id = UUID(obs.user_id) if obs.user_id else None
            actor_user = (
                await auth.user_service.get_user_by_id(session, actor_user_id) if actor_user_id is not None else None
            )
            if data.is_superuser and not (actor_user and actor_user.is_superuser):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only superusers can invite superusers",
                )

            role_ids = [UUID(rid) for rid in data.role_ids] if data.role_ids else []
            target_entity_id = UUID(data.entity_id) if data.entity_id else None
            containment_role_ids = role_ids
            if target_entity_id is not None:
                if actor_user_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authenticated actor is required for membership delegation",
                    )
                can_create_membership = await auth.permission_service.check_permission(
                    session,
                    actor_user_id,
                    "membership:create_tree",
                    entity_id=target_entity_id,
                    user=actor_user,
                )
                if not can_create_membership:
                    raise PermissionDeniedError(message="Insufficient permissions to create this entity membership")
                if auth.membership_service:
                    auto_roles = await auth.membership_service.get_auto_assigned_roles_for_entity(
                        session, target_entity_id
                    )
                    containment_role_ids = list({*role_ids, *(role.id for role in auto_roles)})

            if containment_role_ids and actor_user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authenticated actor is required for role delegation",
                )
            if containment_role_ids:
                assert actor_user_id is not None
                await require_can_delegate_roles(
                    session,
                    auth=auth,
                    actor_user_id=actor_user_id,
                    role_ids=containment_role_ids,
                    entity_id=target_entity_id,
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
            if not auth.config.enable_invitations:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invitation endpoints are disabled",
                )
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
                app=data.app,
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
        except WrongApplicationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "wrong_application",
                    "message": "This account cannot sign in to the requested application.",
                },
            ) from exc
        except OutlabsAuthException:
            raise
        except Exception as e:
            obs.log_500_error(e)
            raise

    return mark_auth_surface(router, "auth")
