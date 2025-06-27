from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Response, Query
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError
from datetime import timedelta, datetime
from typing import Tuple, List, Optional, Union
from beanie import PydanticObjectId

from ..services.user_service import user_service
from ..services.security_service import security_service
from ..services.refresh_token_service import refresh_token_service
from ..config import settings
from ..schemas.auth_schema import TokenSchema, TokenDataSchema, SessionResponseSchema
from ..schemas.user_schema import UserResponseSchema
from ..schemas.password_reset_schema import PasswordResetRequestSchema, PasswordResetConfirmSchema, PasswordChangeSchema
from ..dependencies import get_current_user, get_current_user_with_token, convert_user_to_response
from ..models.user_model import UserModel
from ..models.password_reset_token_model import PasswordResetTokenModel
from ..services.group_service import group_service

router = APIRouter(
    prefix="/v1/auth",
    tags=["Authentication"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)

@router.post("/login")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    use_cookies: Optional[bool] = Query(False, description="Use HTTP-only cookies instead of JSON response"),
    use_enriched_tokens: Optional[bool] = Query(None, description="Include user data and permissions in access token (default: true)")
) -> Union[TokenSchema, dict]:
    """
    Authenticates a user and returns an access token.
    If use_cookies=true, sets HTTP-only cookies instead of JSON response.
    By default, returns enriched tokens with user permissions and role data.
    """
    user = await user_service.get_user_by_email(form_data.username)
    if not user or not security_service.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create Refresh Token
    refresh_token, jti, expires_at = security_service.create_refresh_token(
        data={"sub": str(user.id)}
    )

    # Store refresh token in DB
    await refresh_token_service.create_refresh_token(
        user_id=user.id,
        jti=jti,
        expires_at=expires_at,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    # Determine whether to use enriched tokens
    should_use_enriched = use_enriched_tokens if use_enriched_tokens is not None else settings.ENABLE_ENRICHED_TOKENS_BY_DEFAULT
    
    # Create Access Token - enriched by default, basic if explicitly disabled
    client_account_id = str(user.client_account.id) if user.client_account else None
    
    if should_use_enriched:
        # Create enriched access token with user data and permissions
        access_token = await security_service.create_enriched_access_token(
            user_id=str(user.id),
            client_account_id=client_account_id,
            jti=jti
        )
    else:
        # Create basic access token (for clients that prefer minimal tokens)
        access_token_data = {
            "sub": str(user.id),
            "jti": jti,
            "client_account_id": client_account_id
        }
        access_token = security_service.create_access_token(access_token_data)

    if use_cookies:
        # Set HTTP-only cookies
        # Use secure=False for local development (HTTP), secure=True for production (HTTPS)
        is_secure = not (request.url.hostname in ["localhost", "127.0.0.1"] or request.url.scheme == "http")
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            httponly=True,
            secure=is_secure,  # Dynamic based on environment
            samesite="strict"
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # Convert to seconds
            httponly=True,
            secure=is_secure,  # Dynamic based on environment
            samesite="strict"
        )
        return {"message": "Login successful", "token_type": "cookie"}
    else:
        # Return JSON tokens (current behavior)
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh")
async def refresh_access_token(
    request: Request,
    response: Response,
    authorization: str = Header(None),
    use_cookies: Optional[bool] = Query(False, description="Use HTTP-only cookies"),
    use_enriched_tokens: Optional[bool] = Query(None, description="Include user data and permissions in access token (default: true)")
) -> Union[TokenSchema, dict]:
    # Try to get refresh token from cookies first, then from header
    refresh_token_str = None
    
    if use_cookies:
        refresh_token_str = request.cookies.get("refresh_token")
        if not refresh_token_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found in cookies")
    else:
        # Extract token from Authorization header manually to provide specific error messages
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found")
        
        refresh_token_str = authorization.split(" ")[1]
        if not refresh_token_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found")

    payload = security_service.decode_refresh_token(refresh_token_str)
    jti = payload.jti

    db_token = await refresh_token_service.get_refresh_token_by_jti(jti)
    if not db_token or db_token.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or invalid")

    # With Beanie Links, we need to fetch the user reference or access it properly
    # db_token.user is a Link object, we need to get the referenced user ID
    user_id = db_token.user.ref.id if hasattr(db_token.user, 'ref') else db_token.user.id
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Issue new tokens (implementing token rotation)
    # Revoke the old refresh token
    await refresh_token_service.revoke_token(jti)

    # Create new tokens (implementing token rotation)
    new_refresh_token, new_jti, new_expires_at = security_service.create_refresh_token(data={"sub": str(user.id)})
    await refresh_token_service.create_refresh_token(
        user_id=user.id, jti=new_jti, expires_at=new_expires_at,
        ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Determine whether to use enriched tokens
    should_use_enriched = use_enriched_tokens if use_enriched_tokens is not None else settings.ENABLE_ENRICHED_TOKENS_BY_DEFAULT
    
    # Create new access token - enriched by default, basic if explicitly disabled
    client_account_id = str(user.client_account.id) if user.client_account else None
    
    if should_use_enriched:
        # Create enriched access token with user data and permissions
        new_access_token = await security_service.create_enriched_access_token(
            user_id=str(user.id),
            client_account_id=client_account_id,
            jti=new_jti
        )
    else:
        # Create basic access token (for clients that prefer minimal tokens)
        new_access_token_data = {
            "sub": str(user.id),
            "jti": new_jti,
            "client_account_id": client_account_id
        }
        new_access_token = security_service.create_access_token(new_access_token_data)

    if use_cookies:
        # Update HTTP-only cookies
        # Use secure=False for local development (HTTP), secure=True for production (HTTPS)
        is_secure = not (request.url.hostname in ["localhost", "127.0.0.1"] or request.url.scheme == "http")
        
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=True,
            secure=is_secure,  # Dynamic based on environment
            samesite="strict"
        )
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=is_secure,  # Dynamic based on environment
            samesite="strict"
        )
        return {"message": "Tokens refreshed", "token_type": "cookie"}
    else:
        return {"access_token": new_access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    use_cookies: Optional[bool] = Query(False, description="Clear HTTP-only cookies")
):
    """
    Revokes the current user's refresh token.
    If use_cookies=true, also clears the HTTP-only cookies.
    """
    _, token_data = user_and_token
    jti = token_data.jti
    if jti:
        await refresh_token_service.revoke_token(jti)

    if use_cookies:
        # Clear HTTP-only cookies
        response.delete_cookie(key="access_token", httponly=True, secure=True, samesite="strict")
        response.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="strict")

    # Optional: Add the access token to a blacklist cache (e.g., Redis)
    # for immediate invalidation before it expires.

