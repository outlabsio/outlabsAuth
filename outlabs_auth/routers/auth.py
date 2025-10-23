from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    AccountInactiveError,
    RefreshTokenInvalidError,
)
from outlabs_auth.services.auth import AuthService, TokenPair
from outlabs_auth.schemas.user import UserRead


class UserLoginSchema(BaseModel):
    email: str
    password: str


class RefreshTokenSchema(BaseModel):
    refresh_token: str


def get_auth_router(auth_service: AuthService) -> APIRouter:
    router = APIRouter()

    @router.post("/login", response_model=TokenPair)
    async def login(form_data: UserLoginSchema):
        try:
            _, token_pair = await auth_service.login(
                email=form_data.email, password=form_data.password
            )
            return token_pair
        except (InvalidCredentialsError, AccountInactiveError, AccountLockedError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

    @router.post("/logout")
    async def logout(refresh_token_data: RefreshTokenSchema):
        success = await auth_service.logout(refresh_token_data.refresh_token)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Refresh token not found or already revoked",
            )
        return {"success": True}

    @router.post("/refresh", response_model=TokenPair)
    async def refresh_token(refresh_token_data: RefreshTokenSchema):
        try:
            token_pair = await auth_service.refresh_access_token(
                refresh_token_data.refresh_token
            )
            return token_pair
        except RefreshTokenInvalidError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

    return router
