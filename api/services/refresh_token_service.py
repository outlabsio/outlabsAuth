from beanie import PydanticObjectId
from datetime import datetime
from typing import Optional, List

from ..models.refresh_token_model import RefreshTokenModel
from ..models.user_model import UserModel

class RefreshTokenService:
    """
    Service for refresh token-related business logic using Beanie ODM.
    """
    async def create_refresh_token(
        self,
        user_id: PydanticObjectId, 
        jti: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> RefreshTokenModel:
        """
        Creates and stores a new refresh token record using Beanie ODM.
        """
        # Get the user to create the Link
        user = await UserModel.get(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")
            
        token_data = RefreshTokenModel(
            user=user,
            jti=jti,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await token_data.insert()
        return token_data

    async def get_refresh_token_by_jti(self, jti: str) -> Optional[RefreshTokenModel]:
        """
        Retrieves a refresh token by its JTI using Beanie ODM.
        """
        return await RefreshTokenModel.find_one(RefreshTokenModel.jti == jti)
    
    async def revoke_token(self, jti: str) -> bool:
        """
        Marks a specific refresh token as revoked using Beanie ODM.
        """
        token = await self.get_refresh_token_by_jti(jti)
        if token:
            token.is_revoked = True
            await token.save()
            return True
        return False

    async def revoke_all_tokens_for_user(self, user_id: PydanticObjectId) -> int:
        """
        Revokes all refresh tokens for a given user using Beanie ODM.
        """
        user = await UserModel.get(user_id)
        if not user:
            return 0
            
        tokens = await RefreshTokenModel.find(
            RefreshTokenModel.user.id == user_id,
            RefreshTokenModel.is_revoked == False
        ).to_list()
        
        count = 0
        for token in tokens:
            token.is_revoked = True
            await token.save()
            count += 1
            
        return count

    async def get_sessions_for_user(self, user_id: PydanticObjectId) -> List[RefreshTokenModel]:
        """
        Retrieves all active (non-revoked) refresh tokens for a given user using Beanie ODM.
        """
        user = await UserModel.get(user_id)
        if not user:
            return []
            
        return await RefreshTokenModel.find(
            RefreshTokenModel.user.id == user_id,
            RefreshTokenModel.is_revoked == False,
            RefreshTokenModel.expires_at > datetime.utcnow()
        ).to_list()

    async def revoke_session_by_jti(self, user_id: PydanticObjectId, jti: str) -> bool:
        """
        Revokes a specific refresh token by its JTI, ensuring it belongs to the user using Beanie ODM.
        """
        token = await RefreshTokenModel.find_one(
            RefreshTokenModel.jti == jti,
            RefreshTokenModel.user.id == user_id
        )
        
        if token:
            token.is_revoked = True
            await token.save()
            return True
        return False

refresh_token_service = RefreshTokenService() 