@router.post("/logout_all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Revokes all of the current user's refresh tokens.
    """
    await refresh_token_service.revoke_all_tokens_for_user(current_user.id)

@router.get("/me")
async def get_current_user_info(
    current_user: UserModel = Depends(get_current_user)
) -> UserResponseSchema:
    """
    Returns the current user's information based on the access token.
    """
    user_dict = convert_user_to_response(current_user)
    
    # Get effective permissions for response
    permission_details = await user_service.get_user_effective_permission_details(current_user.id)
    user_dict["permissions"] = permission_details
    
    return UserResponseSchema.model_validate(user_dict)

@router.post("/password/reset-request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request_data: PasswordResetRequestSchema
):
    """
    Initiates a password reset process. In a real app, this would send an email.
    For this implementation, it returns the token directly for testing purposes.
    """
    user = await user_service.get_user_by_email(request_data.email)
    if user:
        # In a real application, you would NOT return the token.
        # You would send it in an email.
        token = await security_service.create_password_reset_token(user.id)

        # This is where you would call an email service:
        # email_service.send_password_reset_email(user.email, token)

        return {"message": "If a user with this email exists, a password reset link has been sent.", "token": token}

    # Return a generic response to prevent user enumeration
    return {"message": "If a user with this email exists, a password reset link has been sent."}

@router.post("/password/reset-confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    request_data: PasswordResetConfirmSchema
):
    """
    Confirms a password reset using the token from the email.
    """
    token_doc = await security_service.verify_password_reset_token(request_data.token)

    if not token_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )

    # Update the user's password
    # With Beanie Links, we need to get the user ID properly
    user_id = token_doc.user.ref.id if hasattr(token_doc.user, 'ref') else token_doc.user.id
    await user_service.update_password(user_id, request_data.new_password)

    # Revoke all of the user's existing sessions for security
    await refresh_token_service.revoke_all_tokens_for_user(user_id)

    # Mark the token as used
    token_doc.used_at = datetime.utcnow()
    await token_doc.save()

@router.get("/sessions", response_model=List[SessionResponseSchema])
async def get_active_sessions(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get all active sessions for the current user.
    """
    sessions = await refresh_token_service.get_sessions_for_user(current_user.id)
    return sessions

@router.delete("/sessions/{jti}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    jti: str,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Revoke a specific session by JTI.
    """
    success = await refresh_token_service.revoke_session_by_jti(current_user.id, jti)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked."
        )

@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request_data: PasswordChangeSchema,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Change the current user's password.
    """
    # Verify current password
    if not security_service.verify_password(request_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )

    # Update password
    await user_service.update_password(current_user.id, request_data.new_password)

    # Revoke all existing sessions for security
    await refresh_token_service.revoke_all_tokens_for_user(current_user.id)

@router.get("/token-info")
async def get_token_info(
    token: str = Depends(oauth2_scheme)
) -> dict:
    """
    Returns information about the current access token.
    Useful for frontend to understand token capabilities.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required"
        )
    
    try:
        # Decode the access token
        token_data = security_service.decode_access_token(token)
        
        if hasattr(token_data, 'permissions') and hasattr(token_data, 'roles'):
            # Enriched token (standard format)
            return {
                "token_type": "enriched",
                "user_id": token_data.sub,
                "client_account_id": token_data.client_account_id,
                "permissions_count": len(token_data.permissions),
                "roles_count": len(token_data.roles),
                "scopes": token_data.scopes,
                "expires_at": token_data.exp,
                "issued_at": token_data.iat,
                "user_email": token_data.user.email,
                "mfa_enabled": token_data.session.mfa_enabled,
                "locale": token_data.session.locale
            }
        else:
            # Basic token (minimal format)
            return {
                "token_type": "basic",
                "user_id": token_data.user_id,
                "client_account_id": token_data.client_account_id,
                "message": "Token contains minimal data - use default login for enriched features"
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        ) 