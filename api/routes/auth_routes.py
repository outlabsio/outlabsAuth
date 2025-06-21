from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import timedelta

from ..database import get_database
from ..services.user_service import user_service
from ..services.security_service import security_service
from ..config import settings
from ..schemas.auth_schema import TokenSchema
from ..schemas.user_schema import UserResponseSchema
from ..dependencies import get_current_user
from ..models.user_model import UserModel

router = APIRouter(
    prefix="/v1/auth",
    tags=["Authentication"]
)

@router.post("/login", response_model=TokenSchema)
async def login_for_access_token(
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
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security_service.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponseSchema)
async def read_users_me(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get the profile of the currently authenticated user.
    """
    return current_user 