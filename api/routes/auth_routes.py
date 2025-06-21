from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from jose import JWTError
from datetime import timedelta, datetime
from typing import Tuple, List

from ..database import get_database
from ..services.user_service import user_service
from ..services.security_service import security_service
from ..services.refresh_token_service import refresh_token_service
from ..config import settings
from ..schemas.auth_schema import TokenSchema, TokenDataSchema, SessionResponseSchema
from ..schemas.user_schema import UserResponseSchema
from ..schemas.password_reset_schema import PasswordResetRequestSchema, PasswordResetConfirmSchema, PasswordChangeSchema
from ..dependencies import get_current_user, get_current_user_with_token
from ..models.user_model import UserModel

router = APIRouter(
    prefix="/v1/auth",
    tags=["Authentication"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)

@router.post("/login", response_model=TokenSchema)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Authenticates a user and returns an access token.
    """
    user = await user_service.get_user_by_email(db, form_data.username)
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
        db,
        user_id=user.id,
        jti=jti,
        expires_at=expires_at,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    # Create Access Token, including client_account_id
    access_token_data = {
        "sub": str(user.id), 
        "jti": jti,
        "client_account_id": str(user.client_account_id) if user.client_account_id else None
    }
    access_token = security_service.create_access_token(access_token_data)

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=TokenSchema)
async def refresh_access_token(
    request: Request,
    refresh_token_str: str = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    if not refresh_token_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found")

    try:
        payload = security_service.decode_access_token(refresh_token_str)
        jti = payload.jti
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    db_token = await refresh_token_service.get_refresh_token_by_jti(db, jti)
    if not db_token or db_token.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or invalid")

    user = await user_service.get_user_by_id(db, db_token.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Issue new tokens (implementing token rotation)
    # Revoke the old refresh token
    await refresh_token_service.revoke_token(db, jti)
    
    # Create new refresh token
    new_refresh_token, new_jti, new_expires_at = security_service.create_refresh_token(data={"sub": str(user.id)})
    await refresh_token_service.create_refresh_token(
        db, user_id=user.id, jti=new_jti, expires_at=new_expires_at,
        ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Create new access token linked to the new refresh token
    new_access_token_data = {
        "sub": str(user.id), 
        "jti": new_jti,
        "client_account_id": str(user.client_account_id) if user.client_account_id else None
    }
    new_access_token = security_service.create_access_token(new_access_token_data)
    
    return {"access_token": new_access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Revokes the current user's refresh token.
    """
    _, token_data = user_and_token
    jti = token_data.jti
    if jti:
        await refresh_token_service.revoke_token(db, jti)
    
    # Optional: Add the access token to a blacklist cache (e.g., Redis)
    # for immediate invalidation before it expires.

@router.post("/logout_all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Revokes all of the current user's refresh tokens.
    """
    await refresh_token_service.revoke_all_tokens_for_user(db, current_user.id)

@router.get("/me", response_model=UserResponseSchema)
async def read_users_me(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get the profile of the currently authenticated user.
    """
    # Convert UserModel to dict and ensure ObjectId fields are strings
    user_dict = current_user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    if user_dict.get("client_account_id"):
        user_dict["client_account_id"] = str(user_dict["client_account_id"])
    return user_dict

@router.post("/password/reset-request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request_data: PasswordResetRequestSchema,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Initiates a password reset process. In a real app, this would send an email.
    For this implementation, it returns the token directly for testing purposes.
    """
    user = await user_service.get_user_by_email(db, request_data.email)
    if user:
        # In a real application, you would NOT return the token.
        # You would send it in an email.
        token = await security_service.create_password_reset_token(db, user_id=user.id)
        
        # This is where you would call an email service:
        # email_service.send_password_reset_email(user.email, token)

        return {"message": "If a user with this email exists, a password reset link has been sent.", "token": token}
    
    # Return a generic response to prevent user enumeration
    return {"message": "If a user with this email exists, a password reset link has been sent."}

@router.post("/password/reset-confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    request_data: PasswordResetConfirmSchema,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Confirms a password reset using the token from the email.
    """
    token_doc = await security_service.verify_password_reset_token(db, token=request_data.token)
    
    if not token_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )

    # Update the user's password
    await user_service.update_password(db, user_id=token_doc.user_id, new_password=request_data.new_password)

    # Revoke all of the user's existing sessions for security
    await refresh_token_service.revoke_all_tokens_for_user(db, token_doc.user_id)

    # Mark the token as used
    await db.password_reset_tokens.update_one(
        {"_id": token_doc.id},
        {"$set": {"used_at": datetime.utcnow()}}
    )

@router.get("/sessions", response_model=List[SessionResponseSchema])
async def get_active_sessions(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Lists active sessions for the authenticated user.
    """
    sessions = await refresh_token_service.get_sessions_for_user(db, current_user.id)
    return sessions

@router.delete("/sessions/{jti}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    jti: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Revokes a specific session (refresh token) by its JTI.
    """
    success = await refresh_token_service.revoke_session_by_jti(db, user_id=current_user.id, jti=jti)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or you do not have permission to revoke it."
        )

@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request_data: PasswordChangeSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Allows an authenticated user to change their password.
    """
    # Verify the current password
    if not security_service.verify_password(request_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password."
        )
    
    # Update to the new password
    await user_service.update_password(db, user_id=current_user.id, new_password=request_data.new_password)
    
    # For security, revoke all other sessions when a password is changed
    await refresh_token_service.revoke_all_tokens_for_user(db, current_user.id) 