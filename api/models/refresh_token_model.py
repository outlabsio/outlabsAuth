from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional
from pydantic import Field, BaseModel

class RefreshTokenModel(BaseModel):
    """
    Pydantic model for refresh tokens stored in the database.
    """
    id: Optional[ObjectId] = Field(None, alias="_id")
    user_id: ObjectId
    jti: str
    expires_at: datetime
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_revoked: bool = False
    
    # Optional device info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        collection = "refresh_tokens"
        # Indexes ensure fast lookups by jti and automatic cleanup of expired/revoked tokens
        indexes = [
            "jti",
            ("expires_at", {"expireAfterSeconds": 0}),
            ("user_id",),
        ]
        populate_by_name = True
        json_encoders = {ObjectId: str} 