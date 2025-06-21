from datetime import datetime, timezone
from typing import Optional
from pydantic import Field

from .base_model import BaseDBModel, PyObjectId

class RefreshTokenModel(BaseDBModel):
    """
    Pydantic model for refresh tokens stored in the database.
    """
    user_id: PyObjectId
    jti: str
    expires_at: datetime
    is_revoked: bool = False
    
    # Optional device info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config(BaseDBModel.Config):
        collection = "refresh_tokens"
        # Indexes ensure fast lookups by jti and automatic cleanup of expired/revoked tokens
        indexes = [
            "jti",
            ("expires_at", {"expireAfterSeconds": 0}),
            ("user_id",),
        ] 