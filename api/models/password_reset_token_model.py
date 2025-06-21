from datetime import datetime
from typing import Optional
from beanie import Link
from pymongo import IndexModel

from .base_model import BaseDocument

class PasswordResetTokenModel(BaseDocument):
    """
    Beanie Document for password reset tokens.
    """
    user: Link["UserModel"]
    token_hash: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    
    class Settings:
        name = "password_reset_tokens"  # MongoDB collection name
        indexes = [
            IndexModel([("expires_at", 1)], expireAfterSeconds=0, name="expires_at_ttl"),  # TTL index for automatic expiration
        ] 