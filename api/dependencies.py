from beanie import PydanticObjectId
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Tuple

from .services.security_service import security_service
from .services.user_service import user_service
from .services.role_service import role_service
from .services.group_service import group_service
from .models.user_model import UserModel
from .schemas.auth_schema import TokenDataSchema

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")

def valid_object_id(id: str):
    try:
        return PydanticObjectId(id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid ObjectId: {id}"
        )

def valid_account_id(account_id: str):
    try:
        return PydanticObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid ObjectId: {account_id}"
        )

async def get_current_user_with_token(
    token: str = Depends(oauth2_scheme)
) -> Tuple[UserModel, TokenDataSchema]:
    """
    Decodes JWT, then retrieves user from DB using Beanie ODM. Returns user and token payload.
    """
    token_data = security_service.decode_access_token(token)
    user = await user_service.get_user_by_id(PydanticObjectId(token_data.user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user, token_data

def has_permission(required_permission: str):
    """
    Dependency factory to check if the current user has the required permission.
    Now includes permissions from both direct roles and group memberships.
    """
    async def _has_permission(
        user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
    ):
        current_user, _ = user_and_token
        
        # Get all effective permissions (direct roles + group roles)
        user_permissions = await group_service.get_user_effective_permissions(current_user.id)
        
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action."
            )
        return current_user
    return _has_permission

async def get_current_user(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
) -> UserModel:
    return user_and_token[0] 