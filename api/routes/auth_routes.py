"""
Authentication routes
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional

from api.schemas.auth_schema import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    EmailVerificationRequest,
    UserInfoResponse,
    ChangePasswordRequest,
    RegisterRequest
)
from api.schemas.user_schema import UserResponse
from api.services.auth_service import AuthService
from api.services.email_service import email_service
from api.services.user_service import UserService
from api.models import UserModel
from api.utils.jwt_utils import decode_token
from api.config import settings

router = APIRouter()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserModel:
    """
    Get current authenticated user from token
    
    Args:
        token: JWT access token
    
    Returns:
        Current user
    
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user = await UserModel.get(payload["sub"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.can_authenticate():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not active"
            )
        
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


@router.post("/register", response_model=UserInfoResponse)
async def register(request: RegisterRequest):
    """
    Register a new user
    
    Args:
        request: Registration data
    
    Returns:
        Created user information
    """
    # Check if user already exists
    existing_user = await UserModel.find_one(UserModel.email == request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = UserModel(
        email=request.email,
        hashed_password=AuthService.hash_password(request.password),
        profile={
            "first_name": request.first_name,
            "last_name": request.last_name,
            "phone": request.phone
        }
    )
    await user.save()
    
    # Send welcome email
    await email_service.send_welcome_email(user)
    
    return UserInfoResponse(
        id=str(user.id),
        email=user.email,
        profile=user.profile.model_dump() if user.profile else {},
        status=user.status,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Login with email and password (WEB FLOW - HTTP-only cookies)
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        form_data: OAuth2 form data (username=email, password)
    
    Returns:
        Access token only (refresh token set as HTTP-only cookie)
    """
    # Get client IP
    ip_address = request.client.host if request.client else None
    
    # Authenticate user (username field contains email)
    user = await AuthService.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create tokens
    access_token, refresh_token, _ = await AuthService.create_tokens(
        user,
        device_info={"user_agent": request.headers.get("user-agent")},
        ip_address=ip_address
    )
    
    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 30 days in seconds
        httponly=True,
        secure=settings.ENVIRONMENT != "development",  # Only HTTPS in production
        samesite="lax"
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token="",  # Don't expose in JSON
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login/json", response_model=TokenResponse)
async def login_json(
    request: Request,
    response: Response,
    login_data: LoginRequest
):
    """
    Login with JSON payload (WEB FLOW - HTTP-only cookies)
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        login_data: Login credentials
    
    Returns:
        Access token only (refresh token set as HTTP-only cookie)
    """
    # Get client IP
    ip_address = request.client.host if request.client else None
    
    # Authenticate user
    user = await AuthService.authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create tokens
    access_token, refresh_token, _ = await AuthService.create_tokens(
        user,
        device_info=login_data.device_info or {"user_agent": request.headers.get("user-agent")},
        ip_address=ip_address
    )
    
    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 30 days in seconds
        httponly=True,
        secure=settings.ENVIRONMENT != "development",  # Only HTTPS in production
        samesite="lax"
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token="",  # Don't expose in JSON
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response
):
    """
    Refresh access token using HTTP-only cookie (WEB FLOW)
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
    
    Returns:
        New access token (new refresh token set as HTTP-only cookie)
    """
    ip_address = request.client.host if request.client else None
    
    # Get refresh token from HTTP-only cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token found"
        )
    
    try:
        access_token, new_refresh_token = await AuthService.refresh_access_token(
            refresh_token,
            ip_address=ip_address
        )
        
        # Set new refresh token as HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 30 days in seconds
            httponly=True,
            secure=settings.ENVIRONMENT != "development",  # Only HTTPS in production
            samesite="lax"
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token="",  # Don't expose in JSON
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Logout by revoking HTTP-only cookie refresh token (WEB FLOW)
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
    
    Returns:
        Success message
    """
    # Get refresh token from HTTP-only cookie
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        # Revoke the token in database
        await AuthService.logout(refresh_token)
    
    # Clear the HTTP-only cookie
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")
    
    return {"message": "Successfully logged out"}


# Mobile/App endpoints (JSON body flows)
@router.post("/mobile/login", response_model=TokenResponse)
async def mobile_login(
    request: Request,
    login_data: LoginRequest
):
    """
    Login for mobile/app (JSON FLOW - tokens in response body)
    
    Args:
        request: FastAPI request object
        login_data: Login credentials
    
    Returns:
        Both access and refresh tokens in JSON body
    """
    # Get client IP
    ip_address = request.client.host if request.client else None
    
    # Authenticate user
    user = await AuthService.authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create tokens
    access_token, refresh_token, _ = await AuthService.create_tokens(
        user,
        device_info=login_data.device_info or {"user_agent": request.headers.get("user-agent")},
        ip_address=ip_address
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,  # Include in JSON for mobile apps
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/mobile/refresh", response_model=TokenResponse)
async def mobile_refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest
):
    """
    Refresh token for mobile/app (JSON FLOW - refresh token in request body)
    
    Args:
        request: FastAPI request object
        refresh_data: Refresh token
    
    Returns:
        New access and refresh tokens in JSON body
    """
    ip_address = request.client.host if request.client else None
    
    try:
        access_token, refresh_token = await AuthService.refresh_access_token(
            refresh_data.refresh_token,
            ip_address=ip_address
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # Include in JSON for mobile apps
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/mobile/logout")
async def mobile_logout(logout_data: LogoutRequest):
    """
    Logout for mobile/app (JSON FLOW - refresh token in request body)
    
    Args:
        logout_data: Refresh token to revoke
    
    Returns:
        Success message
    """
    success = await AuthService.logout(logout_data.refresh_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    
    return {"message": "Successfully logged out"}


@router.post("/logout/all")
async def logout_all_devices(current_user: UserModel = Depends(get_current_user)):
    """
    Logout from all devices
    
    Args:
        current_user: Authenticated user
    
    Returns:
        Number of sessions terminated
    """
    count = await AuthService.logout_all_devices(str(current_user.id))
    return {"message": f"Logged out from {count} device(s)"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserModel = Depends(get_current_user)):
    """
    Get current user information with entity memberships and roles
    
    Args:
        current_user: Authenticated user
    
    Returns:
        Full user information including entities and permissions
    """
    # Enrich user with entity memberships
    user_data = await UserService.enrich_user_with_entities(current_user)
    return UserResponse(**user_data)


@router.post("/password/reset")
async def request_password_reset(reset_data: PasswordResetRequest):
    """
    Request password reset token
    
    Args:
        reset_data: Email address
    
    Returns:
        Success message (always returns success for security)
    """
    token = await AuthService.create_password_reset_request(reset_data.email)
    
    # TODO: Send email with reset token
    # For now, we'll just return success
    # In production, never return the token in the response
    
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/password/reset/confirm")
async def confirm_password_reset(reset_data: PasswordResetConfirm):
    """
    Reset password with token
    
    Args:
        reset_data: Reset token and new password
    
    Returns:
        Success message
    """
    try:
        await AuthService.reset_password(reset_data.token, reset_data.new_password)
        return {"message": "Password successfully reset"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )


@router.post("/password/change")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Change password for authenticated user
    
    Args:
        password_data: Current and new passwords
        current_user: Authenticated user
    
    Returns:
        Success message
    """
    # Verify current password
    if not AuthService.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.hashed_password = AuthService.hash_password(password_data.new_password)
    current_user.last_password_change = datetime.now(timezone.utc)
    await current_user.save()
    
    # Revoke all refresh tokens for security
    await AuthService.logout_all_devices(str(current_user.id))
    
    return {"message": "Password successfully changed. Please login again."}


@router.post("/email/verify")
async def verify_email(verification_data: EmailVerificationRequest):
    """
    Verify email address with token
    
    Args:
        verification_data: Verification token
    
    Returns:
        Success message
    """
    try:
        await AuthService.verify_email(verification_data.token)
        return {"message": "Email successfully verified"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )


