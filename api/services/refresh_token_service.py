from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime
from typing import Optional

from ..models.refresh_token_model import RefreshTokenModel

class RefreshTokenService:
    """
    Service for refresh token-related business logic.
    """
    async def create_refresh_token(
        self, 
        db: AsyncIOMotorDatabase, 
        *,
        user_id: ObjectId, 
        jti: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> RefreshTokenModel:
        """
        Creates and stores a new refresh token record.
        """
        token_data = RefreshTokenModel(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await db.refresh_tokens.insert_one(token_data.model_dump(by_alias=True))
        return token_data

    async def get_refresh_token_by_jti(self, db: AsyncIOMotorDatabase, jti: str) -> Optional[RefreshTokenModel]:
        """
        Retrieves a refresh token by its JTI.
        """
        token_data = await db.refresh_tokens.find_one({"jti": jti})
        if token_data:
            return RefreshTokenModel(**token_data)
        return None
    
    async def revoke_token(self, db: AsyncIOMotorDatabase, jti: str) -> bool:
        """
        Marks a specific refresh token as revoked.
        """
        result = await db.refresh_tokens.update_one(
            {"jti": jti},
            {"$set": {"is_revoked": True}}
        )
        return result.modified_count > 0

    async def revoke_all_tokens_for_user(self, db: AsyncIOMotorDatabase, user_id: ObjectId) -> int:
        """
        Revokes all refresh tokens for a given user.
        """
        result = await db.refresh_tokens.update_many(
            {"user_id": user_id, "is_revoked": False},
            {"$set": {"is_revoked": True}}
        )
        return result.modified_count

refresh_token_service = RefreshTokenService() 