from datetime import datetime
from typing import Optional
from bson import ObjectId

from .base_model import BaseDBModel, PyObjectId

class PasswordResetTokenModel(BaseDBModel):
    user_id: PyObjectId
    token_hash: str
    expires_at: datetime
    used_at: Optional[datetime] = None 