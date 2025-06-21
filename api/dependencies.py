from bson import ObjectId
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from .database import get_database
from .services.security_service import security_service
from .services.user_service import user_service
from .models.user_model import UserModel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")

def valid_object_id(id: str):
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid ObjectId: {id}"
        )

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> UserModel:
    """
    Decodes JWT token to get user_id, then retrieves user from DB.
    This is the primary dependency for endpoint authorization.
    """
    token_data = security_service.decode_access_token(token)
    user = await user_service.get_user_by_id(db, ObjectId(token_data.user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user 