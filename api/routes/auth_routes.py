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
from api.services.auth_service import AuthService
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
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
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
    
    return UserInfoResponse(
        id=str(user.id),
        email=user.email,
        profile=user.profile.model_dump() if user.profile else {},
        is_active=user.is_active,
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Login with email and password
    
    Args:
        request: FastAPI request object
        form_data: OAuth2 form data (username=email, password)
    
    Returns:
        Access and refresh tokens
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
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login/json", response_model=TokenResponse)
async def login_json(
    request: Request,
    login_data: LoginRequest
):
    """
    Login with JSON payload (alternative to form data)
    
    Args:
        request: FastAPI request object
        login_data: Login credentials
    
    Returns:
        Access and refresh tokens
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
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest
):
    """
    Refresh access token using refresh token
    
    Args:
        request: FastAPI request object
        refresh_data: Refresh token
    
    Returns:
        New access and refresh tokens
    """
    ip_address = request.client.host if request.client else None
    
    try:
        access_token, refresh_token = await AuthService.refresh_access_token(
            refresh_data.refresh_token,
            ip_address=ip_address
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
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
async def logout(logout_data: LogoutRequest):
    """
    Logout by revoking refresh token
    
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


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(current_user: UserModel = Depends(get_current_user)):
    """
    Get current user information
    
    Args:
        current_user: Authenticated user
    
    Returns:
        User information
    """
    return UserInfoResponse(
        id=str(current_user.id),
        email=current_user.email,
        profile=current_user.profile.model_dump() if current_user.profile else {},
        is_active=current_user.is_active,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


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