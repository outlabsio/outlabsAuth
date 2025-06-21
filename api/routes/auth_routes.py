from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from jose import JWTError
from datetime import timedelta
from typing import Tuple

from ..database import get_database
from ..services.user_service import user_service
from ..services.security_service import security_service
from ..services.refresh_token_service import refresh_token_service
from ..config import settings
from ..schemas.auth_schema import TokenSchema, TokenDataSchema
from ..schemas.user_schema import UserResponseSchema
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
    refresh_token, jti, expires_at = security_service.create_refresh_token(data={"sub": str(user.id)})
    
    # Store refresh token in DB
    await refresh_token_service.create_refresh_token(
        db,
        user_id=user.id,
        jti=jti,
        expires_at=expires_at,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    # Create Access Token, linked to the refresh token by its JTI
    access_token = security_service.create_access_token(
        data={"sub": str(user.id), "jti": jti}
    )

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
    new_access_token = security_service.create_access_token(data={"sub": str(user.id), "jti": new_jti})
    
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
    return current_user 