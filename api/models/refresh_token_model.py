from datetime import datetime, timezone
from typing import Optional
from pydantic import Field
from beanie import Link
from pymongo import IndexModel

from .base_model import BaseDocument

class RefreshTokenModel(BaseDocument):
    """
    Beanie Document for refresh tokens stored in the database.
    """
    user: Link["UserModel"]
    jti: str
    expires_at: datetime
    is_revoked: bool = False
    
    # Optional device info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    class Settings:
        name = "refresh_tokens"  # MongoDB collection name
        indexes = [
            IndexModel([("jti", 1)], unique=True, name="jti_unique"),  # Unique JTI index
            IndexModel([("expires_at", 1)], expireAfterSeconds=0, name="expires_at_ttl"),  # TTL index for automatic expiration
        ] 